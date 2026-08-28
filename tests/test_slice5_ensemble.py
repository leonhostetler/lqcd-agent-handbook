#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_knowledge_slice5", ROOT / "tools/validate-knowledge.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)


class MilcHisqCatalogTests(unittest.TestCase):
    def setUp(self):
        self.path = ROOT / "ensembles/milc-hisq.yaml"
        self.catalog = yaml.safe_load(self.path.read_text())
        self.groups = self.catalog["spacing_groups"]
        self.defaults = self.catalog["operator_resolution"]["spacing_defaults"]

    def test_catalog_matches_bound_schema(self):
        manifest = yaml.safe_load((ROOT / "handbook.yaml").read_text())
        schema = json.loads((ROOT / "schemas/ensemble.schema.json").read_text())
        validator = Draft202012Validator(
            schema, format_checker=FormatChecker()
        )
        self.assertEqual(manifest["schema_versions"]["ensemble"], 1)
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(list(validator.iter_errors(self.catalog)), [])

        errors: list[str] = []
        count = VALIDATOR.validate_schemas(ROOT, errors)
        self.assertEqual(count, 28)
        self.assertEqual(errors, [])

    def test_published_core_has_unique_suffix_free_names(self):
        names = [
            ensemble["name"]
            for group in self.groups
            for ensemble in group["ensembles"]
        ]
        self.assertEqual(len(names), 24)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name[-1].isdigit() for name in names))
        self.assertNotIn("asqtad", self.path.read_text().casefold())

    def test_physical_defaults_are_explicit(self):
        expected = {
            "0.15": "l3248f211b580m00235m0647m831",
            "0.12": "l4864f211b600m00184m0507m628",
            "0.09": "l6496f211b630m0012m0363m432",
            "0.06": "l96192f211b672m0008m022m260",
            "0.04": "l144288f211b700m000569m01555m1827",
            "0.042": "l144288f211b700m000569m01555m1827",
        }
        resolved = {
            alias: default["ensemble"]
            for default in self.defaults
            for alias in default["aliases"]
            if default["ensemble"] is not None
        }
        self.assertEqual(resolved, expected)

        records = {
            ensemble["name"]: ensemble
            for group in self.groups
            for ensemble in group["ensembles"]
        }
        self.assertTrue(
            all(records[name]["physical_light_mass"] for name in set(expected.values()))
        )

    def test_zero_point_zero_three_has_no_physical_default(self):
        default = next(
            default for default in self.defaults if "0.03" in default["aliases"]
        )
        self.assertIsNone(default["ensemble"])
        group = next(group for group in self.groups if group["id"] == default["spacing_group"])
        self.assertEqual(len(group["ensembles"]), 1)
        self.assertEqual(group["ensembles"][0]["paper_key"], "ms/5")

    def test_catalog_validator_rejects_bad_default(self):
        default = self.defaults[0]
        original = default["ensemble"]
        default["ensemble"] = "l9999f211b999m1m1m1"
        errors: list[str] = []
        VALIDATOR.validate_ensemble_catalog(self.path, self.catalog, errors)
        default["ensemble"] = original
        self.assertTrue(any("is absent from that spacing group" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
