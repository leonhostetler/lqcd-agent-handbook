#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


class DeltaAIMachineTests(unittest.TestCase):
    def test_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(
            (ROOT / "machines/deltaai/machine.yaml").read_text()
        )
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def run_detector(self, hostname: str) -> str:
        env = os.environ.copy()
        env.pop("NERSC_HOST", None)
        env["LQCD_DETECT_NERSC_HOST"] = ""
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

    def test_detector_recognizes_public_login_hosts(self):
        hostnames = ["dtai-login.delta.ncsa.illinois.edu"]
        hostnames.extend(
            f"gh-login{number:02d}.delta.ncsa.illinois.edu"
            for number in range(1, 5)
        )
        for hostname in hostnames:
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "deltaai")

    def test_detector_does_not_conflate_delta_with_deltaai(self):
        self.assertEqual(
            self.run_detector("login.delta.ncsa.illinois.edu"), "unknown"
        )

    def test_profile_records_gh200_resource_shape(self):
        profile = yaml.safe_load(
            (ROOT / "machines/deltaai/machine.yaml").read_text()
        )
        node = profile["node_types"]["gpu-gh200"]
        self.assertEqual(node["sizing"]["installed_nodes"], 152)
        self.assertEqual(node["cpu"]["cores_per_socket"], 72)
        self.assertEqual(node["accelerator"]["per_node"], 4)
        self.assertEqual(node["accelerator"]["memory_gb"], 96)
        self.assertEqual(node["build_constraints"]["cpu_arch"], "aarch64")

    def test_quda_stack_records_runtime_evidence_and_scope_limits(self):
        stack = yaml.safe_load(
            (
                ROOT
                / "machines/deltaai/stacks/quda-cuda12-milc-cg-2026q3/stack.yaml"
            ).read_text()
        )
        self.assertEqual(stack["validated_on"], ["gpu-gh200"])
        self.assertEqual(
            stack["tested_software"]["quda"]["commit"],
            "b6998853f6b605e22d67ea2ddfa3cab0d752679a",
        )
        self.assertEqual(stack["build"]["gpu_arch"], "sm_90")
        self.assertEqual(
            stack["validation"]["resources"]["partition"],
            "ghx4-interactive",
        )
        self.assertEqual(
            [test["result"] for test in stack["validation"]["tests"]],
            ["pass", "pass", "pass"],
        )
        self.assertLessEqual(
            stack["validation"]["tests"][1]["true_l2_relative_residual"],
            stack["validation"]["tests"][1]["requested_l2_relative_residual"],
        )
        self.assertTrue(
            any(
                "no MILC executable" in limit
                for limit in stack["validation"]["scope_limits"]
            )
        )

    def test_quda_stack_notes_preserve_tested_interactive_placement(self):
        notes = (
            ROOT
            / "machines/deltaai/stacks/quda-cuda12-milc-cg-2026q3/notes.md"
        ).read_text()
        self.assertIn("#SBATCH --partition=ghx4-interactive", notes)
        self.assertIn("#SBATCH --gpu-bind=none", notes)
        self.assertIn("tuning-candidate regression warning", notes)


if __name__ == "__main__":
    unittest.main()
