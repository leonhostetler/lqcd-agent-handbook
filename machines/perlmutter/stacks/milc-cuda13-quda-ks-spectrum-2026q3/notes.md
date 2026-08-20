---
title: MILC CUDA 13 QUDA ks_spectrum stack on Perlmutter
summary: Reproduction notes for the validated one-node QUDA-enabled MILC ks_spectrum_hisq application stack.
scope: [machine:perlmutter, software:milc, software:quda]
load_when: Rebuilding or validating the Perlmutter MILC ks_spectrum_hisq stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Perlmutter_GPU/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Perlmutter_GPU/sample.in
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Perlmutter_GPU/bind.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c
observed: "2026-08-20"
observed_on:
  machine: perlmutter
  node_type: gpu-a100-40
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
  toolchain:
    cuda: 13.2.78
    host_compiler: GNU 14.3.0 through Cray wrappers
    mpi: cray-mpich/9.1.0
---

# MILC CUDA 13 QUDA `ks_spectrum` stack on Perlmutter

`stack.yaml` is canonical for commits, the composed profile, build options, measured cost,
node resources, numerical results, and validation limits. Read it together with
`software/milc/build.md` and the Perlmutter machine profile.

## Build from a disposable checkout

Use the already validated Perlmutter QUDA `milc-cg` installation for `QUDA_HOME`, `QMPPAR`,
and `QIOPAR`. Build MILC in a fresh full checkout at the recorded `develop` commit because
the procedure copies the repository `Makefile` into `ks_spectrum` and creates objects in
the source tree. The shared build playbook still governs source acquisition, status checks,
and cost recording.

Apply the `ks-spectrum-hisq-quda` profile and the machine options in `stack.yaml`. The
material adaptation from the upstream Perlmutter GPU compile script is to use the installed
QUDA prefix for all three dependency roots; the install contains the QUDA, QMP, and QIO
headers and libraries used by this build. The MILC Makefile derives its CUDA and QUDA link
flags from `CUDA_HOME` and `QUDA_HOME`.

Build with the recorded single-job parallelism. Verify the executable's shared-library
resolution before preparing a compute-node test.

## One-node validation pattern

Use the upstream `systems/Perlmutter_GPU/sample.in` unchanged with four ranks and four GPUs
on `gpu-a100-40`. Disable Slurm GPU binding so every rank sees all four devices, then use
the upstream four-rank binding script for NUMA and NIC placement. QUDA maps local ranks to
device ordinals zero through three. Pin the scheduler paths at submission:

```bash
working_directory=${WORKING_DIRECTORY:?set WORKING_DIRECTORY}
validation_directory="$working_directory/validation/perlmutter-gpu-a100-40"
validation_script="$working_directory/validate-perlmutter-gpu-a100-40.sbatch"

sbatch --account=<account> \
  --chdir="$validation_directory" \
  --output="$validation_directory/slurm-%j.out" \
  --error="$validation_directory/slurm-%j.err" \
  "$validation_script"
```

An absolute script path does not set Slurm's working directory. With no submission budget,
the agent prepares this command and the operator submits it.

Acceptance requires an application payload exit of zero, `RUNNING COMPLETED`, 24 QUDA CG
convergence records below the requested true-residual tolerance, the literal
`FLTIME: ... (HISQ QUDA D)` marker, and the correlator structure recorded in `stack.yaml`.
Do not require positive MILC `total_iters`: at the tested commit that counter remains zero
on this path even though QUDA reports the actual per-solve iterations.

The validation wrapper records the application payload and acceptance-check outcomes
separately. Require both to exit zero before treating the run as a stack validation.

This sample exercises warm-gauge construction, the QUDA gauge-fixing path, HISQ fermion
links, staggered solves, P2P communication, and correlator generation. The acceptance does
not assert that the final gauge-fixing delta met the configured tolerance, and it checks
correlator structure rather than reference numerical values. The application links QIO but
does not exercise QIO reads or writes, and it does not exercise the compiled smearing or
force paths. A fresh tunecache run is correctness evidence, not a performance benchmark.
