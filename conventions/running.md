---
title: LQCD run outcome reconciliation
summary: Shared rules for reconciling scheduler, runtime, application, artifact, and correctness evidence into a run disposition.
scope: [universal]
load_when: Preparing, observing, classifying, or accounting for a submitted or launched run.
evidence: operator
observed: "2026-08-18"
observed_on:
  requirements: run-outcome-reconciliation
review_by: "2027-08-18"
---

# Run outcome reconciliation

Use this convention after every submitted or launched run. Application guides define progress,
completion, and correctness markers; machine profiles define scheduler semantics; and
`measurement.md` defines artifact validation and workflow accounting. Keep each run's outcome
record and raw evidence in the working project.

## Reconcile independent evidence

Record before assigning a disposition:

- scheduler or local-launcher state, job and step exit codes, terminating signal, and allocation;
- launcher, MPI, accelerator-runtime, and device-reachability evidence;
- the application's last progress marker and normal or abnormal exit evidence;
- completion of the declared work unit, expected artifacts, convergence, and frozen correctness
  checks; and
- paths to the raw scheduler, application, environment, telemetry, and artifact evidence.

No single layer decides the result. Scheduler success does not prove application completion,
artifact validity, or correctness. A normal application exit does not prove scheduler success or
validate artifacts. Artifact presence does not prove current-run ownership, and application
progress does not prove that the declared work unit completed.

## Derive before you analyse

Where a contract-governed extractor or report generator exists for a run's observables,
**run it first and analyse its output.** Do not re-derive by hand quantities the tool
already emits, and do not generate the authoritative record afterwards to confirm a
conclusion already reached by hand.

The ordering is what matters, not the tooling. A hand pass performed first and a generated
record produced second computes the same quantities twice, with the *uncontracted* pass
deciding the reading; the generated table then arrives as confirmation rather than as the
source. Two consequences follow, both observed rather than argued:

- **A hand pass produces a defect class a tool does not.** Transcription between adjacent
  result rows, and aggregation over the wrong subset of calls — a solve-phase mean tallied
  across setup-phase invocations — are the recorded examples. Neither is a reasoning error;
  both are artifacts of moving numbers by hand.
- **A tool can find them after the fact.** In the recorded case a reconciliation tool
  identified such a defect **on its first run**, in a trial that had already been reconciled
  by hand and reported complete.

When the generated record and a hand reading disagree, the generated record is the evidence
and the disagreement is itself a finding: either the tool's contract or the hand reading is
wrong, and which one must be established before the disposition is assigned. Record the
generator and its version alongside the disposition so a later reader knows which contract
produced the numbers.

**Evidence:** empirical, from one operator campaign; the mechanism is that hand-executed
repetition produces transcription-class defects that an executed contract cannot produce.
See [`repeated-work.md`](repeated-work.md) for the broader practice this is one instance of.

## What a completion watch may treat as the end of a job

A long job should be watched, and an unattended agent should not end a work session while a study
has budget and queued work left. But a watch is only as good as its terminal condition, and a
wrong one is worse than none.

**Do not decide a job has ended from a scheduler query.** A query issued from inside a monitoring
subprocess can fail and return **empty**, which is indistinguishable from "the job is no longer
queued" — while the same command run directly succeeds. One recorded campaign saw four false
completions this way, one of which was reported to the operator as a finished job while it was
still running. **A single empty result is never evidence of termination.**

**Prefer a marker the job writes itself.** A lifecycle record the job appends in its own teardown
means the job reached teardown; nothing else needs consulting, and its absence is informative in a
way a failed query is not. Give the watch a wall-clock backstop somewhat longer than the requested
limit so it cannot wait forever.

**Anchor failure patterns precisely.** A bare match on a word like `ERROR` will fire on parameter
and symbol names that legitimately contain it, reporting failures in every healthy start. **A watch
that cries wolf on a normal run is worse than no watch**, because it trains its reader to ignore it.

**When the two kinds of error trade off, prefer a false negative in the failure filter to a false
positive in the terminal condition.** A missed error costs a look at the log. A wrongly declared
completion invites acting on a running job — resubmitting it, or reporting an outcome that does not
exist.

**A watch must die with the job it watches.** Retire it in the same step that reconciles the job,
and confirm none is still bound to something finished. A watch outliving its job is not
untidiness: it is indistinguishable from a live watch on a running one, which degrades the only
signal this arrangement provides. Note also that a watch exiting on its own is not proof the job
ended — confirm against the job's own record before reconciling.

## Assign one disposition

| Disposition | Meaning and treatment |
|---|---|
| `accepted` | The frozen completion, artifact, and correctness contract passed. The run may enter the applicable performance statistics. |
| `rejected` | Meaningful candidate work ran and the evidence establishes that a frozen feasibility, execution-path, artifact, or correctness requirement failed. Retain tuning, feasibility, or debugging evidence, but exclude confirmatory performance. |
| `incomplete` | Candidate work began but stopped through timeout, cancellation, signal, or another premature termination before a pass or classifiable rejection was established. Retain cost and observed progress, but do not treat them as complete-work performance. |
| `no-trial` | Candidate work never meaningfully began because launch or infrastructure failed. Do not use the run to rank the candidate. |
| `indeterminate` | Required evidence is missing or contradictory. Retain the run but make no performance or causal claim. |

A deliberately truncated benchmark is not `incomplete` when it finishes the truncated work unit
defined in its frozen contract. Classify it against that declared unit and preserve the
extrapolation limits in the measurement record.

## State reason and attribution separately

Alongside the disposition, record one primary reason class and the evidence supporting it:

- candidate or resource-plan incompatibility;
- application or input failure;
- environment or infrastructure failure;
- external termination;
- correctness or artifact rejection; or
- unknown.

Disposition states what evidence is admissible; reason states the supported explanation. Do not
attribute an out-of-memory event, invalid decomposition, launch failure, or missing artifact to
the candidate merely because it occurred during that candidate's run. Use `unknown` when the
evidence does not distinguish candidate, environment, or protocol causes.

## Preserve cost and evidentiary value

Every allocation-consuming run remains in the workflow-cost ledger regardless of disposition.
Only `accepted` runs enter confirmatory performance statistics. A `rejected` run may establish a
feasibility boundary when its cause and scope are supported. An `incomplete` run may constrain
cost or progress, but requires an explicit model before extrapolation. `no-trial` and
`indeterminate` outcomes remain debugging and accounting evidence, not candidate rankings.

This convention intentionally does not define scheduler-specific state lists, error-message
catalogs, retry policy, or root-cause procedures. Load the machine profile, application guide,
and relevant debugging knowledge for those details.
