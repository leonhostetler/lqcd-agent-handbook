---
title: QUDA staggered solver memory and capacity accounting
summary: Source-exact field sizes, evidence-tiered CG and multigrid high-water estimates, integrated decomposition search, and capacity decision rules.
scope: [software:quda, software:milc, fermion:staggered]
load_when: Sizing or diagnosing device and host memory for plain CG, deflated CG, or staggered multigrid; or finding rank decompositions under a machine-scoped node limit.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_internal.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/color_spinor_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/gauge_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/dirac_coarse.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/lattice_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/cuda/malloc.cpp
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
python3 tools/quda-staggered-memory.py spinor \
  --local 36 36 24 32 --ncolor 3 --nspin 1 --precision single \
  --subset parity --count 2048

python3 tools/quda-staggered-memory.py gauge \
  --local 6 6 6 8 --ncolor 128 --precision half --geometry coarse \
  --coarse-pad
```

The first command is a retained-vector field allocation, not the eigensolver setup peak.
The second is one native coarse field, not the complete coarse operator.

## Named empirical calibration

The fit commands use calibration `perlmutter-a100-staggered-2024-2026`, obtained from
MILC HISQ runs with QUDA staggered solvers on Perlmutter A100 GPUs. These are planning
models, not source invariants. Detailed populations, errors, build sensitivity, and
exclusions live beside the constants in
[`quda-staggered-memory.py`](../../../tools/quda-staggered-memory.py); inspect them only
when applying or updating a fit.

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

### Plain CG

For this calibration,

```text
QUDA Device high-water ~= 616.2 MiB + 3003 B * V0
QUDA host high-water   ~= 625.2 MiB + 5014 B * V0
```

These coefficients were fitted to the named Perlmutter A100 corpus. See the companion
script for the fit population, observed errors, build sensitivity, and exclusions.

```bash
python3 tools/quda-staggered-memory.py cg-fit --local 36 36 24 32
```

The command excludes the separately reported communication pool and does not predict
scheduler RSS.

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
python3 tools/quda-staggered-memory.py deflated-fit \
  --local 36 36 24 32 --vectors 2048
```

This estimate does not include a larger active eigensolver search basis, a second
preserved parity space, double-precision vectors, undeflated MRHS overhead, or
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

Most terms are enumerated from source. The model also uses `setup_ws = 17,787 B` per
fine local site for setup workspace and `copy_factor = 1.718` on coarse Y-sets. Those
constants were fitted to four-level, half-precision, `nvec_1 = 64` runs in the named
Perlmutter A100 corpus; detailed population, error, and identifiability caveats are in
the companion script. Another `nvec_1` is an explicit extrapolation. The model reports
the communication pool separately as `Pinned device memory used` and also predicts the
QUDA page-locked host counter.

Coarse gauge color is `2*nvec`, so its link storage scales quadratically. Raising
`nvec` from 64 to 96 multiplies that object by 2.25, not 1.5. MMA can allocate additional
MILC-order fields and ghosts, but it affects total high-water only when its phase is the
winner.

Use global geometry whenever it is known. Requested blocks are adjusted and validated
inside the same command, so the memory model cannot accidentally consume stale requested
values:

```bash
python3 tools/quda-staggered-memory.py mg-fit \
  --global 144 144 144 288 --ranks 6 3 6 8 \
  --levels 4 --block1 4 6 6 6 --block2 3 2 2 3 \
  --nvec1 64 --nvec2 96 --nvec3 4000 --mma \
  --machine perlmutter-a100-40 --corpus-advisories
```

The output includes requested and effective blocks, local and coarse geometry, phase
totals, the winning term breakdown, device and page-locked-host counters, prediction
tier, and every extrapolation. If only local dimensions are available, `--local` remains
supported but requires an explicit `--partitioned` mask and cannot establish that the
rank geometry itself lies in the calibration envelope.

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

### Kähler–Dirac current-code calibration

The calculator targets QUDA at or after `0006627c1` and applies the current-code
high-water correction fitted from a same-allocation 0.04-fm result. Scaling that
correction to another local volume is an extrapolation. The companion script records the
measurement and how the historical allocation differed; there is no pre-fix runtime
selector.

## Capacity decisions and A100 margin

Three sampled Perlmutter A100 runs placed whole-device `nvidia-smi` high-water 1.8–2.8
GiB above the sum of QUDA's two device counters. The retrospective workflow used a 4-GiB
MG advisory band to cover that observed context/allocator gap together with model error
and fragmentation.

That 4-GiB number is a **Perlmutter A100 corpus advisory**, not a QUDA requirement or a
portable GPU default. Use it explicitly when that evidence is applicable:

```bash
python3 tools/quda-staggered-memory.py mg-fit \
  --global 144 144 144 288 --ranks 6 3 6 8 \
  --levels 4 --block1 4 6 6 6 --block2 3 2 2 3 \
  --nvec1 64 --nvec2 96 --nvec3 4000 --mma \
  --machine perlmutter-a100-40
```

The tool reports `over-capacity`, `inside-advisory-band`, or
`outside-advisory-band`; it deliberately never reports a guaranteed fit. On another
machine or allocator, measure the gap and supply a local margin. A prediction inside its
own error band is an unresolved sizing result, not evidence that a nearly fitting job is
safe.

## Exhaustive inverse node sizing

`mg-search` answers the inverse question without selecting only one cube-like layout. It
enumerates every four-dimensional rank-grid factorization that tiles the supplied global
lattice below an **exclusive** node limit, derives each local shape and partition mask,
applies QUDA block adjustment, discards source-invalid hierarchies, and prices every
remaining model-compatible decomposition. The default `--min-local 1` imposes no hidden
cube-size heuristic; a larger value is an explicit search filter, not a QUDA rule.

For example, to search a four-level 0.06-fm lattice on fewer than `XXX` Perlmutter nodes:

```bash
python3 tools/quda-staggered-memory.py mg-search \
  --global 96 96 96 192 --nodes-lt XXX \
  --machine perlmutter-a100-40 \
  --levels 4 --block1 6 6 6 4 --block2 2 2 2 2 \
  --nvec1 64 --nvec2 96 --nvec3 2048 --mma
```

The result partitions every source-valid, model-compatible rank geometry into
`outside_advisory_band`, `inside_advisory_band`, or `over_capacity`. The first category
is the defensible screening answer to “which fit?”; it is still not a run guarantee.
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
`MaxRSS` spanned 1.35–3.81 times the QUDA total across MG groups. Undeflated MRHS and
MRHS-MG increments were measured in the corpus but were not mechanistically modelled.
MRHS memory modeling is an explicit roadmap item; until it lands, do not add an observed
constant to a capacity estimate as though it were a transferable formula.

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
