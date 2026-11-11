---
title: Working on Big Red 200
summary: Node-target declaration, the scheduler's core-counted CPUs and shared nodes, GPU affinity that runs opposite to Slurm's default rank order, summed TRES billing, the UCX Cray MPICH default on Slingshot-10, build placement, and storage rules for IU Big Red 200, including why its NFS home must never take a multi-node QIO single-file write.
scope: [machine:big-red-200]
load_when: Building software or preparing a job on Big Red 200.
evidence: reproduced
observations: 2
sources:
  - sinfo, scontrol show partition, scontrol show node and scontrol show config, read twice on 2026-11-11
  - sacctmgr show qos, read twice on 2026-11-11
  - Lmod module list and module avail on a login node, 2026-11-11
  - /proc/mounts and the site quota command on a login node, 2026-11-11
  - one gpu-debug job on a gpu-a100-40 node, 2026-11-11 (nvidia-smi, numactl -H, per-task cpusets, job environment)
  - https://top500.org/system/179949
  - https://top500.org/system/180020
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
observed: "2026-11-11"
observed_on:
  machine: big-red-200
review_by: "2027-05-11"
---

# Working on Big Red 200

The machine profile is canonical for hardware, scheduler, filesystem, and policy values.

> **WARNING — open upstream defect
> ([qio#19](https://github.com/usqcd-software/qio/issues/19),
> [quda#1655](https://github.com/lattice/quda/issues/1655)).** `$HOME` is NFS, and a shared
> file written by several nodes without byte-range locks comes back damaged with no error.
> That covers every QUDA gauge-field save, QUDA single-file vector saves, and MILC
> `save_parallel` and every `save_parallel_*` keyword. **Here the usual NFS escape does not
> apply either:** home is mounted `nolock` with `local_lock=all`, so an `fcntl` byte-range lock
> is taken on the local client only and excludes nobody on another node `[inferred]` from the
> mount options. A locking MPI-IO driver therefore gives no protection on `$HOME`. Write
> multi-node lattice files on `/N/scratch` or `/N/slate` (Lustre, mounted with `flock`), through
> one writer, or as partfiles; see
> [`../../software/qio/parallel-singlefile-writes.md`](../../software/qio/parallel-singlefile-writes.md).
> Keep this warning until the upstream issue is fixed and a multi-node write on Big Red 200's
> home is validated.

## Declare the compute target

Big Red 200 has two node types, `cpu` and `gpu-a100-40`, so select one explicitly before
resolving a build or stack. The login nodes are x86 EPYC hosts with no GPU, so a login host
looks like a `cpu` node. That says nothing about the intended target.

A `gpu-a100-40` node has one 64-core EPYC 7713 in four NUMA domains and four A100-SXM4-40GB
GPUs, 40,960 MiB each, connected all-to-all by NVLink. Reconcile the resolved node type with
`nvidia-smi` once a job runs.

## GPU affinity runs opposite to Slurm's rank order

On a `gpu-a100-40` node, GPU *i*'s CPU affinity is NUMA domain 3 − *i*: GPU 0 sits with cores
48–63, and GPU 3 with cores 0–15. Slurm's default placement for four tasks of 16 cores put
local rank *i* on NUMA domain *i*. QUDA selects its device by local rank
([`../../software/quda/internals/rank-placement.md`](../../software/quda/internals/rank-placement.md)),
so under that default every rank drives the GPU of another NUMA domain. The same holds for the
two network interfaces: `mlx5_0` is next to GPU 3 and NUMA 0, and `mlx5_1` is next to GPU 0 and
NUMA 3. `[observed]` on one node, with `nvidia-smi topo -m` and the tasks' own cpusets; check it
with `nvidia-smi topo -m` before relying on it on another node.

What this costs has not been measured here. Perlmutter's GPU nodes have the same layout, and its
tested wrapper, `tools/perlmutter-quda-bind.sh`, also keeps local rank *i* on NUMA *i*. Its core
and memory indices fit this node, but it steers the network interface with `MPICH_OFI_*`
variables, which the UCX build of Cray MPICH used here does not read `[inferred]`. Record the
binding in force with every run, and treat GPU-affine placement as a candidate to measure, not a
default.

## Count CPUs in cores, not hardware threads

The scheduler presents a `cpu` node as 2:64:2 (sockets:cores:threads) but counts 128 CPUs, and
a `gpu-a100-40` node as 1:64:2 with 64 CPUs. A Slurm CPU here is therefore a **core**, while the
operating system numbers twice as many logical CPUs. So `--cpus-per-task` is in cores, but a
binding tool's CPU indices run over hardware threads. A rank layout copied from a machine whose
scheduler counts threads, such as Perlmutter's GPU nodes, requests twice the cores it means.
A task asking for *N* CPUs receives *N* whole cores with both hardware threads, so `nproc`
reports 2*N* `[observed]` (16 requested, 32 logical CPUs in each task's cpuset). Size the OpenMP
thread count from that, and make a binding wrapper's CPU indices fit the 2*N* logical CPUs the
task holds. The profile records `scheduler_cpus_per_node` and deliberately no
`logical_cpus_per_node`.

## Shared nodes and billing

The scheduler allocates cores and memory (`CR_CORE_MEMORY`) and shares nodes between jobs. A
GPU job that does not request memory receives 125,440 MB per GPU. Billing is the **sum** of
weighted resources, not their maximum: every core, every GB of memory, and every GPU at its
weight in the profile. A request is billed on everything it reserves, including the default
memory per GPU, so request memory and cores deliberately. A whole `gpu-a100-40` node at the
default memory, 64 cores, 490 GB and four GPUs, bills 190 per hour. How billing becomes an allocation
charge is not recorded here.

`gpu-interactive` admits one job per user, with one GPU and at most 122.5 GB of host memory.
`debug` and `gpu-debug` admit four submitted jobs and two nodes per user, for one hour. Larger
or longer GPU work goes to `gpu`, capped at 36 nodes per job and per user.

## MPI and launch

The default programming environment is `PrgEnv-gnu` with the **UCX** build of Cray MPICH
(`craype-network-ucx`, `cray-mpich-ucx`), not the OFI build most HPE Cray EX systems default
to. Slingshot-10 uses Mellanox NICs (the high-speed interface is an `mlx5` device), which UCX
drives. A stack built against `cray-mpich` (OFI) from another Cray EX machine has a different
transport here. Record the network module in every stack. The scheduler's default MPI plugin is
`cray_shasta`, so launch with `srun`. GPU-aware MPI on this machine has not been established.

## Place builds deliberately

Use the Cray wrappers with `craype-accel-nvidia80` and a `cudatoolkit` module for sm_80 GPU
builds. `nvhpc` is also installed. Exact module versions belong in a validated stack. The login
nodes have no GPU, so a build that runs its tests belongs on a GPU node. A compute-node build is
a scheduler job and needs an explicit campaign budget before submission. No per-user login-node
resource cap was found in the session's control group.

## Choose storage by workload

`$HOME` (`/N/u/<user>/BigRed200`) is NFS: keep source, scripts and builds there, and never
multi-node shared-file writes (above). `/N/scratch/<user>` and `/N/slate/<user>` are Lustre
mounted with `flock`. Scratch is the large-capacity space for job I/O, and Slate is persistent.
Per-user quotas are in the profile. Slurm sets no node-local temporary directory variable.
`/tmp` on a `gpu-a100-40` node is a tmpfs of about 252 GB: it is RAM-backed, so a job that writes
there spends host memory the job could otherwise use.
