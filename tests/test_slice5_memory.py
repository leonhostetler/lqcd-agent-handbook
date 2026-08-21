import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "tools/quda-staggered-memory.py"
DECOMPOSITION = ROOT / "tools/quda-staggered-decomposition.py"


def run_json(tool: Path, *args: str, check: bool = True):
    result = subprocess.run(
        [sys.executable, str(tool), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr)
    return result, json.loads(result.stdout)


class StaggeredMemoryTests(unittest.TestCase):
    def test_source_object_is_labelled_and_exact(self):
        _, payload = run_json(
            MEMORY,
            "spinor",
            "--local",
            "4",
            "4",
            "4",
            "4",
            "--ncolor",
            "3",
            "--nspin",
            "1",
            "--precision",
            "single",
            "--subset",
            "parity",
        )
        self.assertEqual(payload["evidence"], "source-exact-object")
        self.assertEqual(payload["bytes"], 3072)
        self.assertIn("excludes", payload["scope"])

    def test_corpus_fit_carries_population_and_limits(self):
        _, payload = run_json(
            MEMORY,
            "cg-fit",
            "--local",
            "36",
            "36",
            "24",
            "32",
        )
        self.assertEqual(payload["evidence"], "corpus-calibrated")
        self.assertIn("12 measurements", payload["calibration"]["cg_population"])
        self.assertIn("whole-process scheduler RSS", payload["calibration"]["outside_scope"])
        self.assertNotIn("fits", payload)

    def test_plain_cg_mrhs_delta_is_source_derived_and_profile_scoped(self):
        _, payload = run_json(
            MEMORY,
            "mrhs-cg-delta",
            "--local",
            "36",
            "36",
            "24",
            "24",
            "--reference-width",
            "1",
            "--width",
            "3",
        )
        detail = payload["detail"]
        self.assertEqual(payload["evidence"], "source-derived-with-corpus-validation")
        self.assertEqual(detail["V0"], 746496)
        self.assertEqual(detail["additional_active_rhs"], 2)
        self.assertEqual(detail["device_bytes_per_additional_rhs"], 160 * 746496)
        self.assertEqual(detail["device_increment_bytes"], 2 * 160 * 746496)
        self.assertEqual(detail["profile"]["precise_precision"], "double")
        self.assertEqual(detail["profile"]["sloppy_precision"], "half")
        self.assertIn("0.04%", payload["validation"]["device_accuracy"])
        self.assertIn("whole-process scheduler RSS", payload["counter_scope"]["not_modelled"])

    def test_plain_cg_mrhs_delta_rejects_invalid_widths(self):
        for widths in (("0", "1"), ("2", "3")):
            with self.subTest(widths=widths):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(MEMORY),
                        "mrhs-cg-delta",
                        "--local",
                        "8",
                        "8",
                        "8",
                        "16",
                        "--width",
                        widths[0],
                        "--reference-width",
                        widths[1],
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 2)

    def test_no_absolute_mrhs_mg_calculator_is_exposed(self):
        result = subprocess.run(
            [sys.executable, str(MEMORY), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("mrhs-cg-delta", result.stdout)
        self.assertNotIn("mrhs-mg", result.stdout)

    def test_mg_fit_separates_device_pool_and_capacity_advisory(self):
        _, payload = run_json(
            MEMORY,
            "mg-fit",
            "--local",
            "16",
            "16",
            "16",
            "32",
            "--block1",
            "4",
            "4",
            "4",
            "4",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "64",
            "--nvec2",
            "32",
            "--nvec3",
            "0",
            "--mma",
            "--partitioned",
            "1",
            "1",
            "1",
            "1",
            "--gpu-gib",
            "40",
            "--margin-gib",
            "4",
        )
        self.assertEqual(payload["evidence"], "caveated-extrapolation")
        self.assertEqual(payload["model_basis"], "corpus-calibrated-with-source-geometry")
        self.assertEqual(
            payload["geometry"]["build_capability"]["QUDA_MULTIGRID_NVEC_LIST"]["status"],
            "unchecked",
        )
        self.assertIn(payload["detail"]["winning_phase"], ("A", "B", "C"))
        self.assertGreater(payload["pool_gib"], 0)
        self.assertGreater(payload["page_locked_host_gib"], 0)
        self.assertFalse(payload["capacity_advisory"]["guarantee"])
        self.assertNotIn("fits", payload["capacity_advisory"])

    def test_global_mg_fit_integrates_transfer_adjustment_and_partitioning(self):
        _, payload = run_json(
            MEMORY,
            "mg-fit",
            "--global",
            "48",
            "32",
            "32",
            "96",
            "--ranks",
            "2",
            "2",
            "2",
            "3",
            "--block1",
            "8",
            "4",
            "4",
            "4",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "64",
            "--nvec2",
            "32",
            "--nvec3",
            "0",
            "--mma",
            "--machine",
            "perlmutter-a100-40",
        )
        self.assertTrue(payload["geometry"]["requested_blocks_changed"])
        self.assertEqual(payload["geometry"]["effective_blocks"][0], [4, 4, 4, 4])
        self.assertEqual(payload["detail"]["x2"], [6, 4, 4, 8])
        self.assertEqual(payload["geometry"]["partitioned"], [1, 1, 1, 1])
        self.assertTrue(any("runtime block" in item for item in payload["warnings"]))

    def test_calibrated_envelope_is_machine_and_parameter_scoped(self):
        _, payload = run_json(
            MEMORY,
            "mg-fit",
            "--global",
            "144",
            "144",
            "144",
            "288",
            "--ranks",
            "6",
            "3",
            "6",
            "8",
            "--block1",
            "4",
            "6",
            "6",
            "6",
            "--block2",
            "3",
            "2",
            "2",
            "3",
            "--nvec1",
            "64",
            "--nvec2",
            "96",
            "--nvec3",
            "4000",
            "--mma",
            "--compiled-nvecs",
            "24",
            "64",
            "96",
            "112",
            "128",
            "--machine",
            "perlmutter-a100-40",
        )
        assessment = payload["prediction_assessment"]
        self.assertEqual(payload["evidence"], "calibrated-envelope-current-code")
        self.assertEqual(assessment["tier"], "calibrated-envelope-current-code")
        self.assertTrue(assessment["reliable_screening_with_published_error"])
        self.assertEqual(
            payload["geometry"]["build_capability"]["QUDA_MULTIGRID_NVEC_LIST"]["status"],
            "pass",
        )
        self.assertEqual(assessment["failed_envelope_checks"], [])
        self.assertIn("Page-locked", payload["counter_scope"]["page_locked_host_gib"])

    def test_three_level_precision_and_custom_controls_are_loudly_unvalidated(self):
        result, payload = run_json(
            MEMORY,
            "mg-fit",
            "--global",
            "64",
            "64",
            "64",
            "96",
            "--ranks",
            "2",
            "2",
            "2",
            "3",
            "--levels",
            "3",
            "--block1",
            "4",
            "4",
            "4",
            "4",
            "--nvec1",
            "64",
            "--nvec3",
            "2048",
            "--null-precision",
            "single",
            "--setup-ws-bytes-per-site",
            "18000",
            "--no-mma",
            "--machine",
            "perlmutter-a100-40",
        )
        self.assertEqual(
            payload["prediction_assessment"]["tier"],
            "unvalidated-structural-extrapolation",
        )
        self.assertIn(
            "unvalidated structural extrapolation",
            payload["detail"]["phase_model_evidence"],
        )
        self.assertIn("LOUD WARNING", result.stderr)
        self.assertTrue(any("precision" in item for item in payload["warnings"]))
        self.assertTrue(any("custom calibration" in item for item in payload["warnings"]))

    def test_two_level_estimate_is_available_but_never_silent(self):
        result, payload = run_json(
            MEMORY,
            "mg-fit",
            "--global",
            "32",
            "32",
            "32",
            "64",
            "--ranks",
            "1",
            "2",
            "2",
            "2",
            "--levels",
            "2",
            "--nvec3",
            "0",
            "--no-mma",
            "--machine",
            "perlmutter-a100-40",
        )
        self.assertEqual(payload["detail"]["mg_levels"], 2)
        self.assertEqual(payload["detail"]["winning_phase"], "A")
        self.assertEqual(payload["geometry"]["effective_blocks"], [])
        self.assertIn("LOUD WARNING", result.stderr)
        self.assertEqual(
            payload["prediction_assessment"]["tier"],
            "unvalidated-structural-extrapolation",
        )

    def test_search_enumerates_all_rank_geometries_below_exclusive_node_bound(self):
        _, payload = run_json(
            MEMORY,
            "mg-search",
            "--global",
            "32",
            "32",
            "32",
            "64",
            "--nodes-lt",
            "3",
            "--machine",
            "perlmutter-a100-40",
            "--block1",
            "2",
            "2",
            "2",
            "2",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "16",
            "--nvec2",
            "16",
            "--no-mma",
        )
        categories = (
            payload["estimated_headroom_meets_margin"]
            + payload["estimated_headroom_below_margin"]
            + payload["estimated_over_capacity"]
        )
        self.assertTrue(payload["search_contract"]["complete_rank_geometry_enumeration"])
        self.assertEqual(payload["search_contract"]["node_bound"], "1 <= nodes < 3")
        self.assertEqual(payload["search_contract"]["min_local_extent"], 1)
        self.assertEqual(len(categories), payload["counts"]["source_valid_and_modelled"])
        self.assertEqual(
            payload["counts"]["rank_geometries_considered"],
            payload["counts"]["source_valid_and_modelled"]
            + payload["counts"]["source_invalid_after_block_adjustment"]
            + payload["counts"]["memory_model_incompatible"],
        )
        identities = {(row["nodes"], tuple(row["rank_geometry"])) for row in categories}
        self.assertEqual(len(identities), len(categories))
        self.assertTrue(all(row["nodes"] < 3 for row in categories))
        self.assertTrue(all("page_locked_host_gib_per_node" in row for row in categories))
        self.assertEqual(
            payload["search_contract"]["build_capability"]["QUDA_MULTIGRID_NVEC_LIST"]["status"],
            "unchecked",
        )

    def test_transfer_adjustment_is_warning_not_automatic_rejection(self):
        result, payload = run_json(
            DECOMPOSITION,
            "--global",
            "48",
            "32",
            "32",
            "96",
            "--ranks",
            "2",
            "2",
            "2",
            "3",
            "--block1",
            "8",
            "4",
            "4",
            "4",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "64",
            "--nvec2",
            "32",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["source_status"], "pass")
        self.assertEqual(
            payload["build_capability"]["QUDA_MULTIGRID_NVEC_LIST"]["status"],
            "unchecked",
        )
        self.assertTrue(payload["requested_blocks_changed"])
        self.assertEqual(payload["levels"][0]["effective_block"], [4, 4, 4, 4])

    def test_compiled_nvec_check_is_explicitly_unchecked_pass_or_fail(self):
        base = (
            "--global", "64", "64", "64", "96",
            "--ranks", "2", "2", "2", "3",
            "--block1", "4", "4", "4", "4",
            "--block2", "2", "2", "2", "2",
            "--nvec1", "64", "--nvec2", "96", "--nvec3", "4000",
        )
        _, unchecked = run_json(DECOMPOSITION, *base)
        _, passed = run_json(
            DECOMPOSITION, *base, "--compiled-nvecs", "24", "64", "96", "112", "128"
        )
        failed_result, failed = run_json(
            DECOMPOSITION, *base, "--compiled-nvecs", "24", "64", check=False
        )
        key = "QUDA_MULTIGRID_NVEC_LIST"
        self.assertEqual(unchecked["build_capability"][key]["status"], "unchecked")
        self.assertEqual(passed["build_capability"][key]["status"], "pass")
        self.assertEqual(failed_result.returncode, 2)
        self.assertEqual(failed["build_capability"][key]["status"], "fail")
        self.assertEqual(
            failed["build_capability"][key]["missing"],
            [{"parameter": "nvec2", "value": 96}],
        )
        self.assertNotIn(4000, [item["value"] for item in passed["build_capability"][key]["required"]])

    def test_deeper_aggregate_bound_uses_spinor_color_not_gauge_color(self):
        result, payload = run_json(
            DECOMPOSITION,
            "--global",
            "64",
            "64",
            "64",
            "96",
            "--ranks",
            "2",
            "2",
            "2",
            "3",
            "--block1",
            "4",
            "4",
            "4",
            "4",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "4",
            "--nvec2",
            "65",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["source_status"], "error")
        self.assertTrue(any("aggregate size 64" in error for error in payload["source_errors"]))

    def test_empirical_thresholds_are_opt_in_advisories(self):
        base = (
            "--global",
            "64",
            "64",
            "64",
            "96",
            "--ranks",
            "2",
            "2",
            "2",
            "3",
            "--block1",
            "4",
            "4",
            "4",
            "4",
            "--block2",
            "2",
            "2",
            "2",
            "2",
            "--nvec1",
            "64",
            "--nvec2",
            "32",
        )
        _, plain = run_json(DECOMPOSITION, *base)
        _, screened = run_json(DECOMPOSITION, *base, "--corpus-advisories")
        self.assertEqual(plain["source_status"], "pass")
        self.assertFalse(plain["empirical_screen"]["enabled"])
        self.assertEqual(plain["empirical_screen"]["advisories"], [])
        self.assertEqual(screened["source_status"], "pass")
        self.assertTrue(screened["empirical_screen"]["advisories"])

    def test_fit_details_live_in_script_and_public_path_is_current_code_only(self):
        document = (ROOT / "software/quda/solvers/staggered-memory.md").read_text()
        script = MEMORY.read_text()
        for detail in ("12 measurements", "57 multi-rank groups", "maximum 10.7%"):
            self.assertNotIn(detail, document)
            self.assertIn(detail, script)
        self.assertIn("73,920 B per partitioned checkerboarded surface site", script)
        _, fit_payload = run_json(MEMORY, "cg-fit", "--local", "8", "8", "8", "16")
        self.assertNotIn("73920", json.dumps(fit_payload["calibration"]))
        self.assertIn("4374.0 MiB", script)
        help_result = subprocess.run(
            [sys.executable, str(MEMORY), "mg-fit", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertNotIn("--pool-era", help_result.stdout)
        self.assertNotIn("--kd-era", help_result.stdout)
        self.assertIn("tensor-core matrix-multiply-", help_result.stdout)
        self.assertIn("accumulate path", help_result.stdout)
        self.assertIn("not MRHS batch width", help_result.stdout)

    def test_decomposition_accepts_arbitrary_lattice_sizes(self):
        cases = (
            (
                ("80", "96", "112", "128"),
                ("2", "3", "4", "4"),
                ("4", "4", "2", "4"),
                ("1", "2", "1", "2"),
                [40, 32, 28, 32],
            ),
            (
                ("72", "120", "96", "144"),
                ("3", "5", "2", "6"),
                ("4", "4", "4", "4"),
                ("3", "3", "2", "3"),
                [24, 24, 48, 24],
            ),
        )
        for global_dims, ranks, block1, block2, expected_local in cases:
            with self.subTest(global_dims=global_dims):
                _, payload = run_json(
                    DECOMPOSITION,
                    "--global",
                    *global_dims,
                    "--ranks",
                    *ranks,
                    "--block1",
                    *block1,
                    "--block2",
                    *block2,
                    "--nvec1",
                    "64",
                    "--nvec2",
                    "32",
                )
                self.assertEqual(payload["source_status"], "pass")
                self.assertEqual(payload["local_dims"], expected_local)
                self.assertEqual(payload["global_dims"], [int(value) for value in global_dims])

    def test_new_public_files_contain_no_private_paths_or_job_identifiers(self):
        paths = (
            ROOT / "software/quda/solvers/staggered-memory.md",
            ROOT / "software/quda/solvers/staggered-multigrid/calibration.md",
            ROOT / "software/quda/solvers/staggered-multigrid/hierarchy-and-setup.md",
            ROOT / "software/quda/solvers/staggered-multigrid/coarse-deflation.md",
            ROOT / "software/quda/solvers/staggered-multigrid/tuning.md",
            ROOT / "software/quda/solvers/staggered-multigrid/diagnostics.md",
            MEMORY,
            DECOMPOSITION,
            ROOT / "tools/quda_staggered_geometry.py",
        )
        text = "\n".join(path.read_text() for path in paths)
        self.assertNotIn("/home/", text)
        self.assertNotIn("job 56826421", text)
        self.assertNotIn("0.09-agent-handoff", text)


if __name__ == "__main__":
    unittest.main()
