---
title: MILC wilson_flow application guide
summary: Input-set structure, flow observables, backend limits, timing boundaries, and completion checks for MILC wilson_flow.
scope: [software:milc]
load_when: Preparing, tuning, benchmarking, or interpreting a MILC wilson_flow run.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/setup.c#L48-L203
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/control.c#L25-L79
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/integrate.c#L6-L129
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/integrate.c#L454-L833
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/staple.c#L207-L284
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/Make_template#L110-L205
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/test/wilson_flow_bbb.symanzik.2.sample-in
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/wilson_flow/test/wilson_flow_bbb.symanzik.2.sample-out
  - https://github.com/leonhostetler/milc_qcd/blob/04be590b79138235ce253b665df2e76ececd5619/wilson_flow/control.c#L25-L94
  - https://github.com/leonhostetler/milc_qcd/blob/04be590b79138235ce253b665df2e76ececd5619/wilson_flow/integrate_quda.c#L8-L119
  - https://github.com/leonhostetler/milc_qcd/blob/04be590b79138235ce253b665df2e76ececd5619/include/generic_quda.h#L43-L82
  - https://github.com/leonhostetler/milc_qcd/blob/04be590b79138235ce253b665df2e76ececd5619/generic/remap_stdio_from_args.c#L89-L105
  - https://github.com/lattice/quda/blob/e9977c0c2c7359bf642108fe2ad01bb6cedea5d6/include/quda.h#L850-L886
  - https://github.com/lattice/quda/blob/e9977c0c2c7359bf642108fe2ad01bb6cedea5d6/lib/interface_quda.cpp#L5347-L5443
observed: "2026-08-19"
observed_on:
  software:
    milc:
      commit: 04be590b79138235ce253b665df2e76ececd5619
      branch: quda_gauge_flow
      forked_from_default: 5b20b44fa9080dc2ee97c213a755d9712457b356
    quda:
      commit: e9977c0c2c7359bf642108fe2ad01bb6cedea5d6
      branch: develop
---

# MILC `wilson_flow` application guide

`wilson_flow` evolves a gauge field under a selected flow action and reports gauge observables
at successive flow times. This guide covers the upstream CPU application structure and the
version-scoped QUDA extension used by the observed production branch. Build capabilities remain
canonical in `../build-profiles.yaml`, and shared instrumentation policy lives in `../timing.md`.

## Input and executable structure

The application reads one global preamble, initializes the lattice and integrator once, and then
loops over configuration-specific input sets until input ends. The preamble contains prompt mode,
lattice dimensions, and an anisotropy value when the executable was built with `ANISOTROPY`.

At the observed revision, each input set supplies, in order:

1. a starting-lattice instruction;
2. a flow description (`wilson`, `symanzik`, or the caveated `zeuthen` token below);
3. `exp_order` and `stepsize`;
4. `local_tol` for an adaptive-integrator target;
5. `stoptime`; and
6. an ending-lattice instruction and any applicable ILDG logical file name.

`reload_*` starts an independent flow from the named gauge field. The CPU path permits
`continue`, which starts the next input set from the in-memory field left by the preceding flow.
The application rejects a `warm` starting lattice. The QUDA branch has a stronger state-ownership
restriction described under saved and continued gauge fields.

The flow action is an input choice, but the integration method is compiled into the executable.
The target `wilson_flow` selects the third-order Luescher scheme. Other upstream targets select
CF3, Carpenter-Kennedy, Berland-Bogey-Bailly, RKMK3/4/5/8, or adaptive Luescher, CF3, and
Bogacki-Shampine schemes; a corresponding `_a` target enables anisotropy. Record the literal
executable and its printed `Integrator = ...` value rather than inferring the method from the
input file.

On the CPU path, `exp_order` controls the series used to exponentiate the anti-Hermitian update.
The observed QUDA wrapper does not consume `exp_order`. It supports the Luescher targets
`wilson_flow` and `wilson_flow_a` (mapped to QUDA Runge-Kutta order 3) and the BBB targets
`wilson_flow_bbb` and `wilson_flow_bbb_a` (mapped to order 4); other compiled integrator targets
terminate in that wrapper. It also accepts only Wilson and Symanzik flow actions.

**Zeuthen-flow heads-up:** the CPU parser accepts `zeuthen`, but at the observed upstream revision
the Zeuthen correction routine is an empty placeholder. The resulting staple uses the Symanzik
coefficients without the declared correction. Do not treat token acceptance as an implemented or
validated Zeuthen-flow calculation.

## Flow rows and endpoint semantics

The CPU path prints this header and one `GFLOW:` row at flow time zero and after every accepted
step:

```text
#LABEL time Clover_t Clover_s Plaq_t Plaq_s Rect_t Rect_s charge
```

It then prints `Number of steps`. Adaptive targets additionally print a `#LABEL2` header,
`ADAPT:` rows, and `Number of rejected steps`. For a positive `stoptime`, the CPU loop shortens
its final step when necessary so the final `GFLOW:` time reaches the requested stop time.
`stoptime -1` instead selects the CPU source's automatic stopping test.

At the observed MILC/QUDA revisions, the accelerated path prints an initial row and subsequent
rows with the prefix `performWFlowQuda:` and the schema:

```text
flow t, Energy_t, Energy_s, Plaq_t, Plaq_s, Rect_t, Rect_s, charge
```

The wrapper fixes the QUDA measurement interval at one step. These fields and the CPU `GFLOW:`
fields are backend-native records; do not rename them or apply a normalization conversion unless
that conversion has been independently established for the exact revisions and observable
definitions.

