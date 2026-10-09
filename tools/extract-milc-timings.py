#!/usr/bin/env python3
"""Read MILC staggered-application output (ks_spectrum, ks_measure) and account for every solve.

    extract-milc-timings.py solves LOG [LOG ...] [--json]

Run it through tools/run-extract-milc-timings, which selects a Python 3.10+ interpreter; a bare
python3 on PATH may be older and cannot parse this file.

One reader of MILC run output, so that a solve is never counted by an ad-hoc grep. This version
implements solve accounting only. The timing series under conventions/measurement.md's
first-solve rule, and the untraced-control comparison, are not implemented yet, and the report
says so.

A solve is one `CONGRAD5` record. Its convergence is judged by two signals that the output
prints independently, and the tool reports both:

  - the QUDA path's `CG: Convergence at <n> iterations[, n = <k>], ... true = <t> (requested = <r>)`
    lines, one per right-hand side. QUDA prints this line for a solve that stopped at its
    iteration limit too, so its presence is not convergence. A right-hand side meets its request
    when true <= requested. Where the line also carries `heavy-quark residual = <h> (requested =
    <q>)`, QUDA's own rule applies (QUDA ba501e4f8, lib/solver.cpp Solver::convergence and
    lib/inv_cg_quda.cpp L2breakdown): both residuals met, or the heavy-quark residual alone once
    the L2 norm has stalled at its precision floor. A right-hand side met that second way is
    counted separately, never folded into the clean count;
  - MILC's status line after each record, ` OK converged final_rsq= ...` or ` NOT converged ...`.

A disagreement between them is reported as an inconsistency. A QUDA convergence line that no
`CONGRAD5` record follows is not a solve: `load_evecs_quda` runs one dummy inversion at zero
iterations per input set to trigger the eigensolve. Those are counted and excluded.

Input sets are delimited by `RUNNING COMPLETED`, which the applications print once per set;
records after the last one form an incomplete set. Per set the report gives solve records and
right-hand sides by parity and deflation, iteration minimum, median and maximum, the summed
`CONGRAD5` time, the worst true residual, deflation-space loads and their times, fresh `TRLM`
eigensolves, other-parity reconstructions, and the set's `Time =` record. Parity is MILC's code:
2 even, 1 odd, 3 even and odd.

Exit status: 0 when every solve converged by both signals, every set completed and the run
printed its `exit:` record; 1 otherwise; 2 on a usage error or an unreadable log. The standard
library only.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys

VERSION = "1.1.0"
NOT_IMPLEMENTED = "timing series under the first-solve rule and the untraced-control comparison: NOT implemented"

PARITY = {"1": "odd", "2": "even", "3": "evenandodd"}
RE_SOLVING = re.compile(r"^Solving for (\d+) source\(s\) (with|without) deflation for parity (\d+)")
RE_QUDA_CONV = re.compile(
    r"^CG: Convergence at (\d+) iterations(?:, n = (\d+))?, L2 relative residual: "
    r"iterated = (\S+), true = (\S+) \(requested = (\S+)\)"
    r"(?:, heavy-quark residual = (\S+) \(requested = (\S+)\))?")
RE_CONGRAD5 = re.compile(r"^CONGRAD5: time = (\S+) .*?iters = (\d+)")
RE_SRCS = re.compile(r"\bsrcs = (\d+)")
RE_STATUS = re.compile(r"^\s*(OK|NOT) converged final_rsq= (\S+) \(cf (\S+)\)")
RE_SET_TIME = re.compile(r"^Time = (\S+) seconds")
RE_LOAD_TIME = re.compile(r"^Time to load deflation space = (\S+) s")
RE_OTHER_PARITY = re.compile(r"^Time to reconstruct other parity eigenvectors = (\S+) s")


def number(text: str) -> float:
    return float(text.rstrip(",;"))


def new_set() -> dict:
    return {"solves": [], "dummy_inversions": 0, "deflation_loads": [], "trlm_eigensolves": 0,
            "other_parity_reconstructions": [], "set_time_s": None, "completed": False}


def parse(path: str) -> dict:
    with open(path, errors="replace") as handle:
        lines = handle.read().splitlines()
    sets: list[dict] = []
    cur = new_set()
    solving: dict | None = None      # last "Solving for" header, consumed by the next CONGRAD5
    pending: list[dict] = []         # QUDA convergence lines not yet claimed by a CONGRAD5
    last_solve: dict | None = None   # waits for MILC's status line
    errors: list[str] = []
    exit_record = False

    def flush_pending():
        nonlocal pending
        # QUDA convergence lines with no CONGRAD5 after them: the dummy inversion of a load.
        cur["dummy_inversions"] += sum(1 for p in pending if p["iterations"] == 0)
        cur.setdefault("unclaimed_convergence_lines", 0)
        cur["unclaimed_convergence_lines"] += sum(1 for p in pending if p["iterations"] != 0)
        pending = []

    for line in lines:
        if (m := RE_SOLVING.match(line)):
            flush_pending()
            solving = {"sources": int(m.group(1)), "deflation": m.group(2),
                       "parity": PARITY.get(m.group(3), m.group(3))}
        elif (m := RE_QUDA_CONV.match(line)):
            pending.append({"iterations": int(m.group(1)), "true": number(m.group(4)),
                            "requested": number(m.group(5)),
                            "hq": number(m.group(6)) if m.group(6) else None,
                            "hq_requested": number(m.group(7)) if m.group(7) else None})
        elif (m := RE_CONGRAD5.match(line)):
            s = RE_SRCS.search(line)
            rhs = [p for p in pending if p["iterations"] != 0] or pending
            solve = {"time_s": number(m.group(1)), "iterations": int(m.group(2)),
                     "rhs": int(s.group(1)) if s else 1,
                     "parity": solving["parity"] if solving else "unlabelled",
                     "deflation": solving["deflation"] if solving else "unlabelled",
                     "quda_true": [p["true"] for p in rhs],
                     "quda_requested": [p["requested"] for p in rhs],
                     "quda_hq": [p["hq"] for p in rhs],
                     "quda_hq_requested": [p["hq_requested"] for p in rhs],
                     "milc_status": None}
            cur["dummy_inversions"] += sum(1 for p in pending if p not in rhs and p["iterations"] == 0)
            pending, solving = [], None
            cur["solves"].append(solve)
            last_solve = solve
        elif (m := RE_STATUS.match(line)):
            if last_solve is not None and last_solve["milc_status"] is None:
                last_solve["milc_status"] = m.group(1)
            last_solve = None
        elif line.startswith("Loading deflation spaces into QUDA"):
            flush_pending()
        elif (m := RE_LOAD_TIME.match(line)):
            flush_pending()
            cur["deflation_loads"].append(number(m.group(1)))
        elif (m := RE_OTHER_PARITY.match(line)):
            cur["other_parity_reconstructions"].append(number(m.group(1)))
        elif line.startswith("TRLM computed the requested"):
            cur["trlm_eigensolves"] += 1
        elif line.startswith("RUNNING COMPLETED"):
            flush_pending()
            cur["completed"] = True
            sets.append(cur)
            cur = new_set()
        elif (m := RE_SET_TIME.match(line)):
            target = sets[-1] if sets and sets[-1]["set_time_s"] is None and not cur["solves"] else cur
            target["set_time_s"] = number(m.group(1))
        elif line.startswith("ERROR"):
            errors.append(line.strip())
        elif line.startswith("exit: "):
            exit_record = True
    flush_pending()
    if cur["solves"] or cur["deflation_loads"] or cur["dummy_inversions"] or not sets:
        sets.append(cur)
    return {"log": path, "sets": sets, "errors": errors, "exit_record": exit_record}


def verdict(true: float, requested: float, hq: float | None, hq_requested: float | None) -> str:
    """One right-hand side: 'met', 'heavy-quark' (met by the heavy-quark residual alone after the
    L2 norm stalled), or 'above'."""
    hq_met = hq is None or hq <= hq_requested
    if true <= requested and hq_met:
        return "met"
    return "heavy-quark" if hq is not None and hq_met else "above"


def verdicts(solve: dict) -> list[str]:
    return [verdict(*v) for v in zip(solve["quda_true"], solve["quda_requested"],
                                     solve["quda_hq"], solve["quda_hq_requested"])]


def judge(run: dict) -> list[str]:
    """Annotate each set with its summary; return the run's problems."""
    problems: list[str] = []
    for i, st in enumerate(run["sets"], 1):
        solves = st["solves"]
        above = sum(v == "above" for s in solves for v in verdicts(s))
        by_hq = sum(v == "heavy-quark" for s in solves for v in verdicts(s))
        not_conv = sum(1 for s in solves if s["milc_status"] == "NOT")
        no_status = sum(1 for s in solves if s["milc_status"] is None)
        inconsistent = sum(
            1 for s in solves if s["quda_true"] and s["milc_status"] is not None
            and (("above" in verdicts(s)) != (s["milc_status"] == "NOT")))
        trues = [t for s in solves for t in s["quda_true"]]
        groups: dict[str, dict] = {}
        for s in solves:
            g = groups.setdefault(f'{s["parity"]}/{s["deflation"]}', {"records": 0, "rhs": 0, "iterations": []})
            g["records"] += 1
            g["rhs"] += s["rhs"]
            g["iterations"].append(s["iterations"])
        st["summary"] = {
            "solve_records": len(solves), "rhs": sum(s["rhs"] for s in solves),
            "groups": {k: {"records": v["records"], "rhs": v["rhs"], "iterations_min": min(v["iterations"]),
                           "iterations_median": statistics.median(v["iterations"]),
                           "iterations_max": max(v["iterations"])} for k, v in groups.items()},
            "congrad5_time_s": sum(s["time_s"] for s in solves),
            "worst_true_residual": max(trues) if trues else None,
            "rhs_above_requested": above, "rhs_met_by_heavy_quark_only": by_hq,
            "milc_not_converged": not_conv,
            "milc_status_missing": no_status, "inconsistent_records": inconsistent}
        tag = f"set {i}"
        if not st["completed"]:
            problems.append(f"{tag}: incomplete (no RUNNING COMPLETED)")
        if above:
            problems.append(f"{tag}: {above} right-hand side(s) above the requested residual")
        if not_conv:
            problems.append(f"{tag}: {not_conv} solve record(s) MILC reports NOT converged")
        if no_status:
            problems.append(f"{tag}: {no_status} solve record(s) with no MILC status line")
        if inconsistent:
            problems.append(f"{tag}: {inconsistent} record(s) where QUDA's true residual and MILC's status disagree")
        if st.get("unclaimed_convergence_lines"):
            problems.append(f"{tag}: {st['unclaimed_convergence_lines']} nonzero-iteration convergence line(s) "
                            "with no CONGRAD5 record")
    if run["errors"]:
        problems.append(f"{len(run['errors'])} ERROR line(s); first: {run['errors'][0][:160]}")
    if not run["exit_record"]:
        problems.append("no exit: record (the run did not finish)")
    return problems


