---
title: Capturing a GPU profile
summary: What a capture must establish before the run — that the artifact is validated rather than the exit status, that a wall-clock anchor exists where the format does not carry one, and whether an untraced control run exists to bound what tracing cost.
scope: [universal]
load_when: Planning, submitting, or validating a profiled run.
evidence: reproduced
observations: 2
sources:
  - operator's screened project records
  - vendor tracer documentation for Nsight Systems and ROCm Systems Profiler
observed: "2026-09-15"
observed_on:
  requirements: gpu-profile-capture
review_by: "2027-09-15"
---

# Capturing a GPU profile

A capture consumes allocation and cannot be repeated cheaply, so what it must contain is
decided before the run, not discovered after it.

## A profiler's exit status is not a completion signal

Writing the report can be a **separate post-process step from running the application**, and it
can fail on its own while the profiler still exits 0. Two independent causes have been observed
producing exactly that outcome: an unsupported operation on a home filesystem, and quota
exhaustion on a filesystem that was otherwise correct. The list is illustrative and explicitly
non-exhaustive — the point is the class, not the two members.

**Validate the artifact, never the status.** For Nsight Systems the signature of this failure is
a `.qdstrm` present with no `.nsys-rep`: the application ran and the conversion did not. Check
per rank on a multi-rank capture; a report that exists for six of eight ranks is a partial
capture, not a successful one.

This is the exact-artifact rule of [`measurement.md`](measurement.md) applied to a profiler, and
that document remains canonical for predeclaring an expected-artifact manifest. Failing to apply
it here has a specific cost: a silent capture failure is discovered after the allocation is
spent, and one lost capture can remove the only run covering a condition.

## Record a time anchor the format does not carry

Application output names phases, iterations and completion; a trace records launches and
durations. Correlating them requires a shared time base, and the formats differ on whether they
supply one.

Nsight Systems records timestamps relative to session start and carries a UTC anchor in the
profile, so absolute correlation is possible after the fact. rocpd captures inspected here
carry timestamps from a monotonic clock and **no wall-clock anchor in the file at all** — the
metadata holds a schema version and identifiers and nothing temporal.

So on a format with no anchor, **the capture must record one itself**: the wall-clock and
monotonic clocks together at launch, written beside the profile. It costs one line in a
submission script and it cannot be reconstructed afterwards. Without it, application phases can
be aligned to the trace only structurally — by order and relative duration — never absolutely.

## Only an untraced control bounds what tracing cost

`[inferred]` A tracer records by intercepting, and it is charged per intercepted event, so its
cost tracks traced-call density rather than elapsed time. It therefore falls unevenly across a
run: a phase dense in host-API and MPI calls is inflated hard while a phase of the same length
dominated by long kernels is barely touched. A profiled run is not a scaled copy of the run
being optimised, and nothing inside the profile reveals the difference.

**So where a capture is still being planned, arrange an untraced control run of the identical
workload in the same job and keep its application timing output beside the profile.** This is a
recommendation, not a gate: most analyses are of captures already taken, and a control cannot be
added to one afterwards. Where one is arranged, identical means the same input, the same
placement and the same binary — confirm it afterwards against an invariant the application
prints, such as iteration counts or residuals, rather than assuming it.

The control is usually already there and free. Any workload that warms an autotune cache has to
run the same input untraced first, so the warming run *is* the control, provided its output is
kept rather than overwritten by the traced run that follows. Where nothing forces a warming run,
the control costs one more execution of a workload already sized to fit the job.

Capture time is the only window, because a control cannot be reconstructed from the profile
afterwards — which is why it is worth deciding before the run even though an analysis can
proceed without one. Where there is no control the perturbation is unmeasured, and
[`profile-metrics.md`](profile-metrics.md) requires the reading to say so; that labelling is not
optional even though the control is. Narrow the trace to what the question needs for the same
reason: where the question is GPU-side, dropping host-call tracing removes most of the cost and
none of the kernel figures.

## Prefer advice to enforcement in scripts that travel

A capture-placement rule encodes one site's layout. A submission script that hard-fails on it
breaks for the next site and for anyone the script is shared with. State the placement, and put
the mechanical check on the artifact, which is site-independent.
