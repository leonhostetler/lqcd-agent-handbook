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
PROFILE = ROOT / "machines/horizon/machine.yaml"
NOTES = ROOT / "machines/horizon/notes.md"


class HorizonMachineTests(unittest.TestCase):
    def test_profile_matches_machine_schema(self):
        schema = json.loads((ROOT / "schemas/machine.schema.json").read_text())
        profile = yaml.safe_load(PROFILE.read_text())
        problems = list(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(profile)
        )
        self.assertEqual(problems, [])

    def test_profile_records_both_documented_node_types(self):
        profile = yaml.safe_load(PROFILE.read_text())
        nodes = profile["node_types"]
        self.assertEqual(sorted(nodes), ["cpu-vv", "gpu-gb200"])
        self.assertEqual(nodes["gpu-gb200"]["sizing"]["installed_nodes"], 2000)
        self.assertEqual(nodes["cpu-vv"]["sizing"]["installed_nodes"], 4752)
        # The documented node holds two GPUs; the early-access scheduler node holds four.
        # The profile carries the documented value and notes.md carries the live one, so a
        # change here must be deliberate and made with the notes table.
        self.assertEqual(nodes["gpu-gb200"]["accelerator"]["per_node"], 2)
        self.assertEqual(nodes["gpu-gb200"]["accelerator"]["arch"], "sm_100")
        self.assertIsNone(nodes["cpu-vv"]["accelerator"])

    def test_notes_carry_the_early_access_drift_before_the_node_target(self):
        body = NOTES.read_text().split("\n---\n", 1)[1]
        sections = body.split("\n## ")
        titles = [section.split("\n", 1)[0] for section in sections[1:]]
        self.assertTrue(titles[0].startswith("Early access"), titles)
        early = " ".join(sections[1].split())
        self.assertIn("four GPUs", early)
        self.assertIn("`debug`", early)

    def test_multiple_node_types_require_explicit_declaration(self):
        notes = " ".join(NOTES.read_text().split())
        self.assertIn("explicitly", notes)

    def test_unavailable_work_filesystem_declares_no_variable(self):
        # During early access the shell sets WORK to a path that does not exist, so the
        # profile must not license a script to reference it.
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertNotIn("environment_variable", profile["filesystems"]["work"])
        declared = {
            fs.get("environment_variable") for fs in profile["filesystems"].values()
        }
        self.assertNotIn("WORK", declared)

    def test_ibrun_is_the_recorded_site_launcher_and_can_never_overlap(self):
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertNotIn("parallel_launcher", profile["scheduler"])
        launcher = profile["scheduler"]["site_launcher"]
        self.assertEqual(launcher["command"], "ibrun")
        self.assertIn("overlap_option", launcher)
        self.assertIsNone(launcher["overlap_option"])

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

    def test_detector_recognizes_horizon_hosts(self):
        for hostname in (
            "horizon.tacc.utexas.edu",
            "login1.horizon.tacc.utexas.edu",
            "c123-456.horizon.tacc.utexas.edu",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "horizon")

    def test_detector_does_not_claim_other_tacc_systems(self):
        for hostname in (
            "login2.vista.tacc.utexas.edu",
            "stampede3.tacc.utexas.edu",
            "nothorizon.tacc.utexas.edu",
        ):
            with self.subTest(hostname=hostname):
                self.assertNotEqual(self.run_detector(hostname), "horizon")


if __name__ == "__main__":
    unittest.main()
