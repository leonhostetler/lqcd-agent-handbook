#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check-batch-script.py"
RUNNER = ROOT / "tools" / "run-batch-script-check"

# Fixtures are synthetic. Real batch scripts in a working project carry allocation
# codes and contact addresses, which must not enter this repository.
CLEAN = """#!/usr/bin/env bash
#SBATCH -A PLACEHOLDER_ACCOUNT
#SBATCH --chdir=/declared/run/root
#SBATCH --output=/declared/run/root/job.out
#SBATCH -N 1
set -euo pipefail

srun ./application input.in
"""


class BatchScriptCheckerTests(unittest.TestCase):
    def run_checker(self, body: str, *arguments: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "job.sbatch"
            script.write_text(body)
            return subprocess.run(
                [sys.executable, str(CHECKER), str(script), *arguments],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

    def test_clean_script_passes(self):
        result = self.run_checker(CLEAN, "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 errors", result.stdout)

    def test_short_form_account_is_recognised(self):
        """Both real batch scripts in the source project use -A, never --account."""
        result = self.run_checker(CLEAN, "--machine", "perlmutter")
        self.assertNotIn("no account directive", result.stdout)

    def test_missing_account_is_an_error(self):
        body = CLEAN.replace("#SBATCH -A PLACEHOLDER_ACCOUNT\n", "")
        result = self.run_checker(body, "--machine", "perlmutter")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no account directive", result.stdout)

    def test_nested_submission_is_an_error(self):
        result = self.run_checker(CLEAN + "sbatch followup.sbatch\n", "--machine", "perlmutter")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("submits another job", result.stdout)

    def test_destructive_removal_is_an_error(self):
        result = self.run_checker(CLEAN + 'rm -rf "$SOMEWHERE"\n', "--machine", "perlmutter")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("destructive operation", result.stdout)

    def test_comments_are_not_operations(self):
        result = self.run_checker(CLEAN + "# do not rm -rf the outputs\n", "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_hardening_warns_but_does_not_fail(self):
        body = CLEAN.replace("set -euo pipefail\n", "")
        result = self.run_checker(body, "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("set -euo pipefail", result.stdout)

    def test_unpinned_directives_warn(self):
        body = CLEAN.replace("#SBATCH --chdir=/declared/run/root\n", "")
        result = self.run_checker(body, "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("working directory not pinned", result.stdout)

    def test_account_value_is_never_printed(self):
        """A lint that echoes an allocation code breaches the rule it enforces."""
        body = CLEAN.replace("PLACEHOLDER_ACCOUNT", "SENTINELCODE")
        result = self.run_checker(body + "rm -f x\n", "--machine", "perlmutter")
        self.assertNotIn("SENTINELCODE", result.stdout)

    def test_status_line_names_what_was_not_checked(self):
        result = self.run_checker(CLEAN, "--machine", "perlmutter")
        self.assertIn("NOT performed", result.stdout)

    def test_driver_without_directives_warns_rather_than_fails(self):
        """A driver that runs from an allocation may call the allocator; it is not
        a batch script, and failing it is how a lint gets ignored."""
        body = "#!/usr/bin/env bash\nset -euo pipefail\nsalloc -N 1 ./inner.sh\n"
        result = self.run_checker(body, "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("does not look like a batch script", result.stdout)
        self.assertIn("submits another job", result.stdout)

    def test_process_substitution_is_not_a_file_write(self):
        """`exec > >(tee log)` is ordinary logging, not a truncating write."""
        result = self.run_checker(CLEAN + 'exec > >(tee "$LOG") 2>&1\n', "--machine", "perlmutter")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("truncating redirection", result.stdout)

    def test_directive_checks_are_skipped_without_a_machine(self):
        result = self.run_checker(CLEAN)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no --machine given", result.stdout)


class BatchScriptRunnerTests(unittest.TestCase):
    def test_runner_selects_a_usable_interpreter(self):
        """A bare `python3` on this fleet predates the checker's own syntax, so the
        documented entry point must go through the shared dispatcher."""
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "job.sbatch"
            script.write_text(CLEAN)
            result = subprocess.run(
                ["/bin/bash", str(RUNNER), str(script), "--machine", "perlmutter"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 errors", result.stdout)


if __name__ == "__main__":
    unittest.main()
