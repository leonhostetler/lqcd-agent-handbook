#!/usr/bin/env python3
"""Structural diff between two GPU profiles.

Answers "what changed" between a before and an after capture, which is the
question a performance session asks once it has acted on a hypothesis. The
comparison is deterministic and offline; judging *why* a number moved is the
session's work, not this tool's.

Both profiles are opened read-only. See ARCHITECTURE.md §profile-analysis.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpu_profile import open_profile  # noqa: E402
from gpu_profile.diff import compute_profile_diff  # noqa: E402
from gpu_profile.metrics import compute_profile_summary  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="gpu-profile-diff.py",
        description="Compare two GPU profiler databases (offline, read-only).",
    )
    ap.add_argument("profile_a", help="baseline profiler database")
    ap.add_argument("profile_b", help="comparison profiler database")
    ap.add_argument("--max-phases", type=int, default=8, help="phase cap (1 disables)")
    args = ap.parse_args(argv)

    summaries = []
    for path in (args.profile_a, args.profile_b):
        try:
            with open_profile(path) as prof:
                summaries.append(compute_profile_summary(prof, max_phases=args.max_phases))
        except (ValueError, NotImplementedError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except sqlite3.Error as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3

    diff = compute_profile_diff(summaries[0], summaries[1])
    print(json.dumps(asdict(diff), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
