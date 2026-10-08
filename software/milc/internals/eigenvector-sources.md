---
title: MILC eigensolver and eigenvector-source selection across QUDA, Grid and CPU builds
summary: Which eigensolver, eigen-parameter grammar, owner of the eigenvectors and readable file formats each combination of HAVE_QUDA, HAVE_GRID, USE_EIG_GPU, USE_CG_GPU and HAVE_QIO selects, including how a Grid eigenpack reaches QUDA deflation.
scope: [software:milc]
load_when: Choosing MILC build switches for an eigensolve or a deflated solve; loading eigenvectors computed elsewhere, such as a Grid eigenpack, into a MILC or QUDA solve; or combining WANTGRID with WANTQUDA.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/include/imp_ferm_links.h#L313-L394
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/read_eigen_param.c#L11-L71
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L278-L318
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/control.c#L301-L362
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/eigen_stuff_QUDA.c#L148-L227
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/io_helpers_ks_eigen.c#L193-L283
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/milc_to_quda_utilities.c#L103-L172
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/eigen_stuff_helpers.c#L577-L625
  - operator's screened DeltaAI run records for the Grid eigenpack route
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Make_template_combos#L171-L198
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Make_template_combos#L330-L340
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile#L771-L787
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/vector_io.cpp#L40-L75
observed: "2026-10-08"
observed_on:
  machine: deltaai
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
---

# MILC eigensolver and eigenvector-source selection across QUDA, Grid and CPU builds

`USE_EIG_GPU` does not mean "eigenvectors on the GPU". It decides **who owns the
eigenvectors** in an accelerated build: the accelerated back end computes or reads them itself,
or MILC holds them on the host and hands them over. Together with the back-end switches it also
selects the eigensolver, the input grammar and which eigenvector files a run can read, and those
choices are made at compile time by one precedence chain. A run's input cannot override any of
them.

## The switches

`WANTQUDA=true` defines `HAVE_QUDA`; `WANTGRID=true`, which `WANTHADRONS=true` also sets, defines
`HAVE_GRID`. The Makefile does not prevent setting both. The `WANT_*_GPU` switches are shared by
the two back ends, so `WANT_EIG_GPU` and `WANT_FN_CG_GPU` produce the same `USE_EIG_GPU` and
`USE_CG_GPU` defines whichever back end is selected. What each switch means is canonical in
[`../project.yaml`](../project.yaml); this leaf records what their combinations select.

## One precedence chain selects the eigensolver and its parameters

`include/imp_ferm_links.h` defines `ks_eigen_param` and binds `ks_eigensolve` in one
`#if`/`#elif` chain, and `read_eigen_param.c` reads the input in a parallel chain. The first
matching row wins:

| Order | Condition | `ks_eigensolve` | Eigen parameters carry `eigPrec`, `blockSize`, `Nkr`, `batchedRotate` |
|---|---|---|---|
| 1 | `HAVE_PRIMME` | PRIMME, CPU | no |
| 2 | `HAVE_ARPACK` | ARPACK, CPU | no |
| 3 | `HAVE_GRID` and `USE_EIG_GPU` | Grid | no; it carries `Nmax`, `reorth_period`, `diagAlg` |
| 4 | `HAVE_QUDA` and `USE_EIG_GPU` | QUDA | **yes** |
| 5 | `HAVE_QDP` | Kalkreuter, QDP | no |
| 6 | otherwise | Kalkreuter-Ritz, CPU | no |

`read_eigen_param.c` adds one case between rows 3 and 4: `HAVE_QUDA` with `USE_CG_GPU` and without
`USE_EIG_GPU` stops with "only the QUDA eigensolver is allowed". `ks_spectrum` reads eigensolver
parameters only for a fresh eigensolve, so that stop fires only on fresh eigenvectors; a reload is
not affected.

Two consequences follow from the chain alone:

- **A QUDA-side reader of the eigensolver-only fields compiles only under row 4.** Such reads
  must be guarded on `USE_EIG_GPU` — and even that guard is insufficient whenever a row above 4
  also matches, since `USE_EIG_GPU` is then defined while the struct lacks the fields.
- **`WANTGRID` plus `WANTQUDA` plus `WANT_EIG_GPU` selects row 3**, Grid's struct and Grid's
  eigensolver, while `eigen_stuff_QUDA.c` and `milc_to_quda_utilities.c` still compile under
  `USE_EIG_GPU` and read the row-4 fields. That build is expected not to compile `[inferred]`, from
  the chain and those readers; it was not built. Adding PRIMME or ARPACK to a QUDA build with
  `WANT_EIG_GPU` is expected to fail the same way. So "Grid computes the eigenvectors and QUDA
  deflates" is not one binary.

When both back ends are enabled with `WANT_FN_CG_GPU`, `Make_template_combos` links QUDA's CG,
not Grid's.

## Who owns the eigenvectors in a QUDA CG build

