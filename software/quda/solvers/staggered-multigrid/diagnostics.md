---
title: Staggered multigrid diagnostic chains
summary: Ordered setup, coarse-eigensolver, hierarchy, and measurement checks with explicitly scoped corpus advisory bands.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: A staggered-MG setup, eigensolve, convergence result, or performance comparison looks unhealthy or inconsistent.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_block_trlm.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp
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

# Staggered multigrid diagnostic chains

Diagnose in dependency order and preserve the raw counters. The reference values here
come from the `perlmutter-a100-staggered-mg-2024-2026` four-level retrospective corpus.
They are advisory comparisons for closely matched MILC HISQ/QUDA staggered runs, not
QUDA error conditions, universal healthy ranges, or substitutes for target-stack
validation.

## Quick reference

| Observable | Corpus reference | Correct interpretation |
|---|---:|---|
| `setup_l1_iters/setup_maxiter_1` | below `0.5` | healthy-side setup screen; within 1% of the cap is pinned |
| `nu3 = nvec_3/V3` | fit envelope `0.022...0.250` | spectrum-calibration domain, not a legality or universal health band |
| TRLM restarts | `4...9` | stable middle reference; the two edges are asymmetric |
| TRLM restarts | `1...2` | consistent under-resolution warning in the sampled corpus |
| `l3_res_max` | about `1.5e-4` | middle-band reference at the two fitted spacings; scale and tolerance remain problem-specific |

The decomposition tool's separate `V3 >= 10000` and coarsest-cell aspect `<= 1.5`
screens are likewise provisional four-ensemble advisories. Source legality always has
priority.

## Setup pinned at its ceiling

1. Confirm the denominator is the matching level-1 setup cap and that the counter is
   from the current hierarchy build rather than a reuse event.
2. Compute `setup_l1_iters/setup_maxiter_1` and check repeated trials, not only one row.
3. If pinned, loosen the requested work or repair hierarchy quality before interpreting
   downstream solve behavior. A capped setup does not prove that the requested setup
   tolerance was achieved.
4. After the change, confirm the setup residual and iteration ratio move in the expected
   direction, then regenerate any cached near-null vectors.

Do not begin by tuning the coarsest polynomial when the level-1 setup is already capped.

## Too few TRLM restarts

1. Confirm that the eigensolver converged the requested prefix and did not merely stop.
2. Read `l3_res_max`, not only the mean residual or `eval_max`.
3. Compute `deflate_a_min/eval_max`; a requested eigenvalue near the Chebyshev window
   edge is weakly discriminated.
4. Reduce filter aggressiveness through one of `deflate_poly_deg`, `deflate_a_min`, or
   `deflate_n_kr` while holding the other two fixed, then repeat.

One or two restarts were worse in every sampled spacing. This is a warning about vector
quality, not an instruction to maximize restart count.

## Many TRLM restarts

Inspect convergence and `l3_res_max` before acting. Ten or more restarts accompanied
both good and failed eigensolves in different fitted populations. If the vectors are
good and the cap was not hit, the count alone is not a failure. If residuals are poor or
the cap was reached, change the joint eigensolver controls or reduce the requested
eigenspace and repeat.

## Spectrum prediction misses

Check, in order:

1. the run used the recorded effective hierarchy and `V3`;
2. `nu3` and mass are inside the fitted envelope;
3. `nvec_2` matches the calibration or `A` was refitted;
4. the ensemble-specific mass coefficient was measured locally; and
5. the eigensolver delivered a converged prefix with acceptable `l3_res_max`.

A large one-sided miss outside the envelope is not evidence for extrapolating the fit.
Inside the envelope, a printed `eval_max` biased low together with few restarts and poor
worst-vector residual can indicate a partially delivered eigenspace.

## A performance comparison looks surprising

Before attributing it to a tuning knob, match the operator, mass, hierarchy, rank
geometry, build, binding, setup/update lifecycle, active batch width, source count,
residual, and correctness. Separate setup from recurring work and state the compatible
solve count. Do not compare GCR-MG and parity-CG iteration numbers as equal units of
work.

No numerical solver timing or crossover from the retrospective corpus is published in
this leaf. Reconstruct the decision from matched measurements using the solver-selection
cost model.

## Minimum incident record

Keep the parameter file, executable and source revisions, build cache, machine/queue,
global and local lattice, rank geometry, requested and effective blocks, all `nvec`
values, `V3`, `nu3`, setup iteration ratios, `eval_max`, filter margin, restart count,
`l3_res_max`, convergence messages, setup/reuse state, memory counters, and correctness
result. Without that record, a future run cannot distinguish a parameter effect from a
different executed solver.
