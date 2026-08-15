#!/usr/bin/env python3
"""Synchronize frontend entrypoint mirrors with canonical AGENTS.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def load_entrypoints(root: Path) -> tuple[Path, list[Path]]:
    config: Any = yaml.safe_load((root / "handbook.yaml").read_text())
    tier = config.get("tier_0", {}) if isinstance(config, dict) else {}
    canonical_name = tier.get("canonical_entrypoint")
    mirror_names = tier.get("mirrors", [])
    if not isinstance(canonical_name, str) or not isinstance(mirror_names, list):
        raise ValueError("handbook.yaml must declare tier_0 canonical_entrypoint and mirrors")
    if not all(isinstance(name, str) for name in mirror_names):
        raise ValueError("tier_0.mirrors must contain only paths")
    return root / canonical_name, [root / name for name in mirror_names]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of updating mirrors")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        canonical, mirrors = load_entrypoints(root)
        canonical_bytes = canonical.read_bytes()
    except (OSError, ValueError) as exc:
        print(f"entrypoint configuration error: {exc}", file=sys.stderr)
        return 2

    stale: list[Path] = []
    for mirror in mirrors:
        try:
            matches = mirror.read_bytes() == canonical_bytes
        except OSError:
            matches = False
        if matches:
            continue
        stale.append(mirror)
        if not args.check:
            mirror.write_bytes(canonical_bytes)

    if stale and args.check:
        names = ", ".join(str(path.relative_to(root)) for path in stale)
        print(f"entrypoint mirrors differ from {canonical.name}: {names}", file=sys.stderr)
        return 1
    if stale:
        names = ", ".join(str(path.relative_to(root)) for path in stale)
        print(f"synchronized entrypoint mirrors from {canonical.name}: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
