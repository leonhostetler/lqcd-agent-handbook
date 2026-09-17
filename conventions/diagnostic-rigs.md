---
title: Diagnostic rigs — designing a multi-leg run and reading what it returns
summary: How to build a diagnostic run whose legs are interpretable, what a rig must gate on rather than merely print, which readings of a sampled resource trace are artifacts, and the ways a rig reports a clean result it did not earn.
scope: [universal]
load_when: Designing, scoring, or interpreting a diagnostic run made of several legs, or adding instrumentation, environment-variable comparisons, or resource sampling to an existing one.
evidence: reproduced
observations: 14
sources:
  - operator's screened split-grid deflation campaign records
observed: "2026-09-17"
observed_on:
  requirements: diagnostic-rig-design
review_by: "2027-09-17"
---

# Diagnostic rigs

A **rig** is one submission that runs several legs to answer a question: an environment-variable
comparison, a scale sweep, an instrumented reproduction, a memory probe. It is not a benchmark —
[`measurement.md`](measurement.md) governs turning runs into comparable numbers — and it is not the
script's safety, which is [`batch-scripts.md`](batch-scripts.md). This convention governs the rig as
an *experiment*: whether its legs can be believed, and how it fails while looking like it worked.

The failures below share one shape. **A rig that is broken usually reports success**, because the
evidence that would have contradicted it is the evidence that went missing.

## Before a leg is spent on a knob

**Only an outcome *change* proves a setting applied.** A leg whose outcome does not move proves
nothing about whether its variable took effect, which means a "clean" result from an inert knob is
indistinguishable from a real negative. Four legs in one campaign were spent this way: a variable
that governed host memory while the traffic under test was device memory; a variable the provider
does not honour at all; and a variable named in upstream documentation under a name the installed
version does not use — had that last name been used, the leg that actually found the mechanism
would have been a silent no-op.

So, before booking a leg:

- **Enumerate what the installed build accepts**, from the library's own query interface or its
  installed manual page, not from upstream documentation. Names change between versions and an
  unrecognised variable is ignored in silence.
- **Confirm it reached the process.** Most communication stacks can dump their effective settings
  into the log; turn that on and keep it on.
- **Confirm it governs the path under test** — the right memory kind, the right transport, the
  right layer. A variable can be real, applied, and irrelevant.

**Check the knob is in the path at all before spending a job on it.** In one case a single `grep`
established that the transport under study used the communication library's point-to-point calls
rather than a runtime copy, which is what made the library's caches relevant; without that, the
whole line of inquiry would have been aimed at the wrong layer.

**An isolating knob may move more than one thing.** A variable used as a single-variable control
can also disable an unrelated policy, change a selection heuristic, or alter overlap. Read the
source for every consumer before treating it as an isolation. Where it moves more than one thing,
it is a fallback-correctness check, not a measurement.

**Bound a cache rather than disabling it.** Setting a cache to zero can select a code path with
almost no field mileage, and such a path can be wrong in ways the normal path is not — in one
recorded case, silently, with whole messages lost and the completion call returning success.
Bounded values also stay closer to the configuration being characterised. If the question requires
the cache genuinely off, treat the result as provisional until the disabled path is independently
shown to be correct.

## Build the validity gate into the rig

**Printing a check and gating on a check are different things.** One rig printed the checksum of
its input file in every leg header; for five consecutive legs it printed the checksum of an *empty*
file, on screen, and scored every one of them anyway. The information was present, visible, and
ignored, because nothing branched on it.

The general rule: **advice in a document is not a guard in a script.** In the same campaign, a
procedure that would have prevented a total run loss existed in the investigation document and was
not implemented in the rig; and a wall-clock hazard was recorded in the plan's own task list while
the budget line that would have acted on it was absent, costing a leg of a fourteen-leg run. Where
a rig computes a value that bears on its own validity, that value must also be the value it
branches on, and a leg whose validity fails must abort rather than record a result.

Concretely, every rig should carry:

- **A declared validity gate per leg class, with a direction.** For a variable expected to be
  inert in some observable, assert that observable does *not* move; for one expected to act, assert
  it moves by roughly the predicted amount. Either way the script states the verdict rather than
  leaving it to the reader.
