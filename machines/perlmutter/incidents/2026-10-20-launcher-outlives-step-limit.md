---
title: A faulted GPU kept the launcher from returning past its step limit
summary: One 288-node gpu-a100-40 job in which a GPU fault left a cancelled step's launcher waiting until the job's walltime ended, so no later leg ran.
scope: [machine:perlmutter]
load_when: A Perlmutter job step reaches its step time limit but the next leg never starts, or a job log shows CUDA_ERROR_CONTAINED or "GPU requires reset".
evidence: observed
observed: "2026-10-20"
observed_on:
  machine: perlmutter
  toolchain:
    cpe: "25.09"
    cray-mpich: "9.0.1"
    cuda: "12.9"
    nvidia-driver: "580.178.04"
---

# A faulted GPU kept the launcher from returning past its step limit

**An unexplained occurrence, seen once.** It narrows a claim in
[`batch-scripts.md`](../../../conventions/batch-scripts.md); it is not a rule.

A multi-leg job on 288 `gpu-a100-40` nodes, one rank per GPU. Each leg's launcher step passed
`--kill-on-bad-exit=1` and a 40-minute `--time`, as that leaf requires.

1. About six minutes into the first leg, one rank reported `CUDA_ERROR_CONTAINED` from a device
   synchronize inside a QUDA gauge-field halo exchange.
2. From then on, the node's job log carried hundreds of `NVML: Failed to get usage: GPU requires
   reset` lines.
3. At 40 minutes, Slurm logged the step `CANCELLED ... DUE TO TIME LIMIT`, and `srun` reported its
   tasks terminated.
4. `srun` did not return. The script never reached its next leg, and the job ran on for another
   50 minutes until its own time limit cancelled it.

The whole allocation was lost, and no leg after the first started.

**Mechanism, `[inferred]`.** A process blocked in the driver on a faulted device does not die
until the device is reset, so the step never finished and `srun` waited on it. The step's
accounting state and the process state were not captured, so this is unconfirmed.

**What to capture if it recurs:** the step's state in the accounting record, and whether the
launcher was still waiting on it. A second observation with that evidence would make an outer
bound worth designing and testing.
