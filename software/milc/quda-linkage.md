---
title: MILC binds its QUDA installation at link time
summary: MILC emits -Wl,-rpath without --enable-new-dtags, so the toolchain decides the tag; through the Cray GNU wrappers an executable carries an absolute DT_RPATH that LD_LIBRARY_PATH cannot override, while NVHPC through Open MPI's mpicc, and oneAPI, write a DT_RUNPATH it can; a composed USQCD install then puts a second libquda.so ahead of the linked one.
scope: [software:milc, software:quda]
load_when: Keeping more than one QUDA installation, building QUDA with a composed USQCD prefix, redirecting a MILC executable at a different QUDA, or recording which library a MILC run actually used.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Make_template_scidac
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L516-L520
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/CMakeLists.txt#L529-L532
  - a controlled NVHPC 26.9 link through Open MPI 5.0.11's mpicc on Horizon, and the dynamic section of a ks_spectrum_hisq linked there, 2026-10-21
  - controlled links with nvc and with Open MPI 5.0.11's mpicc over NVHPC 26.9 on Horizon, with -Wl,--disable-new-dtags, and mpicc --showme:link, 2026-10-24
observed: "2026-10-21"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    linker: GNU ld through the Cray compiler wrappers, default dynamic tags
---

# MILC binds its QUDA installation at link time

A MILC executable carries the **absolute path** of the QUDA installation it was linked against,
in a `DT_RPATH` or a `DT_RUNPATH` entry, and the toolchain decides which. `DT_RPATH` takes
precedence over `LD_LIBRARY_PATH`: pointing such an executable at a different QUDA build is not
possible by environment, and **it requires relinking.** `DT_RUNPATH` yields to `LD_LIBRARY_PATH`:
the executable can be redirected, and an inherited `LD_LIBRARY_PATH` can redirect it without
anyone intending to.

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

The tag observed so far, by toolchain:

| Toolchain | Tag |
|---|---|
| Cray wrappers over GNU (Perlmutter, DeltaAI) | `DT_RPATH` |
| NVHPC through Open MPI's `mpicc` (26.1 on Vista, 26.9 on Horizon) | `DT_RUNPATH` |
| oneAPI (Aurora) | `DT_RUNPATH` |

**On Horizon the tag comes from Open MPI's wrapper, not from NVHPC.** `mpicc --showme:link`
(Open MPI 5.0.11) ends with `-Wl,--enable-new-dtags`, **after** the caller's own flags, so the
last option wins and a caller's `-Wl,--disable-new-dtags` is overridden: that is why a controlled
link through `mpicc` with it still produced `RUNPATH`. NVHPC 26.9's `nvc` called directly writes
`RPATH` for the same `-Wl,-rpath`, and its `-dryrun` passes no dtags option `[experiment]`,
2026-10-24. So through that wrapper no `-Wl` flag restores `RPATH`. Whether Vista's NVHPC 26.1
wrapper behaves the same was not re-checked.

## A default-prefix QUDA install leaves a second `libquda.so`, and MILC prefers it

QUDA overrides the install prefix when the builder did not choose one:

```cmake
if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
  set(CMAKE_INSTALL_PREFIX ${CMAKE_BINARY_DIR}/usqcd CACHE PATH "..." FORCE)
endif()
```

so `install` writes `libquda.so` into `<build>/usqcd/lib` while the build tree keeps its own
copy in `<build>/lib`. **Two copies exist after any QUDA build that did not pass
`-DCMAKE_INSTALL_PREFIX`** — this is not conditional on `QUDA_DOWNLOAD_USQCD`, and QUDA's own
comment on that line says the condition was wanted but could not be applied. What
`QUDA_DOWNLOAD_USQCD` adds is that QMP, QIO and LIME land in **the same** prefix, which is what
makes MILC's link order decide between the two copies.

That order is fixed in MILC's build files. QIO and QMP each emit their own rpath entry:

```make
LQMP = -Wl,-rpath,${QMPLIBDIR} -L${QMPLIBDIR} -lqmp
LQIO = -Wl,-rpath,${QIOLIBDIR} -L${QIOLIBDIR} -lqio -llime
```

