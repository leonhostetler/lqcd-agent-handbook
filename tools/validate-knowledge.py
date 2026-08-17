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


def validate_observed_on(
    value: Any,
    rel: Path,
    errors: list[str],
    *,
    scope: Any = None,
    expected_machine: str | None = None,
    expected_software: str | None = None,
) -> None:
    if not isinstance(value, dict) or not value:
        errors.append(f"{rel}: observed_on must be a non-empty mapping")
        return

    scoped_machines: set[str] = set()
    scoped_software: set[str] = set()
    if isinstance(scope, list):
        for item in scope:
            if not isinstance(item, str) or ":" not in item:
                continue
            axis, name = item.split(":", 1)
            if axis == "machine" and name:
                scoped_machines.add(name)
            elif axis == "software" and name:
                scoped_software.add(name)

    if expected_machine:
        scoped_machines.add(expected_machine)
    if expected_software:
        scoped_software.add(expected_software)

    for machine in sorted(scoped_machines):
        if value.get("machine") != machine:
            errors.append(
                f"{rel}: observed_on.machine must equal scoped machine {machine!r}"
            )

    software = value.get("software")
    if scoped_software and not isinstance(software, dict):
        errors.append(f"{rel}: observed_on.software must be a mapping")
        return
    if not isinstance(software, dict):
        return

    for name in sorted(scoped_software):
        if name not in software:
            errors.append(f"{rel}: observed_on.software is missing {name!r}")

    for name, context in sorted(software.items(), key=lambda item: str(item[0])):
        if not isinstance(name, str) or not isinstance(context, dict):
            errors.append(f"{rel}: observed_on.software entries must be named mappings")
            continue
        commit = context.get("commit")
        branch = context.get("branch")
        if not isinstance(commit, str) or not commit:
            errors.append(
                f"{rel}: observed_on.software.{name}.commit must be a non-empty string"
            )
        if not isinstance(branch, str) or not branch:
            errors.append(
                f"{rel}: observed_on.software.{name}.branch must be a non-empty string"
            )
        elif branch != "develop":
            fork = context.get("forked_from_develop")
            if not isinstance(fork, str) or not fork:
                errors.append(
                    f"{rel}: observed_on.software.{name}.forked_from_develop "
                    "is required off develop"
                )


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
            if isinstance(instance, dict):
                rel = path.relative_to(root)
                if schema_name == "machine.schema.json":
                    validate_observed_on(
                        instance.get("observed_on"),
                        rel,
                        errors,
                        expected_machine=instance.get("name"),
                    )
                elif schema_name == "project.schema.json":
                    validate_observed_on(
                        instance.get("observed_on"),
                        rel,
                        errors,
                        expected_software=instance.get("name"),
                    )
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
            validate_observed_on(
                observed_on, rel, errors, scope=meta.get("scope")
            )
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


