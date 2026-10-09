#!/usr/bin/env python3
"""extract-milc-timings.py solves must account for every solve in MILC output: pass a clean
run, and fail each defect it exists to catch -- a right-hand side above its requested residual,
a heavy-quark residual above its request, a MILC NOT converged status, a disagreement between
the two, an incomplete input set, an ERROR line, a missing exit record. It must accept a
heavy-quark solve that QUDA's own rule accepts, and must not count load_evecs_quda's
zero-iteration dummy inversion as a solve.

extract-milc-timings.py phases must sum the `Aggregate time to` phase records across input sets,
report the remainder of the `Time =` records over them, list `Time to` component timers without
adding them, weight CONGRAD5 throughput by solve time, and fail a log with no phase records, an
incomplete input set, or no exit record.

Every negative test first proves its perturbation changed the log. The logs are synthetic,
written here in the record formats of MILC a5f8f9fa with QUDA ba501e4f8."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "extract-milc-timings.py"


def conv(iters: int, true: float, n: int | None = None, requested: float = 1e-8,
         hq: float | None = None, hq_requested: float = 1e-7) -> str:
    tag = f", n = {n}" if n is not None else ""
    tail = f", heavy-quark residual = {hq:e} (requested = {hq_requested:e})" if hq is not None else ""
    return (f"CG: Convergence at {iters} iterations{tag}, L2 relative residual: "
            f"iterated = {true:e}, true = {true:e} (requested = {requested:e}){tail}")


def heavy_solve(true: float, hq: float, status: str = "OK") -> list[str]:
    """One heavy-quark UML solve: an unreachable L2 request of 1e-16 beside a heavy-quark request."""
    return ["Solving for 1 source(s) without deflation for parity 2",
            conv(460, true, requested=1e-16, hq=hq),
            "CONGRAD5: time = 1.9e+00 (fn_QUDA D) masses = 1 srcs = 1 iters = 460 mflops = 2.6e+06",
            f" {status} converged final_rsq= 1.3e-31 (cf 1e-32) rel = 3.7e-15 (cf 1e-14) restarts = 0 iters= 460 "]


def solve(parity: int, iters: int, true: float, status: str = "OK") -> list[str]:
    return [f"Solving for 1 source(s) with deflation for parity {parity}", conv(iters, true),
            f"CONGRAD5: time = 1.0e+00 (fn_QUDA D) masses = 1 srcs = 1 iters = {iters} mflops = 1.0e+05",
            f" {status} converged final_rsq= 1e-17 (cf 1e-16) rel = 1 (cf 0) restarts = 1 iters= {iters} "]


def input_set(trues=(5e-9, 6e-9), statuses=("OK", "OK"), completed=True) -> list[str]:
    out = ["Loading deflation spaces into QUDA",
           "TRLM computed the requested 32 vectors in 10 restart steps and 100 OP*x operations.",
           conv(0, 1.0, requested=1.0), "Time to load deflation space = 40.0 s"]
    out += solve(2, 900, trues[0], statuses[0]) + solve(1, 60, trues[1], statuses[1])
    if completed:
        out += ["RUNNING COMPLETED", "Time = 5.0e+01 seconds"]
    return out


def clean_log() -> str:
    return "\n".join(input_set() + input_set() + ["exit: Thu Oct  8 15:47:11 2026"]) + "\n"


class SolveAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.clean = self.dir / "clean.out"
        self.clean.write_text(clean_log())

    def run_tool(self, *logs: Path, extra=()):
        return subprocess.run([interpreter_for(), str(TOOL), "solves", *extra, *map(str, logs)],
                              text=True, capture_output=True, check=False)

    def perturbed(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text)
        self.assertNotEqual(path.read_text(), self.clean.read_text(), "vacuous perturbation")
        return path

    def test_clean_run_passes_and_excludes_dummy_inversions(self):
        result = self.run_tool(self.clean)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("extract-milc-timings 1.2.0 solves", result.stdout)
        self.assertIn("NOT implemented", result.stdout)
        self.assertEqual(result.stdout.count("2 solve record(s), 2 right-hand side(s)"), 2, result.stdout)
        self.assertEqual(result.stdout.count("dummy inversions excluded: 1"), 2, result.stdout)
        self.assertIn("no problems found", result.stdout)

    def test_a_residual_above_requested_fails_even_when_milc_says_ok(self):
        log = self.perturbed("above.out", "\n".join(
            input_set() + input_set(trues=(5e-9, 3e+4)) + ["exit: x"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("set 2: 1 right-hand side(s) above the requested residual", result.stdout)
        self.assertIn("disagree", result.stdout)

    def test_milc_not_converged_fails(self):
        log = self.perturbed("not.out", "\n".join(
            input_set() + input_set(trues=(5e-9, 2e-8), statuses=("OK", "NOT")) + ["exit: x"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("set 2: 1 solve record(s) MILC reports NOT converged", result.stdout)
        self.assertNotIn("disagree", result.stdout)

    def test_an_incomplete_set_and_missing_exit_fail(self):
        log = self.perturbed("crash.out", "\n".join(
            input_set() + input_set(completed=False) + ["ERROR: Solver appears to have diverged"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("set 2: incomplete", result.stdout)
        self.assertIn("1 ERROR line(s)", result.stdout)
        self.assertIn("no exit: record", result.stdout)

    def test_a_multi_source_record_counts_every_right_hand_side(self):
        rhs = [conv(1000, 5e-9, n=k) for k in range(15)] + [conv(1000, 2e-8, n=15)]
        record = ["Solving for 16 source(s) with deflation for parity 2", *rhs,
                  "CONGRAD5: time = 1.0e+01 (fn_QUDA D) masses = 1 srcs = 16 iters = 1000 mflops = 1.0e+05",
                  " NOT converged final_rsq= 4e-16 (cf 1e-16) rel = 1 (cf 0) restarts = 1 iters= 1000 ",
                  "RUNNING COMPLETED", "exit: x"]
        log = self.perturbed("multi.out", "\n".join(record) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("1 solve record(s), 16 right-hand side(s)", result.stdout)
        self.assertIn("above requested: 1 rhs", result.stdout)

    def test_a_heavy_quark_solve_met_by_its_heavy_quark_residual_passes(self):
        log = self.perturbed("hq.out", "\n".join(
            input_set() + heavy_solve(3.6e-16, 6.1e-8) + ["RUNNING COMPLETED", "exit: x"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("above requested: 0 rhs; met by heavy-quark residual only: 1 rhs", result.stdout)
        self.assertNotIn("disagree", result.stdout)

    def test_a_heavy_quark_residual_above_its_request_fails(self):
        log = self.perturbed("hq-above.out", "\n".join(
            input_set() + heavy_solve(3.6e-16, 2.0e-7) + ["RUNNING COMPLETED", "exit: x"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("set 2: 1 right-hand side(s) above the requested residual", result.stdout)
        self.assertIn("disagree", result.stdout)

    def test_both_residuals_must_hold_when_l2_is_met(self):
        log = self.perturbed("hq-l2-met.out", "\n".join(
            input_set() + heavy_solve(5.0e-17, 2.0e-7, status="NOT") + ["RUNNING COMPLETED", "exit: x"]) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("above requested: 1 rhs; met by heavy-quark residual only: 0 rhs", result.stdout)
        self.assertNotIn("disagree", result.stdout)

    def test_cpu_output_is_judged_by_milc_status_alone(self):
        cpu = ["CONGRAD5: time = 5.3e-02 (fn D) masses = 1 iters = 99 mflops = 9.0e+03",
               " OK converged final_rsq= 7.9e-17 (cf 1e-16) rel = 1 (cf 0) restarts = 1 iters= 99",
               "RUNNING COMPLETED", "exit: x"]
        log = self.perturbed("cpu.out", "\n".join(cpu) + "\n")
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("unlabelled/unlabelled: 1 record(s)", result.stdout)
        failing = self.perturbed("cpu-not.out", "\n".join(cpu).replace(" OK converged", " NOT converged") + "\n")
        self.assertEqual(self.run_tool(failing).returncode, 1)

    def test_json_carries_version_and_the_unimplemented_scope(self):
        result = self.run_tool(self.clean, extra=["--json"])
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["version"], "1.2.0")
        self.assertIn("NOT implemented", data["not_implemented"])
        self.assertEqual(len(data["runs"][0]["sets"]), 2)

    def test_an_unreadable_log_is_a_usage_error(self):
        result = self.run_tool(self.dir / "absent.out")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


def phase_set(first: bool) -> list[str]:
    out = ["Aggregate time to setup 1.0e+01"] if first else []
    out += ["Aggregate time to read lattice 2.0e+00" if first else "Aggregate time to read lattice 1.0e+00",
            "Time to reload gauge configuration = 1.5e+00",
            "Time to APE smear 3.0e-01 sec",
            "CONGRAD5: time = 1.0e+00 (fn_QUDA D) masses = 1 srcs = 1 iters = 10 mflops = 1.0e+06",
            "CONGRAD5: time = 3.0e+00 (fn_QUDA D) masses = 1 srcs = 1 iters = 30 mflops = 2.0e+06",
            "Aggregate time to compute propagators 5.0e+01",
            "RUNNING COMPLETED", "Time = 7.0e+01 seconds" if first else "Time = 5.5e+01 seconds"]
    return out


def phase_log(sets: list[list[str]] | None = None, machine: bool = True, finished: bool = True) -> str:
    head = (["Machine = QMP (portable), with 4 nodes"] if machine else []) + ["start: Thu Oct  8 15:00:00 2026"]
    body = sets if sets is not None else [phase_set(True), phase_set(False)]
    tail = ["exit: Thu Oct  8 15:02:05 2026"] if finished else []
    return "\n".join(head + [line for st in body for line in st] + tail) + "\n"


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.clean = self.dir / "clean.out"
        self.clean.write_text(phase_log())

    def run_tool(self, *logs: Path, extra=()):
        return subprocess.run([interpreter_for(), str(TOOL), "phases", *extra, *map(str, logs)],
                              text=True, capture_output=True, check=False)

    def perturbed(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text)
        self.assertNotEqual(path.read_text(), self.clean.read_text(), "vacuous perturbation")
        return path

    def json_run(self, path: Path) -> dict:
        result = self.run_tool(path, extra=["--json"])
        data = json.loads(result.stdout)
        self.assertEqual(data["command"], "phases")
        return data["runs"][0]

    def test_clean_log_sums_phases_and_never_adds_component_timers(self):
        result = self.run_tool(self.clean)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("extract-milc-timings 1.2.0 phases", result.stdout)
        self.assertIn("no problems found", result.stdout)
        run = self.json_run(self.clean)
        self.assertEqual(run["phases"]["compute propagators"], {"seconds": 100.0, "records": 2})
        self.assertEqual(run["phases"]["read lattice"], {"seconds": 3.0, "records": 2})
        self.assertEqual(run["phase_sum_s"], 113.0)
        self.assertEqual(run["time_total_s"], 125.0)
        self.assertEqual(run["outside_named_phases_s"], 12.0)
        self.assertEqual(run["components"]["reload gauge configuration"], {"seconds": 3.0, "records": 2})
        self.assertAlmostEqual(run["components"]["APE smear"]["seconds"], 0.6)
        self.assertEqual(run["exit_minus_start_s"], 125.0)

    def test_congrad5_throughput_is_solve_time_weighted_and_scaled_by_ranks(self):
        run = self.json_run(self.clean)
        self.assertEqual(run["ranks"], 4)
        self.assertEqual(run["congrad5"]["records"], 4)
        self.assertAlmostEqual(run["congrad5"]["gflops_per_rank_time_weighted"], 1750.0)
        self.assertAlmostEqual(run["congrad5"]["gflops_aggregate"], 7000.0)
        log = self.perturbed("nomachine.out", phase_log(machine=False))
        run = self.json_run(log)
        self.assertIsNone(run["ranks"])
        self.assertIsNone(run["congrad5"]["gflops_aggregate"])
        self.assertIn("ranks unknown", self.run_tool(log).stdout)

    def test_a_log_without_phase_records_fails(self):
        measure = [[line.replace("Aggregate time to", "Time to") for line in st]
                   for st in (phase_set(True), phase_set(False))]
        log = self.perturbed("measure.out", phase_log(measure))
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no `Aggregate time to` phase records", result.stdout)

    def test_an_incomplete_set_and_a_missing_exit_fail(self):
        crashed = phase_set(False)[:-2]
        log = self.perturbed("crash.out", phase_log([phase_set(True), crashed], finished=False))
        result = self.run_tool(log)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("a trailing input set did not finish", result.stdout)
        self.assertIn("no exit: record", result.stdout)
        run = self.json_run(log)
        self.assertEqual(run["phases"]["compute propagators"], {"seconds": 50.0, "records": 1})
        self.assertEqual(run["outside_named_phases_s"], 8.0)

    def test_several_logs_are_compared_side_by_side(self):
        other = self.perturbed("other.out", phase_log([phase_set(True)]))
        result = self.run_tool(self.clean, other)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("== phase seconds by log", result.stdout)
        row = [line for line in result.stdout.splitlines() if line.strip().startswith("compute propagators")][-1]
        self.assertEqual(row.split()[-2:], ["100.0", "50.0"])


if __name__ == "__main__":
    unittest.main()
