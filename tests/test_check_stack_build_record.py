"""The stack build-record checker must catch every way a record of passed options goes wrong.

CMake mode: a passed flag missing from the record, a recorded value that differs from the one
passed, a passed value that never reached the cache, a cache value nobody passed (a stale cache
or a command that is not the one that ran), a recorded-but-unpassed option that differs from the
build, a source checkout at the wrong commit, and an ambiguous command file. Make mode: a passed
variable missing from the record, a recorded-but-unpassed variable that differs from the
Makefile default, one with no decidable default, a log at the wrong commit or building an
unlisted target, and an unexpanded shell value against a literal record. The controls disable
two checks in the tool's source and show the matching negative then goes quiet.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import PerturbationMixin, interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "check-stack-build-record.py"

QUDA_PROFILES = """\
schema_version: 1
software: quda
profiles:
  fixture:
    summary: Fixture.
    options:
      QUDA_QMP: true
      QUDA_MULTIGRID: false
      QUDA_MAX_MULTI_RHS_TILE: "{tile}"
    capabilities: {{dirac: [staggered]}}
"""
QUDA_CMAKE = """\
option(QUDA_QMP "build QMP" OFF)
option(QUDA_MULTIGRID "build multigrid" OFF)
option(QUDA_INTERFACE_MILC "milc interface" ON)
set(QUDA_MAX_MULTI_RHS_TILE "1" CACHE STRING "tile")
option(QUDA_EXTRA "an option nobody passes" OFF)
if(SOMETHING)
  set(QUDA_COMPUTED "a" CACHE STRING "a conditional default")
endif()
set(QUDA_FROM_ENV "$ENV{SOME_VARIABLE}" CACHE STRING "an environment default")
"""
QUDA_CACHE = """\
# This is the CMakeCache file.
//build type
CMAKE_BUILD_TYPE:STRING=RELEASE
CMAKE_C_COMPILER:STRING=/opt/site/bin/mpicc
CMAKE_INSTALL_PREFIX:PATH=/opt/build/usqcd
QUDA_QMP:BOOL=ON
QUDA_MULTIGRID:BOOL=OFF
QUDA_INTERFACE_MILC:BOOL=ON
QUDA_MAX_MULTI_RHS_TILE:STRING={tile}
QUDA_EXTRA:BOOL={extra}
QUDA_COMPUTED:STRING=a
QUDA_FROM_ENV:STRING=
QUDA_UNDECLARED:STRING=z
QUDA_SOMETHING_INTERNAL:INTERNAL=1
"""
QUDA_COMMAND = """\
#!/bin/bash
set -e
module load toolchain
cmake {fresh} $quda_dir -DCMAKE_BUILD_TYPE=RELEASE -DQUDA_QMP=ON -DQUDA_MULTIGRID=OFF \\
\t-DQUDA_MAX_MULTI_RHS_TILE={tile} {extra}-DCMAKE_C_COMPILER=mpicc \\
\t-DCMAKE_INSTALL_PREFIX=`pwd`/usqcd 2>&1 | tee -a $log_file
cmake --build . -j 8 2>&1 | tee -a $log_file
"""

MILC_PROFILES = """\
schema_version: 1
software: milc
profiles:
  fixture:
    summary: Fixture.
    targets: [app, app_variant]
    options:
      PRECISION: 2
      MPP: true
      WANTQUDA: true
      OPT: {opt}
{extra_options}    capabilities: {{applications: [app]}}
"""
MILC_MAKEFILE = """\
PRECISION ?= 1 # 1 or 2
MPP ?= false
WANTQUDA ?= false
OPT ?= -O3
ifeq ($(X),y)
WANT_COND ?= true
endif
"""
MILC_COMMAND = """\
#!/bin/bash
make clean
make_status=0
MY_CC=mpicc \\
PRECISION=2 \\
MPP=true \\
WANTQUDA=true {extra}\\
QUDA_HOME=${{QUDA_BUILD}}/usqcd \\
make -j 1 $target >> $log_name 2>&1 || make_status=$?
"""
MILC_LOG = 'MILC branch: develop\nMILC commit: {commit}\n\nmake -f Makefile target "MYTARGET= {target}" \\\n'


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t", "GIT_COMMITTER_NAME": "t",
             "GIT_COMMITTER_EMAIL": "t", "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
             "HOME": str(repo)},
    ).stdout.strip()


class Fixture:
    """A fixture handbook root, a committed source checkout, and the build's evidence."""

    def __init__(self, base: Path, software: str):
        self.base = base
        self.software = software
        self.root = base / "handbook"
        (self.root / "software" / software).mkdir(parents=True)
        self.source = base / "source"
        self.source.mkdir()
        (self.source / ("CMakeLists.txt" if software == "quda" else "Makefile")).write_text(
            QUDA_CMAKE if software == "quda" else MILC_MAKEFILE
        )
        git(self.source, "init", "-q")
        git(self.source, "add", ".")
        git(self.source, "commit", "-qm", "fixture")
        self.commit = git(self.source, "rev-parse", "HEAD")

    def profiles(self, text: str) -> None:
        (self.root / "software" / self.software / "build-profiles.yaml").write_text(text)

    def stack(self, machine_options: dict, commit: str | None = None) -> Path:
        options = "".join(f"    {key}: {json.dumps(value)}\n" for key, value in machine_options.items())
        text = textwrap.dedent(f"""\
            software: {self.software}
            tested_software:
              {self.software}: {{commit: {commit or self.commit}, branch: develop}}
            build:
              type: RELEASE
              profile_options_from: software/{self.software}/build-profiles.yaml#fixture
              machine_options:
            """) + options
        path = self.base / "stack.yaml"
        path.write_text(text)
        return path

    def write(self, name: str, text: str) -> Path:
        path = self.base / name
        path.write_text(text)
        return path


