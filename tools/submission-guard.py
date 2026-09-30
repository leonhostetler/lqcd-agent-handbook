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

What counts as a submission is decided on tokens and errs towards refusing. The command line
is split at shell operators (`;`, `&`, `|`, parentheses, backquotes and newlines) even when
they touch a word, so each simple command is judged on its own. The submit command counts
wherever its bare name appears, and as a path (`/usr/bin/<submit>`) in command position. A
string run by `sh -c`, `bash -c` and similar shells, or by `eval`, is judged the same way.

Two readings are exempt because they cannot submit: any argument of a look-up (`type`,
`which`, `whereis`, `man`, `command -v`/`-V`), because a look-up names commands and runs none,
and the submit command invoked with nothing but a help or version flag. The exemption is
scoped to the look-up's own simple command, so a submission after an operator or a newline is
still checked. Everything else that tokenises to the submit command is treated as a submission
-- including the word appearing in heredoc or echoed text, because a heredoc fed to a shell
does submit and a tokeniser cannot tell the two apart. The refusal says so, and the remedy for
text is to write it from a file rather than from the command line.

This is a strong default, not a sandbox. A submission reached through a variable, an alias, a
script that calls the submit command itself, or a remote shell is not seen.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import posixpath
import re
import shlex
import subprocess
import sys

HANDBOOK = pathlib.Path(__file__).resolve().parents[1]
# 1.2.0: a refused launcher step fails the run; an older receipt may be a false pass.
MIN_HARNESS_VERSION = (1, 2, 0)

_spec = importlib.util.spec_from_file_location("check_batch_script",
                                               HANDBOOK / "tools" / "check-batch-script.py")
_CBS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_CBS)


def submit_commands() -> set[str]:
    surfaces = _CBS.runtime_data.scheduler_surfaces(HANDBOOK)
    return {str(s["submit_command"]) for s in surfaces["surfaces"].values() if s.get("submit_command")}


def interactive_by_flag() -> set[str]:
    """Submit commands that are also the interactive command, so `-I` requests an allocation.

    Under PBS `qsub -I` holds nodes with no script to check. Where the two commands differ,
    `-I` means something else (it is `--immediate` to Slurm's submit command).
    """
    surfaces = _CBS.runtime_data.scheduler_surfaces(HANDBOOK)
    return {str(s["submit_command"]) for s in surfaces["surfaces"].values()
            if s.get("submit_command") and s.get("submit_command") == s.get("interactive_command")}


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


LOOKUP_COMMANDS = {"type", "which", "whereis", "man"}
HELP_FLAGS = {"--help", "-h", "--usage", "--version", "-V"}
# Words that run the command after them, so a path-form submit command after one is still in
# command position. `command` without -v/-V runs its argument too.
PREFIX_COMMANDS = {"env", "nohup", "time", "exec", "nice", "command"}
# Shells whose -c argument, and `eval`, whose arguments, are themselves command lines.
SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}
PUNCTUATION = "();<>|&\n`"
SEPARATOR_CHARS = set(";&|()\n`")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MAX_NESTING = 3


