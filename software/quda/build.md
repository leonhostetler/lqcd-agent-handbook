---
title: Building QUDA
summary: Software-specific configure, build, and validation procedure for a selected QUDA profile.
scope: [software:quda]
load_when: Configuring, compiling, installing, or validating QUDA.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/README.md
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
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
