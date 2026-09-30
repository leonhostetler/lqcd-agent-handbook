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
  - https://docs.alcf.anl.gov/account-project-management/allocation-management/allocation-management/
  - Aurora login-node environment, Lmod default modules, and PBS qstat -Q, -Qf and -Bf records, read 2026-09-30
  - four operator-submitted single-node debug jobs on 2026-09-30, reviewed in the working directory
observed: "2026-09-30"
observed_on:
  machine: aurora
review_by: "2027-03-31"
---

# Working on Aurora

The machine profile is canonical for hardware, scheduler, filesystem, and policy values. This
leaf owns how to act on them, and where the live machine differs.

## Declare the compute target

The profile has one node type, `gpu-pvc`, so it is the default. A login node is not a compute
node: it has no GPU and a different CPU (see `build_environment.login`).

## Submit and account

- `qsub` takes `-A <project>`; the project is never inferred. **A project split into
  suballocations needs the suballocation too**: `-A <project>::<suballocationName>` or
  `-A <suballocationID>`, per ALCF. `sbank-list-allocations -r aurora -c` lists them, with
  each one's balance, whether it is restricted, and its user list.
- `[observed]` Do not predict acceptance from that listing. One job was accepted and ran
  against a restricted suballocation whose listed balance was negative and whose user list
  did not show the submitter, while another suballocation of a different project was
  rejected. ALCF documents rejection for a non-positive suballocation balance, so the listing
  and the server's decision can disagree. The operator decides which to charge; a rejection
  message is the evidence, not the listing.
- Every job requests `select`, `walltime`, `place` and `filesystems`. Name every filesystem the
  job touches, colon-separated: `-l filesystems=home:flare`. The live server accepts `home`,
  `flare` and `daos_user`.
- Use `-l place=scatter` for whole-node placement, as ALCF's examples do.
- ALCF says to submit from the project directory on Flare, not from `$HOME`.
- **A PBS job starts in `$HOME`, not in the job directory, and no directive pins the job
  directory.** That is the PBS manual's default (`sandbox` unset). `[observed]` on Aurora:
  the job's start directory and `PBS_JOBDIR` were both `$HOME`, and `$0` was a copy in the
  PBS spool directory. `-W sandbox=PRIVATE` starts the job in a PBS-created directory instead,
  which is not the job directory either. `PBS_O_WORKDIR` names wherever `qsub` ran, so the
  common `cd $PBS_O_WORKDIR` works only when the script is submitted from its own directory.
  Change to the job directory by absolute path first, then resolve from `$PWD`. The checker
  and dry-run harness model this: the harness starts the script in an empty home directory.
- **Key a run root on `${PBS_JOBID%%.*}`, not on `PBS_JOBID`.** `[observed]` `PBS_JOBID` is
  the full identifier, the sequence number followed by the PBS server's internal fully
  qualified host name, so a directory named from it carries an internal host name into every
  path and every record that quotes one. The site also exports `PBS_JOBID_SHORT`, the sequence
  number alone, but the PBS manual does not list it and no profile declares it, so the
  dry-run harness aborts a script that references it; derive the short form from `PBS_JOBID`
  instead.
- `qstat -f "$PBS_JOBID"` works from inside a job, so the teardown record can be taken there.
  `qstat -x -f <id>` afterwards gives the final `resources_used`, including `mem`.
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
  `[observed]` two backgrounded single-rank launches on one node both started and exited 0.
- Cores 0 and 52, and their hyperthreads 104 and 156, are reserved for system services. A
  `--cpu-bind=list:` layout must skip them.
- A node has 6 GPUs of 2 tiles each, which is 12 tiles. `ZE_AFFINITY_MASK=<gpu>.<tile>`
  restricts a rank to one tile. ALCF's `gpu_tile_compact.sh` maps 12 ranks per node to 12
  tiles, and `gpu_dev_compact.sh` maps 6 ranks to 6 GPUs.
- `ZE_FLAT_DEVICE_HIERARCHY=COMPOSITE` is set on the login node and, `[observed]`, inside a
  batch job, so a process sees each GPU as one device with its tiles as sub-devices. Record
  the value in force before interpreting a device count, since a module or script can change
  it.
- **Accelerator memory monitor:** `module load xpu-smi/1.3.5`, then start
  `tools/monitor-gpu.sh <interval> intel` in the background, as the batch-script convention
  shows. `xpu-smi` is on neither the login node's nor a compute node's default `PATH`, and
  the unversioned module loads 1.2.43. That version prints `N/A` for each device's size, so
  the monitor records no rows and says so on stderr.
- `[observed]` One `xpu-smi` query costs several seconds, which is why the Intel monitor
  streams: at a 1 s interval it achieved a 1 s period and left no `xpu-smi` running once
  stopped. Its first sample arrives about 9 s after it starts, so start it well before the
  phase whose peak matters. An idle GPU reads about 80 MiB, not zero. Holding 8 GiB on a
  whole GPU and 4 GiB on one tile of another moved the readings by 8,203 and 4,106 MiB and
  left the other four unchanged. The monitor reports whole GPUs, each the sum of its two
  tiles; `xpu-smi dump -t` resolves tiles when a question needs them.

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
- `[observed]` A compute node's `/tmp` is a tmpfs of about 504 GiB. It lives in memory, so
  every byte written there is host memory the job cannot use. PBS sets `TMPDIR` to a per-job
  directory under `/var/tmp`. What backs `/var/tmp` was not checked, so the profile declares
  no node-local temporary variable yet; do not reference `TMPDIR` as fast local disk.
