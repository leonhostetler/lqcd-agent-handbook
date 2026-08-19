---
title: QUDA MILC deflation-space lifecycle
summary: Ownership, parity reconstruction, eigenvalue mass shifting, batching, invalidation, and exact-current preconditions for the QUDA MILC deflation cache.
scope: [software:quda, software:milc, solver:eigensolver]
load_when: Loading, preserving, reusing, debugging, or cleaning a QUDA deflation space through the MILC interface.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h#L70-L101
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h#L185-L225
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h#L400-L452
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp#L60-L135
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp#L1299-L1645
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp#L1990-L2110
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/milc_to_quda_utilities.c
observed: "2026-08-19"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# QUDA MILC deflation-space lifecycle

The QUDA MILC interface owns process-global preserved deflation state. It keeps:

- one deflation-space pointer for even parity and one for odd parity;
- the mass associated with each parity's current eigenvalues; and
- one shared snapshot of eigenvalues back-shifted to zero mass.

This state can be consumed by deflated MILC solves, `qudaProject`, and
`qudaExactCurrent`. It is separate from QUDA's resident-gauge cache.

## Load modes

`qudaLoadDeflationSpace` accepts one of three modes for the parity selected by
`inv_args.evenodd`:

| Mode | Behavior |
| --- | --- |
| `QUDA_MILC_EIG_COMPUTE` | Calls the deflatable inverter with a dummy source so the eigensolver computes a space or loads it through `vec_infile`. The resulting space is preserved and its eigenvalues are unconditionally back-shifted to refresh the shared zero-mass snapshot. |
| `QUDA_MILC_EIG_LOAD` | Copies the selected parity from full MILC eigenvectors into device fields, then computes Rayleigh-quotient eigenvalues and residuals for the requested operator. |
| `QUDA_MILC_EIG_FROM_OTHER_PARITY` | Reconstructs and normalizes the requested-parity vectors by applying the staggered Dslash to the preserved opposite-parity vectors. Eigenvalues are shifted from the zero-mass snapshot when available; otherwise they are reused or recomputed according to the recorded mass. |

The interface rejects an invalid parity, a missing opposite-parity space, too
few opposite-parity vectors, a null MILC vector array for `EIG_LOAD`, or a
zero-mass cache smaller than the requested preserved space.

When `qudaInvertMsrcDeflatable` requests a preserved parity that does not yet
exist, it reconstructs it from the opposite parity when possible. Otherwise
the eigensolver or vector-file load inside the inversion creates the requested
space.

## Eigenvalue mass convention

For the preconditioned staggered normal operator used by this interface, the
stored mass dependence is

```text
lambda(m) = lambda(0) + 4*m^2
```

After a fresh computation at mass `m`, QUDA records

```text
lambda(0) = lambda(m) - 4*m^2
```

When a preserved space is requested at a different mass and the zero-mass
snapshot exists, QUDA updates the eigenvalues by adding the new `4*m^2`
instead of applying the operator and recomputing every Rayleigh quotient.

A direct `QUDA_MILC_EIG_COMPUTE` intentionally replaces the zero-mass snapshot.
When a deflatable inversion creates a preserved space, it initializes the
snapshot only if none exists. This distinction makes cleanup important before
starting a logically new operator.

The shift is exact only when the operator changes by the mass term alone. The
source explicitly marks shifted eigenvalues as approximate when
`inv_args.naik_epsilon != 0`; more generally, do not reuse the shift across
changes to links, boundary phases, action parameters, or any other
non-mass part of the operator.

If a preserved space is reused at another mass without a zero-mass snapshot,
the deflatable inverter disables preserved eigenvalues so QUDA recomputes them
for that mass.

## Batching

`eigargs.compute_evals_batch_size` controls temporary-vector batching for:

- Rayleigh-quotient and residual computation after `EIG_LOAD`; and
- Dslash reconstruction and any eigenvalue/residual work in
  `EIG_FROM_OTHER_PARITY`.

The implementation caps the batch at the requested eigenvector count. The
configured value must be positive: these paths advance their loops by the
computed batch size. Larger batches expose more multi-right-hand-side work but
allocate more temporary device vectors. This source mechanism does not establish
one universally optimal value.

When shifted eigenvalues are used in the other-parity path, applying the
operator solely to check residuals is gated by `QUDA_DEBUG_VERBOSE`. Normal
verbosity therefore avoids that diagnostic mat-vec work.

## Invalidation and cleanup

`qudaCleanUpDeflationSpace`:

1. deletes both parity spaces and clears their eigenvectors and eigenvalues;
2. resets both recorded masses; and
3. clears the shared zero-mass eigenvalue snapshot.

Call it before reusing the interface with a new gauge field or another change
to the represented operator. Invalidating or reloading QUDA's resident gauge
does not itself clear these process-global deflation pointers or the
zero-mass snapshot.

MILC's observed `finalize_quda` path calls the cleanup routine before
`qudaFinalize`, but finalization is too late to protect multiple distinct
operators processed within one QUDA lifetime. The caller that changes operator
identity owns that earlier lifecycle boundary.

## Exact-current preconditions

At the observed revision, `qudaExactCurrent` requires:

- both even and odd preserved deflation spaces;
- both parity mass tags to be exactly zero;
- at least the requested `eigargs.n_ev` vectors; and
- gauge and covariant-derivative operators compatible with the eigenvector
  storage precision.

Having a zero-mass snapshot is not a substitute for those first two
conditions: the actual parity spaces must be loaded and tagged at mass zero
before the exact-current call.

The exact-current path uses eigensolver precision for its device fields and
operators, even when MILC's solve precision differs. Its host mass and current
arrays are interpreted at MILC's external precision.

## Debugging checklist

When reuse is unexpected or residuals change:

1. record the requested parity, mass, `naik_epsilon`, load mode, vector count,
   eigensolver precision, and batch size;
2. establish whether the parity space came from a fresh computation, MILC
   vectors, a QUDA vector file, or opposite-parity reconstruction;
3. check whether the operator changed without
   `qudaCleanUpDeflationSpace`;
4. distinguish resident-gauge invalidation from deflation-space invalidation;
5. use debug verbosity when a shifted-path residual check is needed; and
6. for exact current, verify both parity mass tags are zero rather than merely
   assuming the cached zero-mass snapshot is sufficient.

See [`../solvers/eigensolver.md`](../solvers/eigensolver.md) for native
eigensolver algorithm and search-space invariants. This page documents source
behavior, not a validated machine-specific exact-current build.
