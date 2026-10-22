"""A five-level staggered-MG hierarchy is screened by the same rules, one aggregation deeper.

Five levels means three aggregations: MILC `nvec 1`, `nvec 2` and `nvec 3` are coarse
colours and `nvec 4` is the coarsest-deflation count -- the "last nvec key is a deflation
count" rule of software/quda/solvers/staggered-multigrid.md#level-naming, applied at a level
count the tools used to refuse. Every per-step source rule, the compiled-colour list, the
MMA colour rule and the MMA pair rule must reach the third aggregation; the corpus bands,
fitted at four levels, must still be declined; and no four-level number may move.

The memory model's phase E (the level-4 build) is a structural extrapolation. The test
pins its shape and its loud warning, never a value.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECOMPOSITION = ROOT / "tools/quda-staggered-decomposition.py"
MEMORY = ROOT / "tools/quda-staggered-memory.py"


def run(tool: Path, *args: str):
    result = subprocess.run(
        [sys.executable, str(tool), *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    payload = json.loads(result.stdout) if result.stdout.strip().startswith("{") else None
    return result, payload


# A 96^3 x 192 lattice on 16 ranks, local 48 48 48 96: three aggregations of 4 4 4 4,
# 2 2 2 2 and 3 3 3 2 coarsen to 24 24 24 16 and a 768-site coarsest grid (the geometry is
# the point, not the adequacy of that grid).
FIVE_LEVEL = (
    "--global", "96", "96", "96", "192", "--ranks", "2", "2", "2", "2",
    "--levels", "5",
    "--block1", "4", "4", "4", "4", "--block2", "2", "2", "2", "2", "--block3", "3", "3", "3", "2",
    "--nvec1", "64", "--nvec2", "96", "--nvec3", "96",
)
# The four-level member with the same first block and the same coarsest grid.
FOUR_LEVEL = (
    "--global", "96", "96", "96", "192", "--ranks", "2", "2", "2", "2",
    "--levels", "4",
    "--block1", "4", "4", "4", "4", "--block2", "6", "6", "6", "4",
    "--nvec1", "64", "--nvec2", "96",
)
COMPILED = ("--compiled-nvecs", "24", "64", "96", "112", "128")


class FiveLevelDecompositionTests(unittest.TestCase):
    def test_three_aggregations_execute_as_requested(self):
        result, payload = run(DECOMPOSITION, *FIVE_LEVEL, "--nvec4", "2048", *COMPILED, "--mma")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["source_status"], "pass", payload["source_errors"])
        self.assertEqual(payload["levels_count"], 5)
        self.assertEqual(
            payload["effective_blocks"], [[4, 4, 4, 4], [2, 2, 2, 2], [3, 3, 3, 2]]
        )
        self.assertFalse(payload["requested_blocks_changed"])
        self.assertEqual(len(payload["levels"]), 3)
        self.assertEqual(payload["coarsest_local_dims"], [2, 2, 2, 6])

    def test_the_coarsest_role_names_and_the_level_four_aliases(self):
        _, payload = run(DECOMPOSITION, *FIVE_LEVEL, "--nvec4", "96", "--mma")
        metrics = payload["metrics"]
        self.assertEqual(metrics["coarsest_global_volume"], 768)
        self.assertEqual(metrics["coarsest_cell_sites"], [24, 24, 24, 16])
        self.assertAlmostEqual(metrics["coarsest_vector_density"], 96 / 768)
        # The numbered alias names the coarsest level by its index, so at five levels it is
        # V4/nu4 and V3/nu3 must not exist: they would name a different grid.
        self.assertEqual(metrics["V4_global"], 768)
        self.assertAlmostEqual(metrics["nu4"], 96 / 768)
        self.assertNotIn("V3_global", metrics)
        self.assertNotIn("nu3", metrics)
        # coarse_fine_work squares the coarse gauge colour of the level above the coarsest,
        # which is nvec 3 at five levels.
        self.assertEqual(metrics["coarse_gauge_colour"], 192)
        self.assertEqual(metrics["coarse_fine_work_basis"], "2*nvec_3=192 over N_c=3")
        self.assertAlmostEqual(
            metrics["coarse_fine_work"], 768 * 192**2 / (96**3 * 192 * 9)
        )

    def test_the_same_coarsest_grid_prices_the_same_at_four_and_five_levels(self):
        _, five = run(DECOMPOSITION, *FIVE_LEVEL, "--nvec4", "96", "--mma")
        _, four = run(DECOMPOSITION, *FOUR_LEVEL, "--nvec3", "96", "--mma")
        self.assertEqual(four["metrics"]["coarsest_global_volume"], 768)
        self.assertEqual(
            five["metrics"]["coarse_fine_work"], four["metrics"]["coarse_fine_work"]
        )

    def test_every_coarse_colour_and_both_mma_pairs_are_checked(self):
        _, payload = run(DECOMPOSITION, *FIVE_LEVEL, *COMPILED, "--mma")
        capability = payload["build_capability"]
        compiled = capability["QUDA_MULTIGRID_NVEC_LIST"]
        self.assertEqual(
            [item["parameter"] for item in compiled["required"]], ["nvec1", "nvec2", "nvec3"]
        )
        self.assertEqual(compiled["status"], "pass")
        colours = capability["QUDA_MMA_COARSE_GAUGE_COLOR"]
        self.assertEqual(
            [item["coarse_gauge_color"] for item in colours["required"]], [128, 192, 192]
        )
        pairs = capability["QUDA_MMA_COARSE_COLOR_PAIR"]
        self.assertEqual(
            [item["pair"] for item in pairs["required"]], [[64, 96], [96, 96]]
        )
        self.assertEqual(pairs["status"], "pass")

    def test_an_uninstantiated_second_pair_is_source_invalid(self):
        """64 -> 96 is instantiated and 96 -> 64 is not: the second pair must be the one that fails."""
        args = [a for a in FIVE_LEVEL]
        args[args.index("--nvec3") + 1] = "64"
        result, payload = run(DECOMPOSITION, *args, "--mma")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["source_status"], "error")
        self.assertTrue(
            any("nvec2->nvec3 = 96 -> 64" in e for e in payload["source_errors"]),
            payload["source_errors"],
        )

    def test_a_third_coarse_colour_missing_from_the_compiled_list_fails(self):
        args = [a for a in FIVE_LEVEL]
        args[args.index("--nvec3") + 1] = "64"
        result, payload = run(
            DECOMPOSITION, *args, "--compiled-nvecs", "24", "96", "128", "--no-mma"
        )
        self.assertEqual(payload["build_capability"]["QUDA_MULTIGRID_NVEC_LIST"]["status"], "fail")
        self.assertTrue(any("nvec1=64 is absent" in e for e in payload["source_errors"]))

    def test_the_third_aggregation_is_halved_like_the_others(self):
        """Level-3 local 6 6 6 12: a 2 2 2 2 third block would leave odd spatial extents."""
        result, payload = run(
            DECOMPOSITION, *FIVE_LEVEL[:FIVE_LEVEL.index("--block3")],
            "--block3", "2", "2", "2", "2", "--nvec1", "64", "--nvec2", "96", "--nvec3", "96",
        )
        self.assertEqual(payload["source_status"], "pass", payload["source_errors"])
        self.assertTrue(payload["requested_blocks_changed"])
        self.assertEqual(payload["effective_blocks"][2], [1, 1, 1, 2])
        self.assertEqual(payload["levels"][2]["requested_block"], [2, 2, 2, 2])

    def test_the_cap_binds_the_third_aggregation(self):
        # One rank: local 96 96 96 192 -> 24 24 24 48 -> 12 12 12 24. A 6 6 6 12 third block
        # divides it, leaves even coarse extents, and has product 2592 -- over the cap, so no
        # halving rescues it and the error names level 3.
        result, payload = run(
            DECOMPOSITION, "--global", "96", "96", "96", "192", "--ranks", "1", "1", "1", "1",
            "--levels", "5", "--block1", "4", "4", "4", "4", "--block2", "2", "2", "2", "2",
            "--block3", "6", "6", "6", "12", "--nvec1", "64", "--nvec2", "96", "--nvec3", "96",
        )
        self.assertEqual(result.returncode, 2)
        self.assertTrue(
            any("level 3" in e and "must be <= 1024" in e for e in payload["source_errors"]),
            payload["source_errors"],
        )

    def test_corpus_bands_are_still_declined_at_five_levels(self):
        _, payload = run(DECOMPOSITION, *FIVE_LEVEL, "--nvec4", "96", "--corpus-advisories")
        screen = payload["empirical_screen"]
        self.assertFalse(screen["evaluated"])
        self.assertEqual(len(screen["advisories"]), 1)
        self.assertIn("this hierarchy has 5", screen["advisories"][0])

    def test_block3_and_nvec4_are_refused_below_five_levels(self):
        result, _ = run(
            DECOMPOSITION, *FOUR_LEVEL, "--block3", "3", "3", "3", "2", "--nvec3", "96"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("block3 is not used", result.stderr)
        result, _ = run(DECOMPOSITION, *FOUR_LEVEL, "--nvec3", "96", "--nvec4", "96")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nvec4 is not used", result.stderr)

    def test_five_levels_without_a_third_aggregation_is_refused(self):
        args = [a for a in FIVE_LEVEL]
        i = args.index("--block3")
        del args[i:i + 5]
        result, _ = run(DECOMPOSITION, *args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("five-level MG requires block3", result.stderr)


class FiveLevelMemoryTests(unittest.TestCase):
    MG = ("mg-fit", *FIVE_LEVEL, "--nvec4", "256", "--mma", "--machine", "other",
          "--gpu-gib", "80", "--margin-gib", "4")

    def test_phase_e_is_reported_and_the_estimate_is_loudly_unvalidated(self):
        result, payload = run(MEMORY, *self.MG)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["evidence"], "unvalidated-structural-extrapolation")
        detail = payload["detail"]
        self.assertEqual(detail["mg_levels"], 5)
        self.assertEqual(sorted(detail["phase_gib"]), ["A", "B", "C", "E"])
        self.assertEqual(detail["deflation_phase"], "E")
        self.assertEqual(detail["x4"], [2, 2, 2, 6])
        self.assertEqual(detail["V4_local"], 48)
        self.assertEqual(detail["post_setup_phase_D"]["status"], "not-modelled-above-four-levels")
        self.assertTrue(any("5-level MG high-water has never been" in w for w in payload["warnings"]))
        self.assertIn("LOUD WARNING: 5-level MG", result.stderr)

    def test_phase_e_carries_the_level_four_objects_and_the_eigenspace(self):
        _, payload = run(MEMORY, *self.MG)
        detail = payload["detail"]
        # Phase E is not the winner for this placement, so read its terms through the
        # phase totals: E must respond to the deflation count and the lower phases must not.
        _, bigger = run(MEMORY, *[a if a != "256" else "512" for a in self.MG])
        self.assertGreater(bigger["detail"]["phase_gib"]["E"], detail["phase_gib"]["E"])
        for phase in ("A", "B", "C"):
            self.assertAlmostEqual(
                bigger["detail"]["phase_gib"][phase], detail["phase_gib"][phase], places=6
            )
        if detail["winning_phase"] != "E":
            self.assertFalse(detail["deflation_enters_total"])
            self.assertTrue(any("nvec_4=256 does not enter" in w for w in payload["warnings"]))

    def test_the_first_two_aggregations_price_as_at_four_levels(self):
        """Phases A and B see no third aggregation, so they equal the four-level member's."""
        _, five = run(MEMORY, *self.MG)
        _, four = run(
            MEMORY, "mg-fit", *FOUR_LEVEL, "--nvec3", "256", "--mma", "--machine", "other",
            "--gpu-gib", "80", "--margin-gib", "4",
        )
        for phase in ("A", "B"):
            self.assertAlmostEqual(
                five["detail"]["phase_gib"][phase], four["detail"]["phase_gib"][phase], places=6
            )

    def test_the_local_mode_accepts_a_third_aggregation(self):
        result, payload = run(
            MEMORY, "mg-fit", "--local", "48", "48", "48", "96", "--partitioned", "1", "1", "1", "1",
            "--levels", "5", "--block1", "4", "4", "4", "4", "--block2", "2", "2", "2", "2",
            "--block3", "3", "3", "3", "2", "--nvec1", "64", "--nvec2", "96", "--nvec3", "96",
            "--nvec4", "0", "--no-mma",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["geometry"]["effective_blocks"][2], [3, 3, 3, 2])

    def test_nvec4_is_refused_below_five_levels(self):
        result, _ = run(
            MEMORY, "mg-fit", *FOUR_LEVEL, "--nvec3", "96", "--nvec4", "96", "--mma",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nvec4 is not used", result.stderr)

    def test_the_search_enumerates_five_level_rungs(self):
        result, payload = run(
            MEMORY, "mg-search", "--global", "64", "64", "64", "96", "--nodes-lt", "3",
            "--machine", "perlmutter-a100-40", "--levels", "5",
            "--block1", "4", "4", "4", "4", "--block2", "2", "2", "2", "2", "--block3", "2", "2", "2", "1",
            "--nvec1", "64", "--nvec2", "96", "--nvec3", "96", "--nvec4", "512", "--no-mma",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["parameters"]["levels"], 5)
        self.assertEqual(payload["parameters"]["requested_block3"], [2, 2, 2, 1])
        self.assertEqual(payload["parameters"]["nvec4"], 512)
        self.assertGreater(payload["counts"]["rank_geometries_considered"], 0)


if __name__ == "__main__":
    unittest.main()
