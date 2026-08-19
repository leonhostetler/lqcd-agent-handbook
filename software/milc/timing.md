---
title: MILC timing instrumentation
summary: Build-time timing macros, output layers, and interpretation rules shared by MILC applications.
scope: [software:milc]
load_when: Building or analyzing a MILC application for tuning, benchmarking, or production-cost estimation.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/Makefile#L916-L939
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/ks_spectrum_includes.h#L33-L40
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/ks_measure_includes.h#L25-L31
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/ks_imp_includes.h#L37-L43
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/generic_ks/gauss_smear_ks_QUDA.c#L73-L130
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_spectrum/setup.c#L78-L100
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_measure/setup.c#L55-L75
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/ks_imp_rhmc/setup.c#L162-L182
  - https://github.com/milc-qcd/milc_qcd/blob/32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839/generic/com_mpi.c#L612-L626
observed: "2026-08-19"
observed_on:
  software:
    milc:
      commit: 32e18069cc5e13d5a2f380dab3cb1ed5a3ebc839
      branch: develop
---

# MILC timing instrumentation

MILC's `CTIME` make variable supplies a bundle of preprocessor definitions that enable timing
records in application and shared-library code. The exact bundle is version- and build-profile
specific; record its resolved value with the executable identity instead of assuming that the
source-tree default was used.

**Operator policy:** keep the relevant timing macros enabled for normal MILC builds. They are
required for tuning and benchmarking builds. If a macro is deliberately omitted because its
output or overhead would invalidate the intended run, record the exception and do not compare the
result as though it had the same instrumentation contract.

An absent timing line is not a zero-cost measurement. First establish whether its macro and code
path were compiled and exercised.

## Macro families

At the observed revision, the source-tree `CTIME` default contains the following principal
families. A build profile may add, remove, or rename members as the software changes.

| Definition | Timing scope |
|---|---|
| `PRTIME` | Application-level phases. The literal prefix differs by application: for example, `Aggregate time to` or `Time to`. |
| `CGTIME` | Staggered solves, including elapsed time and implementation-dependent iteration, mass, right-hand-side, precision, and rate fields. |
| `FFTIME` | Fermion-force work. |
| `FLTIME` | Fermion-link construction or fattening. |
| `GFTIME` | Gauge-force work. |
| `IOTIME` | Supported gauge-field, source, propagator, or related I/O paths. |
| `WMTIME` | Supported staggered-meson contraction work. |
| `GS_TIME` | QUDA two-link Gaussian-smearing work when an application-specific build bundle enables it. |
| `REMAP` | Remapping subcosts emitted by implementations that support them, usually in conjunction with another timer. |

Backend libraries may print additional timing, tuning, convergence, throughput, and memory
records independently of `CTIME`. Treat those as backend evidence and identify their format by
the executable and library revisions.

## Timer ownership

At the observed revision, application `STARTTIME` and `ENDTIME` macros update one
caller-owned elapsed-time variable. Treat that variable as one open interval: on every
preprocessed control-flow path, one start must reach exactly one matching end before the
variable is reused.

Nested or overlapping intervals require independent local variables declared under the same
instrumentation guard as their uses. Audit macro-expanded paths, including early exits and
configuration-specific branches, rather than relying on lexical start/end counts. Balanced
pairs establish that the timer is valid; they do not by themselves establish that its
boundaries measure the intended operation.

## Timing layers

Use the narrowest timer that answers the declared question, but retain its enclosing clocks:

1. scheduler elapsed time and allocated resources establish job cost;
2. a valid application `exit - start` timestamp difference supplies a whole-application
   envelope cross-check, not allocation cost;
3. an application's top-level `Time = ... seconds` record establishes only the interval bracketed
   by that application's control code;
4. `PRTIME` records divide application work into named phases; and
5. component timers such as `CONGRAD5`, `FFTIME`, `FLTIME`, and `GFTIME` characterize individual
   implementations or calls.

These layers can overlap. Never add a parent phase to its child component timers, and do not
assume that the sum of printed components equals either the application or scheduler total.
Report the residual as unaccounted time only after confirming that all terms use compatible
boundaries and recurrence scopes.

Top-level timing boundaries differ among MILC applications and sometimes between the first and
later input sets. Load the relevant application guide before deciding whether a `Time` record
includes setup, gauge-field I/O, ending-lattice output, or work inherited from an adjacent input
set.

## Whole-application timestamps

At the observed revision, `ks_spectrum`, `ks_measure`, and `ks_imp_rhmc` print
`start: <date/time>` early in application setup. The shared normal-exit routine prints
`exit: <date/time>` immediately before its final MPI barrier and `MPI_Finalize`. The
shared abnormal path prints `termination:` instead; an output with `start:` but no normal
`exit:` does not provide a complete whole-application duration.

Subtract `start` from `exit` as a seconds-resolution application wall-clock cross-check.
Retain the literal timestamps, timezone interpretation, and derived duration. This clock begins
after process launch and machine initialization and ends before the final MPI barrier and
finalization, so scheduler job or step elapsed time remains the authoritative allocation clock.
These timestamps are application lifecycle markers, not `CTIME` phase instrumentation.

For an application with multiple top-level `Time` records, compare their compatible sum with
the timestamp-derived duration. Record the difference as an application-envelope residual only
when the output is complete and the timer boundaries are understood. A large difference is a
diagnostic to investigate, not a value to distribute across phases automatically.

## Build and analysis record

For a tuning or benchmark result, capture:

- the resolved `CTIME` value and other timing-related definitions;
- the application executable, MILC revision, linked backend revisions, and build profile;
- which expected marker families actually appeared;
- any `start:`, `exit:`, or `termination:` markers and the valid derived duration;
- the parser or aggregation rule used for each reported quantity; and
- any missing, overlapping, excluded, or unaccounted interval.

Keep raw output and extracted measurements in the working directory. This document owns only the
durable interpretation of the instrumentation.
