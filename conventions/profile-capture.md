---
title: Capturing a GPU profile
summary: What a capture must establish before the run — that the artifact is validated rather than the exit status, and that a wall-clock anchor exists where the format does not carry one.
scope: [universal]
load_when: Planning, submitting, or validating a profiled run.
evidence: reproduced
observations: 2
sources:
  - operator's screened project records
  - vendor tracer documentation for Nsight Systems and ROCm Systems Profiler
observed: "2026-09-14"
observed_on:
  requirements: gpu-profile-capture
review_by: "2027-09-14"
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

## Prefer advice to enforcement in scripts that travel

A capture-placement rule encodes one site's layout. A submission script that hard-fails on it
breaks for the next site and for anyone the script is shared with. State the placement, and put
the mechanical check on the artifact, which is site-independent.
