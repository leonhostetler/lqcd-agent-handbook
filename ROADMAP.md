# LQCD Agent Handbook — Roadmap

This document is the handbook's mutable state: what is done, what is next, what is owed, and
what is parked. It is read in full at the start of every developer-mode session.

**It holds:** slice status, the single next action, open obligations, open questions, the
deferred-decision register, and the proposals already settled. **It does not hold:** session
narratives, defect forensics, measured figures, or acceptance evidence — those are episodes
and live in [`DEVLOG.md`](DEVLOG.md), which is not loaded at session start. Durable design
belongs in `ARCHITECTURE.md`; this document never restates a decision, only its state.

<a id="slice-status"></a>
## 1. Slice status

| Slice | Scope | State |
|---|---|---|
| 0 | rules and skeleton | accepted |
| 0b | agent-neutral frontends (Claude + Codex) | accepted 2026-08-15, six cold cases |
| 0c | user-wide session-logging adapters | accepted 2026-08-17, five cold cases |
| 1 | build QUDA on Perlmutter | accepted 2026-08-17 |
| 2 | QUDA on Frontier; stack schema from two instances | accepted 2026-08-17 |
| 3 | MILC on both machines | accepted 2026-08-17 |
| 4 | modes, benchmarking, the prediction loop | **in progress** |
| 5 | software-local solvers and ensembles | partly landed; acceptance pending |
| 6 | performance analysis | accepted 2026-09-15, three checks |
| 7 | automation and enforcement | partly landed — submission guard 2026-09-24 |

