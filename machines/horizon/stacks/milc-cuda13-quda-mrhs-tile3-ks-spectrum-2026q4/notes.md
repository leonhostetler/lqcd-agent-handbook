---
title: MILC CUDA 13 ks_spectrum stack on the tile-3 QUDA stack on Horizon
summary: The Horizon gpu-gb200 ks_spectrum_hisq build linked against the tile-3 QUDA stack, which the production ks_spectrum campaigns and the throughput probe ran; what differs from the 2026q3 MILC stack, and what its validation covers.
scope: [machine:horizon, software:milc]
load_when: Rebuilding, validating, or launching the milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4 stack on Horizon.
evidence: experiment
sources:
  - operator-submitted build and probe runs reviewed in the working directory
observed: "2026-10-10"
observed_on:
  machine: horizon
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
  toolchain:
    cuda: "13.3"
---

# MILC `ks_spectrum_hisq` on the tile-3 QUDA stack on Horizon

Declare `gpu-gb200` first. Build against the install of
[`quda-cuda13-milc-cg-mrhs-tile3-2026q4`](../quda-cuda13-milc-cg-mrhs-tile3-2026q4/notes.md).
`stack.yaml` is canonical for the passed make variables and the validation; launch as
[`milc-cuda13-quda-ks-spectrum-2026q3`](../milc-cuda13-quda-ks-spectrum-2026q3/notes.md)
describes. What differs from that stack:

- MILC `a5f8f9fa` against QUDA `ba501e4f8` with a three-wide multi-right-hand-side tile.
- The make command passes `WANT_KS_CONT_GPU=false` and `WANTPRIMME=false`, and not the CUDA
  prefixes the 2026q3 stack passed; the link still resolved `-lcuda` and `-lnvidia-ml`.
- It was built in a batch job and not timed or measured.

## What the validation shows

The staggered-CG throughput probe's MILC legs, at 40⁴ per rank on 1, 4, 8 and 16 ranks: every leg
completed and every solve, single and in blocks of 12, converged. Its consistency leg, one 24³×48
field at all four geometries, gave plaquettes equal within 1e-14 and pion correlators identical to
printed precision. MILC's printed NERSC `CKSUM` differed between geometries; that is QMP's
reduction, not the field
([`../../../../software/qmp/binary-reduction.md`](../../../../software/qmp/binary-reduction.md)).
Both profile targets passed the build-record check. Thirty production configurations, ten each from
three campaigns on one and two boards, also passed their correctness checks, among them the
`ks_spectrum_hisq_gb_baryon_blind_no_sink_links` target's only validation.
