#!/usr/bin/env python3
"""Warnings about open upstream defects stay until the defect is fixed and validated.

A warning deleted in a tidy-up is the failure this guards: the defect is still live, and the
next session writes a corrupt file with nothing to stop it. Each entry names the files that
must carry the warning and the issue links it must cite. Remove an entry only on the trigger
recorded in ROADMAP.md's deferred-decision register, with a DEVLOG entry naming the fix and
its validation.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QIO_19 = "https://github.com/usqcd-software/qio/issues/19"
QUDA_1655 = "https://github.com/lattice/quda/issues/1655"

# defect -> (canonical leaf, issue links, files that must point to the canonical leaf)
OPEN_DEFECTS = {
    "qio-parallel-singlefile-writes-on-nfs": (
        "software/qio/parallel-singlefile-writes.md",
        (QIO_19, QUDA_1655),
        (
            "software/qio/README.md",
            "machines/vista/notes.md",
            "machines/horizon/notes.md",
            "software/quda/internals/vector-io-layout.md",
            "machines/vista/stacks/quda-cuda12-milc-cg-2026q3/stack.yaml",
            "machines/vista/stacks/quda-cuda13-milc-cg-2026q3/stack.yaml",
            "machines/vista/stacks/milc-cuda12-quda-ks-spectrum-2026q3/stack.yaml",
            "machines/vista/stacks/milc-cuda13-quda-ks-spectrum-2026q3/stack.yaml",
        ),
    ),
}


class OpenUpstreamDefectTests(unittest.TestCase):
    def test_canonical_leaf_carries_the_warning_and_every_issue_link(self):
        for defect, (leaf, issues, _) in OPEN_DEFECTS.items():
            with self.subTest(defect=defect):
                text = (ROOT / leaf).read_text()
                self.assertIn("WARNING — open upstream defect", text)
                self.assertIn("Keep this warning until", text)
                for issue in issues:
                    self.assertIn(issue, text)

    def test_every_pointer_is_still_in_place(self):
        for defect, (leaf, _, pointers) in OPEN_DEFECTS.items():
            name = Path(leaf).name
            for path in pointers:
                with self.subTest(defect=defect, path=path):
                    self.assertIn(name, (ROOT / path).read_text())

    def test_prominent_warnings_stay_prominent(self):
        # The README and the machine notes must warn before their first section, not deep
        # inside one, and must cite the issues themselves.
        for path in (
            "software/qio/README.md",
            "machines/vista/notes.md",
            "machines/horizon/notes.md",
        ):
            with self.subTest(path=path):
                body = (ROOT / path).read_text().split("\n---\n", 1)[1]
                head = body.split("\n## ", 1)[0]
                self.assertIn("WARNING — open upstream defect", head)
                self.assertIn(QIO_19, head)
                self.assertIn(QUDA_1655, head)

    def test_removal_trigger_is_recorded(self):
        roadmap = (ROOT / "ROADMAP.md").read_text()
        self.assertIn("Removing the warnings about QIO parallel single-file writes on NFS", roadmap)
        self.assertIn("tests/test_open_upstream_defects.py", roadmap)


if __name__ == "__main__":
    unittest.main()
