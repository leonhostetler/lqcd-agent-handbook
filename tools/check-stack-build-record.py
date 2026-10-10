#!/usr/bin/env python3
"""Check that a stack's record of what was passed to its build is complete.

A stack's build block is the complete record of what its build was given: the named
profile's options, the stack's machine options and, for a CMake build, its build type.
Anything not listed took its default at the tested commit (ARCHITECTURE.md, stacks). An
omitted flag is invisible downstream, so this tool compares the record with the build
itself before the stack is written.

The executed command is the evidence of what was passed. Neither CMake's cache nor a Make
build marks which values came from the command line, so the cache and the build log are
consistency checks on the command, not substitutes for it.

Subcommands:

  cmake   --stack STACK --command FILE --cache CMakeCache.txt --source CHECKOUT
          Every -D in the configure command must reach the cache with its value; the
          record must equal what was passed (a recorded option that was not passed must
          equal the build's value); every cache value under the software's prefix whose
          default the source declares unconditionally must equal that default or have been
          passed, which catches a stale cache or a command that is not what ran. Defaults
          the source computes are counted, not checked, and those that read the
          environment are named.

  make    --stack STACK --command FILE --makefile MAKEFILE [--log LOG ...] [--source CHECKOUT]
          The make variables in the command must equal the record; a recorded variable that
          was not passed must equal the Makefile's unconditional default. A log's
          "<SOFTWARE> commit:" header must name the tested commit, and every target it
          builds must be one the profile lists.

  hashes  --install-prefix DIR
          Print the sha256 of every shared library under the install's lib directories, by
          path relative to the install, for the stack's build.installed_libraries.

FILE may be the build script itself: the tool finds the one configure (cmake) or make
invocation that passes variables, joining continued lines. Values that are paths print as
<path>, so nothing user-specific is copied from the report into a stack.

Exit status: 0 when nothing was found, 1 on any error, 2 when the only findings are
comparisons the tool could not decide. It reports what it checked, never that a stack
passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VERSION = "1.0.0"
TOOL = "tools/check-stack-build-record.py"
ROOT = Path(__file__).resolve().parents[1]

CACHE_LINE = re.compile(r"^([^:=#/][^:=]*):([A-Z]+)=(.*)$")
PLACEHOLDER = re.compile(r"<[^<>\s]+>")
MAKE_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
MAKE_DEFAULT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(\?=|:=|::=|=)(.*)$")
TRUE_WORDS = {"ON", "TRUE", "YES", "Y", "1"}
FALSE_WORDS = {"OFF", "FALSE", "NO", "N", "0"}


@dataclass
class Report:
    mode: str
    errors: list[str] = field(default_factory=list)
    undecided: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    environment_defaults: list[str] = field(default_factory=list)

    def status(self) -> int:
        if self.errors:
            return 1
        return 2 if self.undecided else 0


def shown(value: Any) -> str:
    """A value as it may be printed: paths become <path>."""
    text = str(value)
    if text.startswith(("/", "~")) or re.search(r"(^|[\s=:,])/(home|scratch|work|global|lustre)", text):
        return "<path>"
    return repr(text)


def unexpanded(text: str) -> bool:
    """A value the shell would still have expanded: a variable or a command substitution."""
    return "$" in text or "`" in text


def canonical(value: Any, cmake: bool) -> str:
    if isinstance(value, bool):
        # YAML booleans: CMake reads ON/OFF, while MILC's Makefile compares the words true/false.
        return ("TRUE" if value else "FALSE") if cmake else ("true" if value else "false")
    text = "" if value is None else str(value).strip()
    if cmake:
        upper = text.upper()
        if upper in TRUE_WORDS:
            return "TRUE"
        if upper in FALSE_WORDS or upper.endswith("-NOTFOUND"):
            return "FALSE"
    return text


def recorded_matches(recorded: Any, actual: Any, cmake: bool) -> bool | None:
    """Whether a recorded value matches an actual one; None when it cannot be decided."""
    rec = canonical(recorded, cmake)
    act = canonical(actual, cmake)
    if PLACEHOLDER.search(rec):
        pattern = "".join(
            ".+?" if PLACEHOLDER.fullmatch(part) else re.escape(part)
            for part in re.split(r"(<[^<>\s]+>)", rec)
            if part
        )
        return re.fullmatch(pattern, act, re.S) is not None
    if unexpanded(act):
        return None
    return rec == act or path_basename_match(rec, act)


def path_basename_match(short: str, full: str) -> bool:
    """CMake caches a compiler given as `mpicc` as the absolute path it found."""
    return bool(short) and "/" not in short and full.startswith("/") and full.rsplit("/", 1)[-1] == short


def logical_lines(text: str) -> list[str]:
    lines, buffer = [], ""
    for raw in text.splitlines():
        if raw.lstrip().startswith("#") and not buffer:
            continue
        if raw.rstrip().endswith("\\"):
            buffer += raw.rstrip()[:-1] + " "
            continue
        lines.append(buffer + raw)
        buffer = ""
    if buffer:
        lines.append(buffer)
    return lines


SHELL_OPERATORS = {"||", "&&", ";", "|", "&"}
REDIRECTIONS = {">", ">>", "<", ">&", "<&", "&>", "&>>"}


def split_command(line: str) -> list[str]:
    """One simple command's words: stop at the first shell operator and drop redirections."""
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        words = list(lexer)
    except ValueError:
        return []
    command, skip = [], False
    for word in words:
        if skip:
            skip = False
            continue
        if word in SHELL_OPERATORS:
            break
        if word in REDIRECTIONS:
            if command and command[-1].isdigit():
                command.pop()  # the file descriptor of `2>`, split off by the lexer
            skip = True  # the redirection target
            continue
        command.append(word)
    return command


