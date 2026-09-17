---
title: QUDA device memory, pooled reuse, and what the counters miss
summary: Why QUDA's device-memory counter is neither an upper nor a lower bound on what the driver holds, the three allocator behaviours behind that, and what each one costs to recover.
scope: [software:quda]
load_when: Sizing or diagnosing QUDA device memory, reconciling a measured high-water mark against a computed field total, deciding whether a memory saving is recoverable, or changing how a deflation space or gauge tower is allocated.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/targets/cuda/malloc.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/gauge_field.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/include/quda_ptr.h
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/solver.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/eigensolve_quda.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/color_spinor_field.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/check_params.h
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/interface_quda.cpp
  - operator's screened memory-model records
observed: "2026-09-17"
observed_on:
  software:
    quda:
      commit: f2df42ac4caa0cd51b96b01006a1c25c8d753425
      branch: develop
---

# QUDA device memory, pooled reuse, and what the counters miss

[`../solvers/staggered-memory.md`](../solvers/staggered-memory.md) treats `Device memory used`
as the measured quantity that a computed field total is checked against. That comparison has two
systematic corrections, they run in **opposite** directions, and neither is an error in the field
formulas:

- the pool can charge a live allocation far more than it requested, which the counter **includes**
  and a field total does not; and
- every allocation is rounded up to the driver's granularity, which the counter **excludes**
  because it records requested bytes.

So the counter is neither an upper nor a lower bound on what the driver is holding. A capacity
decision taken at a tight margin must say which of these two it has corrected for, and in which
direction.

## Pooled reuse charges the caller the whole block

`quda::pool` serves a device request from the smallest cached block that fits and then charges the
caller that block's **full size**, with no bound on the mismatch
(`lib/targets/cuda/malloc.cpp`):

```cpp
auto it = deviceCache.lower_bound(nbytes);
if (it != deviceCache.end()) {   // sufficiently large allocation found
  nbytes = it->first;            // the caller is charged the whole block
  ptr = it->second;
  deviceCache.erase(it);
}
```

A free never returns memory to the driver. `device_free_` inserts the block back into
`deviceCache` keyed by its size, and nothing in that path calls the driver's free. The pinned pool
has the identical `lower_bound`-then-`nbytes = it->first` shape a few lines above, so this is a
property of the allocator rather than of one memory kind.

**The two combine into waste that no flush can reach.** A small request that arrives while a large
block is cached takes the large block, and the excess is then inside a **live** allocation:
`flushPoolQuda` walks the *cache*, so it cannot see it, and the memory is not released until the
owning field is destroyed. For a field that lives for the job — a resident gauge tower, for
instance — that is `endQuda`.

The shape to look for is **a small, frequently allocated object requested just after a large one
was freed.** Every native gauge field with `ghostExchange == QUDA_GHOST_EXCHANGE_PAD` allocates its
own per-dimension ghost arrays through this same pool (`lib/gauge_field.cpp`, via `quda_ptr`,
which pools by default — `include/quda_ptr.h`), and those arrays are orders of magnitude smaller
than the extended gauge fields a link build leaves in the cache on its way out. A link build
followed by a gauge load is therefore the canonical instance, not a special case.

**It is invisible in the counter, which is the reason it survives review.** `Device memory used`
tracks block sizes, so a run in which this happens is perfectly self-consistent with itself and
merely disagrees with the field arithmetic.

## What recovers it, and what only appears to

- **A pool flush at the right point recovers it.** `flushPoolQuda(QUDA_MEMORY_DEVICE)` is public
  API inside `quda.h`'s `extern "C"` block, so an application can call it without a QUDA change.
  Place it after the **last** producer of the large blocks and before the consumer that would take
  them: flushing between two producers is correct and pointless, because the second producer simply
  reuses what the first left.
- **Bounding the reuse mismatch recovers nothing on its own.** Refusing an oversized block does not
  free it. What bounding does is convert *trapped* waste into *reclaimable* cache, which is a real
  improvement only when it is paired with a flush or with sacrificing the refused block. A proposal
  to bound reuse that does not say which of those it pairs with has not yet saved anything.
- **Disabling the pool is a different lever with its own cost.** It removes the trapping by removing
  the reuse, so every allocation goes to the driver. Price it as a throughput change and measure it,
  rather than treating it as a free memory remedy.

**A modelled saving in a pooled object is an upper bound, not a prediction.** Where the pool may
recycle the blocks a change was meant to free, the change can return less than its arithmetic says
— down to nothing — because what it frees is immediately claimed. Say so when quoting such a
saving, and confirm it against a measured high-water before spending headroom on it.

## Deflation spaces pay allocation granularity, once per vector

`Solver::constructDeflationSpace` builds the space as `n_conv` **independent**
`ColorSpinorField` allocations (`lib/solver.cpp`, `resize(evecs, param.eig_param.n_conv, csParam)`),
and the MILC-facing load paths do the same. Each allocation is rounded up to the driver's
allocation granularity, and an eigenvector is rarely a multiple of it.

