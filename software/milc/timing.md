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
observed: "2026-08-18"
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

## Timing layers

Use the narrowest timer that answers the declared question, but retain its enclosing clocks:

1. scheduler elapsed time and allocated resources establish job cost;
2. an application's top-level `Time = ... seconds` record establishes only the interval bracketed
   by that application's control code;
3. `PRTIME` records divide application work into named phases; and
4. component timers such as `CONGRAD5`, `FFTIME`, `FLTIME`, and `GFTIME` characterize individual
   implementations or calls.

These layers can overlap. Never add a parent phase to its child component timers, and do not
assume that the sum of printed components equals either the application or scheduler total.
Report the residual as unaccounted time only after confirming that all terms use compatible
boundaries and recurrence scopes.

Top-level timing boundaries differ among MILC applications and sometimes between the first and
later input sets. Load the relevant application guide before deciding whether a `Time` record
includes setup, gauge-field I/O, ending-lattice output, or work inherited from an adjacent input
set.

## Build and analysis record

For a tuning or benchmark result, capture:

- the resolved `CTIME` value and other timing-related definitions;
- the application executable, MILC revision, linked backend revisions, and build profile;
- which expected marker families actually appeared;
- the parser or aggregation rule used for each reported quantity; and
- any missing, overlapping, excluded, or unaccounted interval.

Keep raw output and extracted measurements in the working directory. This document owns only the
durable interpretation of the instrumentation.
