---
title: HadronsMILC
summary: Role of HadronsMILC, how its releases pin Grid, Hadrons and pyfm, how a run reports its own provenance, and the 0.3.0 fixes that bear on outputs made with older versions.
scope: [software:hadronsmilc]
load_when: Selecting, building or auditing HadronsMILC, or judging whether outputs made with an older HadronsMILC are trustworthy.
evidence: source
sources:
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/CHANGELOG.md
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/DEPENDENCIES
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/main.cpp#L17-L37
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/configure.ac#L82-L140
observed: "2026-10-23"
observed_on:
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
---

# HadronsMILC

HadronsMILC adds staggered, MILC-convention modules to Hadrons — HISQ smearing, MILC-normalised
actions, staggered solvers and Lanczos, spin-taste gamma maps, random-wall and diluted sources,
all-to-all and LMA meson fields — and builds one executable, `HadronsMILC`, plus a
`HadronsContractor`. It is the measurement engine of the light-quark g-2 low-mode-improvement
(LMI) workflow; pyfm generates its parameter files.

## Versions travel together

- Each release pins its Grid and Hadrons commits in `DEPENDENCIES` (0.3.0: Grid d67dd2079bea,
  Hadrons 3a0980157914, both on `milc-qcd` forks). Build exactly those, plus any header fixes
  recorded with the stack.
- pyfm 0.X pairs with HadronsMILC 0.X. A generated file's `<grid><provenance>` carries pyfm's
  version and `hadronsMilcCompat`; HadronsMILC logs it and warns on a MAJOR.MINOR mismatch.
- Releases are commits on `main` with a `Release v0.X.Y` message. The 0.3.0 tag was not
  published, so `git describe` of the 0.3.0 commit reads `v0.2.1-62-g4a19a15`; identify
  versions by commit.

## A run reports its own stack

From 0.2.1, `HadronsMILC --version` and every job's start-up banner print five lines: the
HadronsMILC version and `git describe`, `Grid git=` (from the installed `Grid/Version.h`),
`Hadrons git=` (from `hadrons-config --git` at configure time), the GridMilc version, and
`Dependency pins=match|mismatch|unchecked`. pyfm's audit parses them. `Grid git=unknown` or
`Dependency pins=mismatch` usually means Grid or Hadrons was built out of tree without the
fixes in `software/grid/build.md` and `software/hadrons/build.md`, not that the commits are
wrong — check before trusting either way.

## Before trusting outputs made with an older version

The 0.3.0 release (2026-10-10) records fixes that matter for existing data:

- **`MSolver::StagCGMILC` subtract-guess bug.** Its `<name>_subtract` solver returned the guess
  minus the final residual instead of the solution minus the guess. Per the changelog, V vectors
  made by `StagA2AVectors` with this solver and guess-vector `lowModes` "are wrong and must be
  regenerated". `StagMixedPrecisionCG` is a different solver; confirm from the input file
  which one an older run used.
- **A use-after-free on gauge links**, fixed in the same release.

To audit an older result, read its log banner (0.2.1 and later) or its build record for the
three commits, and its parameter file for the solver modules, before comparing anything with it.

## Where to look

- [`build.md`](build.md): configure, pin checking, header overrides, linking, and the provenance stamp.
- [`build-profiles.yaml`](build-profiles.yaml): the LMI option sets.
- [`applications/lmi.md`](applications/lmi.md): the LMI workflow, its conventions, sizing and checks.
- [`validation.md`](validation.md): the release's test suite, what is stale in it, and how to read it.
