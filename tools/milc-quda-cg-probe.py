#!/usr/bin/env python3
"""The portable staggered-CG throughput probe: its frozen parameters, inputs and analysis.

The probe measures solver throughput on a stack the same way on every machine, so rows from
different machines compare (software/milc/probes/staggered-cg-throughput.md owns its purpose
and interpretation). This tool is the one home of its parameters: `describe` prints them, and
neither the leaf nor a batch script restates them.

Subcommands:

  describe  Print the probe's name, version and every frozen parameter as JSON.

  inputs    --ranks-per-node R --out DIR [--calibration-mass M --calibration-tolerance T]
            Write, for each point of the geometry ladder, the MILC throughput input, the MILC
            consistency input and the QUDA test command lines, with a manifest naming every
            output the run must produce. Until the probe's mass and tolerance are frozen,
            inputs are written only for a calibration run, which must supply both and is
            marked as calibration in the manifest.

  analyze   --manifest FILE --outputs DIR [--stack PATH --install-prefix DIR]
            Check every output against the manifest — completion, convergence, solve counts,
            the QUDA tests' rank order, and the consistency leg's plaquette and correlators —
            and report each point's throughput. Draft performance.yaml rows are printed only
            for a frozen probe, a stack, and loaded-library hashes from the run. A run of an
            earlier version this one only removed legs from is analyzed as this version, once
            every remaining leg's inputs are shown identical to what this version writes.

The geometry ladder puts one device, every device of one node, two nodes and four nodes in
four points. A node's ranks fill the fastest-varying dimensions, because QMP numbers ranks
with x fastest when MILC declares no map and a slot-mapped launcher places consecutive ranks
together; each further point adds node splits in the slowest dimensions, so two nodes put t
off node and four put z and t off node. The QUDA tests are run with --rank-order row to match.

It reports what it checked, never that a run passed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION = "1.2.1"
ROOT = Path(__file__).resolve().parents[1]
COMPARE = ROOT / "tools" / "milc-compare-fnal-correlators.py"

# The probe's frozen definition. Changing any value makes a new probe version, and rows of
# different versions are not compared (ARCHITECTURE.md, performance references). Frozen at 1.0.0
# from one calibration on a GB200 (2026-10-10): the mass gives a little under 2700 single-RHS
# iterations on one device; the local volume is the largest calibrated one whose full measured
# footprint, not a model's estimate, fits a 40 GB A100. The tolerance is the campaigns' light-quark
# residual, and the correlator limit sits an order of magnitude above the largest cross-build
# difference those campaigns recorded. A mass or tolerance of None marks an unfrozen probe, for
# which `inputs` writes only calibration inputs. 1.1.0 removed the QUDA dslash legs: the test's
# rate rises with its call count for a reason not found, so no count gives a stable figure.
PROBE: dict[str, Any] = {
    "name": "staggered-cg-throughput",
    "version": "1.1.0",
    "mass": 0.01,
    "tolerance": 1e-8,
    "consistency_max_relative_difference": 1e-5,
    "consistency_plaquette_relative_difference": 1e-14,
    "seed": 5682304,
    "start": "warm",
    "throughput_local_volume": [40, 40, 40, 40],
    "consistency_global_volume": [24, 24, 24, 48],
    "milc": {
        "executable": "ks_spectrum_hisq",
        "source": "corner_wall",
        "source_t0": [0, 2, 4, 6],
        "single_set_propagators": 2,
        "multicolor_sets": 4,
        "consistency_single_set_propagators": 1,
        "consistency_multicolor_sets": 1,
        "inv_type": "CGZ",
        "max_cg_iterations": 10000,
        "max_cg_restarts": 50,
    },
    "quda": {
        "invert": "staggered_invert_test",
        "single_sources": 6,
        "block_sources": 48,
        "block_tile": 12,
        "precision": "double",
        "sloppy_precision": "half",
        "reconstruct": 13,
        "sloppy_reconstruct": 9,
        "rank_order": "row",
    },
    "environment": {"QUDA_MILC_HISQ_RECONSTRUCT": "13", "QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY": "9"},
    "ladder": ["device", "node", "2-nodes", "4-nodes"],
    "excluded_solves": "the first solve of each kind in every run",
    "statistic": "solve-time-weighted median",
}
NODES = {"device": 1, "node": 1, "2-nodes": 2, "4-nodes": 4}

# Earlier probe versions whose runs this version analyzes, each with the legs this version removed.
# Removing a leg leaves every other leg's workload as it was, so such a run measured this version's
# workload plus legs the analysis ignores; `analyze` admits it only after regenerating every remaining
# input and finding it identical. A version that changes a remaining leg is never listed here.
REMOVED_LEGS = {"1.0.0": ["dslash-single", "dslash-block"]}
DIMS = "xyzt"


# --- geometry -------------------------------------------------------------------------------

def prime_factors(n: int) -> list[int]:
    factors, p = [], 2
    while n > 1:
        while n % p == 0:
            factors.append(p)
            n //= p
        p += 1
    return sorted(factors, reverse=True)


def geometry(point: str, ranks_per_node: int) -> list[int]:
    """The node_geometry of one ladder point: a node's ranks fill x, y, z first; nodes split t, then z."""
    grid = [1, 1, 1, 1]
    if point == "device":
        return grid
    for index, factor in enumerate(prime_factors(ranks_per_node)):
        grid[index % 3] *= factor
    if point in ("2-nodes", "4-nodes"):
        grid[3] *= 2
    if point == "4-nodes":
        grid[2] *= 2
    return grid


