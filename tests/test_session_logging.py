#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SessionLoggingTests(unittest.TestCase):
    def run_tool(
        self, name: str, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / name), *arguments],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def check_state(self, frontend: str, user_root: Path) -> dict[str, str]:
        result = self.run_tool(
            "check-session-logging.py",
            "--frontend",
            frontend,
            "--user-root",
            str(user_root),
            "--handbook-root",
            str(ROOT),
            "--json",
        )
        return json.loads(result.stdout)

    def install(self, frontend: str, user_root: Path, check: bool = True):
        return self.run_tool(
            "install-session-logging.py",
            "--frontend",
            frontend,
            "--user-root",
            str(user_root),
            "--handbook-root",
            str(ROOT),
            check=check,
        )

    def test_startup_playbook_checks_and_offers_without_auto_install(self):
        text = (ROOT / "playbooks/start-session.md").read_text()
        self.assertIn("tools/check-session-logging.py", text)
        self.assertIn("playbooks/session-logging.md", text)
        self.assertIn("Do not install or repair user-level hooks automatically", text)
        self.assertIn("second mandatory startup question", text)

    def test_checker_reports_missing_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            before = list(Path(temp_dir).rglob("*"))
            state = self.check_state("codex", user_root)
            after = list(Path(temp_dir).rglob("*"))
            self.assertEqual(state["status"], "missing")
            self.assertEqual(before, after)

    @unittest.skipUnless(shutil.which("jq"), "Claude logger requires jq")
    def test_claude_install_is_idempotent_and_preserves_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            settings = user_root / ".claude/settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "true",
                                            "timeout": 2,
                                        }
                                    ]
                                }
                            ]
                        },
                    }
                )
            )

            first = self.install("claude", user_root)
            self.assertIn("Reload hooks", first.stdout)
            installed = user_root / ".claude/log_session.sh"
            self.assertEqual(
                installed.read_bytes(),
                (ROOT / "tools/log-session-claude.sh").read_bytes(),
            )
            self.assertEqual(stat.S_IMODE(installed.stat().st_mode), 0o700)
            config = json.loads(settings.read_text())
            self.assertEqual(config["theme"], "dark")
            commands = [
                item["command"]
                for group in config["hooks"]["Stop"]
                for item in group["hooks"]
            ]
            self.assertIn("true", commands)
            self.assertIn('bash "$HOME/.claude/log_session.sh"', commands)
            self.assertEqual(self.check_state("claude", user_root)["status"], "enabled")

            backups_before = list(settings.parent.glob("*.before-session-logging*"))
            second = self.install("claude", user_root)
            self.assertIn("already current", second.stdout)
            self.assertEqual(
                backups_before,
                list(settings.parent.glob("*.before-session-logging*")),
            )

            installed.write_text("stale\n")
            self.assertEqual(self.check_state("claude", user_root)["status"], "stale")

    def test_codex_json_install_preserves_unrelated_hooks_and_is_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            hooks_path = user_root / ".codex/hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(
                json.dumps(
                    {
                        "description": "operator hooks",
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "true",
                                            "timeout": 3,
                                        }
                                    ]
                                }
                            ]
                        },
                    }
                )
            )

            first = self.install("codex", user_root)
            self.assertIn("review and trust", first.stdout)
            config = json.loads(hooks_path.read_text())
            self.assertEqual(config["description"], "operator hooks")
            commands = [
                item["command"]
                for group in config["hooks"]["Stop"]
                for item in group["hooks"]
            ]
            self.assertIn("true", commands)
            self.assertEqual(
                sum(".codex/log_session.py" in command for command in commands), 1
            )
            installed = user_root / ".codex/log_session.py"
            self.assertEqual(
                installed.read_bytes(),
                (ROOT / "tools/log-session-codex.py").read_bytes(),
            )
            self.assertEqual(stat.S_IMODE(installed.stat().st_mode), 0o700)
            self.assertEqual(
                self.check_state("codex", user_root)["status"], "configured"
            )

            second = self.install("codex", user_root)
            self.assertIn("already current", second.stdout)

    def test_codex_json_install_replaces_imported_claude_logger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            hooks_path = user_root / ".codex/hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": 'bash "$HOME/.claude/log_session.sh"',
                                            "timeout": 30,
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                )
            )

            self.install("codex", user_root)
            config = json.loads(hooks_path.read_text())
            commands = [
                item["command"]
                for group in config["hooks"]["Stop"]
                for item in group["hooks"]
            ]
            self.assertFalse(
                any(".claude/log_session.sh" in command for command in commands)
            )
            self.assertEqual(
                sum(".codex/log_session.py" in command for command in commands), 1
            )

    @unittest.skipUnless(sys.version_info >= (3, 11), "TOML parsing needs 3.11 or tomli")
    def test_codex_inline_toml_install_preserves_existing_hook(self):
        import tomllib

        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            config_path = user_root / ".codex/config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                'model = "example"\n'
                "\n[[hooks.Stop]]\n"
                "\n[[hooks.Stop.hooks]]\n"
                'type = "command"\n'
                'command = "true"\n'
                "timeout = 3\n"
            )

            self.install("codex", user_root)
            self.assertFalse((user_root / ".codex/hooks.json").exists())
            with config_path.open("rb") as stream:
                config = tomllib.load(stream)
            commands = [
                item["command"]
                for group in config["hooks"]["Stop"]
                for item in group["hooks"]
            ]
            self.assertIn("true", commands)
            self.assertEqual(
                sum(".codex/log_session.py" in command for command in commands), 1
            )
            self.assertEqual(
                self.check_state("codex", user_root)["status"], "configured"
            )

    def test_codex_install_refuses_malformed_or_disabled_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "malformed"
            hooks_path = user_root / ".codex/hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text("{not json\n")
            result = self.install("codex", user_root, check=False)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("was not installed", result.stdout)
            self.assertFalse((user_root / ".codex/log_session.py").exists())
            self.assertEqual(hooks_path.read_text(), "{not json\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "disabled"
            config_path = user_root / ".codex/config.toml"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("[features]\nhooks = false\n")
            result = self.install("codex", user_root, check=False)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("hooks are disabled", result.stdout)
            self.assertFalse((user_root / ".codex/log_session.py").exists())

        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "linked"
            target = user_root / ".codex/log_session.py"
            target.parent.mkdir(parents=True)
            target.symlink_to(ROOT / "tools/log-session-codex.py")
            result = self.install("codex", user_root, check=False)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("refusing to replace symbolic link", result.stdout)
            self.assertTrue(target.is_symlink())

    def test_checker_reports_duplicate_codex_handlers_as_broken(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            user_root = Path(temp_dir) / "user"
            config_dir = user_root / ".codex"
            config_dir.mkdir(parents=True)
            shutil.copy2(
                ROOT / "tools/log-session-codex.py",
                config_dir / "log_session.py",
            )
            command = f'{sys.executable} "$HOME/.codex/log_session.py"'
            handler = {
                "type": "command",
                "command": command,
                "timeout": 30,
                "statusMessage": "Logging session transcript",
            }
            (config_dir / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {"hooks": [handler]},
                                {"hooks": [handler]},
                            ]
                        }
                    }
                )
            )
            self.assertEqual(
                self.check_state("codex", user_root)["status"], "broken"
            )

    @unittest.skipUnless(shutil.which("jq"), "Claude logger requires jq")
    def test_claude_logger_excludes_tool_io_and_writes_private_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            launch_dir = temp / "launch"
            launch_dir.mkdir()
            transcript = temp / "transcript.jsonl"
            records = [
                {"type": "user", "message": {"content": "hello"}},
                {
                    "type": "user",
                    "message": {
                        "content": [{"type": "tool_result", "text": "SECRET_TOOL"}]
                    },
                },
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "visible reply"},
                            {"type": "tool_use", "name": "Bash"},
                        ]
                    },
                },
            ]
            transcript.write_text(
                "".join(json.dumps(record) + "\n" for record in records)
            )
            hook = {
                "transcript_path": str(transcript),
                "cwd": str(temp),
                "session_id": "claude-test",
            }
            environment = os.environ.copy()
            environment["CLAUDE_PROJECT_DIR"] = str(launch_dir)
            result = subprocess.run(
                ["bash", str(ROOT / "tools/log-session-claude.sh")],
                cwd=temp,
                env=environment,
                input=json.dumps(hook),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            output = (
                launch_dir
                / f"session_{dt.datetime.now().astimezone():%Y-%m-%d}_claude-test.log"
            )
            text = output.read_text()
            self.assertIn("hello", text)
            self.assertIn("visible reply", text)
            self.assertNotIn("SECRET_TOOL", text)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_codex_logger_uses_last_message_and_excludes_injected_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            launch_dir = temp / "launch"
            launch_dir.mkdir()
            transcript = temp / "rollout.jsonl"
            records = [
                {"type": "session_meta", "payload": {"cwd": str(launch_dir)}},
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "user prompt"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "<environment_context>PRIVATE_CONTEXT</environment_context>",
                            }
                        ],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "commentary"}],
                    },
                },
                {"type": "tool_call", "payload": {"output": "SECRET_TOOL"}},
            ]
            transcript.write_text(
                "".join(json.dumps(record) + "\n" for record in records)
            )
            hook = {
                "transcript_path": str(transcript),
                "cwd": str(temp),
                "last_assistant_message": "final response",
            }
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools/log-session-codex.py")],
                cwd=temp,
                input=json.dumps(hook),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            output = (
                launch_dir
                / f"session_{dt.datetime.now().astimezone():%Y-%m-%d}.log"
            )
            text = output.read_text()
            self.assertIn("user prompt", text)
            self.assertIn("commentary", text)
            self.assertEqual(text.count("final response"), 1)
            self.assertNotIn("PRIVATE_CONTEXT", text)
            self.assertNotIn("SECRET_TOOL", text)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_validator_rejects_missing_declared_logger(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handbook = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                handbook,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "session_*.log"
                ),
            )
            (handbook / "tools/log-session-codex.py").unlink()
            result = subprocess.run(
                [sys.executable, str(handbook / "tools/validate-knowledge.py")],
                cwd=handbook,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(
                "session_logging.frontends.codex.logger does not exist",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
