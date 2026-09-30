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
PROFILE = ROOT / "machines/aurora/machine.yaml"
NOTES = ROOT / "machines/aurora/notes.md"
SURFACES = ROOT / "conventions/scheduler-surfaces.yaml"


class AuroraMachineTests(unittest.TestCase):
    def test_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(PROFILE.read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def test_profile_records_the_single_documented_node_type(self):
        profile = yaml.safe_load(PROFILE.read_text())
        nodes = profile["node_types"]
        # One node type makes it the session default; a second would require declaration.
        self.assertEqual(sorted(nodes), ["gpu-pvc"])
        node = nodes["gpu-pvc"]
        self.assertEqual(node["sizing"]["installed_nodes"], 10624)
        self.assertEqual(node["accelerator"]["vendor"], "intel")
        self.assertEqual(node["accelerator"]["arch"], "pvc")
        self.assertEqual(node["accelerator"]["per_node"], 6)
        self.assertEqual(node["accelerator"]["tiles_per_gpu"], 2)
        self.assertEqual(node["sizing"]["reserved_cpus"], [0, 52, 104, 156])

    def test_scheduler_is_pbs_with_a_recorded_surface(self):
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertEqual(profile["scheduler"]["type"], "pbs")
        surfaces = yaml.safe_load(SURFACES.read_text())["surfaces"]
        self.assertIn("pbs", surfaces)
        # The tools now check and guard Aurora scripts, so the leaf must not say otherwise.
        notes = " ".join(NOTES.read_text().split())
        self.assertNotIn("does not intercept `qsub`", notes)

    def test_pals_mpiexec_is_the_site_launcher_and_its_launches_share(self):
        profile = yaml.safe_load(PROFILE.read_text())
        # MPI launch belongs to the site: the pbs surface names no parallel launcher.
        surfaces = yaml.safe_load(SURFACES.read_text())["surfaces"]
        self.assertNotIn("parallel_launcher", surfaces["pbs"])
        launcher = profile["scheduler"]["site_launcher"]
        self.assertEqual(launcher["command"], "mpiexec")
        self.assertIsNone(launcher["overlap_option"])
        self.assertIs(launcher["steps_share_allocation"], True)

    def test_flare_declares_no_environment_variable(self):
        # The site sets none, so the profile must not license a script to reference one.
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertNotIn("environment_variable", profile["filesystems"]["flare"])

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

    def test_detector_recognizes_aurora_hosts(self):
        for hostname in (
            "aurora.alcf.anl.gov",
            "node.aurora.alcf.anl.gov",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "aurora")

    def test_detector_does_not_claim_other_alcf_systems(self):
        for hostname in (
            "polaris.alcf.anl.gov",
            "sunspot.alcf.anl.gov",
            "notaurora.alcf.anl.gov",
            "aurora.example.org",
        ):
            with self.subTest(hostname=hostname):
                self.assertNotEqual(self.run_detector(hostname), "aurora")


if __name__ == "__main__":
    unittest.main()
