---
title: Horizon performance references
summary: What the Horizon gpu-gb200 production build achieves on the staggered-CG throughput probe, at one GPU, one board, two and four boards, for 1 and 12 right-hand sides, and on three production ks_spectrum workloads, and how to tell a slow run from a normal one; rows live in performance.yaml.
scope: [machine:horizon, software:milc, software:quda]
load_when: Judging whether a MILC or QUDA staggered CG run on Horizon is slower than it should be, comparing Horizon's throughput with another machine's, or adding a performance row for Horizon.
evidence: reproduced
observations: 32
sources:
  - operator-submitted probe run, three jobs on 2026-10-10, reviewed in the working directory; raw outputs are not committed
observed: "2026-10-10"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
---

# Horizon performance references

`performance.yaml` holds the rows; the table below is generated from it. Every row names
[`milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4`](stacks/milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4/notes.md),
which reaches its QUDA build through
[`quda-cuda13-milc-cg-mrhs-tile3-2026q4`](stacks/quda-cuda13-milc-cg-mrhs-tile3-2026q4/notes.md);
build options are read there, never here. The probe is defined in
[`../../software/milc/probes/staggered-cg-throughput.md`](../../software/milc/probes/staggered-cg-throughput.md).

## Reading the rows

- **Compare like with like.** A probe row compares with another machine's probe row of the same
  probe version, as stacks on machines, never bare hardware. A production run compares with a
  row only when its solver path, right-hand-side count, precision, local volume and placement
  match; the probe's 40⁴ per rank is not a production volume.
- **How tight the reference is.** Each row is one run per point: within it the kept solves
  spread under 0.5 % (the min–max column), but no second run on other boards exists yet, so
  board-to-board variation is unmeasured. A shortfall of a few percent stays unresolved until
  the probe is repeated on other boards; a one-GPU run far below its row, where nothing is
  shared, is diagnosed before its numbers are trusted.
- **What the ladder shows on this build.** The per-rank rate falls from one GPU to four boards,
  more for 12 right-hand sides than for 1: a 12-right-hand-side block exchanges a halo 12 times
  as large, and at four boards two dimensions cross the network. QUDA's own invert test agreed
  with every MILC figure within 5 %, so the falloff is not on the MILC side.
- **Campaign rows** compare only with the same workload: the same solve shape and residual on the
  same lattice and placement, on this stack or a later one. They keep only solves long enough to
  measure throughput; solves of a hundred or so iterations swung between 2,700 and 7,800 GFLOP/s
  across identical calls and are left out. Each row's workload says which.
- **Locating a drop.** Re-run the probe and read its legs as the probe page describes: slower on
  one GPU points at the device or board; one GPU fine but one board slow, at on-board links or
  binding; one board fine but two or four slow, at the network or the MPI transport.

## Rows

<!-- BEGIN GENERATED performance table: tools/build-performance-tables.py renders this from performance.yaml; edit the YAML, never this block -->

#### `milc-cuda13-quda-mrhs-tile3-ks-spectrum-2026q4`

| Row | Kind | Solver | Masses | RHS | Precision (sloppy) | Nodes | Ranks | `node_geometry` | Local volume | Off-node dims | Metric | Value (min–max) | Solves / runs | Iterations | Observed |
|---|---|---|---:|---:|---|---:|---:|---|---|---|---|---|---|---|---|
| `probe-device-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 1 | 1 | 1 1 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7436.7 (7434.2–7440.1) | 5 / 1 | 2,665 | 2026-10-10 |
| `probe-device-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 1 | 1 | 1 1 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 15396.2 (15393.2–15403.8) | 3 / 1 | 2,671 | 2026-10-10 |
| `probe-node-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 1 | 4 | 2 2 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 5789.8 (5780.6–5793.1) | 5 / 1 | 2,678 | 2026-10-10 |
| `probe-node-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 1 | 4 | 2 2 1 1 | 40×40×40×40 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 13641.1 (13635.5–13643.6) | 3 / 1 | 2,685 | 2026-10-10 |
| `probe-2-nodes-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 2 | 8 | 2 2 1 2 | 40×40×40×40 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 5307.8 (5305.5–5313.3) | 5 / 1 | 2,683 | 2026-10-10 |
| `probe-2-nodes-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 2 | 8 | 2 2 1 2 | 40×40×40×40 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 10401.8 (10372.5–10410.9) | 3 / 1 | 2,694 | 2026-10-10 |
| `probe-4-nodes-milc-rhs1` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 1 | double (half) | 4 | 16 | 2 2 2 2 | 40×40×40×40 | z, t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 4295.6 (4279.1–4305.2) | 5 / 1 | 2,695 | 2026-10-10 |
| `probe-4-nodes-milc-rhs12` | probe staggered-cg-throughput 1.1.0 | `fn_QUDA` | 1 | 12 | double (half) | 4 | 16 | 2 2 2 2 | 40×40×40×40 | z, t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7801.2 (7790.5–7832.2) | 3 / 1 | 2,698 | 2026-10-10 |
| `campaign-multishift-10-masses` | campaign | `multicg_offset_QUDA` | 10 | 1 | double (single) | 2 | 8 | 1 1 2 4 | 80×80×40×36 | t | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 7365.5 (5826.9–7400.2) | 470 / 10 | 25,288 | 2026-10-10 |
| `campaign-light-mass-rhs3` | campaign | `fn_QUDA` | 1 | 3 | double (half) | 1 | 4 | 1 1 2 2 | 80×80×40×72 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 14427.5 (14194.6–14442.1) | 70 / 10 | 20,794 | 2026-10-10 |
| `campaign-rhs9` | campaign | `fn_QUDA` | 1 | 9 | double (half) | 1 | 4 | 1 1 2 2 | 80×80×40×72 | none | `congrad5_gflops_per_rank` (GFLOP/s per rank) | 14398.8 (12,499–14,595) | 1430 / 10 | 1,034 | 2026-10-10 |

Each row's full record — workload or probe version, warm state, binding, statistic and
evidence — is in `performance.yaml`; build options are read from the named stack.

<!-- END GENERATED performance table -->
