---
title: Developing QUDA
summary: Software-specific rules for modifying QUDA and preparing changes for review.
scope: [software:quda]
load_when: Modifying QUDA source, adding tests, or preparing or reviewing a QUDA change.
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
  - https://github.com/lattice/quda/commit/1757c406e32c5b8aa97a7e38a13627654d651bd8
  - https://github.com/lattice/quda/commit/79af44a6fe6d258de260c1dc0293af524f1c4d7b
  - https://github.com/lattice/quda/pull/1644
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/gauge_backup.h
  - https://github.com/lattice/quda/commit/321f728fb59bbf963814dc5f6941312b26b56310
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/CMakeLists.txt#L7-L11
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/gauge_field.h#L479-L488
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/utils/host_utils.cpp#L1100-L1113
  - https://github.com/lattice/quda/commit/13eb7e1d901604e87d4c3a3d6249e97ce0d3885f
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/host_reference/hisq_force_reference.cpp#L18-L41
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/utils/index_utils.cpp#L56-L72
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/hisq_paths_force_test.cpp#L330-L382
  - https://github.com/lattice/quda/pull/1662
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/utils/command_line_params.cpp#L1000-L1004
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/include/communicator_quda.h#L438-L466
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/include/communicator_quda.h#L596-L613
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/include/communicator_quda.h#L638-L660
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/lib/color_spinor_pack.in.cu#L92-L93
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/lib/hisq_paths_force_quda.cu#L51
  - https://github.com/lattice/quda/blob/2e7dd81894bb75101c86ee63520349fdab03fa74/lib/dslash_policy.hpp#L2039
  - operator's screened prior QUDA development records
  - https://github.com/llvm/llvm-project/blob/main/clang/tools/clang-format/git-clang-format
observed: "2026-10-07"
observed_on:
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
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

A comment, message, or test may cite durable public sources, but never working-directory notes,
local paths, or the handbook. [`conventions/code-changes.md`](../../conventions/code-changes.md)
owns the rule.

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

- Add or update a focused regression test in the repository that owns the changed behavior when
  it can be expressed by the current test harness, then run the relevant CTest registration or
  narrow test executable. An end-to-end consumer test does not replace repo-native coverage for
  a generic QUDA feature.
