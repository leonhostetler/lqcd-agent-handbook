---
title: QUDA CUDA 12 milc-cg stack on DeltaAI
summary: Reproduction commands and GH200 runtime safeguards for the validated DeltaAI CUDA stack.
scope: [machine:deltaai, software:quda]
load_when: Rebuilding or validating the quda-cuda12-milc-cg-2026q3 stack on DeltaAI.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/DeltaAI/compile_quda.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/DeltaAI/submit.sbatch
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/communicator_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_dslash_test_utils.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_invert_test.cpp
observed: "2026-08-17"
observed_on:
  machine: deltaai
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
  toolchain:
    cuda: 12.9.41
---

# QUDA CUDA 12 `milc-cg` on DeltaAI

Load the DeltaAI machine profile and resolve the `milc-cg` profile before using these
notes. Because `gpu-gh200` is the profile's sole node type, it is the default unless the
operator explicitly selects another type after the profile changes. `stack.yaml` is
canonical for tested versions, build cost, and validation results.

## Configure and build

The tested login-node build used the default Cray environment after `module reset`, the
Cray compiler wrappers, and the NVIDIA 9.0 accelerator target:

```bash
module reset
export CRAY_ACCEL_TARGET=nvidia90

cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_C_COMPILER=cc \
  -DCMAKE_CXX_COMPILER=CC \
  -DQUDA_TARGET_TYPE=CUDA \
  -DQUDA_GPU_ARCH=sm_90 \
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
  -DQUDA_INSTALL_ALL_TESTS=ON \
  -DQUDA_CTEST_DISABLE_BENCHMARKS=ON

cmake --build "$QUDA_BUILD_DIR" --target install --parallel 8
```

Configuration downloads Eigen, QMP, QIO, and CCCL when they are absent. The tested build
used a fresh out-of-source directory and a clean, full-history QUDA checkout. Relative to
the cited MILC sample, it did not pull or reuse a checkout in place, reduced build
parallelism from 32 to 8, selected the complete handbook profile explicitly, and then built
only the focused validation executables after installation. The commands above implement the
current all-tests default instead. The cost in `stack.yaml` predates that policy and must not be
used as an estimate for an all-tests build.

## Use the short debugging partition

The focused validation fits DeltaAI's interactive limits, so use `ghx4-interactive`. The
tested one-node layout kept all four devices visible because QUDA maps them by local rank:

```bash
#SBATCH --partition=ghx4-interactive
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=16
#SBATCH --gpus-per-node=4
#SBATCH --gpu-bind=none
#SBATCH --mem=0

export LD_LIBRARY_PATH="$QUDA_BUILD_DIR/usqcd/lib:$QUDA_BUILD_DIR/usqcd/lib64:${LD_LIBRARY_PATH:-}"
export QUDA_RESOURCE_PATH="$VALIDATION_DIRECTORY/tunecache"
export QUDA_ENABLE_GDR=1
export MPICH_GPU_SUPPORT_ENABLED=1
export MPICH_RDMA_ENABLED_CUDA=1
export MPICH_NEMESIS_ASYNC_PROGRESS=1
export MPICH_SMP_SINGLE_COPY_MODE=XPMEM
export OMP_NUM_THREADS=16
export OMP_PROC_BIND=spread
export SRUN_CPUS_PER_TASK=16
mkdir -p "$QUDA_RESOURCE_PATH"
```

Run each executable with four tasks, Slurm core binding, and GPU binding disabled:

```bash
srun --ntasks=4 --cpus-per-task=16 --cpu-bind=cores --gpu-bind=none <test-command>
```

Before validation, record the module list, `nvidia-smi` product, memory, and compute
capability output, plus every rank's host, local rank, and visible devices. Confirm that
QUDA initializes devices zero through three across the four local ranks. The successful
run observed peer access between neighboring ranks in the T-decomposed grid. It did not
capture a NUMA map, so this placement is correctness evidence rather than a performance
prescription.

Submit from the working project so `SLURM_SUBMIT_DIR` resolves the source-independent
build and validation paths used by the job script. Keep the account and raw output out of
the handbook:

```bash
working_directory="$PWD"
validation_root="$working_directory/validation/deltaai-gpu-gh200"
mkdir -p "$validation_root"
cd "$working_directory"
sbatch --account=<project> \
  --output="$validation_root/slurm-%j.out" \
  validate-deltaai-gpu-gh200.sbatch
```

## Focused validation commands

Use the same `srun` options above for each command:

```bash
"$QUDA_BUILD_DIR/tests/staggered_dslash_test" \
  --dslash-type asqtad --test MatPC --dim 4 4 4 8 \
  --gridsize 1 1 1 4 --compute-fat-long true --prec single --niter 10 \
  --gtest_filter=StaggeredDslashTest.verify

"$QUDA_BUILD_DIR/tests/staggered_invert_test" \
  --dslash-type asqtad --ngcrkrylov 8 --compute-fat-long true \
  --dim 6 6 6 8 --gridsize 1 1 1 4 --prec double \
  --tol 1e-6 --tolhq 1e-6 --niter 1000 --enable-testing true \
  --gtest_filter=EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2

"$QUDA_BUILD_DIR/tests/io_test" \
  --dim 4 4 4 8 --gridsize 1 1 1 4 \
  '--gtest_filter=Gauge/GaugeIOTest.*'
```

All three checks passed. The selected inverter case enforced the L2 residual but reported
an inactive heavy-quark tolerance despite the command-line setting, so do not claim a
heavy-quark residual check. The first run populated a fresh tunecache and reported one
tuning-candidate regression warning; it is validation, not benchmark evidence. The MILC
interface was compiled, but no MILC executable was linked or run.
