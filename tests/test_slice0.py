#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class SliceZeroTests(unittest.TestCase):
    def test_required_scaffold_exists(self):
        required = [
            "AGENTS.md",
            "CLAUDE.md",
            "INDEX.md",
            "ARCHITECTURE.md",
            "ROADMAP.md",
            "handbook.yaml",
            "README.md",
            "PRIVACY.md",
            "CONTRIBUTING.md",
            ".gitignore",
            "conventions/orientation.md",
            "modes/user.md",
            "modes/developer.md",
            "schemas/machine.schema.json",
            "schemas/project.schema.json",
            "tools/validate-knowledge.py",
            "tools/lqcd-claude",
            "tools/lqcd-codex",
            "tools/install-codex-skills",
            "tools/sync-agent-entrypoints.py",
            ".claude/skills/lqcd-start-session/SKILL.md",
            ".agents/skills/lqcd-start-session/SKILL.md",
            "playbooks/start-session.md",
            "playbooks/start-session-claude.md",
            "playbooks/start-session-codex.md",
            "playbooks/start-session-prompt.txt",
            "inbox/proposals/.gitkeep",
            "inbox/rejections/.gitkeep",
        ]
        missing = [item for item in required if not (ROOT / item).exists()]
        self.assertEqual(missing, [])

    def test_tier_zero_budget(self):
        config = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        tier = config["tier_0"]
        canonical = ROOT / tier["canonical_entrypoint"]
        total = sum((ROOT / name).stat().st_size for name in tier["files"])
        self.assertIn(tier["canonical_entrypoint"], tier["files"])
        self.assertLessEqual(total, tier["max_combined_bytes"])
        self.assertLessEqual(canonical.stat().st_size, tier["max_entrypoint_bytes"])
        for mirror_name in tier["mirrors"]:
            self.assertEqual(canonical.read_bytes(), (ROOT / mirror_name).read_bytes())

    def test_planning_state_has_one_home(self):
        architecture = (ROOT / "ARCHITECTURE.md").read_text()
        roadmap = (ROOT / "ROADMAP.md").read_text()
        self.assertNotIn("NEXT ACTION:", architecture)
        self.assertEqual(roadmap.count("NEXT ACTION:"), 1)

    def test_schemas_are_well_formed(self):
        for path in (ROOT / "schemas").glob("*.schema.json"):
            Draft202012Validator.check_schema(json.loads(path.read_text()))

    def test_validator_reports_limited_scope(self):
        result = subprocess.run(
            ["python3", str(ROOT / "tools/validate-knowledge.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("publishability NOT checked", result.stdout)
        self.assertNotIn("passed", result.stdout.lower())

    def test_validator_scans_unknown_text_suffixes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            private_path = "/" + "home/example/private/"
            (handbook_copy / "PRIVACY.md.orig").write_text(private_path)

            result = subprocess.run(
                ["python3", str(handbook_copy / "tools/validate-knowledge.py")],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "PRIVACY.md.orig:1: deny-list match (user-specific home path)",
                result.stdout,
            )

    def test_frontmatter_dates_load_as_strings(self):
        text = (ROOT / "conventions/orientation.md").read_text()
        _, raw_frontmatter, _ = text.split("---", 2)
        metadata = yaml.safe_load(raw_frontmatter)
        self.assertIsInstance(metadata["observed"], str)
        self.assertIsInstance(metadata["review_by"], str)

    def test_validator_rejects_unquoted_frontmatter_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            orientation = handbook_copy / "conventions/orientation.md"
            text = orientation.read_text()
            _, raw_frontmatter, _ = text.split("---", 2)
            metadata = yaml.safe_load(raw_frontmatter)
            for field in ("observed", "review_by"):
                value = metadata[field]
                quoted_value = json.dumps(value)
                original = f"{field}: {quoted_value}"
                self.assertIn(original, text)
                text = text.replace(original, f"{field}: {value}", 1)
            orientation.write_text(text)

            result = subprocess.run(
                ["python3", str(handbook_copy / "tools/validate-knowledge.py")],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "observed must be a quoted ISO date string", result.stdout
            )
            self.assertIn(
                "review_by must be a quoted ISO date string", result.stdout
            )

    def test_pending_inbox_entries_are_visible_to_git(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / ".gitignore").write_text((ROOT / ".gitignore").read_text())
            candidate = (
                repo
                / "inbox/proposals"
                / "2026-08-15T120000Z-test-123e4567-e89b-12d3-a456-426614174000.yaml"
            )
            candidate.parent.mkdir(parents=True)
            candidate.write_text("created: 2026-08-15T12:00:00Z\n")

            initialized = subprocess.run(
                ["git", "init", "--quiet"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stdout)

            result = subprocess.run(
                [
                    "git",
                    "-c",
                    f"core.excludesFile={os.devnull}",
                    "check-ignore",
                    "--no-index",
                    str(candidate.relative_to(repo)),
                ],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)

    def test_privacy_screening_targets_only_proposed_handbook_material(self):
        agents = " ".join((ROOT / "AGENTS.md").read_text().split())
        architecture = " ".join(
            (ROOT / "ARCHITECTURE.md").read_text().split()
        )
        user_mode = " ".join((ROOT / "modes/user.md").read_text().split())
        developer_mode = " ".join(
            (ROOT / "modes/developer.md").read_text().split()
        )
        startup = " ".join(
            (ROOT / "playbooks/start-session.md").read_text().split()
        )

        self.assertIn("a user-mode inbox entry", agents)
        self.assertIn("It does not govern files in the working project", agents)
        self.assertIn("You may create a uniquely named file", agents)
        self.assertIn("Apply `PRIVACY.md` only to the exact inbox file", user_mode)
        self.assertIn("Do not scan, redact, or rewrite", user_mode)
        self.assertIn(
            "Apply `PRIVACY.md` only to the exact inbox entry or direct handbook diff",
            developer_mode,
        )
        self.assertIn("This status classification is structural", startup)
        self.assertNotIn("privacy-screened before creation", startup)
        self.assertIn("Privacy-screening boundary", architecture)
        self.assertIn("never to the working directory as a whole", architecture)

    def test_session_logs_are_ignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "session_example.log"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launchers_fail_actionably_without_interface(self):
        for launcher in ("lqcd-claude", "lqcd-codex"):
            with self.subTest(launcher=launcher):
                env = os.environ.copy()
                env.pop("LQCD_HANDBOOK", None)
                result = subprocess.run(
                    [str(ROOT / "tools" / launcher)],
                    cwd=ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("LQCD_HANDBOOK is not set", result.stdout)
                self.assertIn("export LQCD_HANDBOOK=", result.stdout)

    def test_validator_rejects_frontend_manifest_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            manifest = handbook_copy / "handbook.yaml"
            config = yaml.safe_load(manifest.read_text())
            config["launcher"]["frontends"]["codex"]["complete_loading_env"] = (
                "LQCD_HANDBOOK_WRONG_BOOTSTRAP"
            )
            manifest.write_text(yaml.safe_dump(config, sort_keys=False))

            result = subprocess.run(
                [sys.executable, str(handbook_copy / "tools/validate-knowledge.py")],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "missing manifest token 'LQCD_HANDBOOK_WRONG_BOOTSTRAP' for codex",
                result.stdout,
            )

    def test_validator_rejects_startup_prompt_manifest_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            manifest = handbook_copy / "handbook.yaml"
            config = yaml.safe_load(manifest.read_text())
            config["launcher"]["startup_prompt"] = "playbooks/missing-prompt.txt"
            manifest.write_text(yaml.safe_dump(config, sort_keys=False))

            result = subprocess.run(
                [sys.executable, str(handbook_copy / "tools/validate-knowledge.py")],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "launcher.startup_prompt does not exist: playbooks/missing-prompt.txt",
                result.stdout,
            )

    def test_validator_rejects_entrypoint_mirror_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            with (handbook_copy / "CLAUDE.md").open("a") as mirror:
                mirror.write("\nfrontend-only drift\n")

            result = subprocess.run(
                [sys.executable, str(handbook_copy / "tools/validate-knowledge.py")],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "CLAUDE.md differs from canonical entrypoint AGENTS.md", result.stdout
            )

    def test_entrypoint_sync_check_and_repair(self):
        check = subprocess.run(
            [sys.executable, str(ROOT / "tools/sync-agent-entrypoints.py"), "--check"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stdout)

        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            (handbook_copy / "CLAUDE.md").write_text("stale\n")
            repaired = subprocess.run(
                [
                    sys.executable,
                    str(handbook_copy / "tools/sync-agent-entrypoints.py"),
                ],
                cwd=handbook_copy,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(repaired.returncode, 0, repaired.stdout)
            self.assertEqual(
                (handbook_copy / "AGENTS.md").read_bytes(),
                (handbook_copy / "CLAUDE.md").read_bytes(),
            )

    def test_launchers_reject_entrypoint_mirror_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook_copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook_copy,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            with (handbook_copy / "CLAUDE.md").open("a") as mirror:
                mirror.write("\nfrontend-only drift\n")
            env = os.environ.copy()
            env["LQCD_HANDBOOK"] = str(handbook_copy)

            for launcher in ("lqcd-claude", "lqcd-codex"):
                with self.subTest(launcher=launcher):
                    result = subprocess.run(
                        [str(handbook_copy / "tools" / launcher)],
                        cwd=handbook_copy,
                        env=env,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertIn("not synchronized", result.stdout)

    def run_launcher_with_fake_frontend(
        self,
        launcher_name: str,
        executable_name: str,
        launcher_args: tuple[str, ...] = ("--test-forwarded",),
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            capture = temp / "capture.json"
            fake_executable = fake_bin / executable_name
            fake_executable.write_text(
                f"#!{sys.executable}\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "from pathlib import Path\n"
                "keys = [\n"
                "    'LQCD_HANDBOOK',\n"
                "    'LQCD_HANDBOOK_LAUNCHED',\n"
                "    'LQCD_HANDBOOK_FRONTEND',\n"
                "    'CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD',\n"
                "    'LQCD_HANDBOOK_CODEX_BOOTSTRAP',\n"
                "]\n"
                "payload = {\n"
                "    'argv': sys.argv[1:],\n"
                "    'cwd': os.getcwd(),\n"
                "    'env': {key: os.environ.get(key) for key in keys},\n"
                "}\n"
                "Path(os.environ['LQCD_LAUNCH_CAPTURE']).write_text(json.dumps(payload))\n"
            )
            fake_executable.chmod(0o755)
            env = os.environ.copy()
            env["LQCD_HANDBOOK"] = str(ROOT)
            env["LQCD_LAUNCH_CAPTURE"] = str(capture)
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                [str(ROOT / "tools" / launcher_name), *launcher_args],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            return json.loads(capture.read_text())

    def test_frontend_launchers_preserve_cwd_and_set_contract(self):
        claude = self.run_launcher_with_fake_frontend("lqcd-claude", "claude")
        self.assertEqual(claude["cwd"], str(ROOT))
        self.assertEqual(
            claude["argv"], ["--add-dir", str(ROOT), "--test-forwarded"]
        )
        self.assertEqual(claude["env"]["LQCD_HANDBOOK_FRONTEND"], "claude")
        self.assertEqual(
            claude["env"]["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"], "1"
        )

        codex = self.run_launcher_with_fake_frontend("lqcd-codex", "codex")
        self.assertEqual(codex["cwd"], str(ROOT))
        self.assertEqual(codex["argv"][-1], "--test-forwarded")
        self.assertNotIn("--add-dir", codex["argv"])
        self.assertNotIn("--sandbox", codex["argv"])
        self.assertEqual(codex["env"]["LQCD_HANDBOOK_FRONTEND"], "codex")
        self.assertEqual(codex["env"]["LQCD_HANDBOOK_CODEX_BOOTSTRAP"], "1")
        config_index = codex["argv"].index("--config") + 1
        bootstrap = codex["argv"][config_index]
        self.assertIn("developer_instructions=", bootstrap)
        self.assertIn("$LQCD_HANDBOOK/AGENTS.md", bootstrap)
        self.assertNotIn("model_instructions_file", bootstrap)
        self.assertNotIn("-C", codex["argv"])

    def test_zero_argument_launchers_inject_shared_startup_prompt(self):
        startup_prompt = (
            ROOT / "playbooks/start-session-prompt.txt"
        ).read_text().strip()

        claude = self.run_launcher_with_fake_frontend(
            "lqcd-claude", "claude", ()
        )
        self.assertEqual(
            claude["argv"],
            ["--add-dir", str(ROOT), "--", startup_prompt],
        )

        codex = self.run_launcher_with_fake_frontend("lqcd-codex", "codex", ())
        self.assertEqual(codex["argv"][-2:], ["--", startup_prompt])
        self.assertNotIn("--add-dir", codex["argv"])
        self.assertNotIn("--sandbox", codex["argv"])
        config_index = codex["argv"].index("--config") + 1
        self.assertIn("developer_instructions=", codex["argv"][config_index])

    def test_codex_skill_installer_is_idempotent_and_conflict_safe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            env = os.environ.copy()
            env["HOME"] = str(temp / "home")
            env["LQCD_HANDBOOK"] = str(ROOT)
            command = [str(ROOT / "tools/install-codex-skills")]

            first = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertIn("inside the handbook repository", first.stdout)
            target = temp / "home/.agents/skills/lqcd-start-session"
            self.assertTrue(target.is_symlink())
            self.assertEqual(
                target.resolve(),
                (ROOT / ".agents/skills/lqcd-start-session").resolve(),
            )

            second = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertIn("already installed", second.stdout)

            target.unlink()
            target.write_text("operator-owned skill\n")
            conflict = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(conflict.returncode, 2, conflict.stdout)
            self.assertIn("Refusing to replace", conflict.stdout)
            self.assertIn("Review or remove it manually", conflict.stdout)

            target.unlink()
            target.symlink_to(temp / "missing-skill")
            dangling = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(dangling.returncode, 2, dangling.stdout)
            self.assertIn("different or dangling", dangling.stdout)
            self.assertTrue(target.is_symlink())

if __name__ == "__main__":
    unittest.main()
