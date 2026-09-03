---
title: QUDA staggered solver memory and capacity accounting
summary: Source-exact field sizes, evidence-tiered CG and multigrid high-water estimates, integrated decomposition search, and capacity decision rules.
scope: [software:quda, software:milc, fermion:staggered]
load_when: Sizing or diagnosing device and host memory for plain CG, deflated CG, or staggered multigrid; or finding rank decompositions under a machine-scoped node limit.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_internal.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/color_spinor_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solve.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_cg_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_gcr_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_ca_gcr.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/gauge_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/dirac_coarse.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/lattice_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/cuda/malloc.cpp
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

# QUDA staggered solver memory and capacity accounting

Use this page in two layers. The source layer computes individual current QUDA field
allocations. The empirical layer estimates solver high-water counters from a retrospective
MILC/QUDA staggered-solver corpus on Perlmutter A100 GPUs. The second layer is valuable for
planning, but it is not a source invariant and does not become one by being packaged in a
calculator.

The companion tool is [`../../../tools/quda-staggered-memory.py`](../../../tools/quda-staggered-memory.py).
Its JSON output separates source geometry, calibration scope, extrapolation warnings, and
capacity advice. Prefer its `mg-fit --global ... --ranks ...` interface: it derives the
local lattice and partitioned directions, emulates QUDA's block adjustment, and feeds the
effective blocks directly into the memory model. This removes the error-prone manual
handoff. Use
[`../../../tools/quda-staggered-decomposition.py`](../../../tools/quda-staggered-decomposition.py)
when only the source legality and coarse-grid metrics are needed.

## Keep the counters separate

At `endQuda`, current QUDA reports several allocation high-water marks. They are maxima of
the running allocation totals, not live memory at exit:

- `Device memory used` tracks ordinary device allocation;
- `Pinned device memory used` tracks a disjoint device communication-buffer category;
- `Page-locked host memory used` tracks pinned host allocation; and
- `Total host memory used >= ...` includes another host category but explicitly remains a
  lower bound on all process memory.

Add the first two before comparing QUDA-visible use with device capacity. Do not add a
communication-pool estimate to a measured `Pinned device memory used`; that would count it
twice. Scheduler `MaxRSS` includes the application, MPI, runtime, libraries, and untracked
allocation, so it is not interchangeable with a QUDA host counter.

All formulas below are per rank. `V0` is fine **local** volume. Local shape matters even
at fixed volume because communication storage scales with partitioned surfaces.

## Source-exact object layer

For QUDA `b6998853f`, native unreconstructed gauge storage follows

```text
stride = V / 2 + pad
Ninternal = 2 * Ncolor^2
bytes = 2 * align128(site_dim * 2 * stride * Ninternal * precision / 2)
```

where `site_dim` is 1 for scalar, 4 for vector, 6 for tensor, 8 for coarse, and
16 for Kähler–Dirac-inverse geometry. Current native color-spinor storage follows

```text
raw = site_subset * (V / 2) * Ncolor * Nspin * 2 * precision
raw += site_subset * (V / 2) * 4        when precision is below single
bytes = site_subset * align128(raw / site_subset)
```

with `site_subset` one for a parity field and two for a full field. For a native coarse
link field, the padding used by `DiracCoarse` is twice the largest checkerboarded local
surface. These formulas include field padding and alignment but exclude shared
communication buffers, allocator reservation, peer/runtime state, and every other live
field. Their accuracy is exact only inside that object contract and source revision.

Examples:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" spinor \
  --local 36 36 24 32 --ncolor 3 --nspin 1 --precision single \
  --subset parity --count 2048

python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" gauge \
  --local 6 6 6 8 --ncolor 128 --precision half --geometry coarse \
  --coarse-pad
