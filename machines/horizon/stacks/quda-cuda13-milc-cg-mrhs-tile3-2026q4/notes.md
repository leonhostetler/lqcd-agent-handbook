---
title: QUDA CUDA 13 milc-cg-mrhs-tile3 stack on Horizon
summary: The Horizon gpu-gb200 QUDA build with a three-wide multi-right-hand-side tile, which the production ks_spectrum campaigns and the throughput probe ran on; what differs from the 2026q3 milc-cg stack, and what its validation covers.
scope: [machine:horizon, software:quda]
load_when: Rebuilding, validating, or running with the quda-cuda13-milc-cg-mrhs-tile3-2026q4 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/CMakeLists.txt#L213-L216
  - operator-submitted build and probe runs reviewed in the working directory
observed: "2026-10-10"
observed_on:
  machine: horizon
  software:
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
  toolchain:
    cuda: "13.3"
    ucx: 1.22.0
---

# QUDA CUDA 13 `milc-cg-mrhs-tile3` on Horizon

Declare `gpu-gb200` first. `stack.yaml` is canonical for versions, the passed options, the
installed libraries' hashes and the validation. The toolchain, the configure line and the launch
mapping are those of [`quda-cuda13-milc-cg-2026q3`](../quda-cuda13-milc-cg-2026q3/notes.md), with
these differences:

- **The profile adds `-DQUDA_MAX_MULTI_RHS_TILE=3`** (default 1, `CMakeLists.txt` L213–L216), so
  multi-source CG solves run three right-hand sides per dslash tile. It is a different stack from
  any build without it.
- **QUDA `ba501e4f8`**, not `00c7ef33`; the dependencies are the same revisions.
- **Configure, build and install ran in one batch job**, which cloned QUDA and downloaded QMP,
  QIO, Eigen and CCCL at configure, so Horizon's compute nodes reached GitHub and GitLab on
  2026-10-09. The build was not timed or measured.
- **The runs used 32 OpenMP threads per rank**, in 36-core blocks.

## What the validation shows

The staggered-CG throughput probe's QUDA legs, at 40⁴ per rank: on one GPU the HISQ dslash
matches the host reference for 1 and 12 right-hand sides, and 54 CG solves, 48 of them in blocks
of 12 through `invertMultiSrcQuda`, agree with host verification below the 1e-8 target. On 4, 8
and 16 ranks (one, two and four boards) every solve converged. QIO was not exercised; its
multi-rank writes stay unsafe on `$HOME` and `$SCRATCH`. The `libqmp` this installs sums
multi-byte values wrongly in `QMP_binary_reduction` on more than one rank
([`../../../../software/qmp/binary-reduction.md`](../../../../software/qmp/binary-reduction.md)).
