#!/usr/bin/env python3
"""The dry-run harness must present the scheduler's environment, confine its stand-ins,
refuse vacuous perturbations, and write a receipt the guard can read."""
from __future__ import annotations

import importlib.util
import json
import shutil
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


# A script that checks a module-provided variable the way a library preflight does: absent
# before its own `module reset`, present after it.
MODULE_ENV_RECIPE = """here=$(pwd -P)
[ -z "${{SITE_LIB_PATH:-}}" ] || {{ echo "FATAL: set before module reset"; exit 1; }}
module reset
[ "${{SITE_LIB_PATH:-}}" = "/opt/site lib" ] || {{ echo "FATAL: libraries unresolved"; exit 1; }}
modules=$(module -t list 2>&1)
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

    def write_module_env_script(self) -> Path:
        script = self.jobdir / "job.sbatch"
        script.write_text((HEAD + MODULE_ENV_RECIPE).format(jobdir=self.jobdir))
        return script

    def test_module_env_is_exported_by_module_reset_not_before(self):
        script = self.write_module_env_script()
        result = self.run_harness(script, "--module-env", "SITE_LIB_PATH=/opt/site lib")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("module env at reset/load: SITE_LIB_PATH", result.stdout)
        self.assertEqual(self.receipt(script)["positive"]["module_env"], ["SITE_LIB_PATH"])

    def test_without_module_env_the_library_preflight_fails(self):
        # The gap this option closes: an executable module stub cannot change the script's
        # environment, so the preflight fails although the machine would pass it.
        script = self.write_module_env_script()
        result = self.run_harness(script)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("libraries unresolved", result.stdout)

    def test_env_is_not_a_substitute_for_module_env(self):
        # --env sets the value before the script's own reset, which the machine never does.
        script = self.write_module_env_script()
        result = self.run_harness(script, "--env", "SITE_LIB_PATH=/opt/site lib")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("set before module reset", result.stdout)

    def test_module_env_may_not_set_path(self):
        script = self.write_module_env_script()
        result = self.run_harness(script, "--module-env", "PATH=/usr/local/bin")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("may not set PATH", result.stdout)
        self.assertFalse(script.with_name(script.name + ".dry-run-receipt.json").exists())

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

    def test_sandbox_placeholders_in_the_job_directory_are_not_copied(self):
        """An agent sandbox leaves unreadable tooling placeholders where its shell stands."""
        script = self.write_script(PWD_RECIPE)
        placeholder_file = self.jobdir / ".mcp.json"
        placeholder_dir = self.jobdir / ".claude"
        placeholder_file.write_text("")
        (placeholder_dir / "hooks").mkdir(parents=True)
        placeholder_file.chmod(0)
        (placeholder_dir / "hooks").chmod(0)
        self.addCleanup(placeholder_file.chmod, 0o600)
        self.addCleanup((placeholder_dir / "hooks").chmod, 0o700)
        result = self.run_harness(script, "--no-receipt", "--keep")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
        kept = [line.split(":", 1)[1].strip() for line in result.stdout.splitlines()
                if line.startswith("sandbox kept:")]
        self.assertEqual(len(kept), 1, result.stdout)
        copied = Path(kept[0]) / "job"
        self.addCleanup(shutil.rmtree, kept[0], True)
        self.assertTrue((copied / "job.sbatch").is_file())
        self.assertFalse((copied / ".mcp.json").exists())
        self.assertFalse((copied / ".claude").exists())

    def test_runner_selects_a_usable_interpreter(self):
        script = self.write_script(PWD_RECIPE)
        result = subprocess.run(
            ["/bin/bash", str(RUNNER), str(script), "--machine", "perlmutter",
             "--rewrite-root", f"{self.scratch_root}=scratch", "--stand-in", f"{self.gauge}:4096",
             "--no-receipt"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            env=self.env, cwd=self.temp.name)
        self.assertEqual(result.returncode, 0, result.stdout)


# Vista-style launch: two legs through the site launcher and a placement guard that reads
# the launched program's output, as validation rigs on that machine do.
SITE_LAUNCH = """here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
hosts=$(ibrun ./rank-info | grep -c '^host=') || hosts=0
[ "$hosts" = 2 ] || {{ echo "FATAL: placement is not 2 hosts ($hosts)"; exit 1; }}
ibrun ./app inputs/job.in
echo "job ${{SLURM_JOB_ID}} done"
"""
PLACEMENT = "host=node-a\nhost=node-b\n"


class SiteLauncherTests(unittest.TestCase):
    """A machine profile's `scheduler.site_launcher` is stubbed on its own terms."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.jobdir = base / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        self.env = dict(os.environ, TMPDIR=str(base / "tmp"))
        (base / "tmp").mkdir()

    def write_site_script(self) -> Path:
        script = self.jobdir / "job.sbatch"
        script.write_text((HEAD + SITE_LAUNCH).format(jobdir=self.jobdir))
        return script

    def run_vista(self, script: Path, *extra: str):
        argv = [interpreter_for("yaml"), str(HARNESS), str(script), "--machine", "vista", *extra]
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              check=False, env=self.env, cwd=self.temp.name)

    def test_second_site_launcher_step_is_refused_without_sequential_steps(self):
        # overlap_option is null: a call can never share the allocation with an earlier step.
        result = self.run_vista(self.write_site_script(), "--no-receipt",
                                "--launcher-output", PLACEMENT)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[stub ibrun] STEP CREATION REFUSED: 1 step(s)", result.stdout)
        self.assertIn("cannot share it", result.stdout)

    def test_sequential_site_launcher_steps_pass_and_are_logged(self):
        result = self.run_vista(self.write_site_script(), "--no-receipt",
                                "--launcher-output", PLACEMENT, "--allow-sequential-steps")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
        self.assertIn("launcher steps created: 2", result.stdout)
        self.assertIn("1. ibrun ./rank-info", result.stdout)

    def test_placement_guard_fires_on_one_host(self):
        # The passing legs above need both lines to arrive as two lines; an inline shell
        # literal once delivered them as one. Here one host must make the guard fire.
        result = self.run_vista(self.write_site_script(), "--no-receipt",
                                "--launcher-output", "host=node-a host=node-b\n",
                                "--allow-sequential-steps")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("placement is not 2 hosts (1)", result.stdout)

    def test_site_launcher_is_not_stubbed_where_the_profile_records_none(self):
        # The harness PATH is its stub directory plus /usr/bin:/bin, so a site's real
        # launcher elsewhere cannot be reached from here.
        script = self.write_site_script()
        argv = [interpreter_for("yaml"), str(HARNESS), str(script), "--machine", "perlmutter",
                "--no-receipt", "--launcher-output", PLACEMENT, "--allow-sequential-steps"]
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                check=False, env=self.env, cwd=self.temp.name)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn("[stub ibrun]", result.stdout)
        self.assertIn("placement is not 2 hosts (0)", result.stdout)

    def test_site_launcher_may_not_replace_the_parallel_launcher_stub(self):
        spec = importlib.util.spec_from_file_location("dry_run_site", HARNESS)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        args = module.parse_args([str(self.jobdir / "x.sbatch"), "--machine", "vista"])
        bin_dir = Path(self.temp.name) / "bin"
        bin_dir.mkdir()
        with self.assertRaises(module.Refusal):
            module.write_stubs(bin_dir, {"parallel_launcher": "srun"}, set(), args,
                               {"command": "srun", "overlap_option": None})


