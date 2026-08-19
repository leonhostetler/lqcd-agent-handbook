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
`milc-cg` identifies the option set that exposes the MILC interface and staggered CG
capability. QMP and QIO are dependencies selected by that profile, so they do not belong in
the profile slug.

Use `project.yaml` for intrinsic capabilities and option meanings,
`build-profiles.yaml` for named option sets, and `build.md` for the software-specific build
procedure. A machine stack supplies the toolchain, target architecture, build cost, and
validation evidence.

For lower-level behavior, use `solvers/eigensolver.md` for native eigensolver
invariants and `internals/milc-deflation-space.md` for the parity spaces,
mass-shifted eigenvalue cache, invalidation rules, and exact-current
preconditions exposed through the MILC interface.