def coordinates(rank: int, grid: list[int]) -> list[int]:
    coords = []
    for extent in grid:
        coords.append(rank % extent)
        rank //= extent
    return coords


def rank_of(coords: list[int], grid: list[int]) -> int:
    rank = 0
    for extent, value in zip(reversed(grid), reversed(coords)):
        rank = rank * extent + value
    return rank


def off_node_dimensions(grid: list[int], ranks_per_node: int) -> list[str]:
    """Dimensions in which some rank's neighbour sits on another node (x-fastest numbering)."""
    total = math.prod(grid)
    off = set()
    for rank in range(total):
        coords = coordinates(rank, grid)
        for d in range(4):
            if grid[d] == 1:
                continue
            for step in (-1, 1):
                neighbour = list(coords)
                neighbour[d] = (coords[d] + step) % grid[d]
                if rank_of(neighbour, grid) // ranks_per_node != rank // ranks_per_node:
                    off.add(DIMS[d])
    return [d for d in DIMS if d in off]


def check_volume(volume: list[int], grid: list[int], what: str) -> None:
    for d, (extent, split) in enumerate(zip(volume, grid)):
        if extent % split or (extent // split) % 2:
            raise ValueError(f"{what}: {DIMS[d]} extent {extent} does not split into {split} even parts")


def ladder(ranks_per_node: int) -> list[dict[str, Any]]:
    points = []
    for point in PROBE["ladder"]:
        grid = geometry(point, ranks_per_node)
        check_volume(PROBE["consistency_global_volume"], grid, f"consistency volume at {point}")
        check_volume([l * g for l, g in zip(PROBE["throughput_local_volume"], grid)], grid, f"throughput at {point}")
        ranks = math.prod(grid)
        nodes = NODES[point]
        points.append({
            "point": point, "nodes": nodes, "ranks": ranks,
            "ranks_per_node": min(ranks, ranks_per_node), "node_geometry": grid,
            "dimensions_off_node": off_node_dimensions(grid, ranks_per_node) if nodes > 1 else [],
            "throughput_global_volume": [l * g for l, g in zip(PROBE["throughput_local_volume"], grid)],
        })
    return points


# --- MILC inputs ----------------------------------------------------------------------------

def milc_input(global_volume, grid, mass, tolerance, job_id, corr_files, single_propagators, multicolor_sets):
    m = PROBE["milc"]
    lines = ["prompt 0"]
    lines += [f"n{d} {v}" for d, v in zip(DIMS, global_volume)]
    lines += [f"node_geometry {' '.join(map(str, grid))}", f"ionode_geometry {' '.join(map(str, grid))}",
              f"iseed {PROBE['seed']}", f"job_id {job_id}", "",
              "# Gauge field description", "", PROBE["start"], "u0 1.0", "no_gauge_fix", "forget",
              "staple_weight 0", "ape_iter 0", "coordinate_origin 0 0 0 0", "time_bc antiperiodic", "",
              "# Eigenpairs", "", "max_number_of_eigenpairs 0", "",
              "# Chiral condensate and related measurements", "", "number_of_pbp_masses 0", "",
              "# Description of base sources", "", f"number_of_base_sources {len(m['source_t0'])}"]
    for index, t0 in enumerate(m["source_t0"]):
        lines += ["", f"# base source {index}", "", m["source"], "field_type KS", "subset full",
                  f"t0 {t0}", f"source_label c{index}", "forget_source"]
    lines += ["", "# Description of modified sources", "", "number_of_modified_sources 0", "",
              "# Description of propagators", "", f"number_of_sets {1 + multicolor_sets}"]
    solver = [f"inv_type {m['inv_type']}", f"max_cg_iterations {m['max_cg_iterations']}",
              f"max_cg_restarts {m['max_cg_restarts']}", "check yes", "momentum_twist 0 0 0", "precision 2"]
    element = [f"error_for_propagator {tolerance}", "rel_error_for_propagator 0", "fresh_ksprop", "forget_ksprop"]
    lines += ["", "# set 0: single, one RHS per solve", "", "set_type single", *solver, "source 0",
              f"number_of_propagators {single_propagators}"]
    for index in range(single_propagators):
        lines += ["", f"# propagator {index}", f"mass {mass}", "naik_term_epsilon 0", *element]
    first_propagators = [0]
    propagator = single_propagators
    for k in range(multicolor_sets):
        first_propagators.append(propagator)
        lines += ["", f"# set {k + 1}: multicolorsource, {3 * len(m['source_t0'])} RHS per solve", "",
                  "set_type multicolorsource", *solver, f"mass {mass}", "naik_term_epsilon 0",
                  f"number_of_propagators {len(m['source_t0'])}"]
        for source in range(len(m["source_t0"])):
            lines += ["", f"# propagator {propagator}", f"source {source}", *element]
            propagator += 1
    lines += ["", f"number_of_quarks {len(first_propagators)}"]
    for index, prop in enumerate(first_propagators):
        lines += ["", f"# quark {index}", f"propagator {prop}", "identity", "op_label d", "forget_ksprop"]
    lines += ["", "# Description of mesons", "", f"number_of_mesons {len(first_propagators)}"]
    for index in range(len(first_propagators)):
        lines += ["", f"# pair {index}", f"pair {index} {index}", "spectrum_request meson",
                  f"save_corr_fnal {corr_files[index]}", "r_offset 0 0 0 0", "number_of_correlators 1",
                  "correlator PION_5 p000 1 * 1 pion5 0 0 0 E E E"]
    lines += ["", "# Description of baryons", "", "number_of_baryons 0", ""]
    return "\n".join(lines)


def quda_commands(point: dict[str, Any], mass, tolerance) -> dict[str, list[str]]:
    q = PROBE["quda"]
    common = ["--dslash-type", "hisq", "--dim", *map(str, PROBE["throughput_local_volume"]),
              "--gridsize", *map(str, point["node_geometry"]), "--rank-order", q["rank_order"],
              "--prec", q["precision"], "--prec-sloppy", q["sloppy_precision"],
              "--recon", str(q["reconstruct"]), "--recon-sloppy", str(q["sloppy_reconstruct"])]
    verify = "true" if point["point"] == "device" else "false"
    solve = ["--inv-type", "cg", "--mass", str(mass), "--tol", str(tolerance),
             "--niter", str(PROBE["milc"]["max_cg_iterations"]), "--verify", verify]
    return {
        "invert-single": [q["invert"], *common, *solve, "--nsrc", str(q["single_sources"])],
        "invert-block": [q["invert"], *common, *solve, "--nsrc", str(q["block_sources"]),
                         "--nsrc-tile", str(q["block_tile"])],
    }


def point_inputs(point: dict[str, Any], mass, tolerance) -> tuple[dict[str, Any], dict[str, Any]]:
    """One point's MILC legs, each with its input text, and its QUDA commands, as the manifest names them."""
    m = PROBE["milc"]
    name = point["point"]
    milc = {}
    for leg, volume, single, sets in (
        ("throughput", point["throughput_global_volume"], m["single_set_propagators"], m["multicolor_sets"]),
        ("consistency", PROBE["consistency_global_volume"], m["consistency_single_set_propagators"],
         m["consistency_multicolor_sets"]),
    ):
        # One file per meson: the pions share source, operator and mass labels, so in one file
        # their keys would collide and read as a stale append.
        corr = [f"corr-{leg}-{name}-pair{k}.fnal" for k in range(1 + sets)]
        milc[leg] = {"input": f"milc-{leg}-{name}.in", "output": f"out-milc-{leg}-{name}.txt", "correlators": corr,
                     "expected_single_solves": 3 * single, "expected_block_solves": sets, "expected_completed": 1,
                     "text": milc_input(volume, point["node_geometry"], mass, tolerance, f"probe.{leg}.{name}",
                                        corr, single, sets)}
    quda = {k: {"argv": v, "output": f"out-quda-{k}-{name}.txt"} for k, v in quda_commands(point, mass, tolerance).items()}
    return milc, quda


def run_inputs(args: argparse.Namespace) -> int:
    calibration = args.calibration_mass is not None or args.calibration_tolerance is not None
    if PROBE["mass"] is None:
        if args.calibration_mass is None or args.calibration_tolerance is None:
            print("the probe's mass and tolerance are not frozen; inputs exist only for a calibration "
                  "run, which needs --calibration-mass and --calibration-tolerance", file=sys.stderr)
            return 2
        mass, tolerance = args.calibration_mass, args.calibration_tolerance
    else:
        if calibration:
            print("the probe is frozen; a calibration mass or tolerance would make it a different probe",
                  file=sys.stderr)
            return 2
        mass, tolerance = PROBE["mass"], PROBE["tolerance"]
    if args.ranks_per_node < 1:
        print("--ranks-per-node must be at least 1", file=sys.stderr)
        return 2
    try:
        points = ladder(args.ranks_per_node)
    except ValueError as exc:
        print(f"no probe ladder for {args.ranks_per_node} ranks per node: {exc}", file=sys.stderr)
        return 2
    out = args.out
    if out.exists() and any(out.iterdir()):
        print(f"{out} is not empty; the probe writes only into a new directory", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"tool": "tools/milc-quda-cg-probe.py", "tool_version": VERSION,
                "probe": {"name": PROBE["name"], "version": PROBE["version"]},
                "calibration": PROBE["mass"] is None, "mass": mass, "tolerance": tolerance,
                "ranks_per_node": args.ranks_per_node, "environment": PROBE["environment"], "points": []}
    for point in points:
        milc, quda = point_inputs(point, mass, tolerance)
        for spec in milc.values():
            (out / spec["input"]).write_text(spec.pop("text"))
        point.update({"milc": milc, "quda": quda})
        manifest["points"].append(point)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {len(manifest['points'])} points into {out.name}: MILC inputs, QUDA command lines, "
          "manifest.json" + (" (calibration)" if manifest["calibration"] else ""))
    return 0


