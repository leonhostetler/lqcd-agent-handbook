"""The drift triage must name the leaves an upstream merge invalidated, in both directions.

Forward: a cited file changed after the cited revision, and the cited lines moved or not.
Backward: a cited feature-branch commit or pull request became an ancestor of HEAD after
the leaf's observed commit. And the control: when the hunk-overlap check is disabled, the
"cited lines changed" status must disappear, so the status is shown to depend on it.

The re-cite proposal (--suggest-remap) has its own cases: a shifted range is proposed at its
new numbers, a range with an insertion inside it is proposed across the insertion and says
so, a partly rewritten range is proposed between its outermost survivors and says so, a range
deleted in place whose exact text survives once elsewhere is proposed there, a deleted range
and a range of bare braces get no proposal, and the control: with the alignment offset removed
the shifted range must collapse to its old numbers.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import PerturbationMixin, interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "upstream-drift.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t",
             "PATH": "/usr/bin:/bin", "HOME": str(repo)},
    ).stdout.strip()


def build_repo(base: Path) -> dict[str, str]:
    """main: c1 -> c2 (edits a.c lines 1-3) -> merge of feature (c3 adds c.c) as PR #7."""
    repo = base / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.c").write_text("line1\nline2\nline3\nline4\nline5\n")
    (repo / "b.c").write_text("stable\n")
    git(repo, "add", "."); git(repo, "commit", "-q", "-m", "c1")
    c1 = git(repo, "rev-parse", "HEAD")
    (repo / "a.c").write_text("LINE1\nLINE2\nline3\nline4\nline5\n")
    git(repo, "commit", "-q", "-am", "c2: edit a.c top")
    git(repo, "checkout", "-q", "-b", "feature", c1)
    (repo / "c.c").write_text("new\n")
    git(repo, "add", "."); git(repo, "commit", "-q", "-m", "c3: add c.c")
    c3 = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge pull request #7 from org/feature", "feature")
    head = git(repo, "rev-parse", "HEAD")
    return {"repo": str(repo), "c1": c1, "c3": c3, "head": head}


def build_handbook(base: Path, observed: str, c3: str, cite: str | None = None) -> Path:
    """`cite` is the revision the blob URLs name; it defaults to `observed`."""
    cite = cite or observed
    root = base / "handbook"
    if root.exists():
        shutil.rmtree(root)
    (root / "software" / "foo").mkdir(parents=True)
    (root / "software" / "foo" / "project.yaml").write_text(
        "schema_version: 2\nname: foo\nrepository: https://github.com/org/repo.git\n"
    )
    leaf = textwrap.dedent(f"""\
        ---
        title: t
        summary: s
        scope: [software:foo]
        load_when: always
        evidence: source
        sources:
          - https://github.com/org/repo/blob/{cite}/a.c#L1-L2
          - https://github.com/org/repo/blob/{cite}/a.c#L4-L5
          - https://github.com/org/repo/blob/{cite}/b.c
          - https://github.com/org/repo/commit/{c3}
          - https://github.com/org/repo/pull/7
        observed: "2026-01-01"
        observed_on:
          software:
            foo:
              commit: {observed}
              branch: main
        ---
        body
        """)
    (root / "software" / "foo" / "leaf.md").write_text(leaf)
    # A validated-stack record citing the same moved file: pinned by design, so not drift.
    stack = root / "machines" / "box" / "stacks" / "foo-2026q4"
    stack.mkdir(parents=True)
    (stack / "notes.md").write_text(leaf.replace("title: t", "title: stack notes"))
    return root


