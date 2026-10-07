---
title: QUDA staggered deflated CG through MILC
summary: Native-CG deflation mechanics, eigenspace lifecycle, mass and parity validity, memory objects, suitability, and runtime checks for MILC staggered solves.
scope: [software:quda, software:milc, solver:deflated-cg, fermion:staggered]
load_when: Selecting, configuring, sizing, debugging, or validating QUDA low-mode-deflated CG for a MILC staggered solve.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/invert_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/quda_milc_interface.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solver.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_cg_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eigensolve_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/CMakeLists.txt
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn_quda.c
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/d_congrad5_fn_quda.c#L136-L160
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/eigen_stuff_QUDA.c#L112-L255
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile#L604-L619
observed: "2026-10-07"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
---

# QUDA staggered deflated CG through MILC

In this path, “deflated CG” means native `QUDA_CG_INVERTER` with a non-null
`QudaEigParam`. QUDA computes or restores low eigenmodes, uses them to construct a
projected initial correction, and can repeat that projection at reliable updates.

It is not `QUDA_EIGCG_INVERTER` or `QUDA_INC_EIGCG_INVERTER`. Those are separate
incremental-EigCG implementations with a different interface and lifecycle. Keep the
name distinction in run records and performance comparisons.

## Operator and algorithm

The Krylov operator is the same selected-parity Hermitian normal equation as plain
staggered CG:

```text
A_p(m) = 4 m^2 - D_pq D_qp.
```

The MILC interface supplies a TRLM or BlockTRLM eigensolver configured for the
smallest-real spectrum of that preconditioned operator. On first use, the CG solver:

1. constructs an eigensolver for `matEig`;
2. restores a preserved deflation space when present, otherwise allocates `n_conv`
   eigenvectors and computes or loads them;
3. optionally recomputes eigenvalues if vectors were preserved across an operator
   change for which eigenvalues were not preserved;
4. applies the low-mode correction to the current residual;
5. recomputes the true Krylov residual after the projection; and
6. runs the ordinary mixed-precision CG recurrence on the remaining error.

For an eigenspace `V` with eigenvalues `Lambda`, the initial correction has the form

```text
y <- y + V Lambda^-1 Vdag r,
r <- b - A y.
```

The projection changes the iterative initial state; it does not change the operator or
the requested final residual.

## Initial and repeated deflation

The initial projection occurs whenever deflation is enabled and `maxiter > 1`. At a
reliable update, CG can project again when

```text
sqrt(r2) < maxr_deflate * tol_restart.
```

Consequently, `tol_restart = 0` disables repeated reliable-update deflation for a
positive residual while leaving the initial projection active. Treat `tol_restart` as a
behavioral control, not as an inert eigensolver tolerance.

When a caller supplies an initial guess, QUDA first forms `r = b - A x0`, then adds the
deflation correction and recomputes the residual. The first CG residual shown after
projection is therefore not necessarily the source norm or the residual of the raw
caller guess.

The heavy-quark-residual CG path explicitly rejects deflation.

## Eigenspace lifecycle and validity

The generic solver moves eigenvectors and eigenvalues into
`preserve_deflation_space` when `preserve_deflation` is true, then restores them into the
next solver instance. The MILC interface keeps one process-global pointer for even
parity and one for odd parity, plus mass tags and a shared zero-mass eigenvalue snapshot.

