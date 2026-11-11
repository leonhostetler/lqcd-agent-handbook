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
PROFILE = ROOT / "machines/big-red-200/machine.yaml"
NOTES = ROOT / "machines/big-red-200/notes.md"


class BigRed200MachineTests(unittest.TestCase):
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
        self.assertEqual(sorted(nodes), ["cpu", "gpu-a100-40"])
        self.assertEqual(nodes["cpu"]["sizing"]["installed_nodes"], 640)
        self.assertEqual(nodes["gpu-a100-40"]["sizing"]["installed_nodes"], 64)
        self.assertEqual(nodes["gpu-a100-40"]["accelerator"]["per_node"], 4)
        self.assertEqual(nodes["gpu-a100-40"]["accelerator"]["arch"], "sm_80")
        self.assertIsNone(nodes["cpu"]["accelerator"])

    def test_core_counted_cpus_are_not_recorded_as_logical_cpus(self):
        # The scheduler counts cores as CPUs on a two-thread-per-core node. Recording
        # logical_cpus_per_node would let check-batch-script.py compare a core-counted
        # request against a thread count, which is the wrong unit in both directions.
        profile = yaml.safe_load(PROFILE.read_text())
        for name, node in profile["node_types"].items():
            with self.subTest(node_type=name):
                sizing = node["sizing"]
                self.assertNotIn("logical_cpus_per_node", sizing)
                self.assertEqual(sizing["scheduler_cpus_per_node"], sizing["physical_cpu_cores"])

    def test_multiple_node_types_require_explicit_declaration(self):
        notes = " ".join(NOTES.read_text().split())
        self.assertIn("select one explicitly", notes)
        self.assertNotIn("No separate operator declaration is needed", notes)

    def test_node_local_tmp_variable_is_recorded_as_none(self):
        # Read inside a gpu-debug job: the scheduler exports no node-local temporary
        # directory variable. null states that; an absent key would mean unestablished.
        profile = yaml.safe_load(PROFILE.read_text())
        self.assertIn("node_local_tmp_variable", profile["scheduler"])
        self.assertIsNone(profile["scheduler"]["node_local_tmp_variable"])

    def test_gpu_node_records_confirmed_topology(self):
        gpu = yaml.safe_load(PROFILE.read_text())["node_types"]["gpu-a100-40"]
        self.assertEqual(gpu["accelerator"]["memory_gb"], 40)
        self.assertEqual(gpu["sizing"]["numa_domains"], 4)
        self.assertEqual(gpu["sizing"]["network_interfaces_per_node"], 2)
        notes = " ".join(NOTES.read_text().split())
        self.assertIn("GPU affinity runs opposite to Slurm's rank order", notes)

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

    def test_detector_recognizes_big_red_200_hosts(self):
        for hostname in (
            "bigred200.uits.iu.edu",
            "login1.bigred200.uits.iu.edu",
            "login2.bigred200.uits.iu.edu",
            "node.subdomain.bigred200.uits.iu.edu",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "big-red-200")

    def test_detector_does_not_claim_other_iu_systems(self):
        for hostname in (
            "quartz.uits.iu.edu",
            "h1.quartz.uits.iu.edu",
            "notbigred200.uits.iu.edu",
            "bigred200.uits.iu.edu.example.org",
        ):
            with self.subTest(hostname=hostname):
                self.assertEqual(self.run_detector(hostname), "unknown")


if __name__ == "__main__":
    unittest.main()