class CheckerCase(PerturbationMixin, unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.base = Path(self._temp.name)

    def run_tool(self, *args: str) -> tuple[int, dict]:
        done = subprocess.run(
            [interpreter_for("yaml"), str(TOOL), *args, "--json"], capture_output=True, text=True
        )
        self.assertIn(done.returncode, (0, 1, 2), done.stderr)
        return done.returncode, json.loads(done.stdout)

    def assert_found(self, report: dict, kind: str, fragment: str) -> None:
        self.assertTrue(any(fragment in item for item in report[kind]), report[kind])


class CMakeModeTests(CheckerCase):
    def build(self, *, profile_tile="3", command_tile="3", cache_tile="3", cache_extra="OFF",
              passed_extra="", fresh="--fresh", machine_options=None, commit=None,
              command_text=None):
        fixture = Fixture(self.base, "quda")
        fixture.profiles(QUDA_PROFILES.format(tile=profile_tile))
        stack = fixture.stack(
            machine_options
            or {"CMAKE_C_COMPILER": "mpicc", "CMAKE_INSTALL_PREFIX": "<install-prefix>"},
            commit,
        )
        command = fixture.write(
            "compile.sh",
            command_text
            or QUDA_COMMAND.format(fresh=fresh, tile=command_tile, extra=passed_extra),
        )
        cache = fixture.write("CMakeCache.txt", QUDA_CACHE.format(tile=cache_tile, extra=cache_extra))
        return self.run_tool(
            "cmake", "--root", str(fixture.root), "--stack", str(stack), "--command", str(command),
            "--cache", str(cache), "--source", str(fixture.source),
        )

    def test_a_complete_record_has_no_findings(self):
        status, report = self.build()
        self.assertEqual(status, 0, report)
        self.assertEqual((report["errors"], report["undecided"], report["warnings"]), ([], [], []))
        counts = report["counts"]
        self.assertEqual(counts["QUDA_* values checked against their declared default"], 2)
        self.assertEqual(counts["QUDA_* values with computed defaults, not cross-checked"], 2)
        self.assertEqual(counts["QUDA_* values with no declaration found, not cross-checked"], 1)
        self.assertEqual(report["environment_defaults"], ["QUDA_FROM_ENV"])
        self.assertNotIn("/opt/", json.dumps(report))

    def test_rejects_a_passed_flag_missing_from_the_record(self):
        status, report = self.build(passed_extra="-DQUDA_EXTRA=ON ", cache_extra="ON")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "QUDA_EXTRA='ON' was passed to the build but is not in")

    def test_rejects_a_recorded_value_that_differs_from_the_one_passed(self):
        status, report = self.build(command_tile="4", cache_tile="4")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "QUDA_MAX_MULTI_RHS_TILE: recorded '3' but passed '4'")

    def test_rejects_a_passed_value_that_never_reached_the_cache(self):
        status, report = self.build(cache_tile="1")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "passed '3' but the cache holds '1'")

    def test_rejects_a_cache_value_nobody_passed(self):
        status, report = self.build(cache_extra="ON")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "QUDA_EXTRA holds 'ON', but its default")

    def test_rejects_a_recorded_unpassed_option_that_differs_from_the_build(self):
        options = {"CMAKE_C_COMPILER": "mpicc", "CMAKE_INSTALL_PREFIX": "<install-prefix>",
                   "QUDA_INTERFACE_MILC": False}
        status, report = self.build(machine_options=options)
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "QUDA_INTERFACE_MILC is recorded as 'False' but was not passed")

    def test_rejects_a_source_checkout_at_another_commit(self):
        status, report = self.build(commit="0" * 40)
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "not the tested commit")

    def test_warns_when_the_configure_was_not_fresh(self):
        status, report = self.build(fresh="")
        self.assertEqual(status, 0)
        self.assert_found(report, "warnings", "did not use --fresh")

    def test_rejects_a_command_file_with_two_configure_invocations(self):
        twice = QUDA_COMMAND.format(fresh="--fresh", tile="3", extra="")
        status, report = self.build(command_text=twice + twice)
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "found 2")

    def test_control_without_the_stale_cache_check_a_stale_value_goes_unseen(self):
        self.perturb(TOOL, "        if canonical(found[0][0], True) != canonical(value, True):",
                     "        if False:")
        status, report = self.build(cache_extra="ON")
        self.assertEqual(status, 0, report)

    def test_control_without_the_record_check_a_missing_flag_goes_unseen(self):
        self.perturb(TOOL, 'report.errors.append(f"{name}={shown(value)} was passed',
                     '(lambda *_: None)(f"{name}={shown(value)} was passed')
        status, report = self.build(passed_extra="-DQUDA_EXTRA=ON ", cache_extra="ON")
        self.assertFalse(any("is not in the stack's record" in e for e in report["errors"]), report)


