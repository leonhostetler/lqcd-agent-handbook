---
title: QUDA eigensolvers
summary: Supported eigensolver families, parameter invariants, Chebyshev semantics, and validation traps.
scope: [software:quda, solver:eigensolver]
load_when: Configuring, debugging, or validating QUDA eigensolvers, polynomial acceleration, the Chebyshev filter window, or eigensolver-backed deflation through any entry point.
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
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface_internal.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h
  - operator's screened tuning records
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

## The same parameter has a different name at every entry point

`QudaEigParam` is canonical, but no caller spells its fields that way. Before applying any
guidance about a named eigensolver parameter — here or on a solver page — translate it into
the spelling the intended entry point actually accepts. Reading a MILC multigrid key as a
QUDA field name, or the reverse, is a silent misconfiguration rather than an error.

| `QudaEigParam` field | MILC MG parameter file | QUDA standalone test CLI | QUDA MG-embedded test CLI |
|---|---|---|---|
| `n_ev` | `deflate_n_ev` | `--eig-n-ev` | `--mg-eig-n-ev` |
| `n_kr` | `deflate_n_kr` | `--eig-n-kr` | `--mg-eig-n-kr` |
| `max_restarts` | `deflate_max_restarts` | `--eig-max-restarts` | `--mg-eig-max-restarts` |
| `tol` | `deflate_tol` | `--eig-tol` | `--mg-eig-tol` |
| `block_size` | `deflate_block_size` | `--eig-block-size` | `--mg-eig-block-size` |
| `use_poly_acc` | `deflate_use_poly_acc` | `--eig-use-poly-acc` | `--mg-eig-use-poly-acc` |
| `poly_deg` | `deflate_poly_deg` | `--eig-poly-deg` | `--mg-eig-poly-deg` |
| `a_min` | `deflate_a_min` | `--eig-a-min` | `--mg-eig-a-min` |

**The `deflate_` prefix is specific to the MILC multigrid parameter file**, where those keys
are parsed and copied into the level's `QudaEigParam`. It is not a QUDA field prefix and it
does not appear at other entry points.

**MILC's non-multigrid deflation path is a third convention again.** Its interface struct
carries **unprefixed** members close to the QUDA field names — `n_ev`, `n_conv`,
`n_ev_deflate`, `tol`, `eig_type`, `vec_in_parity`, `partfile` — so guidance written in
`deflate_*` spelling does not transfer to it verbatim even though the underlying knobs are
the same. Note `n_ev_deflate`, which selects how many converged vectors are actually used
for projection and has no `deflate_`-prefixed counterpart.

When citing a parameter in a report, name the entry point alongside it. A bare `a_min` is
ambiguous across four spellings and two callers.

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

**A window placed below the requested spectrum is a convergence failure, not a quality
problem.** `a_min` must exceed the largest eigenvalue you intend to request, with margin.
Set it below that and the filter does not separate the requested modes at all: the solver
restarts without converging and delivers **nothing**, rather than delivering the requested
count with poor residuals. Treat window placement as the first hypothesis when an
eigensolve fails to converge, before search-space sizes or polynomial degree.

**Do not switch acceleration off to simplify a diagnosis.** Where the spectrum bottom is
tightly clustered, polynomial acceleration is what makes the eigensolve tractable rather
than an optional refinement; disabling it has been observed to fail outright at the restart
cap with zero converged vectors. Turning the filter off removes the mechanism, not a
confound, and adds a second unbaselined variable. Keep `use_poly_acc` true and vary the
requested count instead, which is the cheap axis.

For accelerated `SR`, the solver targets the largest modes of the transformed operator.
The internal `reverse` state and the displayed spectrum label therefore describe transformed
ordering, not a changed user request. TRLM, BlockTRLM, and TRLM3D may negate their projected
problems for this ordering, but must restore Ritz-value signs before values cross the solver
boundary. The common final check applies the original operator to recompute eigenvalues and
residuals; use those results when deciding whether the requested spectrum was returned.

## A run that does not converge yields no spectrum at all

Two output behaviours govern how an eigensolve can be diagnosed, and both are easy to
discover the expensive way.

**Eigenvalues print only on completion.** A converged run emits its `Eval[...]` lines
together at the end; a run that does not finish emits none of them. **A failed attempt
therefore cannot be mined for the value that would have fixed it** — there is no partial
spectrum to read. Every recipe for establishing a filter window follows from this.

