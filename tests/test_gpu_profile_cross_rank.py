#!/usr/bin/env python3
"""Checks for multi-rank alignment and for the before/after profile diff.

Imbalance is a cross-rank quantity. On one rank, a rank blocked waiting on its
neighbours looks the same as a rank with a problem of its own, which is why
modes/performance.md tells a session not to read one rank's profile as the job's.
These checks pin that the tool computes the cross-rank view rather than implying
it, and that it refuses the comparisons that are not measurements.

All checks run against synthetic databases; real multi-rank captures are ~4 GB per
rank and their paths may not enter this repository.
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
SUMMARY = ROOT / "tools" / "gpu-profile-summary.py"
DIFF = ROOT / "tools" / "gpu-profile-diff.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)


def run(tool: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True)


def _add_late_burst(path: Path, *, count: int = 40, t0: int = 2_000_000_000) -> None:
    """Give one rank extra timeline structure, so its elbow selects a different k.

    A straggler is not enough: stretching every kernel scales a rank's cost curve
    without changing its shape, so all ranks still agree on k and the consensus
    refusal never fires. Adding a distinct burst of a second kernel type, far after
    the existing timeline, is what makes one rank's optimal segmentation genuinely
    finer than its peers'.
    """
    conn = sqlite3.connect(path)
    conn.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (t0 + i * 3_000_000, t0 + i * 3_000_000 + 2_500_000, 3, 4,
             64, 1, 1, 256, 1, 1, 32, 0, 0, 0, 7, 9000 + i)
            for i in range(count)
        ],
    )
    conn.commit()
    conn.close()


def _stretch_kernels(path: Path, factor: int) -> None:
    """Lengthen every kernel so one rank is genuinely slower than its peers."""
    conn = sqlite3.connect(path)
    conn.execute(
        "UPDATE CUPTI_ACTIVITY_KIND_KERNEL SET end = start + (end - start) * ?", (factor,)
    )
    conn.commit()
    conn.close()


class CrossRankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        # Balanced pair.
        cls.r0 = build_synthetic_nsys_db(root / "report.0.sqlite")
        cls.r1 = build_synthetic_nsys_db(root / "report.1.sqlite")
        # Imbalanced pair: rank 1 is the straggler.
        cls.s0 = build_synthetic_nsys_db(root / "slow.0.sqlite")
        cls.s1 = build_synthetic_nsys_db(root / "slow.1.sqlite")
        _stretch_kernels(cls.s1, 3)
        # A pair whose per-rank phase counts genuinely disagree, so the consensus
        # refusal path is exercised rather than skipped.
        cls.d0 = build_synthetic_nsys_db(root / "diverge.0.sqlite")
        cls.d1 = build_synthetic_nsys_db(root / "diverge.1.sqlite")
        _add_late_burst(cls.d1)

        cls.rocpd = build_synthetic_rocpd_db(root / "rank.0.db")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def payload(self, tool: Path, *args: str) -> dict:
        proc = run(tool, *args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # -- cross-rank -----------------------------------------------------------

    def test_cross_rank_needs_more_than_one_profile(self):
        proc = run(SUMMARY, "cross-rank", str(self.r0))
        self.assertNotEqual(proc.returncode, 0)

    def test_rank_ids_come_from_the_varying_filename_slot(self):
        out = self.payload(SUMMARY, "cross-rank", str(self.r0), str(self.r1))
        self.assertEqual(out["rank_ids"], [0, 1])
        self.assertTrue(out["rank_ids_parsed_from_filenames"])

    def test_an_aligned_pair_still_succeeds(self):
        """The no-op guard: the refusal must not have become unconditional."""
        out = self.payload(SUMMARY, "cross-rank", str(self.r0), str(self.r1))
        self.assertTrue(out["cross_rank_available"])

    def test_a_balanced_pair_reports_low_imbalance(self):
        out = self.payload(SUMMARY, "cross-rank", str(self.r0), str(self.r1))
        for phase in out["phases"]:
            self.assertAlmostEqual(phase["gpu_kernel_imbalance"], 0.0, places=6)

    def test_a_straggler_is_detected_and_named(self):
        """Negative control for the check above: without an imbalanced pair, a
        hard-zero imbalance would satisfy it."""
        out = self.payload(SUMMARY, "cross-rank", str(self.s0), str(self.s1))
        worst = max(p["gpu_kernel_imbalance"] for p in out["phases"])
        self.assertGreater(worst, 0.1)
        slowest = {p["gpu_kernel_slowest_rank_id"] for p in out["phases"]}
        self.assertIn(1, slowest)

    def test_a_refusal_carries_the_cause_and_not_only_the_symptom(self):
        """When consensus is refused, say why -- not just that the counts differ.

        The recorded defect: on a four-rank capture the tool computed "cost at k=5
        is 15.8% above optimal k=7 (threshold: 15%)" and reported only "Phase count
        differs across ranks". The second is a consequence of the first, and it
        reads as a tool limitation rather than as a 0.8-point miss that
        --max-phases would settle, so the session hand-rolled a comparison it did
        not need to. The payload must carry the diagnostic the tool already has.
        """
        out = self.payload(SUMMARY, "cross-rank", str(self.d0), str(self.d1))
        self.assertFalse(out["cross_rank_available"])
        self.assertIsNotNone(out.get("consensus_note"))
        self.assertIn("selected_k_by_rank", out)

    def test_the_refusal_payload_names_every_rank_k(self):
        """A no-op perturbation guard: the key must be populated, not merely present."""
        out = self.payload(SUMMARY, "cross-rank", str(self.d0), str(self.d1))
        self.assertEqual(
            sorted(int(k) for k in out["selected_k_by_rank"]), sorted(out["rank_ids"])
        )
        # Rejects a vacuous pairing: the ranks must actually have selected
        # different k, or the refusal under test is not the one being reported.
        self.assertGreater(len(set(out["selected_k_by_rank"].values())), 1)

    def test_mixed_format_profiles_are_refused(self):
        """Two profilers record different things, so a delta across them has no
        denominator. Refusing is the measurement, not a limitation."""
        proc = run(SUMMARY, "cross-rank", str(self.r0), str(self.rocpd))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("mixed-format", proc.stderr)

    def test_per_rank_overview_covers_every_rank(self):
        out = self.payload(SUMMARY, "cross-rank", str(self.r0), str(self.r1))
        self.assertEqual(
            sorted(r["rank_id"] for r in out["per_rank_overview"]), out["rank_ids"]
        )

    def test_cross_rank_leaves_every_profile_unchanged(self):
        before = [p.read_bytes() for p in (self.r0, self.r1)]
        self.payload(SUMMARY, "cross-rank", str(self.r0), str(self.r1))
        self.assertEqual([p.read_bytes() for p in (self.r0, self.r1)], before)

    # -- diff -----------------------------------------------------------------

    def test_a_profile_diffed_against_itself_shows_no_change(self):
        out = self.payload(DIFF, str(self.r0), str(self.r0))
        self.assertEqual(out["profile_span_s"]["delta_pct"], 0.0)
        self.assertEqual(out["gpu_kernel_s"]["delta_pct"], 0.0)
        self.assertTrue(out["phases_match"])

    def test_a_slower_profile_shows_a_positive_kernel_delta(self):
        out = self.payload(DIFF, str(self.s0), str(self.s1))
        self.assertGreater(out["gpu_kernel_s"]["delta_pct"], 0.0)

    def test_diff_reports_which_comparison_mode_it_used(self):
        out = self.payload(DIFF, str(self.r0), str(self.r1))
        self.assertIn(
            out["comparison_mode"], {"phase_aware", "summary", "summary_no_kernel"}
        )

    def test_diff_opens_both_profiles_read_only(self):
        scratch = Path(self._tmp.name) / "scratch.sqlite"
        shutil.copyfile(self.r0, scratch)
        before = scratch.read_bytes()
        self.payload(DIFF, str(scratch), str(self.r1))
        self.assertEqual(scratch.read_bytes(), before)

    def test_diff_rejects_a_missing_file_without_a_traceback(self):
        proc = run(DIFF, str(self.r0), str(Path(self._tmp.name) / "absent.sqlite"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
