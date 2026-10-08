---
title: QUDA CUDA 12 milc-cg stack on DeltaAI at QUDA ba501e4f8
summary: Reproduction notes for the DeltaAI milc-cg QUDA build at ba501e4f8 with its complete test suite, and the focused validation including one deflated-CG case.
scope: [machine:deltaai, software:quda]
load_when: Rebuilding or validating the quda-cuda12-milc-cg-2026q4 stack on DeltaAI, or composing a MILC application against it.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems/DeltaAI/compile_quda.sh
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems/DeltaAI/submit.sbatch
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/staggered_invert_test.cpp
observed: "2026-10-07"
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
    mpi: cray-mpich/9.0.1
---

# QUDA CUDA 12 `milc-cg` on DeltaAI at `ba501e4f8`

`stack.yaml` is canonical for tested commits, dependency revisions, build cost, and validation
results. Because `gpu-gh200` is the DeltaAI profile's sole node type, it is the default unless the
operator explicitly selects another type after the profile changes.

## Configure and build

Use the configure line in
[`../quda-cuda12-milc-cg-2026q3/notes.md`](../quda-cuda12-milc-cg-2026q3/notes.md) unchanged: the
`milc-cg` profile options, the Cray wrappers, `sm_90`, `CMAKE_INSTALL_LIBDIR=lib`, and the
all-tests options. This build used a fresh full-history clone of `develop` and a fresh
out-of-source build directory in the default environment, with `CRAY_ACCEL_TARGET=nvidia90`.

Build at `--parallel 6` on the login node. With every test target included, the largest single
compile process reached about 1.5 GiB, so six jobs stay under the 16 GiB per-user login-node
memory throttle described in `../../notes.md`; the measured wallclock is in `stack.yaml`.
Configure needs the three hosts named in `software/quda/build.md`.

The download step selects newer CCCL here than for the `2026q3` stack; QMP, QIO, and Eigen are
unchanged. `stack.yaml` records each revision.

## Focused validation

Use the `ghx4-interactive` placement, environment block, `srun` line, and the three focused test
commands in the `2026q3` notes, and add a deflated inverter case:

```bash
"$QUDA_BUILD_DIR/tests/staggered_invert_test" \
  --dslash-type asqtad --ngcrkrylov 8 --compute-fat-long true \
  --dim 6 6 6 8 --gridsize 1 1 1 4 --prec double \
  --tol 1e-6 --tolhq 1e-6 --niter 1000 --enable-testing true \
  --inv-deflate true --eig-n-ev 16 --eig-n-kr 32 --eig-n-conv 16 \
  --eig-tol 1e-8 --eig-max-restarts 200 \
  --gtest_filter=EvenOdd/StaggeredInvertTest.verify/cg_mat_pc_direct_pc_double_l2
```

Give every test a fresh `QUDA_RESOURCE_PATH`, pass the launcher's kill-on-bad-exit option and a
per-step time limit, and judge each by its gtest verdict lines with colour codes stripped and
skips counted separately, as `software/quda/build.md` requires. Confirm `gdr=1` from the
tunecache policy keys rather than from the log, per
`software/quda/runtime-environment.md`.

All four checks passed. The deflated case shows that the eigensolve and deflated CG path runs and
meets its residual; on this small random field deflation saved one iteration, so it says nothing
about acceleration.

Do not add QUDA's eigensolver gtest suite (`staggered_eigensolve_test --enable-testing true`) to
this validation as it stands. The suite disables polynomial acceleration, one of its
smallest-real cases did not converge in 1000 restarts on the random 6x6x6x8 field, and the
resulting `errorQuda` aborts every rank, so every later case in the suite goes unreported.
