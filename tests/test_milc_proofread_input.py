#!/usr/bin/env python3
"""milc-proofread-input.sh must keep the GPU runtime out of a parse-only run, supply CUDA
stubs when the driver's libraries are missing, select a CPU SYCL device for a SYCL-linked
executable, disable core dumps, and still fail a bad input. A shell stand-in plays
ks_spectrum: it fails as a QUDA-linked MILC build does on a GPU-less node unless the GPU
runtime was disabled, and otherwise behaves like MILC's prompt-2 parser."""
from __future__ import annotations

import os
import resource
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "milc-proofread-input.sh"

FAKE_MILC = r"""#!/bin/bash
# Stand-in for a QUDA-linked ks_spectrum_hisq in parse-only mode.
echo "core limit: $(ulimit -c)"
if [ -n "${REQUIRE_SYCL_CPU:-}" ] && [ "${ONEAPI_DEVICE_SELECTOR:-}" != opencl:cpu ]; then
  echo "terminate called after throwing an instance of 'sycl::_V1::exception'"
  echo "  what():  No device of requested type available."
  exit 134
fi
if [ "${OMPI_MCA_accelerator:-}" != null ]; then
  echo "UCX  ERROR cuDeviceGetCount(&num_devices) failed: unrecognized error code 34"
  echo "*** An error occurred in MPI_Allreduce"
  exit 1
fi
if [ -n "${REQUIRE_STUB:-}" ]; then
  first=${LD_LIBRARY_PATH%%:*}
  [ -e "$first/libcuda.so.1" ] || { echo "error while loading shared libraries: libcuda.so.1"; exit 127; }
fi
input=$(cat)
grep -q '^prompt 2$' <<< "$input" || { echo "running the real calculation"; exit 0; }
if grep -q bogus_keyword <<< "$input"; then echo "error in input: bogus_keyword"; exit 0; fi
echo "EOF on input"
"""

FAKE_LDD = """#!/bin/bash
echo "\tlibcuda.so.1 => not found"
echo "\tlibc.so.6 => /lib64/libc.so.6 (0x0000)"
"""

FAKE_LDD_SYCL = """#!/bin/bash
echo "\tlibsycl.so.9 => /opt/oneapi/lib/libsycl.so.9 (0x0000)"
echo "\tlibc.so.6 => /lib64/libc.so.6 (0x0000)"
"""


class ProofreadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        d = Path(self.temp.name)
        self.exe = d / "ks_spectrum_hisq"
        self.exe.write_text(FAKE_MILC)
        self.exe.chmod(0o755)
        self.good = d / "good.in"
        self.good.write_text("prompt 0\nnx 4\n")
        self.bad = d / "bad.in"
        self.bad.write_text("prompt 0\nbogus_keyword 1\n")
        self.bin = d / "bin"
        self.bin.mkdir()
        self.stubs = d / "stubs"
        self.stubs.mkdir()
        (self.stubs / "libcuda.so").write_text("")

    def run_tool(self, input_path: Path, env_extra=None, fake_ldd=False, tool=TOOL, extra_args=(),
                 preexec_fn=None):
        env = dict(os.environ)
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("CUDA_HOME", None)
        env["LIBRARY_PATH"] = ""
        if fake_ldd:
            (self.bin / "ldd").write_text(FAKE_LDD if fake_ldd is True else fake_ldd)
            (self.bin / "ldd").chmod(0o755)
            env["PATH"] = f"{self.bin}:{env['PATH']}"
        env.update(env_extra or {})
        return subprocess.run(["bash", str(tool), "--exe", str(self.exe), "--input", str(input_path),
                               "--timeout", "30", *extra_args],
                              text=True, capture_output=True, env=env, check=False,
                              preexec_fn=preexec_fn)

    def crippled_tool(self, remove: str) -> Path:
        script = TOOL.read_text().replace(remove, "")
        self.assertNotEqual(script, TOOL.read_text(), "vacuous perturbation")
        path = Path(self.temp.name) / "crippled.sh"
        path.write_text(script)
        return path

    def test_a_good_input_passes_with_the_gpu_runtime_disabled(self):
        result = self.run_tool(self.good)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)
        self.assertIn("milc-proofread-input 1.2.0", result.stdout)
        self.assertIn("sycl device: not linked", result.stdout)

    def test_a_bad_input_still_fails(self):
        result = self.run_tool(self.bad)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("bogus_keyword", result.stdout)

    def test_the_runtime_variables_are_what_makes_it_pass(self):
        # Negative control: with the tool's accelerator setting overridden, the stand-in
        # fails exactly as a GPU-less login node did, so the verdict is not a pass.
        script = TOOL.read_text().replace('"OMPI_MCA_accelerator=null" ', "")
        self.assertNotEqual(script, TOOL.read_text(), "vacuous perturbation")
        crippled = Path(self.temp.name) / "crippled.sh"
        crippled.write_text(script)
        env = dict(os.environ, LIBRARY_PATH="")
        env.pop("OMPI_MCA_accelerator", None)
        result = subprocess.run(["bash", str(crippled), "--exe", str(self.exe), "--input", str(self.good),
                                 "--timeout", "30"], text=True, capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INDETERMINATE", result.stdout)

    def test_missing_libcuda_is_supplied_from_a_stub_directory(self):
        result = self.run_tool(self.good, {"LIBRARY_PATH": str(self.stubs), "REQUIRE_STUB": "1"}, fake_ldd=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"cuda stubs: libcuda.so.1 from {self.stubs}", result.stdout)

    def test_a_sycl_executable_parses_on_a_cpu_device(self):
        # The site default selects the GPU, as Aurora's login environment does.
        env = {"REQUIRE_SYCL_CPU": "1", "ONEAPI_DEVICE_SELECTOR": "level_zero:gpu"}
        result = self.run_tool(self.good, env, fake_ldd=FAKE_LDD_SYCL)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sycl device: opencl:cpu", result.stdout)

    def test_the_cpu_selector_is_what_makes_a_sycl_executable_pass(self):
        # Negative control: without the selector the stand-in dies at load, as the SYCL
        # QUDA library does on a GPU-less node, and the verdict shows why inline rather
        # than naming a log file the exit trap has already deleted.
        crippled = self.crippled_tool('    runtime_env+=("ONEAPI_DEVICE_SELECTOR=opencl:cpu")\n')
        env = {"REQUIRE_SYCL_CPU": "1", "ONEAPI_DEVICE_SELECTOR": "level_zero:gpu"}
        result = self.run_tool(self.good, env, fake_ldd=FAKE_LDD_SYCL, tool=crippled)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("INDETERMINATE", result.stdout)
        self.assertIn("No device of requested type available", result.stdout)
        self.assertIn("temporary and is now gone", result.stdout)
        self.assertNotIn("Log: ", result.stdout)

    def test_core_dumps_are_disabled_for_the_parse(self):
        # Raise the caller's core limit first: a session whose limit is already 0 would
        # otherwise pass this test against a tool that never lowers it.
        hard = resource.getrlimit(resource.RLIMIT_CORE)[1]
        if hard == 0:
            self.skipTest("hard core limit is 0 here; the tool's ulimit cannot be distinguished")
        raise_limit = lambda: resource.setrlimit(resource.RLIMIT_CORE, (hard, hard))
        log = Path(self.temp.name) / "kept.out"
        result = self.run_tool(self.good, extra_args=("--keep-output", str(log)), preexec_fn=raise_limit)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("core limit: 0", log.read_text())

    def test_missing_libcuda_without_stubs_is_indeterminate_not_a_pass(self):
        result = self.run_tool(self.good, {"REQUIRE_STUB": "1"}, fake_ldd=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("no CUDA stub directory", result.stdout)


if __name__ == "__main__":
    unittest.main()