def find_cmake_configure(text: str) -> tuple[list[str], list[str]]:
    """The one configure invocation in a command file, and every candidate line seen."""
    found = []
    for line in logical_lines(text):
        words = split_command(line)
        if "cmake" not in [Path(w).name for w in words]:
            continue
        start = [Path(w).name for w in words].index("cmake")
        args = words[start + 1:]
        if any(a in ("--build", "--install", "-E", "-P") for a in args[:1]):
            continue
        if any(a.startswith("-D") for a in args):
            found.append(args)
    return (found[0] if len(found) == 1 else []), found


def cmake_definitions(args: list[str]) -> tuple[dict[str, str], bool]:
    passed: dict[str, str] = {}
    fresh = "--fresh" in args
    iterator = iter(range(len(args)))
    for index in iterator:
        arg = args[index]
        if arg == "-D" and index + 1 < len(args):
            arg = "-D" + args[index + 1]
            next(iterator, None)
        if not arg.startswith("-D") or "=" not in arg:
            continue
        name, value = arg[2:].split("=", 1)
        passed[name.split(":", 1)[0]] = value
    return passed, fresh


def read_cache(path: Path) -> dict[str, tuple[str, str]]:
    entries = {}
    for line in path.read_text(errors="replace").splitlines():
        match = CACHE_LINE.match(line)
        if match and match.group(2) not in ("INTERNAL", "STATIC"):
            entries[match.group(1)] = (match.group(2), match.group(3))
    return entries


def cmake_files(source: Path) -> list[Path]:
    files = [source / "CMakeLists.txt"]
    for sub in ("cmake", "lib"):
        if (source / sub).is_dir():
            files += sorted(p for p in (source / sub).rglob("*") if p.name == "CMakeLists.txt" or p.suffix == ".cmake")
    return [f for f in files if f.is_file()]


