"""Corpus bands are scoped to the level count they were fitted at.

Every numerical band in tools/quda_staggered_geometry.py was fitted on four-level
hierarchies. The tool must decline to evaluate them at any other level count and must say
so in a machine-readable way, because an empty advisory list is otherwise indistinguishable
from a pass. See software/quda/solvers/staggered-multigrid.md#level-naming.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECOMPOSITION = ROOT / "tools/quda-staggered-decomposition.py"


def run_json(*args: str):
    result = subprocess.run(
        [sys.executable, str(DECOMPOSITION), *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


FOUR_LEVEL = [
    "--levels", "4",
    "--global", "64", "64", "64", "96",
    "--ranks", "2", "2", "2", "4",
    "--block1", "4", "4", "4", "4",
    "--block2", "2", "2", "2", "2",
    "--nvec1", "64", "--nvec2", "96",
]
THREE_LEVEL = [
    "--levels", "3",
    "--global", "64", "64", "64", "96",
    "--ranks", "2", "2", "2", "4",
    "--block1", "4", "4", "4", "6",
    "--nvec1", "64",
]


def screen(payload):
    return payload["empirical_screen"]


class LevelScopedAdvisoryTests(unittest.TestCase):
    def test_four_level_candidate_is_actually_evaluated(self):
        payload = run_json(*FOUR_LEVEL, "--nvec3", "4000", "--corpus-advisories")
        s = screen(payload)
        self.assertTrue(s["enabled"])
        self.assertTrue(s["evaluated"])
        self.assertEqual(s["fitted_levels"], 4)

    def test_three_level_candidate_is_refused_not_passed(self):
        """The regression guard for the whole change.

        Fails if the guard is ever narrowed back to the V3/aspect pair, which is how the
        nu3 band would silently escape to a level count it was never fitted at.
        """
        payload = run_json(*THREE_LEVEL, "--nvec2", "1024", "--corpus-advisories")
        s = screen(payload)
        self.assertFalse(s["evaluated"], "a three-level hierarchy must not read as screened")
        self.assertEqual(len(s["advisories"]), 1, s["advisories"])
        self.assertIn("not evaluated", s["advisories"][0])
        self.assertIn("fitted at 4 levels", s["advisories"][0])

    def test_density_outside_the_fitted_envelope_is_flagged(self):
        # nu3 well below CORPUS_NU3_MIN: the coarse-spectrum law is an extrapolation here.
        payload = run_json(*FOUR_LEVEL, "--nvec3", "8", "--corpus-advisories")
        s = screen(payload)
        self.assertTrue(s["evaluated"])
        self.assertTrue(
            any("outside the fitted spectrum envelope" in a for a in s["advisories"]),
            s["advisories"],
        )

    def test_screens_off_reports_nothing_as_evaluated(self):
        payload = run_json(*FOUR_LEVEL, "--nvec3", "4000")
        s = screen(payload)
        self.assertFalse(s["enabled"])
        self.assertFalse(s["evaluated"])
        self.assertIsNone(s["V3_min"])
        self.assertIsNone(s["nu3_envelope"])
        self.assertEqual(s["advisories"], [])


if __name__ == "__main__":
    unittest.main()
