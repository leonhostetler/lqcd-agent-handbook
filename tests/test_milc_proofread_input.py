#!/usr/bin/env python3
"""milc-proofread-input.sh must keep the GPU runtime out of a parse-only run and supply CUDA
stubs when the driver's libraries are missing, and still fail a bad input. A shell stand-in
plays ks_spectrum: it fails as a QUDA-linked MILC build does on a GPU-less node unless the
GPU runtime was disabled, and otherwise behaves like MILC's prompt-2 parser."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "milc-proofread-input.sh"

FAKE_MILC = r"""#!/bin/bash
# Stand-in for a QUDA-linked ks_spectrum_hisq in parse-only mode.
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

    def run_tool(self, input_path: Path, env_extra=None, fake_ldd=False):
        env = dict(os.environ)
        env.pop("LD_LIBRARY_PATH", None)
        env.pop("CUDA_HOME", None)
        env["LIBRARY_PATH"] = ""
        if fake_ldd:
            (self.bin / "ldd").write_text(FAKE_LDD)
            (self.bin / "ldd").chmod(0o755)
            env["PATH"] = f"{self.bin}:{env['PATH']}"
        env.update(env_extra or {})
        return subprocess.run(["bash", str(TOOL), "--exe", str(self.exe), "--input", str(input_path),
                               "--timeout", "30"], text=True, capture_output=True, env=env, check=False)

    def test_a_good_input_passes_with_the_gpu_runtime_disabled(self):
        result = self.run_tool(self.good)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)
        self.assertIn("milc-proofread-input 1.1.0", result.stdout)

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

    def test_missing_libcuda_without_stubs_is_indeterminate_not_a_pass(self):
        result = self.run_tool(self.good, {"REQUIRE_STUB": "1"}, fake_ldd=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("no CUDA stub directory", result.stdout)


if __name__ == "__main__":
    unittest.main()
