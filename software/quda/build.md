---
title: Building QUDA
summary: Software-specific configure, build, and validation procedure for a selected QUDA profile.
scope: [software:quda]
load_when: Configuring, compiling, installing, or validating QUDA.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/README.md
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt#L527-L530
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/CMakeLists.txt#L22
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/staggered_invert_test.cpp#L574-L577
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/staggered_dslash_test.cpp#L119
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/staggered_invert_test_gtest.hpp#L30
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_improved_staggered.cpp#L23
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/CMakeLists.txt#L295-L296
observed: "2026-08-20"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
---

# Building QUDA

Follow `playbooks/build-lqcd-stack.md` for the shared workflow. This page supplies the QUDA
half; the selected machine profile and stack own modules, accelerator architecture,
parallelism limits, and scheduler placement.

## Configure out of source

Resolve the selected entry in `build-profiles.yaml`, then combine its options with the
machine-specific values in the nearest stack. Use a fresh out-of-source configuration when
establishing a build:

```bash
source_dir=${QUDA_SOURCE_DIR:?set QUDA_SOURCE_DIR}
build_dir=${QUDA_BUILD_DIR:?set QUDA_BUILD_DIR}
install_dir="$build_dir/usqcd"

cmake --fresh -S "$source_dir" -B "$build_dir" \
  -DCMAKE_BUILD_TYPE=RELEASE \
  -DCMAKE_INSTALL_PREFIX="$install_dir" \
  -DQUDA_TARGET_TYPE=<target> \
  -DQUDA_GPU_ARCH=<accelerator-architecture> \
  <profile options> \
  <machine-specific options>
```

Do not infer the accelerator architecture from a login node. Resolve it from the declared
compute-node type. When using QMP, leave `QUDA_MPI=OFF`; QUDA warns that enabling both may
produce undefined behavior. Enabling QIO requires QMP.

Build and install through CMake, respecting the machine's build-placement and parallelism
limits:

```bash
cmake --build "$build_dir" --target install --parallel <jobs>
```

## Build and install the complete test suite

Keep QUDA's upstream all-tests defaults enabled in every profile unless the operator explicitly
requests a reduced test build:

```bash
-DQUDA_BUILD_ALL_TESTS=ON
-DQUDA_INSTALL_ALL_TESTS=ON
```

With those options, the install build above compiles and installs all tests enabled by the
configured features. A focused runtime validation may execute only the subset required by the
profile's validation contract; it must not narrow what is compiled.

Pin the install library directory with `-DCMAKE_INSTALL_LIBDIR=lib`. QUDA installs its own
libraries to a literal `lib` and sets the installed run path to `${CMAKE_INSTALL_PREFIX}/lib`,
but installs the test support library `libquda_test.so` to `${CMAKE_INSTALL_LIBDIR}`. Where
CMake's `GNUInstallDirs` resolves that to `lib64` — observed on Vista, see
[`quda-cuda12-milc-cg-2026q3`](../../machines/vista/stacks/quda-cuda12-milc-cg-2026q3/notes.md) — every
installed test fails at start-up with `libquda_test.so: cannot open shared object file`, while
the build-tree tests in `<build>/tests` still run. Adding the option to an existing build and
reinstalling is enough; it does not require a fresh configure.

For `milc-cg`, retain `QUDA_INTERFACE_QDP=ON`: the native staggered dslash and inverter
tests construct QDP-ordered host gauge fields even though the intended consumer interface
is MILC. Disabling QDP can produce `QDP interface has not been built` before numerical
verification begins.

## Validate the selected stack

Run on the declared compute-node type and capture accelerator telemetry before accepting
the result. Use a writable, node-type-specific `QUDA_RESOURCE_PATH`; a first run populates
the tunecache and is validation, not a benchmark. Before reusing a tunecache across a source,
build, or runtime change, apply the benchmark-scoped compatibility test in
[`internals/autotuning.md`](internals/autotuning.md). QUDA's Git mismatch is a conservative screen,
not proof that retuning is necessary. Bypass it only when every tuning problem exercised by the
measured workload is demonstrably unchanged; otherwise populate a fresh cache before measurement.

For a multi-GPU run, exercise at least one staggered dslash comparison, one CG solve with a
checked host residual, and QIO write/read tests when QIO is part of the profile. Building
the MILC interface and passing QUDA-native tests does not establish that a MILC executable
links and runs; record that as a validation-scope limit until it is tested separately.

### A test that exits 0 has not necessarily been scored

QUDA's test executables differ in how they reach their gtest suite, and the two ways of getting
it wrong both exit 0. Judge a test by its gtest verdict lines, never by its exit status. At
`00c7ef3`:

- **`staggered_invert_test` runs gtest only with `--enable-testing true`** `[source]`. Without it
  a `--gtest_filter` is ignored and the executable does one plain, unscored run with default
  settings. For CG that means stopping at the default 100 iterations far from any tolerance,
  with no failure reported.
- **Its double-sloppy cases are skipped unless `--prec double`** `[source]`. The skip test rejects
  an outer precision below the sloppy precision, and the default outer precision is single, so a
  filter such as `cg_mat_pc_direct_pc_double_l2` reports `[ SKIPPED ]` and `PASSED 0 tests`.
- **`staggered_dslash_test` always runs its gtest suite and rejects `--enable-testing`** as an
  unexpected argument `[source]`. `io_test` ran its suite with or without the flag `[observed]`.
- **gtest colours its output**, so a verdict line begins with an escape sequence. Strip the
  escape codes before matching `[       OK ]`, and count `[  SKIPPED ]` separately so a skip can
  never read as a pass.
- **Improved staggered needs every partitioned dimension to have a local extent of at least 6**
  `[source]`, and aborts at the first dslash otherwise. Choose the local volume and rank grid of
  a multi-GPU leg together.

### ctest runs each case through an absolute launcher fixed at configure

QUDA builds its ctest launch line from CMake's MPI launcher, as the cache string
`QUDA_CTEST_LAUNCH` `[source]`. CMake's MPI discovery stores that launcher as an absolute path, so
every registered case is recorded as, for example, `"/usr/bin/srun" "-n" "1" <test> <args>`
`[observed]`. Two things follow. A `PATH` stub never sees it: running `ctest` under the dry-run
harness calls the real launcher on the login node. And the launch line is fixed when the build is
configured, so no binding, accelerator, or step time-limit option in the batch script reaches the
cases. To run registered cases from a batch script, export them with
`ctest --test-dir <build> --show-only=json-v1`. Strip the recorded launcher from each case's
`command`, run it in its `WORKING_DIRECTORY` property, skip any case whose `DISABLED` property is
set, and launch each one with the script's own launcher line. Refuse an export whose launcher
differs from the one you expect to strip. Overriding `QUDA_CTEST_LAUNCH` at configure with a bare
launcher name is untested here.
