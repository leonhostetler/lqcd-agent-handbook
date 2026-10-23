---
title: Grid
summary: Role of the Grid library, its milc-qcd fork used by HadronsMILC, and routing to Grid build guidance.
scope: [software:grid]
load_when: Selecting Grid, or deciding between upstream Grid and the milc-qcd fork, for Hadrons or HadronsMILC work.
evidence: source
sources:
  - https://github.com/paboyle/Grid/blob/3232b438f2cf729e515c185e2dbf29d7cc276bb7/Makefile.am
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Makefile.am
  - https://github.com/milc-qcd/Grid/tree/d67dd2079bea125138502a13120858aa58997379/GridMilc
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
---

# Grid

Grid is a data-parallel C++17 library: SIMD-vectorised lattice containers, MPI domain
decomposition, and CUDA, HIP or SYCL acceleration, with Dirac operators, Krylov solvers and
eigensolvers on top. Hadrons is built on it, and HadronsMILC on Hadrons. Grid is used here as
a library; its own test and benchmark programs are for validating a build.

## Two code lines

Every claim in `software/grid/` is labelled **upstream and fork** (the cited code is identical
on upstream `develop`, or the claim was checked there) or **fork-only**. An unlabelled claim
about Grid is a defect: it would read as upstream knowledge.

- **Upstream:** `paboyle/Grid`, default branch `develop`.
- **Fork:** `milc-qcd/Grid` `feature/LMI-develop`, recorded under `forks:` in
  [`project.yaml`](project.yaml). It merges upstream `develop` regularly and adds:
  - `GridMilc/`, a library of staggered spin-taste gammas (`GridMilc/spin/StagGamma.h`) and
    all-to-all meson-field kernels, plus its own tests (fork-only; upstream's top-level
    `Makefile.am` has no `GridMilc` subdirectory);
  - HISQ smearing (`Grid/qcd/utils/HighlyImprovedStaggeredFermionImpl.h`, fork-only);
  - the `--shm-hostname-fallback` runtime flag and the `--enable-old-rng` configure option
    (fork-only).

HadronsMILC's LMI workflow needs the fork. HadronsMILC pins its releases to fork commits in its
`DEPENDENCIES` file; take the Grid commit from there rather than from a branch tip.

## Where to look

- [`build.md`](build.md): configure options that matter, their traps, and what to build.
- [`build-profiles.yaml`](build-profiles.yaml): named option sets and what each provides.
- [`project.yaml`](project.yaml): dependencies and the meaning of each configure option.
- Validated machine combinations live under `machines/<name>/stacks/`, never here.
