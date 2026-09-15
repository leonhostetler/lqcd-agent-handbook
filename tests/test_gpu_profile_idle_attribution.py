#!/usr/bin/env python3
"""Checks for idle attribution and transfer overlap.

These two subcommands exist because the 2026-09-14 acceptance run had to compute
both by hand (ROADMAP.md, Slice 6). Each is interval algebra over hundreds of
thousands of rows, where a wrong merge rule returns a plausible number of seconds
that no reader can check by eye -- the "quiet failure" class
conventions/repeated-work.md says to automate.

That convention also sets the bar a new tool must clear before it replaces the
hand pass: run it against a known-good input, **perturb the input so it must fail
and confirm it does**, and reject a no-op perturbation. Each control below is
paired with the perturbation that must move it and, where the pairing could be
satisfied trivially, with one that must not.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from gpu_profile.detect import open_profile  # noqa: E402
from gpu_profile.metrics import (  # noqa: E402
    compute_idle_attribution,
    compute_transfer_overlap,
)
from gpu_profile_fixtures import (  # noqa: E402
    build_idle_attribution_nsys_db,
    build_synthetic_rocpd_db,
)

MS = 1_000_000


class AttributionTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._open: list = []

    def tearDown(self) -> None:
        for p in self._open:
            p.close()
        self._tmp.cleanup()

    def attribution(self, name: str = "a.db", *, window=None, **kwargs):
        path = build_idle_attribution_nsys_db(self.dir / name, **kwargs)
        profile = open_profile(path)
        self._open.append(profile)
        return compute_idle_attribution(profile, *(window or (None, None)))

    def overlap(self, name: str = "a.db", **kwargs) -> dict:
        path = build_idle_attribution_nsys_db(self.dir / name, **kwargs)
        profile = open_profile(path)
        self._open.append(profile)
        return {t.direction: t for t in compute_transfer_overlap(profile)}

    def category(self, result, name: str):
        return next(c for c in result.categories if c.name == name)


class IdleAttributionTests(AttributionTestBase):
    # -- known-good input -----------------------------------------------------

    def test_the_known_good_timeline_splits_exactly(self):
        """6 ms of kernels, 20 ms of idle, split 4/3/1 with 12 ms residual."""
        a = self.attribution()
        self.assertAlmostEqual(a.kernel_busy_s, 0.006, places=9)
        self.assertAlmostEqual(a.gpu_idle_s, 0.020, places=9)
        self.assertAlmostEqual(self.category(a, "mpi").total_s, 0.004, places=9)
        self.assertAlmostEqual(self.category(a, "host_api").total_s, 0.003, places=9)
        self.assertAlmostEqual(self.category(a, "os_runtime").total_s, 0.001, places=9)
        self.assertAlmostEqual(a.accounted_s, 0.008, places=9)
        self.assertAlmostEqual(a.residual_s, 0.012, places=9)

    def test_the_parts_never_exceed_the_whole(self):
        a = self.attribution()
        self.assertAlmostEqual(a.accounted_s + a.residual_s, a.gpu_idle_s, places=9)

    # -- control 1: a category must move when its events move -----------------

    def test_moving_mpi_out_of_a_gap_moves_its_time_to_the_residual(self):
        """The perturbation that must land on the MPI bucket.

        The call is moved from inside gap A to before the first kernel, where it
        overlaps no idle at all. If the bucket did not fall by exactly its 4 ms and
        the residual did not rise by exactly the same, the intersection is not
        measuring what it claims.
        """
        moved = self.attribution("moved.db", mpi_window=(990 * MS, 994 * MS))
        self.assertAlmostEqual(self.category(moved, "mpi").total_s, 0.0, places=9)
        self.assertAlmostEqual(moved.residual_s, 0.016, places=9)
        base = self.attribution()
        self.assertAlmostEqual(
            moved.residual_s - base.residual_s,
            self.category(base, "mpi").total_s,
            places=9,
        )

    def test_moving_mpi_within_the_same_gap_changes_nothing(self):
        """Rejects the vacuous reading of the control above.

        If any edit to the MPI window moved the number, the control would be
        measuring "something changed" rather than "the overlap with idle changed".
        This call moves by 2 ms and stays inside gap A, so every figure must hold.
        """
        base = self.attribution()
        same = self.attribution("same.db", mpi_window=(1_005 * MS, 1_009 * MS))
        self.assertAlmostEqual(
            self.category(same, "mpi").total_s, self.category(base, "mpi").total_s, places=9
        )
        self.assertAlmostEqual(same.residual_s, base.residual_s, places=9)

    # -- control 2: the OS filter must exclude non-GPU threads ----------------

    def test_a_background_thread_parked_in_poll_is_not_attributed(self):
        """The defect this filter was added for.

        The fixture's background thread is blocked in ``poll`` across the entire
        timeline, so an unfiltered implementation reports os_runtime as 100% of
        idle. On the real MILC/QUDA capture that was 18.691 s of 18.691 s against
        0.389 s for the thread actually driving the GPU.
        """
        a = self.attribution()
        os_cat = self.category(a, "os_runtime")
        self.assertAlmostEqual(os_cat.total_s, 0.001, places=9)
        self.assertLess(os_cat.pct_of_idle, 100.0)

    def test_the_gpu_thread_os_call_is_still_attributed(self):
        """Rejects the vacuous fix: excluding every thread would also pass above."""
        moved = self.attribution("noos.db", os_window=(990 * MS, 991 * MS))
        self.assertAlmostEqual(self.category(moved, "os_runtime").total_s, 0.0, places=9)
        base = self.attribution()
        self.assertGreater(self.category(base, "os_runtime").total_s, 0.0)

    # -- control 3: an untraced category is not a measured zero ---------------

    def test_an_untraced_category_reports_null_not_zero(self):
        """rocprofv3 does not intercept MPI, so has_mpi is False on every such profile.

        Reporting 0.0 there would read as "MPI cost nothing" and send a session
        looking for the bottleneck everywhere else. The category must be marked
        unavailable, carry a reason, and be named in residual_absorbs.
        """
        path = build_synthetic_rocpd_db(self.dir / "r.db")
        profile = open_profile(path)
        self._open.append(profile)
        a = compute_idle_attribution(profile)

        mpi = next(c for c in a.categories if c.name == "mpi")
        self.assertFalse(mpi.available)
        self.assertIsNone(mpi.total_s, "an untraced category must be null, never 0.0")
        self.assertIsNone(mpi.pct_of_idle)
        self.assertIn("MPI", mpi.unavailable_reason or "")
        self.assertIn("mpi", a.residual_absorbs)
        self.assertTrue(
            any("unknown rather than zero" in c for c in a.caveats),
            "the residual must say what it is absorbing",
        )

    def test_a_traced_category_is_never_marked_unavailable(self):
        """Rejects the vacuous fix: marking everything unavailable would also pass."""
        a = self.attribution()
        for name in ("mpi", "host_api", "os_runtime"):
            self.assertTrue(self.category(a, name).available, name)
            self.assertIsNotNone(self.category(a, name).total_s, name)
        self.assertEqual(a.residual_absorbs, [])


class OutsideKernelSpanTests(AttributionTestBase):
    """The window-level account, and the guard that says when the idle split is not it.

    Idle is measured between kernels, so ``kernel_busy + idle`` covers only
    first-kernel-start to last-kernel-end. A window holding startup, teardown or a
    structural stall is mostly outside that, and the idle split then balances exactly
    while describing a sliver of the window -- a closed-looking account of 5% of the
    phase, measured on a real capture (ROADMAP.md, Slice 6). The control is that the
    split is *unchanged* by the perturbation and only the new term and the caveat move.
    """

    SPAN = (1_000_000_000, 1_026_000_000)  # exactly the fixture's kernel span

    def test_a_window_matching_the_kernel_span_has_nothing_outside(self):
        a = self.attribution(window=self.SPAN)
        self.assertAlmostEqual(a.outside_kernel_span_s, 0.0, places=9)
        self.assertFalse([c for c in a.caveats if "lies before the first kernel" in c])

    def test_the_window_identity_closes(self):
        for name, window in (
            ("span", self.SPAN),
            ("wide", (960 * MS, 1_026 * MS)),
            ("narrow", (998 * MS, 1_026 * MS)),
        ):
            with self.subTest(name):
                a = self.attribution(f"{name}.db", window=window)
                self.assertAlmostEqual(
                    a.kernel_busy_s + a.gpu_idle_s + a.outside_kernel_span_s,
                    a.window_s,
                    places=9,
                )

    def test_startup_outside_the_kernel_span_is_reported_and_warned(self):
        """Perturbation: 40 ms of pre-kernel window must land in the new term."""
        a = self.attribution(window=(960 * MS, 1_026 * MS))
        self.assertAlmostEqual(a.outside_kernel_span_s, 0.040, places=9)
        self.assertTrue([c for c in a.caveats if "lies before the first kernel" in c])

    def test_the_idle_split_is_unchanged_by_that_perturbation(self):
        """The reason the guard is needed: every idle figure balances identically."""
        span = self.attribution("span.db", window=self.SPAN)
        wide = self.attribution("wide.db", window=(960 * MS, 1_026 * MS))
        for field in ("gpu_idle_s", "kernel_busy_s", "accounted_s", "residual_s"):
            self.assertAlmostEqual(
                getattr(span, field), getattr(wide, field), places=9, msg=field
            )
        self.assertAlmostEqual(wide.accounted_s + wide.residual_s, wide.gpu_idle_s, places=9)

    def test_a_small_overhang_does_not_trip_the_warning(self):
        """Rejects the no-op perturbation: the guard must discriminate, not always fire."""
        a = self.attribution(window=(998 * MS, 1_026 * MS))
        self.assertAlmostEqual(a.outside_kernel_span_s, 0.002, places=9)
        self.assertLess(a.outside_kernel_span_s / a.window_s, 0.10)
        self.assertFalse([c for c in a.caveats if "lies before the first kernel" in c])


class TransferOverlapTests(AttributionTestBase):
    def test_a_transfer_inside_a_kernel_is_fully_hidden(self):
        h2d = self.overlap()["Host-to-Device"]
        self.assertAlmostEqual(h2d.overlapped_s, 0.001, places=9)
        self.assertAlmostEqual(h2d.exposed_s, 0.0, places=9)
        self.assertAlmostEqual(h2d.pct_overlapped, 100.0, places=6)

    def test_a_transfer_inside_an_idle_gap_is_fully_exposed(self):
        d2h = self.overlap()["Device-to-Host"]
        self.assertAlmostEqual(d2h.overlapped_s, 0.0, places=9)
        self.assertAlmostEqual(d2h.exposed_s, 0.001, places=9)
        self.assertAlmostEqual(d2h.pct_overlapped, 0.0, places=6)

    def test_moving_a_hidden_transfer_into_a_gap_exposes_it(self):
        """The perturbation that must land on the overlap measurement.

        This is the number that decides whether a transfer class costs anything.
        On the real capture, peer-to-peer was the largest class by volume and
        96.8% hidden, so the obvious 'improve communication overlap' finding was
        wrong -- which only the exposed figure, not the volume, could show.
        """
        moved = self.overlap("moved.db", hidden_memcpy=(1_004 * MS, 1_005 * MS))
        h2d = moved["Host-to-Device"]
        self.assertAlmostEqual(h2d.overlapped_s, 0.0, places=9)
        self.assertAlmostEqual(h2d.exposed_s, 0.001, places=9)

    def test_moving_an_exposed_transfer_into_a_kernel_hides_it(self):
        moved = self.overlap("moved2.db", exposed_memcpy=(1_012_500_000, 1_013_500_000))
        d2h = moved["Device-to-Host"]
        self.assertAlmostEqual(d2h.overlapped_s, 0.001, places=9)
        self.assertAlmostEqual(d2h.exposed_s, 0.0, places=9)

    def test_total_is_split_exactly_between_overlapped_and_exposed(self):
        for t in self.overlap().values():
            self.assertAlmostEqual(t.overlapped_s + t.exposed_s, t.total_s, places=9)


if __name__ == "__main__":
    unittest.main()
