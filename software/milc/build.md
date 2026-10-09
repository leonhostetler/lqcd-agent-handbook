---
title: Building MILC applications
summary: Shared portable build contract for MILC application-directory targets and machine adapters.
scope: [software:milc]
load_when: Compiling, linking, or validating any MILC application.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/libraries/Make_vanilla#L29-L49
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/libraries/Make_vanilla#L29-L48
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_spectrum/Make_template#L280-L284
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile#L1436-L1445
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_lat_utils.c#L1752-L1798
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/generic/io_lat_utils.c#L1754-L1810
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_spectrum/Make_template#L79-L82
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_spectrum/Make_template#L116-L119
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_spectrum/control.c#L361-L363
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_spectrum/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_measure/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/ks_imp_rhmc/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/ab5011f5722dd423c9c459dea312ad0b6d565f45/wilson_flow/Make_template
  - operator's DeltaAI build records for the PR #102 branch
observed: "2026-10-09"
observed_on:
  software:
    milc:
      commit: ab5011f5722dd423c9c459dea312ad0b6d565f45
      branch: develop
---

# Building MILC applications

Follow `../../playbooks/build-lqcd-stack.md` for source selection, composition, placement,
cost, and validation. This file owns the shared MILC application-directory build contract.
The selected application guide owns its portable directory and upstream target mapping;
`build-profiles.yaml` owns reusable option sets and compiled capabilities; the machine stack
owns compilers, accelerator target, dependency prefixes, flags, and build placement.

## Resolve the portable recipe

Load the requested application guide before building. When the selected named profile has an
`application_guide` pointer, follow it directly and require its target to appear in the profile's
`targets`. A source-backed target listed by a guide is not by itself a reusable option profile.
If no named profile supplies the requested target and capabilities, report that gap before
deriving and recording a new option set.

For a composed profile, validate `required_capabilities` against the dependency profile. A
current-machine dependency stack that references the resolved dependency profile is sufficient
for the first application build attempt. A missing same-machine application stack limits runtime
claims; it does not require re-inspecting or rebuilding a dependency before the application has
been compiled and linked.

## Reuse a compatible checkout

Use the existing MILC checkout when its revision satisfies the request and planned writes do not
overlap unrelated changes. A disposable checkout is appropriate for explicit pristine
reproduction, a required revision change, conflicting application artifacts, or an operator
cleanliness requirement; it is not the default merely because MILC builds in its source tree.

MILC application targets include their local `Make_template` through a copy of the repository
`Makefile`. Preserve any differing application-local `Makefile`; do not overwrite it.

## Materialize profile and machine options

Construct `profile_args` from every entry under the selected profile's `options` mapping in
`build-profiles.yaml`. Construct `machine_args` from every entry under `build.machine_options`
in the current-machine stack. Each mapping entry becomes exactly one shell-array element in the
form `KEY=value`; the mapping key is the MILC make variable and must not be renamed. Preserve
explicit false, zero, and empty values rather than silently dropping them.

Resolve stack placeholders such as `<quda-install-prefix>` and intentional environment
references against the live build environment before invoking make. Keep each complete
assignment in one quoted array element because values including `CTIME`, `OPT`, `LDFLAGS`, and
`LIBQUDA` can contain whitespace. If a key occurs in both mappings, stop and resolve the
ownership error instead of relying on command-line ordering. Before the build, print or capture
the resolved arrays in provenance so that the command can be reproduced.

