---
title: Grid improved-staggered operator, CG, mixed-precision CG and Lanczos
summary: Operator conventions and the two gauge-import paths, the even-odd operator, CG and mixed-precision CG stopping rules and log lines, and implicitly restarted Lanczos with Chebyshev acceleration, including how a badly placed Chebyshev cut fails.
scope: [software:grid, solver:cg, solver:eigensolver, fermion:staggered]
load_when: Configuring, sizing, debugging or reading the logs of a Grid staggered solve or Lanczos eigensolve, directly or through Hadrons/HadronsMILC.
evidence: source
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/qcd/action/fermion/implementation/ImprovedStaggeredFermionImplementation.h#L107-L285
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/LinearOperator.h#L598-L637
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/iterative/SchurRedBlack.h#L304-L370
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/iterative/ConjugateGradient.h#L94-L259
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/iterative/ConjugateGradientMixedPrec.h#L57-L164
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/lattice/Lattice_transfer.h#L1362-L1530
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/iterative/ImplicitlyRestartedLanczos.h#L66-L497
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/algorithms/approx/Chebyshev.h#L37-L252
  - https://github.com/paboyle/Grid/blob/3232b438f2cf729e515c185e2dbf29d7cc276bb7/Grid/algorithms/iterative/ImplicitlyRestartedLanczos.h
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
---

# Grid staggered solvers

Labels: **[U+F]** upstream and fork (identical on upstream `develop` 3232b438f, or the cited part
checked there); **[F]** fork-only. Lines at fork commit d67dd207. The HadronsMILC modules that
wrap these classes, and their mass and residual conventions, are HadronsMILC knowledge.

## Operator and the two ways to import links

- `ImprovedStaggeredFermion` holds one-hop and three-hop doubled link fields and applies
  `M = Dhop + mass` (`Mooee = mass`) [U+F]. `ImprovedStaggeredFermionD/F` are the double and
  single precision variants; the plain `...R` names used by older tests no longer exist.
- **`ImportGauge(Uthin, Ufat, Ulong)`** applies Grid's staggered phases, boundary phases and the
  `±½·c1/u0`, `±½·c2/u0³` coefficients (constructor defaults c1 = c2 = u0 = 1) [U+F for the
  scaling; the three-field overload is F].
- **`ImportGaugeSimple(Ulong, Ufat)`** stores the links as given — forward link, and minus the
  adjoint of the shifted link backward — with no phases, no ½ and no coefficients [U+F].
- Consequence: MILC-convention fat and long links, which already carry phases and
  coefficients, must go through `ImportGaugeSimple`. Through `ImportGauge` they would be phased
  twice and their hop halved.

## Even-odd operator [U+F]

`SchurStaggeredOperator::Mpc = mass² − Meo·Moe`; it is its own adjoint and positive definite
because the hop is anti-Hermitian, so `Mpc = mass² + D_oe†D_oe` on one parity.
`SchurRedBlackStaggeredSolve` (default parity odd) solves `Mpc` on a source carrying an extra
factor of the mass and reconstructs the other parity. Lanczos eigenvalues of this operator are
eigenvalues of `mass² + D†D`, so Chebyshev bounds must bracket that spectrum.

## ConjugateGradient [U+F]

- Stops when the **recursively updated** `|r|² ≤ tol²·|src|²`, then recomputes the true residual
  and logs `ConjugateGradient Converged on iteration k  Computed residual … True residual …
  Target …`. Read the true residual, not only the computed one.
- With `ErrorOnNoConverge` (default true) it asserts if the true residual exceeds 10⁴ × tol,
  and on reaching `MaxIterations` it logs `did NOT converge` and aborts: a double CG that does
  not converge ends the job.
- Per-iteration residuals print at `Iterative` log level.

## MixedPrecisionConjugateGradient [U+F]

- Defect correction: each outer iteration computes the double residual (logged as `Outer
  iteration i residual <norm²> target <stop>`), solves for a correction in single precision to
  an `InnerTolerance` **relative to that residual**, and accumulates in double. The outer loop
  stops at 100 × the target norm² (10 × tol relative), and the inner tolerance is only ever
  loosened.
- A **double** `ConjugateGradient` then always runs from the corrected solution with
  `ErrorOnNoConverge = true` and `MaxInnerIterations` as its limit. Too small a
  `MaxInnerIterations` for that last factor of ten aborts the job.
- The summary `Inner CG iterations N Restarts R Final CG iterations F` gives the cost as inner
  plus final iterations.
- **Single precision cannot usefully go much below about 1e-7** relative: float roundoff is
  about 6e-8, so inner iterations past that reduce the recursive residual but not the true one
  (inferred). An inner tolerance tighter than 1e-7 costs iterations without accuracy.
- The double↔single conversions use a lane-remapping workspace built once per solve, because the
  two grids have different SIMD layouts [F: `Lattice_transfer.h` differs substantially upstream,
  where this was not checked].

## Implicitly restarted Lanczos [U+F, except `kstart`]

- `ImplicitlyRestartedLanczos(PolyOp, HermOp, Nstop, Nk, Nm, resid, MaxIt, …)` runs Lanczos on
  a Chebyshev polynomial of `H` and tests convergence on `H`. Each restart extends the basis from
  Nk to Nm with full re-orthogonalisation, applies Nm − Nk implicit shifts and rotates.
- Convergence is `|H·v − λv|² / λ_max² < resid²`, with λ_max from an initial power iteration:
  **`resid` is relative to the largest eigenvalue**, not to each λ. `betastp` is accepted and
  ignored.
- On reaching `MaxIt` it prints `NOT converged.` and calls `abort()`.
- All Nm basis vectors stay resident in the field's precision, plus about one extra field and an
  Nm × Nm matrix for the basis rotation.
- The fork adds `kstart`, letting already-converged vectors seed the basis [F].

### The Chebyshev lower bound must lie above the Nstop-th eigenvalue

The Chebyshev polynomial on `[alpha, beta]` is bounded by 1 there and grows rapidly below
`alpha`, so eigenvalues of `H` below `alpha` become the largest eigenvalues of `PolyOp`. Any
wanted eigenvalue above `alpha` lands in the bounded band and cannot be separated from the bulk.

**How a too-low `alpha` fails:** the run does not stop. Every restart reports
`#modes converged: >= 0/Nstop`, the restart residual `beta(k)` freezes at one value, and after a
while the Lanczos coefficients become NaN; the solver keeps iterating until `MaxIt` (which input
generators may set in the thousands) or the job's time limit. Observed once — 7 eigenvalues of a
massless 8⁴ quenched operator lay below `alpha = 0.2` with `Nstop = 32` — and the mechanism is
the polynomial's bounded band. Raising `alpha` to 1.0 converged all 32 on the first restart.

**Reading the spectrum from a failed run:** after the first restart the log prints the filtered
eigenvalues (`eval 0 …`). The few that exceed 1 are `T_{n−1}` of the lowest eigenvalues; invert
`cosh((n−1)·acosh(1 + 2(alpha − λ)/(beta − alpha)))` to recover them and place `alpha` above the
Nstop-th with margin. Give eigensolve steps a time limit, and watch the log for the stall
signature rather than waiting for `MaxIt`.
