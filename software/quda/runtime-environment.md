---
title: Runtime environment a MILC-driven QUDA job carries by default
summary: The environment variables a MILC/QUDA job sets unless the operator says otherwise, why each one, the machine exceptions, the rule that a run records every entry set or deliberately unset, and why GDR is verified from the tunecache keys rather than from QUDA's announcement line.
scope: [software:quda, software:milc]
load_when: Writing or reviewing the environment block of a MILC/QUDA launcher, diffing a launcher against a stack record, verifying that GPU-Direct RDMA or peer-to-peer was actually in force, or comparing two runs whose environment may differ.
evidence: operator
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/communicator_quda.h#L484-L495
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/communicator_quda.h#L193-L258
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/communicator_quda.h#L595-L596
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/communicator_quda.h#L619-L634
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/communicator_quda.h#L703
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/communicator_qmp.cpp#L177
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/communicator_mpi.cpp#L115
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_policy.hpp#L2038-L2041
  - operator's screened runtime and launcher records
observed: "2026-09-25"
observed_on:
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# Runtime environment a MILC-driven QUDA job carries by default

A MILC/QUDA job is configured by environment variables that appear in no input file, no
multigrid parameter file and no build option. Each one has a silent failure mode when it is
omitted: a default that is the slow or expensive end, a value inherited from a site module and
never recorded, a thread count that quietly starves the node. The stack records carry these
values piecemeal, and one that is silent on a variable gives a launcher author nothing to diff
against — a campaign ran several large trials with GPU-Direct RDMA off for exactly that reason,
because the nearest stack record had no row to fire on.

**This leaf states the defaults in one place.** `[operator]` Unless the operator specifies
otherwise for a run, a MILC-driven QUDA job sets:

| Setting | Default | Reason and scope |
|---|---|---|
| `QUDA_ENABLE_GDR=1` | on | GPU-Direct RDMA: QUDA hands device buffers to GPU-aware MPI instead of staging every inter-node halo through pinned host memory. **QUDA's own default is off** — `[source]` the flag is read once and enables GDR only when the string is exactly `1`. On for most systems; **a machine may be the exception**, so record the machine's own verdict in its profile or validated stack rather than assuming either way |
| `MPICH_GPU_SUPPORT_ENABLED=1` | on | GPU-aware Cray MPICH. Set on every Cray MPICH system in this catalogue. **Export it explicitly rather than inheriting it from a site module**, so the run's own record carries it; a value that arrived through `module load` is invisible to a reader of the launcher |
| `QUDA_MILC_HISQ_RECONSTRUCT=13` and `QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9` | always, both | The established pair. Unset means `18`, the most expensive storage, and the sloppy partner inherits the outer value when unset, so setting one is not half of setting both. [`internals/milc-gauge-reconstruct.md`](internals/milc-gauge-reconstruct.md) owns the mechanism |
| `QUDA_ENABLE_P2P` | **leave unset** | QUDA then chooses its best peer-to-peer arrangement: `[source]` copy engines and direct load/store both enabled, and with GDR on the non-peer-to-peer policies disabled as well. **State explicitly that unset is the deliberate choice**, not an omission. Machine exception: the validated Frontier stacks set `QUDA_ENABLE_P2P=0`, because the cited MILC notes report incorrect halo exchange and crashes with peer-to-peer enabled on the ROCm versions tested there; that value is part of those stacks' validated environment and is not a default elsewhere |
| `OMP_NUM_THREADS` | `16` | `[operator]` Provided **more than** `16` CPUs are requested per rank, which leaves headroom for system processes. In one recent controlled observation, performance dropped materially when the requested CPUs per rank **equalled** `OMP_NUM_THREADS` and recovered when the CPU request per rank was raised above it. This is a **distinct rule from the binding arithmetic** in [`../../conventions/batch-scripts.md`](../../conventions/batch-scripts.md), which concerns the wrapper's CPU indices and the hardware-thread multiplier; both bind. The magnitude is unquantified and must not be quoted as a number |
| `QUDA_DETERMINISTIC_REDUCE` | **leave unset** | `[source]` Read once; `1` selects deterministic reductions. A debugging option with a negative performance effect. Set it only for a declared determinism check, and record it either way |
| `MPICH_ENV_DISPLAY=1` | on, in MPICH environments | `[operator]` Logging practice, not a performance setting: Cray MPICH then prints the MPICH environment settings in force at initialisation into the job's own output, which is what makes a variable inherited from a site module — `MPICH_GPU_SUPPORT_ENABLED` above being the usual one — visible in the run's record rather than only in the module it came from |
| `MPICH_OFI_NIC_VERBOSE=2` | on, in MPICH environments | `[operator]` Logging practice: Cray MPICH prints its per-rank network-interface selection, so the interface binding the launch wrapper requested can be confirmed from the log rather than assumed. Costs a few lines of output per rank at start-up and nothing thereafter |

