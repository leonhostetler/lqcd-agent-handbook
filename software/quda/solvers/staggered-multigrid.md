---
title: QUDA staggered multigrid through MILC
summary: Full-system GCR-MG structure, hierarchy lifecycle, build and decomposition constraints, memory objects, suitability, and runtime checks for MILC staggered solves.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Selecting, configuring, sizing, debugging, or validating QUDA staggered multigrid through MILC.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/milc_interface_internal.hpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/multigrid.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solver.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solve.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/block_orthogonalize.in.cu
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/coarse_op.cuh
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/interface_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface_internal.cpp
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/CMakeLists.txt
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c
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

# QUDA staggered multigrid through MILC

The observed MILC “MG” path is a full staggered Dirac solve with outer
`QUDA_GCR_INVERTER` and a reusable QUDA multigrid preconditioner. The outer solver is
not `QUDA_MG_INVERTER`; that enum identifies the attached preconditioner through
`inv_type_precondition`.

This distinction determines the operator, residual, memory model, and runtime messages.
It also makes the path non-equivalent to MILC's parity-normal-equation CG call.

## Operator and solve structure

The MILC interface fixes the outer solve to:

```text
inv_type              = QUDA_GCR_INVERTER
inv_type_precondition = QUDA_MG_INVERTER
solution_type         = QUDA_MAT_SOLUTION
solve_type            = QUDA_DIRECT_SOLVE
gcrNkrylov            = 15
pipeline              = 16
```

Thus GCR solves the full naive or improved-staggered Dirac system. The parity field in
`QudaInvertArgs_t` is currently a dummy for this path; source parity is a property of the
right-hand side, not a request for an even-only or odd-only MG solve.

Each preconditioner application executes a recursive multigrid cycle. Depending on the
level and configuration, that cycle performs pre-smoothing, residual construction and
restriction, a coarse solve or another recursive cycle, prolongation of the correction,
and post-smoothing. The outer flexible GCR recurrence retains a Krylov basis and applies
the full fine operator to converge the requested residual.

## Hierarchy construction

`qudaMultigridCreate` loads the fat/long gauge fields, reads the MILC-interface MG
parameter file, builds a `QudaMultigridParam`, and calls `newMultigridQuda`. The default
interface constructs four levels:

1. the fine staggered or asqtad operator;
2. a Kahler–Dirac-transformed level, using optimized KD by default;
3. one or more aggregation-coarsened levels with generated near-null vectors; and
4. the coarsest solver, optionally with eigensolver deflation when its configured
   `nvec` is positive.

For optimized KD, the top transfer has geometric block size one and uses the fine color
count. Coarse KD instead requires `2 x 2 x 2 x 2` blocking and exactly 24 coarse vectors.
Subsequent aggregation levels generate and block-orthonormalize near-null vectors and
build coarse link fields.

The parameter file controls level count, preconditioner precision, KD transfer type,
aggregation sizes, near-null counts and setup solves, smoothers, coarse solvers, MMA
flags, optional vector I/O, coarsest-level deflation, and multi-source batch size. Some
top-level choices remain prescribed by the interface rather than the file, including the
full outer solve and GCR.

For the four-level optimized-KD hierarchy, use this index crosswalk:

| Executed level | MILC parameter-file index | Tool argument | Meaning |
|---|---|---|---|
| `0`, fine operator and KD transfer | interface-fixed `n_vec[0] = 3` and unit KD block | none | optimized-KD fine-color transfer |
| `1`, KD pseudo-fine | `nvec 1`, `geo_block_size 1`, `setup_* 1` | `--nvec1`, `--block1` | first user aggregation constructs level 2 |
| `2`, intermediate coarse | `nvec 2`, `geo_block_size 2`, `setup_* 2` | `--nvec2`, `--block2` | second user aggregation constructs level 3 |
| `3`, coarsest solve/deflation | `nvec 3` | `--nvec3` | requested deflation-vector count, not a coarse color |

Only `nvec_1` and `nvec_2` select generated coarse-color kernels and must appear in
`QUDA_MULTIGRID_NVEC_LIST`; `nvec_3` does not.

<a id="level-naming"></a>
### Numbered symbols are level indices; role names are roles

**A numbered symbol names an executed level, not a position in the hierarchy.** `V2` and `V3`
are the global grid volumes at executed levels 2 and 3. They coincide with "the coarsest grid"
only for the four-level hierarchy tabulated above; a three-level hierarchy's coarsest grid is
level 2, so its coarsest volume is `V2` and its coarsest density is `nvec_2 / V2`.

Three rules follow, and the third is the one that is easy to get wrong:

