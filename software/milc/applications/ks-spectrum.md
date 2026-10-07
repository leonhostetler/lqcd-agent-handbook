---
title: MILC ks_spectrum application guide
summary: Input-set structure, output boundaries, artifact validation, timing records, and benchmark checks for the MILC ks_spectrum family.
scope: [software:milc]
load_when: Compiling, preparing, tuning, benchmarking, or interpreting a ks_spectrum-family run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L78-L259
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L993-L1389
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/control.c#L76-L1132
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/make_prop.c#L286-L333
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/spectrum_ks.c#L644-L1252
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/spectrum_ks.c#L1357-L1662
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_multicg.c#L760-L823
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/mat_invert.c#L222-L529
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/layout_hyper_prime.c#L278-L314
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L664-L705
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/ks_spectrum_includes.h#L33-L40
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/test/ks_spectrum_hisq.fpi.2.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/test/ks_spectrum_hisq.fpi.2.sample-out
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L121-L126
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L843-L853
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/control.c#L131-L134
  - https://github.com/milc-qcd/milc_qcd/commit/45e0ec0e
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_action_paths_hisq.c#L106-L114
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/imp_actions/hisq/hisq_u3_action.h
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/d_congrad5_fn_quda.c#L130-L134
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/eigen_stuff_QUDA.c#L407-L442
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L1062-L1074
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_meson_mom.c#L290-L356
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_baryon.c#L219-L245
  - operator's campaign records (the pre-2024 gauge-fixing comparison)
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/spectrum_ks.c#L1216-L1247
  - https://github.com/milc-qcd/milc_qcd/commit/08b263db
  - https://github.com/milc-qcd/milc_qcd/commit/6bd16fce292a3bda9d65b426b3d263ee184d3a9a
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L748-L826
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/control.c#L280-L385
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/lattice.h#L143-L148
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/eigen_stuff_QUDA.c#L112-L255
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/d_congrad5_fn_quda.c#L136-L220
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_meson_mom_quda.c#L337-L385
  - operator's rank-count comparison (the baryon normalization)
observed: "2026-10-07"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
---

# MILC `ks_spectrum` application guide

This guide covers the `ks_spectrum` application family, including the HISQ executable variant
used by the handbook's current MILC build profile. It describes application semantics, not a
particular physics workflow. Build capabilities remain canonical in `../build-profiles.yaml`,
and shared instrumentation policy lives in `../timing.md`.

## Portable build recipe

The application directory is `ks_spectrum`, and its upstream targets are defined in
`ks_spectrum/Make_template`. The current named profile `ks-spectrum-hisq-quda` maps to target and
executable `ks_spectrum_hisq`. Resolve the shared invocation in `../build.md` with:

```text
MILC_APPLICATION_DIR=ks_spectrum
MILC_MAKE_TARGET=ks_spectrum_hisq
MILC_BUILT_EXECUTABLE=ks_spectrum_hisq
profile=ks-spectrum-hisq-quda
```

Other upstream targets select Asqtad, naive, eigCG, equation-of-state, chemical-potential, U(1),
or specialized baryon variants. Select such a target from the physics and observable request,
then require a named profile that supplies its exact options before treating the recipe as
portable. Do not infer those options from the HISQ/QUDA profile merely because the application
directory is shared.

## Input structure

The application reads one global preamble and then loops over input sets until input ends.

The preamble establishes prompt mode, lattice dimensions, random seed, job identifier, and any
compiled fixed node or I/O geometry. Each subsequent input set is ordered. At the observed
revision its major sections are:

1. starting and ending gauge-field handling, tadpole factor, gauge fixing, smearing controls,
   coordinate origin, and temporal boundary condition.
   The reload keyword in this section is a correctness choice, not a performance one: only
   two of the three detect a SciDAC/LIME gauge configuration, and the third reads it as MILC binary
   while the log reports the format correctly identified. See
   [`../internals/gauge-read-dispatch.md`](../internals/gauge-read-dispatch.md);
