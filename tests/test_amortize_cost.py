"""The cost tool must never produce a share detached from a production solve count.

That substitution -- reading a cost share off a trial's own solve count and treating it
as production's -- is the failure ARCHITECTURE.md section 7.1a exists to prevent, and
these tests are what keep the structural half of the guard from regressing.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

# Every other test module does this, and this one relied on `unittest discover -s tests`
# having made the directory importable instead. That works under discovery and fails
# under any invocation that names the module directly, which made whether this module
# loaded at all depend on how the suite happened to be launched.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "amortize-cost.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [interpreter_for(), str(TOOL), *args],
        capture_output=True, text=True, check=False,
    )


class AmortizeCostTests(unittest.TestCase):
    A = ("--candidate", "lean", "1500", "16", "64")
    B = ("--candidate", "iso", "2400", "11", "64")

    def test_no_share_or_ranking_without_a_solve_count(self):
        """The exploratory path still runs; it just cannot emit an N-dependent quantity."""
        done = run(*self.A, *self.B, "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(payload["evaluated"], [])
        self.assertIsNone(payload["solve_counts"])
        self.assertIn("omitted by design", payload["note"])
        for row in payload["crossovers"]:
            self.assertNotIn("setup_share", row)

    def test_crossover_is_reported_with_no_solve_count_supplied(self):
        """An exploratory campaign discovers its regime boundary instead of declaring it."""
        done = run(*self.A, *self.B, "--objective", "resource", "--json")
        payload = json.loads(done.stdout)
        crossings = [x for x in payload["crossovers"] if x["crossover_solves"] is not None]
        self.assertEqual(len(crossings), 1)
        self.assertAlmostEqual(crossings[0]["crossover_solves"], 180.0)
        self.assertIn("lean wins below", crossings[0]["relation"])

    def test_setup_share_moves_with_the_solve_count(self):
        """The share is a function of N; a single number for it is the defect."""
        done = run("--candidate", "heavy-setup", "2000", "10", "100",
                   "--solves", "6", "1000", "--objective", "resource", "--json")
        rows = {r["solves"]: r for r in json.loads(done.stdout)["evaluated"]}
        self.assertGreater(rows[6]["setup_share"], 0.95)
        self.assertLess(rows[1000]["setup_share"], 0.20)

    def test_there_is_no_default_solve_count(self):
        """No value may be inferred -- least of all a trial's own."""
        text = TOOL.read_text()
        self.assertIn('"--solves"', text)
        self.assertIn("default=None", text)
        self.assertNotIn("DEFAULT_SOLVES", text)

    def test_resource_and_elapsed_can_rank_differently(self):
        """Node-seconds and wall time are separate objectives, per conventions/measurement.md."""
        done = run("--candidate", "big", "1000", "10", "100",
                   "--candidate", "small", "1000", "10", "50",
                   "--solves", "10", "--json")
        rows = json.loads(done.stdout)["evaluated"]
        resource = {r["candidate"]: r["total"] for r in rows if r["objective"] == "resource"}
        elapsed = {r["candidate"]: r["total"] for r in rows if r["objective"] == "elapsed"}
        self.assertLess(resource["small"], resource["big"])
        self.assertAlmostEqual(elapsed["small"], elapsed["big"])

    def test_invalid_candidate_is_rejected_with_the_name(self):
        done = run("--candidate", "bad", "1", "1", "0")
        self.assertEqual(done.returncode, 2)
        self.assertIn("bad:", done.stderr)
        self.assertIn("resource multiplier must be positive", done.stderr)

    def test_documents_point_at_the_tool(self):
        for rel in ("conventions/measurement.md",
                    "software/quda/solvers/staggered-multigrid/tuning.md"):
            self.assertIn("amortize-cost.py", (ROOT / rel).read_text(), rel)


if __name__ == "__main__":
    unittest.main()
