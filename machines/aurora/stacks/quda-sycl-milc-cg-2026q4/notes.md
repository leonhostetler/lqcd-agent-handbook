---
title: QUDA SYCL milc-cg stack on Aurora
summary: Reproduction commands, the feature/sycl branch requirement, and the runtime placement for the validated Aurora SYCL QUDA stack, including why QUDA_ENABLE_MPS=1 is safe here only together with QUDA_ENABLE_P2P=0.
scope: [machine:aurora, software:quda]
load_when: Rebuilding or validating the quda-sycl-milc-cg-2026q4 stack, or launching QUDA on Aurora.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Aurora/compile_quda.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Aurora/submit.qsub
  - https://github.com/lattice/quda/blob/0616968dec1858307efaa8ff181c9ebead44e0e0/lib/targets/sycl/target_sycl.cmake
  - https://github.com/lattice/quda/blob/0616968dec1858307efaa8ff181c9ebead44e0e0/lib/targets/sycl/comm_target.cpp
  - https://github.com/lattice/quda/blob/0616968dec1858307efaa8ff181c9ebead44e0e0/include/communicator_quda.h
observed: "2026-10-01"
observed_on:
  machine: aurora
  software:
    quda:
      commit: 0616968dec1858307efaa8ff181c9ebead44e0e0
      branch: feature/sycl
      forked_from_default: 00c7ef33dacadfb94860e3ca1cc06862926182dc
  toolchain:
    oneapi: 2026.1.0
---

# QUDA SYCL `milc-cg` on Aurora

Load the Aurora machine profile, select `gpu-pvc`, and resolve the `milc-cg` profile before
using these notes. `stack.yaml` is canonical for tested versions, build cost, and validation
results.

## Use `feature/sycl`, not `develop`

QUDA's SYCL backend lives only on `feature/sycl`. At the fork point recorded in `stack.yaml`,
`develop` lists `SYCL` among the accepted `QUDA_TARGET_TYPE` values but carries no
`lib/targets/sycl` or `include/targets/sycl` directory, so a `develop` checkout cannot build
this stack. This is an explicit operator-requested branch, not the project default; clone it
with `git clone --branch feature/sycl`.

The upstream sample script clones `feature/sycl` on a first run but runs
`git pull; git checkout develop` when the checkout already exists. Do not reuse that block:
a second run of it moves the checkout to a branch with no SYCL backend.

## Configure and build

The SYCL options are read from the environment by `lib/targets/sycl/target_sycl.cmake`, so
export them before configuring. They are the upstream sample's values, including its
large-register-file branch, which also lowers the maximum block size:

```bash
module reset
module load cmake

export QUDA_SYCL_TARGETS="spir64_gen"
export SYCL_LINK_FLAGS=' -Xs "-device pvc" -fsycl-device-code-split=per_kernel -fsycl-max-parallel-link-jobs=32 -flink-huge-device-code -Xs "-options -ze-opt-large-register-file"'
export QUDA_WARP_SIZE=16
export QUDA_MAX_BLOCK_SIZE=512
export QUDA_MAX_ARGUMENT_SIZE=2048
export QUDA_TEST_NUMPROCS=1

cmake -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_C_COMPILER=mpicc -DCMAKE_CXX_COMPILER=mpicxx \
  -DQUDA_TARGET_TYPE=SYCL \
  -DQUDA_BUILD_SHAREDLIB=ON \
  -DQUDA_DIRAC_DEFAULT_OFF=ON -DQUDA_DIRAC_STAGGERED=ON \
  -DQUDA_INTERFACE_MILC=ON -DQUDA_INTERFACE_QDP=ON \
  -DQUDA_QMP=ON -DQUDA_MPI=OFF -DQUDA_QIO=ON \
  -DQUDA_MULTIGRID=OFF \
  -DQUDA_USE_EIGEN=ON -DQUDA_DOWNLOAD_EIGEN=ON \
  -DQUDA_DOWNLOAD_USQCD=ON \
  -DQUDA_BUILD_ALL_TESTS=ON -DQUDA_INSTALL_ALL_TESTS=ON

cmake --build "$QUDA_BUILD_DIR" --target install --parallel 16
```

