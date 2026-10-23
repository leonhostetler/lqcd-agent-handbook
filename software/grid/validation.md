---
title: Validating a Grid GPU build for staggered and HadronsMILC work
summary: Which Grid test programs check a non-unified GPU build for staggered work, how to read them, the failures that are test defects rather than build defects, and how to prove a header override took effect.
scope: [software:grid, fermion:staggered]
load_when: Choosing or reading the first-run checks of a new Grid build, or judging a failed Grid test on a GPU build.
evidence: source
sources:
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/tests/core/Test_staggered.cc
  - https://github.com/milc-qcd/Grid/tree/d67dd2079bea125138502a13120858aa58997379/tests/solver
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/tests/Test_general_stencil.cc#L100-L152
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/GridMilc/tests/Test_a2a_stencil.cc#L148-L235
  - https://github.com/milc-qcd/Grid/commit/dee6224b7
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/lattice/Lattice_ET.h#L248
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/cshift/Cshift_mpi.h#L306-L328
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/benchmarks/Benchmark_comms.cc#L256-L312
  - https://github.com/paboyle/Grid/tree/3232b438f2cf729e515c185e2dbf29d7cc276bb7/tests
observed: "2026-10-23"
observed_on:
  software:
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {cuda: "13.3", openmpi: "5.0.11"}
---

# Validating a Grid GPU build

Labels: **[U+F]** upstream and fork; **[F]** fork-only. Lines at fork commit d67dd207. The
observations below come from one `--disable-unified` CUDA build (`cuda-hadrons-staggered`
profile) run on 1 and 4 GPUs of one node, unless stated otherwise.

## A first-run set, and how to read it

| Program | Checks | Pass looks like |
|---|---|---|
| `tests/core/Test_staggered` [U+F] | staggered hop against a Cshift reference, even-odd split, adjointness | `norm diff` and `EO norm diff` at round-off. **It has no assert**: read the numbers |
| `tests/solver/Test_staggered_cg_{prec,schur,unprec}`, `Test_staggered_multishift` [U+F] | Schur and full CG, multishift CG | `Converged on iteration …` with the true residual near the target |
| `tests/smearing/Test_fatLinks --gauge --fat --long` [F] | HISQ smearing against supplied links | `Grid_pass`; without `--fat/--long` it checks nothing (see `hisq-smearing.md`) |
| `GridMilc/tests/Test_staggamma_applyg5` [F] | spin-taste γ₅ application | passes |
| `GridMilc/tests/Test_a2a_stencil` [F] | A2A meson-field stencil against Cshift, all spin-taste gammas, checkerboarded and full | `=== Test_a2a_stencil complete ===` then `PASS` |
| `benchmarks/Benchmark_staggered{,F}`, `Benchmark_memory_bandwidth` [U+F] | throughput | compare across builds and decompositions |

Run the same tests on 1 rank and on several; iteration counts and norms should agree (they did,
±1 iteration, on 1 and 4 GPUs), because Grid's parallel random-number generator is seeded per
site and gives the same fields under any decomposition.

## Failures that are not build defects

- **`tests/Test_general_stencil` segfaults on a `--disable-unified` build** [U+F]: its host loop
  dereferences `GetEntry(0,i)->_offset`, and the stencil table lives in device memory
  (`Test_general_stencil.cc:109-113`). The test assumes managed memory; drop it from a
  non-unified build's checks. `GeneralLocalStencil` on the device is exercised by HISQ smearing
  instead.
- **`benchmarks/Benchmark_comms` crashes in its "threaded STENCIL halo exchange" section** [U+F]:
  it calls the communicator from eight threads at once, while Grid initialises MPI at
  `MPI_THREAD_SERIALIZED` (see `runtime-environment.md`). Read its sequential sections only, or
  build with `-DGRID_COMMS_THREADS`.
- **`GridMilc/tests/Test_a2a_stencil` cannot run with dimension 3 decomposed** [F test, U+F
  mechanism]: its reference grid puts all lanes in dimension 3, so with `--mpi 1.1.2.2` its first
  `Cshift` in that dimension asserts `simd_layout==2` (`Cshift_mpi.h:326`). Run it multi-rank on
  a layout that keeps dimension 3 whole (`2.2.1.1`, `1.2.2.1`). Reproduced in three runs.

## A fork fix that the HadronsMILC 0.3.0 pin lacks [F]

At d67dd207, `Test_a2a_stencil` passes its gather and full-grid checks and then aborts with
`GRID_ASSERT cb == lat.Checkerboard()` (`Lattice_ET.h:248`) at `CB BothHalf gamma G1_G1`. Fork
commit dee6224b7 (2026-10-11, one file, `GridMilc/spin/StagGamma.h`) fixes it: in
`StagGamma::applyCoeffsAndPhase`, the predicate built from `mod(stag_dirs, 2) == 0` defaulted
to the even checkerboard, so an odd-parity field tripped the conformance check. With only that
header replaced (first on the include path, same `libGrid.a`), the test passes on 1 GPU and on
4 GPUs (`2.2.1.1`, `1.2.2.1`); without it, the same build aborts at the same place. The header is
template-only — `libGridMilc.a` holds only a version string — so the override cannot conflict
with compiled code. Code that reaches `applyCoeffsAndPhase` with odd-parity fields aborts on the
unfixed pin rather than returning wrong numbers.

## Proving a header override took effect [U+F]

Grid includes its own headers with angle brackets, so a directory placed first on the include
path overrides a header for every includer. Prove it from the compiler's dependency records:
automake's `.deps/*.Po` files (depmode `gcc3`) list every header by absolute path. Count the
objects that name the override copy and confirm none names the installed copy; `nvcc -M` gives
the same list for a single source. To rebuild one test with make's exact flags, take
`DEFS`, `DEFAULT_INCLUDES`, `AM_CXXFLAGS`, `CXXFLAGS`, `LDFLAGS` and `LIBS` from that
directory's generated `Makefile` and call the compiler directly; never discover the command
with `make -n` (see `build.md`).
