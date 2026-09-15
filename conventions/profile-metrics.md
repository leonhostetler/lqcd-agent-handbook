---
title: Reading GPU profile metrics
summary: What each extracted profile quantity means, how idle time is attributed and what its residual does and does not prove, what a tracer cannot establish, and the readings that are unfounded on trace data alone.
scope: [universal]
load_when: Reading, quoting, or reasoning about any quantity extracted from a GPU profiler database.
evidence: source
sources:
  - tools/gpu_profile/metrics.py
  - vendor tracer documentation for Nsight Systems and ROCm Systems Profiler
observed: "2026-09-14"
observed_on:
  requirements: gpu-profile-metric-semantics
review_by: "2027-09-14"
---

# Reading GPU profile metrics

A profile is evidence about one execution, under one set of capture options. The quantities
below are the ones an extraction reports; several are easy to misread in a way that produces a
confident, precise-looking, wrong conclusion. Read them exactly as defined here, and cite the
figure the extraction emitted rather than one recomputed by hand.

## Work is not elapsed time

Two quantities answer different questions and are routinely conflated.

- **Kernel work** is the sum of individual kernel durations. Kernels running concurrently on
  different streams each contribute in full, so this can exceed the wall-clock span of the
  capture. It is the denominator for per-kernel shares of work, and it is not elapsed time.
- **Busy time** is the wall-clock time during which at least one kernel was executing, with
  overlapping intervals merged. It is bounded by the profile span.

**Anything divided by elapsed time uses the merged figure.** Utilisation is busy time over the
profile span and never exceeds 100%. The ratio of work to busy time states how much concurrency
was achieved: 1.0 means kernels never overlapped, and a value near 1.0 on a workload built
around multiple streams is itself a finding rather than a neutral fact.

**Host time blocked in synchronization follows the same rule** — concurrent calls across host
threads are merged, not summed, so the figure stays bounded by the span.

## Launch geometry is not occupancy

How much of one full device wave a launch fills follows from grid and block extents, which a
trace records. Register pressure and shared-memory footprint do not follow from those extents,
and either can hold achieved occupancy far below what the geometry permits.

A launch that fills at least one wave establishes only that it fills at least one wave. It
never licenses a claim that occupancy is high, and a low value means only that the grid is too
small to fill the device once. Do not call this quantity occupancy; the honest narrow name is
what stops it being read as the authoritative one.

## Idle time is measured between kernels, not around them

Reported idle time sums the gaps *between* kernel execution intervals. Time before the first
kernel and after the last is excluded from that total, though it still contributes to the span
that utilisation divides by. A capture that begins long before the first launch therefore shows
low utilisation and little idle time at once, and both figures are correct.

## Duration spread is a question, not an answer

The coefficient of variation of a kernel's duration — its standard deviation over its mean —
says the same kernel took materially different times on different launches. It does not say
why. Load imbalance, contention, clock behaviour, and a cold autotune cache all produce it, and
they call for different actions. Where the profiled software autotunes, read that software's
own autotuning document before attributing spread to anything else: on a cold cache the first
launch of each kernel shape is a tuning sweep rather than steady-state work.

## A per-phase figure and a per-phase table count differently

Per-phase time totals are clipped to the phase window, so they sum to the profile total. The
per-phase breakdown tables list every event overlapping the window with its **full** duration,
because a duration describes the event and not the window. One long event therefore appears in
two adjacent phases' tables at full length. Both behaviours are correct; quoting a table figure
as though it were a windowed total is not.

## Attributed idle, and what the residual is not

Idle time on its own says the GPU was waiting; it does not say what for. The extraction
splits inter-kernel idle into host-side categories — **MPI**, **host API** (the CUDA or HIP
runtime and driver), **OS runtime** — and reports whatever none of them covers as the
**residual**.

Three rules decide whether those numbers mean anything.

**The categories are unioned, not summed.** A thread inside an MPI call is frequently also
inside a traced API call, and a nanosecond covered twice is still one nanosecond of idle.
Each category is intersected with the merged idle set, and the accounted total is the
intersection of idle with the *union* of all categories. So the per-category figures may
overlap each other, and `accounted + residual == idle` always holds while the category
figures need not sum to `accounted`. Adding the columns up is the misreading this design
invites; the accounted figure is the one that composes.

