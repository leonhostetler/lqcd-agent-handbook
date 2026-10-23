---
title: Hadrons CUDA 13 hadronsmilc-base stack on Horizon
summary: The Horizon gpu-gb200 build of the milc-qcd Hadrons fork at the HadronsMILC 0.3.0 pin, on the Grid stack; how to reproduce it and how far it is validated.
scope: [machine:horizon, software:hadrons]
load_when: Rebuilding Hadrons for HadronsMILC on Horizon, or judging what the hadrons-cuda13-hadronsmilc-base-2026q4 stack covers.
evidence: experiment
sources:
  - https://github.com/milc-qcd/Hadrons/blob/3a0980157914dd54e96744fccaf0fbf88620b5a5/configure.ac
  - operator-submitted build job reviewed in the working directory
observed: "2026-10-23"
observed_on:
  machine: horizon
  software:
    hadrons:
      commit: 3a0980157914dd54e96744fccaf0fbf88620b5a5
      branch: feature/LMI-develop
      forked_from_default: 28d2806401806592f9caddc8eeedd4277efd341d
  toolchain:
    cuda: "13.3"
    ucx: 1.22.0
---

# Hadrons CUDA 13 `hadronsmilc-base` on Horizon

Declare `gpu-gb200` first. `stack.yaml` is canonical. Built on
`../grid-cuda13-hadrons-staggered-2026q4/`; consumed by `../hadronsmilc-cuda13-lmi-2026q4/`.

Reproduce: run `./bootstrap.sh` on a login node (it downloads SQLite); in a batch job, with
the Grid stack's `bin/` on `PATH`, run `GIT_DIR=<source>/.git <source>/configure --prefix
<prefix> --with-grid=<grid-prefix>`, `make -j48`, `make install`, then `make -k tests
benchmarks`. Confirm `hadrons-config --git` prints `HEAD 3a0980157914…`.

`lib/libHadrons.a` sha256: `fecf1fd1a63cc23d120bec27f837643125cf8ff19ccabaac279d32e76f744216`.

This stack is validated only through HadronsMILC: its own test programs were built, not run.
