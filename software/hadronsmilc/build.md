---
title: Building HadronsMILC
summary: Configure against installed Grid and Hadrons with strict pin checking, carry header-only fixes as an include-path overlay and prove they took effect, the link step, and the provenance a build should end with.
scope: [software:hadronsmilc]
load_when: Configuring, compiling, linking or installing HadronsMILC, or adding a header-only Grid fix to a HadronsMILC build.
evidence: source
sources:
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/configure.ac#L12-L150
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/Makefile.am
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Makefile.am
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/bootstrap.sh
observed: "2026-10-23"
observed_on:
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
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

# Building HadronsMILC

Build Grid (`software/grid/build.md`) and Hadrons (`software/hadrons/build.md`) at the commits
in HadronsMILC's `DEPENDENCIES` first, and make sure both record their commits: Grid's
installed `Grid/Version.h` stamped, Hadrons configured with `GIT_DIR`.

## Bootstrap and configure

1. `./bootstrap.sh` runs `autoreconf` (no downloads).
2. Put the Grid and Hadrons `bin/` directories on `PATH`; configure stops without
   `hadrons-config`, and takes the compiler and flags from it.
3. Configure out of tree:
   `<src>/configure --prefix <prefix> --with-grid=<grid> --with-hadrons=<hadrons>
   --enable-strict-pins [CXXFLAGS="-I<overlay>/include"]`.
   With `--enable-strict-pins`, configure fails unless it reads both commits and they match
   `DEPENDENCIES`; its output then says `grid commit matches DEPENDENCIES pin …` and
   `hadrons commit matches …`.

## Header-only fixes as an include-path overlay

`CXXFLAGS` given to configure come first; configure appends the Grid and Hadrons include paths
after them (`configure.ac:16-22`). Grid and GridMilc include their own headers with angle
brackets, so a directory given here replaces a header for every HadronsMILC source. That
carries a fix that exists only as a header, on a later Grid commit, onto a release pin without
rebuilding Grid — provided no compiled library contains the old code. For the 0.3.0 pin both
fixes in use qualify: Grid's `GeneralLocalStencil.h` (e57b352ec) and GridMilc's `StagGamma.h`
(dee6224b7) are used by neither `libGrid.a`, `libGridMilc.a` nor Hadrons
(`software/grid/hisq-smearing.md`, `software/grid/validation.md`).

**Prove it took effect.** After compiling, the dependency records (`.deps/*.Po`, depmode
`gcc3`) name every header by absolute path. Count objects naming the overlay copy (expect a
non-zero count for each overridden header) and objects naming the installed copy (expect
zero). In the validated stack, 40 objects named the overlay `GeneralLocalStencil.h`, 16 the
overlay `StagGamma.h`, and none the installed copies.

## Build, link and install

The build used for the validated stack ran the library first and then each executable:
`make -C src`, `make HadronsMILC`, `make -C utilities HadronsContractor`, `make install`.

**The validated stack linked both executables with the gold linker** — the Makefile's own
`LDFLAGS` plus `-Xcompiler -fuse-ld=gold` for an nvcc link, or `-fuse-ld=gold` for a host
compiler link. Why it was chosen is not established here, and the default linker was not
tried; if a build linked otherwise fails or misbehaves, this is a difference from the validated
stack to check first.

## A build is finished when it reports its stack

`HadronsMILC --version` (run through the launcher on a compute node for a GPU build) should
print the release version, `Grid git=<pinned commit>… clean`, `Hadrons git=<branch>
<pinned commit>`, and `Dependency pins=match`. Record it with the stack, together with any
overlay headers and their checksums: the banner reports the pinned commits, not the overlay.
