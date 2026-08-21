---
title: QUDA CUDA 13 mg-staggered stack on Perlmutter
summary: Reproduction commands, validated hierarchy, and runtime corrections for native staggered GCR-MG.
scope: [machine:perlmutter, software:quda, solver:multigrid, fermion:staggered]
load_when: Rebuilding or validating the quda-cuda13-mg-staggered-2026q3 stack.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_invert_test.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_invert_test_gtest.hpp
  - operator-submitted validation run reviewed during the 2026-08-20 handbook developer session; raw scheduler output is not committed
observed: "2026-08-20"
observed_on:
  machine: perlmutter
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
  toolchain:
    cuda: 13.2.78
---

# QUDA CUDA 13 `mg-staggered` on Perlmutter

Load the Perlmutter machine profile, declare `gpu-a100-40`, and resolve the
`mg-staggered` profile before using these notes. `stack.yaml` is canonical for
the tested versions, toolchain, historical build cost, hierarchy, and validation result.

This is a bounded sample stack for validating one native QUDA GCR-MG path. Its three-level
synthetic-unit-gauge hierarchy is not a production recommendation, a general hierarchy default,
or a validated linked-MILC target.

## Layout, configure, and build

The validated project layout keeps the QUDA checkout and build tree as siblings, with the
install prefix under the build tree:

```text
<working-directory>/
├── quda/
└── build/
    └── usqcd/
```

Use a full, clean QUDA checkout at the tested commit. After `module reset`, configure with
the Cray wrappers and the complete profile option set:

```bash
export CRAY_ACCEL_TARGET=nvidia80

cmake --fresh -S "$QUDA_SOURCE_DIR" -B "$QUDA_BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$QUDA_BUILD_DIR/usqcd" \
  -DCMAKE_C_COMPILER=cc \
  -DCMAKE_CXX_COMPILER=CC \
  -DQUDA_TARGET_TYPE=CUDA \
  -DQUDA_GPU_ARCH=sm_80 \
  -DQUDA_BUILD_SHAREDLIB=ON \
  -DQUDA_DIRAC_DEFAULT_OFF=ON \
  -DQUDA_DIRAC_STAGGERED=ON \
  -DQUDA_INTERFACE_MILC=ON \
  -DQUDA_INTERFACE_QDP=ON \
  -DQUDA_QMP=ON \
  -DQUDA_MPI=OFF \
  -DQUDA_QIO=ON \
  -DQUDA_MULTIGRID=ON \
  -DQUDA_MULTIGRID_NVEC_LIST=24,64,96,112,128 \
  -DQUDA_MULTIGRID_MRHS_LIST=8,16,32,64 \
  -DQUDA_MAX_MULTI_RHS_TILE=3 \
  -DQUDA_USE_EIGEN=ON \
  -DQUDA_DOWNLOAD_EIGEN=ON \
  -DQUDA_DOWNLOAD_USQCD=ON \
  -DQUDA_BUILD_ALL_TESTS=ON \
  -DQUDA_INSTALL_ALL_TESTS=ON

cmake --build "$QUDA_BUILD_DIR" --target install --parallel 16
```

Run the 16-way build on an allocated `gpu-a100-40` compute node, not a login node.
Configuration requires network access if QMP, QIO, and Eigen are not already present.
A timed-out build is resumable: rerun the same configure command without `--fresh` and
then rerun `cmake --build` against the unchanged tree and cache.

The historical build behind this stack used the same capability options but had
`QUDA_BUILD_ALL_TESTS=OFF` and `QUDA_INSTALL_ALL_TESTS=OFF` in its cache. The required
`staggered_invert_test` target was compiled separately after the install completed. The
commands above intentionally implement the current handbook rule that all available tests
are built and installed by default. Consequently, the historical cost in `stack.yaml` is
not an estimate for a fresh all-tests build.

## Placement and environment

Use one node, four ranks, four GPUs, and a `1 x 1 x 1 x 4` rank grid. Disable Slurm's
per-rank GPU visibility so QUDA can map local rank to device ordinal:

