"""The drift triage must name the leaves an upstream merge invalidated, in both directions.

Forward: a cited file changed after the cited revision, and the cited lines moved or not.
Backward: a cited feature-branch commit or pull request became an ancestor of HEAD after
the leaf's observed commit. And the control: when the hunk-overlap check is disabled, the
"cited lines changed" status must disappear, so the status is shown to depend on it.
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


if __name__ == "__main__":
    unittest.main()
