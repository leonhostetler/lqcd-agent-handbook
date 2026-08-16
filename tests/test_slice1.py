#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_knowledge", ROOT / "tools/validate-knowledge.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class SliceOneMachineTests(unittest.TestCase):
    def test_perlmutter_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(
            (ROOT / "machines/perlmutter/machine.yaml").read_text()
        )
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def run_detector(self, *, nersc_host: str, hostname: str) -> str:
        env = os.environ.copy()
        env.pop("NERSC_HOST", None)
        env["LQCD_DETECT_NERSC_HOST"] = nersc_host
        env["LQCD_DETECT_HOSTNAME"] = hostname
        result = subprocess.run(
            ["bash", str(ROOT / "tools/detect-machine.sh")],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        return result.stdout.strip()

    def test_detector_uses_nersc_machine_marker(self):
        self.assertEqual(
            self.run_detector(nersc_host="perlmutter", hostname="unrelated"),
            "perlmutter",
        )

    def test_detector_recognizes_public_login_aliases(self):
        for hostname in ("perlmutter.nersc.gov", "saul.nersc.gov"):
            with self.subTest(hostname=hostname):
                self.assertEqual(
                    self.run_detector(nersc_host="", hostname=hostname),
                    "perlmutter",
                )

    def test_detector_reports_unknown_without_matching_evidence(self):
        self.assertEqual(
            self.run_detector(nersc_host="", hostname="example.invalid"),
            "unknown",
        )


class SliceOneKnowledgeTests(unittest.TestCase):
    def test_quda_project_matches_project_schema(self):
        schema = json.loads((ROOT / "schemas/project.schema.json").read_text())
        project = yaml.safe_load((ROOT / "software/quda/project.yaml").read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(project)
        )
        self.assertEqual(problems, [])

    def test_slice_one_has_exactly_one_quda_profile(self):
        profiles = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]
        self.assertEqual(list(profiles), ["milc-cg"])
        self.assertFalse(profiles["milc-cg"]["options"]["QUDA_MULTIGRID"])
        self.assertTrue(profiles["milc-cg"]["options"]["QUDA_INTERFACE_QDP"])

    def test_validated_stack_references_profile_and_node_type(self):
        machine = yaml.safe_load(
            (ROOT / "machines/perlmutter/machine.yaml").read_text()
        )
        stack = yaml.safe_load(
            (
                ROOT
                / "machines/perlmutter/stacks/quda-cuda12-milc-cg-2026q3/stack.yaml"
            ).read_text()
        )
        profiles = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]
        self.assertIn(stack["profile"], profiles)
        for node_type in stack["validated_on"]:
            self.assertIn(node_type, machine["node_types"])
        self.assertEqual(stack["validation"]["result"], "pass")
        self.assertEqual(
            [test["result"] for test in stack["validation"]["tests"]],
            ["pass", "pass", "pass"],
        )

    def test_build_skill_adapters_route_to_shared_playbook(self):
        token = "$LQCD_HANDBOOK/playbooks/build-lqcd-stack.md"
        for frontend in (".agents", ".claude"):
            with self.subTest(frontend=frontend):
                skill = (
                    ROOT / frontend / "skills/lqcd-build-stack/SKILL.md"
                ).read_text()
                self.assertIn(token, skill)


class ObservedOnCompletenessTests(unittest.TestCase):
    def validate(self, value, **kwargs):
        errors = []
        VALIDATOR.validate_observed_on(
            value, Path("candidate.yaml"), errors, **kwargs
        )
        return errors

    def test_machine_and_software_context_is_complete(self):
        errors = self.validate(
            {
                "machine": "perlmutter",
                "software": {
                    "quda": {"commit": "abc123", "branch": "develop"}
                },
            },
            scope=["machine:perlmutter", "software:quda"],
        )
        self.assertEqual(errors, [])

    def test_scoped_machine_must_match(self):
        errors = self.validate(
            {"machine": "frontier"}, scope=["machine:perlmutter"]
        )
        self.assertTrue(any("scoped machine" in error for error in errors))

    def test_scoped_software_requires_commit_and_branch(self):
        errors = self.validate(
            {"software": {"quda": {}}}, scope=["software:quda"]
        )
        self.assertTrue(any(".commit" in error for error in errors))
        self.assertTrue(any(".branch" in error for error in errors))

    def test_feature_branch_requires_develop_fork_point(self):
        errors = self.validate(
            {
                "software": {
                    "quda": {"commit": "abc123", "branch": "feature/example"}
                }
            },
            expected_software="quda",
        )
        self.assertTrue(any("forked_from_develop" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
