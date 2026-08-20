---
title: MILC
summary: Role, application selection, QUDA composition, and routing guidance for the MILC application suite.
scope: [software:milc]
load_when: Selecting or compiling a MILC application, build profile, or accelerator interface.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/README.md
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
observed: "2026-08-19"
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
`build-profiles.yaml` for the canonical option set and its composed QUDA requirements,
`build.md` for the shared application-directory build contract, and the selected application
guide for its portable directory and target recipe. A machine stack owns the toolchain, paths,
build cost, scheduler resources, and demonstrated runtime scope.

MILC applications do not share one input grammar or output interpretation. Load the matching
application guide before preparing or analyzing a run:

- `applications/ks-spectrum.md` for source, propagator, and correlator workflows;
- `applications/ks-measure.md` for staggered observable measurements; and
- `applications/ks-imp-rhmc.md` for RHMC trajectories and gauge generation; and
- `applications/wilson-flow.md` for gradient-flow evolution and gauge observables.

For staggered internals shared across applications, use:

- `internals/staggered-inverter-types.md` for `CG`, `CGZ`, `UML`, and `MG`
  dispatch, parity behavior, and set interactions; and
- `internals/quark-source-types.md` for base-source construction, support status,
  subset behavior, and source parity.

These are application guides, not build profiles. They define portable application entry points,
work units, input/output boundaries, and completion semantics; the selected build profile still
owns the exact option set, instrumentation, and accelerator capabilities. Use `timing.md` for the
MILC-wide timing macro policy and output-layer hierarchy.