2. optional eigenpair and chiral-condensate measurements;
3. base sources and modified sources;
4. propagator sets, each with a set type, inverter controls, source reference, and one or more
   propagator definitions. In a multigrid build, which set types take a `rebuild_type` line,
   and where, changed at merge `db6adc7d` (2026-10-06): from there a `single` set with the `MG`
   inverter reads one per propagator, as `multimass` sets always did, and an older input
   without it fails to parse. [`../internals/staggered-inverter-types.md`](../internals/staggered-inverter-types.md)
   owns the rule and the echo line that confirms the choice in effect;
5. derived quarks and sink operators; and
6. meson pairs, baryon triplets, and build-dependent extended baryon requests.

Fields such as `number_of_base_sources`, `number_of_modified_sources`, `number_of_sets`,
`number_of_propagators`, `number_of_quarks`, `number_of_mesons`, and `number_of_baryons` delimit
the records that follow them. Parse those counts and references rather than comments, blank
lines, or assumptions about one familiar input generator.

A propagator set is an execution unit, not necessarily one solve. `set_type`, source parity and
color structure, mass count, and backend dispatch can turn one set into single, multimass,
multi-source, or batched solve calls. Derive the expected runtime calls from both the input and
the emitted solver records.

**Solver-dispatch heads-up:** at the observed revision, `set_type multimass` enters
`mat_invert_multi`, but that routine performs separate single-mass inversions when the set has
at most two masses or the run has a nonzero eigenvector count. `set_type multicolorsource`
instead enters a block inversion over all source colors. Confirm the executed path from the
emitted solver records, including mass and right-hand-side cardinality; the requested set type
alone is not sufficient evidence.

### Fields that parse cleanly and then do something else

Each of these is accepted by the parser, so a proofread passes, and each either has no effect or
an effect the input does not suggest. All are source facts at the observed revision unless
labelled otherwise.

- **`iseed` is a signed 32-bit integer, with no range check.** `setup.c` reads it with `get_i`,
  which parses `%d` into an `int`, and stores the result in an unsigned 32-bit field. A larger
  value is accepted and silently truncated — observed on glibc as the low 32 bits — so the seed
  that runs is not the one written, and seeds that differ only above bit 31 collide. Keep seeds
  at or below 2147483647, which a generator that concatenates a prefix with a gauge
  configuration number easily exceeds, and check the `iseed` the output echoes.
- **`coulomb_gauge_fix` on an input set that starts with `continue` is a no-op.** `control.c`
  gauge-fixes only when the set's start flag is not `continue`, so the field keeps the fixing
  done by the set that reloaded it. That condition arrived in upstream `45e0ec0e` (2024-08-13).
  Before it, every such set ran gauge fixing again on the already fixed field, which typically
  stops after one more over-relaxation step and still moves the field slightly. Output from
  older code therefore matches current output for the first set and differs for wall and
  corner sources in later sets of the same input, by an amount that grows set by set — observed
  once against archived pre-2024 output. An input meant to run under both
  should say `no_gauge_fix` on its `continue` sets.
- **The tadpole factor `u0` does not reach a HISQ solve on the QUDA path.** HISQ path
  coefficients are divided by `u0` only under `TADPOLE_IMPROVE`
  (`generic_ks/ks_action_paths_hisq.c`), which `hisq/hisq_u3_action.h`, the action header the
  `ks_spectrum_hisq` target builds with, does not define. The QUDA CG, multi-shift and Dslash
  calls pass `tadpole = 1.0` for HISQ (`generic_ks/d_congrad5_fn_quda.c`,
  `ks_multicg_offset_quda.c`, `dslash_fn.c`), and QUDA derives the long-link scale from that
  value. A wrong `u0` is therefore inert for HISQ spectroscopy on this path. **One unguarded
  exception:** `ks_eigensolve_QUDA` (`generic_ks/eigen_stuff_QUDA.c`) sets the tadpole
  coefficient, and the long-link scale from it, to `u0` with no HISQ condition. Through
  `6b9b8a06` a QUDA-deflation build reached it; from `d17e9559` that build loads the space
  through `load_evecs_quda`, which passes `1.0` for HISQ, and the exception remains only for a
  build with `USE_EIG_GPU` and neither `USE_CG_GPU` nor `USE_CURRENT_GPU`. Whether it
  mis-scales the long links when `u0 ≠ 1` has not been run.
