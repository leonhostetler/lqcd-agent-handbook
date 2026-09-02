# Production Mode

Production mode executes and monitors a settled campaign. The workload, software stack,
runtime parameters, resource shape, completion contract, and correctness checks are frozen
before campaign work begins. Production mode does not select among candidates or establish new
performance claims. It changes only when the operator explicitly declares a different work
mode.

A production campaign may outlive any one agent session. Its authoritative operational memory
must therefore be durable, structured state in the working project, not an agent's context,
chat transcript, shell history, scheduler history, or handbook content.

## Establish the campaign contract

Before preparing, submitting, monitoring, or reconciling campaign work:

1. Establish the division of labour: inspect or monitor only, prepare-and-handoff, or
   prepare+submit+monitor. Declaring production mode does not authorize project edits, rebuilds,
   Git actions, scheduler submission, cancellation, or deletion unless the operator included
   those actions in scope.
2. Detect the software commit and branch, working-tree state, machine, node type, nearest
   validated stack, build capabilities, runtime environment, and persistent runtime state.
   Record every unvalidated dimension rather than treating a nearby stack as coverage.
3. Record the operator-approved production setup and workload in the working directory. Freeze
   executable and dependency identities, generated inputs, placement, decomposition, batching,
   runtime parameters, persistent setup state, expected artifacts, and completion, numerical,
   and scientific acceptance checks.
4. Create a campaign manifest whose entries have stable work-unit identifiers. For each entry,
   record its input identity, dependencies, expected artifacts, acceptance contract, and current
   campaign status. Declare whether the scope is closed or new units may be enrolled under a
   frozen operator-approved rule. Derive scheduling views from this manifest; do not use a
   last-run cursor or directory presence as the authority for completion.
5. Establish the campaign-scoped node-hour or GPU-hour ceiling and append-only budget ledger
   required by canonical `AGENTS.md`. Record allowed concurrency, submission cadence, retry
   limits, and the operator's escalation conditions.
6. State the retention and recovery policy for raw outputs, scheduler records, environment
   captures, generated intermediates, persistent caches, derived products, and failed attempts.
7. Choose a persistent campaign control root in the working project. Make it discoverable from
   the working project's instructions or another stable project-owned entry point. It must
   survive compute jobs and agent sessions, must not depend on node-local scratch, and must be
   protected or backed up according to project policy.

## Preserve campaign memory across sessions

Maintain these campaign-owned records under the control root:

- a **campaign contract** containing scope, operator authorization, frozen setup, workload,
  acceptance rules, resource limits, retention policy, and schema version;
- a **campaign runbook** containing the validated preparation, submission, monitoring,
  reconciliation, restart, and recovery procedures; artifact layout; routine commands; and
  escalation boundaries;
- a machine-readable **work-unit manifest** defining the currently authorized set and the
  immutable identity and dependencies of each unit, with versioned append-only enrollment when
  the campaign contract permits rolling scope;
- an append-only **attempt and event ledger** recording state transitions, scheduler identifiers,
  timestamps, evidence locations, dispositions, retries, and supported failure classes;
- the append-only **budget ledger** required by canonical `AGENTS.md`, reconciled against actual
  scheduler accounting;
- a **decision, knowledge, and anomaly log** recording evidence-backed operational conclusions,
  approved exceptions, environmental drift, rejected hypotheses, unresolved contradictions,
  invalidation conditions, and why each nonroutine action was taken; and
- a concise **handoff record** naming the last reconciliation time, in-flight and indeterminate
  attempts, blocked or exhausted units, active alerts, remaining budget, known hazards, and the
  next safe actions.

The machine-readable manifest and ledgers are authoritative. The handoff is a restart index, not
a second job database; derive it from structured state when practical and never let it silently
override contradictory raw evidence. Use unambiguous timestamps, preferably UTC, and record the
writer and tool or schema version for every state update.

At the start of every agent session:

1. Read the working project's instructions, campaign contract, runbook, current handoff,
   manifest, attempt ledger, budget ledger, and unresolved decisions before taking operational
   action.
2. Detect current software, filesystem, and machine state and compare them with the frozen
   contract. Long campaign duration makes module, executable, dependency, quota, policy, and
   storage drift plausible even when no campaign file changed.
3. Reconcile every recorded in-flight or indeterminate attempt with the scheduler and observed
   artifacts. Do not assume the previous session ended immediately after its last recorded
   action.
4. Recompute the pending and retryable set from the manifest and accepted evidence. Do not resume
   from a remembered position, transcript summary, or cursor.

Before ending a session that performed or observed campaign work, atomically update the ledgers
and handoff with the last verified state, consumed and reserved budget, in-flight attempts,
unresolved evidence, alerts, and next safe action. A session ending does not pause scheduler
jobs. Do not imply that an agent session is a durable monitor; use scheduler-native or
campaign-owned monitoring and notification mechanisms when continuous observation is required.

