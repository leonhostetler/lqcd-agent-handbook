import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class RunningConventionTests(unittest.TestCase):
    def test_running_convention_is_universal_and_indexed(self):
        path = ROOT / "conventions/running.md"
        metadata = frontmatter(path)
        self.assertEqual(metadata["scope"], ["universal"])
        self.assertEqual(metadata["evidence"], "operator")
        self.assertIn("(running.md)", (ROOT / "conventions/INDEX.md").read_text())

    def test_dispositions_are_small_and_statistical_treatment_is_explicit(self):
        text = (ROOT / "conventions/running.md").read_text()
        normalized = " ".join(text.split())
        for disposition in (
            "`accepted`",
            "`rejected`",
            "`incomplete`",
            "`no-trial`",
            "`indeterminate`",
        ):
            self.assertIn(disposition, text)
        self.assertIn("Only `accepted` runs enter confirmatory", normalized)
        self.assertIn("deliberately truncated benchmark", text)

    def test_independent_evidence_and_attribution_are_reconciled(self):
        text = (ROOT / "conventions/running.md").read_text()
        for evidence in (
            "scheduler",
            "launcher",
            "accelerator-runtime",
            "application",
            "expected artifacts",
            "correctness",
        ):
            self.assertIn(evidence, text)
        self.assertIn("No single layer decides the result", text)
        self.assertIn("State reason and attribution separately", text)
        self.assertIn("Use `unknown`", text)

    def test_modes_and_measurement_route_to_running_dispositions(self):
        for mode in ("tuning", "benchmarking"):
            text = (ROOT / "modes" / f"{mode}.md").read_text()
            self.assertIn("conventions/running.md", text)
        measurement = (ROOT / "conventions/measurement.md").read_text()
        self.assertIn("disposition", measurement)
        self.assertIn("Only `accepted` runs enter", " ".join(measurement.split()))


if __name__ == "__main__":
    unittest.main()
