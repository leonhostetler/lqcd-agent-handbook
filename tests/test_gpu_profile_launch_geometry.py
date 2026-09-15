#!/usr/bin/env python3
"""Controls for launch-geometry extraction and the autotune-warmth gate.

`software/quda/profiling.md` makes establishing tunecache warmth mandatory before
reading call counts, launch geometry or duration spread. Until 2026-09-15 the
extraction multiplied the six extents into `total_threads` and carried nothing else,
so the gate was satisfied by hand on every QUDA performance session.

Two things here are easy to get wrong in a way that reads as plausible, and each has
a control with the perturbation that must move it.

**The vendor conventions differ.** CUDA's `gridX` counts blocks; rocpd's `grid_size_x`
counts *work-items*. Mapping rocpd across raw would overstate the grid by the
workgroup size — 110592 where the answer is 864 — and silently inflate everything
derived from it. `test_rocpd_grid_is_workgroups_not_work_items` fails on exactly that
mistake.

**An absent capability is not a uniform geometry.** A capture whose kernel table lacks
the extents must say so, because an empty result reads as "nothing varied", which is
the claim the gate exists to prevent.
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
from gpu_profile.metrics import compute_launch_geometry  # noqa: E402
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)

EXTENTS = ("gridX", "gridY", "gridZ", "blockX", "blockY", "blockZ")


class LaunchGeometryBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._open: list = []

    def tearDown(self) -> None:
        for p in self._open:
            p.close()
        self._tmp.cleanup()

    def nsys(self, name: str, geometries: list[tuple] | None = None):
        """Build an nsys fixture, optionally rewriting each kernel's geometry.

        `geometries` is one (gridX, gridY, gridZ, blockX, blockY, blockZ) per kernel
        row, cycled if shorter than the table.
        """
        path = build_synthetic_nsys_db(self.dir / name)
        if geometries is not None:
            conn = sqlite3.connect(path)
            rowids = [r[0] for r in conn.execute(
                "SELECT rowid FROM CUPTI_ACTIVITY_KIND_KERNEL ORDER BY start"
            )]
            for i, rid in enumerate(rowids):
                g = geometries[i % len(geometries)]
                conn.execute(
                    "UPDATE CUPTI_ACTIVITY_KIND_KERNEL SET "
                    "gridX=?, gridY=?, gridZ=?, blockX=?, blockY=?, blockZ=? WHERE rowid=?",
                    (*g, rid),
                )
            conn.commit()
            conn.close()
        profile = open_profile(path)
        self._open.append(profile)
        return profile

    def named(self, result, fragment: str):
        for k in result.kernels:
            if fragment in k.name:
                return k
        self.fail(f"no kernel matching {fragment!r} in {[k.name for k in result.kernels]}")


class ExtentExtractionTests(LaunchGeometryBase):
    def test_nsys_populates_all_six_extents(self):
        profile = self.nsys("a.sqlite")
        self.assertTrue(profile.capabilities.has_launch_geometry)
        for k in profile.kernel_events():
            for attr in ("grid_x", "grid_y", "grid_z", "block_x", "block_y", "block_z"):
                self.assertIsNotNone(getattr(k, attr), attr)

    def test_the_extents_multiply_to_total_threads(self):
        """The product the extraction used to carry alone must still be derivable."""
        profile = self.nsys("b.sqlite")
        for k in profile.kernel_events():
            product = (
                k.grid_x * k.grid_y * k.grid_z * k.block_x * k.block_y * k.block_z
            )
            self.assertAlmostEqual(float(product), k.total_threads, places=6)

    def test_rocpd_grid_is_workgroups_not_work_items(self):
        """The vendor-convention control.

        The fixture dispatches 110592 work-items in workgroups of 128. CUDA's gridX
        counts blocks, so the normalised grid is 864. A backend that mapped
        rocpd's grid_size_x straight across would report 110592 here and every
        derived quantity would be wrong by the workgroup size.
        """
        profile = open_profile(build_synthetic_rocpd_db(self.dir / "r.db"))
        self._open.append(profile)
        self.assertTrue(profile.capabilities.has_launch_geometry)
        first = profile.kernel_events()[0]
        self.assertEqual(first.block_x, 128)
        self.assertEqual(first.grid_x, 864)
        self.assertNotEqual(first.grid_x, 110592)

    def test_rocpd_total_threads_counts_work_items(self):
        """grid is divided down; total_threads must not be."""
        profile = open_profile(build_synthetic_rocpd_db(self.dir / "r2.db"))
        self._open.append(profile)
        first = profile.kernel_events()[0]
        self.assertEqual(first.total_threads, 110592.0)

    def test_both_formats_report_the_capability(self):
        nsys = self.nsys("parity.sqlite")
        rocpd = open_profile(build_synthetic_rocpd_db(self.dir / "parity.db"))
        self._open.append(rocpd)
        self.assertEqual(
            nsys.capabilities.has_launch_geometry,
            rocpd.capabilities.has_launch_geometry,
        )


class UnavailableTests(LaunchGeometryBase):
    def strip_extents(self, name: str):
        path = build_synthetic_nsys_db(self.dir / name)
        conn = sqlite3.connect(path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")]
        keep = [c for c in cols if c not in EXTENTS]
        conn.execute(
            f"CREATE TABLE K2 AS SELECT {','.join(keep)} FROM CUPTI_ACTIVITY_KIND_KERNEL"
        )
        conn.execute("DROP TABLE CUPTI_ACTIVITY_KIND_KERNEL")
        conn.execute("ALTER TABLE K2 RENAME TO CUPTI_ACTIVITY_KIND_KERNEL")
        conn.commit()
        conn.close()
        profile = open_profile(path)
        self._open.append(profile)
        return profile

    def test_a_capture_without_extents_reports_unavailable(self):
        result = compute_launch_geometry(self.strip_extents("x.sqlite"))
        self.assertFalse(result.available)
        self.assertIsNotNone(result.unavailable_reason)

    def test_unavailable_is_not_an_empty_available_result(self):
        """The perturbation that must move it: reporting [] with available=True
        would satisfy every other assertion and assert that nothing varied."""
        result = compute_launch_geometry(self.strip_extents("y.sqlite"))
        self.assertEqual(result.kernels, [])
        self.assertTrue(any("not uniform" in c for c in result.caveats))

    def test_kernels_still_load_without_extents(self):
        """The capability must degrade, not break the rest of the extraction."""
        profile = self.strip_extents("z.sqlite")
        self.assertGreater(len(profile.kernel_events()), 0)
        self.assertIsNone(profile.kernel_events()[0].grid_x)

    def test_an_available_capture_is_not_reported_unavailable(self):
        """Rejects a vacuous guard that always reports unavailable."""
        self.assertTrue(compute_launch_geometry(self.nsys("ok.sqlite")).available)


class ProblemSizeGroupingTests(LaunchGeometryBase):
    """Separating a tuning sweep from a kernel launched at several sizes.

    `grid.x = ceil(minThreads / block.x)`, so two launches can share a tune key only
    if their reconstructed minThreads bounds overlap. Without that grouping, the
    multi-blas kernels — which legitimately run at several vector counts — look
    exactly like a sweep, which is what the first implementation reported on a
    known-warm capture.
    """

    # Same minThreads.x (~6400), two block.x values: the shape a sweep leaves.
    SWEPT = [(200, 1, 1, 32, 1, 1), (100, 1, 1, 64, 1, 1)]
    # Different minThreads.x (6400 vs 25600), one block.x each: two call sites.
    TWO_SIZES = [(200, 1, 1, 32, 1, 1), (800, 1, 1, 32, 1, 1)]

    def test_one_problem_size_with_two_block_x_is_surfaced(self):
        result = compute_launch_geometry(self.nsys("s.sqlite", self.SWEPT))
        k = self.named(result, "myKernel3D")
        self.assertEqual(k.distinct_problem_sizes, 1)
        self.assertEqual(k.max_block_x_at_one_problem_size, 2)

    def test_two_problem_sizes_are_not_read_as_one(self):
        """The perturbation that must move it, and the defect it encodes."""
        result = compute_launch_geometry(self.nsys("t.sqlite", self.TWO_SIZES))
        k = self.named(result, "myKernel3D")
        self.assertEqual(k.distinct_problem_sizes, 2)
        self.assertEqual(k.max_block_x_at_one_problem_size, 1)

    # Same minThreads.x and same y, different z extent: different tune keys, and the
    # x-interval clustering alone cannot tell them apart.
    SAME_X_DIFFERENT_Z = [(200, 1, 1, 32, 2, 1), (200, 1, 3, 32, 2, 1)]

    def test_a_different_z_extent_is_a_different_problem_size(self):
        """The y/z bucket is load-bearing, not decoration.

        Observed on a real capture: ComputeStaple ran at one x volume with z extents
        of 1 and 3. Bucketing on x alone merges them and reports a sweep.
        """
        result = compute_launch_geometry(self.nsys("z2.sqlite", self.SAME_X_DIFFERENT_Z))
        k = self.named(result, "myKernel3D")
        self.assertEqual(k.distinct_problem_sizes, 2)
        self.assertEqual(k.max_block_x_at_one_problem_size, 1)

    def test_launch_counts_are_reported_beside_the_block_x_count(self):
        """Without this a reader cannot tell a sweep from repeated call sites."""
        result = compute_launch_geometry(self.nsys("u.sqlite", self.SWEPT))
        k = self.named(result, "myKernel3D")
        self.assertGreater(k.min_launches_per_geometry, 0)
        self.assertEqual(sum(g.launches for g in k.geometries), k.launches)

    def test_a_uniform_capture_flags_nothing(self):
        result = compute_launch_geometry(self.nsys("v.sqlite", [(200, 1, 1, 32, 1, 1)]))
        for k in result.kernels:
            self.assertEqual(k.max_block_x_at_one_problem_size, 1)
        self.assertTrue(any("does not establish" in c for c in result.caveats))

    def test_the_gate_is_never_reported_as_a_verdict(self):
        """No field may assert warmth: the tune key's aux string is not in a profile."""
        result = compute_launch_geometry(self.nsys("w.sqlite", self.SWEPT))
        fields = set(vars(result.kernels[0]))
        for forbidden in ("cold", "warm", "tunecache_warm", "is_swept"):
            self.assertNotIn(forbidden, fields)
        self.assertTrue(any("does not establish" in c or "aux string" in c
                            for c in result.caveats))


if __name__ == "__main__":
    unittest.main()
