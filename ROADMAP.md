# LQCD Agent Handbook — Roadmap

**Status:** Slice 0b is accepted. Slice 1 is in progress; the Perlmutter machine profile
and detector are committed and published.

**NEXT ACTION:** Add the QUDA project record, build guidance, and the single build profile
for the first Perlmutter build.

This document owns mutable build state, acceptance evidence, pending decisions, and the single next action.

<a id="current-slice-state"></a>
## Current slice state

Slice 0 was committed and published at `1352ba5`. Slice 0b was committed and published at
`b06c7d1` on 2026-08-15, and the zero-argument startup repair was committed and published
at `fa9001a`. Slice 1 began with the Perlmutter machine profile, operational notes, machine
detector, and focused tests committed and published at `b116b8f` on 2026-08-15.

Latest automated evidence:

- `python3 tools/validate-knowledge.py`: three schema objects valid, two provenance records complete,
  two frontend adapters valid, 202 long-document references resolved, no deny-list match,
  and Tier 0 at 2,908/6,144 bytes;
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`: all twenty-three checks pass,
  including frontend-manifest consistency, exact entrypoint mirroring, mirror repair, both
  launcher contracts and drift stops, shared zero-argument startup prompting, preserved
  working directory, additive Codex bootstrap, conflict-safe installer behavior, machine
  schema conformance, and Perlmutter detection behavior;
- `bash -n tools/lqcd-claude tools/lqcd-codex tools/install-codex-skills
  tools/detect-machine.sh`,
  `python3 tools/sync-agent-entrypoints.py --check`, and `git diff --check` complete cleanly.
- `tools/detect-machine.sh` resolves the live Perlmutter login environment to `perlmutter`
  from the documented NERSC machine marker.

Accepted on 2026-08-15 by operator report: the Claude launcher in user mode, the Claude
launcher in developer mode, Claude invoked without the launcher, the Codex launcher in user
mode, the Codex launcher in developer mode, and the Codex user skill invoked without the
launcher/bootstrap all behaved as their acceptance cases require.

The first Claude user-mode attempt on 2026-08-15 opened an idle prompt because the launcher
loaded passive instructions but supplied no initial turn. Both launchers now inject the same
manifest-declared startup prompt only when called with zero arguments. The rerun and both
other Claude cases were accepted.

The first Codex launcher user-mode attempt on 2026-08-15 stopped before startup because the
launcher passed `--add-dir`, which Codex treats as a request for another writable root and
the effective permissions rejected. The Codex adapter now relies only on its additive
absolute-path instruction pointer and does not widen or override the caller's permissions.
The repaired launcher rerun and both other Codex cases were accepted on 2026-08-15.

<a id="build-order"></a>
## 9. Build order

Each slice has a **cold-session acceptance test**: a fresh agent, started through the
frontend launcher and given only the task, completes it without the operator re-teaching
anything. That test is the deliverable, not the file count.

### Slice 0 — rules and skeleton *(small; slice 1 writes YAML that needs a schema)*
`CLAUDE.md`, `INDEX.md`, **`ARCHITECTURE.md` + `ROADMAP.md`** (this document, split and
privacy-screened per [§plan-ships-with-handbook](ARCHITECTURE.md#plan-ships-with-handbook)), `handbook.yaml` (`phase: bootstrap`), `README.md`, `PRIVACY.md`,
`conventions/orientation.md`, **`modes/{user,developer}.md`**,
`schemas/{machine,project}.schema.json`, `tools/validate-knowledge.py`,
`inbox/proposals/` and `inbox/rejections/`, **`.claude/skills/lqcd-start-session/`
+ `playbooks/start-session.md`**, the launcher script of [§loading-chain](ARCHITECTURE.md#loading-chain), and
**`.gitignore` carrying `session_*.log`** ([§session-logging](ARCHITECTURE.md#session-logging)) — which must land in the *first* commit,
since developer-mode sessions run inside the repo and start dropping transcripts
immediately.

The Slice 0 validator scope is deliberately smaller than the completed contract in
[§validator-checks](ARCHITECTURE.md#validator-checks): schema meta-validation and explicit
bindings for `machine.yaml` and `project.yaml`; Markdown provenance, evidence placement, and
`review_by`; the privacy deny-list; long-document references; and Tier-0 budgets. Complete
`observed_on` semantics and the P2 restated-value heuristic are deferred below.

`modes/developer.md` is written **first**, before any content exists to govern — it is what
governs every subsequent slice, and writing it last would mean slices 1–4 were built
without it.

*Accept:* seven checks. A session started **through the launcher with no opening instruction
at all** orients itself — Tier 0 is in context and `/lqcd-start-session` is available. It
**detects machine and software rather than asking**, reports what it found, asks only for
the work mode ([§work-mode-currency](ARCHITECTURE.md#work-mode-currency)) before doing anything, and defaults
to user mode when the handbook mode is not stated. Tier 0 is under 6 KB. A cold
developer-mode session reads `ARCHITECTURE.md` + `ROADMAP.md` unprompted and can state the
next action, while a cold user-mode session opens neither. And **a session started
*without* the launcher — bare `claude --add-dir`, so skills load but `CLAUDE.md` does not —
is detected and reported by `lqcd-start-session` rather than proceeding unrestricted**
(trap T2). The final two check handbook location ([§locating-handbook](ARCHITECTURE.md#locating-handbook)): the launcher **fails with an
actionable message when `LQCD_HANDBOOK` is unset**, and `lqcd-start-session` validates the
handbook by content rather than by path. Verify here whether the invoked skill's own
location is recoverable — that decides whether the divergence check is exact or heuristic.

<a id="codex-frontend"></a>
### Slice 0b — agent-neutral frontends

This compatibility slice establishes one handbook behavior behind Claude Code and Codex:

- canonical Tier 0 is `AGENTS.md`; `CLAUDE.md` is an exact generated mirror enforced by
  `tools/sync-agent-entrypoints.py` and the validator;
- `handbook.yaml` declares the canonical entrypoint, mirrors, common launcher markers, and
  both frontend adapters, plus the shared zero-argument startup prompt;
- `playbooks/start-session.md` owns shared behavior, while
  `start-session-{claude,codex}.md` own only complete-loading preflights;
- matching `.claude/skills/` and `.agents/skills/` adapters remain thin;
- `tools/lqcd-claude` and `tools/lqcd-codex` preserve the caller's working directory and
  project instructions, and inject the shared startup prompt when no caller arguments are
  present. Codex uses additive `developer_instructions`, never `model_instructions_file`,
  and does not request an additional writable root or override the caller's permissions;
- `tools/install-codex-skills` optionally exposes the Codex skill through a conflict-safe,
  idempotent user symlink with documented duplicate-discovery and relocation tradeoffs. The
  launcher does not depend on installation.

*Automated acceptance:* the validator rejects frontend-manifest and entrypoint drift;
mirror synchronization is checkable and repairable; both launchers fail actionably without
`LQCD_HANDBOOK`; wrapper tests verify forwarded arguments, common and frontend markers,
shared zero-argument prompting, preserved working directory, and Codex's additive bootstrap;
the Codex wrapper test also rejects `--add-dir` and `--sandbox`. Installer tests cover first
install, idempotence, and conflict refusal.

*Cold-session acceptance matrix:*

| Frontend/case | Expected behavior | State |
|---|---|---|
| Claude launcher, user mode | Tier 0 and shared startup load; only work mode is asked | accepted 2026-08-15 |
| Claude launcher, developer mode | Architecture and roadmap load after explicit declaration | accepted 2026-08-15 |
| Codex launcher, user mode in a project with `AGENTS.md` | Project instructions remain active; Tier 0 and shared startup load | accepted 2026-08-15 |
| Codex launcher, developer mode | Same developer gate and orientation report as Claude | accepted 2026-08-15 |
| Claude without launcher | Partial loading is reported and work stops | accepted 2026-08-15 |
| Codex user skill explicitly invoked without launcher/bootstrap | Skill preflight reports partial loading and work stops | accepted 2026-08-15 |

All six cold cases are recorded and accepted. Functional parity means
the orientation, safeguards, routing, and stop conditions match; the frontend-specific
loading mechanism is allowed to differ.

### Slice 1 — the vertical slice: build QUDA on Perlmutter
`machines/perlmutter/{machine.yaml,notes.md}`, `software/quda/{project.yaml,README.md,
build.md}`, matching `.claude/skills/lqcd-build-stack/` and
`.agents/skills/lqcd-build-stack/` adapters + `playbooks/build-lqcd-stack.md`,
`tools/detect-machine.sh`, and **the first stack record**,
`machines/perlmutter/stacks/quda-cuda<v>-<profile>-2026q3/stack.yaml` — written as the
natural output of the build that actually succeeded.

**`software/quda/build-profiles.yaml` lands here too, with exactly one profile in it** — the
one this build used ([§build-profiles](ARCHITECTURE.md#build-profiles)). A stack references a profile, so
slice 1 cannot produce a well-formed stack without it. One entry, not a taxonomy: the second
profile is written when a second build needs it.

**`stacks/` gets no schema in this slice, deliberately.** A schema written from one instance
encodes Perlmutter's accidents as universals, and the first CUDA/ROCm divergence is exactly
where that breaks. Capture whatever this build genuinely needed as free-form YAML; the
schema is written in slice 2 from two data points.

Validator acceptance expands here: exercise the existing machine and project bindings on
their first instances, define complete `observed_on` semantics from the first real machine
and software facts, and implement that completeness check. `stack.yaml` and
`build-profiles.yaml` are explicit schema-free bootstrap exceptions: the stack exception
ends in slice 2 and the build-profile exception in slice 3.

*Accept:* a cold session builds QUDA correctly on Perlmutter with no re-teaching, and the
stack record it produces is sufficient for a later session to reproduce that build without
re-deriving anything.

### Slice 2 — second machine, same software: QUDA on Frontier
`machines/frontier/` including its first stack, plus **`schemas/stack.schema.json` and its
validator binding, now written from two instances rather than one.**

Also **`tools/build-index.py`**, and the [§indexing](ARCHITECTURE.md#indexing) decision it was waiting on: flat file table
or grouped by object. Two machines is the smallest content that makes the difference legible.

Two systems also make drifting restatements possible for the first time. Implement the P2
restated-value heuristic here, with advisory diagnostics and focused tests.

This is the real test of P3. **If adding Frontier forces an edit to
`playbooks/build-lqcd-stack.md`, machine knowledge has leaked into the task layer** — fix
the factoring before proceeding. Expect HIP/ROCm to stress it hardest, and expect the stack
record to be where the divergence actually shows up: a schema that survives both a CUDA and
a ROCm stack without optional-field sprawl is the thing being validated here.

#### Machine onboarding order, and the one piece of insurance it needs

`[operator]` Live allocations: Perlmutter, Frontier, Aurora, Vista, DeltaAI, Big Red 200,
possibly more. Most used: **Perlmutter, Frontier, DeltaAI.** New systems will arrive.

Machines after Frontier are **not slices** — they are onboarded when needed. The order is
**Frontier → DeltaAI → Aurora**, and the reasoning is worth recording because the obvious
alternative looks better than it is:

- **Frontier second** breaks the vendor axis (AMD/HIP) while holding Slurm fixed. That
  isolates one cause, and it is the divergence most likely to have been silently baked into
  slice 1's free-form stack YAML as a false universal.
- **DeltaAI third** is deliberately the *easy* machine. NVIDIA and Slurm again, closest to
  Perlmutter, so it needs the least new knowledge — which is exactly what makes it the
  acceptance test for "I want to be able to add systems as they come along." An easy
  machine should be cheap; if it is not, the schema is wrong. That signal is only clean on
  a machine with nothing else going on.
- **Aurora later.** It is the most instructive single machine — Intel/SYCL *and* PBS, both
  axes at once — and for that reason the worst slice-2 candidate: two simultaneous causes,
  the least mature QUDA support of the three, and a real chance of stalling on a build
  problem that teaches nothing about knowledge structure. Scheduled where a hard machine
  can be absorbed, and flagged in advance as the one that may force a schema revision, so
  that revision is budgeted rather than a surprise.

This order also has the property that the three most-used machines are covered first, so
the handbook becomes useful in practice at the earliest point.

**The insurance:** three consecutive Slurm machines will encode Slurm as *structure* rather
than as a *value*, and Aurora then pays for it. Cheap fix, from slice 2: write
`machine.yaml`'s scheduler block as **discriminated on `type:`** — `{type: slurm, ...}` —
so that PBS arrives as a new value in an existing shape. The point is not to model PBS
correctly before seeing it; it is to ensure the shape has somewhere to put a second
scheduler. The same applies to `accelerator.vendor`, which Frontier exercises directly.

### Slice 3 — second software: MILC on both machines
`software/milc/`, including the QUDA-interface linkage — the first place where two project
profiles must compose. Adds `software/{qmp,qio}/` as dependencies, plus
`schemas/build-profiles.schema.json` and its validator binding, now derived from profiles
in two software contexts.

### Slice 4 — modes, benchmarking, and the prediction loop
All five `modes/*.md`, `conventions/{running,measurement}.md`,
`playbooks/{run-benchmark,capture-learning}.md`, `schemas/prediction.schema.json`,
the **budget-ledger format** of [§budget-rule](ARCHITECTURE.md#budget-rule) (append-only, debit-at-submit),
`tools/{extract-milc-timings.py,summarize-slurm-job.py,collect-environment.sh}`.
Admit `memory_model.py` and `check_decomposition.py` from validated source versions after screening.
*Accept:* a benchmarking session predicts runtime and memory before submitting, writes the
record **into the working directory**, and files the comparison — and a deliberately stale
fact gets caught by its metric's tolerance ([§tolerances](ARCHITECTURE.md#tolerances)) while ordinary fabric noise does not
trigger a false alarm.

### Slice 5 — software-local solvers and ensembles *(the mining slice; [§developer-mode-spec](ARCHITECTURE.md#developer-mode-spec) governs it)*
`software/<name>/solvers/` seeded from screened, transferable findings in the source tuning corpus;
`ensembles/milc-hisq.yaml`, plus `schemas/ensemble.schema.json` and its validator binding.
Publishability is settled **per class during the import**
([§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)), so the slice is no longer gated on a single up-front decision.

This is the slice where the admission test earns its keep. Run it strictly — stage
extractions **in the working directory beside the source corpus**, assign each candidate a
**scope** and a **durability** verdict
([§admission-test](ARCHITECTURE.md#admission-test)), admit one at a time, and record every rejection as its own file under
`inbox/rejections/` with which test it failed. Expect a wide spread of scopes: universal measurement hygiene, software × solver
cost structure, QUDA-scoped bugs pinned to commit ranges, and a substantial body of
ensemble-scoped parameter knowledge — **all admissible**, each filed where only the sessions
that need it will load it.

*Accept:* three checks. "Which solver stack for ensemble X on machine Y at N solves per
mass" is answered from the handbook alone, with regime and solve count stated. **Every
admitted fact carries a `scope:`, no admitted fact is scoped to an episode, and every
solver fact is filed beneath its software implementation.** And a
tuning session on an ensemble *not* in the corpus loads no ensemble-scoped material at all —
that is the check that narrow knowledge was filed rather than inlined.

### Slice 6 — performance analysis
`modes/performance.md`, `playbooks/analyze-profile.md`, harvested from the operator's PerfAdvisor working tree after screening.

### Slice 7 — automation and enforcement
`tools/log-session.sh` + `tools/install-session-logging.sh` and the detect-and-offer check
in `lqcd-start-session` ([§session-logging](ARCHITECTURE.md#session-logging)); knowledge-capture hooks; the user-mode write guard.
**The `.gitignore` entry that logging makes necessary does not wait for this slice** — the
hazard exists from the first developer-mode session, so it lands in slice 0.

**All three need frontend-specific installers, not only repo files.** Hooks and subagents
are not activated merely by adding the handbook ([§loading-invariants](ARCHITECTURE.md#loading-invariants)), so anything enforcing rather than instructing has to be written into user settings by offer-only installers and versioned here separately from the knowledge. Revisit the loading decision at this point too — a plugin would carry hooks
and agents natively, and by now there is usage data to judge whether that is worth the
install step per machine.

---

<a id="open-questions"></a>
## 10. Open questions for the operator

Nothing here blocks Slice 0b acceptance. New questions land in this section as they arise.

---

<a id="deferred-decisions"></a>
## 11. Deferred decisions

Parked deliberately, each with the **trigger** that should un-park it rather than a slice
number. A deferred decision is only safe when the interim behaviour is conservative; that
column is the test. On the move into the repo ([§plan-ships-with-handbook](ARCHITECTURE.md#plan-ships-with-handbook)) this section travels with `ROADMAP.md`.

| Decision | Interim behaviour | Un-park when |
|---|---|---|
| **Enforcement of the job-submission budget** — agent instruction, a `lqcd-submit` wrapper, or a hook | [§budget-rule](ARCHITECTURE.md#budget-rule)'s default: **no budget stated ⇒ the agent prepares the job and hands the operator the submit command.** Zero machinery, cannot overspend | The first time an agent should submit **unattended**. Until then the conservative default costs nothing and the right mechanism is not yet obvious |
| **Enforcement of user-mode write protection** — instruction, file permissions, worktree, or a `PreToolUse` hook | The P6 instruction of [§handbook-modes](ARCHITECTURE.md#handbook-modes), plus `lqcd-start-session` reporting an unclean handbook tree at session start so a stray edit surfaces the same day | The repo stops changing daily. Read-only permissions fight developer mode, which is *most* sessions during bootstrap. Hooks need an installer regardless ([§loading-invariants](ARCHITECTURE.md#loading-invariants)), so this rides with slice 7 |
| **Domain index shape** — flat table or grouped by object ([§indexing](ARCHITECTURE.md#indexing)) | No generator; Tier-0 routing table only | Slice 2, when two machines make cold-reading legible |
| **Sub-file provenance** — claim IDs with metadata stored separately, versus file-level frontmatter | File-level frontmatter ([§knowledge-atom](ARCHITECTURE.md#knowledge-atom)), and **knowledge files are kept small and atomic** so it stays adequate | A file starts accumulating claims from materially different dates, versions or evidence kinds. Not needed at slice 0, and the machinery costs more than the problem until then |
| **`stacks/` schema** ([§stacks](ARCHITECTURE.md#stacks)) | Free-form YAML written from the slice-1 build | Slice 2, so the schema comes from two instances rather than one |
| **Whether any part of the handbook should be served over MCP** rather than as files, skills and scripts | **None.** Knowledge stays as markdown and YAML read directly; procedures stay as skills plus `tools/` scripts. Works on every machine with no runtime | Any of three: (a) the handbook needs to reach data **too large to commit** — a cross-machine run database is plausible, and would be a *separate* server the handbook talks to, not handbook infrastructure; (b) something genuinely **remote** becomes necessary, such as live job status across machines from one session; (c) slice 6 finds **PerfAdvisor is already service-shaped**, making this a question about preserving an existing shape rather than adding one |
| **Whether session logging should also archive the raw transcript JSONL** for full provenance, tool I/O included ([§session-logging](ARCHITECTURE.md#session-logging)) | **Prose-only.** The shipped logger stays as the operator wrote it; the JSONL under `~/.claude/projects/` is the true last resort where it survives | The prose record proves insufficient to reconstruct an episode the operator needed back — or a machine rebuild/scratch purge destroys a JSONL that was wanted. Note the cost before adopting: much larger files in the working directory, and a far bigger privacy surface, since the JSONL contains every file read and every command run |
| **Whether the handbook is measurably cheaper than the rediscovery it replaces** | No measurement. Cold-session tests stay qualitative | The handbook becomes big enough to feel slow to navigate. **If implemented, it is the lightweight version** (below) — not an A/B harness |
| **How upstream sample scripts relate to the handbook** — whether they are a declared canonical source, a field on a stack, or not represented at all; and how much build knowledge the handbook owns as a result | None. The handbook's build knowledge is written as needed | **When a slice puts a real build in front of us** — slice 1 or slice 3. The design questions here are open and merit their own discussion; deciding them from a description rather than a build would be guessing |


### Notes on deferred decisions


`[operator]` The one input already on the record for that discussion: `milc_qcd/systems/`
holds **sample** QUDA and MILC build and run scripts per system. They are incomplete — they
may not cover a given machine, and they cover essentially one simple stack (QUDA + MILC for
`ks_spectrum` running with CG), not, for example, the multigrid case.

**On that last one, the form is already decided even though the timing is not.** A formal
"same task with and without the handbook" comparison is not affordable or trustworthy here:
it is n=1 per arm against a stochastic agent, where two handbook-free runs of the same build
can differ twofold depending on which wrong path is explored first, and the second arm is
not cold anyway — whoever ran the first one now knows things they leak into the second
through better prompting. It would produce noise that reads like data, which is worse than
no number.

The lightweight version instead, if and when it is wanted:

- **Operator interventions per cold-session test** — how many times the operator had to
  correct or supply something. Countable, low-variance, and it *is* the thing the project
  exists to reduce. Meaningful at n=1 because zero is zero; it needs no control arm.
- **Re-teaching defects** — each time a session had to be told something the handbook
  already contains. Not a metric but a **defect report**: it names a file that failed to be
  found or failed to be right, and it is actionable immediately.
- **Tier-1 bytes actually loaded before useful work began** — the leading indicator of
  navigation overhead, and cheap to observe.

**And a standing rule that needs no harness:** if a session spends more turns navigating the
handbook than doing the task, cut something. The mechanism count in this plan may go **down**
as well as up; [§developer-obligations](ARCHITECTURE.md#developer-obligations)'s slice-boundary review is the place to propose removals, and a
deleted mechanism is a legitimate slice outcome.

The asymmetry that orders the first two: a bad handbook commit costs a `git revert` and is
visible in `git status`; a runaway `sbatch` loop costs allocation that cannot be recovered.
Enforcement effort belongs where the mistake is irreversible.

**On MCP specifically, three arguments that look strong and are not** — recorded so they are
not re-derived:

- **It does not dodge the loading problem, it inherits it.** Skills are the only thing that
  crosses the `--add-dir` boundary ([§session-start](ARCHITECTURE.md#session-start)). MCP servers are
  configured in a project-scoped `.mcp.json` — discovered in the *working* directory, not
  the handbook — or in user settings. A `.mcp.json` shipped in the repo would not load, for
  the same reason hooks do not, and needs the same slice-7 installer.
- **A typed `submit_job` tool would not enforce the budget.** This is the tempting one,
  since it looks like a clean fourth option beside instruction/wrapper/hook. **The agent
  still has Bash**, so an MCP tool is a convention at high cost, not a control. Only
  intercepting the call — a `PreToolUse` hook — actually enforces, which is why the hook
  remains the live candidate.
- **Cross-machine queries are already solved, asynchronously and better.** The handbook is a
  git repo cloned everywhere; [§freshness-model](ARCHITECTURE.md#freshness-model) is exactly this problem
  solved offline. Replacing it with a live network path is a downgrade on login nodes behind
  MFA and restricted egress.

And the cost side is not theoretical: an MCP server is a process with a runtime, on six
heterogeneous login nodes with differing Python/Node environments, module systems, egress
rules and the CPU limits [§build-profiles](ARCHITECTURE.md#build-profiles) already establishes are real.
Markdown plus bash has none of those failure modes. On this fleet that is worth more than
elegance.

---
