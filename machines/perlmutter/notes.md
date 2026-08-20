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
