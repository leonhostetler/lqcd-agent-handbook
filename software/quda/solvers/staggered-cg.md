---
title: QUDA staggered CG through MILC
summary: Operator contract, recurrence, precision behavior, memory objects, suitability, and runtime checks for MILC's QUDA staggered CG path.
scope: [software:quda, software:milc, solver:cg, fermion:staggered]
load_when: Selecting, configuring, sizing, debugging, or validating non-deflated QUDA CG for a MILC staggered solve.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/invert_quda.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solver.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solve.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/inv_cg_quda.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/dirac_staggered.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/dirac_improved_staggered.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/CMakeLists.txt
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn_quda.c
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

# QUDA staggered CG through MILC

This page covers the native `QUDA_CG_INVERTER` reached through MILC's staggered
QUDA interface when no deflation space is attached. It describes the backend solve,
not the higher-level distinctions among MILC's `CG`, `CGZ`, and `UML` algorithms.
Those algorithms prepare different right-hand sides and parity sequences before
calling a parity solver; see
[`../../milc/internals/staggered-inverter-types.md`](../../milc/internals/staggered-inverter-types.md).

## Operator and solve contract

For the observed MILC interface, `setInvertParams` selects:

- `QUDA_CG_INVERTER`;
- `QUDA_MATPC_SOLUTION`;
- `QUDA_DIRECT_PC_SOLVE`;
- the even-even or odd-odd preconditioned operator selected by the MILC parity;
- `QUDA_ASQTAD_DSLASH` when long links are present, otherwise
  `QUDA_STAGGERED_DSLASH`; and
- mass normalization and a caller-supplied initial guess.

The parity-preconditioned staggered `M` implemented by QUDA is the Hermitian
normal-equation operator

```text
A_p(m) = 4 m^2 - D_pq D_qp,
```

on the selected parity. `DiracStaggeredPC::MdagM` and its improved-staggered
counterpart are deliberately undefined because `M` already represents the normal
operator. QUDA's solver factory rejects CG if the matrix reports that it is
non-Hermitian.

Do not transfer this contract to the staggered-MG path. The current MILC MG wrapper
solves the full, unpreconditioned Dirac system with outer GCR.

## How the iteration works

After preparing the parity field, CG:

1. computes `r = b - A x0` when initial-guess use is enabled, otherwise starts from
   `r = b` and a zero solution accumulator;
2. applies the sloppy-precision matrix once per Krylov iteration;
3. updates the solution, residual, and search direction with fused BLAS operations
   and global reductions; and
4. periodically performs a reliable update in the precise operator, recomputing
   `r = b - A x` and restarting the low-precision recurrence from that residual.

The solver can pipeline reductions and can accumulate several direction updates
before touching the precise solution, but the observed CG implementation hard-codes
precise rather than sloppy partial-solution accumulation. Increasing
`solution_accumulator_pipeline` can allocate additional sloppy direction fields and
is not a free tuning knob.

MILC passes `qic->max * qic->nrestart` as QUDA's `maxiter`. That is an iteration cap;
the source warns that QUDA's restart criterion is not MILC's restart criterion, so do
not interpret the product as a count of MILC-style restarts.

## Setup and reusable state

Plain CG has no eigensolver or multigrid setup. It still depends on QUDA's resident
gauge fields and on the operator identity represented by the fat and long links,
mass, parity, boundary phases, precision, and action parameters.

The solver object owns its Krylov workspace and is destroyed after the inversion.
Gauge residency can survive that solver object, subject to the MILC interface's
link-change notification and QUDA gauge-cache checks. A reused initial solution is a
caller concern; it is not a persistent CG search space.

## Build and stack requirements

The QUDA library must include the MILC interface and staggered Dirac operators:

```text
QUDA_INTERFACE_MILC=ON
QUDA_DIRAC_STAGGERED=ON
```

MILC must link QUDA and compile the improved-staggered CG backend, corresponding to
`HAVE_QUDA` and `USE_CG_GPU` in the observed source. The current MILC CMake and Makefile
logic also enables `USE_EIG_GPU` whenever `WANT_FN_CG_GPU` is enabled. That compile-time
coupling does not turn every solve into a deflated solve: runtime deflation is inactive
when `n_ev_deflate` is zero and QUDA receives no `eig_param`.

