#!/usr/bin/env python3
"""Shared helpers for the handbook test suite."""

from __future__ import annotations

import atexit
import functools
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELECT_PYTHON = ROOT / "tools" / "select-python"

# The frontend tooling paths `.gitignore` declares non-content, in the form `copytree`
# needs. An agent sandbox materialises a placeholder at every path it denies writes to —
# a device node, or an unreadable empty file — and a plain copy of the repository dies on
# them with `Permission denied`. `.gitignore` keeps them out of `git status`; it has no
# effect here, so the same declaration is repeated in executable form.
#
# The handbook-owned `skills/` directories are kept: the validator checks the frontend
# adapters they hold, so a copy without them fails for an unrelated reason.

# Schema objects the validator checks: the seven files in `schemas/` plus every YAML
# instance bound to one of them in `validate_schemas`. Adding a stack, machine, project
# or build-profile file changes this number, and the assertion is a deliberate tripwire
# that makes the addition visible rather than silent. Update it in this one place.
EXPECTED_SCHEMA_OBJECTS = 30

TOOLING_FILES = (".mcp.json",)
TOOLING_DIRECTORIES = (".claude", ".agents")
TOOLING_KEEP = ("skills",)


# ---------------------------------------------------------------------------
# Interpreter selection for tools that carry dependencies
# ---------------------------------------------------------------------------
#
# `tools/run-validator` has never invoked the validator through `sys.executable`; it
# goes through `tools/select-python`, which probes for an interpreter carrying the
# caller's declared modules -- including module-provided ones -- and rejects any
# candidate that emits diagnostics. That contract exists because a live session once
# found the mandatory validator unrunnable: no interpreter on `PATH` carried its one
# third-party dependency.
#
# The suite never adopted it, and subprocessed the same dependency-carrying tools with
# `sys.executable` -- the interpreter running the tests, which need not carry anything.
# The failure that produces is not a missing check, it is a check that reports a missing
# module while naming a behaviour it never exercised, and five such tests asserted on
# validator *output*. The tempting repair is to loosen those assertions until the suite
# is green, at which point they pass without the validator ever running.
#
# The rule the two cases differ by:
#
#   Inside a tool already launched through `select-python`, `sys.executable` is correct
#   -- it inherits a dependency set something established. Inside a test it is not,
#   because nothing established what the suite's interpreter carries.
#
# Only five tools carry third-party imports: `validate-knowledge.py` (PyYAML and
# jsonschema) and `build-index.py`, `check-batch-script.py`, `sync-agent-entrypoints.py`
# and `session_logging.py` (PyYAML). Every other tool is stdlib-only and its
# `sys.executable` call sites are correct as they stand.

# Deliberately not a module-level set. Several test modules load this file through
# `spec_from_file_location`, each getting its own copy, so module-level state dedupes
# nothing -- the first version of this printed the banner once per module, seven times
# in a row, which is the cry-wolf failure `running.md` names rather than the loud
# warning it was meant to be. `sys` is the one object guaranteed to be shared.
_REGISTRY = "_lqcd_handbook_announced_dependencies"


def _announced() -> set[tuple[str, ...]]:
    seen = getattr(sys, _REGISTRY, None)
    if seen is None:
        seen = set()
        setattr(sys, _REGISTRY, seen)
    return seen


def _announce(requirements: tuple[str, ...], detail: str) -> None:
    """Say on stderr, once per requirement set, that checks did not run.

    A skip is quiet by default -- `unittest` renders a whole suite of them as
    `OK (skipped=N)`, which reads as success. That is the cry-wolf failure inverted:
    instead of an alarm nobody believes, an absence nobody notices. The banner exists
    so the operator cannot mistake "did not run" for "passed".
    """
    seen = _announced()
    if requirements in seen:
        return
    seen.add(requirements)
    wanted = ", ".join(requirements)
    bar = "!" * 74
    print(
        f"\n{bar}\n"
        f"!! CHECKS DID NOT RUN -- no interpreter carries: {wanted}\n"
        f"!! {detail}\n"
        "!! The tests below are SKIPPED, not passing. Nothing they cover was\n"
        "!! verified, including the privacy deny-list and the schema checks.\n"
        "!! Supply the dependencies, or make them loadable through the module\n"
        "!! system so tools/select-python can find them, and re-run.\n"
        f"{bar}\n",
        file=sys.stderr,
        flush=True,
    )


@functools.lru_cache(maxsize=None)
def _select(requirements: tuple[str, ...]) -> str:
    argv = [
        os.environ.get("BASH") or shutil.which("bash") or "bash",
        str(SELECT_PYTHON),
        "--label",
        "the handbook test suite",
        "--allow-module-load",
    ]
    for module in requirements:
        argv += ["--require", module]
    # `select-python` ends in `exec "$candidate" "$@"`, so everything after `--` is
    # interpreter argv; `-c` passes straight through.
    argv += ["--", "-c", "import sys; print(sys.executable)"]
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return "\0" + (detail[-1] if detail else "select-python found no candidate")
    return proc.stdout.strip()


