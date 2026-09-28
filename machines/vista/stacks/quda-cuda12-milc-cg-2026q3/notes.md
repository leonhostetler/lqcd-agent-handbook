---
title: QUDA CUDA 12 milc-cg stack on Vista
summary: Superseded for multi-rank GPU work by quda-cuda13-milc-cg-2026q3, because its UCX 1.17 transport breaks GPUDirect RDMA. Reproduction commands, the installed-test library-directory fix, the multi-node GDR test failure traced to its UCX 1.17 transport, and the unresolved multi-rank QIO failure for the Vista gpu-gh200 QUDA stack built with GNU 14 and CUDA 12.
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

> **Superseded for multi-rank GPU work — use
> [`quda-cuda13-milc-cg-2026q3`](../quda-cuda13-milc-cg-2026q3/notes.md).** This stack's
> `openmpi/5.0.5` is pinned to UCX 1.17.0, which cannot register GPU memory with UCX's default
> `gdr_copy` transport present, so GPUDirect RDMA fails for small halos and is not in use for
> large ones ([`../../gpu-aware-mpi.md`](../../gpu-aware-mpi.md)). Use this stack only for
> single-GPU work or to reproduce its own recorded results.

Declare `gpu-gh200` before using these notes; Vista has two node types. `stack.yaml` is
canonical for supersession, tested versions, build cost, validation results, and scope
limits.

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

## Multi-node tests fail: UCX 1.17 with `gdr_copy`

**Use [`quda-cuda13-milc-cg-2026q3`](../quda-cuda13-milc-cg-2026q3/notes.md) for multi-rank
GPU work instead.** This stack's `openmpi/5.0.5` is pinned to UCX 1.17.0, whose GPU-memory
registration fails whenever UCX's `gdr_copy` transport is present — which it is by default.
[`../../gpu-aware-mpi.md`](../../gpu-aware-mpi.md) owns the mechanism, the evidence, and the
workarounds; this section records what it did to this stack's tests.

Multi-rank runs used one rank per node through `ibrun`, which with one task per node passes
`--bind-to none` to `mpirun`, `--gridsize 1 1 1 N`, and fresh per-leg tunecaches.

**GDR device-buffer send fails in QUDA's own tests.** With `QUDA_ENABLE_GDR=1`, the dslash
and inverter tests abort on 2 and 4 nodes with UCX's
`ibv_reg_dmabuf_mr(...) failed: Invalid argument` on memory it classifies as `(cuda)`.
Restricting `QUDA_ENABLE_DSLASH_POLICY` separates the policies
([policy enum](https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_policy.hpp#L1655-L1676)):

| GDR | Policies allowed | Result |
|---|---|---|
| 0 | default | pass |
| 1 | `0,1` (host-staged) | pass |
| 1 | `2,3` (GDR send and receive) | fail |
| 1 | `4,5` (host-staged send, GDR receive) | pass |
| 1 | `10,11` (zero-copy pack, GDR receive) | pass |

Each pass is backed by dslash policy keys in its tunecache showing the inter-node dimension
partitioned. The tests' halos are a few kilobytes, inside UCX 1.17's eager zero-copy band,
which registers the send buffer. With a 16x16x8x16 local volume the same policies passed, but
the protocol tables showed only host-sourced rendezvous fetches. MILC's 4-node run on this
stack, at that local volume, therefore most likely completed without GPU-to-GPU transfers as
well — an inference, since that run did not record protocol tables.

With this stack's toolchain, `UCX_TLS=^gdr_copy` removed the failure in a one-node,
two-rank check over the HCA while keeping registered zero-copy; it has not been run across
nodes. `QUDA_ENABLE_GDR=0` and the policy restrictions above also avoid it, without GDR.

**QIO read-back corruption.** Multi-rank `io_test` writes the gauge field with status 0 and
then fails the read with `QIO_compare_checksum: Checksum mismatch` (status -14). It fails
with GDR on and off, from both `$HOME` and `$SCRATCH` (both VAST), and identically on the
cuda13 stack, so it is neither a GDR nor a toolchain effect. The single-rank test passes.
Treat multi-rank QIO gauge I/O through this stack as unvalidated.

## Transport facts recorded with this stack

`libmpi.so` from `openmpi/5.0.5` resolves `libucp` and `libucs` from UCX 1.17.0 through
`DT_RPATH`, even though the module environment lists `ucx/1.20.0`; `LD_LIBRARY_PATH` cannot
redirect it. That version is the cause of the GDR failure above.
