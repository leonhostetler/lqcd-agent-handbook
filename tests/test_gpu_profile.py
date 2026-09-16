#!/usr/bin/env python3
"""Checks for the offline GPU profile extraction tool.

Every check runs against the synthetic database in ``gpu_profile_fixtures``. Real
captures are multi-gigabyte and machine-specific, and their paths and job
identifiers may not enter this repository.

The properties pinned here are the ones ARCHITECTURE.md §profile-analysis and
modes/performance.md depend on: the tool imports nothing outside the standard
library, it cannot write to a profile, its raw-query path is capped, and it
reports a capability gap as a gap rather than as silence.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "gpu-profile-summary.py"
PKG = ROOT / "tools" / "gpu_profile"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpu_profile_fixtures import build_synthetic_nsys_db  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args], capture_output=True, text=True
    )


class GpuProfileToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db = build_synthetic_nsys_db(Path(cls._tmp.name) / "synthetic.sqlite")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def payload(self, *args: str) -> dict:
        proc = run(*args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    # -- the dependency rule -------------------------------------------------

    def test_tool_imports_only_the_standard_library(self):
        """A third-party import is the failure mode that makes the tool unusable on
        a login node at the moment it is wanted -- the handbook has already lost a
        mandatory validator that way. Parsed with ast rather than scanned line by
        line: prose beginning with "from" is not an import."""
        allowed = {
            "__future__", "argparse", "collections", "dataclasses", "enum", "json",
            "math", "pathlib", "re", "sqlite3", "statistics", "sys", "threading",
            "time", "typing", "gpu_profile",
        }
        offenders = []
        for path in [TOOL, *sorted(PKG.glob("*.py"))]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:  # relative import within the package
                        continue
                    mods = [node.module or ""]
                else:
                    continue
                for mod in mods:
                    if mod.split(".")[0] not in allowed:
                        offenders.append(f"{path.name}: {mod}")
        self.assertEqual(offenders, [], f"non-stdlib imports: {offenders}")

    # -- profiles are immutable inputs ---------------------------------------

    def test_a_write_through_the_query_path_is_refused(self):
        proc = run("query", str(self.db), "--sql", "DELETE FROM CUPTI_ACTIVITY_KIND_KERNEL")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("readonly", proc.stderr.lower())

    def test_the_profile_is_unchanged_after_an_attempted_write(self):
        before = self.db.read_bytes()
        run("query", str(self.db), "--sql", "DROP TABLE CUPTI_ACTIVITY_KIND_KERNEL")
        self.assertEqual(self.db.read_bytes(), before)

    # -- the raw-query path is an escape hatch, not the method ---------------

    def test_query_caps_rows_and_reports_truncation(self):
        out = self.payload(
            "query", str(self.db), "--sql", "SELECT start FROM CUPTI_ACTIVITY_KIND_KERNEL",
            "--max-rows", "4",
        )
        self.assertEqual(out["row_count"], 4)
        self.assertTrue(out["truncated"])

    def test_query_reports_a_bad_column_without_a_traceback(self):
        proc = run("query", str(self.db), "--sql", "SELECT nope FROM CUPTI_ACTIVITY_KIND_KERNEL")
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)

    # -- the aggregations the tool exists to own -----------------------------

    def test_summary_separates_kernel_work_from_elapsed_busy_time(self):
        """Summed durations are work; merged intervals are elapsed. Conflating
        them is the misreading modes/performance.md names first."""
        out = self.payload("summary", str(self.db))
        self.assertLessEqual(out["gpu_busy_s"], out["profile_span_s"])
        self.assertGreaterEqual(out["gpu_kernel_s"], out["gpu_busy_s"])
        self.assertLessEqual(out["gpu_utilization_pct"], 100.0)

    def test_kernels_are_grouped_by_full_name_not_display_name(self):
        out = self.payload("kernels", str(self.db))
        names = [k["name"] for k in out["kernels"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(any("myKernel3D" in n for n in names))

    def test_a_window_narrows_the_kernel_count(self):
        whole = self.payload("kernels", str(self.db))["kernels"]
        windowed = self.payload(
            "kernels", str(self.db), "--start-ns", "1000000000", "--end-ns", "1010000000"
        )["kernels"]
        self.assertLess(
            sum(k["calls"] for k in windowed), sum(k["calls"] for k in whole)
        )

    def test_phases_partition_the_profile_in_order(self):
        phases = self.payload("phases", str(self.db))["phases"]
        self.assertTrue(phases)
        for earlier, later in zip(phases, phases[1:]):
            self.assertLessEqual(earlier["start_ns"], later["start_ns"])

    def test_max_phases_one_returns_a_single_phase(self):
        phases = self.payload("phases", str(self.db), "--max-phases", "1")["phases"]
        self.assertEqual(len(phases), 1)

    def test_summary_already_contains_the_phase_table(self):
        """`phases` returns what `summary` already carries, at the same cost --
        measured at 48.7 s each on one capture. The playbook tells a session to read
        it out of the summary rather than pay twice; this pins that it is actually
        the same table, so that instruction stays true."""
        summary = self.payload("summary", str(self.db))
        phases = self.payload("phases", str(self.db))
        self.assertEqual(summary["phases"], phases["phases"])
        self.assertEqual(summary["phase_segmentation"], phases["phase_segmentation"])

    def test_a_phase_table_records_the_segmentation_that_produced_it(self):
        """Phase windows depend on --max-phases as well as on the capture, so a
        start/end pair from one segmentation is meaningless against another. Both
        commands take the flag, so a payload that does not say which cap produced it
        cannot be reconciled."""
        seg = self.payload("phases", str(self.db))["phase_segmentation"]
        self.assertEqual(seg["max_phases"], 8)
        self.assertEqual(seg["selected_k"], len(self.payload("phases", str(self.db))["phases"]))

    def test_two_caps_give_two_segmentations_and_each_says_so(self):
        """The negative control for the check above: if the field did not move with
        the cap it would be decoration."""
        wide = self.payload("phases", str(self.db))
        narrow = self.payload("phases", str(self.db), "--max-phases", "2")
        self.assertNotEqual(len(wide["phases"]), len(narrow["phases"]))
        self.assertNotEqual(
            wide["phase_segmentation"]["max_phases"],
            narrow["phase_segmentation"]["max_phases"],
        )
        self.assertEqual(narrow["phase_segmentation"]["selected_k"], 2)

    def test_a_selected_k_at_the_cap_is_flagged(self):
        """k == cap means the elbow may lie above the cap, so the segmentation may
        be an artefact of the flag rather than of the run."""
        seg = self.payload("phases", str(self.db), "--max-phases", "2")["phase_segmentation"]
        self.assertIsNotNone(seg["note"])
        self.assertIn("equals the cap", seg["note"])

    def test_disabled_segmentation_says_it_is_disabled(self):
        seg = self.payload("phases", str(self.db), "--max-phases", "1")["phase_segmentation"]
        self.assertEqual(seg["selected_k"], 1)
        self.assertIn("disabled", seg["note"])

    def test_mpi_and_marker_presence_are_reported_explicitly(self):
        """Absent instrumentation must read as a gap, never as a clean result."""
        self.assertIn("mpi_present", self.payload("mpi", str(self.db)))
        self.assertIn("markers_present", self.payload("markers", str(self.db)))

    # -- negative controls ---------------------------------------------------

    def test_a_profile_with_no_kernel_table_yields_no_kernels_and_does_not_crash(self):
        empty = Path(self._tmp.name) / "nokernels.sqlite"
        conn = sqlite3.connect(empty)
        conn.execute("CREATE TABLE StringIds (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE CUPTI_ACTIVITY_KIND_MEMCPY (start INT, end INT, bytes INT, copyKind INT)")
        conn.commit()
        conn.close()
        out = self.payload("kernels", str(empty))
        self.assertEqual(out["kernels"], [])

    def test_a_truncated_rocpd_profile_fails_cleanly_rather_than_tracebacking(self):
        """A file carrying only rocpd_string is recognised as rocpd but holds no
        events. Stage 2b made rocpd ingestible, so the property worth pinning is
        no longer that it is deferred -- it is that a degenerate capture is
        reported rather than crashed on."""
        rocpd = Path(self._tmp.name) / "truncated.db"
        conn = sqlite3.connect(rocpd)
        conn.execute("CREATE TABLE rocpd_string (id INTEGER, guid TEXT, string TEXT)")
        conn.commit()
        conn.close()
        proc = run("summary", str(rocpd))
        self.assertNotIn("Traceback", proc.stderr)

    def test_an_nsys_rep_input_is_rejected_with_the_export_command(self):
        proc = run("summary", str(Path(self._tmp.name) / "x.nsys-rep"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("nsys export", proc.stderr)

    def test_a_non_sqlite_file_is_rejected_cleanly(self):
        junk = Path(self._tmp.name) / "junk.sqlite"
        junk.write_text("not a database")
        proc = run("summary", str(junk))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
