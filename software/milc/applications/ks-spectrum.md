---
title: MILC ks_spectrum application guide
summary: Input-set structure, output boundaries, artifact validation, timing records, and benchmark checks for the MILC ks_spectrum family.
scope: [software:milc]
load_when: Preparing, tuning, benchmarking, or interpreting a ks_spectrum-family run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/setup.c#L78-L260
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/setup.c#L994-L1390
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/control.c#L76-L1200
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/make_prop.c#L286-L333
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/spectrum_ks.c#L644-L1255
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/spectrum_ks.c#L1360-L1665
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/generic_ks/ks_multicg.c#L760-L823
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/generic_ks/mat_invert.c#L207-L514
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/generic/io_helpers.c#L664-L705
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/ks_spectrum_includes.h#L33-L40
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/test/ks_spectrum_hisq.fpi.2.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/test/ks_spectrum_hisq.fpi.2.sample-out
observed: "2026-08-18"
observed_on:
  software:
    milc:
      commit: 32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839
      branch: develop
---

# MILC `ks_spectrum` application guide

This guide covers the `ks_spectrum` application family, including the HISQ executable variant
used by the handbook's current MILC build profile. It describes application semantics, not a
particular physics workflow. Build capabilities remain canonical in `../build-profiles.yaml`,
and shared instrumentation policy lives in `../timing.md`.

## Input structure

The application reads one global preamble and then loops over input sets until input ends.

The preamble establishes prompt mode, lattice dimensions, random seed, job identifier, and any
compiled fixed node or I/O geometry. Each subsequent input set is ordered. At the observed
revision its major sections are:

1. starting and ending gauge-field handling, tadpole factor, gauge fixing, smearing controls,
   coordinate origin, and temporal boundary condition;
2. optional eigenpair and chiral-condensate measurements;
3. base sources and modified sources;
4. propagator sets, each with a set type, inverter controls, source reference, and one or more
   propagator definitions;
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

Do not add `Aggregate time to compute propagators` to its constituent `CONGRAD5` times. Use the
parent for workflow accounting and the child records for solver attribution, then report any
compatible residual against the top-level or scheduler clock.

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
batch or mass cardinality, precision, iterations, convergence, and residuals. In particular,
`total_iters` is not a universal acceptance signal: the QUDA application path documented in
`../build.md` can complete valid solves while leaving that application-local counter at zero.

## Completion checks

Accept an output block for performance analysis only when:

- its input was parsed without error and the intended gauge field was loaded;
- the expected `RUNNING COMPLETED` count is present;
- all required solves report convergence under the frozen correctness contract;
- executed solver, batching, precision, and backend records match the intended candidate setup;
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
