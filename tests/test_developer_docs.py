"""The developer-mode load is budgeted, and a changed decision is rewritten, not amended.

Both rules are ARCHITECTURE.md §what-this-document-is. They are enforced here because a
document convention that nothing checks is the class of rule this repository already
records as not firing -- see conventions/repeated-work.md.

The budget itself lives in the validator, beside the Tier-0 budget it mirrors. What this
file adds is the pair of controls proving that budget can fail, plus the amendment-marker
convention, which is a word-level check of the same kind as test_reserved_terms.py.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import PerturbationMixin, interpreter_for  # noqa: E402

HANDBOOK = ROOT / "handbook.yaml"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"
ROADMAP = ROOT / "ROADMAP.md"
VALIDATOR = ROOT / "tools/validate-knowledge.py"

# A paragraph announcing a dated amendment, in the two forms this repository actually
# used before they were removed: a bold lead-in, and an inline parenthetical.
AMENDMENT_RE = re.compile(
    r"(?:\*\*|^)(?:Amended|Narrowed|Revised|Superseded)\b[^\n]{0,80}?\d{4}-\d{2}-\d{2}"
    r"|\((?:amended|narrowed|revised|superseded)\s+\d{4}-\d{2}-\d{2}\)",
    re.MULTILINE,
)

# Verbatim from what this repository carried until it was rewritten. A regex written
# against invented text can silently match nothing; these two are the real forms.
HISTORICAL_FORMS = (
    "**Amended 2026-09-16: an aggregation can be *worse* than absent, and that raises the",
    "after the pointer alone was observed not to fire (amended 2026-08-29)",
)


def run_validator() -> subprocess.CompletedProcess:
    return subprocess.run(
        [interpreter_for("yaml", "jsonschema"), str(VALIDATOR)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class DeveloperDocBudget(PerturbationMixin, unittest.TestCase):
    def test_budget_is_respected(self):
        result = run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("dev docs ", result.stdout)

    def test_summary_still_names_what_it_did_not_check(self):
        """The budget field must not push the disclaimer out of the reported summary."""
        result = run_validator()
        self.assertIn("publishability NOT checked", result.stdout)
        summary = [ln for ln in result.stdout.splitlines() if "dev docs " in ln][-1]
        self.assertIn("publishability NOT checked", summary[:400])

    def test_a_lowered_cap_is_caught(self):
        """Control: the budget must be able to fail."""
        self.perturb(HANDBOOK, "max_combined_bytes: 200000", "max_combined_bytes: 1000")
        result = run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertRegex(result.stdout, r"developer documents are \d+ bytes; limit is 1000")
        # The remedy is named, so a session hitting the cap moves episodes out rather
        # than raising the number -- which is what a bare limit invites.
        self.assertIn("Move episode material to DEVLOG.md", result.stdout)

    def test_listing_the_episode_record_is_caught(self):
        """Control: the split cannot be undone by adding DEVLOG.md to the loaded set."""
        self.perturb(
            HANDBOOK,
            "    - ROADMAP.md\n",
            "    - ROADMAP.md\n    - DEVLOG.md\n",
        )
        result = run_validator()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("must not list the episode record", result.stdout)


class AmendmentsAreRewrittenNotStacked(PerturbationMixin, unittest.TestCase):
    def test_no_dated_amendment_marker(self):
        for path in (ARCHITECTURE, ROADMAP):
            with self.subTest(path=path.name):
                found = AMENDMENT_RE.findall(path.read_text())
                self.assertEqual(
                    found,
                    [],
                    f"{path.name} carries a dated amendment. Rewrite the rule in place and "
                    f"record the change in DEVLOG.md -- ARCHITECTURE.md "
                    f"§what-this-document-is:\n  " + "\n  ".join(found),
                )

    def test_the_pattern_matches_the_forms_that_actually_occurred(self):
        """Vacuity guard: a pattern that matches nothing would pass the check above."""
        for sample in HISTORICAL_FORMS:
            with self.subTest(sample=sample[:40]):
                self.assertTrue(
                    AMENDMENT_RE.search(sample),
                    "pattern does not match a form this repository really used",
                )

    def test_a_planted_amendment_is_caught(self):
        """Control: the guard must fire on a new one."""
        self.perturb(
            ARCHITECTURE,
            "## 0. What this document is\n",
            "## 0. What this document is\n\n**Amended 2026-01-01: a planted marker.**\n",
        )
        self.assertTrue(AMENDMENT_RE.search(ARCHITECTURE.read_text()))


if __name__ == "__main__":
    unittest.main()