# --- analysis -------------------------------------------------------------------------------

CONGRAD = re.compile(r"CONGRAD5: time = (\S+) \((\S+) (\S)\) masses = (\d+)(?: srcs = (\d+))? iters = (\d+) mflops = (\S+)")
QUDA_SINGLE = re.compile(r"Done: (\d+) iter / (\S+) secs = (\S+) Gflops")
QUDA_BLOCK = re.compile(r"Done: (\d+) sub-partitions - (\d+) total iter / (\S+) secs = (\S+) Gflops")
PLAQ = re.compile(r"CHECK PLAQ: (\S+) (\S+)")
ROW_ORDER = "Rank order is row major (x running fastest)"


def weighted_median(values: list[tuple[float, float]]) -> float:
    """Median of (value, weight) pairs, weighted."""
    ordered = sorted(values)
    total = sum(w for _, w in ordered)
    running = 0.0
    for value, weight in ordered:
        running += weight
        if running >= total / 2:
            return value
    return ordered[-1][0]


def summarize(solves: list[tuple[float, float, int]]) -> dict[str, Any]:
    """Statistics over (rate, solve time, iterations), in run order, after the excluded solves."""
    kept = solves[1:]  # the first solve of each kind may carry allocation and tuning
    if not kept:
        return {}
    values = [rate for rate, _, _ in kept]
    iterations = sorted(iters for _, _, iters in kept)
    return {"value": round(weighted_median([(rate, time) for rate, time, _ in kept]), 1),
            "min": round(min(values), 1), "max": round(max(values), 1), "solves": len(kept),
            "iterations": iterations[len(iterations) // 2]}


def analyze_milc(path: Path, spec: dict[str, Any], report: dict[str, Any], where: str) -> dict[str, Any]:
    text = path.read_text(errors="replace")
    result: dict[str, Any] = {}
    completed = text.count("RUNNING COMPLETED")
    if completed != spec["expected_completed"]:
        report["errors"].append(f"{where}: {completed} 'RUNNING COMPLETED' markers, expected {spec['expected_completed']}")
    if re.search(r"NOT converged|not converge", text, re.I):
        report["errors"].append(f"{where}: a solve reports non-convergence")
    single, block = [], []
    for t, solver, prec, masses, srcs, iters, mflops in CONGRAD.findall(text):
        record = (float(mflops) / 1e3, float(t), int(iters), solver, prec)
        (block if int(srcs or 1) > 1 else single).append(record)
    for kind, found, expected in (("single", single, spec["expected_single_solves"]),
                                  ("block", block, spec["expected_block_solves"])):
        if len(found) != expected:
            report["errors"].append(f"{where}: {len(found)} {kind} CONGRAD5 solves, expected {expected}")
        if found:
            result[kind] = summarize([(r[0], r[1], r[2]) for r in found])
            result[kind]["solver"] = found[0][3]
            result[kind]["precision"] = found[0][4]
    plaq = PLAQ.search(text)
    result["plaquette"] = [float(plaq.group(1)), float(plaq.group(2))] if plaq else None
    return result


def analyze_quda(path: Path, kind: str, ranks: int, report: dict[str, Any], where: str) -> dict[str, Any]:
    text = path.read_text(errors="replace")
    if ROW_ORDER not in text:
        report["errors"].append(f"{where}: the log does not show '{ROW_ORDER}'")
    if kind == "invert-single":
        found = [(float(g) / ranks, float(t), int(i)) for i, t, g in QUDA_SINGLE.findall(text)]
        expected = PROBE["quda"]["single_sources"]
    else:
        found = [(float(g) / ranks, float(t), int(i)) for _p, i, t, g in QUDA_BLOCK.findall(text)]
        expected = PROBE["quda"]["block_sources"] // PROBE["quda"]["block_tile"]
    if len(found) != expected:
        report["errors"].append(f"{where}: {len(found)} solves reported, expected {expected}")
    return summarize(found) if found else {}


def compare_correlators(pair: int, paths: list[Path], report: dict[str, Any]) -> None:
    """Every point's correlator for one pair against the first point's, with the shared comparison tool."""
    volume = PROBE["consistency_global_volume"]
    points = [p.stem[len("corr-consistency-"):].rsplit("-pair", 1)[0] for p in paths]
    # Files first: --job-id takes one value per file and would swallow anything after it.
    command = [sys.executable, str(COMPARE), *[str(p) for p in paths], "--nt", str(volume[3]),
               "--lattice", ",".join(map(str, volume))]
    limit = PROBE["consistency_max_relative_difference"]
    if limit is not None:
        command += ["--max-relative-difference", str(limit)]
    command += ["--job-id", *[f"probe.consistency.{point}" for point in points]]
    done = subprocess.run(command, capture_output=True, text=True)
    last = (done.stdout.strip() or done.stderr.strip() or "no output").splitlines()[-1]
    report["consistency_correlators"][f"pair{pair}"] = last
    if done.returncode != 0:
        report["errors"].append(f"consistency correlators, pair {pair}: {last}")


def library_rows(path: Path | None, prefix: Path | None, report: dict[str, Any]) -> list[dict[str, str]]:
    """Lines '<absolute path> <sha256>' recorded by the job, made relative to the install prefix.

    A library listed more than once (ldd can name one twice) is kept once, in first-seen order.
    """
    if path is None:
        return []
    rows = []
    for line in path.read_text().split("\n"):
        if not line.strip():
            continue
        library, digest = line.split()[:2]
        try:
            relative = Path(library).resolve().relative_to(prefix.resolve()) if prefix else Path(Path(library).name)
        except ValueError:
            report["errors"].append(f"loaded library {Path(library).name} is outside the install prefix")
            continue
        entry = {"path": str(relative), "sha256": digest}
        if entry not in rows:
            rows.append(entry)
    return rows


def check_earlier_run(manifest: dict[str, Any], inputs: Path, report: dict[str, Any]) -> list[str]:
    """For a run of a listed earlier version: every remaining input identical to this version's.

    Returns the legs to ignore. Each MILC input is compared as the file the run read, beside the
    manifest; each QUDA command as the manifest recorded it.
    """
    removed = REMOVED_LEGS[manifest["probe"]["version"]]
    problems = []
    for key, value in (("mass", PROBE["mass"]), ("tolerance", PROBE["tolerance"]),
                       ("environment", PROBE["environment"]), ("calibration", False)):
        if manifest.get(key) != value:
            problems.append(f"{key} {manifest.get(key)!r}, this version {value!r}")
    try:
        points = ladder(manifest["ranks_per_node"])
    except (KeyError, TypeError, ValueError) as exc:
        points = []
        problems.append(f"no ladder for the run's ranks per node: {exc}")
    if [p["point"] for p in points] != [p["point"] for p in manifest["points"]]:
        problems.append("its ladder points differ from this version's")
        points = []
    for point, recorded in zip(points, manifest["points"]):
        name = point["point"]
        for key in ("nodes", "ranks", "node_geometry", "dimensions_off_node", "throughput_global_volume"):
            if recorded.get(key) != point[key]:
                problems.append(f"{name}: {key} {recorded.get(key)!r}, this version {point[key]!r}")
        milc, quda = point_inputs(point, PROBE["mass"], PROBE["tolerance"])
        for leg, spec in milc.items():
            text = spec.pop("text")
            written = recorded["milc"].get(leg)
            if written != spec:
                problems.append(f"{name} MILC {leg}: manifest entry differs from this version's")
                continue
            path = inputs / spec["input"]
            if not path.is_file() or path.read_text() != text:
                problems.append(f"{name} MILC {leg}: {spec['input']} is missing or differs from this version's")
        if set(recorded["quda"]) != set(quda) | set(removed):
            problems.append(f"{name}: QUDA legs {sorted(recorded['quda'])}, expected {sorted(set(quda) | set(removed))}")
        for kind, spec in quda.items():
            if recorded["quda"].get(kind) != spec:
                problems.append(f"{name} QUDA {kind}: command differs from this version's")
    for problem in problems:
        report["errors"].append(f"run of probe {manifest['probe']['version']}: {problem}")
    return removed


def run_analyze(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text())
    report: dict[str, Any] = {"tool": "tools/milc-quda-cg-probe.py", "version": VERSION,
                              "probe": {"name": PROBE["name"], "version": PROBE["version"]},
                              "calibration": manifest["calibration"], "errors": [], "points": []}
    ignored: list[str] = []
    if manifest["probe"] != report["probe"]:
        if manifest["probe"].get("name") == PROBE["name"] and manifest["probe"].get("version") in REMOVED_LEGS:
            report["run_probe"] = manifest["probe"]
            ignored = check_earlier_run(manifest, args.manifest.parent, report)
            report["ignored_legs"] = ignored
        else:
            report["errors"].append(f"manifest is for probe {manifest['probe']}, this tool is {PROBE['name']} {PROBE['version']}")
    plaquettes, correlators = {}, {}
    for point in manifest["points"]:
        name, ranks = point["point"], point["ranks"]
        summary: dict[str, Any] = {"point": name, "nodes": point["nodes"], "ranks": ranks,
                                   "node_geometry": point["node_geometry"],
                                   "dimensions_off_node": point["dimensions_off_node"]}
        for leg, spec in point["milc"].items():
            path = args.outputs / spec["output"]
            if not path.is_file():
                report["errors"].append(f"{name}: missing {spec['output']}")
                continue
            result = analyze_milc(path, spec, report, f"{name} MILC {leg}")
            if leg == "throughput":
                summary["milc"] = {k: result.get(k) for k in ("single", "block")}
            else:
                plaquettes[name] = result["plaquette"]
                for pair, file in enumerate(spec["correlators"]):
                    corr = args.outputs / file
                    if corr.is_file():
                        correlators.setdefault(pair, []).append(corr)
                    else:
                        report["errors"].append(f"{name}: missing {file}")
        summary["quda"] = {}
        for kind, spec in point["quda"].items():
            if kind in ignored:
                continue
            path = args.outputs / spec["output"]
            if not path.is_file():
                report["errors"].append(f"{name}: missing {spec['output']}")
                continue
            summary["quda"][kind] = analyze_quda(path, kind, ranks, report, f"{name} QUDA {kind}")
        report["points"].append(summary)
    # The plaquette is a floating-point sum whose order is not fixed: two runs of one input on one
    # rank have differed in the last digit, so it is compared to a relative limit. MILC's NERSC
    # checksum is not compared: built on QMP, its global sum is wrong on more than one rank.
    limit = PROBE["consistency_plaquette_relative_difference"]
    values = [v for v in plaquettes.values() if v is not None]
    if None in plaquettes.values() or any(
        abs(a - b) > limit * max(abs(a), abs(b)) for v in values for a, b in zip(v, values[0])
    ):
        report["errors"].append(
            f"consistency leg: the field's plaquette differs between points by more than {limit} relative: {plaquettes}"
        )
    report["consistency_correlators"] = {}
    for pair, files in sorted(correlators.items()):
        if len(files) > 1:
            compare_correlators(pair, files, report)
    rows = []
    if not manifest["calibration"] and args.stack and not report["errors"]:
        libraries = library_rows(args.loaded_libraries, args.install_prefix, report)
        rows = draft_rows(report, args.stack, libraries)
    print(json.dumps(report | ({"draft_rows": rows} if rows else {}), indent=2))
    return 1 if report["errors"] else 0


def draft_rows(report, stack, libraries):
    rows = []
    for point in report["points"]:
        for kind, label in (("single", 1), ("block", PROBE["quda"]["block_tile"])):
            stats = (point.get("milc") or {}).get(kind)
            if not stats:
                continue
            rows.append({
                "id": f"probe-{point['point']}-milc-rhs{label}", "kind": "probe", "stack": str(stack),
                "probe": report["probe"], "loaded_libraries": libraries,
                "solver": {"path": stats["solver"], "masses": 1, "rhs": label},
                "precision": {"precise": "double" if stats["precision"] == "D" else "single",
                              "sloppy": PROBE["quda"]["sloppy_precision"]},
                "reconstruct": {"precise": PROBE["quda"]["reconstruct"], "sloppy": PROBE["quda"]["sloppy_reconstruct"]},
                "placement": {"nodes": point["nodes"], "ranks": point["ranks"], "device": "<one device: fill in>",
                              "node_geometry": point["node_geometry"],
                              "local_volume": PROBE["throughput_local_volume"],
                              "dimensions_off_node": point["dimensions_off_node"], "binding": "<fill in>"},
                "warm_state": "warm tunecache from a preceding tuning run; first solve excluded",
                "iterations": {"statistic": "median per solve", "value": stats["iterations"]},
                "metric": {"name": "congrad5_gflops_per_rank", "unit": "GFLOP/s per rank",
                           "statistic": PROBE["statistic"], "value": stats["value"], "min": stats["min"],
                           "max": stats["max"], "solves": stats["solves"], "runs": 1},
                "evidence": "reproduced", "observations": stats["solves"],
                "observed": "<date of the run>", "sources": ["<descriptive source of the run>"],
            })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--version", action="version", version=f"{VERSION} (probe {PROBE['version']})")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe")
    p = sub.add_parser("inputs")
    p.add_argument("--ranks-per-node", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--calibration-mass", type=float)
    p.add_argument("--calibration-tolerance", type=float)
    a = sub.add_parser("analyze")
    a.add_argument("--manifest", type=Path, required=True)
    a.add_argument("--outputs", type=Path, required=True)
    a.add_argument("--stack", type=Path)
    a.add_argument("--loaded-libraries", type=Path, help="lines '<path> <sha256>' recorded by the job")
    a.add_argument("--install-prefix", type=Path)
    args = parser.parse_args(argv)
    if args.command == "describe":
        print(json.dumps(PROBE, indent=2))
        return 0
    return run_inputs(args) if args.command == "inputs" else run_analyze(args)


if __name__ == "__main__":
    sys.exit(main())