1. **Use role names in any statement meant to hold at more than one level count** —
   `coarsest_global_volume`, `coarsest_vector_density`, `coarsest_cell_aspect`. These are what
   [`quda-staggered-decomposition.py`](../../../tools/quda-staggered-decomposition.py) always
   reports. It emits the numbered aliases `V3_global` and `nu3` only for a four-level hierarchy
   and `V2_global` only for a three-level one, so an alias cannot outlive its level count.
   `coarsest` is the canonical role word throughout this handbook; `terminal` appears in some
   campaign records as a synonym for the same grid and is normalized to `coarsest` on import.
2. **Use a numbered symbol only where the level count is fixed** by the surrounding text or by
   an explicit statement. Read a numbered symbol from another page or corpus as naming a
   *different grid* unless that page's level count matches.
3. **Renaming a quantity does not rescope a band.** `coarsest_global_volume` is well defined at
   any level count; `V3 >= 10000` is a threshold fitted on four-level hierarchies. Rewriting the
   threshold in role-based form does not make it apply at three levels — it silently converts a
   level-scoped advisory into a level-independent one, which is the extrapolation
   [`calibration.md`](staggered-multigrid/calibration.md) excludes. **Every numerical band
   therefore carries its fitted level count inline, next to the number**, and the decomposition
   tool declines to evaluate a band outside the level count it was fitted at, reporting
   `empirical_screen.evaluated = false` rather than an empty advisory list.

The distinction is between a *quantity*, which is role-based, and a *band*, which is
population-scoped. Only the first travels for free.

MILC `use_mma` selects QUDA's tensor-core matrix-multiply-accumulate path. In the
observed memory path it can retain extra MILC-order/AoS coarse-gauge copies and ghosts.
It is independent of active multi-right-hand-side batch width: `use_mma = true` does not
mean multiple sources, and a batch-width setting does not by itself enable MMA.

## Reuse, updates, and cleanup

MILC stores the MG object in one static process-global `mg_preconditioner` pointer.
It creates the hierarchy when notified that fermion links are fresh and the pointer is
null. Later link or mass changes cause `qudaInvertMsrcMG` to reload gauge fields and call
`updateMultigridQuda`:

- a **full** update rebuilds the fine operators and resets or refreshes hierarchy state;
- a **thin** update changes fields and mass in place where supported and resets the
  staggered KD fields without regenerating all hierarchy state.

The requested rebuild mode is consulted only when an update is required. It does not
force work on every solve.

The observed MILC source explicitly notes that changing `mgparamfile` after the static
object exists is not detected. Treat the parameter-file identity as part of the MG
object's lifecycle: destroy and recreate the object rather than assuming a new filename
will reconfigure it.

`mat_invert_mg_cleanup` calls `qudaMultigridDestroy`; use it as a terminal cleanup in the
observed implementation. The static pointer is not reset to null after destruction, so
creating another hierarchy in the same process after that cleanup requires a source fix
or an audited lifecycle wrapper.

Stored near-null vectors carry a further lifecycle boundary that is invisible to the
hierarchy parameters: a set saved in QIO partfile format is readable only under the rank-grid
factorization that wrote it. See
[`../internals/vector-io-layout.md`](../internals/vector-io-layout.md) before reusing saved
vectors across a placement change.

## Cost structure

Separate these costs in every measurement:

- gauge load and hierarchy setup or update;
- near-null generation, orthonormalization, and coarse-operator construction;
- optional coarsest-level eigensolver setup;
- one recursive MG preconditioner application per outer GCR step;
- outer fine-operator work and GCR orthogonalization; and
- multi-source batching, residual checks, and any vector I/O.

Hierarchy setup is reusable only across solves for which its links, mass/update policy,
parameter file, decomposition, and other operator state remain valid. A timing that
omits setup answers a different question from end-to-end time. Always state the solve
count over which setup is amortized.

## Build and stack requirements

QUDA must compile the MILC interface, staggered operators, and multigrid:

```text
QUDA_INTERFACE_MILC=ON
QUDA_DIRAC_STAGGERED=ON
QUDA_MULTIGRID=ON
```

MILC must link QUDA, enable its improved-staggered GPU CG backend, and define the MG
path (`HAVE_QUDA`, `USE_CG_GPU`, and `MULTIGRID` in the observed source; corresponding
CMake controls are `WANTQUDA`, `WANT_FN_CG_GPU`, and `WANT_MULTIGRID`).

QUDA compiles coarse-color and multi-right-hand-side kernels for configured lists. The
requested `nvec_1` and `nvec_2` must be represented in
`QUDA_MULTIGRID_NVEC_LIST`, while a selected active multi-source batch shape must be
represented in `QUDA_MULTIGRID_MRHS_LIST`. These are separate checks from the runtime
`use_mma` switch. The QUDA defaults are not proof that an arbitrary MILC `nvec` or batch
size was instantiated.

