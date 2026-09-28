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
PROFILE = ROOT / "machines/vista/machine.yaml"


class VistaMachineTests(unittest.TestCase):
    def test_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(PROFILE.read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def test_profile_records_both_node_types(self):
        profile = yaml.safe_load(PROFILE.read_text())
        nodes = profile["node_types"]
        self.assertEqual(sorted(nodes), ["cpu-gg", "gpu-gh200"])
        self.assertEqual(nodes["gpu-gh200"]["sizing"]["installed_nodes"], 600)
        self.assertEqual(nodes["cpu-gg"]["sizing"]["installed_nodes"], 256)
        # One GPU per node: the value most likely to be carried over wrongly from a
        # four-way GH200 machine.
        self.assertEqual(nodes["gpu-gh200"]["accelerator"]["per_node"], 1)
        self.assertEqual(nodes["gpu-gh200"]["accelerator"]["arch"], "sm_90")
        self.assertIsNone(nodes["cpu-gg"]["accelerator"])

    def test_multiple_node_types_require_explicit_declaration(self):
        notes = " ".join((ROOT / "machines/vista/notes.md").read_text().split())
        self.assertIn("explicitly", notes)
        self.assertNotIn("No separate operator declaration is needed", notes)

    def test_launcher_is_not_overridden_without_a_modelled_harness(self):
        # The dry-run harness stubs the surface's parallel_launcher with srun's step
        # semantics; naming ibrun there would model it with rules nobody established.
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertNotIn("parallel_launcher", profile["scheduler"])

    def test_ibrun_is_the_recorded_site_launcher_and_can_never_overlap(self):
        # The harness stubs it from this record; a null overlap option is what makes a
        # second concurrent call refusable, so it must stay an explicit null.
        profile = yaml.safe_load(PROFILE.read_text())
        launcher = profile["scheduler"]["site_launcher"]
        self.assertEqual(launcher["command"], "ibrun")
        self.assertIn("overlap_option", launcher)
        self.assertIsNone(launcher["overlap_option"])
        self.assertNotIn("parallel_launch", profile["site_policy"])

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

    def test_detector_recognizes_login_and_compute_hosts(self):
        for hostname in (
            "vista.tacc.utexas.edu",
            "login2.vista.tacc.utexas.edu",
            "c123-456.vista.tacc.utexas.edu",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "vista")

    def test_detector_does_not_claim_other_tacc_systems(self):
        for hostname in (
            "stampede3.tacc.utexas.edu",
            "login1.frontera.tacc.utexas.edu",
            "notvista.tacc.utexas.edu",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "unknown")


if __name__ == "__main__":
    unittest.main()