Build-option presence proves only that the path was compiled. A machine stack should
also validate one representative staggered solve at each precision and communication
mode that will be used.

## When to use it

Use this path when all of the following are true:

- the requested backend system is the Hermitian parity-preconditioned staggered
  normal equation;
- a lightweight solve with no low-mode or hierarchy setup is desired;
- the resident gauge and requested parity are valid for the current source; and
- a validated QUDA/MILC stack exposes the required precision and communication mode.

Plain CG is the source-level baseline for measuring whether the setup and persistent
memory of deflation or multigrid are justified. Source structure alone does not supply
that crossover; record the expected solve count and benchmark the executed path.

## When not to use it

Do not use this path:

- as a direct CG solve of the full staggered Dirac matrix—the full operator is not the
  Hermitian parity operator required by native CG;
- when the application requires a full-system MG-preconditioned solve rather than a
  parity normal equation;
- when the requested residual, precision, or operator combination has not been
  validated on the selected stack; or
- solely because an input file says `CG`: MILC set dispatch, initial-propagator rules,
  and multimass dispatch can select a different executed path.

If low modes dominate repeated solves, plain CG may remain correct but cease to be the
best amortized choice. That is a benchmark decision, not a universal source fact.

## Tunables and hard invariants

The primary solve controls are the L2 and optional heavy-quark tolerances, precise and
sloppy precision, reliable-update threshold, iteration cap, pipeline setting, and
initial-guess policy.

Keep these invariants explicit:

- CG requires a matrix that reports Hermitian.
- A zero-norm source is handled as a trivial solution by the MILC parity wrapper before
  the QUDA call.
- When advanced features are disabled for preconditioning, QUDA disables reliable
  updates and pipelining and forces a zero initial guess.
- The separate heavy-quark CG path does not support CG as a preconditioner and disables
  some advanced features. Deflation is an error on that path.
- Convergence of the iterated residual is not a substitute for the post-solve true
  residual when `compute_true_res` is enabled.

## Memory model

For each active right-hand side, the observed CG implementation owns:

- precise residual and solution-accumulator fields (`r` and `y`);
- sloppy search-direction and matrix-image fields (`p` and `Ap`);
- a separate sloppy residual when precise and sloppy precision differ; and
- any extra direction fields required by the solution-accumulator pipeline.

The working set scales approximately linearly with local parity volume and active
right-hand-side count. It sits on top of resident precise/sloppy gauge fields and QUDA
runtime allocations. There is no persistent eigenvector or coarse-grid hierarchy in
plain CG.

This inventory is the stable source contract, not a byte-exact capacity estimator.
Allocator pools, halo buffers, field order, gauge reconstruction, communication backend,
and concurrent right-hand sides affect the observed high-water mark. Use the shared
staggered memory page and calculator when those are admitted to the handbook.

## Runtime confirmation and correctness

Confirm the executed path from output and returned state:

1. At verbose logging, look for `Creating a CG solver` and `CG` iteration/summary lines.
2. In MILC timing output, identify the relevant `fn_QUDA` parity or block call; do not
   confuse it with `fn_QUDA_MG`.
3. Record selected parity, mass, Dslash type, source count, precise/sloppy precision,
   tolerance, iteration cap, and whether the initial guess was nonzero.
4. Check `num_iters`, the returned true residual, MILC's convergence flag, and an
   application-level residual or solution comparison appropriate to the workflow.
5. Treat a maximum-iteration warning, non-finite residual, or disagreement between
   iterated and true residual as a failed validation even if a timing was printed.

For multi-source calls, the observed MILC interface reports the last source's true
residual fields and uses QUDA's block-solver iteration convention. Record source count
and batching before comparing that number with sequential solves.

## Limitations and version sensitivity

This page is exact for the observed QUDA and MILC revisions. In particular, it relies on
the current MILC parameter mapping, the parity-preconditioned staggered `M` convention,
and the current CG workspace/reliable-update implementation. Recheck these files when
upgrading either repository.

This source-backed page intentionally gives no universal timing rank against deflated CG
or multigrid and no fitted memory constant.