# Legs independent, as diagnostic rigs are written: a failed launch is recorded and the script
# carries on, so it exits 0 past a refused step. The exit code alone cannot show the refusal.
TOLERANT_LAUNCH = """set +e
here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || {{ echo "FATAL: $here is not the job directory"; exit 1; }}
grep -q "^mass 0.1$" inputs/job.in || {{ echo "FATAL: input changed"; exit 1; }}
for leg in a b; do
  ibrun ./app "$leg" || echo "leg $leg failed; continuing"
done
echo "job ${{SLURM_JOB_ID}} done"
"""


class StepRefusalTests(unittest.TestCase):
    """A refused launcher step fails the run even when the script exits 0."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.jobdir = base / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        self.env = dict(os.environ, TMPDIR=str(base / "tmp"))
        (base / "tmp").mkdir()
        self.script = self.jobdir / "job.sbatch"
        self.script.write_text((HEAD + TOLERANT_LAUNCH).format(jobdir=self.jobdir))

    def run_vista(self, *extra: str):
        argv = [interpreter_for("yaml"), str(HARNESS), str(self.script), "--machine", "vista",
                *extra]
        return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              check=False, env=self.env, cwd=self.temp.name)

    def receipt(self) -> dict:
        return json.loads(self.script.with_name(self.script.name + ".dry-run-receipt.json").read_text())

    def test_refused_step_fails_the_positive_control_although_the_script_exits_zero(self):
        result = self.run_vista()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("exit code: 0", result.stdout)
        self.assertIn("launcher steps refused: 1", result.stdout)
        self.assertIn("POSITIVE CONTROL FAILED: 1 launcher step(s) were refused", result.stdout)
        positive = self.receipt()["positive"]
        self.assertFalse(positive["passed"])
        self.assertEqual(positive["step_refusals"], 1)

    def test_sequential_steps_pass_when_declared(self):
        result = self.run_vista("--allow-sequential-steps")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("launcher steps refused: 0", result.stdout)
        self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
        self.assertEqual(self.receipt()["positive"]["step_refusals"], 0)

    def test_negative_run_with_a_refused_step_is_not_counted_as_fired(self):
        # The input guard fires, but the launch path was never exercised as submitted.
        result = self.run_vista("--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("NEGATIVE TEST PASSED", result.stdout)  # guard fired before any launch
        # Here the run exits non-zero AFTER a refused step: the old verdict counted that as the
        # guard firing, though the exit came from a script whose launch never ran as submitted.
        result = self.run_vista("--negative", "job.sbatch", 's/^echo "job .* done"$/exit 3/')
        self.assertIn("exit code: 3", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("NEGATIVE TEST FAILED: 1 launcher step(s) were refused", result.stdout)
        self.assertFalse(self.receipt()["negatives"][-1]["fired"])


if __name__ == "__main__":
    unittest.main()
