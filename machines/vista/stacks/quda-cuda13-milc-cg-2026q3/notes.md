---
title: QUDA CUDA 13 milc-cg stack on Vista
summary: Reproduction commands for the Vista gpu-gh200 QUDA stack built with NVHPC 26.1, CUDA 13.1 and Open MPI 5.0.9 (UCX 1.20.0), whose multi-node GPUDirect RDMA is validated with UCX's default transports.
scope: [machine:vista, software:quda]
load_when: Rebuilding, validating, or running multi-rank or GPUDirect RDMA work with the quda-cuda13-milc-cg-2026q3 stack on Vista.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Vista/compile_quda.sh
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L529-L532
  - operator-run and operator-submitted validation runs reviewed in the working directory
observed: "2026-09-28"
observed_on:
  machine: vista
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 13.1.80
    ucx: 1.20.0
---

# QUDA CUDA 13 `milc-cg` on Vista

Declare `gpu-gh200` before using these notes; Vista has two node types. `stack.yaml` is
canonical for tested versions, build cost, validation results, and scope limits.

**Prefer this stack to `quda-cuda12-milc-cg-2026q3` for any multi-rank GPU work.** Its Open
MPI links UCX 1.20.0, and GPUDirect RDMA works across nodes with UCX's default transports.
The cuda12 stack's Open MPI is pinned to UCX 1.17.0, whose GPU-memory registration fails
with the `gdr_copy` transport present; [`../../gpu-aware-mpi.md`](../../gpu-aware-mpi.md)
owns that mechanism.

## Toolchain

```bash
module reset
module load nvidia/26.1 cuda/13.1 openmpi/5.0.9 cmake/4.1.1
```

`openmpi/5.0.9` is offered with `nvidia/26.1` (and with `gcc/15.1.0`); both builds link UCX
1.20.0. This stack uses the NVIDIA compilers, as the upstream
`systems/Vista/compile_quda.sh` does. CMake reports the CUDA compiler as NVIDIA 13.1.80 with
host compiler NVHPC 26.1.0. Load the same modules at run time.

## Configure and build

```bash
cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_C_COMPILER=mpicc -DCMAKE_CXX_COMPILER=mpicxx \
  -DQUDA_TARGET_TYPE=CUDA -DQUDA_GPU_ARCH=sm_90 \
  <milc-cg profile options from software/quda/build-profiles.yaml>
cmake --build "$QUDA_BUILD_DIR" --target install --parallel 32
```

Build on a compute node; the login-node limits in [`../../notes.md`](../../notes.md) rule
out this parallelism. Configure downloads QMP, QIO, Eigen, and CCCL. Keep
`CMAKE_INSTALL_LIBDIR=lib`: the reason is the same as for the cuda12 stack
([`../quda-cuda12-milc-cg-2026q3/notes.md`](../quda-cuda12-milc-cg-2026q3/notes.md)).
Under this toolchain the build ran without errors and the installed tests resolved every
library on the first attempt.

## What the validation shows

- **Single GPU:** the installed dslash, CG and QIO tests pass with the same figures as the
  cuda12 stack.
- **GPUDirect RDMA, four nodes, UCX defaults:** the dslash passes at two local volumes,
  under the default policy set and under the GDR send-and-receive policies `2,3`, and CG
  passes, with no registration errors. UCX's protocol tables (`UCX_PROTO_INFO=y`) record
  inter-node `rendezvous data fetch into cuda/GPU0 from cuda` for the larger halos: the HCA
  moved data GPU to GPU. The smaller halos travel in UCX's eager copy band by design, so a
  GDR validation needs a halo above the rendezvous threshold as well;
  [`../../../../software/quda/runtime-environment.md`](../../../../software/quda/runtime-environment.md)
  owns how to read these tables.
- **Multi-rank QIO still fails**, identically to the cuda12 stack. That failure is not a GDR
  or toolchain effect, and its cause is open.
