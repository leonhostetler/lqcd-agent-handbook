---
title: QUDA's error exit runs static destructors that corrupt the heap
summary: errorQuda reaches exit() through MPI_Abort with QUDA still initialized, so libquda's static destructors free cached fields through an allocation map already destroyed; the glibc heap error, core dump, garbage tunecache file and occasional hang that follow an ERROR line are this, not the failure.
scope: [software:quda]
load_when: A QUDA run prints "double free or corruption", "Attempt to free invalid host pointer", or another heap error after an ERROR line; hangs after an errorQuda instead of exiting; exits with SIGABRT or a core dump after errorQuda; or leaves a garbage-named file in its run or tunecache directory.
evidence: reproduced
observations: 22
sources:
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/util_quda.cpp#L178-L191
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/communicator_qmp.cpp#L505-L509
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/communicator_single.cpp#L130
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/interface_quda.cpp#L1505-L1605
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/targets/cuda/malloc.cpp#L71
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/targets/cuda/malloc.cpp#L144-L151
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/targets/cuda/malloc.cpp#L489-L493
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/targets/cuda/malloc.cpp#L611-L626
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/include/field_cache.h#L49
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/field_cache.cpp#L6
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/color_spinor_field.cpp#L286
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/tune.cpp#L104-L123
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/lib/QMP_init.c#L330-L339
  - https://github.com/lattice/quda/pull/1654
  - operator's screened QUDA pull-request review records
  - agent-run gdb traces on DeltaAI reviewed in the working directory; raw output is not committed
observed: "2026-10-08"
observed_on:
  machine: deltaai
  node_type: gpu-gh200
  software:
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
  toolchain:
    cuda: 12.9.41
    host_compiler: GNU 14.2.0 through Cray wrappers
    mpi: Cray MPICH 9.0.1
---

# QUDA's error exit runs static destructors that corrupt the heap

**Read the first `ERROR` line, not the last one.** After `errorQuda`, a QUDA process commonly
fails a second time on its way out. It may print a glibc heap error, dump core, write a
garbage-named tunecache file, or hang. All of these come from tearing down the process. None of
them is the cause of the failure the `ERROR` line already reported. Do not debug the heap error.

## Mechanism

Read from source at `ba501e4f8`, and traced under gdb at one and four ranks.

1. **The abort reaches `exit()`, with QUDA still initialized.**
   - `errorQuda_` saves the tunecache and calls `comm_abort(1)`.
   - The QMP backend calls `QMP_abort`, and then `std::abort()`. The `std::abort()` is never
     reached.
   - On Cray MPICH, `MPI_Abort` itself calls `exit()`. With a launcher it goes through PMI2
     (`PMI2_Abort`); as a singleton it goes through `MPL_exit`. If `MPI_Abort` returned,
     `QMP_abort` would call `exit()` next anyway.
   - The single-process backend calls `std::exit` directly.
2. **`endQuda` is what normally empties QUDA's static owners**: the field cache,
   `solutionResident`, `momResident` and the memory pools. On the abort path it never runs.
3. **The destructors then run in an order that breaks.**
   - `exit()` runs libquda's static destructors in the reverse of construction order. Across
     translation units, that order is link order.
   - In the build traced, `malloc.cpp` constructs after `field_cache.cpp`. So the `alloc[]`
     tracking maps, and the four memory-pool maps beside them, are destroyed first.
   - Then `FieldTmp<ColorSpinorField>::cache` is destroyed. Each cached field calls `host_free`,
     and `track_free` indexes and erases a map that no longer exists.
   - libstdc++'s map destructor frees the nodes without resetting the header. glibc reports the
     damage on the next free, as `double free or corruption` with `(!prev)` or `(out)`.

The traced stack, innermost first:

```text
malloc_printerr <- free <- quda::track_free <- quda::host_free_
<- ColorSpinorField::destroy <- ~ColorSpinorField <- (FieldTmp<ColorSpinorField>::cache)
<- __cxa_finalize <- _dl_fini <- __run_exit_handlers <- exit
<- MPI_Abort <- QMP_abort <- comm_abort <- errorQuda_
```

**The hang has the same cause.** When the lookup in the destroyed map misses instead,
`host_free_` prints `Attempt to free invalid host pointer (color_spinor_field.cpp:286 in
destroy())` and calls `errorQuda("Aborting")` again. That call:

- re-saves the tunecache through `get_resource_path()`'s function-local `static std::string`,
  which has already been destroyed — hence the file with a garbage name and header;
- then re-enters `MPI_Abort` from inside `exit()`.

This is `inferred`: the hang was seen once, on a pull-request build, and was not reproduced under
gdb. The steps above are read from source.

**Only one rank usually reports it.** In a multi-rank abort the launcher kills the other ranks
before they reach their exit handlers.

## What was seen

| Where | Aborts reaching `errorQuda` | Heap error | Other |
|---|---|---|---|
| `develop` `00c7ef33` and builds of lattice/quda#1654 forked from it | 13: eigensolver test (6), MILC CG divergence (7) | 12 | 1 hang (garbage tunecache file, invalid-pointer message) |
| `develop` `ba501e4f8` | 9: eigensolver test at TRLM and BLOCK TRLM (4), MILC eigensolve through `qudaLoadDeflationSpace` (4), MILC deflated CG divergence (1) | 8 | 1 ended by signal before printing |

There were three `errorQuda` sites (TRLM restart exhaustion, BLOCK TRLM restart exhaustion, and
CG divergence) and one or four ranks per process group. The eigensolver is not the trigger. Any
`errorQuda` reached while the field cache holds fields is enough.

All runs were on DeltaAI `gpu-gh200`, with CUDA 12.9, GNU 14 through the Cray wrappers, and Cray
MPICH 9.0.1. Not tested:
- other MPI libraries, and whether their `MPI_Abort` runs exit handlers;
- other machines or compilers, and other link orders.

## What to do with it

- **Classify an aborted run by its first `ERROR` line.** Exit status 134, `Aborted (core
  dumped)` and the heap message are symptoms of exiting. A rig or scoring script that keys on the
  signal, or on a single error message, will mislabel the run. Match any `ERROR:` line.
- **Expect an `errorQuda` to hang sometimes.** Give every launcher step its own time limit
  ([`../../../conventions/batch-scripts.md`](../../../conventions/batch-scripts.md)), so a hung
  abort costs only its own leg.
- **A garbage-named file in a run or tunecache directory is this signature.** Keep it as evidence.
  Never load it as a tunecache, and never delete it as debris before it is recorded.
- **Set `ulimit -c 0` in a leg expected to abort**, unless the core is wanted. Otherwise every such
  leg writes a core of the dying process wherever the site's core pattern points.
- **A fix belongs upstream, and fixing only the map is not one.** Static objects that QUDA's own
  destructors rely on should be constructed on first use and never destroyed: the field cache and
  the other static field owners, and also the tracking maps, the pool maps and the resource path.
  Repairing `alloc[]` alone sends the cache's device frees on to the destroyed pool maps and a
  CUDA runtime that is shutting down. As of this entry the fix is proposed, not built.