**Read the validated stacks' thread rows against that rule before copying one.** Most record
`OMP_NUM_THREADS: 16` at `32` CPUs per rank, which satisfies it. One Perlmutter stack records
`32` threads at `32` CPUs per rank — the equal case. That record validated correctness on a tiny
lattice and is not invalidated by the rule, but a performance run must not copy its thread pair.

## A run records every entry, set or deliberately unset

A launcher exports every row above, or states in its own provenance record that a row is
deliberately unset, and the run's execution manifest carries the value in force for each.
"Unset" and "not recorded" are different states: the first is a decision a reader can check,
the second is the omission this leaf exists to prevent. Stack records carry the same rows under
`runtime:` so that a launcher diffed against a stack has something to fire on, and a stack whose
validation run did not record a variable says so rather than leaving the row absent.

Recording is what makes a comparison between two runs honest. Every setting above changes
memory, communication path or arithmetic, so two runs that differ in one of them are not a
matched pair, and a difference that was never recorded cannot be found afterwards.

## Verify GDR from the tunecache keys, never from QUDA's announcement line

The natural check — grep the log for `Enabling GPU-Direct RDMA access` — is wrong under the
communicator backend every validated MILC stack in this catalogue uses, and it is wrong in the
direction that reads as *GDR off*.

`[source]` In `comm_peer2peer_init`, every message gated on rank `0` — `Enabling GPU-Direct RDMA
access`, `Disabling GPU-Direct RDMA access`, and all the `Enabling peer-to-peer ...` and
`Disabling peer-to-peer ...` variants — tests the `Communicator::rank` **data member**, not
`comm_rank()`. That member is initialised to `-1`. The **QMP** backend never assigns it: its
`comm_rank()` reads the QMP node number directly, so `rank` stays `-1` and none of those lines can
print, at any verbosity, whatever the setting. The **MPI** backend does assign it, through
`MPI_Comm_rank`, so the same lines print there — which is why the omission is easy to carry from
one build to another unnoticed. The ungated `Peer-to-peer enabled for rank ...` lines from the same
function print normally under QMP, so a reader sees the initialisation happen and the announcement
missing, and concludes GDR was off.

**What does confirm it.** The tunecache config string is built from the same `comm_gdr_enabled()`
and stamped on every multi-GPU dslash *policy* key:

```text
,p2p=<N>,gdr=<0|1>,nvshmem=<0|1>
```

`gdr=1` is the setting itself. `p2p=7` rather than `p2p=3` is a second, independent witness: the
value is the enabled-feature mask, `3` by default, and `4` is added **only through the GDR branch**,
so `7` is unreachable with GDR off. A cold-cache run writes these keys by its first solve; read the
run's own tunecache and record what it says in the execution manifest.
[`internals/autotuning.md`](internals/autotuning.md) owns the key structure.

`[experiment]` Confirmed on a two-node rig with GDR off and on, twice each: the off legs carry
`p2p=3,gdr=0` on every policy key, the on legs `p2p=7,gdr=1`, and no leg carries the announcement.
Two large GDR-on logs from a separate campaign carry none either.

**Actionable consequence.** A launcher that gates on the announcement line either aborts a correct
run or, more likely, records zero and lets a reader conclude the setting failed; one diagnostic
rig labelled six valid legs indeterminate on exactly that gate. Verify `QUDA_ENABLE_GDR` and
`QUDA_ENABLE_P2P` from the `gdr=` and `p2p=` fields of the tunecache keys, and state the backend
when reporting, so a reader on an MPI-backend build understands why their log does carry the line.
Upstream, the gates should call `comm_rank()`.

## What GDR is worth, as far as it has been measured here

`[experiment]` One measurement exists: on a two-node, eight-rank staggered CG problem at a small
local volume, `QUDA_ENABLE_GDR=1` ran of order ten percent faster than off, in two repeats and two
iteration classes, against a repeat spread of about one and a half percent. That is a lower-bound
class datum at a volume where little of the halo crosses the fabric, not the large-lattice
number; do not quote it as the effect at production scale.

## Scope and evidence

The default table is operator policy from experience across the machines in this catalogue,
including one recent controlled observation on the thread rule; it is not a measured optimum
for any workload, and every stack record remains canonical for what its own validation run set.
The GDR default, the P2P mask, the deterministic-reduce flag, the announcement gates and the
tune-key config string are read from the QUDA source at the observed revision. The dead-code
finding is invalidated by an upstream change that assigns `Communicator::rank` in the QMP backend
or gates the messages on `comm_rank()`; re-check the cited lines before relying on it at another
revision.
