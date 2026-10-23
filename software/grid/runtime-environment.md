---
title: Grid runtime flags, GPU binding, communication and device memory
summary: How Grid parses its command-line flags, selects a GPU, groups ranks on a node, passes halos to MPI, budgets device memory, and which local lattice extents a decomposition may use.
scope: [software:grid]
load_when: Launching any Grid-based program (Grid tests, Hadrons, HadronsMILC), choosing --mpi/--shm/--device-mem, binding GPUs, or diagnosing a start-up hang, a layout assert, or device out-of-memory.
evidence: source
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/util/Init.cc#L111-L142
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/util/Init.cc#L196-L375
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/threads/Accelerator.cc#L20-L104
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/Communicator_base.cc#L36
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/Communicator_mpi3.cc#L46-L83
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/Communicator_mpi3.cc#L420-L505
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/SharedMemoryMPI.cc#L183-L319
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/SharedMemory.cc#L71-L111
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/allocator/MemoryManager.cc#L89-L147
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/allocator/MemoryManagerCache.cc#L254-L268
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/cartesian/Cartesian_red_black.h#L205-L216
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/cshift/Cshift_mpi.h#L69-L80
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/cshift/Cshift_mpi.h#L306-L328
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/log/Log.cc#L60-L107
  - https://github.com/paboyle/Grid/tree/3232b438f2cf729e515c185e2dbf29d7cc276bb7/Grid
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {cuda: "13.3", openmpi: "5.0.11"}
---

# Grid at run time

Labels: **[U+F]** upstream and fork (cited code identical on upstream `develop` 3232b438f, or
the cited part checked there); **[F]** fork-only (`milc-qcd` `feature/LMI-develop`). Line
numbers are at fork commit d67dd207. Every Grid-based executable, Hadrons and HadronsMILC
included, takes these flags after its own arguments.

## Flags are exact, separate tokens; unknown ones are ignored [U+F]

A flag matches only as its own argv entry, with its value in the next entry
(`Init.cc:130-142`): `--shm=2048` and misspelled flags are silently ignored. Confirm from the
start-up log that each flag took effect.

| Flag | Effect and default |
|---|---|
| `--grid X.Y.Z.T`, `--mpi a.b.c.d` | global lattice and rank grid; defaults 8.8.8.8 and 1.1.1.1 |
| `--accelerator-threads n` | `blockDim.y` of every device kernel (threads per block = lanes × n); default 8 |
| `--threads n` | OpenMP threads, capped at `OMP_NUM_THREADS` |
| `--shm M` | MiB of device memory per rank for the stencil comms buffer; default 1024 |
| `--shm-mpi 0\|1` | **default 1**: every halo, on-node ones included, goes through MPI |
| `--device-mem M` | MiB cap on the evictable device-field cache; default 80% of device memory |
| `--comms-overlap` | staggered and Wilson kernels compute the interior while halos are in flight |
| `--log list` | **replaces** the default `Error,Warning,Message`; always append to it |
| `--debug-stdout` | per-rank stdout/stderr files; non-zero ranks are otherwise silent |
| `--debug-signals` | backtrace handlers, installed only at the end of initialisation, plus floating-point traps (a NaN becomes SIGFPE) |
| `--shm-hostname-fallback 1` | **[F]** regroup ranks by hostname when MPI reports singleton nodes; `--enable-shm=nvlink` builds only |

`--comms-concurrent` and `--comms-sequential` are parsed nowhere; recipes that pass them get
no effect. Upstream has `--batched-solver-split`, which the fork lacks.

## One GPU per rank must be arranged outside Grid [U+F]

Every rank calls `cudaSetDevice(0)` (`Accelerator.cc:20-60`; see `build.md` on
`--enable-setdevice`), so it uses the first device it can see. Launch each rank through a
wrapper that sets `CUDA_VISIBLE_DEVICES` to one device, chosen from a local-rank variable the
launcher really sets per rank; without it every rank on a node shares device 0, with no error,
only slowdown or out-of-memory. Grid's own detection order for printing is
`OMPI_COMM_WORLD_LOCAL_RANK`, `MV2_COMM_WORLD_LOCAL_RANK`, then `SLURM_LOCALID`.

## Ranks on a node and the rank layout [U+F, except the fallback]