The `mg-staggered` build profile and
`machines/perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/stack.yaml` record one
validated native QUDA path on `gpu-a100-40`. Its synthetic unit-gauge test covers the
listed hierarchy, generated coarse-color set, QMP backend, and `sm_80` target; it does
not validate a linked MILC executable, other hierarchy shapes, `gpu-a100-80`, or
production performance. The linked MILC layer is recorded separately in
[`milc-cuda13-quda-ks-spectrum-mg-2026q3`](../../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md),
which is itself narrow. Require a stack whose scope matches the intended run rather
than generalizing from either bounded validation.

## Geometry and decomposition constraints

Each aggregation block acts on the local lattice at that level. QUDA's transfer
constructor checks each requested block size and, when invalid, repeatedly halves it
while warning until it finds a usable value or reaches zero and errors. A usable block
must divide the local extent and produce a supported even coarse extent; the x direction
also cannot collapse to a single block in the rejected case.

This behavior means the input `geo_block_size` is not necessarily the executed block
size. Confirm the `Transfer: using block size ...` message for every aggregation level.

Additional hard constraints include:

- optimized KD requires unit geometric block volume and fine-color `Nvec`;
- coarse KD requires block size two in all four dimensions and `Nvec = 24`;
- an aggregation coarse space may not exceed the degrees of freedom in its aggregate;
- the current top-level MG constructor accepts only `QUDA_DIRECT_SOLVE` for the outer
  system;
- each smoother solve type must be direct or direct-preconditioned; and
- improved-staggered long-link coarsening requires aggregate extent at least three in
  each coarsened direction unless `allow_truncation` explicitly permits dropping those
  long-link contributions. This binds on the **first** aggregation, where the improved
  operator still carries long links, and never on a coarse-to-coarse stage; with
  `allow_truncation` false, QUDA's default, it is a hard error rather than a silent
  adjustment. Combined with the level-1 even requirement, a first-stage extent must be
  even and at least four; and
- with `use_mma true`, the coarse gauge colour `2*nvec_(L-1)` must be one of `12, 48,
  64, 128, 192`; other values abort in coarse-operator construction. This restricts the
  usable near-null counts to `{6, 24, 32, 64, 96}` and is **independent of**
  `QUDA_MULTIGRID_NVEC_LIST`. The constraint acts on the derived coarse gauge colour, not
  on the requested `nvec`, which is why a value such as `nvec_1 = 48` can be a legal
  aggregation and a compiled coarse colour and still fail at runtime. This is the second
  constraint that turns on `2*nvec_(L-1)` rather than `nvec` itself — coarse-operator
  cost, which scales as `(2*nvec)^2`, is the other.

Decomposition choice therefore changes both legality and the executed hierarchy. Check
it before allocating a long setup job; do not infer validity from global lattice
divisibility alone.

Use the source-scoped preflight tool before sizing:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-staggered-decomposition.py" \
  --global 64 64 64 96 --ranks 2 2 2 3 \
  --block1 4 4 4 4 --block2 2 2 2 2 \
  --nvec1 64 --nvec2 96 --nvec3 0 \
  --compiled-nvecs 24 64 96 112 128
