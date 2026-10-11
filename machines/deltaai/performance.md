---
title: DeltaAI performance references
summary: What the DeltaAI gpu-gh200 production build achieves on three production ks_spectrum workloads, and how to tell a slow run from a normal one; rows live in performance.yaml.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Judging whether a MILC or QUDA staggered CG run on DeltaAI is slower than it should be, comparing DeltaAI's throughput with another machine's, or adding a performance row for DeltaAI.
evidence: reproduced
observations: 1970
sources:
  - operator-submitted production jobs, one 10-configuration job per campaign, analyzed under a benchmark contract frozen before extraction and reviewed in the working directory; raw outputs are not committed
observed: "2026-10-11"
observed_on:
  machine: deltaai
  node_type: gpu-gh200
  software:
    milc:
      commit: 6bd16fce292a3bda9d65b426b3d263ee184d3a9a
      branch: fix/baryon-normalization
      forked_from_default: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
---

# DeltaAI performance references

`performance.yaml` holds the rows; the table below is generated from it. Every row names
[`milc-cuda12-quda-mrhs-tile3-ks-spectrum-2026q4`](stacks/milc-cuda12-quda-mrhs-tile3-ks-spectrum-2026q4/notes.md),
which reaches its QUDA build through
[`quda-cuda12-milc-cg-mrhs-tile3-2026q4`](stacks/quda-cuda12-milc-cg-mrhs-tile3-2026q4/notes.md);
build options are read there, never here. No probe rows exist yet: the staggered-CG throughput
probe ([`../../software/milc/probes/staggered-cg-throughput.md`](../../software/milc/probes/staggered-cg-throughput.md))
has not been run on DeltaAI.

## Reading the rows

- **Campaign rows compare only with the same workload**: the same solve shape and residual on
  the same lattice and placement, on this stack or a later one. They keep only solves long
  enough to measure throughput; each row's workload says what is left out.
- **Against another machine's campaign rows of the same workload**, the comparison is between
  stacks at their own production placements, never bare hardware: each machine places a
  campaign on as many devices as its memory requires, so local volume, ranks and the dimensions
  that cross the network differ.
- **How tight the reference is.** Each row is one job of 10 configurations, so the min–max
  column is spread within one job; job-to-job spread is unmeasured. A run of the same workload
  far below the row's minimum is diagnosed before its numbers are trusted.
- **Locating a drop.** Once probe rows exist, re-run the probe and read its legs as the probe
  page describes. Until then, compare the run's iteration counts with the row's first: a changed
  iteration count is a different solve, not a slower machine.

## Rows

<!-- BEGIN GENERATED performance table: tools/build-performance-tables.py renders this from performance.yaml; edit the YAML, never this block -->

#### `milc-cuda12-quda-mrhs-tile3-ks-spectrum-2026q4`

| Row | Kind | Solver | Masses | RHS | Precision (sloppy) | Nodes | Ranks | `node_geometry` | Local volume | Off-node dims | Metric | Value (min–max) | Solves / runs | Iterations | Observed |
|---|---|---|---:|---:|---|---:|---:|---|---|---|---|---|---|---|---|
| `campaign-multishift-10-masses` | campaign | `multicg_offset_QUDA` | 10 | 1 | double (single) | 3 | 12 | 1 1 4 3 | 80×80×20×48 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 3826.6 (3548.9–3882.2) | 470 / 10 | 25,262 | 2026-10-11 |
| `campaign-light-mass-rhs3` | campaign | `fn_QUDA` | 1 | 3 | double (half) | 2 | 8 | 1 1 2 4 | 80×80×40×36 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7389.9 (7052.3–7404.8) | 70 / 10 | 20,920 | 2026-10-11 |
| `campaign-rhs9` | campaign | `fn_QUDA` | 1 | 9 | double (half) | 2 | 8 | 1 2 2 2 | 80×40×40×72 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7639.1 (6758.7–7,781) | 1430 / 10 | 1,034 | 2026-10-11 |

Each row's full record — workload or probe version, warm state, binding, statistic and
evidence — is in `performance.yaml`; build options are read from the named stack.

<!-- END GENERATED performance table -->
