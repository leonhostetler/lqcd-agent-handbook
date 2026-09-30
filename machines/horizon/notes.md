---
title: Working on Horizon
summary: Early-access drift between TACC's Horizon guide and the live scheduler (4-GPU boards, debug partitions, no $WORK), node-target declaration, submission, agent placement, ibrun rank placement on a four-GPU board, build, and storage rules for TACC Horizon, including the open defect that makes multi-node QIO single-file writes on its VAST filesystems unsafe.
scope: [machine:horizon]
load_when: Building software or preparing a job on Horizon.
evidence: docs
sources:
  - https://docs.tacc.utexas.edu/hpc/horizon/
  - https://docs.tacc.utexas.edu/basics/conduct/
  - https://developer.nvidia.com/cuda-gpus
  - Horizon Lmod module listing and live Slurm partition and node records, read from a login node 2026-09-28
  - the site's installed ibrun script, read 2026-09-28
  - operator-submitted build, validation and diagnostic jobs on gpu-gb200 nodes, 2026-09-29, reviewed in the working directory
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
observed: "2026-09-29"
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
> MILC `save_mpiio` was clean on Vista's VAST NFS because MPI-IO there locks each write; it has
> not been run on Horizon.
> `[observed]` on Horizon: an eight-rank QUDA gauge write on `$HOME` over two nodes returned
> status 0 and failed its read-back checksum (`-14`); the single-rank test passed.
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

**Inside a job the board looks like this.** `[reproduced ×3]`: in-job `nvidia-smi` and
`lscpu` on build and validation jobs. Four GB200 GPUs of 185 GiB each, every pair joined by
NVLink (`NV6`); GPUs 0-1 attach to socket 0 (cores 0-71) and GPUs 2-3 to socket 1 (cores
72-143). A rank therefore belongs on the socket of the GPU it drives, which *Launch MPI deliberately*
below sets up.

**The guide's GB host memory is ambiguous**: its prose gives 120 GiB per Grace CPU and its
table 240 GiB per node, so the profile records neither. On a board `free` reported 1692 GiB
and `lscpu` 34 NUMA nodes, of which only 0 and 1 hold CPUs. GPU memory exposed as NUMA memory
would account for the excess over the documented LPDDR, but that was not verified, so the
host memory behind each socket remains unresolved. Do not budget host memory from `free`.

**Do not write `$WORK` into a script.** The shell sets it during early access, but the
directory does not exist. The profile therefore declares no variable for it.

Expect every row of the table to change. When TACC opens the documented queues, update the
profile and this section together.

## Declare the compute target

Horizon documents two node types, `gpu-gb200` and `cpu-vv`. Select one explicitly before
resolving a build or stack. The login nodes are Grace Grace nodes, which are neither type,
so a login host says nothing about the intended target. During early access only
`gpu-gb200` hardware is schedulable.

## Submit and account

Batch submission works from a login node `[reproduced]`. Give the project name exactly as
`/usr/local/etc/taccinfo` prints it: TACC's submit filter matches it case-sensitively and
rejects any other spelling as an unknown project, even when it names the right allocation
`[observed]`.

## Set the OpenMP thread count

TACC's default environment exports `OMP_NUM_THREADS=1`, and a job inherits it. Every job must
set its own thread count; GNU `nproc` honours the variable too, so inside a job it reports one
CPU however many the job holds `[reproduced]`.

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

**`ibrun`'s own rank placement is wrong for a four-GPU board.** With several tasks per node it
passes `--map-by socket:PE=<cores per task>` unless `OPENMPI_AFFINITY` is already set
`[source]`, which alternates ranks between the two sockets. QUDA gives local rank *n* GPU *n*,
so local ranks 1 and 2 land on the socket away from their GPU. Export
`OPENMPI_AFFINITY="--map-by slot:PE=36 --bind-to core"` before `ibrun` at four ranks per node:
each rank then holds the 36 cores beside its GPU `[reproduced]`, recorded by a per-rank wrapper.

**A subset launch is always unbound.** `ibrun -n N -o M` replaces any mapping with
`--bind-to none` `[source]`, so every rank may use all 144 cores. Several such ranks with
`OMP_PROC_BIND` set pin their threads to the same cores and serialise the threads that drive
the GPUs: a four-rank MILC run spent about 13 ms per multi-GPU dslash instead of about 40 us
`[experiment]`. Set `OMP_PROC_BIND=false` for a subset launch, or use the whole allocation.
[`../../conventions/batch-scripts.md`](../../conventions/batch-scripts.md) owns the mechanism.

## Place builds deliberately

GB200 GPUs are compute capability 10.0, so a GPU build targets `sm_100`; an `sm_90` build
from Vista or DeltaAI does not run correctly here. The login nodes share the Grace
architecture of the GB nodes and run the same software stacks. Compile on a login node only
at low parallelism; TACC's conduct guide prohibits highly parallel builds there. A parallel
build of a large GPU code belongs on a compute node. A compute-node build is a scheduler job,
and therefore requires an explicit campaign budget before submission.

Several CUDA, NVIDIA compiler, and Open MPI versions are installed. Choose them from a
validated stack, and record exact module versions in the stack, not in the profile.

**The `cmake/4.4.0` module was unusable** when the first stacks were built: its binaries lacked
execute permission, so `cmake` silently resolved to `/usr/bin/cmake` 3.30.5 `[observed]`. QUDA
needs 3.18 or newer, so the validated stacks use the system cmake explicitly. Check
`type -a cmake` before relying on the module.

**Inside an agent sandbox, unload `xalt` before linking.** XALT's `ld` wrapper writes under a
hard-coded `/tmp`, which a sandbox that confines writes makes read-only, and every link then
fails, including CMake's compiler checks `[reproduced]`. A batch job is unaffected, so keep XALT
loaded there.

## Choose storage by workload

Run jobs from `$SCRATCH`. It purges files whose access time is more than ten days old, and
deliberately altering access times to evade the purge is prohibited. `$HOME` is small and
not for parallel or high-intensity I/O. Neither accepts Lustre striping commands.
Node-local `/tmp` is cleared when the job ends; copy out anything needed afterwards.

Follow the universal
[bounded filesystem-discovery convention](../../conventions/filesystem-discovery.md).
