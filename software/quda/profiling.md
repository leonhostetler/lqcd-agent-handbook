---
title: Reading a QUDA kernel in a GPU profile
summary: Why a profile's kernel short name names the launcher rather than the computation, how a demangled name resolves to its functor and source file, why an enum template argument discriminates without naming and how the tunecache header recovers the revision needed to resolve it, what a cold tunecache does to call counts, launch geometry and duration spread, and how to read the y block extent on a warm one.
scope: [software:quda]
load_when: Interpreting QUDA kernel names, call counts, launch geometry, or duration spread in a GPU profile.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/targets/cuda/kernel.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/tunable_nd.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/kernels/dslash_staggered.cuh
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/tune.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multi_blas_quda.cu
observed: "2026-09-15"
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

## An enum template argument is a discriminator, not a name

`[inferred]` The section above assumes the source revision is in reach. Where it is not, one
class of template argument still looks readable and is not.

A demangled name renders a non-type template argument of enumeration type as its **integer
value** beside the enumeration's type name — `(quda::KernelType)5`, `(QudaReconstructType_s)18`.
The integer is what the profile carries. The mapping from it to a name lives in the enumeration
declaration in the source, and nothing in the profile identifies which revision built the binary,
so a mapping recalled rather than read cannot be checked against the capture at all, however
familiar it feels.

Two things follow, and they pull in opposite directions. The value is a perfectly good
**discriminator**: rows that differ only in it are different instantiations, and their call
counts, durations and launch geometry are comparable against one another without any mapping.
It is not a **name**, and the failure is writing the interpretation into prose — calling a row
"the interior dslash" — where nothing downstream marks it as unverified. A hypothesis record is
the worst place for it: a bottleneck named for an attribution the evidence does not carry reads
exactly like one that is grounded, which is the failure
[`../../conventions/profile-metrics.md`](../../conventions/profile-metrics.md) names for
unobservable bottlenecks, one field over.

**Look for the tunecache before falling back.** `[source]` The profile does not carry the
revision, but a run that wrote a tunecache does. That file's header second field is the Git
descriptor [`internals/autotuning.md`](internals/autotuning.md) records, and it names the commit
the build was configured from — `1.1.0-<commit>-sm_80` on one observed CUDA cache, alongside the
GPU architecture and CUDA version. Resolve that commit in a QUDA checkout and the enumeration
can be read at the revision that actually built the binary instead of at whatever revision is
checked out. Confirm the commit resolves to an object before relying on it, and note what the
header does **not** establish: `internals/autotuning.md` owns that, and a cache written by a
different build than the one profiled is exactly the case to rule out.

**Where neither a revision nor a tunecache header is available, identify such a kernel by its
template arguments and by what the run's decomposition implies, and say which.** The partitioned dimensions follow from
the rank grid, so which exterior-kernel values may legally appear follows too, and that
constrains a mapping without asserting one. Resolving it properly is the procedure above applied
to one more template argument: read the enumeration in the revision that built the binary.

**Run the decomposition cross-check even when the revision is in hand.** It is independent of
the source read and costs nothing: on one capture the exterior values present were exactly those
the rank grid permits, with the unpartitioned dimension's value absent from the profile
altogether. A source read and a decomposition argument that agree are two premises; a source read
alone is one, and it is the one that silently goes wrong when the cache header belongs to a
different build.

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

`gpu-profile-summary.py launch-geometry` supplies the evidence for this gate: per kernel, the
distinct grid and block extents, how many distinct *problem sizes* they represent, and the
launch count behind each. Two of its fields carry the reading and neither is a verdict.

- **`max_block_x_at_one_problem_size`.** `Tunable::advanceBlockDim` steps `block.x` and derives
  `grid.x = (minThreads + block.x - 1) / block.x` from it, so a sweep moves block.x *while the
  problem size is fixed*. Inverting that recurrence bounds `minThreads` from a single launch,
  which is how the tool separates a sweep from a kernel launched at several sizes. Skipping that
  separation is not a small error: on a known-warm capture it reported 25 of 153 kernels as
  swept, because the multi-blas kernels legitimately run at several vector counts.
