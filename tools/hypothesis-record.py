#!/usr/bin/env python3
"""Check a hypothesis record, and compute the speedup bounds it must not assert.

The provenance check is guarded against its own absence. Until 2026-09-14 it read
``if src and queries and ...``, so a hypothesis with an empty ``queries`` list skipped
it entirely: a record whose every figure was fabricated passed with zero errors. A
guard that cannot fire is the same defect as a harness that cannot fail
(conventions/repeated-work.md), so an empty list is now itself an error and the
negative control in tests/test_hypothesis_record.py pins it.

ARCHITECTURE.md §profile-analysis: a speedup bound follows arithmetically from a
claimed runtime fraction, so it is computed here rather than written by whoever
wrote the record. A wrong bound supplied by hand reads as a precise,
profile-grounded fact, and nothing downstream rechecks it.

A second guard, added 2026-09-15 when Slice 6 check 1 was relaxed from "derived_by_hand
is empty" to "hand-derived figures are declared": the declaration became the only
safeguard, and nothing read it. Emptying the list while still citing hand-derived
figures passed with zero errors. A figure whose ``from`` is not a command shipped in
tools/ was not emitted by an extraction command, so it must set ``hand_derived`` and be
covered by a declaration; a flag with no declaration, and a declaration covering no
flagged figure, are both errors. This catches inconsistency, not dishonesty -- a record
that flags nothing still passes, and that residual is named in ARCHITECTURE.md
§profile-analysis rather than papered over.

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

TOOLS_DIR = Path(__file__).resolve().parent
SCHEMA = TOOLS_DIR.parent / "schemas" / "hypothesis.schema.json"

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


def is_extraction_command(src: str) -> bool:
    """True when ``src`` starts with the name of a tool shipped beside this one.

    Derived from the installed layout rather than a hardcoded name, so renaming or
    adding an extraction tool does not silently turn its output into hand-derived
    figures. Anything else -- a grep of a run log, a build record, a second profiler --
    is a quantity the extraction did not emit, which is what derived_by_hand declares.
    """
    head = src.strip().split()[0] if src.strip() else ""
    name = Path(head).name
    return bool(name) and (TOOLS_DIR / name).is_file()


def check(record: dict, schema: dict) -> list[str]:
    errors: list[str] = []
    for key in schema.get("required", []):
        if key not in record:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors

    declared = bool((record.get("extraction") or {}).get("derived_by_hand"))
    flagged_anywhere = False

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
        if not queries:
            errors.append(
                f"{where}.queries: empty; a figure that names no command is not evidence. "
                "An empty list must not silently satisfy the provenance check below"
            )
        for j, entry in enumerate(evidence):
            src = entry.get("from")
            if src and not any(src in q for q in queries):
                errors.append(
                    f"{where}.evidence[{j}].from: {src!r} names no listed query; "
                    "every figure must be traceable to the command that produced it"
                )
            hand = bool(entry.get("hand_derived"))
            flagged_anywhere = flagged_anywhere or hand
            if src and not hand and not is_extraction_command(src):  # GUARD: unflagged
                errors.append(
                    f"{where}.evidence[{j}]: {src!r} is not a command the extraction "
                    "tools provide, so this figure was derived by hand; set hand_derived "
                    "and name the quantity in extraction.derived_by_hand"
                )
            if hand and not declared:
                errors.append(
                    f"{where}.evidence[{j}]: flagged hand_derived while "
                    "extraction.derived_by_hand is empty; the declaration is the only "
                    "caveat a reader gets"
                )

        # grounding.basis declared an enum that nothing read: it is nested one level
        # below the properties this function scans, so every value passed. Same class
        # as the `if src and queries` short-circuit and the unread declaration list.
        gschema = item["properties"]["grounding"]
        grounding = hyp.get("grounding")
        if isinstance(grounding, dict):
            basis = grounding.get("basis")
            allowed = gschema["properties"]["basis"]["enum"]
            if basis not in allowed:  # GUARD: basis
                errors.append(
                    f"{where}.grounding.basis: {basis!r} not one of {allowed}"
                )
            if basis in ("handbook_leaf", "both") and not grounding.get("leaves"):
                errors.append(
                    f"{where}.grounding: basis {basis!r} names a leaf but `leaves` is "
                    "empty; a cited leaf is checkable and recall is not"
                )
            if basis == "source" and not grounding.get("sources"):
                errors.append(
                    f"{where}.grounding: basis 'source' but `sources` is empty; "
                    "a source claim names its file, line and revision or it is recall"
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

    if declared and not flagged_anywhere:
        errors.append(
            "extraction.derived_by_hand declares quantities but no evidence item sets "
            "hand_derived; a declaration naming no figure caveats nothing"
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
        f"hand-derivation declared, derived bounds · {len(errors)} error(s) · "
        "scientific validity NOT checked"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
