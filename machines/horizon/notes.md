---
title: Working on Horizon
summary: Early-access drift between TACC's Horizon guide and the live scheduler (4-GPU boards, debug partitions, no $WORK), node-target declaration, submission, per-user job limits and the project-wide allocation check at submission, agent placement, the board's host memory and NUMA layout (sample host memory per NUMA node, never with free), the GPU driver's memory mode (check every board for NUMA mode before timing; a within-process CG slowdown seen on CDMM-mode boards was absent in NUMA mode), srun and ibrun rank placement on a four-GPU board, MILC and QUDA ranks launched under numactl --localalloc by default (operator policy), CUDA-aware MPI, Open MPI's HAN collective component (exclude it for large host-buffer allreduces at four ranks per board; not compared for small reductions), page cache left on one NUMA node pushing a large process into swap (drop input files' cache after reading them), concurrent ibrun launches on disjoint nodes, what a lost node does to a job, profiling with Nsight Systems (unload XALT first, trace every rank, and never trace MPI on only some ranks), build, and storage rules for TACC Horizon, including node-local /tmp and the open defect that makes multi-node QIO single-file writes on its VAST filesystems unsafe.
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
  - operator-submitted spectroscopy jobs on gpu-gb200 nodes and their scheduler records, 2026-10-09, reviewed in the working directory
  - live Slurm partition, node and job records, read from a login node 2026-10-09
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
  - colleague's world-readable Horizon job logs (nvidia-smi topo -m), read 2026-10-09
  - live Slurm QOS records (sacctmgr show qos), read 2026-10-10
  - an unattended submission loop's refused submission, 2026-10-10, reviewed in the working directory, and the operator's report of the reason its excess jobs waited
  - operator-submitted Nsight Systems probe and capture jobs on gpu-gb200 nodes, 2026-10-09 and 2026-10-12, reviewed in the working directory
  - the site's installed ibrun script, read 2026-10-13
  - operator-submitted placement trials and production jobs running concurrent ibrun launches on gpu-gb200 nodes, with their placement probes and scheduler step records, 2026-10-13 to 2026-10-16, reviewed in the working directory
  - operator-submitted jobs cancelled by node failures, and in-job df -T records of node-local /tmp, 2026-10-15, reviewed in the working directory
  - Horizon login-node module, package and file-mode checks of cmake, and a gpu-gb200 build job's preflight, 2026-10-21
  - operator-submitted Grid, Hadrons and HadronsMILC build and validation jobs on gpu-gb200 nodes, with in-job numactl -H, ompi_info, ucx_info -d and placement probes and their scheduler records, 2026-10-22 and 2026-10-23, reviewed in the working directory
  - operator-submitted Nsight Systems start-up test and profile jobs on gpu-gb200 nodes, with in-job stall stacks and SQLite exports, 2026-10-27, reviewed in the working directory
  - QMP source, QMP_init.c, QMP_split.c and QMP_topology.c, at the revision QUDA pins for the 2026q4 stacks
  - operator-submitted MPI_Allreduce diagnostic jobs on 2 to 162 gpu-gb200 boards, with in-job coll_base_verbose and ompi_info output, and a HadronsMILC LMI production-volume run on 162 boards, 2026-10-26 and 2026-10-27, reviewed in the working directory
  - the openmpi/5.0.11 modulefile, read from a login node 2026-10-27
  - operator-submitted single-process host-memory jobs on gpu-gb200 boards, with in-job per-NUMA-node meminfo, vmstat and page-cache samplers, a page-cache eviction comparison and two confirmation runs, 2026-10-27 and 2026-10-28, reviewed in the working directory
  - https://www.gnu.org/software/coreutils/manual/html_node/dd-invocation.html
  - site staff's description of the GPU memory-mode and thermal-zone checks, relayed by the operator, 2026-10
  - operator-submitted MILC/QUDA CG and staggered-multigrid jobs on 27 and 144 gpu-gb200 boards across a site maintenance, with in-job per-rank memory-policy probes, per-board memory-mode audits, per-node nvidia-smi records and GPU clock telemetry, 2026-10-26 to 2026-10-29, reviewed in the working directory
  - an operator-submitted HadronsMILC LMI run on 162 gpu-gb200 boards after the site maintenance, ended by a node failure, with in-job per-NUMA-node meminfo, free and per-node GPU clock samplers, 2026-10-29, reviewed in the working directory
  - live Slurm controller configuration (scontrol show config), read from a login node 2026-10-29
  - https://slurm.schedmd.com/slurm.conf.html
observed: "2026-10-29"
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
| Per-user limits in `debug` | not given | 20 running jobs, 40 submitted, 1000 nodes, 2 days per job (QOS `qdebug`, read 2026-10-10) |
| Node-local `/tmp` | 130 GiB local storage per node | a local xfs disk, not tmpfs, about 156 GiB free per board (`df -T` in a job on two boards, 2026-10-15) |

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

**A board has about 957 GiB of host memory, and `free` also counts the GPUs' memory**
`[observed]`, `numactl -H` in a job, 2026-10-22. NUMA nodes 0 and 1 (cores 0-71 and 72-143)
hold 488,985 and 490,747 MiB, together 979,732 MiB: exactly the configured memory `sinfo`
reports per board. Each GPU's 184 GiB of HBM appears as a CPU-less NUMA node of 188,416 MiB
(nodes 2, 10, 18 and 26 for GPUs 0-3), and those four account for the rest of the 1692 GiB
`free` reports. That layout is the GPU driver's **NUMA mode**; a board in CDMM mode shows only
nodes 0 and 1 (*Check each board's GPU memory mode before timing*, below). So budget about
957 GiB of host memory per board, about 478 GiB per socket, and do not budget from `free`.
The guide's 120 GiB (prose) and 240 GiB (table) describe neither.
A whole-node job requesting `--mem=0` is nonetheless granted 1562.5 GiB, and TACC's submit
filter attaches 200000 MiB per GPU, so neither grant is the board's host memory either
`[observed]`, 2026-10-09.

**In NUMA mode `free` also counts the GPUs' allocations as used, so it cannot sample host
memory** `[observed]`, one 162-board job's batch node, 2026-10-29. With each GPU holding about
166 GiB, `free` reported about 760 GiB used while NUMA nodes 0 and 1 held about 60 GiB.
Subtracting each GPU's `memory.used` from `nvidia-smi` does not recover host memory either: the
result stayed about 32 GiB above nodes 0 and 1 in every phase of that job, for a reason not
established. Sample host memory per socket instead, as `MemUsed` (`MemTotal` − `MemFree`) of
nodes 0 and 1 in `/sys/devices/system/node/node<N>/meminfo`, and subtract `FilePages` where page
cache should not count. A CDMM-mode board's `free` sees only nodes 0 and 1, so a figure taken
there compares with neither reading.

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

A job may request its GPUs as `--gpus-per-node 4`. The submit filter accepted it, and the job
record shows `gres/gpu:nvidia_gb200:4` `[reproduced ×6]`.

**Keep a submission loop under the per-user job limits.** With `qlimits` absent, read them from
the QOS records with a bare `sacctmgr -P show qos format=Name,MaxJobsPU,MaxSubmitPU,MaxTRESPU,MaxWall`;
the early-access table above gives the `debug` values. The two job limits fail differently
`[observed]`, 2026-10-10:

- **Past the running limit, a job is accepted and waits** with reason `QOSMaxJobsPerUserLimit`.
  That is a full allowance, not a stuck queue, and not a reason to cancel.
- **Past the submit limit, `sbatch` refuses** with `QOSMaxSubmitJobPerUserLimit`, and nothing is
  queued. A loop must not advance its own state on that refusal.

An unattended loop's job cap therefore belongs at or below the submit limit, and counts every
job of the user, not only its own.

**The allocation balance is enforced at submission, across the whole project** `[observed]` by
the operator, during early access. A submission is refused when the reserved cost of the
project's queued and running jobs, every member's, plus the new job would exceed the balance
`taccinfo` prints, whether or not those jobs have actually been debited from the balance. So
one member's large pending job can block another member's submission, and a loop can be refused
for budget while far below the job limits. Whether a running job counts at its full time limit
or only its remaining time has not been established; count the full limit, the conservative
case. Before a large submission, sum nodes × time limit over a bare
`squeue -A <project> -h -o "%D %l %P"` and compare it with the balance. The profile gives no
charge rate for `debug`. The check appears to belong to TACC's submit filter, which prints
"Checking available allocation" on every submission, not to the Slurm QOS, which carries no
`GrpTRESMins` `[inferred]`.

**`sacct` memory figures miss short steps.** The accounting gather interval is
`JobAcctGatherFrequency=task=120` (`scontrol show config`, 2026-10-22), so a step shorter than
two minutes shows `MaxRSS` 0 or blank even after the job has left the queue `[reproduced]`, in
three jobs' records. Record host memory for short steps with the job's own sampler, and report
an empty field as not measured.

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
On Horizon the step covers only the nodes other than the batch node `[reproduced ×6]`:
accounting records of two two-node and four one-node jobs. A two-node `ibrun` created one step,
named `prted`, on the second node. The batch node's ranks ran inside the batch step, and a
one-node `ibrun` created no step at all. Two consequences follow. Never background an `ibrun`
over the job's whole node list while later legs launch: concurrent launches work only on
disjoint nodes, set up as the next paragraph describes. And read a job's
host memory per node from the batch step for the batch node and from the `prted` step for the
others: a one-node job's whole application appears under the batch step.

**Concurrent launches on disjoint nodes work once each is narrowed and pinned.** A job can run
several `ibrun` calls side by side, each on its own subset of the job's nodes, if every launch
sets two things in its own subshell:

- **Narrow the allocation variables to the subset.** `ibrun` builds its hostfile from
  `SLURM_NODELIST` and `SLURM_TASKS_PER_NODE` and takes the slot count from `SLURM_NPROCS`
  `[source]`. Export `SLURM_NODELIST`, `SLURM_JOB_NODELIST`, `SLURM_NNODES`,
  `SLURM_JOB_NUM_NODES`, `SLURM_TASKS_PER_NODE`, `SLURM_NTASKS`, `SLURM_NPROCS` and
  `SLURM_JOB_CPUS_PER_NODE` for the subset. Do not narrow with `ibrun -n/-o`, which drops the
  binding (below).
- **Pin the daemon step to the subset.** The hostfile does not place the remote daemons. For a
  subset that excludes the batch node, PRRTE gave `srun` no node list, and Slurm alternated the
  `prted` step between the job's nodes, so every other launch ran on another subset's nodes
  `[experiment]`, the pin below as the one variable. Pass
  `--prtemca plm_slurm_args --nodelist=<the subset's nodes other than the batch node>` through
  `MY_MPIRUN_OPTIONS`, which `ibrun` appends to its `mpirun` command `[source]`; the variable
  route is closed, because `ibrun` unsets `PRTE_MCA_plm_slurm_args`. Leave it unset for a
  subset that is the batch node alone, whose ranks run under `mpirun` itself.

Pinned, 36 of 36 launches landed on their own nodes with the intended CPU blocks, in one-node,
concurrent one-node and two-node subsets, where the unpinned control misplaced 6 of 6; in
production jobs of up to four concurrent subsets every `prted` step ran on its own subset's
nodes `[reproduced]`. Do not trust the setup alone: record each launch's hosts and allowed
CPUs, or compare the application's rank-0 host with its subset. Each subset's `ibrun` still
creates its own step, so the accounting rule above applies per subset. More than four
concurrent subsets have not been run.

The profile records `ibrun` as `scheduler.site_launcher`, and the batch-script dry-run
harness stubs it from that record.

**`srun` with a per-rank wrapper places a one-board job correctly** `[observed]`, an in-job
placement probe and Grid's own start-up lines, 2026-10-22. Slurm here defaults to PMIx
(`MpiDefault=pmix`) and does not constrain devices or cores (`ConstrainDevices=no`,
`ConstrainCores=no`), so every rank sees all four GPUs until something narrows them.
`srun --cpu-bind=none tools/horizon-gb200-bind.sh <app>` with `--ntasks-per-node=4
--cpus-per-task=36` gave local rank n GPU n, cores 36n..36n+35 and HCA `mlx5_0`, `mlx5_1`,
`mlx5_4`, `mlx5_5`, and Grid reported `Node  communicator of size 4`; Grid, Hadrons and
HadronsMILC validation runs on one and four GPUs used it. The script restricts each rank to
its GPU, as Grid requires; for QUDA it has a mode that leaves all four visible, not run here.
Multi-node `srun` launches were not tested.

**`ibrun`'s own rank placement is wrong for a four-GPU board.** With several tasks per node it
passes `--map-by socket:PE=<cores per task>` unless `OPENMPI_AFFINITY` is already set
`[source]`, which alternates ranks between the two sockets. QUDA gives local rank *n* GPU *n*,
so local ranks 1 and 2 land on the socket away from their GPU. Export
`OPENMPI_AFFINITY="--map-by slot:PE=36 --bind-to core"` before `ibrun` at four ranks per node:
each rank then holds the 36 cores beside its GPU `[reproduced]`, recorded by a per-rank wrapper.

**Launch MILC and QUDA ranks under `numactl --localalloc` by default** `[operator]`, from
2026-10-29 until further notice, except in a run that tests the flag itself:
`ibrun numactl --localalloc <executable> <input>`. Each rank gets an explicit local memory
policy. Placement does not change, but the rank's memory leaves automatic NUMA-balancing scans,
which are on (`kernel.numa_balancing` 1) on the compute nodes. On CDMM-mode boards that removed
a within-process CG slowdown of up to about 30 %. On NUMA-mode boards it cost 0.93–0.96× for CG
and 0.78× for one multigrid solve, with no measured floor. Answers were bitwise identical in every pair
([`incidents/2026-10-27-cg-drift-under-numa-balancing-cdmm.md`](incidents/2026-10-27-cg-drift-under-numa-balancing-cdmm.md)).
Check that it reached every rank: a probe launched the same way prints `policy: local` from
`numactl --show`. `Mems_allowed` shows the cpuset, not the policy. **Do not wrap
`tools/horizon-gb200-bind.sh` in it.** That script ends in its own `numactl --membind`, whose
policy replaces the outer one `[inferred]`. `--membind` is also an explicit policy, so it should
opt out of scanning the same way `[inferred]`, but that was not measured.

**A subset launch is always unbound.** `ibrun -n N -o M` replaces any mapping with
`--bind-to none` `[source]`, so every rank may use all 144 cores. Several such ranks with
`OMP_PROC_BIND` set pin their threads to the same cores and serialise the threads that drive
the GPUs: a four-rank MILC run spent about 13 ms per multi-GPU dslash instead of about 40 us
`[experiment]`. Set `OMP_PROC_BIND=false` for a subset launch, or use the whole allocation.
[`../../conventions/batch-scripts.md`](../../conventions/batch-scripts.md) owns the mechanism.

## A lost node ends the whole job

When one node of a job stops responding, Slurm cancels the whole job (`DUE TO NODE FAILURE`;
`sinfo -R` gives the node as not responding) `[reproduced ×3]`. Every launch dies with it,
those on healthy nodes included, and node-local `/tmp` goes with the job. Before the
cancellation, `ibrun` returned exit status 0 for an application run that was killed when PRRTE
lost that node's daemons `[reproduced ×2]`. A launch's exit status therefore does not show that
the application finished: judge every run by the application's own completion markers and
its artifacts ([`../../conventions/running.md`](../../conventions/running.md)). A job that
carries many work units should record each unit's result as it finishes and copy each unit's
node-local outputs off the node then, so a cancellation costs only the units in flight.

**The job holds every node for at least ten minutes after one dies.** Slurm marks a node down
only after `SlurmdTimeout` passes with no response from it: 600 s here (`scontrol show config`,
2026-10-29; [`slurm.conf`](https://slurm.schedmd.com/slurm.conf.html)). In one 162-board job the
dead node's GPU clock sampler went silent, with normal clocks and temperatures, 819 s before the
cancellation, and the application logged nothing after that moment `[observed]`. Budget a lost
node as the work in flight plus at least ten minutes of the whole allocation. When reconciling
such a job, date the failure from the last sample of per-node telemetry and the application's
last log line, never from the cancellation time.

## Nsight Systems needs XALT unloaded on the GB compute nodes

`module reset` loads TACC's `xalt` module, which puts XALT's `libxalt_init.so` in `LD_PRELOAD`,
so it is loaded into `nsys` and every process `nsys` starts. With it there, `nsys profile` from
the `nvidia/26.9` module (Nsight Systems 2026.4.1) aborts every target within seconds and writes
no report, with:

    terminate called after throwing an instance of 'boost::wrapexcept<QuadDCommon::LogicException>'
    Failed to probe the process (sync). Timeout: 2 sec

`[reproduced ×4]`, 2026-10-09 to 2026-10-12, four jobs on four gpu-gb200 nodes with
`xalt/3.2.4` loaded. It fails alone on `sleep 3` with only `-t cuda`, under `ibrun` with any
combination of `osrt`, `mpi`, `nvtx` and process-tree sampling, and with CPU sampling and
context-switch tracing both off (`--sample=none --cpuctxsw=none`).

**Removing the preload is the fix** `[experiment]`, 2026-10-12: on one node, in one job, between
two failing controls, `env -u LD_PRELOAD` alone made the same command write its report, and so
did `module unload xalt`. With XALT unloaded, four ranks under `ibrun` traced `cuda`, `nvtx`,
`osrt`, `mpi` and process-tree sampling, and a four-rank MILC run with QUDA then traced to
completion with output identical to an untraced run. So **in any job that runs `nsys`, run
`module unload xalt` after loading modules and assert that `LD_PRELOAD` no longer names XALT
before launching it**; a later `module reset` restores it.

Why the preload breaks the probe is not established, so the rule is empirical. It is not Yama
`ptrace_scope`, which is 2 on the compute nodes as on the login node, nor the 64K-page kernel:
both were unchanged between the failing and passing legs. `nsys status -e` reports every check
OK either way, so it does not predict the failure. A missing `TMPDIR` fails with a different
message, `temp_directory_path: Not a directory` (`[observed]` on a login node). Validate a
capture by its `.nsys-rep` files, never by `nsys`'s exit status:
[`../../conventions/profile-capture.md`](../../conventions/profile-capture.md) owns that rule.

**Trace every rank, or leave `mpi` out of a partial trace.** With Open MPI 5.0.11 under
`ibrun`, `nsys profile` (2026.4.1) run with `-t mpi --mpi-impl=openmpi` on some ranks of a MILC
and QUDA job, and not on the others, deadlocks the whole job in QMP's start-up,
`QMP_init_msg_passing`. `MPI_Init`, QMP's duplicate of the world communicator, its first barrier
and its first allreduces all complete. The traced rank then waits forever in Open MPI's
communicator-context agreement, inside QMP's first `MPI_Comm_split`. Tracing every rank starts
and runs, and so does tracing the same subset without `-t mpi`. Process-tree context-switch
tracing, a launch wrapper and the node count (two boards or 27) made no difference.
`[reproduced ×2]`, 2026-10-27: one job tracing 8 of 108 ranks on 27 boards, and one tracing 2
of 8 ranks on two boards with one variable moved per leg. The mechanism is `[inferred]`. The
traced rank's report stores the split communicators with cross-rank fields and the duplicate
without them, which suggests the MPI wrapper does cross-rank work at a split that untraced ranks
never join; that exchange was not observed. Other MPI libraries, Nsight Systems versions and
applications are untested.

Two consequences hold whatever the mechanism. **A traced launch can stall silently at start-up
and spend its whole time limit**, so gate a profiled leg on the application's first start-up
marker, not on its exit. And **Nsight Systems records an MPI call only when it returns**, so a
call that hangs is absent from the report; read the hang from the sampled call stack instead,
here `opal_progress` under `ompi_request_default_wait`.

**Tracing every rank works, and at 27 boards it was cheap** `[reproduced ×2]`, 2026-10-27: 8
ranks on 2 boards, then all 108 ranks on 27 boards, MILC `ks_spectrum_hisq` with QUDA CG.
- **The recipe:**
  - XALT unloaded, as above, and `TMPDIR=/tmp`;
  - one `nsys profile -t cuda,nvtx,osrt,mpi --mpi-impl=openmpi --sample=process-tree` per
    rank, inside the launcher (`ibrun <per-rank wrapper> <application>`);
  - the output named `prof_<rank>` from `OMPI_COMM_WORLD_RANK`, and each rank's `nsys`
    stderr kept in its own log.
- **Numerics:** iterations and correlators were bit-identical to an untraced run, and the
  tunecache was unchanged.
- **Cost per iteration:** +14 % on 2 boards, but +1.9 % on 27 boards, measured against an
  untraced leg of the same job. The overhead depends on the per-rank work, so measure it at the
  scale used.
- **Reports:** about 8 kB per CG iteration per rank. Two 108-rank legs wrote 55 and 73 GB in
  all, so size the capture from rank count × iterations.
- **Finalisation:** on 2 boards, writing the reports after the application exited took about
  2.5 minutes (0.6–0.8 GB per rank). Include that time in the leg's limit.
- **A harmless warning, before the late-October 2026 maintenance:** on driver 615.71.09, nsys
  printed "Installed CUDA driver version (13.4) is not supported by this build of Nsight Systems"
  and still collected every CUDA kernel, copy and runtime call. The driver now reports CUDA 13.3;
  whether the warning is gone has not been checked.
- **Ending a stalled leg:** SIGINT to a running `nsys profile` writes a report of what has run
  so far, and under `prterun` it then ends the whole job within about 10 s (exit 130). Only the
  signalled node's ranks get reports.

Export the reports to SQLite on node-local disk
([`../../conventions/profile-capture.md`](../../conventions/profile-capture.md)).

## UCX devices, and the HPC-X alternative

**TACC's default environment already sets
`UCX_NET_DEVICES=mlx5_0:1,mlx5_1:1,mlx5_4:1,mlx5_5:1`** `[observed]`, 2026-10-09. It is present
in a login shell and in every batch job's recorded environment, although `module show
ucx/1.22.0` sets only `TACC_UCX_*`. A launcher that "adds" this list changes nothing.

GB200 compute nodes carry `mlx5_0`–`mlx5_5`. `nvidia-smi topo -m` places `mlx5_0`–`mlx5_3` on
the NUMA side of GPUs 0–1 and `mlx5_4`–`mlx5_5` on the other. The login node has only `mlx5_0`,
so a script that checks for these devices fails there and passes on a compute node. UCX 1.22's
own default `UCX_MAX_RNDV_RAILS` is already 2 (`ucx_info -c`).

**`openmpi/5.0.11` is CUDA-aware on compute nodes only** `[observed]`, 2026-10-22. It was
configured `--with-cuda` with the CUDA accelerator component built as a loadable module, so
`ompi_info` lists `accelerator: cuda` on a compute node and only `null` on a login node, which
has no GPU driver: test CUDA-awareness inside a job. On a compute node `ucx_info -d` lists the
`cuda_copy`, `cuda_ipc` and `gdr_copy` transports, and Grid's halo exchange passed device
buffers to this MPI correctly on four ranks. `ompi_info` reports that Open MPI was configured
against `/opt/apps/ucx/1.21.0` while the `ucx/1.22.0` module is the one loaded; no fault was
traced to it.

**NVIDIA's HPC-X stack is an alternative MPI with its own traps** `[observed]`:
- **What it is.** After `module use /home1/apps/nvidia/modulefiles`, the module is
  `nvhpc-hpcx-cuda13/26.9`: HPC-X 2.50, with Open MPI `5.0.10rc2`, UCX 1.21 and HCOLL.
  HPC-X's `libmpi` carries the run path `$ORIGIN/../../ucx/mt/lib`, so the ranks it launches
  load UCX's multi-threaded build.
- **Loading it in a sandbox.** The modulefile is Tcl and calls `exec uname`; inside an agent
  sandbox `module load` silently loads nothing. HPC-X's own `hpcx-init.sh` plus `hpcx_load`
  sets up the same environment, but it reads unset variables, so source it with `set -u`
  relaxed. [`../../conventions/agent-sandbox.md`](../../conventions/agent-sandbox.md) owns the
  class.
- **The wrong MPI loads without any error.** An executable built against HPC-X records HPC-X in
  its run path, but `LD_LIBRARY_PATH` outranks a run path, and both stacks ship `libmpi.so.40`
  and `libucp.so.0`. With TACC's `openmpi` or `ucx` module loaded, the HPC-X executable loads
  TACC's libraries. Check `ldd` inside the job and refuse to run when either library resolves
  outside HPC-X.
- **No measured gain.** MILC and QUDA rebuilt against it at the same commits gave no measurable
  speed-up over the TACC stack, for a one-board and a two-node spectroscopy run, one run each.

## Open MPI's HAN component and large host-buffer allreduces

**Exclude HAN for a job whose cost is dominated by large host-buffer allreduces at four ranks
per board.** With TACC's Open MPI it ran those sums about 20 times slower than the `tuned`
component `[reproduced ×2]`: two diagnostic jobs, 2026-10-27, timing a standalone in-place
`MPI_Allreduce` of doubles from `malloc` buffers, barrier-bracketed, slowest rank per call.
The scope is what was measured:

- `openmpi/5.0.11` with `ucx/1.22.0` on `gpu-gb200`;
- four ranks per board, launched with `srun` and the per-rank binding wrapper;
- 512 MiB to 4.608 GB per call, on 1 to 162 boards.

| Boards (ranks) | Bytes per call | HAN (default) | HAN excluded |
|---|---|---|---|
| 2 (8) | 4.608 GB | 19.10 s | 0.86 s |
| 16 (64) | 3.456 GB | 20.27 s | 0.76 s |
| 162 (648) | 3.456 GB | 22.35 s | 1.18 s |
| 162 (648) | 4.608 GB | 29.64 s | 1.52 s |

Medians of 2–4 timed calls, after an untimed first call. With HAN, each rank moved 150–425 MB/s
on 2 to 162 boards. Without it, at 3.456 GB and 4.608 GB, 4.4–5.4 GB/s on 2 to 128 boards and
2.9–3.0 GB/s on 162. Every sum was exact.

**It matches the application.** Inside a HadronsMILC LMI meson-field run on 162 boards, the
same calls took 18.86 s and 25.28 s per block for those two sizes, and their sum was 27% of the
job's charge `[observed]`. The incident
[`incidents/2026-10-26-meson-field-global-sum-slow-under-han.md`](incidents/2026-10-26-meson-field-global-sum-slow-under-han.md)
records it. The standalone process was 1.17–1.19 times slower than the application, so the
application adds nothing measurable on top. The software side is in
[`../../software/hadronsmilc/applications/lmi.md`](../../software/hadronsmilc/applications/lmi.md).

**What selects HAN, and how to exclude it.**

- The `openmpi/5.0.11` modulefile sets `OMPI_MCA_coll=^hcoll` `[source]`: the modulefile, read
  2026-10-27. With that value, `coll_base_verbose` output shows HAN chosen for the world
  communicator and running `allreduce`.
- Export `OMPI_MCA_coll=^hcoll,han` to the ranks. A new value replaces the module's, so keep
  `hcoll` in the list. `tuned` then picks the algorithm.
- The setting covers every collective the process makes, not only the large sums.

**Where HAN is not slow.** On one board it disqualifies itself ("only local processes"), and
the default equals the exclusion. On communicators with one rank per board it is selected and
fast. A quarter-size sum on four concurrent one-rank-per-board communicators of 162 ranks
took 0.435 s with HAN and 0.443 s without. The slow path therefore needs several ranks per
board. Which HAN stage costs the time was not isolated, so the mechanism is
**empirical**. A fixed cost per 64 KiB pipeline segment explains only part:

- with 4 MiB segments (`OMPI_MCA_coll_han_allreduce_segsize=4194304`), 4–16 boards ran 3.5–6
  times faster;
- 2 boards ran no faster with 4 MiB segments;
- at 162 boards, 4 MiB segments still took 5.0 s per 4.608 GB call.

**Not compared, so do not extend the exclusion to them on this evidence:**

- **Small, latency-bound reductions**, such as the per-iteration sums of CG and multigrid. CG and
  MG jobs on Horizon have run with HAN at its default, and HAN against `tuned` has not been
  compared for them. One coarse side cell is not a comparison: a 16-byte sum over 648 ranks took
  about 0.1 ms either way, over 2–4 calls.
- **The rest of a job that excludes HAN.** An LMI job's Lanczos and solves run under the same
  setting. No application run with HAN excluded has been measured, so neither its overall saving
  nor its outputs have been checked.
- Device buffers, other numbers of ranks per board, HPC-X's Open MPI, and other Open MPI
  versions.

## Check each board's GPU memory mode before timing

**A GB200 board's GPU driver runs in NUMA mode or in CDMM mode; read it before timing.** Site
staff named two configurations that make MILC run slow: a board in CDMM mode instead of NUMA mode,
and a board not booted with its thermal zones disabled. Across a site maintenance in late October
2026 the boards moved from CDMM to NUMA mode and the driver from 615.71.09 to 610.57.04
`[observed]`. Every job of one campaign whose memory layout was recorded before it ran on CDMM-mode
boards, and two jobs after it, of 27 and 144 boards, ran on NUMA-mode boards throughout. Two
changes followed, and they differ in reach:

- **A within-process CG slowdown seen on CDMM-mode boards (+30 % per iteration) was absent on
  NUMA-mode boards at both sizes**, the 27-board case rerun on the same inputs and placement
  ([`incidents/2026-10-27-cg-drift-under-numa-balancing-cdmm.md`](incidents/2026-10-27-cg-drift-under-numa-balancing-cdmm.md)).
- **The 144-board job ran about 2× faster than 144- and 216-board jobs before the maintenance**:
  the same staggered-multigrid hierarchy, loaded vectors and placement at 0.50× the recurring
  solve time and 0.36× the setup time, with identical operator-apply, halo and reduction counts,
  and light-mass CG on the same lattice about 1.85× faster per site, with no throttling. **At 27
  boards that did not reproduce.** Apart from the vanished slowdown, the same solves ran at the
  speed of healthy jobs before the maintenance. A 27-board job on boards all in CDMM mode ran its
  unaffected solves only 15–20 % slower than NUMA mode now. So NUMA mode is not shown to make
  MILC/QUDA faster in general. What made the large earlier jobs slow is not established: a few
  slow boards pacing a large job, or thermal state never recorded before, are candidates
  `[inferred]`.

Which of the memory mode, the driver and the thermal setting removed the slowdown is not
separable: they changed together, and no thermal-zone state was recorded before.

**Read it on every board, inside the job** (once per node, before the timed work and again after).
The NUMA-mode column is `[observed]` on every board of a 27-board job, where all 26 thermal zones
per board also read `disabled`. In the CDMM column, the first two rows are the site's description
and the third is `[observed]`:

| Reading | NUMA mode | CDMM mode |
|---|---|---|
| `grep -o 'CoherentGPUMemoryMode:.*' /proc/driver/nvidia/params` | `"numa"` | `"driver"` |
| `cat /sys/module/nvidia_uvm/parameters/uvm_disable_sam_migration` | `N` | `Y` |
| `grep Mems_allowed_list /proc/self/status`, any process | `0-2,10,18,26` | `0-1` |

The third row needs neither driver file and is free to log from any rank, which makes it the
cross-check when the files are unreadable `[observed]`: `0-1` on every rank of a 27-board job
before the maintenance, `0-2,10,18,26` on every rank of the 144-board job after it. Record each
`/sys/class/thermal/thermal_zone*/mode` too; the site's guidance is that every zone should read
`disabled`. Record the driver with `nvidia-smi --query-gpu=driver_version --format=csv,noheader`.

**Before the maintenance, the clock-event reasons also carried bit `0x400`, which NVML's documented
table does not name** `[reproduced]`. On driver 615.71.09 it appeared in every 27-board job that
sampled clocks per node (not in one 2-board job) and in up to 91 % of a batch node's samples, with
the SM clock 0.3–7 % below its maximum.
After the maintenance it was absent from every sample: three legs on 27 boards, sampled per node,
and a 144-board job's batch node. Its meaning is not identified. Linking it to the thermal
management the maintenance disabled is `[inferred]` from the timing alone. A reader that decodes
`clocks_event_reasons.active` must report unnamed bits rather than count those samples as having
no reason. A clock 7 % low cannot by itself explain a 2× slower job.
Do not read the mode from `/sys/devices/system/node/online`: in NUMA mode it lists every node
ID (`0-33`), including those without memory, so it does not show which nodes hold memory
`[observed]`.

**Gate a timed job on the memory mode and record the rest.** Stop before any timed work when a
board is not in NUMA mode. The slowdown above appeared only on CDMM-mode boards, and a
bulk-synchronous job runs at the pace of its slowest board `[inferred]`. A thermal zone not `disabled` labels the
result rather than stopping it, until its effect has been measured. Before the maintenance the
fleet was probably mixed (one board showed the NUMA layout on 2026-10-22, above), which would make
apparently identical jobs differ by node set `[inferred]`.

**Do not compare timings across a change of memory mode or driver** without re-measuring a
reference on each side.

## Page cache left on one NUMA node can push a large process into swap

**Drop a large input file's page cache once it has been read, when the process reading it needs
more host memory than one NUMA node holds.** Otherwise clean cache can stay resident on one node
while the kernel swaps the process. Nothing fails; the process just slows down.

**A controlled comparison** `[experiment]`, eviction the one variable moved: one board, a single
CPU process run as `numactl --cpunodebind=0,1 --interleave=0,1`, reading 147.5 GB HDF5 files from `$SCRATCH` and
then allocating more than one NUMA node's ~478 GiB. Two legs ran in one job on that board,
differing only in eviction:

- **No eviction:** about 393 GiB of clean cache stayed on node 0 for the rest of the leg.
  - Interleaved allocation landed mostly on node 1: 391 against 45 GiB of anonymous memory.
  - Node 1's own cache was reclaimed, then the process swapped, up to 39 GiB of `VmSwap`.
- **Eviction every 30 s:** at most 5 MiB was cached after any pass. Anonymous memory split
  215 / 214 GiB, and nothing swapped.

**The swap has been sampled twice** `[reproduced ×2]`: the leg above, and a diagnostic job on
another board with the nodes the other way round:

- about 408 GiB of cache stayed on node 1;
- 444 against 35 GiB of anonymous memory went to node 0;
- `VmSwap` reached 68 GiB, with about ten threads waiting in `__read_swap_cache_async`.

There was no compaction, transparent-huge-page or NUMA-migration activity in either run.

**With eviction, it did not recur `[reproduced ×2]`.** Two boards ran with the 30 s loop: the full
workload on one, two allocations after a prefill on the other, nine between them. The most cached after any pass was 12 MiB,
anonymous memory split within 1 GiB between the nodes, and no run swapped.

**The kernel settings seen on the compute nodes** `[observed]`, read from `/proc` and `/sys` in
the jobs:

- `vm.swappiness` 60;
- `vm.zone_reclaim_mode` 0;
- `kernel.numa_balancing` 1;
- `vm.min_free_kbytes` 17,301,504;
- `vm.watermark_scale_factor` 10;
- transparent huge pages `madvise`;
- a 100 GiB swap partition;
- the batch step's task cgroup with `memory.max`, `memory.high` and `memory.swap.max` all `max`.

So the job's memory request does not prevent this: no cgroup limit was in play.

**Mechanism: partly observed, partly inferred.**

- *Observed:* allocation falls back away from the node holding the cache.
- *Inferred, not established:* reclaim works per NUMA node. With `zone_reclaim_mode` 0 an
  allocation goes to the other node rather than reclaiming locally, and the node that keeps its
  cache never runs short enough to have it reclaimed. Which node keeps its cache is not
  predictable: it differed between the two boards.

**How to drop it.** For each file, after it is read, run `dd if=<file> iflag=nocache count=0`.
That is coreutils' documented way to drop a whole file's cache, through
`posix_fadvise(POSIX_FADV_DONTNEED)`. It works from any process on the node, for clean pages
only. A background loop in the batch script, every 30 s over the input files, is the form that
was validated. Check the process's `VmSwap` in `/proc/<pid>/status` rather than the job's
memory record. The application case is pyfm's `contract` step
([`../../software/hadronsmilc/applications/lmi.md`](../../software/hadronsmilc/applications/lmi.md));
the incident
[`incidents/2026-10-27-pyfm-contract-swapped-under-page-cache.md`](incidents/2026-10-27-pyfm-contract-swapped-under-page-cache.md)
records what it looked like.

**Not tested:**

- dropping the cache inside the reading process;
- reading with `O_DIRECT`;
- a NUMA policy other than `--interleave=0,1`;
- several processes per board;
- files on other filesystems.

## Place builds deliberately

GB200 GPUs are compute capability 10.0, so a GPU build targets `sm_100`; an `sm_90` build
from Vista or DeltaAI does not run correctly here. The login nodes share the Grace
architecture of the GB nodes and run the same software stacks. Compile on a login node only
at low parallelism; TACC's conduct guide prohibits highly parallel builds there. A parallel
build of a large GPU code belongs on a compute node. A compute-node build is a scheduler job,
and therefore requires an explicit campaign budget before submission.

Several CUDA, NVIDIA compiler, and Open MPI versions are installed. Choose them from a
validated stack, and record exact module versions in the stack, not in the profile.

**The `cmake/4.4.0` module is unusable, and `module reset` loads it.** Its binaries lack execute
permission, so `cmake` silently resolves to the system `/usr/bin/cmake` `[reproduced]`. That was
3.30.5 when the first stacks were built, and 3.31.8 (`cmake-3.31.8-1.el10`) on 2026-10-21 after a
site package update. QUDA needs 3.18 or newer, so the validated stacks use the system cmake. In a
build script, `module unload cmake`, assert that the module is no longer loaded, and record the
live `cmake --version` instead of pinning the version a stack recorded: a guard pinned to 3.30.5
failed its preflight on 3.31.8 `[observed]`.

**Inside an agent sandbox, unload `xalt` before linking.** XALT's `ld` wrapper writes under a
hard-coded `/tmp`, which a sandbox that confines writes makes read-only, and every link then
fails, including CMake's compiler checks `[reproduced]`. A batch job is unaffected, so keep XALT
loaded there, except in a job that runs Nsight Systems (see "Nsight Systems needs XALT unloaded on
the GB compute nodes").

## Choose storage by workload

Run jobs from `$SCRATCH`. It purges files whose access time is more than ten days old, and
deliberately altering access times to evade the purge is prohibited. `$HOME` is small and
not for parallel or high-intensity I/O. Neither accepts Lustre striping commands.
Node-local `/tmp` is a local disk, not a memory-backed tmpfs (early-access table), so a file
written there costs no host memory. It is cleared when the job ends, and lost with a cancelled
one; copy out anything needed as soon as it is complete.

**Stage a writer that reopens its file per record on `/tmp`, not on `$SCRATCH`.** Such a writer
pays the shared filesystem's per-open latency every time. During one slow period that latency
rose from milliseconds to hundreds of milliseconds per open, on many nodes at once for about
half a day, and an output phase that normally takes seconds took most of a job's walltime
`[observed]`; the cause was not visible from inside a job. MILC `ks_spectrum`'s FNAL correlator
writer is one such writer
([`../../software/milc/applications/ks-spectrum.md`](../../software/milc/applications/ks-spectrum.md),
"Rank 0 reopens a destination for every pair"). Write to `/tmp`, then copy each finished file
to `$SCRATCH` and verify the copy before deleting the original.

Follow the universal
[bounded filesystem-discovery convention](../../conventions/filesystem-discovery.md).
