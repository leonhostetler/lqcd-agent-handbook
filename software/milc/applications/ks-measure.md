---
title: MILC ks_measure application guide
summary: Source-backed input, observable, completion, and timing structure for the MILC ks_measure family.
scope: [software:milc]
load_when: Compiling, preparing, tuning, benchmarking, or interpreting a ks_measure-family run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/setup.c#L59-L628
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/control.c#L39-L320
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/ks_measure_includes.h#L25-L31
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/test/ks_measure_hisq.2.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/test/ks_measure_hisq.2.sample-out
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/setup.c#L184-L200
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/setup.c#L205-L262
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/setup.c#L375-L460
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_measure/control.c#L82-L170
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L565-L665
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/f_meas_current.c#L1572-L1900
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/f_meas_current.c#L2030-L2060
observed: "2026-10-07"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
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
   condition. From `d17e9559` (PR #99, 2026-10-06) a QIO build reads two more directives after
   the APE smearing parameters: a fat-link file command (`fresh_fat`, `continue_fat`,
   `reload_serial_fat`, or `reload_parallel_fat`, the reload forms followed by a file name) and
   the `_long` equivalents; the reload forms overwrite the links just built from the gauge field;
2. optional eigenpair input, calculation, and output. From `d17e9559` a build with the
   accelerated eigensolver and either the accelerated CG or current path also reads
   `tol_restart`, and on reload `file_number_of_eigenpairs` and `eigensolver_prec`;
3. `number_of_sets` observable sets; and
4. for each observable set, repetition count, solver limits, precision, mass count, and the mass,
   Naik correction, absolute residual, and relative residual for every member. From `d17e9559`,
   when eigenpairs are requested, each set also reads `deflate yes|no`; before it every set
   deflated whenever eigenvectors existed.

Compile-time features can add current, susceptibility, chemical-potential, eigenvector, U(1), or
other controls. Use the current `setup.c` and executable's printed options to establish the
actual grammar. Count fields delimit repeated records; comments and sample-file layout do not.

When `WANT_SHIFT_GPU` or `WANT_SPIN_TASTE_GPU` is enabled, load
`../../quda/internals/milc-shift-interface.md` before treating current or spin-taste observables
as validated. These switches select separate interface paths with selector and resident-gauge
contracts beyond ordinary solver validation.

From `d17e9559`, a build with `WANT_CURRENT_GPU` computes the exact low-mode current through
`qudaExactCurrent` and projects the low modes out of stochastic sources through `qudaProject`,
both from a deflation space of both parities that the application loads at mass zero at
start-up; with the accelerated eigensolver as well, the host eigenvector arrays stay empty.
The same merge makes the five-mass current writers emit a separate strange-mass record in both
the low-mode and the high-mode output, so the expected record count changes across it. Each
input set reloads the space through QUDA, and QUDA restores a space it already holds without
checking that the links changed, so hold one gauge configuration per process. Measured at
`a5f8f9fa`: on the second gauge configuration of a process the exact current came out wrong by
orders of magnitude and a block of deflated stochastic solves diverged, while the run reported
`RUNNING COMPLETED` and exited 0; mechanism, measurement and the one-call remedy are in
[`../../quda/internals/milc-deflation-space.md`](../../quda/internals/milc-deflation-space.md).
The exact current also needs a QUDA built with `QUDA_DIRAC_COVDEV`, which the QUDA `milc-cg`
profile leaves off; against such a build it stops at run time, not at link time.

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
keyword's value. Count those positions in this application's own parameter
reader before assuming a comment is safe anywhere; the starting-lattice filename is one of
them in every application.

The tool also checks, before parsing, that every `node_geometry` extent is divisible by the
matching `ionode_geometry` extent — a layout rule the parse returns before reaching; see
the proofread section of [`ks-spectrum.md`](ks-spectrum.md).

**What it does not cover:** semantics. A wrong tadpole factor, a wrong `node_geometry`, a
gauge file that does not exist, an unsubstituted template placeholder, a wrong mass — none
are caught. It complements a launcher's assertions; it does not replace them.

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
separate masses or repetitions. From `d17e9559` the current paths add unconditional
`Time to ...` lines of their own: deflation-space loading, other-parity reconstruction, source
collection, the one-link dslash, and one measurement step per block of random sources.

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
