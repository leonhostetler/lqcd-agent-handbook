---
title: Staggered multigrid hierarchy and setup guidance
summary: Source constraints and corpus-scoped guidance for coarse-grid shape, eigenspace density, and the level-1 setup-tolerance knee.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Choosing or auditing staggered-MG levels, aggregation, coarse volume, near-null counts, or setup tolerances after source legality is established.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/block_orthogonalize.in.cu
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
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

# Staggered multigrid hierarchy and setup guidance

First pass the source constraints in
[`../staggered-multigrid.md`](../staggered-multigrid.md) and the decomposition tool.
Only then apply the empirical screens on this page. A source-valid hierarchy can still
be a poor hierarchy; an empirical warning can never make a source-invalid hierarchy
legal.

The numerical guidance below is the named `perlmutter-a100-staggered-mg-2024-2026`
retrospective calibration. It covers four-level MILC HISQ/QUDA staggered MG on
Perlmutter A100 GPUs, with `nvec_1 = 64` and almost always `nvec_2 = 96`, at two working
lattice spacings. It is an advisory starting point, not a QUDA convergence requirement
or a portable default.

## Describe the executed hierarchy

Record the effective block sizes printed by QUDA, not only the requested values. From
the global lattice and executed blocks, calculate:

```text
V3   = product of the global coarsest-grid extents
nu3  = nvec_3 / V3
```

`V3` describes the global problem seen by the coarsest solver. Per-rank coarse volume
primarily changes communication and is not a substitute for `V3`. Also record the four
physical or lattice extents of one coarsest cell and their aspect ratio; equal `V3`
does not make a strongly anisotropic cell equivalent to a balanced one.

Use `nu3` to compare requested coarse eigenspaces across different hierarchies. Equal
`nvec_3` values at different `V3` request different fractions of the coarse problem.
The corpus cannot, however, separate `nvec_3/V3` from the fraction of the complete
coarse colour space because `nvec_2` was nearly fixed. If `nvec_2` changes, treat the
existing `nu3` calibration as needing a refit.

The decomposition tool reports these quantities without treating them as legality
conditions:

```bash
python3 tools/quda-staggered-decomposition.py \
  --global LX LY LZ LT --ranks RX RY RZ RT \
  --block1 B1X B1Y B1Z B1T --block2 B2X B2Y B2Z B2T \
  --nvec1 NV1 --nvec2 NV2 --nvec3 NV3 --corpus-advisories
```

The existing opt-in screen warns at global `V3 < 10000` or coarsest-cell aspect above
`1.5`. Those cutoffs came from four ensembles and remain provisional. They are useful
for ranking legal candidates, not rejecting a new discretization or machine without a
measurement.

## Locate the setup-tolerance knee

For each level-1 setup solve, monitor

```text
rho_setup = setup_l1_iters / setup_maxiter_1.
```

The retrospective data support one mechanism: changing `setup_tol_1` materially changes
total setup cost when the solve approaches its iteration ceiling. Well below that knee,
tightening the tolerance primarily buys setup quality and moves only a minority setup
component. At the ceiling, the setup solve is capped rather than demonstrably converged,
and the resulting vectors can degrade every downstream level.

As a corpus advisory, `rho_setup < 0.5` was the healthy-side screen; a run within one
percent of the ceiling is pinned. These are diagnostic bands, not QUDA success criteria.
Locate the knee on the target problem by varying the tolerance while holding the
hierarchy, setup cap, stack, and reuse state fixed. Keep the tightest value that remains
comfortably below the rising-cost region and passes the downstream checks in
[`diagnostics.md`](diagnostics.md).

Do not transfer this numeric screen blindly to `setup_tol_2`: it acts on a different
level and its iteration counter and cap must first be identified explicitly.

## Decision sequence

1. Reject source-invalid blocks, aggregate spaces, and uncompiled coarse colours.
2. Rank the remaining candidates by global `V3`, coarsest-cell shape, memory headroom,
   and `nu3`; retain more than one candidate when the empirical screens disagree.
3. Run a bounded setup probe and confirm the executed blocks and `rho_setup`.
4. Check coarse-spectrum and eigensolver health before measuring production cost.
5. Measure setup and recurring solve cost for the declared compatible solve count.

Changing levels, blocks, `nvec_1`, or `nvec_2` changes the meaning of later calibrations.
Return to the first step rather than carrying forward an old `nvec_3`, spectrum fit, or
setup-tolerance conclusion.
