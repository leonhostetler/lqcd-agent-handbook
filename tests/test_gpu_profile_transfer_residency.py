#!/usr/bin/env python3
"""Controls for the transfer-residency split and its rate-split discriminator.

`software/quda/internals/managed-memory.md` records that an unprefetched managed buffer
shows up as a device-to-device copy running orders of magnitude below device bandwidth
while copies of the same direction run at full rate. Until 2026-09-15 the extraction read
only `copyKind` and `bytes`, so both `memcpy` and `transfer-overlap` **merged the two
populations into one averaged rate** — on a real capture, 289 slow transfers at 7.5 GB/s
and 162 fast ones at 3050 GB/s reported as a single unremarkable 14 GB/s. The tool was not
merely silent on the leaf's discriminator; it concealed it.

Three things here are easy to get wrong in a way that reads as plausible.

**An absent column is not "all device memory".** A capture whose MEMCPY table lacks
`srcKind`/`dstKind` must report residency unavailable with a reason. An empty list reads as
"nothing to split", which is the claim this exists to prevent.

**The LEFT JOIN matters.** Joining the memory-kind enum with an INNER JOIN would drop every
transfer whose end kind is absent from the enum table, turning a residency question into
missing transfers — a silent undercount of the totals every other subcommand shares.

**A split must be able to *not* fire.** A check that always reports a split is
indistinguishable from one that never runs, so the negative control flattens the two
populations to one rate and asserts the split disappears while the rows remain.
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
from gpu_profile.metrics import (  # noqa: E402
    RESIDENCY_RATE_SPLIT_FACTOR,
    compute_memcpy_by_kind,
    compute_transfer_residency,
)
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)

MB = 1_048_576
# Two Device-to-Device populations of equal volume, three orders of magnitude apart:
# managed destination is served by page migration, device->device runs at full rate.
SLOW_NS = 100_000_000  # 64 MB in 100 ms  -> ~0.67 GB/s
FAST_NS = 100_000  # 64 MB in 100 us  -> ~671 GB/s


class ResidencyBase(unittest.TestCase):
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

    def nsys_with_residency(self, name: str, *, slow_ns: int = SLOW_NS) -> Path:
        """Fixture whose MEMCPY table carries srcKind/dstKind and two D2D populations."""
        path = build_synthetic_nsys_db(self.dir / name)
        conn = sqlite3.connect(path)
        conn.execute("ALTER TABLE CUPTI_ACTIVITY_KIND_MEMCPY ADD COLUMN srcKind INTEGER")
        conn.execute("ALTER TABLE CUPTI_ACTIVITY_KIND_MEMCPY ADD COLUMN dstKind INTEGER")
        conn.execute("UPDATE CUPTI_ACTIVITY_KIND_MEMCPY SET srcKind = 1, dstKind = 2")
        conn.execute(
            "CREATE TABLE ENUM_CUDA_MEM_KIND (id INTEGER PRIMARY KEY, name TEXT, label TEXT)"
        )
        conn.executemany(
            "INSERT INTO ENUM_CUDA_MEM_KIND VALUES (?,?,?)",
            [
                (0, "CUDA_MEMOPR_MEMORY_KIND_PAGEABLE", "Pageable"),
                (1, "CUDA_MEMOPR_MEMORY_KIND_PINNED", "Pinned"),
                (2, "CUDA_MEMOPR_MEMORY_KIND_DEVICE", "Device"),
                (4, "CUDA_MEMOPR_MEMORY_KIND_MANAGED", "Managed"),
            ],
        )
        # copyKind 8 is labelled Peer-to-Peer in the base fixture's enum; add the
        # Device-to-Device label so the two populations share one direction.
        conn.execute("INSERT OR REPLACE INTO ENUM_CUDA_MEMCPY_OPER VALUES (9, 'Device-to-Device')")
        conn.executemany(
            "INSERT INTO CUPTI_ACTIVITY_KIND_MEMCPY "
            "(start, end, bytes, copyKind, srcKind, dstKind) VALUES (?,?,?,?,?,?)",
            [
                # Device -> Managed: destination not resident, served by migration.
                (910_000_000, 910_000_000 + slow_ns, 64 * MB, 9, 2, 4),
                # Managed -> Device: full rate, identical volume.
                (930_000_000, 930_000_000 + FAST_NS, 64 * MB, 9, 4, 2),
            ],
        )
        conn.commit()
        conn.close()
        return path


class TestResidencyAvailability(ResidencyBase):
    def test_absent_columns_report_unavailable_not_empty(self) -> None:
        """The base fixture has no srcKind/dstKind: that is unavailable, not all-device."""
        path = build_synthetic_nsys_db(self.dir / "plain.sqlite")
        prof = self._open_profile(path)
        self.assertFalse(prof.capabilities.has_transfer_residency)
        res = compute_transfer_residency(prof)
        self.assertFalse(res.available)
        self.assertIsNotNone(res.unavailable_reason)
        self.assertIn("unavailable", res.unavailable_reason)
        self.assertEqual(res.rows, [])
        self.assertEqual(res.rate_splits, [])

    def test_rocpd_declares_residency_unavailable(self) -> None:
        """rocpd carries a direction string and no per-end memory kind."""
        path = build_synthetic_rocpd_db(self.dir / "r.db")
        prof = self._open_profile(path)
        self.assertFalse(prof.capabilities.has_transfer_residency)
        res = compute_transfer_residency(prof)
        self.assertFalse(res.available)
        self.assertEqual(res.rows, [])

    def test_present_columns_are_detected_and_resolved_to_labels(self) -> None:
        prof = self._open_profile(self.nsys_with_residency("res.sqlite"))
        self.assertTrue(prof.capabilities.has_transfer_residency)
        res = compute_transfer_residency(prof)
        self.assertTrue(res.available)
        pairs = {(r.kind, r.src_kind, r.dst_kind) for r in res.rows}
        self.assertIn(("Device-to-Device", "Device", "Managed"), pairs)
        self.assertIn(("Device-to-Device", "Managed", "Device"), pairs)


class TestRateSplit(ResidencyBase):
    def test_split_fires_and_names_the_slow_population(self) -> None:
        prof = self._open_profile(self.nsys_with_residency("split.sqlite"))
        res = compute_transfer_residency(prof)
        self.assertEqual(len(res.rate_splits), 1, res.rate_splits)
        msg = res.rate_splits[0]
        self.assertIn("Device->Managed", msg)
        self.assertIn("managed-memory.md", msg)
        slow = next(r for r in res.rows if r.dst_kind == "Managed")
        fast = next(r for r in res.rows if r.src_kind == "Managed")
        self.assertGreater(
            fast.effective_GBs / slow.effective_GBs, RESIDENCY_RATE_SPLIT_FACTOR
        )

    def test_negative_control_equal_rates_report_no_split(self) -> None:
        """Flatten the two populations to one rate: rows stay, the split must vanish.

        Without this the check could always fire and still pass the test above.
        """
        prof = self._open_profile(
            self.nsys_with_residency("nosplit.sqlite", slow_ns=FAST_NS)
        )
        res = compute_transfer_residency(prof)
        self.assertTrue(res.available)
        pairs = {(r.src_kind, r.dst_kind) for r in res.rows}
        self.assertIn(("Device", "Managed"), pairs)
        self.assertIn(("Managed", "Device"), pairs)
        self.assertEqual(res.rate_splits, [])

    def test_per_direction_row_averages_what_residency_separates(self) -> None:
        """The defect being repaired: one direction, one rate, both populations hidden.

        This asserts the *old* behaviour still holds for `memcpy_by_kind` — it is a
        correct per-direction aggregate — and that residency is what recovers the split.
        So it fails if the split is ever folded into the per-direction rows, which would
        change a figure other subcommands share.
        """
        prof = self._open_profile(self.nsys_with_residency("avg.sqlite"))
        d2d = [m for m in compute_memcpy_by_kind(prof) if m.kind == "Device-to-Device"]
        self.assertEqual(len(d2d), 1)
        merged = d2d[0].effective_GBs
        res = compute_transfer_residency(prof)
        rates = sorted(
            r.effective_GBs for r in res.rows if r.kind == "Device-to-Device"
        )
        self.assertLess(rates[0], merged)
        self.assertGreater(rates[-1], merged)


class TestResidencyTotalsAgree(ResidencyBase):
    def test_residency_rows_conserve_the_per_direction_totals(self) -> None:
        """A LEFT JOIN keeps every transfer; an INNER JOIN would silently drop some."""
        prof = self._open_profile(self.nsys_with_residency("totals.sqlite"))
        res = compute_transfer_residency(prof)
        by_kind = {m.kind: m for m in compute_memcpy_by_kind(prof)}
        for kind, summary in by_kind.items():
            rows = [r for r in res.rows if r.kind == kind]
            self.assertEqual(
                sum(r.transfers for r in rows), summary.transfers, f"{kind} count"
            )
            self.assertEqual(
                sum(r.total_bytes for r in rows), summary.total_bytes, f"{kind} bytes"
            )

    def test_unknown_end_kind_is_kept_not_dropped(self) -> None:
        """An end kind absent from the enum must survive as Unknown, not vanish."""
        path = self.nsys_with_residency("unknown.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(
            "INSERT INTO CUPTI_ACTIVITY_KIND_MEMCPY "
            "(start, end, bytes, copyKind, srcKind, dstKind) VALUES (?,?,?,?,?,?)",
            (950_000_000, 950_100_000, MB, 9, 7, 7),  # 7 is not in the enum table
        )
        conn.commit()
        conn.close()
        prof = self._open_profile(path)
        res = compute_transfer_residency(prof)
        self.assertTrue(any(r.src_kind == "Unknown" for r in res.rows))
        by_kind = {m.kind: m for m in compute_memcpy_by_kind(prof)}
        rows = [r for r in res.rows if r.kind == "Device-to-Device"]
        self.assertEqual(
            sum(r.transfers for r in rows), by_kind["Device-to-Device"].transfers
        )


if __name__ == "__main__":
    unittest.main()