def report(run: dict, problems: list[str]) -> str:
    out = [f"== {run['log']}"]
    for i, st in enumerate(run["sets"], 1):
        sm = st["summary"]
        worst = f"{sm['worst_true_residual']:.3e}" if sm["worst_true_residual"] is not None else "n/a (no QUDA lines)"
        set_time = f"{st['set_time_s']:.1f} s" if st["set_time_s"] is not None else "none"
        loads = ", ".join(f"{t:g} s" for t in st["deflation_loads"]) or "none"
        out.append(f"set {i}: {'completed' if st['completed'] else 'INCOMPLETE'}; Time = {set_time}; "
                   f"{sm['solve_records']} solve record(s), {sm['rhs']} right-hand side(s); "
                   f"CONGRAD5 time {sm['congrad5_time_s']:.3f} s")
        for key, g in sorted(sm["groups"].items()):
            out.append(f"    parity/deflation {key}: {g['records']} record(s), {g['rhs']} rhs, iterations "
                       f"min {g['iterations_min']} median {g['iterations_median']:g} max {g['iterations_max']}")
        out.append(f"    true residual: worst {worst}; above requested: {sm['rhs_above_requested']} rhs; "
                   f"met by heavy-quark residual only: {sm['rhs_met_by_heavy_quark_only']} rhs; "
                   f"MILC NOT converged: {sm['milc_not_converged']}; status missing: {sm['milc_status_missing']}; "
                   f"inconsistent: {sm['inconsistent_records']}")
        out.append(f"    deflation loads: {loads}; fresh TRLM eigensolves: {st['trlm_eigensolves']}; "
                   f"other-parity reconstructions: {len(st['other_parity_reconstructions'])}; "
                   f"dummy inversions excluded: {st['dummy_inversions']}")
    out.append(f"run: {sum(s['completed'] for s in run['sets'])} set(s) completed; "
               f"ERROR lines {len(run['errors'])}; exit record {'present' if run['exit_record'] else 'ABSENT'}")
    out += [f"PROBLEM: {p}" for p in problems] or ["no problems found"]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", action="version", version=f"extract-milc-timings {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)
    sv = sub.add_parser("solves", help="account for every solve in one or more MILC output logs")
    sv.add_argument("logs", nargs="+")
    sv.add_argument("--json", action="store_true", help="emit the full per-solve record as JSON")
    args = parser.parse_args(argv)

    runs, failed = [], False
    for path in args.logs:
        try:
            run = parse(path)
        except OSError as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
            return 2
        problems = judge(run)
        failed |= bool(problems)
        runs.append((run, problems))
    if args.json:
        print(json.dumps({"tool": "extract-milc-timings", "version": VERSION, "not_implemented": NOT_IMPLEMENTED,
                          "runs": [dict(r, problems=p) for r, p in runs]}, indent=1))
    else:
        print(f"extract-milc-timings {VERSION} solves · {NOT_IMPLEMENTED}")
        for run, problems in runs:
            print(report(run, problems))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
