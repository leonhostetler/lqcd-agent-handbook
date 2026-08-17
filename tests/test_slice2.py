#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_knowledge_slice2", ROOT / "tools/validate-knowledge.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class SliceTwoStackTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "schemas/stack.schema.json").read_text())
        self.stack_paths = sorted(ROOT.glob("machines/*/stacks/*/stack.yaml"))

    def test_schema_is_bound_and_both_vendor_stacks_validate(self):
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        validator = Draft202012Validator(
            self.schema, format_checker=FormatChecker()
        )
        self.assertEqual(manifest["schema_versions"]["stack"], 1)
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(len(self.stack_paths), 2)
        for path in self.stack_paths:
            with self.subTest(path=path):
                problems = list(validator.iter_errors(yaml.safe_load(path.read_text())))
                self.assertEqual(problems, [])

    def test_schema_uses_values_not_vendor_specific_structure(self):
        stacks = [yaml.safe_load(path.read_text()) for path in self.stack_paths]
        self.assertEqual({stack["build"]["target"] for stack in stacks}, {"CUDA", "HIP"})
        target_schema = self.schema["$defs"]["build"]["properties"]["target"]
        self.assertEqual(target_schema, {"type": "string", "minLength": 1})
        self.assertNotIn("gpu_arch", self.schema["$defs"]["build"]["required"])

    def test_stack_cross_references_are_complete(self):
        errors: list[str] = []
        count = VALIDATOR.validate_schemas(ROOT, errors)
        self.assertEqual(count, 8)
        self.assertEqual(errors, [])

    def test_frontier_stack_records_runtime_evidence_and_limits(self):
        stack = yaml.safe_load(
            (
                ROOT
                / "machines/frontier/stacks/quda-rocm7-milc-cg-2026q3/stack.yaml"
            ).read_text()
        )
        self.assertEqual(stack["validated_on"], ["gpu-mi250x"])
        self.assertEqual(stack["validation"]["resources"]["mpi_ranks"], 8)
        self.assertEqual(stack["validation"]["runtime"]["QUDA_ENABLE_P2P"], 0)
        self.assertEqual(
            [test["result"] for test in stack["validation"]["tests"]],
            ["pass", "pass", "pass"],
        )
        self.assertTrue(
            any(
                "no MILC executable" in limit
                for limit in stack["validation"]["scope_limits"]
            )
        )

    def test_frontier_notes_pin_scheduler_paths_to_working_project(self):
        notes = (
            ROOT
            / "machines/frontier/stacks/quda-rocm7-milc-cg-2026q3/notes.md"
        ).read_text()
        self.assertIn('--chdir="$working_directory"', notes)
        self.assertIn('--output="$validation_directory/slurm-%j.out"', notes)
        self.assertIn("An absolute script path does not set Slurm's working directory", notes)

    def test_shared_build_playbook_did_not_gain_machine_branches(self):
        playbook = (ROOT / "playbooks/build-lqcd-stack.md").read_text().casefold()
        self.assertNotIn("frontier", playbook)
        self.assertNotIn("perlmutter", playbook)


class SliceTwoIndexTests(unittest.TestCase):
    def run_indexer(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(root / "tools/build-index.py"), *args, "--root", str(root)],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_committed_grouped_indexes_are_current(self):
        result = self.run_indexer(ROOT, "--check")
        self.assertEqual(result.returncode, 0, result.stdout)
        machines = (ROOT / "machines/INDEX.md").read_text()
        software = (ROOT / "software/INDEX.md").read_text()
        self.assertIn("## frontier", machines)
        self.assertIn("## perlmutter", machines)
        self.assertIn("## quda", software)
        frontier_stack = "QUDA ROCm 7 milc-cg stack on Frontier"
        self.assertIn(frontier_stack, machines)
        self.assertIn(frontier_stack, software)

    def test_index_check_detects_and_repairs_frontmatter_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copy = Path(temp_dir) / "handbook"
            shutil.copytree(
                ROOT,
                copy,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            notes = copy / "machines/frontier/notes.md"
            notes.write_text(notes.read_text().replace("Compute-target", "GPU-target", 1))

            stale = self.run_indexer(copy, "--check")
            self.assertEqual(stale.returncode, 1, stale.stdout)
            self.assertIn("stale generated index: machines/INDEX.md", stale.stdout)

            rebuilt = self.run_indexer(copy)
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stdout)
            current = self.run_indexer(copy, "--check")
            self.assertEqual(current.returncode, 0, current.stdout)


class SliceTwoRestatementTests(unittest.TestCase):
    def make_candidate(self, root: Path, notes_text: str) -> None:
        machine = root / "machines/example"
        machine.mkdir(parents=True)
        (machine / "machine.yaml").write_text(
            "schema_version: 1\n"
            "name: example\n"
            "node_types:\n"
            "  gpu:\n"
            "    accelerator:\n"
            "      memory_gb: 64\n"
        )
        (machine / "notes.md").write_text(notes_text)

    def test_p2_heuristic_warns_on_unpointed_numeric_restatement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_candidate(root, "Use the 64 GB device.\n")
            warnings: list[str] = []
            count = VALIDATOR.validate_restatements(root, warnings)
            self.assertEqual(count, 1)
            self.assertIn("P2 advisory", warnings[0])
            self.assertIn("machine.yaml", warnings[0])

    def test_p2_heuristic_accepts_canonical_pointer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_candidate(
                root,
                "The machine profile is canonical; it records a 64 GB device.\n",
            )
            warnings: list[str] = []
            count = VALIDATOR.validate_restatements(root, warnings)
            self.assertEqual(count, 0)
            self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
