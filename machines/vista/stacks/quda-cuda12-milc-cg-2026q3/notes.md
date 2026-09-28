---
title: QUDA CUDA 12 milc-cg stack on Vista
summary: Reproduction commands, the installed-test library-directory fix, and the unresolved multi-node GDR and QIO test failures for the Vista gpu-gh200 QUDA stack.
scope: [machine:vista, software:quda]
load_when: Rebuilding, validating, or running multi-rank tests of the quda-cuda12-milc-cg-2026q3 stack on Vista.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Vista/compile_quda.sh
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L529-L532
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/CMakeLists.txt#L22
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_policy.hpp#L1655-L1676
  - operator-submitted validation and debugging runs reviewed in the working directory
observed: "2026-09-28"
observed_on:
  machine: vista
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 12.8.93
---

# QUDA CUDA 12 `milc-cg` on Vista

Declare `gpu-gh200` before using these notes; Vista has two node types. `stack.yaml` is
canonical for tested versions, build cost, validation results, and scope limits.

## Toolchain

Use one GNU toolchain for QUDA and MILC alike:

```bash
module reset
module load gcc/14.2.0 cuda/12.8 openmpi/5.0.5 cmake
```

`cuda/12.9` is offered only with `gcc/15.1.0` or the NVIDIA compilers, and CUDA 12.9's host
configuration rejects GNU newer than 14, so GNU 14.2 with CUDA 12.8 is the supported GNU
pairing. The upstream `systems/Vista/compile_quda.sh` instead builds with the NVIDIA
compiler module; that is a different toolchain from this stack.

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

Build on a compute node; the login-node limits in `machines/vista/notes.md` rule out this
parallelism. Configure downloads QMP, QIO, Eigen, and CCCL.

**Set `CMAKE_INSTALL_LIBDIR=lib`.** On this system `GNUInstallDirs` selects `lib64`, so
without it `libquda_test.so` installs to `usqcd/lib64`
([`tests/CMakeLists.txt:22`](https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/CMakeLists.txt#L22)),
while QUDA hard-codes the installed run path to `${CMAKE_INSTALL_PREFIX}/lib`
([`CMakeLists.txt`](https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L529-L532)).
Every installed test then fails with `libquda_test.so: cannot open shared object file`. The
build-tree tests are unaffected. Applying the option to an existing build and reinstalling
recompiled QMP and relinked QUDA, yet `libquda.so`, `libqmp.so`, `libqio.so`, and
`liblime.so` came out byte-identical, so an executable already linked against the install
was not invalidated.

Load `gcc/14.2.0` at run time as well. Neither the QUDA libraries' run path nor an
application's records GNU 14's runtime directory, and the system `libstdc++` lacks
`GLIBCXX_3.4.31`/`3.4.32`.

## Validate on one GPU

```bash
export QUDA_RESOURCE_PATH=<fresh gpu-gh200 tunecache directory>
mpirun -np 1 --bind-to none "$QUDA_BUILD_DIR/usqcd/bin/staggered_dslash_test" \
  --dslash-type asqtad --test MatPC --dim 4 4 4 8 --gridsize 1 1 1 1 \
  --compute-fat-long true --prec single --niter 10 --gtest_filter=StaggeredDslashTest.verify
mpirun -np 1 --bind-to none "$QUDA_BUILD_DIR/usqcd/bin/staggered_invert_test" \
  --dslash-type asqtad --ngcrkrylov 8 --compute-fat-long true --dim 6 6 6 8 \
  --gridsize 1 1 1 1 --prec double --tol 1e-6 --tolhq 1e-6 --niter 1000 \
  --enable-testing true \
  --gtest_filter=EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2
mpirun -np 1 --bind-to none "$QUDA_BUILD_DIR/usqcd/bin/io_test" \
  --dim 4 4 4 8 --gridsize 1 1 1 1 '--gtest_filter=Gauge/GaugeIOTest.*'
```

## Multi-node tests fail: not yet explained

Multi-rank runs used one rank per node through `ibrun`, which with one task per node passes
`--bind-to none` to `mpirun`, `--gridsize 1 1 1 N`, and fresh per-leg tunecaches.

**GDR device-buffer policies fail in QUDA's own tests.** With `QUDA_ENABLE_GDR=1`, the
dslash and inverter tests abort on 2 and 4 nodes after UCX reports
`ibv_reg_dmabuf_mr(...) failed: Invalid argument` and cannot register memory it classifies
as `(cuda)`. Restricting `QUDA_ENABLE_DSLASH_POLICY` isolates it
([policy enum](https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_policy.hpp#L1655-L1676)):

| GDR | Policies allowed | Result |
|---|---|---|
| 0 | default | pass |
| 1 | `0,1` (host-staged) | pass |
| 1 | `2,3,4,5` (device buffers to MPI) | fail |
| 1 | `10,11` (zero-copy pack, GDR receive) | pass |

Each pass is backed by dslash policy keys in its tunecache showing the inter-node dimension
partitioned; a pass without them is not evidence. Since the passing `10,11` policies receive
through GDR, the failing operation is probably a GDR *send* from a device buffer — an
inference, because policies `2,3` were not separated from `4,5`. The composed MILC
`ks_spectrum_hisq` ran on 4 nodes with GDR on and the same enabled policy set without this
error; why it escapes is not established.

Until resolved: run QUDA's native multi-rank tests with `QUDA_ENABLE_GDR=0`, or with GDR on
and `QUDA_ENABLE_DSLASH_POLICY=0,1,10,11`. These are candidate workarounds, validated only for
the dslash and inverter tests above, not as fixes.

**QIO read-back corruption.** Multi-rank `io_test` writes the gauge field with status 0 and
then fails the read with `QIO_compare_checksum: Checksum mismatch` (status -14). It fails
with GDR on and off, and from both `$HOME` and `$SCRATCH` (both VAST); the single-rank test
passes. Treat multi-rank QIO gauge I/O through this stack as unvalidated.

## Transport facts recorded with this stack

`libmpi.so` from `openmpi/5.0.5` resolves `libucp` and `libucs` from UCX 1.17.0, the version
Open MPI was built against, even though the module environment lists `ucx/1.20.0`; check
`ldd` on `libmpi.so` rather than the module list when recording the UCX in use.
