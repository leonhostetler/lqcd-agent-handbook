---
title: QUDA CUDA 13 milc-cg stack on Perlmutter
summary: Reproduction commands and two required runtime/build corrections for the validated stack.
scope: [machine:perlmutter, software:quda]
load_when: Rebuilding or validating the quda-cuda13-milc-cg-2026q3 stack.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/include/communicator_quda.h
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/lib/extract_gauge_ghost.in.cu
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/tests/staggered_dslash_test_utils.h
observed: "2026-08-20"
observed_on:
  machine: perlmutter
  software:
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
  toolchain:
    cuda: 13.2.78
---

# QUDA CUDA 13 `milc-cg` on Perlmutter

Load the Perlmutter machine profile, declare `gpu-a100-40`, and resolve the `milc-cg`
profile before using these notes. `stack.yaml` is canonical for the tested versions,
toolchain, build cost, and validation result.

## Configure and build

After `module reset`, configure with the Cray wrappers and the complete profile option set:

```bash
cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_C_COMPILER=cc \
  -DCMAKE_CXX_COMPILER=CC \
  -DQUDA_TARGET_TYPE=CUDA \
  -DQUDA_GPU_ARCH=sm_80 \
  -DQUDA_DIRAC_DEFAULT_OFF=ON \
  -DQUDA_DIRAC_STAGGERED=ON \
  -DQUDA_INTERFACE_MILC=ON \
  -DQUDA_INTERFACE_QDP=ON \
  -DQUDA_QMP=ON \
  -DQUDA_MPI=OFF \
  -DQUDA_QIO=ON \
  -DQUDA_MULTIGRID=OFF \
  -DQUDA_USE_EIGEN=ON \
  -DQUDA_DOWNLOAD_EIGEN=ON \
  -DQUDA_DOWNLOAD_USQCD=ON \
  -DQUDA_BUILD_ALL_TESTS=ON \
  -DQUDA_INSTALL_ALL_TESTS=ON

cmake --build "$QUDA_BUILD_DIR" --target install --parallel 8
```

Configuration requires network access when the downloaded QMP, QIO, and Eigen dependencies
are not already present. Keep the login-node build at the machine profile's eight-job
ceiling. The recorded build then compiled only the focused validation executables. The commands
above implement the current all-tests default instead. The cost in `stack.yaml` predates that
policy and must not be used as an estimate for an all-tests build.

## Multi-GPU placement

Use four ranks and four GPUs. Disable Slurm's per-rank GPU visibility:

```bash
#SBATCH --nodes=1
#SBATCH --constraint=gpu&hbm40g
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-task=1
#SBATCH --gpu-bind=none

srun --ntasks=4 --cpus-per-task=32 --cpu-bind=cores \
  --gpus-per-task=1 --gpu-bind=none <test-command>
```

QUDA assigns a device ordinal by counting earlier ranks on the same host. If Slurm exposes
only one device to each rank, local ranks one through three still request ordinals one
through three from a one-device view and stop with `Too few GPUs available`. With binding
disabled, all ranks see all four devices and QUDA's local-rank mapping selects one each.

Set `MPICH_GPU_SUPPORT_ENABLED=1`, `QUDA_ENABLE_GDR=1`, and a fresh writable
`QUDA_RESOURCE_PATH`. Record `nvidia-smi` telemetry by local rank before validation and
confirm four 40 GB A100 devices with compute capability 8.0.

## Focused validation commands

Use the same `srun` options above for each command:

```bash
"$QUDA_BUILD_DIR/tests/staggered_dslash_test" \
  --dslash-type asqtad --test MatPC --dim 4 4 4 8 \
  --gridsize 1 1 1 4 --compute-fat-long true --niter 10 \
  --gtest_filter=StaggeredDslashTest.verify

"$QUDA_BUILD_DIR/tests/staggered_invert_test" \
  --dslash-type asqtad --ngcrkrylov 8 --compute-fat-long true \
  --dim 6 6 6 8 --gridsize 1 1 1 4 --prec double \
  --tol 1e-6 --tolhq 1e-6 --niter 1000 --enable-testing true \
  --gtest_filter='EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2'

"$QUDA_BUILD_DIR/tests/io_test" \
  --dim 4 4 4 8 --gridsize 1 1 1 4 \
  --gtest_filter='Gauge/GaugeIOTest.*'
```

The inverter's aggregate statistics may print `-nan` for a one-solve test because it
excludes the first solve before calculating the mean. Judge this validation by the checked
true residual and GoogleTest result, not that empty-sample statistic.
