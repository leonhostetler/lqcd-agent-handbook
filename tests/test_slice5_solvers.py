import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    _, raw, _ = text.split("---", 2)
    return yaml.safe_load(raw)


class SolverImportTests(unittest.TestCase):
    def test_task_time_solver_routing_contract_is_complete(self):
        agents = (ROOT / "AGENTS.md").read_text()
        tuning_mode = " ".join((ROOT / "modes/tuning.md").read_text().split())
        playbook = (ROOT / "playbooks/tune-solver.md").read_text()

        self.assertIn("whenever the task narrows or changes", agents)
        self.assertIn("whose `load_when` matches", agents)
        self.assertIn("../playbooks/tune-solver.md", tuning_mode)
        for trigger in (
            "selects a solver",
            "summarizes or interprets",
            "diagnoses an unhealthy result",
            "explains a solver parameter",
            "chooses the next candidate",
        ):
            self.assertIn(trigger, tuning_mode)

        required_leaves = (
            "software/INDEX.md",
            "software/quda/solvers/staggered-solver-selection.md",
            "software/quda/solvers/staggered-multigrid.md",
            "software/quda/solvers/staggered-multigrid/tuning.md",
            "software/quda/solvers/staggered-multigrid/hierarchy-and-setup.md",
            "software/quda/solvers/staggered-multigrid/diagnostics.md",
            "software/quda/solvers/staggered-multigrid/coarse-deflation.md",
            "software/quda/solvers/staggered-multigrid/calibration.md",
            "software/quda/solvers/staggered-memory.md",
        )
        for relative in required_leaves:
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertIn(f"(../{relative})", playbook)

    def test_selection_leaf_is_scoped_and_indexed(self):
        path = ROOT / "software/quda/solvers/staggered-solver-selection.md"
        metadata = frontmatter(path)
        self.assertEqual(metadata["evidence"], "inferred")
        self.assertIn("software:quda", metadata["scope"])
        self.assertIn("software:milc", metadata["scope"])
        self.assertIn(
            "quda/solvers/staggered-solver-selection.md",
            (ROOT / "software/INDEX.md").read_text(),
        )

    def test_profiles_record_compiled_deflation_and_separate_multigrid(self):
        quda_profiles = yaml.safe_load(
            (ROOT / "software/quda/build-profiles.yaml").read_text()
        )["profiles"]
        milc = yaml.safe_load(
            (ROOT / "software/milc/build-profiles.yaml").read_text()
        )["profiles"]["ks-spectrum-hisq-quda"]

        cg = quda_profiles["milc-cg"]
        mg = quda_profiles["mg-staggered"]
        self.assertEqual(cg["capabilities"]["solvers"], ["cg", "deflated-cg"])
        self.assertFalse(cg["options"]["QUDA_MULTIGRID"])
        self.assertIn("multigrid", cg["excludes"])
        self.assertEqual(
            mg["capabilities"]["solvers"],
            ["cg", "deflated-cg", "gcr", "multigrid"],
        )
        self.assertTrue(mg["options"]["QUDA_MULTIGRID"])
        self.assertIn("staggered-deflated-cg", milc["capabilities"]["quda_paths"])
        self.assertEqual(
            milc["composes"]["quda"]["required_capabilities"]["solvers"],
            ["cg", "deflated-cg"],
        )

    def test_current_eigensolver_enabled_stacks_limit_deflated_runtime_claims(self):
        paths = (
            "machines/perlmutter/stacks/quda-cuda12-milc-cg-2026q3/stack.yaml",
            "machines/perlmutter/stacks/quda-cuda13-milc-cg-2026q3/stack.yaml",
            "machines/frontier/stacks/quda-rocm7-milc-cg-2026q3/stack.yaml",
            "machines/deltaai/stacks/quda-cuda12-milc-cg-2026q3/stack.yaml",
            "machines/perlmutter/stacks/milc-cuda12-quda-ks-spectrum-2026q3/stack.yaml",
            "machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-2026q3/stack.yaml",
            "machines/frontier/stacks/milc-rocm7-quda-ks-spectrum-2026q3/stack.yaml",
            "machines/deltaai/stacks/milc-cuda12-quda-ks-spectrum-2026q3/stack.yaml",
            "machines/perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/stack.yaml",
        )
        for relative in paths:
            with self.subTest(stack=relative):
                stack = yaml.safe_load((ROOT / relative).read_text())
                limits = " ".join(stack["validation"]["scope_limits"]).casefold()
                self.assertIn("deflat", limits)
                self.assertTrue(
                    "did not exercise" in limits
                    or "plain cg only" in limits
                    or "gcr-mg only" in limits
                )

    def test_native_and_linked_mg_validation_stay_distinguished(self):
        """The two MG stacks validate different layers and must not be conflated.

        Until 2026-09-02 this guarded a stronger claim -- that NO stack validated a
        linked MILC MG executable -- because none did. One now does, so the assertion
        that would have caught an overclaim has to change or it merely pins a stale
        fact. It is replaced by assertions that the linked stack's own scope limits
        are stated, which is the overclaim actually available today: reading a
        production-gauge, warm-cache, stored-setup run as general MG validation.
        """
        selection = (
            ROOT / "software/quda/solvers/staggered-solver-selection.md"
        ).read_text()
        playbook = (ROOT / "playbooks/tune-solver.md").read_text()
        # The native stack is still described as native and unit-gauge.
        self.assertIn("native stack validate one unit-gauge hierarchy", selection)
        # The linked stack is admitted, but never without its two load-bearing limits.
        self.assertIn(
            "with stored setup state loaded rather than generated", selection
        )
        self.assertIn(
            "hierarchy setup from scratch is not what it validates", selection
        )
        # The playbook keeps the native seed scoped to bounded QUDA feasibility.
        self.assertIn("native GCR-MG reproduction seed", playbook)
        self.assertIn("not linked-application validation", playbook)

    def test_selection_and_playbook_keep_regimes_reuse_scoped(self):
        selection = (
            ROOT / "software/quda/solvers/staggered-solver-selection.md"
        ).read_text()
        playbook = (ROOT / "playbooks/tune-solver.md").read_text()
        for text in (selection, playbook):
            self.assertIn("C_s(N) = I_s + N R_s", text)
            self.assertIn("compatible", text)
            self.assertIn("reuse", text)
            self.assertIn("crossover", text)
            self.assertIn("Stop", text)
        self.assertIn("setup-dominated", selection)
        self.assertIn("throughput-dominated", selection)
        self.assertNotIn("20–50", selection)
        self.assertNotIn("500+", selection)


if __name__ == "__main__":
    unittest.main()
