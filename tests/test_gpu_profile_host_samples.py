#!/usr/bin/env python3
"""Checks for the host-samples subcommand.

It exists because `idle-attribution` and `window-breakdown` both *size* host time
they cannot name -- as `residual` and as the uncovered remainder -- and neither can
say which code was running, since the time is unattributed exactly when no traced
call is in progress. Sampling is the only instrument in a capture that answers it.
Characterising such a window was hand-derived four times in one session, which
crosses §prefer-a-tool's threshold, and on that capture it named a 55 s stretch of
an 88 s startup window that every traced category reported as empty.

The rules these pin are the ones a plausible implementation gets wrong: a count is
not a duration, only the leaf frame is counted, and a format that cannot resolve
symbols must say so rather than report zero.

Every perturbation below asserts it landed before the assertion runs.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gpu-profile-summary.py"
NSYS = ROOT / "tools" / "gpu_profile" / "nsys.py"
METRICS = ROOT / "tools" / "gpu_profile" / "metrics.py"
ROCPD = ROOT / "tools" / "gpu_profile" / "rocpd.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import PerturbationMixin  # noqa: E402
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


class HostSampleTests(unittest.TestCase):
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

    # -- what it names --------------------------------------------------------

    def test_it_names_the_leaf_symbols_it_sampled(self):
        out = self.payload("host-samples", str(self.nsys))
        self.assertTrue(out["available"])
        self.assertEqual(out["total_samples"], 200)
        top = out["by_symbol"][0]
        self.assertEqual(top["name"], "host_compute")
        self.assertEqual(top["samples"], 120)
        self.assertAlmostEqual(top["pct_of_samples"], 60.0, places=6)

    def test_only_the_leaf_frame_is_counted(self):
        """Every fixture sample carries a depth-1 `caller_frame`. Counting all
        frames would rank it first and double every total, which is the ordinary
        way a hand-written sampling query goes wrong."""
        out = self.payload("host-samples", str(self.nsys))
        names = [r["name"] for r in out["by_symbol"]]
        self.assertNotIn("caller_frame", names)
        self.assertEqual(sum(r["samples"] for r in out["by_symbol"]), out["total_samples"])

    def test_modules_are_reported_beside_symbols(self):
        out = self.payload("host-samples", str(self.nsys))
        self.assertEqual(out["by_module"][0]["name"], "app_binary")
        self.assertEqual(out["by_module"][0]["samples"], 120)
        self.assertEqual(
            sum(r["samples"] for r in out["by_module"]), out["total_samples"]
        )

    def test_the_window_bounds_what_is_counted(self):
        whole = self.payload("host-samples", str(self.nsys))
        narrow = self.payload(
            "host-samples", str(self.nsys),
            "--start-ns", "520000000", "--end-ns", "570000000",
        )
        self.assertLess(narrow["total_samples"], whole["total_samples"])
        self.assertGreater(narrow["total_samples"], 0)

    # -- a count is not a duration -------------------------------------------

    def test_no_row_carries_a_duration(self):
        """The reading this forbids: treating a sample share as a time share. The
        capture's sampling period is a perf-event period, not a fixed rate, and
        samples are summed over every thread, so seconds would be wrong twice."""
        out = self.payload("host-samples", str(self.nsys))
        for row in out["by_symbol"] + out["by_module"]:
            self.assertEqual(set(row), {"name", "module", "samples", "pct_of_samples"})
        self.assertTrue(any("not a duration" in c for c in out["caveats"]))

    def test_the_leaf_only_reading_is_caveated(self):
        out = self.payload("host-samples", str(self.nsys))
        self.assertTrue(any("leaf frame" in c for c in out["caveats"]))

    def test_the_multi_thread_reading_is_caveated(self):
        out = self.payload("host-samples", str(self.nsys))
        self.assertEqual(out["threads_sampled"], 2)
        self.assertTrue(any("sampled threads" in c for c in out["caveats"]))

    # -- thread state ---------------------------------------------------------

    def test_blocked_threads_are_split_out_and_caveated(self):
        """A sample on a Waiting thread is a blocked thread, not a computing one.
        Ranking them together without saying so repeats the OS-attribution defect
        conventions/profile-metrics.md records, where an unfiltered progress thread
        covered 100% of a window."""
        out = self.payload("host-samples", str(self.nsys))
        states = {s["state"]: s["samples"] for s in out["by_thread_state"]}
        self.assertEqual(states, {"Running": 170, "Waiting": 30})
        self.assertTrue(any("not in the Running state" in c for c in out["caveats"]))

    # -- unavailable is not empty ---------------------------------------------

    def test_a_format_without_symbol_resolution_says_so(self):
        """rocpd records samples but carries no symbol column this implementation
        has verified against a real capture. That must read as "not implemented",
        never as "no samples" -- the second is a claim about the run."""
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "r.db"
            shutil.copy(self.rocpd, db)
            conn = sqlite3.connect(db)
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'rocpd_sample%'"
            ).fetchone()[0]
            conn.execute(
                f'INSERT INTO "{tbl}" (nid,pid,tid,start,end) VALUES (0,1,1,1000,2000)'
            )
            conn.commit()
            conn.close()
            out = self.payload("host-samples", str(db))
        self.assertFalse(out["available"])
        self.assertIn("not implemented", out["unavailable_reason"])
        self.assertNotIn("no CPU sampling", out["unavailable_reason"])

    def test_a_capture_without_sampling_is_unavailable_not_zero(self):
        out = self.payload("host-samples", str(self.rocpd))
        self.assertFalse(out["available"])
        self.assertIn("no CPU sampling", out["unavailable_reason"])
        self.assertTrue(any("not an empty one" in c for c in out["caveats"]))

    def test_the_profile_is_not_written_to(self):
        before = self.nsys.read_bytes()
        self.payload("host-samples", str(self.nsys))
        self.assertEqual(self.nsys.read_bytes(), before)


class HostSampleControls(PerturbationMixin, unittest.TestCase):
    """Each control perturbs the implementation and asserts the perturbation landed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.nsys = build_synthetic_nsys_db(root / "n.sqlite")
        self.rocpd = build_synthetic_rocpd_db(root / "r.db")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_counting_every_frame_instead_of_the_leaf_is_caught(self):
        before = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.perturb(NSYS, "WHERE c.stackDepth = 0", "WHERE c.stackDepth >= 0")
        after = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertIn(
            "caller_frame", [r["name"] for r in after["by_symbol"]],
            "counting every frame did not surface the caller; the control is inert",
        )
        self.assertNotIn("caller_frame", [r["name"] for r in before["by_symbol"]])

    def test_a_hardcoded_capability_is_caught(self):
        """The original defect: nsys reported has_cpu_samples=False unconditionally
        while real captures carried millions of callchain rows."""
        before = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertTrue(before["available"])
        self.perturb(
            NSYS,
            'has_cpu_samples=(\n                    self._table_has_data("COMPOSITE_EVENTS")',
            'has_cpu_samples=(\n                    False and self._table_has_data("COMPOSITE_EVENTS")',
        )
        after = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertFalse(after["available"])

    def test_reporting_an_unresolvable_format_as_empty_is_caught(self):
        """If rocpd returned an empty aggregate instead of None, "cannot resolve
        symbols" would silently become "the host did nothing"."""
        self.perturb(
            ROCPD,
            "        `capabilities.has_cpu_samples` still reports truthfully whether the capture\n"
            "        has any.\n        \"\"\"\n        return None",
            "        `capabilities.has_cpu_samples` still reports truthfully whether the capture\n"
            "        has any.\n        \"\"\"\n        return HostSampleAggregates("
            "total_samples=0, threads_sampled=0, by_symbol=[], by_module=[], by_thread_state=[])",
        )
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "r.db"
            shutil.copy(self.rocpd, db)
            conn = sqlite3.connect(db)
            tbl = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'rocpd_sample%'"
            ).fetchone()[0]
            conn.execute(
                f'INSERT INTO "{tbl}" (nid,pid,tid,start,end) VALUES (0,1,1,1000,2000)'
            )
            conn.commit()
            conn.close()
            out = json.loads(run("host-samples", str(db)).stdout)
        self.assertTrue(
            out["available"], "perturbation did not take effect"
        )
        self.assertEqual(out["total_samples"], 0)

    def test_dropping_the_not_a_duration_caveat_is_caught(self):
        """The caveat lives in metrics.py, so the control must perturb metrics.py.
        The first version of this test perturbed nsys.py with an edit that replaced
        a string with itself and then asserted the caveat was still present -- a
        control that passes whatever the code does, which is the defect
        conventions/repeated-work.md names as indistinguishable from a working
        guard."""
        before = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertTrue(any("not a duration" in c for c in before["caveats"]))
        self.perturb(
            METRICS,
            '        "Samples are a count, not a duration.',
            '        "REMOVED BY CONTROL.',
        )
        after = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertFalse(
            any("not a duration" in c for c in after["caveats"]),
            "perturbation did not take effect",
        )

    def test_dropping_the_leaf_frame_caveat_is_caught(self):
        self.perturb(
            METRICS,
            '        "Only the leaf frame is counted,',
            '        "REMOVED BY CONTROL,',
        )
        out = json.loads(run("host-samples", str(self.nsys)).stdout)
        self.assertFalse(any("leaf frame" in c for c in out["caveats"]))

    def test_reporting_an_uninstrumented_capture_as_empty_is_caught(self):
        """`available: False` must not collapse into a zero count: a capture with no
        sampling supports no claim about the host, and equally none that it was
        idle."""
        self.perturb(
            METRICS,
            "    if not profile.capabilities.has_cpu_samples:\n        return _empty(",
            "    if False and not profile.capabilities.has_cpu_samples:\n        return _empty(",
        )
        out = json.loads(run("host-samples", str(self.rocpd)).stdout)
        self.assertNotIn(
            "no CPU sampling", out["unavailable_reason"] or "",
            "perturbation did not take effect",
        )


if __name__ == "__main__":
    unittest.main()
