---
title: Validating a HadronsMILC build with its own test suite
summary: What HadronsMILC 0.3.0's test suite contains, the stale parameter files and script defaults to correct first, why a run must not be judged by its exit code, and how to read the sib check that fails on every build.
scope: [software:hadronsmilc, fermion:staggered]
load_when: Running or interpreting HadronsMILC's test/ suite, or checking that a HadronsMILC parameter file matches the module schemas before a run.
evidence: source
sources:
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/test/README.md
  - https://github.com/Michael628/HadronsMILC/tree/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/test/params
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Modules/MFermion/SpinTaste.hpp#L98-L113
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Modules/MFermion/LMAMesonFieldProp.hpp#L332-L381
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/test/compare_lma_mesonfield.py#L49-L92
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/test/compare_sib_hvp_a2a_batch.py#L1-L60
  - https://github.com/Michael628/HadronsMILC/commit/582c934
observed: "2026-10-23"
observed_on:
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
  toolchain: {gcc: "15.3", cuda: "13.3", openmpi: "5.0.11"}
---

# Validating HadronsMILC with its test suite

`test/` holds hand-written parameter files (`params/`), 4⁴ fixture lattices (`lat/`), frozen
references (`ref/`) and comparison scripts that need Python with `numpy`, `h5py` and, for one,
`pandas`. Run each parameter file from inside a copy of `test/` (outputs go to `work/`) with
`HadronsMILC params/<file> --grid 4.4.4.4`, then its script. The scripts default to a CPU build
at `../build-scalar/HadronsMILC`; 4⁴ fixtures fit one rank only.

## Never judge a run by its exit code

Hadrons' XML reader ignores an element in the wrong place and leaves the parameter at its
default. A `MFermion::SpinTaste` module whose `<gammas>` is not nested in `<spinTaste>` gets an
empty gamma list: the run only warns ("empty gamma list; publishing an empty vector",
"MesonField: empty spin-taste gamma list; no meson fields will be computed"), exits 0 and writes
nothing. Scan every log for those lines and for "is not produced by any module" (a reference to
an object no module publishes, which aborts at graph construction), and check that every
expected output file exists.

## Correct the release's stale inputs first

Twenty of the 26 XML files in `test/params/` at 0.3.0 do not match the 0.3.0 modules:

- **11 use the old flat `SpinTaste` options.** Since the gamma-map rework (2026-09-25/26),
  `SpinTasteMILCPar` nests `gammas`, `applyG5` and `gauge` in `<spinTaste>`
  (`SpinTaste.hpp:110-113`); wrap them.
- **6 reference `<name>_t0` of a single-timeslice `StagLMAMesonFieldProp`.** Since 582c934
  (before the release) such a module publishes plain `<name>`
  (`LMAMesonFieldProp.hpp:332-339`); drop the suffix.
- **3 are not well-formed XML.**
- `compare_lma_mesonfield.py` documents `--nnoise 1`, but `lma-mesonfield-file-compare.20.xml`
  sets `nNoise=2`; pass `--nnoise 2` or the script stops at its shape check.

Only the `sib-*` parameter files are current. Both schema drifts are mechanically checkable from
the XML alone: every `MFermion::SpinTaste` has a `<spinTaste>` child, and no option value is
`X_t<n>` where `X` is a `StagLMAMesonFieldProp` with one timeslice (or batch mode). Run such a
check on generated and hand-written inputs alike before a submission.

## What the corrected suite shows

With the stale inputs corrected, the CB-pair stencil versus legacy meson fields, the LMA
file-driven and weighted reconstructions, the LMA-guessed mixed-precision CG and the
setup-error negatives all pass on a CUDA build and on a CPU build of the same commits, and every
output dataset agrees between the two builds to ≤ 1.8 × 10⁻⁸ relative (single-precision
storage).

## `compare_sib_hvp_a2a_batch.py` check 1 fails on every build: its expectation is wrong

Check 1 compares the low-mode overlaps of the solve made with the A2A-batch guess and of the
guess itself (`MF(eigfull_vec, h)` vs `MF(eigfull_vec, g)`) **timeslice by timeslice**, at
1 × 10⁻⁴. The high-mode part of the solution is orthogonal to the eigenvectors only over the
whole volume, so per-timeslice overlaps need not agree (they differ by 1.6 relative), while
their time sums agree to round-off (4 × 10⁻⁸, the ratio exactly 1 for every eigen-pair row) on
both a GPU and a CPU build. The guess is exactly the low-mode part of the solution; the check's
expectation is wrong. Verify the time-summed overlaps instead, and do not treat this failure
alone as a build defect.

## HISQ smearing is not exercised by the suite

The suite loads pre-smeared fixture links. To check `MGauge::HISQSmear`, smear
`lat/lat.sample.l4444.ildg.20` with `HISQSmear`, save the links with `MIO::SaveIldg`, and
compare them with Grid's `Test_fatLinks --gauge … --fat … --long …` (`software/grid/hisq-smearing.md`).
The fixture `fatlinks`/`longlinks` files differ from that smearing by about 1.6 × 10⁻⁷ and
1.2 × 10⁻⁷ relative and their provenance is unrecorded, so they are not a reference for it.
