"""A hierarchy quantity is named by its role, never by a level index.

ARCHITECTURE.md 5.4. The coarsest grid is level 3 in a four-level hierarchy and level 2 in
a three-level one, so `V3`, `nu3`, `nvec_3` and `l3_res_max` name a DIFFERENT grid
depending on a fact the symbol does not carry. They are banned from staggered guidance.

The single allowed home is the overview's crosswalk and its #level-naming section, where
the numbered forms are the subject rather than the vocabulary.
"""

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
ALLOWED = {"software/quda/solvers/staggered-multigrid.md"}
BANNED = re.compile(r"\b(V3|nu3|V2|nvec_3|l3_res_max|V3_global|V2_global)\b")
ROLE_NAMES = (
    "coarsest_global_volume",
    "coarsest_vector_density",
    "coarsest_deflation_count",
    "coarsest_res_max",
)
SCOPES = ("software/quda/solvers", "software/quda/internals", "playbooks")


def staggered_docs():
    for scope in SCOPES:
        for f in sorted((ROOT / scope).rglob("*.md")):
            yield f


class RoleNotIndexTests(unittest.TestCase):
    def test_no_index_named_hierarchy_quantities_in_guidance(self):
        offenders = []
        for f in staggered_docs():
            rel = str(f.relative_to(ROOT))
            if rel in ALLOWED:
                continue
            text = f.read_text()
            for m in BANNED.finditer(text):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line}: {m.group(1)}")
        self.assertEqual(
            offenders,
            [],
            "Index-named hierarchy quantities found. Use the role name "
            f"({', '.join(ROLE_NAMES)}) — see ARCHITECTURE.md 5.4:\n"
            + "\n".join(offenders),
        )

    def test_the_role_names_are_actually_in_use(self):
        """Guards the lazy fix: deleting the symbols instead of renaming them."""
        corpus = "\n".join(
            f.read_text() for f in staggered_docs()
        )
        for name in ROLE_NAMES:
            self.assertIn(name, corpus, f"role name {name} is not used anywhere")

    def test_architecture_states_the_rule_and_names_this_test(self):
        arch = (ROOT / "ARCHITECTURE.md").read_text()
        self.assertIn('<a id="role-not-index"></a>', arch)
        self.assertIn("tests/test_role_not_index.py", arch)

    def test_the_level_naming_anchor_the_leaves_cite_exists(self):
        overview = (ROOT / "software/quda/solvers/staggered-multigrid.md").read_text()
        self.assertIn('<a id="level-naming"></a>', overview)
        citing = [
            f for f in staggered_docs() if "#level-naming" in f.read_text()
        ]
        self.assertGreaterEqual(
            len(citing), 3, "leaves should cite the anchor rather than restate the rule"
        )


if __name__ == "__main__":
    unittest.main()
