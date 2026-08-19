# Debugging Mode

Debugging mode finds the cause of incorrect, unstable, or unexplained behavior and establishes
the narrowest justified correction. It changes only when the operator explicitly declares a
different work mode.

## Establish the task

Before editing, building, or running anything:

1. Obtain the problem statement and identify the code checkout, reproducer, expected behavior,
   and observed behavior. Detect repository and build state rather than asking for facts already
   available from the working directory.
2. If the operator has not already said, ask whether the task is **analysis-only** or
   **hands-on**. Hands-on means permission to edit, build, recompile, or run within the
   stated project scope; under the standing safeguards in canonical `AGENTS.md`, it does not
   authorize commits, pushes, pull requests, or scheduler submission.
3. Record the exact commit and branch, working-tree changes, build capabilities, runtime
   parameters, defaults, overrides, and relevant project instructions. Treat persistent notes
   as leads until reconciled with the current source and environment.
4. Resolve the machine, node type, and nearest validated stack. No matching stack is normal in
   debugging mode; report the unvalidated scope instead of treating it as established behavior.

## Debugging method

1. Convert the symptom into an explicit correctness invariant. Trace the value or state that
   controls that invariant through every relevant construction and call path; distinguish
   control state from labels, diagnostics, and other presentation-only state.
2. When data are distributed, make invariant checks collective. A root-rank or single-partition
   scan establishes only local cleanliness. Reduce the failure predicate or count across all
   ranks and, on failure, retain a bounded localization record with rank, global index,
   component, and applicable right-hand side or parity. State explicitly when only local
   coverage was available.
3. Before calling a rerun a reproduction, compare a reproduction fingerprint: executable and
   input identity, RNG seed and state plus consumer order, rank topology and decomposition,
   tunecache, resident objects, and other persistent state. Regenerated data or a changed
   decomposition defines a different trial unless equivalence is demonstrated. If a symptom
   disappears, audit this fingerprint before attributing the change to a fix or to
   nondeterminism.
4. When algorithm semantics are uncertain, construct the smallest independent mathematical or
   computational reproducer. Prefer an existing result or a one-variable differential check
   before requesting another allocation-consuming run.
5. Inspect what tests actually execute. Check defaults, test-harness rewrites, disabled
   features, and interactions among options; a parameter matrix is not coverage when the
   triggering feature is overwritten before execution.
6. For an experiment intended to change control flow or remove work, derive the expected counts
   of semantically meaningful calls or markers from source before running it. Compare observed
   counts with that prediction. Counts can establish reachability and work removal; they do not
   establish numerical correctness, so pair them with an invariant or reference comparison.
7. Put a correctness guard at the shared API or construction boundary when one exists. Express
   the supported invariant directly and reject every unsupported case, rather than enumerating
   only the failures known today.
8. When a fix changes transformed, cached, or restarted state, trace every representation
   through its write, read, restart, and external-output boundaries. Internal consistency does
   not establish that the boundary contract is correct.
9. Validate in layers: source mechanism, independent reproducer, compilation, focused runtime
   check, regression coverage, and integration exercise. State which layers were completed and
   never claim beyond the capabilities that were built and executed.

## Permissions and safeguards

- In analysis-only work, inspect and report without editing, building, recompiling, or executing
  the target workload.
- In hands-on work, make only changes needed to test the stated hypothesis. Do not broaden a
  correctness fix into a feature, optimization, or refactor without operator direction.
- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour
  ceiling and a working-directory budget ledger. Without both, prepare the job and give the
  submit command to the operator.
- Before any proposed submission, compare purpose, node count, walltime, and concurrency with
  the selected machine profile. When appropriate, prefer the documented debug or interactive
  class for faster turnaround. Record the suitability decision, selected class, and reason;
  this never overrides site policy or the budget rule.

## Tools and routing

Use the working project's instructions, the detected software profile, the selected machine
profile, and the nearest stack before applying machine- or software-specific advice. Use
`compute-sanitizer`, `valgrind4hpc`, or vendor diagnostics only when available and
appropriate to the suspected failure. Use `playbooks/build-lqcd-stack.md` when debugging
requires a new or rebuilt stack.

Keep raw outputs, diagnostics, temporary models, and run state in the working directory.
Only durable conclusions that pass the handbook admission and privacy rules may be proposed
for canonical knowledge.

## Done

Debugging is done when the cause is demonstrated or the remaining uncertainty is explicitly
bounded; the reproducer, environment, and violated invariant are recorded; any hands-on fix
is validated to its stated scope; and unresolved integration or regression risks are named.
A transition to performance, benchmarking, tuning, or production requires another explicit
operator declaration.
