"""Performance rows must reach verified builds, and each page's table must be the YAML's.

A machine's performance.yaml may hold rows for any number of application stacks; the generated
table groups them by stack. A row is admitted only when its application stack and the
dependency stack it pairs with both carry passed record checks, and a probe row only when the
libraries the run loaded carry the hashes the dependency stack recorded. The negatives cover
each of those, the schema's probe/campaign split, the internal consistency checks, and a stale,
missing or unmarked generated table.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import support  # noqa: E402

support.require_importable("yaml", "jsonschema")

import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "build-performance-tables.py"
SPEC = importlib.util.spec_from_file_location("validate_knowledge_perf", ROOT / "tools/validate-knowledge.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)

MILC = "machines/horizon/stacks/milc-cuda13-quda-ks-spectrum-2026q3/stack.yaml"
SECOND_MILC = "machines/horizon/stacks/milc-cuda13-quda-ks-spectrum-fixture/stack.yaml"
QUDA = "machines/horizon/stacks/quda-cuda13-milc-cg-2026q3/stack.yaml"
LIBQUDA = {"path": "lib/libquda.so", "sha256": "a" * 64}
CHECK = {
    "tool": "tools/check-stack-build-record.py", "version": "1.0.0", "date": "2026-10-10",
    "mode": "make", "evidence": ["the build command"], "errors": 0, "undecided": 0,
}
PAGE = """\
---
title: Horizon performance references
summary: Fixture page.
scope: [machine:horizon]
load_when: Fixture.
evidence: reproduced
observations: 2
observed: "2026-10-10"
observed_on:
  machine: horizon
---

# Horizon performance

