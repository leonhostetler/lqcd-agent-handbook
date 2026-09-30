#!/usr/bin/env python3
"""The Intel accelerator monitor must turn xpu-smi's output into the seven-field line the one
reader reads, round used memory up, and write no row -- never a zero -- where xpu-smi answers
N/A or answers in a layout nobody established.

The fixtures reproduce the layouts xpu-smi 1.3.5 and 1.2.43 printed on an Aurora compute
node on 2026-09-30, with synthetic UUIDs; the values are the ones recorded while 8 GiB was
held on GPU 0 and 4 GiB on one tile of GPU 3."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import interpreter_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROWS = ROOT / "tools" / "xpu-smi-memory-rows.sh"
MONITOR = ROOT / "tools" / "monitor-gpu.sh"
SAMPLER = ROOT / "tools" / "gpu-memory-sampler.sh"
EXTRACT = ROOT / "tools" / "extract-gpu-telemetry.py"

NAME = "Intel(R) Data Center GPU Max 1550"
DISCOVERY_135 = "Device ID,Device Name,SOC UUID,Memory Physical Size\n" + "".join(
    f'{i},"{NAME}","00000000-0000-0000-0000-00000000000{i}","131072.00 MiB"\n' for i in range(6))
DISCOVERY_1243 = DISCOVERY_135.replace('"131072.00 MiB"', '"N/A"')
HELD = [8283.38, 79.95, 79.94, 4185.61, 79.95, 79.95]
DUMP_135 = "Timestamp, DeviceId, GPU Memory Used (MiB)\n" + "".join(
    f"20:06:34.704,    {i}, {v:.2f}\n" for i, v in enumerate(HELD))
DUMP_1243_FIRST = "Timestamp, DeviceId, GPU Memory Used (MiB)\n" + "".join(
    f"20:05:58.425,    {i},  N/A\n" for i in range(6))
# A per-tile dump carries a TileId column; it must never be read as a device row.
DUMP_TILES = ("Timestamp, DeviceId, TileId, GPU Memory Used (MiB)\n"
              "20:06:21.081,    0,    0, 39.12\n20:06:21.081,    0,    1, 39.05\n")

# Answers like xpu-smi: once for `dump -n 1`, and every interval, header first, for
# `dump -i N` with no count -- the streaming form the monitor uses.
FAKE = """#!/bin/bash
case "$1" in
  discovery) cat "$FAKE_DIR/discovery" ;;
  dump)
    case " $* " in
      *" -n "*) cat "$FAKE_DIR/dump" ;;
      *) head -1 "$FAKE_DIR/dump"
         while true; do tail -n +2 "$FAKE_DIR/dump"; /bin/sleep 1; done ;;
    esac ;;