def tokenise(command: str) -> list[str]:
    """Shell words, with operators split out even where they touch a word.

    `shlex.split` leaves `python3;` as one token, which hides where a simple command ends. A
    redirection such as `>&` may also read as a separator here; that only narrows a look-up's
    scope or ends a script search early, and both of those refuse rather than allow.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def is_separator(token: str) -> bool:
    return bool(token) and all(c in PUNCTUATION for c in token) and any(c in SEPARATOR_CHARS for c in token)


def command_start(tokens: list[str], i: int) -> int:
    """Index of the first token of the simple command containing tokens[i]."""
    j = i
    while j > 0 and not is_separator(tokens[j - 1]):
        j -= 1
    return j


def command_word(tokens: list[str], start: int) -> int:
    """Index of the command word of the simple command starting at `start`, skipping assignments."""
    j = start
    while j < len(tokens) and ASSIGNMENT.match(tokens[j]) and not is_separator(tokens[j]):
        j += 1
    return j


def names_submit(tokens: list[str], i: int, submits: set[str]) -> bool:
    """True when tokens[i] is the submit command: its bare name anywhere, or a path in command position."""
    token = tokens[i]
    if token in submits:
        return True
    if "/" not in token or posixpath.basename(token) not in submits:
        return False
    j = command_word(tokens, command_start(tokens, i))
    while j < i and (tokens[j] in PREFIX_COMMANDS or tokens[j].startswith("-")
                     or ASSIGNMENT.match(tokens[j])):
        j += 1
    return j == i


def is_lookup(tokens: list[str], i: int) -> bool:
    """True when tokens[i], the submit command's name, cannot be submitting anything."""
    start = command_word(tokens, command_start(tokens, i))
    if start < i:
        word = tokens[start]
        if word in LOOKUP_COMMANDS:
            return True
        flags = {t for t in tokens[start + 1:i] if t.startswith("-")}
        if word == "command" and flags & {"-v", "-V"}:
            return True
    rest = []
    for t in tokens[i + 1:]:
        if is_separator(t):
            break
        rest.append(t)
    return bool(rest) and all(t in HELP_FLAGS for t in rest)


def is_eval_argument(tokens: list[str], i: int) -> bool:
    """True when tokens[i] is an argument of `eval`, which the nested pass judges as a command line."""
    word = command_word(tokens, command_start(tokens, i))
    return word < i and tokens[word] == "eval"


def nested_commands(tokens: list[str]) -> list[str]:
    """Command lines that a shell's -c option or `eval` will run."""
    found = []
    for i, token in enumerate(tokens):
        if is_separator(token):
            continue
        if token == "eval" and command_word(tokens, command_start(tokens, i)) == i:
            words = []
            for t in tokens[i + 1:]:
                if is_separator(t):
                    break
                words.append(t)
            if words:
                found.append(" ".join(words))
        elif posixpath.basename(token) in SHELLS:
            for j in range(i + 1, len(tokens) - 1):
                flag = tokens[j]
                if is_separator(flag) or not flag.startswith("-") or flag.startswith("--"):
                    break
                if "c" in flag[1:]:
                    found.append(tokens[j + 1])
                    break
    return found


def find_submission(command: str, submits: set[str], depth: int = 0) -> tuple[list[str], int] | None:
    """The tokens of the command line that submits, and the submit command's index in them."""
    tokens = tokenise(command)
    at = next((i for i in range(len(tokens))
               if names_submit(tokens, i, submits) and not is_lookup(tokens, i)
               and not is_eval_argument(tokens, i)), None)
    if at is not None:
        return tokens, at
    if depth < MAX_NESTING:
        for inner in nested_commands(tokens):
            found = find_submission(inner, submits, depth + 1)
            if found is not None:
                return found
    return None


def find_script(tokens: list[str], submit: str, cwd: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """The script a submit command names, or (None, reason)."""
    try:
        at = tokens.index(submit)
    except ValueError:
        return None, "submit command not found in the tokenised command"
    rest = []
    for token in tokens[at + 1:]:
        if is_separator(token):
            break
        rest.append(token)
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
    found = find_submission(command, submit_commands())
    if found is None:
        return 0, ""
    tokens, at = found
    hit = tokens[at]
    cwd = pathlib.Path(event.get("cwd") or os.getcwd())
    if posixpath.basename(hit) in interactive_by_flag():
        options = []
        for token in tokens[at + 1:]:
            if is_separator(token):
                break
            options.append(token)
        if "-I" in options:
            return 2, (f"submission refused: '{hit} -I' requests an interactive allocation, which "
                       "has no script to check and holds nodes until it is released; the operator "
                       "starts one from their own shell")
    script, reason = find_script(tokens[at:], hit, cwd)
    if script is None:
        return 2, (f"submission refused: {reason}\n"
                   f"  (the command line contains '{hit}' as a word and is treated as a submission; "
                   f"if it only mentions the word, for example in heredoc or echoed text, write that "
                   f"text from a file instead)")

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
