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


if __name__ == "__main__":
    unittest.main()
