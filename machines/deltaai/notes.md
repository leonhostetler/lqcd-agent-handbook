---
title: Working on DeltaAI
summary: Compute-target resolution and Grace Hopper build and run prerequisites for DeltaAI.
scope: [machine:deltaai]
load_when: Building software or preparing a job on DeltaAI.
evidence: docs
sources:
  - https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/architecture.html
  - https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/running-jobs.html
  - https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/job-accounting.html
  - https://docs.ncsa.illinois.edu/systems/deltaai/en/latest/user-guide/prog-env.html
observed: "2026-08-17"
observed_on:
  machine: deltaai
review_by: "2027-02-17"
---

# Working on DeltaAI

The machine profile is canonical for hardware, scheduler, filesystem, and policy values.

## Resolve the compute target

A DeltaAI login node has no GPU and does not itself establish a compute target. Because the
machine profile currently contains exactly one `node_types` entry, `gpu-gh200` is the
default when the operator has not made an explicit selection. No separate operator
declaration is needed. Validation remains specific to the node type actually run.

A full node contains four GH200 superchips. Each combines one 72-core Grace CPU NUMA
domain with one 96 GB H100 GPU, and the smallest allocatable unit is one superchip.
Requesting CPU cores or host memory beyond one superchip's share can increase the charged
GPU fraction even when fewer GPUs are requested. Once a job starts, reconcile the resolved
node type and requested fraction with accelerator and NUMA telemetry before treating the
run as validation.

## Place builds deliberately

Use the Cray compiler wrappers and the NVIDIA 9.0 target recorded in the profile. The
default environment supplies `PrgEnv-gnu`, `cudatoolkit`, and
`craype-accel-nvidia90`; exact versions belong in a validated stack, not the machine
profile.

GPU-aware Cray MPICH requires `MPICH_GPU_SUPPORT_ENABLED=1`, and the application must link
`libmpi_gtl_cuda`. Keep compile-time and runtime module settings aligned. A compute-node
build is a scheduler job and therefore requires an explicit campaign budget before
submission.

**The login node caps each user's memory, and the cap stalls work instead of failing it.** All
of one user's processes on a login node share one control group. Its `memory.high` is 16 GiB
and its `memory.max` is 20 GiB (read from the user slice, `[reproduced ×2]`, 2026-10-03 and
2026-10-05, the second on `gh-login02`). Above `memory.high` the kernel throttles every process
in the group and reclaims from it, killing none; at `memory.max` it kills. A parallel build that
crosses the first limit therefore freezes everything the user runs on that node, including an
agent session and its shell. It looks like a hang, not a build error. Two QUDA builds stalled
this way at `-j16`, at the same file and with the agent unresponsive, while the same
configuration later built on a compute node. That the throttle caused it is inferred, because
the group's event counters had been reset before anyone read them. On the login node, keep
parallel jobs × the largest per-process RSS under 16 GiB; the validated stacks record their
per-process peak. A build whose compile processes each need several GiB belongs on a compute
node, as a job under the campaign budget.

## Choose storage by workload

DeltaAI has no `/scratch` filesystem. Use `/work/hdd` for large computational I/O,
`/work/nvme` for many small files, or job-scoped `/tmp` for node-local small-file I/O.
Copy anything needed after the job out of `/tmp`, because it is purged at job end.
Neither `/projects` nor `/work` has snapshots or backups.

The `ghx4-interactive` partition is for short debugging and prototyping. Its two-hour,
four-node, and eight-running-node-hour-per-user limits are recorded in the profile; use
`ghx4` for larger or longer work. It also admits **one job per user, queued or running**. A
second submission is rejected at submit time with `QOSMaxSubmitJobPerUserLimit` and is not
queued, so a campaign of several jobs there is serial. Submit each job only after the previous
one has left the queue, and treat a rejected submission as not submitted. The partition is also
**charged at twice the `ghx4` rate**, a charge factor of 2.0, so a one-GPU job there bills two
GH200-hours per hour. Count it at that rate in a budget ledger, and use `ghx4` when the queue
wait allows.
