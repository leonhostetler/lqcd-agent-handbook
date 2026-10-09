---
title: MILC CUDA 12 QUDA ks_spectrum stack on DeltaAI at MILC a5f8f9fa
summary: Reproduction notes for ks_spectrum_hisq at MILC a5f8f9fa on QUDA ba501e4f8, the OpenMP link flags it needs, and its one-gauge-configuration-per-process deflation limit.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Rebuilding or validating the DeltaAI MILC ks_spectrum_hisq stack with QUDA at or past MILC d17e9559, or deflating with QUDA-resident eigenvectors in it.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems/DeltaAI/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems/DeltaAI/sample.in
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems/DeltaAI/submit.sbatch
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/control.c#L280-L385
observed: "2026-10-07"
observed_on:
  machine: deltaai
  node_type: gpu-gh200
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
  toolchain:
    cuda: 12.9.41
    host_compiler: GNU 14.2.0 through Cray wrappers
    mpi: cray-mpich/9.0.1
---

# MILC CUDA 12 QUDA `ks_spectrum` stack on DeltaAI at `a5f8f9fa`

`stack.yaml` is canonical for commits, the composed profile, build options, measured cost, node
resources, numerical results, and validation limits. Read it together with
`software/milc/build.md` and the DeltaAI machine profile. Because `gpu-gh200` is the profile's
sole node type, it is the default unless the operator explicitly selects another type after the
profile changes.

## Build

Use the validated `quda-cuda12-milc-cg-2026q4` installation for `QUDA_HOME`, `QMPPAR`, and
`QIOPAR`, apply the `ks-spectrum-hisq-quda` profile, and materialise the machine options in
`stack.yaml` with the shared invocation in `software/milc/build.md`. Build in a disposable
worktree: the procedure copies the repository `Makefile` into `ks_spectrum` and builds objects in
the source tree.

Two departures from the `2026q3` record matter:

- **Name the OpenMP runtime on the link line.** A command-line `LDFLAGS` replaces the Makefile's
  own OpenMP additions (the mechanism is in `software/milc/build.md`), and the `2026q3` value of
  `-g` no longer links here. The value in `stack.yaml` carries `OPT` and `-fopenmp -lgomp`. After
  linking, `readelf -d` must list exactly one OpenMP runtime; at run time it resolved from the
  HPC SDK compiler library directory on the default library path.
- **Build serially.** `make -j1`. In parallel, objects compile before the target recipe has
  generated `quark_action.h` and fail.

At this MILC revision `libraries/Make_vanilla` overrides the library compiler with `mpicc`
(`software/milc/build.md`). DeltaAI's Cray MPICH provides an `mpicc` that wraps plain `gcc`, so the
`su3` library builds, but with that wrapper rather than the Cray `cc` named in `MY_CC`; check the
library compile lines of the build log.

MILC PR #102 (merge `ab5011f5`) removes both quirks: the `make -j` races and the `mpicc`
override. This record's commit precedes it, so the serial build and the wrapper observation stand
for reproducing it. A build past that merge is not validated by this record;
`software/milc/build.md` states what changed.

Confirm `DT_RPATH` names the composed install prefix and that the install and build-tree
`libquda.so` share one GNU Build ID, per `software/milc/quda-linkage.md`.

## Validate

Use the `ghx4-interactive` placement, environment block, and `srun` line of the `2026q3` notes,
with `sample.in` unchanged, a fresh tunecache per leg, the launcher's kill-on-bad-exit option,
and a per-step time limit. Acceptance is the `2026q3` contract: payload exit zero,
`RUNNING COMPLETED`, 24 QUDA CG convergence records under the requested true residual, the
`FLTIME: ... (HISQ QUDA D)` marker, and the correlator structure in `stack.yaml`. At this revision
the QUDA CG `CONGRAD5` lines carry `srcs = 1` even for single-source solves.

## Deflation: one gauge configuration per process

This stack also ran QUDA eigensolves and deflated CG through MILC. The first input set of a process
behaves: a fresh QUDA eigensolve, then converged deflated solves. **A later input set in the same
process does not**: it deflates with the first set's eigenvectors, no second eigensolve runs, and
in the validation run half its solves stalled orders of magnitude above tolerance while the run
reported `RUNNING COMPLETED` and exited 0. Run one gauge configuration per process when
eigenvectors are QUDA-resident. The mechanism and the cleanup call that removes the failure are in
`software/quda/internals/milc-deflation-space.md`.

To see which case a run is in, count `TRLM computed the requested` lines per input set; at the
default QUDA verbosity the restore itself prints nothing. And judge every deflated solve by its
true residual, never by the presence of a `Convergence at` line, which QUDA prints for a solve that
stopped at its iteration limit too.

The deflation test used a random `warm` field, whose lowest eigenvalues lie far below those of a
physical ensemble, and a Chebyshev window chosen for it (`stack.yaml`). Those parameters are a
property of the test field, not guidance for production.
