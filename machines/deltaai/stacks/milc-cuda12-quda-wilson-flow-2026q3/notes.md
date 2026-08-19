---
title: MILC CUDA 12 QUDA wilson_flow stack on DeltaAI
summary: Reproduction notes for the validated one-node QUDA-enabled MILC wilson_flow application stack.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Rebuilding or validating the DeltaAI MILC wilson_flow stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/control.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/integrate_quda.c
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/interface_quda.cpp
observed: "2026-08-19"
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

# MILC CUDA 12 QUDA `wilson_flow` stack on DeltaAI

`stack.yaml` is canonical for commits, profiles, build options and costs, node resources,
runtime results, and validation limits. Read it with the MILC `wilson_flow` application guide
and the DeltaAI machine profile. This is a correctness stack, not a performance prescription.

## Use upstream `develop`

The QUDA Wilson-flow wrapper is present in upstream MILC at the recorded `develop` commit. Do
not use the former personal `quda_gauge_flow` branch. Follow the shared build playbook for source
acquisition, then confirm the branch and exact commit before building:

```bash
git -C "$MILC_SOURCE_DIR" switch develop
git -C "$MILC_SOURCE_DIR" status --short --branch
git -C "$MILC_SOURCE_DIR" rev-parse HEAD
```

For an exact stack reproduction, detach a disposable full checkout at the commit in `stack.yaml`.
The procedure copies the repository `Makefile` into the application directory and creates build
artifacts there, so do not use an operator-owned working checkout.

## Build QUDA and MILC

Build QUDA with the existing `milc-cg` profile. Its Wilson-flow kernels are part of the QUDA
library source list; there is no separate gauge-flow CMake option. The fresh build used for this
validation had the same options as the existing DeltaAI QUDA stack. The only material difference
was the separately measured build cost recorded under `dependency_acquisition` in `stack.yaml`.

Apply the `wilson-flow-quda` MILC profile and the machine options from `stack.yaml`. The following
is the application-specific portion of the tested GNU build:

```bash
milc_source=${MILC_SOURCE_DIR:?set MILC_SOURCE_DIR}
milc_install=${MILC_INSTALL_DIR:?set MILC_INSTALL_DIR}
quda_install=${QUDA_INSTALL_DIR:?set QUDA_INSTALL_DIR}
cuda_prefix=${CUDA_TOOLKIT_DIR:?set CUDA_TOOLKIT_DIR}

cp "$milc_source/Makefile" "$milc_source/wilson_flow/Makefile"
cd "$milc_source/wilson_flow"

profile_args=(
  PRECISION=2 MPP=true OMP=true WANTQUDA=true WANTQMP=true WANTQIO=true
  "CTIME=-DNERSC_TIME -DCGTIME -DFFTIME -DFLTIME -DGFTIME -DREMAP -DPRTIME -DIOTIME -DGS_TIME"
)
machine_args=(
  MY_CC=cc MY_CXX=CC ARCH= GPU_ARCH=nvidia OFFLOAD=CUDA COMPILER=gnu
  "OPT=-O3 -Ofast -g" "LDFLAGS=-g -fopenmp -lgomp"
  "CUDA_HOME=$cuda_prefix" "CUDA_MATH=$cuda_prefix"
  "CUDA_COMP=$cuda_prefix" "CUDA_NVML=$cuda_prefix"
  "QUDA_HOME=$quda_install" "QMPPAR=$quda_install" "QIOPAR=$quda_install"
)

mkdir -p "$milc_install/bin"
for target in wilson_flow wilson_flow_bbb; do
  make clean "${profile_args[@]}" "${machine_args[@]}"
  make -j1 "$target" "${profile_args[@]}" "${machine_args[@]}"
  install -m 0755 "$target" "$milc_install/bin/${target}_gpu"
done
```

The explicit OpenMP link flags are intentional. Passing `LDFLAGS=-g` on the make command line
overrides the Makefile's ordinary GNU/OpenMP `LDFLAGS +=` additions. The first attempted build
therefore compiled but failed at final link with unresolved `GOMP_parallel` and `omp_*` symbols.
Including `-fopenmp -lgomp` in the command-line value produced both executables. If `LDFLAGS` is
not assigned on the command line, let the Makefile add the compiler-family flags itself.

Before allocating a node, confirm that both executables resolve QUDA, QMP, QIO, the OpenMP
runtime, Cray MPICH, and CUDA without missing libraries.

## Run a short smoke test

Use the short debugging partition, four ranks, all-device visibility, and a new run-owned output
and tunecache directory. This input shape reproduces the tested two-step endpoint while leaving
the gauge path operator-selected:

```text
prompt 0
nx 16
ny 16
nz 16
nt 48
reload_parallel <gauge-file>
wilson
exp_order 16
stepsize 0.0625
stoptime 0.125
forget
```

The exact-binary step size and stop time avoid the wrapper's integer-conversion endpoint hazard.
For other values, validate the actual final row rather than trusting the echoed stop time.

```bash
#SBATCH --partition=ghx4-interactive
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --exclusive
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=16
#SBATCH --gpus-per-node=4
#SBATCH --gpu-bind=none
#SBATCH --mem=0

export LD_LIBRARY_PATH="$QUDA_INSTALL_DIR/lib:$QUDA_INSTALL_DIR/lib64:${LD_LIBRARY_PATH:-}"
export QUDA_RESOURCE_PATH="$VALIDATION_DIRECTORY/tunecache"
export QUDA_ENABLE_GDR=1
export MPICH_GPU_SUPPORT_ENABLED=1
export MPICH_RDMA_ENABLED_CUDA=1
export MPICH_NEMESIS_ASYNC_PROGRESS=1
export MPICH_SMP_SINGLE_COPY_MODE=XPMEM
export OMP_NUM_THREADS=16
export OMP_PROC_BIND=spread
export SRUN_CPUS_PER_TASK=16
mkdir -p "$QUDA_RESOURCE_PATH"

srun -K --ntasks=4 --cpus-per-task=16 --cpu-bind=cores --gpu-bind=none \
  "$MILC_INSTALL_DIR/bin/wilson_flow_bbb_gpu" short.in short.out
```

With no submission budget, prepare the script and let the operator submit it. Pin the scheduler
output path to the working project, not the handbook.

Acceptance requires successful scheduler and payload exits, the BBB integrator marker, the QUDA
gradient-flow marker, a successful SciDAC/QIO reload with gauge health records, one header and
three finite flow rows at the expected increasing times, `RUNNING COMPLETED`, and a normal
`exit:`. Keep raw output for review; a completion marker alone does not validate the endpoint.

The run used `forget`. Current source writes a requested QUDA ending lattice from resident
`QUDA_SMEARED_LINKS`, but this stack did not validate that save. It also does not qualify QUDA
`continue`, CPU/QUDA numerical equivalence, Symanzik flow, multi-node execution, or production
timing. A fresh tunecache run is correctness evidence rather than a benchmark.
