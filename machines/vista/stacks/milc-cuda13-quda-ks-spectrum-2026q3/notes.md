---
title: MILC ks_spectrum_hisq stack with QUDA on Vista, CUDA 13
summary: Vista build options and the four-node GPUDirect RDMA validation of MILC ks_spectrum_hisq composed with the NVHPC 26.1 / CUDA 13.1 / Open MPI 5.0.9 QUDA milc-cg stack.
scope: [machine:vista, software:milc]
load_when: Rebuilding, validating, or launching the milc-cuda13-quda-ks-spectrum-2026q3 stack on Vista.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Vista/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - operator-run and operator-submitted validation runs reviewed in the working directory
observed: "2026-09-28"
observed_on:
  machine: vista
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
  toolchain:
    cuda: 13.1.80
    ucx: 1.20.0
---

# MILC `ks_spectrum_hisq` with QUDA on Vista, CUDA 13

Declare `gpu-gh200` first. Build against the QUDA install of
[`quda-cuda13-milc-cg-2026q3`](../quda-cuda13-milc-cg-2026q3/notes.md), whose notes own the
toolchain. `stack.yaml` is canonical for tested versions, cost, and validation results. The
shared invocation is in `software/milc/build.md`.

## Machine options

Materialize `machine_args` from `stack.yaml`, resolving the prefixes against the loaded
`cuda/13.1` module and the QUDA install, with `QUDA_HOME`, `QMPPAR`, and `QIOPAR` naming the
same prefix. Two points carry over from the cuda12 stack
([`../milc-cuda12-quda-ks-spectrum-2026q3/notes.md`](../milc-cuda12-quda-ks-spectrum-2026q3/notes.md)),
and one is new:

- **`LDFLAGS` must carry `-fopenmp`**, for the reason given there: a command-line `LDFLAGS`
  replaces the Makefile's own. The NVIDIA C compiler behind `mpicc` accepts the flag, and the
  link succeeded on the first attempt.
- **`-lcuda -lnvidia-ml` are added**, as the upstream Vista script does for this compiler.
- **`OFFLOAD=CUDA` stays inert** in the Makefile's CUDA block; the CUDA libraries arrive
  through `libquda.so`'s own dependencies.

If the tree already holds objects from another toolchain, build in a separate checkout of
the same commit rather than cleaning them: MILC compiles inside its source tree.

The executable carries `RUNPATH` to the QUDA install and to Open MPI 5.0.9, so
`LD_LIBRARY_PATH` can redirect it. Load `nvidia/26.1 cuda/13.1 openmpi/5.0.9` in the job.

## Launch and what the validation shows

Launch as the cuda12 stack does: one rank per node through `ibrun`, the upstream `sample.in`
unchanged (`node_geometry 1 1 2 2` on four nodes), 72 CPUs per rank with 16 OpenMP threads,
`QUDA_ENABLE_GDR=1`, and UCX's **default** transport list — no `UCX_TLS` setting is needed.

The four-node run completed, converged all 24 CG solves under the 1e-8 true-residual target,
and its 12 correlator records agree with the cuda12 stack's run and with two older Vista runs
to the file's printed precision. Unlike the cuda12 stack, GPUDirect RDMA is shown at the
transport level, not only in QUDA's policy keys: UCX's protocol tables record inter-node
GPU-to-GPU rendezvous fetches.

Other lattice sizes, decompositions, and any QIO gauge I/O through this stack remain
unvalidated; the multi-rank QIO read-back failure of the composed QUDA stack persists.