**Deflation application is announced in two forms that are not the same quantity.** At
`QUDA_VERBOSE` the eigensolver prints one of

```text
Deflating <N> vectors
Deflating <N> left and right singular vectors
```

The first comes from the path that deflates eigenvectors of the normal operator; the second
from the path that deflates left and right singular vectors of the operator. **Do not
compare `<N>` across the two forms**; record the count together with the wording that
produced it. When a caller embeds the eigensolver in a multigrid hierarchy, the line is
prefixed with that level, for example `MG level 3 (GPU): Deflating <N> vectors`.

Assert that `<N>` equals the requested count on **every** invocation, not merely the first:
a count that changes mid-run, or a short prefix of invocations, is the observable form of a
partially applied space. Absence of the line altogether, in a run that requested
deflation, means the space was constructed and then not used.

**A block solver can suppress the diagnostics a scalar solver prints.** `block_size > 1`
selects the block Lanczos variant, and it has been observed to emit no restart-summary line
at all, where the scalar variant prints per-restart converged-count accounting and a named
failure giving the request, search space, Krylov space and restart count. Where the block
variant is silent the restart count must be reconstructed from the `blockLanczosStep`
sequence, which descends once per restart and so forms a sawtooth — a fallback, not an
equivalent source. **Prefer `block_size = 1` while diagnosing**, and treat a larger block as
a later performance choice.

## Establishing `a_min` when the spectrum is not yet known

Two approaches with opposite failure modes. Both keep acceleration on, per the correction
above, and both are easier to read at `block_size = 1`.

**Method A — small probe, then extrapolate.** Request a small count with a conservative
`a_min`, then fit the **whole delivered prefix** and extrapolate to the production count.

> **Publish its limitation with it or the recipe is a trap.** The probe measures the largest
> eigenvalue of the *probe's* request; production needs the largest of a much bigger
> request. **Setting `a_min` from a small probe's printed maximum reproduces exactly the
> failure the probe was run to diagnose.** Use the fitted curve, never the top value, and
> state the reach: under a power law with exponent near `1.5`, a `16x` increase in requested
> count is roughly a `74x` increase in eigenvalue.

> **The extrapolation is unreliable and biased low.** Backtested against a hierarchy whose
> full spectrum was known, fitting a short prefix under-predicted in every case
> tried, and the error did not improve with more probe points. The cause is structural:
> where the spectrum bottom is dominated by a constant term, a short prefix largely measures
> that constant and carries little information about the power-law amplitude. Under-
> prediction is the dangerous direction, since it places the window below the request.
> Prefer a ratio transfer from a fully delivered sibling spectrum where one exists, and
> apply a large safety factor regardless.

**Method B — conservative `a_min` at the full count, then tighten.** Request the production
count immediately with a deliberately generous margin.

> **Its advantage is that the output is not a throwaway.** A converged run at conservative
> `a_min` has produced usable production vectors, and since a larger margin improves vector
> residual they are at least as good as a tighter run's, merely slower to obtain. Save them:
> the measured largest eigenvalue then buys a faster later *rebuild* rather than being
> needed to make this run usable at all.

> **Its failure mode is all-or-nothing.** By the completion-only rule above, a
> non-converging attempt yields nothing. A very large margin also tends to *increase* the
> restart count, so an over-conservative window can exhaust the budget by itself.

| Situation | Method |
|---|---|
| no scale information at all | **A** — B cannot choose a conservative window without one |
| plausible upper bound available, ample walltime | **B** — exact value, and the vectors are keepers |
| must guarantee information from a single submission | **A** — it always returns a delivered prefix |
| tight per-attempt budget, cheap retries unavailable | **A** first |

**They compose, and that is the recommended path when starting blind:** run **A** for the
scale, set the window generously above its extrapolated value, then run **B** for the exact
value *and* the production space in one submission.

**Evidence label.** The output behaviours and the block-variant selection are read from
source at the observed revision. The convergence-failure mode, the acceleration correction,
the measured low bias of the short-prefix fit, and the block-variant silence are empirical,
from one operator corpus on one machine; the mechanisms are stated so they can be extended,
the magnitudes are deliberately not given as bands.

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
