#!/usr/bin/env python3
"""Checks on the capability notes a capture's gaps produce.

These notes are the only place the tooling tells a session what to ask for on the
next capture, so a note that names an insufficient command is worse than silence:
it is followed. The same reason is why the counter notes name no command at all --
the question they report is not answerable by any capture flag, and offering one
invited exactly the reading the performance mode exists to prevent. The rocpd
guard below is structural rather than per note, because
the defect it pins was not specific to any one of them -- every rocpd re-profile
command omitted the output-format variable, and the next note added would have
omitted it too.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / "tools" / "gpu_profile" / "diagnostics.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import gpu_profile.diagnostics as diagnostics  # noqa: E402
from gpu_profile.base import Format, ProfileCapabilities  # noqa: E402
from gpu_profile.diagnostics import capability_notes  # noqa: E402
from support import PerturbationMixin  # noqa: E402


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


# The counter notes name no re-profile command on purpose, so the nsys guard below is a
# per-note expectation rather than a count. A count cannot distinguish a note that lost its
# command from the one note that must not carry one, and it was a count that let the
# forbidden counter remedy sit in N4 and R4 unnoticed.
NO_COMMAND_NOTES = {"N4", "R4"}


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

    def test_every_other_nsys_note_names_a_command(self) -> None:
        """Every note but the counter one must stay actionable."""
        for note in capability_notes(Format.NSYS, _no_capabilities()):
            if note.code in NO_COMMAND_NOTES:
                continue
            self.assertIn(
                "nsys profile",
                note.message,
                f"nsys note {note.code} names no re-profile command",
            )

    def test_counter_notes_offer_no_capture_flag(self) -> None:
        """The counter notes must not name a remedy the mode and conventions forbid.

        Counter collection is a separate job: it serialises kernel replay and distorts
        the durations a timing capture exists to measure. So there is no flag that adds
        counters to *this* capture, and a note offering one is followed -- which is how
        a session ends up classifying memory- versus compute-bound from a trace.
        """
        fired = set()
        for fmt in (Format.NSYS, Format.ROCPD):
            for note in capability_notes(fmt, _no_capabilities()):
                if note.code not in NO_COMMAND_NOTES:
                    continue
                fired.add(note.code)
                for forbidden in ("--gpu-metrics-device", "--hardware-counters", "Re-profile"):
                    self.assertNotIn(
                        forbidden,
                        note.message,
                        f"counter note {note.code} offers a capture-side counter remedy",
                    )
        self.assertEqual(fired, NO_COMMAND_NOTES, "a counter note did not fire")


class CapabilityNoteControls(PerturbationMixin, unittest.TestCase):
    """Each control reverts part of the fix and asserts the guards above would notice.

    Run by hand when the fix landed; carried here so they run on every suite, because
    the defect this repository keeps recording is a control that goes inert later.
    """

    def setUp(self) -> None:
        # Registered before any perturbation, so it runs *after* the file is restored:
        # addCleanup is LIFO, and reloading a still-perturbed module would leak it.
        self.addCleanup(importlib.reload, diagnostics)

    def _notes(self, fmt: Format) -> list:
        importlib.reload(diagnostics)
        return diagnostics.capability_notes(fmt, _no_capabilities())

    def _lines(self, fmt: Format, needle: str) -> list[str]:
        return [
            line
            for note in self._notes(fmt)
            for line in note.message.splitlines()
            if needle in line
        ]

    def test_emptying_the_output_constant_is_caught(self):
        """The constant must be the thing interpolated, not decoration beside the guard."""
        self.perturb(
            DIAGNOSTICS,
            '_ROCPD_OUTPUT = "ROCPROFSYS_USE_ROCPD=true"',
            '_ROCPD_OUTPUT = ""',
        )
        lines = self._lines(Format.ROCPD, "rocprof-sys-sample")
        self.assertTrue(lines, "no commands were produced; the control proves nothing")
        self.assertFalse(
            any("ROCPROFSYS_USE_ROCPD=true" in line for line in lines),
            "emptying the constant did not change the commands; it is not consulted",
        )

    def test_dropping_mpip_from_the_mpi_note_is_caught(self):
        self.perturb(
            DIAGNOSTICS,
            'f"  Re-profile with: {_ROCPD_OUTPUT} {_MPIP} "',
            'f"  Re-profile with: {_ROCPD_OUTPUT} "',
        )
        r1 = [n for n in self._notes(Format.ROCPD) if n.code == "R1"]
        self.assertEqual(len(r1), 1)
        self.assertNotIn("ROCPROFSYS_USE_MPIP=true", r1[0].message)

    def test_suppressing_the_rocpd_branch_is_caught(self):
        """The vacuity guard: every check above iterates, so an empty list must be visible."""
        self.perturb(DIAGNOSTICS, "    elif fmt is Format.ROCPD:", "    elif False:")
        self.assertEqual(self._notes(Format.ROCPD), [])

    def test_a_rocm_variable_reaching_an_nsys_note_is_caught(self):
        """The specificity control: the rocpd guard must not match everything."""
        self.perturb(
            DIAGNOSTICS,
            '"  Re-profile with: nsys profile -t cuda ..."',
            '"  Re-profile with: ROCPROFSYS_USE_ROCPD=true nsys profile -t cuda ..."',
        )
        self.assertTrue(
            any("ROCPROFSYS" in n.message for n in self._notes(Format.NSYS)),
            "the perturbation did not reach an nsys note",
        )

    def test_the_source_is_restored_between_controls(self):
        """Guards the mixin itself: a leaked perturbation would silently weaken the suite."""
        self.assertIn(
            '_ROCPD_OUTPUT = "ROCPROFSYS_USE_ROCPD=true"',
            DIAGNOSTICS.read_text(),
        )


if __name__ == "__main__":
    unittest.main()
