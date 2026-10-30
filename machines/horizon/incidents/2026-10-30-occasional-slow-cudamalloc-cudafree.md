---
title: An occasional cudaMalloc or cudaFree took 10-200 ms on NUMA-mode GB200 boards
summary: In one single-board microbenchmark, 4-15 of 160 field-sized cudaMalloc or cudaFree calls took 10-124 ms in two of six fill levels, and 17 of 3,016 1 GiB allocations took over 100 ms, with no kernel reclaim or compaction and no tie to how full the GPU was; the cause is not identified.
scope: [machine:horizon]
load_when: A Grid, HadronsMILC or other CUDA job on Horizon shows occasional slow allocations or per-call setup time that grows with rank count.
evidence: observed
sources:
  - an operator-submitted single-board CUDA allocation and device-fill microbenchmark on a gpu-gb200 board, with in-job per-node meminfo and vmstat samplers, 2026-10-30, reviewed in the working directory
observed: "2026-10-30"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  toolchain:
    cuda: "13.3"
    nvidia_driver: "610.57.04"
---

# An occasional cudaMalloc or cudaFree took 10-200 ms

**What happened.** A standalone CUDA program on one NUMA-mode board, four processes, filled each
GPU with 1 GiB allocations to 0, 100, 144, 170, 170 and 180 thousand MiB, then timed `cudaMalloc`,
`cudaFree` and first use at 2 to 128 MiB, 20 repetitions each.

- The medians were flat across fill levels: under 1 ms per call at 16 and 32 MiB.
- At the 144 and 180 thousand MiB levels, 4 to 15 of 160 calls at 16 and 32 MiB took 10 to 124
  ms. That raised the mean `cudaMalloc` from 0.23 to 3.4–4.1 ms and the mean `cudaFree` from 0.15
  to 1.7–5.7 ms.
- The two 170 thousand MiB levels, fuller than 144, had one such call in 320.
- 17 of 3,016 1 GiB allocations took over 100 ms, up to 201 ms, at the 170 and 180 thousand MiB
  levels. The median per 1 GiB was 8.6 ms.
- No kernel reclaim, compaction or allocation-stall counter moved during the job.

**What is not known.** The cause: driver-internal work, the NUMA memory mode, or activity
elsewhere on the board. Whether the tail existed before the late-October 2026 maintenance, on
driver 615.71.09 in CDMM mode: nothing measured it then. Its rate over a longer run: each leg
timed only 1–2 s of calls.

**Why it matters.** A bulk-synchronous job whose ranks allocate on every solve waits at its next
collective for the slowest rank. With hundreds of ranks, some rank would hit a call like this
almost every time. That is the inferred mechanism behind Grid's slow per-solve setup on these
boards (`../../../software/grid/runtime-environment.md`, "The freed-block cache is small"). Time
a longer allocation loop, and run it on a CDMM-mode or driver-615 board if one becomes
available, before treating this as a site defect.
