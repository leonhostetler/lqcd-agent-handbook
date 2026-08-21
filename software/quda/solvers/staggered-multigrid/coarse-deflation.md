---
title: Staggered-MG coarse deflation guidance
summary: Corpus-scoped coarse-spectrum calibration, filter-window feedback, restart diagnostics, and solve-count-based deflation scheduling.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Configuring or diagnosing the coarsest staggered-MG eigensolve, deflation window, requested vector count, or mass-dependent deflation schedule.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eigensolve_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_block_trlm.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/eigensolve_quda.h
observed: "2026-08-20"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# Staggered-MG coarse deflation guidance

Coarsest-level deflation is an eigensolver setup investment followed by a recurring
coarse-solve effect. Configure it from the executed hierarchy, measured spectrum,
eigenvector quality, compatible reuse count, and target workload. Do not copy a bare
`nvec_3` or mass switch from another ensemble.

All numerical bands and fitted constants below belong to the named
`perlmutter-a100-staggered-mg-2024-2026` retrospective. Its
[`calibration manifest`](calibration.md) defines the 49-cell fit population, ensemble
support, literal MILC input-mass convention, relevant precision, and exclusions.
Values outside that declared envelope are probes, not validated predictions.

## Predict, then verify, the requested spectrum

The corpus fit for the largest requested coarse eigenvalue is

```text
eval_max = A * nu3^alpha + (c * m)^2
nu3      = nvec_3 / V3

A        = 0.0585
alpha    = 1.551
```

The joint fit has 11.9% RMS and 20.4% p90 relative error over
`nu3 = 0.022...0.250` vectors per coarsest site and
`m = 0.000569...0.01555` in the calibration manifest's literal MILC input-mass
convention. The coefficient `c` is ensemble-specific: it was `10.74` and `8.00` on the
two fitted ensembles. On a new ensemble, estimate it at two or more heavy-mass probes
from `c_i = sqrt(max(eval_max - A*nu3^alpha, 0))/m_i` while holding the hierarchy fixed.
Agreement among the probes is an applicability check; do not transfer either fitted
value.

The shared exponent and coefficient are an empirical prior, not a source law. A changed
`nvec_2` invalidates `A` because the calibration cannot distinguish `nu3` from the
fraction of the full coarse colour space. Refit rather than extrapolate. In all cases,
compare the prediction with the run's printed `eval_max`; a large, one-sided mismatch
can indicate a partially delivered eigenspace instead of a new spectral law.

## Set `deflate_a_min` by feedback

The Chebyshev filter separates eigenvalues least effectively near its window edge.
`deflate_a_min` must exceed the largest requested eigenvalue, with enough margin that
the upper requested vectors are not left at that weak-discrimination edge.

In seven controlled ladders at one fitted spacing, raising the margin within
`1.6x...14.5x` improved the coarse-vector residual in every ladder and usually increased
the restart count. The direction is established only over that scanned range; the
optimum was not located. Treat margins near or below `2x` as a corpus warning, not a
universal lower bound, and do not describe the combined evidence as an `8x...26x`
optimum.

Use the [`observable extraction contract`](diagnostics.md#observable-extraction-contract)
so `eval_max`, `l3_res_max`, and restart counts refer to one delivered eigensolve event.
Then use this loop:

1. predict `eval_max` inside the fitted envelope or obtain it from a cheap probe;
2. choose an explicit trial margin and hold the other eigensolver controls fixed;
3. record printed `eval_max`, `l3_res_max`, convergence state, and TRLM restarts; and
4. move the window edge based on vector quality and restart behavior, then remeasure.

Solve time alone did not resolve the window-edge direction in the corpus and is not the
quality objective for this scan.

## Tune the joint eigensolver channel

`deflate_poly_deg`, `deflate_a_min`, and `deflate_n_kr` all affect the number of TRLM
restarts. Use that restart count as their joint observable instead of assigning three
independent optimum values.

The corpus reference band is `4...9` restarts. One or two restarts were a consistent
warning for worse `l3_res_max` across all sampled spacings. The upper side is asymmetric:
ten or more restarts were benign in one fitted population and accompanied failed
convergence in another. Above the reference band, inspect `l3_res_max`, the convergence
prefix, and whether `deflate_max_restarts` was reached; do not declare failure from the
count alone.

The retrospective `deflate_poly_deg` solve-side slowdown has no established mechanism.
It is excluded as a tuning rule. Adjusting polynomial degree to move the restart count
is supported; predicting recurring solve performance from that incident is not.

## Derive a deflation schedule for the workload

At every sampled mass and `nu3`, measure a matched deflated and undeflated configuration
with the same hierarchy, stack, tolerances, and reuse contract. Let

```text
Delta I = deflated setup investment - undeflated setup investment
Delta R = deflated recurring cost - undeflated recurring cost.
```

When `Delta R < 0`, the positive crossover is `Nstar = Delta I / -Delta R`. Enable the
coarse eigenspace only when the declared compatible solve count exceeds that measured
crossover and memory remains feasible. When `Delta R >= 0`, that pair provides no
positive performance crossover.

Write the resulting schedule as `nu3(m)` and derive the actual integer `nvec_3` from the
selected `V3`. A bare mass threshold does not transfer, and two runs at one mass do not
justify interpolation across an unmeasured mass range. No corpus timing, crossover, or
switch-point value is a public default; measure all of them on the target workload.
