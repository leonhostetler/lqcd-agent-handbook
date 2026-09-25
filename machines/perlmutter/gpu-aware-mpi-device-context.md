---
title: GPU-aware MPI holds a context on ordinal 0 in every multi-node job on Perlmutter
summary: In a job spanning nodes, GPU-aware Cray MPICH creates a CUDA context on each rank's current device at MPI_Init; with all devices visible that is ordinal 0, so every rank but the first on a node leaves about 416 MiB there for the life of the job. Budget ordinal 0 for it. A constructor preloaded into the process, selecting the device before MPI_Init, removed it at two nodes with no measured cost, but that remedy is untested at scale and is not the recommended path.
scope: [machine:perlmutter]
load_when: Budgeting device memory for a multi-node GPU job on Perlmutter, reading a per-ordinal memory asymmetry in telemetry, deciding whether to select the device before MPI initialisation, or attaching a preload to a launched rank.
evidence: experiment
sources:
  - operator's screened diagnostic-rig records
observed: "2026-09-25"
observed_on:
  machine: perlmutter
  node_type: gpu-a100-40
  toolchain:
    cray-mpich: "9.1.0"
    cuda: "13.2"
    nvidia-driver: "580"
---

# GPU-aware MPI holds a context on ordinal 0 in every multi-node job on Perlmutter

A multi-node GPU job on Perlmutter that leaves every device visible — which QUDA requires
([`../../software/quda/internals/rank-placement.md`](../../software/quda/internals/rank-placement.md))
— starts with device `0` of every node already holding one CUDA context per **sibling** rank,
before the application has allocated anything. At four ranks per node that is three contexts of
about `416` MiB, `1248` MiB in all, sitting on one device for the life of the job. A capacity
screen that prices every device at nominal capacity is wrong on ordinal `0` by that constant, and a
job that fits on three devices of four fails on the fourth by less than it.

## The mechanism, from four contrasts

`[experiment]` A 60-line probe with no lattice code, run at four ranks per node on two nodes,
with per-process device sampling at one-second period. Each leg moves one thing:

| Leg | What moved | Ordinal `0` | Ordinals `1`-`3` |
|---|---|---|---|
| no MPI at all | — | one process, its own context | one each |
| `MPI_Init` before device selection, GPU-aware MPI on | the order | **four processes**: the local rank plus three sibling ranks at about `416` MiB each | one each |
| device selection before `MPI_Init` | the order, reversed | one process | one each |
| `MPI_Init` first, GPU-aware MPI **off** | the transport | one process | one each |

So the context belongs to the GPU-aware transport, it is created during `MPI_Init`, and it lands
on whichever device is **current** at that moment — ordinal `0` when nothing has selected one.
The application adds nothing: the linked MILC/QUDA executable, run as a fifth leg, showed exactly
the probe's surplus on ordinal `0` and one process per device elsewhere.

**It appears only in jobs that span more than one node.** The same five legs on **one** node
showed one process per device in every leg and no surplus at all — a one-node job opens no fabric
endpoint, and the transport context comes with the endpoint. A one-node rig therefore cannot see
this, and a null result from one is not evidence against it.

**GPU-Direct RDMA does not change it.** With `QUDA_ENABLE_GDR=1` the arrangement is identical:
three sibling contexts on ordinal `0`.

## Budget it; removal is measured at two nodes and untested at scale

**Budgeting is the recommended approach.** It costs nothing, changes nothing about how the job
runs, and its assumption is checkable from the first telemetry sample. On every multi-node job
launched with GPU-aware MPI and open visibility, price ordinal `0` at

```text
capacity - (ranks per node - 1) x 416 MiB
```

and treat the first telemetry sample as the check: it should show ordinal `0` above its siblings
by about that amount before any lattice work. A first sample that does **not** show the asymmetry
means the launch arrangement is not the one the budget assumed — which is itself worth knowing.
The memory leaf's Perlmutter advisory band was fitted to a whole-device gap that, on the sampled
node's ordinal `0`, plausibly contained this term `[inferred]`; the band is not a substitute for
budgeting it explicitly on the device that carries it.

**Removing it is possible, and is not yet recommended.** Selecting the rank's own device
**inside the process, before `MPI_Init`** puts the transport's context on that device, one per
rank, where it costs nothing extra. The recipe below did exactly that at two nodes. **It has not
been run at scale**, and at production volume the transport context on device `0` is doing real
work under GDR for three sibling ranks, so the two-node timing null bounds nothing there. Until a
production-scale run has measured it, prefer the budget above and treat the recipe as a measured
option to be trialled deliberately, on its own, as a launch change that starts a new measurement
population. Turning GPU-aware MPI off also removes the term, and is not a remedy at all: it
changes the halo path for the whole run, against the default in
[`../../software/quda/runtime-environment.md`](../../software/quda/runtime-environment.md).

