---
title: Capturing a GPU profile on Frontier
summary: Which ROCm module version ships a profiler is not fixed, so verify the profiler command resolves after the modules load and before the profiled step runs.
scope: [machine:frontier]
load_when: Planning or submitting a profiled run on Frontier.
evidence: inferred
sources:
  - operator's screened project records
observed: "2026-09-16"
observed_on:
  machine: frontier
review_by: "2027-09-16"
---

# Capturing a GPU profile on Frontier

**Profiler availability here is a property of the ROCm module version, not of ROCm.** The
machine profile records `rocprofv3` and `rocprof-sys-sample` as provided by the `rocm` module
and marks the second version-sensitive. A ROCm module default was observed to stop providing
`rocprof-sys-sample` during 2026; that is one observation, and what follows is an inference
from it rather than a reproduced result.

## Verify the command before the job depends on it

Pinning ROCm is not profiler knowledge and is not owned here — [`notes.md`](notes.md) has why a
lone `rocm/<version>` pin resolves silently to the meta-module's default and what to load
instead. It governs any pinned ROCm work, profiling included.

What is specific to capture is that a correct pin can still land on a module that does not ship
the profiler, and that this failure does not look like one: the job runs, exits cleanly, and
produces no profile. Check that the command resolves after the modules are loaded and before
the profiled step runs, and fail there. That is a check on the tool's presence rather than on a
site path, so it is the mechanical kind
[`conventions/profile-capture.md`](../../conventions/profile-capture.md) prefers to a
site-specific guard.

That convention owns what to request from each profiler and how to name per-rank output, and
[`../perlmutter/profile-capture.md`](../perlmutter/profile-capture.md) is the sibling instance
of the same class on the other machine: what a site does to a capture is machine knowledge, and
what a tracer records is not.
