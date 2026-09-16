#!/usr/bin/env python3
"""Checks on the capability notes a capture's gaps produce.

These notes are the only place the tooling tells a session what to ask for on the
next capture, so a note that names an insufficient command is worse than silence:
it is followed. The rocpd guard below is structural rather than per note, because
the defect it pins was not specific to any one of them -- every rocpd re-profile
command omitted the output-format variable, and the next note added would have
omitted it too.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from gpu_profile.base import Format, ProfileCapabilities  # noqa: E402
from gpu_profile.diagnostics import capability_notes  # noqa: E402


def _no_capabilities() -> ProfileCapabilities:
    """A capture missing everything, so every note fires."""
    return ProfileCapabilities(
        has_kernels=False,
        has_memcpy=False,
        has_runtime_api=False,
        has_markers=False,
        has_mpi=False,
        has_cpu_samples=False,
        has_os_runtime=False,
        has_pmc_counters=False,
        has_sysmetrics=False,
        has_launch_geometry=False,
        has_transfer_residency=False,
        schema_version="3",
    )


def _command_lines(fmt: Format, needle: str) -> list[str]:
    return [
        line
        for note in capability_notes(fmt, _no_capabilities())
        for line in note.message.splitlines()
        if needle in line
    ]


class RocpdReprofileCommands(unittest.TestCase):
    def test_notes_actually_fire(self) -> None:
        """Vacuity guard: the checks below iterate, so an empty list must fail here."""
        notes = capability_notes(Format.ROCPD, _no_capabilities())
        self.assertGreaterEqual(len(notes), 4, "rocpd capability notes did not fire")

    def test_every_rocprof_sys_command_requests_rocpd_output(self) -> None:
        """rocprof-sys writes perfetto unless told otherwise, and this reader cannot open it.

        A command that omits ROCPROFSYS_USE_ROCPD produces a run that succeeds and an
        artifact open_profile() rejects -- the failure lands after the allocation is spent.
        """
        lines = _command_lines(Format.ROCPD, "rocprof-sys-sample")
        self.assertTrue(lines, "no rocprof-sys-sample command lines were produced")
        for line in lines:
            self.assertIn(
                "ROCPROFSYS_USE_ROCPD=true",
                line,
                f"re-profile command omits the rocpd output variable: {line.strip()}",
            )

    def test_mpi_note_requests_the_mpip_interposer(self) -> None:
        """MPI ranges come from MPIP, which rocpd output alone does not enable."""
        notes = [n for n in capability_notes(Format.ROCPD, _no_capabilities()) if n.code == "R1"]
        self.assertEqual(len(notes), 1, "the rocpd MPI note (R1) did not fire")
        self.assertIn("ROCPROFSYS_USE_MPIP=true", notes[0].message)

    def test_nsys_notes_carry_no_rocm_variables(self) -> None:
        """Negative control: the guard must be specific to rocpd, not matching everything."""
        for note in capability_notes(Format.NSYS, _no_capabilities()):
            self.assertNotIn(
                "ROCPROFSYS", note.message, f"nsys note {note.code} names a ROCm variable"
            )

    def test_nsys_notes_still_name_a_command(self) -> None:
        """The nsys side is untouched by this change and must stay actionable."""
        lines = _command_lines(Format.NSYS, "nsys profile")
        self.assertGreaterEqual(len(lines), 4, "nsys re-profile commands went missing")


if __name__ == "__main__":
    unittest.main()