- **A positive control.** When probing further into a question, re-run a leg with a known,
  previously measured effect, purely to show the rig still reproduces it. If it does, the new legs
  mean something; if it does not, nothing in the run does.
- **A matched control at the same work count.** Without one, a rising trace is just a rising trace.
  The control is what converts an observation into a difference.
- **A self-check on the analysis, not only on the run.** Where a previous analysis was wrong in a
  specific place, assert the correct value there and refuse to be believed otherwise.
- **A correctness check, even in a resource rig.** Outputs unchanged, iteration counts matched, no
  tuning inside the measured region. A memory or time saving that changes an answer is not a
  saving, and this is how a setting that silently corrupted results was caught rather than adopted.

**Let an independent leg fail alone, and put the controls first.** The abort policy itself is set in
[`batch-scripts.md`](batch-scripts.md) and follows from which budget is scarce; a diagnostic rig
behind a queue wait is the case where continuing past a failed leg is correct. Two scheduling
consequences are this convention's own. **Order the noise-floor, repeat-baseline and control legs
early** — they are what every other leg is read against, so they are the last thing that should be
at risk from an earlier failure. One rig put its repeat baseline last, an early leg's failure took
it, and three otherwise good legs came back with nothing to judge them against; when the baseline
was finally measured it showed the previous run's headline effect had been noise. And **a leg that
continues past a failure is a leg that will be scored**, so the validity gates above stop being
hygiene and become load-bearing.

## A clean result the rig did not earn

**A check that looks for evidence of failure returns "no failure" for a log that is truncated,
empty, or was never written.** This is the single most expensive scoring defect recorded in the
corpus. One leg filled the filesystem; four later legs then aborted and had their logs cut off at a
handful of lines each. Counting occurrences of the failure string in a truncated log returns zero,
so **four aborting legs were scored clean**, and the results block printed two confident
conclusions built on them — one of which recommended starting an expensive instrumented build that
had no support whatsoever.

So **gate every negative check on a positive completeness assertion first**: an expected record
count, a terminal marker the leg writes in its own teardown, or a byte-size floor. A log that fails
the completeness test is `indeterminate` under [`running.md`](running.md), never a pass. The same
applies to the absence of an artifact, an empty query result, and a zero count of anything.

Note the direction. `running.md` covers the mirror failure — an unanchored pattern matching symbol
and parameter names and reporting failures in every healthy run. Both are live, and a rig usually
contains one of each.

**A leg that exits zero has not necessarily run.** An application that validates its input and
exits cleanly produces a successful status and no work; so does one killed before it reached the
work. Score on a positive marker of the work itself — a completion record, a count of the
operations the leg existed to perform, a nonzero resource figure — never on the exit status alone.
A guard for a behaviour change must assert the *changed behaviour*, not that the run survived.

**Check the ordering of the scoring function itself.** One rig's verdict routine tested a
diagnostic marker before it tested the exit status, so every leg carrying that marker received a
weaker label than it had earned. A scoring function is code and carries the same defect classes as
any other.

## Reading a sampled resource trace

Six rules, each recorded because getting it wrong produced a written-up conclusion that was later
retracted.

**A null from an instrument that cannot resolve the effect is not a null.** At one sampling
interval a device-memory trace looked like a single fixed step; at a ten-times finer interval it is
a steady per-unit creep. The coarse monitor could not have resolved it over the run's length, and
its silence was written up as evidence of absence. **Before believing a null, state what the
instrument could have detected** — its resolution, its coverage, and its window — and compare that
against the effect size in question.

**Discard the first work unit from resource traces, not only from timings.** `measurement.md`
excludes the first solve from a recurring *time* figure. The same exclusion is needed for memory
and other resource traces, and its failure mode there is worse: the working set is allocated during
the first unit, so any window including it reports a one-time *allocation* as a growth *slope*,
which then reads as a leak. One rig's own results block reported a flat control as accreting for
exactly this reason.

**Measure per unit of the thing that drives the effect.** A term that tracks work units must not be
reported per second. Doing so penalises any leg that is merely slower, and in one recorded case the
resulting artifact read exactly like a mechanism: a leg that was substantially slower than the
baseline was reported as consuming substantially *less* per second, when its per-work-unit
consumption was unchanged.

