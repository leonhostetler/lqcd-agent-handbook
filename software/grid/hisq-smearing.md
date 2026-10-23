---
title: HISQ smearing in the Grid fork, and its slow stencil setup on GPUs
summary: What the fork's HISQ smearing computes and its limits, why it is slow on GPUs at the HadronsMILC 0.3.0 pin, and the one-header fix that is a drop-in.
scope: [software:grid, fermion:staggered]
load_when: Smearing HISQ links with Grid or HadronsMILC (MGauge::HISQSmear), checking smeared links, or diagnosing slow smearing or slow GeneralLocalStencil construction on a GPU.
evidence: source
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/qcd/utils/HighlyImprovedStaggeredFermionImpl.h#L106-L500
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/qcd/utils/Transporters.h#L110-L260
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/stencil/GeneralLocalStencil.h#L79-L151
  - https://github.com/milc-qcd/Grid/commit/e57b352ec
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/tests/smearing/Test_fatLinks.cc#L30-L201
  - https://github.com/paboyle/Grid/blob/3232b438f2cf729e515c185e2dbf29d7cc276bb7/Grid/stencil/GeneralLocalStencil.h
  - operator report of production smearing times with and without the fix (anonymized)
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {cuda: "13.3"}
---

# HISQ smearing (Grid fork)

Labels: **[U+F]** upstream and fork; **[F]** fork-only. Lines at fork commit d67dd207.

## What it computes [F]

`HighlyImprovedStaggeredFermionImpl` (absent upstream; HadronsMILC exposes it as
`MGauge::HISQSmear`) builds two-level HISQ links: it multiplies the thin links by MILC-convention
staggered phases and the boundary phase (default antiperiodic in time), smears to fat7 links
without Naik, projects to U(3), then applies the asqtad step with the Lepage and Naik terms,
producing fat and long links.

- **No Naik-epsilon (charm) correction**: it exists only as commented-out code, so the output
  is valid for light and strange valence quarks, not charm.
- Phases and boundary are baked into the links, so pair them only with an operator that imports
  links verbatim (`ImportGaugeSimple`; see `solvers/staggered.md`).
- `tests/smearing/Test_fatLinks --gauge U --fat F --long L --tol t` [F] compares the smearing
  of `U` against supplied fat and long links. Without `--fat`/`--long` it compares the smearing
  with itself and passes trivially, so it validates nothing.

## Why it is slow on GPUs, and the fix

**The mechanism [U+F].** Smearing builds many `GeneralLocalStencil` objects, and at d67dd207
the stencil constructor fills its lookup table with one blocking host-to-device copy per entry
(`acceleratorPut` inside the fill loop, `GeneralLocalStencil.h:79-151`): `npoints × outer
sites` tiny synchronous copies per stencil, each paying the full latency. Upstream `develop`
has the same code. On a CPU build the copy is a host memory copy and cheap.

**The fix [F].** Fork commit e57b352ec ("Bulk transfer GeneralLocalStencil lookup table to
device", on `feature/LMI-develop`, after the HadronsMILC 0.3.0 pin) fills a host vector and
issues one copy; it changes only `Grid/stencil/GeneralLocalStencil.h`. Because the header has
no compiled counterpart in `libGrid.a`, a d67dd207 stack can take the e57b352ec copy of that one
file first on the consumer's include path; record it as a local patch in the stack.

**Effect.** Without the fix, smearing time grows linearly with the local volume (about
3.8 × 10⁻⁴ s per local site on one GB200 GPU; measured at 16³×32 and 32⁴); an operator report
puts an 80³×144 lattice on 8 GPUs at about 2000 s before the fix and about 1 s after. With the
fixed header, smeared links on a 4⁴ test lattice were bitwise identical to the unpatched code's
(fat and long residuals exactly 0 in `Test_fatLinks`), as the change to copy order alone predicts.
