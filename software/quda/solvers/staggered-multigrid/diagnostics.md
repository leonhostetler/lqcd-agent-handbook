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
come from the `perlmutter-a100-staggered-mg-2024-2026` four-level retrospective. Its
[`calibration manifest`](calibration.md) defines “closely matched” separately for each
advisory. The bands are not QUDA error conditions, universal healthy ranges, or
substitutes for target-stack validation.

## Quick reference

Every band below was fitted on **four-level** hierarchies. A numbered symbol is an executed
level index, so at three levels the coarsest grid is level 2 and these bands do not apply to it
until refitted — see [level naming](../staggered-multigrid.md#level-naming). The `Fitted at`
column exists so a band cannot be added here without answering that question.

| Observable | Corpus reference | Fitted at | Correct interpretation |
|---|---:|---:|---|
| `setup_l1_iters/setup_maxiter_1` | below `0.5` | 4 levels | healthy-side setup screen; within 1% of the cap is pinned |
| `nu3 = nvec_3/V3` | fit envelope `0.022...0.250` | 4 levels | spectrum-calibration domain, not a legality or universal health band |
| TRLM restarts | `4...9` | 4 levels | stable middle reference; the two edges are asymmetric |
| TRLM restarts | `1...2` | 4 levels | consistent under-resolution warning in the sampled corpus |
| restarts far above band, cap NOT reached, **empty** `Eval[...]` prefix | — | 4 levels | stalled filter, not a slow solve; see the eigensolve triage below |
| `l3_res_max` | about `1.5e-4` | 4 levels | middle-band reference at the two fitted spacings; scale and tolerance remain problem-specific |

The decomposition tool's separate `V3 >= 10000` and coarsest-cell aspect `<= 1.5`
screens are likewise provisional four-ensemble advisories. Source legality always has
priority.

## Observable extraction contract

The retrospective field names are derived quantities, not literal QUDA labels. For the
source revision in this page's frontmatter, extract them as follows. If a later build
changes a message format, preserve the raw lines and update this contract before using
the old numerical bands.

- **`setup_l1_iters`:** within one hierarchy-build event, read the ordered lines matching
  `MG level 1 (GPU): CG: <k> iterations, n = <j>, ...`. A reset of `k` to zero starts a
  new level-1 near-null CG stream. Take the terminal printed `k` before the next reset
  or the end of the build, then take the arithmetic mean of those terminal values.
  Do not add one to the printed counter and do not substitute solve-side level-1 GCR
  iterations.
- **`setup_maxiter_1`:** read the literal MILC parameter-file value
  `setup_maxiter 1` used for the same hierarchy build. If it cannot be recovered, report
  `rho_setup` as unavailable rather than borrowing a cap from another level or run.
- **`eval_max` and `l3_res_max`:** for one coarsest eigensolve event, collect its lines
  matching
  `MG level 3 (GPU): Eval[NNNN] = (+real,imag) ... Residual = <r>`.
  `eval_max` is the maximum printed real eigenvalue and `l3_res_max` is the maximum
  printed `Residual` over the same delivered prefix. Count the `Eval[...]` lines and
  compare that count with requested `nvec_3` and the event's convergence summary; a
  short prefix is partial delivery, not a smaller complete spectrum.
- **TRLM restarts:** from the summary for that same event, parse the integer immediately
  before `restart steps`. Current variants include
  `TRLM computed the requested ... vectors in <R> restart steps ...` and
  `BLOCK TRLM ... in <R> restart steps with ...`. An absent summary is missing data,
  not zero restarts. **Block TRLM (`deflate_block_size > 1`) has been observed to emit no
  summary line at all**, in which case the count must be reconstructed from the
  `blockLanczosStep` sequence, which descends once per restart and so forms a sawtooth.
  That reconstruction is a fallback, not an equivalent source; prefer
  `deflate_block_size 1` while diagnosing.

Keep separate records when a log contains multiple hierarchy builds or eigensolve
events; never maximize or average across them silently. Compute global `V3` and `nu3`
from the global lattice and QUDA's executed blocks with the decomposition tool, not from
the per-rank coarse volume or requested blocks.

## An eigensolve delivers nothing: check restarts and the prefix first

When a coarsest eigensolve fails or delivers no vectors, read the **restart count and the
delivered `Eval[...]` prefix together, before** any setup-cap, spectrum, or filter-window
analysis. That one pair separates "stalled" from "slow" immediately, and it is cheap; the
alternative is spending a second submission to learn the same thing. This gate is scoped
to that symptom and does not displace the dependency order for the others.

| restarts | delivered prefix | reading |
|---|---|---|
| inside `4...9` | full | eigensolve healthy; look elsewhere |
| far above band, cap **not** reached | **empty** | **stalled** — the filter is not separating. Re-derive the window from a measured `eval_max` before spending more walltime |
| cap reached | partial or none | request too large, or the eigensolver controls are wrong |
| `1...2` | full | under-resolution warning; see below |

Two things make this gate work, and both are general eigensolver behaviour rather than
staggered-MG specifics — see [`../eigensolver.md`](../eigensolver.md): eigenvalues print
**only on completion**, so a stalled run yields no spectrum to inspect, and a filter window
placed below the largest requested eigenvalue causes **non-convergence** rather than merely
poor vectors. A stall with an empty prefix therefore points at the window before it points
at anything else. The MILC multigrid spelling of that window is `deflate_a_min`; see
[`coarse-deflation.md`](coarse-deflation.md) for what is specific to the coarsest level.

Before concluding that a coarse solver is unhealthy, also confirm which **mode** it is in:
a CA coarse solver with `Nkrylov == maxiter` runs as a fixed-degree preconditioner that
applies no stopping test and reports `iterated = 1.000000e+00 (requested =
0.000000e+00)`. See
[`the MG overview`](../staggered-multigrid.md). That output is a mode signature, not a
failure.

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
