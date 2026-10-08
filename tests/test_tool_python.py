#!/usr/bin/env python3
"""The handbook tool Python: select-python probes it first, setup-tool-python builds it."""

from __future__ import annotations

import hashlib
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
SELECT_PYTHON = ROOT / "tools" / "select-python"
SETUP = ROOT / "tools" / "setup-tool-python"
REQUIREMENTS = ROOT / "tools" / "requirements.txt"
MARKER = "lqcd-tool-python.requirements.sha256"
REPORT_MARK = "import os; print(os.environ.get('LQCD_TEST_MARK'))"


def environment(tool_dir: Path, path: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["LQCD_HANDBOOK_TOOL_PYTHON"] = str(tool_dir)
    if path is not None:
        env["PATH"] = path
    # A site shell-init file sourced by every non-interactive bash is unrelated to what
    # these tests check, and under a stubbed PATH it writes noise into their output.
    env.pop("BASH_ENV", None)
    return env


def fake_interpreter(tool_dir: Path, target: str, prelude: str = "") -> None:
    """A tool Python whose interpreter is `target`, marking the processes it runs."""
    bin_dir = tool_dir / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    python.write_text(
        f"#!/bin/sh\n{prelude}export LQCD_TEST_MARK=tool\nexec '{target}' \"$@\"\n"
    )
    python.chmod(0o700)


def select(env: dict[str, str], *options: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(SELECT_PYTHON), "--require", "json", *options, "--", "-c", REPORT_MARK],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def interpreter_dir() -> str:
    return str(Path(sys.executable).parent)


class SelectPythonToolPythonTests(unittest.TestCase):
    def test_a_qualifying_tool_python_is_preferred_to_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            fake_interpreter(tool_dir, sys.executable)
            result = select(environment(tool_dir))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "tool\n")

    def test_without_a_tool_python_path_is_used(self):
        # The control for the test above: the mark comes from the tool Python, not from
        # anything else in the environment.
        with tempfile.TemporaryDirectory() as temp_dir:
            result = select(environment(Path(temp_dir) / "absent"))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "None\n")

    def test_a_tool_python_that_emits_diagnostics_is_passed_over(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            fake_interpreter(tool_dir, sys.executable, prelude="echo 'site diagnostic'\n")
            result = select(environment(tool_dir))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "None\n")

    def test_a_tool_python_missing_a_requirement_is_passed_over(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            fake_interpreter(tool_dir, sys.executable)
            env = environment(tool_dir)
            result = subprocess.run(
                ["/bin/bash", str(SELECT_PYTHON), "--require", "lqcd_no_such_module",
                 "--", "-c", REPORT_MARK],
                env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("(tool Python)", result.stderr)
            self.assertIn("tools/setup-tool-python --check says why", result.stderr)

    def test_the_opt_out_skips_the_tool_python(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            fake_interpreter(tool_dir, sys.executable)
            result = select(environment(tool_dir), "--no-tool-python")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "None\n")

    def test_failure_names_the_setup_tool_when_none_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stubs = Path(temp_dir) / "bin"
            stubs.mkdir()
            generic = stubs / "python3"
            generic.write_text("#!/bin/sh\nexit 1\n")
            generic.chmod(0o700)
            result = select(environment(Path(temp_dir) / "absent", path=str(stubs)))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("tools/setup-tool-python builds one", result.stderr)


def no_qualifying_path(temp: Path) -> str:
    """A PATH whose only python3 fails every probe."""
    stubs = temp / "no-python"
    stubs.mkdir()
    generic = stubs / "python3"
    generic.write_text("#!/bin/sh\nexit 1\n")
    generic.chmod(0o700)
    return str(stubs)


def qualifying_path(temp: Path) -> tuple[str, str]:
    """A PATH whose python3.11 carries the developer tools' packages, and its target."""
    target = interpreter_for("yaml", "jsonschema", "tomllib")
    stubs = temp / "with-python"
    stubs.mkdir()
    (stubs / "python3.11").symlink_to(target)
    return str(stubs), str(stubs / "python3.11")


class SetupToolPythonCheckTests(unittest.TestCase):
    def check(self, tool_dir: Path, path: str | None = None) -> str:
        env = environment(tool_dir, path=path)
        if path is not None:
            # An exported site `module` function would let the dispatcher find an
            # interpreter outside the PATH this test controls.
            for key in [k for k in env if k.startswith("BASH_FUNC_")]:
                del env[key]
        result = subprocess.run(
            ["/bin/bash", str(SETUP), "--check"],
            env=env, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def managed(self, tool_dir: Path, target: str, marker: str | None = None) -> None:
        fake_interpreter(tool_dir, target)
        digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
        (tool_dir / MARKER).write_text((marker or digest) + "\n")

    def test_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            out = self.check(temp / "absent", path=no_qualifying_path(temp))
            self.assertIn("tool python: missing", out)

    def test_not_needed_when_an_interpreter_qualifies(self):
        # The control for test_missing: the same absent environment, and the only change
        # is an interpreter on PATH that carries the packages.
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            path, interpreter = qualifying_path(temp)
            out = self.check(temp / "absent", path=path)
            self.assertIn("tool python: not needed", out)
            self.assertIn(interpreter, out)
            self.assertIn("per-user environment missing", out)

    def test_ready_then_stale_when_requirements_move(self):
        target = interpreter_for("yaml", "jsonschema")
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            self.managed(tool_dir, target)
            self.assertIn("tool python: ready", self.check(tool_dir))
            (tool_dir / MARKER).write_text("0" * 64 + "\n")
            # A stale environment that still imports cleanly is a usable interpreter.
            out = self.check(tool_dir)
            self.assertIn("tool python: not needed", out)
            self.assertIn("per-user environment stale", out)

    def test_broken_when_the_packages_do_not_import(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tool_dir = temp / "tool-python"
            self.managed(tool_dir, "/bin/false")
            out = self.check(tool_dir, path=no_qualifying_path(temp))
            self.assertIn("tool python: broken", out)

    def test_broken_but_not_needed_when_an_interpreter_qualifies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tool_dir = temp / "tool-python"
            self.managed(tool_dir, "/bin/false")
            path, interpreter = qualifying_path(temp)
            out = self.check(tool_dir, path=path)
            self.assertIn("tool python: not needed", out)
            self.assertIn(interpreter, out)
            self.assertIn("per-user environment broken", out)

    def test_a_directory_it_did_not_build_is_reported_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir) / "tool-python"
            tool_dir.mkdir()
            sentinel = tool_dir / "someone-elses-file"
            sentinel.write_text("keep\n")
            self.assertIn("was not built by this tool", self.check(tool_dir))
            result = subprocess.run(
                ["/bin/bash", str(SETUP)],
                env=environment(tool_dir), text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("refused", result.stdout)
            self.assertEqual(sentinel.read_text(), "keep\n")


class SetupToolPythonBuildTests(unittest.TestCase):
    def test_a_failed_rebuild_restores_the_previous_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            tools = temp / "tools"
            tools.mkdir()
            for name in ("setup-tool-python", "select-python", "tool-python-location.sh"):
                shutil.copy2(ROOT / "tools" / name, tools / name)
            # A requirement no index can satisfy; PIP_NO_INDEX keeps the failure offline.
            (tools / "requirements.txt").write_text("lqcd-handbook-no-such-package==0\n")
            tool_dir = temp / "tool-python"
            tool_dir.mkdir()
            (tool_dir / MARKER).write_text("previous\n")
            env = environment(tool_dir, path=f"{interpreter_dir()}{os.pathsep}/usr/bin:/bin")
            env["PIP_NO_INDEX"] = "1"
            result = subprocess.run(
                ["/bin/bash", str(tools / "setup-tool-python")],
                env=env, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("previous environment was restored", result.stdout)
            self.assertEqual((tool_dir / MARKER).read_text(), "previous\n")
            self.assertEqual(sorted(p.name for p in temp.iterdir()), ["tool-python", "tools"])


class RequirementsTests(unittest.TestCase):
    def test_every_requirement_is_pinned_and_probed(self):
        # setup-tool-python's probe names the import of each line here; a package added
        # without extending the probe would build an environment the check never tests.
        names = []
        for line in REQUIREMENTS.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            spec = line.split(";")[0].strip()
            self.assertIn("==", spec, f"unpinned requirement: {line}")
            names.append(spec.split("==")[0].lower())
        self.assertEqual(sorted(names), ["jsonschema", "pyyaml", "tomli"])
        probe = SETUP.read_text()
        for module in ("import yaml, jsonschema", "import tomllib", "import tomli"):
            self.assertIn(module, probe)


if __name__ == "__main__":
    unittest.main()
