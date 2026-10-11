"""The staggered-CG probe must generate a fair ladder and refuse any run it cannot vouch for.

Inputs: the ladder puts a node's ranks in the fastest dimensions and adds one off-node
dimension per step, for any ranks-per-node the volumes divide into; the MILC inputs carry the
frozen sets and one correlator file per meson; the QUDA commands match MILC's rank order; and
nothing is written for an unfrozen probe without a calibration mass, or for a frozen one with
one. Analysis: a complete synthetic run reports the first-solve-excluded statistics and no
errors, a frozen probe drafts rows, a plaquette differing only by rounding passes, MILC's
checksum is ignored, and each way a run can be incomplete or inconsistent is an error. A run of
an earlier version that only lost legs is analyzed as this version, and refused if any remaining
input differs. The controls remove the first-solve exclusion and the input-file comparison and
show each reported result moves.
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
    else:
        lines += [f"Done: 1 sub-partitions - 1500 total iter / {4.0 + n:g} secs = {ranks * (13000 + 100 * n):g} Gflops, 0.4 secs per source"
                  for n in range(4)]
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
        self.assertEqual(probe["version"], "1.1.0")
        self.assertEqual(probe["throughput_local_volume"], [40, 40, 40, 40])
        self.assertNotIn("dslash_iterations", probe["quda"])
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
            self.assertEqual(set(point["quda"]), {"invert-single", "invert-block"})
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
        self.inputs_dir = out
        if mutate:
            mutate(files, manifest)
            (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
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
        self.assertEqual(set(node["quda"]), {"invert-single", "invert-block"})
        self.assertEqual(set(report["consistency_correlators"]), {"pair0", "pair1"})
        self.assertFalse(report["calibration"])
        self.assertNotIn("draft_rows", report)  # rows only for a named stack

    def test_a_frozen_probe_drafts_rows_for_a_named_stack(self):
        libraries = self.base / "loaded-libraries.txt"
        prefix = self.base / "install"
        (prefix / "lib").mkdir(parents=True)
        (prefix / "lib" / "libquda.so").write_bytes(b"quda")
        # the job's ldd listing can name a library twice; a row lists it once
        libraries.write_text(f"{prefix}/lib/libquda.so {'a' * 64}\n" * 2)
        status, report = self.analyze(None, "--stack", "machines/m/stacks/milc-x/stack.yaml",
                                      "--loaded-libraries", str(libraries), "--install-prefix", str(prefix))
        self.assertEqual(status, 0, report["errors"])
        rows = report["draft_rows"]
        self.assertEqual(len(rows), 8)  # four points, 1 and 12 RHS
        self.assertEqual(rows[0]["probe"], {"name": "staggered-cg-throughput", "version": "1.1.0"})
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

    def test_ignores_milcs_checksum(self):
        # Built on QMP, MILC sums the NERSC checksum wrongly on more than one rank.
        def mutate(files, manifest):
            name = manifest["points"][1]["milc"]["consistency"]["output"]
            files[name] = files[name].replace("CKSUM: 1a2b3c", "CKSUM: ffff")
        status, report = self.analyze(mutate)
        self.assertEqual((status, report["errors"]), (0, []))

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
            files[manifest["points"][0]["quda"]["invert-single"]["output"]] = None
        self.assert_error(self.analyze(mutate)[1], "missing out-quda-invert-single-device.txt")

    def as_earlier_run(self, files, manifest, version="1.0.0"):
        """Make the run one of an earlier version: its manifest lists the dslash legs too."""
        manifest["probe"]["version"] = version
        for point in manifest["points"]:
            for kind in ("dslash-single", "dslash-block"):
                point["quda"][kind] = {"argv": ["staggered_dslash_test"], "output": f"out-quda-{kind}-{point['point']}.txt"}

    def test_an_earlier_run_that_only_lost_legs_is_analyzed_as_this_version(self):
        status, report = self.analyze(self.as_earlier_run)
        self.assertEqual((status, report["errors"]), (0, []))
        self.assertEqual(report["probe"]["version"], "1.1.0")
        self.assertEqual(report["run_probe"]["version"], "1.0.0")
        self.assertEqual(report["ignored_legs"], ["dslash-single", "dslash-block"])
        self.assertEqual(set(report["points"][0]["quda"]), {"invert-single", "invert-block"})

    def change_an_earlier_runs_milc_input(self, files, manifest):
        self.as_earlier_run(files, manifest)
        path = self.inputs_dir / manifest["points"][2]["milc"]["throughput"]["input"]
        path.write_text(path.read_text().replace("mass 0.01", "mass 0.02"))

    def test_refuses_an_earlier_run_whose_milc_input_differs(self):
        self.assert_error(self.analyze(self.change_an_earlier_runs_milc_input)[1],
                          "2-nodes MILC throughput: milc-throughput-2-nodes.in is missing or differs")

    def test_refuses_an_earlier_run_whose_quda_command_differs(self):
        def mutate(files, manifest):
            self.as_earlier_run(files, manifest)
            argv = manifest["points"][1]["quda"]["invert-block"]["argv"]
            argv[argv.index("--nsrc-tile") + 1] = "6"
        self.assert_error(self.analyze(mutate)[1], "node QUDA invert-block: command differs")

    def test_refuses_an_earlier_run_with_a_leg_this_version_did_not_remove(self):
        def mutate(files, manifest):
            self.as_earlier_run(files, manifest)
            manifest["points"][0]["quda"]["other-test"] = {"argv": ["x"], "output": "out-x.txt"}
        self.assert_error(self.analyze(mutate)[1], "device: QUDA legs")

    def test_refuses_a_run_of_an_unlisted_version(self):
        self.assert_error(self.analyze(lambda f, m: self.as_earlier_run(f, m, "0.1.0"))[1], "manifest is for probe")

    def test_control_without_the_input_comparison_a_changed_input_passes(self):
        self.perturb(TOOL, "if not path.is_file() or path.read_text() != text:", "if not path.is_file():")
        status, report = self.analyze(self.change_an_earlier_runs_milc_input)
        self.assertEqual((status, report["errors"]), (0, []))

    def test_control_without_the_first_solve_exclusion_the_slow_solve_counts(self):
        self.perturb(TOOL, "    kept = solves[1:]  # the first solve", "    kept = solves  # the first solve")
        _, report = self.analyze()
        self.assertEqual(report["points"][0]["milc"]["single"]["min"], 2000.0)


if __name__ == "__main__":
    unittest.main()