- **`min_launches_per_geometry`.** A tuning candidate is launched once to warm up plus
  `candidate_iter()` times to be timed, so a sweep is **many geometries with a handful of
  launches each**. Two geometries with 72 and 24 launches are two call sites whatever block.x
  does, and reading the first field without this one reproduces the same false positive.

**Neither field settles warmth, and the tool does not claim to.** A tune key is a functor, a
problem size *and* an `aux` string carrying the communication policy, the shared-memory
carve-out and the multi-blas vector count — none of which any kernel name records. Two keys
differing only in `aux` are indistinguishable in a profile, so the tunecache the run wrote
remains the thing that settles it; [`internals/autotuning.md`](internals/autotuning.md) owns
how to read it.

## On a warm cache, `grid.y == 1` makes `block.y` the y extent

The section above covers a cold cache, where launch geometry describes the search. The
complementary reading matters just as often and is the one that misleads on a **warm** cache,
where geometry is stable and therefore looks like a fixed property of the kernel.

Most QUDA kernels launch through `TunableKernel2D`/`TunableKernel3D`, whose y dimension is not a
free tuning parameter. `advanceBlockDim` raises `block.y` only while `param.block.y <
vector_length_y`, and every path that sets it — `initTuneParam`, `defaultTuneParam`, and both
branches of `advanceBlockDim` — recomputes `grid.y = (vector_length_y + block.y - 1) / block.y`.
Two consequences follow directly:

- **`block.y` never exceeds `vector_length_y`.**
- **So `grid.y == 1` implies `block.y == vector_length_y` exactly** — the y block extent *is* the
  kernel's y problem size, not a tuned tile over it.

That turns a column the profile already records into a readable quantity. Where `grid.y == 1`,
rows of one demangled name that differ only in `block.y` are **different y problem sizes**, and
the duration difference between them is work. Where `grid.y > 1`, `block.y` is a tile and says
nothing about the problem size; only the product does.

The multi-blas kernels are the worked example, because they are where a session is most likely to
reach the wrong conclusion. `MultiBlasArg`'s y length is the number of y/w vectors in the call,
and one demangled `multi_axpyBzpcx_` name can legitimately appear with several `block.y` values
in a single run: the tune key carries `NXZ` in its `aux` string, so call sites with different
vector counts are different keys, not repeated tuning of one. **A high coefficient of variation
across those rows is batch-size variation, not load imbalance, contention, clock behaviour or a
cold cache** — the four causes [`../../conventions/profile-metrics.md`](../../conventions/profile-metrics.md)
lists. The discriminator is cheap: group by `block.y` as well as by name, and check whether mean
duration is *linear* in it. If it is, the spread is the vector count and there is nothing to fix.

**Do not group these rows together and quote one mean.** Merging launches that differ in y
problem size produces a spread that is an artefact of the merge, which is the same defect the
short-name warning above describes, one column over.

## A transfer far below device bandwidth is a memory-residency question

The sections above concern kernels. One transfer reading deserves the same treatment, because
it presents as a kernel-adjacent oddity and resolves somewhere else entirely: a
**device-to-device** copy running one to three orders of magnitude below device bandwidth,
while copies of the same size and kind elsewhere in the run reach full rate.

That is not contention and not clock behaviour — neither appears in the causes
[`../../conventions/profile-metrics.md`](../../conventions/profile-metrics.md) lists for a
spread that large. It is a residency question, and
[`internals/managed-memory.md`](internals/managed-memory.md) owns it: QUDA reaches managed
memory by two routes and only one of them can be prefetched. The discriminator is in the trace
already — unified-memory migration events lying *inside* the slow copies' intervals — so group
transfers by size **and** by enclosing annotation range before concluding anything from a
rate.
