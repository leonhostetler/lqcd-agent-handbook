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
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/blas_quda.cu
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/copy_color_spinor_mg.in.hpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/tests/CMakeLists.txt
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/include/enum_quda_fortran.h
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/quda_fortran.F90
  - https://github.com/llvm/llvm-project/blob/main/clang/tools/clang-format/git-clang-format
observed: "2026-08-19"
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

Use `$LQCD_HANDBOOK/tools/clang-format-quda.py`. It requires `clang-format` and
`git-clang-format` on `PATH`, uses the repository-root `.clang-format`, includes CUDA
extensions, and excludes `tests/googletest/` and `lib/generate/`. It checks for its
dependencies and never installs, fetches, stages, commits, pushes, or opens a pull request.

After every hands-on QUDA source edit, format only the explicit repository-relative files
changed by the current task before final validation and handoff:

```bash
"$LQCD_HANDBOOK/tools/clang-format-quda.py" \
  --scope worktree --apply -- <changed-file>...
"$LQCD_HANDBOOK/tools/clang-format-quda.py" \
  --scope worktree -- <changed-file>...
```

Worktree scope compares the selected tracked files with `HEAD`; explicitly named untracked
source files are formatted in full. Pass literal file paths, not directories or globs. If a
selected file was already dirty before the task, run check mode first and do not apply
formatting to hunks the task does not own. Check mode is the default: exit 0 means clean,
1 means formatting changes are required, and 2 means the tool failed.

When the operator says **“please clang-format”** without a narrower scope, treat it as an
explicit request to apply formatting to the full QUDA branch diff. Refresh or otherwise
verify the intended pull-request target ref separately—the tool never fetches—then run:

```bash
"$LQCD_HANDBOOK/tools/clang-format-quda.py" \
  --scope branch --base <target-ref> --apply
"$LQCD_HANDBOOK/tools/clang-format-quda.py" \
  --scope branch --base <target-ref>
```

Branch scope computes the merge base with the named target and includes committed, staged,
and unstaged changed lines. It excludes untracked files unless they are explicitly named
after `--`. Reinspect the resulting `git diff`. Do not treat a formatter version or helper
recipe quoted by the wiki as a durable pin; it must be compatible with the checked-out
style file and current project instructions.

## Match validation to the impact

QUDA pull-request automation does not establish full runtime correctness. At the observed
commit, the GitHub Actions pull-request workflows build and install but do not run tests;
the separate CSCS pipeline runs `ctest`. Run focused validation before relying on CI.

When a correctness repair is prerequisite to an optimization, establish and validate the narrow
repair first. Preserve its output as the optimization baseline, then change placement or
dataflow. Otherwise the original defect contaminates the oracle and a result change cannot be
attributed cleanly.

For accelerator refactors, keep a precision ledger for host storage, device storage, operators,
intermediates, accumulators, reductions, and outputs. Algebraically equivalent placement may
change working precision and reduction order. For template-dispatched operations, also trace
the relevant field tuple, such as color, spin, order, location, and precision, through dispatch
and the generated instantiation lists; an exposed API can compile yet reject an unsupported
combination at runtime. Validate every affected precision and representation path.

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

- Enforce public-input, preserved-state, vector-cardinality, and similar runtime contracts with
  always-on `errorQuda` paths. Use `assert` only for internal conditions whose checks may safely
  disappear from release builds.
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
