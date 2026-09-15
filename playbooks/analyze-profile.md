# Analyse a GPU profile

This playbook is the procedure performance mode points at. It takes a capture and produces a
ranked, evidenced hypothesis list that tuning mode can act on. It does not apply changes:
applying one and remeasuring is an adaptive search and belongs to tuning under an explicit
declaration.

Load [`conventions/profile-metrics.md`](../conventions/profile-metrics.md) first. Every
quantity named below is defined there, and the readings it forbids are the ones this procedure
is shaped to avoid.

## 1. Establish the decision

State what the analysis is for before opening anything: the decision it serves, the region of
interest, and what would count as an answer. Establish the division of labour, and whether
capture is in scope — a capture run consumes allocation and falls under the ceiling and ledger
rules like any other job.

Identify the build that produced the capture: software revision and branch, build profile and
compiled capabilities, runtime options, decomposition, node type. **A suggestion is only
actionable if the change it names is available in that build**, and nothing in the profile
establishes that.

## 2. Establish what the capture contains

Run `tools/gpu-profile-summary.py schema <profile>` and read the capability notes in
`summary`. Verify what is present rather than assuming the requested tracing options took
effect: a capture-scope control that returns success without gating the trace is a known defect
class, and the resulting profile looks entirely valid.

Record the capture conditions that decide what the numbers mean — autotune cache warmth,
whether warmup or first-solve passes fall inside the window, which ranks were profiled. These
are not metadata. A figure read without them is not interpretable later, including by you.

Report every capability gap as a gap. Absent instrumentation supports no hypothesis about the
absent subsystem, and equally supports no claim that it is healthy.

Where capture is in scope rather than already done, read
[`conventions/profile-capture.md`](../conventions/profile-capture.md) **before** submitting. It
covers what cannot be recovered afterwards: that a profiler can exit 0 having written no report,
and that a format carrying no wall-clock anchor needs the capture to record one, or application
output can never be aligned to the trace absolutely.

## 3. Account for the elapsed time

Segment before aggregating: `phases`. A whole-profile average over a run whose parts differ
describes none of them. Prefer application annotations or a known application structure over
inferred segmentation where either exists.

Then account for the dominant phase's elapsed time, in a fixed order — kernel work, memory
transfers, communication, idle gaps — using `kernels`, `memcpy`, `transfer-overlap`, `mpi`,
`gaps`, `idle-attribution`, `streams` with the phase's `--start-ns` and `--end-ns`. Rank by
share of elapsed time, never by how unusual a number looks. Two of those are the ones that
change conclusions: `transfer-overlap` because a transfer class only costs what it exposes, and
`idle-attribution` because idle is the largest line in most phases and is otherwise unnamed.

**The account must close, and `idle-attribution` is what closes it — on the window, not only
on the idle.** Check `outside_kernel_span_s` first: the account closes as
`kernel_busy + idle + outside_kernel_span == window`, and where that last term is large the
window is mostly before the first kernel or after the last, so the idle split below describes
a fraction of it while still balancing exactly. That case is a finding in its own right and is
usually startup, teardown or a structural stall; the tool warns above 10% of the window.
Then split the idle: `idle-attribution` divides inter-kernel idle into MPI, host-API and OS
time and reports the residual — host time the capture located but did not name. A large
residual is the finding, not a gap in the analysis: read its gap
histogram, which usually separates diffuse per-launch overhead from a few structural stalls,
and read
[`conventions/profile-metrics.md`](../conventions/profile-metrics.md) on what it is an upper
bound for before attributing it to anything. A category reported null there is untraced, not
zero, and the residual has absorbed it.

On a multi-rank capture, run `cross-rank` before attributing any wait. A rank blocked on its
neighbours looks exactly like a rank with a problem of its own.

## 4. Drill with a purpose

State the question a query answers before issuing it. Use the subcommands first; reach for
`query` only when none answers the question, and keep it read-only and row-capped — an uncapped
scan of a multi-gigabyte profile is the ordinary accident, not the exotic one.

Record each query you keep. The prose session log deliberately omits tool output, so a query
that is not written into the record is not recoverable, and an analysis nobody can re-derive is
one that has to be re-trusted instead.

Stop when the ranked list stops changing. Depth is not evidence.

## 5. Cross-reference the code that produced the profile

This is the step a standalone analyser cannot take, and it is where most of the value is.

A demangled kernel name resolves to the source that launched it. Read that source to confirm a
suspected pattern rather than inferring it from a duration. Read the build log to establish
whether an option the suggestion depends on is actually compiled in. Where the software has a
handbook leaf covering the mechanism, load it: a cited leaf is a stronger premise than recall,
and it is checkable. For QUDA, [`software/quda/profiling.md`](../software/quda/profiling.md) is
the leaf that turns a demangled kernel name into the source file that defines it.

Reading source, build logs, and run logs is in scope here. **Changing any of them is not.**

## 6. Write the hypothesis record

Write the record into the working directory against
[`schemas/hypothesis.schema.json`](../schemas/hypothesis.schema.json). It is the deliverable;
the terminal summary is not.

Each hypothesis names its bottleneck and phase, the evidence as specific figures, the queries
those figures came from, the fraction of the phase's elapsed time attributable to it or an
explicit null, a concrete suggestion and the class of change it needs, what would refute it,
and whether it is grounded in the profile, in a named leaf, or in both.

The `bottleneck` field is deliberately free text rather than a fixed vocabulary. The obvious
vocabulary to adopt is known to be too coarse to discriminate — several distinct pathologies
collapse into one of its values — so fixing it before enough records exist to show which names
recur would import that defect and make it expensive to correct.

Three rules decide whether the record is worth anything:

- **Every figure cited is one the extraction emitted.** A hypothesis is an inference and an
  inference names its premises. A misremembered number reads as a precise, profile-grounded
  fact and nothing downstream rechecks it.
- **Ground every suggestion in the profile or in a named leaf, and say which.** Resting on
  neither is recall about an application's options.
- **Rank the list.** A correct diagnosis buried under four wrong ones is not the result that was
  led with.

Speedup bounds follow arithmetically from the claimed fraction and are computed, never
asserted.

## 7. Apply stop rules

Stop and report rather than continuing when: the account in step 3 cannot be closed and the
missing time is not explainable; the capture lacks the instrumentation the question needs; the
build cannot be identified, so no suggestion is known to be available; or the ranked list has
stabilised. Each of those is a result, not a failure — and three of them name the capture that
would answer the question, which is the more useful output.

## 8. Record and hand off

The claimed runtime fraction is a **prediction**. Record it before the next run and compare
after it with `tools/gpu-profile-diff.py`; a systematically inflated fraction is then a
detectable defect rather than an invisible one.

Hand to tuning: the ranked hypotheses with their evidence and queries, the capture conditions
the analysis depended on, which suggestions are unvalidated on the current stack or unavailable
in the current build, and what the capture could not observe — so tuning does not read silence
as a clean bill.

Durable residue is routed, and only the residue: a metric definition or measurement rule to
`conventions/`; a name-resolution rule, mechanism, or solver behaviour to `software/<name>/`; a
capture hazard or placement fact to `machines/<name>/`. Measured timings, call counts and phase
breakdowns stay in the working directory.
