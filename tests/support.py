#!/usr/bin/env python3
"""Shared helpers for the handbook test suite."""

from __future__ import annotations

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
