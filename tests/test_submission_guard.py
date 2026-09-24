#!/usr/bin/env python3
"""The submission guard must refuse a submit command whose script has not passed the
checker and the dry-run harness, stay silent otherwise, fail closed in a handbook session,
and be installable and checkable without touching anything outside a user root."""
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
GUARD = ROOT / "tools" / "submission-guard.py"
HOOK = ROOT / "tools" / "submission-guard-hook.sh"
HARNESS = ROOT / "tools" / "dry-run-batch-script.py"
LOGGING_RUNNER = ROOT / "tools" / "run-session-logging-python"

CLEAN = """#!/usr/bin/env bash
#SBATCH -A PLACEHOLDER_ACCOUNT
#SBATCH --chdir={jobdir}
#SBATCH --output={jobdir}/job.out
#SBATCH -N 1
set -euo pipefail
here=$(pwd -P)
[ -r "$here/inputs/job.in" ] || exit 1
grep -q "^mass 0.1$" inputs/job.in || exit 1
srun -N 1 ./app inputs/job.in
"""


class GuardDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jobdir = Path(self.temp.name) / "trial"
        (self.jobdir / "inputs").mkdir(parents=True)
        (self.jobdir / "inputs" / "job.in").write_text("mass 0.1\n")
        self.script = self.jobdir / "job.sbatch"
        self.script.write_text(CLEAN.format(jobdir=self.jobdir))
        self.python = interpreter_for("yaml")

    def guard(self, command: str, cwd: Path | None = None):
        event = {"tool_name": "Bash", "tool_input": {"command": command},
                 "cwd": str(cwd or self.temp.name)}
        return subprocess.run([self.python, str(GUARD), "--machine", "perlmutter"],
                              input=json.dumps(event), text=True, capture_output=True, check=False)

    def dry_run(self, *extra: str):
        env = dict(os.environ, TMPDIR=self.temp.name)
        return subprocess.run([self.python, str(HARNESS), str(self.script), "--machine",
                               "perlmutter", *extra], text=True, capture_output=True,
                              check=False, env=env, cwd=self.temp.name)

    def test_non_submission_commands_are_ignored(self):
        for command in ("ls -la", "squeue --me", "sacct -j 1 -X", "echo sbatch-like-word"):
            with self.subTest(command=command):
                result = self.guard(command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    def test_submission_without_receipt_is_refused(self):
        result = self.guard(f"sbatch {self.script}")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no dry-run receipt", result.stderr)

    def test_shell_tool_is_recognised_by_its_command_not_its_name(self):
        """A frontend that names its shell tool differently must not slip past the guard."""
        for tool_name in ("Bash", "shell", "exec_command", None):
            with self.subTest(tool_name=tool_name):
                event = {"tool_input": {"command": f"sbatch {self.script}"}, "cwd": self.temp.name}
                if tool_name is not None:
                    event["tool_name"] = tool_name
                result = subprocess.run([self.python, str(GUARD), "--machine", "perlmutter"],
                                        input=json.dumps(event), text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 2, result.stderr)

    def test_submission_with_passed_receipt_and_negative_is_allowed(self):
        self.assertEqual(self.dry_run().returncode, 0)
        self.assertEqual(self.dry_run("--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/").returncode, 0)
        result = self.guard(f"sbatch {self.script}")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_receipt_without_a_fired_negative_is_refused(self):
        self.assertEqual(self.dry_run().returncode, 0)
        result = self.guard(f"sbatch {self.script}")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no negative test has fired", result.stderr)

    def test_stale_receipt_is_refused(self):
        self.assertEqual(self.dry_run().returncode, 0)
        self.assertEqual(self.dry_run("--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/").returncode, 0)
        self.script.write_text(self.script.read_text() + "echo edited after the dry run\n")
        result = self.guard(f"sbatch {self.script}")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("different version of the script", result.stderr)

    def test_checker_error_is_refused_even_with_a_receipt(self):
        self.assertEqual(self.dry_run().returncode, 0)
        self.assertEqual(self.dry_run("--negative", "inputs/job.in", "s/^mass 0.1$/mass 0.2/").returncode, 0)
        # Add the fatal recipe; the receipt is now stale AND the checker errors.
        self.script.write_text(self.script.read_text() + 'cd "$SLURM_SUBMIT_DIR"\n')
        result = self.guard(f"sbatch {self.script}")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("checker error", result.stderr)
        self.assertIn("SLURM_SUBMIT_DIR", result.stderr)

    def test_relative_path_resolves_against_the_event_cwd(self):
        result = self.guard("sbatch job.sbatch", cwd=self.jobdir)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no dry-run receipt", result.stderr)

    def test_unresolvable_script_is_refused(self):
        result = self.guard("sbatch --wrap='hostname'")
        self.assertEqual(result.returncode, 2, result.stderr)
        result = self.guard("sbatch /no/such/script.sbatch")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("submit by absolute path", result.stderr)

    def test_hook_shim_has_no_opinion_outside_a_handbook_session(self):
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": f"sbatch {self.script}"}})
        env = {k: v for k, v in os.environ.items() if k != "LQCD_HANDBOOK"}
        result = subprocess.run(["/bin/bash", str(HOOK)], input=event, text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def broken_handbook(self) -> Path:
        """A 'handbook' with the surface file but no tools: the prefilter can run, the guard cannot."""
        fake = Path(self.temp.name) / "fake-handbook"
        (fake / "conventions").mkdir(parents=True)
        (fake / "conventions" / "scheduler-surfaces.yaml").write_bytes(
            (ROOT / "conventions" / "scheduler-surfaces.yaml").read_bytes())
        return fake

    def test_hook_shim_fails_closed_when_the_guard_cannot_run(self):
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": f"sbatch {self.script}"}})
        env = dict(os.environ, LQCD_HANDBOOK=str(self.broken_handbook()))
        result = subprocess.run(["/bin/bash", str(HOOK)], input=event, text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("refused", result.stderr)

    def test_hook_shim_fails_closed_when_it_cannot_even_prefilter(self):
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        env = dict(os.environ, LQCD_HANDBOOK=self.temp.name)  # no surface file, no tools
        result = subprocess.run(["/bin/bash", str(HOOK)], input=event, text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_hook_shim_blocks_through_the_real_guard(self):
        event = json.dumps({"tool_name": "Bash", "tool_input": {"command": f"sbatch {self.script}"},
                            "cwd": self.temp.name})
        env = dict(os.environ, LQCD_HANDBOOK=str(ROOT), LQCD_MACHINE="perlmutter")
        result = subprocess.run(["/bin/bash", str(HOOK)], input=event, text=True,
                                capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("no dry-run receipt", result.stderr)

    def test_hook_shim_prefilter_skips_non_submissions_cheaply(self):
        """With the surface file present but no guard, a non-submission must still pass:
        proof the prefilter decided it without consulting the (absent) guard."""
        env = dict(os.environ, LQCD_HANDBOOK=str(self.broken_handbook()))
        for command in ("ls -la", "squeue --me", "echo sbatch-like-word"):
            with self.subTest(command=command):
                event = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
                result = subprocess.run(["/bin/bash", str(HOOK)], input=event, text=True,
                                        capture_output=True, env=env, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)


class GuardInstallerTests(unittest.TestCase):
    def run_tool(self, name: str, *arguments: str):
        return subprocess.run([str(LOGGING_RUNNER), str(ROOT / "tools" / name), *arguments],
                              cwd=ROOT, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=False)

    def state(self, user_root: Path) -> dict:
        result = self.run_tool("check-submission-guard.py", "--frontend", "claude",
                               "--user-root", str(user_root), "--handbook-root", str(ROOT), "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)

    def test_install_check_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            (user_root / ".claude").mkdir(parents=True)
            settings = user_root / ".claude" / "settings.json"
            settings.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
                {"type": "command", "command": "bash unrelated.sh", "timeout": 1}]}]}}))
            self.assertEqual(self.state(user_root)["status"], "missing")
            result = self.run_tool("install-submission-guard.py", "--frontend", "claude",
                                   "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.state(user_root)["status"], "enabled")
            config = json.loads(settings.read_text())
            self.assertEqual(len(config["hooks"]["Stop"]), 1, "unrelated hooks are preserved")
            groups = config["hooks"]["PreToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Bash"])
            self.assertEqual(len(groups[0]["hooks"]), 1)
            hook = user_root / ".claude" / "submission_guard.sh"
            self.assertEqual(hook.read_bytes(), HOOK.read_bytes())
            self.assertEqual(hook.stat().st_mode & 0o777, 0o700)
            again = self.run_tool("install-submission-guard.py", "--frontend", "claude",
                                  "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertIn("already current", again.stdout)
            hook.write_text("# drifted\n")
            self.assertEqual(self.state(user_root)["status"], "stale")

    def codex_state(self, user_root: Path) -> dict:
        result = self.run_tool("check-submission-guard.py", "--frontend", "codex",
                               "--user-root", str(user_root), "--handbook-root", str(ROOT), "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)

    def test_codex_json_install_preserves_unrelated_hooks_and_is_configured(self):
        """Codex speaks the same command-hook protocol; what differs is trust, which the
        installer never grants and the checker never infers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            hooks_path = user_root / ".codex" / "hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(json.dumps({"description": "operator hooks", "hooks": {"Stop": [
                {"hooks": [{"type": "command", "command": "true", "timeout": 3}]}]}}))
            self.assertEqual(self.codex_state(user_root)["status"], "missing")
            first = self.run_tool("install-submission-guard.py", "--frontend", "codex",
                                  "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertIn("review and trust", first.stdout)
            config = json.loads(hooks_path.read_text())
            self.assertEqual(config["description"], "operator hooks")
            self.assertEqual([h["command"] for g in config["hooks"]["Stop"] for h in g["hooks"]], ["true"])
            groups = config["hooks"]["PreToolUse"]
            self.assertEqual([g["matcher"] for g in groups], ["Bash"])
            self.assertEqual(groups[0]["hooks"][0]["command"], 'bash "$HOME/.codex/submission_guard.sh"')
            hook = user_root / ".codex" / "submission_guard.sh"
            self.assertEqual(hook.read_bytes(), HOOK.read_bytes())
            self.assertEqual(hook.stat().st_mode & 0o777, 0o700)
            self.assertEqual(self.codex_state(user_root)["status"], "configured")
            second = self.run_tool("install-submission-guard.py", "--frontend", "codex",
                                   "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertIn("already current", second.stdout)

    def test_codex_inline_toml_install_preserves_existing_hook(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            config_toml = user_root / ".codex" / "config.toml"
            config_toml.parent.mkdir(parents=True)
            config_toml.write_text('[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ntype = "command"\n'
                                   'command = "true"\ntimeout = 3\n')
            result = self.run_tool("install-submission-guard.py", "--frontend", "codex",
                                   "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertEqual(result.returncode, 0, result.stdout)
            text = config_toml.read_text()
            self.assertIn('command = "true"', text)
            self.assertIn("[[hooks.PreToolUse]]", text)
            self.assertIn('matcher = "Bash"', text)
            self.assertFalse((user_root / ".codex" / "hooks.json").exists())
            self.assertEqual(self.codex_state(user_root)["status"], "configured")

    def test_codex_install_refuses_malformed_or_disabled_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "malformed"
            hooks_path = user_root / ".codex" / "hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text("{not json\n")
            result = self.run_tool("install-submission-guard.py", "--frontend", "codex",
                                   "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(hooks_path.read_text(), "{not json\n")
            self.assertFalse((user_root / ".codex" / "submission_guard.sh").exists())
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "disabled"
            config_toml = user_root / ".codex" / "config.toml"
            config_toml.parent.mkdir(parents=True)
            config_toml.write_text("[features]\nhooks = false\n")
            result = self.run_tool("install-submission-guard.py", "--frontend", "codex",
                                   "--user-root", str(user_root), "--handbook-root", str(ROOT))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("hooks are disabled", result.stdout)


if __name__ == "__main__":
    unittest.main()