```

The first command is a retained-vector field allocation, not the eigensolver setup peak.
The second is one native coarse field, not the complete coarse operator.

## Named empirical calibration

The fit commands use calibration `perlmutter-a100-staggered-2024-2026`. The
[`staggered-MG calibration manifest`](staggered-multigrid/calibration.md) defines the
shared operator, machine, hierarchy, ensemble, and convention scope. Memory-specific
populations, errors, build sensitivity, and exclusions live beside the constants in
[`quda-staggered-memory.py`](../../../tools/quda-staggered-memory.py). These are planning
models, not source invariants; inspect both records when applying or updating a fit.

**The error direction is not shared across solvers, so do not carry one solver's bias to
another.** On one workload the plain-CG device estimate **under**-predicted the measured
high-water by roughly a third, while the single matched three-level MG point ran the other
way and **over**-predicted by about a tenth. Treat a CG device estimate as a **lower bound**.
Treat an MG device estimate as **neither bound** until a matched-phase measurement exists on
the target.

That MG over-prediction is weak evidence and must not be read as headroom: it came from a
warm run whose measured peak fell in the steady solve while the model's winning term was a
setup phase, so the two numbers describe different moments. It is one point, phase-mismatched,
and it is **not** licence to shave a cold setup-phase prediction — where the model's known
failure is the opposite direction, below.

For MG, inspect `prediction_assessment.tier` before using the number:

- `calibrated-envelope-current-code` means every checked machine, hierarchy, precision,
  geometry, block, and vector component is inside the recorded calibration envelope. It
  is a reliable screening prediction with the published error, not a runtime guarantee.
- `caveated-extrapolation` means the source formulas still produce a planning estimate,
  but at least one component leaves that envelope and no combined empirical error bound
  applies.
- `unvalidated-structural-extrapolation` is used for two- and three-level hierarchies.
  These paths have never been measured and always emit a loud warning.

The current-code KD correction remains a separately declared one-point extrapolation even
inside the first tier. A final candidate must still be measured on its target stack.

For `mg-fit` JSON, top-level `evidence` is the actual prediction tier above, while
`model_basis` records `corpus-calibrated-with-source-geometry`. Thus an
`--machine other` result says `evidence: caveated-extrapolation` instead of inheriting a
calibrated label. The `detail.phase_model_evidence` string describes whether the
two-, three-, or four-level phase structure has empirical support; it does not claim
that every four-level candidate is inside the calibration envelope.

### Plain CG

For this calibration,

```text
QUDA Device high-water ~= 616.2 MiB + 3003 B * V0
QUDA host high-water   ~= 625.2 MiB + 5014 B * V0
```

These coefficients were fitted to the named Perlmutter A100 corpus. See the companion
script for the fit population, observed errors, build sensitivity, and exclusions.

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" cg-fit --local 36 36 24 32
```

The command excludes the separately reported communication pool and does not predict
scheduler RSS.

### Plain-CG active batch width

For current unsplit mixed-precision MATPC/direct-PC CG, the source-derived device
increment from active batch width `w0` to `w` is

```text
Delta D_CG(w; w0) = (w - w0) [
    5 C_pc(V0, 3, 1, P_precise)
  + (Np + 4) C_pc(V0, 3, 1, P_sloppy)
]
```

`C_pc` is the source-exact parity `ColorSpinorField` allocation and `Np` is
`solution_accumulator_pipeline`. The five precise fields are interface `b`/`x`, CG
`r`/`y`, and the precise operator temporary. The sloppy set is `p`, `Ap`, the mixed
residual, `Np` search-direction fields, and the sloppy operator temporary.

The public command intentionally exposes only the audited current profile: double
precise, half sloppy, and `Np = 1`. In that profile the law reduces to

```text
Delta D_CG(w; w0) = (w - w0) * 160 B * V0.
```

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" mrhs-cg-delta \
  --local 36 36 24 24 --reference-width 1 --width 3
```

Here `w` is the active MILC `block_solver_batch_size`, not necessarily the total
application source count. Three matched Perlmutter A100 width-1 to width-3 cells,
spanning a factor of 10.7 in local volume, validate the per-additional-RHS device term to
at most 0.04%. One cell records QUDA `d61517229`; the relevant field structure remains
at the current `b6998853f` anchor. The other two cells widen the geometry check but omit
their source revision. Older unversioned cells form a different source/path regime and
are excluded rather than fitted into this law.

This is an increment to add to an appropriate one-RHS device estimate, not a replacement
base fit. It excludes deflation-space storage, equal-precision alias changes, other
inverters, heavy-quark residual workspaces, split grid, and whole-process RSS. The
matched cells did not establish any width term for QUDA's pinned-device, page-locked
host, or total-host counters.

### Deflated CG

A single-precision staggered color vector on one parity has logical payload

```text
3 colors * 2 real components * 4 B * V0 / 2 = 12 B * V0.
```

For `n_ev` resident vectors, the observed incremental model was

```text
device increment ~= 1.03 * n_ev * 12 B * V0
host increment   ~=        n_ev * 12 B * V0.
```

The multiplier was fitted to retained-space results in the named Perlmutter A100 corpus;
the companion script contains the population and observed errors. In the observed
file-backed workflow, size for the resident vector count in the file, not only the count
selected for projection.

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" deflated-fit \
  --local 36 36 24 32 --vectors 2048
```

