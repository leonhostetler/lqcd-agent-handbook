#!/usr/bin/env python3
"""quda-mg-observables.py must read level-1 near-null setup streams in BOTH line shapes QUDA
prints -- batched (`n = <j>`, batch width 16) and unbatched (no stream index, batch width 1) --
prefer QUDA's per-stream end-of-solve summary to the trace and read `CA-CG:` as well as `CG:`,
and must emit `first_cycle_contraction` per solve, as the extraction contract in
software/quda/solvers/staggered-multigrid/diagnostics.md defines. Every negative test first
proves its perturbation changed the input. The logs are synthetic, written here, in the line
shapes observed at QUDA 00c7ef33d / MILC 6b9b8a06."""
from __future__ import annotations

import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "quda-mg-observables.py"
CAP = 6
MGPARAMS = f"mg_levels 4\nsetup_maxiter 1 {CAP}\nnvec 1 3\nnvec 2 4\nnvec 3 2\n"


def batched_stream(n: int, last: int) -> list[str]:
    return [f"MG level 1 (GPU): CG: {k:5d} iterations, n = {n}, <r,r> = 1.0e+00, |r|/|b| = 1.0e+00"
            for k in range(last + 1)]


def unbatched_stream(last: int) -> list[str]:
    return [f"MG level 1 (GPU): CG: {k:5d} iterations, <r,r> = 1.0e+00, |r|/|b| = 1.0e+00"
            for k in range(last + 1)]


def ca_batched_stream(n: int, last: int, basis: int = 4) -> list[str]:
    """`ca-cgnr` setup: a trace line once per basis block, so the last one can sit below `last`."""
    return [f"MG level 1 (GPU): CA-CG: {k:5d} iterations, n = {n}, <r,r> = 1.0e+00, |r|/|b| = 1.0e+00"
            for k in range(0, last + 1, basis)]


def summary(final: int, n: int | None = None, solver: str = "CG") -> str:
    index = "" if n is None else f"n = {n}, "
    return (f"MG level 1 (GPU): {solver}: Convergence at {final} iterations, {index}L2 relative residual: "
            "iterated = 1.0e-06, true = 1.0e-06 (requested = 1.0e-06)")


def outer_solve(first: float) -> list[str]:
    return ["GCR:     0 iterations, <r,r> = 1.000000e+00, |r|/|b| = 1.000000e+00",
            f"GCR:     1 iterations, <r,r> = 1.0e-03, |r|/|b| = {first:.6e}",
            "MG level 1 (GPU): GCR:     1 iterations, <r,r> = 1.0e-03, |r|/|b| = 9.000000e-01",
            "GCR:     2 iterations, <r,r> = 1.0e-05, |r|/|b| = 1.000000e-03",
            "GCR: Convergence at 2 iterations, L2 relative residual: iterated = 1.0e-09, "
            "true = 2.0e-09 (requested = 1.0e-08)"]


def log_text(setup: list[str], after: list[str] = (), firsts=(0.05, 0.04)) -> str:
    lines = ["setting up the MG inverter",
             "MG level 0 (GPU): Transfer: using block size 1 x 1 x 1 x 1",
             "MG level 1 (GPU): Transfer: using block size 2 x 2 x 2 x 2",
             *setup,
             "MG level 2 (GPU): Transfer: using block size 2 x 2 x 2 x 2",
             "mat_invert_mg_field_gpu: MG inverter setup complete. Time = 12.5",
             *after]
    for f in firsts:
        lines += outer_solve(f)
    return "\n".join(lines) + "\n"


class ObservablesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.mg = self.dir / "mgparams.txt"
        self.mg.write_text(MGPARAMS)

    def row(self, text: str) -> dict:
        log = self.dir / f"log{len(list(self.dir.iterdir()))}.out"
        log.write_text(text)
        result = subprocess.run([interpreter_for(), str(TOOL), str(log), "--mgparams", str(self.mg)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = list(csv.DictReader(io.StringIO(result.stdout), delimiter="\t"))
        self.assertEqual(len(rows), 1)
        return rows[0]

    def perturbed(self, base: str, new: str) -> str:
        self.assertNotEqual(base, new, "vacuous perturbation")
        return new

    # -- level-1 setup streams --------------------------------------------------------------
    def test_batched_streams_are_counted_per_index(self):
        setup = []
        for n in range(3):
            setup += batched_stream(n, CAP)
        r = self.row(log_text(setup))
        self.assertEqual(r["setup_l1_streams"], "3")
        self.assertEqual(r["setup_l1_capped_fraction"], "1")

    def test_unbatched_streams_are_counted_not_reported_unavailable(self):
        setup = unbatched_stream(CAP) + unbatched_stream(CAP) + unbatched_stream(3)
        r = self.row(log_text(setup))
        self.assertEqual(r["setup_l1_streams"], "3")
        self.assertEqual(r["setup_l1_capped_fraction"], "0.666667")

    def test_unbatched_cap_change_moves_the_fraction(self):
        base = log_text(unbatched_stream(CAP) * 1 + unbatched_stream(CAP) + unbatched_stream(CAP))
        new = self.perturbed(base, log_text(unbatched_stream(CAP) + unbatched_stream(CAP) + unbatched_stream(CAP - 1)))
        self.assertEqual(self.row(base)["setup_l1_capped_fraction"], "1")
        self.assertEqual(self.row(new)["setup_l1_capped_fraction"], "0.666667")

    def test_unbatched_shape_after_setup_is_not_a_setup_stream(self):
        base = log_text(unbatched_stream(CAP))
        new = self.perturbed(base, log_text(unbatched_stream(CAP), after=unbatched_stream(2)))
        self.assertEqual(self.row(base)["setup_l1_streams"], "1")
        self.assertEqual(self.row(new)["setup_l1_streams"], "1")

    def test_no_setup_lines_stays_unavailable(self):
        r = self.row(log_text([]))
        self.assertEqual(r["setup_l1_streams"], "unavailable")
        self.assertEqual(r["setup_l1_capped_fraction"], "unavailable")
        self.assertEqual(r["setup_maxiter_1"], str(CAP))

    # -- per-stream summary (1.7.0) ----------------------------------------------------------
    def test_ca_cg_trace_is_read(self):
        setup = []
        for n in range(3):
            setup += ca_batched_stream(n, 3)
        r = self.row(log_text(setup))
        self.assertEqual(r["setup_l1_streams"], "3")
        self.assertEqual(r["setup_l1_count_source"], "trace")

    def test_summary_gives_the_final_count_the_ca_trace_misses(self):
        # The CA trace stops one block short of the cap; the summary says the cap was reached.
        setup = []
        for n in range(3):
            setup += ca_batched_stream(n, CAP - 2)
        base = log_text(setup)
        self.assertEqual(self.row(base)["setup_l1_capped_fraction"], "0")
        new = self.perturbed(base, log_text(setup + [summary(CAP, n, "CA-CG") for n in range(3)]))
        r = self.row(new)
        self.assertEqual(r["setup_l1_count_source"], "summary")
        self.assertEqual(r["setup_l1_streams"], "3")
        self.assertEqual(r["setup_l1_capped_fraction"], "1")

    def test_summary_count_below_cap_is_not_capped(self):
        setup = []
        for n in range(3):
            setup += batched_stream(n, CAP)
        base = log_text(setup + [summary(CAP, n) for n in range(3)])
        new = self.perturbed(base, log_text(setup + [summary(CAP, 0), summary(CAP, 1), summary(CAP - 1, 2)]))
        self.assertEqual(self.row(base)["setup_l1_capped_fraction"], "1")
        self.assertEqual(self.row(new)["setup_l1_capped_fraction"], "0.666667")

    def test_unbatched_summary_shape_is_read(self):
        setup = unbatched_stream(CAP) + [summary(CAP)] + unbatched_stream(3) + [summary(3)]
        r = self.row(log_text(setup))
        self.assertEqual(r["setup_l1_count_source"], "summary")
        self.assertEqual(r["setup_l1_streams"], "2")
        self.assertEqual(r["setup_l1_capped_fraction"], "0.5")

    def test_cgnr_wrapper_summary_is_never_read(self):
        setup = []
        for n in range(3):
            setup += batched_stream(n, 3)
        base = log_text(setup + [summary(3, n) for n in range(3)])
        new = self.perturbed(base, log_text(setup + [summary(3, n) for n in range(3)]
                                            + [summary(CAP, n, "CGNR") for n in range(3)]))
        self.assertEqual(self.row(base)["setup_l1_capped_fraction"], "0")
        self.assertEqual(self.row(new)["setup_l1_capped_fraction"], "0")
        self.assertEqual(self.row(new)["setup_l1_streams"], "3")

    def test_summary_after_setup_is_not_a_setup_stream(self):
        setup = batched_stream(0, 3) + [summary(3, 0)]
        base = log_text(setup)
        new = self.perturbed(base, log_text(setup, after=[summary(CAP, 0)]))
        self.assertEqual(self.row(new)["setup_l1_streams"], "1")
        self.assertEqual(self.row(new)["setup_l1_capped_fraction"], "0")

    # -- first_cycle_contraction ------------------------------------------------------------
    def test_first_cycle_contraction_is_per_solve_in_order(self):
        r = self.row(log_text([], firsts=(0.05, 0.04, 0.03)))
        self.assertEqual(r["first_cycle_contraction"], "0.05;0.04;0.03")

    def test_prefixed_inner_gcr_line_is_not_read_as_outer(self):
        # Each solve carries an "MG level 1 (GPU): GCR: 1 iterations" line at 0.9; it must not appear.
        r = self.row(log_text([], firsts=(0.05,)))
        self.assertEqual(r["first_cycle_contraction"], "0.05")

    def test_first_cycle_value_change_is_seen(self):
        base = log_text([], firsts=(0.05, 0.04))
        new = self.perturbed(base, log_text([], firsts=(0.05, 0.02)))
        self.assertEqual(self.row(new)["first_cycle_contraction"], "0.05;0.02")

    def test_no_outer_trace_is_unavailable(self):
        text = log_text([], firsts=())
        self.assertNotIn("GCR:     1 iterations, <r,r>", text.replace("MG level 1 (GPU): GCR:", ""))
        r = self.row(text + "MG level 1 (GPU): Transfer: using block size 2 x 2 x 2 x 2\n")
        self.assertEqual(r["first_cycle_contraction"], "unavailable")


if __name__ == "__main__":
    unittest.main()