Through MILC `6b9b8a06` the staggered call site requested `n_ev_deflate > 0` only for
even-parity solves. From `d17e9559` (PR #99, 2026-10-06) it requests it for every parity
whose propagator says `deflate yes` (the single-source entry now wraps the multi-source one),
so the first odd-parity solve makes QUDA reconstruct the odd space from the preserved even
one. The same call site zeroes `n_ev_deflate` whenever the propagator asks for a nonzero
relative residual, because QUDA's deflation does not support that stopping condition; the
only trace is the line `Solving for <n> source(s) without deflation for parity <p>`.

From `d17e9559` MILC's `ks_spectrum` and `ks_measure` also build the space before any solve,
through `load_evecs_quda`, at mass zero from the charge-0, Naik-epsilon-0 links. The
eigensolver window is therefore judged against the zero-mass spectrum, and every solve's
eigenvalues come from the `4 m^2` shift below. Before that merge the space was computed inside
the first deflated solve, at that solve's mass.

For the preconditioned staggered normal operator, the interface shifts preserved
eigenvalues across masses using

```text
lambda(m) = lambda(0) + 4 m^2.
```

That update is exact only when the non-mass operator is unchanged. The source marks it
as approximate when `naik_epsilon != 0`. Changes to links, boundary phases, Naik term,
action, parity representation, or other operator state require an explicit validity
decision and usually cleanup/reconstruction, not merely a new mass tag.

The canonical details are in
[`../internals/milc-deflation-space.md`](../internals/milc-deflation-space.md). Native
TRLM/BlockTRLM search-space and polynomial invariants are in
[`eigensolver.md`](eigensolver.md).

## Cost structure

Deflated CG has three distinct costs:

- **setup:** generate or load the eigenvectors and establish eigenvalues;
- **projection:** dense reductions and vector updates for the retained low modes at the
  initial residual and any triggered repeated deflation; and
- **remaining solve:** ordinary CG iterations and reliable updates.

A preserved space removes repeated eigensolver setup only while it remains valid. It
does not remove projection cost, the resident-vector memory cost, or the need to confirm
true residuals. Source structure establishes these components but not the solve count at
which they beat plain CG or multigrid.

## Build and stack requirements

The path needs the same QUDA MILC and staggered capabilities as plain CG:

```text
QUDA_INTERFACE_MILC=ON
QUDA_DIRAC_STAGGERED=ON
```

MILC must compile with QUDA CG and eigensolver support (`HAVE_QUDA`, `USE_CG_GPU`, and
`USE_EIG_GPU`). Through `6b9b8a06` MILC's Makefile forced `WANT_EIG_GPU` on with
`WANT_FN_CG_GPU`; from `d17e9559` it does not, and a build without `USE_EIG_GPU` can deflate
only with eigenvectors MILC reads from its own files or computes on the host and hands to QUDA
(`QUDA_MILC_EIG_LOAD`), a fresh-eigenvector request then terminating at input. The selected
QUDA revision, precision set, communication backend, eigenvector I/O path, and intended
block-TRLM settings still require stack validation.

## When to use it

Use this path when:

- the target system is the selected-parity Hermitian staggered normal equation;
- low modes can be represented by a valid eigenspace for the exact operator;
- enough compatible solves will reuse that space to justify its setup and residency;
- the retained-vector count and eigensolver workspace fit with safe device-memory
  headroom; and
- the stack has validated both the eigensolve and the deflated solve, including true
  residuals.

Typical reuse candidates are multiple right-hand sides or masses whose eigenvectors
remain valid under the interface's mass-shift contract. The actual crossover depends on
solve count, source structure, mass, lattice, hardware, and eigensolver setup; benchmark
it rather than importing a campaign-specific threshold.

## When not to use it

Do not use or reuse this path when:

- the requested solve is the full non-Hermitian staggered system rather than the parity
  normal equation;
- the links, phases, action parameters, Naik term, or parity representation changed
  without rebuilding or explicitly validating the space;
- a heavy-quark residual is the convergence path;
- eigensolver setup cannot be amortized by the expected compatible solve count;
- the retained/search vectors leave insufficient memory for gauge fields, CG workspace,
  communication buffers, and application allocations; or
- the run cannot distinguish native CG deflation from EigCG/IncEigCG in its
  parameters and logs.

Do not treat successful return from an unconverged eigensolver run as proof of
a useful deflation space. The observed MILC path sets `require_convergence` true; other
callers may not.

## Tunables and hard invariants

The deflation layer adds `n_conv`, `n_ev_deflate`, `n_ev`, `n_kr`, eigensolver type,
block size, eigensolver precision and tolerance, restart limit, polynomial bounds and
degree, vector I/O, `preserve_deflation`, `preserve_evals`, and `tol_restart` to the base
CG controls.

Keep these invariants explicit:

- the eigensolver search space must satisfy the native invariants documented in
  `eigensolver.md`;
- preserved space size must be at least the requested converged-vector count;
- preserved eigenvalue count must match the requested converged count;
- eigensolver-vector precision must match the operator used by `matEig`;
- `tol_restart = 0` disables repeated projection at reliable updates;
- mass shifting is not a general operator-update mechanism; and
- a resident-gauge invalidation does not clear the process-global MILC deflation cache.

## Memory model

Peak memory is the sum of ordinary CG and eigensolver/deflation state:

- the precise and sloppy CG fields described in
  [`staggered-cg.md`](staggered-cg.md);
- `n_conv` retained parity eigenvectors at eigensolver precision and their eigenvalues;
- the larger eigensolver search basis governed by `n_kr` while setup is active;
- eigensolver rotation, Rayleigh-quotient, residual, and batching temporaries; and
- optionally both even- and odd-parity preserved spaces in the MILC interface.

The persistent floor after setup is dominated by retained eigenvectors; the peak during
setup can be materially larger because the search basis and temporary batches coexist.
Vector count, local parity volume, storage precision, field order, I/O staging, and
allocator pooling all matter. A retained count alone is not a byte-exact memory model.

Use [`staggered-memory.md`](staggered-memory.md) to price the source-derived retained-vector
payload and, when its evidence scope applies, the separately labelled Perlmutter A100
high-water fit. The fit does not include an arbitrary search-basis peak or a second
preserved parity space. Measure device high-water across eigensolver setup, first
projection, and a representative solve rather than sampling only steady-state CG.

## Runtime confirmation and correctness

For a fresh space, confirm that output shows an eigensolver construction and convergence
before CG. For reuse, look for messages such as `Restoring deflation space`,
`Preserving deflation space`, `Shifting eigenvalues`, or `Resetting eigenvalues`, as
applicable. From MILC `d17e9559` the application side adds `Loading deflation spaces into
QUDA` and `Time to load deflation space = ...` before the first solve, and one
`Solving for <n> source(s) with|without deflation for parity <p>` line per call.

Record:

1. parity, mass, `naik_epsilon`, links/operator identity, and source count;
2. eigensolver type, `n_conv`, `n_ev_deflate`, `n_ev`, `n_kr`, block size, precision,
   tolerance, restart limit, and polynomial settings;
3. whether vectors were computed, loaded, reconstructed from the other parity, or
   restored from the process cache;
4. `tol_restart`, number of reliable updates, and whether repeated deflation occurred;
5. setup time separately from projection/solve time; and
6. QUDA true residual, MILC convergence state, and an application-level solution check.

For multi-source calls, the MILC interface returns the last source's residual fields.
Inspect per-source QUDA summaries when diagnosing one member of a block.

## Limitations and version sensitivity

Through `6b9b8a06` the MILC call site deflated only the even-parity CG call; from `d17e9559`
it deflates every parity the propagator asks for. Its `QudaEigensolverArgs_t` size is checked
across the interface, so a QUDA/MILC header mismatch fails deliberately rather than remaining
ABI-compatible by accident.

Parity reconstruction, mass-shift caching, cleanup, and the repeated-deflation trigger
are exact-current behaviors. Re-audit them when either repository changes. This page
does not publish a universal eigenvector count, polynomial window, crossover solve
count, timing rank, or fitted memory constant.
