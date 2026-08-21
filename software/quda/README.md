---
title: QUDA
summary: Role, interfaces, and routing guidance for the QUDA accelerator library.
scope: [software:quda]
load_when: Selecting QUDA capabilities, interfaces, or build guidance.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/README.md
observed: "2026-08-15"
observed_on:
  software:
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
---

# QUDA

QUDA is primarily an accelerator library used by applications such as MILC rather than a
standalone production application. It provides lattice-QCD Dirac operators, linear
solvers, field operations, application interfaces, and multi-GPU support. Its own small
executables are useful for focused validation and performance work.

Keep the software name and build profile separate. `quda` identifies the project;
`milc-cg` identifies the option set that exposes the MILC interface and plain or deflated
staggered CG capability. QMP and QIO are dependencies selected by that profile, so they
do not belong in the profile slug. `mg-staggered` adds multigrid kernels and records plain and deflated
CG as compiled capabilities in the same library. Its current Perlmutter stack validates a
native GCR-MG harness only; it does not validate linked MILC multigrid.

Use `project.yaml` for intrinsic capabilities and option meanings,
`build-profiles.yaml` for named option sets, and `build.md` for the software-specific build
procedure. A machine stack supplies the toolchain, target architecture, build cost, and
validation evidence.

For MILC-facing staggered solver behavior, use:

- [`solvers/staggered-solver-selection.md`](solvers/staggered-solver-selection.md) for the
  compatibility gates, reuse-scoped cost model, solve-count regimes, measurement
  requirements, and stop rules that choose among the implementations;
- [`solvers/staggered-cg.md`](solvers/staggered-cg.md) for the Hermitian parity
  normal-equation CG contract and workspace;
- [`solvers/staggered-deflated-cg.md`](solvers/staggered-deflated-cg.md) for native CG with
  an attached low-mode eigenspace, projection triggers, and reuse requirements; and
- [`solvers/staggered-multigrid.md`](solvers/staggered-multigrid.md) for the full-system
  outer GCR plus multigrid-preconditioner hierarchy.

The multigrid overview routes to a public calibration manifest plus four action leaves
for hierarchy/setup, coarse deflation, ordered tuning, and diagnostics. The manifest
defines the population, conventions, and applicability test without requiring access to
the source corpus. Its fitted envelopes and diagnostic bands are not source requirements
or machine-independent defaults.

Use [`solvers/staggered-memory.md`](solvers/staggered-memory.md) for source-exact field
sizes, corpus-calibrated high-water estimates with their evidence limits, decomposition
coupling, active-batch plain-CG increments, and capacity accounting across all three
solver paths. Its MRHS-MG result is a narrow marginal field slope, not an absolute
capacity predictor.

Use [`../../playbooks/tune-solver.md`](../../playbooks/tune-solver.md) to execute the
cross-solver selection and tuning procedure for a declared production workload.

Use [`solvers/eigensolver.md`](solvers/eigensolver.md) for native eigensolver invariants
and [`internals/milc-deflation-space.md`](internals/milc-deflation-space.md) for the parity
spaces, mass-shifted eigenvalue cache, invalidation rules, and exact-current preconditions
exposed through the MILC interface.
