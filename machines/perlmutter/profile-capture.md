---
title: Capturing a GPU profile on Perlmutter
summary: Nsight Systems cannot write a report on the home filesystem; capture from scratch and validate the artifact rather than the exit status.
scope: [machine:perlmutter]
load_when: Planning or submitting a profiled run on Perlmutter.
evidence: reproduced
observations: 2
sources:
  - operator's screened project records
observed: "2026-07-20"
observed_on:
  machine: perlmutter
review_by: "2027-07-20"
---

# Capturing a GPU profile on Perlmutter

**Nsight Systems cannot write a report on the home filesystem.** The application runs to
completion and a `.qdstrm` intermediate appears, but conversion to `.nsys-rep` fails —
observed as `errno 524` (ENOTSUPP) — and **nsys exits 0 regardless**. The job therefore looks
successful until a later step reports the file missing, by which point the allocation is spent.

Capture from the scratch filesystem the machine profile declares (`PSCRATCH`), where it works.
The two conditions have been separated: the recorded failure was on the home filesystem, and
every committed benchmark capture written to scratch succeeded.

[`conventions/profile-capture.md`](../../conventions/profile-capture.md) owns the general rule
this is one instance of — a profiler's exit status does not establish that a report was
written. That rule is what catches the *other* causes, which are not filesystem-related.

**This is advice, not a guard.** An earlier attempt encoded a path-prefix check into submit
scripts and was reverted: those scripts ship to end users, and hard-failing on one site's
directory layout is wrong. Put the check on the artifact instead.
