---
title: Reading a QUDA kernel in a GPU profile
summary: Why a profile's kernel short name names the launcher rather than the computation, how a demangled name resolves to its functor and source file, and what a cold tunecache does to call counts, launch geometry and duration spread.
scope: [software:quda]
load_when: Interpreting QUDA kernel names, call counts, launch geometry, or duration spread in a GPU profile.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/targets/cuda/kernel.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/tunable_nd.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/kernels/dslash_staggered.cuh
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/tune.cpp
observed: "2026-09-14"
observed_on:
  software:
    quda: {commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a, branch: develop}
---

# Reading a QUDA kernel in a GPU profile

[`conventions/profile-metrics.md`](../../conventions/profile-metrics.md) defines what each
extracted quantity means. This leaf covers what those quantities mean **when the profiled
software is QUDA**, where three of them are systematically misread.

## The short name is the launcher, not the computation

QUDA dispatches almost everything through a small set of generic entry points — `Kernel1D`,
`Kernel2D`, `Kernel3D`, and the reduction equivalents. The computation is a **template
argument**:

```text
template <template <typename> class Functor, typename Arg, bool grid_stride = false>
__global__ ... Kernel3D(const GRID_CONSTANT Arg arg)
```

`@tparam Functor Kernel functor that defines the kernel`. So `Kernel3D` names the launcher and
says nothing about what ran. A profile reporting hundreds of thousands of `Kernel3D` calls is
reporting *every three-dimensional kernel in the run*, not one hot kernel.

**Group by the full demangled name, never the short name.** Grouping by short name merges
unrelated computations into one row and produces a duration spread that is an artefact of the
merge. `tools/gpu-profile-summary.py` already groups by demangled name; the trap is a
hand-written query that groups by `shortName` because it is the readable column.

## A demangled name resolves to a source file

The functor and its `Arg` are the navigation keys, and both live in `include/kernels/`. The
staggered dslash is the worked example: functor `staggered` and `StaggeredArg` are both declared
in `include/kernels/dslash_staggered.cuh`. The dispatch site is the corresponding
`TunableKernel` subclass, which launches the generic entry point with that functor —
`launch_device<Functor, grid_stride>(KERNEL(Kernel2D), tp, stream, arg)`.

So the procedure is: take the demangled name, read the functor and `Arg` out of the template
arguments, and find the `include/kernels/*.cuh` that declares them. The `Arg`'s own template
parameters — precision, colour count, whether the improved action is in play — distinguish
instantiations that share a functor, which is why two rows with the same functor can be
genuinely different kernels.

**Confirm a suspected pattern by reading that file.** A duration does not tell you whether a
kernel is doing what you think; the functor body does.

## A cold tunecache changes what the profile contains

[`internals/autotuning.md`](internals/autotuning.md) is canonical for what makes a cache warm and
how to verify it. This is the separate question of what a cold cache does to a *trace*.

When a tune key is cold, QUDA sweeps candidate launch parameters. For each candidate it issues
one warm-up launch plus a fixed number of timed launches, and **every one of them is a real
kernel launch that the profiler records**. Three readings follow, and all three are wrong on a
cold-cache capture:

- **Call counts are inflated.** The profile reports far more launches than the application
  performed, because most of them are tuning trials.
- **Recorded launch geometry is a trial, not the chosen one.** Block and grid extents vary by
  design across candidates. Anything computed from launch geometry — wave fill, threads per
  launch — describes the search, not what production runs.
- **Duration spread is large by construction.** Candidates are deliberately different, so they
  take deliberately different times. A high coefficient of variation here is the tuning sweep,
  and reading it as load imbalance or contention is the standard way a cold-cache profile
  produces a confident wrong diagnosis.

**Establish cache state before reading any of these three.** A capture whose warmth is unknown
supports no claim about kernel call counts, launch geometry, or duration spread. That is a
capability gap in the sense [`conventions/profile-metrics.md`](../../conventions/profile-metrics.md)
uses, and it is reported as one.
