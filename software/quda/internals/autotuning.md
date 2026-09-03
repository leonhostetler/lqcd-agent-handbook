---
title: QUDA autotuning and tunecache reuse
summary: How QUDA identifies, selects, stores, and reuses tuned launch and communication-policy parameters.
scope: [software:quda]
load_when: Reusing, migrating, validating, or interpreting a QUDA tunecache for tuning or benchmarking.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/README.md
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/NEWS
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/cuda/target_cuda.cmake
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/hip/target_hip.cmake
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/tune_key.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/tune_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/targets/cuda/tunable_kernel.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/color_spinor_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/gauge_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/communicator_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/util_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/tune.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/dslash.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/dslash_policy.hpp
  - https://github.com/lattice/quda/commit/d96a56f4e04cfe7158a923e06cc706af4e8a36cf
observed: "2026-08-18"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
---

# QUDA autotuning and tunecache reuse

For a benchmark, reuse a tunecache across a source, build, or runtime change only when every
tuning problem exercised by the measured workload is demonstrably unchanged. Treat QUDA's
Git-version rejection as a conservative screen, not as proof that retuning is necessary. If an
affected entry cannot be ruled out or safely replaced, populate a fresh cache before measurement.

This rule is deliberately asymmetric. Avoiding an unnecessary tuning pass saves setup cost;
silently reusing a no-longer-optimal launch or communication policy can bias the benchmark the
cache was meant to support.

## What the autotuner does

Most performance-critical QUDA operations derive a `TuneKey` and ask `tuneLaunch` for a
`TuneParam`. A cache hit returns the stored parameter after launch-validity checks; it does not
remeasure the alternatives or establish that the stored choice is still optimal. A miss explores
the tunable's candidate space, times candidates on the device, retimes the best first-stage
candidates, and stores the fastest surviving choice.

The generic candidate space can include block and grid dimensions, dynamic shared-memory
over-allocation, shared-memory carveout, and four operation-defined auxiliary integers. Some
policies use those auxiliary values to select algorithms. In particular, multi-GPU dslash policy
tuning can choose communication and overlap strategies as well as kernel launch parameters.

## The cache has three distinct identities

| Layer | Stored content | What it establishes |
| --- | --- | --- |
| file header | QUDA semantic version, Git descriptor, and `QUDA_HASH` build descriptor | whether QUDA's coarse whole-file gate accepts the cache |
| `TuneKey` | `volume`, `name`, and `aux` strings | which stored row a tunable looks up |
| `TuneParam` | block and grid dimensions, shared-memory settings, four auxiliary values, tuning time, and comment | the launch or policy choice reused on a hit |

At the observed revision, CUDA's `QUDA_HASH` contains only CPU architecture, configured GPU
architecture, and CUDA compiler version; HIP has the analogous HIP compiler descriptor. It is
not a content hash and does not cover the full CMake configuration, flags, host compiler,
driver/runtime, communication libraries, or source. The Git descriptor comes from `git describe`
during CMake configuration. Consequently, a header mismatch can reject a harmless comment-only
commit, while a matching header cannot prove tuning equivalence after an unrecorded build or
runtime change.

Setting `QUDA_TUNE_VERSION_CHECK=0` disables all three header comparisons together: semantic
version, Git descriptor, and build descriptor. It does not weaken only the Git check. Use this
override only as the final mechanical step after the compatibility audit below, and record it as
part of the benchmark environment.

## What a `TuneKey` captures

Key construction is distributed among the tunable implementations rather than enforced by one
complete schema. Representative keys encode local field dimensions, operation or functor type,
precision, field order, spin and color, vector layout, right-hand-side count and tiling, dslash
subtype, dagger and xpay state, and selected compile-time policies. Multi-GPU dslash policy keys
also append partition topology, visible-device ordering, P2P/GDR/NVSHMEM state, and the enabled
policy set.

These are strong distinctions, but they are not a proof that every performance-relevant input is
encoded. For example, `QUDA_ENABLE_TUNING_SHARED` can change generic shared-memory candidate
enumeration without being appended to the generic key. A changed key naturally misses and tunes a
new row. The dangerous case is changed generated code, candidate enumeration, parameter meaning,
or execution environment under an unchanged key: QUDA silently returns the old row and checks
basic launch validity, not current optimality.

