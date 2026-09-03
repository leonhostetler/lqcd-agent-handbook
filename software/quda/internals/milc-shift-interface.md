---
title: MILC shift and spin-taste paths through QUDA
summary: Build contracts, selector semantics, a resolved one-sided-shift bug, and resident-gauge validation traps.
scope: [software:quda, software:milc]
load_when: Debugging or validating MILC WANT_SHIFT_GPU or WANT_SPIN_TASTE_GPU paths.
evidence: source
sources:
  - https://github.com/lattice/quda/issues/1614
  - https://github.com/lattice/quda/pull/1615
  - https://github.com/lattice/quda/commit/e318708117360dc09c1f0808615bee93ef372aae
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/interface_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ext_src/make_ext_src.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/f_meas_current.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_meson_mom.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_meson_mom_quda.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/shift_field.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/spin_taste_ops.c
observed: "2026-08-18"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC shift and spin-taste paths through QUDA

MILC's covariant-shift and spin-taste GPU switches exercise operator paths distinct from its
QUDA solver path. A successful QUDA build or solver comparison does not validate these paths.

## Build contract

The applicable build capabilities are:

- MILC: `WANTQUDA=true`, plus `WANT_SHIFT_GPU=true` and/or
  `WANT_SPIN_TASTE_GPU=true` for the path under test;
- QUDA: `QUDA_INTERFACE_MILC=ON` and `QUDA_DIRAC_COVDEV=ON`.

Set `QUDA_DIRAC_COVDEV=ON` explicitly when `QUDA_DIRAC_DEFAULT_OFF=ON`. The two MILC path
switches are independent at the observed revision; enabling the shift path is not a declared
prerequisite for the spin-taste path.

## Selector contract

The canonical selector behavior is the implementation in QUDA `shiftQuda` together with the
MILC interface check in `qudaShift`:

| Selector | Operation |
| --- | --- |
| `1` | forward covariant shift |
| `2` | backward covariant shift |
| `3` | symmetric average of forward and backward shifts |

At the observed QUDA revision, the `include/quda.h` parameter comment says `forward=2`; that is
a documentation error. Do not derive the selector map from that comment.

## Resolved one-sided-shift bug

[QUDA issue #1614](https://github.com/lattice/quda/issues/1614) and
[PR #1615](https://github.com/lattice/quda/pull/1615) record a bug in the selector composition.
The old implementation initialized both temporary fields from the input, conditionally
overwrote the requested forward and backward contributions, and then unconditionally added the
temporaries. A one-sided request therefore retained and added an unmodified input contribution.
The symmetric selector happened to overwrite both temporaries and could pass while both
one-sided selectors were wrong.

The fix dispatches explicitly: selector `1` computes only the forward result, selector `2`
computes only the backward result, and selector `3` computes both and averages them. For an old
or diverged checkout, first test whether it contains the upstream merge commit:

```bash
git merge-base --is-ancestor e318708117360dc09c1f0808615bee93ef372aae HEAD
```

A nonzero result does not prove the checkout is affected because the fix may have been
cherry-picked or reimplemented. Inspect `shiftQuda` for explicit selector dispatch before
qualifying that checkout.

## Consumer reachability

The one-sided selector path is not confined to `ks_measure`. `spin_taste_op_ape_fn` dispatches
the APE rho forward and backward indices to `mult_rhois_ape_field`, and the observed MILC source
has callers in external-source, current-measurement, and meson-momentum code. This establishes
source reachability, not that every build executes those indices. When qualifying an old
checkout, inventory the requested spin-taste indices across its consumers and test every
reachable one-sided case.

## Focused validation

Use a direct CPU-versus-QUDA comparison before an application observable:

1. Start from the same nontrivial, full-volume color vector and gauge field.
2. Compare all four directions for forward, backward, and symmetric selectors.
3. Pass the loop's selector value to both implementations and derive the result label from that
   executed value. A printed parameter matrix is not coverage if the call uses a constant.
4. Report a relative L2 difference, with an absolute-norm fallback when the reference norm is
   zero, against a precision-appropriate tolerance chosen before the run.
5. Exercise first-load and resident-gauge reuse states, then repeat the focused comparison on
   one rank and multiple ranks.
6. Only then validate the application observable or spin-taste operator that consumes the
   shift.

QUDA's covariant-derivative test is useful primitive coverage, but it does not by itself cover
the public shift selector composition, the MILC wrapper, or resident-gauge state transitions.
Use the layered debugging method in `../../../modes/debugging.md` when constructing the
reproducer and evidence chain.

## Resident-gauge trap in the spin-taste path

Some MILC local spin-taste helpers reach the QUDA wrapper without explicit link arguments. The
observed QUDA wrapper can use that form only when its reload state permits reuse and the expected
covariant-derivative gauge is already resident. A preceding GPU shift can establish compatible
resident state, so an application may appear to work only because of call order. Enabling
`WANT_SHIFT_GPU` is not a sound correction for a spin-taste ownership or reload defect.

Validate the spin-taste path by invoking the target local operator first in a fresh process, then
repeat after gauge reuse, on one rank and multiple ranks. A robust interface correction must make
the gauge input, ownership, invalidation, and reload precondition explicit rather than relying on
an earlier operation to prime hidden state.

## Evidence limits

The historical shift defect and fix are public upstream evidence. The current resident-gauge
behavior is source-backed, but this page does not establish that every MILC spin-taste operator
has been validated at the observed revisions. Record the exact operator and state transitions in
any future validation claim.
