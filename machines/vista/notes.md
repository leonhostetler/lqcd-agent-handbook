---
title: Working on Vista
summary: Node-target declaration, agent placement, the operator submission hand-off, whole-node charging, launcher, and storage rules for TACC Vista.
scope: [machine:vista]
load_when: Building software or preparing a job on Vista.
evidence: docs
sources:
  - https://docs.tacc.utexas.edu/hpc/vista/
  - https://docs.tacc.utexas.edu/basics/conduct/
  - Vista Lmod module metadata (module spider python3; module show TACC)
  - direct observation of batch submission from a compute node, in an operator's working-project session
  - the site's installed ibrun script and the Open MPI 5.0.9 runtime's Slurm launch options, read 2026-09-28
  - job-step accounting of six operator multi-node jobs on 2 and 4 nodes, one prted step per ibrun call
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

## Hand every batch submission to the operator

The batch submit command does not run on a compute node. Inside an `idev` session it prints
a site notification and submits nothing:

```text
NOTIFICATION: sbatch not available on compute nodes. Use a login node.
```

An agent session runs on a compute node, so it cannot submit. This holds even when a campaign
ceiling and a declared account would otherwise let it. Plan every submission as an operator
hand-off:
- prepare the script;
- pass the batch-script checker and the dry-run harness;
- record the reservation;
- give the operator the absolute-path submit command to run in a shell on a login node.

A command the operator runs through the agent session's own shell, for example a `!`-prefixed
command, also runs on the compute node and is refused the same way. Debit the ledger when the
operator reports the job was submitted. Do not try to reach a login node from the compute node
to get around the refusal.

This is the site's refusal, not the agent sandbox: it also occurred in the operator's shell,
outside the sandbox. Read-only scheduler queries still work from the same session.
[reproduced ×2 on 2026-09-28: a bare submit from the agent session, and the same command in
the operator's own shell, both on one `gpu-gh200` node in one `idev` session. Not yet
observed on `cpu-gg` nodes, or inside a batch job. TACC's Vista guide shows submission from a
login node but does not state the restriction.]

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
job's directives. With the Open MPI stacks it runs `mpirun` over a hostfile it builds from
the allocation. It forwards the environment with `-x` and passes `--bind-to none` at one task
per node. It writes those hostfiles under `$HOME/.slurm` and removes them on exit, so it
writes outside a job's run root on every call. `[source]`: the site's installed script.

**Each `ibrun` call on a multi-node job creates one Slurm job step**, named `prted` (Open
MPI's remote daemons). The step spans every node except the batch node, where rank 0's
daemon runs inside `mpirun` outside any step. `[reproduced ×6]`: the jobs' own step
accounting, on 2 and 4 nodes. The step claims its nodes: `mpirun` passes no
`--overlap` option, and `ibrun` clears `PRTE_MCA_plm_slurm_args`, the one variable that could
add it. So a second `ibrun` cannot share those nodes while an earlier one is still running.
`[inferred]` from those launch options and Slurm's step rules; no concurrent `ibrun` has been
run. Until it has, **never background an `ibrun`**, a sampler for instance, while later legs
launch. Run legs one after another, and keep a node sampler a plain background process on
the batch node (`conventions/batch-scripts.md`). A single-node job needs no remote daemons,
so it presumably creates no step; that case has not been observed.

The machine profile records `ibrun` as `scheduler.site_launcher`, and the batch-script dry-run
harness stubs it from that record. Each call is logged as a step, and a second step is
refused unless the run passes `--allow-sequential-steps`, which a script that launches its
legs in turn needs. The stub runs nothing, so a guard that reads a launched program's output,
such as a placement check, needs that output supplied with `--launcher-output`. The harness
still does not model the launch itself: rank placement, environment forwarding, and binding
are what `ibrun` does on the machine, and a receipt says nothing about them.

**Choose the MPI module from a validated stack, not from the module list.** Each TACC Open MPI
build is linked to one UCX version, which need not be the one the loaded `ucx` module names,
and the one behind the GNU 14 / CUDA 12 `openmpi/5.0.5` breaks GPUDirect RDMA; see
[`gpu-aware-mpi.md`](gpu-aware-mpi.md). For multi-rank GPU work use the CUDA 13 stacks,
[`quda-cuda13-milc-cg-2026q3`](stacks/quda-cuda13-milc-cg-2026q3/notes.md) and
[`milc-cuda13-quda-ks-spectrum-2026q3`](stacks/milc-cuda13-quda-ks-spectrum-2026q3/notes.md).

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