- The node group comes from `MPI_Comm_split_type(MPI_COMM_TYPE_SHARED)`; Grid asserts equal
  ranks per node. The log line `Node  communicator of size n` shows what MPI reported; a size of
  1 with several ranks per node means no on-node grouping (`--enable-shm` none, or MPI not
  reporting locality — the fork's `--shm-hostname-fallback 1` [F] works around the latter).
- Cartesian coordinates are **re-mapped** from (node, on-node rank), not taken from the MPI
  world rank: on-node ranks form a sub-block chosen greedily from dimension 0, which
  `GRID_SHM_DIMS_4=a.b.c.d` overrides (`SharedMemoryMPI.cc:213-319`). Do not infer neighbours
  from world ranks.

## Halos pass device pointers to MPI by default [U+F]

With the default accelerator-aware build, halos are `MPI_Isend/Irecv` on device buffers and
`Cshift` uses `MPI_Sendrecv` on device views (`Communicator_mpi3.cc:420-505`). The MPI library
must therefore be CUDA-aware; a non-aware MPI fails or corrupts data at the first exchange, not
at start-up. Grid initialises MPI at `MPI_THREAD_SERIALIZED` unless compiled with
`-DGRID_COMMS_THREADS` (no configure option sets it), and skips its own initialisation if MPI is
already up (`Communicator_mpi3.cc:46-83`). Code that calls the communicator from several threads
at once (`Benchmark_comms`'s threaded section) crashes under the default.

`--comms-overlap` runs the interior kernel between posting and completing the halo exchange.
Whether that wins depends on the MPI library progressing transfers while the host waits; measure
it rather than assume it.

## Device memory: what is allocated and what is reported [U+F]

Per rank, a `--disable-unified` build holds:

1. the comms buffer, `--shm` MiB, allocated at start-up and never freed;
2. the field cache, capped at `--device-mem` (default 80% of device memory). The cap counts
   only evictable views; open views are not counted (`MemoryManagerCache.cc:254-268`);
3. a cache of recently freed blocks (default 8 large, 16 small; `GRID_ALLOC_NCACHE_*`);
4. direct device allocations outside the memory manager.

So the default 80% leaves at most 20% for everything else, and a device can run out while the
`MemoryManager Cache … bytes` line looks safe; lower `--device-mem` when memory is tight. The
"accelerator Mbytes" counter is decremented when a block goes back to the free cache and
under-reports. A failed allocation prints ` cudaMalloc failed for <bytes>` and returns NULL,
which the memory manager does not check: treat that line as the cause of any later segfault.

`--shm` overflow prints `ShmBufferMalloc exceeded shared heap size -- try increasing with --shm
<MB> flag` and asserts. Every communicator reuses the same buffer from its start, so the size
needed is the largest single-communicator total, not a sum (inferred; it assumes one halo
exchange in flight at a time). Raise it only when that message appears.

## Which local extents a decomposition may use [U+F]

Both rules come from the SIMD layout. `GridDefaultSimd` assigns lanes in factors of two from the
last dimension down (`Init.cc:111-125`); at `gen-simd-width=64` a GPU build has 4 complex-double
lanes (layout 1.1.2.2) and 8 complex-single lanes (1.2.2.2).

- **Red-black grids need an even per-lane extent.** For every checkerboarded dimension with
  more than one lane, `GridRedBlackCartesian::Init` asserts `(_rdimensions[d] & 0x1) == 0`
  (`Cartesian_red_black.h:205-216`). Any program that builds a single-precision red-black grid
  — every mixed-precision staggered solve — therefore needs local extents in dimensions 1–3
  that are multiples of 4 on a 64-byte GPU build. An 8⁴ lattice on `--mpi 1.1.1.4` (local
  time extent 2) aborts at grid construction. For a global extent of 144 that excludes
  splitting a dimension 8, 16 or 24 ways; for 288, 16 or 32 ways. Observed once at 8⁴; the
  rule is in the source.
- **`Cshift` along a dimension that is both decomposed and split more than two ways in SIMD
  asserts** `simd_layout==2` (`Cshift_mpi.h:69-80, 326`). `GridDefaultSimd` never puts more than
  two lanes in one dimension, so only code that builds its own layout (for example a grid with
  all lanes in one dimension) can reach it; the assert names `Cshift_mpi.h`, not the caller.

## Start-up order, for locating a hang [U+F, except the fallback]

`acceleratorInit` (prints `OPENMPI|SLURM detected`, `AcceleratorCudaInit`) → flag parsing →
memory manager → `MPI_Init_thread` → `MPI_Comm_split_type` (prints `World communicator of
size N`, `Node  communicator of size n`) → device comms buffer (`acceleratorAllocDevice … for
comms buffers`, `Setting up IPC`) → on-node barriers → banner → `MPI is initialised and logging
filters activated`. A hang before the `World communicator` line is inside MPI start-up, not Grid;
a hang between `Setting up IPC` and the banner is in on-node barriers or a CUDA call. Capture
non-zero ranks with `--debug-stdout`. Grid has no launcher-specific branch beyond choosing which
local-rank variable to print.