| | `USE_EIG_GPU` defined | `USE_EIG_GPU` undefined |
|---|---|---|
| Fresh eigenvectors | QUDA's eigensolver computes them on the device (`QUDA_MILC_EIG_COMPUTE`) | refused, see above |
| Eigenvectors from a file | QUDA reads its own file through `vec_infile`, assuming even parity | MILC reads the file into host `eigVec` with `reload_ks_eigen`, rebuilds the other parity and checks residuals on the host, then copies the file's parity to QUDA (`QUDA_MILC_EIG_LOAD`) |
| Precision of the resident deflation space | the input's `eigensolver_prec` | MILC's build precision, which `QUDA_MILC_EIG_LOAD` requires |
| Input, on reload | also asks `file_number_of_eigenpairs` and `eigensolver_prec` | no extra field |

The ownership rules once the space is resident, including on-demand reconstruction of the other
parity, are in
[`../../quda/internals/milc-deflation-space.md`](../../quda/internals/milc-deflation-space.md).

## Which files a run can read

**QUDA's own reader is QIO only.** `vec_infile` goes through QIO's spinor-field reader, so a build
with `USE_EIG_GPU` defined reads SciDAC eigenvector files and nothing else.

**MILC's reader also reads Grid eigenpacks, without Grid.** In any QIO build `reload_ks_eigen`
treats a `reload_serial_ks_eigen` or `reload_parallel_ks_eigen` argument that is a **directory**
as a Grid multi-file eigenpack: it reads `<dir>/v<i>.bin` for each requested vector and sets the
eigenvector parity to **odd**, the Grid convention. A regular file is read as a MILC SciDAC file and
taken as even parity. The reader, `io_grid_ks_eigen.o`, is linked whenever QIO is and needs no
Grid library. Grid's single-file eigenpack format is not supported. Without QIO only MILC's ASCII
and serial formats can be read.

## Loading a Grid eigenpack into QUDA deflation

The only route is MILC-owned eigenvectors: a QUDA CG build with QIO and **without**
`WANT_EIG_GPU` — `WANTQUDA=true WANT_FN_CG_GPU=true WANTQMP=true WANTQIO=true`, with neither
`WANTGRID` nor a CPU eigensolver needed — and the eigenpack directory given to a
`reload_*_ks_eigen` keyword. MILC reads the odd-parity vectors, and QUDA receives them through
`QUDA_MILC_EIG_LOAD` and reconstructs the even parity when an even-parity solve needs it.

**At `a5f8f9fa` this build does not compile**, because `load_quda_default_eig_args` reads the
row-4 fields unguarded; the observation is recorded in [`../project.yaml`](../project.yaml) under
`WANT_FN_CG_GPU`. The route therefore needs those reads guarded on `USE_EIG_GPU`.

**With the guard the route works** `[observed]`, once, on DeltaAI: one rank, one GH200, a
`ks-spectrum-hisq-quda` build with `WANT_EIG_GPU=false` from `a5f8f9fa` plus that guard and no other
change to the eigenvector path, against QUDA `ba501e4f8`. A 500-vector Grid eigenpack for one gauge
configuration of a public 16³×48 HISQ ensemble was read from its directory and loaded into QUDA, and
a two-mass UML solve on both parities was run deflated and undeflated:

- MILC's host check of the file's own parity, the odd one, and QUDA's Rayleigh quotients at load
  agreed with the stored eigenvalues, so the Grid vectors are eigenvectors of MILC's operator with
  no normalization or convention change.
- **The host check of the reconstructed even parity reports the lowest modes badly**, its residual
  and Rayleigh quotient far from the stored eigenvalue. That is the reconstruction, not the file:
  `construct_eigen_other_parity` applies the Dslash and normalizes by the result's norm, which is
  √λ for an exact eigenvector, so the stored parity's residual enters the rebuilt one divided by
  √λ and is amplified most for the smallest eigenvalues. Judge a reloaded eigenpack by the parity
  it was stored in.
- Every deflated solve converged below the requested true residual in several-fold fewer
  iterations than the undeflated one, the even-parity solves included, so QUDA's on-demand
  reconstruction of the other parity worked from the loaded odd space.
- The pion correlators of the two legs agreed to the precision of the solves.

Reading the eigenpack is serial, one file per vector, and dominated the run's wall time.

## What this does not cover

- How Grid's own CG uses a Grid-computed eigenspace (row 3 with Grid's CG) was not traced.
- Whether a SciDAC eigenvector file written by MILC is readable through QUDA's `vec_infile`, which
  would offer a route that keeps `USE_EIG_GPU`, was not checked.
- Only `ks_spectrum`'s setup and control flow were read; other applications that reload
  eigenvectors may gate their input differently.
- The Grid route ran on one rank only; reading an eigenpack across several ranks, and
  `reload_parallel_ks_eigen`, were not exercised.
