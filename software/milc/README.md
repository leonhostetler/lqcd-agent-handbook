---
title: MILC
summary: Role, application selection, QUDA composition, and routing guidance for the MILC application suite.
scope: [software:milc]
load_when: Selecting a MILC application, build profile, or accelerator interface.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/README.md
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
observed: "2026-08-17"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC

MILC is a suite of lattice-QCD applications rather than one executable. Select the
application and physics action first, then choose a build profile that provides the needed
communication, I/O, and accelerator paths.

The `ks-spectrum-hisq-quda` profile builds the `ks_spectrum_hisq` application and composes
with QUDA's `milc-cg` profile. Composition is explicit because a successful MILC build
requires more than a QUDA library: the QUDA installation must contain its MILC interface,
staggered operators and CG solver, plus the QMP and QIO dependencies selected by that QUDA
profile.

Use `project.yaml` for intrinsic MILC capabilities and option meanings,
`build-profiles.yaml` for the canonical option set and its composed QUDA requirements, and
`build.md` for the software-local build and acceptance procedure. A machine stack owns the
toolchain, paths, build cost, scheduler resources, and demonstrated runtime scope.

MILC applications do not share one input grammar or output interpretation. Load the matching
application guide before preparing or analyzing a run:

- `applications/ks-spectrum.md` for source, propagator, and correlator workflows;
- `applications/ks-measure.md` for staggered observable measurements; and
- `applications/ks-imp-rhmc.md` for RHMC trajectories and gauge generation; and
- `applications/wilson-flow.md` for gradient-flow evolution and gauge observables.

These are application guides, not build profiles. They define work units, input/output
boundaries, and completion semantics; the selected build profile still owns which executable,
instrumentation, and accelerator capabilities exist. Use `timing.md` for the MILC-wide timing
macro policy and output-layer hierarchy.
