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

The numerical guidance below belongs to the named
`perlmutter-a100-staggered-mg-2024-2026` retrospective. Its
[`calibration manifest`](calibration.md) defines the ensembles, literal mass convention,
population used by each advisory, exclusions, and the test for a closely matched target.
It is an advisory starting point, not a QUDA convergence requirement or a portable
default. Use the overview's level/index crosswalk when translating these quantities into
MILC parameter-file keys, and see [level naming](../staggered-multigrid.md#level-naming)
for why the keys differ by level count.

## Describe the executed hierarchy

Record the effective block sizes printed by QUDA, not only the requested values. From
the global lattice and executed blocks, calculate:

```text
coarsest_global_volume  = product of the global coarsest-grid extents
coarsest_vector_density = coarsest_deflation_count / coarsest_global_volume
```

Both are named for the **role** of the grid, not its index, because the coarsest grid is
level 3 in a four-level hierarchy and level 2 in a three-level one. The decomposition tool
reports exactly these names. See
[level naming](../staggered-multigrid.md#level-naming) for the rule and for the
parameter-file keys each maps to.

The coarsest global volume describes the problem seen by the coarsest solver. Per-rank
coarse volume primarily changes communication and is not a substitute for it. Also record
the four physical or lattice extents of one coarsest cell and their aspect ratio; equal
volume does not make a strongly anisotropic cell equivalent to a balanced one.

**Every numerical band on this page and in the calibration manifest was fitted on
four-level hierarchies.** Applying one to a three-level hierarchy by substituting its
coarsest density is an extrapolation across level count, which
[`calibration.md`](calibration.md) already excludes — renaming the quantity to its role
name does not rescope the band.

Use `coarsest_vector_density` to compare requested coarse eigenspaces across different
hierarchies. Equal coarsest deflation counts at different coarsest volumes request
different fractions of the coarse problem. The corpus cannot, however, separate that
density from the fraction of the complete coarse colour space, because the near-null count
on the level above the coarsest — `nvec 2` in a four-level MILC parameter file, `nvec 1` in
a three-level one — was nearly fixed. If it changes, treat the existing calibration as
needing a refit.

The decomposition tool reports these quantities without treating them as legality
conditions:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-decomposition.py" \
  --global LX LY LZ LT --ranks RX RY RZ RT \
  --block1 B1X B1Y B1Z B1T --block2 B2X B2Y B2Z B2T \
  --nvec1 NV1 --nvec2 NV2 --nvec3 NV3 --corpus-advisories
```

The existing opt-in screen warns at `coarsest_global_volume < 10000` or coarsest-cell
aspect above `1.5`, both fitted at four levels
([level naming](../staggered-multigrid.md#level-naming)). Those cutoffs came from three
ensembles and remain provisional. They are useful for ranking legal candidates, not
rejecting a new discretization or machine without a measurement.

**A later four-level population converged below the volume screen, and that matters for
how the screen is used.** At 0.09 fm on a `64^3 x 96` lattice, two four-level classes at
`coarsest_global_volume = 8192` — below the `10000` cutoff — reached the requested `1e-8`,
with worst true residuals `7.8e-09` and `8.5e-09` at outer counts of `32...33` and
`35...36`. A third class at `16384` converged at outer count `24`. So the **ordering** the
screen encodes survives — larger coarsest volume bought iterations, monotonically across
those three points — while the **absolute cutoff did not act as a feasibility boundary**.
Treat `10000` as a ranking prior, never as a rejection threshold; a candidate below it
needs a measured outer-iteration count, not a veto. Evidence: one ensemble, one spacing,
three classes, four levels; the screen has still not been refitted.

## Locate the setup-tolerance knee

For each level-1 setup solve, monitor

```text
setup_l1_capped_fraction = (level-1 near-null CG streams ending at setup_maxiter 1)
                         / (level-1 near-null CG streams)
```

Derive it with the
[`observable extraction contract`](diagnostics.md#observable-extraction-contract). The
denominator of the cap comparison is the literal MILC `setup_maxiter 1` value, not a
solve-side level-1 GCR counter.

**Count capped streams; do not average their iteration counts.** A capped stream
contributes exactly the cap to any mean, so a mean-to-cap ratio saturates near 1 once a
minority of streams cap out and stops distinguishing a mostly converged setup from a
completely pinned one. One measured set of five builds spanning 16/32 to 64/64 capped
streams gave mean-to-cap ratios of 0.963, 0.975, 0.982, 1.000 and 1.000 — visually
identical — where the capped fraction gave 0.500, 0.667, 0.750, 1.000 and 1.000. The
superseded `rho_setup` was that ratio, and its name also omitted which level it described.

The retrospective data support one mechanism: changing `setup_tol_1` materially changes
total setup cost when the solve approaches its iteration ceiling. Well below that knee,
tightening the tolerance primarily buys setup quality and moves only a minority setup
component. At the ceiling, the setup solve is capped rather than demonstrably converged,
and the resulting vectors can degrade every downstream level.

**A nonzero capped fraction is the pinned signal**, and it is structural rather than a
fitted band: that share of streams stopped because the cap stopped them, so their setup
tolerance was not demonstrably reached.

**The knee is not always reachable, and a population exists where it never was.** In a
0.09 fm campaign spanning three- and four-level hierarchies, every build that generated
its own level-1 near-null vectors was capped: `setup_l1_capped_fraction` ran `0.500`,
`0.667`, `0.750`, `1.000` and `1.000` at caps of `20000`, `20000`, `20000`, `8000` and `8`.
Raising the cap from `8000` to `20000` reduced the fraction but did not clear it. Where that
holds, the tolerance scan below cannot be run as written — there is no unpinned side to
locate a knee against — and the first move is to establish whether any setup tolerance
converges at an affordable cap before treating `setup_tol_1` as a tunable at all. The
retrospective screened this axis with a mean-to-cap ratio instead, which cannot be
recomputed as a fraction from the published manifest; see the setup-knee row in
[`calibration.md`](calibration.md). Locate the knee on the target problem by varying the
tolerance while holding the hierarchy, setup cap, stack, and reuse state fixed. Keep the
tightest value that remains comfortably below the rising-cost region and passes the
downstream checks in [`diagnostics.md`](diagnostics.md).

Do not transfer this numeric screen blindly to `setup_tol_2`: it acts on a different
level and its iteration counter and cap must first be identified explicitly.

## Decision sequence

1. Reject source-invalid blocks, aggregate spaces, and uncompiled coarse colours.
2. Rank the remaining candidates by `coarsest_global_volume`, coarsest-cell shape, memory
   headroom, and `coarsest_vector_density`; retain more than one candidate when the
   empirical screens disagree.
3. Run a bounded setup probe and confirm the executed blocks and
   `setup_l1_capped_fraction`.
4. Check coarse-spectrum and eigensolver health before measuring production cost.
5. Measure setup and recurring solve cost for the declared compatible solve count.

Changing levels, blocks, `nvec_1`, or `nvec_2` changes the meaning of later calibrations.
Return to the first step rather than carrying forward an old coarsest deflation count,
spectrum fit, or setup-tolerance conclusion.
