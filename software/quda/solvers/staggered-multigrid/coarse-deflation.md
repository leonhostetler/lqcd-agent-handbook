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
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_cg_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_ca_gcr.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface_internal.cpp
  - operator's screened tuning records
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
coarsest deflation count — `nvec 3` in a four-level MILC parameter file, `nvec 2` in a
three-level one — or a mass switch from another ensemble.

All numerical bands and fitted constants below belong to the named
`perlmutter-a100-staggered-mg-2024-2026` retrospective. Its
[`calibration manifest`](calibration.md) defines the 49-cell fit population, ensemble
support, literal MILC input-mass convention, relevant precision, and exclusions.
Values outside that declared envelope are probes, not validated predictions.

**This page is the staggered-multigrid layer only.** Behaviour shared by every QUDA
eigensolver caller — the supported solver families and search-space invariants, Chebyshev
window semantics, the completion-only printing rule, the deflation-application log forms,
the recipes for establishing a filter window, and the block-variant diagnostics — lives in
[`../eigensolver.md`](../eigensolver.md). Read it first; this page adds only what is
specific to the coarsest level of a staggered MG hierarchy.

**Parameter spelling on this page is the MILC multigrid parameter file's.** Its
`deflate_`-prefixed keys are parsed by the MILC interface and copied into that level's
`QudaEigParam`; the prefix is not a QUDA field name and does not transfer to other
deflation entry points, including MILC's own non-multigrid path. The
[`entry-point mapping table`](../eigensolver.md) gives the four spellings.

## Which coarse solvers support deflation, and how one disables it silently

Deflation is not available for an arbitrary coarse solver, and one configuration turns it
off without failing. Establish both before tuning a window or a vector count.

**Supported set.** `multigrid.cpp` accepts coarse-level deflation for `CGNR`, `CA_CGNR`,
`CGNE`, `CA_CGNE`, `GCR`, `CA_GCR`, and `BICGSTABL`, and errors out for anything else.
A coarse solver outside that set is a configuration error, not a quiet no-op.

**Two supported solvers deflate against the same operator family.** `CGNR` delegates to
the inner CG, which constructs its deflation space against the eigen-operator; `CA_GCR`
under `QUDA_EIG_TR_LANCZOS` or `QUDA_EIG_BLK_TR_LANCZOS` constructs it against `MdagM`.
The practical consequence is that **a persisted coarse eigenspace survives a
`cgnr` <-> `ca-gcr` change**, which is what makes that comparison affordable: the
eigenspace is loaded rather than rebuilt.

**The hazard.** For any other `eig_type`, `CA_GCR` constructs the deflation space against
the plain operator and then sets `deflate = false`. It inspects the space and **silently
turns deflation off.** The run completes normally, the eigenspace is simply unused, and
the symptom presents as a hierarchy-quality collapse rather than as a configuration error.

**Actionable check.** Whenever a CA-type coarse solver is configured with deflation, assert
that the applied vector count equals the requested count on **every** coarsest-level
invocation, and that the line appears at all — its absence is the signature of the
silent-disable branch above. The literal `Deflating <N> ...` forms, the reason the two
wordings are not the same quantity, and the per-invocation rule are on the
[`general eigensolver page`](../eigensolver.md). At the coarsest level of a four-level
hierarchy the line is prefixed `MG level 3 (GPU):`. Do not infer from a clean exit that the
eigenspace was applied.

**Evidence label.** The supported set, the operator families, and the disabling branch are
read from source at the observed revision. The supported branch has been confirmed at
runtime by the count check above; **the silent-disable branch has not been observed here**,
because the configurations in use were on the safe branch. Treat it as a source-derived
hazard with a cheap runtime guard, not as a measured failure.

## Predict, then verify, the requested spectrum

The corpus fit for the largest requested coarse eigenvalue is

```text
eval_max                 = A * coarsest_vector_density^alpha + (c * m)^2
coarsest_vector_density  = coarsest_deflation_count / coarsest_global_volume

A        = 0.0585
alpha    = 1.551
```

The joint fit has 11.9% RMS and 20.4% p90 relative error over
`coarsest_vector_density = 0.022...0.250` vectors per coarsest site and
`m = 0.000569...0.01555`, all four-level, in the calibration manifest's literal MILC
input-mass convention. The coefficient `c` is ensemble-specific: it was `10.74` and `8.00` on the
two fitted ensembles, specifically `c(0.04 fm) = 10.74` and `c(0.06 fm) = 8.00`. On a
new ensemble, estimate it at two or more heavy-mass probes
from `c_i = sqrt(max(eval_max - A*coarsest_vector_density^alpha, 0))/m_i` while holding
the hierarchy fixed.
Agreement among the probes is an applicability check; do not transfer either fitted
value.

The shared exponent and coefficient are an empirical prior, not a source law. Changing the
near-null count on the level above the coarsest — `nvec 2` in a four-level MILC parameter
file, `nvec 1` in a three-level one — invalidates `A`, because the calibration cannot
distinguish `coarsest_vector_density` from the fraction of the full coarse colour space.
Refit rather than extrapolate. In all cases, compare the prediction with the run's printed
`eval_max`; a large, one-sided mismatch can indicate a partially delivered eigenspace
instead of a new spectral law.

## Set `deflate_a_min` by feedback

The Chebyshev filter separates eigenvalues least effectively near its window edge.
`deflate_a_min` must exceed the largest requested eigenvalue, with enough margin that
the upper requested vectors are not left at that weak-discrimination edge.

