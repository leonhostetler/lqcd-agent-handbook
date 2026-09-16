# Performance Mode

Performance mode answers where a run's time goes and why. It captures or ingests a profiler
database, extracts a structured summary, and produces a ranked list of hypotheses, each naming
the evidence it rests on and the fraction of runtime it claims. It diagnoses; it does not
search. Applying a change and remeasuring is an adaptive search and belongs to tuning. The mode
changes only when the operator explicitly declares a different work mode.

A profile is evidence about one execution, on one machine, under one set of capture options. It
is not a description of the application, and every number read out of it inherits the conditions
of the run that produced it.

## Establish the task

Before analysing a profile:

1. State the decision the analysis serves, the region of interest, and what would count as an
   answer. "Make it faster" is not a decision; "is the solve phase held up by communication or
   by kernel work" is.
2. Establish the division of labour: analysis-only, capture-and-analyse, or prepare-and-handoff.
   Permission to analyse does not authorize project edits, rebuilds, Git actions, or scheduler
   submission unless the operator included those actions in scope.
3. Identify the profile and the build that produced it — software revision and branch, build
   profile and compiled capabilities, runtime options, decomposition, and node type. A profile
   whose provenance is unknown supports observations but no actionable suggestion, because
   nothing establishes that the suggested change is even available in that build.
4. Record the capture conditions that decide what the numbers mean: autotune cache warmth,
   whether warmup or first-solve passes are inside the capture window, which ranks were
   profiled, and which tracing options were requested.
5. Establish what the capture actually contains before analysing it. Verify the present event
   tables rather than assuming the requested options took effect — a capture-scope control that
   returns success without gating the trace is a known class of defect, and the resulting
   profile looks valid.

## What a trace shows, and what it does not

[`conventions/profile-metrics.md`](../conventions/profile-metrics.md) defines every extracted
quantity and the readings that are unfounded on trace data alone. **Load it before quoting any
figure from a profile.** It is named here rather than only in routing because a correctly
indexed leaf has been observed not to fire at the moment it applied.

The rule it exists to enforce is short enough to carry in the mode: **a bottleneck the capture
cannot observe may not be asserted from it.** Tracers record API calls, launches, durations,
transfers and ranges; without deliberately collected counters they record neither achieved
bandwidth nor cache behaviour nor achieved occupancy. Memory-boundedness, occupancy, and the
health of an uninstrumented subsystem are questions for a counter-collecting run, not findings.

## Analysis method

1. Summarise with `tools/gpu-profile-summary.py` rather than by querying the database by hand
   in the session. The
   correct aggregations — concurrency-aware busy time, kernel totals grouped by full demangled
   name, per-phase figures clipped to their window, numerically stable duration spread — are each
   easy to get wrong in a way that reads as plausible.
2. Segment before aggregating. A whole-profile average over a run whose parts differ describes
   none of them, and the dominant phase is frequently not the one with the interesting defect.
   Prefer application annotations or a known application structure over inferred segmentation
   when either is available.
3. Work the dominant phase first, and inside it in a fixed order: kernel work, memory transfers,
   communication, idle gaps. Rank by share of elapsed time, not by how unusual a number looks.
   Attribute the idle rather than describing it — `idle-attribution` splits it into MPI, host
   API and OS time and reports what none of them covers, and that residual is frequently the
   largest single entry. Measure transfers with `transfer-overlap`, not by volume: the biggest
   class by bytes is regularly the one that costs nothing.
4. Drill with a purpose. State the question a query answers before issuing it, and stop when the
   ranked list stops changing. Raw query access is an escape hatch, not the method: keep it
   read-only and row-capped, because an uncapped scan of a multi-gigabyte profile is the ordinary
   accident.
5. Cross-reference the code that produced the profile. A demangled kernel name resolves to the
   source that launched it; a suspected pattern is confirmed by reading that source, not inferred
   from a duration. Reading source, build logs, and run logs is in scope for this mode. Changing
   any of them is not.
6. Reconcile against what the handbook already records before concluding. When the software has
   a leaf on reading its kernels in a profile, load it before interpreting names, call counts,
   launch geometry or duration spread — for QUDA that is
   [`software/quda/profiling.md`](../software/quda/profiling.md), which records why a cold
   tunecache inflates all four.
7. Treat one rank's profile as one rank's view. Imbalance is a cross-rank quantity and is not
   visible from a single rank, where a rank waiting on its neighbours looks like a rank with a
   communication problem of its own. Use the `cross-rank` subcommand across the per-rank
   captures; it refuses a mixed-format set rather than producing a delta with no denominator.

## What a hypothesis carries

Each hypothesis names the bottleneck and the phase it belongs to; the evidence, as specific
figures; the queries those figures came from, so the analysis can be re-derived rather than
re-trusted; the fraction of that phase's elapsed time attributable to it, or an explicit null
when it is not computable; a concrete suggestion and the class of change it needs — runtime
options, launch geometry, source, or algorithm; and what would confirm or refute it.

**Every figure cited is one the extraction produced.** A hypothesis is an inference, and an
inference names its premises. A fabricated or misremembered number is the expensive failure in
this mode, because it reads as a precise, profile-grounded fact and nothing downstream rechecks
it.

**Ground every suggestion in the profile or in a named handbook leaf, and say which.** A
suggestion resting on neither is recall about an application's options, which is exactly the
failure this rule exists to prevent. Citing a leaf is not a weaker form of evidence than the
profile; it is a different premise, and naming it lets the reader check both.

**The list is ranked, and the ranking is part of the answer.** A correct diagnosis buried under
four wrong ones is not the result that was led with. A ranked list with stated fractions is
falsifiable; an unordered list of observations is not.