class UpstreamDriftTests(PerturbationMixin, unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed -- this check DID NOT RUN")
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.repo = build_repo(self.base)

    def run_tool(self, root: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [interpreter_for("yaml"), str(TOOL), "--root", str(root),
             "--checkout", f"foo={self.repo['repo']}", "--json", *extra],
            capture_output=True, text=True, check=False,
        )

    def findings(self, root: Path) -> dict[str, dict]:
        done = self.run_tool(root)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        leaves = {leaf["leaf"]: leaf for leaf in payload["leaves"]}
        self.assertIn("software/foo/leaf.md", leaves)
        report = leaves["software/foo/leaf.md"]
        by_source = {}
        for f in report["findings"]:
            key = f["source"].split("/blob/")[-1] if f["kind"] == "blob" else f["kind"]
            by_source[key] = f
        by_source["_ancestry"] = report["ancestry"]
        return by_source

    def test_forward_drift_distinguishes_cited_lines_from_the_rest_of_the_file(self):
        root = build_handbook(self.base, self.repo["c1"], self.repo["c3"])
        f = self.findings(root)
        self.assertEqual(f["_ancestry"], "HEAD descends from the observed commit")
        self.assertEqual(f[f"{self.repo['c1']}/a.c#L1-L2"]["status"], "cited lines changed since the cited revision")
        self.assertEqual(f[f"{self.repo['c1']}/a.c#L4-L5"]["status"],
                         "file changed outside cited lines since the cited revision")
        self.assertEqual(f[f"{self.repo['c1']}/b.c"]["status"], "unchanged since the cited revision")
        self.assertFalse(f[f"{self.repo['c1']}/b.c"]["flag"])
        self.assertTrue(f[f"{self.repo['c1']}/a.c#L1-L2"]["flag"])

    def test_the_other_direction_reports_a_merge_after_observation(self):
        root = build_handbook(self.base, self.repo["c1"], self.repo["c3"])
        f = self.findings(root)
        self.assertEqual(f["commit"]["status"], "merged since observation")
        self.assertTrue(f["commit"]["flag"])
        self.assertEqual(f["pull"]["status"], "merged since observation")
        self.assertTrue(any("#7" in m for m in f["pull"]["merges"]))

    def test_a_leaf_observed_at_head_is_not_flagged(self):
        root = build_handbook(self.base, self.repo["head"], self.repo["c3"])
        f = self.findings(root)
        self.assertEqual(f["_ancestry"], "HEAD is the observed commit")
        self.assertEqual(f["commit"]["status"], "merged before observation")
        self.assertEqual(f["pull"]["status"], "merged before observation")
        for key, finding in f.items():
            if key != "_ancestry":
                self.assertFalse(finding["flag"], key)
        done = self.run_tool(root, "--fail-on-drift")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_drift_is_measured_from_observation_when_the_citation_is_older(self):
        """A leaf re-observed at HEAD that still cites older blob URLs has nothing to review."""
        root = build_handbook(self.base, self.repo["head"], self.repo["c3"], cite=self.repo["c1"])
        f = self.findings(root)
        for key in (f"{self.repo['c1']}/a.c#L1-L2", f"{self.repo['c1']}/a.c#L4-L5", f"{self.repo['c1']}/b.c"):
            self.assertEqual(f[key]["status"], "current", key)
            self.assertFalse(f[key]["flag"], key)

    def test_a_citation_older_than_observation_still_flags_later_change(self):
        """Observed at c2 citing c1 lines: a.c changed c1->c2, so its cited lines are unreliable
        and nothing changed c2->HEAD on a.c; c.c did arrive after c2 and is not cited. Build a
        leaf observed at c2 citing a.c at c1 and check the predate status surfaces only when the
        file moves again after observation."""
        c2 = git(Path(self.repo["repo"]), "rev-parse", "HEAD^1")  # first parent of the merge
        root = build_handbook(self.base, c2, self.repo["c3"], cite=self.repo["c1"])
        f = self.findings(root)
        # a.c is identical between c2 and HEAD, so an old citation is not drift.
        self.assertEqual(f[f"{self.repo['c1']}/a.c#L1-L2"]["status"], "unchanged since observation")
        self.assertFalse(f[f"{self.repo['c1']}/a.c#L1-L2"]["flag"])

    def test_stack_records_are_skipped_unless_asked_for(self):
        """A stack record's citations are pinned to the build it records; upstream moving is
        not drift for it, so it is skipped by default and listed only with --include-stacks."""
        root = build_handbook(self.base, self.repo["c1"], self.repo["c3"])
        done = self.run_tool(root)
        leaves = {leaf["leaf"] for leaf in json.loads(done.stdout)["leaves"]}
        self.assertIn("software/foo/leaf.md", leaves)
        self.assertNotIn("machines/box/stacks/foo-2026q4/notes.md", leaves)
        self.assertFalse(json.loads(done.stdout)["summary"]["stack_records_included"])
        done = self.run_tool(root, "--include-stacks")
        leaves = {leaf["leaf"] for leaf in json.loads(done.stdout)["leaves"]}
        self.assertIn("machines/box/stacks/foo-2026q4/notes.md", leaves)

    def test_fail_on_drift_exits_nonzero_when_something_moved(self):
        root = build_handbook(self.base, self.repo["c1"], self.repo["c3"])
        done = self.run_tool(root, "--fail-on-drift")
        self.assertEqual(done.returncode, 1, done.stderr)

    def test_summary_names_what_was_checked_and_never_passed(self):
        root = build_handbook(self.base, self.repo["head"], self.repo["c3"])
        done = subprocess.run(
            [interpreter_for("yaml"), str(TOOL), "--root", str(root),
             "--checkout", f"foo={self.repo['repo']}"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        last = done.stdout.strip().splitlines()[-1]
        self.assertIn("leaves with sources read", last)
        self.assertIn("claims NOT judged", last)
        self.assertNotIn("passed", last.lower())

    def test_control_the_cited_lines_status_depends_on_the_overlap_check(self):
        """Disable the hunk-overlap test and the finer status must vanish, not persist."""
        self.perturb(TOOL, "if start <= b and end >= a:\n            return True",
                     "if False:\n            return True")
        root = build_handbook(self.base, self.repo["c1"], self.repo["c3"])
        f = self.findings(root)
        self.assertEqual(f[f"{self.repo['c1']}/a.c#L1-L2"]["status"],
                         "file changed outside cited lines since the cited revision")


def build_remap_repo(base: Path) -> dict[str, str]:
    """c1: f.c has fifteen lines, the tenth a bare brace. c2: old lines 11-12 move to the
    top of the file, three header lines follow them, one line is inserted between old 4 and 5,
    old line 8 is rewritten, and old lines 13-14 are deleted."""
    repo = base / "rrepo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    words = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota",
             None, "kappa", "lambda", "mu", "nu", "xi"]
    old = [f"int {w}_function(void) {{ return {i}; }}" if w else "}" for i, w in enumerate(words, 1)]
    (repo / "f.c").write_text("\n".join(old) + "\n")
    git(repo, "add", "."); git(repo, "commit", "-q", "-m", "c1")
    c1 = git(repo, "rev-parse", "HEAD")
    new = (old[10:12] + ["#include <a.h>", "#include <b.h>", ""] + old[:4]
           + ["int inserted_function(void) { return 99; }"] + old[4:7]
           + ["int THETA_function(void) { return 0; }"] + old[8:10] + old[14:])
    (repo / "f.c").write_text("\n".join(new) + "\n")
    git(repo, "commit", "-q", "-am", "c2: move two up, shift, insert one, rewrite one, delete two")
    return {"repo": str(repo), "c1": c1, "head": git(repo, "rev-parse", "HEAD")}


def build_remap_handbook(base: Path, cite: str) -> Path:
    root = base / "rhandbook"
    if root.exists():
        shutil.rmtree(root)
    (root / "software" / "foo").mkdir(parents=True)
    (root / "software" / "foo" / "project.yaml").write_text(
        "schema_version: 2\nname: foo\nrepository: https://github.com/org/rrepo.git\n"
    )
    (root / "software" / "foo" / "leaf.md").write_text(textwrap.dedent(f"""\
        ---
        title: t
        summary: s
        scope: [software:foo]
        load_when: always
        evidence: source
        sources:
          - https://github.com/org/rrepo/blob/{cite}/f.c#L1-L2
          - https://github.com/org/rrepo/blob/{cite}/f.c#L4-L6
          - https://github.com/org/rrepo/blob/{cite}/f.c#L7-L9
          - https://github.com/org/rrepo/blob/{cite}/f.c#L10
          - https://github.com/org/rrepo/blob/{cite}/f.c#L11-L12
          - https://github.com/org/rrepo/blob/{cite}/f.c#L13-L14
        observed: "2026-01-01"
        observed_on:
          software:
            foo:
              commit: {cite}
              branch: main
        ---
        body
        """))
    return root


class SuggestRemapTests(PerturbationMixin, unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is not installed -- this check DID NOT RUN")
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.repo = build_remap_repo(self.base)
        self.root = build_remap_handbook(self.base, self.repo["c1"])

    def run_tool(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [interpreter_for("yaml"), str(TOOL), "--root", str(self.root),
             "--checkout", f"foo={self.repo['repo']}", *extra],
            capture_output=True, text=True, check=False,
        )

    def remaps(self, *extra: str) -> dict[str, dict | None]:
        done = self.run_tool("--json", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        report = {leaf["leaf"]: leaf for leaf in payload["leaves"]}["software/foo/leaf.md"]
        return {f["source"].split("#")[-1]: f["remap"] for f in report["findings"]}

    def test_a_shifted_range_is_proposed_at_its_new_numbers(self):
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L1-L2"]["status"], "moved")
        self.assertEqual(r["L1-L2"]["lines"], [6, 7])
        self.assertIn("+5", r["L1-L2"]["detail"])

    def test_an_insertion_inside_the_range_is_proposed_across_it_and_says_so(self):
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L4-L6"]["status"], "split")
        self.assertEqual(r["L4-L6"]["lines"], [9, 12])
        self.assertIn("1 line(s) were inserted", r["L4-L6"]["detail"])

    def test_a_partly_rewritten_range_is_proposed_between_its_survivors_and_says_so(self):
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L7-L9"]["status"], "partial")
        self.assertEqual(r["L7-L9"]["lines"], [13, 15])
        self.assertIn("2 of 3", r["L7-L9"]["detail"])
        self.assertIn("re-read", r["L7-L9"]["detail"])

    def test_a_range_deleted_in_place_whose_text_survives_once_elsewhere_is_proposed_there(self):
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L11-L12"]["status"], "elsewhere")
        self.assertEqual(r["L11-L12"]["lines"], [1, 2])
        self.assertIn("read the code around that copy", r["L11-L12"]["detail"])

    def test_a_deleted_range_and_a_bare_brace_get_no_proposal(self):
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L13-L14"]["status"], "unresolved")
        self.assertNotIn("lines", r["L13-L14"])
        self.assertEqual(r["L10"]["status"], "unresolved")
        self.assertNotIn("lines", r["L10"])
        self.assertIn("distinctive", r["L10"]["detail"])

    def test_without_the_flag_nothing_is_proposed_and_the_summary_says_so_with_it(self):
        for remap in self.remaps().values():
            self.assertIsNone(remap)
        done = self.run_tool("--suggest-remap")
        last = done.stdout.strip().splitlines()[-1]
        self.assertIn("re-cite proposed for 4 line citations, refused for 2", last)
        self.assertIn("claims NOT judged", last)
        self.assertIn("remap -> #L6-L7  (moved", done.stdout)
        self.assertIn("remap: unresolved", done.stdout)

    def test_control_the_proposal_depends_on_the_alignment_offset(self):
        """Map every surviving line to its own old number and the shifted range must be
        reported unmoved at L1-L2, not moved to L6-L7."""
        self.perturb(TOOL, "mapping[i] = new_start + k + 1", "mapping[i] = i")
        r = self.remaps("--suggest-remap")
        self.assertEqual(r["L1-L2"]["status"], "unmoved")
        self.assertEqual(r["L1-L2"]["lines"], [1, 2])


if __name__ == "__main__":
    unittest.main()
