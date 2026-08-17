---
title: QUDA ROCm 7 milc-cg stack on Frontier
summary: Reproduction commands and runtime safeguards for the validated Frontier HIP stack.
scope: [machine:frontier, software:quda]
load_when: Rebuilding or validating the quda-rocm7-milc-cg-2026q3 stack.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/compile_quda.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/README.md
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/include/communicator_quda.h
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/tests/staggered_dslash_test_utils.h
observed: "2026-08-17"
observed_on:
  machine: frontier
  software:
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
  toolchain:
    rocm: 7.1.1
    hip: 7.1.52802
---

# QUDA ROCm 7 `milc-cg` on Frontier

Load the Frontier machine profile, select `gpu-mi250x`, and resolve the `milc-cg` profile
before using these notes. `stack.yaml` is canonical for tested versions, build cost, and
validation results.

## Configure and build

The MILC Frontier sample establishes the ROCm and Cray MPICH linking pattern. Use a fresh
out-of-source build and the narrower handbook profile rather than the sample's pull-in-place,
reused build directory, two conflicting build types, and all-tests build:

```bash
module reset
module load PrgEnv-amd amd/7.1.1 rocm/7.1.1
module load craype-accel-amd-gfx90a
module load cmake
module load ninja

compile_flags="-I${MPICH_DIR}/include --offload-arch=gfx90a"
link_flags="-Wl,-rpath=${MPICH_DIR}/lib -L${MPICH_DIR}/lib -lmpi \
${CRAY_XPMEM_POST_LINK_OPTS} -lxpmem ${PE_MPICH_GTL_DIR_amd_gfx90a} \
${PE_MPICH_GTL_LIBS_amd_gfx90a} --offload-arch=gfx90a"

cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" -G Ninja \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_C_COMPILER=hipcc \
  -DCMAKE_CXX_COMPILER=hipcc \
  -DCMAKE_C_STANDARD=99 \
  -DCMAKE_C_FLAGS="$compile_flags" \
  -DCMAKE_CXX_FLAGS="$compile_flags" \
  -DCMAKE_HIP_FLAGS="$compile_flags" \
  -DCMAKE_SHARED_LINKER_FLAGS="$link_flags" \
  -DCMAKE_EXE_LINKER_FLAGS="$link_flags" \
  -DROCM_PATH="$ROCM_PATH" \
  -DQUDA_TARGET_TYPE=HIP \
  -DQUDA_GPU_ARCH=gfx90a \
  -DBUILD_SHARED_LIBS=ON \
  -DQUDA_BUILD_SHAREDLIB=ON \
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
  -DQUDA_BUILD_ALL_TESTS=OFF \
  -DQUDA_INSTALL_ALL_TESTS=OFF \
  -DQUDA_CTEST_DISABLE_BENCHMARKS=ON

cmake --build "$QUDA_BUILD_DIR" --target install --parallel 4
cmake --build "$QUDA_BUILD_DIR" \
  --target staggered_dslash_test staggered_invert_test io_test \
  --parallel 4
```

Configuration downloads Eigen, QMP, and QIO when they are absent. The tested login-node
build used four jobs. Reassess placement if a future profile is materially larger.

## Keep scheduler output in the working project

An absolute script path does not set Slurm's working directory. Create the output directory
before submission and pin both paths on `sbatch`; otherwise `slurm-%j.out` appears in the
directory from which the operator submits:

```bash
working_directory="$PWD"
validation_directory="$working_directory/validation/frontier-gpu-mi250x"
mkdir -p "$validation_directory"

sbatch --account=<project> \
  --chdir="$working_directory" \
  --output="$validation_directory/slurm-%j.out" \
  validate-frontier-gpu-mi250x.sbatch
```

Do not put allocation names or user-specific absolute paths in the handbook or a committed
job script.

## Runtime safeguards and placement

Use one rank per visible GCD and keep all eight devices visible. QUDA selects devices from
local rank; per-rank visibility would leave ranks above zero with too few visible devices.
The tested grid and required environment are:

```bash
export LD_LIBRARY_PATH="$QUDA_BUILD_DIR/usqcd/lib:$QUDA_BUILD_DIR/usqcd/lib64:${LD_LIBRARY_PATH:-}"
export QUDA_RESOURCE_PATH="$VALIDATION_DIRECTORY/tunecache"
export QUDA_ENABLE_P2P=0
export QUDA_ENABLE_GDR=1
export MPICH_GPU_SUPPORT_ENABLED=1
mkdir -p "$QUDA_RESOURCE_PATH"

#SBATCH --nodes=1
#SBATCH --constraint=nvme
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=7
```

`QUDA_ENABLE_P2P=0` is part of the validated configuration. The cited MILC Frontier notes
report incorrect halo exchange with ROCm 6 and crashes with tested ROCm 7 versions when
QUDA P2P is enabled. This validation did not retest the failing path.

Use the eight NUMA-aware CPU masks and memory map from the cited MILC Frontier submission
sample. Record `rocm-smi --showproductname --showmeminfo vram`, module state, and rank-visible
device variables before validation.

## Focused validation commands

Apply the same eight-rank CPU and memory binding to each command:

```bash
"$QUDA_BUILD_DIR/tests/staggered_dslash_test" \
  --dslash-type asqtad --test MatPC --dim 4 4 8 8 \
  --gridsize 1 1 2 4 --compute-fat-long true --prec single --niter 10 \
  --gtest_filter=StaggeredDslashTest.verify

"$QUDA_BUILD_DIR/tests/staggered_invert_test" \
  --dslash-type asqtad --ngcrkrylov 8 --compute-fat-long true \
  --dim 6 6 12 8 --gridsize 1 1 2 4 --prec double \
  --tol 1e-6 --tolhq 1e-6 --niter 1000 --enable-testing true \
  --gtest_filter=EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2

"$QUDA_BUILD_DIR/tests/io_test" \
  --dim 4 4 8 8 --gridsize 1 1 2 4 \
  '--gtest_filter=Gauge/GaugeIOTest.*'
```

The validated run passed all three checks. The inverter's aggregate statistics printed
`-nan` for the one-solve sample because they exclude the first solve; the checked true
residual and GoogleTest result passed. A tuning-candidate regression warning appeared while
populating the fresh tunecache, so the run is correctness evidence, not performance evidence.