This estimate does not include a larger active eigensolver search basis, a second
preserved parity space, double-precision vectors, the plain-CG production-width
increment above, or
whole-process RSS. Add or measure those according to the executed lifecycle.

## Staggered-MG high-water model

The model is a maximum over allocation phases rather than a sum over every object:

| MG levels | Included phases | Evidence |
|---|---|---|
| 4 | A: near-null generation; B: level-2 build; C: level-3 build | corpus-calibrated |
| 3 | A and B, with estimated deflation on the larger level-2 grid | **never empirically validated** |
| 2 | KD resident state only, plus an optional estimated deflation term | **never empirically validated** |

This matters operationally. If A wins, changing aggregation may not change the peak at
all. If B wins, block size, level-2 volume, coarse color, and MMA copies are directly on
the capacity path. A field inventory added without lifetimes overstates phases that never
coexist and can still miss the real peak phase.

**The winning phase decides whether the coarsest deflation count is visible at all.** The
coarsest eigenspace
is carried in exactly one phase — A at two levels, B at three, C at four — and the
four-level term is sized by `max(nvec 2, nvec 3)`. When another phase wins, or when
`nvec 3 <= nvec 2` at four levels, the reported total is **flat in the deflation count** and its
headroom is not eigenspace-aware. This is not a corner case: a large-volume four-level
candidate frequently peaks in phase A, where the fitted setup workspace dominates, so a
requested eigenspace of several thousand vectors can contribute nothing to the estimate.
`mg-fit` reports `detail.deflation_enters_total` and `detail.deflation_phase`, and emits a
`LOUD WARNING` whenever a positive coarsest deflation count does not reach the total. Never rank an
eigenspace-blind candidate's headroom against a responsive one's.

**A measured peak can also fall outside every modelled phase.** The phases above are setup
phases, treated as alternatives; a run whose high-water occurs in the steady solve, with the
complete hierarchy and a resident eigenspace co-allocated, has no term here. The resulting
error is one-sided — the model under-predicts — and it is not detected by any tier label.
Measure the winner on the target stack.

Most terms are enumerated from source. The model also uses `setup_ws = 17,787 B` per
fine local site for setup workspace and `copy_factor = 1.718` on coarse Y-sets. Those
constants were fitted to four-level, half-precision, `nvec_1 = 64` runs in the named
Perlmutter A100 corpus; detailed population, error, and identifiability caveats are in
the companion script. Another `nvec_1` is an explicit extrapolation. The model reports
the communication pool separately as `Pinned device memory used` and also predicts the
QUDA page-locked host counter.

Coarse gauge color is `2*nvec`, so its link storage scales quadratically. Raising
`nvec` from 64 to 96 multiplies that object by 2.25, not 1.5. Here MMA means the
tensor-core matrix-multiply-accumulate path selected by MILC `use_mma`. It can allocate
additional MILC-order/AoS coarse fields and ghosts, but affects total high-water only
when its phase is the winner. It is not MRHS batch width.

Use global geometry whenever it is known. Requested blocks are adjusted and validated
inside the same command, so the memory model cannot accidentally consume stale requested
values:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" mg-fit \
  --global 144 144 144 288 --ranks 6 3 6 8 \
  --levels 4 --block1 4 6 6 6 --block2 3 2 2 3 \
  --nvec1 64 --nvec2 96 --nvec3 4000 --mma \
  --compiled-nvecs 24 64 96 112 128 \
  --machine perlmutter-a100-40 --corpus-advisories
