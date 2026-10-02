#!/usr/bin/env python3
"""milc-compare-fnal-correlators.py must pass matching files and fail each structural defect
the ks_spectrum guide names, and every negative test must first prove its perturbation
changed something. The fixture files are synthetic, written here."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "milc-compare-fnal-correlators.py"
NT = 8
ARGS = ["--nt", str(NT), "--job-id", "TestRun", "--lattice", "4,4,4,8"]


def fnal_text(scale: float = 1.0, keys=("PION_5_p000", "RHO_i_p000")) -> str:
    """A small FNAL-format file: one metadata block, then one block per correlator."""
    out = ["---", "JobID:                        TestRun",
           'date:                         "synthetic"',
           "lattice_size:                 4,4,4,8", "..."]
    for n, key in enumerate(keys):
        out += ["---", f"correlator:                   {key}",
                f"correlator_key:               {key}", "..."]
        for t in range(NT):
            out.append(f"{t}\t{scale * (n + 1) * 0.5 ** t:.6e}\t{0.0:.6e}")
    return "\n".join(out) + "\n"


class CompareCorrelatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.ref = self.dir / "ref.corr"
        self.ref.write_text(fnal_text())

    def run_tool(self, *files: Path, extra=()):
        return subprocess.run([interpreter_for(), str(TOOL), *ARGS, *extra, *map(str, files)],
                              text=True, capture_output=True, check=False)

    def perturbed(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_text(text)
        self.assertNotEqual(path.read_text(), self.ref.read_text(), "vacuous perturbation")
        return path

    def test_identical_files_pass_and_report_zero_difference(self):
        copy = self.dir / "copy.corr"
        copy.write_text(self.ref.read_text())
        result = self.run_tool(self.ref, copy)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("largest |difference| / correlator scale = 0.000e+00", result.stdout)
        self.assertIn("milc-compare-fnal-correlators 1.1.0", result.stdout)

    def test_a_difference_is_reported_and_judged_only_against_a_given_limit(self):
        other = self.perturbed("other.corr", fnal_text(scale=1.0 + 2e-5))
        reported = self.run_tool(self.ref, other)
        self.assertEqual(reported.returncode, 0, reported.stdout)
        self.assertIn("2.000e-05", reported.stdout)
        judged = self.run_tool(self.ref, other, extra=["--max-relative-difference", "1e-5"])
        self.assertEqual(judged.returncode, 1, judged.stdout)
        self.assertIn("EXCEEDS", judged.stdout)
        within = self.run_tool(self.ref, other, extra=["--max-relative-difference", "1e-4"])
        self.assertEqual(within.returncode, 0, within.stdout)

    def test_each_structural_defect_fails(self):
        text = self.ref.read_text()
        lines = text.splitlines(keepends=True)
        first_t3 = next(i for i, ln in enumerate(lines) if ln.startswith("3\t"))
        cases = {
            "dropped_row": ("".join(lines[:first_t3] + lines[first_t3 + 1:]), "rows with time indices"),
            "stale_append": (text + text, "appears twice"),
            "wrong_job_id": (text.replace("TestRun", "OtherRun"), "JobID"),
            "wrong_lattice": (text.replace("4,4,4,8", "4,4,4,16"), "lattice_size"),
            "non_finite": (text.replace("1.250000e-01", "nan", 1), "non-finite"),
            "empty": ("---\nJobID: TestRun\nlattice_size: 4,4,4,8\n...\n", "no correlator records"),
        }
        for name, (bad, needle) in cases.items():
            with self.subTest(defect=name):
                path = self.perturbed(f"{name}.corr", bad)
                result = self.run_tool(path)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(needle, result.stdout)

    def test_a_missing_or_extra_correlator_fails_the_comparison(self):
        fewer = self.perturbed("fewer.corr", fnal_text(keys=("PION_5_p000",)))
        result = self.run_tool(self.ref, fewer)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("key set differs", result.stdout)

    def run_ids(self, ids, *files: Path):
        args = ["--nt", str(NT), "--job-id", *ids, "--lattice", "4,4,4,8", *map(str, files)]
        return subprocess.run([interpreter_for(), str(TOOL), *args],
                              text=True, capture_output=True, check=False)

    def test_one_job_id_per_file_compares_runs_with_different_job_ids(self):
        # A tested run and its reference are separate jobs with separate JobIDs.
        other = self.perturbed("other.corr", fnal_text().replace("TestRun", "RefRun"))
        single = self.run_ids(["TestRun"], self.ref, other)
        self.assertEqual(single.returncode, 1, single.stdout)
        self.assertIn("metadata JobID 'RefRun', expected 'TestRun'", single.stdout)
        paired = self.run_ids(["TestRun", "RefRun"], self.ref, other)
        self.assertEqual(paired.returncode, 0, paired.stdout)
        self.assertIn("largest |difference| / correlator scale = 0.000e+00", paired.stdout)

    def test_per_file_job_ids_are_checked_in_file_order(self):
        other = self.perturbed("other.corr", fnal_text().replace("TestRun", "RefRun"))
        swapped = self.run_ids(["RefRun", "TestRun"], self.ref, other)
        self.assertEqual(swapped.returncode, 1, swapped.stdout)
        self.assertEqual(swapped.stdout.count("PROBLEM metadata JobID"), 2)

    def test_a_job_id_count_that_matches_neither_form_is_a_usage_error(self):
        copy = self.dir / "copy.corr"
        copy.write_text(self.ref.read_text())
        result = self.run_ids(["TestRun", "TestRun"], self.ref, copy, copy)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("one value or one per file", result.stderr)

    def test_an_unreadable_file_is_a_usage_error_not_a_pass(self):
        result = self.run_tool(self.ref, self.dir / "absent.corr")
        self.assertEqual(result.returncode, 2, result.stdout)


if __name__ == "__main__":
    unittest.main()
