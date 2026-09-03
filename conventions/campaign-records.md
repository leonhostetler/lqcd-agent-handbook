---
title: Campaign records, ownership, and what must stay computed
summary: How to decide which document owns a fact, which records must be append-only or immutable, what must never be stored, and the four records that exist only because an allocation is real.
scope: [universal]
load_when: Opening or reorganising a multi-study campaign against an allocation, or deciding which document owns a new kind of fact.
evidence: operator
observed: "2026-09-03"
observed_on:
  requirements: campaign-record-architecture
review_by: "2027-09-03"
---

# Campaign records, ownership, and what must stay computed

Where a campaign's observations live is already settled: with the campaign, not in this
repository. This convention is the next question down — how to organise them so they stay
true over months of runs.

**These rules are corrections, not a template.** They come from a multi-study campaign that
reorganised its own records while running, and each one is stated with the failure that produced
it. **Do not copy a directory layout, a file naming scheme, or a vocabulary from any campaign**,
including the one behind this page. Derive your own from the first rule; a structure inherited
without its derivation is copied wrongly.

## Decide who owns each fact

**Assign an owner by lifetime and mutability, not by topic.** The question is not "what is this
fact about" but "how long is it true, and what happens to it when it changes". A document whose
content is overwritten at every reconciliation cannot own a fact that must outlive one study. A
record that is immutable once closed cannot own a fact that will be amended. A family- or
class-scoped record cannot own a fact that spans families.

**When no existing document's lifetime and mutability match, that is a missing document, not a
place to squeeze the fact in.** The campaign behind this page discovered a whole class of durable
cross-cutting knowledge with no owner: its volatile-state file overwrote itself, its study
decisions were immutable and study-scoped, and its candidate-ordering records were narrower than
the facts. Each candidate home was disqualified by lifetime or mutability alone. Squeezing the
fact into the nearest one would have hidden the gap and lost the knowledge at the next
reconciliation.

Three mutability classes are usually enough, and mixing them in one file is the failure this rule
prevents:

- **Immutable once closed** — the submitted inputs, raw artifacts, and decision of a completed
  run. Never edited afterwards; superseded only by a new record that cites it.
- **Append-only** — resource ledgers and evidence ledgers. Corrections append a replacement row
  carrying the identifier of the row it supersedes; a recorded row is never edited, so the history
  of a correction survives.
- **Amended in place** — durable conclusions and open questions, which cite immutable evidence
  rather than restating it.

**Retrospective and prospective knowledge are different fact classes.** What runs have taught you
and what you predict about a candidate you have not run behave differently: the first is settled
and accumulates, the second carries a confidence tier, a declared scope, an invalidation list, and
a falsifier. Keep them in separate records with an explicit graduation rule — **a finding becomes a
prospective rule only when it constrains a candidate nobody has run.** Merging them produces a
document whose entries cannot all be trusted the same way, and a reader has no signal about which
is which.

## Keep the records true

**Derived state is computed on demand, never stored.** Any quantity that is a function of a ledger
— a total, a readiness verdict, a count of candidates in some state — goes stale the moment the
ledger gains a row, and a stored copy is indistinguishable from a current one at a glance. Compute
it with a committed tool and let the ledger be the only authority.

The failure is not hypothetical and it is not rare: in the campaign behind this page, a consumed
node-hour total restated in a summary document went stale **three separate times** while the
ledger beside it was correct throughout, and each staleness survived until someone happened to
check. **A summary sentence containing a number is a cache with no invalidation.** Prefer a
pointer to the ledger, or a generated line, to a number a human retyped.

**An offline result needs a tool that regenerates it and a check mode that verifies it.** Desk
computations — a feasibility bound, a memory model evaluated over a candidate space, an
enumeration of legal placements — are how a campaign answers questions without spending its
allocation, which makes them load-bearing. Require every one to be reproducible by a committed
tool with a mode that diffs its output against the committed result, and to record the model
identity, its evidence tier, and its limitations. Re-run that check after any software or model
change before continuing to rely on a conclusion that cites it.

Without it a desk result is an assertion with a plausible shape, and it will be cited long after
the model under it moved. An offline screen also grants no authority and never supersedes a
measurement: it ranks what to measure next.

## The records that exist because the allocation is real

A campaign that submits jobs is spending something irreversible, and four records follow from
that alone.

**A budget ledger with explicit reservations, released at reconciliation.** Reserve before
submitting, reconcile against the actual charge afterwards, and record both. **Reserve on the
requested wall time plus a margin, not on the expected run time**: a job that times out is charged
for the wall it actually consumed, which the scheduler may let exceed the request, so a
reservation computed from expected duration understates the worst case exactly when the worst case
happens.

**An authority record naming a ceiling, a maximum submission count, and the chargeable account.**
The Tier-0 standing rules already forbid submitting without a ceiling and forbid inferring
the chargeable account, and every session carries them. What this adds is that the grant
is a **record with a lifetime**: it is opened explicitly, consumed against a counter, and closed
explicitly with its unused ceiling and submissions stated. An expired or exhausted grant that was
never closed reads like live authority to the next session.

**Predictions recorded before submission, never after.** A prediction written after the result is
known tests nothing, and no amount of care in writing it recovers the difference. This is also
what makes later knowledge export tractable rather than a mining expedition: an observation whose
prediction preceded its run can support a general claim, and one harvested retrospectively cannot,
however good the data. **Deciding after the fact which rules a completed run bears on does not
change what that run can support** — so name the candidate rules in the study record before the
job is submitted, including rules the run only incidentally touches.

**A candidate registry with lifecycle states.** Record each candidate's state — proposed,
feasible, validated, retired, and why — so a candidate that was ruled out stops resurfacing in
every later review, and so the reason it was ruled out survives the study that ruled it out.

## What not to carry across campaigns

Directory layouts, file names, label grammars, and result vocabularies are instantiations. They
encode one campaign's parameter space and scheduler, and they are the part most likely to be
copied and least likely to fit. Carry the rules above; derive the rest.
