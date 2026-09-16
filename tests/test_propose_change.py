#!/usr/bin/env python3
"""Checks for the change-proposal harness.

`conventions/repeated-work.md` refuses to trust a new tool on a passing run: it
must be made to fail on purpose, and a perturbation that could succeed without
changing anything is vacuous. Every check below that asserts a step *passes* is
paired with one that makes the same step fail.

The harness shells out to the validator and the test suite. Running the real suite
from inside the suite would recurse and cost 70 s, so composition is tested with an
injected runner while the two steps whose logic is real -- index currency and the
privacy surface -- are exercised against real files. One end-to-end check plants a
deny-list violation in a copy of the tree and runs the real validator, because that
is the step whose failure matters most and a fake runner could not prove it fires.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "propose-change.py"

# Assembled at runtime, never written contiguously in this file. The validator
# scans every text file in the repository, including this one, so a literal
# deny-list violation here would make the handbook fail its own privacy check --
# and the placeholder forms it exempts (`<user>`, `$HOME`) are exempt precisely
# because they do not match, so they cannot be planted to prove the check fires.
PLANTED_HOME_PATH = "/" + "home/" + "someuser" + "/scratch/run.log"
TEST_GIT_EMAIL = "harness-test" + "@" + "example.invalid"

_spec = importlib.util.spec_from_file_location("_propose_change", HARNESS)
pc = importlib.util.module_from_spec(_spec)
# Register before executing: @dataclass resolves cls.__module__ through sys.modules
# and raises AttributeError on a module that is not there.
sys.modules["_propose_change"] = pc
_spec.loader.exec_module(pc)


@dataclass
class FakeProc:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def runner(**by_prefix):
    """Fake subprocess runner keyed on a distinctive token in the command."""

    def run(cmd, cwd):
        joined = " ".join(str(c) for c in cmd)
        for token, result in by_prefix.items():
            if token in joined:
                return result(cwd) if callable(result) else result
        return FakeProc()

    return run


class ValidatorStep(unittest.TestCase):
    def test_it_reports_the_validator_summary_not_a_stray_warning(self):
        """The summary is on stdout and the P2 advisories are on stderr. The first
        draft read the last stderr line and reported an unrelated file's advisory
        as the result."""
        step = pc.run_validator(ROOT, runner(**{"run-validator": FakeProc(
            0, stdout="no deny-list matches · 30 schema objects valid\n",
            stderr="warning: some/other/file.md:7: P2 advisory: numeric value 2\n")}))
        self.assertTrue(step.ok)
        self.assertIn("no deny-list matches", step.detail)
        self.assertNotIn("P2 advisory", step.detail)

    def test_it_fails_when_the_validator_fails(self):
        step = pc.run_validator(ROOT, runner(**{"run-validator": FakeProc(
            1, stderr="error: a/b.md:1: deny-list match (email address)\nchecked: ...\n")}))
        self.assertFalse(step.ok)
        self.assertIn("1 error(s)", step.detail)

    def test_a_silent_success_is_not_accepted(self):
        """Exit 0 with no summary means the validator did not run as expected;
        treating that as a pass is how a skipped check looks like a clean one."""
        step = pc.run_validator(ROOT, runner(**{"run-validator": FakeProc(0, stdout="")}))
        self.assertFalse(step.ok)


class SuiteStep(unittest.TestCase):
    def test_it_reports_how_many_tests_ran(self):
        step = pc.run_suite(ROOT, runner(**{"unittest": FakeProc(
            0, stderr="....\n----\nRan 352 tests in 71.4s\n\nOK\n")}))
        self.assertTrue(step.ok)
        self.assertIn("Ran 352 tests", step.detail)

    def test_it_fails_when_a_test_fails(self):
        step = pc.run_suite(ROOT, runner(**{"unittest": FakeProc(
            1, stderr="Ran 352 tests in 71.4s\n\nFAILED (failures=1)\n")}))
        self.assertFalse(step.ok)
        self.assertIn("FAILED", step.detail)


class IndexStep(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "software").mkdir()
        self.index = self.root / "software" / "INDEX.md"
        self.index.write_text("original\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_current_indices_pass(self):
        step = pc.regenerate_indices(self.root, runner(**{"build-index": FakeProc(0)}))
        self.assertTrue(step.ok)
        self.assertIn("already current", step.detail)

    def test_a_stale_index_fails_and_is_named(self):
        """The negative control for the check above. An index left unregenerated is
        well-formed and plausible, so nothing else in the pipeline notices by eye."""
        def rewrite(cwd):
            self.index.write_text("regenerated\n")
            return FakeProc(0)

        step = pc.regenerate_indices(self.root, runner(**{"build-index": rewrite}))
        self.assertFalse(step.ok)
        self.assertIn("software/INDEX.md", step.detail)
        self.assertIn("stale", step.detail)

    def test_a_failing_generator_fails_the_step(self):
        step = pc.regenerate_indices(
            self.root, runner(**{"build-index": FakeProc(1, stderr="boom")})
        )
        self.assertFalse(step.ok)


class PrivacySurface(unittest.TestCase):
    def test_it_reports_what_it_scanned_not_only_what_it_found(self):
        """The failure this step exists for: a sweep that never ran and a sweep that
        found nothing produce identical output unless the count is printed."""
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "added.txt"
            step = pc.privacy_surface(Path(d), ["one", "two", "three"], out)
        self.assertTrue(step.ok)
        self.assertIn("3 added lines", step.detail)

    def test_an_empty_proposal_says_so_rather_than_reporting_zero_matches(self):
        with tempfile.TemporaryDirectory() as d:
            step = pc.privacy_surface(Path(d), [], None)
        self.assertIn("no added lines", step.detail)
        self.assertNotIn("0 added lines", step.detail)

    def test_it_writes_the_lines_where_a_reviewer_can_read_them(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "added.txt"
            pc.privacy_surface(Path(d), ["alpha", "beta"], out)
            self.assertEqual(out.read_text().splitlines(), ["alpha", "beta"])

    def test_it_names_the_categories_no_pattern_can_decide(self):
        """The validator's deny list is regexes; PRIVACY.md also forbids hostnames,
        job ids and unpublished results. Claiming a clean sweep without naming those
        would be the tool overstating what it checked."""
        with tempfile.TemporaryDirectory() as d:
            step = pc.privacy_surface(Path(d), ["x"], None)
        self.assertIn("internal hostnames", step.detail)
        self.assertIn("job, ticket, or run identifiers", step.detail)


class AddedLinesFromGit(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for cmd in (["git", "init", "-q"],
                    ["git", "config", "user.email", TEST_GIT_EMAIL],
                    ["git", "config", "user.name", "t"]):
            subprocess.run(cmd, cwd=self.root, check=True, capture_output=True)
        (self.root / "a.md").write_text("base\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True,
                       capture_output=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_it_sees_lines_added_to_a_tracked_file(self):
        (self.root / "a.md").write_text("base\nADDED-TRACKED\n")
        self.assertIn("ADDED-TRACKED", pc.added_lines(self.root, "HEAD"))

    def test_it_sees_a_whole_new_untracked_file(self):
        """A new leaf is the likeliest place for material that must not be
        published, and `git diff` does not see it at all."""
        (self.root / "new.md").write_text("ADDED-UNTRACKED\n")
        self.assertIn("ADDED-UNTRACKED", pc.added_lines(self.root, "HEAD"))

    def test_an_unchanged_tree_yields_no_added_lines(self):
        """Rejects the vacuous version of the two checks above: if this returned
        content for a clean tree, matching a token would prove nothing."""
        self.assertEqual(pc.added_lines(self.root, "HEAD"), [])


class EndToEndNegative(unittest.TestCase):
    """The step whose failure matters most, proven against the real validator."""

    def test_a_planted_deny_list_violation_fails_the_validator_step(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "hb"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            clean = pc.run_validator(copy)
            self.assertTrue(clean.ok, f"copy is not clean to begin with: {clean.detail}")

            target = copy / "conventions" / "orientation.md"
            target.write_text(target.read_text() + f"\nSee {PLANTED_HOME_PATH}\n")
            dirty = pc.run_validator(copy)
        self.assertFalse(dirty.ok, "the real validator did not catch a planted home path")
        self.assertIn("error", dirty.detail)


class ReportComposition(unittest.TestCase):
    def test_one_failing_step_fails_the_report(self):
        r = pc.Report(base="HEAD", head="abc1234")
        r.steps = [pc.Step("a", True, ""), pc.Step("b", False, "")]
        self.assertFalse(r.ok)
        self.assertIn("NOT READY", pc.render(r))

    def test_a_passing_report_still_refuses_to_clear_publication(self):
        """The tool must not read as a publication verdict; PRIVACY.md keeps that
        decision with a person."""
        r = pc.Report(base="HEAD", head="abc1234")
        r.steps = [pc.Step("a", True, "")]
        rendered = pc.render(r)
        self.assertIn("clearance NOT granted", rendered)

    def test_the_report_records_the_harness_version_and_the_commit(self):
        """repeated-work.md requires a tool's version beside the output it
        generates, so a later behaviour change is attributable."""
        r = pc.Report(base="main", head="abc1234")
        rendered = pc.render(r)
        self.assertIn(pc.VERSION, rendered)
        self.assertIn("abc1234", rendered)
        self.assertIn("main", rendered)


if __name__ == "__main__":
    unittest.main()