and they reach the link line **before** QUDA does, through
`LIBSCIDAC = ${LIBQOP} ${LIBQDP} ${LIBQIO} ${LIBQMP}` and
`ILIB = ${LIBSCIDAC} ${LMPI} ${LIBADD}`, where `LIBADD` is what carries `LIBQUDA`. In a
composed build `QMPLIBDIR` and `QIOLIBDIR` both name the composed prefix, so **the composed
prefix precedes `QUDA_HOME/lib` in the run path**, whichever tag carries it, and the loader
resolves `libquda.so` from the install — not from the `-L` directory the link line named for
QUDA.

Confirm it rather than deriving it. `readelf -d` shows the order and `ldd` shows the choice:

```text
 0x000000000000000f (RPATH)  Library rpath: [<build>/usqcd/lib:<build>/lib:...]
        libquda.so => <build>/usqcd/lib/libquda.so
```

**The two copies are the same compilation but are not interchangeable.** They share a GNU Build
ID, and their file hashes differ because CMake rewrites the rpath on install — so a hash
comparison reports a difference that means nothing, while a Build ID comparison is the cheap
check that means something. What genuinely differs is where each copy finds *its own*
dependencies: `CMAKE_INSTALL_RPATH` is set to `${CMAKE_INSTALL_PREFIX}/lib`, so the installed
copy resolves QMP, QIO and LIME from the composed prefix, while the build-tree copy keeps rpath
entries pointing into their separate build trees. Loading the other one is not a no-op.

**The failure this creates is a partial rebuild.** Refresh one copy and not the other and the
executable's loaded QUDA is no longer its linked QUDA, with no warning, and where the tag is
`RPATH` with no environment escape. Nothing crashes; the binary runs code its own records do
not describe.

## Actionable consequences

1. **On a `DT_RPATH` toolchain, two QUDA builds mean two executables.** There is no
   environment-variable path to sharing one binary between them. Budget the relink, and give
   each executable a name that says which library it carries. On a `DT_RUNPATH` toolchain
   `LD_LIBRARY_PATH` can redirect one binary, but its records then describe a library it did
   not load; keep one executable per QUDA build there too.
2. **An executable's identity is incomplete without its library's, and the library to record
   is the resolved one.** A recorded build hash does not say which QUDA was used, and the run
   cannot be reconstructed from it alone. Record the library `ldd` resolves, never the `-L`
   target the build script intended — in a composed stack they are different paths. On a
   `DT_RUNPATH` toolchain, check before launch that `ldd` resolves `libquda.so` from the
   intended install: the installed library's hash does not show which file the loader picks.
3. **Verify with `readelf -d <executable>`** rather than reasoning from the build script.
   Expect exactly one of `RPATH` or `RUNPATH`, and read the path it names.
4. **A rebuild that changes the QUDA install invalidates prior executables**, even when the
   QUDA commit and every compile option are unchanged. Rebuilding QUDA in place is the case
   where this is easiest to miss: the executable keeps working and silently resolves to a
   library that is no longer what its records describe.
5. **In a composed stack, rebuild both copies or neither.** Compare the two `libquda.so` Build
   IDs with `readelf -n` after any QUDA rebuild; equal is the only acceptable result, and
   unequal means the executable is running the copy you did not rebuild.

## Scope

The controlled `RPATH` link ran at MILC `6b9b8a06` through the Cray wrappers; the lines that
emit the flags in `Makefile` and `Make_template_scidac` are unchanged at `a5f8f9fa`, read
2026-10-07, and a `ks_spectrum_hisq` link at `a5f8f9fa` on Horizon still emits a bare
`-Wl,-rpath`.
The emission of a bare `-Wl,-rpath` is a property of MILC's build files and is expected to
transfer; **which tag results is a
linker-default property and is not.**

The binding itself depends on nothing in QUDA — QUDA is simply the library most often swapped,
and the same binding applies to the QMP and QIO paths MILC emits the same way, so a stack that
rebuilds any of them inherits it. The composed-install section is the one part that does depend
on a QUDA build option, namely the composed USQCD prefix, which is why the scope names both
projects rather than `software:milc` alone.

The duplicate-copy behaviour was observed on **two independently built composed stacks**, each
reproducing the rpath order, the duplicate `libquda.so`, matching Build IDs within a stack, and
resolution from the install prefix. Both were on one machine with one MILC revision and one
CMake, so what transfers is the mechanism — QUDA's default-prefix override plus MILC's emission
order — rather than the observation count. See
[`build.md`](build.md) for the surrounding build contract and
[`../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md`](../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md)
for a stack where two QUDA installations coexist under exactly this constraint.
