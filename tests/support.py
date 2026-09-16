#!/usr/bin/env python3
"""Shared helpers for the handbook test suite."""

from __future__ import annotations

import atexit
import shutil
from pathlib import Path

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