## An `aux` field is evidence about the cache, not about the run

Auxiliary strings are printed as part of a tuning event, and a tuning event happens only on
the **first** execution of each distinct kernel shape. Reading them as a record of what the
run did is a live inference error.

The concrete case: QUDA's `parity=` field appears inside autotuning `aux` strings. **The
absence of `parity=0` from a log is evidence about the tunecache, not about which parities
executed** — a warm cache simply does not re-tune, and so does not re-print. Determine
parity behaviour from the calling application's inverter semantics
([`MILC staggered inverter types`](../../milc/internals/staggered-inverter-types.md)),
never from which kernel tags happen to appear.

The general rule: an `aux` field tells you a key was tuned at that moment. It does not tell
you how often the operation ran, and its absence does not tell you the operation did not run.

## Cache warmth is per shape, not per parameter name

A cache is warm for the exact keys it holds. Changing a parameter that alters a kernel's
**shape** produces new keys and a fresh round of tuning, even when the surrounding
build looks unchanged and the geometry is identical.

For staggered multigrid this bites on coarse colour specifically: changing a near-null
count at an unchanged coarsest volume still pays a full coarse-operator retune, because the
coarse-operator kernels are instantiated per coarse colour. **Treat warmth as per terminal
shape *and* colour.** Budget a cold retune whenever either moves, and do not carry a warm
measurement across such a change without re-warming.

**Budget a shape QUDA has never built as two submissions, not one.** The first execution of
a new coarsest shape pays its whole tuning cost at once, and that cost is of the same order
as a short-queue walltime — it can consume the allocation before the run reaches the stage
it was submitted for. Submit a **build stage** whose declared purpose is to tune and save
the cache, then a **warm stage** seeded from it.

In one measured scan every one of five first attempts timed out and every one of five warm
retries completed its setup, with new cache entries in the high hundreds on the first
execution against a few to a few hundred on the retry. The entry counts are properties of
that placement and shape; what transfers is that the cost is **one-time per shape** and
large enough to be scheduled around rather than absorbed.

Two of those build stages also completed and saved work beyond the cache — an eigensolve, in
that case — which turned the second submission into a cheap load. So the two-submission rule
bounds the first stage; it does not imply the second costs the same.

## Benchmark-scoped compatibility test

Define the cache's scope by the exact workload and measured region, not by the QUDA repository as
a whole. For every `TuneKey` exercised there, establish all of the following:

1. The key still names the same operation and the stored `TuneParam` fields have the same meaning.
2. The generated device and communication code reachable from that operation is unchanged in any
   way that could alter the best candidate.
3. Candidate enumeration, launch construction, and policy availability are unchanged.
4. The performance-relevant environment is equivalent: accelerator model and partitioning,
   compiler and code-generation options, driver/runtime, communication stack and routing, rank
   placement, topology, tuning controls, and representative operating conditions.
5. Every changed path that is exercised but intentionally receives a new key is warmed and tuned
   before the measured series.

The test asks whether the tuning problem changed, not whether a fresh cache would be byte-for-byte
identical. Timing noise can select a different near-tied candidate even when the problem is
equivalent.

### Changes that can justify reuse

Reuse across a Git mismatch is justified when the audit closes every path above. Typical examples
are:

- comments or documentation that are not build or code-generation inputs and cannot affect
  source-location-dependent behavior;
- tests, examples, disabled features, or unbuilt files unreachable from the declared workload;
- formatting or refactoring for which the relevant generated code, key construction, candidate
  space, and launch semantics are shown to be unchanged;
- a change confined to a kernel family that the benchmark does not exercise; or
- a changed operation that provably receives new keys while all reused entries remain unchanged.

A host-only change is not automatically safe. Host code can select a different tunable, construct
its key or arguments, change overlap and ordering, or alter which kernels execute.

### Changes that require replacement or a fresh cache

Do not reuse an affected row after a change to any of the following unless equivalence is
independently demonstrated:

