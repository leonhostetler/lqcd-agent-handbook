---
title: MILC staggered inverter types
summary: The four staggered inv_type choices, their normal-equation paths, parity behavior, set dispatch, initial guesses, and backend requirements.
scope: [software:milc, solver:staggered-inverter]
load_when: Selecting, debugging, or comparing a MILC staggered inv_type or interpreting its parity work.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quark_types.h#L175-L213
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L203-L365
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L436-L708
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L723-L1305
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn.c#L15-L108
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_multicg.c#L763-L823
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/setup.c#L530-L835
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c#L72-L341
observed: "2026-08-19"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC staggered inverter types

MILC's generic staggered interface defines four `enum inv_type` values. In
`ks_spectrum` they are selected by the input strings `CG`, `CGZ`, `UML`, and
`MG`. This page covers the staggered `generic_ks` implementations, not Wilson or
clover inverters that reuse the same control structure.

## Algorithm and parity behavior

| Input | Implementation | Solve structure | Initial state and parity consequence |
| --- | --- | --- | --- |
| `CG` | `mat_invert_cg_field` | Forms `Mdag * src`, then solves the normal equation independently on even and odd sites. | Supports a supplied destination as an initial guess. At nonzero mass, applying `Mdag` to a parity-pure source generally populates both parities, so source parity does not normally remove one solve. |
| `CGZ` | `mat_invert_cgz_field` | Solves the even and odd systems directly from `src`, then applies `Mdag` to obtain the full solution. | Allocates a zero high-mode guess; optional deflation may seed low modes. A parity with exactly zero source norm is returned as a zero solution with zero iterations. |
| `UML` | `mat_invert_uml_field` | Forms `Mdag * src`, solves the even system, reconstructs the odd solution from the even solution and source, then polishes the odd system. | The primary solve parity is always even. Reconstruction divides by `2 * mass`, so this implementation is not a mass-zero path. |
| `MG` | QUDA multigrid wrappers | Solves the full staggered Dirac system through QUDA rather than exposing separate MILC even- and odd-normal-equation solves. | Requires the QUDA GPU multigrid build path. A source that is merely parity-pure is still one full-system solve; only a completely zero source is trivial. |

`CG`, `CGZ`, and `UML` overwrite `qic->parity` while executing their internal
even and odd phases. `ks_spectrum` sets the propagator control parity to
`EVENANDODD`; its input does not select which internal parity these algorithms
solve first.

The zero-source shortcut is exact: the selected parity norm is globally summed.
If it is zero, MILC zeros that parity of the destination, marks the solve
converged, and reports zero iterations. For a block solve, the norm is summed
over every right-hand side, so the parity is skipped only when all block sources
are zero there.

## Choosing with source parity

Classify the source using
[`quark-source-types.md`](quark-source-types.md) before reasoning about parity
work.

- `CGZ` is the only choice whose normal-equation right-hand side is the original
  source. A fresh parity-pure source can therefore eliminate the absent-parity
  solve through the zero-source check.
- `CG` first applies `Mdag`; its parity support is not generally the same as the
  original source.
- `UML` always pays for the even primary solve and uses the odd system only for
  reconstruction and polishing. Do not assume that exchanging even and odd
  source support gives symmetric work.
- `MG` is a full-system QUDA solve. Treat source parity as a property of the
  right-hand side, not as a request for a different MG solve parity.

These mechanisms predict solver work, not wall-clock ordering. Benchmark the
executed path before making a performance choice, and retain convergence and
correctness checks.

## Propagator-set dispatch

`ks_spectrum` groups propagators into sets. The set type changes how the selected
`inv_type` is reached:

| `set_type` | Dispatch |
| --- | --- |
| `single` | Calls the selected single-source field inverter for each source/color entry. |
| `multisource` | Uses the selected block inverter for several sources at one mass. |
| `multicolorsource` | Uses the selected block inverter across source colors at one mass. |
| `multimass` | Uses separate selected single-mass inverters when there are at most two masses or eigenvectors are enabled. With more than two masses and no eigenvectors, `mat_invert_multi` instead executes the multimass CG path on even and odd sites, regardless of the requested `inv_type`. |

Every member of one set must have the same requested inverter type, initial-load
status, precision, and other set-wide controls required by the application.

If any propagator is loaded as an initial guess, `ks_spectrum` changes the
execution to `single` and `CG`. This avoids UML's odd-site reconstruction
overwriting a preloaded odd solution. Therefore the input `inv_type` is not
proof of the executed inverter when an initial propagator is supplied.

## Multigrid rebuild modes

For `MG`, the accepted rebuild strings are:

| Input | Behavior |
| --- | --- |
| `FULL` | Request a full multigrid rebuild. |
| `THIN` | Request the lower-overhead thin rebuild, which may produce a less effective preconditioner. |
| `CG` | Bypass multigrid for that call. The observed dispatch invokes MILC's UML implementation and warns that forced solves should be moved to a different set. |

The `CG` rebuild label should not be confused with `inv_type CG`: the current
fallback implementation is UML. Without the compiled multigrid path,
`ks_spectrum` initializes the rebuild choice to this fallback.

## Deflation interaction

The MILC `CG`, `CGZ`, and `UML` implementations can apply their CPU low-mode
deflation step on both parities. When the QUDA deflation path is compiled, those
CPU deflation calls are skipped and deflation ownership moves to QUDA.

Deflation does not change the parity algorithms above:

- `CGZ` may begin from an exact low-mode component rather than an entirely zero
  vector, but its high-mode guess remains zero and its right-hand side remains
  `src`.
- `UML` still solves even first and reconstructs odd.
- block zero-source detection still considers all right-hand sides together.

For preserved QUDA-space ownership, mass shifting, and invalidation, load
[`../../quda/internals/milc-deflation-space.md`](../../quda/internals/milc-deflation-space.md).

## Runtime confirmation

Confirm the executed path from output rather than the input label alone.
Relevant messages identify plain CG, zero-guess CG, UML, multigrid, multimass,
and block calls. Also record:

- set type and right-hand-side count;
- mass count and whether eigenvectors forced separate inversions;
- source parity and whether a zero-source parity reported zero iterations;
- initial-propagator use and any forced `single`/`CG` substitution;
- MG rebuild choice and whether the UML fallback ran; and
- backend, precision, convergence, residuals, and elapsed time.

This source-backed page deliberately makes no universal speed ranking among the
four choices.
