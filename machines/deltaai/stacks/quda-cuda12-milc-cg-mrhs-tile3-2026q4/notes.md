---
title: QUDA CUDA 12 milc-cg-mrhs-tile3 stack on DeltaAI
summary: The DeltaAI gpu-gh200 QUDA build with a three-wide multi-right-hand-side tile at QUDA 00c7ef33, which the production ks_spectrum campaigns run on; what differs from quda-cuda12-milc-cg-2026q4, and what its validation covers.
scope: [machine:deltaai, software:quda]
load_when: Rebuilding, validating, or running with the quda-cuda12-milc-cg-mrhs-tile3-2026q4 stack on DeltaAI.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt
  - operator-run build, production runs and probe runs reviewed in the working directory
observed: "2026-10-11"
observed_on:
  machine: deltaai
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 12.9
---

# QUDA CUDA 12 `milc-cg-mrhs-tile3` on DeltaAI

`stack.yaml` is canonical for versions, the passed options, the installed libraries' hashes and
the validation. The toolchain and dependency revisions are those of
[`quda-cuda12-milc-cg-2026q4`](../quda-cuda12-milc-cg-2026q4/stack.yaml), with these
differences:

- **The profile adds `-DQUDA_MAX_MULTI_RHS_TILE=3`**, so multi-source CG solves run three
  right-hand sides per dslash tile. It is a different stack from any build without it.
- **QUDA `00c7ef33`**, not `ba501e4f`.
- **The configure line passes no `CMAKE_INSTALL_LIBDIR`**, so the cache holds the default
  `lib64`; the core libraries still install under `lib/` and `libquda_test.so` under `lib64/`,
  as `installed_libraries` records.
- **`CRAY_ACCEL_TARGET=nvidia90` is exported by the build script, not passed to CMake**, so it
  is not among the recorded options; the toolchain's `target_module` carries it.

## What the validation shows

The staggered-CG throughput probe's QUDA legs ran `staggered_invert_test` at 40⁴ per rank on
one GPU, one node, two nodes and four nodes. On one GPU, 54 solves, single and in blocks of 12
through `invertMultiSrcQuda`, were verified against the host; the multi-rank points checked
convergence, the true residual and row-major rank order. Three production `ks_spectrum`
campaigns through the MILC interface, on 8 ranks over two nodes and 12 ranks over three: in 30
checked configurations every multi-shift and single-mass solve, with 1, 3 and 9 right-hand
sides, converged. The
`libqmp` this installs sums multi-byte values wrongly in `QMP_binary_reduction` on more than
one rank ([`../../../../software/qmp/binary-reduction.md`](../../../../software/qmp/binary-reduction.md)).