def validate_frontends(root: Path, errors: list[str]) -> int:
    config = load_yaml(root / "handbook.yaml")
    launcher = config.get("launcher", {}) if isinstance(config, dict) else {}
    if not isinstance(launcher, dict):
        errors.append("handbook.yaml: launcher must be a mapping")
        return 0

    common_fields: dict[str, str] = {}
    for field in ("handbook_env", "launched_env", "frontend_env"):
        value = launcher.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"handbook.yaml: launcher.{field} must be a non-empty string")
        else:
            common_fields[field] = value

    startup_prompt_value = launcher.get("startup_prompt")
    startup_prompt_path: Path | None = None
    if not isinstance(startup_prompt_value, str) or not startup_prompt_value:
        errors.append("handbook.yaml: launcher.startup_prompt must be a non-empty string")
    else:
        startup_prompt_relative = Path(startup_prompt_value)
        if startup_prompt_relative.is_absolute() or ".." in startup_prompt_relative.parts:
            errors.append(
                "handbook.yaml: launcher.startup_prompt must stay inside the repository"
            )
        else:
            candidate = root / startup_prompt_relative
            if not candidate.is_file():
                errors.append(
                    "handbook.yaml: launcher.startup_prompt does not exist: "
                    f"{startup_prompt_value}"
                )
            elif not candidate.read_text().strip():
                errors.append(
                    f"{startup_prompt_value}: launcher startup prompt must not be empty"
                )
            else:
                startup_prompt_path = candidate

    frontends = launcher.get("frontends")
    if not isinstance(frontends, dict) or not frontends:
        errors.append("handbook.yaml: launcher.frontends must be a non-empty mapping")
        return 0

    tier = config.get("tier_0", {}) if isinstance(config, dict) else {}
    canonical = tier.get("canonical_entrypoint") if isinstance(tier, dict) else None
    mirrors = tier.get("mirrors", []) if isinstance(tier, dict) else []
    allowed_entrypoints = {
        value for value in [canonical, *mirrors] if isinstance(value, str)
    }
    shared_playbook = root / "playbooks/start-session.md"
    try:
        shared_text = shared_playbook.read_text()
    except OSError as exc:
        errors.append(f"playbooks/start-session.md cannot be read: {exc}")
        shared_text = ""

    required = (
        "executable",
        "entrypoint",
        "skill",
        "preflight",
        "complete_loading_env",
    )
    checked = 0
    for frontend, raw_spec in sorted(frontends.items(), key=lambda item: str(item[0])):
        checked += 1
        prefix = f"launcher.frontends.{frontend}"
        if not isinstance(frontend, str) or not frontend:
            errors.append("handbook.yaml: frontend names must be non-empty strings")
            continue
        if not isinstance(raw_spec, dict):
            errors.append(f"handbook.yaml: {prefix} must be a mapping")
            continue

        spec: dict[str, str] = {}
        for field in required:
            value = raw_spec.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"handbook.yaml: {prefix}.{field} must be a non-empty string")
            else:
                spec[field] = value
        if len(spec) != len(required):
            continue

        paths: dict[str, Path] = {}
        for field in ("executable", "entrypoint", "skill", "preflight"):
            relative = Path(spec[field])
            if relative.is_absolute() or ".." in relative.parts:
                errors.append(f"handbook.yaml: {prefix}.{field} must stay inside the repository")
                continue
            path = root / relative
            if not path.is_file():
                errors.append(f"handbook.yaml: {prefix}.{field} does not exist: {spec[field]}")
                continue
            paths[field] = path

        executable = paths.get("executable")
        if executable is not None and executable.stat().st_mode & 0o111 == 0:
            errors.append(f"{spec['executable']}: frontend launcher is not executable")
        if spec["entrypoint"] not in allowed_entrypoints:
            errors.append(
                f"handbook.yaml: {prefix}.entrypoint is not the canonical entrypoint "
                "or a declared mirror"
            )

        expected_by_file = {
            "executable": [
                common_fields.get("handbook_env"),
                common_fields.get("launched_env"),
                common_fields.get("frontend_env"),
                spec["complete_loading_env"],
                f"{common_fields.get('frontend_env')}={frontend}",
                startup_prompt_value if isinstance(startup_prompt_value, str) else None,
                spec["entrypoint"],
                spec["skill"],
            ],
            "preflight": [
                common_fields.get("launched_env"),
                common_fields.get("frontend_env"),
                spec["complete_loading_env"],
                spec["entrypoint"],
                spec["skill"],
            ],
            "skill": [
                spec["executable"],
                spec["complete_loading_env"],
                spec["preflight"],
            ],
        }
        for field, tokens in expected_by_file.items():
            path = paths.get(field)
            if path is None:
                continue
            text = path.read_text()
            for token in tokens:
                if token and token not in text:
                    errors.append(
                        f"{spec[field]}: missing manifest token {token!r} for {frontend}"
                    )
        if spec["preflight"] not in shared_text:
            errors.append(
                f"playbooks/start-session.md: missing {frontend} preflight "
                f"{spec['preflight']!r}"
            )
    if startup_prompt_path is not None:
        prompt_text = startup_prompt_path.read_text()
        if "lqcd-start-session" not in prompt_text:
            errors.append(
                f"{startup_prompt_value}: startup prompt must invoke lqcd-start-session"
            )
    return checked