```

It emulates the current transfer constructor's halving, keeps requested and effective
blocks separate, checks aggregate, long-link, and compiled-`nvec` constraints, and reports
global and local coarse volumes. Pass `--mma` to check the coarse gauge colour against
QUDA's supported MMA set; the result appears as
`build_capability.QUDA_MMA_COARSE_GAUGE_COLOR.status`, which is `unchecked` unless `--mma`
or `--no-mma` is supplied. Pass `--allow-truncation` to enumerate the truncated long-link
space deliberately. Every result is derived from the supplied global lattice and rank
geometry; there is no built-in lattice size or lattice-spacing default. The
`build_capability.QUDA_MULTIGRID_NVEC_LIST.status` field is `pass` or `fail` only when
`--compiled-nvecs` is supplied; otherwise it is explicitly `unchecked`. A geometry
`source_status: pass` with an unchecked build capability is not proof that the executable
contains the requested coarse-color kernels.

For the observed optimized-KD MILC hierarchy, the first true
aggregate has coarse-space capacity `3*b1/2`, while the next uses
`nvec_1*b2`: coarse `ColorSpinorField` color is `nvec_1` with spin stored separately,
even though the corresponding coarse **gauge** field combines them into color
`2*nvec_1`.

Adding `--corpus-advisories` applies a separate, provisional screen mined from four
ensembles: warn below global `V3 = 10000` sites or above coarsest-cell aspect 1.5 — both fitted at four
levels, and the tool declines to evaluate them at any other level count
([level naming](#level-naming)). Those
warnings are empirical tuning evidence, not QUDA errors. The tool's source status remains
independent, and runtime `Transfer: using block size ...` output remains authoritative.

## Empirical tuning guidance

This page owns the current source and interface contract. The
[`calibration manifest`](staggered-multigrid/calibration.md) defines the population,
literal mass convention, advisory-specific exclusions, and meaning of “closely matched”
for the separately labelled `perlmutter-a100-staggered-mg-2024-2026` retrospective.
The following action leaves carry its guidance:

- [`staggered-multigrid/hierarchy-and-setup.md`](staggered-multigrid/hierarchy-and-setup.md)
  for global coarse geometry, `nu3`, and the level-1 setup-tolerance knee;
- [`staggered-multigrid/coarse-deflation.md`](staggered-multigrid/coarse-deflation.md)
  for the fitted coarse-spectrum envelope, filter-window feedback, restart diagnostics,
  and workload-derived deflation schedules;
- [`staggered-multigrid/tuning.md`](staggered-multigrid/tuning.md) for the ordered tuning
  gates and stop rules; and
- [`staggered-multigrid/diagnostics.md`](staggered-multigrid/diagnostics.md) for setup,
  hierarchy, and eigensolver triage.

Their numerical bands are corpus advisories, not QUDA invariants or solver-global
defaults. The handbook intentionally withholds retrospective solver timing and crossover
values; derive those from matched target-workload measurements and the compatible-reuse
cost model.

## When to use it

Use this path when:

- the application intends a full-system staggered solve rather than an exposed
  single-parity normal equation;
- a legal hierarchy and compiled coarse-color set exist for the selected local geometry;
- the hierarchy can be reused or updated across enough compatible solves to justify
  setup and resident memory;
- a validated machine stack supports the selected precision, communication, MMA, and
  multi-source configuration; and
- setup, solve, true residual, and application correctness can all be measured.

MG is structurally suited to cases where eliminating slow error components through a
hierarchy is valuable across repeated solves. Source code alone does not determine the
mass, volume, solve count, or machine at which it beats CG or deflated CG.

## When not to use it

Do not use this path when:

- the build lacks any required QUDA/MILC capability or requested coarse-color
  instantiation;
- local dimensions cannot support the effective KD and aggregation hierarchy;
- an asqtad aggregation is too small for long links and dropping them is not an accepted
  approximation;
- the workflow requires a caller-provided nonzero initial guess—the observed interface
  marks MG initial-guess handling as broken because of its sign convention;
- the parameter file or represented operator changed but the static hierarchy cannot be
  safely destroyed and recreated or updated;
- one-off setup and memory cannot be amortized within the stated solve count; or
- only steady-state solve timing can be measured while the decision requires end-to-end
  cost.

Do not compare its outer iteration count numerically with parity CG iterations. The
operators, recurrence, and work per iteration differ.

## Tunables and hard invariants

The major hierarchy controls are level count, KD transfer type, aggregation blocks,
near-null counts, setup solver and iteration cap, null/coarse precision, pre/post
smoothing, coarse solver/tolerance/cap, coarsest deflation, vector I/O, MMA use,
long-link truncation, rebuild type, GCR basis, and right-hand-side batch size.

The current interface also fixes behavior that should not be mistaken for a tuned input:

- outer solver: GCR;
- outer system: full `M`, direct solve;
- outer sloppy precision: single precision;
- outer GCR basis in the solve wrapper: 15;
- top-level spin blocking: zero for staggered chirality mapping; and
- initial guess: effectively unsupported in the MILC MG wrapper.

The interface flips the mass sign on entry to match the full-parity convention and flips
the solution sign on return. These are current compatibility workarounds, not user
tunables.

### A CA coarse solver's `maxiter` and basis size jointly select its execution mode

`coarse_solver_maxiter` and `coarse_solver_ca_basis_size` are not independent knobs. For a
coarse CA solver, QUDA sets `fixed_iteration` when
`param.sloppy_converge && n_krylov == param.maxiter && !param.compute_true_res`, where the
local `n_krylov` comes from the solver parameter field `Nkrylov`. The multigrid setup
already forces `sloppy_converge` true and `compute_true_res` false for **every** coarse
solver, so the condition reduces to **`Nkrylov == maxiter`** — and at level `l` the
multigrid setup assigns `Nkrylov` from the MILC key `coarse_solver_ca_basis_size` and
`maxiter` from `coarse_solver_maxiter`.

Under `fixed_iteration` the solver stops being a restarted convergent solver and becomes a
**fixed-degree polynomial preconditioner**: it computes no residual norm and applies no
stopping test. `b2` is forced to `1.0` and the stopping value to `0`, so the run prints

```text
iterated = 1.000000e+00 (requested = 0.000000e+00)
```

**That line is the mode's signature, and it is easily misread as a failed solve.** The mode
is also invisible in a parameter-file diff, because neither parameter looks unusual alone.

**A second, related trap in the MILC interface.** It clamps `ca_basis_size` to `maxiter`,
then selects a power basis at `<= 8` and a Chebyshev basis above it, with the Chebyshev
lower bound hard-coded to zero. A single parameter-file line therefore changes the basis
type, and a solver-name change alone can silently change it too. QUDA emits an
approximate-lambda-max line only on the Chebyshev branch, so the **absence** of that line
is how to confirm the power branch actually executed.

**Actionable consequence.** When configuring or diagnosing a CA coarse solver, record
`Nkrylov` and `maxiter` together and state which mode they select. Do not judge a terminal
that misses its requested tolerance as unhealthy before checking the mode.

## Memory model

MG residency combines several classes of device allocation:

- precise, sloppy/refinement, and preconditioner fat/long gauge fields;
- fine-level full spinors and the outer GCR basis and matrix images;
- near-null vectors and transfer fields on each generated level;
- coarse link fields whose storage grows with coarse color squared and coarse volume;
- smoother and coarse-solver workspaces at every active level;
- residual, correction, restriction, and prolongation temporaries;
- optional coarsest-level eigenvectors and eigensolver search space; and
- multi-source batches and communication/halo buffers.

Setup peak can exceed steady-state solve memory because null-vector generation,
orthogonalization, coarse construction, and optional eigensolver work coexist with the
partially built hierarchy. A model based only on fine-volume spinors or retained null
vectors will undercount that peak.

Memory depends on local geometry at every level, effective block sizes after QUDA's
validation/halving, `nvec`, coarse precision, compiled kernel shapes, GCR basis,
right-hand-side batch size, gauge representation, communication backend, and allocator
pool state. [`staggered-memory.md`](staggered-memory.md) separates source-exact object
sizes from the calibrated four-level Perlmutter A100 model, loudly warned two-/three-level
extrapolations, integrated geometry checks, and machine-scoped capacity advice.
The text gives only the operational caveat; detailed fit populations, errors, and
historical changes live in the companion calculator. Use the model only inside its
declared scope and measure setup and solve high-water on the target stack.

## Runtime confirmation and correctness

Confirm all of the following from output or returned state:

1. MILC reports `setting up the MG inverter` and `MG inverter setup complete` for a new
   hierarchy, or clearly reports reuse.
2. QUDA reports the configured level count, effective transfer block sizes, near-null
   generation/load, coarse construction, and any coarsest eigensolve.
3. An invalidation reports `Performing a full MG solver update` or `Performing a thin MG
   solver update` as intended.
4. The outer path identifies GCR with an MG preconditioner, and MILC timing identifies
   `fn_QUDA_MG` rather than the CG/UML fallback.
5. The parameter file, build cache, local lattice, rank/GPU geometry, effective
   aggregation blocks, `nvec`, precisions, source count, batch size, and rebuild choice
   are recorded.
6. Returned true residuals and MILC convergence state satisfy the request, followed by
   an application-level residual or solution comparison.

The observed multi-source wrapper reports the last source's residual fields and QUDA's
block iteration convention. Diagnose per-source failures from QUDA summaries rather
than assuming the returned scalar describes every right-hand side.

The `CG` MG-rebuild label in MILC is a bypass: it executes the UML fallback, not this MG
path and not necessarily the high-level `CG` algorithm. Confirm that no fallback warning
was printed.

## Limitations and version sensitivity

The following are exact-current limitations or workarounds in the observed interface:

- fixed full-system outer GCR rather than a selectable Schur solve;
- fixed single outer sloppy precision;
- broken nonzero initial-guess handling;
- mass and returned-solution sign flips for MILC/QUDA convention compatibility;
- a static hierarchy that does not notice a changed parameter-file path;
- terminal cleanup that destroys but does not null the static MILC pointer; and
- true-residual/iteration return values that summarize the last member of a
  multi-source call.

Recheck the interface, transfer validation, compiled `nvec` lists, and update semantics
when upgrading QUDA or MILC. This source-backed overview deliberately does not publish a
universal hierarchy, setup amortization threshold, timing crossover, or fitted memory
constant.
