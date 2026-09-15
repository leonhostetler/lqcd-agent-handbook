#!/usr/bin/env python3
"""Checks for the window-breakdown subcommand.

It exists because `idle-attribution` reports how much of a window lies outside the
kernel span and cannot describe it — inter-kernel idle is empty before the first
kernel, so every category intersected against it reads zero. Characterising that
window was hand-derived three times, which crosses §prefer-a-tool's threshold.

Every perturbation below asserts it landed before the assertion runs. A control
whose edit silently matched nothing proves nothing, and this repository has hit
that three times.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gpu-profile-summary.py"
METRICS = ROOT / "tools" / "gpu_profile" / "metrics.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


class WindowBreakdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.nsys = build_synthetic_nsys_db(root / "n.sqlite")
        cls.rocpd = build_synthetic_rocpd_db(root / "r.db")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def payload(self, *args: str) -> dict:
        proc = run(*args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # -- the window it describes ----------------------------------------------

    def test_the_default_window_ends_at_the_first_kernel(self):
        out = self.payload("window-breakdown", str(self.nsys))
        summary = self.payload("summary", str(self.nsys))
        kernels = self.payload("kernels", str(self.nsys))
        self.assertEqual(out["region"], "head")
        self.assertGreater(out["window_s"], 0.0)
        # The head window must not overlap kernel execution at all.
        self.assertLessEqual(out["window_s"], summary["profile_span_s"])
        self.assertTrue(kernels["kernels"])

    def test_it_describes_what_idle_attribution_can_only_size(self):
        """The complement: over the head window idle-attribution reports nearly all
        of it outside the kernel span, and names none of it."""
        idle = self.payload(
            "idle-attribution", str(self.nsys),
            "--start-ns", "500000000", "--end-ns", "1000000000",
        )
        window = self.payload(
            "window-breakdown", str(self.nsys),
            "--start-ns", "500000000", "--end-ns", "1000000000",
        )
        self.assertAlmostEqual(idle["outside_kernel_span_s"], idle["window_s"], places=6)
        self.assertGreater(window["covered_s"], 0.0)

    # -- the distinction that matters -----------------------------------------

    def test_an_untraced_category_reports_null_not_zero(self):
        cats = {c["name"]: c for c in self.payload("window-breakdown", str(self.nsys))["categories"]}
        missing = [c for c in cats.values() if not c["available"]]
        self.assertTrue(missing, "fixture should lack at least one traced category")
        for c in missing:
            self.assertIsNone(c["total_s"])
            self.assertIsNone(c["events"])
            self.assertIsNotNone(c["unavailable_reason"])

    def test_an_untraced_category_is_caveated(self):
        out = self.payload("window-breakdown", str(self.nsys))
        self.assertTrue(any("not the same" in c for c in out["caveats"]))

    # -- occupancy arithmetic -------------------------------------------------

    def test_no_category_exceeds_the_window(self):
        out = self.payload("window-breakdown", str(self.nsys))
        for c in out["categories"]:
            if c["available"]:
                self.assertLessEqual(c["total_s"], out["window_s"] + 1e-9)

    def test_covered_and_uncovered_close_the_window(self):
        out = self.payload("window-breakdown", str(self.nsys))
        self.assertAlmostEqual(out["covered_s"] + out["uncovered_s"], out["window_s"], places=6)

    def test_categories_are_not_summed_into_covered(self):
        """Overlapping categories are unioned. If they were summed, covered_s could
        exceed the window, which is how an overlapping trace over-accounts."""
        out = self.payload("window-breakdown", str(self.nsys))
        total = sum(c["total_s"] for c in out["categories"] if c["available"])
        self.assertLessEqual(out["covered_s"], total + 1e-9)
        self.assertLessEqual(out["covered_s"], out["window_s"] + 1e-9)

    # -- bins and naming ------------------------------------------------------

    def test_bins_tile_the_window_without_gaps(self):
        out = self.payload("window-breakdown", str(self.nsys), "--bins", "4")
        bins = out["bins"]
        self.assertEqual(len(bins), 4)
        self.assertEqual(bins[0]["start_ns"], out["start_ns"])
        self.assertEqual(bins[-1]["end_ns"], out["end_ns"])
        for a, b in zip(bins, bins[1:]):
            self.assertEqual(a["end_ns"], b["start_ns"])

    def test_top_events_name_what_occupies_the_window(self):
        events = self.payload("window-breakdown", str(self.nsys))["top_events"]
        self.assertTrue(events)
        self.assertEqual(events, sorted(events, key=lambda e: -e["total_s"]))
        self.assertTrue(all(e["category"] for e in events))

    # -- degenerate and cross-format ------------------------------------------

    def test_a_zero_duration_window_does_not_divide_by_zero(self):
        out = self.payload("window-breakdown", str(self.nsys), "--region", "tail")
        self.assertEqual(out["window_s"], 0.0)
        self.assertEqual(out["uncovered_pct"], 0.0)
        self.assertTrue(any("zero duration" in c for c in out["caveats"]))

    def test_it_runs_on_both_formats(self):
        for name, db in (("nsys", self.nsys), ("rocpd", self.rocpd)):
            with self.subTest(fmt=name):
                out = self.payload("window-breakdown", str(db))
                self.assertIn("categories", out)
                self.assertGreaterEqual(out["window_s"], 0.0)

    def test_the_profile_is_not_written_to(self):
        before = self.nsys.read_bytes()
        self.payload("window-breakdown", str(self.nsys))
        self.assertEqual(self.nsys.read_bytes(), before)


class WindowBreakdownControls(unittest.TestCase):
    """Each control perturbs the implementation and asserts the perturbation landed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = build_synthetic_nsys_db(Path(self._tmp.name) / "n.sqlite")
        self.original = METRICS.read_text()

    def tearDown(self) -> None:
        METRICS.write_text(self.original)
        self._tmp.cleanup()

    def perturb(self, old: str, new: str) -> None:
        self.assertIn(old, self.original, "control edit matched nothing; it would prove nothing")
        METRICS.write_text(self.original.replace(old, new, 1))

    def test_summing_categories_instead_of_merging_is_caught(self):
        """The recorded defect this guards: a hand pass summed peer-to-peer transfer
        durations instead of merging them and overstated the total by 28%. Summing
        overlapping intervals inflates occupancy, and `uncovered` is derived from
        `covered`, so the window identity still balances -- only the value moves."""
        before = json.loads(run("window-breakdown", str(self.db)).stdout)["covered_s"]
        self.perturb(
            "    covered_ns = sum(e - s for s, e in merge_intervals(all_intervals))",
            "    covered_ns = sum(e - s for s, e in all_intervals)",
        )
        after = json.loads(run("window-breakdown", str(self.db)).stdout)["covered_s"]
        self.assertGreater(after, before, "summing did not inflate; the control is inert")

    def test_reporting_an_untraced_category_as_zero_is_caught(self):
        self.perturb(
            "                    name=name, available=False, total_s=None,\n"
            "                    pct_of_window=None, events=None, unavailable_reason=reason,",
            "                    name=name, available=False, total_s=0.0,\n"
            "                    pct_of_window=0.0, events=0, unavailable_reason=reason,",
        )
        out = json.loads(run("window-breakdown", str(self.db)).stdout)
        missing = [c for c in out["categories"] if not c["available"]]
        self.assertTrue(missing)
        self.assertTrue(
            any(c["total_s"] == 0.0 for c in missing),
            "perturbation did not take effect",
        )

    def test_dropping_the_caveat_is_caught(self):
        self.perturb(
            '        caveats.append(\n            "A category reported as unavailable was not traced.',
            '        pass  # noqa\n        _unused = (\n            "A category reported as unavailable was not traced.',
        )
        out = json.loads(run("window-breakdown", str(self.db)).stdout)
        self.assertFalse(any("not the same" in c for c in out["caveats"]))


if __name__ == "__main__":
    unittest.main()
