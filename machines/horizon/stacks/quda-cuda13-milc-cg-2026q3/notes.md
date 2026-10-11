---
title: QUDA CUDA 13 milc-cg stack on Horizon
summary: Reproduction commands for the Horizon gpu-gb200 QUDA stack built with NVHPC 26.9, CUDA 13.3 and Open MPI 5.0.11 (UCX 1.22.0) for sm_100, with the launch mapping that keeps each rank beside its GPU on a four-GPU board.
scope: [machine:horizon, software:quda]
load_when: Rebuilding, validating, or running multi-rank work with the quda-cuda13-milc-cg-2026q3 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/targets/cuda/target_cuda.cmake#L120-L130
  - operator-submitted build and validation runs reviewed in the working directory
observed: "2026-09-29"
observed_on:
  machine: horizon
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 13.3.73
    ucx: 1.22.0
---

# QUDA CUDA 13 `milc-cg` on Horizon

Declare `gpu-gb200` before using these notes; Horizon has two node types. `stack.yaml` is
canonical for tested versions, build cost, validation results, and scope limits.
[`../../notes.md`](../../notes.md) owns the early-access layout this was validated on.

## Toolchain

```bash
module reset
module load nvidia/26.9 cuda/13.3 openmpi/5.0.11 ucx/1.22.0
module unload cmake
```

These are TACC's defaults at the time of validation, loaded by version so a later default
change cannot move them. The `cmake` module is unloaded because its binaries were not
executable; `/usr/bin/cmake` 3.30.5 configured and built the stack, and QUDA needs 3.18 or
newer. Load the same modules at run time.

## Configure and build

```bash
cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_C_COMPILER=mpicc -DCMAKE_CXX_COMPILER=mpicxx \
  -DQUDA_TARGET_TYPE=CUDA -DQUDA_GPU_ARCH=sm_100 \
  <milc-cg profile options from software/quda/build-profiles.yaml>
cmake --build "$QUDA_BUILD_DIR" --target install --parallel 64
```

Configure on a login node: it downloads QMP, QIO, Eigen and CCCL, and whether compute nodes
reach the network was not established when this stack was built. They did on 2026-10-09, when
[`quda-cuda13-milc-cg-mrhs-tile3-2026q4`](../quda-cuda13-milc-cg-mrhs-tile3-2026q4/notes.md)
configured in a batch job. Build on a compute node; the login node's conduct rules
rule out this parallelism. The cache shows `CMAKE_CUDA_ARCHITECTURES=75` beside
`QUDA_GPU_ARCH=sm_100`. That is a leftover default: QUDA sets the architecture on its own
library target, which compiles `compute_100`/`sm_100`, and it is the only target that compiles
device code.

## Launch

Four GPUs and four ranks share one scheduler node during early access, so rank placement
matters here in a way it does not on a one-GPU node:

- **Leave every GPU visible.** QUDA gives local rank *n* device *n*;
  [`../../../../software/quda/internals/rank-placement.md`](../../../../software/quda/internals/rank-placement.md)
  owns why restricting visibility breaks that.
- **Bind consecutive 36-core blocks**, so each rank sits on the socket of its GPU (GPUs 0-1 on
  cores 0-71, GPUs 2-3 on 72-143): export
  `OPENMPI_AFFINITY="--map-by slot:PE=36 --bind-to core"` before `ibrun`, which uses a preset
  value. `ibrun`'s own mapping alternates ranks between sockets, putting local ranks 1 and 2
  beside the wrong GPU.
- **Never run several ranks unbound with `OMP_PROC_BIND` set.** `ibrun -n N -o M` forces
  `--bind-to none`, and then every rank pins its thread 0 to the same core; a multi-GPU dslash
  took about 13 ms instead of about 40 us. Set `OMP_PROC_BIND=false` for such a launch, or use
  the whole allocation. [`../../notes.md`](../../notes.md) owns the mechanism.

## What the validation shows

- **One GPU:** the installed dslash, CG and QIO tests pass.
- **Eight ranks on two boards:** dslash passes at two local volumes and CG converges, with
  peer-to-peer between the GPUs of a board and GPUDirect RDMA between boards. UCX's protocol
  tables record inter-node GPU-to-GPU rendezvous fetches striped over two HCAs.
  [`../../../../software/quda/runtime-environment.md`](../../../../software/quda/runtime-environment.md)
  owns how to read them.
- **Multi-rank QIO fails** its read-back checksum on `$HOME`. The cause is the open upstream
  defect in
  [`../../../../software/qio/parallel-singlefile-writes.md`](../../../../software/qio/parallel-singlefile-writes.md)
  (qio#19, quda#1655), not this stack. Horizon has no Lustre filesystem to write on instead.