class MakeModeTests(CheckerCase):
    def build(self, *, opt="-O3", extra_options="", passed_extra="", log_commit=None,
              log_target="app", machine_options=None):
        fixture = Fixture(self.base, "milc")
        fixture.profiles(MILC_PROFILES.format(opt=opt, extra_options=extra_options))
        stack = fixture.stack(machine_options or {"MY_CC": "mpicc", "QUDA_HOME": "<quda-install-prefix>"})
        command = fixture.write("compile.sh", MILC_COMMAND.format(extra=passed_extra))
        log = fixture.write("make.log", MILC_LOG.format(commit=log_commit or fixture.commit, target=log_target))
        return self.run_tool(
            "make", "--root", str(fixture.root), "--stack", str(stack), "--command", str(command),
            "--makefile", str(fixture.source / "Makefile"), "--log", str(log),
            "--source", str(fixture.source),
        )

    def test_a_complete_record_has_no_findings(self):
        status, report = self.build()
        self.assertEqual(status, 0, report)
        self.assertEqual((report["errors"], report["undecided"], report["warnings"]), ([], [], []))

    def test_rejects_a_passed_variable_missing_from_the_record(self):
        status, report = self.build(passed_extra="\\\nWANTX=true ")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "WANTX='true' was passed to the build but is not in")

    def test_rejects_a_recorded_unpassed_variable_that_differs_from_the_default(self):
        status, report = self.build(opt="-O2")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "OPT is recorded as '-O2' but was not passed")

    def test_leaves_undecided_a_variable_whose_default_is_conditional(self):
        status, report = self.build(extra_options="      WANT_COND: true\n")
        self.assertEqual(status, 2)
        self.assert_found(report, "undecided", "WANT_COND is recorded")

    def test_rejects_a_log_at_another_commit(self):
        status, report = self.build(log_commit="f" * 40)
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "not the tested")

    def test_rejects_a_log_building_an_unlisted_target(self):
        status, report = self.build(log_target="other_app")
        self.assertEqual(status, 1)
        self.assert_found(report, "errors", "builds other_app, which the profile does not list")

    def test_leaves_undecided_an_unexpanded_value_against_a_literal_record(self):
        status, report = self.build(machine_options={"MY_CC": "mpicc", "QUDA_HOME": "/opt/quda"})
        self.assertEqual(status, 2)
        self.assert_found(report, "undecided", "QUDA_HOME: passed as")
        self.assertNotIn("/opt/quda", json.dumps(report))


class HashModeTests(unittest.TestCase):
    def test_hashes_every_shared_library_by_relative_path_and_skips_links(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            (prefix / "lib").mkdir()
            (prefix / "lib64").mkdir()
            (prefix / "lib" / "libquda.so").write_bytes(b"quda")
            (prefix / "lib" / "libquda.so.1").symlink_to("libquda.so")
            (prefix / "lib64" / "libqmp.so.2").write_bytes(b"qmp")
            (prefix / "lib" / "notes.txt").write_text("not a library")
            done = subprocess.run(
                [interpreter_for("yaml"), str(TOOL), "hashes", "--install-prefix", str(prefix)],
                capture_output=True, text=True, check=True,
            )
            import yaml

            rows = yaml.safe_load(done.stdout)["installed_libraries"]
            self.assertEqual(
                rows,
                [
                    {"path": "lib/libquda.so", "sha256": hashlib.sha256(b"quda").hexdigest()},
                    {"path": "lib64/libqmp.so.2", "sha256": hashlib.sha256(b"qmp").hexdigest()},
                ],
            )
            self.assertNotIn(temp, done.stdout)


if __name__ == "__main__":
    unittest.main()
