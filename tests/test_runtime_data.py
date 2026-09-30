#!/usr/bin/env python3
"""The runtime-data projection and the standard-library rule for operational tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
GENERATOR = TOOLS / "build-runtime-data.py"
VALIDATOR = TOOLS / "validate-knowledge.py"

sys.path.insert(0, str(TOOLS))
import runtime_data  # noqa: E402


def generator_root(temp: Path) -> Path:
    """The smallest tree the generator reads: the manifest, the surfaces, the profiles."""
    root = temp / "handbook"
    (root / "tools").mkdir(parents=True)
    for name in ("build-runtime-data.py", "runtime_data.py"):
        shutil.copy2(TOOLS / name, root / "tools" / name)
    shutil.copy2(ROOT / "handbook.yaml", root / "handbook.yaml")
    (root / "conventions").mkdir()
    shutil.copy2(ROOT / "conventions/scheduler-surfaces.yaml", root / "conventions")
    for profile in (ROOT / "machines").glob("*/machine.yaml"):
        target = root / "machines" / profile.parent.name
        target.mkdir(parents=True)
        shutil.copy2(profile, target / "machine.yaml")
    shutil.copytree(ROOT / "tools/generated", root / "tools/generated")
    return root


class GeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.python = interpreter_for("yaml")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = generator_root(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def generate(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([self.python, str(self.root / "tools/build-runtime-data.py"),
                               "--root", str(self.root), *args],
                              text=True, capture_output=True, check=False)

    def test_the_committed_projection_is_current(self):
        result = subprocess.run([self.python, str(GENERATOR), "--check", "--root", str(ROOT)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_changed_profile_is_stale_until_regenerated(self):
        self.assertEqual(self.generate("--check").returncode, 0)  # control: the copy is current
        profile = self.root / "machines/perlmutter/machine.yaml"
        profile.write_text(profile.read_text() + "lqcd_test_marker: 1\n")
        stale = self.generate("--check")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("tools/generated/machines/perlmutter.json: stale", stale.stdout)
        self.assertEqual(self.generate().returncode, 0)
        self.assertEqual(self.generate("--check").returncode, 0)
        self.assertEqual(runtime_data.machine(self.root, "perlmutter")["lqcd_test_marker"], 1)

    def test_a_file_no_source_produces_is_reported_then_removed(self):
        ghost = self.root / "tools/generated/machines/ghost.json"
        ghost.write_text("{}\n")
        result = self.generate("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ghost.json: no source produces it", result.stdout)
        self.assertEqual(self.generate().returncode, 0)
        self.assertFalse(ghost.exists())

    def test_a_date_becomes_an_iso_string(self):
        surfaces = self.root / "conventions/scheduler-surfaces.yaml"
        surfaces.write_text(surfaces.read_text() + "lqcd_test_date: 2026-08-28\n")
        self.assertEqual(self.generate().returncode, 0)
        self.assertEqual(runtime_data.scheduler_surfaces(self.root)["lqcd_test_date"], "2026-08-28")

    def test_a_value_json_cannot_represent_stops_the_build(self):
        surfaces = self.root / "conventions/scheduler-surfaces.yaml"
        before = (self.root / runtime_data.SCHEDULER_SURFACES).read_text()
        surfaces.write_text(surfaces.read_text() + "lqcd_test_blob: !!binary aGVsbG8=\n")
        result = self.generate()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("conventions/scheduler-surfaces.yaml.lqcd_test_blob", result.stderr)
        self.assertEqual((self.root / runtime_data.SCHEDULER_SURFACES).read_text(), before)

    def test_projection_is_one_key_per_line(self):
        # A search match in a one-line file would return the whole file.
        text = (ROOT / runtime_data.machine_path("perlmutter")).read_text()
        self.assertGreater(text.count("\n"), 20)
        self.assertLess(max(len(line) for line in text.splitlines()), 400)


class LoaderTests(unittest.TestCase):
    def test_a_missing_projection_names_the_generator(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(runtime_data.RuntimeDataError, "build-runtime-data.py"):
                runtime_data.handbook(Path(temp))

    def test_an_unprofiled_machine_is_none_but_a_stale_one_raises(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertIsNone(runtime_data.machine(root, "nowhere"))
            (root / "machines/nowhere").mkdir(parents=True)
            (root / "machines/nowhere/machine.yaml").write_text("scheduler: {type: slurm}\n")
            with self.assertRaises(runtime_data.RuntimeDataError):
                runtime_data.machine(root, "nowhere")


class OperationalToolsRunWithoutSitePackages(unittest.TestCase):
    """`-S` hides every installed package, which is a machine with a bare system Python."""

    @classmethod
    def setUpClass(cls) -> None:
        control = subprocess.run([sys.executable, "-S", "-c", "import yaml"],
                                 capture_output=True, check=False)
        if control.returncode == 0:
            raise unittest.SkipTest("PyYAML imports even with -S; this check cannot fail here")

    def run_bare(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        return subprocess.run([sys.executable, "-S", *args], input=stdin, text=True,
                              capture_output=True, cwd=ROOT, env=env, check=False)

    def assert_no_import_failure(self, result: subprocess.CompletedProcess[str]) -> None:
        output = result.stdout + result.stderr
        self.assertNotIn("ModuleNotFoundError", output)
        self.assertNotIn("Traceback", output)

    def test_the_checker_reads_a_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "job.sh"
            script.write_text("#!/bin/bash\nset -euo pipefail\necho hello\n")
            result = self.run_bare(str(TOOLS / "check-batch-script.py"), str(script),
                                   "--machine", "perlmutter")
        self.assert_no_import_failure(result)

    def test_the_guard_reads_the_surfaces_and_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            event = json.dumps({"tool_input": {"command": "sbatch job.sh"}, "cwd": temp})
            (Path(temp) / "job.sh").write_text("#!/bin/bash\n")
            result = self.run_bare(str(TOOLS / "submission-guard.py"), "--machine", "perlmutter",
                                   stdin=event)
        self.assert_no_import_failure(result)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_the_startup_checkers_and_installers_load(self):
        with tempfile.TemporaryDirectory() as temp:
            for tool in ("check-session-logging.py", "check-submission-guard.py"):
                with self.subTest(tool=tool):
                    result = self.run_bare(str(TOOLS / tool), "--frontend", "claude",
                                           "--user-root", temp, "--handbook-root", str(ROOT))
                    self.assert_no_import_failure(result)
                    self.assertEqual(result.returncode, 0, result.stderr)
        for tool in ("install-session-logging.py", "install-submission-guard.py",
                     "dry-run-batch-script.py"):
            with self.subTest(tool=tool):
                result = self.run_bare(str(TOOLS / tool), "--help")
                self.assert_no_import_failure(result)
                self.assertEqual(result.returncode, 0, result.stderr)


IMPORT_CHECK = """
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("validate_knowledge", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
errors = []
count = module.validate_operational_imports(Path(sys.argv[2]), errors)
print(json.dumps({"count": count, "errors": errors}))
"""


class OperationalImportRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.python = interpreter_for("yaml", "jsonschema")
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "handbook"
        shutil.copytree(TOOLS, self.root / "tools",
                        ignore=shutil.ignore_patterns("__pycache__", "generated"))
        shutil.copy2(ROOT / "handbook.yaml", self.root / "handbook.yaml")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def check(self) -> dict:
        result = subprocess.run([self.python, "-c", IMPORT_CHECK, str(VALIDATOR), str(self.root)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def add_to_guard(self, text: str) -> None:
        guard = self.root / "tools/submission-guard.py"
        guard.write_text(guard.read_text() + text)

    def test_the_listed_tools_pass(self):
        report = self.check()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["count"], 10)

    def test_a_lazy_third_party_import_is_caught(self):
        self.add_to_guard("\n\ndef later():\n    import yaml\n    return yaml\n")
        errors = self.check()["errors"]
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("tools/submission-guard.py", errors[0])
        self.assertIn("imports yaml", errors[0])

    def test_a_local_module_that_is_not_listed_is_caught(self):
        self.add_to_guard("\n\nimport quda_staggered_geometry\n")
        errors = self.check()["errors"]
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("quda_staggered_geometry", errors[0])

    def test_tomli_is_the_one_exception(self):
        self.add_to_guard("\n\ndef toml():\n    import tomli\n    return tomli\n")
        self.assertEqual(self.check()["errors"], [])


if __name__ == "__main__":
    unittest.main()
