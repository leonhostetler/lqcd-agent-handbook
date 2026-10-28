---
title: An LMI meson-field global sum took 27% of a 162-board job, inside Open MPI's HAN allreduce
summary: One HadronsMILC LMI run on 162 gpu-gb200 boards spent 11,397 s of its 11.6 h in the meson-field global sum, a host MPI_Allreduce of 3.456 and 4.608 GB per block running at about 180 MB/s per rank; a standalone benchmark later reproduced it and traced it to Open MPI's HAN collective component.
scope: [machine:horizon, software:hadronsmilc]
load_when: A HadronsMILC A2A meson-field job on Horizon logs a Global Sum Time of many seconds per block, or any multi-board job on Horizon spends far longer than expected in a large host-buffer MPI_Allreduce.
evidence: observed
sources:
  - operator-submitted HadronsMILC LMI production-volume run on 162 gpu-gb200 boards, 2026-10-25 to 2026-10-26, and its log, reviewed in the working directory
  - operator-submitted MPI_Allreduce diagnostic jobs on 2 to 162 gpu-gb200 boards, 2026-10-27, reviewed in the working directory
observed: "2026-10-26"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
    hadrons:
      commit: 3a0980157914dd54e96744fccaf0fbf88620b5a5
      branch: feature/LMI-develop
      forked_from_default: 28d2806401806592f9caddc8eeedd4277efd341d
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain:
    cuda: "13.3"
    openmpi: "5.0.11"
    ucx: "1.22.0"
---

# An LMI meson-field global sum took 27% of a 162-board job, inside Open MPI's HAN allreduce

**An occurrence, seen once in an application, then diagnosed with a benchmark.** The durable
fact, with its scope and what was not compared, is in [`../notes.md`](../notes.md), "Open MPI's
HAN component and large host-buffer allreduces". This file records what it looked like.

The job was a HadronsMILC LMI run of the whole workflow on a 144³×288 HISQ ensemble:

- the Lanczos, two `StagA2AMesonFieldLegacy` modules and 144 sources;
- 162 `gpu-gb200` boards, 648 ranks, four per board, launched with `srun` and a per-rank binding
  wrapper;
- TACC's `openmpi/5.0.11` environment, unchanged.

It completed, and its eigenvalues and the correlators compared matched an earlier run
bitwise.

1. **The meson-field step took 15,125 s.** Its per-block `Global Sum Time` lines added up to
   **11,397 s**, 27% of the job's 41,731 s.
2. **The sizes and times per block:**
   - 256 blocks of 4.608 GB took 25.28 s each, and 256 blocks of 3.456 GB took 18.86 s each
     (medians);
   - the first block of each size took 104.2 s and 30.1 s;
   - both sizes ran at about 180 MB/s per rank. A bandwidth-limited sum should run at GB/s rates,
     and the one-board benchmark did: 6 GB/s.
3. **Nothing reported a fault.** The time appears only in the per-block log lines.

**How it was diagnosed.** A standalone benchmark made the same call: one in-place host
`MPI_Allreduce` of doubles at the same sizes, in a fresh process.

- With the default environment it took 22.35 s and 29.64 s per call on 162 boards: 1.17–1.19
  times the application's time.
- In the same job, excluding HAN (`OMPI_MCA_coll=^hcoll,han`) gave 1.18 s and 1.52 s.
- An earlier job on 2 to 16 boards had shown the same split.
- `coll_base_verbose` confirmed that HAN served the world communicator.

**Still open.** No application run with HAN excluded has been measured, so the saving in the
workflow and the effect on its other phases are inferred, not observed.

**If it recurs or is retested, capture:**

- the per-block `Global Sum Time` lines, separating the first block of each size;
- a short leg with `OMPI_MCA_coll_base_verbose=20`, to record which component served the
  communicator;
- the job's environment value of `OMPI_MCA_coll`.
