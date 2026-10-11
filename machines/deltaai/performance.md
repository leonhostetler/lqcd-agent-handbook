---
title: DeltaAI performance references
summary: What the DeltaAI gpu-gh200 production build achieves on the staggered-CG throughput probe, at one GPU, one node, two and four nodes, for 1 and 12 right-hand sides, and on three production ks_spectrum workloads, and how to tell a slow run from a normal one; rows live in performance.yaml.
scope: [machine:deltaai, software:milc, software:quda]
load_when: Judging whether a MILC or QUDA staggered CG run on DeltaAI is slower than it should be, comparing DeltaAI's throughput with another machine's, or adding a performance row for DeltaAI.
evidence: reproduced
observations: 2002
sources:
  - operator-submitted probe run, three jobs on 2026-10-11, reviewed in the working directory; raw outputs are not committed
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
build options are read there, never here. The probe is defined in
[`../../software/milc/probes/staggered-cg-throughput.md`](../../software/milc/probes/staggered-cg-throughput.md).

## Reading the rows

- **Compare like with like.** A probe row compares with another machine's probe row of the same
  probe version, as stacks on machines, never bare hardware. A production run compares with a
  row only when its solver path, right-hand-side count, precision, local volume and placement
  match; the probe's 40⁴ per rank is not a production volume.
- **Against Horizon, use the probe rows.** At every probe point DeltaAI's per-rank rate is 0.60
  to 0.70 of Horizon's, except 12 right-hand sides on four nodes (0.54). The two machines'
  campaign rows of one workload sit near 0.5 because each places it differently (here two
  nodes with t off node, on Horizon one board), so a ratio taken from them mixes placement into
  the device comparison.
- **Campaign rows compare only with the same workload**: the same solve shape and residual on
  the same lattice and placement, on this stack or a later one. They keep only solves long
  enough to measure throughput; each row's workload says what is left out.
- **Against another machine's campaign rows of the same workload**, the comparison is between
  stacks at their own production placements, never bare hardware: each machine places a
  campaign on as many devices as its memory requires, so local volume, ranks and the dimensions
  that cross the network differ.
- **How tight the reference is.** Each probe row is one run per point, and each campaign row one
  job of 10 configurations, so the min–max column is spread within one run or job (under 2 %
  for the probe); run-to-run and node-to-node spread is unmeasured. A run of the same workload
  far below the row's minimum is diagnosed before its numbers are trusted.
- **What the ladder shows on this build.** The per-rank rate falls from one GPU to four nodes,
  more for 12 right-hand sides than for 1, and most at four nodes, where z joins t off node.
  QUDA's own invert test agreed with the MILC figure within 2 % at every point but one: with 12
  right-hand sides on four nodes it ran 17 % below MILC, warm and with about 1 % spread. One run
  does not say whether that repeats; until it is repeated, do not read a slow QUDA invert test
  at that point as a fault.
- **Locating a drop.** Compare the run's iteration counts with the row's first: a changed
  iteration count is a different solve, not a slower machine. Then re-run the probe and read
  its legs as the probe page describes: slower on one GPU points at the device or node; one GPU
  fine but one node slow, at on-node links or binding; one node fine but two or four slow, at
  the network or the MPI transport.

## Rows

<!-- BEGIN GENERATED performance table: tools/build-performance-tables.py renders this from performance.yaml; edit the YAML, never this block -->

#### `milc-cuda12-quda-mrhs-tile3-ks-spectrum-2026q4`

| Row | Kind | Solver | Masses | RHS | Precision (sloppy) | Nodes | Ranks | `node_geometry` | Local volume | Off-node dims | Metric | Value (min–max) | Solves / runs | Iterations | Observed |
|---|---|---|---:|---:|---|---:|---:|---|---|---|---|---|---|---|---|
| `probe-device-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 1 | 1 | 1 1 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 4806.2 (4765.3–4847.8) | 5 / 1 | 2,668 | 2026-10-11 |
| `probe-device-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 1 | 1 | 1 1 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 9644.6 (9626.6–9,673) | 3 / 1 | 2,673 | 2026-10-11 |
| `probe-node-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 1 | 4 | 2 2 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 4028.6 (4010.3–4036.7) | 5 / 1 | 2,675 | 2026-10-11 |
| `probe-node-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 1 | 4 | 2 2 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 8212.6 (8,207–8222.4) | 3 / 1 | 2,688 | 2026-10-11 |
| `probe-2-nodes-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 2 | 8 | 2 2 1 2 | 40×40×40×40 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 3594.2 (3546.2–3603.2) | 5 / 1 | 2,686 | 2026-10-11 |
| `probe-2-nodes-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 2 | 8 | 2 2 1 2 | 40×40×40×40 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 6600.1 (6,532–6603.8) | 3 / 1 | 2,702 | 2026-10-11 |
| `probe-4-nodes-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 4 | 16 | 2 2 2 2 | 40×40×40×40 | z, t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 2921.1 (2,902–2951.4) | 5 / 1 | 2,697 | 2026-10-11 |
| `probe-4-nodes-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 4 | 16 | 2 2 2 2 | 40×40×40×40 | z, t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 4224.9 (4193.7–4249.6) | 3 / 1 | 2,699 | 2026-10-11 |
| `campaign-multishift-10-masses` | campaign | `multicg_offset_QUDA` | 10 | 1 | double (single) | 3 | 12 | 1 1 4 3 | 80×80×20×48 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 3826.6 (3548.9–3882.2) | 470 / 10 | 25,262 | 2026-10-11 |
| `campaign-light-mass-rhs3` | campaign | `fn_QUDA` | 1 | 3 | double (half) | 2 | 8 | 1 1 2 4 | 80×80×40×36 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7389.9 (7052.3–7404.8) | 70 / 10 | 20,920 | 2026-10-11 |
| `campaign-rhs9` | campaign | `fn_QUDA` | 1 | 9 | double (half) | 2 | 8 | 1 2 2 2 | 80×40×40×72 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7639.1 (6758.7–7,781) | 1430 / 10 | 1,034 | 2026-10-11 |

Each row's full record — workload or probe version, warm state, binding, statistic and
evidence — is in `performance.yaml`; build options are read from the named stack.

<!-- END GENERATED performance table -->
