import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class MILCApplicationGuideTests(unittest.TestCase):
    def test_three_application_guides_are_version_scoped_and_indexed(self):
        index = (ROOT / "software/INDEX.md").read_text()
        for name in ("ks-spectrum", "ks-measure", "ks-imp-rhmc"):
            path = ROOT / "software/milc/applications" / f"{name}.md"
            self.assertTrue(path.is_file(), path)
            metadata = frontmatter(path)
            self.assertEqual(metadata["scope"], ["software:milc"])
            self.assertEqual(metadata["evidence"], "source")
            observed = metadata["observed_on"]["software"]["milc"]
            self.assertTrue(observed["commit"])
            self.assertEqual(observed["branch"], "develop")
            self.assertIn(f"milc/applications/{name}.md", index)

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
