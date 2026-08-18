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
