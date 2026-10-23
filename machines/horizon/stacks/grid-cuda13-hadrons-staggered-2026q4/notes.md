---
title: Grid CUDA 13 cuda-hadrons-staggered stack on Horizon
summary: The Horizon gpu-gb200 build of the milc-qcd Grid fork at the HadronsMILC 0.3.0 pin, how to reproduce it, what its one-board validation covers, and the throughput it showed.
scope: [machine:horizon, software:grid]
load_when: Rebuilding, validating, or building Hadrons and HadronsMILC on the grid-cuda13-hadrons-staggered-2026q4 stack on Horizon.
evidence: experiment
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac
  - operator-submitted build, test-build and validation jobs reviewed in the working directory
observed: "2026-10-23"
observed_on:
  machine: horizon
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain:
    cuda: "13.3"
    ucx: 1.22.0
---

# Grid CUDA 13 `cuda-hadrons-staggered` on Horizon

Declare `gpu-gb200` first. `stack.yaml` is canonical for versions, options, cost and
validation; this page is the procedure and what the numbers mean. The base of
`../hadronsmilc-cuda13-lmi-2026q4/`.

## Reproduce

1. Load `gcc/15.3.0`, `cuda/13.3`, `openmpi/5.0.11` after `module reset`, unloading `nvidia`
   and `cmake`. Build GMP, MPFR, LIME and serial HDF5 (C++ API) from the tarballs and options
   in `stack.yaml` into one dependency prefix, on a login node at low parallelism.
2. Check out milc-qcd Grid at d67dd207 and run `./bootstrap.sh` on a login node (it downloads
   Eigen).
3. In a batch job on one board, out of tree: `configure` with the profile's options and the
   stack's `machine_options` (no `--enable-fermion-instantiations`); `make -j48 -C Grid`;
   `make -j48 -C GridMilc libGridMilc.a`; `make -C Grid install`;
   `make -C GridMilc install-libLIBRARIES install-nobase_dist_libGridMilc_aHEADERS`;
   `make install-binSCRIPTS`. Build the test programs with `make -k` per test directory.
4. Stamp the installed `Grid/Version.h` (`software/grid/build.md`).

Expected `Grid/Config.h`: `GRID_CUDA`, `ENABLE_FERMION_INSTANTIATIONS`, `ACCELERATOR_AWARE_MPI`,
`GRID_DEFAULT_GPU`, no `GRID_UVM`, no `HAVE_FFTW`.

The installed static libraries, for checking which build a consumer linked:

| File | sha256 |
|---|---|
| `lib/libGrid.a` | `c3d1b1fc12ebc65db2b7f3dd387e07650b2466621c4b3ce3c4db61ac65fa2e82` |
| `lib/libGridMilc.a` | `01256594510552fdd0f94bb2a97a509e5a23fa56393c28b235443c92c73a5783` |

## What the validation shows

Correctness on 1 and 4 GPUs of one board is in `stack.yaml`: the staggered operator, CG
variants, multishift and the GridMilc gamma test pass, with identical results across the two
decompositions. The failures are explained in `software/grid/validation.md`; the one that
matters for HadronsMILC, the A2A checkerboard abort, is fixed by a header the HadronsMILC
stack adds.

Throughput seen on this stack, `--accelerator-threads 8`, one run of three repetitions per
figure, fresh processes. Observations; none has been admitted as a performance reference:

| Measurement | Value |
|---|---|
| `Benchmark_staggered`, double, 1 GPU, 32⁴ | 2.49 TF/s median (2.21–2.50) |
| `Benchmark_staggeredF`, single, 1 GPU, 32⁴ | 5.28 TF/s (5.14–5.31) |
| Same, 4 GPUs (`1.1.2.2`), aggregate | 6.32 TF/s double, 10.93 TF/s single |
| `--comms-overlap`, 4 GPUs, double | 0.90 × the default |
| `Benchmark_memory_bandwidth` peak | 6.36 TB/s on 1 GPU; 25.4 TB/s on 4 |
| `Benchmark_comms`, device buffers, large messages | about 203 GB/s per rank, one direction; host buffers about 33 GB/s |
| `Test_fatLinks` HISQ smearing without the stencil fix | about 3.8 × 10⁻⁴ s per local site on 1 GPU |
| Device memory, small-lattice tests | 10.8 GiB per GPU peak, `--shm 2048` included |

The four-GPU Dslash rate per GPU is 0.63 (double) and 0.52 (single) of the one-GPU rate with
halos through MPI (`--shm-mpi 1`, the default) and no overlap; the shortfall has not been
profiled. The first double-precision one-GPU repetition ran 12% slow, unexplained.
