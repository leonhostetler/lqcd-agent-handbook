---
title: QUDA MILC gauge reconstruct is environment-only
summary: Two environment variables decide how the MILC interface stores HISQ long links, never fat links; unset means the most expensive option, the sloppy partner inherits rather than defaulting, and a change re-tunes the kernels that read long links.
scope: [software:quda, software:milc, fermion:staggered]
load_when: Setting or auditing gauge-field storage for a MILC-facing QUDA run, comparing two runs' memory or timing, or reusing a tunecache across a reconstruct change.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L260-L292
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L979-L999
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/multigrid.cpp#L464-L468
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/staggered_kd_build_xinv.cu#L150-L153
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/instantiate.h#L110-L210
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L226-L228
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/CMakeLists.txt#L220-L240
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/systems
  - operator's screened benchmark records (2026)
observed: "2026-10-07"
observed_on:
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
---

# QUDA MILC gauge reconstruct is environment-only

`QUDA_MILC_HISQ_RECONSTRUCT` and `QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY` decide how the MILC interface
stores the HISQ **long** links, and never the fat links: `[source]` the interface hard-codes the
fat-link field, its sloppy copy and its preconditioner copy to `18` and reads the variables for the
long-link field only. They appear in no input file, no multigrid
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
setting does not describe a run taken under another, because the stored size of the long-link
fields differs. Record the pair beside any figure derived from the run.

**And it leaves a tunecache only partly warm.** Because each reconstruct is a distinct kernel
specialisation, a different setting produces *new tune keys for the kernels that read or copy
the long links* — the staggered dslash, gauge copies and ghost extraction, and the memory
operations keyed by their byte count — while every other entry still hits, link fattening
included (`[experiment]`, two caches at QUDA `b6998853` differing only in the pair). A run
seeded from a cache built at another reconstruct is therefore neither cold nor warm, and **any
timing from it must say so** — see [`autotuning.md`](autotuning.md), which owns cache warmth.

## It does not decide the KD build's gauge copy

Building the Kahler-Dirac inverse begins by deciding whether it can use the gauge field it was
handed or must materialise its own copy:

```cpp
bool need_new_U = true;
if (location == QUDA_CUDA_FIELD_LOCATION && gauge.Reconstruct() == QUDA_RECONSTRUCT_NO
    && gauge.Precision() == QUDA_SINGLE_PRECISION)
  need_new_U = false;
```

The field it is handed is the smoother's short-link field, which for HISQ is the fat-link field,
and the MILC interface stores that at `18` whatever these variables say. On this path the first
condition therefore always holds, and **precision alone decides the copy**: a full unreconstructed
single-precision copy of the fine fat-link field is allocated for the duration of the build unless
the smoother already holds that field in single precision. The reconstruct pair does not enter.

The copy is still a real allocation that a setup-phase memory estimate has to carry, invisible in
any input file, and **it is paid again on every full multigrid update**, because that update
rebuilds the KD inverse; a thin update pays nothing. Which of the two a MILC run performs is
decided by its set type — see
[`../solvers/staggered-multigrid.md`](../solvers/staggered-multigrid.md).

## What to do

**Set `QUDA_MILC_HISQ_RECONSTRUCT=13` and `QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9` unless there is
a stated reason not to**, and set both explicitly rather than relying on either default.

```bash
export QUDA_MILC_HISQ_RECONSTRUCT=13
export QUDA_MILC_HISQ_RECONSTRUCT_SLOPPY=9
```

**That pair is the established convention, measured once, and the distinction still matters.**
All seven of MILC's own sample submission scripts under `systems/` use exactly `13`/`9`, as does
every stack record in this handbook that carries the pair. **One controlled comparison exists**
`[experiment]`, the pair being the only variable moved: plain mixed-precision CG (`inv_type UML`,
double/single, point source) on a 64³×96 HISQ ensemble near physical light mass, on one Perlmutter
`gpu-a100-40` node with four ranks, both legs in one job and each warm on its own tunecache, at
QUDA `b6998853` and MILC `6b9b8a06` on `develop`. `18`/`18` took **1.16 times** as long per even
solve as `13`/`9` (medians of five warm solves, 3.99 against 3.45 ms per iteration), and its
device high-water was 0.7 GiB higher per rank, small because only the long links change storage.
It is one job on one node, unrepeated: `13`/`9` is the measured faster pair for that solve, not a
general optimum, and the comparison says nothing about multigrid, more nodes, or other
precisions. Treat a departure as a candidate to measure rather than a mistake — and treat it as
invalidating every memory and timing figure recorded here, all of which were taken at `13`/`9`.

**Do not expect equal iteration counts across the pair.** In the same comparison the even-solve
counts of three colour solves moved by −0.5 %, +2.2 % and +0.5 %, against at most 0.25 % between
the `18`/`18` counts and an earlier, separately tuned `18`/`18` run of the same even-parity system
`[experiment]`. `[inferred]` The sloppy long links are part of the mixed-precision iteration, so a
different pair is a different iteration path rather than a round-off perturbation, and over about
sixteen thousand iterations the difference reaches the percent level. A reconstruct control that
expects equality to round-off will report a discrepancy every time.

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