**A command-line assignment replaces the Makefile's own additions to that variable.** GNU make
gives a command-line variable precedence over the Makefile's ordinary `+=`, while an environment
variable is appended to. So a stack's `LDFLAGS` is the complete link value, not a prefix. With
`OMP=true` and `COMPILER=gnu` the Makefile appends `-fopenmp ... -lgomp` to `LDFLAGS` while the
objects still compile with `-fopenmp`, so `LDFLAGS=-g` on the command line compiles and then
fails at the final link on unresolved OpenMP symbols, unless the compiler wrapper supplies
OpenMP itself; the DeltaAI Cray wrappers do not (observed 2026-10-07, see
[the DeltaAI stack notes](../../machines/deltaai/stacks/milc-cuda12-quda-ks-spectrum-2026q4/notes.md)).
Name the runtime of the compiler actually behind the wrapper, which `COMPILER`
does not tell you: `-fopenmp -lgomp` for GCC; `-fopenmp` alone for Intel `icx`, where adding
`-lgomp` links a second OpenMP runtime (see the
[Aurora stack notes](../../machines/aurora/stacks/milc-sycl-quda-ks-spectrum-2026q4/notes.md)).
After linking, `readelf -d` must list exactly one of `libgomp`, `libiomp5` or `libomp`.
From `d17e9559` (PR #99, 2026-10-06) the Makefile also appends `${OPT}` to `LDFLAGS`, so a
command-line `LDFLAGS` drops the optimization flags from the link line as well; put them in the
stack's value when they matter at link time.

## The library compiler follows `COMPILER`, except from `d17e9559` through `a5f8f9fa`

`libraries/Make_vanilla` maps `COMPILER` to a C compiler. The application's `libmake` rule
passes `APP_CC`, `PRECISION`, `ARCH` and `COMPILER` to it, never `CC`, and `Make_vanilla` reads
`APP_CC` nowhere, so the `COMPILER` mapping alone selects the library compiler, whatever the
application compiler is. Confirm it on the library compile lines of the build log.

From `d17e9559` through `a5f8f9fa` an uncommented `CC = mpicc` (which entered through merge
`87e4529d`) overrides the mapping, so every `su3` library build at those revisions compiles with
`mpicc` whatever `COMPILER` names, and on a system without that wrapper the library step fails
before any application object compiles. At those revisions expect to override it (an edit to
`Make_vanilla`, or building the libraries directly with `CC` on the make command line).
`[observed]` on DeltaAI at `a5f8f9fa`: with `APP_CC=cc` passed, every library compile line used
`mpicc` and every application object `cc`. DeltaAI's Cray MPICH provides an `mpicc` that wraps
plain `gcc`, so there the library builds, with that wrapper rather than the Cray one; the failure
on a system with no `mpicc` has not been run. PR #102 (merge `ab5011f5`, 2026-10-09) deletes the
override; with it, the same DeltaAI build compiled every library object with `gcc`, the mapping
for `COMPILER=gnu` `[observed]`.

For example, this profile fragment:

```yaml
options:
  PRECISION: 2
  CTIME: -DONE -DTWO
```

must become two array elements:

```bash
profile_args=("PRECISION=2" "CTIME=-DONE -DTWO")
```

After the application guide supplies its directory and target values and both argument arrays
have been materialized, use this shared invocation:

```bash
milc_source=${MILC_SOURCE_DIR:?set MILC_SOURCE_DIR}
milc_install=${MILC_INSTALL_DIR:?set MILC_INSTALL_DIR}
application_dir=${MILC_APPLICATION_DIR:?set MILC_APPLICATION_DIR}
target=${MILC_MAKE_TARGET:?set MILC_MAKE_TARGET}
built_executable=${MILC_BUILT_EXECUTABLE:?set MILC_BUILT_EXECUTABLE}
install_name=${MILC_INSTALL_NAME:-$built_executable}
jobs=${MILC_BUILD_JOBS:?set MILC_BUILD_JOBS}

cd "$milc_source/$application_dir"
if test -e Makefile; then
  cmp -s ../Makefile Makefile || {
    echo "application Makefile differs from the repository Makefile" >&2
    exit 1
  }
else
  cp ../Makefile Makefile
fi

mkdir -p "$milc_install/bin"
declare -p profile_args machine_args >/dev/null 2>&1 || {
  echo "materialize profile_args and machine_args before building" >&2
  exit 1
}
printf 'MILC make argument: %q\n' "${profile_args[@]}" "${machine_args[@]}"
make -j "$jobs" "$target" "${profile_args[@]}" "${machine_args[@]}"
install -m 0755 "$built_executable" "$milc_install/bin/$install_name"
```

Populate `profile_args` exactly from the selected named profile and `machine_args` from the
current-machine stack. Do not copy another machine's compiler, accelerator, link, or filesystem
values. Do not run a broad clean merely to obtain a first build; preserve existing artifacts and
let the target-specific MILC dependency rules rebuild what the resolved configuration requires.

## Two build constraints through `a5f8f9fa`, lifted from `ab5011f5`

- **Through `a5f8f9fa`, build serially from a clean tree.** The target recipe generates the
  application's `quark_action.h`; with `MILC_BUILD_JOBS` above 1, objects that include it
  compile first and fail with `quark_action.h: No such file or directory` `[observed]`, and the
  application can also race ahead of the `su3` and `complex` libraries that `libmake` builds.
  From PR #102 (merge `ab5011f5`) the application `Make_template`s make the libraries wait for
  `libmake` and re-copy the action headers after `${LASTMAKE}` cleans the tree. On DeltaAI
  `ks_spectrum_hisq` then built from a clean tree at `-j16` every time, the
  `ks-spectrum-hisq-quda` profile's target included, and each of the 31 applications that
  change ended a clean build the same way at `-j16` as at `-j1` `[observed]`; some of them fail
  both ways, on errors unrelated to the race. Nine legacy applications whose
  `Make_template` names unsuffixed `su3.a` and `complex.a` are not covered; they do not link
  serially either. The validated stacks still record `-j1` builds, so parallel builds are not
  yet part of any stack's validation.
- **Through `a5f8f9fa`, a build without QIO does not compile.** From `d17e9559`
  `generic/io_lat_utils.c` uses `QIO_SINGLEFILE`, `QIO_PARTFILE`, `QIO_PARTFILE_DIR` and
  `QIO_UNKNOWN` in `open_scidac_detect_volume_format` with no `HAVE_QIO` guard, so a
  `ks_spectrum_hisq` build with `WANTQIO=false` fails at either precision `[observed]`. From
  `ab5011f5` those uses, and `ks_spectrum`'s `QIO_verbose` call before the QUDA eigenvector
  load, are guarded on `HAVE_QIO`, and without QIO the function opens the file as a plain MILC
  file. A CPU `ks_spectrum_hisq` with `WANTQIO=false` then compiles and links, compiled and not
  run. The profiles keep `WANTQIO=true`.

## Preserve timing and linkage evidence

Keep the timing definitions described in `timing.md` enabled. They are required for tuning and
benchmarking builds and are the normal recommendation for other builds. Record the exact
profile-owned `CTIME` value with the executable identity.

Before allocating a node, confirm that the executable has no unresolved shared libraries and
that it resolves the dependencies required by the profile. A successful link is compatibility
evidence, not runtime validation.

Record which accelerator library the executable actually carries, not only that it linked.
MILC binds it by absolute path at link time, so the environment cannot redirect it later and
the executable's own hash does not identify it — see
[`quda-linkage.md`](quda-linkage.md).

## Validate the application contract

Use the smallest workload that exercises the requested profile capabilities on the resolved node
type. The application guide owns its completion, cardinality, numerical, artifact, and timing
interpretation; the machine stack owns placement and telemetry expectations. Record payload and
wrapper exits separately, preserve explicit scope limits for linked but unexercised paths, and
treat a fresh accelerator tunecache run as validation rather than benchmark evidence.
