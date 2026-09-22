"""Source claims in the staggered tools cite a permalink, not a bare file:line.

A bare `coarse_op.cuh:1217` citation goes stale in silence: between the revision these tools
model and the build the campaigns run, the two rules in that file moved by 50 and 56 lines.
A drifted citation reads exactly like a missing one, and a missing one has real cost -- the
KD per-axis even rule shipped uncited and was twice searched for in QUDA, missed, and
reported as having no source.

These tests pin the convention rather than the prose: every QUDA link in either tool is
pinned to a full 40-character commit, never to a branch, and the rules that have already
been mis-dismissed are cited by name.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "tools/quda_staggered_geometry.py"
MEMORY = ROOT / "tools/quda-staggered-memory.py"

# The revision both tools declare they reproduce.
SOURCE_COMMIT = "b6998853f6b605e22d67ea2ddfa3cab0d752679a"
BLOB = re.compile(r"https://github\.com/lattice/quda/blob/([^/]+)/(\S+?)(?:#L\d+(?:-L\d+)?)?\s")


class SourceCitationTests(unittest.TestCase):
    def test_every_quda_link_is_pinned_to_a_full_commit(self):
        """A branch or short hash in a permalink defeats the point of having one."""
        for tool in (GEOMETRY, MEMORY):
            with self.subTest(tool.name):
                links = BLOB.findall(tool.read_text() + "\n")
                self.assertTrue(links, "no QUDA source links found")
                for ref, path in links:
                    self.assertRegex(
                        ref, r"^[0-9a-f]{40}$",
                        f"{tool.name} cites {path} at '{ref}', which is not a full commit",
                    )

    def test_the_tools_cite_the_revision_they_model(self):
        for tool in (GEOMETRY, MEMORY):
            with self.subTest(tool.name):
                for ref, path in BLOB.findall(tool.read_text() + "\n"):
                    self.assertEqual(
                        ref, SOURCE_COMMIT,
                        f"{tool.name} cites {path} at a revision it does not model",
                    )

    def test_the_kd_even_rule_is_cited_in_both_tools(self):
        """The rule that was twice reported as spurious. It is real; keep it findable."""
        expected = (
            f"https://github.com/lattice/quda/blob/{SOURCE_COMMIT}"
            "/lib/coarse_op.cuh#L1022-L1026"
        )
        for tool in (GEOMETRY, MEMORY):
            with self.subTest(tool.name):
                self.assertIn(expected, tool.read_text())

    def test_no_bare_file_line_citation_survives_for_the_moved_rules(self):
        """coarse_op.cuh line numbers drift; a bare one must not be left behind."""
        for tool in (GEOMETRY, MEMORY):
            with self.subTest(tool.name):
                text = tool.read_text()
                for stale in ("coarse_op.cuh:1217", "coarse_op.cuh:1217-1220"):
                    self.assertNotIn(stale, text)

    def test_a_re_verification_against_the_built_revision_is_recorded(self):
        """The modelled revision is not the one the campaigns run; say when they last agreed."""
        for tool in (GEOMETRY, MEMORY):
            with self.subTest(tool.name):
                self.assertIn(
                    "00c7ef33dacadfb94860e3ca1cc06862926182dc", tool.read_text()
                )


if __name__ == "__main__":
    unittest.main()
