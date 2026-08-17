---
title: MILC CUDA 12 QUDA ks_spectrum stack on DeltaAI
summary: Reproduction notes for the validated one-node QUDA-enabled MILC ks_spectrum_hisq application stack.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Rebuilding or validating the DeltaAI MILC ks_spectrum_hisq stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/DeltaAI/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/DeltaAI/sample.in
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/DeltaAI/submit.sbatch
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c
observed: "2026-08-17"
observed_on:
  machine: deltaai
  node_type: gpu-gh200
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
  toolchain:
    cuda: 12.9.41
    host_compiler: GNU 14.2.0 through Cray wrappers
    mpi: cray-mpich/9.0.1
---

# MILC CUDA 12 QUDA `ks_spectrum` stack on DeltaAI

`stack.yaml` is canonical for commits, the composed profile, build options, measured cost,
node resources, numerical results, and validation limits. Read it together with
`software/milc/build.md` and the DeltaAI machine profile. Because `gpu-gh200` is the
profile's sole node type, it is the default unless the operator explicitly selects another
type after the profile changes.

## Build from a disposable checkout

Use the validated DeltaAI QUDA `milc-cg` installation for `QUDA_HOME`, `QMPPAR`, and
`QIOPAR`. Build MILC in a fresh full checkout detached at the recorded commit because the
procedure copies the repository `Makefile` into `ks_spectrum` and creates objects in the
source tree. This keeps the operator's source checkout clean. The shared build playbook
still governs source acquisition, status checks, and cost recording.

Apply the `ks-spectrum-hisq-quda` profile and the machine options in `stack.yaml`. The
material adaptations from the upstream DeltaAI compile script are to use the existing
validated QUDA installation rather than building dependencies in place, and to call the
site-recommended Cray `cc` and `CC` wrappers directly instead of the interception-layer
`mpicc` and `mpiCC` names. The resulting executable linked Cray MPICH through those
wrappers and resolved QUDA, QMP, QIO, OpenMP, and CUDA libraries before validation.

Build with the recorded single-job parallelism, install the completed executable into a
separate prefix, and verify its shared-library resolution before preparing a compute-node
test.

## Use the short debugging partition

The one-node application validation fits DeltaAI's interactive limits, so use
`ghx4-interactive`, even though the upstream example names `ghx4`. Start from the upstream
`systems/DeltaAI/sample.in` unchanged. Use four ranks, retain all-device visibility, and
let QUDA map local ranks to device ordinals zero through three:

```bash
#SBATCH --partition=ghx4-interactive
#SBATCH --time=00:15:00
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=16
#SBATCH --gpus-per-node=4
#SBATCH --gpu-bind=none
#SBATCH --mem=0

export LD_LIBRARY_PATH="$QUDA_INSTALL_PREFIX/lib:$QUDA_INSTALL_PREFIX/lib64:${LD_LIBRARY_PATH:-}"
export QUDA_RESOURCE_PATH="$VALIDATION_DIRECTORY/tunecache"
export QUDA_ENABLE_GDR=1
export QUDA_MILC_HISQ_RECONSTRUCT=13
export QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9
export MPICH_RDMA_ENABLED_CUDA=1
export MPICH_GPU_SUPPORT_ENABLED=1
export MPICH_NEMESIS_ASYNC_PROGRESS=1
export MPICH_SMP_SINGLE_COPY_MODE=XPMEM
export OMP_NUM_THREADS=16
export OMP_PROC_BIND=spread
export SRUN_CPUS_PER_TASK=16
mkdir -p "$QUDA_RESOURCE_PATH"

srun --ntasks=4 --cpus-per-task=16 --cpu-bind=cores --gpu-bind=none \
  "$MILC_INSTALL_PREFIX/bin/ks_spectrum_hisq" sample.in sample.out
```

The tested Cray MPICH environment report showed `CMA` for the effective shared-memory
single-copy mode and asynchronous progress disabled despite the two legacy variables above.
Treat those variables as upstream compatibility settings, not evidence that XPMEM or async
progress was active. The one-node test observed QUDA peer access between neighboring local
ranks; it did not demonstrate multi-node GPUDirect RDMA.

Pin the scheduler output path at submission and submit from the working project so
`SLURM_SUBMIT_DIR` resolves the build, install, and validation roots used by the job script:

```bash
working_directory=${WORKING_DIRECTORY:?set WORKING_DIRECTORY}
validation_root="$working_directory/validation/deltaai-gpu-gh200-milc-ks-spectrum"
validation_script="$working_directory/validate-deltaai-gpu-gh200-milc-ks-spectrum.sbatch"

mkdir -p "$validation_root"
cd "$working_directory"
sbatch --account=<account> \
  --output="$validation_root/slurm-%j.out" \
  "$validation_script"
```

With no submission budget, the agent prepares this command and the operator submits it.

Acceptance requires an application payload exit of zero, `RUNNING COMPLETED`, 24 QUDA CG
convergence records below the requested true-residual tolerance, the literal
`FLTIME: ... (HISQ QUDA D)` marker, and the correlator structure recorded in `stack.yaml`.
Do not require positive MILC `total_iters`: at the tested commit that counter remains zero
on this path even though QUDA reports the actual per-solve iterations.

The initial harness's nonfatal correlator counter searched for an older `STARTPROP`
delimiter. The FNAL YAML output instead identifies records with `correlator:`, so direct
review found the expected 12 records and 384 data rows; the reusable parser was corrected
after the run. Keep raw output available for review rather than allowing a summary parser
to replace the application evidence.

This sample exercises warm-gauge construction, the QUDA gauge-fixing path, HISQ fermion
links, staggered solves, P2P communication, and correlator generation. The acceptance does
not assert that the final gauge-fixing delta met the configured tolerance, and it checks
correlator structure rather than reference numerical values. The application links QIO but
does not exercise QIO reads or writes, and it does not exercise the compiled smearing or
force paths. A fresh tunecache run is correctness evidence, not a performance benchmark.
