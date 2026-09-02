---
title: LQCD repeated work and the automation checkpoint
summary: When a repeated campaign action should become a tool, the periodic checkpoint that surfaces the candidates, and the exercise a new tool must pass before it is trusted.
scope: [universal]
load_when: Closing a study or phase, changing work mode, or deciding whether a repeated manual procedure should become a script.
evidence: operator
observed: "2026-09-02"
observed_on:
  requirements: repeated-work-automation
review_by: "2027-09-02"
---

# Repeated work and the automation checkpoint

The Tier-0 standing rule prefers a tool over prose *when a durable rule can be executed*.
That is an authoring rule about knowledge. This convention is its working-practice
counterpart: it governs the procedures a campaign performs repeatedly while it runs, and it
exists because those procedures are not visible when the campaign starts.

## Why a checkpoint rather than a trigger

Most handbook rules attach to an event — before writing a batch script, before sizing a
decomposition. This one has no such event. **The set of repeated actions emerges as a
campaign develops and changes shape as its phase changes**, so an instruction read once at
orientation is read against a set of repetitions that does not yet exist. A rule with no
natural trigger needs a recurring one, and the recurring one has to be cheap or it will be
skipped.

## The checkpoint

**At each study or phase closure, and at each work-mode change, ask one question:** what has
been done by hand more than twice since the last checkpoint, and should it now be executed?

Those two moments are chosen because they are exactly when the set of repeated actions has
just shifted, and because a work-mode change already forces the mode document to be re-read.
Keep the answer in the working project's own records, with the checkpoint date, the
candidates considered, and what was decided for each — including the ones deliberately left
manual, so the next checkpoint does not re-litigate them.

A candidate qualifies when all of these hold:

- it has a fixed procedure that does not require judgement at each step;
- it has run more than twice and is expected to run again;
- its inputs and outputs are already written down somewhere; and
- a wrong result would be hard to notice by eye.

The last condition is the important one. Automate the step whose failure is *quiet*, not
merely the step that is tedious.

## What hand repetition costs, and it is not mainly time

Prose procedure re-executed by hand costs tokens and wall-clock, but the load-bearing cost is
a **defect class that an executed contract does not produce**: transcription between adjacent
records, aggregation over the wrong subset, and re-derivation of quantities a contracted
extractor already emits. These are not reasoning errors and they do not correlate with care.
They are artifacts of moving values by hand, and reviewing the same values by hand is a weak
detector of them. See [`running.md`](running.md) for the reconciliation-specific ordering rule
this generalises.

## The counterweight: an unexercised tool is worse than the hand pass

A tool replaces a visible error class with a silent one unless it is made to fail on purpose.
Two recorded failures make the point from opposite directions:

- **A wrapper script that had never worked at all went undetected for a day**, because
  nothing exercised it as a tool; the hand fallback quietly absorbed its absence.
- **A verification harness reported success while modifying nothing.** Its negative-control
  path had been silently dropped in a rewrite, so it certified the very guards it was built
  to test. The rule that fell out of it is the general one: **a harness that cannot fail is
  the same defect as a guard that cannot fire.**

So a new tool is not trusted on the strength of a passing run. Before it replaces the hand
procedure:

1. run it against a known-good input and confirm the expected result;
2. **perturb the input so it must fail, and confirm it does** — a check that never fires and
   a check that always passes are indistinguishable from a passing run alone;
3. reject a no-op perturbation: if the negative test can succeed without changing anything,
   the test is vacuous;
4. record its version alongside the outputs it generates, so a later behaviour change is
   visible in the record rather than invisible in a regenerated table.

**Do not automate on the strength of this convention alone when the procedure is genuinely
short-lived, needs judgement at each step, or would cost more to verify than the remaining
repetitions cost to perform.** The checkpoint asks the question; it does not answer it, and
"leave it manual, reviewed at the next checkpoint" is a legitimate outcome to record.

## Evidence and limits

Empirical, from one operator campaign, converted from recorded episodes rather than argued
from mechanism. The defect classes, the two tool-failure modes, and the checkpoint timing are
what transfer; no rate, frequency threshold, or cost model is claimed. The "more than twice"
figure is a prompt for the question, not a measured boundary.
