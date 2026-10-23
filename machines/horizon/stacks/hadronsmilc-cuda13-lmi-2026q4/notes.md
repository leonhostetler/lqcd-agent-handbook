---
title: HadronsMILC CUDA 13 LMI stack on Horizon
summary: The Horizon gpu-gb200 build of the HadronsMILC 0.3.0 release set with two header fixes, how to reproduce it, and what its one-board validation covers — test suite, GPU against CPU, and the pyfm LMI chain on one and four GPUs.
scope: [machine:horizon, software:hadronsmilc]
load_when: Rebuilding, validating, or running LMI work with the hadronsmilc-cuda13-lmi-2026q4 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/DEPENDENCIES
  - operator-submitted build and validation jobs reviewed in the working directory
observed: "2026-10-23"
observed_on:
  machine: horizon
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
  toolchain:
    cuda: "13.3"
    ucx: 1.22.0
---

# HadronsMILC CUDA 13 LMI on Horizon

Declare `gpu-gb200` first. `stack.yaml` is canonical for versions, options, cost and
validation. It composes `../hadrons-cuda13-hadronsmilc-base-2026q4/`, which is built on
`../grid-cuda13-hadrons-staggered-2026q4/`.

## Reproduce

1. Build the Grid stack and stamp its `Grid/Version.h`.
2. Copy the two overlay headers named in `stack.yaml` from their Grid commits (`git show
   <commit>:<path>`) into `<overlay-prefix>/include/` at the same relative paths, and check
   their sha256.
3. Build the Hadrons stack (its notes give the commands, including `GIT_DIR`) and confirm
   `hadrons-config --git` prints the commit.
4. HadronsMILC 4a19a15: `./bootstrap.sh`; with Hadrons' `bin/` also on `PATH`, configure with
   `--enable-strict-pins` and the overlay in `CXXFLAGS`; `make -j48 -C src`; link `HadronsMILC`
   and `HadronsContractor` with gold; `make install`.
5. Check the dependency records for the overlay (`software/hadronsmilc/build.md`) and run
   `HadronsMILC --version` through the launcher on a compute node: expect the banner recorded
   in `stack.yaml`, ending `Dependency pins=match`.

| File | sha256 |
|---|---|
| `<hadrons-prefix>/lib/libHadrons.a` | `fecf1fd1a63cc23d120bec27f837643125cf8ff19ccabaac279d32e76f744216` |
| `<hadronsmilc-prefix>/lib/libHadronsMILC.a` | `43ed86b43fa6d36a1ee4994daf9d9aa4af6db3d31feca6ba0a46f76c67531592` |
| `<hadronsmilc-prefix>/bin/HadronsMILC` | `9298ff5a77b01f51a29037c015aa7cb02338fa2e5046db880619face1fe4fc27` |
| `<hadronsmilc-prefix>/bin/HadronsContractor` | `7edf334b61e2da00748bfadcd2acc21d64fd728d8e1225a307510f2d23fd1677` |

## What the validation shows

- **Every GPU-specific change is checked.** The fixed `GeneralLocalStencil.h` gives smeared
  links bitwise equal to stock Grid's; the fixed `StagGamma.h` is exercised by the CB-pair
  meson-field test and by Grid's A2A stencil test (Grid stack).
- **The GPU build agrees with a CPU build of the same commits** to 1.8 × 10⁻⁸ on every output
  of HadronsMILC's own (corrected) test suite.
- **The production `lmi` chain is decomposition-independent.** A pyfm-generated input on 8⁴ gave
  the same correlators, eigenvalues and `a2aLL` contractions on one GPU and on four (time split
  or whole) to 4.5 × 10⁻¹⁰, and on the CPU build to 5 × 10⁻⁹. The Lanczos needed its Chebyshev
  lower bound above the 32nd eigenvalue: a first attempt with `alpha` 0.2 stalled and ran on NaN
  until its step time limit (`software/grid/solvers/staggered.md`).

At 8⁴ every HadronsMILC run took 10–14 s and used 3.3 GiB per GPU, dominated by `--shm 2048`;
none of that says anything about production cost.

## Before production

Not covered here, and needed before a 144³×288 campaign on this stack: a multi-node run; a
Lanczos `alpha` checked against that ensemble's spectrum; a decomposition from the allowed set
(`software/hadronsmilc/applications/lmi.md`); and, before any comparison with earlier results,
the provenance of those results (`software/hadronsmilc/README.md`).
