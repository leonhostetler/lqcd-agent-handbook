---
title: MILC ROCm 7 QUDA ks_spectrum stack on Frontier
summary: Reproduction notes for the validated one-node QUDA-enabled MILC ks_spectrum_hisq application stack.
scope: [machine:frontier, software:milc, software:quda]
load_when: Rebuilding or validating the Frontier MILC ks_spectrum_hisq stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/sample.in
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c
observed: "2026-08-17"
observed_on:
  machine: frontier
  node_type: gpu-mi250x
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
  toolchain:
    rocm: 7.1.1
    hip: 7.1.52802
    mpi: cray-mpich/9.1.0
---

# MILC ROCm 7 QUDA `ks_spectrum` stack on Frontier

`stack.yaml` is canonical for commits, the composed profile, build options, measured cost,
node resources, numerical results, and validation limits. Read it together with
`software/milc/build.md` and the Frontier machine profile.

## Build from a disposable checkout

Use the already validated QUDA `milc-cg` installation for `QUDA_HOME`, `QMPPAR`, and
`QIOPAR`. Build MILC in a fresh full checkout detached at the recorded commit so copying
the top-level `Makefile` into `ks_spectrum` does not alter the operator's source checkout.
The shared build playbook still governs source acquisition, status checks, and cost
recording.

Apply the `ks-spectrum-hisq-quda` profile and the machine options in `stack.yaml`. The one
material adaptation from the upstream Frontier compile script is version-scoped: the
tested ROCm installation provides the component libraries under the consolidated
`/opt/rocm-7.1.1/lib` directory, so the link flags use that directory rather than obsolete
component-specific subdirectories.

Build with the recorded single-job parallelism. Verify the executable's shared-library
resolution before preparing a compute-node test.

## One-node validation pattern

Start from the upstream `systems/Frontier/sample.in` unchanged. Create a fresh per-run
directory and tunecache, retain all-device visibility, use QMP over the loaded Cray MPICH,
and disable QUDA P2P as recorded in `stack.yaml`. Pin both scheduler paths at submission:

```bash
working_directory=${WORKING_DIRECTORY:?set WORKING_DIRECTORY}
validation_directory="$working_directory/validation/frontier-gpu-mi250x"
validation_script="$working_directory/validate-frontier-gpu-mi250x.sbatch"

sbatch --account=<account> \
  --chdir="$validation_directory" \
  --output="$validation_directory/slurm-%j.out" \
  "$validation_script"
```

An absolute script path does not set Slurm's working directory. With no submission budget,
the agent prepares this command and the operator submits it.

The application acceptance criteria are the payload exit, `RUNNING COMPLETED`, QUDA's CG
convergence records and true residuals, the HISQ QUDA link marker, and the correlator-file
structure recorded in `stack.yaml`. Do not require positive MILC `total_iters`: at the
tested commit that counter remains zero on this path even though QUDA reports the actual
per-solve iterations. Keep the application-step outcome separate from any post-run wrapper
assertion so a harness defect cannot overwrite valid numerical evidence.

This sample exercises warm-gauge construction, the QUDA gauge-fixing path, HISQ fermion
links, staggered solves, and correlator generation. The acceptance does not assert that the
final gauge-fixing delta met the configured tolerance, and it checks correlator structure
rather than reference numerical values. The application links QIO but does not exercise QIO
reads or writes, and it does not exercise the compiled smearing or force paths. A fresh
tunecache run is correctness evidence, not a performance benchmark.
