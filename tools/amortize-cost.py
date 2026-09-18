#!/usr/bin/env python3
"""Cost a measured candidate at production solve counts it was never run at.

A tuning or benchmarking trial runs few solves on purpose: it exists to measure the
terms of a cost model cheaply, not to rehearse production. This tool consumes those
terms -- one-time cost, recurring cost per solve, and the resource each was measured
at -- and evaluates them where the decision actually lives.

It reports pairwise crossovers with no solve count supplied, because an exploratory
campaign discovers its regimes rather than declaring them. It reports shares,
per-solve costs and rankings only at solve counts it is explicitly given, because
those quantities are meaningless without one: there is no default and none is
inferred from the trial. See conventions/measurement.md.
"""

from __future__ import annotations

import argparse
import json
import sys

RESOURCE = "resource"
ELAPSED = "elapsed"
OBJECTIVES = (RESOURCE, ELAPSED)


class InputError(ValueError):
    """A candidate or solve count is outside the model's contract."""


class Candidate:
    """One measured (one-time, recurring) pair and the resource it was measured at."""

    def __init__(self, name: str, setup: float, solve: float, nodes: float) -> None:
        if setup < 0 or solve < 0:
            raise InputError("costs must be non-negative")
        if nodes <= 0:
            raise InputError("resource multiplier must be positive")
        self.name = name
        self.setup = setup
        self.solve = solve
        self.nodes = nodes

    def one_time(self, objective: str) -> float:
        return self.setup * self.nodes if objective == RESOURCE else self.setup

    def recurring(self, objective: str) -> float:
        return self.solve * self.nodes if objective == RESOURCE else self.solve

    def total(self, n: int, objective: str) -> float:
        return self.one_time(objective) + n * self.recurring(objective)


def crossover(a: Candidate, b: Candidate, objective: str) -> dict:
    """Solve count at which b overtakes a, following C_s(N) = I_s + N R_s."""
    d_one_time = b.one_time(objective) - a.one_time(objective)
    d_recurring = a.recurring(objective) - b.recurring(objective)
    out = {"objective": objective, "a": a.name, "b": b.name}
    if d_recurring == 0:
        out["relation"] = "identical recurring cost" if d_one_time == 0 else (
            f"{a.name} cheaper at every solve count" if d_one_time > 0
            else f"{b.name} cheaper at every solve count")
        out["crossover_solves"] = None
        return out
    n_star = d_one_time / d_recurring
    if n_star <= 0:
        cheaper = a.name if a.total(1, objective) <= b.total(1, objective) else b.name
        out["relation"] = f"no positive crossover; {cheaper} dominates for this objective"
        out["crossover_solves"] = None
        return out
    below, above = (a.name, b.name) if a.one_time(objective) < b.one_time(objective) else (b.name, a.name)
    out["relation"] = f"{below} wins below, {above} wins above"
    out["crossover_solves"] = n_star
    return out


def evaluate(candidates: list[Candidate], solves: list[int], objective: str) -> list[dict]:
    rows = []
    for n in solves:
        priced = sorted(candidates, key=lambda c: c.total(n, objective))
        best = priced[0].total(n, objective)
        for c in priced:
            total = c.total(n, objective)
            rows.append({
                "objective": objective,
                "solves": n,
                "candidate": c.name,
                "total": total,
                "per_solve": total / n,
                "setup_share": c.one_time(objective) / total if total else 0.0,
                "relative_to_best": total / best if best else float("inf"),
            })
    return rows


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    out.add_argument(
        "--candidate", nargs=4, action="append", required=True,
        metavar=("NAME", "SETUP", "SOLVE", "NODES"),
        help="one measured candidate: one-time cost, recurring cost per solve, "
             "and the node or GPU count both were measured at",
    )
    out.add_argument(
        "--solves", nargs="+", type=int, default=None,
        help="production solve counts to evaluate. Omit to report crossovers only; "
             "there is no default, and a trial's own solve count is not one",
    )
    out.add_argument(
        "--objective", choices=OBJECTIVES + ("both",), default="both",
        help="resource cost (time x nodes), elapsed time, or both",
    )
    out.add_argument("--resource-unit", default="node-seconds", help="label for the resource column")
    out.add_argument("--json", action="store_true", help="emit JSON instead of text")
    return out


def build(raw: list[list[str]]) -> list[Candidate]:
    seen, out = set(), []
    for name, setup, solve, nodes in raw:
        if name in seen:
            raise InputError(f"duplicate candidate name {name!r}")
        seen.add(name)
        try:
            out.append(Candidate(name, float(setup), float(solve), float(nodes)))
        except ValueError as exc:
            raise InputError(f"{name}: {exc}") from exc
    return out


def report(candidates: list[Candidate], solves, objectives: list[str], unit: str) -> dict:
    result = {
        "candidates": [
            {"name": c.name, "setup": c.setup, "solve": c.solve, "nodes": c.nodes}
            for c in candidates
        ],
        "crossovers": [],
        "evaluated": [],
        "solve_counts": solves,
    }
    for objective in objectives:
        for i, a in enumerate(candidates):
            for b in candidates[i + 1:]:
                result["crossovers"].append(crossover(a, b, objective))
        if solves:
            result["evaluated"].extend(evaluate(candidates, solves, objective))
    if not solves:
        result["note"] = (
            "No solve counts supplied, so per-solve cost, setup share and ranking are "
            "omitted by design: each is a function of the production solve count and is "
            "false without one. Use the crossovers above to locate the regime boundary, "
            "or pass --solves to evaluate specific counts."
        )
    result["resource_unit"] = unit
    return result


def render(result: dict) -> str:
    lines = ["candidates (one-time, per-solve, resource):"]
    for c in result["candidates"]:
        lines.append(f"  {c['name']}: setup {c['setup']:g}s, solve {c['solve']:g}s/solve, {c['nodes']:g} nodes")
    lines.append("")
    lines.append("crossovers:")
    for x in result["crossovers"]:
        n = x["crossover_solves"]
        where = f"N* = {n:.1f} solves -- {x['relation']}" if n is not None else x["relation"]
        lines.append(f"  [{x['objective']}] {x['a']} vs {x['b']}: {where}")
    if result["evaluated"]:
        lines.append("")
        unit = result["resource_unit"]
        lines.append(f"evaluated (resource in {unit}):")
        header = f"  {'objective':9} {'N':>8} {'candidate':22} {'total':>16} {'per solve':>12} {'setup share':>12} {'vs best':>8}"
        lines.append(header)
        for r in result["evaluated"]:
            lines.append(
                f"  {r['objective']:9} {r['solves']:>8} {r['candidate']:22} "
                f"{r['total']:>16.1f} {r['per_solve']:>12.3f} {r['setup_share']:>11.1%} {r['relative_to_best']:>8.3f}"
            )
    if "note" in result:
        lines.extend(["", result["note"]])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        candidates = build(args.candidate)
        if args.solves is not None:
            if not args.solves or any(n < 1 for n in args.solves):
                raise InputError("--solves takes one or more counts of at least 1")
        objectives = list(OBJECTIVES) if args.objective == "both" else [args.objective]
        result = report(candidates, args.solves, objectives, args.resource_unit)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
