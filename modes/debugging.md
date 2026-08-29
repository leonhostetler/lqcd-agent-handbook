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
   nondeterminism. For golden or reference artifacts, record both the producing code identity
   and the semantic contract they represent. An intentional correctness or normalization change
   invalidates an old golden result even when its filename and input are unchanged.
4. When algorithm semantics are uncertain, construct the smallest independent mathematical or
   computational reproducer. Prefer an existing result or a one-variable differential check
   before requesting another allocation-consuming run. Forward/adjoint duality, agreement
   between implementations that share a convention, and other self-consistency checks can all
   pass with the same normalization or boundary error; pair them with an independent oracle such
   as a free-field limit, analytic coefficient, host reference, cross-code comparison, or
   controlled convergence limit.
5. For an instrumented reproducer, minimize the work needed to exercise the invariant, not the
   rank count in isolation. Estimate completion time and resource cost from per-rank work and
   diagnostic overhead; fewer ranks can increase elapsed time. Prefer a topology already shown to
   complete, and keep it fixed across before/after comparisons unless topology is the tested variable.
6. Inspect what tests actually execute. Check defaults, test-harness rewrites, disabled
   features, and interactions among options; a parameter matrix is not coverage when the
   triggering feature is overwritten before execution. For distributed behavior, include a
   non-degenerate topology in which the affected halo, collective, or state transition must run,
   and retain a branch marker, topology record, or semantic event count as reachability evidence.
7. Treat compiler warnings as a set of root causes and reachability evidence, not a raw line
   count. Group repeated diagnostics by originating definition and configuration. Before
   suppressing or annotating an unused symbol, trace its intended callers and guards: an expected
   central routine becoming unused may mean the target path was compiled out or its dispatch was
   bypassed. Rebuild every affected legal configuration and compare the resulting warning set.
8. For interacting compile-time features, derive a state table from actual dispatch rather than
   option names. Distinguish capability, provider, owner, consumer, and cleanup state. Guard
   allocation, handoff, use, and cleanup by their own semantic preconditions; identical macro
   expressions are not required when the operations answer different questions. Compile the
   rare legal combinations that select different branches.
9. For an experiment intended to change control flow or remove work, derive the expected counts
   of semantically meaningful calls or markers from source before running it. Compare observed
   counts with that prediction. Counts can establish reachability and work removal; they do not
   establish numerical correctness, so pair them with an invariant or reference comparison. If
   source inspection says a path exists or is enabled while the predicted events never occur,
   treat the disagreement as evidence that an intervening state transition makes the path
   unreachable; reconcile the full state machine before blaming timing noise.
10. Put a correctness guard at the shared API or construction boundary when one exists. Express
    the supported invariant directly and reject every unsupported case, rather than enumerating
    only the failures known today.
11. When a fix changes transformed, cached, or restarted state, trace every representation
    through its write, read, restart, and external-output boundaries. Internal consistency does
    not establish that the boundary contract is correct.
12. Treat a change from eager to lazy work as a lifecycle change. Inventory every consumer and
    possible first-use order, the provenance metadata needed to interpret stored inputs, the
    operator, links, boundary conditions, precision, and persistent state present at the deferred
    point, and any output or save side effects that disappear when no consumer runs. Exercise
    cold-start cases in which the first consumer requests each supported transformed representation.
13. For dynamic-analysis campaigns, preserve a baseline pass without newly generated suppressions
    and classify findings by stack and provenance before adding narrow, documented suppressions.
    Track coverage by tool, configuration, and rank; a timeout leaves every unfinished cell
    incomplete even when earlier cells passed. Verify a fix by the disappearance of the targeted
    stack and its exact count or byte delta, not by an aggregate zero-error summary.
14. At host-device and other transfer boundaries, establish what each diagnostic tool can
    observe. Do not assume a host memory checker witnessed device-kernel writes or that a device
    sanitizer validated host-only work. Trace producer, transfer, and consumer before classifying
    undefinedness or ownership, then corroborate with a tool that observes the producer or with an
    independent checksum, reload, or result invariant.
15. Validate in layers: source mechanism, independent reproducer, compilation, focused runtime
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

Load `conventions/batch-scripts.md` before writing, modifying, or reviewing any batch script or
preparing a submit command. A diagnostic rerun is still a submission, and debugging is where a
script is most likely to be edited quickly under pressure.

Keep raw outputs, diagnostics, temporary models, and run state in the working directory.
Only durable conclusions that pass the handbook admission and privacy rules may be proposed
for canonical knowledge.

## Done

Debugging is done when the cause is demonstrated or the remaining uncertainty is explicitly
bounded; the reproducer, environment, and violated invariant are recorded; any hands-on fix
is validated to its stated scope; and unresolved integration or regression risks are named.
A transition to performance, benchmarking, tuning, or production requires another explicit
operator declaration.