```

The output includes requested and effective blocks, local and coarse geometry, phase
totals, the winning term breakdown, device and page-locked-host counters, prediction
tier, and every extrapolation. The nested
`geometry.build_capability.QUDA_MULTIGRID_NVEC_LIST.status` is `pass` or `fail` only
when `--compiled-nvecs` is supplied and otherwise says `unchecked`; source-valid geometry
does not prove build capability. If only local dimensions are available, `--local`
remains supported but requires an explicit `--partitioned` mask and cannot establish
that the rank geometry itself lies in the calibration envelope.

### The floor at a fixed placement is phase A, and hierarchy tuning cannot lower it

At a placement already chosen, the device high-water **floor** is phase A — near-null
generation on the fine grid. Phase A scales with fine **local** volume and is invariant to
level count, aggregation blocks, the coarse near-null counts, the coarsest deflation count
and MMA. Only the level-1 near-null count moves it, and weakly: roughly `4%` between counts
of `64` and `24`.

**So retuning the hierarchy cannot rescue a placement whose local volume has already broken
the fit.** No choice of levels, blocks or coarse counts reaches the floor.

**But it can change which placements legally exist**, and that is a different question. An
aggregation block change can make a node count legal that was source-invalid before, and a
legal smaller node count carries a larger local volume and therefore a higher floor. The
order in which to screen those two questions is a tuning decision, not a memory fact; it is
stated once, at
[`tuning.md` gate 3](staggered-multigrid/tuning.md).

This rule was filed with a stronger operational clause — that no hierarchy retuning can
restore a fit that local volume has already broken — and that clause was **falsified the same
day** by a block change that opened a node count where the original blocking was
source-invalid. The floor claim survived; the enumeration around it did not. Evidence:
mechanism, at one ensemble and placement family; the fitted setup-workspace coefficient it
rests on is corpus-fitted, so a refit invalidates the magnitude but not the invariance.

### What the coarsest eigenspace costs, and how that scales

Stored coarsest eigenvectors are the term most often traded against hierarchy shape, so its
scaling is worth stating directly. Storage runs as

```text
coarsest eigenvector storage  ~  coarsest_deflation_count
                                 * coarsest_global_volume
                                 * nvec_(L-1)
