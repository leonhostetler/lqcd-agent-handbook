---
title: Working on Vista
summary: Node-target declaration, agent placement, whole-node charging, launcher, and storage rules for TACC Vista.
scope: [machine:vista]
load_when: Building software or preparing a job on Vista.
evidence: docs
sources:
  - https://docs.tacc.utexas.edu/hpc/vista/
  - https://docs.tacc.utexas.edu/basics/conduct/
  - Vista Lmod module metadata (module spider python3; module show TACC)
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

## Load a new enough Python before launching the agent

Load the modules in the shell that starts the agent session, before starting it:

```bash
module load gcc/15.1.0 cuda/12.9 python3
```

The handbook's tools need Python 3.10 or newer, and the system interpreter is older. The
`python3` module exists only under the `gcc` branch of Vista's module hierarchy, while
TACC's default modules load the `nvidia` compiler. The default's own attempt to load
`python3` therefore fails without an error, and only the system interpreter remains. The
session-logging checker and installer never load modules. The submission guard can
discover module interpreters, but not one hidden behind a compiler the shell has not
loaded. Without this line, session logging cannot be installed or checked, and the guard
cannot run. The guard refuses a submission when it cannot run, so every submit is blocked.
This is needed in every session, not only at installation, because the guard runs at each
intercepted submit. [reproduced ×2 on 2026-09-28: an operator session, and a
module-discovery probe under TACC's default modules that found only the system interpreter]

Loading `gcc` replaces the default `nvidia` compiler in the shell the agent inherits. A
build must therefore load its own compiler and MPI explicitly, as its validated stack
records, rather than rely on the inherited environment.

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
