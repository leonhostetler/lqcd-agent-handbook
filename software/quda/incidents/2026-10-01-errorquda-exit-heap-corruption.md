---
title: QUDA's error exit corrupts the heap, and once hung instead of aborting
summary: After errorQuda, the abort path printed a glibc heap error in every one of thirteen observed exits, and once wrote a tunecache file to a garbage path and hung until its step limit; unexplained, and present on develop.
scope: [software:quda]
load_when: A QUDA run prints "double free or corruption", "Attempt to free invalid host pointer", or another heap error after an ERROR line; hangs after an errorQuda instead of exiting; or leaves a garbage-named file in its run or tunecache directory.
evidence: reproduced
observations: 13
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/util_quda.cpp
  - https://github.com/lattice/quda/pull/1654
  - operator's screened QUDA pull-request review records
observed: "2026-10-03"
observed_on:
  machine: deltaai
  node_type: gpu-gh200
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
  toolchain:
    cuda: 12.9.41
    host_compiler: GNU 14.2.0 through Cray wrappers
---

# QUDA's error exit corrupts the heap, and once hung instead of aborting

**An unexplained occurrence.** No mechanism is known. This records what was seen, so the next
session recognises it and does not chase it as the cause of the failure it follows.

## What was seen

`errorQuda` saves the tunecache and then calls `comm_abort` (`errorQuda_` in
`lib/util_quda.cpp`). In thirteen runs that reached it, the process failed a second time on the
way out:

- **Twelve aborted with a glibc heap error**, `double free or corruption (out)` or `(!prev)`, and a
  core dump (exit status 134). The tunecache had already been saved normally.
- **One hung.** It printed QUDA's own `Attempt to free invalid host pointer
  (color_spinor_field.cpp:286 in destroy())`, wrote a second tunecache file to a path made of
  garbage bytes (a 270-byte file whose name and header strings were unprintable), and then ran
  until its ten-minute step limit stopped it (exit status 143) instead of aborting.

The thirteen exits came from two entry points: `staggered_eigensolve_test` with a TRLM eigensolve
that cannot converge (six runs, one rank), and MILC `ks_spectrum_hisq` CG solves that QUDA declared
diverged (seven runs). So the eigensolver is not the trigger.

One run, the eigensolver test, was on `develop` at `00c7ef33`. The other twelve, including the
hang, were builds of lattice/quda#1654, a pull request forked from that commit; several used its
float-float storage. The `develop` run shows the defect does not need the pull request. Whether the
hang does is not known: it was seen once, in a float-float build. On 2026-10-05 `develop`'s tip was
still `00c7ef33`, so this describes current `develop`.

Observed on DeltaAI `gpu-gh200`, with CUDA 12.9 and GNU 14 through the Cray wrappers, at one rank
per process group. Not tested: other machines, compilers or MPI libraries, multi-rank aborts, and
other routes into `errorQuda`.

## What to do with it

- **Read the first `ERROR` line, not the last one.** The heap error and the invalid-free message
  come from the exit path, after the real failure has been reported. They are a symptom of exiting,
  not the cause of the run's death. Grep for the first `ERROR:` before reading a core dump.
- **Expect an `errorQuda` to hang sometimes.** Give every launcher step its own time limit
  ([`../../../conventions/batch-scripts.md`](../../../conventions/batch-scripts.md)), so a hung
  abort costs its leg and not the job.
- **A garbage-named file in a run or tunecache directory is this signature.** Keep it as evidence.
  Never load it as a tunecache, and never delete it as debris before it is recorded.
- **Report a reproduction upstream with the first `ERROR` line and the exit-path message
  together.** As of this entry no upstream issue is known to cover it.
