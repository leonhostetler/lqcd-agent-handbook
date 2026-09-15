#!/usr/bin/env python3
"""Checks for the hypothesis-record tool.

The property it exists for: a speedup bound follows arithmetically from a claimed
runtime fraction, so a record that asserts a different one is rejected rather than
believed. ARCHITECTURE.md §profile-analysis -- a wrong bound supplied by hand reads
as a precise, profile-grounded fact and nothing downstream rechecks it.
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "hypothesis-record.py"

VALID = {
    "schema_version": 1,
    "generated": "2026-09-14",
    "profile": {
        "identity": "run-a/rank0",
        "capture_conditions": {"autotune_cache": "warm"},
    },
    "extraction": {"tool": "gpu-profile-summary.py"},
    "hypotheses": [
        {
            "bottleneck": "host-blocked on synchronization",
            "phase": "solve",
            "description": "The host spends most of the phase blocked in synchronization.",
            "evidence": [
                {"quantity": "cpu_sync_blocked_pct", "value": 40.0, "unit": "%",
                 "from": "gpu-profile-summary.py summary run-a/rank0"}
            ],
            "queries": ["gpu-profile-summary.py summary run-a/rank0"],
            "runtime_fraction_pct": 40.0,
            "suggestion": "Overlap the transfer with the following solve.",
            "change_class": "source",
            "grounding": {"basis": "profile"},
            "confidence": "medium",
            "refuted_by": "A capture showing host sync time below 10% of the phase.",
        }
    ],
}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


class HypothesisRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "record.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, record: dict) -> str:
        self.path.write_text(json.dumps(record))
        return str(self.path)

    # -- the property the tool exists for -------------------------------------

    def test_a_record_asserting_bounds_that_do_not_follow_is_rejected(self):
        bad = copy.deepcopy(VALID)
        bad["hypotheses"][0]["speedup_bounds_pct"] = {"lower": 300.0, "upper": 900.0}
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("derived, never asserted", proc.stderr)

    def test_fix_writes_the_derived_bounds(self):
        path = self.write(copy.deepcopy(VALID))
        self.assertEqual(run(path, "--fix").returncode, 0)
        written = json.loads(Path(path).read_text())["hypotheses"][0]["speedup_bounds_pct"]
        # 40% of the phase: halving it gains 25%, removing it entirely gains 66.7%.
        self.assertEqual(written, {"lower": 25.0, "upper": 66.7})

    def test_a_null_fraction_yields_null_bounds(self):
        rec = copy.deepcopy(VALID)
        rec["hypotheses"][0]["runtime_fraction_pct"] = None
        path = self.write(rec)
        run(path, "--fix")
        self.assertIsNone(json.loads(Path(path).read_text())["hypotheses"][0]["speedup_bounds_pct"])

    def test_a_fraction_leaving_no_residual_reports_an_unbounded_upper(self):
        """Reporting a huge finite number there would be meaningless precision."""
        rec = copy.deepcopy(VALID)
        rec["hypotheses"][0]["runtime_fraction_pct"] = 99.95
        path = self.write(rec)
        run(path, "--fix")
        bounds = json.loads(Path(path).read_text())["hypotheses"][0]["speedup_bounds_pct"]
        self.assertIsNone(bounds["upper"])
        self.assertIsNotNone(bounds["lower"])

    # -- evidence provenance --------------------------------------------------

    def test_a_figure_citing_no_listed_query_is_rejected(self):
        bad = copy.deepcopy(VALID)
        bad["hypotheses"][0]["evidence"][0]["from"] = "somewhere I did not record"
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("names no listed query", proc.stderr)

    def test_a_hypothesis_with_no_evidence_is_rejected(self):
        bad = copy.deepcopy(VALID)
        bad["hypotheses"][0]["evidence"] = []
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no figures is an opinion", proc.stderr)

    # -- the schema is the source of the key list -----------------------------

    def test_required_keys_come_from_the_schema_not_the_tool(self):
        """Adding a required key to the schema must tighten the tool without an
        edit to it; restating the list in both is the drift P2 forbids."""
        schema = json.loads((ROOT / "schemas" / "hypothesis.schema.json").read_text())
        required = schema["properties"]["hypotheses"]["items"]["required"]
        self.assertIn("refuted_by", required)
        bad = copy.deepcopy(VALID)
        del bad["hypotheses"][0]["refuted_by"]
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing required key refuted_by", proc.stderr)

    def test_an_illegal_enum_value_is_rejected(self):
        bad = copy.deepcopy(VALID)
        bad["hypotheses"][0]["change_class"] = "vibes"
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not one of", proc.stderr)

    # -- reporting and dependencies -------------------------------------------

    def test_a_valid_record_passes_and_names_what_was_not_checked(self):
        proc = run(self.write(copy.deepcopy(VALID)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("NOT checked", proc.stdout)
        self.assertNotIn("passed", proc.stdout.lower())

    def test_the_tool_imports_only_the_standard_library(self):
        allowed = {"__future__", "argparse", "json", "sys", "pathlib"}
        for node in ast.walk(ast.parse(TOOL.read_text())):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            else:
                continue
            for mod in mods:
                self.assertIn(mod.split(".")[0], allowed, f"non-stdlib import: {mod}")

    def test_a_malformed_record_fails_cleanly(self):
        self.path.write_text("{not json")
        proc = run(str(self.path))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
