---
title: MILC CUDA 13 QUDA staggered-MG ks_spectrum stack on Perlmutter
summary: Reproduction notes for the first validated linked-MILC staggered multigrid ks_spectrum_hisq stack, and the two build facts that make it reproducible.
scope: [machine:perlmutter, software:milc, software:quda, solver:multigrid, fermion:staggered]
load_when: Rebuilding or validating the Perlmutter MILC ks_spectrum_hisq stack with QUDA staggered multigrid.
evidence: experiment
observed: "2026-08-31"
observed_on:
  machine: perlmutter
  node_type: gpu-a100-40
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
  toolchain:
    cuda: 13.2.78
    host_compiler: GNU 14.3.0 through Cray wrappers
sources:
  - machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/stack.yaml
  - operator-submitted validation run reviewed in the working directory
---

# MILC CUDA 13 QUDA staggered-MG ks_spectrum stack on Perlmutter

This is the handbook's first stack in which a **linked MILC executable** ran QUDA staggered
multigrid. The existing
[`quda-cuda13-mg-staggered-2026q3`](../quda-cuda13-mg-staggered-2026q3/notes.md) stack
validates QUDA's own native GCR-MG test path and nothing about MILC linkage; this record
closes that gap and does not replace it.

Read [`stack.yaml`](stack.yaml) `validation.scope_limits` before citing this stack. The
validation is narrow: one hierarchy, one placement, one gauge configuration, with stored
near-null and eigenvector sets loaded rather than generated.

## Build order

1. Build QUDA from the [`mg-staggered`](../../../../software/quda/build-profiles.yaml)
   profile. The composed installation supplies QMP and QIO; MILC links against both.
2. Build `ks_spectrum_hisq` from the
   [`ks-spectrum-hisq-quda-mg`](../../../../software/milc/build-profiles.yaml) profile,
   pointing `QUDA_HOME`, `QMPPAR`, and `QIOPAR` at that installation.

## Two build facts that are easy to get wrong

**1. The action header is a copy step, not a repository file.** `ks_spectrum/quark_action.h`
is not tracked by MILC. The build copies it in, and for this stack it is byte-identical to the
tracked `generic_ks/imp_actions/hisq/hisq_u3_action.h`. A checkout at the pinned commit is
therefore not sufficient to reproduce the build; the copy must be reproduced too. The
same applies to `ks_spectrum/Makefile`, copied unmodified from the application directory's
parent.

**2. `MULTIGRID` is a `KSCGMULTI` define, not a `WANT_*` switch.** In the observed GNU Make
path the MG dispatch is compiled only when `KSCGMULTI` carries `-DMULTIGRID`. A build that
sets every `WANT_*` variable correctly and leaves `KSCGMULTI` at its plain-CG value produces
a working QUDA-accelerated executable with **no** MG path, and the omission does not surface
until a run silently takes the CG fallback. `software/milc/project.yaml` records
`WANT_MULTIGRID` as the corresponding CMake control; the two build systems do not agree, so
check the one you are actually using.

## The linked QUDA cannot be changed by environment

This stack's executable carries the absolute path of its QUDA installation in `DT_RPATH`, so
no environment variable can point it at a different one. The mechanism and its consequences
are recorded once, in
[`software/milc/quda-linkage.md`](../../../../software/milc/quda-linkage.md).

What matters here: a second QUDA installation exists on this machine at the same commit with a
wider `QUDA_MULTIGRID_NVEC_LIST`, and it has its **own** relinked executable. The two cannot be
interchanged, and this record covers only the one named in `tested_software`. Confirm which
library an executable carries with `readelf -d` before attributing a run to this stack.

## Deviation from the mg-staggered profile

The QUDA installation behind this validation was configured with `QUDA_BUILD_ALL_TESTS` and
`QUDA_INSTALL_ALL_TESTS` **OFF**. The handbook default, set on 2026-08-20 and enforced by a
regression test, is ON. Every other option matches the `mg-staggered` profile, including
`QUDA_MULTIGRID_NVEC_LIST` and `QUDA_MULTIGRID_MRHS_LIST`.

This is recorded rather than corrected because the validation evidence belongs to this
library. Rebuilding with tests enabled produces a **different** installation that this record
does not cover, and the executable would have to be relinked against it per the `DT_RPATH`
constraint above. A reproduction that follows the current profile is expected to differ from
this record in exactly that one respect.

## Build cost

### The MILC application build

`stack.yaml` records **54.97 s wall and 145,724 KiB peak RSS at `-j1`**, measured under
`/usr/bin/time -v`. This is a fresh instrumented rebuild of the identical recipe against the
same QUDA installation, run in a **copy** of the application directory, not the original build
of the validated executable — that build's log was overwritten by a later relink and carried no
timing.

The rebuild reproduced the recipe: 95 application objects, every one compiled with
`-DMULTIGRID`, the MG entry points present in the resulting binary, and `DT_RPATH` resolving to
the same QUDA installation. Its size differs from the validated executable by 272 bytes,
consistent with the differing absolute path lengths baked into `DT_RPATH`.

Two scope notes:

- It covers **application objects and the final link only.** The dependent MILC libraries
  `su3.2.a` and `complex.2.a` were already present and were not rebuilt. The comparable
  [`ks-spectrum-hisq-quda`](../milc-cuda13-quda-ks-spectrum-2026q3/stack.yaml) cost of 55.56 s
  *does* include those libraries, so the two figures are not measuring the same work despite
  landing within a second of each other. Do not read the near-equality as agreement.
- The validated executable was built on a **compute node** inside an interactive allocation;
  this measurement was taken on a **login node**, within the site's limited-compilation
  guidance at `-j1`.

To re-measure, build in a copy of the application directory or a disposable checkout. Building
in place overwrites the executable whose hash the working directory's validation records pin.

### The composed QUDA build, for planning

QUDA is the expensive half by three orders of magnitude, and a session budgeting this stack
should plan around it rather than around the MILC link:

- The QUDA installation **this stack composes** was built across three resumable one-hour
  `gpu-a100-40` allocations, with a final build command of about **40 minutes**. Its cost is
  owned by [`quda-cuda13-mg-staggered-2026q3`](../quda-cuda13-mg-staggered-2026q3/stack.yaml);
  see the note there that the historical build compiled a focused test target separately and is
  not an all-tests estimate.
- A **second** QUDA installation at the same commit, differing only in
  `QUDA_MULTIGRID_NVEC_LIST`, took **1 h 35 m on one node** in a single interactive allocation.
  That build enabled the full test suite. It is the closer estimate for a from-scratch build
  under the current profile, and it is **not** the installation this stack was validated
  against.
