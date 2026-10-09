#!/usr/bin/env python3
"""Read MILC staggered-application output (ks_spectrum, ks_measure): account for every solve, and sum its phases.

    extract-milc-timings.py solves LOG [LOG ...] [--json]
    extract-milc-timings.py phases LOG [LOG ...] [--json]

Run it through tools/run-extract-milc-timings, which selects a Python 3.10+ interpreter; a bare
python3 on PATH may be older and cannot parse this file.

One reader of MILC run output, so that a solve or a phase is never counted by an ad-hoc grep.
This version implements solve accounting and per-phase timing. The timing series under
conventions/measurement.md's first-solve rule, and the untraced-control comparison, are not
implemented yet, and the report says so.

`phases` sums the PRTIME records `Aggregate time to <phase> <seconds>` over the input sets of a
log (MILC a5f8f9fa, ks_spectrum/ks_spectrum_includes.h ENDTIME; ks_imp_rhmc prints the same
form). Each such record closes one interval of a single caller-owned timer, so phases do not
overlap and may be added. The report gives each phase's total and record count; the sum of the
top-level `Time =` records; their remainder over the phases, labelled as time outside named
phases, which holds inter-set cleanup and any component timer no phase encloses; and the
`exit:` minus `start:` envelope. `Time to <name>` component timers are listed with their totals
and never added to anything, because whether one nests inside a phase depends on the
application and revision (software/milc/timing.md). ks_measure prints its phases as `Time to`
records, which this version does not separate from component timers; a log with no
`Aggregate time to` record is reported as a problem rather than as zero cost. `CONGRAD5` records
are summarised by count, time, and their `mflops` field weighted by solve time; that field is a
per-rank nominal rate, so the aggregate is given only when the log's `Machine = ..., with <n>
nodes` line names the rank count. Given several logs, a table puts their phases side by side.

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

Exit status for `solves`: 0 when every solve converged by both signals, every set completed and
the run printed its `exit:` record. For `phases`: 0 when every set completed, the run printed its
`exit:` record, and at least one phase record was found. Otherwise 1; 2 on a usage error or an
unreadable log. The standard library only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import statistics
import sys
from pathlib import Path

VERSION = "1.2.0"
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
RE_PHASE = re.compile(r"^Aggregate time to (.+?) (\S+)\s*$")
RE_COMPONENT = re.compile(r"^Time to (.+?)(?: =)? ([-+0-9.eE]+)(?: (?:sec|s))?\s*$")
RE_MFLOPS = re.compile(r"\bmflops = (\S+)")
RE_MACHINE = re.compile(r"^Machine = .*, with (\d+) nodes")
RE_STAMP = re.compile(r"^(start|exit): (.+?)\s*$")


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


def parse_phases(path: str) -> dict:
    with open(path, errors="replace") as handle:
        lines = handle.read().splitlines()
    phases: dict[str, dict] = {}
    pending: dict[str, dict] = {}      # phase records of the input set not yet closed by `Time =`
    components: dict[str, dict] = {}
    times: list[float] = []
    completed = 0
    stamps: dict[str, str] = {}
    ranks = None
    cg = {"records": 0, "time_s": 0.0, "mflops_time": 0.0}
    for line in lines:
        if (m := RE_PHASE.match(line)):
            ph = pending.setdefault(m.group(1), {"seconds": 0.0, "records": 0})
            ph["seconds"] += number(m.group(2))
            ph["records"] += 1
        elif (m := RE_SET_TIME.match(line)):
            times.append(number(m.group(1)))
            for name, ph in pending.items():
                total = phases.setdefault(name, {"seconds": 0.0, "records": 0})
                total["seconds"] += ph["seconds"]
                total["records"] += ph["records"]
            pending = {}
        elif line.startswith("RUNNING COMPLETED"):
            completed += 1
        elif (m := RE_CONGRAD5.match(line)):
            t = number(m.group(1))
            cg["records"] += 1
            cg["time_s"] += t
            if (f := RE_MFLOPS.search(line)):
                cg["mflops_time"] += t * number(f.group(1))
        elif (m := RE_COMPONENT.match(line)):
            c = components.setdefault(m.group(1), {"seconds": 0.0, "records": 0})
            c["seconds"] += number(m.group(2))
            c["records"] += 1
        elif (m := RE_MACHINE.match(line)) and ranks is None:
            ranks = int(m.group(1))
        elif (m := RE_STAMP.match(line)):
            stamps.setdefault(m.group(1), m.group(2))
    envelope = None
    if "start" in stamps and "exit" in stamps:
        try:
            fmt = "%a %b %d %H:%M:%S %Y"
            envelope = (datetime.datetime.strptime(stamps["exit"], fmt)
                        - datetime.datetime.strptime(stamps["start"], fmt)).total_seconds()
        except ValueError:
            envelope = None
    total = sum(times)
    phase_sum = sum(p["seconds"] for p in phases.values())
    per_rank = cg["mflops_time"] / cg["time_s"] / 1e3 if cg["time_s"] else None
    return {"log": path, "ranks": ranks, "input_sets_completed": completed, "time_records": len(times),
            "phases": phases, "phase_sum_s": phase_sum, "time_total_s": total,
            "unclosed_set_phases": pending,
            "outside_named_phases_s": total - phase_sum if times else None,
            "components": components, "start": stamps.get("start"), "exit": stamps.get("exit"),
            "exit_minus_start_s": envelope,
            "congrad5": {"records": cg["records"], "time_s": cg["time_s"],
                         "gflops_per_rank_time_weighted": per_rank,
                         "gflops_aggregate": per_rank * ranks if per_rank is not None and ranks else None}}


def judge_phases(run: dict) -> list[str]:
    problems = []
    if not run["phases"]:
        problems.append("no `Aggregate time to` phase records (a build without PRTIME, or an application "
                        "such as ks_measure that prints its phases as `Time to`)")
    if run["input_sets_completed"] == 0 or run["time_records"] != run["input_sets_completed"]:
        problems.append(f"{run['input_sets_completed']} RUNNING COMPLETED marker(s) against "
                        f"{run['time_records']} `Time =` record(s): an input set is incomplete")
    if run["unclosed_set_phases"]:
        problems.append(f"{len(run['unclosed_set_phases'])} phase(s) recorded after the last `Time =` record: "
                        "a trailing input set did not finish, and its phases are not in the totals")
    if run["outside_named_phases_s"] is not None and run["outside_named_phases_s"] < 0:
        problems.append("the phases exceed the `Time =` total: a phase record is duplicated or misattributed")
    if run["exit"] is None:
        problems.append("no exit: record (the run did not finish)")
    return problems


def report_phases(run: dict, problems: list[str]) -> str:
    total = run["time_total_s"]
    share = lambda s: f"{100 * s / total:5.1f} %" if total else "    n/a"
    out = [f"== {run['log']}",
           f"ranks {run['ranks'] if run['ranks'] is not None else 'unknown (no Machine line)'}; "
           f"input sets completed {run['input_sets_completed']}"]
    out.append(f"    {'phase (Aggregate time to ...)':38s} {'seconds':>10s} {'records':>8s}  share of Time")
    for name, p in run["phases"].items():
        out.append(f"    {name:38s} {p['seconds']:10.1f} {p['records']:8d}  {share(p['seconds'])}")
    out.append(f"    {'sum of phases':38s} {run['phase_sum_s']:10.1f}")
    if run["outside_named_phases_s"] is not None:
        out.append(f"    {'outside named phases':38s} {run['outside_named_phases_s']:10.1f}           "
                   f"{share(run['outside_named_phases_s'])}  (Time total less the phases)")
    out.append(f"    {'Time total (sum of Time = records)':38s} {total:10.1f}")
    env = run["exit_minus_start_s"]
    out.append(f"    {'exit - start':38s} {env:10.0f}" if env is not None else "    exit - start: n/a")
    if run["components"]:
        out.append("    component timers (Time to ..., listed only, never added):")
        for name, c in run["components"].items():
            out.append(f"      {name:36s} {c['seconds']:10.1f} {c['records']:8d}")
    cg = run["congrad5"]
    if cg["records"]:
        rate = cg["gflops_per_rank_time_weighted"]
        agg = cg["gflops_aggregate"]
        out.append(f"    CONGRAD5: {cg['records']} record(s), {cg['time_s']:.1f} s; nominal GFLOP/s per rank, "
                   f"solve-time weighted: {rate:.1f}" if rate is not None else
                   f"    CONGRAD5: {cg['records']} record(s), {cg['time_s']:.1f} s; no mflops field")
        if agg is not None:
            out[-1] += f"; x {run['ranks']} ranks = {agg:.1f}"
    out += [f"PROBLEM: {p}" for p in problems] or ["no problems found"]
    return "\n".join(out)


def compare_phases(runs: list[dict]) -> str:
    names: list[str] = []
    for run in runs:
        names += [n for n in run["phases"] if n not in names]
    labels = [Path(r["log"]).name for r in runs]
    width = max(12, *(len(x) for x in labels))
    out = ["== phase seconds by log", f"    {'phase':38s}" + "".join(f" {x:>{width}s}" for x in labels)]
    for n in names:
        cells = [f"{r['phases'][n]['seconds']:.1f}" if n in r["phases"] else "-" for r in runs]
        out.append(f"    {n:38s}" + "".join(f" {c:>{width}s}" for c in cells))
    for label, key in (("outside named phases", "outside_named_phases_s"), ("Time total", "time_total_s")):
        cells = [f"{r[key]:.1f}" if r[key] is not None else "-" for r in runs]
        out.append(f"    {label:38s}" + "".join(f" {c:>{width}s}" for c in cells))
    return "\n".join(out)


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
    ph = sub.add_parser("phases", help="sum the per-phase timing records in one or more MILC output logs")
    ph.add_argument("logs", nargs="+")
    ph.add_argument("--json", action="store_true", help="emit the full per-log record as JSON")
    args = parser.parse_args(argv)

    reader, judger, writer = ((parse, judge, report) if args.command == "solves"
                              else (parse_phases, judge_phases, report_phases))
    runs, failed = [], False
    for path in args.logs:
        try:
            run = reader(path)
        except OSError as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
            return 2
        problems = judger(run)
        failed |= bool(problems)
        runs.append((run, problems))
    if args.json:
        print(json.dumps({"tool": "extract-milc-timings", "version": VERSION, "command": args.command,
                          "not_implemented": NOT_IMPLEMENTED,
                          "runs": [dict(r, problems=p) for r, p in runs]}, indent=1))
    else:
        print(f"extract-milc-timings {VERSION} {args.command} · {NOT_IMPLEMENTED}")
        for run, problems in runs:
            print(writer(run, problems))
        if args.command == "phases" and len(runs) > 1:
            print(compare_phases([r for r, _ in runs]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