```bash
export MPICH_GPU_SUPPORT_ENABLED=1
export QUDA_ENABLE_GDR=1
export QUDA_RESOURCE_PATH="<fresh-writable-tunecache-directory>"
export OMP_NUM_THREADS=16
export OMP_PLACES=cores
export OMP_PROC_BIND=close
export SRUN_CPUS_PER_TASK=16
```

All four ranks must see all four 40 GB A100 devices. The validated `srun` shape is
`--nodes=1 --ntasks=4 --cpus-per-task=16 --cpu-bind=cores --gpus-per-task=1
--gpu-bind=none --kill-on-bad-exit=1`.

## Focused native validation

From the allocation shell, launch the test executable with `srun`:

```bash
srun \
  --nodes=1 \
  --ntasks=4 \
  --cpus-per-task=16 \
  --cpu-bind=cores \
  --gpus-per-task=1 \
  --gpu-bind=none \
  --kill-on-bad-exit=1 \
  "$QUDA_BUILD_DIR/tests/staggered_invert_test" \
  --dslash-type asqtad \
  --compute-fat-long true \
  --unit-gauge true \
  --dim 16 16 16 32 \
  --gridsize 1 1 1 4 \
  --prec double \
  --prec-sloppy single \
  --prec-precondition single \
  --prec-null single \
  --recon 18 \
  --recon-sloppy 18 \
  --recon-precondition 18 \
  --mass 0.1 \
  --tol 1e-6 \
  --tolhq 1e-6 \
  --niter 1000 \
  --nrepeat 1 \
  --nsrc 1 \
  --inv-type gcr \
  --solve-type direct \
  --solution-type mat \
  --ngcrkrylov 8 \
  --pipeline 0 \
  --inv-multigrid true \
  --mg-levels 3 \
  --mg-staggered-coarsen-type kd-optimized \
  --mg-block-size 0 1 1 1 1 \
  --mg-nvec 0 3 \
  --mg-nvec-batch 0 1 \
  --mg-setup-use-mma 0 false \
  --mg-smoother-solve-type 0 direct-pc \
  --mg-block-size 1 4 4 4 4 \
  --mg-nvec 1 64 \
  --mg-nvec-batch 1 8 \
  --mg-setup-use-mma 1 true \
  --mg-smoother-solve-type 1 direct \
  --mg-allow-truncation false \
  --mg-verbosity 0 verbose \
  --mg-verbosity 1 verbose \
  --mg-verbosity 2 verbose \
  --verbosity verbose \
  --verify true \
  --enable-testing false
```

The last option is intentional. In the observed source, the GoogleTest `no_schwarz` tuple
sets `inv_type_precondition` to invalid, while the native non-GTest path injects
`QUDA_MG_INVERTER` when `--inv-multigrid true` is selected. Thus
`--enable-testing false` still runs `staggered_invert_test` and its host verification; it
selects the executable's native path instead of a GoogleTest parameter tuple.

Optimized KD construction at MG level 0 reads the next smoother entry and requires
`QUDA_DIRECT_SOLVE`. Keep `--mg-smoother-solve-type 1 direct`; using `direct-pc` there
stops with `Invalid solve type 2 for optimized KD operator`. The level-0 `direct-pc`
entry is valid for the outer fine smoother.

Accept the run only if all of the following are present:

- transfer reports `1 x 1 x 1 x 1` at level 0 and `4 x 4 x 4 x 4` at level 1;
- `MG Setup Done` and a completed outer solve are reported;
- the host L2 relative residual is at most the predeclared acceptance limit; and
- the process exits zero without fatal, error, or failure markers.

The recorded run requested `1e-6` and produced matching QUDA and host L2 residuals of
`7.260597e-07`. Treat its setup and solve rates as validation observations only. The run
uses a synthetic unit gauge and does not validate the compiled MILC interface, QIO path,
production gauge fields, other hierarchy shapes, or benchmark performance.
