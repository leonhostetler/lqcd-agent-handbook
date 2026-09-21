#!/usr/bin/env python3
"""Advisory lint for batch submission scripts.

This is a lint, not a sandbox. It cannot stop a script being written unchecked,
and it cannot decide the questions that matter most: whether a writable root was
genuinely approved, whether an invoked program is safe, or what the author meant.
Those stay with the reviewer, and `conventions/batch-scripts.md` owns the rules.

What it does decide is mechanical: whether the script submits another job, whether
it names a destructive operation, whether it hardens itself, and -- given a machine
profile -- whether it pins the directives whose defaults are unsafe. Scheduler
directive and option names come from conventions/scheduler-surfaces.yaml, keyed by
the profile's scheduler type, so this tool carries no scheduler knowledge of its own.

It never prints the value of an account option. Allocation codes are deny-listed,
and a lint that echoed one into a log that later gets committed would breach the
rule it exists to enforce.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - the runner guarantees this
    sys.exit("check-batch-script requires PyYAML; invoke it through tools/run-validator's dispatcher")

HANDBOOK = pathlib.Path(__file__).resolve().parents[1]
SURFACES = HANDBOOK / "conventions" / "scheduler-surfaces.yaml"

# An application fed its input on stdin cannot be checked by this lint: whether that
# input parses is a question only the application answers. The warning exists because
# the answer is cheap and the omission is expensive -- one campaign lost a two-day
# queue wait and its only authorised submission to a misplaced comment line. Note the
# limit: a script passing its input as argv rather than on stdin is NOT detected here.
STDIN_REDIRECT = re.compile(r"<\s*[\"']?\$?[\w{}./$-]+\.(?:inp|in|input)\b")

# Destructive operations. Illustrative, not exhaustive -- the leaf says so, and so
# does this list: absence from it is an oversight, never permission. Each entry is
# (regex, human description).
DESTRUCTIVE = [
    (r"\brm\s+(-\w+\s+)*-\w*[rf]", "recursive or forced removal"),
    (r"\brm\s+", "file removal"),
    (r"\bunlink\b", "unlink"),
    (r"\brmdir\b", "directory removal"),
    (r"-delete\b", "find-driven deletion"),
    (r"\btruncate\b", "truncation"),
    (r"\bshred\b", "shred"),
    (r"\bmkfs\b", "filesystem creation"),
    (r"\bchown\b", "ownership change"),
    (r"\bchmod\s+(-\w+\s+)*-\w*R", "recursive permission change"),
    (r"\bchgrp\s+(-\w+\s+)*-\w*R", "recursive group change"),
    (r"\brsync\b[^\n]*--delete", "synchronisation with deletion"),
    (r"\bgit\s+clean\b", "git clean"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bgit\s+restore\b", "git restore"),
    (r"\bgit\s+checkout\s+--\s", "git checkout of a path"),
    (r"\b(scancel|pkill|killall)\b", "broad process or job cancellation"),
    (r"\bsed\b[^\n]*\s-i\b", "in-place stream edit"),
    # `tee` is deliberately absent. The leaf names non-appending tee as an
    # illustrative hazard, but a lint cannot tell writing a new log from
    # overwriting an input, and `exec > >(tee run.log)` is ordinary logging.
    # Flagging it fired on known-good scripts, which is worse than not flagging.
]

# Indirect execution. Not destructive in itself; it moves behaviour where a
# command-level review cannot see it, so the reviewer is told where to look.
INDIRECT = [
    (r"\beval\b", "eval"),
    (r"\b(bash|sh)\s+-c\b", "inline shell command"),
    (r"\bxargs\b", "xargs"),
    (r"\bssh\b", "remote command"),
    (r"\b(python[0-9.]*|perl|ruby)\s+-c\b", "inline interpreter command"),
]

HARDENING = re.compile(r"^\s*set\s+-[a-zA-Z]*e[a-zA-Z]*u[a-zA-Z]*\b.*\bpipefail\b", re.M)


# Accelerator memory samplers, keyed by the vendor a machine profile declares.
# conventions/batch-scripts.md requires the command to be resolved FROM the profile,
# never from memory; this table exists so the lint can RECOGNISE a sampler, and is
# deliberately not a menu for a script to copy from.
TELEMETRY = {
    "nvidia": ("nvidia-smi",),
    "amd": ("rocm-smi", "amd-smi"),
}

# The handbook's own reference sampler satisfies the rule without naming a vendor
# tool on the script's command line, so recognise it too -- otherwise using the
# supported implementation would trip the check written to encourage it.
SAMPLER_TOOL = "gpu-memory-sampler"


def accelerator_vendors(machine: str | None) -> set[str] | None:
    """Declared accelerator vendors across a profile's node types, lowercased.

    None means the question was not asked (no --machine). An empty set means the
    profile declares no accelerated node type, so the telemetry rule does not apply.
    """
    if machine is None:
        return None
    profile_path = HANDBOOK / "machines" / machine / "machine.yaml"
    if not profile_path.exists():
        sys.exit(f"no machine profile at machines/{machine}/machine.yaml")
    profile = yaml.safe_load(profile_path.read_text())
    vendors = set()
    for node_type in (profile.get("node_types") or {}).values():
        accelerator = (node_type or {}).get("accelerator")
        if accelerator and accelerator.get("vendor"):
            vendors.add(str(accelerator["vendor"]).lower())
    return vendors


def strip_comments(text: str) -> list[tuple[int, str]]:
    """Return (lineno, code) for lines that are not comments or directives.

    Directive lines are handled separately; a `#SBATCH` line is not shell code and
    a destructive word inside a comment is not an operation.
    """
    out = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        code = re.sub(r"(?<!\\)#.*$", "", raw)
        if code.strip():
            out.append((number, code))
    return out


def load_surface(machine: str | None):
    """Return (surface, profile_scheduler) or (None, None) when not requested."""
    if machine is None:
        return None, None
    profile_path = HANDBOOK / "machines" / machine / "machine.yaml"
    if not profile_path.exists():
        sys.exit(f"no machine profile at machines/{machine}/machine.yaml")
    profile = yaml.safe_load(profile_path.read_text())
    scheduler = profile.get("scheduler", {})
    surfaces = yaml.safe_load(SURFACES.read_text())["surfaces"]
    kind = scheduler.get("type")
    if kind not in surfaces:
        sys.exit(f"no recorded submission surface for scheduler type {kind!r}")
    surface = dict(surfaces[kind])
    # A machine profile may override any field of its type's surface.
    surface.update({k: v for k, v in scheduler.items() if k in surface})
    return surface, scheduler


def option_present(directives: list[str], long_opt: str, short_opt: str | None) -> bool:
    forms = [long_opt] + ([short_opt] if short_opt else [])
    for line in directives:
        for form in forms:
            if re.search(rf"(?<![\w-]){re.escape(form)}(?=[\s=]|$)", line):
                return True
    return False


def check(path: pathlib.Path, machine: str | None,
          work_mode: str | None = None) -> tuple[list, list, list]:
    text = path.read_text()
    code_lines = strip_comments(text)
    errors, warnings, notes = [], [], []

    surface, _ = load_surface(machine)

    if surface:
        prefix = surface["directive_prefix"]
        directives = [l for l in text.splitlines() if l.strip().startswith(prefix)]
        submit = surface["submit_command"]
        interactive = surface["interactive_command"]
    else:
        directives = []
        submit = interactive = None
    # A file with no directives is probably a driver that runs from an allocation,
    # where calling the allocator is its job. Report submission there, but do not
    # fail: crying wolf on a project's own driver is how a lint gets ignored.
    looks_like_batch = bool(directives)

    for number, code in code_lines:
        # Nested submission: the one mistake with unbounded, unrecoverable cost.
        if submit:
            for command in (submit, interactive):
                if re.search(rf"(?<![\w./-]){re.escape(command)}(?![\w-])", code):
                    finding = (number, f"submits another job ({command})")
                    (errors if looks_like_batch else warnings).append(finding)
        for pattern, description in DESTRUCTIVE:
            if re.search(pattern, code):
                errors.append((number, f"destructive operation: {description}"))
                break
        for pattern, description in INDIRECT:
            if re.search(pattern, code):
                warnings.append((number, f"indirect execution ({description}) hides behaviour from review"))
                break
        # Enumerate writes for review step 4 rather than guessing which are unsafe.
        # Excluded, because each fired on known-good scripts and none is a write:
        # `>&` duplicates a descriptor, `>(` opens a process substitution, and `->`
        # is an arrow inside a message. A quoted path is still a real target.
        for match in re.finditer(r"(?<![0-9<>&-])>(?![>&(])\s*(\S+)", code):
            target = match.group(1)
            if target[0] in "><&(":  # `exec > >(tee log)` redirects to a process
                continue
            notes.append((number, f"truncating redirection to {target}"))

    if not HARDENING.search(text):
        warnings.append((0, "no `set -euo pipefail`; a shebang flag does not cover -u or pipefail"))

    if surface and not directives:
        # A driver that runs from an allocation is not a batch script, and judging
        # it against directive rules is a category error rather than a finding.
        notes.append((0, f"no {surface['directive_prefix']} directives; this does not look "
                         "like a batch script, so directive checks were skipped"))
    elif surface:
        if not option_present(directives, surface["account_option"], surface.get("account_option_short")):
            errors.append((0, "no account directive; the chargeable account must be declared, never inherited"))
        for key, short_key, label in (
            ("chdir_option", "chdir_option_short", "working directory"),
            ("output_option", "output_option_short", "output destination"),
        ):
            if not option_present(directives, surface[key], surface.get(short_key)):
                warnings.append((0, f"{label} not pinned ({surface[key]}); it will be inherited"))
    elif machine is None:
        notes.append((0, "no --machine given: directive, nested-submission, and "
                         "accelerator-telemetry checks were skipped"))

    # -- accelerator telemetry --------------------------------------------------
    # The leaf requires a background accelerator-memory sampler in every work mode
    # but production. Only PRESENCE is decidable here: whether the sampler ran,
    # covered the whole run, sampled often enough, or wrote anything is not, and
    # both the leaf and the summary line say so.
    #
    # Why this is worth a check at all: an application's own memory counters are
    # printed during teardown, so a run killed by the out-of-memory handler, a
    # signal, or a walltime limit reports none -- which is exactly when the number
    # decides the diagnosis. A script with no sampler cannot produce it afterwards.
    vendors = accelerator_vendors(machine)
    if vendors:
        recognised = {command for commands in TELEMETRY.values() for command in commands}
        recognised.add(SAMPLER_TOOL)
        found = any(
            re.search(rf"(?<![\w.-]){re.escape(command)}\b", code)
            for _, code in code_lines
            for command in recognised
        )
        if not found:
            expected = ", ".join(sorted(
                command for vendor in vendors for command in TELEMETRY.get(vendor, ())
            )) or "an accelerator telemetry tool"
            message = (f"no accelerator memory sampler ({expected}); "
                       "conventions/batch-scripts.md requires one in every work mode "
                       "but production")
            if work_mode and work_mode.lower() != "production":
                warnings.append((0, f"{message} -- work mode is {work_mode}"))
            else:
                notes.append((0, f"{message}; pass --work-mode to raise this to a warning"))

    # -- per-step host-memory accounting ---------------------------------------
    # The leaf requires every script to record its own per-step accounting at
    # teardown. Presence of the query is decidable; whether it runs in teardown,
    # covers the right job, or is guarded against an unreachable database is not.
    if surface and surface.get("accounting_command"):
        accounting = surface["accounting_command"]
        if not any(re.search(rf"(?<![\w.-]){re.escape(accounting)}\b", code)
                   for _, code in code_lines):
            warnings.append((0, f"no per-step accounting query ({accounting}); "
                                "conventions/batch-scripts.md requires the script to record "
                                "its own host-memory accounting before it exits"))

    # Proofreading belongs at authoring time, which is when this lint runs. At run
    # time it saves nothing: an application that parses its whole input before
    # computing fails the job anyway, after the queue wait and the submission are
    # already spent.
    for number, code in code_lines:
        if STDIN_REDIRECT.search(code):
            warnings.append((number,
                             "an input file is piped into a program on stdin and this lint "
                             "cannot tell whether it parses. Proofread it while the script is "
                             "being written -- at run time it saves nothing. For MILC: "
                             "tools/milc-proofread-input.sh"))
            break

    return errors, warnings, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Advisory lint for batch submission scripts.")
    parser.add_argument("script", type=pathlib.Path)
    parser.add_argument("--machine", help="machine profile name, enabling directive checks")
    parser.add_argument("--work-mode",
                        help="current work mode; outside production a missing accelerator "
                             "memory sampler is raised from a note to a warning")
    args = parser.parse_args()

    if not args.script.is_file():
        sys.exit(f"no such script: {args.script}")

    errors, warnings, notes = check(args.script, args.machine, args.work_mode)

    for label, items in (("error", errors), ("warning", warnings), ("note", notes)):
        for number, message in items:
            where = f"{args.script}:{number}" if number else str(args.script)
            print(f"{label}: {where}: {message}")

    print(
        f"{len(errors)} errors · {len(warnings)} warnings · {len(notes)} notes · "
        "approved-root, invoked-program, intent, sampler-coverage, and "
        "teardown-placement checks NOT performed"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