**OS-runtime attribution covers only the threads that drive the GPU.** OS tracing records
every thread, and a communication progress thread parked in `poll` or `futex` runs for
essentially the whole job. Unfiltered, that single thread covers every idle gap and reports
the application as OS-blocked ~100% of the time — measured at 18.691 s of 18.691 s on a real
capture, against 0.389 s for the thread actually issuing the launches. Both figures are
arithmetically correct and one of them is worthless. A thread "drives the GPU" if it appears
in the runtime-API table, so a capture without API tracing yields no OS attribution rather
than an unfiltered one.

**The residual is an upper bound on host compute, never a measurement of it.** It is host
time the capture located but did not name, and it also holds every host-side call the
profiler did not trace — Nsight Systems' `CUDA_SKIP_SOME_API_CALLS` omits cheap API calls by
design, and each omission lands here. Treat it as "time the capture cannot explain", which is
a finding worth acting on and a different claim from "time the application spent computing".

Read the residual's own gap histogram before concluding anything from its total. The
distribution routinely separates two unrelated costs that the sum hides: very many sub-100 µs
slices, which are per-launch host overhead spread across every kernel, and a few thousand
slices of milliseconds, which are real host-side work at a structural boundary. One total
covering both describes neither.

**An untraced category is reported as null, and null is not zero.** Where the capture cannot
observe a category the extraction emits no number for it, names the reason, and lists it among
what the residual absorbs. This is the absent-instrumentation rule below applied where it is
easiest to get wrong: rocprofv3 does not intercept MPI, so a naive
implementation reports `mpi = 0.0` on every AMD profile, and a session reading that goes
looking for the bottleneck anywhere but communication. If a category is null, its share is
unknown, and the residual is inflated by exactly the unknown amount.

## Transfer time is only a cost when it is exposed

A transfer that runs while kernels run costs nothing in wall-clock. The extraction reports,
per direction, total transfer time, the part overlapping merged kernel execution, and the
**exposed** part that does not — and only the last lengthens the run.

Volume cannot substitute for this and routinely points the opposite way. On a real capture
the peer-to-peer class was the largest by far — 1.1 TB across 315k transfers — and 96.8% of
its time was hidden behind kernels, leaving 0.088 s exposed in a 42 s phase. The obvious
reading of the volume figure ("communication dominates, improve the overlap") was wrong, and
the overlap measurement is the only thing in the profile that says so. Quote exposed time
when arguing that a transfer class costs something.

Per-direction intervals are **merged before measuring**, for the reason in the first section:
transfers issued on several streams run concurrently, and summing their durations returns
work rather than elapsed time. A hand-rolled version that sums instead of merges overstates
both the total and the overlap — by 28% on the capture above.

## What a tracer does not record

`[docs]` Nsight Systems and ROCm Systems Profiler are **tracers**. They record API calls, kernel
launches and their durations, memory transfers, synchronization, and annotation ranges. Unless
hardware counters were deliberately collected, they do not record achieved memory bandwidth,
cache hit behaviour, access coalescing, or achieved occupancy.

**A bottleneck the capture cannot observe may not be asserted from it.** A kernel that is slow
in a trace is slow; whether it is slow *because* it is memory-bound is a separate claim needing
counters the trace does not hold. Record that as a question for a counter-collecting run, not as
a finding. The temptation is strong precisely because the conclusion is often plausible, and
nothing in the output marks it as unsupported.

## Absent instrumentation is not an absent bottleneck

A capture with no communication tables supports no communication hypothesis — and supports no
claim that communication is healthy either. The same holds for annotations, host sampling, and
counters. Report the capability gap as a gap. Silence in a profile is the absence of a
measurement, never the presence of a clean result.

## One rank's profile is one rank's view

Imbalance is a cross-rank quantity. On a single rank, a rank blocked waiting on its neighbours
is indistinguishable from a rank with a communication problem of its own, and reading the first
as the second is the standard way a profile produces a confident wrong diagnosis. Compute the
cross-rank view across the per-rank captures before attributing a wait to the rank that is
waiting.

Comparing captures taken by two different profilers is not a measurement: the two record
different things, so a delta across them has no denominator.