```

where `nvec_(L-1)` is the near-null count on the level above the coarsest — the coarse colour
— which is `nvec 2` in a four-level MILC parameter file and `nvec 1` in a three-level one.
Compute exact bytes with the source-exact object layer above rather than from this
proportionality; what follows is the ranking consequence.

**This relation predicts stored bytes on disk, not a device-memory peak.** The eigenspace is
resident in exactly one allocation phase, and whether that phase is the winner decides
whether it appears in the high-water figure at all — see the phase model above. Ranking
candidates by predicted device peak using this relation will silently rank an
eigenspace-blind candidate against a responsive one.

**Affordable density falls as the square of coarsest volume.** Under a fixed memory budget the
affordable `coarsest_vector_density` scales as `1/coarsest_global_volume^2`, because the
budget caps the count while the density divides it by the volume again. Halving coarsest
volume quadruples the density you can afford. This is the term that decides whether an
eigenspace-heavy candidate fits, and it is why two candidates with similar coarsest volumes
can differ sharply in what deflation they can carry.

**Coarsest volume is set by the product of the effective aggregation blocks, not by level
count.** Removing a final aggregation multiplies coarsest volume by that block's effective
volume. Matching density across two such hierarchies then costs a storage ratio of
`(V_a/V_b)^2 * (colour_a/colour_b)` — which is the quantified price of the substitution that
[`hierarchy-and-setup.md`](staggered-multigrid/hierarchy-and-setup.md) already tells you not
to make: carry the coarsest deflation count across a level-count change, do not match density.

**Use effective blocks, never requested ones.** QUDA halves a block it cannot use, and the
difference is not marginal: in one recorded case a requested `2x2x2x2` second aggregation
became `2x2x2x1`, because the level-2 local `t` extent of `6` would have given an odd coarse
extent — doubling the coarsest volume against what the requested blocks implied. Every
quantity in this section is wrong by that factor if requested blocks are used. The `mg-fit`
command above adjusts and validates blocks inside the same invocation for exactly this
reason.

### Unvalidated hierarchy, precision, and fit controls

Pass `--levels 2` with no aggregation blocks or `--levels 3` with `--block1`. Both modes
emit `LOUD WARNING` on stderr and in JSON because neither has ever been empirically
validated. The three-level estimate includes the coarse deflation space on the larger
level-2 grid; omitting that term can turn an apparent fit into an out-of-memory run.

`--null-precision` and `--setup-precision` expose the source-sized precision terms.
`--setup-ws-bytes-per-site` and `--coarse-copy-factor` expose the two fitted controls.
The defaults are the only empirically calibrated combination. Any precision change or
control override is deliberately allowed for what-if analysis but emits a loud warning
and invalidates the published error statistics.

When improving the model, start in the companion script at `CALIBRATION`, the
`CALIBRATED_*` support sets, `mg_corpus_fit()`, and `prediction_assessment()`. Attach a
new allocation to the phases in which it is live, refit rather than silently replacing a
constant, and validate device, communication-pool, and page-locked-host counters
separately.

### Communication pool

Current source keeps four device communication buffers and grows them to the largest
encountered ghost requirement. The current-code corpus calibration estimates the separate
`Pinned device memory used` counter as

```text
26,812 B * sum(partitioned surfaceCB).
```

That coefficient was fitted to the later-code portion of the named Perlmutter A100
corpus; its detailed error is in the companion script metadata, while the historical-code
value appears only in an adjacent source comment. It is not an API guarantee and should be replaced by a target-build
measurement when available.

**Scope limit: the coefficient is calibrated on fully-partitioned geometries and
over-predicts when few directions are partitioned.** On a target with all four directions
partitioned (32 ranks, `2x2x2x4`) it was accurate to `0.4%` — predicted `1,361` MiB against
`1,366.9` MiB observed, and the observed value repeated on every run of that geometry. With
only `t` partitioned (4 ranks, `1x1x1x4`) it over-predicted by `31%`: about `3,350` MiB
predicted against `2,304.0` MiB observed. The likely mechanism is that current source keeps
four buffers grown to the largest encountered ghost requirement, so a coefficient fitted
against fully-partitioned geometries stops tracking the surface sum once few directions are
partitioned; that is a hypothesis, not a measured cause. The error direction is the safe
one. Empirical, one low-partition point.

### Kähler–Dirac current-code calibration

The calculator targets QUDA at or after `0006627c1` and applies the current-code
high-water correction fitted from a same-allocation 0.04-fm result. Scaling that
correction to another local volume is an extrapolation. The companion script records the
measurement and how the historical allocation differed; there is no pre-fix runtime
selector.

### MRHS-MG: marginal slope only

Source inspection closes a marginal production-field slope for one exact four-level
topology: optimized KD, outer GCR(15), post CA-GCR(8), intermediate GCR(8), bottom
Chebyshev CA-GCR(16), double outer precision, single sloppy/coarse precision, and half
fine/pseudo-fine preconditioning. After the recursive solvers are created, each
additional active RHS keeps the following fields live together:

```text
fine and KD pseudo-fine: 3 double full + 54 single full + 18 half full
level 2:                2 single full + 27 single parity
level 3:                2 single full + 32 single parity
```

For the matched four-level hierarchy with fine volume `884736`, level-2 volume `1024`,
and `coarsest_global_volume = 64`,
`nvec_1 = 64`, and `nvec_2 = 96`, this field inventory is `1475.1875 MiB` per
additional active RHS. A historical build-`7519b9dcf` width-2 to width-3 pair measured
`1481.4 MiB`, 0.42% above that source slope.

This does **not** define an absolute MRHS-MG capacity model. The matched width-1 to
width-2 transition also activated an unexplained `5467.3 MiB` fixed high-water term.
Its source owner, build transfer, and behavior on another hierarchy are unresolved.
The calculator therefore has no MRHS-MG width option: use the slope only as a scoped
marginal diagnostic for the named topology, and measure the complete high-water at the
target widths and stack.

## Independent target measurements

The following were measured on a single 0.09-fm HISQ target (`64^3 x 96`, Perlmutter
A100-40, QUDA `b6998853f`, MILC `6b9b8a06e`, 32 ranks at `2x2x2x4`, `nvec_1 = 64`,
`use_mma` true), comparing each prediction with the QUDA `Device memory used` counter
like for like. **They are accuracy observations against the named calibration, not
correction factors.** Do not multiply a prediction by any ratio below: the population is
one workspace, one build, and one ensemble, and
[`staggered-multigrid/calibration.md`](staggered-multigrid/calibration.md) places the
0.09-fm population outside the fitted envelope for exactly this reason.

| Path | Prediction tier reported | Measured / predicted |
|---|---|---|
| Plain CG, two local volumes an eight-fold span apart | `corpus-calibrated` | `1.318`, `1.339` |
| Three-level MG, one hierarchy at three eigenspace sizes | `unvalidated-structural-extrapolation` | `0.902`, `0.923`, `0.980` |
| Four-level MG, three coarsest-grid shapes | `caveated-extrapolation` | `1.080`, `1.091`, `1.135` |

Three consequences are worth carrying:

- **The plain-CG fit under-predicted by about a third at both volumes**, against its
  published device rms of `7.2%` and maximum of `12.6%`, with both points inside the
  stated envelope. The near-constant *relative* offset across an eight-fold volume span
  suggests a missing term that scales with `V0` rather than a fixed per-rank constant.
  Confounds that were not excluded: a `multimass` set dispatch issuing two solver calls
  per checked solve, resident application-side gauge state, and the build's
  `KS_MULTICG` option. **Treat a predicted plain-CG device figure as a lower bound for a
  MILC `ks_spectrum` multimass workload**, and measure before committing to a capacity
  decision inside the advisory band.
- **The sign of the MG error flipped with level count** — three levels over-predicted,
  four levels under-predicted — so no single correction exists, and a level count is not
  a free parameter for a capacity estimate. The four-level errors are the unsafe
  direction.
- **The tier labels did not order the outcomes.** The three-level path, which this page
  warns has never been empirically validated, was the more accurate of the two and erred
  conservatively; two of the three four-level points were eigenspace-blind in the sense
  described above, which inflates their spread. A tier states what evidence exists, never
  how accurate a given prediction will be.

## A loading run and a generating run are not the same capacity problem

Near-null generation allocates a fine-grid workspace that a run **loading** stored vectors
never allocates at all, so a loading run's device high-water sits materially below an
otherwise identical generating run's. The gap is structural — it is the presence or
absence of an allocation, not a fitted difference — so **size the two separately and never
quote one as a bound on the other.** A capacity plan built from a loading run will
under-provision the run that has to create the vectors in the first place.

Two consequences follow for planning:

- **The expensive placement and the recurring placement can be decoupled.** Because
  single-file vectors carry no rank-grid binding, generation and later solves need not run
  at the same decomposition — the partfile format does bind, and that distinction is the
  subject of [`../internals/vector-io-layout.md`](../internals/vector-io-layout.md). A
  one-off generation run may therefore be placed where it fits rather than where the
  production solve is cheapest.
- **A run that loads some levels and generates others is neither case** and must be sized
  as a generating run.

**Scope and evidence.** Empirical at four levels on one ensemble, plus the source-level
fact that the workspace is allocated only on the generating path; the mechanism is
expected to transfer and no ratio is quoted, since the magnitude depends on the fine local
volume. Invalidated by a change to the setup-workspace model or to the vector format's
placement binding.

## Disabling MMA is a coupled memory-throughput lever, not a memory remedy

Turning `use_mma` off measurably lowers device high-water — consistent with the extra
MILC-order coarse-gauge copies and ghosts that the MMA path can retain, recorded in
[`../staggered-multigrid.md`](../staggered-multigrid.md) — but it is not free. In the one
recorded attempt the memory saving was real and substantial while the same eigensolve made
only marginal progress in the time available, so the throughput cost was large and remains
**unquantified**.

**Actionable consequence.** Treat `use_mma false` as a coupled axis to be measured on both
memory and time together, never as a capacity fix reached for when a candidate does not
fit. Where it is being considered for fit alone, prefer a decomposition or placement change
first — those move the fine local volume, which is what actually sets the floor.

**Scope and evidence.** Empirical, a single observation on one ensemble at three levels;
the direction of both effects is the transferable content and neither magnitude is quoted.
Invalidated by a change in QUDA's MMA implementation or in the coarse colour.

## Capacity decisions and A100 margin

Three sampled Perlmutter A100 runs placed whole-device `nvidia-smi` high-water 1.8–2.8
GiB above the sum of QUDA's two device counters. The retrospective workflow used a 4-GiB
MG advisory band to cover that observed context/allocator gap together with model error
and fragmentation.

That 4-GiB number is a **Perlmutter A100 corpus advisory**, not a QUDA requirement or a
portable GPU default. Use it explicitly when that evidence is applicable:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" mg-fit \
  --global 144 144 144 288 --ranks 6 3 6 8 \
  --levels 4 --block1 4 6 6 6 --block2 3 2 2 3 \
  --nvec1 64 --nvec2 96 --nvec3 4000 --mma \
  --compiled-nvecs 24 64 96 112 128 \
  --machine perlmutter-a100-40
```

