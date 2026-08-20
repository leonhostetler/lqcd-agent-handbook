---
title: MILC ks_measure application guide
summary: Source-backed input, observable, completion, and timing structure for the MILC ks_measure family.
scope: [software:milc]
load_when: Compiling, preparing, tuning, benchmarking, or interpreting a ks_measure-family run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/setup.c#L55-L651
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/control.c#L39-L321
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/ks_measure_includes.h#L25-L31
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/test/ks_measure_hisq.2.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/test/ks_measure_hisq.2.sample-out
observed: "2026-08-18"
observed_on:
  software:
    milc:
      commit: 32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839
      branch: develop
---

# MILC `ks_measure` application guide

`ks_measure` measures staggered-fermion observables on a gauge field. Its input and output are
not reduced forms of `ks_spectrum`; use this guide and `../timing.md` rather than applying a
spectroscopy parser.

## Portable build recipe

The application directory is `ks_measure`, and its upstream targets are defined in
`ks_measure/Make_template`. Basic action targets are `ks_measure_hisq` and
`ks_measure_asqtad`; distinct targets add eigCG, equation-of-state, susceptibility,
chemical-potential, disconnected-current, or U(1) paths. Resolve the shared invocation in
`../build.md` only after selecting the variant required by the input and observables.

The handbook does not yet contain a named `ks_measure` build profile. The source-backed target
map is therefore routing knowledge, not a claim that another application's option set is valid.
A reusable build must first resolve or propose a named profile for the requested target and
backend; do not borrow `ks-spectrum-hisq-quda` merely because both applications use HISQ.

## Input structure

The application reads a global preamble containing prompt mode, lattice dimensions, random seed,
job identifier, and any compiled geometry. It then loops over ordered input sets.

At the observed revision, an input set describes:

1. starting and ending gauge-field handling, smearing, coordinate origin, and temporal boundary
   condition;
2. optional eigenpair input, calculation, and output;
3. `number_of_sets` observable sets; and
4. for each observable set, repetition count, solver limits, precision, mass count, and the mass,
   Naik correction, absolute residual, and relative residual for every member.

Compile-time features can add current, susceptibility, chemical-potential, eigenvector, U(1), or
other controls. Use the current `setup.c` and executable's printed options to establish the
actual grammar. Count fields delimit repeated records; comments and sample-file layout do not.

When `WANT_SHIFT_GPU` or `WANT_SPIN_TASTE_GPU` is enabled, load
`../../quda/internals/milc-shift-interface.md` before treating current or spin-taste observables
as validated. These switches select separate interface paths with selector and resident-gauge
contracts beyond ordinary solver validation.

## Output and work-unit boundaries

Each successful input set emits observable records such as `PBP` and `FACTION`, followed by
`RUNNING COMPLETED`, a top-level `Time = ... seconds`, and `total_iters`. Enabled features can
emit additional observable and eigenpair sections.

At the observed revision, the top-level interval starts immediately before `readin()` for each
input set. It excludes global setup but includes parameter input, the requested calculations,
and an ending-lattice save performed by the application before the completion marker. This
boundary differs from both `ks_spectrum` and `ks_imp_rhmc`; cleanup after the completion record
is outside this application interval.

With `PRTIME`, this application uses `Time to ...` rather than `Aggregate time to ...` for its
phase records. Source-backed phases include setup, input, eigenpairs, the combined observable
calculation, lattice output, and optional eigenvector work. `CGTIME` and backend records are
needed when solve-level attribution is required; the combined observable phase alone does not
separate masses or repetitions.

## Tuning and benchmarking interpretation

Define the production unit from the input contract: commonly one observable workload on one
gauge configuration, but possibly multiple input sets, charges, mass sets, repetitions, or
enabled observable families. Record all of those dimensions before comparing runs.

For component measurements, group solve records by executed backend, precision, mass set,
residual contract, repetition, source/noise construction, and any enabled low-mode or current
path. For workflow costing, retain gauge-field I/O, eigenpair work, observable calculation,
ending-lattice output, application total, and scheduler total as distinct layers.

Do not infer output completeness from `RUNNING COMPLETED` alone. Check that each declared
observable set produced the expected records for every mass and repetition, that numerical
checks passed, and that any required files were written.

## Completion checks

A measurement block is acceptable benchmark evidence only when:

- the intended gauge field and all declared measurement sets were read;
- the expected observable cardinality is present;
- required solves converged under the frozen residual contract;
- optional eigenpair/current/chemical-potential paths requested by the input are present;
- required ending-lattice or observable files exist; and
- both application and scheduler exit states are successful.

## Coverage

This is a source- and upstream-sample-backed structural guide. It has not yet been confirmed
against a representative production-shaped `ks_measure` tuning or benchmark corpus. Before
publishing a production cost model, inspect a complete timing-enabled run, its scheduler output,
and a failed or truncated case; then confirm the recurrence and aggregation semantics of every
timer used.