**A window below the largest requested eigenvalue causes non-convergence, not merely poor
vectors**, and a non-converging eigensolve prints no spectrum at all. Both are general
eigensolver behaviour and are stated with their consequences in
[`../eigensolver.md`](../eigensolver.md); the point to carry here is that
`deflate_a_min` is the MILC multigrid spelling of that window, and that it should be the
**first** hypothesis when a coarsest eigensolve fails to converge — before setup-cap,
spectrum, or vector-count analysis.

In seven controlled four-level ladders at one fitted spacing, raising the margin within
`1.6x...14.5x` improved the coarse-vector residual in every ladder and usually increased
the restart count. The direction is established only over that scanned range; the
optimum was not located. Treat margins near or below `2x` as a corpus warning, not a
universal lower bound, and do not describe the combined evidence as an `8x...26x`
optimum.

Use the [`observable extraction contract`](diagnostics.md#observable-extraction-contract)
so `eval_max`, `coarsest_res_max`, and restart counts refer to one delivered eigensolve
event.
Then use this loop:

1. predict `eval_max` inside the fitted envelope or obtain it from a cheap probe;
2. choose an explicit trial margin and hold the other eigensolver controls fixed;
3. record printed `eval_max`, `coarsest_res_max`, convergence state, and TRLM restarts;
   and
4. move the window edge based on vector quality and restart behavior, then remeasure.

Solve time alone did not resolve the window-edge direction in the corpus and is not the
quality objective for this scan.

### Establishing `deflate_a_min` when the coarse spectrum is unknown

Use the two methods and the choosing table in
[`../eigensolver.md`](../eigensolver.md) — a small accelerated probe fitted over its whole
delivered prefix, or a conservative window at the full count whose vectors are keepers —
together with their failure modes. Both keep acceleration on and are easier to read at
`deflate_block_size 1`.

What is specific to this level: the spectrum law above is the curve to fit in Method A, so
the reach of an extrapolation is set by its exponent, and `coarsest_vector_density` rather
than a bare coarsest deflation count is what transfers between hierarchies. A fully
delivered sibling spectrum at a different coarse colour is usually the better ratio source
than a short prefix at the same one.

## Tune the joint eigensolver channel

`deflate_poly_deg`, `deflate_a_min`, and `deflate_n_kr` all affect the number of TRLM
restarts. Use that restart count as their joint observable instead of assigning three
independent optimum values.

The corpus reference band is `4...9` restarts, fitted at four levels. One or two restarts
were a warning for worse `coarsest_res_max` across the spacings sampled by that fit.

**That direction did not reproduce in a later population, and the warning should be read
as unconfirmed outside its fit.** Across 22 completed coarsest eigensolves at 0.09 fm
spanning three- and four-level hierarchies, the eight rows at one or two restarts gave
`coarsest_res_max` of `6.3e-05...3.4e-04` — at or below the corpus middle-band reference —
while the five rows at five or six restarts gave `2.0e-04...3.3e-03`. **The contrast is
not clean and does not overturn the warning:** the two worst residuals both come from a
single class that was later retired, and with those excluded the two groups overlap. Read
this as a flag for a controlled one-parameter check before relying on the low-restart
warning at a new spacing or level count, not as a refutation. The
upper side is asymmetric: ten or more restarts were benign in one fitted population and
accompanied failed convergence in another. Above the reference band, inspect
`coarsest_res_max`, the convergence prefix, and whether `deflate_max_restarts` was reached;
do not declare failure from the count alone.

`deflate_block_size` belongs in this channel too, and the page previously omitted it. It is
the MILC multigrid spelling of the eigensolver's `block_size`: **source-exact**, the MILC
interface selects block TR Lanczos when `deflate_block_size > 1` and plain TR Lanczos
otherwise, so one key silently chooses between two code paths. `1` or unset is plain TRLM.
The general consequences — that the block variant may print no restart summary, and that
the sawtooth reconstruction is a fallback rather than an equivalent source — are in
[`../eigensolver.md`](../eigensolver.md).

**What is specific to this level is the cost, and it is not source-derived.** Block TRLM
appears to require substantially more **autotuning** for a small performance gain, so on a
cold tunecache it can consume the walltime the coarsest eigensolve itself needs.
**Default to `1`**, and reserve a larger block for later-stage performance tuning or
benchmarking, once the cache is warm for that terminal shape **and** coarse colour — the two
are separate cache identities, as
[`../../internals/autotuning.md`](../../internals/autotuning.md) records. **Evidence label:
operator experience plus one uncontrolled observation** — a cold-cache run at a large block
size accumulated a full coarse-operator retune and was cut off mid-eigensolve. The
controlled pair has not been run. Mechanism-plus-caveat, never a fitted band.

The retrospective `deflate_poly_deg` solve-side slowdown has no established mechanism.
It is excluded as a tuning rule. Adjusting polynomial degree to move the restart count
is supported; predicting recurring solve performance from that incident is not.

## Derive a deflation schedule for the workload

At every sampled mass and `coarsest_vector_density`, measure a matched deflated and
undeflated configuration
with the same hierarchy, stack, tolerances, and reuse contract. Let

```text
Delta I = deflated setup investment - undeflated setup investment
Delta R = deflated recurring cost - undeflated recurring cost.
```

When `Delta R < 0`, the positive crossover is `Nstar = Delta I / -Delta R`. Enable the
coarse eigenspace only when the declared compatible solve count exceeds that measured
crossover and memory remains feasible. When `Delta R >= 0`, that pair provides no
positive performance crossover.

Write the resulting schedule as `coarsest_vector_density(m)` and derive the actual integer
coarsest deflation count from the selected `coarsest_global_volume`. A bare mass threshold
does not transfer, and two runs at one mass do not justify interpolation across an
unmeasured mass range. No corpus timing, crossover, or switch-point value is a public
default; measure all of them on the target workload.
