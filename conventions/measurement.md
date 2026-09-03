---
title: LQCD measurement and workflow cost accounting
summary: Shared rules for steady-state solve measurements, exact artifact validation, per-run workflow ledgers, and production-cost projections.
scope: [universal]
load_when: Planning, measuring, comparing, or projecting the cost of tuning and benchmarking runs.
evidence: operator
observed: "2026-08-18"
observed_on:
  requirements: workflow-cost-accounting
review_by: "2027-08-18"
---

# Measurement and workflow cost accounting

Use this convention to turn raw run evidence into comparable measurements and production-cost
projections. Software application guides define what their markers and work units mean; machine
profiles define resource accounting; work modes define why the measurement is being made. This
file defines how those facts are reconciled.

Keep every observed ledger and projection in the working project. They are campaign evidence,
not handbook knowledge.

## Freeze the measurement contract

Before a measured series, state:

- the decision, target quantity, and comparison or acceptance threshold;
- the frozen candidate setup and workload;
- the production work unit and how application input sets compose it;
- the correctness and completion checks;
- the warm-state contract and repetition plan;
- the timer boundaries and resource-cost unit; and
- every truncated dimension and intended extrapolation.

Do not change the contract after inspecting measured results. An adaptive change returns the
work to tuning; it does not revise the current benchmark in place.

## Measure a homogeneous solver series

To estimate steady-state production solve cost, run multiple solves using the same solver and
candidate setup, differing only in source or right-hand-side content. Exclude the first solve by
default because it may contain allocation, initialization, or autotuning overhead, and summarize
the remaining solves. A single solve is not representative evidence of steady-state cost.

Record the number of retained solves and their variability; there is no universal sample count.
A material change in solver, precision, batching pattern, decomposition, or other solve
characteristic starts another homogeneous series.

If production pays first-use cost once per job, gauge configuration, or other declared work
unit, measure it separately and include or amortize it in the workflow projection. Excluding the
first solve is a steady-state solver convention, not an instruction to remove recurring cost
from an end-to-end workflow benchmark.

## Establish the machine's single-measurement resolution before ranking on time

Repeating solves inside one job bounds solve-to-solve spread. It does not bound the spread
between two otherwise identical **jobs**, which is set by node allocation, machine state and
other factors a campaign does not control. Those are different quantities, and the second is
usually the larger.

**A machine therefore has a resolution floor for single unrepeated measurements, and it must
be measured rather than assumed.** Establish it with a zero-variable repeat: submit the same
parameter set twice, changing nothing, and compare. Until that floor is known, no wall-time
or rate ratio within it is resolved, and a ranking built on one is not a result.

The failure is not noisy-looking data — it is data that looks clean. A controlled repeat can
reproduce a run **bit-for-bit** in every deterministic observable, iteration counts and peak
memory included, and still differ materially in wall time. Nothing in either run appears
anomalous, so the difference is silently attributed to whichever parameter the study happened
to be varying.

Three consequences:

- **Report the floor with the ranking**, not separately. A candidate ordering whose gaps sit
  inside it is unresolved, whatever the point estimates say.
- **Prefer deterministic observables for anything the floor would swallow.** Iteration counts,
  convergence behaviour, memory high-water and residuals repeat exactly when the numerical
  path is deterministic, so they can separate candidates that wall time cannot. Design the
  study around them rather than discovering afterwards that its comparisons are unresolvable.
- **Re-establish the floor after a machine, scheduler or placement change.** It is a property
  of the system as configured, not a constant, and a value measured elsewhere does not
  transfer.

A floor is a limit on resolution, not an error bar: it says which comparisons a single
measurement cannot decide, not how uncertain a given number is.

### A deterministic-looking observable is not a determinism claim

The advice above pushes a study toward observables that repeat exactly. That creates its own
trap, and it is worth stating in the same place: **constancy observed within one run is not
evidence that an observable is deterministic for that parameter set.**

One measured case: a run returned an identical iteration count on every solve of a
trial, and its **byte-identical repeat** — same inputs, same placement, same build — did not.
The count moved by one. Constancy within a single run can be luck, and a study that has
already been blocked from ranking on wall time is exactly the study most tempted to treat it
as a noise-free discriminator.

**Establish determinism the same way the resolution floor is established: with a
zero-variable repeat.** Until then, a separation resting on such an observable is suggestive,
and should be reported as suggestive rather than as a resolved difference.