Where a quantity is derived by hand rather than by the extraction tool, the record says so.
Check the finished record with `tools/hypothesis-record.py`: it derives the speedup bounds
rather than trusting them, and refuses a figure that names no query it came from.

**A claimed fraction is a prediction.** The speedup it implies is arithmetic and is computed
rather than asserted. Record the prediction before the next run and compare after it, so a
systematically inflated fraction becomes a detectable defect instead of an invisible one.

## Handoff to tuning

Performance mode ends at a ranked, evidenced hypothesis list. Acting on it — changing a runtime
option, a launch geometry, source, or an algorithm, rebuilding, and remeasuring — is tuning and
requires an explicit operator declaration. The agent may identify the boundary and recommend the
transition; it remains in performance mode until the operator declares it.

The handoff carries the ranked hypotheses with their evidence and queries; the capture conditions
the analysis depended on; the predicted runtime fraction and implied bound for each; which
suggestions are unvalidated on the current stack or unavailable in the current build; and what
the capture could not observe, so tuning does not treat silence as a clean bill.

## Permissions and safeguards

- Treat a profile as an immutable input. Open it read-only, never write to it, and never modify
  a profiler's native output file; work from exports or copies.
- A capture run consumes allocation like any other run. Never submit one without an explicit
  campaign-scoped node-hour or GPU-hour ceiling and a working-directory budget ledger; without
  both, prepare the job and give the submit command to the operator. Compare purpose, node count,
  walltime, and concurrency against the machine profile and record the scheduler class chosen and
  why.
- Do not change project code, build options, or runtime parameters in this mode. A change
  belongs to a declared tuning session, which loads `software/<name>/development.md` before any
  authorized software change.
- Keep profiles, extracted summaries, queries, hypothesis records, and measured figures in the
  working directory. They are run evidence, not handbook knowledge. Profile paths, job
  identifiers, and hostnames stay there too.
- State a capability gap rather than working around it silently, and treat an absent solver,
  stack, or application record as an explicit limitation rather than filling it with an
  unlabelled assumption.

## Tools and routing

Before substantive analysis, run the task-time Tier-2 routing checkpoint, and re-run it whenever
the application, phase, suspected bottleneck, or immediate decision changes.
Open the [profile-analysis playbook](../playbooks/analyze-profile.md) before beginning an
analysis; it owns the procedure this mode governs. Load
[`conventions/profile-metrics.md`](../conventions/profile-metrics.md) before reading or quoting
any extracted quantity; it is the canonical home for what each one means, and
[`conventions/profile-capture.md`](../conventions/profile-capture.md) before submitting a
capture, for what cannot be recovered after the run.

**Reload the routing this mode depends on after a context compaction.** A deep drill-down is the
session shape most likely to compact, and a compaction removes every Tier-2 leaf while still
supporting a confident restatement — so the metric rules above can be gone precisely when the
analysis is deepest. Re-read them rather than recalling them.

Use the detected machine profile, software profile, nearest stack, build profile, and the
relevant application guide and solver documents when they exist.
Extract with `tools/gpu-profile-summary.py` — `summary`, `phases`, `kernels`, `gaps`,
`idle-attribution`, `transfer-overlap`, `memcpy`, `mpi`, `streams`, `markers`,
`window-breakdown`, `host-samples`, `launch-geometry`, `cross-rank`, `schema`, `query` — and reach for `query` only when no subcommand answers the question, since it
is capped and read-only by design rather than by convention. `idle-attribution` is what closes
the account in step 3 below; `transfer-overlap` is what decides whether a transfer class costs
anything, which its volume does not; and `host-samples` **names** the host time
`idle-attribution` can only size as a residual, which on one capture was the largest cost in
the run and invisible to every traced category.
Compare a before and an after capture with `tools/gpu-profile-diff.py`, which is how
a hypothesis's claimed runtime fraction gets checked against what actually changed.
Load the profiled software's
autotuning and solver leaves before interpreting kernel duration or its spread. Open the
[solver-tuning playbook](../playbooks/tune-solver.md) when the analysis becomes solver-specific.

Use [`conventions/batch-scripts.md`](../conventions/batch-scripts.md) before writing, modifying,
or reviewing any capture or submission script, or preparing a submit command;
[`conventions/repeated-work.md`](../conventions/repeated-work.md) at each study or phase closure
and at each work-mode change, to decide whether a procedure now repeated by hand should become a
tool; [`conventions/running.md`](../conventions/running.md) to reconcile a capture run's outcome;
[`conventions/measurement.md`](../conventions/measurement.md) for the per-run observed ledger and
for what makes two timings comparable; and
[`conventions/campaign-records.md`](../conventions/campaign-records.md) when the analysis belongs
to a multi-study campaign.

Route the durable residue of an analysis, and only that: a metric definition or measurement rule
to `conventions/`; a name-resolution rule, a mechanism, or a solver behaviour to
`software/<name>/`; a capture hazard or placement fact to `machines/<name>/`. Measured timings,
call counts, phase breakdowns, and campaign-specific optima remain in the working directory.

## Done

Performance analysis is done when the run's elapsed time is accounted for by phase; a ranked
hypothesis list exists, each entry carrying its evidence, the queries behind it, and a stated
runtime fraction or an explicit null; the capture conditions and capability gaps are recorded;
and what the capture could not observe is named rather than left as silence. Before closing, run
the automation checkpoint in
[`conventions/repeated-work.md`](../conventions/repeated-work.md) and record its outcome,
including candidates deliberately left manual. A transition to tuning, benchmarking, debugging,
or production requires another explicit operator declaration.
