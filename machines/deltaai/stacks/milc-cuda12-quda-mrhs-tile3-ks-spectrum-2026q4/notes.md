---
title: MILC ks_spectrum on the tile-3 QUDA stack on DeltaAI
summary: The DeltaAI gpu-gh200 ks_spectrum_hisq and GB-baryon builds at MILC 6bd16fce on QUDA 00c7ef33 with a three-wide multi-right-hand-side tile, which the production campaigns and DeltaAI's performance rows run on.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Rebuilding, validating, or running with the milc-cuda12-quda-mrhs-tile3-ks-spectrum-2026q4 stack on DeltaAI.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/commit/6bd16fce292a3bda9d65b426b3d263ee184d3a9a
  - operator-run builds, production runs and probe runs reviewed in the working directory
observed: "2026-10-11"
observed_on:
  machine: deltaai
  software:
    milc:
      commit: 6bd16fce292a3bda9d65b426b3d263ee184d3a9a
      branch: fix/baryon-normalization
      forked_from_default: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 12.9
---

# MILC `ks_spectrum` on the tile-3 QUDA stack on DeltaAI

`stack.yaml` is canonical for versions, the passed make variables, the record checks and the
validation. It composes
[`quda-cuda12-milc-cg-mrhs-tile3-2026q4`](../quda-cuda12-milc-cg-mrhs-tile3-2026q4/notes.md)
and builds both profile targets, `ks_spectrum_hisq` and
`ks_spectrum_hisq_gb_baryon_blind_no_sink_links`, from one script with the same 30 make
variables. Differences from
[`milc-cuda12-quda-ks-spectrum-2026q4`](../milc-cuda12-quda-ks-spectrum-2026q4/stack.yaml):

- **MILC `6bd16fce`**, one commit on develop `6b9b8a06` that reduces KS baryon correlators over
  ranks once rather than twice, so a multi-rank nucleon is no longer multiplied by the rank
  count. The commit has since reached develop.
- **`LDFLAGS` is `-g`, passed through the environment.** The build script sets every make
  variable in `make`'s environment rather than on its command line, so the Makefile's own
  `LDFLAGS +=` OpenMP additions still apply and the link line carries `-fopenmp -lgomp`. Passed
  on the command line, the same `-g` replaces them and fails on OpenMP symbols, which is why
  [`milc-cuda12-quda-ks-spectrum-2026q4`](../milc-cuda12-quda-ks-spectrum-2026q4/notes.md) names
  the runtime; the precedence rule is in
  [`../../../../software/milc/build.md`](../../../../software/milc/build.md). Keep the two forms
  apart when reproducing either stack.
- **No `CUDA_*` paths are passed**; the Cray wrappers and the loaded `cudatoolkit` module
  supply them.

## What the validation shows

The staggered-CG throughput probe ran `ks_spectrum_hisq` on one GPU, one node, two nodes and
four nodes: every leg completed and every solve converged, and its consistency leg, one field at
all four geometries, gave plaquettes within 1.4e-15 relative and pion correlators within 2.2e-19
of the correlator scale of the one-rank leg. Three production campaigns, 10 configurations each,
were accepted under a frozen benchmark contract: 12 ranks on three nodes and 8 ranks on two,
multi-shift CG and 3- and 9-right-hand-side CG through `invertMultiSrcQuda`, every solve
converged, and the campaign tunecaches were read and not rewritten. The GB-baryon target was
exercised by one campaign only, with no cross-geometry check. MILC's printed NERSC checksum is
unreliable on more than one rank on this stack's `libqmp`
([`../../../../software/qmp/binary-reduction.md`](../../../../software/qmp/binary-reduction.md)).
