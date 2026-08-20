---
title: MILC CUDA 13 QUDA wilson_flow stack on Perlmutter
summary: Reproduction notes for the validated one-node QUDA-enabled MILC wilson_flow application stack.
scope: [machine:perlmutter, software:milc, software:quda]
load_when: Rebuilding or validating the Perlmutter MILC wilson_flow stack with QUDA.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/control.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/integrate_quda.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Perlmutter_GPU/bind.sh
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/lib/CMakeLists.txt
  - https://github.com/lattice/quda/blob/7733f60bb744204576f82574ece8d8bd454fbcfd/lib/interface_quda.cpp
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

# MILC CUDA 13 QUDA `wilson_flow` stack on Perlmutter

`stack.yaml` is canonical for commits, profiles, build options and costs, node resources,
runtime results, and validation limits. Read it with the MILC `wilson_flow` application guide
and the Perlmutter machine profile. This is a correctness stack, not a performance prescription.

## Build from a disposable checkout

Use the already validated Perlmutter CUDA 13 QUDA `milc-cg` installation for `QUDA_HOME`,
`QMPPAR`, and `QIOPAR`. QUDA's Wilson-flow kernels are included in that build; there is no
separate gauge-flow CMake option. Build MILC in a fresh full checkout at the recorded `develop`
commit because the procedure copies the repository `Makefile` into `wilson_flow` and creates
objects in the source tree. The shared build playbook still governs source acquisition, status
checks, and cost recording.

Apply the `wilson-flow-quda` MILC profile and the machine options from `stack.yaml`:

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

The explicit OpenMP link flags are intentional because a command-line `LDFLAGS` assignment
overrides the Makefile's ordinary GNU/OpenMP additions. Before allocating a node, confirm that
both executables resolve QUDA, QMP, QIO, the OpenMP runtime, Cray MPICH, and CUDA without missing
libraries. The recorded builds completed with upstream compiler warnings listed in `stack.yaml`;
none was a build failure, but the warned QIO and save paths remain outside this validation.

## Run a short smoke test

Use the debug QoS, four ranks, all-device visibility, the upstream Perlmutter binding script,
and a fresh run-owned tunecache. The tested input used a small serially readable NERSC gauge:

```text
prompt 0
nx 4
ny 4
nz 4
nt 8
reload_serial <gauge-file>
wilson
exp_order 8
stepsize 0.0625
stoptime 0.125
forget
```

The exact-binary step size and stop time avoid the wrapper's integer-conversion endpoint hazard.
For other values, validate the actual final row rather than trusting the echoed stop time.

```bash
#SBATCH --qos=debug
#SBATCH --time=00:05:00
#SBATCH --nodes=1
#SBATCH --constraint=gpu&hbm40g
#SBATCH --ntasks-per-node=4
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-task=1
#SBATCH --gpu-bind=none

export LD_LIBRARY_PATH="$QUDA_INSTALL_DIR/lib:$QUDA_INSTALL_DIR/lib64:${LD_LIBRARY_PATH:-}"
export QUDA_RESOURCE_PATH="$VALIDATION_DIRECTORY/tunecache"
export QUDA_ENABLE_GDR=1
export MPICH_GPU_SUPPORT_ENABLED=1
export OMP_NUM_THREADS=32
export OMP_PROC_BIND=spread
export SRUN_CPUS_PER_TASK=32
mkdir -p "$QUDA_RESOURCE_PATH"

bind_script="$MILC_SOURCE_DIR/systems/Perlmutter_GPU/bind.sh"
srun -K --ntasks=4 --cpus-per-task=32 --cpu-bind=none \
  --gpus-per-task=1 --gpu-bind=none \
  "$bind_script" "$MILC_INSTALL_DIR/bin/wilson_flow_bbb_gpu" short.in short.out
```

Pin the scheduler working directory and output paths at submission. With no submission budget,
prepare the script and let the operator submit it. Keep raw scheduler and application output in
the working project, not the handbook.

Acceptance requires successful scheduler and payload exits, telemetry for four 40 GB A100 devices
with compute capability 8.0, the BBB integrator and QUDA gradient-flow markers, a successful NERSC
serial reload with checksum and gauge-health records, one header and three finite flow rows at
`0`, `0.0625`, and `0.125`, `RUNNING COMPLETED`, and a normal `exit:` marker. A completion marker
alone does not validate the endpoint.

The run used `forget`. This stack does not qualify the Luescher runtime path, Symanzik flow, QIO
reload or save, QUDA ending-lattice save, `continue`, CPU/QUDA numerical equivalence, multi-node
execution, or production timing. A fresh tunecache run is correctness evidence rather than a
benchmark.
