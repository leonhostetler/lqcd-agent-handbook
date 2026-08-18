---
title: Developing QUDA
summary: Software-specific rules for modifying QUDA and preparing changes for review.
scope: [software:quda]
load_when: Modifying QUDA source, adding tests, or preparing a QUDA change for review.
evidence: source
sources:
  - https://github.com/lattice/quda/wiki/
  - https://github.com/lattice/quda/wiki/Coding-Conventions-and-Style
  - https://github.com/lattice/quda/wiki/Updating-the-QUDA-Interface
  - https://github.com/lattice/quda/wiki/Adding-new-QUDA-features
  - https://github.com/lattice/quda/wiki/Checking-that-new-QUDA-features-preserve-Dslash-behavior
  - https://github.com/lattice/quda/wiki/Validating-Large-Multigrid-Changes
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/.clang-format
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/CMakeLists.txt
  - https://github.com/lattice/quda/tree/b6998853f6b605e22d67ea2ddfa3cab0d752679a/.github/workflows
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/ci/pipeline.yml
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/enum_quda_fortran.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/quda_fortran.F90
observed: "2026-08-18"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
---

# Developing QUDA

These conventions apply whenever QUDA source is modified or a QUDA change is prepared for
review, independently of work mode. Working-project instructions and explicit operator
direction remain in force. `project.yaml` is canonical for QUDA's default branch; the
operator-selected checkout and pull-request target are session state.

## Prepare a reviewable diff

For changes intended for upstream review, prepare a diff suitable for a pull request. The
Git-authorization safeguard in canonical `AGENTS.md` remains in force: preparing the change
does not authorize committing it, pushing it, or opening or updating the pull request.
Before formatting or final validation, compare the complete change against the current
intended target. Keep the diff limited to the requested change; leave unrelated refactoring
and repository-wide formatting out of it.

## Format only changed lines

Before a pull request is opened or updated, always clang-format the changed C, C++, and
CUDA lines using the repository-root `.clang-format`.

- Apply formatting to the diff relative to the intended target, not to every line of each
  touched file. When using a diff-formatting helper, ensure its file selection includes
  `.cu` and `.cuh`.
- Exclude vendored and generated sources unless they are the intended subject of the change.
- Reinspect the resulting diff. Do not treat a formatter version or helper recipe quoted by
  the wiki as a durable pin; it must be compatible with the checked-out style file and
  current project instructions.

## Match validation to the impact

QUDA pull-request automation does not establish full runtime correctness. At the observed
commit, the GitHub Actions pull-request workflows build and install but do not run tests;
the separate CSCS pipeline runs `ctest`. Run focused validation before relying on CI.

- Add or update a focused regression test when the changed behavior can be expressed by the
  current test harness, then run the relevant CTest registration or narrow test executable.
- Select the dimensions the change can affect, such as build configuration, operator,
  precision, and single- versus multi-GPU execution. Do not mistake a matrix of requested
  values for coverage without checking that the harness reaches the changed path.
- When Dslash behavior is in scope, cover the applicable operator families, precisions, and
  partitionings using the current tests rather than copying the wiki's historical shell loops.
- For large multigrid changes, define an impact-specific test matrix; the wiki's exhaustive
  examples are guidance, not a minimum for every change.
- Record the build configuration, commands, results, and untested scope in the review or
  handoff.

## Preserve interface and build contracts

- Treat public enumeration ordering and values as interface-sensitive. When
  `include/enum_quda.h` changes, update the hand-maintained
  `include/enum_quda_fortran.h` mirror in the same change.
- When `include/quda.h` changes, audit and update the applicable Fortran declarations,
  module structures, and stubs in `include/quda_fortran.h`, `lib/quda_fortran.F90`, and
  `lib/interface_quda.cpp`.
- If significant new functionality materially increases compile time or library size, make
  it configurable through the current CMake option and compile-guard patterns. A disabled
  build should report a clear error if that functionality is invoked; do not reuse the
  wiki's removed Autoconf recipe.

## Treat the wiki as a lead, not command authority

The [QUDA Development section](https://github.com/lattice/quda/wiki#quda-development)
provides useful mechanism-specific context and deeper recipes. Its pages were updated at
different times, and some still describe historical build systems, formatter versions,
branch practices, CI controls, or test commands. Reconcile those details with the selected
checkout and current upstream before acting, and preserve the durable intent rather than
historical command text.
