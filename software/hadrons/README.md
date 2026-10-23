---
title: Hadrons
summary: Role of Hadrons as the module framework under HadronsMILC, the milc-qcd fork that HadronsMILC pins, and routing to Hadrons build guidance.
scope: [software:hadrons]
load_when: Selecting or building Hadrons, or deciding between upstream Hadrons and the milc-qcd fork for HadronsMILC work.
evidence: source
sources:
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/configure.ac
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/Makefile.am
observed: "2026-10-23"
observed_on:
  software:
    hadrons:
      commit: 3a0980157914dd54e96744fccaf0fbf88620b5a5
      branch: feature/LMI-develop
      forked_from_default: 28d2806401806592f9caddc8eeedd4277efd341d
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
---

# Hadrons

Hadrons runs lattice-QCD measurements as modules — actions, solvers, sources, propagators,
contractions, I/O — named in an XML parameter file. It builds a dependency graph from the
modules' declared inputs and outputs, schedules them, and frees each object once nothing
downstream needs it. It is built on Grid. HadronsMILC adds staggered/MILC modules on top and
links Hadrons' library into its own executable.

## Two code lines

Claims in `software/hadrons/` are labelled **upstream and fork** or **fork-only**, as for
Grid.

- **Upstream:** `aportelli/Hadrons`, default branch `develop`.
- **Fork:** `milc-qcd/Hadrons` `feature/LMI-develop`, the line HadronsMILC pins (0.3.0 pins
  3a098015). It lacks some upstream modules — the baryon contractions among them — so three of
  its own tests do not compile (see [`build.md`](build.md)).

Build against the Hadrons commit in HadronsMILC's `DEPENDENCIES` file, with the Grid commit
pinned beside it.

## Where to look

- [`build.md`](build.md): bootstrap, configure, the commit stamp, and what to expect from its tests.
- [`build-profiles.yaml`](build-profiles.yaml): the option set for a HadronsMILC stack.
