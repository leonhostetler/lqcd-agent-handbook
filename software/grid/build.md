---
title: Building Grid
summary: Bootstrap, configure traps, what to build and install, the test programs that do not compile, and the post-install version stamp for Grid and its milc-qcd fork.
scope: [software:grid]
load_when: Configuring, compiling, installing, or test-building Grid, including as the base of a Hadrons or HadronsMILC stack.
evidence: source
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/bootstrap.sh#L4-L20
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac#L208-L244
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac#L295-L329
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac#L436-L453
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac#L753-L800
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/configure.ac#L827-L858
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/Makefile.am#L25-L83
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/FFT.h#L115-L201
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/FFT.h#L635-L645
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/threads/Accelerator.cc#L20-L104
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/SharedMemoryMPI.cc#L183-L252
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/scripts/filelist
  - https://github.com/paboyle/Grid/blob/3232b438f2cf729e515c185e2dbf29d7cc276bb7/configure.ac
  - https://github.com/paboyle/Grid/blob/3232b438f2cf729e515c185e2dbf29d7cc276bb7/Grid/algorithms/FFT.h
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {gcc: "15.3", cuda: "13.3", openmpi: "5.0.11"}
---

# Building Grid

Follow `playbooks/build-lqcd-stack.md` for the shared workflow. This page supplies the Grid
half; the machine profile and stack own modules, architecture flags and placement. Labels:
**[U+F]** upstream and fork (cited code identical on upstream `develop` 3232b438f, or
checked there); **[F]** fork-only (`milc-qcd` `feature/LMI-develop`). Line numbers are at fork
commit d67dd207.

## Bootstrap once, in the source tree [U+F]

`./bootstrap.sh` downloads Eigen 3.4.0 (network access needed), unpacks it into the tree, runs
`scripts/filelist` to write the `Make.inc` source lists, and generates `configure`. `Make.inc`
is generated and git-ignored: after adding or removing a source file, run `scripts/filelist`
again before configuring.

## Configure out of source

Read option effects from `configure.ac` and the build's `Grid/Config.h`, not from Grid's
`README.md`, `CLAUDE.md` or `systems/*/config-command`; several of those disagree with the
code. The traps:

- **Never pass `--enable-fermion-instantiations`, with any value** [U+F]. Its action assigns
  the wrong shell variable (configure.ac:208-212), so passing it, `=yes` included, removes
  every fermion-operator instantiation from `libGrid.a`. Downstream code then fails to link
  with undefined `WilsonFermion<…>` or `CayleyFermion5D<…>` symbols. Confirm
  `#define ENABLE_FERMION_INSTANTIATIONS 1` in `Grid/Config.h`.
- **`--enable-setdevice` does nothing** [U+F]. Configure reads `${enable_SETDEVICE}`
  (configure.ac:753), so `GRID_DEFAULT_GPU` is always defined and every rank uses device 0 of
  the devices it can see (`Accelerator.cc:20-60`). Bind one GPU per rank outside Grid, with a
  wrapper that sets `CUDA_VISIBLE_DEVICES` per local rank.
- **GPU builds need a non-`none` `--enable-shm`** [U+F]. The default is `no`, which splits the
  node communicator per rank, so ranks on one node never use device IPC. Any other value
  takes the same device-buffer path on GPU (`SharedMemoryMPI.cc:183-252`); `nvlink` is
  conventional and additionally enables the runtime `--shm-hostname-fallback` flag [F].
- **Accelerator-aware MPI is on by default** [U+F] (configure.ac:295-307): halo exchange
  passes device pointers to MPI, so the MPI must be CUDA-aware at run time (check its
  accelerator component on a compute node; a login node without a driver may not show it).
  `--enable-accelerator-aware-mpi=no` stages through host buffers and is the only mode in which
  the default-on comms checksums do anything.
- **`--disable-unified`** [U+F] replaces managed memory with explicit device allocations
  behind a software cache. Host code that dereferences device-resident data then segfaults
  instead of page-faulting it in; wrong view access modes give stale data.
- **`--enable-comms=mpi`** [U+F] is the same communicator as `mpi3`; only the `-auto` forms add
  MPI flags, so without `-auto` the compiler must be an MPI wrapper (for nvcc,
  `-ccbin mpicxx`).
- **Pass exactly one `-gencode`** for the target GPU in `CXXFLAGS` [U+F]. Configure adds none;
  each extra architecture adds a device compilation pass to every source (inferred from nvcc
  behaviour, not measured).
- **For Hadrons, keep `--enable-zmobius`** (the default) [U+F]. Hadrons constructs
  `ZMobiusFermion`, whose method definitions live only in Grid's z-Mobius instantiation
  sources, so a `--disable-zmobius` Grid is expected to break the Hadrons link (inferred from
  the declaration/definition split; not test-built). `--disable-gparity` and
  `--disable-fermion-reps` are safe for Hadrons and remove 44 of the 163 library sources
  compiled at default options.
