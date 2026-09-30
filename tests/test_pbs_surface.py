#!/usr/bin/env python3
"""The PBS surface must reach every batch-script tool: the checker reads its null options
without inventing them, the dry-run harness starts an unpinned job where PBS does, and the
submission guard intercepts qsub, including the interactive form it cannot check."""
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
CHECKER = ROOT / "tools" / "check-batch-script.py"
HARNESS = ROOT / "tools" / "dry-run-batch-script.py"
GUARD = ROOT / "tools" / "submission-guard.py"

# Synthetic fixtures: no project name, no address, no site path.
HEAD = """#!/usr/bin/env bash
#PBS -A <project>
#PBS -q debug
#PBS -l select=1
#PBS -l walltime=00:05:00
#PBS -l filesystems=home
#PBS -o {jobdir}/job.out
#PBS -j oe
set -euo pipefail
"""

CD_RECIPE = """cd {jobdir}
here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
"""

# Relies on the start directory, which under PBS is the home directory.
START_DIR_RECIPE = """here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
"""

# The common PBS idiom: correct only when qsub runs in the job directory itself.
SUBMIT_DIR_RECIPE = """cd "$PBS_O_WORKDIR"
here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
"""

TAIL = """grep -q "^mass 0.1$" inputs/job.in || {{ echo "FATAL: input changed"; exit 1; }}
mpiexec -n 1 -ppn 1 ./app inputs/job.in > leg1.out &
first=$!
mpiexec -n 1 -ppn 1 ./app inputs/job.in > leg2.out &
second=$!
wait "$first"; wait "$second"
qstat -f "$PBS_JOBID" > job-record.txt || true
echo "job $PBS_JOBID done"
"""


class PbsCheckerTests(unittest.TestCase):
    def run_checker(self, body: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "job.pbs"
            script.write_text(body.format(jobdir="/declared/run/root"))
            return subprocess.run(
                [interpreter_for("yaml"), str(CHECKER), str(script), "--machine", "aurora"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    def test_script_that_changes_to_its_job_directory_is_clean(self):
        result = self.run_checker(HEAD + CD_RECIPE + TAIL)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 errors", result.stdout)
        # A null option is never reported as unpinned: PBS has nothing to pin it with.
        self.assertNotIn("working directory not pinned", result.stdout)
        self.assertNotIn("None", result.stdout)
        self.assertNotIn("no working-directory directive", result.stdout)

    def test_relying_on_the_start_directory_warns_and_names_home(self):
        result = self.run_checker(HEAD + START_DIR_RECIPE + TAIL)
        self.assertIn("no working-directory directive", result.stdout)
        self.assertIn("home directory", result.stdout)

    def test_submit_dir_idiom_warns_without_suggesting_a_directive(self):
        result = self.run_checker(HEAD + SUBMIT_DIR_RECIPE + TAIL)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("$PBS_O_WORKDIR", result.stdout)
        self.assertIn("cannot pin one", result.stdout)

    def test_missing_project_is_an_error(self):
        body = HEAD.replace("#PBS -A <project>\n", "") + CD_RECIPE + TAIL
        result = self.run_checker(body)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no account directive", result.stdout)

    def test_nested_submission_is_one_error(self):
        result = self.run_checker(HEAD + CD_RECIPE + TAIL + "qsub followup.pbs\n")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(result.stdout.count("submits another job"), 1, result.stdout)


class PbsHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.jobdir = base / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        (base / "tmp").mkdir()
        self.env = dict(os.environ, TMPDIR=str(base / "tmp"))

    def write_script(self, recipe: str) -> Path:
        script = self.jobdir / "job.pbs"
        script.write_text((HEAD + recipe + TAIL).format(jobdir=self.jobdir))
        return script

    def run_harness(self, script: Path, *extra: str):
        argv = [interpreter_for("yaml"), str(HARNESS), str(script), "--machine", "aurora", *extra]
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              check=False, env=self.env, cwd=self.temp.name)

    def test_script_that_changes_directory_passes_with_concurrent_launches(self):
        result = self.run_harness(self.write_script(CD_RECIPE))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NOT pinned (the home directory)", result.stdout)
        self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
        # Two backgrounded PALS launches share the allocation: none may be refused.
        self.assertIn("launcher steps created: 2", result.stdout)
        self.assertIn("launcher steps refused: 0", result.stdout)
        self.assertIn("job 999999 done", result.stdout)

    def test_relying_on_the_start_directory_fails(self):
        result = self.run_harness(self.write_script(START_DIR_RECIPE))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("is not the job directory", result.stdout)
        self.assertIn("POSITIVE CONTROL FAILED", result.stdout)

    def test_submit_dir_idiom_fails_under_submission_by_absolute_path(self):
        result = self.run_harness(self.write_script(SUBMIT_DIR_RECIPE))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("is not the job directory", result.stdout)

    def test_negative_test_fires(self):
        script = self.write_script(CD_RECIPE)
        result = self.run_harness(script, "--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NEGATIVE TEST PASSED", result.stdout)


class PbsGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.jobdir = base / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        (base / "tmp").mkdir()
        self.env = dict(os.environ, TMPDIR=str(base / "tmp"))
        self.script = self.jobdir / "job.pbs"
        self.script.write_text((HEAD + CD_RECIPE + TAIL).format(jobdir=self.jobdir))
        self.python = interpreter_for("yaml")

    def guard(self, command: str, machine: str = "aurora"):
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": self.temp.name}
        return subprocess.run([self.python, str(GUARD), "--machine", machine],
                              input=json.dumps(event), text=True, capture_output=True, check=False)

    def dry_run(self, *extra: str):
        return subprocess.run([self.python, str(HARNESS), str(self.script), "--machine", "aurora",
                               *extra], text=True, capture_output=True, check=False,
                              env=self.env, cwd=self.temp.name)

    def test_qsub_without_a_receipt_is_refused(self):
        result = self.guard(f"qsub {self.script}")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no dry-run receipt", result.stderr)

    def test_qsub_with_a_passed_receipt_and_a_fired_negative_is_allowed(self):
        self.assertEqual(self.dry_run().returncode, 0)
        self.assertEqual(self.dry_run("--negative", "inputs/job.in",
                                      "s/^mass 0.1$/mass 0.2/").returncode, 0)
        result = self.guard(f"qsub -q debug {self.script}")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_interactive_qsub_is_refused_with_its_own_reason(self):
        result = self.guard("qsub -I -l select=1 -l walltime=00:30:00 -q debug")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("interactive allocation", result.stderr)

    def test_dash_capital_i_is_not_interactive_where_the_commands_differ(self):
        # To Slurm's submit command -I is --immediate; the script is still checked.
        result = self.guard(f"sbatch -I {self.script}", machine="perlmutter")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("interactive allocation", result.stderr)


if __name__ == "__main__":
    unittest.main()