def declared_cmake_defaults(source: Path) -> dict[str, list[tuple[str, bool, str]]]:
    """Every option() and set(... CACHE ...) definition: name -> [(value, conditional, where)]."""
    definitions: dict[str, list[tuple[str, bool, str]]] = {}
    for path in cmake_files(source):
        lines = [re.sub(r"(?<!\\)#.*$", "", raw) for raw in path.read_text(errors="replace").splitlines()]
        depth, buffer, start = 0, "", 0
        for number, line in enumerate(lines, 1):
            if not buffer:
                if not re.match(r"^\s*[A-Za-z_]+\s*\(", line):
                    continue
                buffer, start = line, number
            else:
                buffer += " " + line
            if buffer.count("(") > buffer.count(")"):
                continue
            command, buffer = re.match(r"^\s*([A-Za-z_]+)\s*\((.*)\)\s*$", buffer, re.S), ""
            if not command:
                continue
            name, args = command.group(1).lower(), command.group(2)
            if name in ("if", "foreach", "while", "function", "macro"):
                depth += 1
                continue
            if name in ("endif", "endforeach", "endwhile", "endfunction", "endmacro"):
                depth = max(0, depth - 1)
                continue
            tokens = [t[1:-1] if t.startswith('"') else t for t in re.findall(r'"(?:[^"\\]|\\.)*"|\S+', args)]
            where = f"{path.relative_to(source)}:{start}"
            if name == "option" and len(tokens) >= 2:
                value = tokens[2] if len(tokens) >= 3 else "OFF"
                definitions.setdefault(tokens[0], []).append((value, depth > 0, where))
            elif name == "cmake_dependent_option" and tokens:
                definitions.setdefault(tokens[0], []).append((tokens[2] if len(tokens) > 2 else "", True, where))
            elif name == "set" and "CACHE" in tokens and tokens:
                cache_at = tokens.index("CACHE")
                value = " ".join(tokens[1:cache_at])
                definitions.setdefault(tokens[0], []).append((value, depth > 0 or "FORCE" in tokens, where))
    return definitions


def declared_make_defaults(makefile: Path) -> dict[str, list[tuple[str, bool]]]:
    """Top-level NAME ?= value (and =, :=) definitions; inside a conditional they are not decidable."""
    definitions: dict[str, list[tuple[str, bool]]] = {}
    depth = 0
    for line in logical_lines(makefile.read_text(errors="replace")):
        stripped = line.strip()
        word = stripped.split(None, 1)[0] if stripped else ""
        if word in ("ifeq", "ifneq", "ifdef", "ifndef"):
            depth += 1
            continue
        if word == "endif":
            depth = max(0, depth - 1)
            continue
        if line[:1] in (" ", "\t"):
            continue
        match = MAKE_DEFAULT.match(stripped)
        if match:
            value = match.group(3).split("#", 1)[0].strip()
            definitions.setdefault(match.group(1), []).append((value, depth > 0 or match.group(2) != "?="))
    return definitions


def load_stack(path: Path) -> dict[str, Any]:
    stack = yaml.safe_load(path.read_text())
    if not isinstance(stack, dict):
        raise SystemExit(f"{path}: not a stack record")
    return stack


def recorded_options(stack: dict[str, Any], root: Path, report: Report) -> dict[str, Any]:
    build = stack.get("build", {})
    pointer = build.get("profile_options_from", "")
    record: dict[str, Any] = {}
    if "#" not in str(pointer):
        report.errors.append(f"build.profile_options_from {pointer!r} names no profile")
    else:
        file, profile = str(pointer).split("#", 1)
        profiles = yaml.safe_load((root / file).read_text()).get("profiles", {})
        if profile not in profiles:
            report.errors.append(f"profile {pointer!r} does not exist under {root.name}")
        else:
            record.update(profiles[profile].get("options", {}) or {})
            report.checked.append(f"profile options from {pointer}")
    record.update(build.get("machine_options", {}) or {})
    return record


def check_commit(stack: dict[str, Any], source: Path | None, report: Report) -> None:
    software = stack.get("software")
    tested = (stack.get("tested_software", {}) or {}).get(software, {}) or {}
    commit = tested.get("commit")
    if source is None:
        return
    if not (source / ".git").exists():
        report.warnings.append(f"source is not a git checkout; its commit was not checked against {commit}")
        return
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0 or head.stdout.strip() != commit:
        report.errors.append(
            f"source checkout is at {head.stdout.strip() or 'an unreadable revision'}, not the tested commit {commit}; "
            "its declared defaults are not the build's"
        )
    else:
        report.checked.append(f"source checkout at the tested {software} commit")


def compare_passed_with_record(passed: dict[str, str], record: dict[str, Any], cmake: bool, report: Report) -> None:
    for name, value in sorted(passed.items()):
        if name not in record:
            report.errors.append(f"{name}={shown(value)} was passed to the build but is not in the stack's record")
            continue
        match = recorded_matches(record[name], value, cmake)
        if match is None:
            report.undecided.append(
                f"{name}: passed as {shown(value)}, an unexpanded shell value, against recorded {shown(record[name])}"
            )
        elif not match:
            report.errors.append(f"{name}: recorded {shown(record[name])} but passed {shown(value)}")