Record newly established campaign-specific knowledge before the session ends. State the claim,
scope, evidence, observation time, confidence or unresolved uncertainty, and conditions that
would invalidate it. Update the private runbook only after the procedure is demonstrated, and
retain rejected explanations so later sessions do not repeat disproven work. Do not use verbatim
agent transcripts as the knowledge store.

## Keep the production setup frozen

- Do not adapt software, algorithms, scientific inputs, runtime parameters, resource placement,
  decomposition, batching, or acceptance checks in response to campaign results while remaining
  in production mode.
- An operational repair may be retried in production only when it preserves the frozen
  executable, workload, execution path, and acceptance contract. Record the defect, repair, and
  affected attempts.
- A suspected code or input defect requires debugging. Choosing a different candidate requires
  tuning. Establishing performance or cost for a changed setup requires benchmarking. Recommend
  the applicable transition, but remain in production mode until the operator explicitly
  declares it.
- Do not silently mix work produced by different software, input, resource, or persistent-state
  identities. Split the manifest into explicitly identified campaign strata when the operator
  approves a necessary change.
- Reverify immutable identities and mutable external dependencies before each submission wave.
  Stop when the executable, dependency stack, generated input, machine contract, or persistent
  state no longer matches the approved stratum.

## Give every attempt an immutable identity

1. Assign a unique attempt identifier before submission and bind it to exactly one manifest
   work unit or one declared batch of work units. Include that identity in scheduler-visible
   metadata when the scheduler supports it.
2. Give every attempt isolated raw outputs, scheduler logs, environment capture, telemetry, and
   artifact-validation state. Never overwrite or append to a prior attempt's outputs.
3. Persist the prepared attempt and exact submission command before invoking the scheduler.
   Record the scheduler response and job identifier before marking the attempt submitted.
4. If submission acknowledgement is lost or ambiguous, mark the attempt indeterminate and query
   scheduler state using its unique identity. Do not submit a replacement until duplicate launch
   has been excluded.
5. Track attempt lifecycle separately from work-unit acceptance. Prepared, submitting,
   submitted, pending, running, and scheduler-complete are operational states; none means that
   the work unit is accepted.
6. Make status updates atomic or append-only so interruption cannot leave a cursor ahead of the
   evidence. Preserve the complete attempt history when a work unit is retried.
7. Never alter or remove an enrolled work-unit identity in place. Record supersession,
   withdrawal, or an approved manifest extension as a new event and manifest revision.

When several work units share one allocation, record the exact membership and execution order.
Choose packing from validated runtime and resource evidence, leave a stated walltime margin, and
bound the number of units exposed to one job failure. Reconcile each member independently so
completed members can be retained and unfinished members can be retried without ambiguity.

## Control generated and persistent state

- Give every generated input or intermediate artifact a producer identity, producer version,
  source-input identity, parameters, and checksum or equivalent integrity record. Validate every
  required artifact before launching dependent work.
- When randomness is part of the workload, define a reproducible namespace covering every axis
  that distinguishes independent work. Check seed or identifier derivation for collisions and
  representation limits; retain the derivation rule and generator provenance with the campaign.
- Declare the compatibility key, ownership, lifetime, and update policy for caches, checkpoints,
  reusable setup, and other persistent runtime state. Do not permit uncontrolled concurrent
  writers. Prefer frozen read-only state or attempt-owned state when sharing is not proven safe.
- Treat node-local scratch as disposable staging. Record what must be copied to persistent
  storage, validate the copy, and do not mark the work unit accepted while required evidence or
  products exist only on ephemeral storage.
- Monitor capacity and quota for control state, raw outputs, scratch, and derived products.
  Storage pressure does not authorize deletion or reduced retention without operator approval.

## Preflight before submission

Before every submission:

1. Reconcile the proposed work units with the manifest and verify that none is already accepted,
   withdrawn, or active in another attempt.
2. Verify executable and dependency identity, final generated-input identity, required inputs
   and intermediate artifacts, working directory, output destinations, permissions, scratch
   capacity, persistent-state compatibility, and expected free storage.
3. Require planned output targets to be absent from the attempt-owned validation root. Refuse a
   layout in which stale or partial artifacts could satisfy the current attempt.
4. Compare the requested machine, node type, scheduler class, resources, walltime, and
   concurrency with the selected machine profile and frozen production setup.
5. Check the remaining campaign budget against the full requested allocation. Record the
   reservation in the append-only budget ledger according to canonical `AGENTS.md`.
6. Validate batch membership, dependency ordering, retry eligibility, and the absence of another
   operator or agent preparing the same work. Use a campaign-defined lock or single-writer
   protocol for state-changing automation.
7. Capture the exact submission command, manifest revision, contract stratum, and prepared
   attempt record before launch.