- **From `d17e9559`, one gauge configuration per process when eigenvectors are QUDA-resident.**
  Each input set reloads or recomputes the deflation space through QUDA, and QUDA restores the
  space it already holds without checking that the links changed, so a later input set deflates
  with the earlier gauge configuration's eigenvectors. Mechanism and remedy are in
  [`../../quda/internals/milc-deflation-space.md`](../../quda/internals/milc-deflation-space.md).
  Read from source, not run.
- **At `a5f8f9fa` a single-precision build with host eigenvectors is type-mismatched.**
  `lattice.h` declares `eigVal` as `double *` and `eigVec` as double-precision vectors, while
  the eigensolver and residual-check routines take `Real *` and `su3_vector **`, which at
  `PRECISION=1` are single. GCC 14 and later reject the call; older compilers warn and then
  misread the eigenvalues. The profiles here build `PRECISION=2`, where the types coincide.
  Read from source, not compiled.
- **Meson correlator normalization factors are echoed with `%g`.** The log shows six significant
  digits while the run uses the full value, so an input reconstructed from a log is not the
  input that ran. Take numeric values from the input file.
- **A meson pair and its reverse are not independent.** The first propagator of a pair becomes
  the antiquark (`generic_ks/ks_meson_mom.c`). For a local spin-taste sink, which multiplies by a
  real site sign, the site value is `su3_dot` of the signed first propagator with the second, so
  reversing the pair conjugates it site by site. At zero momentum the reversed correlator is
  therefore the complex conjugate; at nonzero momentum it is the conjugate at the opposite
  momentum (inferred from the Fourier phase). For these sinks, pairs with the first index at or
  below the second are complete. The point-split vector sinks apply operators to both
  propagators and are not covered.
- **A baryon triplet's order changes the value on each gauge configuration.** `ks_nucleon_nd`
  (`generic_ks/ks_baryon.c`) builds row r of the color matrix from quark r's propagator from
  source color r and sums its determinant over corner sites, so reordering a mixed-mass triplet
  changes which mass carries which source color. Each ordering is a separate estimator. That the
  orderings share an ensemble average, through a global color rotation of the source time
  slice, is an inference that has not been tested. One ordering per mass set gives one
  estimator and all orderings give more at contraction cost only; which is wanted is an analysis
  decision.

Input generators commonly rotate source times as `t0 = (k·n mod s) + j·s` over a gauge
configuration index `n`. That visits every offset only when `gcd(k, s) = 1`: with `k = 9` and
`s = 18`, only offsets 0 and 9 ever occur. Check the gcd, and make `n` an exact non-negative
integer for every gauge configuration run, since a negative `n` gives a negative remainder in C
and in shell arithmetic.

### Proofread the input before submitting, not at run time

This application acts on `prompt 2`, which MILC's own source calls **proofreading**: it
parses the complete input set and performs no physics. `setup()` returns before
`setup_layout()`, so no lattice is allocated, no gauge file is opened — the starting-lattice
reader takes the filename as a string and never touches it — and no accelerator is
initialised. One rank is enough; the input's `node_geometry` is read but never acted on.

Run it with `tools/milc-proofread-input.sh`, **when the input and batch script are written**.
Running it inside the job saves nothing: this application already parses its whole input
before computing, so a bad input fails the run seconds in, after the queue wait and the
submission have been spent.

**Judge by the log, never by the exit code.** On an input error MILC sets a stop flag, the
work loop is never entered, and it reaches `normal_exit(0)` — a rejected input and a clean
run both exit `0`. A clean proofread ends with `EOF on input`, which is the parser reaching
the end of the file; require that positively rather than only checking for errors.

Errors are printed in several shapes and **inconsistent case** — a lowercase
`error in input:` from the application's own setup, an uppercase `ERROR IN INPUT:` and a
trailing `INPUT ERROR.` from the shared reader. Matching only one shape misses the others.

**What it covers:** the whole input grammar — keyword order, malformed or missing fields,
unknown keyword values, and every position where a comment is illegal. MILC strips `#`
comments in exactly one reader, `get_next_tag`; keywords read by a bare `scanf` do not
tolerate a preceding comment line, and a comment placed above one is consumed **as** that
keyword's value. There are ten such positions in `ks_spectrum`'s parameter reader alone,
plus the starting-lattice filename.