Determinism can also **degrade with magnitude**. In the same corpus the spread widened as the
count grew — exact to within one at a count near `24`, a few units wide near `32` and `60`,
and tens wide near `3400`. An observable that repeats exactly in a tight regime may not repeat
in a looser one, so a determinism check belongs at the operating point being used, not at a
convenient one.

## Pair a screening rate with the guard that makes it meaningful

A screening metric expressed as work-per-unit-time can usually be improved by loosening a
downstream tolerance. The rate rises because less work is being done per unit of result, and
the quantity the study actually cares about gets worse. **The rate ranking and the quality
ranking then disagree in sign**, which is the failure that makes an unguarded rate dangerous
rather than merely noisy.

So **declare a quality guard on the same probe, before running the scan**, and rank on the
pair. One measured case: the trial posting the best screening rate in an entire study — a
large improvement over baseline — was correctly rejected because the residual it actually
reached had degraded by more than an order of magnitude.

**Then check that the guard you executed is the guard you wrote.** In that same study the
recorded guard was looser than the one applied at reconciliation: a trial the study rejected
would have **passed** the written rule. A later study copying the written guard would retain
a candidate the original had rejected, and nothing in either record would look wrong. Write
the guard as an expression, apply it mechanically, and reconcile the written and executed
forms before the result is used elsewhere.

## Keep the timing layers distinct

Retain the enclosing clocks even when a narrow component timer answers the immediate question:

| Layer | What it establishes |
|---|---|
| Scheduler elapsed and allocated resources | Allocation cost for the job or step. |
| Whole-application wall clock | An application-envelope cross-check when usable start and normal-exit timestamps are present. |
| Application work-unit total | The interval owned by an application's control loop; its boundary is application-specific. |
| Application phase | Named setup, I/O, solve, contraction, output, or other phase work. |
| Component occurrence | A solve, force, smearing, I/O, or other implementation-level measurement. |

These clocks need not share start and end boundaries. A parent phase can contain component
records, and the sum of printed components need not equal either the application or scheduler
total. Load the relevant application guide before assigning ownership or recurrence.

## Write one observed workflow ledger per run

Create an observed ledger for every allocation-consuming run regardless of the disposition
assigned under `running.md`. Give each run isolated raw output and an immutable identity. The
ledger references raw evidence; it does not replace it.

The run header records:

- run identifier, stage, and intended question;
- executable, software and dependency revisions, and build profile;
- candidate setup, workload, input, and generated-input identity;
- machine, node type, scheduler request, placement, decomposition, and binding;
- tunecache and other persistent setup state;
- expected application work units, expected-artifact manifest, and validation root; and
- raw application, scheduler, environment, telemetry, and artifact locations.

For each reported quantity, record:

| Field | Meaning |
|---|---|
| quantity | The measured or derived metric and units. |
| evidence source | The raw file and marker, scheduler field, telemetry source, or derivation. |
| boundary | Job, step, process, application input set, phase, component, or artifact operation. |
| occurrence count | How many repeated units the value represents. |
| statistic | Total, mean, median, interval, distribution summary, or explicitly limited single observation. |
| recurrence | Once per campaign, job, gauge configuration, source, solve, cadence, or other declared unit. |
| accounting role | Parent clock, non-overlapping partition term, nested diagnostic, excluded cost, or derived residual. |
| warm state | Cold, warm, mixed, or not applicable. |
| validity | Run disposition from `running.md` and completion and correctness status of the associated work. |
| limitation | Noise, missing coverage, incompatible boundary, or extrapolation restriction. |

The accounting role prevents double counting. A solver occurrence can explain a propagator phase
without becoming an additional term beside that parent in the same total.

The workflow-cost ledger is not the submission-budget ledger. The former explains measured and
projected cost; the latter records authorization and allocation consumption and remains
append-only under the campaign budget rule.

## Validate run-owned artifacts exactly

Freeze an expected-artifact manifest from the final generated input and the applicable
application and runtime semantics before launching the run. Do not derive it only from a
generator template, a previous run, or a planned source count: the submitted input is the
authority for the output actions the executable was asked to perform.

For every expected artifact, record:

- the output action and application work unit that produces it;
- its path resolved against the captured application working directory;
- whether multiple actions intentionally contribute to the same path;
- the expected format, internal record identities and multiplicities, and payload shape; and
- the run-manifest fields or embedded metadata that associate it with this run.

Use a new run-owned validation root whenever possible. Otherwise verify before launch that every
planned target is absent and inventory the root. An application that appends to an existing file
can make a failed or partial run appear complete, so existence, modification time, and nonzero
file size are not sufficient provenance checks.

