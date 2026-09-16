#!/usr/bin/env python3
"""Controls for `--phase N`: selecting a window by index instead of transcribing ns.

Every windowed subcommand took an absolute `--start-ns`/`--end-ns` pair, so a session
copied boundaries out of a phase table into each call by hand — about a dozen times in one
analysis. That is the transcription defect `conventions/repeated-work.md` names, and a
mistyped or stale boundary returns a *plausible* window with no error at all.

Adding `phase_segmentation` to the payload (2026-09-15) made a mismatch **detectable**.
`--phase N` removes the transcription instead, by resolving the index against the same
segmentation and the same `--max-phases` cap that produced the table.

Two things here are easy to get wrong.

**The cap is part of the answer.** Phase boundaries depend on the capture *and* on
`--max-phases`, so `--phase 2` under two different caps is two different windows. The
control asserts that moving the cap moves the resolved window, which is what stops the
flag from silently pinning one segmentation.

**Resolution must not cost a whole summary.** `cmd_phases` once computed the full summary
and discarded eleven fields; resolving a boundary needs the segmentation only, and
`test_resolution_does_not_compute_a_full_summary` fails if that regresses.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

from gpu_profile.detect import open_profile  # noqa: E402
from gpu_profile.phases import detect_phases  # noqa: E402
from gpu_profile_fixtures import build_synthetic_nsys_db  # noqa: E402


def _load_cli():
    """Import the hyphenated CLI script as a module so `_window` can be unit-tested."""
    import importlib.util

    path = ROOT / "tools" / "gpu-profile-summary.py"
    spec = importlib.util.spec_from_file_location("gpu_profile_summary_cli", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CLI = _load_cli()


class PhaseWindowBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = build_synthetic_nsys_db(self.dir / "p.sqlite")
        self.profile = open_profile(self.path)

    def tearDown(self) -> None:
        self.profile.close()
        self._tmp.cleanup()

    @staticmethod
    def _args(**kw):
        base = {"start_ns": None, "end_ns": None, "phase": None, "max_phases": 8}
        base.update(kw)
        return type("Args", (), base)()


class TestPhaseResolution(PhaseWindowBase):
    def test_phase_index_resolves_to_that_phase_boundary(self) -> None:
        phases = detect_phases(self.profile, max_phases=8)
        for i, ph in enumerate(phases, start=1):
            win = CLI._window(self._args(phase=i), self.profile)
            self.assertEqual(win, (ph.start_ns, ph.end_ns), f"phase {i}")

    def test_explicit_ns_pair_still_works_unchanged(self) -> None:
        win = CLI._window(self._args(start_ns=10, end_ns=20), self.profile)
        self.assertEqual(win, (10, 20))

    def test_no_window_argument_returns_none(self) -> None:
        self.assertIsNone(CLI._window(self._args(), self.profile))

    def test_cap_changes_the_resolved_window(self) -> None:
        """The negative control: the cap is part of the answer, not decoration.

        If --phase ignored --max-phases this would pass trivially by returning the same
        window twice, so the assertion is that the two differ whenever the segmentations
        do.
        """
        wide = detect_phases(self.profile, max_phases=8)
        narrow = detect_phases(self.profile, max_phases=1)
        if len(wide) == len(narrow):
            self.skipTest("fixture does not segment differently under the two caps")
        w1 = CLI._window(self._args(phase=1, max_phases=8), self.profile)
        n1 = CLI._window(self._args(phase=1, max_phases=1), self.profile)
        self.assertNotEqual(
            w1, n1, "--phase must resolve against the cap it was given"
        )

    def test_resolution_does_not_compute_a_full_summary(self) -> None:
        """Segmentation only. A full summary costs roughly three times as much."""
        with mock.patch.object(
            CLI, "compute_profile_summary", side_effect=AssertionError("full summary")
        ):
            win = CLI._window(self._args(phase=1), self.profile)
        self.assertIsNotNone(win)


class TestPhaseErrors(PhaseWindowBase):
    def test_phase_with_explicit_ns_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            CLI._window(self._args(phase=1, start_ns=5), self.profile)
        self.assertIn("mutually exclusive", str(cm.exception))

    def test_phase_is_one_based(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            CLI._window(self._args(phase=0), self.profile)
        self.assertIn("1-based", str(cm.exception))

    def test_out_of_range_names_the_cap_and_the_count(self) -> None:
        """An out-of-range index must say what segmentation it was resolved against."""
        n = len(detect_phases(self.profile, max_phases=8))
        with self.assertRaises(SystemExit) as cm:
            CLI._window(self._args(phase=n + 5), self.profile)
        msg = str(cm.exception)
        self.assertIn("out of range", msg)
        self.assertIn("--max-phases", msg)
        self.assertIn(str(n), msg)


class TestPhaseFlagIsRegistered(unittest.TestCase):
    def test_every_windowed_subcommand_accepts_phase_and_max_phases(self) -> None:
        """A flag registered on some windowed subcommands and not others is a trap."""
        parser = CLI.build_parser()
        choices = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]
        windowed = [
            name
            for name, sp in choices.items()
            if any("--start-ns" in a.option_strings for a in sp._actions)
        ]
        self.assertIn("gap-detail", windowed)
        self.assertIn("idle-attribution", windowed)
        for name in windowed:
            opts = {o for a in choices[name]._actions for o in a.option_strings}
            self.assertIn("--phase", opts, f"{name} takes ns but not --phase")
            self.assertIn("--max-phases", opts, f"{name} takes --phase but not the cap")


if __name__ == "__main__":
    unittest.main()
