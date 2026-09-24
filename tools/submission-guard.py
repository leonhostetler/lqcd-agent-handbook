#!/usr/bin/env python3
"""Decide whether a batch-script submission may proceed. Runs as a PreToolUse hook.

Reads the frontend's hook event on stdin (JSON with `tool_name`, `tool_input.command` and
`cwd`), and does nothing unless the command invokes a submit command recorded in
`conventions/scheduler-surfaces.yaml`. For a submission it resolves the script from the
command line and refuses unless ALL of:

  1. `tools/check-batch-script.py` reports zero errors for the script, against the machine
     profile when the machine can be detected;
  2. a receipt written by `tools/dry-run-batch-script.py` sits beside the script, its
     recorded sha256 matches the script as it is now, its positive control passed, and at
     least one negative test against that same text fired.

Refusal is exit status 2 with the reason on stderr, which is how a PreToolUse hook blocks a
tool call. Anything else is exit 0 and silence. The hook shim that invokes this fails CLOSED
in a handbook session: if this tool cannot run, the submission is refused rather than waved
through, because a guard that allows when broken is not a guard.

The failure this exists to stop cost a two-day queue wait: a launcher that had passed a
private dry run died in ten seconds on an assumption the machine did not share. Every one of
its causes -- job-directory resolution, an unmodelled scheduler variable, a harness that could
not run the campaign tool -- is decidable before the submit command is typed, and the human
review steps that were supposed to decide them are exactly the steps that erode under time
pressure. This tool does not erode.

Deliberately NOT here: budget and account checks (they live in the working-directory ledger,
whose format the handbook ships but whose numbers it never holds), and any override switch.
An operator who must submit an unchecked script does so from their own shell.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import shlex
import subprocess
import sys

HANDBOOK = pathlib.Path(__file__).resolve().parents[1]
MIN_HARNESS_VERSION = (1, 0, 0)

_spec = importlib.util.spec_from_file_location("check_batch_script",
                                               HANDBOOK / "tools" / "check-batch-script.py")
_CBS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_CBS)


def submit_commands() -> set[str]:
    import yaml  # the runner guarantees this
    surfaces = yaml.safe_load((HANDBOOK / "conventions" / "scheduler-surfaces.yaml").read_text())
    return {str(s["submit_command"]) for s in surfaces["surfaces"].values() if s.get("submit_command")}


def detect_machine(explicit: str | None) -> str | None:
    if explicit:
        return None if explicit == "unknown" else explicit
    env = os.environ.get("LQCD_MACHINE")
    if env:
        return None if env == "unknown" else env
    detector = HANDBOOK / "tools" / "detect-machine.sh"
    try:
        proc = subprocess.run(["bash", str(detector)], text=True, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    name = proc.stdout.strip()
    return None if (proc.returncode != 0 or not name or name == "unknown") else name


def find_script(tokens: list[str], submit: str, cwd: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """The script a submit command names, or (None, reason)."""
    try:
        at = tokens.index(submit)
    except ValueError:
        return None, "submit command not found in the tokenised command"
    rest = tokens[at + 1:]
    for stop in ("&&", "||", ";", "|"):
        if stop in rest:
            rest = rest[:rest.index(stop)]
    if any(t == "--wrap" or t.startswith("--wrap=") for t in rest):
        return None, "a --wrap submission has no script to check; write the script"
    found = []
    for token in rest:
        if token.startswith("-"):
            continue
        candidate = pathlib.Path(token)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        if candidate.is_file():
            found.append(candidate.resolve())
    if not found:
        return None, ("no existing file named on the command line resolves to the script; submit "
                      "by absolute path")
    if len(found) > 1:
        return None, f"more than one existing file on the command line: {', '.join(map(str, found))}"
    return found[0], ""


def version_tuple(text) -> tuple:
    try:
        return tuple(int(p) for p in str(text).split("."))
    except ValueError:
        return ()


def receipt_problems(script: pathlib.Path) -> list[str]:
    path = script.with_name(script.name + ".dry-run-receipt.json")
    if not path.is_file():
        return [f"no dry-run receipt at {path.name}; run tools/run-dry-run-batch-script on the script"]
    try:
        receipt = json.loads(path.read_text())
    except ValueError:
        return [f"{path.name} is not valid JSON"]
    problems = []
    if receipt.get("script_sha256") != file_sha256(script):
        problems.append("the receipt was written for a different version of the script; "
                        "re-run the dry run on the script as it is now")
        return problems
    if version_tuple(receipt.get("harness_version")) < MIN_HARNESS_VERSION:
        problems.append(f"receipt harness version {receipt.get('harness_version')!r} predates "
                        f"{'.'.join(map(str, MIN_HARNESS_VERSION))}")
    positive = receipt.get("positive") or {}
    if not positive.get("passed"):
        problems.append("the positive control did not pass (or was never run) on this script text")
    negatives = [n for n in receipt.get("negatives") or [] if n.get("fired")]
    if not negatives:
        problems.append("no negative test has fired against this script text; a guard that was "
                        "never made to fire is not a guard (batch-scripts.md step 9)")
    return problems


def file_sha256(path: pathlib.Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decide(event: dict, machine_arg: str | None) -> tuple[int, str]:
    # Any tool whose input carries a shell command line is a shell tool, whatever the
    # frontend calls it: both verified frontends report the canonical name "Bash", and
    # keying on the name would let a differently named shell tool through silently.
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return 0, ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    submits = submit_commands()
    hit = next((t for t in tokens if t in submits), None)
    if hit is None:
        return 0, ""
    cwd = pathlib.Path(event.get("cwd") or os.getcwd())
    script, reason = find_script(tokens, hit, cwd)
    if script is None:
        return 2, f"submission refused: {reason}"

    problems = []
    machine = detect_machine(machine_arg)
    errors, _, _ = _CBS.check(script, machine)
    for number, message in errors:
        where = f"{script.name}:{number}" if number else script.name
        problems.append(f"checker error at {where}: {message}")
    problems.extend(receipt_problems(script))
    if not problems:
        return 0, ""
    lines = [f"submission refused for {script}:"]
    lines += [f"  - {p}" for p in problems]
    if machine is None:
        lines.append("  (machine not detected, so the checker's directive checks were skipped; "
                     "set LQCD_MACHINE or run on a profiled machine)")
    lines.append("  See conventions/batch-scripts.md, 'Review before submission'.")
    return 2, "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="PreToolUse submission guard (reads the hook event on stdin)")
    ap.add_argument("--machine", help="override machine detection (tests)")
    ap.add_argument("--event-file", type=pathlib.Path, help="read the event from a file instead of stdin")
    args = ap.parse_args(argv)
    raw = args.event_file.read_text() if args.event_file else sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        print("submission guard: the hook event is not valid JSON; refusing", file=sys.stderr)
        return 2
    if not isinstance(event, dict):
        event = {}
    rc, message = decide(event, args.machine)
    if message:
        print(message, file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
