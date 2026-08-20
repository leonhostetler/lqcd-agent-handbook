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
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])
        self.assertEqual(
            manifest["schema_versions"]["machine"], profile["schema_version"]
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            profile["schema_version"],
        )

    def test_perlmutter_profile_records_installed_nodes_by_type(self):
        profile = yaml.safe_load(
            (ROOT / "machines/perlmutter/machine.yaml").read_text()
        )
        counts = {
            name: node["sizing"]["installed_nodes"]
            for name, node in profile["node_types"].items()
        }
        self.assertEqual(
            counts,
            {
                "cpu": 3072,
                "gpu-a100-40": 1536,
                "gpu-a100-80": 256,
            },
        )

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

    def test_node_type_resolution_defaults_only_unambiguous_profiles(self):
        for relative_path in (
            "AGENTS.md",
            "playbooks/start-session.md",
            "playbooks/build-lqcd-stack.md",
        ):
            with self.subTest(relative_path=relative_path):
                text = " ".join((ROOT / relative_path).read_text().split())
                self.assertIn("`node_types` entry", text)
                self.assertIn("default", text)
                self.assertTrue("multiple" in text or "otherwise" in text)

        for machine, expected in (
            ("deltaai", "gpu-gh200"),
            ("frontier", "gpu-mi250x"),
        ):
            with self.subTest(machine=machine):
                profile = yaml.safe_load(
                    (ROOT / f"machines/{machine}/machine.yaml").read_text()
                )
                self.assertEqual(list(profile["node_types"]), [expected])
                notes = " ".join(
                    (ROOT / f"machines/{machine}/notes.md").read_text().split()
                )
                self.assertIn("No separate operator declaration is needed", notes)

        perlmutter = yaml.safe_load(
            (ROOT / "machines/perlmutter/machine.yaml").read_text()
        )
        self.assertGreater(len(perlmutter["node_types"]), 1)
        self.assertIn(
            "explicitly",
            (ROOT / "machines/perlmutter/notes.md").read_text(),
        )


class SliceOneKnowledgeTests(unittest.TestCase):
    def test_quda_project_matches_project_schema(self):
        schema = json.loads((ROOT / "schemas/project.schema.json").read_text())
        project = yaml.safe_load((ROOT / "software/quda/project.yaml").read_text())
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(project)
        )
        self.assertEqual(problems, [])
        self.assertEqual(project["default_branch"], "develop")
        self.assertEqual(
            manifest["schema_versions"]["project"], project["schema_version"]
        )
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            project["schema_version"],
        )

    def test_slice_one_has_exactly_one_quda_profile(self):
        profiles = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]
        self.assertEqual(list(profiles), ["milc-cg"])
        self.assertFalse(profiles["milc-cg"]["options"]["QUDA_MULTIGRID"])
        self.assertTrue(profiles["milc-cg"]["options"]["QUDA_INTERFACE_QDP"])

    def test_complete_test_suite_is_the_build_default(self):
        options = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]["milc-cg"]["options"]
        self.assertTrue(options["QUDA_BUILD_ALL_TESTS"])
        self.assertTrue(options["QUDA_INSTALL_ALL_TESTS"])

        architecture = " ".join((ROOT / "ARCHITECTURE.md").read_text().split())
        playbook = " ".join(
            (ROOT / "playbooks/build-lqcd-stack.md").read_text().split()
        )
        guide = (ROOT / "software/quda/build.md").read_text()
        self.assertIn(
            "A reduced test build requires an **explicit operator instruction",
            architecture,
        )
        self.assertIn("Build the complete available test suite by default", playbook)
        self.assertIn("do not infer an opt-out", playbook)
        self.assertIn("-DQUDA_BUILD_ALL_TESTS=ON", guide)
        self.assertIn("-DQUDA_INSTALL_ALL_TESTS=ON", guide)
        self.assertNotIn("-DQUDA_BUILD_ALL_TESTS=OFF", guide)
        self.assertNotIn("-DQUDA_INSTALL_ALL_TESTS=OFF", guide)

        for notes in ROOT.glob("machines/*/stacks/quda-*/notes.md"):
            with self.subTest(notes=notes):
                text = notes.read_text()
                self.assertNotIn("-DQUDA_BUILD_ALL_TESTS=OFF", text)
                self.assertNotIn("-DQUDA_INSTALL_ALL_TESTS=OFF", text)

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
                self.assertIn("resolved machine node type", skill)

    def test_build_playbook_offers_canonical_full_clone_when_source_is_missing(self):
        playbook = (ROOT / "playbooks/build-lqcd-stack.md").read_text()
        normalized = " ".join(playbook.split())
        project = yaml.safe_load((ROOT / "software/quda/project.yaml").read_text())
        self.assertEqual(project["repository"], "https://github.com/lattice/quda.git")
        self.assertEqual(project["default_branch"], "develop")
        required = (
            "read its canonical repository URL and `default_branch`",
            "Offer to clone it before performing any network or filesystem write",
            "require that it does not already exist",
            "git clone --branch <default-branch> -- <repository-url> <destination>",
            "Only select a tested stack commit when the operator specifically asks",
            "the existence of a nearest stack is not such a request",
            "git clone -- <repository-url> <destination>",
            "git -C <destination> checkout --detach <tested-commit>",
            "Do not use a shallow clone",
            "never inside the handbook",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, normalized)

        self.assertNotIn("git clone --branch develop", normalized)

        self.assertLess(
            normalized.index("Offer to clone"), normalized.index("git clone --")
        )


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

    def test_feature_branch_requires_default_fork_point(self):
        errors = self.validate(
            {
                "software": {
                    "quda": {"commit": "abc123", "branch": "feature/example"}
                }
            },
            expected_software="quda",
            default_branches={"quda": "develop"},
        )
        self.assertTrue(any("forked_from_default" in error for error in errors))

    def test_project_default_branch_does_not_require_fork_point(self):
        errors = self.validate(
            {"software": {"qmp": {"commit": "abc123", "branch": "master"}}},
            expected_software="qmp",
            default_branches={"qmp": "master"},
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