**QUDA endpoint heads-up:** the observed wrapper assigns `stoptime / stepsize` to QUDA's unsigned
integer `n_steps`. A positive nonintegral quotient is truncated, and floating-point roundoff can
also put a mathematically integral quotient just below the integer boundary. QUDA then reports
the initial row plus `n_steps` rows and ends at `n_steps * stepsize`; it does not independently
enforce the requested `stoptime`. The CPU automatic-stop value is not implemented by this QUDA
path and must not be used with it. Freeze and validate the actual final flow-time contract rather
than accepting the echoed `stoptime` or a completion marker.

## Saved and continued gauge fields

On the CPU path, flow integration updates the MILC site links. A requested ending-lattice save or
a following `continue` therefore operates on that evolved in-memory field, subject to the usual
format-specific gauge-field validation.

The observed QUDA wrapper instead copies the MILC site links into a temporary host array, loads
them into QUDA, and leaves the evolved field in QUDA's resident smeared field. It frees the host
input array without copying the evolved links back to the MILC site structure. The surrounding
control code subsequently calls the generic MILC save routine, and a later input set reloads QUDA
from those same MILC site links.

Consequently, this guide qualifies the observed QUDA branch only for independently reloaded input
sets with `forget` ending-lattice handling. A QUDA ending-lattice save or `continue` chain is not
valid evidence of a saved or continued flowed field until the ownership path is corrected and a
direct loaded-field-versus-saved-field comparison passes. File existence alone cannot establish
that property.

## Output and timing boundaries

One normally exiting process emits one `start: <date/time>` and `exit: <date/time>` pair. Unlike
the other current MILC application guides, it emits one `RUNNING COMPLETED` marker and one
top-level `Time = ... seconds` record only after the entire input stream ends. Each successful
input set instead emits one `Time to complete flow = ... seconds` record.

The per-flow timer starts after `readin()` has loaded the starting gauge field. It excludes that
input set's gauge-file read but includes flow integration and a requested ending-lattice save. On
the observed QUDA path it also includes host-to-device gauge loading and, for the first flow in a
process, QUDA initialization; later flows reuse the initialized library but load their gauge
field again.

The top-level timer starts before global `setup()`. It includes global setup, every gauge-file
load, every flow, and requested ending-lattice saves. It is printed before lattice cleanup, QUDA
finalization, and normal-exit finalization, so those final activities are outside `Time`. Use the
`start:` to `exit:` duration as an application-envelope cross-check and scheduler elapsed time as
the allocation-cost clock.

QUDA profile records such as `loadGaugeQuda` and `wFlowQuda` are backend component timers inside
these application intervals. Do not add a component time to its enclosing per-flow or application
time. See `../timing.md` for the shared timing-layer rules.

## Output ownership and completion checks

When `REMAP_STDIO_APPEND` is compiled, MILC opens redirected stdout and stderr in append mode. A
reused destination can therefore contain a failed attempt followed by a successful attempt. Use
new run-owned output paths. If inherited output must be diagnosed, segment it into lifecycle
attempts before interpreting markers; a later `RUNNING COMPLETED` does not repair an earlier
partial block in the same file.

Accept a flow workload for performance or scientific analysis only when:

- one accepted process attempt has a normal `exit:`, and the application and scheduler exit
  states are successful;
- the intended number of input sets and corresponding per-flow timers is present;
- each intended gauge field was loaded successfully and its identity and health checks match the
  run contract;
- the printed flow action, integrator, anisotropy state, precision, and CPU or QUDA backend match
  the intended executable and input;
- every flow block has exactly one applicable header, an initial time-zero row, the expected
  finite numeric columns, strictly increasing later times, and the expected row cardinality;
- the CPU `Number of steps` and any adaptive rejected-step record are consistent with the rows,
  or the QUDA row count and actual final time are consistent with the intended integer-step
  contract;
- the final observed flow time satisfies the declared scientific endpoint requirement; and
- every requested CPU ending-lattice artifact exists and passes structural, numerical, and
  scientific validation, while the observed QUDA branch obeys the `forget` and independent-reload
  restriction above.

## Tuning and benchmarking interpretation

One application work unit is one successful input set: a starting gauge state, flow action,
compiled integrator and backend, step schedule, observable stream, and ending-lattice policy. A
workflow can apply several actions or step schedules to the same gauge configuration; those are
separate flow work units even when one scheduler job packages them together.

For comparisons, record lattice volume, rank and device decomposition, executable target,
isotropy or anisotropy, flow action, backend and revisions, host and device precision, requested
step size and stop time, actual step count and final time, adaptive tolerance and rejected steps
when applicable, measurement interval, gauge-load method, ending-lattice policy, and accelerator
warm state. Separate first-process QUDA initialization from repeated per-configuration gauge
loads and flow work.

Retain gauge I/O, per-flow application time, backend child profiles, whole-application time, and
scheduler elapsed time as distinct layers. Normalize production cost by the declared flow work
unit or gauge-configuration workflow, not by the single process-level `RUNNING COMPLETED` marker.

## Coverage

The CPU input, target, row, and timer structure is backed by upstream MILC source and regression
samples at commit `32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839`. The QUDA sections are scoped to
MILC fork commit `04be590b79138235ce253b665df2e76ececd5619` on `quda_gauge_flow` with QUDA commit
`e9977c0c2c7359bf642108fe2ad01bb6cedea5d6`. They do not claim that current upstream MILC has the
same wrapper or that CPU and QUDA observables are scientifically equivalent.

The Zeuthen placeholder, QUDA endpoint conversion, and absent flowed-field copyback are
version-scoped source findings with direct acceptance consequences. Reconcile them against any
newer source before preparing an input or qualifying a stack. This guide does not establish a
validated build profile, machine stack, observable-normalization conversion, or production cost
model.
