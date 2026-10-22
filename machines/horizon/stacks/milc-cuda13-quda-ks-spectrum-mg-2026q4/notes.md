---
title: MILC CUDA 13 QUDA staggered-MG ks_spectrum stack on Horizon
summary: The Horizon gpu-gb200 ks_spectrum_hisq build with MILC's QUDA multigrid path, linked against the mg-staggered QUDA stack; what differs from the tile-3 MILC stack, what its validation covers, and why a synthetic-field check needs a heavy mass.
scope: [machine:horizon, software:milc]
load_when: Rebuilding, validating, or launching the milc-cuda13-quda-ks-spectrum-mg-2026q4 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/mat_invert.c
  - agent-submitted build and validation runs reviewed in the working directory
observed: "2026-10-22"
observed_on:
  machine: horizon
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
  toolchain:
    cuda: "13.3"
---

# MILC `ks_spectrum_hisq` with QUDA multigrid on Horizon

Declare `gpu-gb200` first. Build against the install of
[`quda-cuda13-mg-staggered-2026q4`](../quda-cuda13-mg-staggered-2026q4/notes.md). `stack.yaml` is
canonical for the passed make variables and the validation. The make command is that of
[`milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4`](../milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4/notes.md),
at the same MILC commit, with these differences:

- **The profile is `ks-spectrum-hisq-quda-mg`**: `KSCGMULTI` adds `-DMULTIGRID`, and the QUDA it
  links is the `mg-staggered` build.
- **The build was timed**: 194 s at `-j 1` from a checkout with no objects, libraries included.
- **The link records its library path as `DT_RUNPATH`, not `DT_RPATH`**: the QUDA install's
  `lib`, Open MPI's `lib` and the NVHPC compilers' `lib`. `LD_LIBRARY_PATH` outranks a run path,
  so a launcher that inherits one can load a different `libquda.so` than the stack's hash names.
  Check with `ldd` before launch that `libquda.so` resolves from the intended install.
- **The OpenMP runtime is NVHPC's `libnvomp.so`**, the only one in `NEEDED`.

## What the validation shows

One warm 72×96×48×48 field and one point source, an MG set and a UML reference set at one mass,
on one board (4 ranks, `2 2 1 1`) and two boards (8 ranks, `2 2 2 1`). It used a four-level
hierarchy with blocks `6 6 6 4` and `3 2 2 3`, no coarsest-level deflation, and `rebuild_type
THIN`.

- At both placements the hierarchy was built with the requested blocks, and MILC reported that
  the fresh-link signal was consumed by hierarchy creation with no first-solve update.
- At mass 0.5, every MG and UML solve met the 1e-8 target, MILC's MG timer label appeared on
  every MG solve, and no fallback warning was printed.
- MG and UML pion correlators agreed to 3e-14 of the correlator's scale, and the two-board
  correlators agreed with the one-board ones.
- The two-board tunecache shows GPU-Direct RDMA in force (`gdr=1`, `p2p=7`).

**On this warm field, check correctness at a heavy mass.** The field is strongly disordered
(plaquette 0.337), and at a light mass (below 0.02) no MG solve converged within 40 minutes at
either placement, after setups of 20–38 min from an empty tunecache. That result is about the
field, not the stack: it was observed once, the setup's near-null solves took over a thousand
iterations per vector, and the level-1 coarse solver barely reduced its residual. It shows nothing
about convergence on a real configuration, which this record does not validate. A light-mass
check belongs on a real configuration.
