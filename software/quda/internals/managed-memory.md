---
title: QUDA managed memory and the prefetch gate
summary: Why memory obtained through the MILC-facing qudaAllocateManaged entry point is structurally excluded from QUDA's managed-memory prefetch, what that costs, and the profile signature that identifies it.
scope: [software:quda]
load_when: A QUDA run reports non-zero managed memory, a device-to-device copy runs far below device bandwidth, or a profile carries unified-memory migration events.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/cuda/malloc.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/targets/hip/malloc.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/color_spinor_field.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/gauge_field.cpp
observed: "2026-09-15"
observed_on:
  software:
    quda: {commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a, branch: develop}
---

# QUDA managed memory and the prefetch gate

QUDA reaches managed memory by two independent routes, and only one of them can be
prefetched. Which route a run used is not visible in the profile and is easy to
misattribute, because both report the same non-zero `Managed memory used` line.

## Two routes in, one gate

`use_managed_memory()` is QUDA's own allocator mode. It is false unless
`QUDA_ENABLE_MANAGED_MEMORY=1`, and when it is true it routes **every**
`device_malloc` through `managed_malloc_`, printing `Using managed memory for CUDA
allocations` as it does so. The absence of that warning from a run log is therefore
positive evidence that this route was not taken.

`qudaAllocateManaged` is the second route: a MILC-facing entry point declared in
`include/quda_milc_interface.h` — *"Allocate managed memory to reduce CPU-GPU
transfers"* — whose body is exactly `return managed_malloc(bytes)`. An application
calls it directly, and it is unaffected by `QUDA_ENABLE_MANAGED_MEMORY`.

**The prefetch gate reads only the first route.** `is_prefetch_enabled()` returns
false unless `use_managed_memory() || use_qdp_managed()` is true, and only then does
it consult `QUDA_ENABLE_MANAGED_PREFETCH`. Setting that variable alone therefore does
nothing at all. Since `managed_malloc_` prefetches only `if (is_prefetch_enabled())`,
and the field-level prefetches in `color_spinor_field.cpp` and `gauge_field.cpp` are
gated the same way, **memory obtained through `qudaAllocateManaged` can never be
prefetched unless the application also converts every QUDA device allocation to
managed.** The two are independent choices in the interface and a single switch in the
implementation.

The HIP target carries the same structure, so the gate is a portability-neutral
property of QUDA rather than a CUDA accident.

## What it costs, and the signature that identifies it

Unprefetched managed memory is not slow in proportion to its size; it is slow in
proportion to how much of it the device touches without it being resident. The cost
appears where the source pages are faulted in, which is **not** where the application
thinks the transfer is.

The signature in a trace is specific enough to diagnose without counters:

- a **device-to-device** copy running one to three orders of magnitude below device
  bandwidth, while other copies of the same kind run at full rate;
- **unified-memory migration events** — many of them, at page granularity — lying
  *inside* those slow copies' intervals rather than beside them;
- the migration direction is **host-to-device**, because the managed end was not
  device-resident.

**Split the direction by the memory residency of its two ends; that is the
discriminator, and it needs no size matching.** `[experiment]` A copy's `copyKind` says
device-to-device while `srcKind`/`dstKind` say which end is managed, and the two
populations separate completely: the copies whose **destination** is managed are the slow
ones, and the copies whose **source** is managed run at full device rate. Measured on one
CUDA capture, one direction held a destination-managed population at single-digit GB/s and
a source-managed population of comparable total volume at over 3000 GB/s — a factor of
about 400 inside one `copyKind`, on one device, in one run. A rate difference that large is
not contention and not clock behaviour, and
[`../../../conventions/profile-metrics.md`](../../../conventions/profile-metrics.md) lists
neither as a cause of a spread that size.

This supersedes an earlier formulation that asked for *two copies of identical size*
differing by an order of magnitude, and grouping by size and by enclosing annotation
range. Both work and both are avoidable work: residency is one `GROUP BY` and it does not
require finding a matched pair. `gpu-profile-summary.py memcpy` reports the residency rows
beside the per-direction ones and names a split above an order of magnitude itself.

**A per-direction rate averages the two populations and is the misleading number.** This
is not a hypothetical: until 2026-09-15 the extraction read `copyKind` and `bytes` only, so
it reported one device-to-device row whose rate sat between the two populations and looked
unremarkable. The merged figure is a correct aggregate and the wrong quantity for this
question. Where a capture records no per-end memory kind — rocpd does not — residency is
reported **unavailable**, which is not the same as both ends being ordinary device memory.

**Zero user-prefetch migrations is the direct evidence that the gate never fired.**
`[experiment]` A migration event carries a cause, and the vendor vocabulary distinguishes a
page fault from a speculative prefetch from an explicit **user** prefetch. On a capture
whose managed memory arrived through `qudaAllocateManaged`, the user-prefetch cause was
absent from the profile entirely while the page-fault cause ran into the millions. That is
a profile-side test of the same conclusion the log-side test below reaches, and it is worth
having both: it is positive evidence about what the run did, not an inference from what the
run failed to print.

`Managed memory used` in a run's own end-of-run report establishes that managed memory
exists; only the absence of `Using managed memory for CUDA allocations` establishes
which route allocated it.

**Where a slow population is found, confirm the mechanism rather than stopping at the
rate.** Count the migration events lying inside one slow copy's own interval. On the
capture above, a single copy of a few hundred megabytes carried over seventeen thousand
host-to-device migrations covering more than 80% of its duration, and the migrated volume
matched the copy's payload — the whole destination buffer was being faulted in while the
copy ran. A rate split says the populations differ; only the enclosed migrations say why.
See [`../profiling.md`](../profiling.md), which owns the name-resolution rules.

## What follows for a suggestion

Setting `QUDA_ENABLE_MANAGED_MEMORY=1` and `QUDA_ENABLE_MANAGED_PREFETCH=1` together is
the only combination that turns the gate on, and it is not a targeted change: it
converts every QUDA device allocation to managed memory, which on a run already near
device-memory capacity is a different experiment rather than a fix. The targeted
changes are a QUDA source change decoupling `is_prefetch_enabled()` from
`use_managed_memory()`, or having `qudaAllocateManaged` issue its own prefetch; or an
application change that stops routing those fields through managed memory. All three
are tuning-mode actions and none is validated here.

**This leaf records a mechanism, not a measurement.** How much any particular run loses
to it is a property of that run and belongs in its working directory. The magnitudes quoted
above are there to make the signature recognisable — the shape of the split and its rough
order — and not as expected values for any other run.

**The source reading and the empirical confirmation are at different revisions.** The gate
described above was read in the source at the commit in `observed_on`. The `[experiment]`
figures were measured on a CUDA capture whose build was configured from a different revision
(tunecache descriptor `1.1.0-3ada421b8-sm_100`, CUDA 13.1). They therefore corroborate the
mechanism across two revisions rather than confirming it at the one the source was read at,
and neither establishes the other: re-read the gate before relying on it in a third.
