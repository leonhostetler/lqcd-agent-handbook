---
title: Working on Perlmutter
summary: Node-target declaration and build-placement rules for Perlmutter.
scope: [machine:perlmutter]
load_when: Building software or preparing a job on Perlmutter.
evidence: docs
sources:
  - https://docs.nersc.gov/development/coding-agents/
  - https://docs.nersc.gov/jobs/policy/
  - https://docs.nersc.gov/policies/resource-usage/
  - https://docs.nersc.gov/development/compilers/wrappers/
observed: "2026-08-15"
observed_on:
  machine: perlmutter
review_by: "2027-02-15"
---

# Working on Perlmutter

The machine profile is canonical for hardware, scheduler, filesystem, and policy values.

## Declare the compute target

A login node identifies the machine, not the intended compute-node type. Select
`cpu`, `gpu-a100-40`, or `gpu-a100-80` explicitly before resolving a build or stack.
Use the Slurm constraint recorded for that node type; quote constraints containing `&`
when they appear on a shell command line.

Once a GPU job starts, reconcile the declared node type with accelerator telemetry before
treating the run as validation. Shared GPU architecture may support an inference about
binary compatibility, but validation remains specific to the node types actually run.

## Bound filesystem discovery

Follow the universal [bounded filesystem-discovery convention](../../conventions/filesystem-discovery.md).
NERSC specifically prohibits recursive traversal from `/`, `/global`, `/global/cfs`,
`/global/homes`, `/pscratch`, `/opt`, `/usr`, or another shared top-level directory on both
login and compute nodes. For a bounded, computationally substantial search, use NERSC's
`$perlmutter-compute` route. Neither a compute allocation nor that route broadens the permitted
filesystem root.

## Place builds deliberately

The Cray compiler wrappers are intended to compile on login nodes for execution on compute
nodes. Keep login-node builds within the limits and parallelism recorded in the machine
profile. Move a long, CPU-intensive, or memory-intensive build to a compute allocation. A
compute-node build is a scheduler job and therefore requires an explicit campaign budget
before submission.

## Rank binding

`tools/perlmutter-quda-bind.sh` is the tested four-rank binding wrapper for GPU nodes **running
QUDA**: NIC policy and mapping, CPU cores and memory domain per local rank, and deliberately no
accelerator binding. The name carries both scopes on purpose — the CPU, memory and interface
binding is a property of this machine and reusable by any application at four ranks per node,
while the absence of accelerator binding is a property of QUDA and must be re-decided for any
other application.
The stack records name this arrangement under `runtime: cpu_binding`, so a launcher that omits it
has not reproduced the stack.

Two constraints travel with it and neither is enforced by the script. Its CPU indices reach 127,
so the job must hold all **128** logical CPUs of the node — with four tasks per node, 32 CPUs per
task. And `lrank` is taken modulo four, so any other rank layout silently gives two ranks the same
binding. See [`../../conventions/batch-scripts.md`](../../conventions/batch-scripts.md) for the
general rule and
[`../../software/quda/internals/rank-placement.md`](../../software/quda/internals/rank-placement.md)
for why accelerator visibility must stay open.
