#!/usr/bin/env python3
"""Checks for the hypothesis-record tool.

Two properties it exists for.

A speedup bound follows arithmetically from a claimed runtime fraction, so a record
that asserts a different one is rejected rather than believed. ARCHITECTURE.md
§profile-analysis -- a wrong bound supplied by hand reads as a precise,
profile-grounded fact and nothing downstream rechecks it.

And a figure the extraction did not emit is declared as such. When Slice 6 check 1 was
relaxed on 2026-09-15 from "derived_by_hand is empty" to "hand-derived figures are
caveated", the declaration became the whole safeguard -- and nothing read it: emptying
the list while still citing hand-derived figures passed with zero errors. The controls
below pin the guard that closed it, including the two that perturb the tool itself,
because a guard that cannot fire is the same defect as a harness that cannot fail.
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


def run(*args: str, tool: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(tool or TOOL), *args], capture_output=True, text=True
    )


# A figure read from a run log rather than emitted by an extraction command. This is the
# ordinary case the relaxed criterion admits, not an exotic one: comparing a capture
# against an untraced control run is cross-source arithmetic by construction.
RUN_LOG_SOURCE = "grep -E 'Aggregate time' output.tune"


def with_run_log_figure(*, flagged: bool, declared: bool) -> dict:
    """VALID plus one figure taken from outside the profile, flagged and declared or not."""
    rec = copy.deepcopy(VALID)
    hyp = rec["hypotheses"][0]
    entry = {
        "quantity": "un-profiled elapsed time",
        "value": 52.358,
        "unit": "s",
        "from": RUN_LOG_SOURCE,
    }
    if flagged:
        entry["hand_derived"] = True
    hyp["evidence"].append(entry)
    hyp["queries"].append(RUN_LOG_SOURCE)
    if declared:
        rec["extraction"]["derived_by_hand"] = ["un-profiled elapsed time, from the control run"]
    return rec


def sandboxed_tool(tmp: Path, old: str, new: str) -> Path:
    """Write a perturbed copy of the tool into a stand-in handbook layout.

    The tool resolves both the schema and the set of extraction commands from its own
    location, so a perturbed copy needs that layout around it rather than a bare file.
    The substitution is asserted to have landed: a pattern that silently matches nothing
    produces a control that passes for the wrong reason, which is the defect the
    2026-09-14 round hit.
    """
    source = TOOL.read_text()
    assert source.count(old) == 1, f"perturbation anchor not unique: {old!r}"
    patched = source.replace(old, new)
    assert patched != source, "perturbation did not land"
    (tmp / "tools").mkdir(parents=True, exist_ok=True)
    (tmp / "schemas").mkdir(parents=True, exist_ok=True)
    (tmp / "schemas" / "hypothesis.schema.json").write_text(
        (ROOT / "schemas" / "hypothesis.schema.json").read_text()
    )
    for name in ("gpu-profile-summary.py", "gpu-profile-diff.py"):
        (tmp / "tools" / name).write_text("# stand-in for layout resolution\n")
    dest = tmp / "tools" / "hypothesis-record.py"
    dest.write_text(patched)
    return dest


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

    def test_an_empty_query_list_does_not_disable_the_provenance_check(self):
        """The negative control for the guard itself.

        Until 2026-09-14 the check read ``if src and queries and ...``, so an empty
        ``queries`` list skipped it: a record whose every figure was fabricated
        passed with zero errors. This is the perturbation that must land on the
        guard rather than beside it -- the figure below names a source no command
        could have produced, and it is the empty list, not the figure, that used to
        let it through.
        """
        bad = copy.deepcopy(VALID)
        bad["extraction"]["tool"] = "none - figures invented"
        bad["hypotheses"][0]["evidence"][0]["from"] = "my imagination"
        bad["hypotheses"][0]["queries"] = []
        proc = run(self.write(bad))
        self.assertEqual(proc.returncode, 1, "fabricated record passed: the guard did not fire")
        self.assertIn("queries: empty", proc.stderr)

    def test_the_empty_query_perturbation_is_not_vacuous(self):
        """Rejects the no-op version of the control above.

        If the same record with its queries restored also failed, the control would
        prove nothing about the empty list -- it would just be a broken record.

        The flag and declaration below are not a loosening of this control. "my
        imagination" is not a command the extraction tools provide, so the 2026-09-15
        guard fires on it too; declaring it keeps the queries list the only variable
        that moves between this test and the one above.
        """
        ok = copy.deepcopy(VALID)
        ok["hypotheses"][0]["evidence"][0]["from"] = "my imagination"
        ok["hypotheses"][0]["evidence"][0]["hand_derived"] = True
        ok["extraction"]["derived_by_hand"] = ["a figure with no command behind it"]
        ok["hypotheses"][0]["queries"] = ["my imagination was not consulted"]
        self.assertEqual(run(self.write(ok)).returncode, 0)

    # -- hand-derivation is declared ------------------------------------------

    def test_a_figure_from_outside_the_extraction_tools_must_be_flagged(self):
        proc = run(self.write(with_run_log_figure(flagged=False, declared=True)))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("derived by hand", proc.stderr)

    def test_that_perturbation_is_not_vacuous(self):
        """The same record, flagged and declared, passes -- so the rejection above is
        the missing flag and not the run-log figure itself."""
        proc = run(self.write(with_run_log_figure(flagged=True, declared=True)))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_flagging_without_declaring_is_rejected(self):
        """The defect this guard was built for, reproduced exactly.

        On 2026-09-15 a real record had its extraction.derived_by_hand emptied while
        every hand-derived figure stayed cited, and the checker reported zero errors.
        """
        proc = run(self.write(with_run_log_figure(flagged=True, declared=False)))
        self.assertEqual(proc.returncode, 1, "emptying the declaration passed: guard did not fire")
        self.assertIn("only", proc.stderr)
        self.assertIn("caveat", proc.stderr)

    def test_declaring_without_flagging_is_rejected(self):
        """A declaration that names no figure caveats nothing, so the link is checked
        in both directions rather than only the one that is easy to forget."""
        rec = copy.deepcopy(VALID)
        rec["extraction"]["derived_by_hand"] = ["a quantity no evidence item claims"]
        proc = run(self.write(rec))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("caveats nothing", proc.stderr)

    def test_extraction_commands_are_recognised_from_the_installed_layout(self):
        """Not vacuous: the fixture's command must really be a file in tools/, or the
        test would pass because nothing matched rather than because matching worked."""
        self.assertTrue((ROOT / "tools" / "gpu-profile-summary.py").is_file())
        proc = run(self.write(copy.deepcopy(VALID)))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    # -- the guard itself can fail --------------------------------------------

    def test_silencing_the_guard_fails_the_control(self):
        """Perturb the tool so the guard never fires, and confirm the control above
        then passes. If it still failed, the assertion would be resting on something
        other than this guard.

        ``declared=False`` deliberately: with a declaration present and nothing flagged
        the dangling-declaration check also fires, so the record would go on failing
        with this guard silenced -- a confounded control that proves nothing. The first
        draft of this test had exactly that defect and the suite caught it.
        """
        tool = sandboxed_tool(
            Path(self._tmp.name),
            "if src and not hand and not is_extraction_command(src):  # GUARD: unflagged",
            "if False:  # GUARD: unflagged (silenced)",
        )
        path = self.write(with_run_log_figure(flagged=False, declared=False))
        self.assertEqual(run(path, tool=tool).returncode, 0, "guard was not the thing being tested")
        self.assertEqual(run(path).returncode, 1, "unperturbed tool must still reject it")

    def test_a_guard_that_always_fires_is_also_wrong(self):
        """The opposite perturbation. A check that fires on everything is
        indistinguishable from one that fires on nothing, so pin that it discriminates."""
        tool = sandboxed_tool(
            Path(self._tmp.name),
            "if src and not hand and not is_extraction_command(src):  # GUARD: unflagged",
            "if src:  # GUARD: unflagged (always firing)",
        )
        path = self.write(copy.deepcopy(VALID))
        self.assertEqual(run(path, tool=tool).returncode, 1, "guard is a constant, not a check")
        self.assertEqual(run(path).returncode, 0, "unperturbed tool must accept a clean record")

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