Configure logs `With user SYCL_LINK_FLAGS:` followed by the value in force; check it. No GPU is
needed at build time: device code is compiled ahead of time for `pvc`, and the installed
`libquda.so` carries it in a `.tgtimg` section. The `milc-cg` profile values that equal QUDA's
defaults are passed explicitly so the record does not depend on those defaults.

The oneAPI linker writes `DT_RUNPATH`, not `DT_RPATH`, so the installed tests and a MILC
executable linked against this install can be redirected by `LD_LIBRARY_PATH`. See
[`../../../../software/milc/quda-linkage.md`](../../../../software/milc/quda-linkage.md),
which says to confirm the tag rather than assume it.

## Runtime placement

Run one rank per GPU tile, twelve per node, through ALCF's tile wrapper, which sets
`ZE_AFFINITY_MASK=<gpu>.<tile>` from the PALS local rank:

```bash
mpiexec -n 12 --ppn 12 \
  --cpu-bind list:1-8:9-16:17-24:25-32:33-40:41-48:53-60:61-68:69-76:77-84:85-92:93-100 \
  /soft/tools/mpi_wrapper_utils/gpu_tile_compact.sh <executable> <args>
```

**The CPU list replaces the upstream sample's `--depth=16 --cpu-bind depth`.** Twelve ranks of
depth sixteen claim logical CPUs 0 to 191 in order `[inferred]` from the CPU numbering (0 to 103
physical, 104 to 207 their hyperthreads): rank 0 takes reserved core 0, and ranks 6 to 11 land on
the hyperthreads of the cores ranks 0 to 5 already hold. That layout was not run here. The list gives each rank
eight physical cores and skips reserved cores 0 and 52. Confirm with
`OMP_DISPLAY_AFFINITY=true`.

### Why `QUDA_ENABLE_MPS=1` is safe here, and only with `QUDA_ENABLE_P2P=0`

With one visible device per rank, QUDA's per-host rank count gives every rank above the first
a `gpuid` past the device count, and it aborts with `Too few GPUs` unless
`QUDA_ENABLE_MPS=1` clamps the index to 0. The
[rank-placement leaf](../../../../software/quda/internals/rank-placement.md) explains why that
clamp corrupts the peer-to-peer decision: `gpuid == neighbor_gpuid` then holds for distinct
devices. On this branch that decision is never reached when `QUDA_ENABLE_P2P=0`, because the
whole peer-to-peer setup is gated on it. Peer-to-peer is not available here anyway, since the
SYCL target's `comm_peer2peer_possible` returns false and its neighbour-memory hooks are empty.
So the pair is coherent. **Do not set `QUDA_ENABLE_MPS=1` without `QUDA_ENABLE_P2P=0` on this
stack**: `[inferred]` from the source, the same-device clause would then enable a peer path to
memory that was never mapped. That combination was not run.

The tunecache witnesses this: every multi-GPU dslash policy key carries `p2p=0,gdr=1`. The
`p2p=7` witness of GPU-Direct RDMA in
[`../../../../software/quda/runtime-environment.md`](../../../../software/quda/runtime-environment.md)
does not apply when peer-to-peer is disabled; read `gdr=` alone.

## Focused validation commands

Apply the launcher above to each command. Every partitioned dimension has local extent 6, the
minimum improved staggered accepts:

```bash
"$QUDA_BUILD_DIR/usqcd/bin/staggered_dslash_test" \
  --dslash-type asqtad --test MatPC --dim 6 6 6 6 --gridsize 1 2 2 3 \
  --compute-fat-long true --prec single --niter 10 \
  --gtest_filter=StaggeredDslashTest.verify

"$QUDA_BUILD_DIR/usqcd/bin/staggered_invert_test" \
  --dslash-type asqtad --compute-fat-long true --dim 6 6 6 6 --gridsize 1 2 2 3 \
  --prec double --tol 1e-6 --tolhq 1e-6 --niter 1000 --enable-testing true \
  --gtest_filter=EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2

"$QUDA_BUILD_DIR/usqcd/bin/io_test" --dim 6 6 6 6 --gridsize 1 2 2 3 \
  '--gtest_filter=Gauge/GaugeIOTest.*'
```

All three passed, scored by their gtest verdict lines. The whole job, including the companion
MILC legs, held at most 4.8 GiB on any GPU.
