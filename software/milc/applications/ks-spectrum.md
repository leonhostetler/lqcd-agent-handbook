---
title: MILC ks_spectrum application guide
summary: Input-set structure, output boundaries, timing records, and benchmark checks for the MILC ks_spectrum family.
scope: [software:milc]
load_when: Preparing, tuning, benchmarking, or interpreting a ks_spectrum-family run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/setup.c#L78-L260
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/control.c#L76-L1200
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

## Tuning and benchmarking interpretation

For a solver or component comparison, classify occurrences by the executed backend and solver,
precision, set type, masses, right-hand-side shape, source parity/color structure, tolerance,
and decomposition. A later occurrence can be the first use of a new kernel family even when it
is not literally the first solve in the file. Exclude or include first-use cost according to the
declared warm-state contract in benchmarking mode.

For workflow-cost estimation:

- define how many input sets constitute one gauge-configuration workload;
- verify expected source, propagator, quark, correlator, and output-file cardinalities;
- separate gauge-field I/O, setup, solves, sink operations, contractions, and output;
- normalize elapsed time and resource cost by the declared production unit rather than by the
  number of `RUNNING COMPLETED` markers; and
- retain scheduler elapsed time, because application timers need not cover process launch,
  backend initialization/finalization, monitoring, or all output activity.

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
- every required correlator or other output artifact exists with the expected structure; and
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
