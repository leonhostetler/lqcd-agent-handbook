#!/usr/bin/env python3
"""Report which handbook leaves an upstream checkout has drifted away from.

Every leaf cites its sources as GitHub blob, commit, or pull-request URLs pinned to a
revision, and records the commit it was observed on. Given a local checkout of a tracked
software, this tool compares those citations with the checkout's HEAD and reports, per
leaf, what moved. It answers two questions:

- forward drift: a file the leaf cites changed between the cited revision and HEAD, and
  which merges touched it;
- the other direction: a commit or pull request the leaf cites from a feature branch has
  since become an ancestor of HEAD, so a claim written against "not yet merged" is stale.

It is a triage, not a review. It names candidates; whether a diff changes a claim is a
reading job. It reports what it checked and never says "passed".

Usage:
    upstream-drift.py --checkout milc=/path/to/milc_qcd [--checkout quda=/path/to/quda]
                      [--root HANDBOOK] [--leaf PATH ...] [--json] [--fail-on-drift]

A checkout name is the handbook's software name; the tool maps it to the repository
recorded in software/<name>/project.yaml and only considers citations into that repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

VERSION = "1.1.0"
KNOWLEDGE_ROOTS = ("conventions", "machines", "software", "ensembles", "playbooks", "modes")

BLOB_RE = re.compile(
    r"https://github\.com/(?P<org>[^/\s]+)/(?P<repo>[^/\s]+)/blob/(?P<rev>[^/\s]+)/"
    r"(?P<path>[^#\s]+)(?:#L(?P<a>\d+)(?:-L(?P<b>\d+))?)?"
)
COMMIT_RE = re.compile(r"https://github\.com/(?P<org>[^/\s]+)/(?P<repo>[^/\s]+)/commit/(?P<sha>[0-9a-fA-F]{7,40})")
PULL_RE = re.compile(r"https://github\.com/(?P<org>[^/\s]+)/(?P<repo>[^/\s]+)/pull/(?P<num>\d+)")
HEX_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} in {repo}: {proc.stderr.strip()}")
    return proc.stdout


def git_ok(repo: Path, *args: str) -> bool:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    return proc.returncode == 0


def resolve(repo: Path, rev: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout.strip() or None


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return git_ok(repo, "merge-base", "--is-ancestor", a, b)


def ancestry(repo: Path, observed: str | None, head: str) -> str:
    """Report ancestry, never a commit distance (ARCHITECTURE.md, version lifetimes)."""
    if observed is None:
        return "no observed commit"
    full = resolve(repo, observed)
    if full is None:
        return "observed commit not in this checkout"
    if full == head:
        return "HEAD is the observed commit"
    if is_ancestor(repo, full, head):
        return "HEAD descends from the observed commit"
    if is_ancestor(repo, head, full):
        return "HEAD is an ancestor of the observed commit"
    return "diverged"


def hunks_touch(repo: Path, rev: str, head: str, path: str, a: int, b: int) -> bool | None:
    """Whether any hunk of rev..HEAD on `path` overlaps old lines [a, b]."""
    try:
        diff = git(repo, "diff", "-U0", rev, head, "--", path)
    except GitError:
        return None
    for line in diff.splitlines():
        m = HUNK_RE.match(line)
        if not m:
            continue
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        # A pure insertion has count 0 and sits after `start`; treat it as touching
        # the cited range when it lands inside it.
        end = start + max(count, 1) - 1
        if start <= b and end >= a:
            return True
    return False


def merges_touching(repo: Path, rev: str, head: str, path: str | None) -> list[str]:
    args = ["log", "--merges", "--first-parent", "--format=%h %s", f"{rev}..{head}"]
    if path:
        args += ["--", path]
    out = git(repo, *args, check=False)
    return [line for line in out.splitlines() if line.strip()]


def merge_of_pull(repo: Path, rng: str, num: str) -> str | None:
    out = git(repo, "log", "--merges", "--format=%h %s", "--grep", f"pull request #{num} ", rng, check=False)
    for line in out.splitlines():
        if re.search(rf"#{num}\b", line):
            return line
    return None


# ---------------------------------------------------------------------------
# Handbook side
# ---------------------------------------------------------------------------

def repo_key(url: str) -> str | None:
    m = re.match(r"https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}".lower()


def software_repositories(root: Path) -> dict[str, str]:
    """software name -> org/repo, from software/<name>/project.yaml."""
    out: dict[str, str] = {}
    for project in sorted((root / "software").glob("*/project.yaml")):
        try:
            data = yaml.safe_load(project.read_text())
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("repository"), str):
            key = repo_key(data["repository"])
            if key:
                out[project.parent.name] = key
    return out


def frontmatter(path: Path) -> dict[str, Any] | None:
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        data = yaml.safe_load(text[4:end])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def is_stack_record(root: Path, path: Path) -> bool:
    """A validated-stack record: machines/<machine>/stacks/<stack>/... .

    Its citations are pinned by design -- it records a build that happened at a commit --
    so upstream movement is not drift for it, and it is skipped unless asked for.
    """
    parts = path.relative_to(root).parts
    return len(parts) >= 4 and parts[0] == "machines" and parts[2] == "stacks"


def leaf_records(root: Path, only: list[str] | None,
                 include_stacks: bool = False) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    for top in KNOWLEDGE_ROOTS:
        base = root / top
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == "INDEX.md":
                continue
            if not include_stacks and is_stack_record(root, path):
                continue
            rel = str(path.relative_to(root))
            if only and not any(rel == o or rel.startswith(o.rstrip("/") + "/") for o in only):
                continue
            if path.suffix == ".md":
                meta = frontmatter(path)
            elif path.suffix in (".yaml", ".yml"):
                try:
                    meta = yaml.safe_load(path.read_text())
                except Exception:
                    meta = None
                if not isinstance(meta, dict):
                    meta = None
            else:
                continue
            if meta and isinstance(meta.get("sources"), list):
                records.append((path, meta))
    return records


def observed_commit(meta: dict[str, Any], name: str) -> str | None:
    software = (meta.get("observed_on") or {}).get("software") or {}
    entry = software.get(name) if isinstance(software, dict) else None
    if isinstance(entry, dict) and isinstance(entry.get("commit"), str):
        return entry["commit"]
    return None


@dataclass
class Finding:
    source: str
    kind: str          # blob | commit | pull
    status: str
    detail: str = ""
    merges: list[str] = field(default_factory=list)
    flag: bool = False


@dataclass
class LeafReport:
    leaf: str
    software: str
    observed: str | None
    ancestry: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return any(f.flag for f in self.findings)


def check_leaf(repo: Path, head: str, name: str, key: str, rel: str, meta: dict[str, Any]) -> LeafReport | None:
    observed = observed_commit(meta, name)
    report = LeafReport(rel, name, observed, ancestry(repo, observed, head))
    observed_full = resolve(repo, observed) if observed else None
    cited_here = False
    for raw in meta["sources"]:
        if not isinstance(raw, str):
            continue
        m = BLOB_RE.search(raw)
        if m and f"{m['org']}/{m['repo']}".lower() == key:
            cited_here = True
            report.findings.append(check_blob(repo, head, observed_full, raw, m))
            continue
        m = COMMIT_RE.search(raw)
        if m and f"{m['org']}/{m['repo']}".lower() == key:
            cited_here = True
            report.findings.append(check_commit(repo, head, observed_full, raw, m["sha"]))
            continue
        m = PULL_RE.search(raw)
        if m and f"{m['org']}/{m['repo']}".lower() == key:
            cited_here = True
            report.findings.append(check_pull(repo, head, observed_full, raw, m["num"]))
    if not cited_here and observed is None:
        return None
    if observed is not None and report.ancestry == "diverged":
        report.findings.append(Finding("observed_on", "observed", "diverged",
                                       "the checkout and the observed commit share no line of descent", flag=True))
    return report


def check_blob(repo: Path, head: str, observed_full: str | None, raw: str, m: re.Match) -> Finding:
    """Drift of one blob citation.

    Drift is measured from the leaf's observed commit when the citation predates it: a
    leaf re-observed at a later commit has already been read against that commit, so what
    matters is what moved since. When the citation is newer than, or equal to, the
    observed commit, the cited revision is the base.
    """
    rev, path = m["rev"], m["path"]
    if not HEX_RE.match(rev):
        return Finding(raw, "blob", "unpinned revision", f"cites {rev!r}, not a commit", flag=True)
    full = resolve(repo, rev)
    if full is None:
        return Finding(raw, "blob", "unresolvable", "cited commit is not in this checkout", flag=True)
    if not is_ancestor(repo, full, head):
        return Finding(raw, "blob", "not an ancestor of HEAD",
                       "the cited revision is on another line of descent", flag=True)
    base, since = full, "the cited revision"
    lines_still_valid = True
    if observed_full and full != observed_full and is_ancestor(repo, full, observed_full):
        base, since = observed_full, "observation"
        # The cited line numbers belong to the cited revision; they still hold at the
        # observed commit only if the file did not change in between.
        lines_still_valid = not git(repo, "diff", "--numstat", full, observed_full, "--", path, check=False).strip()
    if base == head:
        return Finding(raw, "blob", "current", f"{since} is HEAD")
    if not git_ok(repo, "cat-file", "-e", f"{head}:{path}"):
        return Finding(raw, "blob", "removed", "cited file is absent at HEAD",
                       merges_touching(repo, base, head, path), flag=True)
    numstat = git(repo, "diff", "--numstat", base, head, "--", path, check=False).strip()
    if not numstat:
        return Finding(raw, "blob", f"unchanged since {since}", "cited file identical at HEAD")
    merges = merges_touching(repo, base, head, path)
    added, removed = numstat.split()[0], numstat.split()[1]
    if m["a"]:
        a = int(m["a"])
        b = int(m["b"]) if m["b"] else a
        if not lines_still_valid:
            return Finding(raw, "blob", f"file changed since {since}; cited lines predate it",
                           f"L{a}-L{b} are numbered at a revision the file changed after; re-cite",
                           merges, flag=True)
        touched = hunks_touch(repo, base, head, path, a, b)
        if touched:
            return Finding(raw, "blob", f"cited lines changed since {since}",
                           f"L{a}-L{b} overlap a hunk", merges, flag=True)
        return Finding(raw, "blob", f"file changed outside cited lines since {since}",
                       f"L{a}-L{b} untouched; {added}+/{removed}- elsewhere", merges, flag=True)
    return Finding(raw, "blob", f"file changed since {since}", f"{added}+/{removed}-", merges, flag=True)


def check_commit(repo: Path, head: str, observed_full: str | None, raw: str, sha: str) -> Finding:
    full = resolve(repo, sha)
    if full is None:
        return Finding(raw, "commit", "unresolvable", "cited commit is not in this checkout", flag=True)
    on_head = is_ancestor(repo, full, head)
    if not on_head:
        return Finding(raw, "commit", "not merged", "cited commit is not an ancestor of HEAD")
    if observed_full and is_ancestor(repo, full, observed_full):
        return Finding(raw, "commit", "merged before observation", "already an ancestor of the observed commit")
    merges = merges_touching(repo, observed_full or full, head, None) if observed_full else []
    return Finding(raw, "commit", "merged since observation",
                   "the cited commit became an ancestor of HEAD after the leaf's observed commit", merges, flag=True)


def check_pull(repo: Path, head: str, observed_full: str | None, raw: str, num: str) -> Finding:
    if observed_full:
        hit = merge_of_pull(repo, f"{observed_full}..{head}", num)
        if hit:
            return Finding(raw, "pull", "merged since observation", "", [hit], flag=True)
        hit = merge_of_pull(repo, observed_full, num)
        if hit:
            return Finding(raw, "pull", "merged before observation", "", [hit])
    else:
        hit = merge_of_pull(repo, head, num)
        if hit:
            return Finding(raw, "pull", "merged (no observed commit to compare)", "", [hit], flag=True)
    return Finding(raw, "pull", "no merge of this pull request on HEAD",
                   "by merge-commit subject; a squash or rebase merge is invisible here")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def parse_checkouts(items: list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--checkout expects NAME=PATH, got {item!r}")
        name, path = item.split("=", 1)
        repo = Path(path).expanduser().resolve()
        if not git_ok(repo, "rev-parse", "--is-inside-work-tree"):
            raise SystemExit(f"{repo} is not a Git checkout")
        out[name] = repo
    return out


def render(reports: list[LeafReport], checkouts: dict[str, Path], heads: dict[str, str],
           counted: int, sources: int, include_stacks: bool = False) -> str:
    lines: list[str] = []
    for name, repo in checkouts.items():
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD", check=False).strip()
        lines.append(f"{name}: {repo} at {heads[name][:9]} ({branch})")
    flagged = [r for r in reports if r.flagged]
    for r in flagged:
        lines.append("")
        lines.append(f"{r.leaf}  [{r.software}: {r.ancestry}]")
        for f in r.findings:
            if not f.flag:
                continue
            short = f.source if f.kind == "observed" else f.source.split("/blob/")[-1] if f.kind == "blob" else f.source.rsplit("/", 2)[-2] + "/" + f.source.rsplit("/", 1)[-1]
            lines.append(f"  - {f.status}: {short}" + (f"  ({f.detail})" if f.detail else ""))
            for mline in f.merges[:6]:
                lines.append(f"      {mline}")
            if len(f.merges) > 6:
                lines.append(f"      ... {len(f.merges) - 6} more")
    unresolvable = sum(1 for r in reports for f in r.findings if f.status == "unresolvable")
    rollup = by_merge(reports)
    if rollup:
        lines.append("")
        lines.append("merges to review, by the leaves they touch:")
        for (software, merge), leaves in rollup:
            lines.append(f"  {software}: {merge}  -> {len(leaves)} leaf/leaves")
            for leaf in leaves:
                lines.append(f"      {leaf}")
    lines.append("")
    lines.append(
        f"upstream-drift {VERSION}: {counted} leaves with sources read · {sources} citations into "
        f"{len(checkouts)} checkout(s) compared · {len(flagged)} leaves to review · "
        f"{unresolvable} citations unresolvable · "
        f"{'stack records included' if include_stacks else 'stack records skipped'} · claims NOT judged"
    )
    return "\n".join(lines)


def by_merge(reports: list[LeafReport]) -> list[tuple[tuple[str, str], list[str]]]:
    """(software, merge line) -> sorted leaves whose flagged citations that merge touched."""
    table: dict[tuple[str, str], set[str]] = {}
    for r in reports:
        for f in r.findings:
            if not f.flag:
                continue
            for m in f.merges:
                table.setdefault((r.software, m), set()).add(r.leaf)
    return sorted(((k, sorted(v)) for k, v in table.items()), key=lambda kv: (kv[0][0], -len(kv[1]), kv[0][1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=os.environ.get("LQCD_HANDBOOK") or str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--checkout", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--leaf", action="append", help="limit to this handbook path or directory (repeatable)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-drift", action="store_true", help="exit 1 when any leaf is flagged")
    parser.add_argument("--include-stacks", action="store_true",
                        help="also read validated-stack records under machines/*/stacks/, which are skipped by default "
                             "because their citations are pinned to the build they record")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    checkouts = parse_checkouts(args.checkout)
    repos = software_repositories(root)
    for name in checkouts:
        if name not in repos:
            raise SystemExit(f"no software/{name}/project.yaml with a repository under {root}")
    heads = {name: git(repo, "rev-parse", "HEAD").strip() for name, repo in checkouts.items()}

    reports: list[LeafReport] = []
    counted = 0
    sources = 0
    for path, meta in leaf_records(root, args.leaf, args.include_stacks):
        counted += 1
        rel = str(path.relative_to(root))
        for name, repo in checkouts.items():
            report = check_leaf(repo, heads[name], name, repos[name], rel, meta)
            if report is None:
                continue
            sources += sum(1 for f in report.findings if f.kind != "observed")
            if report.findings or report.observed:
                reports.append(report)

    if args.json:
        payload = {
            "version": VERSION,
            "checkouts": {n: {"path": str(p), "head": heads[n]} for n, p in checkouts.items()},
            "leaves": [
                {**asdict(r), "flagged": r.flagged} for r in reports
            ],
            "by_merge": [{"software": k[0], "merge": k[1], "leaves": v} for k, v in by_merge(reports)],
            "summary": {"leaves_read": counted, "citations": sources,
                        "leaves_to_review": sum(1 for r in reports if r.flagged),
                        "stack_records_included": args.include_stacks},
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render(reports, checkouts, heads, counted, sources, args.include_stacks))
    if args.fail_on_drift and any(r.flagged for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
