---
title: Building MILC applications
summary: Shared portable build contract for MILC application-directory targets and machine adapters.
scope: [software:milc]
load_when: Compiling, linking, or validating any MILC application.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_measure/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_imp_rhmc/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/wilson_flow/Make_template
observed: "2026-08-20"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
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
`Makefile`. Preserve any differing application-local `Makefile`; do not overwrite it. After the
application guide supplies its application-specific recipe values, use this shared invocation
shape:

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
make -j "$jobs" "$target" "${profile_args[@]}" "${machine_args[@]}"
install -m 0755 "$built_executable" "$milc_install/bin/$install_name"
```

Populate `profile_args` exactly from the selected named profile and `machine_args` from the
current-machine stack. Do not copy another machine's compiler, accelerator, link, or filesystem
values. Do not run a broad clean merely to obtain a first build; preserve existing artifacts and
let the target-specific MILC dependency rules rebuild what the resolved configuration requires.

## Preserve timing and linkage evidence

Keep the timing definitions described in `timing.md` enabled. They are required for tuning and
benchmarking builds and are the normal recommendation for other builds. Record the exact
profile-owned `CTIME` value with the executable identity.

Before allocating a node, confirm that the executable has no unresolved shared libraries and
that it resolves the dependencies required by the profile. A successful link is compatibility
evidence, not runtime validation.

## Validate the application contract

Use the smallest workload that exercises the requested profile capabilities on the resolved node
type. The application guide owns its completion, cardinality, numerical, artifact, and timing
interpretation; the machine stack owns placement and telemetry expectations. Record payload and
wrapper exits separately, preserve explicit scope limits for linked but unexercised paths, and
treat a fresh accelerator tunecache run as validation rather than benchmark evidence.