- a kernel, functor, template, inline helper, generated source, or device-code option on the
  measured path;
- `TuneKey`, `TuneParam`, cache serialization, tuning controls, candidate enumeration, launch
  construction, or policy-selection code;
- compiler, optimization or architecture flags, JIT configuration, relevant build options, or
  runtime/driver components that can change generated code;
- accelerator model, MIG or analogous partitioning, a materially different enforced clock or
  power policy, or another hardware condition that can change the optimum; or
- communication implementation, library, transport, topology, process placement, P2P, GDR, or
  NVSHMEM behavior relevant to a tuned policy.

Also use a fresh cache when the affected keys cannot be bounded with confidence. At the observed
revision, QUDA exposes a read-only cache map and no supported interface for deleting or retuning a
selected on-disk entry. Manual TSV surgery is format-sensitive and is not a handbook-supported
selective-invalidation method. A naturally new key can be added to a copied cache; an affected
unchanged key requires a fresh cache unless a future QUDA revision supplies a supported selective
replacement mechanism.

## Controlled cross-build reuse workflow

1. Freeze the benchmark workload, measured region, correctness checks, and performance acceptance
   threshold. Preserve the source cache immutably with its header, checksum, producing software
   and build identity, machine and accelerator identity, runtime and communication environment,
   decomposition, and tuning controls.
2. Work from a copy in an isolated writable `QUDA_RESOURCE_PATH`. Do not let concurrent jobs write
   the same cache; QUDA's source notes that its exclusive lock-file method is not robust on Lustre
   without filesystem `flock` support.
3. Audit the old-to-new source and build difference against the key set and measured call path.
   Use `QUDA_ENABLE_TRACE=2` during a production-shaped diagnostic run when an execution inventory
   is needed: level 2 records every `tuneLaunch` call and its key. Disable trace for the measured
   series because tracing is diagnostic work.
4. If the header differs and the audit establishes equivalence, set
   `QUDA_TUNE_VERSION_CHECK=0`, record the waiver and its evidence, and run a complete
   production-shaped warmup with tuning enabled. Missing or intentionally new keys will tune and
   join the copied cache.
5. Run the same warmup again. Require no `Tuned ...` diagnostics, no new cache rows, and no
   correctness failure before starting the benchmark. Active multi-GPU tuning can perturb binary
   reproducibility, so complete the tuning run before the measured series.
6. Remove diagnostic tracing, freeze the warmed cache and environment, and verify that the
   measured series performs no autotuning. Keep tuning enabled: at the observed revision,
   `QUDA_ENABLE_TUNING=0` skips cache loading and uses default launch parameters rather than
   reusing a complete cache. Use application timers or a current-run profiler for benchmark
   evidence. If any compatibility question remains open, stop and build a fresh cache.

If a cross-build cache gains even one new row, QUDA writes the entire combined map with the
current header. Old rows then appear beneath the new build identity even though they were
not retuned. Preserve the immutable source cache and external provenance record so this
rewrite does not erase the cache's lineage.

## Tunecache timing is not current-run timing

Each stored row carries the time measured when that row was tuned. Cache hits increment a call
counter but do not update the stored time. QUDA's `profile*.tsv` reports are first-order estimates
formed from cached time multiplied by current call count, and full trace records likewise carry
the cached time. After cross-build reuse, these files can contain stale timing estimates even
when the selected parameters remain optimal.

**Per-call stability across trials that share a cache is a signature of that sharing, not of
measurement precision.** Two runs reporting the same per-call time for a key are reporting the
same stored number, and will do so however much their actual execution differed.

Use a level-2 trace as a key and execution-order inventory, not as proof of present performance.
Base a benchmark comparison on measurements made by the current run, with tunecache population
outside the measured region.

## Evidence limits

This page is a source-level analysis of QUDA at the observed revision, not a runtime validation on
every supported accelerator and communication backend. Key examples are representative rather
than exhaustive because individual tunables construct their own auxiliary strings. Recheck the
implementation before relying on selective invalidation, cache-format details, or environment
variables in a later QUDA revision.
