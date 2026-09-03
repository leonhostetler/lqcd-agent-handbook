---
title: MILC binds its QUDA installation at link time
summary: MILC emits -Wl,-rpath without --enable-new-dtags, so an executable carries an absolute DT_RPATH that LD_LIBRARY_PATH cannot override; changing the QUDA a build uses requires relinking.
scope: [software:milc]
load_when: Keeping more than one QUDA installation, redirecting a MILC executable at a different QUDA, or recording which library a MILC run actually used.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Make_template_scidac
observed: "2026-09-02"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
  toolchain:
    linker: GNU ld through the Cray compiler wrappers, default dynamic tags
---

# MILC binds its QUDA installation at link time

A MILC executable does not resolve QUDA at run time in the way an environment variable can
influence. It carries the **absolute path** of the QUDA installation it was linked against in
a `DT_RPATH` entry, and `DT_RPATH` takes precedence over `LD_LIBRARY_PATH`. Pointing an
existing executable at a different QUDA build is therefore not possible by environment:
**it requires relinking.**

## Mechanism

MILC adds the library search path with a bare `-Wl,-rpath` and never passes
`--enable-new-dtags` — `Makefile` for QUDA, `Make_template_scidac` for QMP and QIO. The tag
type is then decided by the linker default, not by MILC.

That default is what makes this bite. A controlled link on the Cray wrappers, moving only
`--enable-new-dtags`, produced:

| Link flags | Resulting tag |
|---|---|
| `-Wl,-rpath,<dir>` (what MILC emits) | `DT_RPATH` |
| `-Wl,--enable-new-dtags,-rpath,<dir>` | `DT_RUNPATH` |

The distinction is the whole fact. `DT_RUNPATH` is consulted **after** `LD_LIBRARY_PATH`, so a
`RUNPATH`-tagged binary can be redirected by environment; `DT_RPATH` is consulted **before** it
and cannot. A toolchain whose linker defaults to new dtags will produce the redirectable form
from the same MILC source, so confirm the tag rather than assuming either behaviour.

## Actionable consequences

1. **Two QUDA builds mean two executables.** There is no environment-variable path to
   sharing one binary between them. Budget the relink, and give each executable a name that
   says which library it carries.
2. **An executable's identity is incomplete without its library's.** A recorded build hash
   does not say which QUDA was used, and the run cannot be reconstructed from it alone. Record
   the library's hash alongside the executable's.
3. **Verify with `readelf -d <executable>`** rather than reasoning from the build script.
   Expect exactly one of `RPATH` or `RUNPATH`, and read the path it names.
4. **A rebuild that changes the QUDA install invalidates prior executables**, even when the
   QUDA commit and every compile option are unchanged. Rebuilding QUDA in place is the case
   where this is easiest to miss: the executable keeps working and silently resolves to a
   library that is no longer what its records describe.

## Scope

Observed at one MILC revision through the Cray wrappers. The emission of a bare `-Wl,-rpath`
is a property of MILC's build files and is expected to transfer; **which tag results is a
linker-default property and is not.**

The scope is `software:milc` alone deliberately. Nothing here depends on QUDA's version or build
options — QUDA is simply the library most often swapped. The same binding applies to the
QMP and QIO paths MILC emits the same way, so a stack that rebuilds any of them inherits it. See
[`build.md`](build.md) for the surrounding build contract and
[`../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md`](../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md)
for a stack where two QUDA installations coexist under exactly this constraint.
