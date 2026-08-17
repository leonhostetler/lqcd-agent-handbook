---
title: Working on Frontier
summary: Compute-target resolution and HIP build and run prerequisites for Frontier.
scope: [machine:frontier]
load_when: Building software or preparing a job on Frontier.
evidence: docs
sources:
  - https://docs.olcf.ornl.gov/systems/frontier_user_guide.html
  - https://docs.olcf.ornl.gov/data/index.html
observed: "2026-08-17"
observed_on:
  machine: frontier
review_by: "2027-02-17"
---

# Working on Frontier

The machine profile is canonical for hardware, scheduler, filesystem, and policy values.

## Resolve the compute target

A login node identifies Frontier but does not itself establish a compute target. Because
the machine profile currently contains exactly one `node_types` entry, `gpu-mi250x` is
the default when the operator has not made an explicit selection. No separate operator
declaration is needed.

Each compute node has four MI250X packages, but Slurm, `ROCR_VISIBLE_DEVICES`, and the
ROCr runtime expose their eight GCDs as eight separate GPU devices with 64 GB each. Do
not treat one MI250X package as one schedulable device. Once a job starts, reconcile the
resolved node type with the runtime device count and accelerator telemetry before treating
the run as validation.

## Place builds deliberately

Use the Cray compiler wrappers and the `gfx90a` target recorded in the profile. Load a
compatible CPE and ROCm combination; exact version pins belong in a validated stack, not
the machine profile. GPU-aware Cray MPICH additionally requires the target and ROCm modules
plus `MPICH_GPU_SUPPORT_ENABLED=1`; linking details remain toolchain-specific.

Login nodes are appropriate for editing and compilation, but not parallel or threaded jobs
or long, compute-intensive, or memory-intensive builds. Move those builds to a compute
allocation. A compute-node build is a scheduler job and therefore requires an explicit
campaign budget before submission.

## Account for the default core specialization

Frontier compute nodes have 64 physical CPU cores, but Slurm reserves eight by default,
leaving 56 allocatable cores. Treat 56 as the default when constructing rank and thread
layouts unless the job explicitly and deliberately changes core specialization.

The `debug` QOS is for short non-production debugging only, with the limits recorded in
the profile. Production work and job chaining do not belong there.