- **CPU builds need FFTW** [U+F]. `PlannedFFT` (`FFT.h:635-645`) names `FFTW<scalar>::FFTW_plan`
  outside any guard, but `FFTW<ComplexD/F>` defines it only for CUDA, HIP, or CPU builds with
  `HAVE_FFTW` (`FFT.h:115-201`). A CPU build whose configure finds no FFTW compiles until the
  fermion instantiations, then fails with "no type named 'FFTW_plan' in
  'struct Grid::FFTW<std::complex<double>>'". Configure only reports `FFTW: no`. Pass
  `--with-fftw=<prefix>` with double and single precision installed. Observed once (gcc 15.3,
  `--enable-simd=GEN`); the mechanism is in the source.
- **A missing GMP is silent** [U+F]: its check has no not-found action (configure.ac:436-442).
  Confirm `HAVE_LIBGMP` in `Grid/Config.h`.

## Build and install

- **Library only:** `make -C Grid -jN && make -C Grid install` builds and installs `libGrid.a`
  and its headers [U+F]. A plain top-level `make` also links about 90 benchmark, example and
  HMC programs, each through the same compiler.
- **GridMilc** [F]: `make -C GridMilc libGridMilc.a`, then
  `make -C GridMilc install-libLIBRARIES install-nobase_dist_libGridMilc_aHEADERS`. Its headers
  are templates; the library holds only a version string, so a header-only fix can be applied
  to a consumer by putting a corrected copy first on its include path.
- **`grid-config`:** `make install-binSCRIPTS` [U+F]. Hadrons' configure needs it on `PATH`.
- **Test programs** [U+F]: subdirectory tests are `EXTRA_PROGRAMS`, built by
  `make -C tests/<dir> tests-local` (and `make tests` from the top); root tests build with `all`.
  Build the complete set by default, as the build playbook requires, with `make -k`.

### Test programs that do not compile at d67dd207

Expect these, and do not chase them when judging a build:

| Program | Build | First error | Label |
|---|---|---|---|
| `lanczos/Test_stag_lanczos`, `Test_stag_lanczos_milc` | all | `ImprovedStaggeredFermionR` / `NaiveStaggeredFermionR` no longer exist | [F] (absent upstream) |
| `core/Test_prec_change` | all | `LatticeFermionD2` undefined | [U+F] |
| `debug/Test_hipfft_*` (4) | non-HIP | `hipfft/hipfft.h` missing | [U+F] |
| `IO/Test_serialisation` | CUDA | no HDF5 type for `std::complex`; on GPU `Grid::complex` is `thrust::complex` | [U+F] |
| `lexLattice/*`, `core/Test_uvm` | CUDA | device-code and SIMD-type incompatibilities | [U+F] |
| `sp2n/*` | all, Sp disabled | compile errors (CUDA) or link errors (CPU) | [U+F] |
| `solver/Test_wilson_mg_mp`, `Test_wilsonclover_mg_mp`, `Test_wilsonclover_mg_lime` | CPU (GEN) | no matching `GridBLAS::gemmBatched` | [U+F] |

Observed in one CUDA build (nvcc 13.3, sm_100) and one CPU build (gcc 15.3, GEN width 16)
of the same commit; `IO/Test_serialisation`, `lexLattice/*` and `core/Test_uvm` compile in the
CPU build. None is used by a staggered or Hadrons workflow.

## After an out-of-tree install: stamp `Grid/Version.h` [U+F]

`Grid/Makefile.am:25-47` writes `Version.h` from `git log` run in the **build** directory.
Out of tree that is not a git work tree, so the installed header is a single newline. Grid's
banner then reports the commit hash as undefined, and downstream consumers that read
`GITHASH` see nothing (HadronsMILC's `--version` prints `Grid git=unknown`, and its
`--enable-strict-pins` configure fails). After installing, with the source tree clean at the
built commit, write the line the rule would have written:

```bash
printf '%s\n' "$(git -C <src> log -n 1 --format=format:'#define GITHASH "%H:%d clean"' HEAD)" \
  > <prefix>/include/Grid/Version.h
```

`libGrid.a` itself is not rebuilt, so Grid's own banner still says undefined. Observed in two
out-of-tree builds; the mechanism is in the rule.

## Discovering a compile command: never `make -n` [generic automake]

In an automake build tree, `make -n` (and `-B`) is not print-only: the `am--refresh` rule
recurses through `$(MAKE)`, which make runs even under `-n`, and can re-run `aclocal`,
`automake` and `autoconf` in the source tree and `config.status --recheck` in the build tree.
Read the compiler inputs from the generated `Makefile` (`DEFS`, `DEFAULT_INCLUDES`,
`AM_CXXFLAGS`, `CXXFLAGS`, `LDFLAGS`, `LIBS`) or from a `V=1` build log instead. Observed once
in a Grid build tree; the mechanism is GNU make's documented handling of `$(MAKE)` lines.
