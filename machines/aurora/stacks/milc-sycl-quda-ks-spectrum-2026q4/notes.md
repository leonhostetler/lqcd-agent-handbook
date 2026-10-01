---
title: MILC ks_spectrum_hisq on SYCL QUDA on Aurora
summary: Machine options and reproduction for the validated Aurora MILC stack, and why the upstream Aurora link flags must not be copied - with icx they link GNU and Intel OpenMP runtimes together, which collapsed every rank's threads onto one CPU and returns thread id 0 on every thread.
scope: [machine:aurora, software:milc]
load_when: Rebuilding or validating the milc-sycl-quda-ks-spectrum-2026q4 stack, building any OpenMP MILC application with the Intel compilers on Aurora, or reusing the upstream Aurora MILC scripts.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Aurora/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Aurora/submit.qsub
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_meson_mom.c
observed: "2026-10-01"
observed_on:
  machine: aurora
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
  toolchain:
    oneapi: 2026.1.0
---

# MILC `ks_spectrum_hisq` on SYCL QUDA on Aurora

Resolve the `ks-spectrum-hisq-quda` profile and the
[`quda-sycl-milc-cg-2026q4`](../quda-sycl-milc-cg-2026q4/notes.md) stack first; this stack
links that installation. `stack.yaml` is canonical for options, versions and results.

## Build

Follow [`software/milc/build.md`](../../../../software/milc/build.md) with `module reset` and
`machine_args` materialized from `stack.yaml`. Point `QUDA_HOME`, `QMPPAR` and `QIOPAR` at the
QUDA install prefix. The upstream sample points `QUDA_HOME` at the QUDA build tree while QMP
and QIO come from the install prefix, which links one `libquda.so` and loads the other; see
[`quda-linkage.md`](../../../../software/milc/quda-linkage.md).

`OFFLOAD=SYCL` is inert, as `OFFLOAD=CUDA` is on Vista: the Makefile tests for lowercase
`sycl`. The value is kept because it is what the upstream sample passes; the lowercase form
would add `-cc=icx -cxx=icpx -fsycl` to every compile and is untested. MILC is host code here,
and SYCL reaches it only through `libquda.so`.

## Do not copy the upstream link flags

The upstream script passes `LDFLAGS="-g "` through the environment, so the Makefile's
`COMPILER=gnu` branch appends `-fopenmp -L<a nonexistent path> -lgomp` to it. `mpicc` here is
`icx`, for which `-fopenmp` links Intel's `libiomp5`, so the executable carries **both**
`libgomp.so.1` and `libiomp5.so`, `libgomp` first. Use the command-line value
`LDFLAGS=-g -fopenmp`, and confirm with `readelf -d` that `libiomp5.so` is the only OpenMP
runtime listed.

Observed consequences of the mixed link `[experiment]`:

- **Thread ids collapse.** A minimal OpenMP program compiled with `icx -fopenmp` and linked the
  upstream way reported thread id 0 on all eight threads of a parallel region; linked with
  `-fopenmp` alone it reported eight distinct ids. The compiler-generated parallel region runs
  on `libiomp5`, while the `omp_get_thread_num` call binds to `libgomp`, which did not create
  those threads.
- **Thread placement collapses.** In the validation job, `OMP_DISPLAY_AFFINITY` placed all
  eight threads of every rank on the first CPU of that rank's mask under the upstream-flag
  executable, and on eight distinct cores under the corrected one. With a warm tunecache,
  compute-propagators time was 22.7 s against 13.3 s, one observation each. A probable
  mechanism, not established here, is that `libgomp` applies `OMP_PROC_BIND=spread` to the
  initial thread at load and `libiomp5` then inherits a one-CPU mask.
- **Correlators were unaffected on the upstream sample.** They were bit-identical to the
  corrected executable's. `ks_meson_cont_mom` in `generic_ks/ks_meson_mom.c` accumulates into
  per-thread slots indexed by `omp_get_thread_num`, so with collapsed ids every thread writes
  thread 0's slots. `[inferred]` That races only when two threads touch one time slice, which
  depends on the local lattice, thread count and site layout; it did not occur at this
  sample's 16 x 8 x 8 x 16 local volume with eight threads. Treat other geometries as
  unverified rather than safe, and avoid the mixed link.

## Run

Use the launcher, binding and QUDA environment of the QUDA stack, twelve ranks per node, with
the input's `node_geometry` matching the rank grid. Give each run a fresh output directory: the
FNAL correlator writer appends.

**Proofreading needs a CPU SYCL device on a login node.** The QUDA library constructs a static
SYCL device at load, and a login node has no GPU, so the executable aborts with
`No device of requested type available` before reading input, whatever `prompt` says. With
`ONEAPI_DEVICE_SELECTOR=opencl:cpu` the `prompt 2` parse ran to `EOF on input`, and the process
then aborted in QUDA teardown after parsing. Judge it by the log, as the proofread rule says.
`tools/milc-proofread-input.sh` does not yet set the selector.
