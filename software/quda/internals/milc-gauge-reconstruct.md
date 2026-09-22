---
title: QUDA MILC gauge reconstruct is environment-only
summary: Two environment variables decide how every MILC-interface gauge field is stored; unset means the most expensive option, the sloppy partner inherits rather than defaulting, and a change re-tunes the gauge-touching kernels.
scope: [software:quda, software:milc, fermion:staggered]
load_when: Setting or auditing gauge-field storage for a MILC-facing QUDA run, comparing two runs' memory or timing, or reusing a tunecache across a reconstruct change.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L260-L292
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/instantiate.h#L110-L210
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L226-L228
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/CMakeLists.txt#L220-L240
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems
observed: "2026-09-21"
observed_on:
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# QUDA MILC gauge reconstruct is environment-only

`QUDA_MILC_HISQ_RECONSTRUCT` and `QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY` decide how every fat and
long gauge field the MILC interface creates is stored. They appear in no input file, no multigrid
parameter file, and no build option. **A trial package can be frozen, checksummed, dry-run and
reviewed and still differ from another run in gauge-field storage, with the only evidence sitting
in a launcher's `export` lines.**

## Four source facts, and the second and third are the traps

1. **Legal values are `18`, `13`, `9`.** Anything else is a hard `errorQuda`, so a typo fails
   loudly rather than silently — the one piece of good news here.
2. **Unset means `18`**, which is *no* reconstruction: the most memory-hungry and
   highest-bandwidth storage available. Doing nothing does not give a neutral setting; it gives
   the expensive end.
3. **The sloppy partner inherits the outer value when unset**, rather than having a default of
   its own. Setting only the first variable to `13` therefore yields **`13/13`, not the
   `13/9`** a reader would assume from a record quoting both. Half-configuring is silent.
4. **Both are read once per process and cached** behind a `static` guard, so the value in force
   is whatever the environment held at first use. Changing it later in the run does nothing.

## It is also gated by a build option, and the error says so obscurely

Reconstruct is a **template parameter**, not a runtime branch: the dispatcher compares the
field's reconstruct against each compiled specialisation and instantiates that kernel. Which
specialisations exist is fixed at build time by `QUDA_RECONSTRUCT`, a three-bit mask over
`18`, `13/12` and `9/8`.

The default is `7` — all three — so this does not normally bite. A build that narrows the mask
to cut compile surface makes a runtime `13` or `9` fail with `QUDA_RECONSTRUCT=<n> does not
enable <m>`, which names the build mask rather than the environment variable the operator set.
**Treat the compiled mask as a capability of the build profile**, like any other, when a run
requests a non-default reconstruct.

## What it costs beyond bytes

Reconstruction trades arithmetic for memory traffic. For a bandwidth-bound staggered operator the
performance effect is usually the larger one, so this is not purely a capacity knob.

**It silently invalidates comparisons.** A memory model or a timing calibration taken under one
setting does not describe a run taken under another, because the stored size of every gauge field
differs. Record the pair beside any figure derived from the run.

**And it leaves a tunecache only partly warm.** Because each reconstruct is a distinct kernel
specialisation, a different setting produces *new tune keys for exactly the gauge-touching
kernels* while every other entry still hits. A run seeded from a cache built at another
reconstruct is therefore neither cold nor warm, and **any timing from it must say so** — see
[`autotuning.md`](autotuning.md), which owns cache warmth.

## It also forces an extra gauge copy in the KD build

Building the Kahler-Dirac inverse begins by deciding whether it can use the gauge field it was
handed or must materialise its own copy:

```cpp
bool need_new_U = true;
if (location == QUDA_CUDA_FIELD_LOCATION && gauge.Reconstruct() == QUDA_RECONSTRUCT_NO
    && gauge.Precision() == QUDA_SINGLE_PRECISION)
  need_new_U = false;
```

The test requires **both** conditions. At `13` or `9` the first fails outright, so a full
unreconstructed single-precision copy of the fine gauge field is allocated for the duration of
the build. At `18` the copy is avoided only if the field is also single precision.

This does not change the recommendation -- `13`/`9` remains what every validated stack and
every upstream MILC sample script uses -- but it is a real, reconstruct-dependent allocation
that a setup-phase memory estimate has to carry, and it is invisible in any input file for the
reasons this page already gives.

## What to do

**Set `QUDA_MILC_HISQ_RECONSTRUCT=13` and `QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9` unless there is
a stated reason not to**, and set both explicitly rather than relying on either default.

```bash
export QUDA_MILC_HISQ_RECONSTRUCT=13
export QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9
```

**That pair is the established convention, not a measured optimum, and the distinction matters.**
All seven of MILC's own sample submission scripts under `systems/` use exactly `13`/`9`, as does
every stack record in this handbook that carries the pair. What no record here contains is a
controlled comparison: **nobody has measured `18`/`18` against `13`/`9` on a matched pair on any
machine in this catalogue**, so the case for `13`/`9` is consistency with every validated stack
and every upstream sample, not evidence that it is fastest or smallest for a given workload. Treat a
departure as a candidate to measure rather than a mistake — and treat it as invalidating every
memory and timing figure recorded here, all of which were taken at `13`/`9`.

The pair is deliberately asymmetric, the sloppy field being stored more compactly than the outer
one. `[inferred]` That is consistent with the mixed-precision arrangement it serves, where the
inner solve tolerates a coarser representation than the outer one; no source statement in either
project asserts the reasoning, so do not carry it further than the pattern.

Taking a default by omission gives the most expensive storage while leaving no trace of the
choice anywhere in the trial package.

**Set them from one pair of shell variables rather than typing the values twice**, so that a
provenance line and the exported value cannot drift apart. That is the typed-constant rule in
[`../../../conventions/batch-scripts.md`](../../../conventions/batch-scripts.md) applied to a
pair that is unusually easy to half-edit.
