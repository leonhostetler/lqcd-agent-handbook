#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

import pathlib  # noqa: E402
# Guard the in-process imports below. Choosing another interpreter cannot help here --
# these must import in *this* one -- so an absent dependency becomes a loud module skip
# rather than a collection error naming a missing module instead of a behaviour.
import importlib.util as _dep_util  # noqa: E402
_DEP_SUPPORT_SPEC = _dep_util.spec_from_file_location(
    "handbook_dep_guard", pathlib.Path(__file__).resolve().parents[1] / "tests/support.py"
)
_DEP_SUPPORT = _dep_util.module_from_spec(_DEP_SUPPORT_SPEC)
assert _DEP_SUPPORT_SPEC.loader is not None
_DEP_SUPPORT_SPEC.loader.exec_module(_DEP_SUPPORT)
_DEP_SUPPORT.require_importable("yaml", "jsonschema")

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


class FrontierMachineTests(unittest.TestCase):
    def test_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(
            (ROOT / "machines/frontier/machine.yaml").read_text()
        )
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def test_profile_records_installed_nodes(self):
        profile = yaml.safe_load(
            (ROOT / "machines/frontier/machine.yaml").read_text()
        )
        self.assertEqual(
            profile["node_types"]["gpu-mi250x"]["sizing"]["installed_nodes"],
            9856,
        )

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
        for hostname in (
            "frontier.olcf.ornl.gov",
            "login07.frontier.olcf.ornl.gov",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "frontier")

    def test_detector_recognizes_compute_hostname(self):
        self.assertEqual(self.run_detector("frontier01234"), "frontier")


if __name__ == "__main__":
    unittest.main()