- Select the dimensions the change can affect, such as build configuration, operator,
  precision, and single- versus multi-GPU execution. Do not mistake a matrix of requested
  values for coverage without checking that the harness reaches the changed path. For a
  distributed change, include a non-degenerate partition in which the affected communication
  must occur and retain a marker or event count showing that it did.

  **QUDA's tunecache already holds that marker**, written by the run itself, provided each leg has
  its own fresh tunecache: a shared or reused one mixes runs. Two fields of the tuning keys carry
  it, read from `include/communicator_quda.h` at `develop` `2e7dd8189` `[source]`:

  - `topo=xyzt` is the rank grid, `comm_dim(d)` for each dimension, and a test's forced
    partitioning does not change it. Ghost-pack and multi-GPU dslash policy keys carry it, so any
    leg that exchanged a spinor halo has it. A leg asked for `--gridsize 1 1 2 2` that shows
    `topo=1122` ran on that grid; one that shows only `topo=1111` did not.
  - `comm=xyzt` is the set of partitioned dimensions and is on many more keys, the HISQ link and
    force kernels and the gauge kernels included. A bit is 1 when the rank grid splits that
    dimension **or** a test forces partitioning there (`comm_dim_partitioned`), so forcing only
    adds bits: the AND of a leg's `comm=` masks is a lower bound on what it really split, and a
    single-rank test that forces partitions shows `comm=0000` among its keys. The exception is
    `comm_dim_partitioned_string` called with an override, which can clear a split dimension's
    bit, so read the bound only from keys written without one.

  Require the intended split in `topo=` when the leg wrote any key carrying it, otherwise in the
  AND of its `comm=` masks, and record the masks beside the result. A leg missing an intended
  dimension did not exercise that dimension's communication, whatever `--gridsize` it was given.
  This complements an in-job placement probe and does not replace it: neither field records
  ranks per node. `[observed]` once, on one four-GPU node: `hisq_endtoend_test` at one rank
  showed `topo=1111` and, under `--all-partitions`, all sixteen `comm=` masks including `0000`;
  at `--gridsize 1 1 1 2` and `1 1 2 2` it showed `topo=1112` and `topo=1122`, with `comm=` ANDs
  of `0001` and `0011`. `tools/quda-tunecache-policies.py` reads the policy rows' separate
  `commDim` field and neither of these.

  **A distributed change has two peer kinds, and a run contains only the ones its placement
  created.** Peers on different nodes exchange large messages through a rendezvous handshake that
  completes before any payload moves; co-located peers exchange through the intra-node
  peer-to-peer path, which has no handshake and reads the send buffer immediately. That difference
  is tens of microseconds of slack, and it reliably hides a race against unretired device work. A
  device-side transport change passed a multi-node rig **three times, bit-identically, across three
  code paths, on code that was wrong**, because the rig ran one rank per node and every peer was
  therefore remote; at four ranks per node the same commit produced NaN on the first exchange. Note
  that the two obvious rungs have *opposite* blind spots — a single-node correctness harness never
  leaves the node, and a one-rank-per-node multi-node rig never stays on it — so the fault lived in
  the placement neither rung could create.

  Therefore **validate any change to a device-side communication path with at least two ranks
  sharing a node**, and record ranks-per-node beside every result, because a pass is evidence only
  for the peer kinds the run actually contained. For each rung of a validation ladder, write down
  what it *structurally cannot* create rather than only what it tests, and assert the placement
  from inside the job rather than trusting the request — see
  [`conventions/diagnostic-rigs.md`](../../conventions/diagnostic-rigs.md).
- When Dslash behavior is in scope, cover the applicable operator families, precisions, and
  partitionings using the current tests rather than copying the wiki's historical shell loops.
- For large multigrid changes, define an impact-specific test matrix; the wiki's exhaustive
  examples are guidance, not a minimum for every change.
- Record the build configuration, commands, results, and untested scope in the review or
  handoff.
- **Size host memory for an older test harness when a bisection runs it at production volume.**
  Before `321f728fb` (2026-08-28), QUDA's tests held one `std::mt19937_64` per local site for
  their host random numbers. That is 2504 bytes a site, outside QUDA's own host counters, so
  about 10 GB at four million local sites. `[observed]` once: the resident-set excess of an older
  build over a current one matched that figure to about a percent. A leg run on a pre-August-2026
  test at production local volume needs that headroom, or the scheduler's memory limit kills it
  before the observable is reached.

**Iteration counts are the right invariant for a transport or data-movement change.** Such a change
is not a numerical one, so counts must be bit-identical solve for solve against the unmodified path;
any drift means the operators being compared disagree, which is a defect rather than a tolerance
question. Pair it with an output comparison at printed precision and with a check that the timers
the change was meant to move are the only ones that moved — if a solver-internal count or maximum
shifts, the change leaked out of the layer it was scoped to.

## Know what QUDA's own tests cannot see

Three properties of QUDA's test harness make a check silent instead of failing it. Each is read
from `develop` at `00c7ef33d` and is unchanged at `e75ee8835` `[source]` unless tagged otherwise.

- **A RELEASE build compiles QUDA's tests with every warning suppressed.** `tests/CMakeLists.txt`
  gives the `quda_test` support library `$<IF:$<CONFIG:RELEASE>,-w,-Wall -Wextra>` as a `PUBLIC`
  compile option, so every test executable that links it inherits `-w`; the default `DEVEL` build
  type gets `-Wall -Wextra` instead. The recipe in [`build.md`](build.md) builds `RELEASE`, so a
  clean build log there says nothing about test code. To check a change's test code for warnings,
  recompile each test translation unit it touches with the build's own command, `-w` removed and
  `-Wall -Wextra -fsyntax-only` added — and first make one deliberate warning fire under that same
  command, because a check that cannot fire reads exactly like a clean one. The option belongs to
  the test library, so it is no evidence either way about warnings in `lib/`.
