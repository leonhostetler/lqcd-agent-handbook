#!/usr/bin/env python3
"""quda-tunecache-policies.py must read only policy rows, refuse single-GPU rows as GDR
evidence, and fail each check it is asked for. The tunecache files are synthetic, in the
tab-separated layout QUDA 1.1.0 writes."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "quda-tunecache-policies.py"

HEADER = ("tunecache\t1.1.0\t1.1.0-deadbeef-sm_100\tcpu_arch=aarch64,gpu_arch=sm_100\t# synthetic\n\n"
          "          volume\tname\taux\tblock.x\tblock.y\tblock.z\tgrid.x\tgrid.y\tgrid.z\t"
          "shared_bytes\tshared_carve_out\taux.x\taux.y\taux.z\taux.w\ttime\tcomment\n")


def row(aux: str, seconds: float, kernel: str = "N4quda9StaggeredIdEE") -> str:
    return (f"      8x16x8x16\t{kernel}\t{aux}\t32\t1\t1\t1\t1\t1\t0\t0\t-1\t-1\t-1\t-1\t"
            f"{seconds:g}\t# synthetic\n")


def policy(comm: str, p2p: int, gdr: int, seconds: float) -> str:
    return row(f"policy,GPU-offline,vol=16384,commDim={comm},p2p={p2p},gdr={gdr},nvshmem=0,pol=11", seconds)


class TunecachePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def cache(self, name: str, *rows: str) -> Path:
        path = self.dir / name
        path.write_text(HEADER + "".join(rows))
        return path

    def run_tool(self, *args):
        return subprocess.run([interpreter_for(), str(TOOL), *map(str, args)],
                              text=True, capture_output=True, check=False)

    def test_counts_only_policy_rows_and_reports_the_slowest(self):
        path = self.cache("t.tsv",
                          policy("0011", 7, 1, 4.1e-5), policy("0011", 7, 1, 3.9e-5),
                          row("policy_kernel=interior,GPU-offline,commDim=0011,p2p=7,gdr=1", 9.0),
                          row("GPU-offline,vol=16384", 5.0))
        result = self.run_tool("--expect-gdr", "1", path)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("2 policy row(s)", result.stdout)
        self.assertIn("slowest policy: 4.100e-05", result.stdout)
        self.assertIn("quda-tunecache-policies 1.0.0", result.stdout)

    def test_gdr_off_fails_an_expectation_of_gdr_on(self):
        path = self.cache("off.tsv", policy("0011", 3, 0, 4e-5))
        result = self.run_tool("--expect-gdr", "1", path)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("without gdr=1", result.stdout)

    def test_a_single_gpu_row_is_not_gdr_evidence(self):
        # QUDA stamps gdr=1 on a policy that communicates nothing; it must not count.
        path = self.cache("one_gpu.tsv", policy("0000", 0, 1, 2e-5))
        result = self.run_tool("--expect-gdr", "1", path)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no policy row with a partitioned dimension", result.stdout)

    def test_no_policy_rows_fails_an_expectation(self):
        path = self.cache("none.tsv", row("GPU-offline,vol=16384", 1e-5))
        result = self.run_tool("--expect-gdr", "1", path)
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_a_slow_policy_fails_a_ceiling_and_a_fast_one_does_not(self):
        slow = self.cache("slow.tsv", policy("0011", 7, 1, 1.3e-2))
        fast = self.cache("fast.tsv", policy("0011", 7, 1, 4e-5))
        self.assertEqual(self.run_tool("--max-policy-seconds", "1e-3", slow).returncode, 1)
        self.assertEqual(self.run_tool("--max-policy-seconds", "1e-3", fast).returncode, 0)

    def test_without_checks_it_reports_and_passes(self):
        path = self.cache("plain.tsv", policy("0011", 3, 0, 1.3e-2))
        self.assertEqual(self.run_tool(path).returncode, 0)

    def test_an_unreadable_file_is_a_usage_error(self):
        self.assertEqual(self.run_tool(self.dir / "absent.tsv").returncode, 2)


if __name__ == "__main__":
    unittest.main()
