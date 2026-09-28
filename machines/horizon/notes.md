---
title: Working on Horizon
summary: Early-access drift between TACC's Horizon guide and the live scheduler (4-GPU boards, debug partitions, no $WORK), node-target declaration, agent placement, launcher, build, and storage rules for TACC Horizon, including the open defect that makes multi-node QIO single-file writes on its VAST filesystems unsafe.
scope: [machine:horizon]
load_when: Building software or preparing a job on Horizon.
evidence: docs
sources:
  - https://docs.tacc.utexas.edu/hpc/horizon/
  - https://docs.tacc.utexas.edu/basics/conduct/
  - https://developer.nvidia.com/cuda-gpus
  - Horizon Lmod module listing and live Slurm partition and node records, read from a login node 2026-09-28
  - the site's installed ibrun script, read 2026-09-28
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
observed: "2026-09-28"
observed_on:
  machine: horizon
review_by: "2026-12-31"
---

# Working on Horizon

The machine profile is canonical for the documented hardware, scheduler, filesystem, and
policy values. During early access the live machine differs from it; this leaf owns those
differences.

> **WARNING — open upstream defect
> ([qio#19](https://github.com/usqcd-software/qio/issues/19),
> [quda#1655](https://github.com/lattice/quda/issues/1655)).** `$HOME` and `$SCRATCH` are
> VAST filesystems mounted over NFS, and a multi-node QIO single-file write on NFS silently
> corrupts the file. That covers every QUDA gauge-field save, QUDA single-file vector saves,
> and MILC `save_parallel_*`. **Horizon has no Lustre escape**: `$WORK` is unavailable in
> early access, and TACC's guide lists it as VAST too. Write such files through one writer or
> as partfiles; see
> [`../../software/qio/parallel-singlefile-writes.md`](../../software/qio/parallel-singlefile-writes.md).
> `[inferred]` from the NFS mounts and the defect's mechanism; not yet reproduced on Horizon.
> Keep this warning until the upstream issue is fixed and validated on Horizon.

## Early access: the live machine is not the documented one

Horizon is in early access, limited to internal users. TACC's guide is marked in progress
and says queue limits may change without notice. On 2026-09-28 the live scheduler differed
from the guide in ways that change job sizing:

| | TACC's guide (the profile) | Live scheduler, 2026-09-28 |
|---|---|---|
| GB node | 1 Grace CPU, 72 cores, 2 GPUs | 2 sockets, 144 cores, 4 GB200 GPUs: a whole NVL4 board |
| GB node count | about 2,000 | 1,008 |
| GB queues | `gb`, `gb-dev`, `gb-large` | `debug` (whole node) and `debug-shared` (shared) |
| Vera Vera nodes | 4,752, queues `vv*` | none in the scheduler |
| `$WORK` | VAST, later in 2026 | the variable is set but names a path that does not exist |
| `qlimits` | the source of live limits | not installed on the login node |

**Size a job from what the scheduler allocates, not from the profile.** One scheduler
node today holds four GPUs, twice the profile's `per_node`. Rank counts, decompositions,
and memory estimates built on the documented value are wrong by that factor. Before sizing,
check the live layout with a bare `sinfo -o "%P %D %c %G"` and a bare `scontrol show
partition`. Once a job runs, reconcile the node with `nvidia-smi`. A scheduler query run
under the agent sandbox must be the whole command; see
[`../../conventions/agent-sandbox.md`](../../conventions/agent-sandbox.md).

**The guide's GB host memory is ambiguous**: its prose gives 120 GiB per Grace CPU and its
table 240 GiB per node, so the profile records neither. Read it from the node before a
host-memory estimate depends on it.

**Do not write `$WORK` into a script.** The shell sets it during early access, but the
directory does not exist. The profile therefore declares no variable for it.

Expect every row of the table to change. When TACC opens the documented queues, update the
profile and this section together.

## Declare the compute target

Horizon documents two node types, `gpu-gb200` and `cpu-vv`. Select one explicitly before
resolving a build or stack. The login nodes are Grace Grace nodes, which are neither type,
so a login host says nothing about the intended target. During early access only
`gpu-gb200` hardware is schedulable.

## Run agent sessions on compute nodes

TACC strongly recommends running AI-assisted work on compute nodes rather than login nodes.
Every SU such a process consumes is charged to the allocation, including an `idev` session
held while the agent reads or waits.

Whether the batch submit command works from a Horizon compute node has not been
established. Vista's refuses it (see [`../vista/notes.md`](../vista/notes.md)). Test it once
before planning a campaign around agent submission.

## Launch MPI deliberately

TACC's `ibrun` wrapper is installed. With Open MPI it runs `mpirun` over a hostfile built
from the allocation and written under `$HOME/.slurm`. It forwards the environment with `-x`,
passes no step-sharing option, and clears `PRTE_MCA_plm_slurm_args`, the one variable that
could add one. `[source]`: the site's installed script. This is the same launch path as on
Vista, where each multi-node `ibrun` call creates one Slurm step that claims its nodes.
`[inferred]` to hold here; not yet observed on Horizon. Until it has been, never background
an `ibrun` while later legs launch.

The profile records `ibrun` as `scheduler.site_launcher`, and the batch-script dry-run
harness stubs it from that record.

## Place builds deliberately

GB200 GPUs are compute capability 10.0, so a GPU build targets `sm_100`; an `sm_90` build
from Vista or DeltaAI does not run correctly here. The login nodes share the Grace
architecture of the GB nodes and run the same software stacks. Compile on a login node only
at low parallelism; TACC's conduct guide prohibits highly parallel builds there. A parallel
build of a large GPU code belongs on a compute node. A compute-node build is a scheduler job,
and therefore requires an explicit campaign budget before submission.

Several CUDA, NVIDIA compiler, and Open MPI versions are installed. Choose them from a
validated stack, and record exact module versions in the stack, not in the profile.

## Choose storage by workload

Run jobs from `$SCRATCH`. It purges files whose access time is more than ten days old, and
deliberately altering access times to evade the purge is prohibited. `$HOME` is small and
not for parallel or high-intensity I/O. Neither accepts Lustre striping commands.
Node-local `/tmp` is cleared when the job ends; copy out anything needed afterwards.

Follow the universal
[bounded filesystem-discovery convention](../../conventions/filesystem-discovery.md).