After the run, classify every file in the validation root as an expected application artifact,
an explicitly allowlisted run-infrastructure file, or unexpected output. Compare sets in both
directions:

```text
missing artifacts    = expected paths - observed expected-class paths
unexpected artifacts = observed application-artifact paths - expected paths
```

Pass structural validation only when both sets are empty and every expected artifact has its
declared internal records and payload shape. Preserve the exact missing and unexpected sets in
the run ledger. Deduplicate repeated destination paths for file-set comparison, but preserve all
expected contributions to each path for the internal-record check.

Keep three acceptance layers distinct:

1. **structural validity** — exact paths, format, record identities and multiplicities, sample
   coverage, parseable finite payload, and current-run association;
2. **numerical validity** — convergence and comparison with required invariants or references
   under the frozen tolerance and metric; and
3. **scientific validity** — approval that the requested parameters and observables answer the
   intended physics question.

A normal process exit does not establish structural validity, and structural validity does not
establish either numerical or scientific validity. Do not require every numerical sample to be
nonzero as a generic structural check; exact or near-zero values may be physically expected.

## Build a compatible accounting view

For each accounting view:

1. select one parent clock;
2. select only non-overlapping child terms with compatible boundaries and recurrence;
3. show nested diagnostics separately;
4. preserve excluded work with its reason; and
5. compute a residual only from that declared parent and partition.

Use:

```text
residual = parent clock - sum(compatible non-overlapping partition terms)
```

Label the result by its parent, such as application residual or scheduler residual. Do not call
it unaccounted time when timer overlap, missing instrumentation, or incompatible boundaries make
the subtraction invalid. Complete closure is not required; an explicit unexplained residual is
better evidence than a forced partition.

## State recurrence before projecting

Classify every projected term:

| Recurrence class | Typical examples |
|---|---|
| Campaign one-time | Tunecache population or reusable algorithm setup. |
| Job-fixed | Process launch, backend initialization, and job-level finalization. |
| Gauge-configuration recurring | Gauge input, gauge fixing, or configuration-specific setup. |
| Source recurring | Source construction and its associated propagators or contractions. |
| Solve recurring | A homogeneous steady-state solve class with a declared production count. |
| Cadence-dependent | Checkpoints, measurements, saves, or output performed every declared number of work units. |
| Excluded from production | Diagnostic work or an artifact of the tuning/benchmark protocol. |

The same operation can have a different recurrence in another production design. State the
reuse scope rather than assigning recurrence from its position in one output file.

## Keep production projection separate

Construct a projection only after the observed ledgers pass their validity checks. Keep measured
run accounting separate from the projected campaign. Choose non-overlapping terms: for example,
a source-recurring term cannot include solve work that is also counted by solve class below.

```text
projected aggregate application work
  = campaign one-time cost
  + job count                 × job-fixed cost
  + gauge-configuration count × gauge-configuration cost
  + source count              × source-recurring cost
  + solve counts by class     × steady solve cost by class
  + cadence-weighted work
```

Adapt the terms to the application rather than forcing this example onto every workflow. Label
each coefficient and multiplier as measured, modeled, assumed, or unknown. A truncated
benchmark must classify each extrapolation as fixed, proportional, empirically modeled, or not
safely extrapolatable.

Aggregate work is a serial-equivalent quantity, not campaign calendar time. A makespan estimate
also states job packing, concurrency, and whether queue time is excluded. Report the projected
per-work-unit elapsed time, aggregate resource cost, and makespan assumptions separately.

Calculate resource cost from the actual allocation associated with each elapsed interval:

```text
node-hours = elapsed hours × allocated nodes
GPU-hours  = elapsed hours × allocated GPUs
```

Report elapsed time and resource cost separately. Do not mistake a lower wall time obtained with
more resources for lower campaign cost.

With repetitions, keep one observed ledger per run. Form the comparison and production
projection only from accepted runs, preserving the distribution, exclusions, and reason for
every rejected observation.

## Validity and completion

A performance quantity enters a comparison or projection only when:

- its boundary and evidence source are known;
- the required application work is complete and the exact artifact-set and structural checks
  pass;
- the executed path matches the frozen candidate setup;
- numerical and scientific checks required by the contract pass;
- scheduler and application exit states are reconciled;
- its accounting and recurrence roles are declared; and
- uncertainty and missing coverage are reported.

Runs classified as `rejected`, `incomplete`, `no-trial`, or `indeterminate` retain observed
ledgers because they consume allocation or provide feasibility and debugging evidence. Only
`accepted` runs enter a confirmatory performance distribution.
