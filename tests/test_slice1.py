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


if __name__ == "__main__":
    unittest.main()
