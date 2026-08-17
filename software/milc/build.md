---
title: Building MILC ks_spectrum_hisq with QUDA
summary: Software-specific build and validation procedure for the composed MILC ks_spectrum_hisq and QUDA profile.
scope: [software:milc, software:quda]
load_when: Compiling, linking, or validating the QUDA-enabled MILC ks_spectrum_hisq application.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/compile_ks_spectrum_hisq.sh
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/systems/Frontier/sample.in
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c
observed: "2026-08-17"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
    quda:
      commit: 7733f60bb744204576f82574ece8d8bd454fbcfd
      branch: develop
---

# Building MILC `ks_spectrum_hisq` with QUDA

Follow `playbooks/build-lqcd-stack.md` for source selection and the shared workflow. Use a
disposable full MILC checkout for the build because the upstream application procedure
copies the repository `Makefile` into the application directory and builds there. Do not
modify the source checkout that the operator placed in scope.

Resolve the canonical application options and composed QUDA capability requirements from
`build-profiles.yaml`. Resolve compilers, accelerator target, dependency prefixes, flags,
and build placement from the selected machine stack.

## Build the application

Starting from a clean disposable checkout at the selected commit:

```bash
milc_source=${MILC_SOURCE_DIR:?set MILC_SOURCE_DIR}
milc_install=${MILC_INSTALL_DIR:?set MILC_INSTALL_DIR}
quda_install=${QUDA_INSTALL_DIR:?set QUDA_INSTALL_DIR}

cd "$milc_source/ks_spectrum"
cp ../Makefile ./Makefile

export QUDA_HOME="$quda_install"
export QMPPAR="$quda_install"
export QIOPAR="$quda_install"
export OFFLOAD=<accelerator-backend>
export MY_CC=<c-compiler>
export MY_CXX=<cxx-compiler>
export COMPILER=<makefile-compiler-family>
export OPT=<compile-flags>
export LDFLAGS=<mpi-link-flags>
export LIBQUDA=<quda-and-accelerator-link-flags>
export CGEOM=<fixed-geometry-defines>
export KSCGMULTI=<multimass-policy-define>
export CTIME=<timing-defines>
export PRECISION=<profile-value>
export MPP=<profile-value>
export OMP=<profile-value>
export WANTQUDA=<profile-value>
export WANT_FN_CG_GPU=<profile-value>
export WANT_FL_GPU=<profile-value>
export WANT_GF_GPU=<profile-value>
export WANT_FF_GPU=<profile-value>
export WANT_MIXED_PRECISION_GPU=<profile-value>
export WANT_GAUGEFIX_OVR_GPU=<profile-value>
export WANT_GSMEAR_GPU=<profile-value>
export WANTQMP=<profile-value>
export WANTQIO=<profile-value>

make -j <jobs> ks_spectrum_hisq
install -m 0755 ks_spectrum_hisq "$milc_install/bin/ks_spectrum_hisq"
```

The nearest validated stack is canonical for all concrete values above. Confirm that the
result has no unresolved shared libraries before spending a job allocation.

## Validate the composed stack

Run the exact upstream machine sample input on the stack's declared compute-node type. A
valid acceptance checks both layers:

- the application payload exits zero and prints `RUNNING COMPLETED`;
- QUDA reports the expected number of CG solves, each solve reports convergence, and the
  maximum reported true residual is below the requested tolerance;
- the HISQ fermion-link path reports QUDA execution; and
- the correlator file exists and has the structure implied by the input.

At the observed MILC commit, `total_iters` is not an acceptance signal for this application
path. `solve_ksprop` initializes that local counter to zero and returns it without
incrementing it, while QUDA prints the actual iterations for each solve. A wrapper that
requires positive `total_iters` can therefore fail after a successful application payload.
Use the QUDA convergence and true-residual records instead, and record wrapper and payload
exit states separately.

Treat a fresh QUDA tunecache run as validation rather than benchmark evidence. Linkage does
not prove runtime coverage: explicitly state whether the sample exercised QIO, smearing,
force paths, and the P2P-enabled communication path.
