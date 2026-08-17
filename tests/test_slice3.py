#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_knowledge_slice3", ROOT / "tools/validate-knowledge.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class SliceThreeProfileTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(
            (ROOT / "schemas/build-profiles.schema.json").read_text()
        )
        self.profile_paths = sorted(ROOT.glob("software/*/build-profiles.yaml"))

    def test_schema_is_bound_to_profiles_in_two_software_contexts(self):
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )
        self.assertEqual(manifest["schema_versions"]["build_profiles"], 1)
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(
            {path.parent.name for path in self.profile_paths}, {"milc", "quda"}
        )
        for path in self.profile_paths:
            with self.subTest(path=path):
                problems = list(validator.iter_errors(yaml.safe_load(path.read_text())))
                self.assertEqual(problems, [])

    def test_milc_profile_composes_the_validated_quda_profile(self):
        milc = yaml.safe_load(
            (ROOT / "software/milc/build-profiles.yaml").read_text()
        )["profiles"]["ks-spectrum-hisq-quda"]
        quda = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]["milc-cg"]
        composition = milc["composes"]["quda"]
        self.assertEqual(composition["profile"], "milc-cg")
        for capability, required in composition["required_capabilities"].items():
            self.assertLessEqual(set(required), set(quda["capabilities"][capability]))

    def test_validator_rejects_a_missing_composed_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            path = copy / "software/milc/build-profiles.yaml"
            record = yaml.safe_load(path.read_text())
            record["profiles"]["ks-spectrum-hisq-quda"]["composes"]["quda"][
                "profile"
            ] = "missing-profile"
            errors: list[str] = []
            VALIDATOR.validate_build_profile_references(copy, path, record, errors)
            self.assertTrue(any("composes missing profile" in error for error in errors))

    def test_dependency_projects_validate_and_record_exact_revisions(self):
        schema = json.loads((ROOT / "schemas/project.schema.json").read_text())
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        expected = {
            "qmp": "3010fef5b5784b3e6eeec9fff38cb9954a28ad42",
            "qio": "273841537392f9465d229c957228755e923408eb",
        }
        for name, commit in expected.items():
            with self.subTest(name=name):
                project = yaml.safe_load(
                    (ROOT / f"software/{name}/project.yaml").read_text()
                )
                self.assertEqual(list(validator.iter_errors(project)), [])
                self.assertEqual(project["default_branch"], "master")
                self.assertEqual(
                    project["observed_on"]["software"][name]["commit"], commit
                )


class SliceThreeFrontierStackTests(unittest.TestCase):
    def setUp(self):
        self.stack_path = (
            ROOT
            / "machines/frontier/stacks/"
            "milc-rocm7-quda-ks-spectrum-2026q3/stack.yaml"
        )
        self.stack = yaml.safe_load(self.stack_path.read_text())

    def test_composed_stack_cross_references_are_complete(self):
        errors: list[str] = []
        count = VALIDATOR.validate_schemas(ROOT, errors)
        self.assertEqual(count, 17)
        self.assertEqual(errors, [])
        self.assertIn("quda", self.stack["tested_software"])

    def test_frontier_payload_and_quda_solves_pass(self):
        self.assertEqual(self.stack["validation"]["result"], "pass")
        runtime = self.stack["validation"]["runtime"]
        self.assertEqual(runtime["application_payload_exit_code"], 0)
        self.assertEqual(runtime["outer_harness_exit_code"], 1)
        cg = next(
            test
            for test in self.stack["validation"]["tests"]
            if test["name"] == "quda_cg_convergence"
        )
        self.assertEqual(cg["solves"], 24)
        self.assertEqual(cg["convergence_markers"], cg["solves"])
        self.assertLessEqual(
            float(cg["maximum_true_residual"]),
            float(cg["requested_true_residual"]),
        )

    def test_runtime_scope_does_not_overclaim_linked_features(self):
        limits = " ".join(self.stack["validation"]["scope_limits"]).casefold()
        self.assertIn("qio was linked", limits)
        self.assertIn("did not exercise qio", limits)
        self.assertIn("smearing", limits)
        self.assertIn("reference correlator values", limits)
        self.assertIn("gauge-fixing", limits)
        self.assertIn("p2p-disabled", limits)
        self.assertIn("not benchmark evidence", limits)

    def test_total_iters_false_negative_is_documented(self):
        build = (ROOT / "software/milc/build.md").read_text()
        notes = self.stack_path.with_name("notes.md").read_text()
        self.assertIn("`total_iters` is not an acceptance signal", build)
        self.assertIn("Do not require positive MILC `total_iters`", notes)
        self.assertIn("payload exited zero", self.stack["validation"]["scope_limits"][-1])


class SliceThreePerlmutterStackTests(unittest.TestCase):
    def setUp(self):
        self.stack_path = (
            ROOT
            / "machines/perlmutter/stacks/"
            "milc-cuda12-quda-ks-spectrum-2026q3/stack.yaml"
        )
        self.stack = yaml.safe_load(self.stack_path.read_text())

    def test_perlmutter_payload_and_quda_solves_pass(self):
        self.assertEqual(self.stack["validation"]["result"], "pass")
        runtime = self.stack["validation"]["runtime"]
        self.assertEqual(runtime["application_payload_exit_code"], 0)
        self.assertEqual(runtime["outer_harness_exit_code"], 1)
        cg = next(
            test
            for test in self.stack["validation"]["tests"]
            if test["name"] == "quda_cg_convergence"
        )
        self.assertEqual(cg["solves"], 24)
        self.assertEqual(cg["convergence_markers"], cg["solves"])
        self.assertLessEqual(
            float(cg["maximum_true_residual"]),
            float(cg["requested_true_residual"]),
        )

    def test_perlmutter_runtime_scope_is_explicit(self):
        limits = " ".join(self.stack["validation"]["scope_limits"]).casefold()
        self.assertIn("did not exercise qio", limits)
        self.assertIn("smearing", limits)
        self.assertIn("reference correlator values", limits)
        self.assertIn("gauge-fixing", limits)
        self.assertIn("p2p-enabled", limits)
        self.assertIn("not benchmark evidence", limits)
        self.assertIn("no runtime memory measurement", limits)

    def test_perlmutter_harness_false_negative_is_documented(self):
        notes = self.stack_path.with_name("notes.md").read_text()
        runtime = self.stack["validation"]["runtime"]
        self.assertIn("`FLTIME: ... (HISQ QUDA D)`", notes)
        self.assertIn("wrapper false negative", notes)
        self.assertIn("non-literal FLTIME marker", runtime["outer_harness_result"])


if __name__ == "__main__":
    unittest.main()
