#!/usr/bin/env python3
"""Check a hypothesis record, and compute the speedup bounds it must not assert.

ARCHITECTURE.md §profile-analysis: a speedup bound follows arithmetically from a
claimed runtime fraction, so it is computed here rather than written by whoever
wrote the record. A wrong bound supplied by hand reads as a precise,
profile-grounded fact, and nothing downstream rechecks it.

Required keys and enums are read from schemas/hypothesis.schema.json rather than
restated, so the two cannot drift. Standard library only: this runs beside a
profile on a login node, where a third-party import is the failure mode that makes
a mandatory check unrunnable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "hypothesis.schema.json"

# Above this fraction the full-elimination bound diverges; report null rather than
# an arbitrarily large finite number that reads as precision.
MAX_FRACTION = 0.999


def amdahl_bounds(fraction_pct: float | None) -> dict | None:
    """Lower bound = halving the cost; upper bound = eliminating it entirely."""
    if fraction_pct is None:
        return None
    f = fraction_pct / 100.0
    lower = round((1.0 / (1.0 - 0.5 * f) - 1.0) * 100.0, 1)
    upper = None if f >= MAX_FRACTION else round((1.0 / (1.0 - f) - 1.0) * 100.0, 1)
    return {"lower": lower, "upper": upper}


def check(record: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in record:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors

    item = schema["properties"]["hypotheses"]["items"]
    enums = {
        k: v["enum"]
        for k, v in item["properties"].items()
        if isinstance(v, dict) and "enum" in v
    }

    for i, hyp in enumerate(record.get("hypotheses", [])):
        where = f"hypotheses[{i}]"
        for key in item.get("required", []):
            if key not in hyp:
                errors.append(f"{where}: missing required key {key}")
        for key, allowed in enums.items():
            if key in hyp and hyp[key] not in allowed:
                errors.append(f"{where}.{key}: {hyp[key]!r} not one of {allowed}")

        evidence = hyp.get("evidence") or []
        if not evidence:
            errors.append(f"{where}.evidence: empty; a hypothesis with no figures is an opinion")
        queries = hyp.get("queries") or []
        for j, entry in enumerate(evidence):
            src = entry.get("from")
            if src and queries and not any(src in q for q in queries) and src not in queries:
                errors.append(
                    f"{where}.evidence[{j}].from: {src!r} names no listed query; "
                    "every figure must be traceable to the command that produced it"
                )

        fraction = hyp.get("runtime_fraction_pct")
        expected = amdahl_bounds(fraction)
        stated = hyp.get("speedup_bounds_pct")
        if stated is not None and stated != expected:
            errors.append(
                f"{where}.speedup_bounds_pct: {stated} does not follow from "
                f"runtime_fraction_pct={fraction} (computed {expected}); "
                "this field is derived, never asserted"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hypothesis-record.py",
        description="Check a hypothesis record and derive its speedup bounds.",
    )
    ap.add_argument("record", help="path to a hypothesis record JSON file")
    ap.add_argument(
        "--fix", action="store_true", help="write the computed speedup bounds into the record"
    )
    args = ap.parse_args(argv)

    try:
        schema = json.loads(SCHEMA.read_text())
        record = json.loads(Path(args.record).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = check(record, schema)

    if args.fix:
        for hyp in record.get("hypotheses", []):
            hyp["speedup_bounds_pct"] = amdahl_bounds(hyp.get("runtime_fraction_pct"))
        Path(args.record).write_text(json.dumps(record, indent=2) + "\n")
        errors = [e for e in errors if "speedup_bounds_pct" not in e]
        print(f"wrote derived bounds into {args.record}")

    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    n = len(record.get("hypotheses", []))
    print(
        f"{n} hypotheses checked · required keys, enums, evidence provenance, "
        f"derived bounds · {len(errors)} error(s) · scientific validity NOT checked"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
