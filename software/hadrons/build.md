---
title: Building Hadrons
summary: Bootstrap, out-of-tree configure against an installed Grid, recording the Hadrons commit, and the test and benchmark programs that do not compile on the milc-qcd fork.
scope: [software:hadrons]
load_when: Configuring, compiling, installing or test-building Hadrons, including as the base of a HadronsMILC stack.
evidence: source
sources:
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/bootstrap.sh
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/configure.ac#L13-L89
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/hadrons-config.in
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/Makefile.am
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/benchmarks/Benchmark_meson_field.cc#L37-L38
  - https://github.com/milc-qcd/Hadrons/commit/9ec7c43c13b3cb7e823f37d4ef31d695bc235ef6
  - https://github.com/aportelli/Hadrons/blob/develop/configure.ac
observed: "2026-10-23"
observed_on:
  software:
    hadrons:
      commit: 3a0980157914dd54e96744fccaf0fbf88620b5a5
      branch: feature/LMI-develop
      forked_from_default: 28d2806401806592f9caddc8eeedd4277efd341d
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {gcc: "15.3", cuda: "13.3", openmpi: "5.0.11"}
---

# Building Hadrons

Follow `playbooks/build-lqcd-stack.md` for the shared workflow; Grid comes first
(`software/grid/build.md`). Labels: **[U+F]** upstream and fork (identical on upstream
`develop`); **[F]** fork-only (`milc-qcd` `feature/LMI-develop`).

## Bootstrap once, in the source tree [U+F]

`./bootstrap.sh` generates the module list (`Hadrons/make_module_list.sh` writes
`Modules.hpp` and the module sources list), downloads the SQLite amalgamation from sqlite.org
(network access needed) and checks its sha256, then runs `autoreconf`. Rerun the module list
after adding or removing a module. The fork's bootstrap also accepts `--custom` [F].

## Configure out of tree

- Put the installed Grid's `bin/` on `PATH` and pass `--with-grid=<grid prefix>`. Configure
  stops with `grid-config not found` otherwise, and takes the compiler, flags, linker and
  libraries from `grid-config` (`configure.ac:13-46`) [U+F]. No other option is needed for a
  HadronsMILC stack.
- **Record the commit: run configure with `GIT_DIR=<source>/.git`** [U+F].
  `HADRONS_SHA=$(git rev-parse HEAD)` runs in configure's working directory
  (`configure.ac:77-78`) and becomes `hadrons-config --git`. Out of tree that directory is not
  a git work tree, the stamp is empty, and HadronsMILC's `--enable-strict-pins` cannot read the
  Hadrons commit. With `GIT_DIR`, `hadrons-config --git` prints `<branch> <sha>`
  (`HEAD <sha>` for a detached checkout).

## Build and install

`make -jN && make install` builds `libHadrons.a`, the headers and the utilities
(`HadronsXmlRun`, `HadronsXmlValidate`, `HadronsContractor`, `HadronsContractorBenchmark`)
[U+F]. Tests and benchmarks are `EXTRA_PROGRAMS`, built with `make tests` and
`make benchmarks`; build them with `make -k`, as the build playbook requires.

`HadronsXmlValidate` parses a parameter file against Hadrons' own module registry only; it does
not know HadronsMILC's modules, so it cannot check a HadronsMILC input.

### Programs that do not compile at 3a098015

| Program | First error | Label |
|---|---|---|
| `tests/Test_hadrons_spectrum`, `Test_sigma_to_nucleon`, `Test_xi_to_sigma` | `MContraction::Baryon`, `SigmaToNucleon*`, `XiToSigma*` are not members | [F]: the fork has no baryon contraction modules (moved out from 9ec7c43c, "Temporarily move modules that nvcc won't compile on Summit"); upstream still has them |
| `benchmarks/Benchmark_meson_field` | `DomainWallFermionR` is not a type | [U+F]: Grid no longer defines the `…R` typedefs |

Observed in one CUDA build and one CPU build of the same commits; the other 15 test programs
built. None of these four is used by HadronsMILC.
