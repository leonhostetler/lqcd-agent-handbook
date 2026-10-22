---
title: QUDA CUDA 13 mg-staggered stack on Horizon
summary: The Horizon gpu-gb200 QUDA build of the mg-staggered profile, which the linked MILC multigrid stack composes; what differs from the tile-3 milc-cg stack, and what its native GCR-MG validation covers.
scope: [machine:horizon, software:quda]
load_when: Rebuilding, validating, or running with the quda-cuda13-mg-staggered-2026q4 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/CMakeLists.txt
  - agent-submitted build and validation runs reviewed in the working directory
observed: "2026-10-21"
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

# QUDA CUDA 13 `mg-staggered` on Horizon

Declare `gpu-gb200` first. `stack.yaml` is canonical for versions, the passed options, the
installed libraries' hashes and the validation. The modules, wrappers and launch mapping are those
of [`quda-cuda13-milc-cg-mrhs-tile3-2026q4`](../quda-cuda13-milc-cg-mrhs-tile3-2026q4/notes.md), at
the same QUDA commit and dependency revisions, with these differences:

- **The profile is `mg-staggered`**: multigrid on, coarse colours 24, 64, 96, 112 and 128,
  multigrid right-hand-side widths 8, 16, 32 and 64, the three-wide tile, and every test built
  and installed. A legal aggregation whose `nvec` is not in that list fails at run time.
- **The configure passes `QUDA_TARGET_TYPE=CUDA`** explicitly. With the profile and the machine
  options, that is everything the build was given; the build-record check passed against the
  cache and the source.
- **The system cmake was 3.31.8 on 2026-10-21**, not the 3.30.5 the 2026q4 stacks record. A
  build script that pins the cmake version should read the live one first. `module reset` loads
  the `cmake` module by default, so unload it and assert that it is gone.
- **The driver was 615.71.09** (`nvidia-smi` reports CUDA UMD 13.4), not the 2026q4 stacks'
  595.71.05.
- **Configure, build and install took 36m36s in one batch job on one board** at `--parallel 64`;
  the build stage alone took 35 min. Memory was not measured, since `/usr/bin/time` is not
  installed.

## What the validation shows

QUDA's native `staggered_invert_test`, three-level GCR-MG on a unit gauge, 16³×32 on four GPUs of
one board, the hierarchy of the Perlmutter
[`quda-cuda13-mg-staggered-2026q3`](../../../perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/notes.md)
validation: the transfers ran at `1 x 1 x 1 x 1` and `4 x 4 x 4 x 4`, and GCR converged in 18
iterations, as on Perlmutter, to a host-verified residual of 7.75e-7 against the requested 1e-6.
Multi-board MG and GPU-Direct RDMA across boards are validated through the composed
[`milc-cuda13-quda-ks-spectrum-mg-2026q4`](../milc-cuda13-quda-ks-spectrum-mg-2026q4/notes.md), not
natively. No eigensolve, deflated solve or QIO path ran.