def run_cmake(args: argparse.Namespace) -> Report:
    report = Report("cmake")
    stack = load_stack(args.stack)
    record = recorded_options(stack, args.root, report)
    build_type = stack.get("build", {}).get("type")
    if build_type:
        record.setdefault("CMAKE_BUILD_TYPE", build_type)
    configure, candidates = find_cmake_configure(args.command.read_text(errors="replace"))
    if len(candidates) != 1:
        report.errors.append(
            f"expected one cmake configure invocation passing -D values in the command file, found {len(candidates)}"
        )
        return report
    passed, fresh = cmake_definitions(configure)
    report.checked.append(f"{len(passed)} -D values from the configure command")
    if not fresh:
        report.warnings.append(
            "the configure did not use --fresh: values from an earlier configure in the same build "
            "directory would survive in the cache unless that directory was new"
        )
    cache = read_cache(args.cache)
    report.checked.append(f"{len(cache)} cache entries")
    check_commit(stack, args.source, report)

    for name, value in sorted(passed.items()):
        if name not in cache:
            report.errors.append(f"{name} was passed but is not in the cache, so it did not reach this build")
        elif not unexpanded(value) and not recorded_matches(value, cache[name][1], True):
            report.errors.append(f"{name}: passed {shown(value)} but the cache holds {shown(cache[name][1])}")
    compare_passed_with_record(passed, record, True, report)
    for name, value in sorted(record.items()):
        if name in passed:
            continue
        if name not in cache:
            report.errors.append(f"{name} is recorded but is not a cache variable of this build")
        elif recorded_matches(value, cache[name][1], True) is False:
            report.errors.append(
                f"{name} is recorded as {shown(value)} but was not passed, and the build holds {shown(cache[name][1])}"
            )

    prefix = args.prefix or f"{str(stack.get('software', '')).upper()}_"
    definitions = declared_cmake_defaults(args.source) if args.source else {}
    decided = computed = undeclared = 0
    for name, (_kind, value) in sorted(cache.items()):
        if not name.startswith(prefix) or name in passed:
            continue
        found = definitions.get(name, [])
        if not found:
            undeclared += 1
            continue
        if len(found) > 1 or found[0][1] or "$" in found[0][0]:
            computed += 1
            if any("$ENV{" in item[0] for item in found):
                report.environment_defaults.append(name)
            continue
        decided += 1
        if canonical(found[0][0], True) != canonical(value, True):
            report.errors.append(
                f"{name} holds {shown(value)}, but its default ({found[0][2]}) is {shown(found[0][0])} and the "
                "command did not pass it: a stale cache, or a command that is not the one that ran"
            )
    report.counts = {
        f"{prefix}* values checked against their declared default": decided,
        f"{prefix}* values with computed defaults, not cross-checked": computed,
        f"{prefix}* values with no declaration found, not cross-checked": undeclared,
    }
    return report


def find_make_invocation(text: str) -> tuple[dict[str, str], list[str], int]:
    """The make invocation that passes variables: its assignments, its targets, and the count found."""
    found = []
    for line in logical_lines(text):
        words = split_command(line)
        names = [Path(w).name for w in words]
        if "make" not in names:
            continue
        at = names.index("make")
        before = [w for w in words[:at] if MAKE_ASSIGNMENT.match(w)]
        after = [w for w in words[at + 1:] if MAKE_ASSIGNMENT.match(w)]
        if before or after:
            targets = [w for w in words[at + 1:] if not w.startswith("-") and not MAKE_ASSIGNMENT.match(w)]
            found.append((before + after, targets))
    if len(found) != 1:
        return {}, [], len(found)
    assignments = dict(MAKE_ASSIGNMENT.match(w).groups() for w in found[0][0])
    return assignments, found[0][1], 1


