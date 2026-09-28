#!/usr/bin/env python3
"""Stack supersession is data that nearest-stack resolution reads, not prose it may miss."""
from __future__ import annotations

import importlib.util
import pathlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

# Guard the in-process imports below; an absent dependency becomes a loud module skip.
_DEP_SUPPORT_SPEC = importlib.util.spec_from_file_location(
    "handbook_dep_guard", pathlib.Path(__file__).resolve().parents[1] / "tests/support.py"
)
_DEP_SUPPORT = importlib.util.module_from_spec(_DEP_SUPPORT_SPEC)
assert _DEP_SUPPORT_SPEC.loader is not None
_DEP_SUPPORT_SPEC.loader.exec_module(_DEP_SUPPORT)
_DEP_SUPPORT.require_importable("yaml", "jsonschema")

import yaml


ROOT = Path(__file__).resolve().parents[1]
handbook_copy_ignore = _DEP_SUPPORT.handbook_copy_ignore
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_knowledge_supersession", ROOT / "tools/validate-knowledge.py"
)
VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
assert VALIDATOR_SPEC.loader is not None
VALIDATOR_SPEC.loader.exec_module(VALIDATOR)

VISTA = "machines/vista/stacks"
SUPERSEDED = {
    "quda-cuda12-milc-cg-2026q3": "quda-cuda13-milc-cg-2026q3",
    "milc-cuda12-quda-ks-spectrum-2026q3": "milc-cuda13-quda-ks-spectrum-2026q3",
}


def load(root: Path, stack: str) -> dict:
    return yaml.safe_load((root / VISTA / stack / "stack.yaml").read_text())


class RecordedSupersessionTests(unittest.TestCase):
    def test_superseded_nearest_stack_ties_its_successor_and_names_it(self):
        # The case the field exists for: identical tested commits leave nearest-stack
        # derivation without a tie-breaker, so the successor must be readable as data.
        for old, new in SUPERSEDED.items():
            with self.subTest(stack=old):
                superseded, successor = load(ROOT, old), load(ROOT, new)
                self.assertEqual(
                    superseded["tested_software"], successor["tested_software"]
                )
                self.assertEqual(
                    superseded["superseded_by"],
                    [{"stack": new, "work": "multi-rank GPU work"}],
                )
                self.assertIn("gpu-gh200", successor["validated_on"])
                self.assertNotIn("superseded_by", successor)

    def test_scope_limits_point_to_the_field_rather_than_restating_the_successor(self):
        for old, new in SUPERSEDED.items():
            with self.subTest(stack=old):
                limits = " ".join(load(ROOT, old)["validation"]["scope_limits"])
                self.assertIn("superseded_by", limits)
                self.assertNotIn(new, limits)

    def test_startup_reports_and_prefers_a_matching_successor(self):
        startup = " ".join((ROOT / "playbooks/start-session.md").read_text().split())
        for phrase in (
            "when a candidate stack records `superseded_by`, report the supersession",
            "whenever that candidate is nearest or tied for nearest",
            "prefer a listed successor whose `validated_on` includes the resolved node type",
            "even when the superseded stack matches the environment more closely",
            "With node type undeclared, report the supersession without choosing",
            "nearest stack and any supersession of it",
        ):
            self.assertIn(phrase, startup)

    def test_recorded_stacks_validate(self):
        errors: list[str] = []
        VALIDATOR.validate_schemas(ROOT, errors)
        self.assertEqual(errors, [])


class SupersessionValidatorTests(unittest.TestCase):
    """Each control must fire; a check that cannot fail proves nothing."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "handbook"
        shutil.copytree(
            ROOT,
            self.root,
            ignore=handbook_copy_ignore(ROOT, ".git", "__pycache__", "*.pyc"),
        )

    def rewrite(self, stack: str, entries: list[dict]) -> None:
        path = self.root / VISTA / stack / "stack.yaml"
        text = path.read_text()
        new = yaml.safe_dump({"superseded_by": entries}, sort_keys=False)
        found = re.search(r"^superseded_by:\n(?:  .*\n)+", text, re.MULTILINE)
        rewritten = (
            text[: found.start()] + new + text[found.end() :] if found else text + new
        )
        self.assertEqual(yaml.safe_load(rewritten)["superseded_by"], entries)
        path.write_text(rewritten)

    def errors(self) -> list[str]:
        found: list[str] = []
        VALIDATOR.validate_schemas(self.root, found)
        return found

    def assertFires(self, fragment: str) -> None:
        found = self.errors()
        self.assertTrue(
            any(fragment in message for message in found),
            f"expected {fragment!r} among {found}",
        )

    def test_unmodified_copy_is_clean(self):
        self.assertEqual(self.errors(), [])

    def test_missing_successor(self):
        self.rewrite(
            "quda-cuda12-milc-cg-2026q3",
            [{"stack": "quda-cuda14-milc-cg-2026q4", "work": "multi-rank GPU work"}],
        )
        self.assertFires("which has no stack.yaml")

    def test_self_reference(self):
        self.rewrite(
            "quda-cuda12-milc-cg-2026q3",
            [{"stack": "quda-cuda12-milc-cg-2026q3", "work": "multi-rank GPU work"}],
        )
        self.assertFires("names the stack itself")

    def test_successor_for_other_software(self):
        self.rewrite(
            "quda-cuda12-milc-cg-2026q3",
            [{"stack": "milc-cuda13-quda-ks-spectrum-2026q3", "work": "multi-rank GPU work"}],
        )
        self.assertFires("records software 'milc', not 'quda'")

    def test_successor_on_no_shared_node_type(self):
        path = self.root / VISTA / "quda-cuda13-milc-cg-2026q3/stack.yaml"
        text = path.read_text()
        old, new = "validated_on:\n  - gpu-gh200\n", "validated_on:\n  - cpu-gg\n"
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))
        self.assertFires("shares no validated_on node type")

    def test_cycle(self):
        self.rewrite(
            "quda-cuda13-milc-cg-2026q3",
            [{"stack": "quda-cuda12-milc-cg-2026q3", "work": "single-GPU work"}],
        )
        self.assertFires("forms a cycle")

    def test_duplicate_successor(self):
        entry = {"stack": "quda-cuda13-milc-cg-2026q3", "work": "multi-rank GPU work"}
        self.rewrite("quda-cuda12-milc-cg-2026q3", [entry, entry])
        self.assertFires("twice")

    def test_schema_requires_the_covered_work(self):
        self.rewrite(
            "quda-cuda12-milc-cg-2026q3", [{"stack": "quda-cuda13-milc-cg-2026q3"}]
        )
        self.assertFires("'work' is a required property")


if __name__ == "__main__":
    unittest.main()
