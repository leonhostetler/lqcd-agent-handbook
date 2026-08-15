#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class SliceZeroTests(unittest.TestCase):
    def test_required_scaffold_exists(self):
        required = [
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
            ".claude/skills/lqcd-start-session/SKILL.md",
            "playbooks/start-session.md",
            "inbox/proposals/.gitkeep",
            "inbox/rejections/.gitkeep",
        ]
        missing = [item for item in required if not (ROOT / item).exists()]
        self.assertEqual(missing, [])

    def test_tier_zero_budget(self):
        config = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        tier = config["tier_0"]
        total = sum((ROOT / name).stat().st_size for name in tier["files"])
        self.assertLessEqual(total, tier["max_combined_bytes"])
        self.assertLessEqual((ROOT / "CLAUDE.md").stat().st_size, tier["max_claude_md_bytes"])

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
            quoted_observed = json.dumps("2026-08-14")
            quoted_review = json.dumps("2027-08-14")
            text = text.replace(
                f"observed: {quoted_observed}", "observed: 2026-08-14"
            )
            text = text.replace(
                f"review_by: {quoted_review}", "review_by: 2027-08-14"
            )
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

    def test_launcher_fails_actionably_without_interface(self):
        env = os.environ.copy()
        env.pop("LQCD_HANDBOOK", None)
        result = subprocess.run(
            [str(ROOT / "tools/lqcd-claude")],
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


if __name__ == "__main__":
    unittest.main()
