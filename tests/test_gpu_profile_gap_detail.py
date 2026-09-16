#!/usr/bin/env python3
"""Controls for `gap-detail`: naming a large GPU-idle stall, not only sizing it.

`idle-attribution` reports a residual and a bucket histogram. The histogram separates
diffuse per-launch overhead from a few structural stalls, and that is where it stops —
**one bucket can hold two unrelated mechanisms.** On a real capture the >100 ms bucket of
a single phase held both a host `memset` (about 89% of samples in three gaps) and MILC
host-side vector arithmetic (46% in a fourth); at phase level the two averaged into "some
host work" at 4.5% and 11.2% and neither was identifiable. Per-gap sampling is what
separates them, and doing it by hand took a `LAG` query plus two further calls per gap.

Two things here are easy to get wrong in a way that reads as plausible.

**Gaps must come from merged kernel intervals, not consecutive launches.** The hand
procedure used `LAG(end) OVER (ORDER BY start)`, which equals the merged answer only when
kernels never overlap. Under concurrency it reports a "gap" while the GPU was still busy
with an overlapping kernel — idle time that does not exist.
`test_overlapping_kernels_do_not_produce_a_phantom_gap` fails on exactly that mistake.

**An absent sampling capability is not an unoccupied gap.** A capture with no CPU samples
must still size the gaps and say that the uncovered part is unnamed.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

from gpu_profile.detect import open_profile  # noqa: E402
from gpu_profile.metrics import compute_gap_details  # noqa: E402
from gpu_profile_fixtures import build_idle_attribution_nsys_db  # noqa: E402


class GapDetailBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._open: list = []

    def tearDown(self) -> None:
        for p in self._open:
            p.close()
        self._tmp.cleanup()

    def _open_profile(self, path: Path):
        p = open_profile(path)
        self._open.append(p)
        return p


class TestGapSelection(GapDetailBase):
    def test_the_two_known_gaps_are_found_at_their_known_lengths(self) -> None:
        """The fixture has exactly two 10 ms gaps; nothing else may appear."""
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "g.sqlite")
        )
        res = compute_gap_details(prof, min_gap_s=0.001)
        self.assertTrue(res.available)
        self.assertEqual(res.gaps_considered, 2)
        self.assertEqual([round(g.duration_s, 3) for g in res.gaps], [0.01, 0.01])
        self.assertAlmostEqual(res.total_gap_s, 0.02, places=6)

    def test_min_gap_floor_excludes_and_the_count_follows(self) -> None:
        """The floor is a real filter, not a display cap: gaps_considered moves too."""
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "f.sqlite")
        )
        included = compute_gap_details(prof, min_gap_s=0.001)
        excluded = compute_gap_details(prof, min_gap_s=1.0)
        self.assertEqual(included.gaps_considered, 2)
        self.assertEqual(excluded.gaps_considered, 0)
        self.assertEqual(excluded.gaps, [])
        self.assertEqual(excluded.total_gap_s, 0.0)

    def test_top_limits_rows_without_changing_the_totals(self) -> None:
        """A display cap must not move the population figures beside it."""
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "t.sqlite")
        )
        res = compute_gap_details(prof, min_gap_s=0.001, top=1)
        self.assertEqual(len(res.gaps), 1)
        self.assertEqual(res.gaps_considered, 2)
        self.assertAlmostEqual(res.total_gap_s, 0.02, places=6)

    def test_gaps_are_ranked_longest_first(self) -> None:
        path = build_idle_attribution_nsys_db(self.dir / "r.sqlite")
        # Stretch the second gap by moving K3 later, so the order is unambiguous.
        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE CUPTI_ACTIVITY_KIND_KERNEL SET start = start + 20000000, "
            "end = end + 20000000 WHERE start >= 1024000000"
        )
        conn.commit()
        conn.close()
        prof = self._open_profile(path)
        res = compute_gap_details(prof, min_gap_s=0.001)
        durations = [g.duration_s for g in res.gaps]
        self.assertEqual(durations, sorted(durations, reverse=True))
        self.assertEqual([g.rank for g in res.gaps], [1, 2])
        self.assertAlmostEqual(res.gaps[0].duration_s, 0.03, places=6)


class TestMergedIntervals(GapDetailBase):
    def test_overlapping_kernels_do_not_produce_a_phantom_gap(self) -> None:
        """The control against the hand LAG shortcut.

        A long kernel spanning the whole timeline means the GPU is never idle. A
        start-to-end difference between consecutive launches still reports two gaps;
        merged intervals report none.
        """
        path = build_idle_attribution_nsys_db(self.dir / "ovl.sqlite")
        conn = sqlite3.connect(path)
        rows = list(
            conn.execute("SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start")
        )
        first_start = rows[0][0]
        last_end = rows[-1][1]
        # One kernel covering everything, on its own stream.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
        template = dict(zip(cols, list(conn.execute(
            "SELECT * FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start LIMIT 1"))[0]))
        template["start"] = first_start
        template["end"] = last_end
        if "streamId" in template:
            template["streamId"] = 99
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL ({','.join(cols)}) VALUES ({placeholders})",
            [template[c] for c in cols],
        )
        conn.commit()
        conn.close()
        prof = self._open_profile(path)
        res = compute_gap_details(prof, min_gap_s=0.001)
        self.assertEqual(
            res.gaps_considered,
            0,
            "a kernel spanning the timeline leaves no idle gap; merged intervals must "
            "see that and a consecutive-launch difference must not be used",
        )
        self.assertEqual(res.total_gap_s, 0.0)


class TestWindowAndCapability(GapDetailBase):
    def test_window_restricts_to_gaps_inside_it(self) -> None:
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "w.sqlite")
        )
        # Gap A is [1.002 .. 1.012]; a window ending at 1.013 holds it and not gap B.
        res = compute_gap_details(
            prof, 1_000_000_000, 1_013_000_000, min_gap_s=0.001
        )
        self.assertEqual(res.gaps_considered, 1)
        self.assertAlmostEqual(res.gaps[0].duration_s, 0.01, places=6)

    def test_missing_cpu_sampling_is_a_named_gap_not_an_empty_one(self) -> None:
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "ns.sqlite")
        )
        res = compute_gap_details(prof, min_gap_s=0.001)
        self.assertTrue(res.available)
        self.assertTrue(res.gaps, "gaps must still be sized without sampling")
        if not prof.capabilities.has_cpu_samples:
            self.assertTrue(
                any("no CPU sampling" in c for c in res.caveats),
                "an unnamed uncovered part must be declared a capability gap",
            )
            self.assertEqual(res.gaps[0].top_symbols, [])

    def test_transfer_caveat_is_always_present(self) -> None:
        """A gap with no kernel may still hold a transfer; the output must say so."""
        prof = self._open_profile(
            build_idle_attribution_nsys_db(self.dir / "c.sqlite")
        )
        res = compute_gap_details(prof, min_gap_s=0.001)
        self.assertTrue(any("transfer-overlap" in c for c in res.caveats))


if __name__ == "__main__":
    unittest.main()