The tool reports `estimated-over-capacity`,
`estimated-headroom-below-margin`, or `estimated-headroom-meets-margin`. The names say
which side of the requested margin the estimate occupies; none is a guaranteed fit. On
another machine or allocator, measure the gap and supply a local margin. A prediction
inside its own error band is an unresolved sizing result, not evidence that a nearly
fitting job is safe.

## Exhaustive inverse node sizing

`mg-search` answers the inverse question without selecting only one cube-like layout. It
enumerates every four-dimensional rank-grid factorization that tiles the supplied global
lattice below an **exclusive** node limit, derives each local shape and partition mask,
applies QUDA block adjustment, discards source-invalid hierarchies, and prices every
remaining model-compatible decomposition. The default `--min-local 1` imposes no hidden
cube-size heuristic; a larger value is an explicit search filter, not a QUDA rule.

For example, to search a four-level 0.06-fm lattice on fewer than 17 Perlmutter
nodes (replace `17` with the intended exclusive bound):

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-memory.py" mg-search \
  --global 96 96 96 192 --nodes-lt 17 \
  --machine perlmutter-a100-40 \
  --levels 4 --block1 6 6 6 4 --block2 2 2 2 2 \
  --nvec1 64 --nvec2 96 --nvec3 2048 --mma \
  --compiled-nvecs 24 64 96 112 128
