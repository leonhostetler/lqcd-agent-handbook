---
title: pyfm's contract step ran its last two gammas 7–9 times slow, swapping while its input files' page cache filled one NUMA node
summary: A one-rank pyfm a2aLL contract on one gpu-gb200 board ran its last two gammas 7.2 and 9.2 times slower than the first five, with correct outputs. Sampled reruns traced it to swap with hundreds of GiB of clean meson-field page cache left on one NUMA node; dropping that cache removed it.
scope: [machine:horizon, software:pyfm]
load_when: A pyfm contract step, or any single process on Horizon that reads hundreds of GB of files and then needs more than one NUMA node's memory, runs several times slower than expected with no error, or its VmSwap is non-zero.
evidence: observed
sources:
  - operator-submitted pyfm contract jobs on single gpu-gb200 boards, with in-job per-NUMA-node meminfo, vmstat and page-cache samplers, 2026-10-27 and 2026-10-28, reviewed in the working directory
observed: "2026-10-27"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  software:
    pyfm:
      commit: 9282eac110f95e536607ac9acfee26024677cd13
      branch: main
  toolchain:
    python: "3.12.14"
    coreutils: "9.5"
---

# pyfm's contract step ran its last two gammas 7–9 times slow, swapping while its input files' page cache filled one NUMA node

**An occurrence, then diagnosed with sampled reruns.** The durable fact, its scope and what was
not tested are in [`../notes.md`](../notes.md), "Page cache left on one NUMA node can push a
large process into swap". The pyfm side is in
[`../../../software/hadronsmilc/applications/lmi.md`](../../../software/hadronsmilc/applications/lmi.md).
This file records what it looked like.

The job was pyfm's `contract` step of the HadronsMILC LMI workflow on a 144³×288 HISQ ensemble:

- three diagrams and seven gammas of `a2aLL` correlators, from meson fields written by an earlier
  run;
- one rank on one CPU-only board, launched as
  `srun --cpu-bind=none numactl --cpunodebind=0,1 --interleave=0,1`, with 64 threads.

It completed, and its outputs later matched every rerun bitwise.

1. **The first five gammas contracted in a normal time; the last two took 7.2 and 9.2 times
   as long.** The whole step took 2.4 times what the five normal gammas imply.
2. **Nothing reported a fault.** Used host memory sat flat, tens of GiB below the normal peak,
   for most of the two slow gammas. The only other sign was NUMA node 1 ending with little free
   memory.

**How it was diagnosed.** The job had no memory sampler, so the last two gammas were rerun on
other boards with one. Each rerun sampled per-node meminfo, `vmstat` and the process's
`/proc/<pid>/status` every 5 s.

- On a fresh board they ran in a normal time.
- After a `cat` of the other five files, the first ran 9.4 times as long.
  - It swapped up to 68 GiB, with about 408 GiB of clean cache held on node 1.
  - Under `--interleave=0,1`, 444 against 35 GiB of its anonymous memory went to node 0.
- A later job ran the same pair twice on one board, once with the cache dropped every 30 s and
  once without.
  - Without, it swapped 39 GiB. This time the cache stayed on node 0.
  - With eviction, nothing swapped.
- A rerun of the full seven-gamma step with eviction ran every gamma in a normal time and swapped
  nothing.
- The original job is attributed to the same mechanism by its shape and by that rerun. It was
  not itself sampled.

**Still open.**

- Why the node holding the cache was never reclaimed.
- In the control without eviction, the gamma that did not swap still ran 25% slower than with
  eviction, with its anonymous memory skewed across the two nodes. Skewed placement without
  swap is a candidate cause, not established.

**If it recurs, capture:**

- per-node `MemFree`, `FilePages` and `AnonPages` from `/sys/devices/system/node/node*/meminfo`;
- `pswpin`, `pswpout` and `pgmajfault` from `/proc/vmstat`;
- the process's `VmRSS` and `VmSwap`;
- `fincore` of the input files before and after each read.
