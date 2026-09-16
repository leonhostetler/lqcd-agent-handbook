#!/usr/bin/env python3
"""Run every check a handbook change proposal owes, in one pass, and report.

`conventions/repeated-work.md` says to automate the step whose failure is *quiet*,
not merely the step that is tedious. This sequence -- diff, regenerate indices, run
the validator, run the suite, scope a privacy review -- was performed by hand nine
times across two sessions, and two of its steps fail silently when skipped:

  * an index left unregenerated passes the eye, because a stale row is
    well-formed and plausible; and
  * a privacy sweep that was never run produces exactly the same output as one
    that found nothing.

The second is the reason this tool reports a *scanned* count rather than only a
verdict. A sweep that reports "0 matches" and a sweep that did not happen are
indistinguishable; one that reports the number of added lines it read cannot be
confused with one that read none. Every step here prints what it examined, not
just what it concluded -- the validator's own summary line, the test count, the
lines scanned -- so a step that quietly did nothing looks different from a step
that found nothing.

**What this tool does not do.** It renders no publication verdict. The validator's
deny list is regular expressions over paths, emails, keys and scheduler accounts;
`PRIVACY.md` also forbids internal hostnames, job identifiers, unpublished results
and live campaign state, and none of those is a pattern. So the privacy step ends
by writing the proposal's added lines to a file and naming the categories a reader
must judge. That is a review surface, deliberately not a gate: a tool that claimed
to clear a proposal for publication would be the worst possible place to be wrong.

It also does not commit, and it does not decide whether the change is correct.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "1.0.0"

#: Categories PRIVACY.md forbids that no regular expression can decide. Printed
#: beside the diff so a reviewer knows what they are looking for; the validator
#: covers the patternable ones and is run separately.
UNPATTERNABLE = (
    "internal hostnames beyond documented public login hosts",
    "job, ticket, or run identifiers",
    "unpublished ensemble parameters or measurements",
    "live campaign state, budgets, ledgers, or raw run evidence",
    "capture or dataset filenames that identify an unpublished run",
)


@dataclass
class Step:
    name: str
    ok: bool
    detail: str


@dataclass
class Report:
    base: str
    head: str
    steps: list[Step] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def changed_files(root: Path, base: str, run=_run) -> list[str]:
    proc = run(["git", "diff", "--name-only", base], root)
    tracked = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], root)
    return sorted(set(tracked) | {ln for ln in untracked.stdout.splitlines() if ln.strip()})


def added_lines(root: Path, base: str, run=_run) -> list[str]:
    """Lines this proposal adds, tracked and untracked alike.

    Untracked files are included deliberately: a new leaf is the most likely place
    for material that should not be published, and `git diff` alone does not see it.
    """
    out: list[str] = []
    proc = run(["git", "diff", "--unified=0", base], root)
    out += [
        ln[1:] for ln in proc.stdout.splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    untracked = run(["git", "ls-files", "--others", "--exclude-standard"], root)
    for rel in untracked.stdout.splitlines():
        if not rel.strip():
            continue
        path = root / rel
        try:
            out += path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
    return out


def regenerate_indices(root: Path, run=_run) -> Step:
    """Regenerate in place and report which indices moved.

    In place rather than check-only: a stale index is always a defect in the
    proposal and never a decision, so the useful output is the corrected file plus
    a loud statement that the author must include it.
    """
    before = {p: p.read_bytes() for p in sorted(root.glob("*/INDEX.md"))}
    proc = run([sys.executable, "tools/build-index.py"], root)
    if proc.returncode != 0:
        return Step("indices", False, f"build-index.py failed: {proc.stderr.strip()[:400]}")
    moved = [
        str(p.relative_to(root)) for p in sorted(root.glob("*/INDEX.md"))
        if before.get(p) != p.read_bytes()
    ]
    if moved:
        return Step(
            "indices", False,
            "regenerated and CHANGED: " + ", ".join(moved)
            + " — they were stale; include them in the proposal and re-run",
        )
    return Step("indices", True, f"{len(before)} generated indices already current")


def run_validator(root: Path, run=_run) -> Step:
    """Run the validator and report its own summary line.

    The summary goes to stdout and the P2 advisories go to stderr, so reading the
    last stderr line reports a warning about some unrelated file as though it were
    the result. The first draft of this function did exactly that.
    """
    proc = run(["./tools/run-validator"], root)
    if proc.returncode != 0:
        errs = [ln for ln in proc.stderr.splitlines() if ln.lstrip().startswith("error")]
        tail = (proc.stderr.strip().splitlines() or [""])[-1]
        return Step("validator", False, f"{len(errs)} error(s); last line: {tail[:300]}")
    summary = (proc.stdout.strip().splitlines() or [""])[-1]
    if not summary:
        return Step("validator", False, "validator exited 0 but printed no summary")
    # 400, not 300: the summary ends with "publishability NOT checked", and truncating
    # that away would leave the harness reporting a clean validator run with the one
    # phrase §validator-not-clearance exists for removed.
    return Step("validator", True, summary[:400])


def run_suite(root: Path, run=_run) -> Step:
    proc = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], root)
    tail = [ln for ln in proc.stderr.strip().splitlines() if ln.startswith("Ran ")]
    ran = tail[-1] if tail else "no test count reported"
    if proc.returncode != 0:
        return Step("suite", False, f"{ran}; FAILED")
    return Step("suite", True, ran)


def privacy_surface(root: Path, lines: list[str], out_path: Path | None) -> Step:
    """Write the proposal's added lines somewhere a reviewer can read them.

    Reports the count, so a sweep that did not run is distinguishable from one that
    found nothing -- which is the failure this step exists for.
    """
    if out_path is not None:
        out_path.write_text("\n".join(lines) + ("\n" if lines else ""))
    where = f" → {out_path}" if out_path is not None else ""
    if not lines:
        return Step("privacy-surface", True, "no added lines in this proposal")
    return Step(
        "privacy-surface", True,
        f"{len(lines)} added lines written for review{where}; "
        f"judge by hand: {'; '.join(UNPATTERNABLE)}",
    )


def build_report(root: Path, base: str, out_path: Path | None, run=_run) -> Report:
    head = run(["git", "rev-parse", "--short", "HEAD"], root).stdout.strip()
    report = Report(base=base, head=head)
    files = changed_files(root, base, run)
    report.steps.append(
        Step("diff", True, f"{len(files)} changed file(s): " + ", ".join(files[:12])
             + (" …" if len(files) > 12 else ""))
    )
    report.steps.append(regenerate_indices(root, run))
    report.steps.append(run_validator(root, run))
    report.steps.append(run_suite(root, run))
    report.steps.append(privacy_surface(root, added_lines(root, base, run), out_path))
    return report


def render(report: Report) -> str:
    out = [
        f"change proposal · propose-change {VERSION} · base {report.base} · HEAD {report.head}",
        "",
    ]
    for s in report.steps:
        out.append(f"  [{'ok ' if s.ok else 'FAIL'}] {s.name:16s} {s.detail}")
    out.append("")
    out.append(
        "all mechanical checks passed — publication clearance NOT granted; "
        "the privacy surface above is for a human decision"
        if report.ok else
        "PROPOSAL NOT READY — fix the FAIL lines above and re-run"
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.environ.get("LQCD_HANDBOOK"),
                    help="handbook root (default: $LQCD_HANDBOOK)")
    ap.add_argument("--base", default="HEAD", help="git ref the proposal is against")
    ap.add_argument("--added-lines-out", default=None,
                    help="write the proposal's added lines here for privacy review")
    args = ap.parse_args(argv)
    if not args.root:
        print("error: --root or $LQCD_HANDBOOK required", file=sys.stderr)
        return 2
    root = Path(args.root).resolve()
    if not (root / ".git").exists():
        print(f"error: {root} is not a git repository", file=sys.stderr)
        return 2
    out = Path(args.added_lines_out).resolve() if args.added_lines_out else None
    report = build_report(root, args.base, out)
    print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