{begin}
{end}
"""


def row(**overrides):
    base = {
        "id": "probe-one-device",
        "kind": "probe",
        "stack": MILC,
        "probe": {"name": "staggered-cg-throughput", "version": "1.0.0"},
        "loaded_libraries": [LIBQUDA],
        "solver": {"path": "fn_QUDA", "masses": 1, "rhs": 12},
        "precision": {"precise": "double", "sloppy": "half"},
        "reconstruct": {"precise": 13, "sloppy": 9},
        "placement": {
            "nodes": 1, "ranks": 1, "device": "one GB200 GPU", "node_geometry": [1, 1, 1, 1],
            "local_volume": [32, 32, 32, 32], "dimensions_off_node": [],
            "binding": "36 cores beside the GPU",
        },
        "warm_state": "warm tunecache; first solve excluded",
        "iterations": {"statistic": "median per solve", "value": 1500},
        "metric": {
            "name": "congrad5_gflops_per_rank", "unit": "GFLOP/s per rank",
            "statistic": "solve-time-weighted median", "value": 14000, "min": 13900,
            "max": 14100, "solves": 9, "runs": 1,
        },
        "evidence": "reproduced",
        "observations": 9,
        "observed": "2026-10-10",
        "sources": ["operator-submitted probe run reviewed in the working directory"],
    }
    base.update(overrides)
    return base


def campaign_row(**overrides):
    base = row(id="campaign-specnd", kind="campaign", stack=SECOND_MILC)
    del base["probe"], base["loaded_libraries"]
    base["workload"] = "a spectroscopy campaign: 8 corner-wall sources, 4 masses, 3 RHS per solve"
    base["library_evidence"] = "library modification time predates the jobs; hash taken after"
    base["solver"] = {"path": "fn_QUDA", "masses": 1, "rhs": 3}
    base["placement"] = dict(base["placement"], ranks=4, node_geometry=[1, 1, 2, 2],
                             local_volume=[80, 80, 40, 72])
    base.update(overrides)
    return base


class PerformanceReferenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.copy = Path(temp.name) / "handbook"
        shutil.copytree(ROOT, self.copy, ignore=support.handbook_copy_ignore(ROOT, ".git", "__pycache__", "*.pyc"))
        self.edit_stack(MILC, record_checks=[CHECK])
        self.edit_stack(QUDA, record_checks=[dict(CHECK, mode="cmake")], installed_libraries=[LIBQUDA])
        second = self.copy / SECOND_MILC
        second.parent.mkdir()
        shutil.copy(self.copy / MILC, second)

    def edit_stack(self, rel, **build_fields):
        path = self.copy / rel
        stack = yaml.safe_load(path.read_text())
        for key, value in build_fields.items():
            if value is None:
                stack["build"].pop(key, None)
            else:
                stack["build"][key] = value
        path.write_text(yaml.safe_dump(stack, sort_keys=False))

    def write(self, rows, generate=True, page=True):
        machine = self.copy / "machines/horizon"
        (machine / "performance.yaml").write_text(
            yaml.safe_dump({"schema_version": 1, "machine": "horizon", "rows": rows}, sort_keys=False)
        )
        if page:
            spec = importlib.util.spec_from_file_location("perf_gen", GENERATOR)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            (machine / "performance.md").write_text(PAGE.format(begin=module.BEGIN, end=module.END))
        if generate:
            self.generate()

    def generate(self, *extra):
        return subprocess.run(
            [support.interpreter_for("yaml"), str(GENERATOR), "--root", str(self.copy), *extra],
            capture_output=True, text=True,
        )

    def errors(self):
        errors: list[str] = []
        VALIDATOR.validate_schemas(self.copy, errors)
        VALIDATOR.validate_generated_performance_tables(self.copy, errors)
        return errors

    def assert_error(self, fragment):
        errors = self.errors()
        self.assertTrue(any(fragment in error for error in errors), errors)

    # Positive cases

    def test_one_machine_holds_rows_for_several_stacks(self):
        self.write([row(), row(id="probe-one-node", placement=dict(row()["placement"], ranks=4, node_geometry=[1, 1, 2, 2])),
                    campaign_row()])
        self.assertEqual(self.errors(), [])
        page = (self.copy / "machines/horizon/performance.md").read_text()
        self.assertIn("#### `milc-cuda13-quda-ks-spectrum-2026q3`", page)
        self.assertIn("#### `milc-cuda13-quda-ks-spectrum-fixture`", page)
        self.assertLess(page.index("probe-one-node"), page.index("campaign-specnd"))
        self.assertEqual(self.generate("--check").returncode, 0)

    def test_the_manifest_declares_the_schema_version(self):
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        schema = json.loads((ROOT / "schemas/performance.schema.json").read_text())
        self.assertEqual(manifest["schema_versions"]["performance"], schema["properties"]["schema_version"]["const"])

    # Admission: verified builds only

    def test_rejects_a_stack_without_record_checks(self):
        self.edit_stack(MILC, record_checks=None)
        self.write([row()])
        self.assert_error("has no build.record_checks, so its passed options are unverified")

    def test_rejects_a_dependency_stack_without_record_checks(self):
        self.edit_stack(QUDA, record_checks=None)
        self.write([row()])
        self.assert_error("dependency stack machines/horizon/stacks/quda-cuda13-milc-cg-2026q3/stack.yaml has no")

    def test_rejects_a_probe_whose_library_hash_differs(self):
        self.write([row(loaded_libraries=[dict(LIBQUDA, sha256="b" * 64)])])
        self.assert_error("is not evidence for that stack")

    def test_rejects_a_row_naming_a_library_stack(self):
        self.write([row(stack=QUDA)])
        self.assert_error("is not an application stack")

    def test_rejects_a_row_on_another_machine(self):
        self.write([row(stack="machines/vista/stacks/milc-cuda13-quda-ks-spectrum-2026q3/stack.yaml")])
        self.assert_error("is not a stack on 'horizon'")

    def test_rejects_a_fresh_dependency_build_without_library_hashes(self):
        stack = yaml.safe_load((self.copy / MILC).read_text())
        acquisition = stack["build"]["dependency_acquisition"]
        acquisition["equivalent_validated_stack"] = acquisition.pop("validated_stack")
        (self.copy / MILC).write_text(yaml.safe_dump(stack, sort_keys=False))
        self.write([campaign_row(stack=MILC)])
        self.assert_error("built its own dependency and records no build.installed_libraries")

    # Schema shape

    def test_rejects_a_probe_row_without_its_loaded_libraries(self):
        bad = row()
        del bad["loaded_libraries"]
        self.write([bad])
        self.assert_error("'loaded_libraries' is a required property")

    def test_rejects_a_build_option_in_a_row(self):
        self.write([row(build_options={"QUDA_MAX_MULTI_RHS_TILE": "3"})])
        self.assert_error("Additional properties are not allowed ('build_options' was unexpected)")

    def test_rejects_a_campaign_row_without_its_workload(self):
        bad = campaign_row()
        del bad["workload"]
        self.write([bad])
        self.assert_error("'workload' is a required property")

    # Internal consistency

    def test_rejects_a_geometry_that_does_not_make_the_rank_count(self):
        self.write([row(placement=dict(row()["placement"], ranks=8))])
        self.assert_error("makes 1 ranks, not 8")

    def test_rejects_off_node_dimensions_on_one_node(self):
        self.write([row(placement=dict(row()["placement"], dimensions_off_node=["t"]))])
        self.assert_error("a one-node row cannot have dimensions off node")

    def test_rejects_a_value_outside_its_range(self):
        self.write([row(metric=dict(row()["metric"], value=15000))])
        self.assert_error("lies outside its min-max")

    def test_rejects_duplicate_row_ids(self):
        self.write([row(), row()])
        self.assert_error("is used by an earlier row")

    # Generated table

    def test_rejects_a_stale_table(self):
        self.write([row()])
        data = self.copy / "machines/horizon/performance.yaml"
        record = yaml.safe_load(data.read_text())
        record["rows"][0]["metric"]["value"] = 14050
        data.write_text(yaml.safe_dump(record, sort_keys=False))
        self.assertEqual(self.generate("--check").returncode, 1)
        self.assert_error("generated table is stale")

    def test_rejects_rows_without_a_page(self):
        self.write([row()], generate=False, page=False)
        self.assert_error("missing; performance.yaml needs a page")

    def test_rejects_a_page_without_the_markers(self):
        self.write([row()], generate=False)
        page = self.copy / "machines/horizon/performance.md"
        page.write_text(page.read_text().split("<!-- BEGIN")[0])
        self.assert_error("needs exactly one generated-table block")


if __name__ == "__main__":
    unittest.main()