```

The result partitions every source-valid, model-compatible rank geometry into
`estimated_headroom_meets_margin`, `estimated_headroom_below_margin`, or
`estimated_over_capacity`. The first category is the defensible screening answer to
“which has the requested estimated headroom?”; it is still not a run guarantee.
Each row carries its prediction tier, requested-versus-effective blocks, both device
counters, page-locked host per rank and node, and warnings. The counts prove that all
rank geometries considered were source-invalid, outside the checkerboarded memory model's
representable domain, or returned exactly once.

The search currently has one built-in machine profile, `perlmutter-a100-40`. Use
`mg-fit --machine other --gpu-gib ... --margin-gib ...` for a caveated one-decomposition
estimate elsewhere. Add another named search profile only after its ranks per node,
device capacity, host capacity, context/allocator gap, and model transfer have been
measured.

## Page-locked host prediction and remaining limits

The MG tool predicts QUDA's `Page-locked host memory used` using

```text
MG page-locked host = CG QUDA host - CG host-pool + MG host-pool.
```

This identity and its parameter-to-counter prediction were validated in the named corpus;
population and errors live in the script. On current code, the CG and MG pool calibrations
are the same, but the explicit subtraction/addition is retained so a target-build pool
measurement has a correct place to enter.

Do not construct a whole-process host formula from this calibration. The unexplained gap
between QUDA's page-locked and total host counters reached 1.53 GiB, while scheduler
`MaxRSS` spanned 1.35–3.81 times the QUDA total across MG groups. The plain-CG device
increment above creates no host formula, and the unresolved MRHS-MG activation term must
not be added to a capacity estimate as though it were transferable.

For a capacity decision, record and compare all of the following on the target stack:

1. local lattice and rank geometry;
2. requested and executed blocks, `nvec`, precision, MMA, source count, and solver phase;
3. QUDA `Device`, `Pinned device`, `Page-locked host`, and `Total host` high-water;
4. whole-device sampling and scheduler `MaxRSS`;
5. QUDA/MILC revisions, allocator and communication backend, and warm-state contract;
6. model calibration name, result, error or advisory band, and every extrapolation; and
7. whether setup, steady solve, or a reused state owns the reported peak.

Measure the final candidate on the actual stack. The calculator is a screening and
diagnostic instrument; it does not upgrade a corpus fit into runtime validation.
