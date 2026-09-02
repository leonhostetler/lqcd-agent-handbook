---
title: Perlmutter A100 staggered-MG retrospective calibration
summary: Corpus-independent population, convention, and applicability manifest for the numerical staggered-MG advisories.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Applying or auditing a numerical hierarchy, setup, spectrum, filter-window, or TRLM-restart advisory from the staggered-MG guidance.
evidence: experiment
sources:
  - Operator-cleared retrospective MILC/QUDA tuning corpus; raw run records are not committed to the handbook.
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

# Perlmutter A100 staggered-MG retrospective calibration

This page is the public manifest for calibration
`perlmutter-a100-staggered-mg-2024-2026`. It contains enough context to decide whether
a numerical advisory is applicable without access to the source corpus. The raw run
records are not committed, so independently replaying a fit still requires the source
corpus or new target measurements.

The `observed_on` revisions above anchor the current source interpretation and log
semantics. They are not a claim that every historical measurement used those commits.
The retrospective population spans multiple QUDA builds. Treat build-sensitive runtime
effects separately and confirm every mechanism and output field after an upgrade.

## Common execution scope

All admitted numerical guidance came from MILC HISQ solves using QUDA staggered
multigrid on Perlmutter A100-40 GPUs. The production hierarchy had four levels indexed
`0...3`, `nvec_1 = 64`, almost always `nvec_2 = 96`, half-precision fine and
pseudo-fine preconditioning, and single-precision coarse-deflation vectors. The source
and solver overview remain authoritative for the exact operator and hierarchy contract.

The ensemble support was:

| Lattice spacing | Global lattice | Literal MILC input masses | Admitted uses |
|---|---:|---|---|
| 0.04 fm | `144^3 x 288` | `0.000569`, `0.001555`, `0.003110`, `0.006220`, `0.009330`, `0.012440`, `0.015550` | hierarchy ordering, spectrum fit, restart diagnostics, setup knee |
| 0.06 fm | `96^3 x 192` | same seven-mass list | hierarchy ordering, spectrum fit, filter-window ladders, restart diagnostics, setup knee |
| 0.09 fm | `64^3 x 96` | `0.0012` in the hierarchy campaign | Varies by advisory — see the population table below |

Here `m` is the literal positive `mass` value in the MILC propagator set associated
with the MG solve. It is dimensionless lattice input, with no conversion to physical
units and no replacement by QUDA's internal sign-flipped full-system mass. This is the
`m` used by the coarse-spectrum fit.

## Population by advisory

The calibration name is shared, but each advisory uses a different screened
subpopulation. **Every band below was fitted on four-level hierarchies**; see
[level naming](../staggered-multigrid.md#level-naming). A band has no value at another level
count until it is refitted there, whatever role-based name it is written in:

| Advisory | Population and exclusions |
|---|---|
| `coarsest_global_volume` and coarsest-cell aspect | The three lattice spacings above. Only the 0.09-fm population broadly scanned decompositions. The ordering is established; `coarsest_global_volume >= 10000` and aspect `<= 1.5` are provisional screens, not fitted failure boundaries. |
| Coarse-spectrum law | 49 distinct converged `(spacing, coarsest_global_volume, coarse colour, coarsest_deflation_count, mass)` cells: 23 at 0.04 fm and 26 at 0.06 fm. The envelope is `coarsest_vector_density = 0.022...0.250` and `m = 0.000569...0.015550`. Of those 49 fitted cells the near-null count on the level above the coarsest — `nvec 2` in these four-level files — was `96` in 45, `64` in three, and `128` in one; all four non-96 cells are at 0.06 fm, so the population weakly constrains that dependence. The 0.09-fm cells are outside the fit and are diagnostic only. |
| `deflate_a_min` direction | Seven controlled one-parameter ladders at 0.06 fm spanning `deflate_a_min/eval_max = 1.6...14.5`, and one five-point ladder at 0.09 fm spanning `1.96...130`. Raising the margin improved the worst-vector channel in every 0.06 ladder; the optimum was not located at either spacing. |
| TRLM restart bands | 318 completed deflated rows at 0.04 and 0.06 fm with production residual request `1e-8`; 324 rows when the six completed 0.09-fm rows are included. The stable `4...9` middle band comes from the two working spacings. The 0.09-fm rows support only the low-restart warning. |
| Level-1 setup-cap ratio | Rows with both the terminal level-1 setup iterations and matching `setup_maxiter 1`. The two working spacings sampled the healthy side of one knee; the 0.09-fm rows were pinned within one percent of the cap. `rho_setup < 0.5` is a healthy-side screen, not a QUDA convergence criterion. |

Memory fits use the same named retrospective family but different screened populations.
Their exact counts, support sets, errors, current-code correction, and exclusions live
in `tools/quda-staggered-memory.py` and are emitted in every fit result; use
[`../staggered-memory.md`](../staggered-memory.md) as their public contract.

## What “closely matched” means

Before using a numerical band, match the operator and action, four-level indexing,
mass convention, `nvec_1`, `nvec_2`, relevant precision, observable definition, and the
advisory's own parameter envelope. Match the hierarchy and source revision wherever they
can change the observable. Hardware portability was not established merely because a
spectrum quantity is mathematically machine-independent.

A target outside that scope may still use the source mechanism and measurement
procedure, but its numerical result is a probe. In particular:

- changing `nvec_2` invalidates the fitted spectrum coefficient;
- using two or three levels invalidates all four-level numerical bands;
- the 0.09-fm population does not extend the working spectrum fit; and
- a new machine, allocator, build, precision, or operator requires target validation.

No retrospective solver timing, crossover, mass switch point, run path, job identifier,
or allocation identifier is part of this public calibration.