The cost per resident parity is

```text
n_conv * (ceil(bytes / granularity) * granularity - bytes)
```

which averages about half a granule per vector for an arbitrary local volume and approaches a full
granule in the worst case. `[observed]` On one CUDA system the granularity was measured at 2 MiB;
treat that as a property of the driver to re-measure, not as a QUDA constant, because nothing in
QUDA's source fixes it.

**This one is invisible in the other direction:** QUDA reports the bytes it requested, so the
rounding appears in neither the counter nor the field arithmetic, only in what the device has left.
Its size scales with the *vector count*, so it matters for a large deflation space and is
negligible for a handful of fields.

**QUDA already carries the mechanism that avoids it.** A composite `ColorSpinorField` makes exactly
one allocation for the whole set and hands out `QUDA_REFERENCE_FIELD_CREATE` views into it
(`lib/color_spinor_field.cpp`). It is live code, not vestigial — GMRESDR uses it for its Krylov
basis and `newDeflationQuda` for its Ritz space — so a slab is a supported pattern in this codebase
rather than a novel one.

## `computeEvals` grows the eigenvector array and never trims it

`EigenSolver::computeEvals` needs somewhere to put `A·v`, so it grows `evecs` by
`compute_evals_batch_size` (`lib/eigensolve_quda.cpp`):

```cpp
if (size + batch_size > static_cast<int>(evecs.size())) resize(evecs, size + batch_size, QUDA_NULL_FIELD_CREATE);
```

It never shrinks back. `Solver::destroyDeflationSpace` then `std::move`s the oversized array into
the preserved `deflation_space`, so the extra vectors are held for the life of the job.

**The signature is in the run's own log.** `destroyDeflationSpace` logs
`Preserving deflation space of size <n>` at `QUDA_VERBOSE`, and `<n>` is
`n_conv + compute_evals_batch_size` rather than `n_conv`. QUDA's own default batch size is 4
(`lib/check_params.h`); the MILC interface passes the application's value straight through, so the
inflation is whatever the caller asked for. The cost is `batch_size` eigenvectors per resident
parity, held from the moment `computeEvals` returns.

**This reproduces on any deflated solve with `preserve_deflation` set.** It needs no particular
application or decomposition.

**The obvious one-line repair is wrong.** Trimming to `n_conv` before returning destroys live
Krylov vectors: every deflated Krylov solver on this revision — CG, PCG, GCR, CA-CG, CA-GCR,
BiCGStab and BiCGStab(l) — calls `computeEvals` with the **Krylov** space, which is legitimately
larger than `n_conv`. The safe form records `evecs.size()` on entry and shrinks back to that on
exit, which is a no-op for every caller that did not need the grow. `recompute_evals` may
legitimately call it again, which simply re-grows it.

## If you change how either is allocated

- **The two are coupled, in one direction.** A slab-backed deflation space and the `computeEvals`
  grow are incompatible: the grow appends *owning* fields and breaks the invariant that every
  vector lives in the slab. Either land the trim first, or size the slab to cover
  `n_conv + compute_evals_batch_size` so the grow condition is never true. The second costs one
  batch of vectors and touches no eigensolver code.
- **Prefer reference views to a type change.** Keeping one owning allocation plus `n` fields
  created with `QUDA_REFERENCE_FIELD_CREATE` leaves every consumer unchanged, because a reference
  field is a `ColorSpinorField` like any other. Adopting the composite *type* instead ripples into
  every consumer that holds the space by value, moves it, or slices it.
- **Ownership plumbing is where the risk is, not the arithmetic.** The slab must travel with every
  `std::move` of the vector array through construction, destruction, injection and extraction, or
  the fields dangle.
- **Chunk the slab rather than taking it whole.** A single very large contiguous request can fail
  on a fragmented device where many small ones succeed. Chunks of order a gigabyte recover nearly
  all of the rounding while keeping every request to a size the driver handles routinely.
- **The load path and a genuine eigensolve are not the same problem.** With eigenvectors read from
  file the space is created once at `n_conv` and never resized. An eigensolve resizes the Krylov
  space more than once and reorders it by swapping elements, which wants a test rather than an
  argument. Land the load path first.

Treat any of these as a source trial under [`../development.md`](../development.md): they change
allocation shape, so they re-tune the affected keys and need the iteration-count invariant checked.

## Evidence limits

Every mechanism above was read in the source at the revision in `observed_on` and is present in
upstream `develop`, not only on a feature branch. **This leaf records mechanisms, not magnitudes.**
What any of them costs in a particular run is a property of that run's geometry, vector count and
driver, and belongs in that run's working directory. The one measured quantity quoted — the 2 MiB
allocation granularity — is labelled `[observed]` because it came from a single system and is not a
QUDA property at all.

The allocation-granularity and pooled-reuse terms have not been separated by experiment here: they
were derived from the source and from a reconciliation between computed field totals and measured
high-water marks, which cannot attribute a residual to one of them alone.
