---
title: MILC ks_imp_rhmc application guide
summary: Source-backed input, trajectory, acceptance, completion, and timing structure for MILC RHMC generation.
scope: [software:milc]
load_when: Preparing or interpreting a ks_imp_rhmc input, trajectory output, tuning run, or benchmark.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/setup.c#L108-L700
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/control.c#L27-L195
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/ks_imp_includes.h#L37-L43
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/test/su3_rhmc_hisq.1.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/test/su3_rhmc_hisq.1.sample-out
observed: "2026-08-18"
observed_on:
  software:
    milc:
      commit: 32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839
      branch: develop
---

# MILC `ks_imp_rhmc` application guide

`ks_imp_rhmc` generates gauge fields with rational hybrid Monte Carlo. Its repeated unit is a
trajectory, with measurements and gauge-field output at separately declared cadences. It must
not be costed or parsed as a spectroscopy or standalone-measurement application.

## Input structure

At the observed revision, the initial section establishes prompt mode, lattice dimensions,
random seed, pseudofermion count, rational-function parameter file, gauge coupling, dynamical
masses and flavors, and tadpole factor.

Each subsequent input set supplies the trajectory and I/O contract, including:

1. warmup-trajectory count, measured-trajectory count, and trajectories between measurements;
2. molecular-dynamics step size, steps per trajectory, and the compiled integrator's controls;
3. solver residuals, iteration limits, and precisions for molecular-dynamics, action, and
   pseudofermion-generation roles;
4. fermion-force precision and optional measurement masses and repetitions; and
5. starting and ending gauge-field instructions.

The rational-function file is part of the executable input contract even though it is external
to the main input stream. Preserve it with the benchmark input and executable identity.
Compile-time action, integrator, force, backend, and diagnostic choices can change both accepted
fields and output.

The input keyword `warms` counts RHMC warmup trajectories. It is not the accelerator warm state,
kernel autotuning, or the generic first-occurrence exclusion used in component benchmarking.
Record those concepts separately.

## Output and work-unit boundaries

The application performs the declared warmup trajectories, emits `WARMUPS COMPLETED`, then runs
the declared measured trajectories. Each trajectory can emit initial and final action records,
`ACCEPT` or `REJECT` with an action difference, plaquettes, solver records, and force/link
diagnostics. Gauge and fermionic measurements occur at the declared trajectory interval.

One successful input set emits `RUNNING COMPLETED`, an average-CG-iteration summary when
measurements occurred, a top-level `Time = ... seconds`, and `total_iters`. Acceptance and
rejection are valid algorithm outcomes; `REJECT` alone is not an application failure.

At the observed revision, the first top-level interval begins before global setup. The
application prints `Time` and resets its clock before performing the requested ending-lattice
save. Consequently, the first total excludes its own ending-lattice save, and a later input-set
total can include the preceding set's save before its own `readin()` and trajectories. Do not
treat top-level `Time` as a self-contained per-input-set production cost. Use scheduler elapsed
time and explicit I/O timing to close the ledger.

With `PRTIME`, application phases use `Aggregate time to ...` records for setup, individual
trajectories, gauge measurements, and chiral-condensate measurements. Component macros add
solve, fermion-force, fermion-link, gauge-force, remapping, and I/O records as supported by the
compiled paths. Parent trajectory times overlap their component timers.

## Tuning and benchmarking interpretation

Choose and state the normalization unit explicitly:

- one molecular-dynamics trajectory;
- one measured trajectory including its scheduled observables;
- one input set with warmups and measured trajectories; or
- one saved gauge configuration including the declared save cadence.

For a production-cost estimate, separate setup, RHMC warmup trajectories, measured trajectories,
periodic measurements, acceptance diagnostics, and gauge-field I/O. Weight trajectory and
measurement costs by their declared cadence. Scheduler elapsed time and node- or GPU-hours are
the authoritative resource-cost layer.

For component tuning, classify solver and force calls by their algorithmic role as well as
backend, precision, residual, rational term, and decomposition. A fast force or solve is not by
itself a faster or valid trajectory; preserve action-difference, reversibility or other declared
correctness checks, and acceptance behavior appropriate to the study.

Do not discard the first trajectory merely because it is first. Decide separately whether the
target includes global setup, accelerator autotuning, the input's RHMC warmup trajectories, and
steady measured trajectories. These costs have different recurrence and scientific meanings.

## Completion checks

An input set is acceptable benchmark evidence only when:

- the expected warmup and measured trajectory counts are present;
- every measured trajectory has the required action and `ACCEPT`/`REJECT` records;
- solver, force, and link paths match the intended candidate setup and satisfy the numerical
  contract;
- all measurements required by the cadence are present;
- the requested ending gauge field is successfully written and validated separately from the
  earlier `RUNNING COMPLETED` marker; and
- both application and scheduler exit states are successful.

## Coverage

This is a source- and upstream-sample-backed structural guide. It has not yet been confirmed
against a representative production-shaped `ks_imp_rhmc` tuning or benchmark corpus. Such a
corpus is needed before fixing a production timing model, expected timer cardinalities, or a
default trajectory repetition protocol.
