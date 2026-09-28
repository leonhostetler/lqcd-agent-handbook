---
title: MILC ks_spectrum_hisq stack with QUDA on Vista
summary: Superseded for multi-rank GPU work by milc-cuda13-quda-ks-spectrum-2026q3, because its UCX 1.17 transport breaks GPUDirect RDMA. Vista build options, the OpenMP link fix, placement, and the four-node validation of MILC ks_spectrum_hisq composed with the Vista GNU 14 / CUDA 12 QUDA milc-cg stack, whose GPU-to-GPU transfer was not shown.
scope: [machine:vista, software:milc]
load_when: Rebuilding, validating, or launching the milc-cuda12-quda-ks-spectrum-2026q3 stack on Vista.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Vista/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Vista/submit.sbatch
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - operator-submitted validation run reviewed in the working directory
observed: "2026-09-28"
observed_on:
  machine: vista
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
  toolchain:
    cuda: 12.8.93
---

# MILC `ks_spectrum_hisq` with QUDA on Vista

> **Superseded for multi-rank GPU work — use
> [`milc-cuda13-quda-ks-spectrum-2026q3`](../milc-cuda13-quda-ks-spectrum-2026q3/notes.md).**
> This stack's Open MPI is pinned to UCX 1.17.0, so its multi-node runs do not get working
> GPUDirect RDMA ([`../../gpu-aware-mpi.md`](../../gpu-aware-mpi.md)). Use it only for
> single-GPU work or to reproduce its own recorded results.

Declare `gpu-gh200` first. Build against the QUDA install of
[`quda-cuda12-milc-cg-2026q3`](../quda-cuda12-milc-cg-2026q3/notes.md), whose notes own the
toolchain and its scope limits. `stack.yaml` is canonical for tested versions, cost, and
validation results. The shared invocation is in `software/milc/build.md`.

## Machine options, and two that differ from the reference scripts

Materialize `machine_args` from `stack.yaml`, resolving the prefixes against the loaded
`cuda/12.8` module and the QUDA install. Point `QUDA_HOME`, `QMPPAR`, and `QIOPAR` at the
same install prefix, so every run path names one directory.

- **`LDFLAGS=-g -fopenmp`, not `-g`.** A command-line `LDFLAGS` replaces the Makefile's own
  `LDFLAGS += -fopenmp` for `COMPILER=gnu` with `OMP=true`, while the objects are still
  compiled with `-fopenmp` through `OCFLAGS`. With plain `mpicc` the link then fails on
  undefined `omp_get_num_threads` and `omp_get_thread_num`. The DeltaAI stack's `LDFLAGS=-g`
  linked because its Cray wrappers supply OpenMP.
- **`OFFLOAD=CUDA` is inert in the Makefile's CUDA block**, which tests for lowercase `cuda`.
  The executable still resolves `libcudart`, `libcublas`, and `libcufft` through
  `libquda.so`'s own dependencies. The `CUDA_*` prefixes are recorded for parity with the
  other stacks, not because this build reads them.

The linker here emits `RUNPATH`, not `RPATH`: `readelf -d` on the executable shows the QUDA
install and Open MPI library directories as `RUNPATH`. `LD_LIBRARY_PATH` can therefore
redirect the loaded `libquda.so`, the opposite of the case described in
`software/milc/quda-linkage.md`. Record the library `ldd` resolves at run time, and keep a
stray QUDA library directory out of `LD_LIBRARY_PATH`.

Load `gcc/14.2.0 cuda/12.8 openmpi/5.0.5` in the job as well; the GNU 14 runtime is not on
the run path.

## Launch

The validation ran one rank per node through `ibrun`, with the upstream `sample.in`
unchanged (`node_geometry 1 1 2 2` on four nodes) and 72 CPUs requested per rank with 16
OpenMP threads. At one task per node, TACC's `ibrun` launches Open MPI's `mpirun` with
`--bind-to none`; each rank's affinity was all 72 cores.

Environment exported for the run: `QUDA_ENABLE_GDR=1`, `QUDA_MILC_HISQ_RECONSTRUCT=13`,
`QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9`, `OMP_NUM_THREADS=16`, `OMP_PROC_BIND=spread`,
`OMP_PLACES=cores`, a fresh `QUDA_RESOURCE_PATH`; `QUDA_ENABLE_P2P` and
`QUDA_DETERMINISTIC_REDUCE` deliberately unset. The tunecache policy keys (`commDim=0011`,
`gdr=1`) confirm that QUDA handed device buffers to MPI; they do not show that the HCA moved
data GPU to GPU, and this run did not record UCX's protocol tables.

Batch submission from a compute node is refused on Vista; see
[`../../notes.md`](../../notes.md).

## What the validation shows, and what it does not

The four-node run completed, converged all 24 CG solves under the 1e-8 true-residual target,
and wrote all 12 correlator records. Its correlators agree with two earlier Vista runs of
the same sample input — built with a different toolchain and older revisions — to the file's
printed precision, and those two references differ from each other by the same amount.

QUDA's own multi-node tests fail with GDR on for the device-buffer policies, and its
multi-rank QIO read-back fails a checksum (see the QUDA stack notes). The GDR failure comes
from this stack's UCX 1.17.0 and its `gdr_copy` transport
([`../../gpu-aware-mpi.md`](../../gpu-aware-mpi.md)). This run's halos are large enough to
take a protocol that avoids it, and at this local volume a two-node QUDA test recorded only
host-sourced transfers, so this run most likely did not move data GPU to GPU either. **For
GDR, use [`milc-cuda13-quda-ks-spectrum-2026q3`](../milc-cuda13-quda-ks-spectrum-2026q3/notes.md).**
Treat other lattice sizes, decompositions, and any QIO gauge I/O through this stack as
unvalidated.