esac
"""


class IntelTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "xpu-smi"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin", FAKE_DIR=str(self.base))

    def answer(self, discovery: str, dump: str):
        (self.base / "discovery").write_text(discovery)
        (self.base / "dump").write_text(dump)

    def rows(self) -> list[str]:
        result = subprocess.run(["bash", str(ROWS)], env=self.env, text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def monitor(self, seconds: float = 2.5) -> tuple[str, str]:
        result = subprocess.run(["timeout", str(seconds), "bash", str(MONITOR), "1", "intel"],
                                env=self.env, text=True, capture_output=True, check=False)
        return result.stdout, result.stderr

    def test_held_memory_becomes_five_fields_rounded_up(self):
        self.answer(DISCOVERY_135, DUMP_135)
        rows = self.rows()
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], f"0,00000000-0000-0000-0000-000000000000,{NAME},8284,131072")
        self.assertEqual(rows[3].split(",")[3], "4186")
        self.assertEqual(rows[1].split(",")[3], "80")

    def test_na_answers_are_dropped_not_written_as_zero(self):
        for discovery, dump in ((DISCOVERY_1243, DUMP_1243_FIRST), (DISCOVERY_1243, DUMP_135),
                                (DISCOVERY_135, DUMP_1243_FIRST)):
            with self.subTest(dump=dump[:40]):
                self.answer(discovery, dump)
                self.assertEqual(self.rows(), [])

    def test_an_unestablished_layout_yields_no_rows(self):
        self.answer(DISCOVERY_135, DUMP_TILES)
        self.assertEqual(self.rows(), [])

    def test_absent_xpu_smi_prints_nothing_and_exits_zero(self):
        env = dict(self.env, PATH="/usr/bin:/bin")
        result = subprocess.run(["bash", str(ROWS)], env=env, text=True,
                                capture_output=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_monitor_output_is_read_by_the_one_reader(self):
        self.answer(DISCOVERY_135, DUMP_135)
        out, _ = self.monitor()
        log = self.base / "telemetry.out"
        log.write_text(out)
        self.assertIn("telemetry_start,interval_s=1,monitor-gpu-intel", out)
        result = subprocess.run(
            [interpreter_for("yaml"), str(EXTRACT), str(log), "--json", "--expect-devices", "6",
             "--expect-model", "Max 1550"], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["malformed_lines"], 0)
        peaks = {d["index"]: d["peak_used_mib"] for d in summary["devices"]}
        self.assertEqual(peaks[0], 8284)
        self.assertEqual(peaks[3], 4186)
        self.assertEqual(summary["sampling_interval_s"], [1])

    def test_monitor_under_1_2_43_says_so_and_the_reader_reports_missing_data(self):
        self.answer(DISCOVERY_1243, DUMP_1243_FIRST)
        out, err = self.monitor()
        self.assertIn("xpu-smi stream ended", err)
        log = self.base / "telemetry.out"
        log.write_text(out)
        result = subprocess.run([interpreter_for("yaml"), str(EXTRACT), str(log)],
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING DATA, not a zero peak", result.stderr)

    def test_monitor_streams_at_the_interval_rather_than_polling(self):
        self.answer(DISCOVERY_135, DUMP_135)
        out, _ = self.monitor(seconds=4.5)
        stamps = sorted({line.split(",")[0] for line in out.splitlines()
                         if "telemetry_start" not in line})
        self.assertGreaterEqual(len(stamps), 3, out)
        log = self.base / "telemetry.out"
        log.write_text(out)
        result = subprocess.run([interpreter_for("yaml"), str(EXTRACT), str(log), "--json"],
                                text=True, capture_output=True, check=False)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["achieved_period_exceeds_interval"], [])

    def test_stopping_the_monitor_stops_the_stream(self):
        # A monitor that survives its job cannot be told from a live one; nor can its query.
        self.answer(DISCOVERY_135, DUMP_135)
        monitor = subprocess.Popen(["bash", str(MONITOR), "1", "intel"], env=self.env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        fake = str(self.base / "bin" / "xpu-smi")
        self.assertTrue(self.running(fake), "the stream never started")
        monitor.terminate()
        monitor.wait(timeout=10)
        deadline = time.time() + 5
        while self.running(fake) and time.time() < deadline:
            time.sleep(0.2)
        self.assertFalse(self.running(fake), "xpu-smi outlived the monitor")

    @staticmethod
    def running(path: str) -> bool:
        return subprocess.run(["pgrep", "-f", path], capture_output=True).returncode == 0

    def test_unknown_vendor_never_fails_the_job(self):
        result = subprocess.run(["bash", str(MONITOR), "1", "acme"], env=self.env, text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn("no monitor for vendor acme", result.stderr)

    def test_sampler_shares_the_parse(self):
        self.answer(DISCOVERY_135, DUMP_135)
        result = subprocess.run(["bash", str(SAMPLER), "--vendor", "intel", "--interval", "1",
                                 "--max-seconds", "1"], env=self.env, text=True,
                                capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = [l for l in result.stdout.splitlines() if "telemetry_start" not in l]
        self.assertEqual(len(data), 6)
        self.assertTrue(data[0].endswith(f"{NAME},8284,131072"))


class AchievedPeriodTests(unittest.TestCase):
    """The reader measures the period the collector achieved, for every vendor."""

    def extract(self, gap: int, interval: int = 2) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "telemetry.out"
            lines = [f"2026-09-30T20:20:00Z,node,telemetry_start,interval_s={interval},x,0,0"]
            for k in range(5):
                s = f"2026-09-30T20:20:{k * gap:02d}Z"
                lines.append(f"{s},node,0,GPU-0,Model,{100 + k},1000")
            log.write_text("\n".join(lines) + "\n")
            result = subprocess.run([interpreter_for("yaml"), str(EXTRACT), str(log), "--json"],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_a_period_far_above_the_interval_is_flagged(self):
        # The recorded case: asked for 2 s, sampled about every 9 s.
        summary = self.extract(gap=9)
        self.assertEqual(summary["achieved_period_s"], {"node": 9.0})
        self.assertEqual(summary["achieved_period_exceeds_interval"], ["node"])

    def test_a_period_at_the_interval_is_not_flagged(self):
        summary = self.extract(gap=2)
        self.assertEqual(summary["achieved_period_s"], {"node": 2.0})
        self.assertEqual(summary["achieved_period_exceeds_interval"], [])


class HarnessStubTests(unittest.TestCase):
    """On an Intel machine the dry run must answer the helper's queries, or a script whose
    guard reads the monitor's rows could never pass a positive control."""

    def test_the_helper_reads_the_harness_stub(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            jobdir = base / "trial"
            jobdir.mkdir()
            (base / "tmp").mkdir()
            script = jobdir / "job.pbs"
            script.write_text(
                "#!/usr/bin/env bash\n#PBS -A <project>\n#PBS -o " + str(jobdir) + "/job.out\n"
                "set -euo pipefail\ncd " + str(jobdir) + "\n"
                f'rows=$("{ROWS}")\n'
                '[ "$(printf "%s\\n" "$rows" | wc -l)" -eq 6 ] || { echo "FATAL: no rows"; exit 1; }\n'
                'printf "%s\\n" "$rows"\n')
            result = subprocess.run(
                [interpreter_for("yaml"), str(ROOT / "tools" / "dry-run-batch-script.py"),
                 str(script), "--machine", "aurora", "--gpu-count", "6",
                 "--gpu-memory-mib", "131072", "--no-receipt"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                env=dict(os.environ, TMPDIR=str(base / "tmp")), cwd=temp)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("POSITIVE CONTROL PASSED", result.stdout)
            self.assertIn(",0,131072", result.stdout)


if __name__ == "__main__":
    unittest.main()