**A peak is a function of when the job stopped, if the curve has not saturated.** Compare slopes,
or compare at matched work — never end-points.

**Trust plateaus, not last samples.** Readings taken during an abort are junk; one run shows every
device at an identical value no earlier sample resembles. And where the sampler covers one node at
a coarse interval, **every measured peak is a floor**, not the peak: the true maximum across all
nodes, and between samples, is at least as high.

**Failed runs are data.** A leg that exhausts a resource gives a measured *floor* on a footprint no
successful run has bounded, and the failing request size in the error message sharpens it further.
Do not discard a failed leg from the analysis merely because it produced no primary result.

## Exhaust what is already on disk

**The first question of any resource investigation is what the completed runs already know.** In
one campaign every submission backgrounded a device-telemetry sampler, so thousands of samples
across seven finished jobs were sitting in the run logs — unread, while a model was being fitted to
a handful of scalar peaks quoted by hand. Reading them produced four results at zero allocation
cost, including one that retracted a published conclusion.

Instruments that run unattended accumulate evidence nobody has looked at. Before booking a leg,
inventory what the existing logs, telemetry, scheduler accounting and environment dumps contain.
This is also the cheapest form of the rule in [`repeated-work.md`](repeated-work.md): a parser for a
format the campaign keeps producing pays for itself quickly, and one that silently returns zero
legs on a new banner format is the failure that convention's negative test exists to catch.

## Instrumentation has preconditions of its own

**Prove the fault is reachable before building a detector for it.** One instrumented scheme was
built to test whether an index mapping was wrong; the mapping was subsequently *proven correct* by
reading the source, in an afternoon. Instrumentation costs a build, a rebuild everywhere the
library is linked, a run, and a removal plan — spend the cheaper effort first.

**Assert the topology a test depends on, from inside the job.** Where a leg's validity depends on
how ranks were placed, placement is part of the protocol and not a scheduling convenience. A
request to the scheduler is not a guarantee, and placement has been observed to come out other than
asked. Print the resolved placement before running anything, assert it, and fail the leg on a
mismatch — otherwise a leg that lands in the degenerate arrangement silently re-runs the case you
already have instead of the one you booked.

**Instrumentation that adds work inside the window of interest can mask the fault.** Record that as
an explicit alternative explanation for a quiet detector, and see
[`../modes/debugging.md`](../modes/debugging.md) for how to discriminate it.

## Core dumps at rank scale

**Size a core before enabling one.** Multiply the per-rank core size by the rank count and compare
it against the **quota headroom of the filesystem the core pattern writes to**, not its capacity. In
one recorded case that product was three orders of magnitude larger than the headroom available,
and the quota went in roughly twelve seconds — which truncated the shared input file the later legs
depended on, truncated their logs, and left the rig unable to open a log at all for the last eight.

So, in the script rather than in a document: direct the core pattern at a filesystem with room and
do not inherit it; cap how many cores are kept; and delete between legs.

**A truncated core is not a degraded core — it is worth nothing.** A debugger reads the signal from
the note at the front of the file and then stops, because the faulting instruction page and the
stack segment lie past the end of the file. The recorded pair yielded a signal and **zero caller
frames**. Before drawing any conclusion from a core, verify completeness — the size declared in its
own program headers against the file size — and record that check. A core that yields a signal and
no frames looks, at a glance, exactly like one that yields a stack.

## Sampling a process by name

**An exact-match process lookup silently fails for any executable whose name exceeds fifteen
characters**, because the kernel's per-process command field truncates there. One host-memory
sampler emitted a placeholder for every per-process column in two runs for this reason, producing no
data for the exact quantity it had been added to capture. Match the truncated form, or select by
something other than the name — and have the sampler assert it matched at least one process rather
than writing a placeholder.

## Evidence and limits

Empirical, converted from recorded episodes in one operator campaign rather than argued from
mechanism, except where a mechanism is named in the text. What transfers is the failure mode and
the guard; no rate, threshold, sampling interval, or cost figure is claimed, and the illustrative
magnitudes are reported only to convey scale. Each rule above cost something specific in its source
campaign, which is the only evidence offered that it is worth its space.
