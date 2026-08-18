import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class MeasurementConventionTests(unittest.TestCase):
    def test_measurement_convention_is_universal_and_indexed(self):
        path = ROOT / "conventions/measurement.md"
        metadata = frontmatter(path)
        self.assertEqual(metadata["scope"], ["universal"])
        self.assertEqual(metadata["evidence"], "operator")
        self.assertIn(
            "(measurement.md)",
            (ROOT / "conventions/INDEX.md").read_text(),
        )

    def test_observed_ledgers_and_projections_remain_separate(self):
        text = (ROOT / "conventions/measurement.md").read_text()
        self.assertIn("one observed workflow ledger per run", text)
        self.assertIn("Keep production projection separate", text)
        self.assertIn(
            "workflow-cost ledger is not the submission-budget ledger", text
        )
        for field in (
            "evidence source",
            "boundary",
            "occurrence count",
            "recurrence",
            "accounting role",
            "warm state",
            "validity",
            "limitation",
        ):
            self.assertIn(f"| {field} |", text)

    def test_accounting_requires_compatible_nonoverlapping_terms(self):
        text = (ROOT / "conventions/measurement.md").read_text()
        self.assertIn("select one parent clock", text)
        self.assertIn("non-overlapping child terms", text)
        self.assertIn(
            "residual = parent clock - sum(compatible non-overlapping partition terms)",
            text,
        )
        self.assertIn("Complete closure is not required", text)

    def test_artifact_contract_is_predeclared_exact_and_layered(self):
        convention = (ROOT / "conventions/measurement.md").read_text()
        benchmark = (ROOT / "modes/benchmarking.md").read_text()
        for text in (convention, benchmark):
            self.assertIn("expected-artifact manifest", text)
            self.assertIn("final generated input", text)
            self.assertIn("missing", text)
            self.assertIn("unexpected", text)

        self.assertIn("new run-owned validation root", convention)
        self.assertIn("Deduplicate repeated destination paths", convention)
        for layer in (
            "structural validity",
            "numerical validity",
            "scientific validity",
        ):
            self.assertIn(layer, convention)
        self.assertIn("nonzero", convention)

    def test_steady_state_solver_series_rule_is_routed(self):
        convention = (ROOT / "conventions/measurement.md").read_text()
        benchmark = (ROOT / "modes/benchmarking.md").read_text()
        for text in (convention, benchmark):
            self.assertIn("multiple", text)
            self.assertIn("homogeneous", text)
            self.assertIn("Exclude the first solve", text)
            self.assertIn("default because", text)
            self.assertIn("single solve", text)
        for mode in ("tuning", "benchmarking"):
            self.assertIn(
                "conventions/measurement.md",
                (ROOT / "modes" / f"{mode}.md").read_text(),
            )

    def test_milc_whole_application_clock_is_a_cross_check(self):
        timing_path = ROOT / "software/milc/timing.md"
        timing = timing_path.read_text()
        sources = frontmatter(timing_path)["sources"]
        self.assertTrue(any("generic/com_mpi.c" in source for source in sources))
        self.assertIn("`start: <date/time>`", timing)
        self.assertIn("`exit: <date/time>`", timing)
        self.assertIn("`termination:`", timing)
        self.assertIn("## Whole-application timestamps", timing)
        self.assertIn("before its final MPI barrier", timing)
        self.assertIn("authoritative allocation clock", timing)

        spectrum = (
            ROOT / "software/milc/applications/ks-spectrum.md"
        ).read_text()
        self.assertIn("One normally exiting process emits one", spectrum)
        self.assertIn("normal `exit:` marker is present", spectrum)


if __name__ == "__main__":
    unittest.main()