**One layout rule is checked statically, because the parse returns before it.** Every
`node_geometry` extent must be divisible by the matching `ionode_geometry` extent;
otherwise MILC terminates every rank in layout initialisation with `ionode geometry ... is
incommensurate with node geometry ...` (`generic/layout_hyper_prime.c` `init_io_node`, the
same test in the other layouts) — after a proofread of the same input has passed. The
likely way to break it is a placement change: it forces `node_geometry` to be edited and
leaves an inherited `ionode_geometry` looking plausible. `tools/milc-proofread-input.sh`
compares the two lines before parsing, fails a non-dividing extent, and reports lines that
divide but differ. **Set `ionode_geometry` equal to `node_geometry`** unless a coarser I/O
partition is intended: equality is always legal, and a launcher guard on placement must
read both lines.

**What it does not cover:** semantics. A wrong tadpole factor, a wrong `node_geometry`, a
gauge file that does not exist, an unsubstituted template placeholder, a wrong mass — none
are caught. It complements a launcher's assertions; it does not replace them.

## Output and work-unit boundaries

One normally exiting process emits one `start: <date/time>` and `exit: <date/time>` pair
around the application run. Their difference is a whole-application wall-clock cross-check; it
is not scheduler allocation time and the `exit:` marker precedes final MPI finalization. See
`../timing.md` for its relationship to the application and component clocks.

One successful pass through `readin()` emits one `RUNNING COMPLETED` marker followed by a
top-level `Time = ... seconds` record and `total_iters`. A file may contain many such blocks.
One block is an **input set**, not automatically one gauge configuration: a workflow may split
different sources or source times for the same gauge configuration across several input sets.

At the observed revision, the first top-level interval begins before global `setup()`. Later
intervals begin at the preceding input set's reported end and can include cleanup performed after
that preceding `Time` record. The first and later `Time` records therefore do not have identical
setup or ownership scope. Treat scheduler elapsed time as the allocation-cost clock and record
how input sets compose the declared production work unit.

With `PRTIME`, application phases use `Aggregate time to ...` records. Common phases include
parameter and gauge-field input, gauge fixing, fermion links, eigenpairs, measurements, source
construction, propagators, sink operators, and correlator construction. Optional code paths add
or omit phases, so absence is not evidence of zero cost.

With the corresponding component instrumentation:

- `CONGRAD5` records identify the executed inverter family and report implementation-dependent
  time, iteration, mass, right-hand-side, precision, and throughput fields;
- backend convergence and true-residual records establish whether the requested numerical path
  completed;
- meson, baryon, smearing, link, and I/O timers provide child costs inside application phases;
  and
- backend tuning and memory records describe accelerator state, not `ks_spectrum` work units.

From `d17e9559` a QUDA-accelerated build also emits, read from source: `srcs = <n>` on every
`CONGRAD5` line from the QUDA CG path, including single-source solves, because that entry now
wraps the multi-source one; `Loading deflation spaces into QUDA`, `Time to load deflation
space = ...`, and one `Solving for <n> source(s) with|without deflation for parity <p>` line per
solve when eigenpairs are requested; QIO debug-level output during the eigenvector load, which
the application switches on just before it and the next MILC SciDAC call switches off; and, in
a `WANT_KS_CONT_GPU` build, several lines from every rank around each contraction call. Saved
eigenvector files from that revision are written at `eigensolver_prec` (single unless it is 2),
not at the build precision.

Do not add `Aggregate time to compute propagators` to its constituent `CONGRAD5` times. Use the
parent for workflow accounting and the child records for solver attribution, then report any
compatible residual against the top-level or scheduler clock.

## Aligning application phases with a GPU profile

The phase structure above lives in **application output, not in the trace**. A profiler records
launches, transfers and durations; it does not record that a given interval was gauge fixing or
propagator construction. So a profiled `ks_spectrum` run carries its phase names in stdout and
its phase *costs* in the profile, and the two have to be joined before either is interpreted.