- **`GaugeField::raw_pointer()` returns the same array on every call for a pointer-array field.**
  For a per-dimension (QDP-style) order it fills a function-static `void *data_array[8]` and
  returns it (`include/gauge_field.h:479-488`), so the next call on *any* field overwrites what an
  earlier call returned. A function passed `a.raw_pointer()` and `b.raw_pointer()` as two
  arguments receives `b`'s pointers twice. That is why
  `compare_link(const GaugeField &, const GaugeField &)` (`tests/utils/host_utils.cpp:1100-1113`)
  has compared its second field with itself since `13eb7e1d9` (2023-05); its only caller,
  `hisq_paths_force_test`, ignores the result, so only its printed agreement table is vacuous,
  reporting zero differences down to 1e-16 between a host and a device computation `[observed]`
  once. A fix is proposed in lattice/quda#1662, unmerged at this writing. Where code needs two
  fields' per-dimension pointers at once, take them with `data<T>(d)`, or copy each returned array
  before the next call. Exact agreement between independently computed floating-point fields is
  itself the signal to check that two different buffers reached the comparison.
- **QUDA's host outer-product reference is correct only on one rank.**
  `computeLinkOrderedOuterProduct` (`tests/host_reference/hisq_force_reference.cpp:18-41`) takes
  each site's 1- or 3-hop neighbour through `neighborIndexFullLattice`, whose `neighborIndex`
  wraps modulo the local extents and reads no ghost zone (`tests/utils/index_utils.cpp:56-72`).
  On a rank grid split in some direction, its value at each site whose neighbour lies on another
  rank is built from this rank's opposite face, where QUDA's device code reads the neighbour rank.
  `hisq_paths_force_test` builds its outer products this way and copies the same host field to the
  device (`tests/hisq_paths_force_test.cpp:330-382`), so its host–device comparison is unaffected
  `[inferred]`; on more than one rank it exercises the force on an input that is not the lattice's
  outer product. A test that compares a device outer product against this reference fails at
  exactly those boundary sites on a real rank grid `[observed]` once, at 2 and 4 ranks on one node.
  A single-rank run with forced partitioning (`--partition`) cannot show this: the neighbour rank
  is the rank itself, so the wrap and the exchange agree. Before relying on a host reference beyond
  one rank, check how it finds neighbours, and validate a test that compares against one on a real
  rank grid split in the directions it checks.

**One harness option cannot be passed at all.** At `00c7ef33d`, `--mg-eig-save-prec <level>
<precision>` is registered as a per-level option and then given `->transform(prec_transform)`
on the whole option (`tests/utils/command_line_params.cpp`), so the level token also goes
through the precision transform and every value is rejected `[source]`, `[observed]` once.
Eigenvectors saved by `staggered_invert_test` therefore land in the default precision,
double, twice a single-precision save: size a test-harness bank for that, or save through the
application when the precision matters.

## Preserve solver semantics when changing execution

When replacing, wrapping, batching, or redistributing an existing solver, inventory the stock
behavior beyond its central recurrence. Build a semantics matrix covering initial guesses,
per-right-hand-side convergence, residual modes, zero-norm handling, nonfinite guards, the total
iteration budget, reported iteration and residual fields, and optional chronological, resident,
or action-computation behavior. Implement each supported row equivalently or reject it with an
always-on check at the shared API boundary. A few observed zero initial guesses or unused options
are evidence about those calls, not permission to narrow the public contract.

## Respect state and object lifetimes

