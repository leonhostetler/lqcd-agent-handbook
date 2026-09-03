import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MG_DIR = ROOT / "software/quda/solvers/staggered-multigrid"


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class Stage5GuidanceTests(unittest.TestCase):
    def test_manifest_and_four_action_leaves_are_scoped_and_indexed(self):
        expected = {
            "calibration.md": "experiment",
            "hierarchy-and-setup.md": "experiment",
            "coarse-deflation.md": "experiment",
            "tuning.md": "inferred",
            "diagnostics.md": "experiment",
        }
        index = (ROOT / "software/INDEX.md").read_text()
        for name, evidence in expected.items():
            with self.subTest(leaf=name):
                path = MG_DIR / name
                metadata = frontmatter(path)
                self.assertEqual(metadata["evidence"], evidence)
                self.assertIn("solver:multigrid", metadata["scope"])
                self.assertIn(f"quda/solvers/staggered-multigrid/{name}", index)

    def test_calibration_manifest_is_corpus_independent(self):
        text = (MG_DIR / "calibration.md").read_text()
        for detail in (
            "raw run records are not committed",
            "Literal MILC input masses",
            "m` is the literal positive `mass",
            "Population by advisory",
            "What “closely matched” means",
            "multiple QUDA builds",
        ):
            self.assertIn(detail.replace("`", chr(96)), text)

    def test_hierarchy_metrics_are_advisories_not_source_constraints(self):
        text = (MG_DIR / "hierarchy-and-setup.md").read_text()
        # Role names, not level indices -- ARCHITECTURE.md 5.4. The definition and the
        # non-separability caveat must both survive the rename.
        self.assertIn(
            "coarsest_vector_density = coarsest_deflation_count / coarsest_global_volume",
            text,
        )
        # Assert the claim, not its punctuation: the corpus cannot distinguish the
        # requested density from the fraction of the complete coarse colour space.
        self.assertIn(
            "separate that density from the fraction of the complete coarse colour space",
            " ".join(text.split()),
        )
        self.assertIn("#level-naming", text)
        self.assertIn("not a QUDA convergence requirement", text)
        # The setup screen counts capped streams; it does not average their iteration
        # counts. A mean-to-cap ratio saturates near 1 once a minority cap out, and
        # `rho_setup` also elided which level it described.
        self.assertIn("setup_l1_capped_fraction", text)
        self.assertIn("Count capped streams; do not average", text)
        self.assertNotIn("`rho_setup <", text)
        self.assertIn("$LQCD_HANDBOOK/tools/quda-staggered-decomposition.py", text)

    def test_spectrum_fit_carries_full_envelope_and_feedback_limits(self):
        text = (MG_DIR / "coarse-deflation.md").read_text()
        for detail in (
            "49",
            "A        = 0.0585",
            "alpha    = 1.551",
            "11.9% RMS",
            "20.4% p90",
            "0.022...0.250",
            "0.000569...0.01555",
            "near-null count on the level above the coarsest",
            "`nvec 2` in a four-level MILC",
            "optimum was not located",
            "4...9",
        ):
            self.assertIn(detail, text)
        self.assertIn("universal lower bound", text)
        self.assertIn("do not transfer either fitted", text)

    def test_observables_have_a_raw_log_extraction_contract(self):
        text = (MG_DIR / "diagnostics.md").read_text()
        for detail in (
            "Observable extraction contract",
            "MG level 1 (GPU): CG:",
            "setup_maxiter 1",
            "MG level <C> (GPU): Eval[NNNN]",
            "restart steps",
            "partial delivery",
        ):
            self.assertIn(detail, text)
        # The coarsest level is 3 at four levels and 2 at three; a fixed prefix reads
        # nothing at three levels, and the contract must say so.
        self.assertIn("`2` in a three-level one", text)
        self.assertNotIn("matching\n  `MG level 3 (GPU)", text)

    def test_timing_class_is_procedural_and_not_a_public_threshold(self):
        tuning = (MG_DIR / "tuning.md").read_text()
        coarse = (MG_DIR / "coarse-deflation.md").read_text()
        diagnostics = (MG_DIR / "diagnostics.md").read_text()
        self.assertIn("supplies no numerical solver timing or crossover threshold", tuning)
        self.assertIn("Nstar = Delta I / -Delta R", coarse)
        self.assertIn("No corpus timing, crossover", coarse)
        self.assertIn("No numerical solver timing or crossover", diagnostics)

    def test_mrhs_mg_boundary_remains_explicit(self):
        memory = (ROOT / "software/quda/solvers/staggered-memory.md").read_text()
        tool = (ROOT / "tools/quda-staggered-memory.py").read_text()
        self.assertIn("MRHS-MG: marginal slope only", memory)
        self.assertIn("does **not** define an absolute MRHS-MG capacity model", memory)
        self.assertIn("5467.3 MiB", memory)
        self.assertNotIn('add_parser("mrhs-mg', tool)


if __name__ == "__main__":
    unittest.main()
