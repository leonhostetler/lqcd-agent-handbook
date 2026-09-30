---
title: Working on Aurora
summary: Where a PBS job starts and how to reach the job directory, node-target resolution, submission requirements (filesystems resource, place, project directory), where live queues differ from ALCF's table, PALS mpiexec rank and GPU-tile placement, build placement, and storage and network rules for ALCF Aurora.
scope: [machine:aurora]
load_when: Building software or preparing a job on Aurora.
evidence: docs
sources:
  - https://docs.alcf.anl.gov/aurora/
  - https://docs.alcf.anl.gov/aurora/getting-started-on-aurora/
  - https://docs.alcf.anl.gov/aurora/running-jobs-aurora/
  - https://docs.alcf.anl.gov/aurora/compiling-and-linking/
  - https://docs.alcf.anl.gov/aurora/data-management/lustre/flare/
  - Aurora login-node environment, Lmod default modules, and PBS qstat -Q, -Qf and -Bf records, read 2026-09-30
observed: "2026-09-30"
observed_on:
  machine: aurora
review_by: "2027-03-31"
---

# Working on Aurora

The machine profile is canonical for hardware, scheduler, filesystem, and policy values. This
leaf owns how to act on them, and where the live machine differs.

> **The accelerator-memory sampler has no Intel branch.** `tools/gpu-memory-sampler.sh`
> reads `nvidia-smi` only, and `--vendor intel` exits with an error as an unknown vendor, so
> do not start it on Aurora. The batch-script instrumentation rule cannot yet be met here.
> Say so in the script review rather than dropping the rule silently.

## Declare the compute target

The profile has one node type, `gpu-pvc`, so it is the default. A login node is not a compute
node: it has no GPU and a different CPU (see `build_environment.login`).

## Submit and account

- `qsub` takes `-A <project>`; the project is never inferred.
- Every job requests `select`, `walltime`, `place` and `filesystems`. Name every filesystem the
  job touches, colon-separated: `-l filesystems=home:flare`. The live server accepts `home`,
  `flare` and `daos_user`.
- Use `-l place=scatter` for whole-node placement, as ALCF's examples do.
- ALCF says to submit from the project directory on Flare, not from `$HOME`.
- **A PBS job starts in `$HOME`, not in the job directory, and no directive pins the job
  directory.** That is the PBS manual's default (`sandbox` unset); it has not yet been
  observed on Aurora. `-W sandbox=PRIVATE` starts the job in a PBS-created directory instead,
  which is not the job directory either. `PBS_O_WORKDIR` names wherever `qsub` ran, so the
  common `cd $PBS_O_WORKDIR` works only when the script is submitted from its own directory.
  Change to the job directory by absolute path first, then resolve from `$PWD`. The checker
  and dry-run harness model this: the harness starts the script in an empty home directory.
- The submission guard refuses `qsub -I`: an interactive allocation has no script to check.
  The operator starts one from their own shell.
- Interactive: `qsub -I -l select=1,walltime=1:00:00,place=scatter -l filesystems=home:flare -A <project> -q debug`.

### Live queues differ from ALCF's table

On 2026-09-30 `qstat -Qf` agreed with the profile's limits except in two places:

| | ALCF table | Live server |
|---|---|---|
| `debug-scaling` minimum nodes | 2 | 1 |
| `prod-large` | absent | a routing queue for 1,920 to 10,624 nodes, to `large` or `backfill-large` |

The live server also lists many site, vendor, training and reservation queues. They are not
general-purpose and are not in the profile.

## Launch MPI deliberately

- The launcher is Cray PALS `mpiexec`: `-n` total ranks, `-ppn` ranks per node, `--depth` CPUs
  per rank, `--cpu-bind`, `--env VAR=value`. Several launches may run at once by
  backgrounding them; give each a disjoint set of cores, GPUs or nodes (a hostfile).
- Cores 0 and 52, and their hyperthreads 104 and 156, are reserved for system services. A
  `--cpu-bind=list:` layout must skip them.
- A node has 6 GPUs of 2 tiles each, which is 12 tiles. `ZE_AFFINITY_MASK=<gpu>.<tile>`
  restricts a rank to one tile. ALCF's `gpu_tile_compact.sh` maps 12 ranks per node to 12
  tiles, and `gpu_dev_compact.sh` maps 6 ranks to 6 GPUs.
- The login environment sets `ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE`, so a process sees each
  GPU as one device with its tiles as sub-devices. Record the value in force on the compute
  node before interpreting a device count.

## Place builds deliberately

ALCF expects GPU code that needs no GPU at build time to compile well on login nodes. A
build that needs a GPU at build time runs on a compute node, which makes it a job under the
budget rule. The default environment is oneAPI with MPICH, libfabric and PALS. More
software is under `module use /soft/modulefiles`. SYCL ahead-of-time compilation targets
the device name `pvc`.

## Storage and network

- `$HOME` is for small files and binaries (50 GB default quota). Run from Flare,
  `/lus/flare/projects/<project>` (1 TB default quota). The site sets no variable for it.
- Compute nodes have no direct outbound network. Set
  `http_proxy`/`https_proxy` to `http://proxy.alcf.anl.gov:3128` for a download inside a job.
  Login nodes need no proxy.