Joining them needs a shared time base, and whether one exists is a property of the capture
format rather than of this application — see
[`conventions/profile-capture.md`](../../../conventions/profile-capture.md), which is canonical
for it. Where the format records a wall-clock origin, place the `Aggregate time to ...` records
on the trace timeline directly. Where it does not, the anchor has to have been written by the
capture itself; failing that, align **structurally** — by the order of the phases listed above
and their relative durations — and say that the alignment is structural, because a structural
match to a repeating sequence is weaker evidence than a timestamp.

Two cautions specific to this application:

- **Inferred phases and application phases are different objects.** A profile-side segmentation
  derives boundaries from kernel activity; it will happily split one `Aggregate time to ...`
  interval across several segments, or merge two. Report them as two alignments, never as one
  phase list.
- **Check which level any annotation sits at before treating it as a phase boundary.** Marker
  ranges in a profiled run may come from the solver library rather than from the application,
  in which case they name internal operations and not physics stages. Annotation depth is a
  build-time property; establish it for the build in hand rather than assuming the ranges mark
  the stages named above.

## Artifact prediction and exact validation

Derive the expected artifacts from the final generated input submitted to `ks_spectrum`, not
only from the input generator or a previous run. Walk every input set using its count fields,
record every active output directive, and resolve relative destinations against the captured
application working directory. For the single-file correlator output described below, the
expected file set is the set of unique resolved destinations; the manifest must separately
retain every contribution expected within each destination.

For meson, baryon, and build-enabled extended-baryon correlators:

- `forget_corr` requests inline correlator records delimited by `STARTPROP` and `ENDPROP`; it does
  not declare an external correlator-file artifact;
- `save_corr_fnal <path>` declares an external FNAL-format correlator destination; and
- several pairs, triplets, input sets, or correlator requests may name the same destination, so
  neither the save-directive count nor `number_of_correlators` is the external file count.

Within a meson pair, repeated input lines with the same correlator-label/momentum-label pair are
combined into one reported correlator. Predict the persisted record multiset with that grouping
rule rather than treating every input line as a distinct record. Baryon and optional extended-
baryon sections have their own count fields and record identities; do not reuse the meson rule
without checking the enabled application path.

At the observed revision, external FNAL meson, baryon, and build-enabled extended-baryon writers
open their destinations in append mode. Each reported correlator contains delimited metadata, a
correlator identity, and `nt` indexed real/imaginary samples. Therefore:

1. create a new run-owned correlator root, or verify before launch that every planned target is
   absent;
2. compare the unique resolved target paths with the observed files in both directions;
3. parse every expected file and verify the frozen input `JobID`, lattice dimensions, expected
   correlator identities and multiplicities, complete time-index coverage, and finite numeric
   fields; and
4. reject stale appended records, missing records, and unexpected records even when the file
   count is correct.

Do not use nonzero values as a structural criterion: symmetry channels or individual components
may legitimately vanish. Structural validation establishes that the requested records were
written; numerical comparison and scientific approval remain separate checks.

If an external FNAL file cannot be opened, the observed implementation prints an error, switches
that correlator path to the inline `forget_corr` behavior, and can continue. A normal `exit:`, a
`RUNNING COMPLETED` marker, or the presence of inline correlators therefore does not prove that a
requested external artifact was created. Require the requested output route, absence of writer
errors, and the exact manifest checks above.

`tools/milc-compare-fnal-correlators.py` executes the file checks of step 3 and the duplicate
check of step 4 for FNAL correlator files, and compares several files record by record against
the first, relative to each correlator's own scale. Use it rather than reading the files by eye:
a stale appended record or a short time range looks complete. It does not know the expected
correlator identities, so compare its reported key set with the input's requests, and it
reports numerical differences without judging them unless given `--max-relative-difference`.
Files from different runs carry different `JobID`s — a tested run against its reference
always does — so give `--job-id` one value per file, in file order, rather than editing the
files to agree.

