#!/usr/bin/env python3
"""The dry-run harness must present the scheduler's environment, confine its stand-ins,
refuse vacuous perturbations, and write a receipt the guard can read."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "dry-run-batch-script.py"
RUNNER = ROOT / "tools" / "run-dry-run-batch-script"

# Synthetic fixtures: no allocation code, no address, no site path.
HEAD = """#!/usr/bin/env bash
#SBATCH -A PLACEHOLDER_ACCOUNT
#SBATCH --chdir={jobdir}
#SBATCH --output={jobdir}/job.out
#SBATCH -N 1
set -euo pipefail
"""

# The recipe that killed a job after a two-day queue wait: resolves from the
# submission-directory variable, which is never the job directory under --chdir.
SUBMIT_DIR_RECIPE = """here=$(cd "${{SLURM_SUBMIT_DIR:-$(dirname "$0")}}" && pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
cd "$here"
"""

PWD_RECIPE = """here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
"""

TAIL = """[ -s "{gauge}" ] || {{ echo "FATAL: gauge missing"; exit 1; }}
[ "$(stat -c %s "{gauge}")" -eq 4096 ] || {{ echo "FATAL: gauge size"; exit 1; }}
module load stubmod/1.0
modules=$(module -t list 2>&1)
case "$modules" in *stubmod/1.0*) : ;; *) echo "FATAL: module drift"; exit 1 ;; esac
grep -q "^mass 0.1$" inputs/job.in || {{ echo "FATAL: input changed"; exit 1; }}
srun -N 1 ./app inputs/job.in raw/application.out
echo "job ${{SLURM_JOB_ID}} done"
"""


class DryRunHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.jobdir = base / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        self.scratch_root = base / "scratch"  # a "site scratch" root the script names
        self.gauge = self.scratch_root / "lats" / "gauge.bin"
        self.env = dict(os.environ, TMPDIR=str(base / "tmp"))
        (base / "tmp").mkdir()

    def write_script(self, recipe: str) -> Path:
        script = self.jobdir / "job.sbatch"
        body = (HEAD + recipe + TAIL).format(jobdir=self.jobdir, gauge=self.gauge)
        script.write_text(body)
        return script

    def run_harness(self, script: Path, *extra: str, negative: bool = False):
        argv = [interpreter_for("yaml"), str(HARNESS), str(script), "--machine", "perlmutter",
                "--rewrite-root", f"{self.scratch_root}=scratch",
                "--stand-in", f"{self.gauge}:4096", *extra]
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              check=False, env=self.env, cwd=self.temp.name)

    def receipt(self, script: Path) -> dict:
        return json.loads(script.with_name(script.name + ".dry-run-receipt.json").read_text())

    def test_pwd_first_script_passes_positive_control(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
        self.assertIn("job 999999 done", result.stdout)
        self.assertTrue(self.receipt(script)["positive"]["passed"])

    def test_submit_dir_recipe_fails_under_the_machine_environment(self):
        """The failure that cost a two-day queue wait, reproduced on a login node."""
        script = self.write_script(SUBMIT_DIR_RECIPE)
        result = self.run_harness(script)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("is not the job directory", result.stdout)
        self.assertIn("POSITIVE CONTROL FAILED", result.stdout)
        self.assertFalse(self.receipt(script)["positive"]["passed"])

    def test_negative_test_fires_and_is_recorded(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script, "--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NEGATIVE TEST PASSED", result.stdout)
        negatives = self.receipt(script)["negatives"]
        self.assertEqual(len(negatives), 1)
        self.assertTrue(negatives[0]["fired"])

    def test_noop_perturbation_is_refused(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script, "--negative", "inputs/job.in", "s/^nothing$/x/")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("matched nothing", result.stdout)

    def test_omitted_stand_in_makes_the_absence_guard_fire(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script, "--omit-stand-in", str(self.gauge))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gauge missing", result.stdout)
        self.assertIn("NEGATIVE TEST PASSED", result.stdout)

    def test_short_stand_in_makes_the_size_guard_fire(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script, "--short-stand-in", str(self.gauge))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("gauge size", result.stdout)

    def test_module_drift_makes_the_module_guard_fire(self):
        script = self.write_script(PWD_RECIPE)
        result = self.run_harness(script, "--module-drift", "stubmod/1.0")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("module drift", result.stdout)

    def test_stand_in_outside_the_sandbox_is_refused_before_anything_runs(self):
        """An earlier harness created stand-ins wherever a declaration pointed."""
        script = self.write_script(PWD_RECIPE)
        stray = Path(self.temp.name) / "stray" / "file"
        for declared in (f"{stray}:10", "relative/file:10", "$ROOT/file:10"):
            with self.subTest(declared=declared):
                result = self.run_harness(script, "--stand-in", declared)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("HARNESS REFUSED", result.stdout)
                self.assertNotIn("POSITIVE CONTROL", result.stdout)
        self.assertFalse(stray.exists())
        self.assertFalse((Path(self.temp.name) / "relative").exists())

    def test_changed_script_starts_a_fresh_receipt(self):
        script = self.write_script(PWD_RECIPE)
        self.run_harness(script, "--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/")
        self.assertEqual(len(self.receipt(script)["negatives"]), 1)
        script.write_text(script.read_text() + "echo changed\n")
        self.run_harness(script)
        receipt = self.receipt(script)
        self.assertEqual(receipt["negatives"], [])
        self.assertTrue(receipt["positive"]["passed"])

    def test_real_job_directory_is_never_written(self):
        script = self.write_script(PWD_RECIPE)
        before = sorted(p.relative_to(self.jobdir) for p in self.jobdir.rglob("*"))
        self.run_harness(script, "--no-receipt")
        after = sorted(p.relative_to(self.jobdir) for p in self.jobdir.rglob("*"))
        self.assertEqual(before, after)

    def test_runner_selects_a_usable_interpreter(self):
        script = self.write_script(PWD_RECIPE)
        result = subprocess.run(
            ["/bin/bash", str(RUNNER), str(script), "--machine", "perlmutter",
             "--rewrite-root", f"{self.scratch_root}=scratch", "--stand-in", f"{self.gauge}:4096",
             "--no-receipt"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            env=self.env, cwd=self.temp.name)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
