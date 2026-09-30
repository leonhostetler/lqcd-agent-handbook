---
title: MILC CUDA 13 QUDA ks_spectrum stack on Horizon
summary: Reproduction notes for the Horizon gpu-gb200 MILC ks_spectrum_hisq stack linked against the CUDA 13 QUDA stack, validated on one GPU, one four-GPU board, and two boards, with the launch settings that keep unbound ranks from sharing a core.
scope: [machine:horizon, software:milc]
load_when: Rebuilding, validating, or launching the Horizon MILC ks_spectrum_hisq stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L636-L642
  - operator-submitted validation runs reviewed in the working directory
observed: "2026-09-29"
observed_on:
  machine: horizon
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
  toolchain:
    cuda: 13.3.73
---

# MILC `ks_spectrum_hisq` with QUDA on Horizon

Declare `gpu-gb200` first. Build against the QUDA install of
[`quda-cuda13-milc-cg-2026q3`](../quda-cuda13-milc-cg-2026q3/notes.md), whose notes own the
toolchain and the launch mapping. `stack.yaml` is canonical for tested versions, cost, and
validation results. The shared invocation is in `software/milc/build.md`.

## Build

Materialize `machine_args` from `stack.yaml` with the prefixes of the loaded `cuda/13.3`
module and the QUDA install, as on Vista. It builds on a login node in about a minute at one
job. The GPU-less login node has no driver `libcuda`, and the link resolves `-lcuda` and
`-lnvidia-ml` from the toolkit's stub libraries, which the `cuda` module puts on
`LIBRARY_PATH`. The executable records no path to the stubs and loads the driver's libraries
on a compute node. Its run path names the QUDA install and Open MPI 5.0.11.

## Proofread on the login node

`tools/milc-proofread-input.sh` proofreads this executable on the GPU-less login node as it is.
From version 1.1.0 it keeps MPI's GPU support out of the parse-only run and, when the
executable's `libcuda.so.1` cannot be resolved, links the toolkit's stubs from the `cuda`
module's `LIBRARY_PATH`. Load the stack's modules first; without them the tool finds no stubs
and reports the proofread indeterminate rather than guessing.

## Launch

- **One GPU, or a subset of the allocation (`ibrun -n N -o M`):** `ibrun` launches these with
  `--bind-to none`, so set `OMP_PROC_BIND=false`. With `spread` every unbound rank pins its
  thread 0 to core 0, and the four-rank leg ran at about 13 ms per multi-GPU dslash instead of
  about 42 us: 544 s for a solve one GPU finished in 0.84 s. It was still numerically correct,
  which is what makes it easy to miss.
- **The whole allocation:** bind consecutive 36-core blocks as the QUDA stack notes describe,
  and `OMP_PROC_BIND=spread` is then safe.
- `OMP_NUM_THREADS` must be set explicitly; TACC's default environment sets it to 1.

## What the validation shows

The upstream `systems/Vista/sample.in` (16^3 x 32) ran unchanged apart from its node geometry
on one GPU, on four ranks of one board, and on eight ranks of two boards. All 24 CG solves in
every leg converged under the 1e-8 true-residual target. The 12 correlator records agree across
the three geometries to the file's printed precision, after structural checks of every record.
Other lattice sizes, decompositions, deflation, and any QIO gauge I/O through this stack remain
unvalidated. Multi-rank QIO writes, including MILC's `save_parallel_*`, are unsafe on `$HOME` and
`$SCRATCH` because of the open upstream defect in
[`../../../../software/qio/parallel-singlefile-writes.md`](../../../../software/qio/parallel-singlefile-writes.md).