If any preflight check fails, do not submit. Leave the work unit eligible for a corrected attempt
and record the failed preflight without representing it as executed work.

## Monitor, reconcile, and retry

1. Monitor scheduler state at a rate consistent with site policy. Keep monitoring helpers and
   credentials scoped to the campaign, and ensure background helpers terminate when their job
   or monitoring task ends.
2. Persist scheduler metadata and accounting evidence promptly; scheduler history may expire
   before a long campaign ends. Periodically reconcile the full manifest, not only recently
   submitted work.
3. Reconcile scheduler, launcher, runtime, application, artifact, numerical, and scientific
   evidence using `conventions/running.md`. Use the relevant application guide for progress,
   completion, work-unit, and correctness semantics.
4. Validate the exact expected-artifact set and its internal record identities, multiplicities,
   and payload shape using `conventions/measurement.md`. File existence, nonzero size, scheduler
   success, or a normal application exit is never sufficient by itself.
5. Assign every completed attempt a disposition from `conventions/running.md`. Mark a manifest
   work unit accepted only when its frozen acceptance contract passes. Write acceptance as a
   separate atomic record; never alter raw output to represent acceptance.
6. Reconcile actual allocation consumption in the budget ledger for every attempt, regardless
   of disposition. A failed or canceled allocation still consumes campaign budget when the
   scheduler accounts it.
7. Classify failures from evidence before retrying. Do not retry blindly, exceed the authorized
   retry or resource limits, or launch a duplicate while another attempt remains active or
   indeterminate.
8. Create a new attempt for every authorized retry. Preserve the earlier raw evidence, state the
   supported failure class, and record why the retry can succeed without changing the frozen
   production contract.
9. Escalate repeated failures, contradictory evidence, unexplained output drift, exhausted retry
   limits, projected budget overrun, storage pressure, and environmental changes according to
   the campaign contract. Stop affected submissions while the condition is unresolved.

Keep live campaign state in the working directory: manifests, job identifiers, queue state,
completed work-unit lists, retry counts, missing outputs, alerts, and consumed budget are not
handbook knowledge. Preserve raw evidence immutably. Derived products must identify their raw
inputs, transformation parameters, tool revision, output identity, and validation status.

## Permissions and safeguards

- Production is the lowest write-privilege work mode. Limit writes to authorized campaign-owned
  state and explicitly requested operational actions.
- Never submit without both explicit submission scope and the campaign budget controls required
  by canonical `AGENTS.md`. Without them, prepare the attempt and give the submission command to
  the operator.
- Do not cancel a running job, withdraw a manifest entry, replace an accepted result, delete raw
  evidence, or clean shared scratch or persistent state without explicit operator authority.
- Do not modify project code, rebuild the stack, or change the frozen production setup under an
  operational request. Stop at the mode boundary and request the necessary authority or mode
  transition.
- Follow machine policy and the working project's instructions. A handbook budget, retry,
  concurrency, or monitoring rule never overrides site limits, allocation policy, or project
  ownership.
- Keep private campaign identifiers, unpublished inputs and results, credentials, and live
  operational state out of handbook proposals and reports unless the operator separately clears
  their publication.

## Tools and routing

Use the working project's instructions, detected software profile, selected machine profile,
nearest validated stack, build profile, relevant application guide, and relevant solver or
runtime documents. Load `conventions/running.md` for evidence reconciliation and run disposition,
`conventions/measurement.md` for run-owned artifact validation and workflow accounting, and
`conventions/batch-scripts.md` before writing, modifying, or reviewing any batch script or
preparing a submit command. Load [`conventions/repeated-work.md`](../conventions/repeated-work.md) at each study or phase closure and at each work-mode change, to decide whether a procedure now repeated by hand should become a tool.

Keep campaign contracts, runbooks, launchers, manifests, ledgers, handoffs, private knowledge,
monitoring state, and raw evidence in the working project. Route only durable, generalized
mechanisms through handbook admission: universal run rules to `conventions/`, software semantics
to `software/<name>/`, machine behavior to `machines/<name>/`, and validated combinations to
stacks. Campaign-specific state or knowledge does not become handbook knowledge merely because
it is useful across agent sessions.

## Done

Production is done after the operator closes the campaign scope and every in-scope manifest entry
is accepted, explicitly withdrawn by the operator, or recorded with a bounded unresolved status;
no duplicate or untracked attempts remain active; scheduler and application evidence and
resource consumption are reconciled; raw evidence and derived-product provenance are retained;
and the contract, ledgers, final handoff, and closure summary are consistent and sufficient for
another operator to audit or resume the campaign safely. Before closing, run the automation checkpoint in [`conventions/repeated-work.md`](../conventions/repeated-work.md) and record its outcome, including candidates deliberately left manual. Any change to the frozen setup or
investigation beyond failure triage requires an explicit transition to debugging, performance,
tuning, or benchmarking mode.
