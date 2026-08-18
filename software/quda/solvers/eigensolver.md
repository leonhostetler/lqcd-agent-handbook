---
title: QUDA eigensolvers
summary: Supported eigensolver families, parameter invariants, Chebyshev semantics, and validation traps.
scope: [software:quda, solver:eigensolver]
load_when: Configuring, debugging, or validating QUDA eigensolvers, polynomial acceleration, or eigensolver-backed deflation.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/enum_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/eigensolve_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eigensolve_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_trlm.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_block_trlm.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_trlm_3d.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_iram.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/eigensolve_test.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/eigensolve_test_gtest.hpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_eigensolve_test.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/staggered_eigensolve_test_gtest.hpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/utils/command_line_params.cpp
observed: "2026-08-18"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
---

# QUDA eigensolvers

This leaf covers the native eigensolver family selected through `QudaEigParam` and
`EigenSolver::create()`. The public parameter structure and the selected checkout remain
canonical; use this summary to choose a supported path and to recognize misleading tests or
diagnostics.

## Choose a supported solver and operator

| `QudaEigType` | Implemented scope |
|---|---|
| `QUDA_EIG_TR_LANCZOS` | Hermitian operators; real spectrum (`LR` or `SR`) |
| `QUDA_EIG_BLK_TR_LANCZOS` | Hermitian operators; real spectrum; block-size constraints apply |
| `QUDA_EIG_TR_LANCZOS_3D` | Hermitian 3D systems split in `ortho_dim = 3`; real spectrum |
| `QUDA_EIG_IR_ARNOLDI` | Hermitian or non-Hermitian operators; real, modulus, or imaginary selection as the operator permits |
| `QUDA_EIG_BLK_IR_ARNOLDI` | Enumerated but not implemented; the factory errors |

The shared factory rejects a non-Hermitian operator for a Lanczos solver, an imaginary
spectrum for a Hermitian operator, and `compute_svd` without a normal operator. Polynomial
acceleration adds stricter requirements: both operator and solver must be Hermitian, and the
requested spectrum must be `QUDA_SPECTRUM_SR_EIG`.

## Respect search-space invariants

The common constructor requires `n_kr > n_ev >= n_conv > 0`. A value of `-1` for
`n_ev_deflate` resolves to `n_conv`; the resolved count may not exceed `n_conv`.
`ortho_block_size` must be non-negative.

Additional Lanczos constraints are enforced by the concrete solvers:

- TRLM requires `n_kr >= n_ev + 6` and `n_kr >= n_conv + 12`.
- Block TRLM requires `n_kr >= n_ev + 6`; `block_size` must be positive, may not exceed
  `n_conv`, and must divide both `n_kr` and `n_ev`.
- TRLM3D requires `n_kr >= n_ev + 6` and supports only spatial splitting with
  `ortho_dim = 3`.

If `require_convergence` is true, exhausting `max_restarts` is an error. If it is false,
the solver warns and continues with the current factorization; callers must then inspect the
recomputed eigenvalues and residuals rather than treating return as convergence.

## Interpret Chebyshev acceleration correctly

QUDA's Chebyshev polynomial is small on `[a_min, a_max]` and grows only below `a_min`.
It therefore accelerates the smallest-real spectrum; it is not a generic accelerator for
both ends of the spectrum. In particular, `LR` with `use_poly_acc` is rejected rather than
silently mapped to `SR`.

- `a_max <= 0` requests a power-iteration estimate. The current estimator normalizes on
  every iteration and adds a safety margin.
- A non-finite `a_max` or `a_min >= a_max` is an error.
- A non-positive `a_min` produces a warning. At zero the polynomial is degenerate and
  neither suppresses nor amplifies, so polynomial work does not imply acceleration.
- `poly_deg = 0` with acceleration is an error.

For accelerated `SR`, the solver targets the largest modes of the transformed operator.
The internal `reverse` state and the displayed spectrum label therefore describe transformed
ordering, not a changed user request. TRLM, BlockTRLM, and TRLM3D may negate their projected
problems for this ordering, but must restore Ritz-value signs before values cross the solver
boundary. The common final check applies the original operator to recompute eigenvalues and
residuals; use those results when deciding whether the requested spectrum was returned.

## Validate the path that can fail

Do not infer polynomial-acceleration coverage from the gtest spectrum matrix. In both
`eigensolve_test` and `staggered_eigensolve_test`, `--enable-testing` forces
`use_poly_acc = false` after the parameter tuple is applied. The matrix exercises `LR` and
`SR`, but only without acceleration.

When polynomial acceleration or transformed Ritz state is in scope, run focused standalone
cases without `--enable-testing`:

1. Exercise `SR` with acceleration for scalar TRLM and for BlockTRLM with a block size
   greater than one.
2. Verify that `LR` without acceleration still returns the upper end of the spectrum and
   that `LR` with acceleration fails at construction.
3. If bound handling changed, cover both an explicit valid `a_max` and automatic estimation,
   plus a non-finite `a_max` and invalid bound ordering.
4. Check final eigenvalues and residuals against the original operator. For a positive
   semidefinite operator, negative returned Ritz values indicate a transformed-state boundary
   failure even if internal convergence tests pass.
5. Add TRLM3D, IRAM, ARPACK, deflation, or multigrid integration only when the changed call
   path can affect it; source-level reachability through the shared factory is not runtime
   validation.

Record the operator form, preconditioning, solver type, spectrum, polynomial settings,
search-space sizes, block size, precision, and whether the harness rewrote any parameter.
Without that state, a convergence or wrong-spectrum report is not reproducible.
