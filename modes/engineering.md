# Engineering Mode

Engineering mode changes software on purpose: it adds or extends a capability, restructures
code, changes an interface, ports to a new platform, or reviews and validates a change another
author proposed. Its deliverable is a change whose behavior matches a stated contract, validated
to a stated scope and ready for review. The mode changes only when the operator explicitly
declares a different work mode.

This is a **work** mode. It grants no write access to the handbook; that is decided by the
handbook mode, and developer mode is a different thing with a deliberately different name.

## Boundaries with the other work modes

The mode follows the immediate decision, not the fact that source is being edited.

- **Debugging** finds the cause of a defect in code that already exists and makes the narrowest
  justified correction. A defect in the change under construction is part of engineering; a
  defect found in code the change did not touch is a debugging phase, declared as one.
- **Tuning** keeps a source change *because it measured better* against an objective. When
  candidates are selected by measurement, the work is tuning, and `modes/tuning.md` governs
  trials that change source. When the change is required by a capability, structure, or
  interface contract and is accepted on correctness, it is engineering.
- **Performance** diagnoses where time goes. Engineering may ask for a performance check of its
  change, but the profile analysis is a declared performance phase.
- **Benchmarking** measures a frozen candidate. A claim about the speed of a finished change is
  a benchmark claim and needs that mode's contract.
- **Building a stack** to run existing software is not engineering. Use
  `playbooks/build-lqcd-stack.md` under whatever mode the work is in. Changing the build system
  itself is engineering.

## Establish the task

Before editing, building, or running anything:

1. State the change contract: the behavior or capability to be added or altered, the acceptance
   criteria, and what must **not** change, including results that must stay bitwise identical,
   results that may change within a stated tolerance, defaults, and supported options.
2. Identify whose change it is. For your own change, establish the target branch it will be
   reviewed against. For another author's change, establish the exact head under review, its
   base, and what the operator wants back: a verdict, findings, proposed patches, or a retest.
3. If the operator has not already said, ask whether the task is **analysis-only** or
   **hands-on**. Under the standing safeguards in canonical `AGENTS.md`, hands-on authorizes
   edits, builds, and runs within the stated project scope, not commits, pushes, pull-request
   actions, review comments, or scheduler submission.
4. Detect the commit and branch of every checkout involved, working-tree changes, build
   capabilities, and the machine, node type, and nearest validated stack. A change under
   construction never has a validated stack; report the unvalidated scope.
5. Load `software/<name>/development.md` for every software project the change modifies. It
   owns that project's formatting, testing, interface, and review rules; this mode does not
   restate them.

## Engineering method

1. **Inventory the interfaces before writing code.** List every boundary the change crosses:
   exported headers and structure layouts, library binary interfaces, enumerations and their
   values, file and checkpoint formats, input grammars, environment variables, and defaults.
   For each, name the consumers. A change to a structure layout or exported declaration
   invalidates every consumer binary compiled against the old one, even when the consumer's
   source is untouched, because the layout was compiled into it.
2. **Keep the trees separate.** Build the base, the change, and every proposed fix from their
   own checkouts or worktrees and their own build directories. Never modify a checkout under
   review in place, and never move one to a new head; a new head gets a new tree. Every build
   gets its own consumer binaries and its own autotuning cache, because a dynamically linked
   consumer runs whichever library its recorded search path finds.
3. **Build the base first, with the same options.** A failure that the base shares is not a
   finding against the change. Differential evidence, base versus change under one build and
   run recipe, is what makes a finding attributable.
4. **Derive the build matrix from dispatch, not option names.** Compile every legal combination
   of the options the change touches that selects a different code path, including the rare
   ones. `modes/debugging.md` method step 8 describes the state table; the same table decides
   which combinations must build here.
5. **A new test must fail without the change.** A regression test that passes on the base and
   on the change demonstrates nothing about the change. Run every new test against the base, or
   against a deliberately broken variant, and record that it failed there. This is the rule in
   [`conventions/repeated-work.md`](../conventions/repeated-work.md) that a harness that cannot
   fail is a defect, applied to a test.
6. **State numerical equivalence claims as what they are.** "Bitwise identical to the previous
   implementation" and "agrees within tolerance" are different claims and need different tests.
   When a change alters a numerical representation, test at the representation's limits, such as
   exponent range, underflow, and the precision floor a requested tolerance can fall below, not
   only at typical values. Pair self-consistency checks with an independent reference, as
   `modes/debugging.md` method step 4 requires.
7. **Validate in layers**, as `modes/debugging.md` method step 15 lays out: source mechanism,
   compilation across the matrix, focused runtime checks, regression coverage, and integration
   with real consumers. State which layers were completed and never claim beyond what was built
   and executed.
8. **Scope every finding on another author's change.** A finding carries the head and base it
   was observed on, the reproducer, and the build options and run recipe. A proposed fix lives
   in its own tree as a patch against the reviewed head. When the head moves, re-read each
   finding against the new head; a finding fixed at one head says nothing about the next until
   it is retested there.

## Permissions and safeguards

- In analysis-only work, inspect and report without editing, building, or running.
- In hands-on work, keep the diff limited to the stated change. Do not fold unrelated fixes,
  refactors, or formatting into it; report them separately.
- Leave the working tree unstaged and uncommitted, summarize the validation, and suggest a
  commit message. Never stage, commit, push, comment on, or update a pull or merge request
  unless the operator explicitly asks for that specific action.
- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour
  ceiling and a working-directory budget ledger. A build on a compute node is a job. Without
  both, prepare the job and give the submit command to the operator.

## Tools and routing

Use the working project's instructions, the software's `development.md`, the selected machine
profile, and the nearest stack before applying machine- or software-specific advice. Use
`playbooks/build-lqcd-stack.md` when the change needs a stack built or rebuilt.

Load [`conventions/batch-scripts.md`](../conventions/batch-scripts.md) before writing,
modifying, or reviewing any batch script or preparing a submit command. A validation matrix is
many builds and runs, and each one is a submission.

Load [`conventions/code-changes.md`](../conventions/code-changes.md) before writing or reviewing
a source change; what its comments, messages, and tests may reference is defined there.

Load [`conventions/diagnostic-rigs.md`](../conventions/diagnostic-rigs.md) before designing,
scoring, or interpreting a validation run made of several legs, and
[`conventions/running.md`](../conventions/running.md) to reconcile each run's outcome.

Load [`conventions/repeated-work.md`](../conventions/repeated-work.md) at each study or phase closure and at each work-mode change, to decide whether a procedure now repeated by hand should become a tool. A retest procedure repeated once per head is a common candidate.

Keep findings, patches, reproducers, build logs, and measured figures in the working directory.
Knowledge about an unmerged change is not handbook knowledge until the change merges and its
commits resolve on the default branch.

## Done

Engineering is done when the change meets its stated contract; the interface inventory and the
consumers rebuilt against it are recorded; the build matrix, new tests and their failing-base
evidence, and the completed validation layers are named; unvalidated combinations and open
findings are listed; and the tree is handed off unstaged with a suggested commit message, or,
for another author's change, the verdict and findings are scoped to the head they were
observed on. Before closing, run the automation checkpoint in
[`conventions/repeated-work.md`](../conventions/repeated-work.md) and record its outcome,
including candidates deliberately left manual. A transition to debugging, performance, tuning,
benchmarking, or production requires another explicit operator declaration.