def validate_session_logging(root: Path, errors: list[str]) -> int:
    config = load_yaml(root / "handbook.yaml")
    logging = config.get("session_logging", {}) if isinstance(config, dict) else {}
    if not isinstance(logging, dict):
        errors.append("handbook.yaml: session_logging must be a mapping")
        return 0

    paths: dict[str, Path] = {}
    for field in ("runner", "checker", "installer", "playbook"):
        value = logging.get(field)
        if not isinstance(value, str) or not value:
            errors.append(
                f"handbook.yaml: session_logging.{field} must be a non-empty string"
            )
            continue
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(
                f"handbook.yaml: session_logging.{field} must stay inside the repository"
            )
            continue
        path = root / relative
        if not path.is_file():
            errors.append(
                f"handbook.yaml: session_logging.{field} does not exist: {value}"
            )
            continue
        paths[field] = path

    launcher = config.get("launcher", {}) if isinstance(config, dict) else {}
    launcher_frontends = (
        launcher.get("frontends", {}) if isinstance(launcher, dict) else {}
    )
    frontends = logging.get("frontends")
    if not isinstance(frontends, dict) or not frontends:
        errors.append(
            "handbook.yaml: session_logging.frontends must be a non-empty mapping"
        )
        return len(paths)
    if isinstance(launcher_frontends, dict) and set(frontends) != set(
        launcher_frontends
    ):
        errors.append(
            "handbook.yaml: session_logging.frontends must match launcher.frontends"
        )

    logger_paths: dict[str, Path] = {}
    for frontend, spec in sorted(frontends.items(), key=lambda item: str(item[0])):
        prefix = f"session_logging.frontends.{frontend}"
        if not isinstance(spec, dict):
            errors.append(f"handbook.yaml: {prefix} must be a mapping")
            continue
        value = spec.get("logger")
        if not isinstance(value, str) or not value:
            errors.append(f"handbook.yaml: {prefix}.logger must be a non-empty string")
            continue
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"handbook.yaml: {prefix}.logger must stay inside the repository")
            continue
        path = root / relative
        if not path.is_file():
            errors.append(f"handbook.yaml: {prefix}.logger does not exist: {value}")
            continue
        logger_paths[str(frontend)] = path

    for field in ("runner", "checker", "installer"):
        path = paths.get(field)
        if path is not None and path.stat().st_mode & 0o111 == 0:
            errors.append(f"{path.relative_to(root)}: session-logging tool is not executable")
    for path in logger_paths.values():
        if path.stat().st_mode & 0o111 == 0:
            errors.append(f"{path.relative_to(root)}: session logger is not executable")

    startup = root / "playbooks/start-session.md"
    logging_playbook = paths.get("playbook")
    if startup.is_file():
        startup_text = startup.read_text()
        for field in ("runner", "checker", "playbook"):
            value = logging.get(field)
            if isinstance(value, str) and value not in startup_text:
                errors.append(
                    f"playbooks/start-session.md: missing session_logging.{field} "
                    f"token {value!r}"
                )
    if logging_playbook is not None:
        playbook_text = logging_playbook.read_text()
        tokens = [logging.get("runner"), logging.get("installer")]
        tokens.extend(
            spec.get("logger")
            for spec in frontends.values()
            if isinstance(spec, dict)
        )
        for token in tokens:
            if isinstance(token, str) and token not in playbook_text:
                errors.append(
                    f"{logging_playbook.relative_to(root)}: missing logging asset "
                    f"token {token!r}"
                )
    return len(paths) + len(logger_paths)


def validate_tier_zero(root: Path, errors: list[str]) -> tuple[int, int]:
    config = load_yaml(root / "handbook.yaml")
    tier = config.get("tier_0", {}) if isinstance(config, dict) else {}
    canonical_name = tier.get("canonical_entrypoint")
    mirror_names = tier.get("mirrors", [])
    names = tier.get("files", [])
    if not isinstance(canonical_name, str):
        raise ValueError("tier_0.canonical_entrypoint must be a path")
    if not isinstance(mirror_names, list) or not all(
        isinstance(name, str) for name in mirror_names
    ):
        raise ValueError("tier_0.mirrors must be a list of paths")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("tier_0.files must be a list of paths")

    canonical = root / canonical_name
    canonical_bytes = canonical.read_bytes()
    if canonical_name not in names:
        errors.append(f"canonical entrypoint {canonical_name} is not a Tier-0 file")
    for mirror_name in mirror_names:
        mirror = root / mirror_name
        try:
            mirror_bytes = mirror.read_bytes()
        except OSError as exc:
            errors.append(f"entrypoint mirror {mirror_name} cannot be read: {exc}")
            continue
        if mirror_bytes != canonical_bytes:
            errors.append(
                f"{mirror_name} differs from canonical entrypoint {canonical_name}; "
                "run tools/sync-agent-entrypoints.py"
            )

    total = sum((root / name).stat().st_size for name in names)
    maximum = int(tier.get("max_combined_bytes", 0))
    entrypoint_size = len(canonical_bytes)
    entrypoint_max = int(tier.get("max_entrypoint_bytes", 0))
    if total > maximum:
        errors.append(f"Tier 0 is {total} bytes; limit is {maximum}")
    if entrypoint_size > entrypoint_max:
        errors.append(
            f"{canonical_name} is {entrypoint_size} bytes; limit is {entrypoint_max}"
        )
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
    frontend_count = validate_frontends(root, errors)
    logging_count = validate_session_logging(root, errors)
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
            f"{privacy_count} text files · {frontend_count} frontend adapters · "
            f"{logging_count} session-logging assets · "
            f"{reference_count} references · "
            f"Tier 0 {tier_bytes}/{tier_limit} bytes · publishability NOT checked",
            file=sys.stderr,
        )
        return 1

    print(
        f"no deny-list matches · {schema_count} schema objects valid · "
        f"{provenance_count} provenance records complete · "
        f"{frontend_count} frontend adapters valid · "
        f"{logging_count} session-logging assets valid · "
        f"{reference_count} references resolved · "
        f"Tier 0 {tier_bytes}/{tier_limit} bytes · publishability NOT checked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