`handbook.yaml` owns `phase`, which stays `bootstrap` until Slice 5 is accepted. Machines
after Frontier are onboarded as needed rather than as slices; the order and its reasoning are
in [§build-order](#build-order). Validated combinations are canonical in each
`machines/<name>/stacks/<stack>/stack.yaml`, never here. Per-slice episodes — what was built,
what each run established, and what it did not — are in [`DEVLOG.md`](DEVLOG.md).

**NEXT ACTION:** Finish Slice 4. Its remaining deliverables are listed under
[§open-obligations](#open-obligations); `tools/extract-milc-timings.py` is the one that
unblocks the most, because the untraced-control comparison is built into it.

<a id="open-obligations"></a>
## 2. Open obligations

Everything owed, in one place. An item leaves this list only when the thing it names exists,
not when a session reports it done.

### Slice 4 — in progress

| # | Owed | Note |
|---|---|---|
| 4.1 | `tools/extract-milc-timings.py` | carries the untraced-control comparison (below) |
| 4.2 | `tools/summarize-slurm-job.py` | |
| 4.3 | `tools/collect-environment.sh` | |
| 4.4 | `schemas/prediction.schema.json` | |
| 4.5 | `playbooks/run-benchmark.md`, `playbooks/capture-learning.md` | |
| 4.6 | Append-only submission-budget-ledger format | [§budget-rule](ARCHITECTURE.md#budget-rule); debit at submit, reconcile down at completion |
| 4.7 | Scheduler-placement guidance in `conventions/running.md` | the `modes/debugging.md` half landed; this half did not |

**The untraced-control comparison lands in 4.1**, not as a profile subcommand, because it
combines a profile figure with an application run-log figure. It crossed
[§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s threshold at six hand uses, and it carries a
failure that reverses its own conclusion: including the control's first solve moves its mean
roughly fourfold and yields "tracing is nearly free", the opposite of what the data says,
through arithmetic that looks entirely ordinary. `conventions/measurement.md`'s first-solve
rule is what the tool must apply, and is the rule the hand passes kept getting wrong. Building
it inside 4.1 rather than beside it keeps one canonical reader of MILC timing output.

### Slice 5 — partly landed

| # | Owed |
|---|---|
| 5.1 | Deflated-CG runtime validation — every eigensolver-enabled stack records in `scope_limits` that no eigensolve or deflated solve was exercised |
| 5.2 | Ensemble-scoped operational imports |
| 5.3 | The three slice acceptance checks |
| 5.4 | A mechanistic MRHS memory model — observed increments may guide its design but may not be promoted as a transferable capacity formula without allocation-lifetime analysis and validation across MRHS widths |

### Slice 7 — not started

| # | Owed |
|---|---|
| 7.1 | **Landed at submit time, 2026-09-24:** `tools/submission-guard.py` intercepts the surface's submit command and refuses it without a clean checker run and a current receipt from `tools/dry-run-batch-script.py` (offer-only installer for Claude Code and Codex; Codex enforces once the operator trusts the handler in `/hooks`). **Still owed:** the guard before a batch-script *write* lands, and the enforcement half of the authoring-time input-proofread rule (`conventions/batch-scripts.md` step 3), which the lint can only advise |
| 7.2 | Knowledge-capture hooks |
| 7.3 | User-mode write guard |

All three need frontend-specific offer-only installers, not repo files: hooks and subagents
are not activated merely by adding the handbook
([§loading-invariants](ARCHITECTURE.md#loading-invariants)). Revisit the loading decision here
too — a plugin would carry hooks and agents natively, and by then there is usage data to judge
whether that is worth a per-machine install.

### Cross-cutting

| # | Owed |
|---|---|
| X.2 | Skill adapters absent from both `.claude/skills/` and `.agents/skills/`: `lqcd-run-benchmark`, `lqcd-tune-solver`, `lqcd-analyze-profile`, `lqcd-capture-learning` |
| X.3 | Deferred skill-installation portability — define the supported platform and Codex-surface matrix, then replace the Unix-only symlink installer with a manifest-driven, conflict-safe one. Preserve `$HOME/.agents/skills` as the Codex user scope; preflight every target; never overwrite unmanaged paths. Launcher and Tier-0 routing must keep working without skill installation |
| X.4 | A guard on the suite's own two conventions, which are currently held by habit alone. A test must resolve an interpreter through `tests/support.py`'s `interpreter_for` before subprocessing any of the five tools carrying a third-party import, never `sys.executable` and never a bare `python3`; and it must copy the repository through `handbook_copy_ignore`, never a bare `ignore_patterns`. Both were violated in more than a dozen places at once, and the second had already been extracted into a shared helper that one call site never adopted — so neither is a single slip that correcting fixes. The suite already enforces two naming conventions this way, in `tests/test_reserved_terms.py` and `tests/test_role_not_index.py`; this is the same shape. **The reason it is owed rather than optional:** a reintroduction is silent. A test that reaches for `sys.executable` on a machine whose default interpreter happens to carry the dependency passes, and only fails somewhere else, later, for someone who reads the failure as a missing module rather than as an unexercised check |
| X.5 | An AMD accelerator monitor and the extractor branch to read it, plus AMD sampling in the retained `tools/gpu-memory-sampler.sh`. `tools/monitor-gpu.sh` is NVIDIA-only and says so rather than carrying a branch that reports its own absence; the sampler's `amd` branch records that it is unimplemented and exits 0. The reason is the same in both: `rocm-smi`'s memory field names and column order have moved between ROCm releases, and the handbook ships no parse it has not run against the installed tool. **Until it lands, the instrumentation rule in [`conventions/batch-scripts.md`](conventions/batch-scripts.md) cannot be met on an AMD machine**, and Frontier is profiled rather than hypothetical. Establish the layout on the target and pin the ROCm version it was established against. **Ship a monitor and its extractor branch together**: a monitor emits the vendor tool's own table, so one without a matching reader produces a file nothing can read, which is the defect the pair exists to prevent |

### Watch items

Below [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s threshold, recorded so the next
occurrence trips the rule rather than starting the count again.

- **MPI collective-size breakdown** separating fabric latency from rank skew — at two hand uses.
- **Kernel template-argument resolution** against the revision that built the binary —
  deliberately manual, because it needs the decomposition cross-check and therefore judgement
  at each step.

<a id="build-order"></a>
## 3. Build order

Each slice has a **cold-session acceptance test**: a fresh agent, started through the frontend
launcher and given only the task, completes it without the operator re-teaching anything. That
test is the deliverable, not the file count.

### Slice 0 — rules and skeleton

Tier 0 and its mirror, this document and `ARCHITECTURE.md`, `handbook.yaml`, `README.md`,
`PRIVACY.md`, `conventions/orientation.md`, `modes/{user,developer}.md`, the machine and
project schemas, `tools/validate-knowledge.py`, `inbox/`, the start-session skill and playbook,
the launcher, and **`.gitignore` carrying `session_*.log`** — which lands in the *first* commit,
since developer-mode sessions run inside the repo and drop transcripts immediately.

`modes/developer.md` is written **first**, before any content exists to govern; writing it last
would mean slices 1–4 were built without it.

*Accept:* seven checks — a launcher-started session with no opening instruction orients itself;
it detects machine and software rather than asking; it asks only for the work mode and defaults
to user mode; Tier 0 is under 6 KB; a cold developer session reads both long documents
unprompted and can state the next action while a user-mode session opens neither; a session
started *without* the launcher is detected and reported rather than proceeding (trap T2); the
launcher fails actionably when `LQCD_HANDBOOK` is unset; and the handbook is validated by
content rather than by path.

### Slice 0b — agent-neutral frontends

One handbook behaviour behind Claude Code and Codex. Canonical Tier 0 is `AGENTS.md` with
`CLAUDE.md` an exact generated mirror; `handbook.yaml` declares entrypoint, mirrors, markers and
both adapters; `playbooks/start-session.md` owns shared behaviour while the two preflights own
only complete-loading checks; both launchers preserve the caller's working directory and
project instructions. Codex uses additive `developer_instructions`, never
`model_instructions_file`, and requests no additional writable root.

*Accept:* six cold cases — each frontend in user and developer mode, plus each frontend started
without the launcher, where partial loading must be reported and work must stop. Functional
parity means orientation, safeguards, routing and stop conditions match; the loading mechanism
may differ. All six accepted 2026-08-15.

### Slice 0c — user-wide session-logging adapters

The session-logging mechanism pulled forward from Slice 7: shared checker, installer and
interpreter dispatcher, frontend-specific `Stop` loggers, the detect-and-offer startup step.
The contract is shared and installation is frontend-specific. Startup checks after freshness,
reports `enabled`, `configured`, `missing`, `stale` or `broken`, and makes a non-blocking offer
for repairable states without adding a second mandatory question. Installation is never
automatic.

*Accept:* five cold cases — logger absent and install accepted on each frontend, plus
logger-current on either. All five accepted 2026-08-17.

### Slice 1 — the vertical slice: build QUDA on Perlmutter

The Perlmutter machine profile, the QUDA project record and build guide, the build-stack skill
and playbook, `tools/detect-machine.sh`, and **the first stack record** written as the natural
output of the build that succeeded. `software/quda/build-profiles.yaml` lands here with exactly
one profile — a stack references a profile, so the slice cannot produce a well-formed stack
without it. One entry, not a taxonomy.

**`stacks/` gets no schema in this slice, deliberately.** A schema written from one instance
encodes Perlmutter's accidents as universals, and the first CUDA/ROCm divergence is where that
breaks.

*Accept:* a cold session builds QUDA on Perlmutter with no re-teaching, and the stack record it
produces lets a later session reproduce that build without re-deriving anything.
**Accepted 2026-08-17.**

### Slice 2 — second machine, same software: QUDA on Frontier

`machines/frontier/` with its first stack, plus `schemas/stack.schema.json` written from two
instances rather than one, `tools/build-index.py`, and the P2 restated-value heuristic.

This is the real test of P3: **if adding Frontier forces an edit to
`playbooks/build-lqcd-stack.md`, machine knowledge has leaked into the task layer.** It did
not. **Accepted 2026-08-17** — domain indices grouped by scoped object, the stack schema bound
to both a CUDA and a HIP instance, the P2 heuristic advisory with focused tests.

#### Machine onboarding order

`[operator]` Most-used machines: Perlmutter, Frontier, DeltaAI. Machines after Frontier are
onboarded when needed, in the order **Frontier → DeltaAI → Aurora**. Frontier second breaks the
vendor axis while holding Slurm fixed, isolating one cause. DeltaAI third is deliberately the
*easy* machine — NVIDIA and Slurm again — which makes it the acceptance test for onboarding
cost: an easy machine should be cheap, and if it is not, the schema is wrong. Aurora is
scheduled last because it moves two axes at once (Intel/SYCL *and* PBS) and has the least
mature QUDA support, so it is the one that may force a schema revision; flagging that in
advance makes the revision budgeted rather than a surprise.

**The insurance:** three consecutive Slurm machines would encode Slurm as *structure* rather
than as a *value*. From slice 2 the scheduler block is **discriminated on `type:`** so PBS
arrives as a value in an existing shape. The same applies to `accelerator.vendor`.

### Slice 3 — second software: MILC on both machines

`software/milc/` including the QUDA-interface linkage — the first place two project profiles
must compose — plus `software/{qmp,qio}/` and `schemas/build-profiles.schema.json` derived from
profiles in two software contexts. **Accepted 2026-08-17.**

### Slice 4 — modes, benchmarking, and the prediction loop

All five work modes, `conventions/{running,measurement}.md`, the benchmark and capture
playbooks, the prediction schema, the budget-ledger format, and the MILC timing, Slurm summary
and environment-collection tools. MILC application semantics live under
`software/milc/applications/`, not in the generic modes. The staggered memory and decomposition
calculators were admitted as `tools/quda-staggered-memory.py` and
`tools/quda-staggered-decomposition.py`.

*Accept:* a benchmarking session predicts runtime and memory before submitting, writes the
record **into the working directory**, and files the comparison — and a deliberately stale fact
is caught by its metric's tolerance ([§tolerances](ARCHITECTURE.md#tolerances)) while ordinary
fabric noise does not raise a false alarm.

**In progress.** Remaining deliverables are itemised in [§open-obligations](#open-obligations).

### Slice 5 — software-local solvers and ensembles

*The mining slice; [§developer-mode-spec](ARCHITECTURE.md#developer-mode-spec) governs it.*
`software/<name>/solvers/` seeded from screened transferable findings, `ensembles/milc-hisq.yaml`
and its schema. Publishability is settled **per class during the import**
([§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)), so the slice is not gated on one
up-front decision.

Run the admission test strictly — stage extractions **in the working directory beside the
source corpus**, assign each candidate a scope and a durability verdict
([§admission-test](ARCHITECTURE.md#admission-test)), admit one at a time, and record every
rejection as its own file under `inbox/rejections/` with the test it failed.

*Accept:* three checks. "Which solver stack for ensemble X on machine Y at N solves per mass" is
answered from the handbook alone, with regime and solve count stated. Every admitted fact
carries a `scope:`, none is scoped to an episode, and every solver fact is filed beneath its
software implementation. And a tuning session on an ensemble *not* in the corpus loads no
ensemble-scoped material at all — the check that narrow knowledge was filed rather than inlined.

**Partly landed.** The ensemble catalog, schema, naming rule and spacing-default convention are
prepared independently of the private corpus; the solver batch covers source-backed staggered
CG, deflated-CG and multigrid overviews, capability coverage, selection and tuning procedures,
and the memory/decomposition tools. Remaining work is in
[§open-obligations](#open-obligations).

### Slice 6 — performance analysis

`modes/performance.md`, `playbooks/analyze-profile.md`, `conventions/profile-metrics.md`,
`conventions/profile-capture.md`, the hypothesis-record schema and checker, and the offline
extraction and diff tools, harvested from the operator's PerfAdvisor working tree with the exact
proposed additions screened at intake. [§profile-analysis](ARCHITECTURE.md#profile-analysis)
governs the split: extraction ships as a tool, interpretation as leaves, and no second agent is
wrapped.

*Accept:* three checks. A cold session given only a profile declares performance mode, extracts
with the tool rather than by querying the database by hand, and produces a ranked hypothesis
record `tools/hypothesis-record.py` accepts, every figure traceable to a named command and every
hand-derived quantity declared. Given a capture lacking the instrumentation its question needs,
the session **reports the gap instead of producing hypotheses** — the check the rest rests on,
because a confident answer drawn from a capture that cannot support one reads exactly like a
good answer and nothing downstream detects it. And a performance session on software with no
profiling leaf loads no QUDA-scoped material at all.

**Accepted 2026-09-15** on all three. **Cold** means no access to a prior analysis *of the
capture under test*; knowledge of the application, machine and software stack is explicitly not
contamination. The calibration harness stays outside the handbook: the source suite's
injected-bottleneck profiles, ground truth and scorer remain working-directory observations
under [§records-in-working-directory](ARCHITECTURE.md#records-in-working-directory), and the
handbook ships the rule and never the numbers. The stage record, the five acceptance exercises
and the post-acceptance defect record are in [`DEVLOG.md`](DEVLOG.md).

### Slice 7 — automation and enforcement

The loggers, installer and startup check landed early in Slice 0c. The first enforcement landed
2026-09-24: a `PreToolUse` guard on the scheduler submit command, with a shipped dry-run harness
that writes the receipt the guard demands (7.1, submit-time half). It was built the day after a
launcher that had followed the handbook's own recipe died ten seconds into a two-day queue wait —
the episode is in `DEVLOG.md`. What remains is itemised in [§open-obligations](#open-obligations):
the write-time guard, knowledge-capture hooks, and the user-mode write guard. Invoked by hand,
`tools/check-batch-script.py` stays advisory; at the submit command it now enforces.

<a id="open-questions"></a>
## 4. Open questions for the operator

None outstanding. New questions land here as they arise; answered ones move to
[§settled](#settled).

<a id="deferred-decisions"></a>
## 5. Deferred decisions

Parked deliberately, each with the **trigger** that should un-park it rather than a slice
number. A deferred decision is only safe when the interim behaviour is conservative; that
column is the test.

| Decision | Interim behaviour | Un-park when |
|---|---|---|
| **Enforcement of the job-submission budget** — agent instruction, a `lqcd-submit` wrapper, or a hook | [§budget-rule](ARCHITECTURE.md#budget-rule)'s default: no budget stated ⇒ the agent prepares the job and hands over the submit command. Zero machinery, cannot overspend. Since 2026-09-24 `tools/submission-guard.py` intercepts the submit command for *readiness* (checker and dry-run receipt), so the vehicle for a budget check exists; it deliberately reads no ledger | **Operator-initiated only** (ruled 2026-09-15). The operator declares up front what an unattended submission loop would do — ceiling, ledger discipline, and the stop that fires at the ceiling — before any of it is built. Not un-parked by an agent finding a loop convenient, nor by a workflow reaching the point where submission is the only manual step |
| **Enforcement of user-mode write protection** | The P6 instruction of [§handbook-modes](ARCHITECTURE.md#handbook-modes), plus startup reporting an unclean handbook tree so a stray edit surfaces the same day | The repo stops changing daily. Read-only permissions fight developer mode, which is *most* sessions during bootstrap. Rides with slice 7, which needs an installer regardless |
| **Sub-file provenance** — claim IDs versus file-level frontmatter | File-level frontmatter ([§knowledge-atom](ARCHITECTURE.md#knowledge-atom)), with knowledge files kept small and atomic so it stays adequate | A file accumulates claims from materially different dates, versions or evidence kinds |
| **Whether any part of the handbook should be served over MCP** | **None.** Knowledge stays markdown and YAML; procedures stay skills plus `tools/` scripts. Works on every machine with no runtime | Any of three: the handbook must reach data too large to commit; something genuinely remote becomes necessary, such as live cross-machine job status; or a capability arrives already service-shaped |
| **Whether session logging should archive the raw transcript JSONL** ([§session-logging](ARCHITECTURE.md#session-logging)) | **Prose-only.** The JSONL under each frontend's user state is the true last resort where it survives | The prose record proves insufficient to reconstruct an episode, or a rebuild destroys a JSONL that was wanted. Cost first: much larger working-directory files, and a far bigger privacy surface, since the JSONL holds every file read and command run |
| **Whether the handbook is measurably cheaper than the rediscovery it replaces** | No measurement; cold-session tests stay qualitative | The handbook becomes big enough to feel slow to navigate — and then the lightweight version below, never an A/B harness |
| **A retained validation set for the fitted tool models** — screened `(inputs → measured counter)` rows as fixtures, so a published error is re-derivable in-repo | **None committed.** `tools/quda-staggered-memory.py` carries its population and error as prose and the corpus is not in this repository ([§non-public-evidence](ARCHITECTURE.md#non-public-evidence)). The regression test pins documented examples to the model's **own output**, so it detects drift but not an error present from the start. Meanwhile, under [§decisions-knowledge-contract](ARCHITECTURE.md#decisions-knowledge-contract), no fit may be revised, which is conservative but leaves known one-sided errors uncorrected | A fit needs revising rather than annotating. The open case is whether the MG model's phase A genuinely peaks before the coarsest eigensolve or whether its fitted setup-workspace constant absorbs a near-constant eigenspace term; those imply opposite repairs and no in-repo evidence distinguishes them. Needs a publishability decision on the fact class first ([§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)) |
| **A controlled vocabulary for a hypothesis's `bottleneck` field** | **Free text**, per `schemas/hypothesis.schema.json`. The obvious enum to adopt is demonstrably too coarse — three distinct scenarios legitimately take one value, which is why its own scorer needs a second keyword gate. Adopting it would import a known defect into a schema, where it is expensive to correct | Enough hypothesis records exist to show which names recur. Derive the vocabulary from them rather than guessing; it is a `schema_version` bump |
| **Optional follow-up mining from the `ks_spectrum` benchmark corpus** — memory/telemetry analysis, reference-correlator comparison, broader gauge-I/O validation | The admitted guidance requires ordinary resource evidence and structural, numerical and scientific checks, but claims no telemetry method, comparison recipe, or preferred I/O path | A concrete tuning or validation decision needs an item and suitably scoped evidence exists. Optional; none blocks Slice 4 |
| **Whether the handbook ingests and interprets hardware counters** — sampled device-wide metrics inside the timing export, versus per-kernel replayed counters in a separate artifact | **Neither.** `modes/performance.md` routes every counter-requiring question to a counter-collecting run and refuses to assert one from a trace, and `conventions/profile-capture.md` records that counter collection is a separate job because replay distorts exactly the durations a timing capture exists to measure. `ProfileCapabilities.has_pmc_counters` already detects the tables on both formats — `CUPTI_ACTIVITY_KIND_METRICS` and `rocpd_pmc_event` — but nothing reads them, and no leaf says what a counter would license | A counter collection is actually run, so the interpretation contract can be written from observation rather than from vendor documentation — the overclaim that dropped the source capability matrix's bandwidth and occupancy rows. **Decide the two tiers separately:** sampled device-wide metrics land in the same export and may be admissible to the existing extractor, while per-kernel replayed counters are a different artifact whose figures must never enter a timing hypothesis record. A replay run consumes allocation, so [§budget-rule](ARCHITECTURE.md#budget-rule) applies |
| **Whether split-grid deflation solver knowledge is admitted to `software/quda/solvers/`** — the scheme, its cost decomposition, the sub-grid and parent segment contract, the sources-per-sub-partition width, and its interaction with the rank cell | **None admitted.** The scheme, cost model, orchestrator design and every measured figure stay in the operator's working project. Two 2026-09-17 passes have taken residue from that campaign without touching the solver: debugging method first, then upstream QUDA and MILC behaviour read from `develop` together with software-independent tuning practice. All of it is already landed. The solver was rejected in both passes — as not debugging knowledge, and as describing an unmerged branch — and the second pass sharpened the second reason: the cycle-count mapping behind the campaign's most transferable-looking tuning lever runs through a parameter that is absent from upstream, so even the method residue had to be written without naming it. Conservative because the handbook then asserts nothing about a solver path that does not exist upstream: no session routes to it, `staggered-solver-selection.md` does not offer it as a candidate, and there is no fact that can go stale | **Two conditions, independent of one another, and then a third decision.** The work merges upstream, so its commits resolve and its branch context is stable — [§version-lifetimes](ARCHITECTURE.md#version-lifetimes) is explicit that a feature-branch commit can be rebased away or never land, leaving every citation unresolvable and silently so. **And** the open correctness question on the configuration the campaign's own figures were measured on is settled, because selection or tuning guidance for a path whose correctness is unresolved is guidance that may be wrong. Only then does the numerical half need its own decision under [§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers): mechanism and parameter semantics are publishable on merge, calibrated cost constants are campaign measurements and are not. **Not un-parked by the branch working well**, which is the condition most likely to be mistaken for the trigger |

**On measuring the handbook's value, the form is decided even though the timing is not.** A
"same task with and without the handbook" comparison is n=1 per arm against a stochastic agent,
where two handbook-free runs can differ twofold depending on which wrong path is explored first,
and the second arm is not cold anyway. It would produce noise that reads like data. The
lightweight version instead: **operator interventions per cold-session test** (countable, and
meaningful at n=1 because zero is zero); **re-teaching defects**, which are defect reports
naming a file that failed to be found or failed to be right; and **Tier-1 bytes actually loaded
before useful work began**. And a standing rule needing no harness: if a session spends more
turns navigating the handbook than doing the task, cut something — a deleted mechanism is a
legitimate slice outcome.

<a id="settled"></a>
## 6. Settled and rejected

Proposals already decided, one line each, so they are not re-litigated. The evidence behind
each is in [`DEVLOG.md`](DEVLOG.md).

| Proposal | Outcome |
|---|---|
| **Requiring a declared production solve count before tuning may start** | **Rejected 2026-09-18**, while the rule it came with was accepted. Forcing the number would tax every campaign setup and would be wrong about exploratory tuning, where the regimes are an *output* of the measured crossovers. The accepted form leads with the purpose of a trial and handles the unknown case by reporting `C(N)` and `N*`, which is strictly more informative than a winner; `tools/amortize-cost.py` enforces the half that needs enforcing by emitting crossovers with no count supplied and shares only at counts it is given. A future session tightening this back into a required question is the re-litigation this line exists to stop |
| **Slice 6 Stage 6 / a fourth acceptance check** re-pointing the source suite's scored scenarios at a handbook hypothesis record | **Withdrawn 2026-09-15.** The five exercises found more than a score could; the profile-blind property is held by that suite's own scoring tests, so re-pointing the scorer is the only thing that would put it at risk; and its scenarios are synthetic microbenchmarks measuring recall, a weak proxy for real captures with no ground truth |
| **A self-resubmitting optimisation loop** | **Set aside 2026-09-15**, not deferred toward. Its use is hypothetical, and the interim behaviour is zero machinery that cannot overspend — precisely the property such a loop removes, so the trade needs stating up front |
| **A standalone perturbation runner** | **Withdrawn 2026-09-16.** The tool already existed in-tree as a per-file test helper; what was missing was extraction into `tests/support.py`. The in-test form is also better: a standalone runner checks once at authoring time, while a control carrying its own perturbation re-checks every suite run, which is the only thing that catches a control going inert later |
| **A parallel rank loader for `cross-rank`** | **Declined 2026-09-16.** Three observations crossed a counter built for silent arithmetic errors, but a serial loader is slow rather than wrong. Ordinary ergonomics, not a defect-rate obligation |
| **Deduplicating `software/INDEX.md`** | **Dropped.** Its duplicated leaves are each scoped to two software projects, so deduplication means choosing a group to break; the byte argument runs against a locked decision whose reopen trigger is legibility, explicitly not size |
| **A framework detector on the extraction output** | **Dropped.** Every `top_kernels` row already carries the namespace, so a detector would be a second rottable list restating what the session can read |
| **A MILC RHMC host-cost-structure fact** | **Not admitted.** Mechanism inferred from sampled symbol names alone, no source read, one capture of an unpublished run. Obligation 4 forbids mining and admitting in one step |
| **Memory-bandwidth and occupancy rows from the source capability matrix** | **Dropped.** Both contradict the tracer rule; importing a matrix wholesale is how a known overclaim enters a convention |
| **A `capture_notes:` pointer field in machine profiles** | **Dropped.** The validator resolves Markdown links, not bare YAML strings, so it would rot unchecked |
| **Writing a software condition into a leaf's `load_when`** | **Rejected.** `scope:` already decides which software; `load_when` says which situation within it. Restating it would put one fact in two places that could disagree |
| **Requiring an owed item to name what it searched** (`conventions/repeated-work.md`) | **Declined.** One missed search does not carry a convention change |
| **rocpd host-sample symbol resolution** | **Deliberately not implemented.** A join written from the schema alone would emit plausible symbol names nothing could verify; the tool returns `None` so the caller says "not implemented for this format", which is a different statement from "no samples" |
| **A validator check for files named in the directory tree but absent** | **Not added.** A guard firing on legitimate future additions is the noisy guard [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s counterweight warns against |

---