Before moving construction across a helper that checks, backs up, splits, or rebuilds resident
state, inspect its callees for deep copies, deletion, global-pointer replacement, lazy
reconstruction, and address capture. Names such as `check` and `backup` do not establish purity
or pointer preservation. Reconcile resident state and create the required layouts before
constructing `Dirac` or other consumers that retain field pointers; then exercise cold, warm,
reuse, invalidation, and teardown transitions affected by the change.

If a public setter is callable before `initQuda`, keep that path to pure data storage. Do not
assume communicator-backed logging, `comm_*`, `printfQuda`, or `errorQuda` is available there;
defer communicator-dependent validation and messages until the first post-initialization use,
or make post-initialization an explicit API precondition.

## A buffer's memory kind decides which calls on its path are synchronous

Accelerator copy APIs are host-blocking for most transfer directions, and the vendor
API-synchronization contract carves out an explicit exception: **for transfers from device memory
to device memory, no host-side synchronization is performed.** The driver-API forms and the HIP
equivalents state the same. The call enqueues and returns.

The consequence is a change that is silent in review. When a staging buffer moves from pinned host
memory to device memory, an unedited copy call on its path changes from host-blocking to
asynchronous, because the direction changed underneath it. In one recorded case the communication
call on the following line then began handing the fabric a buffer the copy had not yet written.
Correctness had been arriving for free from the *direction* of the copy, nothing in the diff said
so, and the result was wrong data moving at several times the previous speed.

**The communication layer is not a participant in the accelerator stream.** Nothing orders an RDMA
or peer-to-peer engine against default-stream work, so a packing kernel or a device-to-device copy
may still be pending when a transfer is started. The receive side carries the mirror hazard: a
device-to-device copy *out of* a shared receive buffer is equally unretired when the next receive is
armed into it, or when the buffer is returned to a pool.

So whenever a buffer changes memory kind, **re-derive which calls on its path were synchronous
because of the old kind, and enumerate them** rather than assuming the edit was local. Where a
drain is required, prefer one that stays correct if stream assignment changes later, and place it so
the packing loop's own ordering is not relied upon across iterations.

## Put the change in the layer that owns it

Before writing a change that crosses into or out of an application interface, decide which of
QUDA's layers owns it: the core, the public `quda.h` API, or an application adapter such as
`lib/milc_interface.cpp`. Anything that reads, writes, or accumulates data in QUDA's own field
storage belongs in the core behind a public entry point; an adapter translates host conventions
and nothing more. The layers, the rule, and the existing adapter code that does not follow it
are in [`interface-layers.md`](interface-layers.md).

## Preserve interface and build contracts

- Enforce public-input, preserved-state, vector-cardinality, and similar runtime contracts with
  always-on `errorQuda` paths. Use `assert` only for internal conditions whose checks may safely
  disappear from release builds.
- Treat public enumeration ordering and values as interface-sensitive. An enum-value repair is
  a state-machine change: enumerate every legal state and transition, then audit all reads,
  writes, defaults, sentinels, and validators. A legal value must not double as the invalid
  sentinel, and separating colliding values may expose assignments that still collapse the
  states. Test every legal state and affected transition. When `include/enum_quda.h` changes,
  update the hand-maintained `include/enum_quda_fortran.h` mirror in the same change. The
  recorded instance is public history since PR #1644 (merge `d220bf72d`, 2026-08-20):
  `QUDA_UPDATE_SPLIT_GAUGE_OFF` shared the value 0 with `QUDA_UPDATE_SPLIT_GAUGE_FALSE`, so a
  request to free the split-gauge buffers read as a request to reuse them, and
  `use_split_gauge_bkup = false` was rejected as "undefined" because the parameter validator
  used `FALSE` as its sentinel. The fix moved `OFF` to -1, kept it alive through the update so
  the epilogue frees the buffers, and made the validator reject only `INVALID`.
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