### The measured remedy: a preloaded constructor, untested beyond two nodes

`[experiment]` A shared object whose constructor runs before `main` — return unless both
`SLURM_LOCALID` and `SLURM_PROCID` are set, then `cudaSetDevice(SLURM_LOCALID mod device count)`
— loaded with `LD_PRELOAD` into a MILC/QUDA rank, makes the rank's device current before
GPU-aware Cray MPICH initialises. Measured at two nodes, eight ranks, with GDR on: one application
process per device, ordinal `0` no longer carrying the sibling contexts, iteration counts
identical, and solve times inside the `1.5` percent repeat spread of the unshimmed legs over
`24` CG solves, twice — the shim neither helped nor cost anything resolvable. QUDA's own device
selection later in `initQuda` derives the same per-host ordinal and agrees with the preselection,
so there is no conflict and no affinity change. `cudaSetDevice` alone creates no context.

```c
/* preselect-device.c: choose this rank's CUDA device before main(), hence before MPI_Init.
 * Loaded with LD_PRELOAD; no change to the application, QUDA or MPI.
 * Does nothing unless SLURM_LOCALID and SLURM_PROCID are set, never aborts, and prints
 * exactly one line to stderr so a log can prove it ran for every rank. */
#include <cuda_runtime.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

__attribute__((constructor)) static void preselect_device(void) {
  const char *lid = getenv("SLURM_LOCALID");
  const char *pid = getenv("SLURM_PROCID");
  if (!lid || !pid) return;
  int dev = atoi(lid), count = 0;
  if (cudaGetDeviceCount(&count) != cudaSuccess || count <= 0) {
    fprintf(stderr, "preselect-device: rank %s localid %s: no devices visible, doing nothing\n", pid, lid);
    return;
  }
  dev %= count;
  cudaError_t e = cudaSetDevice(dev);
  fprintf(stderr, "preselect-device: rank %s localid %s -> cudaSetDevice(%d) %s (pid %ld)\n",
          pid, lid, dev, e == cudaSuccess ? "ok" : cudaGetErrorString(e), (long)getpid());
}
```

Build it as a position-independent shared object against the CUDA runtime of the toolkit the
application uses — with the toolkit module loaded, the shape is `cc -shared -fPIC -o
libpreselect-device.so preselect-device.c -lcudart` — and confirm with `ldd` that it resolves the
same `libcudart` major version as the application before relying on it. Record its checksum
beside the run like any other input.

**Attach it inside the per-task wrapper, never as an environment prefix on the launcher.**
Prefixed on `srun`, the launcher process inherits the preload together with the batch step's
`SLURM_LOCALID=0`, and the constructor's `cudaSetDevice(0)` creates a `416` MiB primary context
on ordinal `0` of the node the launcher runs on, held for the job — a bystander that is not an
application rank and that the rig which measured the remedy showed exactly. Exporting
`LD_PRELOAD` inside the wrapper the launcher executes gives it only to the ranks. Short-lived
`12` MiB entries on every device from launch helpers appear too and vanish within a sample; they
are not this.

**Two verification signals, both cheap.** The first telemetry sample shows no ordinal-`0`
asymmetry, and per-process device sampling shows one application pid per device. The
constructor's one stderr line per rank proves it ran; it does not prove where the context landed.

## Scope, and what is not claimed

Perlmutter A100 nodes, Cray MPICH `9.1.0` with GPU support on, CUDA `13.2`, driver `580`, at four
ranks per node. The size is a measurement at that toolchain and will move with the runtime; the
mechanism — a GPU-aware transport initialising on the current device before the application
selects one — is expected wherever visibility is left open and the transport behaves the same,
and is not claimed for any other machine until measured there.

The timing null for the preload is a two-node result at a small local volume, where the
ordinal-`0` transport context has little to do; at production volume, where a device `0`
transport context would serve three sibling ranks' buffers under GDR, the effect is unmeasured
in either direction — which is why budgeting, not removal, is the recommendation of this leaf.
Adopting the preload is a launch change: it starts a new measurement population, is trialled on
its own rather than bundled, and is not to be slipped into a campaign that has ruled launch
changes out.
