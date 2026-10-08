#!/usr/bin/env python3
"""extract-milc-timings.py solves must account for every solve in MILC output: pass a clean
run, and fail each defect it exists to catch -- a right-hand side above its requested residual,
a MILC NOT converged status, a disagreement between the two, an incomplete input set, an ERROR
line, a missing exit record. It must not count load_evecs_quda's zero-iteration dummy inversion
as a solve. Every negative test first proves its perturbation changed the log. The logs are
synthetic, written here in the record formats of MILC a5f8f9fa with QUDA ba501e4f8."""
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


def conv(iters: int, true: float, n: int | None = None, requested: float = 1e-8) -> str:
    tag = f", n = {n}" if n is not None else ""
    return (f"CG: Convergence at {iters} iterations{tag}, L2 relative residual: "
            f"iterated = {true:e}, true = {true:e} (requested = {requested:e})")


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
        self.assertIn("extract-milc-timings 1.0.0", result.stdout)
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
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("NOT implemented", data["not_implemented"])
        self.assertEqual(len(data["runs"][0]["sets"]), 2)

    def test_an_unreadable_log_is_a_usage_error(self):
        result = self.run_tool(self.dir / "absent.out")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
