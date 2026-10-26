---
title: MILC ks_imp_rhmc application guide
summary: Source-backed input, trajectory, acceptance, completion, and timing structure for MILC RHMC and RHMD generation, including the update record an RHMD build prints in place of ACCEPT/REJECT.
scope: [software:milc]
load_when: Compiling, preparing, tuning, benchmarking, or interpreting a ks_imp_rhmc run, from an su3_rhmc* or an su3_rhmd* target.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/Make_template#L162-L168
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/Make_template#L224-L240
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/update_rhmc.c#L305-L308
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/update_rhmc.c#L723-L742
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/setup.c#L108-L700
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/control.c#L27-L195
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/ks_imp_includes.h#L37-L43
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/test/su3_rhmc_hisq.1.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/test/su3_rhmc_hisq.1.sample-out
observed: "2026-10-09"
observed_on:
  software:
    milc:
      commit: ab5011f5722dd423c9c459dea312ad0b6d565f45
      branch: develop
---

# MILC `ks_imp_rhmc` application guide

`ks_imp_rhmc` generates gauge fields with rational hybrid Monte Carlo. Its repeated unit is a
trajectory, with measurements and gauge-field output at separately declared cadences. It must
not be costed or parsed as a spectroscopy or standalone-measurement application.

## Portable build recipe

The application directory is `ks_imp_rhmc`, and its upstream targets are defined in
`ks_imp_rhmc/Make_template`. `su3_rhmc` selects the generic Asqtad RHMC target, while
`su3_rhmc_hisq` selects the standard HISQ RHMC target; other targets change the action,
integrator, equation-of-state or susceptibility terms, or experimental force construction.
Both standard RHMC targets have an RHMD twin built from the same options without `-DHMC`:
`su3_rhmd` beside `su3_rhmc`, and `su3_rhmd_hisq` beside `su3_rhmc_hisq`. That define is the only
difference within each pair, and it decides whether a trajectory ends in a Metropolis test, as the
output section below describes.
Resolve the shared invocation in `../build.md` only after matching those compile-time choices
to the intended rational-function and trajectory contract.

The handbook does not yet contain a named `ks_imp_rhmc` build profile. Treat this source-backed
target map as routing knowledge and resolve or propose a named option profile before recording a
portable build or stack. Do not infer force, integrator, or accelerator options from a
spectroscopy profile.

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

### This application does NOT implement proofreading, and setting `prompt 2` runs the job

Some MILC applications act on `prompt 2` to parse an input and perform no physics. **This one
does not.** The shared input reader accepts the value `2` unconditionally, but without the
corresponding guard the application reads the input exactly as if `prompt 0` and then
**proceeds to run the real calculation**.

Do not set `prompt 2` here expecting a syntax check. `tools/milc-proofread-input.sh` carries
the list of applications that implement it and **refuses** this one rather than running it.
For an application without the mode, the cheap pre-submission check is a short job in a debug
class, not a proofread.

## Output and work-unit boundaries

The application performs the declared warmup trajectories, emits `WARMUPS COMPLETED`, then runs
the declared measured trajectories. Each trajectory can emit initial and final action records,
one update record carrying the action difference (below), plaquettes, solver records, and force/link
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

### An RHMD build never accepts or rejects

The update record depends on whether the target defines `HMC`. Every `su3_rhmc*` target does: the
starting links are copied before the molecular dynamics, restored on rejection, and the record is
`ACCEPT: delta S = …` or `REJECT: delta S = …`. The RHMD targets, `su3_rhmd*` and `su3_leapfrog`, do not:
no test is made, the evolved field is always kept, and the record is `CHECK: delta S = …`. An RHMD output
contains no `ACCEPT` or `REJECT` line at all.

- Count an RHMD output's trajectories by its `CHECK: delta S` records. `ACCEPT` plus `REJECT` is zero
  there.
- An RHMD `delta S` measures integration error and decides nothing. However large it is, the run keeps
  the field, saves it on schedule and continues from it. Whether a value is acceptable is the
  campaign's judgement against its step size and its own history; the application flags nothing.

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
- every measured trajectory has its action records and one update record: `ACCEPT` or `REJECT`
  from an `su3_rhmc*` target, `CHECK: delta S` from an RHMD target;
- solver, force, and link paths match the intended candidate and satisfy the numerical
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
