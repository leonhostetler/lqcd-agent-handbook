#!/usr/bin/env python3
"""Regenerate or check tools/generated/, the JSON operational tools read instead of YAML.

YAML stays the only format anyone writes (ARCHITECTURE.md §runtime-data). This developer
tool projects what the operational tools consume: the `handbook.yaml` blocks named in its
`runtime_data` block, the scheduler surfaces, and every machine profile, one JSON file per
source. The projection is exact or it refuses: a YAML date becomes an ISO-8601 string, and
any other value JSON cannot represent stops the build rather than being coerced.

    build-runtime-data.py           write the projection; remove files no source produces
    build-runtime-data.py --check   exit 1, naming each file, when the committed one differs
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_data  # noqa: E402


def exact(value: Any, where: str) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{where}: key {key!r} is not a string")
            out[key] = exact(item, f"{where}.{key}")
        return out
    if isinstance(value, list):
        return [exact(item, f"{where}[{index}]") for index, item in enumerate(value)]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{where}: {value!r} has no JSON form")
        return value
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    raise ValueError(f"{where}: a {type(value).__name__} has no JSON form")


def load(root: Path, relative: Path) -> Any:
    return exact(yaml.safe_load((root / relative).read_text()), relative.as_posix())


def render(source: Path, data: Any) -> str:
    return json.dumps(runtime_data.envelope(source, data), indent=2, ensure_ascii=False,
                      allow_nan=False) + "\n"


def projection(root: Path) -> dict[Path, str]:
    """Every generated file, keyed by its path relative to the root."""
    manifest = load(root, Path("handbook.yaml"))
    blocks = (manifest.get("runtime_data") or {}).get("handbook_blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("handbook.yaml: runtime_data.handbook_blocks must be a non-empty list")
    missing = [name for name in blocks if name not in manifest]
    if missing:
        raise ValueError(f"handbook.yaml: runtime_data names absent blocks: {', '.join(missing)}")
    files = {
        runtime_data.HANDBOOK: render(Path("handbook.yaml"),
                                      {name: manifest[name] for name in blocks}),
        runtime_data.SCHEDULER_SURFACES: render(
            runtime_data.SURFACES_SOURCE, load(root, runtime_data.SURFACES_SOURCE)),
    }
    for profile in sorted((root / "machines").glob("*/machine.yaml")):
        name = profile.parent.name
        source = runtime_data.machine_source(name)
        files[runtime_data.machine_path(name)] = render(source, load(root, source))
    return files


def committed(root: Path) -> set[Path]:
    generated = root / runtime_data.GENERATED
    return {p.relative_to(root) for p in generated.rglob("*.json")} if generated.is_dir() else set()


def check(root: Path) -> int:
    wanted = projection(root)
    problems = []
    for relative, text in sorted(wanted.items()):
        path = root / relative
        if not path.is_file():
            problems.append(f"{relative.as_posix()}: missing")
        elif path.read_text() != text:
            problems.append(f"{relative.as_posix()}: stale")
    for relative in sorted(committed(root) - set(wanted)):
        problems.append(f"{relative.as_posix()}: no source produces it")
    for problem in problems:
        print(problem)
    if problems:
        print("run tools/build-runtime-data.py and include the result")
    return 1 if problems else 0


def write(root: Path) -> int:
    wanted = projection(root)
    for relative, text in sorted(wanted.items()):
        path = root / relative
        if not path.is_file() or path.read_text() != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(relative.as_posix())
    for relative in sorted(committed(root) - set(wanted)):
        (root / relative).unlink()
        print(f"{relative.as_posix()} (removed)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        return check(root) if args.check else write(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"runtime-data generation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
