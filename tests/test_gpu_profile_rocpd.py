#!/usr/bin/env python3
"""Checks for rocpd ingestion and for nsys/rocpd behavioural parity.

The extraction tool is vendor-neutral by design: two profiled machines run
different accelerators, and modes/performance.md states its rules without naming a
vendor. These checks pin that the two formats produce structurally comparable
output and that vendor vocabulary is carried as data rather than assumed.

All checks run against the synthetic databases in ``gpu_profile_fixtures``. Real
rocpd captures are ~4 GB per rank and machine-specific; their paths may not enter
this repository.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gpu-profile-summary.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_profile_fixtures import (  # noqa: E402
    build_synthetic_nsys_db,
    build_synthetic_rocpd_db,
)


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


class RocpdIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.rocpd = build_synthetic_rocpd_db(root / "synthetic.rocpd")
        cls.nsys = build_synthetic_nsys_db(root / "synthetic.sqlite")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def payload(self, *args: str) -> dict:
        proc = run(*args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # -- rocpd is ingested at all --------------------------------------------

    def test_a_rocpd_profile_produces_a_summary(self):
        out = self.payload("summary", str(self.rocpd))
        self.assertGreater(out["profile_span_s"], 0.0)
        self.assertTrue(out["top_kernels"])

    def test_rocpd_device_info_carries_amd_vocabulary_as_data(self):
        """SM/CU is vendor vocabulary. The tool reports the vendor rather than
        assuming one, which is what lets one rule cover both machines."""
        dev = self.payload("summary", str(self.rocpd))["device_info"]
        self.assertEqual(dev["vendor"], "amd")
        self.assertIsNotNone(dev["sm_count"])

    def test_rocpd_memory_copies_are_split_by_direction(self):
        kinds = {t["kind"] for t in self.payload("memcpy", str(self.rocpd))["transfers"]}
        self.assertIn("Host-to-Device", kinds)
        self.assertIn("Device-to-Host", kinds)

    # -- capability honesty ---------------------------------------------------

    def test_api_regions_alone_do_not_count_as_user_markers(self):
        """The synthetic capture holds HIP/HSA API regions and no rocTX ranges.
        Counting API regions as annotations would report phase-labelling data that
        does not exist."""
        self.assertFalse(self.payload("markers", str(self.rocpd))["markers_present"])

    def test_a_roctx_range_flips_marker_detection(self):
        """Negative control for the check above: without this, markers_present
        could be hard-false and both checks would still pass."""
        marked = Path(self._tmp.name) / "marked.rocpd"
        marked.write_bytes(self.rocpd.read_bytes())
        conn = sqlite3.connect(marked)
        conn.row_factory = sqlite3.Row
        guid = conn.execute("SELECT guid FROM rocpd_string LIMIT 1").fetchone()[0]
        tbl = lambda b: f"`{b}_{guid.replace('-', '_')}`"  # noqa: E731

        sid = conn.execute("SELECT MAX(id) FROM rocpd_string").fetchone()[0] + 1
        conn.execute(
            f"INSERT INTO {tbl('rocpd_string')} (id, guid, string) VALUES (?,?,?)",
            (sid, guid, "ROCTX"),
        )
        conn.execute(
            f"INSERT INTO {tbl('rocpd_string')} (id, guid, string) VALUES (?,?,?)",
            (sid + 1, guid, "solve_phase"),
        )

        # Clone existing rows rather than constructing them: the concrete tables
        # carry NOT NULL columns this check has no business knowing about.
        def clone(table, overrides):
            row = dict(conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone())
            row.update(overrides)
            cols = list(row)
            conn.execute(
                f"INSERT INTO {tbl(table)} ({','.join(cols)}) "
                f"VALUES ({','.join('?' * len(cols))})",
                [row[c] for c in cols],
            )

        eid = conn.execute("SELECT MAX(id) FROM rocpd_event").fetchone()[0] + 1
        clone("rocpd_event", {"id": eid, "category_id": sid})
        rid = conn.execute("SELECT MAX(id) FROM rocpd_region").fetchone()[0] + 1
        clone("rocpd_region", {"id": rid, "event_id": eid, "name_id": sid + 1,
                               "start": 1_000, "end": 2_000})
        conn.commit()
        conn.close()
        self.assertTrue(self.payload("markers", str(marked))["markers_present"])

    def test_rocpd_reports_absent_mpi_rather_than_implying_health(self):
        """rocprofv3 does not intercept MPI. Absent tables must read as a gap."""
        self.assertFalse(self.payload("mpi", str(self.rocpd))["mpi_present"])

    # -- parity between the two formats ---------------------------------------

    def test_both_formats_yield_the_same_summary_shape(self):
        a = self.payload("summary", str(self.nsys))
        b = self.payload("summary", str(self.rocpd))
        self.assertEqual(set(a), set(b))

    def test_the_work_versus_elapsed_invariant_holds_on_both_formats(self):
        for name, db in (("nsys", self.nsys), ("rocpd", self.rocpd)):
            with self.subTest(fmt=name):
                out = self.payload("summary", str(db))
                self.assertLessEqual(out["gpu_busy_s"], out["profile_span_s"])
                self.assertGreaterEqual(out["gpu_kernel_s"], out["gpu_busy_s"])
                self.assertLessEqual(out["gpu_utilization_pct"], 100.0)

    def test_phases_partition_in_order_on_both_formats(self):
        for name, db in (("nsys", self.nsys), ("rocpd", self.rocpd)):
            with self.subTest(fmt=name):
                phases = self.payload("phases", str(db))["phases"]
                self.assertTrue(phases)
                for earlier, later in zip(phases, phases[1:]):
                    self.assertLessEqual(earlier["start_ns"], later["start_ns"])

    # -- the guardrails apply to rocpd too -------------------------------------

    def test_a_rocpd_profile_is_opened_read_only(self):
        """Target a concrete GUID-suffixed table, not an un-suffixed passthrough
        view: a DELETE against a view is refused whatever the connection mode, so
        aiming at one would pass without testing anything."""
        conn = sqlite3.connect(self.rocpd)
        concrete = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'rocpd_kernel_dispatch%'"
        ).fetchone()[0]
        conn.close()
        before = self.rocpd.read_bytes()
        proc = run("query", str(self.rocpd), "--sql", f"DELETE FROM `{concrete}`")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("readonly", proc.stderr.lower())
        self.assertEqual(self.rocpd.read_bytes(), before)

    def test_rocpd_schema_listing_names_the_passthrough_views(self):
        tables = self.payload("schema", str(self.rocpd))["tables"]
        self.assertIn("rocpd_kernel_dispatch", tables)
        self.assertIn("rocpd_string", tables)


if __name__ == "__main__":
    unittest.main()
