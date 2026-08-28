---
title: Batch submission script safety and structure
summary: Invariants and required resolutions for writing, modifying, or reviewing a batch submission script on a shared system.
scope: [universal]
load_when: Writing, modifying, or reviewing a batch submission script, or preparing a submit command to hand to the operator.
evidence: operator
observed: "2026-08-28"
observed_on:
  requirements: batch-script-safety
review_by: "2027-08-28"
---

# Batch submission scripts

A batch script is the one artifact an agent writes that later executes on compute nodes with
the operator's full credentials. Nothing that constrains the agent's own tool calls
constrains it: no sandbox, no permission prompt, no approval step stands between the script
and the filesystem. Treat every line as code that will run unsupervised.

Nothing here names a scheduler. Directive prefixes, option names, and job variables come from
`conventions/scheduler-surfaces.yaml`, keyed by the machine profile's `scheduler.type`, with
any site override taken from the profile itself. Never write a directive or variable from
memory.

## Resolve these before writing a line

None of the four is inferable. Establish each, and say which are still unresolved rather than
choosing for the operator.

- **Node type.** From an explicit operator declaration, or the sole entry when a profile has
  one. A login host never reveals it.
- **Chargeable account.** See below — this is the one most often guessed.
- **Ceiling and balance.** An explicit campaign-scoped node-hour or GPU-hour ceiling must
  exist, with the current balance read from the working-directory ledger. Without a ceiling,
  prepare the job and hand the submit command to the operator; do not submit.
- **Scheduler class.** Compare purpose, node count, walltime, and concurrency against the
  machine profile's policy, and record the class chosen and why.

### The chargeable account is never inferred

Operators routinely hold several submission accounts, and a wrong one spends someone else's
allocation irreversibly. Do not take it from a scheduler or environment default, from the
first row of an accounting query, from another script in the working directory, or from an
archived campaign script — stale accounts survive longest in old scripts. Enumerating the
available accounts and presenting them is useful; selecting one is not. **A single visible
account is still not a declaration**: what an agent can see is not necessarily what the
operator may charge for this campaign. Record it beside the ledger in the working directory,
never in the handbook.

## Filesystem discipline

**A batch script is append-only with respect to inputs and shared data: read what exists,
create what does not.** Treat everything under shared or project storage as an immutable
input. Copy a file into the job's own directory before doing anything to it; never edit a
shared script in place, never overwrite an input, and never write output beside an input
merely because that directory happens to be writable.

**Run-owned mutable state is the deliberate exception.** A tunecache, checkpoint, or restart
file inside the run directory or an explicitly designated cache path is written and rewritten
by design. The invariant protects inputs and shared data, not every byte on disk.

**Declare one run root and put every write under it.** It must be job-private, keyed on the
scheduler's job-id variable — and on the array variables when the job is an array, because
array tasks otherwise collide. Create it so that a collision is loud rather than silent: a
requeued job reuses its job id, and silently reusing a populated directory is exactly the
overwrite this section forbids. Anything written outside that root needs a destination the
operator designated explicitly.

**Destructive operations.** The following are illustrative, **not exhaustive** — treat an
absence from this list as an oversight, never as permission:

- removal or unlinking of anything pre-existing, including find-driven deletion and directory
  removal;
- **truncating redirection onto an existing file**, and its equivalents: non-appending `tee`,
  copying or installing over an existing target, in-place stream editing, replacing a symlink,
  extracting an archive over a populated tree;
- moving or renaming pre-existing project or shared files;
- recursive permission or group changes, ownership changes, filesystem creation;
- deletion driven by a synchronisation tool's delete flag;
- broad process or job cancellation.

The question that decides every case nobody enumerated: **name the approved writable root
this write lands under, or do not write it.** Do not add cleanup logic for tidiness. Leaving
temporary files behind is always preferable to risking data that cannot be recreated.

## Variables and paths

Use `set -euo pipefail`, and quote every path expansion. Note that `set -e` does not reach
inside a job step launched by the scheduler's parallel launcher — check that step's exit
status explicitly.

**Reference only variables the machine profile declares.** A profile records the filesystem
roots its site provides and, in its scheduler block, whether the site exports a node-local
temporary directory at all. An explicit `null` there means the site provides none; an absent
key means nobody has established it, so ask rather than assume. The mechanism matters: under
`set -u` an undeclared variable aborts the job, and without `set -u` it expands to nothing,
turning a path into an absolute one at the filesystem root.

Never build a destructive target from an unvalidated variable, a `..` segment, a wildcard, or
command substitution. **Never rely on a preceding `cd` for safety** — a failed or unexpected
`cd`, a symlink, or a later edit to the script makes the target something else entirely.
Prefer creating new paths over recursive deletion of existing ones.

## Directives and submission

**Scheduler directives are writes too.** The output and error targets truncate by default, so
a review that only inspects commands will miss them; use the surface record's append option
when a job may be requeued. Pin the working directory and the output destination explicitly
rather than letting the scheduler inherit them — an inherited submission directory has already
put scheduler output somewhere it did not belong. Schedulers differ here in a way that
punishes assumption: some start a job in the submission directory, others in the home
directory.

**A batch script must not submit another job.** No nested submission or interactive
allocation unless the operator explicitly asked for a workflow that requires it. This is the
one mistake with unbounded, unrecoverable cost.

**No indirect destructive behaviour.** These rules follow the behaviour, not the syntax. They
apply equally inside another shell script, an inline interpreter command, an evaluated string,
an argument-dispatching helper, a generated script, a remote command, and any script the agent
itself wrote or modified.

## Review before submission

In this order, because the irreversible items come first:

1. Confirm the ceiling exists and the balance covers the reservation; debit at submit.
2. Confirm the account came from the operator, not from inference.
3. Read the complete script, including every directive.
4. List every command that creates, modifies, moves, or deletes, and every program or script
   it invokes.
5. Verify each write lands under a named, approved root.
6. Check for unsafe expansion, indirect execution, and nested submission.
7. Show the operator anything that could touch pre-existing data, and wait.

When uncertain whether an operation could affect shared or pre-existing data, leave it out and
ask. A non-destructive alternative that costs disk space is always the better trade.
