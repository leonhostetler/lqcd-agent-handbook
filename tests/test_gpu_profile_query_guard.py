#!/usr/bin/env python3
"""Controls for the `query` escape hatch: plan check, deadline, and rendering.

The recorded defect these guard. A session analysing a real capture wrote a query
whose CTE SQLite chose to *inline* rather than materialise. Inside a correlated
subquery that turns a 260-row derivation into a full scan of a 5,066,637-row event
table, once for each of 4,749,738 outer rows -- roughly 2.4e13 row visits to
recompute a constant. It returned a single row, so `--max-rows` bounded nothing,
and it was not interruptible because the CLI passed no stop_event, so it had to be
killed as a process after ~26 minutes.

Three claims in the docs were wrong at once, and each has a control below:

* that the escape hatch was "interruptible" -- nothing could stop it;
* that "an uncapped scan" was the hazard -- one scan of that table costs 0.23 s,
  and the hazard is the nested loop around it;
* that the row cap was the safeguard -- it bounds output, never work.

Per conventions/repeated-work.md a guard that cannot fire is indistinguishable
from one that always passes, so every control here is paired with the perturbation
that must move it, and the discriminating case that must *not* move it: the same
query written with MATERIALIZED has to be accepted, or the guard is a blanket ban
on correlated subqueries rather than a plan check.
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
SUMMARY = ROOT / "tools" / "gpu-profile-summary.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

from gpu_profile.detect import open_profile  # noqa: E402
from gpu_profile_fixtures import build_synthetic_nsys_db  # noqa: E402

# Above NESTED_SCAN_ROW_THRESHOLD (100_000), so the guard has something to size.
BIG_ROWS = 150_000


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SUMMARY), *args], capture_output=True, text=True
    )


class QueryGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.db = build_synthetic_nsys_db(root / "report.0.sqlite")
        # A table large enough to trip the threshold, and a small one that must not.
        conn = sqlite3.connect(cls.db)
        conn.execute("CREATE TABLE BIG (start INTEGER, end INTEGER, kind INTEGER)")
        conn.executemany(
            "INSERT INTO BIG VALUES (?,?,?)",
            [(i * 10, i * 10 + 5, i % 3) for i in range(BIG_ROWS)],
        )
        conn.execute("CREATE TABLE SMALL (start INTEGER, end INTEGER)")
        conn.executemany("INSERT INTO SMALL VALUES (?,?)", [(i, i + 1) for i in range(50)])
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # -- the plan check -------------------------------------------------------

    # Outer over SMALL, inner re-scanning BIG: the guard keys on the scanned
    # table's size, so this is flagged exactly as the real one was, while staying
    # cheap enough that --allow-nested-scan can be shown to actually run it.
    HAZARD_SQL = """
        WITH picked AS (SELECT start, end FROM BIG WHERE kind = 2 AND start < 100)
        SELECT (SELECT COUNT(*) FROM SMALL u
                WHERE EXISTS (SELECT 1 FROM picked
                              WHERE u.start >= picked.start AND u.end <= picked.end)) AS n
    """

    def test_a_correlated_scan_of_a_large_table_is_refused(self):
        proc = run("query", str(self.db), "--sql", self.HAZARD_SQL)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("re-scans BIG", proc.stderr)
        self.assertIn("MATERIALIZED", proc.stderr)

    def test_the_materialized_form_of_the_same_query_is_accepted(self):
        """The discriminating case: the guard reads the plan, not the SQL text.

        Without this the guard could be a blanket refusal of correlated subqueries
        and every other control here would still pass.
        """
        proc = run(
            "query", str(self.db), "--sql", self.HAZARD_SQL.replace("AS (", "AS MATERIALIZED (")
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_correlated_scan_of_a_small_table_is_allowed(self):
        """The threshold must be load-bearing, not decorative."""
        sql = """
            SELECT (SELECT COUNT(*) FROM SMALL u
                    WHERE EXISTS (SELECT 1 FROM SMALL s
                                  WHERE u.start >= s.start AND u.end <= s.end)) AS n
        """
        proc = run("query", str(self.db), "--sql", sql)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_override_runs_the_query_the_guard_refused(self):
        proc = run(
            "query", str(self.db), "--sql", self.HAZARD_SQL, "--allow-nested-scan"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_a_plain_aggregate_is_not_flagged(self):
        proc = run("query", str(self.db), "--sql", "SELECT COUNT(*) AS n FROM BIG")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    # -- the deadline ---------------------------------------------------------

    def test_the_deadline_stops_a_query_the_override_let_through(self):
        proc = run(
            "query", str(self.db), "--sql", self.HAZARD_SQL,
            "--allow-nested-scan", "--max-seconds", "0.05",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("max-seconds", proc.stderr)

    def test_zero_disables_the_deadline(self):
        proc = run(
            "query", str(self.db), "--sql", "SELECT COUNT(*) AS n FROM BIG",
            "--max-seconds", "0",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_row_cap_does_not_bound_work(self):
        """The premise the deadline exists for, asserted rather than assumed.

        A one-row aggregate under a one-row cap must still visit every row: if the
        cap bounded work this count could not be right.
        """
        proc = run(
            "query", str(self.db), "--sql", "SELECT COUNT(*) AS n FROM BIG", "--max-rows", "1"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["rows"][0]["n"], BIG_ROWS)

    def test_elapsed_time_is_reported(self):
        proc = run("query", str(self.db), "--sql", "SELECT 1 AS n")
        self.assertIn("elapsed_s", json.loads(proc.stdout))

    # -- the plan surface itself ---------------------------------------------

    def test_explain_plan_does_not_execute_the_query(self):
        """Planning must be free, or checking every query would cost more than it saves."""
        profile = open_profile(self.db)
        try:
            plan = profile.explain_plan("SELECT COUNT(*) FROM BIG")
            self.assertTrue(any("BIG" in str(r[3]) for r in plan))
        finally:
            profile.close()

    def test_the_profile_is_not_written_to(self):
        before = self.db.stat().st_mtime_ns
        run("query", str(self.db), "--sql", self.HAZARD_SQL)
        self.assertEqual(self.db.stat().st_mtime_ns, before)


class TableRenderingControls(unittest.TestCase):
    """`--table` must not drop a section that the JSON carries.

    The union below was added to transfer-overlap precisely so a session would stop
    adding the per-direction column by hand -- and `--table`, which is what a session
    actually reads, silently dropped every nested object. A renderer that hides a
    field is the same defect as a tool that never computed it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db = build_synthetic_nsys_db(Path(cls._tmp.name) / "r.sqlite")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_every_json_key_survives_table_rendering(self):
        as_json = json.loads(run("transfer-overlap", str(self.db)).stdout)
        as_table = run("--table", "transfer-overlap", str(self.db)).stdout
        for key, value in as_json.items():
            if value is None:
                continue
            self.assertIn(key, as_table, f"--table dropped the {key!r} section")

    def test_the_union_is_rendered_with_its_fields(self):
        as_table = run("--table", "transfer-overlap", str(self.db)).stdout
        self.assertIn("union:", as_table)
        self.assertIn("directions_sum_exposed_s", as_table)


if __name__ == "__main__":
    unittest.main()