**Baryon amplitudes scale with the rank count before `6bd16fc`.** Up to that commit,
`spectrum_ks_print_baryon` sums each `NUCLEON` and `DELTA` correlator over ranks twice — once
as a vector, then again per time slice — so the printed and FNAL-written values are the MPI rank
count times the true sum. The factor is exact, so effective masses are unaffected, but
amplitudes from runs with different rank counts disagree. Mesons and the `GB_BARYON` path reduce
once and are unaffected. The second sum arrived with merge `08b263db` (2023-08-23); it is present
at the observed revision and at `6b9b8a0`, the tested commit of the validated `ks_spectrum`
stacks, and `6bd16fc` removes it; that commit reached `develop` as PR #101 (merge `bcab3de7`,
2026-10-06), so every `develop` checkout from there on is free of it. For a build without that
commit, divide the
baryon correlators by the run's rank count, or confirm with a one-rank and a two-rank run of the
same input: the baryon ratio is exactly 2 and the mesons agree. Reproduced at one, two and four
ranks on one input.

Apply the same manifest discipline to any other active `ks_spectrum` save directives, including
saved gauge fields, eigenvectors, sources, propagators, or derived quarks. Their format-specific
structure is outside this correlator section and must be validated with the corresponding MILC
I/O semantics rather than inferred from the FNAL correlator format.

## Tuning and benchmarking interpretation

For a solver or component comparison, classify occurrences by the executed backend and solver,
precision, set type, masses, right-hand-side shape, source parity/color structure, tolerance,
and decomposition. A later occurrence can be the first use of a new kernel family even when it
is not literally the first solve in the file. Exclude or include first-use cost according to the
declared warm-state contract in benchmarking mode.

**Solver-work heads-up:** treat single-right-hand-side and block or multi-right-hand-side paths
as different warm-state classes unless runtime and tunecache evidence establishes otherwise. At
the observed revision, CGZ solves the even and odd parity systems independently from zero initial
guesses, while UML solves the even system, reconstructs the odd solution, and then polishes it.
Solver-call count is therefore not a comparable work metric by itself; compare elapsed time,
total iterations, convergence, and correctness evidence.

For workflow-cost estimation:

- define how many input sets constitute one gauge-configuration workload;
- freeze and verify the exact expected source, propagator, quark, correlator-record, and output-
  file sets from the final generated input;
- separate gauge-field I/O, setup, solves, sink operations, contractions, and output;
- normalize elapsed time and resource cost by the declared production unit rather than by the
  number of `RUNNING COMPLETED` markers; and
- retain scheduler elapsed time, because application timers need not cover process launch,
  backend initialization/finalization, monitoring, or all output activity.

If gauge-field loading is a non-negligible fraction of the production-shaped workflow, treat the
gauge reload method, file format, and storage path as candidate tuning dimensions and measure the
gauge-load phase separately.

Requested input labels are not runtime evidence. Confirm the emitted solver/backend token,
batch or mass cardinality, precision, iterations, convergence, and residuals. At the observed
MILC revision, `total_iters` is not an acceptance signal for the current `ks_spectrum_hisq` QUDA
path: `solve_ksprop` initializes that local counter to zero and returns it without incrementing
it, while QUDA reports the actual iterations for each solve. Judge that path by its QUDA
convergence and true-residual records, and record wrapper and payload exit states separately.

## Completion checks

Accept an output block for performance analysis only when:

- its input was parsed without error and the intended gauge field was loaded;
- the expected `RUNNING COMPLETED` count is present;
- all required solves report convergence under the frozen correctness contract;
- executed solver, batching, precision, and backend records match the intended candidate;
- the requested output route was used, no artifact-writer error occurred, and the exact expected
  artifact paths and internal records pass structural validation with no unresolved missing or
  unexpected entries; and
- a normal `exit:` marker is present and the application and scheduler exit states are
  successful.

A truncated output, missing artifact, nonconverged solve, or automatically substituted runtime
path remains useful debugging or tuning evidence, but it is not a valid confirmatory benchmark.

## Coverage

The detailed operational interpretation is strongest for timing-enabled HISQ spectroscopy with
QUDA-accelerated staggered solves and source/propagator/correlator workflows. It does not imply
the same input grammar, timing boundaries, or production work unit for `ks_measure`,
`ks_imp_rhmc`, every compile-time `ks_spectrum` feature, or a different MILC revision. Reconcile
the guide with the current source and build profile before constructing an automated parser.