def interpreter_for(*requirements: str) -> str:
    """Path to an interpreter carrying `requirements`, or skip loudly.

    Use this instead of `sys.executable` whenever a test subprocesses a tool with a
    third-party import. Never fall back to `sys.executable` on failure: that reinstates
    the defect this exists to remove, wearing a different error message.
    """
    resolved = _select(tuple(requirements))
    if resolved.startswith("\0"):
        _announce(tuple(requirements), resolved[1:])
        raise unittest.SkipTest(
            f"no interpreter carries {', '.join(requirements)} -- this check DID NOT RUN"
        )
    return resolved


def require_importable(*modules: str) -> None:
    """Skip the calling module loudly unless `modules` import in *this* interpreter.

    For a test that parses YAML in-process rather than subprocessing a tool, choosing a
    different interpreter cannot help -- the import has to succeed here. Call this at
    module scope, above the import it guards; `unittest`'s loader turns a module-level
    `SkipTest` into a reported skip rather than a collection error.
    """
    missing = tuple(m for m in modules if not _importable(m))
    if not missing:
        return
    _announce(missing, f"this interpreter is {sys.executable}")
    raise unittest.SkipTest(
        f"{', '.join(missing)} not importable here -- these checks DID NOT RUN"
    )


def _importable(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # pragma: no cover - malformed name or package
        return False


def handbook_copy_ignore(root, *patterns):
    """Return a `copytree` ignore callable for a copy of the handbook at `root`.

    Drops the sandbox tooling placeholders in addition to `patterns`, which are matched
    by name exactly as `shutil.ignore_patterns` would match them.
    """
    root = Path(root)
    by_pattern = shutil.ignore_patterns(*patterns)

    def ignore(directory, names):
        dropped = set(by_pattern(directory, names))
        current = Path(directory)
        if current == root:
            dropped.update(name for name in names if name in TOOLING_FILES)
        elif current.parent == root and current.name in TOOLING_DIRECTORIES:
            dropped.update(name for name in names if name not in TOOLING_KEEP)
        return dropped

    return ignore


# ---------------------------------------------------------------------------
# Source perturbation for controls
# ---------------------------------------------------------------------------
#
# A control that passes proves nothing on its own: it has to be shown to fail when the
# fix it guards is reverted. Doing that by hand is what this repository kept getting
# wrong -- five controls have been recorded as vacuous, and a vacuous perturbation
# reports OK, which is indistinguishable from a guard that works.
#
# Three near-identical copies of this helper existed before it was extracted here. It
# adds one check none of them had: a replacement equal to the text it replaces passes
# `assertIn` and writes nothing, which is exactly how the fifth recorded vacuous control
# got in. `perturb` now fails on a no-op edit rather than letting the assertion below it
# decide.
#
# Restoration is belt and braces because the file being rewritten is real source in the
# working tree, not a fixture. `addCleanup` runs after a test that raises; the `atexit`
# hook covers an interpreter exiting for another reason, including KeyboardInterrupt.
# Neither survives SIGKILL, so `tools/run-change-proposal` printing the diff before it
# runs the suite remains the backstop.

_PERTURBED: dict[Path, str] = {}


def _restore_perturbed() -> None:
    for path, original in list(_PERTURBED.items()):
        try:
            if path.read_text() != original:
                path.write_text(original)
        except OSError:  # pragma: no cover - best effort on the way out
            pass
    _PERTURBED.clear()


atexit.register(_restore_perturbed)


class PerturbationMixin:
    """Rewrite implementation source for the duration of one test.

    Mix into a `TestCase` and call `self.perturb(path, old, new)`. The file is restored
    when the test finishes, however it finishes.
    """

    def perturb(self, path: Path, old: str, new: str, count: int = 1) -> None:
        path = Path(path)
        original = _PERTURBED.get(path)
        if original is None:
            original = path.read_text()
            _PERTURBED[path] = original
            self.addCleanup(_restore_one, path)
        self.assertIn(old, original, "control edit matched nothing; it would prove nothing")
        rewritten = original.replace(old, new, count)
        # Not assertNotEqual: on failure it renders both copies of the file, which is
        # tens of kilobytes of noise around a one-line finding.
        if rewritten == original:
            self.fail(f"control edit changed nothing in {path.name}; it would prove nothing")
        path.write_text(rewritten)

    def perturbed_source(self, path: Path) -> str:
        """The unperturbed text of `path`, for a control that needs to read it."""
        return _PERTURBED.get(Path(path)) or Path(path).read_text()


def _restore_one(path: Path) -> None:
    original = _PERTURBED.pop(Path(path), None)
    if original is not None:
        Path(path).write_text(original)
