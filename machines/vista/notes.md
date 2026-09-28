---
title: Working on Vista
summary: Node-target declaration, agent placement, whole-node charging, launcher, and storage rules for TACC Vista.
scope: [machine:vista]
load_when: Building software or preparing a job on Vista.
evidence: docs
sources:
  - https://docs.tacc.utexas.edu/hpc/vista/
  - https://docs.tacc.utexas.edu/basics/conduct/
observed: "2026-09-28"
observed_on:
  machine: vista
review_by: "2027-03-28"
---

# Working on Vista

The machine profile is canonical for hardware, scheduler, filesystem, and policy values.

## Declare the compute target

Vista has two node types, `gpu-gh200` and `cpu-gg`, so select one explicitly before
resolving a build or stack. The login nodes are themselves Grace Grace nodes. A login
host therefore looks like a `cpu-gg` node, and that resemblance says nothing about the
intended target.

A `gpu-gh200` node holds one GH200 superchip: one 72-core Grace CPU and one Hopper GPU.
Hardware that has four GPUs per node elsewhere has one here, so rank and decomposition
arithmetic carried over from a four-way GH200 machine is wrong by that factor. The CPU and
GPU memories appear as separate NUMA nodes, so a host-memory figure read from a NUMA or
`free`-style listing must say which node it counted. Once a GPU job starts, reconcile the
declared node type with accelerator telemetry before treating the run as validation.

## Run agent sessions on compute nodes

TACC requires every AI-assisted workload to run on compute nodes, never on login nodes. Its
suggested workflow is to start an `idev` session and run the agent there. That session is a
job, and it consumes allocation for as long as it holds the node. That includes time the
agent spends reading or waiting.

## Size requests in whole nodes

TACC does not share nodes. Every job is charged for whole nodes at the partition's rate, with
a minimum of a quarter hour per job, whether or not every core or GPU is used. The rates and
per-partition limits are in the profile; TACC's `qlimits` utility reports the current limits
and may be ahead of the documentation.

Do not request specific nodes by name, whether in a batch script, an `idev` invocation, or an
MPI hostfile. TACC deletes such jobs from the queue unless staff approved the request in
advance. Jobs inherit the environment present at submission. TACC advises against managing
that environment with Slurm's export option, so load modules in the script instead.

## Launch MPI deliberately

TACC documents `ibrun` as its Vista-aware MPI launcher, taking rank and node counts from the
job's directives. The handbook's scheduler surface records `srun`, and the batch-script
dry-run harness models `srun`'s step semantics only. A script that launches with `ibrun`
therefore goes through a launcher whose step behaviour the harness has not modelled. State
which launcher a script uses, and do not treat a dry-run receipt as evidence about `ibrun`.

## Place builds deliberately

Compiling on a login node is permitted at low parallelism. TACC names `make -j 12` as an
example of a prohibited login-node build, and it throttles per-process memory there. A
parallel build of a large GPU code belongs on a compute node. A compute-node build is a
scheduler job, and therefore requires an explicit campaign budget before submission.

TACC recommends the most recent NVIDIA compiler and OpenMPI modules. These may be newer than
the defaults. Exact module versions belong in a validated stack, not in the profile.

## Choose storage by workload

Run jobs from `$SCRATCH`, not from `$WORK`. `$WORK` is a Lustre filesystem shared with most
other TACC systems. `$HOME` and `$SCRATCH` are VAST filesystems and do not accept Lustre
striping commands. `$SCRATCH` purges files whose access time is more than ten days old, and
deliberately altering access times to evade the purge is prohibited. Node-local `/tmp` is
cleared when the job ends; copy out anything needed afterwards.

Follow the universal
[bounded filesystem-discovery convention](../../conventions/filesystem-discovery.md).
