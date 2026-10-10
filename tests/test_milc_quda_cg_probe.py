"""The staggered-CG probe must generate a fair ladder and refuse any run it cannot vouch for.

Inputs: the ladder puts a node's ranks in the fastest dimensions and adds one off-node
dimension per step, for any ranks-per-node the volumes divide into; the MILC inputs carry the
frozen sets and one correlator file per meson; the QUDA commands match MILC's rank order; and
nothing is written for an unfrozen probe without a calibration mass, or for a frozen one with
one. Analysis: a complete synthetic run reports the first-solve-excluded statistics and no
errors, a frozen probe drafts rows, a plaquette differing only by rounding passes, and each way
a run can be incomplete or inconsistent is an error. The control removes the first-solve
exclusion and shows the reported value moves.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import PerturbationMixin  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "milc-quda-cg-probe.py"
MASS, TOL = "0.01", "1e-10"
UNFROZEN = ('"mass": 0.01,\n    "tolerance": 1e-8,', '"mass": None,\n    "tolerance": None,')


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


def fnal(job_id: str, scale: float = 1.0) -> str:
    out = ["---", f"JobID:                        {job_id}", 'date:                         "synthetic"',
           "lattice_size:                 24,24,24,48", "...", "---",
           "correlator:                   PION_5", "correlator_key:               PION_5_p000", "..."]
    out += [f"{t}\t{scale * 0.9 ** t:.6e}\t{0.0:.6e}" for t in range(48)]
    return "\n".join(out) + "\n"


def milc_output(single: list[tuple[float, int, float]], block: list[tuple[float, int, float]],
                plaq="5.0000000000000000e-01 4.9000000000000000e-01", cksum="1a2b3c", completed=True) -> str:
    lines = [f"CHECK PLAQ: {plaq}", f"CHECK NERSC LINKTR: 1.0e-01 CKSUM: {cksum}"]
    for t, iters, gflops in single:
        lines.append(f"CONGRAD5: time = {t:e} (fn_QUDA D) masses = 1 srcs = 1 iters = {iters} mflops = {gflops * 1e3:e}")
    for t, iters, gflops in block:
        lines.append(f"CONGRAD5: time = {t:e} (fn_QUDA D) masses = 1 srcs = 12 iters = {iters} mflops = {gflops * 1e3:e}")
    if completed:
        lines.append("RUNNING COMPLETED")
    return "\n".join(lines) + "\n"


def quda_output(kind: str, ranks: int, row_order=True) -> str:
    lines = ["Rank order is row major (x running fastest)" if row_order else "Rank order is column major (t running fastest)"]
    if kind == "invert-single":
        lines += [f"Done: 1500 iter / {1.0 + n:g} secs = {ranks * (9000 + 100 * n):g} Gflops" for n in range(6)]
    elif kind == "invert-block":
        lines += [f"Done: 1 sub-partitions - 1500 total iter / {4.0 + n:g} secs = {ranks * (13000 + 100 * n):g} Gflops, 0.4 secs per source"
                  for n in range(4)]
    else:
        lines += ["120.0us per kernel call", "GFLOPS = 7000.5", "GBYTES = 6500.25"]
    return "\n".join(lines) + "\n"


class ProbeCase(PerturbationMixin, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)

    def inputs(self, ranks_per_node="4", *extra):
        out = self.base / f"inputs-{ranks_per_node}"
        done = run("inputs", "--ranks-per-node", ranks_per_node, "--out", str(out), *extra)
        return done, out

    def probe_inputs(self, ranks_per_node="4"):
        done, out = self.inputs(ranks_per_node)
        self.assertEqual(done.returncode, 0, done.stderr)
        return out, json.loads((out / "manifest.json").read_text())


class InputTests(ProbeCase):
    def test_describe_prints_the_frozen_definition(self):
        probe = json.loads(run("describe").stdout)
        self.assertEqual(probe["name"], "staggered-cg-throughput")
        self.assertEqual(probe["version"], "1.0.0")
        self.assertEqual(probe["throughput_local_volume"], [40, 40, 40, 40])
        self.assertEqual((probe["mass"], probe["tolerance"]), (0.01, 1e-8))

    def test_an_unfrozen_probe_writes_inputs_only_for_a_calibration(self):
        self.perturb(TOOL, *UNFROZEN)
        done, out = self.inputs()
        self.assertEqual(done.returncode, 2)
        self.assertIn("not frozen", done.stderr)
        self.assertFalse(out.exists())
        done, out = self.inputs("4", "--calibration-mass", MASS, "--calibration-tolerance", TOL)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(json.loads((out / "manifest.json").read_text())["calibration"])

    def test_a_frozen_probe_refuses_a_calibration_mass(self):
        done, _ = self.inputs("4", "--calibration-mass", MASS, "--calibration-tolerance", TOL)
        self.assertEqual(done.returncode, 2)
        self.assertIn("different probe", done.stderr)
        done, out = self.inputs("4")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(json.loads((out / "manifest.json").read_text())["calibration"])

    def test_refuses_to_write_into_a_directory_with_files(self):
        out = self.base / "used"
        out.mkdir()
        (out / "old.txt").write_text("previous run")
        done = run("inputs", "--ranks-per-node", "4", "--out", str(out))
        self.assertEqual(done.returncode, 2)
        self.assertIn("not empty", done.stderr)

    def test_the_ladder_adds_one_off_node_dimension_per_step(self):
        for rpn, geometries in (("4", [[1, 1, 1, 1], [2, 2, 1, 1], [2, 2, 1, 2], [2, 2, 2, 2]]),
                                ("12", [[1, 1, 1, 1], [3, 2, 2, 1], [3, 2, 2, 2], [3, 2, 4, 2]])):
            with self.subTest(ranks_per_node=rpn):
                _, manifest = self.probe_inputs(rpn)
                points = manifest["points"]
                self.assertEqual([p["node_geometry"] for p in points], geometries)
                self.assertEqual([p["dimensions_off_node"] for p in points], [[], [], ["t"], ["z", "t"]])
                self.assertEqual([p["nodes"] for p in points], [1, 1, 2, 4])
                for p in points:
                    product = 1
                    for v in p["node_geometry"]:
                        product *= v
                    self.assertEqual(p["ranks"], product)

    def test_refuses_a_ladder_the_volumes_cannot_divide(self):
        done, _ = self.inputs("5")
        self.assertEqual(done.returncode, 2)
        self.assertIn("does not split", done.stderr)

    def test_milc_inputs_carry_the_frozen_sets_and_a_file_per_meson(self):
        out, manifest = self.probe_inputs()
        point = manifest["points"][3]
        text = (out / point["milc"]["throughput"]["input"]).read_text()
        self.assertIn("node_geometry 2 2 2 2", text)
        self.assertIn("nx 80", text)
        self.assertIn("mass 0.01", text)
        self.assertIn("error_for_propagator 1e-08", text)
        self.assertIn("\nwarm\n", text)
        self.assertEqual(text.count("set_type single"), 1)
        self.assertEqual(text.count("set_type multicolorsource"), 4)
        self.assertIn("number_of_sets 5", text)
        files = [line.split()[1] for line in text.splitlines() if line.startswith("save_corr_fnal")]
        self.assertEqual(len(files), len(set(files)), "two mesons share a correlator file")
        self.assertEqual(files, point["milc"]["throughput"]["correlators"])
        consistency = (out / point["milc"]["consistency"]["input"]).read_text()
        self.assertIn("nx 24", consistency)
        self.assertIn("nt 48", consistency)

    def test_quda_commands_match_milcs_rank_order_and_block_path(self):
        _, manifest = self.probe_inputs()
        for point in manifest["points"]:
            for kind, command in point["quda"].items():
                argv = command["argv"]
                self.assertEqual(argv[argv.index("--rank-order") + 1], "row")
                self.assertEqual(argv[argv.index("--gridsize") + 1:argv.index("--gridsize") + 5],
                                 [str(v) for v in point["node_geometry"]])
                verify = argv[argv.index("--verify") + 1]
                self.assertEqual(verify, "true" if point["point"] == "device" else "false")
            block = point["quda"]["invert-block"]["argv"]
            self.assertEqual(block[block.index("--nsrc-tile") + 1], "12")


class AnalyzeTests(ProbeCase):
    def write_run(self, mutate=None):
        out, manifest = self.probe_inputs()
        outputs = self.base / "outputs"
        outputs.mkdir()
        files: dict[str, str] = {}
        for point in manifest["points"]:
            tp, cs = point["milc"]["throughput"], point["milc"]["consistency"]
            # the first solve of each kind is slow, as a tuning or allocation solve would be
            files[tp["output"]] = milc_output(
                [(5.0, 1500, 2000.0)] + [(1.0, 1500, 9000.0 + 10 * n) for n in range(5)],
                [(20.0, 1500, 3000.0)] + [(4.0, 1500, 14000.0 + 10 * n) for n in range(3)])
            files[cs["output"]] = milc_output([(0.1, 900, 500.0)] * 3, [(0.4, 900, 800.0)])
            for name in cs["correlators"]:
                files[name] = fnal(f"probe.consistency.{point['point']}")
            for kind, command in point["quda"].items():
                files[command["output"]] = quda_output(kind, point["ranks"])
        if mutate:
            mutate(files, manifest)
        for name, text in files.items():
            if text is not None:
                (outputs / name).write_text(text)
        return out / "manifest.json", outputs

    def analyze(self, mutate=None, *extra):
        manifest, outputs = self.write_run(mutate)
        done = run("analyze", "--manifest", str(manifest), "--outputs", str(outputs), *extra)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return done.returncode, json.loads(done.stdout)

    def assert_error(self, report, fragment):
        self.assertTrue(any(fragment in e for e in report["errors"]), report["errors"])

    def test_a_complete_run_reports_first_solve_excluded_statistics(self):
        status, report = self.analyze()
        self.assertEqual((status, report["errors"]), (0, []))
        device = report["points"][0]
        self.assertEqual(device["milc"]["single"]["solves"], 5)
        self.assertEqual(device["milc"]["single"]["min"], 9000.0)
        self.assertEqual(device["milc"]["block"]["solves"], 3)
        self.assertGreaterEqual(device["milc"]["block"]["value"], 14000.0)
        node = report["points"][1]
        # QUDA's figure is summed over ranks; the probe reports it per rank
        self.assertEqual(node["quda"]["invert-single"]["min"], 9100.0)
        self.assertEqual(node["quda"]["dslash-block"]["gbytes_per_second_per_rank"], 6500.25)
        self.assertEqual(set(report["consistency_correlators"]), {"pair0", "pair1"})
        self.assertFalse(report["calibration"])
        self.assertNotIn("draft_rows", report)  # rows only for a named stack

    def test_a_frozen_probe_drafts_rows_for_a_named_stack(self):
        libraries = self.base / "loaded-libraries.txt"
        prefix = self.base / "install"
        (prefix / "lib").mkdir(parents=True)
        (prefix / "lib" / "libquda.so").write_bytes(b"quda")
        libraries.write_text(f"{prefix}/lib/libquda.so {'a' * 64}\n")
        status, report = self.analyze(None, "--stack", "machines/m/stacks/milc-x/stack.yaml",
                                      "--loaded-libraries", str(libraries), "--install-prefix", str(prefix))
        self.assertEqual(status, 0, report["errors"])
        rows = report["draft_rows"]
        self.assertEqual(len(rows), 8)  # four points, 1 and 12 RHS
        self.assertEqual(rows[0]["probe"], {"name": "staggered-cg-throughput", "version": "1.0.0"})
        self.assertEqual(rows[0]["loaded_libraries"], [{"path": "lib/libquda.so", "sha256": "a" * 64}])
        self.assertEqual(rows[0]["placement"]["local_volume"], [40, 40, 40, 40])
        self.assertEqual(rows[-1]["placement"]["dimensions_off_node"], ["z", "t"])

    def test_accepts_a_plaquette_that_differs_only_by_rounding(self):
        def mutate(files, manifest):
            name = manifest["points"][2]["milc"]["consistency"]["output"]
            files[name] = files[name].replace("5.0000000000000000e-01", "5.0000000000000011e-01")
        status, report = self.analyze(mutate)
        self.assertEqual((status, report["errors"]), (0, []))

    def test_rejects_correlators_that_disagree_beyond_the_limit(self):
        def mutate(files, manifest):
            name = manifest["points"][3]["milc"]["consistency"]["correlators"][1]
            files[name] = fnal("probe.consistency.4-nodes", scale=1.001)
        self.assert_error(self.analyze(mutate)[1], "consistency correlators, pair 1")

    def test_rejects_a_field_whose_plaquette_differs_between_points(self):
        def mutate(files, manifest):
            name = manifest["points"][2]["milc"]["consistency"]["output"]
            files[name] = files[name].replace("5.0000000000000000e-01", "5.0000000000100000e-01")
        self.assert_error(self.analyze(mutate)[1], "plaquette differs between points by more than")

    def test_rejects_a_field_whose_checksum_differs_between_points(self):
        def mutate(files, manifest):
            name = manifest["points"][1]["milc"]["consistency"]["output"]
            files[name] = files[name].replace("CKSUM: 1a2b3c", "CKSUM: ffff")
        self.assert_error(self.analyze(mutate)[1], "checksum differs between points")

    def test_rejects_a_missing_correlator_file(self):
        def mutate(files, manifest):
            files[manifest["points"][3]["milc"]["consistency"]["correlators"][1]] = None
        self.assert_error(self.analyze(mutate)[1], "missing corr-consistency-4-nodes-pair1.fnal")

    def test_rejects_a_correlator_that_breaks_structure(self):
        def mutate(files, manifest):
            name = manifest["points"][2]["milc"]["consistency"]["correlators"][0]
            files[name] = files[name].replace("probe.consistency.2-nodes", "probe.consistency.other")
        self.assert_error(self.analyze(mutate)[1], "consistency correlators, pair 0")

    def test_rejects_a_wrong_number_of_solves(self):
        def mutate(files, manifest):
            name = manifest["points"][0]["milc"]["throughput"]["output"]
            files[name] = "\n".join(l for l in files[name].splitlines() if "srcs = 12" not in l or "3.000000e+06" in l)
        self.assert_error(self.analyze(mutate)[1], "1 block CONGRAD5 solves, expected 4")

    def test_rejects_a_run_that_did_not_complete(self):
        def mutate(files, manifest):
            name = manifest["points"][1]["milc"]["throughput"]["output"]
            files[name] = files[name].replace("RUNNING COMPLETED", "")
        self.assert_error(self.analyze(mutate)[1], "'RUNNING COMPLETED' markers")

    def test_rejects_non_convergence(self):
        def mutate(files, manifest):
            name = manifest["points"][0]["milc"]["throughput"]["output"]
            files[name] += "ks_congrad: NOT converged after 10000 iterations\n"
        self.assert_error(self.analyze(mutate)[1], "non-convergence")

    def test_rejects_a_quda_test_in_the_wrong_rank_order(self):
        def mutate(files, manifest):
            point = manifest["points"][2]
            files[point["quda"]["invert-block"]["output"]] = quda_output("invert-block", point["ranks"], row_order=False)
        self.assert_error(self.analyze(mutate)[1], "Rank order is row major")

    def test_rejects_a_missing_quda_output(self):
        def mutate(files, manifest):
            files[manifest["points"][0]["quda"]["dslash-single"]["output"]] = None
        self.assert_error(self.analyze(mutate)[1], "missing out-quda-dslash-single-device.txt")

    def test_control_without_the_first_solve_exclusion_the_slow_solve_counts(self):
        self.perturb(TOOL, "    kept = solves[1:]  # the first solve", "    kept = solves  # the first solve")
        _, report = self.analyze()
        self.assertEqual(report["points"][0]["milc"]["single"]["min"], 2000.0)


if __name__ == "__main__":
    unittest.main()
