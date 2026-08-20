import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class MILCApplicationGuideTests(unittest.TestCase):
    def test_application_guides_are_version_scoped_and_indexed(self):
        index = (ROOT / "software/INDEX.md").read_text()
        expected_branches = {
            "ks-spectrum": "develop",
            "ks-measure": "develop",
            "ks-imp-rhmc": "develop",
            "wilson-flow": "develop",
        }
        for name, branch in expected_branches.items():
            path = ROOT / "software/milc/applications" / f"{name}.md"
            self.assertTrue(path.is_file(), path)
            metadata = frontmatter(path)
            self.assertEqual(metadata["scope"], ["software:milc"])
            self.assertEqual(metadata["evidence"], "source")
            observed = metadata["observed_on"]["software"]["milc"]
            self.assertTrue(observed["commit"])
            self.assertEqual(observed["branch"], branch)
            self.assertIn("Compiling", metadata["load_when"])
            self.assertIn(f"milc/applications/{name}.md", index)

    def test_all_application_guides_own_portable_build_routing(self):
        expected = {
            "ks-spectrum": ("ks_spectrum", "ks_spectrum_hisq"),
            "ks-measure": ("ks_measure", "ks_measure_hisq"),
            "ks-imp-rhmc": ("ks_imp_rhmc", "su3_rhmc_hisq"),
            "wilson-flow": ("wilson_flow", "wilson_flow_bbb"),
        }
        for name, markers in expected.items():
            with self.subTest(application=name):
                guide = (
                    ROOT / "software/milc/applications" / f"{name}.md"
                ).read_text()
                self.assertIn("## Portable build recipe", guide)
                self.assertIn("`../build.md`", guide)
                for marker in markers:
                    self.assertIn(marker, guide)

    def test_composed_milc_stacks_route_to_portable_recipes(self):
        stack_paths = sorted(ROOT.glob("machines/*/stacks/milc-*/stack.yaml"))
        self.assertTrue(stack_paths)
        for path in stack_paths:
            with self.subTest(stack=path):
                stack = yaml.safe_load(path.read_text())
                recipe = stack["build"]["portable_recipe"]
                self.assertTrue((ROOT / recipe).is_file(), recipe)

        perlmutter = yaml.safe_load(
            (
                ROOT
                / "machines/perlmutter/stacks/"
                "milc-cuda13-quda-wilson-flow-2026q3/stack.yaml"
            ).read_text()
        )
        nearest = perlmutter["build"]["nearest_application_stack"]
        self.assertTrue((ROOT / nearest).is_file(), nearest)

    def test_application_timer_boundaries_remain_distinct(self):
        spectrum = (
            ROOT / "software/milc/applications/ks-spectrum.md"
        ).read_text()
        measure = (
            ROOT / "software/milc/applications/ks-measure.md"
        ).read_text()
        rhmc = (
            ROOT / "software/milc/applications/ks-imp-rhmc.md"
        ).read_text()

        self.assertIn("first top-level interval begins before global `setup()`", spectrum)
        self.assertIn("starts immediately before `readin()`", measure)
        self.assertIn("excludes global setup", measure)
        self.assertIn("before performing the requested ending-lattice", rhmc)
        self.assertIn("`warms` counts RHMC warmup trajectories", rhmc)

    def test_ks_spectrum_artifacts_follow_save_destinations_and_records(self):
        path = ROOT / "software/milc/applications/ks-spectrum.md"
        spectrum = path.read_text()
        sources = frontmatter(path)["sources"]

        self.assertTrue(any("generic/io_helpers.c" in source for source in sources))
        self.assertTrue(any("spectrum_ks.c" in source for source in sources))
        for marker in (
            "`forget_corr`",
            "`save_corr_fnal <path>`",
            "unique resolved destinations",
            "append mode",
            "`STARTPROP`",
            "`ENDPROP`",
            "requested output route",
        ):
            self.assertIn(marker, spectrum)
        self.assertIn("same correlator-label/momentum-label pair", spectrum)
        self.assertIn("`nt` indexed real/imaginary samples", spectrum)
        self.assertIn("can continue", spectrum)

    def test_wilson_flow_backend_and_endpoint_boundaries_are_explicit(self):
        path = ROOT / "software/milc/applications/wilson-flow.md"
        guide = path.read_text()
        sources = frontmatter(path)["sources"]

        self.assertTrue(any("wilson_flow/integrate_quda.c" in source for source in sources))
        self.assertTrue(any("wilson_flow/staple.c" in source for source in sources))
        self.assertTrue(any("lib/interface_quda.cpp" in source for source in sources))
        for marker in (
            "`stoptime / stepsize`",
            "actual final flow-time contract",
            "empty placeholder",
            "without copying the evolved links back",
            "`writeGaugeQuda` with `QUDA_SMEARED_LINKS`",
            "`continue` remains unqualified",
            "`REMAP_STDIO_APPEND`",
            "`forget` ending-lattice handling",
            '`LDFLAGS="-g -fopenmp -lgomp"`',
        ):
            self.assertIn(marker, guide)

        profiles = yaml.safe_load(
            (ROOT / "software/milc/build-profiles.yaml").read_text()
        )["profiles"]
        self.assertIn("wilson-flow-quda", profiles)
        composition = profiles["wilson-flow-quda"]["composes"]["quda"]
        self.assertEqual(composition["profile"], "milc-cg")
        self.assertEqual(
            composition["required_capabilities"]["gauge_operations"],
            ["wilson-flow"],
        )

    def test_build_playbook_prefers_composition_and_checkout_reuse(self):
        playbook = (ROOT / "playbooks/build-lqcd-stack.md").read_text()
        for marker in (
            "Use the composition fast path",
            "sufficient for the first build attempt",
            "Treat build and link as the cheapest compatibility probe",
            "prefer using it",
            "Do not create a second checkout solely",
            "inherited versus newly demonstrated",
        ):
            self.assertIn(marker, playbook)

    def test_timing_policy_and_mode_routing_are_explicit(self):
        timing = (ROOT / "software/milc/timing.md").read_text()
        build = (ROOT / "software/milc/build.md").read_text()
        self.assertIn("required for tuning and benchmarking builds", timing)
        self.assertIn("record its resolved value", timing)
        self.assertIn("timing definitions described in `timing.md`", build)

        for mode in ("tuning", "benchmarking"):
            text = (ROOT / "modes" / f"{mode}.md").read_text()
            self.assertIn("application guide", text)


if __name__ == "__main__":
    unittest.main()
