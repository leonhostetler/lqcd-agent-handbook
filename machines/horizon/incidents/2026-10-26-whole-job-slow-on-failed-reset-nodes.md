---
title: A whole CG job ran 20–30 times slow on a node set the site then drained for failed GPU resets
summary: One 27-node gpu-gb200 job in which every staggered CG solve ran 20–30 times slower than on healthy nodes, with GPUs nearly idle at full clock on every host, and five of its nodes were drained with "GPUs failed to reset" a minute after it ended; per-host telemetry could not single them out.
scope: [machine:horizon]
load_when: A multi-node GPU job on Horizon runs many times slower than expected from its first solve, with low GPU utilisation and full clocks on every node, or `sinfo -R` gives "GPUs failed to reset" for a job's nodes.
evidence: observed
observed: "2026-10-26"
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
  toolchain:
    cuda: "13.3"
    openmpi: "5.0.11"
    ucx: "1.22.0"
    nvidia-driver: "615.71.09"
---

# A whole CG job ran 20–30 times slow on a node set the site then drained for failed GPU resets

**An unexplained occurrence, seen once.** It is not a rule.

A 27-node `gpu-gb200` job, 108 ranks, one rank per GPU, ran MILC `ks_spectrum_hisq` mixed-precision staggered CG
through QUDA. A GPU clock sampler ran on every node, started from inside the application step.

1. Every CG solve that finished ran **20–30 times slower** than the same solves at the same placement on other nodes, from the first
   solve. Iteration counts were identical to those of the reference runs.
2. On **every** host, GPU utilisation sat at 1–4 % during the solves, with the SM clock at its maximum, no thermal or
   power slowdown reason, and temperatures under 45 °C. An unnamed reason bit, `0x400`, appeared on some hosts, as it
   also does on healthy nodes. No host's telemetry differed from the others'.
3. Phases that ran on the host alone, such as reading the gauge field, ran at normal speed.
4. About a minute after the job ended, the site drained **5 of its 27 nodes**, all with the reason
   `TACC: GPUs failed to reset`, set by `root`. Nothing in the job's own output mentioned a GPU fault.

Every timed leg after the first hit its time limit before its first solve finished, so the job produced no usable
measurement.

**Ruled out:** the per-node sampler. A later job on other nodes, changing only the sampler (none, every node at 2 s,
every node at 10 s, batch node only), ran every leg at the reference speed and showed no effect beyond its noise floor
of 0.2–0.3 %. A rerun of the original job on a node set excluding the five drained nodes ran within 5 % of the
reference speed.

**Mechanism, `[inferred]`.** Faulty GPUs on some of the five nodes stalled their ranks, and the global reduction in
every CG iteration made every other rank wait for them. That would leave every GPU idle at full clock, and it is why
per-host GPU telemetry looks the same everywhere and cannot point to the bad nodes. The link between the drained nodes
and the slowdown is a correlation with a site-recorded fault: what the fault was, and when it began, are not known.

**What to capture if it recurs:**

- Right after the job ends, `sinfo -R -o "%E | %U | %H | %N" -n <the job's nodes>`, run bare. Save the output: a drain
  reason disappears when the site returns the node to service, and nothing inside the job records it.
- `nvidia-smi -q` on every node at the start and the end of the job, so a failing node's error and remapping state is
  on record.
- A second occurrence with that evidence, and a node-by-node timing that singles out the slow host, would turn the
  correlation into a finding.

**A guard, used in the rerun but not triggered there:** a short, fast solve as the first leg, with the job ending
itself if that leg runs above a few times the healthy rate. On a node set like this one it would cost minutes of the
allocation instead of all of it `[inferred]`.
