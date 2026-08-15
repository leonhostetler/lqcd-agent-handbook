#!/usr/bin/env python3
"""Validate handbook schemas, provenance, privacy patterns, references, and Tier 0."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:  # pragma: no cover - environment failure
    raise SystemExit(f"validator dependency missing: {exc}; install PyYAML and jsonschema")

EVIDENCE = {"source", "docs", "observed", "reproduced", "experiment", "operator", "inferred"}
KNOWLEDGE_ROOTS = {"conventions", "machines", "software", "ensembles"}
LONG_DOCS = ("ARCHITECTURE.md", "ROADMAP.md")
ANCHOR_RE = re.compile(r'<a\s+id="([a-z0-9][a-z0-9-]*)"\s*></a>')
LINK_RE = re.compile(r'\[([^\]]+)\]\((?:(ARCHITECTURE|ROADMAP)\.md)?#([a-z0-9][a-z0-9-]*)\)')
BARE_SECTION_RE = re.compile(r'§([a-z][a-z0-9-]*)')

DENY_PATTERNS = {
    "user-specific home path": re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/"),
    "user-specific HPC home path": re.compile(r"/global/homes/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/"),
    "allocation-specific project path": re.compile(r"/lustre/orion/[A-Za-z0-9._-]+/"),
    "local Dropbox path": re.compile(r"(?:~/|/(?:home|Users)/[^/]+/)Dropbox/"),
    "email address": re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "literal secret assignment": re.compile(r"(?i)\b(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_+/=-]{12,}"),
    "literal scheduler account": re.compile(r"(?:--account(?:=|\s+)|#PBS\s+-A\s+)(?![<$])[A-Za-z][A-Za-z0-9_-]{2,}"),
}


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except Exception as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc


def frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        data = yaml.safe_load(text[4:end])
    except Exception as exc:
        raise ValueError(f"{path}: invalid frontmatter YAML: {exc}") from exc
    return data if isinstance(data, dict) else None


def has_version_anchor(value: Any, key: str = "") -> bool:
    anchor_keys = {"commit", "branch", "version", "toolchain", "module", "revision", "documentation_version"}
    if key.lower() in anchor_keys and value not in (None, "", [], {}):
        return True
    if isinstance(value, dict):
        return any(has_version_anchor(v, str(k)) for k, v in value.items())
    if isinstance(value, list):
        return any(has_version_anchor(v, key) for v in value)
    return False


def validate_iso_date(
    value: Any, field: str, rel: Path, errors: list[str]
) -> dt.date | None:
    if not isinstance(value, str):
        errors.append(f"{rel}: {field} must be a quoted ISO date string (YYYY-MM-DD)")
        return None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        errors.append(f"{rel}: {field} is not an ISO date (YYYY-MM-DD)")
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        errors.append(f"{rel}: {field} is not an ISO date (YYYY-MM-DD)")
        return None


def iter_repo_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name.startswith("session_") and path.suffix == ".log":
            continue
        yield path


def validate_schemas(root: Path, errors: list[str]) -> int:
    schema_dir = root / "schemas"
    loaded: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_dir.glob("*.schema.json")):
        try:
            schema = json.loads(path.read_text())
            Draft202012Validator.check_schema(schema)
            loaded[path.name] = schema
        except Exception as exc:
            errors.append(f"{path.relative_to(root)}: invalid JSON schema: {exc}")

    bindings = [
        ("machines/**/machine.yaml", "machine.schema.json"),
        ("software/**/project.yaml", "project.schema.json"),
    ]
    checked = 0
    for pattern, schema_name in bindings:
        schema = loaded.get(schema_name)
        if schema is None:
            continue
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for path in root.glob(pattern):
            checked += 1
            try:
                instance = load_yaml(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            for problem in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
                where = ".".join(str(part) for part in problem.absolute_path) or "<root>"
                errors.append(f"{path.relative_to(root)}:{where}: {problem.message}")
    return len(loaded) + checked


def validate_provenance(root: Path, errors: list[str], warnings: list[str]) -> int:
    required = {"title", "summary", "scope", "load_when", "evidence", "observed", "observed_on"}
    checked = 0
    today = dt.date.today()
    for top in sorted(KNOWLEDGE_ROOTS):
        base = root / top
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            if path.name == "INDEX.md":
                continue
            checked += 1
            try:
                meta = frontmatter(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            rel = path.relative_to(root)
            if meta is None:
                errors.append(f"{rel}: missing YAML frontmatter")
                continue
            missing = sorted(required - meta.keys())
            if missing:
                errors.append(f"{rel}: missing provenance keys: {', '.join(missing)}")
            if "observed" in meta:
                validate_iso_date(meta["observed"], "observed", rel, errors)
            kind = meta.get("evidence")
            if kind not in EVIDENCE:
                errors.append(f"{rel}: illegal evidence value {kind!r}")
            if kind == "reproduced" and not isinstance(meta.get("observations"), int):
                errors.append(f"{rel}: evidence reproduced requires integer observations")
            if kind == "reproduced" and isinstance(meta.get("observations"), int) and meta["observations"] < 2:
                errors.append(f"{rel}: reproduced observations must be at least 2")
            if kind == "observed" and "incidents" not in rel.parts:
                errors.append(f"{rel}: evidence observed is allowed only under incidents/")
            observed_on = meta.get("observed_on")
            if not isinstance(observed_on, dict) or not observed_on:
                errors.append(f"{rel}: observed_on must be a non-empty mapping")
            anchored = has_version_anchor(observed_on)
            review = meta.get("review_by")
            if not anchored and review is None:
                errors.append(f"{rel}: review_by is required when observed_on has no version anchor")
            if anchored and review is not None:
                errors.append(f"{rel}: review_by must be omitted when observed_on has a version anchor")
            if review is not None:
                review_date = validate_iso_date(review, "review_by", rel, errors)
                if review_date is not None and review_date < today:
                    warnings.append(f"{rel}: review_by {review_date} is in the past")
    return checked


def validate_privacy(root: Path, errors: list[str]) -> int:
    checked = 0
    for path in iter_repo_files(root):
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        checked += 1
        for label, pattern in DENY_PATTERNS.items():
            for match in pattern.finditer(text):
                excerpt = match.group(0)
                if "<" in excerpt or "$" in excerpt:
                    continue
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{path.relative_to(root)}:{line}: deny-list match ({label})")
    return checked


def validate_references(root: Path, errors: list[str]) -> int:
    texts = {name: (root / name).read_text() for name in LONG_DOCS}
    anchors = {name: set(ANCHOR_RE.findall(text)) for name, text in texts.items()}
    all_anchors = set().union(*anchors.values())
    checked = 0
    for name, text in texts.items():
        for visible, target_stem, slug in LINK_RE.findall(text):
            checked += 1
            target = f"{target_stem}.md" if target_stem else name
            if slug not in anchors.get(target, set()):
                errors.append(f"{name}: unresolved cross-reference {target}#{slug}")
            if visible.startswith("§") and visible[1:] != slug:
                errors.append(f"{name}: link label {visible!r} does not match #{slug}")
        stripped = LINK_RE.sub("", text)
        for slug in BARE_SECTION_RE.findall(stripped):
            checked += 1
            if slug not in all_anchors:
                errors.append(f"{name}: unresolved bare section reference §{slug}")
    return checked


def validate_tier_zero(root: Path, errors: list[str]) -> tuple[int, int]:
    config = load_yaml(root / "handbook.yaml")
    tier = config.get("tier_0", {}) if isinstance(config, dict) else {}
    names = tier.get("files", [])
    total = sum((root / name).stat().st_size for name in names)
    maximum = int(tier.get("max_combined_bytes", 0))
    claude_size = (root / "CLAUDE.md").stat().st_size
    claude_max = int(tier.get("max_claude_md_bytes", 0))
    if total > maximum:
        errors.append(f"Tier 0 is {total} bytes; limit is {maximum}")
    if claude_size > claude_max:
        errors.append(f"CLAUDE.md is {claude_size} bytes; limit is {claude_max}")
    return total, maximum


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    schema_count = validate_schemas(root, errors)
    provenance_count = validate_provenance(root, errors, warnings)
    privacy_count = validate_privacy(root, errors)
    reference_count = validate_references(root, errors)
    try:
        tier_bytes, tier_limit = validate_tier_zero(root, errors)
    except Exception as exc:
        errors.append(f"Tier-0 configuration error: {exc}")
        tier_bytes, tier_limit = 0, 0

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            f"checked: {schema_count} schema objects · {provenance_count} knowledge files · "
            f"{privacy_count} text files · {reference_count} references · "
            f"Tier 0 {tier_bytes}/{tier_limit} bytes · publishability NOT checked",
            file=sys.stderr,
        )
        return 1

    print(
        f"no deny-list matches · {schema_count} schema objects valid · "
        f"{provenance_count} provenance records complete · {reference_count} references resolved · "
        f"Tier 0 {tier_bytes}/{tier_limit} bytes · publishability NOT checked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
