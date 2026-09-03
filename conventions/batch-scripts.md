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

### The work must be projected to fit, and the limit belongs to the queue class

**No job should be submitted whose projected work cannot finish inside the limit it is
authorized for.** Project from *measured* stage times — setup, the slowest compatible recurring
unit times the number required, and the workload's own overhead — with a margin, and require the
total to fit. Where no measurement exists, the first job is itself the bounded probe that produces
one; that is a different thing from submitting a full run and hoping.

**The walltime limit is a property of the selected queue class, not of the site**, so never
hardcode it into a plan or a stop rule. Record the class, its limit, and where that limit came
from, and recompute whenever the class changes. The asymmetry is worth stating because it is easy
to get backwards: **a projection that fits a short queue also fits a long one; a projection that
fits a long queue says nothing about a short one.**

When the projection does not fit, the move is a bounded probe or a different queue — never a
submission in the hope that the work finishes.

### A record field may contain only variables, never a typed constant

Where a job writes its own provenance — the hierarchy it built, the state it started from, the
parameters it used — **every such field must be derived from the variable that drives the run.** A
hand-typed constant records what the author believed when they wrote the line, not what executed,
and the two part company silently the moment the script is copied and edited. The result is a
provenance record that is confidently wrong, which is worse than an absent one because nothing
downstream has reason to doubt it.

The exception worth naming is a value *computed* from the run's own inputs, which cannot drift from
them.

**One instance of this is not the fix.** In a recorded case the defect was found and patched, and
reappeared one event later in a line the patch did not cover — three times in all. When a typed
constant is found in a record, search every other field of the same kind rather than correcting the
one that was noticed.

### A runnable artifact is not one of these

**The presence of something that would run is not a precondition satisfied.** A workspace that
has submitted before is full of launchers, parameter files and input sets that still execute:
an earlier study's trial directory, a frozen campaign kept for provenance, a handoff or example
tree. None of them establishes a node type, an account, a ceiling or a scheduler class, and
finding one is not a reason to submit.

**The mechanism is that the two halves of a past submission decay at different rates.** What
made it legitimate — a live grant, a balance, a declared account, a verified baseline, an open
question worth the allocation — was external to the file and has since expired. What remains in
the tree is the executable half, complete and plausible, carrying no trace of the half that is
gone. A script cannot look expired, so its presence reads as permission when it is only
residue.

So treat a historical study directory as **evidence to read, not a template to run**. Where a
past launcher is genuinely the right starting point, copy it into the new job's own directory
and re-resolve all four preconditions from scratch rather than inheriting them — every value it
carries is a claim about a submission that already happened. The stale-account trap below is the
most expensive instance of this, not a separate rule.

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

**Command substitution takes the status of the command inside it, and that reaches teardown.**
`sum=$(checksum "$f" | field 1)` assigns the *pipeline's* status, so under `set -euo pipefail` a
missing file aborts the script at that line. In a teardown path this is doubly costly: the job
loses the terminal records it was about to write — including the ones that say how it ended — and
exits with a status describing the teardown rather than the run, so the failure is reported as
something it was not. Guard such assignments explicitly, or accept a failing status with `|| true`
where absence is legitimate, and never let the last records depend on a file that may not exist.

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
8. Run the script with every external effect stubbed, and prove each guard fires.

`tools/run-batch-script-check` mechanises the parts of steps 3 to 6 that a machine can
decide — nested submission, destructive operations, hardening, indirect execution, and the
directives whose defaults are unsafe. Pass `--machine` to enable the directive checks, which
need the profile. It is advisory: it reports what it examined and states plainly that
approved-root, invoked-program, and intent checks were not performed. Running it does not
discharge this review; failing to run it is not an excuse for skipping one.

When uncertain whether an operation could affect shared or pre-existing data, leave it out and
ask. A non-destructive alternative that costs disk space is always the better trade.

### Step 8: a guard that never fires looks exactly like one that passes

Steps 3 to 7 and the checker are **static**. They can tell you a guard is present and
plausible; **none of them can tell you it fires.** A guard with an inverted test, a variable
that is empty at the moment it is read, or a condition that silently exits zero reads as
correct on every inspection and protects nothing on the night. Submissions have been lost
this way, to defects catchable on a login node for no allocation at all.

So execute the script before submitting it, with everything that reaches outside replaced by
a stub:

- **Run a copy, never the real job directory.** The point is to reach *past* the preflight,
  which means the script will create and write things.
- **Stub every external effect**: the parallel launcher, the modules system, scheduler
  queries, compiler or version probes, and any sleep. Stub the submission command itself so
  that it **refuses** — a batch script must never submit another job, and the refusal turns
  that mistake into a visible failure.
- **Make sure the stubs win.** A shell startup file or an exported shell function can put the
  real command back ahead of them; clear both, or the run silently tests nothing.
- **Do not fake anything verified by checksum.** No stand-in satisfies a hash, and those
  inputs are read-only, so leave them at their real paths. A guard that checks only a *size*
  can be satisfied by a sparse file, so even a very large input costs no space.
- **Positive control:** on correct inputs the script must run to completion. If it does not,
  that is a defect in the script, not in the harness — do not submit.
- **Negative test, one guard at a time:** perturb the input that guard protects and require
  the run to fail. **A perturbation that changed nothing is not a test** — confirm the file
  actually differs before believing the result, because an expression that matched nothing
  produces the same clean output as a guard that works.

A workspace that submits often should script this rather than repeat it by hand. If it does,
the harness itself is subject to the same rule it enforces: it must be made to fail on
purpose before it is trusted, since a harness that cannot fail is the same defect as a guard
that cannot fire.