def run_make(args: argparse.Namespace) -> Report:
    report = Report("make")
    stack = load_stack(args.stack)
    record = recorded_options(stack, args.root, report)
    passed, _targets, count = find_make_invocation(args.command.read_text(errors="replace"))
    if count != 1:
        report.errors.append(f"expected one make invocation passing variables in the command file, found {count}")
        return report
    report.checked.append(f"{len(passed)} make variables from the build command")
    check_commit(stack, args.source, report)
    compare_passed_with_record(passed, record, False, report)
    defaults = declared_make_defaults(args.makefile)
    for name, value in sorted(record.items()):
        if name in passed:
            continue
        found = defaults.get(name, [])
        if len(found) == 1 and not found[0][1] and "$" not in found[0][0]:
            if canonical(found[0][0], False) != canonical(value, False):
                report.errors.append(
                    f"{name} is recorded as {shown(value)} but was not passed, and the Makefile default is "
                    f"{shown(found[0][0])}"
                )
        else:
            report.undecided.append(
                f"{name} is recorded as {shown(value)} but was not passed, and the Makefile sets no "
                "unconditional default to compare with"
            )

    software = str(stack.get("software", ""))
    commit = ((stack.get("tested_software", {}) or {}).get(software, {}) or {}).get("commit")
    profile = str(stack.get("build", {}).get("profile_options_from", "")).split("#", 1)
    targets: list[str] = []
    if len(profile) == 2:
        profiles = yaml.safe_load((args.root / profile[0]).read_text()).get("profiles", {})
        targets = list((profiles.get(profile[1], {}) or {}).get("targets", []) or [])
    header = re.compile(rf"^{re.escape(software.upper())} commit:\s*([0-9a-f]+)", re.I | re.M)
    for log in args.log or []:
        text = log.read_text(errors="replace")
        commits = set(header.findall(text))
        if not commits:
            report.warnings.append(f"log {log.name} has no '{software.upper()} commit:' header to check")
        elif commits != {commit}:
            report.errors.append(f"log {log.name} names commit {', '.join(sorted(commits))}, not the tested {commit}")
        else:
            report.checked.append(f"log {log.name} names the tested commit")
        built = set(re.findall(r'"MYTARGET=\s*([A-Za-z0-9_]+)"', text))
        for target in sorted(built - set(targets)):
            report.errors.append(f"log {log.name} builds {target}, which the profile does not list")
    return report


def run_hashes(args: argparse.Namespace) -> int:
    prefix = args.install_prefix
    rows = []
    for libdir in ("lib", "lib64"):
        base = prefix / libdir
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue
            if not (path.name.endswith(".so") or ".so." in path.name):
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append({"path": f"{libdir}/{path.name}", "sha256": digest})
    if not rows:
        print("no shared libraries found under lib/ or lib64/", file=sys.stderr)
        return 1
    print(yaml.safe_dump({"installed_libraries": rows}, sort_keys=False), end="")
    return 0


def print_report(report: Report, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.__dict__ | {"tool": TOOL, "version": VERSION, "status": report.status()}, indent=2))
        return
    print(f"{TOOL} {VERSION} ({report.mode})")
    for line in report.checked:
        print(f"  checked: {line}")
    for name, value in report.counts.items():
        print(f"  {name}: {value}")
    if report.environment_defaults:
        print("  computed defaults that read the environment: " + ", ".join(report.environment_defaults))
    for kind, items in (("ERROR", report.errors), ("UNDECIDED", report.undecided), ("warning", report.warnings)):
        for item in items:
            print(f"  {kind}: {item}")
    print(
        f"  {len(report.errors)} errors, {len(report.undecided)} undecided, {len(report.warnings)} warnings"
        " · completeness is checked only against the evidence named above"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("cmake", "make"):
        p = sub.add_parser(mode)
        p.add_argument("--stack", type=Path, required=True)
        p.add_argument("--command", type=Path, required=True)
        p.add_argument("--root", type=Path, default=Path(os.environ.get("LQCD_HANDBOOK", ROOT)))
        p.add_argument("--json", action="store_true")
        if mode == "cmake":
            p.add_argument("--cache", type=Path, required=True)
            p.add_argument("--source", type=Path, required=True)
            p.add_argument("--prefix", help="cache-variable prefix to cross-check (default: <SOFTWARE>_)")
        else:
            p.add_argument("--makefile", type=Path, required=True)
            p.add_argument("--log", type=Path, action="append")
            p.add_argument("--source", type=Path)
    hashes = sub.add_parser("hashes")
    hashes.add_argument("--install-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "hashes":
        return run_hashes(args)
    report = run_cmake(args) if args.mode == "cmake" else run_make(args)
    print_report(report, args.json)
    return report.status()


if __name__ == "__main__":
    sys.exit(main())
