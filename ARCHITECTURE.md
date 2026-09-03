# LQCD Agent Handbook — Architecture

This document is the durable design authority for the handbook. Changes require a stated reason and an update to the decision log. Mutable build state and the next action live only in `ROADMAP.md`.

<a id="decisions-locked"></a>
## 1. Decisions locked

Every decision below is settled. Re-opening one needs a reason and a note in the decision
log; the **reopen trigger** column names the condition that would justify it. Anything
*not* settled lives in [§open-questions](ROADMAP.md#open-questions) or [§deferred-decisions](ROADMAP.md#deferred-decisions) — this table plus those two sections is the complete
state, and a reader who wants to know "is this still open?" needs to look nowhere else.

<a id="decisions-foundational"></a>
### 1.1. Foundational

| Decision | Choice | Reopen when |
|---|---|---|
| **Repo split** | Single public repo. No private overlay, no `local/`. Non-transferable knowledge stays in the working directory ([§no-escape-hatch](#no-escape-hatch)) | The operator needs a *durable* fact to travel that cannot be published — the working directory has been shown to cover every case so far |
| **Loading** | One shared contract behind frontend launchers. Both set common launch/frontend markers and preserve working-project instructions; Claude loads an exact `CLAUDE.md` mirror, while Codex receives an additive pointer to canonical `AGENTS.md` without another writable root ([§loading-chain](#loading-chain)). Revisited for Slice 0c: user-wide session logging remains an offer-only installer because it must work outside LQCD projects, Codex plugin hooks still require trust, and Claude/Codex need different adapters | Playbook routing costs more than a per-machine plugin install would, or the Slice-7 enforcement hooks and agents become load-bearing ([§loading-invariants](#loading-invariants)) |
| **Encoding** | Schema-validated YAML for facts a script consumes; Markdown prose beside it for mechanism ([§knowledge-atom](#knowledge-atom)) | — |
| **Build order** | One vertical LQCD-knowledge slice end to end. Slice 1 remains "build QUDA on Perlmutter"; the explicitly scoped Slice 0c pulls the already-designed cross-frontend session-logging adapter forward without changing the knowledge order ([§build-order](ROADMAP.md#build-order)) | — |

<a id="decisions-structure"></a>
### 1.2. Structure

| Decision | Choice | Reopen when |
|---|---|---|
| **Stacks** | Validated machine × software × toolchain × **build profile** records, filed **under the machine** ([§stacks](#stacks)). Never speculative — a stack exists only if it was built and run | — |
| **Build profiles** | Named option sets with **capabilities** live in `software/<name>/build-profiles.yaml`; stacks reference a profile and record what it **cost** here. Where a build may run is machine knowledge; a compute-node build is a job under [§budget-rule](#budget-rule) ([§build-profiles](#build-profiles)) | — |
| **Application guides** | A suite's version-scoped input grammar, work units, output structure, timing-marker semantics, and completion/correctness signals live in `software/<name>/applications/`. They are application guides, not build profiles: work modes own the experimental method, build profiles own compiled capabilities and instrumentation, and stacks own the exact combinations validated on a machine ([§application-guides](#application-guides)) | Several suites expose a stable, useful application schema that is better represented as validated structured data than as prose |
| **Development conventions** | Software-specific code-change and contribution rules live in `software/<name>/development.md`. Because they vary by project and cut across work modes, they load whenever that software is modified or prepared for review; modes and playbooks point there rather than duplicate them. Only software-independent rules belong in `conventions/`. When a rule is executable, its project-specific helper stays centrally discoverable in `tools/`, carries the software name, and is routed only from that development leaf ([§directory-layout](#directory-layout)) | — |
| **Solver placement** | Solver availability and behavior are software-specific. Implementation knowledge lives in `software/<name>/solvers/`; build profiles declare enabled capabilities, and stacks record what was validated. Software-independent terminology belongs in `conventions/`, while `playbooks/tune-solver.md` owns the selection procedure | A body of actionable solver knowledge proves genuinely software-independent |
| **Indexing** | Tier-0 `INDEX.md` is a ~dozen-line routing table; per-domain indices are **generated**, committed, and grouped by scoped object ([§indexing](#indexing)) | A domain has enough objects that grouping obscures rather than improves cold reading |
| **Version pins** | `project.yaml` carries **none**. Pins live in stacks; the checkout in front of you is session state ([§version-lifetimes](#version-lifetimes)) | — |
| **Branch policy** | **There is none, deliberately.** QUDA and MILC are built from `develop`, a feature branch, or a fork, per episode; tagged releases are not used. So the branch is session state too, and the environment-vs-stack check reports **ancestry — including `diverged` — never a commit distance** ([§version-lifetimes](#version-lifetimes)) | Either project adopts a real release cadence |
| **Node types** | One `machines/<name>/` per machine, with `node_types:` inside for CPU/GPU partitions *and* for heterogeneous accelerators — never `machine-gpu/` beside `machine-cpu/`. Node types carry build-determining fields separately from sizing-determining ones, including documented installed inventory per type; stacks record `validated_on:` as a list, and shared-architecture compatibility is **reported as an inference, never as validation**. An explicit operator declaration selects the node type; without one, exactly one profiled node type is the unambiguous default, while multiple profiled types require a declaration. A login host alone never selects it. The resolved type is reconciled against vendor runtime telemetry once a job runs ([§node-types](#node-types)) | — |
| **Machine order** | Frontier → DeltaAI → Aurora, onboarded as needed rather than as slices. Scheduler and accelerator fields are **discriminated on type from slice 2** so PBS and non-NVIDIA arrive as values, not restructures ([§build-order](ROADMAP.md#build-order)) | — |
| **Scheduler submission surface** | Recorded **once per scheduler type** in `conventions/scheduler-surfaces.yaml` — directive prefix, account/chdir/output option names, and the job-id, array, and submit-directory variables — so submission guidance stays scheduler-agnostic. A machine profile names its `type` and carries only what its site genuinely changes or provides; a site facility that does not exist is an explicit `null`, never omitted ([§scheduler-surface](#scheduler-surface)) | A scheduler arrives whose submission surface cannot be expressed as named options and variables |
| **The plan itself** | Ships in the repo as `ARCHITECTURE.md` (durable) + `ROADMAP.md` (state), developer-mode only ([§plan-ships-with-handbook](#plan-ships-with-handbook)) | — |
| **Cross-references** | Stable `<a id="slug">` anchors, not section numbers; numbers stay in headings and may change freely. Validator-enforced. **Long documents only** — knowledge files are already addressed by path ([§stable-anchors](#stable-anchors)) | — |
| **Predictions** | The loop is mandatory in benchmarking and tuning, but records live in the **working directory**; only `prediction.schema.json` ships ([§records-in-working-directory](#records-in-working-directory)) | — |

<a id="decisions-knowledge-contract"></a>
### 1.3. Knowledge contract

| Decision | Choice | Reopen when |
|---|---|---|
| **Admission** | Gate on **durability**, not on breadth. Narrow scope is fine; episodes are not knowledge ([§admission-test](#admission-test)) | — |
| **Scope** | Required frontmatter field, seven levels; it decides *placement*, and only `episode` blocks admission ([§scope-levels](#scope-levels)) | — |
| **Evidence** | One field, seven values, replacing `verified/operator/inferred`. `observations:` required for `reproduced`. No `confidence:` field ([§evidence-vocabulary](#evidence-vocabulary)) | — |
| **Staleness** | `observed_on` compared against the detected environment. No `valid_when` predicate. `review_by` **only** for facts with no version anchor ([§staleness](#staleness)) | — |
| **Mined material** | Staged **outside the repo**, in the working directory beside the corpus, and **defaults to staying out** absent an explicit publishability decision. Publishability is decided **per class, not per item**, during the import ([§validator-not-clearance](#validator-not-clearance), [§ensemble-numbers](#ensemble-numbers)) | — |
| **Calibration accuracy versus refits** | An accuracy observation measured outside a calibration's declared envelope is recorded as a **scoped observation, never folded into a fitted constant**, and no fit is revised while the corpus that validates it lives outside this repository — a revision could then be asserted but not re-checked, trading a verifiable published error for an unverifiable one. Tool changes that only add warnings, legality gates, or reported fields are exempt, because they alter no predicted value ([§validator-not-clearance](#validator-not-clearance)) | A retained validation set makes a fit's published error re-derivable inside the repository ([§deferred-decisions](ROADMAP.md#deferred-decisions)) |
| **Ensemble identity and spacing defaults** | A suffix-free MILC `l...` label identifies an ensemble; a trailing lowercase letter identifies one generation stream and is not part of the ensemble identity. An unqualified spacing resolves only through `operator_resolution.spacing_defaults`; an explicit name, stream, mass, paper key, or geometry wins. A spacing with no published physical-mass default keeps a null `ensemble` rather than silently selecting or relabeling another ensemble | MILC changes its public naming convention, or the operator adopts a different default-selection policy |
| **Reference build scripts** | Public upstream sample scripts may be cited and version-pinned as stack `reference_sources`; they are evidence, not canonical instructions. The validated stack notes own the reproducible procedure and explicitly record deviations from the sample ([§stacks](#stacks)) | A project publishes a supported machine recipe whose contract should supersede handbook-owned reproduction notes |
| **The validator** | Reports what it checked, **never "passed"** ([§validator-not-clearance](#validator-not-clearance)) | — |

<a id="decisions-operation"></a>
### 1.4. Operation

| Decision | Choice | Reopen when |
|---|---|---|
| **Automation of repeated work** | Two separate rules, deliberately not merged. **Authoring time** ([§prefer-a-tool](#prefer-a-tool)): a mined fact that can be executed must ship as a script plus an index line. **Working practice** (`conventions/repeated-work.md`): a procedure a campaign repeats should become a tool, surfaced by a checkpoint at each study or phase closure and each work-mode change rather than by an event trigger, because the set of repeated actions is not visible at the start. Every work mode carries the checkpoint in its `Done` and `Tools and routing` sections, so a mode change fires it mechanically, and the Tier-0 standing rule names the trigger and points at the leaf on [§batch-scripts](#batch-scripts)'s pattern. A new tool is not trusted on a passing run: it must be made to fail on purpose, and a no-op negative test is vacuous | A checkpoint proves too weak in practice — the next stronger anchor is a required field in an existing mandatory record, not a louder instruction |
| **Work mode** | Current, not permanent — may change mid-session, but only by explicit declaration. It follows the immediate decision and deliverable, not every tool used along the way ([§work-mode-currency](#work-mode-currency)) | — |
| **Task-time Tier-2 routing** | Session startup loads Tier 1 only. Before substantive LQCD analysis or action, and whenever a task narrows or changes, the agent derives named applications, solvers, ensembles, and the immediate decision from the operator request and active project instructions, then uses `INDEX.md` and only the matching domain indices to load the smallest Tier-2 leaves whose `load_when` matches. Interpretation of mechanisms, parameters, failures, campaign evidence, or next candidates waits for this check | A reliable executable task router makes the Tier-0 checkpoint redundant |
| **Tuning and benchmarking boundary** | Tuning adaptively searches for a candidate — the solver, build, runtime, resource-placement, and workflow choices being evaluated — while benchmarking measures a candidate and workload frozen before the measured series. A campaign may move from tuning to confirmatory benchmarking, but never occupies a hybrid mode, and an exploratory winner needs an independent confirmation before it supports a benchmark claim ([§work-modes](#work-modes), [§the-loop](#the-loop)) | A durable workflow requires simultaneous adaptive selection and confirmatory measurement with no safe phase boundary |
| **Session start** | Machine and software are **detected**, not asked. Only the work mode is a mandatory question; missing session logging produces a non-blocking offer in the orientation report ([§work-mode-currency](#work-mode-currency), [§session-logging](#session-logging)) | — |
| **Stale clones** | `lqcd-start-session` **auto-pulls** when upstream is a clean fast-forward and the tree is clean except for qualifying pending intake; otherwise it reports and stops ([§freshness-model](#freshness-model)) | — |
| **Privacy-screening boundary** | Screen only the exact material crossing into the handbook: a user-mode inbox entry or a direct developer-mode change. Handbook privacy rules never mandate scanning, redacting, or rewriting the working project that holds source evidence ([§privacy-screening](#privacy-screening), [§handbook-modes](#handbook-modes)) | The repository's publication boundary changes |
| **Concurrency** | Unique filenames for every user-mode write; `base_handbook_commit` on proposals. No branches, no PRs, no curator ([§freshness-model](#freshness-model)) | The handbook gains contributors beyond the operator |
| **Intake lifecycle** | An inbox entry has two pending states, not one: **untracked** (filed locally, unreachable from any other clone) and **committed** (transported so another machine can review it). Both are pending; committing is transport, never admission. Detection is therefore a **listing of `inbox/`**, never a reading of `git status` ([§freshness-model](#freshness-model)) | Intake gains a review queue outside the repository, or entries stop travelling between clones |
| **Handbook change and commit approval** | Developer mode permits analysis and proposals, not unreviewed changes. Every edit must be shown and explicitly approved before application. Commits are operator-owned: the agent never commits unless explicitly requested to create that specific commit ([§developer-obligations](#developer-obligations)) | The operator explicitly delegates a named class of changes or adopts a different review workflow |
| **Project Git authority** | Authorization to change project code does not authorize commits or publication. Canonical `AGENTS.md` owns the standing rule: the agent requires an explicit operator request before committing, pushing, or opening or updating a pull or merge request. The default handoff is an uncommitted working tree, a validation summary, and a suggested commit message | The operator explicitly delegates a named class of Git actions |
| **Job submission** | No budget stated ⇒ the agent prepares the job and hands over the submit command ([§budget-rule](#budget-rule)) | An agent should submit unattended — see [§deferred-decisions](ROADMAP.md#deferred-decisions) |
| **Batch submission scripts** | Guidance is one universal Tier-2 convention leaf, loaded before writing, modifying, or reviewing a batch script or preparing a submit command. Reached from a Tier-0 pointer **and from every task-time routing surface that can reach script work** — modes' "Tools and routing", playbook routing tables — after the pointer alone was observed not to fire (amended 2026-08-29). Mechanically decidable rules move to `tools/check-batch-script.py`, which is **advisory lint, never a sandbox** ([§batch-scripts](#batch-scripts)) | Slice 7 lands a `PreToolUse` guard that enforces rather than advises |
| **Chargeable account** | **Never inferred** — not from a scheduler or environment default, an accounting query, another script in the working directory, or an archived campaign script. Enumerating available accounts is expected; selecting one is not ([§account-rule](#account-rule)) | The operator declares a standing per-campaign default account |
| **Budget** | **Granted** in the opening message, **scoped** per-campaign, **tracked** in an append-only ledger in the working directory. Debit reserved cost at submit, reconcile down at completion. The handbook ships the format, never the numbers ([§budget-rule](#budget-rule)) | — |
| **Test builds** | Build the complete available test suite by default. A reduced test build requires an **explicit operator instruction for that build**; record the opt-out and exact excluded targets. Test execution may remain focused on the validation contract | The complete suite cannot be compiled within available build resources and the operator adopts another standing policy |
| **Session logging** | One frontend-neutral provenance contract with frontend-specific `Stop` loggers, a shared interpreter dispatcher and checker, and an offer-only installer. The dispatcher selects a compatible versioned Python without loading a module; adapters are copied into `~/.claude/` or `~/.codex/`, and Codex still requires user trust. Logs remain **operator-facing provenance backups**: agents do not read them unless the operator explicitly requests review, and authorized review treats them as private evidence rather than canonical knowledge ([§session-logging](#session-logging)) | The prose-only record proves insufficient for reconstructing what happened — see [§deferred-decisions](ROADMAP.md#deferred-decisions) |
| **Interpreter selection** | One shared dispatcher probes caller-declared requirements and rejects any candidate that emits diagnostics. The `PATH` scan never loads a module. A caller whose output is read by a human may additionally opt into **discovering** module-provided interpreters — enumerated from the module system, never named in the tool ([§session-logging](#session-logging)) | A caller needs an interpreter that neither `PATH` nor the module system exposes |
| **Repo name** | `lqcd-agent-handbook` ([§locating-handbook](#locating-handbook)) | — |
| **Locating the handbook** | `LQCD_HANDBOOK` is the sole interface; **the launcher fails fast if it is unset** — no `$HOME` fallback. No canonical path, and no clone path recorded anywhere in the repo: [§deny-list](#deny-list) denies it. Validation is **identity by content**, not by path ([§locating-handbook](#locating-handbook)) | — |

---

<a id="design-principles"></a>
## 2. Design principles

**P1 — The handbook is a router with leaves, not a document.**
A handbook that gets read in full costs more tokens than it saves. Three tiers, with budgets:

| Tier | Content | Budget | Loaded |
|---|---|---|---|
| 0 | canonical `AGENTS.md` (≤ 5 KB) + `INDEX.md` (a few hundred bytes) | **≤ 6 KB combined** | loaded by Codex through its additive pointer or through Claude's exact `CLAUDE.md` mirror ([§loading-chain](#loading-chain)) |
| 1 | one mode doc + one `machine.yaml` + one `project.yaml` + the nearest `stack.yaml` | ~10–15 KB | once machine and software are **detected** and the mode is stated ([§work-mode-currency](#work-mode-currency)) |
| 2 | everything else | unbounded | on demand, by name, from `INDEX.md` |

If canonical `AGENTS.md` starts accumulating facts instead of pointers, the design has failed.
`CLAUDE.md` is a generated compatibility mirror and may never diverge from it.
A prior deep-dive investigation grew a very long entry document. That is appropriate
for an investigation read by long sessions and completely wrong for a handbook read by
dozens of short ones.

**P2 — One *canonical source* per fact; restatements must point to it.** Not "a fact may
appear only once" — that rule forbids a build skill from saying *"on Perlmutter, use the
validated `quda-cuda12-2026q3` stack"* without inlining the module list, which is a pointer,
not a duplicate. What must never happen is **two places that could disagree and no rule
about which wins.**

Legitimate restatements, each already relied on elsewhere in this document:

- **generated views** — the domain indices of [§indexing](#indexing), derived from frontmatter;
- **capability vs. pinned version** — `machine.yaml` says what the site offers, `stack.yaml`
  says what one build used ([§stacks](#stacks));
- **operational summaries** — a skill naming the stack to use without reproducing it.

The rule each must satisfy: **name the canonical home, and never restate a value that could
drift** — restate a *reference*, not a number.

**P3 — Four axes, composed at session start.** `mode × machine × software × (ensemble)`.
A task instruction like "build QUDA" is not one piece of knowledge; it is a generic
workflow that *reads* a machine profile and a project profile.

The test is **whether adding a machine requires editing a playbook**, not whether the
playbook is lexically free of machine names. A playbook that branches on a *capability*
read from the profile — `if the machine is CUDA-based … if HIP-based …` — is correct
factoring, not a violation. Optimise for correctness and maintainability, not for the
absence of strings.

**P3a — but the axes interact, and the interaction needs its own home.** Factoring is not
the claim that machine and software facts are independent. "QUDA commit X builds under
CUDA 12.2 but not 12.4 on this machine" belongs to neither profile, and forcing it into
one produces a misleading universal. Validated combinations are recorded as **stacks**
([§stacks](#stacks)). P3 governs *procedures*; stacks hold *interaction terms*.

**P4 — Every fact carries provenance and can go stale.** Evidence kind, observation count,
date, and the machine + software versions it was observed on ([§evidence-vocabulary](#evidence-vocabulary)). The evidence vocabulary
distinguishes *how* something is known; mechanism independently determines how far it may
generalize. A one-off observation stays an incident, a reproduced fact without a mechanism
remains a scoped empirical claim, and only a fact with a mechanism may become a rule.

**P5 — The handbook must detect its own rot, and no single mechanism does it.** Two are
needed, because they catch disjoint classes:

- **Environment vs. nearest validated stack** ([§stacks](#stacks)) catches build-side rot — module names,
  compiler compatibility, queue policy, build flags. These go stale with *no performance
  consequence at all*, so nothing else sees them.
- **The predict → run → compare loop** ([§predict-compare-loop](#predict-compare-loop)) catches model-side rot — cost and memory models
  drifting from reality.

Neither substitutes for the other. An earlier draft claimed the prediction loop was the only
such mechanism; that was true before stacks existed and is now wrong.

**P6 — Write-protection by mode.** In user mode an agent may write to `inbox/` and
nowhere else in the repo, even under auto-accept permissions ([§modes](#modes)).

---

<a id="directory-layout"></a>
## 3. Directory layout

This is the **target completed-bootstrap layout**, not an inventory of files currently present.
`ROADMAP.md` owns landing state and identifies which target entries remain future additions.

```
lqcd-agent-handbook/
├── AGENTS.md                  # CANONICAL Tier-0 entrypoint (§loading-chain). ≤5 KB;
│                              #   router + standing rules, never a place for facts.
├── CLAUDE.md                  # exact generated mirror of AGENTS.md for Claude Code;
│                              #   validator-enforced and never edited independently.
├── INDEX.md                   # ROUTING TABLE ONLY (§indexing): ~a dozen lines, one per
│                              #   domain. Never one line per file — that does not scale.
├── ARCHITECTURE.md            # the durable design: this document's §decisions-locked
│                              #   … §predict-compare-loop. Developer mode only.
│                              #   Changes rarely and never silently.
├── ROADMAP.md                 # the mutable build state: this document's §build-order
│                              #   … §deferred-decisions — slice status, next action,
│                              #   acceptance results, pending decisions. Dev mode only.
├── handbook.yaml              # the repo's own posture: phase (bootstrap|maintenance),
│                              #   schema versions, tier-budget limits
├── README.md                  # for humans arriving on GitHub
├── PRIVACY.md                 # what may never be committed; the screening checklist
├── CONTRIBUTING.md            # how a fact enters: inbox → review → merge
├── .gitignore                 # `session_*.log` from slice 0 — developer-mode sessions
│                              #   run INSIDE this repo and the Stop hook drops verbatim
│                              #   transcripts here (§session-logging). Not optional.
│
├── conventions/
│   ├── INDEX.md               # generated grouped projection from knowledge frontmatter
│   ├── orientation.md         # HISQ is the default everywhere; vocabulary; units;
│   │                          #   evidence tags; what "solve", "setup", "sweep" mean here;
│   │                          #   the do-not-read rule for session_*.log (§session-logging)
│   ├── batch-scripts.md       # submission-script invariants: append-only w.r.t. inputs
│   │                          #   and shared data, account and ceiling resolution,
│   │                          #   directive pinning, review gate (§batch-scripts)
│   ├── running.md             # env-var capture, verbosity, sacct/scontrol/nvidia-smi
│   │                          #   logging, session logging (§session-logging),
│   │                          #   the job-submission budget rule and its ledger
│   └── measurement.md         # conditional first-solve exclusion for a homogeneous
│                              #   steady-state solver series; tunecache state; CONGRAD5
│                              #   counting; valid benchmark comparisons
│
├── modes/                     # two families; ONE FROM EACH is in force at any moment
│   ├── debugging.md           #  ┐
│   ├── performance.md         #  │ work modes — what the agent is doing.
│   ├── benchmarking.md        #  │ Current, not permanent: may change mid-session,
│   ├── tuning.md              #  │ but only by explicit declaration (§work-mode-currency).
│   ├── production.md          #  ┘
│   ├── user.md                #  ┐ handbook modes — what it may write
│   └── developer.md           #  ┘ (default user; developer is declared, never inferred)
│
├── machines/
│   ├── INDEX.md               # generated; multi-axis stack notes appear here and below
│   └── <name>/                # perlmutter, frontier, deltaai, aurora, vista,
│   │                          #   big-red-200, … (§build-order has the order)
│       ├── machine.yaml       # STABLE CAPABILITY only: what the site offers. Site-wide
│       │                      #   facts once (filesystems, scheduler, modules, policy),
│       │                      #   then `node_types:` — CPU and GPU partitions differ in
│       │                      #   hardware, queues and limits on most machines (§node-types).
│       ├── stacks/            # VALIDATED COMBINATIONS (§stacks). One dir per stack that
│       │   └── <stack>/       #   was actually built and run — never speculative.
│       │       ├── stack.yaml #   e.g. quda-cuda12-2026q3/, milc-quda-2026q3/
│       │       └── notes.md
│       ├── notes.md           # prose: gotchas, folklore-with-evidence, workarounds
│       └── incidents/         # one dated file per incident, co-located with its machine
│
├── software/
│   ├── INDEX.md               # generated; grouped by scoped software object
│   └── <name>/                # milc, quda, grid, qmp, qio, qex
│       ├── project.yaml       # SOFTWARE-INTRINSIC ONLY: what it is, its deps, which
│       │                      #   build options exist and what they mean, which
│       │                      #   interfaces it exposes. NO version pin (§version-lifetimes).
│       ├── build-profiles.yaml# named option sets + the capabilities each yields, e.g.
│       │                      #   cg-staggered vs mg-staggered. Stacks reference these
│       │                      #   rather than restating flags per machine (§build-profiles).
│       ├── README.md          # what it is, how it relates to the others
│       ├── build.md           # the software-specific half of building it
│       ├── development.md     # software-specific code-change and contribution rules;
│       │                      #   loaded when editing source or preparing a change for review
│       ├── applications/      # application-family input/output and work-unit semantics;
│       │   └── <application>.md # version-scoped; never a campaign ledger or build profile
│       ├── solvers/           # implementation-specific solver mechanisms and tuning
│       │   ├── <solver>.md    # parameters, limitations, and enabling-profile links
│       │   └── <solver>/      # deeper tuning and memory-model docs when needed
│       ├── internals/         # deeper reference, loaded only when debugging it
│       └── incidents/         # unexplained occurrences, scoped to a commit range
│
├── ensembles/
│   ├── INDEX.md               # generated even before the first ensemble is published
│   ├── milc-hisq.yaml         # one record per ensemble: volume, a, masses, beta,
│   │                          #   spectrum characteristics, recommended stack, papers
│   ├── <ensemble>/            # per-ensemble detail, loaded ONLY when that ensemble is
│   │   ├── notes.md           #   in play — this is what makes narrow scope
│   │   │                      #   free (§admission-test)
│   │   └── incidents/
│   └── notes.md               # cross-ensemble trends
│
├── .claude/skills/            # Claude Code adapters; thin procedures and pointers.
│   ├── lqcd-start-session/    #   auto-loaded from --add-dir; never owns facts.
│   ├── lqcd-build-stack/      #   `lqcd-` prefix is mandatory — trap T3.
│   ├── lqcd-run-benchmark/
│   ├── lqcd-tune-solver/
│   ├── lqcd-analyze-profile/
│   └── lqcd-capture-learning/
│                              # Hooks and agents still require frontend installation.
│
├── .agents/skills/           # Codex adapters; same names and shared playbooks.
│   └── lqcd-start-session/    #   optional user symlink source; never owns facts.
│
├── playbooks/                 # the durable procedure text each skill points at, in plain
│   ├── start-session.md       #   shared workflow every frontend executes.
│   ├── start-session-claude.md #  Claude Code complete-loading preflight.
│   ├── start-session-codex.md #   Codex complete-loading preflight.
│   ├── build-lqcd-stack.md    #   One file per skill, same stem without the `lqcd-` prefix.
│   ├── run-benchmark.md
│   ├── tune-solver.md
│   ├── analyze-profile.md
│   └── capture-learning.md
│
├── tools/                     # tested executable helpers; software-specific tools carry
│   │                          #   the software name; installers are offer-only
│   ├── lqcd-claude, lqcd-codex # frontend launchers preserving the caller's cwd
│   ├── install-codex-skills   # optional, conflict-safe user skill symlink
│   ├── sync-agent-entrypoints.py # regenerates CLAUDE.md from canonical AGENTS.md
│   ├── build-index.py         # regenerates or checks grouped domain indices
│   ├── detect-machine.sh
│   ├── collect-environment.sh
│   ├── clang-format-quda.py   # QUDA-only changed-line formatter: named worktree files
│   │                          #   or the full merge-base branch diff
│   ├── check-session-logging.py   # startup diagnostic; never installs (§session-logging)
│   ├── install-session-logging.py # shared offer-only installer and frontend dispatcher
│   ├── session_logging.py         # shared configuration/merge helpers
│   ├── log-session-claude.sh      # Claude Stop-hook logger copied into user config
│   ├── log-session-codex.py       # Codex Stop-hook logger copied into user config
│   ├── memory_model.py            # admitted from a validated source model
│   ├── check_decomposition.py     # admitted from a validated source tool
│   ├── extract-milc-timings.py
│   ├── summarize-slurm-job.py
│   ├── check-batch-script.py      # advisory batch-script lint (§batch-scripts)
│   └── validate-knowledge.py      # schema, provenance, privacy, staleness, generated
│                                  #   indices, P2 advisories, and references (§validator-checks)
│
├── schemas/                   # stack.schema.json is derived from the first CUDA and
│   │                          #   HIP instances rather than from one (§stacks)
│   ├── machine.schema.json, project.schema.json, ensemble.schema.json
│   ├── build-profiles.schema.json, stack.schema.json
│   └── incident.schema.json, prediction.schema.json
│
└── inbox/                     # the ONLY path a user-mode agent may write to.
    │                          #   Every write is a NEW uniquely-named file (§freshness-model) —
    │                          #   nothing here is ever appended to or edited.
    ├── proposals/             #   <ISO8601>-<machine>-<uuid>.yaml
    └── rejections/            #   <ISO8601>-<machine>-<uuid>.yaml
                               # NO mining/ — quarantine cannot live in the public repo
                               #   it is quarantining against. Staging is in the working
                               #   directory, beside the corpus (§validator-not-clearance).

# Deliberately absent: local/, and any private overlay repo. See §no-escape-hatch.
```

<a id="plan-ships-with-handbook"></a>
### 3.1. The plan ships with the handbook

A developer-mode agent cannot adhere to an architecture it cannot read, and [§developer-obligations](#developer-obligations) item 1 makes
this document the authority. It therefore lives **in the repo**, not beside the corpus that
happened to prompt it. It moves in slice 0, split along the durable/mutable seam:

| File | Holds | Changes |
|---|---|---|
| `ARCHITECTURE.md` | [§decisions-locked](#decisions-locked) through [§predict-compare-loop](#predict-compare-loop): principles, layout, the four axes, the knowledge-atom contract, screening, the mode specifications, the prediction loop, **and the decision log** | rarely, deliberately, with the reason recorded |
| `ROADMAP.md` | [§build-order](ROADMAP.md#build-order) through [§deferred-decisions](ROADMAP.md#deferred-decisions): slice definitions, per-slice status and acceptance results, **the next action**, open questions, and the deferred-decision register | every developer session |

**The split is not cosmetic.** A prior investigation established the rule it cost sessions
to learn: *duplicating mutable state across two files guarantees they drift.* So —

- **`ROADMAP.md` is the only file that states the next action.** `ARCHITECTURE.md` must
  never contain one; if a "next step" appears there, it is a bug, and deleting it is the fix.
- **`handbook.yaml` is the only machine-readable statement of `phase`.** `ROADMAP.md`
  references it; it does not restate it. One field, one home.
- **Canonical `AGENTS.md` restates neither.** Its exact `CLAUDE.md` mirror routes identically: *if developer mode, read
  `ARCHITECTURE.md` and `ROADMAP.md` before acting; if user mode, never open them.*

That last line is what keeps the Tier-0 budget intact (P1). The plan is substantial and it
is irrelevant to a user-mode session tuning a solver — so it is developer-mode Tier 1, and
a user-mode session pays two lines of routing for it, not two documents.

**The decision log is [§decisions-locked](#decisions-locked)**, which already carries every settled decision with its reopen
trigger. It is a section, not a directory, and it travels with `ARCHITECTURE.md`. What it
must keep as it grows is the *rationale* alongside the trigger: in six months "why does
Claude use `--add-dir` while Codex deliberately does not?" will be asked again, and the
answer should not have to be reconstructed from the section it points at.

**Between [§decisions-locked](#decisions-locked), [§open-questions](ROADMAP.md#open-questions) and [§deferred-decisions](ROADMAP.md#deferred-decisions) the state is complete.** [§decisions-locked](#decisions-locked) is what is settled, [§open-questions](ROADMAP.md#open-questions) what the
operator still owes an answer on, [§deferred-decisions](ROADMAP.md#deferred-decisions) what is parked with a trigger. A reader asking "is
this still open?" looks in three places and nowhere else — which is only true if new
decisions land in [§decisions-locked](#decisions-locked) rather than being left in the section that argued them.

<a id="stable-anchors"></a>
### 3.2. Cross-references use stable anchors, not section numbers

Long documents cross-reference themselves constantly — this one does so over 200 times
across 51 sections. **Section numbers are the wrong identifier for that**, and the failure is silent:
insert one subsection and every later reference still resolves, just to the wrong place. A
dangling-reference check passes throughout. The stranger re-read caught four such
references, and [§ensemble-numbers](#ensemble-numbers) had to be numbered `6.3a` because
renumbering its successors was too expensive to contemplate — the scheme buckling under its
own use.

So every section carries a stable slug, declared as `<a id="slug"></a>` on the line above
its heading, and every cross-reference names the slug:

```
<a id="the-slug"></a>
### 3.7. A section title

…referenced elsewhere as [`[§the-slug](#the-slug)`], which renders as §the-slug.
```

- **Numbers stay in headings** for navigation and for talking about the document, and are
  now **free to change** — they carry no reference load.
- `<a id>` rather than `{#slug}`: the latter is Pandoc/kramdown and GitHub renders it as
  literal text, while GitHub's own auto-anchors derive from heading text *including the
  number*, so they break on renumbering too. An HTML anchor renders invisibly, links
  correctly, and greps cleanly.
- **Inside code fences, use the bare `§slug`** — markdown links do not render there.
- The validator enforces it ([§validator-checks](#validator-checks) item 8), which is the
  whole point: **a stale reference becomes an error instead of a redirection.**

**Scope this deliberately: long documents only** — `ARCHITECTURE.md` and `ROADMAP.md`. The
knowledge files need none of it, because there the atom *is* the file and its path is
already a stable anchor; [§knowledge-atom](#knowledge-atom) and
[§deferred-decisions](ROADMAP.md#deferred-decisions) keep those files small for exactly that reason.
Applying anchors there would be ceremony without benefit.

**The honest limit:** slugs decay too. A section rewritten in substance while keeping its
slug is a subtler wrongness than a stale number, and no validator catches it. Slug stability
is a promise; the check enforces that the promise was *made*, not that it was kept.


<a id="stacks"></a>
### 3.3. Stacks — the validated-combination record

A **stack** is one machine × one software set × one toolchain × one **build profile**
([§build-profiles](#build-profiles)) that **was actually built and run**. It lives under the machine (`machines/<name>/stacks/<stack>/`) because that matches
how it is reached: `detect-machine.sh` runs at session start, so the machine is always known
before the question is asked. Cross-cutting queries — "where do we have a validated QUDA
build?" — are served by a generated index, not by directory structure.

```yaml
# machines/perlmutter/stacks/quda-cuda12-mg-2026q3/stack.yaml
machine: perlmutter
validated_on: [gpu-a100-40]   # node types actually exercised; joins machine.yaml (§node-types)
profile: mg-staggered         # names software/quda/build-profiles.yaml (§build-profiles)
tested_software:
  quda:   {commit: <quda-commit>, branch: develop}
  qmp:    {version: ...}
tested_toolchain:
  compiler: ...
  cuda: ...
  mpi: ...
build:
  cmake_options: [...]        # profile options PLUS whatever this machine needed
  cost:                       # machine-specific, and the reason §build-profiles exists
    where: batch              # login | interactive | batch
    wallclock: 2h10m
    parallelism: 16
    peak_host_memory_gb: 48
validation:
  date: 2026-08-12
  by: <operator|agent>
  tests_run: [staggered_dslash, milc_interface]
  result: pass
```

Three rules, each guarding a specific failure:

**1. A stack exists only if it was validated.** No speculative entries, no "should work",
no filling in the matrix. Machines × software × compilers × CUDA/ROCm × MPI is unbounded,
and a `stacks/` tree that tries to be complete becomes a wall of half-true YAML that is
worse than nothing. **An absent stack is honest information** — "nobody has tried this" —
and it should stay absent until someone does.

**2. Fields are named `tested_*`, never `supported_*` or `valid_from`.** A stack record
says *this combination worked on this date*. It does not license interpolation across a
version range that was never run. The naming makes the overclaim awkward to write, which is
more reliable than a rule telling people not to.

**3. `machine.yaml` and `stack.yaml` split canonical ownership explicitly.**
`machine.yaml` holds **what the site offers** — stable capability, hardware, scheduler,
queue policy. `stack.yaml` holds **what this build used** — pinned versions. Module names
will appear in both; that is a legitimate restatement, not a P2 violation, provided each
side says which is canonical for what. Left unstated, they drift within two months.

**Public upstream sample scripts are reference evidence, not canonical instructions.** A
stack may pin them under `reference_sources` and cite them, but its notes own the tested
procedure and state every material deviation. Sample coverage is intentionally incomplete
and may describe only one narrow application profile; making it canonical would leave the
handbook unable to distinguish a useful starting point from the combination actually run.

**Stacks are also the handbook's cheapest rot detector.** They are its fastest-staling
knowledge — a site module update invalidates one overnight with nobody touching the repo —
and that same property makes the comparison *current environment vs. nearest validated
stack* a concrete staleness signal. It catches the whole class of build/module/queue rot
that a performance-prediction miss never will ([§predict-compare-loop](#predict-compare-loop)).

<a id="indexing"></a>
### 3.4. Indexing: a routing table at Tier 0, generated indices per domain

This contract is implemented by `tools/build-index.py`, four committed domain indices, and
the stale-index check in `tools/validate-knowledge.py`.

An exhaustive one-line-per-file index and a 6 KB Tier-0 budget are **incompatible at any
realistic size** — 200 files at 60 characters is already 12 KB, and no amount of disciplined
editing fixes a scaling contradiction. So the index splits in two:

**Tier 0: `INDEX.md` is a routing table**, roughly a dozen lines, one per domain — what
lives there and when to open it. A few hundred bytes, which leaves the 6 KB budget almost
entirely to canonical `AGENTS.md`'s standing rules. (It currently does not; this is what makes the
budget comfortable rather than tight.)

**Tier 2: each domain carries its own `INDEX.md`, generated** by `tools/build-index.py`
from file frontmatter — `title`, `summary`, `scope`, `load_when`.

Three properties this buys, in order of importance:

1. **Generation is a P2 argument, not a convenience.** A hand-maintained index is a second
   home for descriptive metadata and it *will* drift from the frontmatter. Generated, the
   index is a **projection**: one canonical home, many views.
2. **It dissolves the multi-axis-scope problem.** A fact scoped
   `[machine:perlmutter, software:quda]` can appear in both the machine index and the
   software index while being stored once. **Directory placement therefore stops having to
   encode scope** — it is storage; metadata carries the truth.
3. **Generated indices are committed, not built on demand.** An agent must not have to run
   a script to discover what exists — that is a tool call and a permission prompt before any
   work begins. `build-index.py` runs in CI and at commit time in developer mode, and
   `validate-knowledge.py` fails when a committed index is stale relative to frontmatter.

**What skills do *not* replace.** Auto-discovered skills advertise **procedures**; they do
not advertise **facts**. Nothing tells an agent that `machines/frontier/incidents/` exists.
So [§session-start](#session-start)'s skill loading reduces the need for *playbook* routing, not for *knowledge* routing,
and the domain indices stay load-bearing.

**Slice 2 decision: group by scoped object.** A flat table was rejected because the first
multi-axis stack notes already interleave machine and software facts when projected into
both domains. Grouping gives a cold reader one stable heading per detected object while
preserving a single metadata source. Empty domains still receive a committed generated
index so routing never depends on whether the first fact has landed.

---

<a id="version-lifetimes"></a>
### 3.5. There is no "the QUDA commit" — three lifetimes, three homes

Facts about software have radically different lifetimes, and an earlier draft put them in
one file. `project.yaml` was specified to hold "branch/commit, build flags, deps,
interfaces" — but the operator has QUDA checked out at different commits on Perlmutter, on
Frontier, and locally, and **the handbook cannot name one of them.**

The failure this causes is silent, which is what makes it worth a rule: an agent reads
`commit: <quda-commit>`, assumes it describes the tree in front of it, and gives confidently
wrong build advice. Nothing errors.

| Lifetime | Home | Example |
|---|---|---|
| **software-intrinsic** — true of the code regardless of where it is built | `software/<name>/project.yaml` | what QUDA is, its dependencies, which cmake options exist and what they do, the MILC interface it exposes |
| **version-scoped** — true over a commit range, tied to no particular build | `software/<name>/` docs and `incidents/`, with a commit range in `scope:` | "a QUDA allocation bug, observed on `<quda-commit>`" |
| **validated build** — one machine × software × toolchain that was actually built | `machines/<m>/stacks/<s>/stack.yaml` ([§stacks](#stacks)) | `tested_software: {quda: {commit: <quda-commit>}}` |
| **session state** — the checkout actually in front of you | **nowhere.** `git rev-parse HEAD` | — |

**`project.yaml` therefore carries no version pin.** Pins belong to stacks, which are
records of builds that happened; the handbook describes software, not checkouts.

**What the session does with this** is the same comparison P5 already relies on: detect the
checkout, find the nearest validated stack, and *report the gap*. But the gap is **not a
distance** —

`[operator]` **Each `project.yaml` owns the software's `default_branch`. A newly cloned
checkout selects the remote tip of that branch unless the operator requests another branch
or commit.** This is a source-acquisition default, not a universal branch policy or a claim
that one revision is supported everywhere. An explicit request to reproduce a validated
stack selects that stack's tested commit instead; merely finding a nearby stack does not.
Existing checkouts are never moved to the default branch automatically. **Tagged releases
are explicitly not used for QUDA or MILC:** neither project releases on a regular schedule
and releases run years out of date.

So "40 commits behind" remains the wrong report: an existing or explicitly selected
checkout need not be an ancestor *or* a descendant of the stack's commit. Feature branches
and `develop` diverge, and a commit count between diverged histories is not misleading in
the mild sense — it is meaningless. The check is **ancestry, and the third case is the one
that matters**:

| `git merge-base --is-ancestor` | Report |
|---|---|
| stack commit ⊑ HEAD | HEAD descends from the validated commit |
| HEAD ⊑ stack commit | HEAD is an ancestor of the validated commit |
| neither | **diverged** — no single number describes this, and the stack's build knowledge may not apply at all |

Report the exact commits and branch context in all three cases, but no commit count.

**Better still, ask the question the report is a proxy for.** What anyone actually wants to
know is whether the recorded build options still exist — so check that directly against the
tree in front of you rather than inferring it from topology. It is cheap, it is exact, and
it is valid across diverged histories where distance is not.

That converts the silent error class into a stated one, and it is the same
environment-vs-stack check that detects build-side rot ([§stacks](#stacks)) and orients the session
([§work-mode-currency](#work-mode-currency)). One mechanism, three uses.

**Version-scoped claims state what was tested, not a range.** "Observed on `<commit-a>`;
clean on `<commit-b>` and `<commit-c>`" is defensible. "Broken from `<commit-a>` through
`<commit-c>`" is not, unless the range was actually walked.

**And a SHA alone is not always a durable identifier.** Work done on a feature branch or a
fork may be rebased before it lands, or may never land at all — so the commit an incident
cites can cease to exist, or reappear as a different SHA with the same content. A bare
`observed on <commit-a>` is then unresolvable by the next reader, and silently so.

Therefore **every commit reference records its branch context**, in `stack.yaml`'s
`tested_software` and in `observed_on.software` alike: the branch, and, when that is not the
project's recorded default branch, where it forked from that default. Where even that is
unstable, say so — an observation whose code state cannot be recovered is weaker evidence,
and [§evidence-vocabulary](#evidence-vocabulary) should grade it accordingly rather than let
a precise-looking SHA imply a precision that is not there.

<a id="observed-on-completeness"></a>
#### Complete observation predicates

Slice 1 supplies the first machine and software records, so `observed_on` completeness can
now be stated from real instances instead of guessed in a schema:

- every `machine:<name>` scope requires `observed_on.machine: <name>`;
- every `software:<name>` scope requires an `observed_on.software.<name>` mapping with both
  `commit` and `branch`; a `project.yaml` record imposes the same requirement for its
  `name`, even though the record itself carries no version pin;
- a software observation on a branch other than the project's recorded `default_branch`
  also records the commit where it forked from that default, as `forked_from_default`;
- claims whose behavior depends on a compiler, accelerator toolkit, or other toolchain
  component name the observed component under `observed_on.toolchain`; and
- `universal` facts and requirement-owned policy use a truthful non-version predicate and
  `review_by`, rather than inventing a machine or software context.

These are minimum predicates: an atom may include a more specific node type or toolchain
without widening its scope. Stack records apply the same software commit-and-branch rule
under `tested_software` and join validation to the machine through `validated_on`. The
validator enforces the mechanically decidable machine/software portion; developer review
decides whether a claim is toolchain-dependent.

<a id="node-types"></a>
### 3.6. Node types — one machine, several targets

`[operator]` Several of these machines are used both ways: GPU runs usually, CPU runs
occasionally. That means a different build, different queues and partitions, different
limits — **on the same machine, under the same allocation and site policy.**

**This is not a new axis.** It is an over-flattened `machine.yaml`, which was specified as
though a machine had one hardware description. Perlmutter has had CPU and GPU nodes from
the start. The fix is structural, not dimensional:

```yaml
# machines/perlmutter/machine.yaml — the homogeneous-accelerator case; where a machine
# carries more than one GPU, the keys become specific (see below)
scheduler: {type: slurm, ...}     # discriminated on type — see §build-order
filesystems: {...}                # site-wide facts stated ONCE, never per node type
site_policy: {...}
node_types:
  gpu:
    accelerator: {vendor: nvidia, arch: sm_80, per_node: 4, memory_gb: 40}
    cpu: {...}
    queues: [...]
    limits: {...}
    sizing: {installed_nodes: <documented-count>, ...}
  cpu:
    accelerator: null
    cpu: {...}
    queues: [...]
    limits: {...}
    sizing: {installed_nodes: <documented-count>, ...}
```

The alternative — `machines/perlmutter-gpu/` beside `machines/perlmutter-cpu/` — duplicates
every shared fact, and duplicated knowledge is the stated failure mode (P2).

**Installed inventory belongs to the node type.** Every node type records
`sizing.installed_nodes` from public site documentation. A machine-wide total is derived
only when the types are exhaustive and disjoint; storing only that total would hide the
capacity distinction that determines whether a CPU- or accelerator-specific request is
plausible. The value is documented installed inventory, not current idle, schedulable, or
allocation-eligible capacity. Use it as an upper-bound sanity check, then query the scheduler
for live eligible capacity before judging queue feasibility. A request for a large fraction
of installed nodes triggers a warning and live inspection, not an automatic rejection.

**The build side needs nothing new.** A CPU build is already expressible: it is simply
another stack ([§stacks](#stacks)), and the stack's `validated_on:` list is the join back to
`machine.yaml`'s `node_types:`. That field also lets the staleness check catch a real error — *this stack was validated on GPU nodes and
you are submitting to CPU* — which is otherwise silent until the job fails or, worse,
succeeds slowly.

**The consequence worth naming: the stack, not the machine, is the right unit to resolve at
session start.** CPU-vs-GPU does not stop at the build and the queue. It decides **which
solvers exist at all** — the deflated-CG and multigrid landscape admitted from the source tuning
corpus is QUDA-on-GPU, and a CPU run is a different regime — and it decides whether
`memory_model.py`'s device-memory half means anything. All of that follows from the stack in
one lookup. [§loading-chain](#loading-chain) step 3 resolves it accordingly.

**Two failure modes this creates, both handled by reporting rather than by machinery:**

- **No matching stack is normal, not an error.** During slice 1, and in any debugging
  session where the point is to build something new, there is no validated stack. Report it
  as unvalidated territory and continue. It *is* mode-sensitive, though: in production mode
  running against no validated stack deserves a loud warning; in debugging mode it is the
  expected state.
- **Node-type resolution is deterministic, not guessed.** An explicit operator declaration
  wins. Without one, a machine profile containing exactly one `node_types` entry supplies
  that sole type as the default; a profile with multiple entries remains unresolved until
  the operator declares one. `detect-machine.sh` reads a hostname, but a login node alone
  never selects a partition or node type. This removes a redundant prompt on single-target
  machines without inventing intent on heterogeneous ones.

#### Heterogeneous accelerators, and the distinction that matters

`[operator]` A single machine may also carry **different GPUs**: 40 GB beside 80 GB A100s,
or — more starkly — an A100 partition beside a GH200 partition. `node_types:` already holds
this; keys simply become specific (`gpu-a100-40`, `gpu-a100-80`, `gpu-gh200`, `cpu`) rather
than a bare `gpu`. What matters is that these two examples differ in kind:

| | Same arch, different memory (A100 40 vs 80 GB) | Different arch (A100 vs GH200) |
|---|---|---|
| Build | **identical** | **different** — `QUDA_GPU_ARCH`, often a different toolchain |
| QUDA tunecache | not portable across devices in practice | definitely not portable |
| Memory model | **different** — this is the whole difference | different |
| Decomposition | **different** — feasible node counts change | different |

**So the two consequences must be tracked separately.** Splitting stacks on memory rebuilds
identical binaries for no reason; *not* splitting on architecture silently runs an sm_80
build on sm_90 hardware. `node_types` therefore carries both the build-determining fields
(vendor, arch, toolchain constraints) and the sizing-determining ones (device memory, GPUs
per node, interconnect), and consumers take what they need: the build path reads the first
group, `memory_model.py` and `check_decomposition.py` read the second.

**Compatibility is inferable; validation is not.** [§stacks](#stacks)'s rule 1 — a stack exists only if it
was validated — must not be quietly weakened into "an sm_80 stack covers every sm_80 node
type." Instead `stack.yaml` records `validated_on:` as a *list* of node types actually
exercised, and where another node type shares the architecture the agent may **report the
likely compatibility as an inference, flagged as such**, rather than presenting it as a
validated build. Preserving that line is the difference between an honest stack record and
a matrix quietly filled in.

**The tunecache follows the node type, not the machine.** `[operator]` A tuning run must
precede benchmarking, and a cache tuned on one accelerator does not carry to another — so
cache identity is keyed by node type. On a heterogeneous machine, "there is already a
populated tunecache" is not a machine-level fact and must not be recorded as one.

**And here detection *does* return, after the fact.** The resolved node type is the planned
target; once a job is running, vendor runtime telemetry such as `nvidia-smi` or `rocm-smi`
reports what it actually got. Reconciling the two is cheap and catches the case where a job landed on
hardware other than the one planned for — which on a mixed-memory partition is easy to do
and otherwise shows up only as an unexplained performance or OOM anomaly.

<a id="build-profiles"></a>
### 3.7. Build profiles — what a build can do, versus what it cost to build

`[operator]` The same software is compiled differently for different work: a QUDA build for
CG solves is not a QUDA build for multigrid. MG needs different flags, and it takes **much**
longer to compile — long enough that a login node may be the wrong place for it, and
`salloc`/`sbatch` the right one.

Two facts are entangled there, and they belong in different homes:

- **What option set means "multigrid"**, and what capabilities it yields — *software*
  knowledge. True of QUDA everywhere.
- **What that build cost on this machine, and where it was allowed to run** — *machine ×
  software* knowledge, which is exactly a stack.

So `software/<name>/build-profiles.yaml` names the option sets, and stacks **reference a
profile** rather than restating its cmake options on every machine:

```yaml
# software/quda/build-profiles.yaml
profiles:
  cg-staggered:
    options: [QUDA_DIRAC_STAGGERED=ON, QUDA_MULTIGRID=OFF, ...]
    capabilities: {solvers: [cg, deflated-cg], dirac: [staggered]}
  mg-staggered:
    options: [QUDA_MULTIGRID=ON, QUDA_MULTIGRID_NVEC_LIST=..., ...]
    capabilities: {solvers: [cg, deflated-cg, multigrid], dirac: [staggered]}
    build_cost: expensive     # qualitative here; the number is per-machine, in the stack
```

**Why the capability list, and not just the flags.** A session asks *"can I run multigrid
here?"*, not *"is `QUDA_MULTIGRID` set?"*. Making capability explicit is what lets the
generated index answer the first question, and it keeps the flag→capability mapping in the
one place that should own it ([§version-lifetimes](#version-lifetimes): `project.yaml` holds which options exist and what they
mean). Profiles are version-sensitive — option names come and go — so a profile that stops
matching a checkout is version-scoped knowledge and carries a commit range like any other.

**Capability variants multiply stacks deliberately, and that is fine.** A CG-only and an MG
stack coexisting on one machine is not matrix-filling — both were validated, so [§stacks](#stacks)'s rule
1 holds. And the reason to keep both is precisely the build cost: **an expensive MG build is
the argument for retaining a cheap CG-only stack** when the work does not need MG. Record
that trade, not just the two records.

**Where a build may run is machine knowledge.** `machine.yaml` gains a `build_environment:`
— whether long compiles are permitted on login nodes and under what CPU/wallclock limits,
whether dedicated build nodes exist, and **which filesystem to build on**, since compiling
many small objects on a parallel filesystem is markedly slower than on node-local storage
and is the kind of thing rediscovered painfully once per machine.

**The stack records the cost, because that is what makes the next build predictable:**
wallclock, `-j` parallelism, peak host memory, and where it ran. Host memory earns its place
— parallel `nvcc` template instantiation is memory-hungry, and `-j` × per-job footprint
overrunning a shared login node is a routine way to get a build killed, or to get a polite
note from the site.

**A compute-node build is a job.** If MG must be built under `salloc` or `sbatch`, it
consumes allocation and therefore falls under [§budget-rule](#budget-rule) — a stated ceiling, a ledger debit, the
same as any run. Worth saying explicitly, because "the budget rule is about runs" is the
natural assumption and it is wrong.

<a id="application-guides"></a>
### 3.8. Application guides — how one executable describes work

Some software projects are suites whose applications accept different input grammars, perform
different repeated work, and emit outputs with different timing and correctness semantics. A
software-level statement such as "parse the MILC output" is therefore too broad to act on, while
putting those details in benchmarking mode would make a software-independent method depend on
one application.

Application-family knowledge lives in
`software/<name>/applications/<application>.md`. Call these **application guides**, not bare
"profiles": a build profile already means a named option set and capability claim. An application
guide:

- names the application family and the executable variants actually covered;
- identifies the portable application directory, upstream target mapping, and invocation shape
  needed to build those variants without restating profile- or machine-owned flags;
- describes the ordered input sections and the count fields that delimit repeated records;
- defines the meaningful work units and how they map to input sets, output blocks, and artifacts;
- identifies normal-completion, correctness, convergence, and rejection signals;
- maps application, library, and backend timing markers to their semantic and recurrence scope;
- distinguishes unconditional output from build-time instrumentation and backend diagnostics;
- states the observed software revision and every important coverage gap.

The guide owns portable application entry points and interprets their output; it does not own a
campaign's inputs, outputs, measurements, selected parameters, compiler flags, or dependency
prefixes. Those remain in the working directory or their canonical build profile and machine
stack. A portable recipe is not a validation claim: build profiles own enabled instrumentation
and compiled capabilities, while stacks own the executable revision and paths actually built and
run on a machine.

Work modes compose with these guides. Tuning and benchmarking define how candidates are selected
or frozen, while the relevant application guide defines what a solve, trajectory, input set,
completion marker, or timer means for that executable. When an application lacks a guide, the
session must characterize those boundaries from source and representative output before treating
an extracted number as comparable evidence.

<a id="scheduler-surface"></a>
### 3.9. The scheduler submission surface

Submission guidance must not name one scheduler. Three profiled machines are Slurm and
Aurora is PBS, so a leaf that writes `sbatch`, `#SBATCH`, or `$SLURM_JOB_ID` into its prose
fails the P3 test the moment Aurora lands. The slice-2 insurance already discriminates
`scheduler:` on `type:` so a second scheduler arrives as a value; this section states what
that block must carry for the discrimination to be usable by a consumer rather than merely
well-shaped.

**The surface belongs to the scheduler, not to the machine.** Implementation made this
concrete: the three profiled machines are all Slurm, and their `scheduler:` blocks were
byte-identical. Writing `#SBATCH`, `--account`, and `SLURM_JOB_ID` into each profile would
restate three dozen values that cannot legitimately differ, which is precisely the drift P2
forbids, and would make Aurora a hand-filled fourth copy. So the surface is recorded once
per scheduler type, in `conventions/scheduler-surfaces.yaml`:

```yaml
surfaces:
  slurm:
    submit_command: sbatch
    interactive_command: salloc
    query_command: squeue
    queues_command: sinfo
    directive_prefix: "#SBATCH"
    account_option: "--account"
    chdir_option: "--chdir"
    output_option: "--output"
    error_option: "--error"
    append_output_option: "--open-mode=append"
    job_id_variable: SLURM_JOB_ID
    array_job_id_variable: SLURM_ARRAY_JOB_ID
    array_task_id_variable: SLURM_ARRAY_TASK_ID
    submit_dir_variable: SLURM_SUBMIT_DIR
```

Every field is here because [§batch-scripts](#batch-scripts) or its checker consumes it;
none is decorative. Aurora then arrives as one new `pbs` entry, which is what the slice-2
insurance promised when it discriminated the block on `type:`.

**A machine profile names its `type` and carries only what its site changes or provides.**
It may override any field, because a site can wrap a submit command or disable an option;
absent an override the type record is canonical, so there is never a pair that can disagree
without a rule about which wins.

**A site facility that does not exist is declared as an explicit `null`, never omitted.**
This is a machine-profile field, because whether a site exports a node-local temporary
directory is a site convention rather than a property of the scheduler. It is also the
mechanism that replaces naming a site variable in prose. A live Perlmutter
session found `SLURM_TMPDIR` unset, and the two safeguards a submission script normally
carries interact badly there: under `set -u` the reference aborts the job, and without it
`"${SLURM_TMPDIR}/work"` expands to an absolute path at the filesystem root. An explicit
`null` states *this site provides none* — a fact — while an omitted key is indistinguishable
from one nobody recorded. The same rule governs which filesystem variables a script may
name: only those a profile declares, which is why the guidance never writes `$SCRATCH`,
`$PROJECT`, or `$CFS` into its own text.

**Populate from fact, not from anticipation.** The Slurm values are recorded because they
are verified. PBS values arrive with Aurora; inventing them now would be the overclaim
[§stacks](#stacks) rule 2 exists to prevent, in a schema instead of a stack. The same rule
binds the site fields: `node_local_tmp_variable` is recorded only where it was actually
checked, and stays absent elsewhere. An unrecorded field means *nobody has established
this*, and a consumer must ask rather than assume — which is why absence and an explicit
`null` are deliberately different states.

<a id="session-start"></a>
## 4. How a session starts across frontends

The handbook presents one session-start contract through frontend-specific adapters.
Verified loading facts are kept explicit because Claude Code and Codex discover external
instructions differently.

`[verified]` against the Claude Code documentation, 2026-08-12:

- `.claude/skills/` inside an `--add-dir` directory loads automatically;
- a root `CLAUDE.md` there loads only with
  `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`;
- other `.claude/` configuration, including hooks and agents, does not cross that boundary.

`[verified]` against the Codex documentation, 2026-08-15:

- Codex builds its `AGENTS.md` instruction chain from the working-project root toward the
  current directory; `--add-dir` grants another writable root but does not add that
  directory to the instruction chain, and it is rejected when effective permissions do
  not allow additional writable roots;
- project skills are discovered from `.agents/skills/` between the current directory and
  repository root, while user skills live in `$HOME/.agents/skills`; symlinked skill
  directories are supported;
- the `developer_instructions` configuration field is additive, while
  `model_instructions_file` replaces the normal instructions and therefore must not be used
  for this integration.

<a id="loading-chain"></a>
### 4.1. The shared contract and adapter chains

1. A frontend launcher resolves `LQCD_HANDBOOK` and exports
   `LQCD_HANDBOOK_LAUNCHED=1` plus
   `LQCD_HANDBOOK_FRONTEND=<claude|codex>`. There is no path fallback; see
   [§locating-handbook](#locating-handbook). On a zero-argument launch, it passes the shared,
   manifest-declared `playbooks/start-session-prompt.txt` as the initial user prompt so the
   workflow begins without operator prompting. Caller-supplied arguments pass through
   unchanged. Claude adds the handbook through its additional-directory mechanism. Codex
   points to the absolute handbook path in additive instructions without requesting an
   additional writable root or overriding the caller's permission profile.
2. The canonical Tier-0 rules live in **`AGENTS.md`**. Claude Code loads the validated,
   byte-identical `CLAUDE.md` mirror through its additional-directory memory flag. Codex
   receives an additive `developer_instructions` pointer to canonical `AGENTS.md`; the
   working project's own `AGENTS.md` chain remains active.
3. The active adapter runs the same `playbooks/start-session.md`, which first routes to
   `start-session-claude.md` or `start-session-codex.md` for complete-loading checks. The
   Claude skill is auto-discovered from the added directory. Codex can start directly from
   the injected pointer; `.agents/skills/lqcd-start-session/` is also the source for an
   optional user-scoped skill symlink.
4. The shared playbook detects machine and software, loads the applicable mode and nearest
   stack, and reports `no matching validated stack` when none exists. That is Tier 1;
   everything later is Tier 2, pulled by name from `INDEX.md`.

The launchers deliberately preserve the caller's current directory. The handbook augments a
working project; it never becomes the working project and never replaces that project's
instructions.

<a id="loading-traps"></a>
### 4.2. Three traps this creates

**T1 — file access is not instruction discovery.** Claude Code needs both `--add-dir` and
its additional-directory memory flag for the mirror. Codex does not add an external
`AGENTS.md` or `.agents/skills/` directory to the working project's discovery chain, and
its `--add-dir` flag is a write grant rather than a read-only loading mechanism.
Consequently each launcher must use the frontend's explicit bootstrap mechanism; a generic
`--add-dir` wrapper is both insufficient and too permissive for Codex.

**T2 — partial loading remains a live failure mode.** A skill, an added directory, or an
instruction pointer can be present while the Tier-0 rules or the correct adapter are absent.
Every adapter therefore carries independent safeguards, checks the shared launcher and
frontend markers, and stops with `partial loading` rather than reconstructing missing rules.

**T3 — user- and repository-scoped skills with the same name are not merged.** All
handbook skills carry the `lqcd-` prefix. The Codex installer is offer-only, creates a
symlink to the versioned skill, is idempotent for that exact link, and refuses to replace
any existing file, directory, or different symlink. When Codex runs inside the handbook
repository, both the repository skill and optional user link may appear; the user link is
intended for sessions in other repositories. Because it is an absolute symlink, moving the
handbook clone requires removing the obsolete link and reinstalling it.

<a id="freshness-model"></a>
### 4.3. Many machines, many sessions: a freshness model, not a merge model

The handbook is cloned on every system the operator works on, and sessions start there many
times a day. The obvious worry is concurrent writes; **the real risk is a stale clone.**

A merge conflict is loud and git handles it. A clone three weeks behind is silent: an agent
on Frontier reads a fact that was corrected on Perlmutter and acts on it with full
confidence. That is precisely the failure the handbook exists to prevent, so freshness gets
the mechanism and merging gets a convention.

**Why contention is smaller than it looks.** In user mode an agent writes only *new*
files under `inbox/`, never editing anything that exists — so there is nothing to conflict
on. The only genuine multi-writer targets are `ROADMAP.md` and canonical knowledge files,
and those are written only in developer mode: one operator, usually one session.

Seven rules:

1. **Everything user mode writes is a new, uniquely-named file** —
   `<ISO8601>-<machine>-<uuid>.yaml` under `inbox/proposals/` or `inbox/rejections/`.
   No shared append targets. (An earlier draft had a single `inbox/rejected.md`; it was a
   merge-conflict magnet and is removed.)
2. **Every proposal carries `base_handbook_commit`**, plus `machine` and `created`. This is
   what distinguishes "this contradicts the handbook" from "this contradicted an *old*
   handbook", and it is nearly free to record.
3. **A qualifying new untracked inbox entry is pending intake, not a dirty-tree
   failure.** It qualifies only when Git reports it as `??`, it is a direct child of
   `inbox/proposals/` or `inbox/rejections/`, its name follows the required convention,
   and no other status is present. This classification is structural only: it neither
   inspects nor clears the contents. Report each pending path. Modified, deleted, or renamed
   tracked paths; nested or misnamed inbox paths; and changes anywhere else remain hard
   stops.
3a. **Frontend session tooling is declared non-content in `.gitignore`, so it never reaches
   rule 3.** An agent sandbox materialises a placeholder at every path it denies writes to,
   and Git reports each as `??` although nothing was authored — enough to stop a session on
   the sandbox's own bookkeeping, as ten such paths did on Perlmutter on 2026-08-28. Do not
   try to recognise a placeholder by inspecting it: that same sandbox represented the same
   paths first as character devices owned by `nobody` and then, minutes later, as empty
   unwritable regular files owned by the operator. Ownership, size, mode, and file type all
   moved. Declaration is stable where inspection is not, so `.mcp.json`, `.claude/*`, and
   `.agents/*` are ignored, with the handbook-owned `skills/` directories re-included — a
   new or modified file under `.claude/skills/` is still reported, because that part *is*
   handbook content. Extend the ignore list when a frontend adds a tooling path; outside
   those declared paths, a `??` entry is real and rule 3 applies unchanged.
4. **A committed inbox entry is pending intake too, and it is the ordinary
   cross-machine case.** An untracked proposal cannot leave the clone that wrote it, so the
   only way to put one in front of the machine that will review it is to commit it.
   Committing an entry is an act of **transport, not of admission**: it changes where the
   proposal can be read, never whether it has been accepted. Such an entry produces no
   status output at all, so **intake is detected by listing `inbox/proposals/` and
   `inbox/rejections/`, never by reading `git status`** — ignoring `.gitkeep`. Report every
   entry found, in either state, and treat neither state as clearance.
5. **Disposition empties the inbox.** Promotion writes the leaf and removes the proposal;
   rejection records the outcome under `inbox/rejections/` and removes the proposal. An
   entry therefore lives exactly as long as it is undecided, so a non-empty `inbox/` always
   means undecided work. That invariant is what makes a directory listing trustworthy, and
   it is why a decided entry is never left in place as a record of its own decision.
6. **`lqcd-start-session` resolves freshness before any work begins.** Fetch the configured
   upstream. If HEAD already matches upstream, continue. If upstream is a fast-forward and
   the tree is clean or contains only untracked pending intake, **pull with
   `git pull --ff-only`**. On an incoming-path collision, other dirtiness, an ahead branch,
   a missing upstream, or divergence, report the state and stop. Report committed intake in
   the orientation summary; it never blocks, because it leaves the tree clean.

   **A fetch that fails on the environment is not divergence.** A sandbox with a read-only
   `HOME` cannot take Git's credential lock, and the fetch dies before reaching the network
   (`unable to get credential storage lock`). Retry once as
   `GIT_TERMINAL_PROMPT=0 git -c credential.helper= fetch`, which needs no credentials for a
   public HTTPS remote and fails immediately rather than hanging on a prompt for a private
   one. If the retry also fails, freshness is genuinely unverified: report that and stop.
   The gate is never satisfied by a fetch that did not run.
7. **Developer mode requires current HEAD and a clean tracked tree before it may write.**
   Untracked pending intake may remain while it is reviewed; committed intake needs no
   exception, because it is not dirt. In both states, compare each entry's
   `base_handbook_commit` with current HEAD before promotion or rejection. There is no
   other dirty-tree exception; [§developer-obligations](#developer-obligations) scopes the
   gate itself to drift the session did not author.

**No branches, no pull requests, no curator role.** Direct commits to main in developer
mode. Those are multi-developer conventions with no second reviewer here; revisit only if
the handbook gains other contributors.

<a id="loading-invariants"></a>
### 4.4. What this does *not* change

**Knowledge still lives in plain Markdown and YAML, and skills stay thin.** Frontend discovery rules differ, so durable content must remain in ordinary files that every adapter — or a human with a text editor — can reach. A skill is a procedure plus pointers; it is never the only copy of a fact.

**Hooks and subagents cannot be assumed to activate merely because the handbook is added.**
Anything relying on them needs an installer that writes into user settings and remains a
separate artifact from the repo's own contents. Session logging exercises that contract in
Slice 0c with explicit consent and Codex trust; technical enforcement of the user-mode
write restriction (P6, [§handbook-modes](#handbook-modes)) remains deferred to Slice 7
([§deferred-decisions](ROADMAP.md#deferred-decisions)).

<a id="session-logging"></a>
### 4.5. Session logging: operator provenance, not an agent input by default

The contract is frontend-neutral and the adapters are not. On every assistant-turn
boundary, a user-level **global `Stop` hook** re-renders the transcript to
`<launch-dir>/session_<date>_<session-id>.log`: user prompts and visible assistant text,
with tool calls and tool outputs excluded. The logger is idempotent, pins to the launch
directory rather than the live `cwd`, waits for transcript flushing where needed, writes
atomically, and sets mode `0600`.

`[verified]` Claude Code uses the Bash + `jq` adapter copied to
`~/.claude/log_session.sh` and a `Stop` command merged into
`~/.claude/settings.json`. `[verified]` Codex uses the Python adapter copied to
`~/.codex/log_session.py` and a `Stop` command in user-level `hooks.json` or inline
TOML. Codex supplies `transcript_path` and `last_assistant_message`, documents its
transcript JSONL as unstable, and requires the operator to review and trust the exact
non-managed hook definition through `/hooks`.

**Interpreter selection is explicit and does not mutate modules.** A live Perlmutter
startup exposed two independent hazards: the unversioned system `python3` was too old to
parse the tools, while a module-provided Python emitted scheduler-authentication diagnostics
into otherwise valid JSON. NERSC's site-injected Python monitor can also sample
nondeterministically at interpreter exit, after an otherwise clean capability probe. The
shared dispatcher therefore disables NERSC PyMon for its own subprocess, prefers a
compatible versioned command, verifies the required Python, YAML, and TOML capabilities,
rejects candidates that emit diagnostics during the probe, and only then executes the
checker or installer. The disable variable is inert away from NERSC and does not alter the
caller's module state. The Codex installer records the selected absolute interpreter in the
hook command, so later hooks do not depend on `PATH` or a module environment.

**The no-module rule is scoped to the session-logging path, not to every caller.** Its
reason is output integrity: this checker's stdout is parsed as JSON, so an interpreter that
emits site diagnostics corrupts the result even when its imports succeed. That reason does
not transfer to a caller whose output a human reads. A Perlmutter developer session found
the consequence: the knowledge validator additionally requires `jsonschema`, no interpreter
on `PATH` provided it, and [§developer-obligations](#developer-obligations) item 6 makes that
validator mandatory before every commit — so the one check guarding the privacy deny-list
could not be run at all.

**A human-facing caller may therefore opt into module-provided interpreters, by discovery
rather than by name.** The dispatcher enumerates what the module system offers and probes
each candidate with the caller's own requirements, in the same preference order the `PATH`
scan uses; it never carries a module name, which would be machine knowledge in a shared tool
(P3). The existing safeguards are what make this safe without new machinery — because the
dispatcher already suppresses the site Python monitor for its own subprocess, the preferred
module on the machine that exposed the defect probes cleanly and is selected, while the
reject-on-output rule still stands guard over any candidate that emits regardless. Selection
remains explicit, the probe is unchanged, and the load happens in the dispatcher's own
process, so no caller's environment is mutated. Session logging does not pass the flag and
its behaviour is unchanged.

**Startup checks and offers; it never auto-installs.** After handbook freshness is
established, `lqcd-start-session` runs `tools/check-session-logging.py` through the shared
interpreter dispatcher for the active frontend. Missing, stale, or broken state produces a non-blocking offer in the orientation
report rather than a second mandatory question. Codex trust is not inferred from config
files: configured state is reported separately, and the operator completes trust in the
frontend. Declining changes nothing and is not persisted.

**Installation remains a user decision.** On explicit consent,
`tools/install-session-logging.py` dispatches to the active frontend, backs up and merges
user configuration, preserves unrelated hooks, and copies the adapter into that
frontend's user directory. It refuses malformed or ambiguous configuration rather than
guessing. It cannot arrive merely through `--add-dir` ([§loading-invariants](#loading-invariants)), and it
must not point a global hook into `$LQCD_HANDBOOK`: unrelated sessions must not fail
because a clone moved or disappeared. The startup checker compares the copy with the
handbook and can offer repair when they drift.

**The plugin question was reconsidered here and the launcher design remains.** This logger
applies to every agent session on the account, not only projects that enable an LQCD
plugin. Codex plugin hooks still require the same explicit trust, and a plugin would not
provide the Claude adapter. The offer-only user installer is therefore the smaller common
contract; Slice 7 may revisit plugins for enforcement hooks and agents with different
scope.

**What the logs are for.** `[operator]` They are a last-resort backup of the work and
thinking a session contained — an **ultimate provenance record for the operator**, not a
routine knowledge source for the agent.
**Explicit review is a narrow operator-controlled exception.** It exists for recovery or
targeted reasoning analysis. Authorization to read is not publication clearance: the
transcript remains private, and any durable candidate follows mined-material
classification, targeted repository-boundary privacy screening, and an affirmative publishability decision
before admission. Two consequences:

- **They are not an input to the capture loop ([§predict-compare-loop](#predict-compare-loop)) by default.** Predictions and
  comparisons live in session memory, or — when work crosses sessions — in a document the
  agent writes deliberately into the working directory. Reasoning worth keeping should be
  written down on purpose. Routine capture never mines logs merely because they are
  present; only an explicit operator request activates the exception above.
- **`conventions/orientation.md` carries an explicit rule: do not read `session_*.log`
  unless the operator explicitly requests it.** This has to be a rule rather than an omission, because a
  fresh agent landing in a working directory will *see* the file, obviously relevant and
  full of context. It is a token trap — verbatim transcript is the least dense form of that
  knowledge and the most likely to be stale. State the reason with the rule; a rule without
  one gets rationalized around.

**The privacy consequence is immediate.** During bootstrap, most sessions are developer-mode
sessions run *inside the handbook repo* — so the hook drops verbatim transcripts into a
public repo's working tree, `git add`-able, containing precisely what [§deny-list](#deny-list) denies:
usernames, paths, hostnames, and whatever was discussed. `session_*.log` goes in
`.gitignore` **at slice 0**, and `PRIVACY.md` names it as a known hazard. A file nobody
reads is exactly the file that gets committed by accident.

**Prose-only, for now.** Both filters exclude tool I/O, which sits in mild tension
with "a backup of the actual work": on a debugging session the build command and its error
output *are* the work, and what survives is the narration about it. The raw transcript JSONL
under each frontend's user state still holds everything, so it remains the true last
resort — but it is keyed by session id, nowhere near the work, and the first thing lost
when a machine is rebuilt or a scratch filesystem is purged. Archiving it alongside the
log is parked in [§deferred-decisions](ROADMAP.md#deferred-decisions) rather than decided here.

<a id="locating-handbook"></a>
### 4.6. Locating the handbook: `LQCD_HANDBOOK` is the contract

The repo is **`lqcd-agent-handbook`**. Every document calls the thing a handbook, and
"knowledge" oversells it — the repo is at least as much procedure, skills and tools as it
is facts.

**There is no canonical path, and the handbook must never record one.** Clone locations on
these systems look like `/global/homes/<u>/<user>/…` or `/lustre/…/proj-shared/<alloc>/…`:
usernames and allocation codes, which [§deny-list](#deny-list) denies outright. So a clone path is not merely
awkward to store, it is unpublishable. It is also not machine knowledge — `machine.yaml` is
stable site capability, and where one operator's clone sits is neither stable nor the
site's — and it is self-referential: a file inside the repo naming the repo's location can
only be read by something that already found the repo. It could validate; it could never
locate.

**`LQCD_HANDBOOK` is therefore the whole interface, and the launcher fails without it.**
An earlier draft fell back to `$HOME/lqcd-agent-handbook`. That silently undermines the
contract: a machine where the variable was never set keeps working until the day `$HOME` is
not where the clone lives — small-quota home filesystems, or homes not mounted on compute
nodes, make that a question of when — and the failure is reading an unintended tree while
everything looks fine. Failing fast costs one line in a shell profile on a new machine,
at a moment when you have just cloned the repo and know exactly where it is.

**Most of the checking is replaced by construction.** The launcher resolves the variable
with `realpath` and re-exports it before `exec`, so inside the session it is guaranteed
set, absolute, symlink-resolved, and naming the *same tree* the active frontend adapter
identifies. Detection is a poor substitute for making two values agree at their source.

**The variable is needed in-session** — not only by the launcher — because the agent
constructs paths to invoke `tools/*.py` and read `playbooks/*.md`. "It is already in
context" is not a reason to drop it; context gives the agent the content, not a root to
build paths from.

**What `lqcd-start-session` verifies, and what "correctly" can mean.** Not "matches an
expected path" — nothing knows what that is, which is the point. **Identity by content:**
`$LQCD_HANDBOOK` resolves to a directory containing `handbook.yaml`, canonical
`AGENTS.md`, its declared mirrors, and the active frontend skill; to distinguish *the*
handbook from a stray copy, its `git remote` matches the canonical upstream. Checkable
from inside, with no external knowledge, identically on every machine.

**The residual failure mode.** Launcher arguments, environment variables, and the loaded adapter can still identify different clones, or a marker can be reset mid-session. The frontend preflight validates the normalized root, declared entrypoint, adapter skill, and common markers together. Any disagreement is trap T2's sibling and takes the same response as [§freshness-model](#freshness-model): **report and stop, never guess.**

---

<a id="knowledge-atom"></a>
## 5. The knowledge-atom contract

Every Markdown knowledge file opens with frontmatter:

```yaml
---
title: Building QUDA on Perlmutter
summary: cmake options, module order, and the two errors that mean a stale module tree
scope: [machine:perlmutter, software:quda]   # REQUIRED. Levels in §scope-levels; a conjunction
                                             # means the fact holds only where all hold.
load_when: building or rebuilding QUDA on this machine
evidence: reproduced        # REQUIRED. Vocabulary in §evidence-vocabulary
observations: 3             # REQUIRED when evidence: reproduced
sources:                    # OPTIONAL; always a list
  - upstream QUDA documentation
observed: "2026-08-12"
observed_on:                # REQUIRED. Not documentation — this is the staleness
  machine: perlmutter       #   predicate, compared against the detected environment
  software:                   # branch context, not a bare SHA — see §version-lifetimes
    quda: {commit: <quda-commit>, branch: develop}
    milc: {commit: <milc-commit>, branch: develop}
  toolchain: {cuda: 12.2}
# review_by: "YYYY-MM-DD"   # ONLY for facts with no version anchor at all — see §staleness
---
```

`sources` is optional and always a list. Use public citations or descriptive source classes,
never paths to private material.

`title`, `summary` and `load_when` exist for `tools/build-index.py` ([§indexing](#indexing)). They are
specified from slice 0 even though the generator is not written until slice 2, so that no
file needs retrofitting when it arrives.

<a id="evidence-vocabulary"></a>
### 5.1. The evidence vocabulary

One field, seven values. It replaces the `verified | operator | inferred` scheme carried
over from the adjacent multigrid investigation.

| `evidence:` | Means | Extra |
|---|---|---|
| `source` | read from the code itself | cite file and line |
| `docs` | site or vendor documentation | cite the page |
| `observed` | seen **once** | — |
| `reproduced` | seen **more than once** | `observations:` required |
| `experiment` | controlled comparison, exactly one variable moved | name the variable |
| `operator` | operator-owned policy, default, or terminology | not empirical verification |
| `inferred` | conclusion reasoned from other facts | name the premises; keep it labeled |

**Why the split.** `verified` conflated "I read it in `gauge_field.cpp`" with "I saw it
happen once", and those carry completely different weight. That mattered because **two
rules already in this plan depend on the distinction and could not previously express it**:
[§validator-not-clearance](#validator-not-clearance)'s "a fix that worked once is an incident, not a build instruction", and [§scope-levels](#scope-levels)'s "an
incident is never promoted to a rule without a mechanism". With the vocabulary above, the
permissible uses are explicit:

- `observed` may become only an `incidents/` entry.
- `reproduced`, `experiment`, `source`, and `docs` may support reusable empirical
  claims.
- `operator` may establish operator-owned policy, defaults, or terminology, but it is
  not empirical verification.
- `inferred` may support a conclusion that names its premises and remains labeled as an
  inference.

The validator enforces the mechanically decidable part: legal evidence values and
placement of `observed` entries. It cannot determine whether prose is an empirical claim,
an operator policy, or an inference; developer review enforces that semantic distinction.

**Why there is no `confidence:` field.** The review that prompted this proposed one
(low/medium/high) alongside the kind. It is omitted deliberately: confidence is a judgement
that drifts between authors and sessions, no validator can check it, and it is *derivable* —
`source` and `reproduced observations: 5` already state the confidence. A separate field only creates
somewhere for the two to disagree.

**Why the three old tags were enough where they came from.** In the multigrid investigation
`[verified]` sat beside a 39 GB corpus, so it was cheap to audit — you could go and look.
The handbook deliberately has no such backing ([§no-escape-hatch](#no-escape-hatch)), so the tag itself must carry the
weight the corpus used to.

<a id="staleness"></a>
### 5.2. Staleness: a mismatch detector, not a calendar and not a validity claim

Two tempting mechanisms are both wrong, and the right one needs no new field.

**A calendar `review_by` on every file is a weak signal.** Validity correlates with events,
not with dates — a QUDA bug stays true until someone patches it, which could be next week or
never. And a few hundred files with rolling review dates produce a steady drip of "review
this" prompts that get waved through unread, which is the ritual failure [§freshness-model](#freshness-model) rejected when
it chose auto-pull over always-warn.

**A `valid_when` version predicate is worse: it invites an overclaim.** A field shaped
`cuda: {min: 12.0, max: 12.9}` asks the author to state a range they never tested. They
tested 12.2. That is exactly the claim [§version-lifetimes](#version-lifetimes) forbids — *tested on A and B* is defensible,
*valid from A through B* is not — and a field whose natural filling-in is a lie is a bad
trade.

**Use `observed_on`, which is already mandatory.** It is a factual record of the conditions
under which the fact was seen, and the session already detects the current environment
([§work-mode-currency](#work-mode-currency)). Comparing them turns documentation into a detector:

> "These notes were observed under CUDA 12.2; this system is on 12.4."

The check is honest **because it does not claim to know whether the fact still holds.** It
reports that the ground moved and leaves the judgement to the reader. No new field, no
invitation to overclaim.

**`review_by` survives for exactly one class: facts with no version anchor.** Queue limits,
site policy, allocation conventions, filesystem purge rules. Nothing in the environment
reveals that those changed — they rot on the site's schedule, invisibly, and a date is the
only signal available. So `review_by` is **required there and dropped everywhere else**,
which shrinks the set small enough that the prompts still mean something.

**Granularity: once per load, not once per fact.** When a session loads a machine's or a
software's documents and the environment differs from what they were observed under, it says
so once. A per-claim diff would cost more attention than it saves, and for software commits
it is ill-defined anyway — every checkout differs from every other. The meaningful version
of that comparison is [§version-lifetimes](#version-lifetimes)'s relationship to the nearest validated stack, which already exists
and is already reported at session start.

<a id="validator-checks"></a>
### 5.3. Validator contract

This section specifies the completed contract, not current bootstrap status. Implementation
is staged by `ROADMAP.md`: its acceptance evidence records which checks have landed, and
the validator final status line reports counts for what it actually checked. A check
specified here is not protection until its implementation and acceptance test land.

Every Markdown knowledge file carries the frontmatter contract above. Every YAML fact class
is either explicitly bound to a schema or named in `ROADMAP.md` as a temporary bootstrap
exception with a landing slice. The completed validator enforces:

1. schema conformance for every explicitly bound YAML fact file; a schema and its validator
   binding land together;
2. presence and legality of the provenance keys on every knowledge file, including a legal
   `evidence:` value and an `observations:` count wherever `evidence: reproduced`;
3. **the mechanically decidable part of the promotion rule in
   [§evidence-vocabulary](#evidence-vocabulary)** — `evidence: observed` is allowed only
   under an `incidents/` path. Semantic classification remains a developer-review
   obligation;
4. **`observed_on` present and complete** according to
   [§observed-on-completeness](#observed-on-completeness) — it is the staleness predicate ([§staleness](#staleness)), not
   documentation, so an absent one disables the mismatch check silently;
5. `review_by` present **iff** the fact has no version anchor, and not in the past
   (warn, don't fail — staleness is a signal, not an error);
6. the privacy deny-list ([§deny-list](#deny-list)) across every UTF-8-decodable
   working-tree file except explicitly local `session_*.log` files — reporting **what was
   checked, never "passed"** ([§validator-not-clearance](#validator-not-clearance));
7. **a restated *value* with no canonical pointer** — the P2 check. Restating a reference
   is fine; restating a number that could drift is not (advisory, heuristic);
8. **cross-reference integrity in the long documents** — every `](#slug)` and every bare
   `§slug` resolves to a declared `<a id="slug">`, and a link's visible text matches its
   target. See [§stable-anchors](#stable-anchors) for why this is a check and not a
   convention.

Run it in CI and from `lqcd-capture-learning` before anything is committed.

**Inline claims carry their evidence too**: a bare number with no kind and no citation is
not admissible. A bare device-memory number is not usable later; a value tagged
`[reproduced ×3]` with its measurement tool, machine, software commit, and date is.

<a id="role-not-index"></a>
### 5.4. Name a quantity by its role, never by a level index

A hierarchical solver numbers its levels, and the number is not stable across
configurations. In staggered multigrid the coarsest grid is level 3 in a four-level
hierarchy and level 2 in a three-level one, so a symbol like `V3` or `nu3` or `l3_res_max`
names **a different grid** depending on a fact the symbol does not carry. Every such symbol
is a latent defect: correct where it was written, silently wrong where it is read.

**The rule.** A quantity defined by its *position* in a hierarchy — coarsest, terminal,
fine, the level above the coarsest — is named by that position:
`coarsest_global_volume`, `coarsest_vector_density`, `coarsest_deflation_count`,
`coarsest_res_max`, `nvec_(L-1)`. A level index may not be appended to such a name, and a
numbered alias may not be introduced as a synonym for one.

**Two exceptions, both requiring the mapping inline.** A numbered symbol is admissible when
it is (a) a literal parameter-file key the reader must type, or (b) a literal token the
application prints. In both cases the level mapping appears in the same sentence, and the
role leads:

```text
the near-null count on the level above the coarsest, `nvec_(L-1)` — `nvec 2` in a
four-level MILC parameter file, `nvec 1` in a three-level one
```

Not `nvec_2 (4-level MG)`. The difference is that the first form is **self-describing**: a
line reached by grep, with no surrounding context, still resolves correctly. The second
requires the reader to already know the level count, which is frequently the very thing
being decided.

**Why a crosswalk table is not the mitigation.** A table is a lookup you must know to
perform. An agent that greps a symbol gets a line, not the table, which is the same reason
[§batch-scripts](#batch-scripts) exists: a correctly indexed pointer does not fire at the moment it
applies. The mapping therefore travels *in the sentence*, and the table remains explanatory
only.

**Why not separate documents per level count.** Splitting staggered-MG guidance into
three-level and four-level pages would duplicate the source contract — operator, transfer
rules, lifecycle, memory objects, runtime confirmation — none of which depends on level
count, and duplication is what drifts. The genuinely level-scoped content is the fitted
numerical bands, which already carry their fitted level count
([§ensemble-numbers](#ensemble-numbers) governs their admission). A future three-level band
set is a separate *calibration*, not a separate guide.

Enforced by `tests/test_role_not_index.py`, because a naming convention that nothing checks
is the class of rule this document already records as not firing.

<a id="reserved-terms"></a>
### 5.5. Reserved terms: configuration, setup, candidate

Two words carry an established meaning in lattice QCD that a general-software reading would
miss, and both were used in the other sense here before this rule existed.

**`configuration` means a gauge configuration.** Nothing else. A set of solver, build,
runtime, placement or decomposition choices is a **candidate**. Writing "this configuration
was 10% slower" in a field where a configuration is an element of the ensemble invites a
reader to think a different gauge field was used.

**`setup` means a solver's setup phase** — near-null generation, hierarchy construction,
eigenspace generation — because that is what `setup_tol`, `setup_maxiter` and the setup/solve
cost split already mean throughout `software/`. It is therefore not available as a word for
the thing being tuned. The mode documents originally said "candidate setup"; that term is
retired for this reason, and `candidate` alone carries it.

| Sense | Term | Not |
|---|---|---|
| element of a gauge ensemble | `configuration` | — |
| solver setup phase | `setup` | — |
| the parameter set under evaluation | `candidate` | `configuration`, `setup`, `candidate setup` |

A numbered symbol also has a reserved reading; see
[§role-not-index](#role-not-index).

Enforced by `tests/test_reserved_terms.py`, which allows `configuration` only where a gauge
configuration is meant. The check is a word-level heuristic and so is deliberately narrow: it
catches the phrasings that recur, not every possible misuse.

<a id="privacy-screening"></a>
## 6. Public-repo screening

This section applies only to the exact material proposed for the handbook: a new user-mode
inbox entry or a direct developer-mode change. The working project is the canonical home for
episode evidence and live campaign state, not an object to scan, redact, or rewrite under
these rules. Distill and screen the candidate at the repository boundary; preserve its source
workspace under that project's instructions.

<a id="deny-list"></a>
### 6.1. The deny-list (mechanical, enforced by `validate-knowledge.py`)

Never committed: allocation/project codes; usernames; any path containing a username
(`/global/homes/<u>/…`, `/lustre/orion/<proj>/…`); internal hostnames beyond the public
login-node names; email addresses; tokens, keys, ticket numbers; anything from a
non-public repository or an embargoed dataset; unpublished ensemble parameters; site
policy stated in confidence rather than published.

Paths in examples use documented placeholders (`$SCRATCH`, `$PROJWORK`, `<user>`).

<a id="no-escape-hatch"></a>
### 6.2. There is no escape hatch, and none is needed

Earlier drafts carried a `.gitignored` `local/`. It is removed. Three tiers already cover
everything, and they are the durable/episode distinction of [§admission-test](#admission-test) expressed as filesystem:

| Tier | Holds | Lifetime |
|---|---|---|
| **the handbook** | durable, transferable knowledge | travels with you to every system |
| **the working directory** | episodes, evidence, live campaign state, allocation codes, unpublished results | stays where the work happened |
| **the session** | the current environment | discovered at runtime, never stored |

The operator does not work *inside* the handbook. They work in a project directory that has
its own frontend instruction file, its own logs, and its own outputs — and **anything that fails the [§deny-list](#deny-list)
screening remains there instead.** The screening decision happens only when material is
proposed for the handbook; it does not turn the working directory itself into an intake
target. Material that never crosses that boundary was never handbook material.

Each candidate for the old `local/` dissolves on inspection:

| Proposed for `local/` | Where it actually belongs |
|---|---|
| Allocation / project codes | The working directory — a property of a campaign, not a machine |
| Site paths containing a username | **Nowhere.** `pwd`, `$SCRATCH`, `squeue -u $USER` — runtime state mistaken for a fact |
| A node-hour budget and its consumption | Granted in the opening message; the ledger lives in the working directory, scoped per campaign ([§budget-rule](#budget-rule)) |
| Unpublished ensemble parameters | The project doing that physics; it graduates to the handbook on publication |
| Evidence behind a mined claim | The corpus that produced it, which already exists and is already organised |

**The mistake this corrects** is reading "public repo" as "written for strangers." The
handbook is public in the sense of *shareable*; its actual readers are the operator's own
agent sessions, which run inside working directories where the evidence already sits.

**One mechanism replaces it.** A fact mined from private work names its source
descriptively, never by path — a path into a directory that exists on one machine is worse
than useless, and [§deny-list](#deny-list) forbids it:

```yaml
evidence: reproduced
observations: 12
sources:
  - operator's screened tuning records
```

Enough for the operator or their agent to know where to look; nothing for a stranger to
chase. This also repairs [§non-public-evidence](#non-public-evidence): a claim may rest on strong but unpublishable evidence
**without pretending a mechanism is a substitute for it.** A plausible mechanism is not
proof that an empirical claim is true, and the earlier rule implied otherwise.

<a id="validator-not-clearance"></a>
### 6.3. The validator is a safety net, never clearance

`validate-knowledge.py` catches what a regex can catch: `/global/homes/<user>`, tokens,
email addresses, allocation formats. It **cannot** detect that a paragraph contains an
unpublished scientific result, a site policy given in confidence, or a collaborator's
unshared work. Those are semantic, and no deny-list reaches them.

The risk is not the coverage gap itself — it is that **"the validator passed" reads like
clearance**, and an agent under auto-accept permissions will reasonably act on it. So the
tool's success message is more dangerous than its blind spots. Two rules follow.

**1. The validator never reports "passed."** It reports what it checked:

> `no deny-list matches · schema valid · provenance complete · publishability NOT checked`

Naming the thing it cannot check is what stops it from being mistaken for permission. This
is a wording change in a script and it is the cheapest safeguard in this document.

**2. Mined material defaults to staying out.** Under [§developer-obligations](#developer-obligations) item 3 extractions are already
quarantined, but the *disposition* was wrong: an unclassified fact
drifted toward admission, because the mining step exists to feed the handbook. Inverted —
**material from a prior corpus stays in its working directory unless someone affirmatively
classifies it as publishable.** Absence of a decision means "stays out." Under [§no-escape-hatch](#no-escape-hatch)'s
three-tier model this is nearly free: the working directory is where it already sits, so the
default is inaction.

**The inversion applies to mining, not to ordinary capture.** A fact learned while using the
handbook — "this cmake flag is required on Frontier" — needs no publication decision and
follows the normal `inbox/` proposal flow. Requiring a ceremony for routine capture would
stop capture happening, which costs more than the risk it guards against. The deny-list
applies to the exact handbook candidate in both flows, never to the working directory as a
whole.

**What this does not solve, stated plainly:** publishability is the operator's judgement,
not the agent's. An agent can flag "this looks like an unpublished result" but cannot know
what has been published. The control is therefore procedural rather than technical — the
inversion guarantees mined material *reaches the operator as a decision* instead of being
admitted by default.

**Quarantine cannot live inside the repo it is quarantining against.** An earlier draft
staged extractions in `inbox/mining/<source>/`. That is self-defeating: if the directory is
committed, staging *is* publishing, and the decision the quarantine exists to force has
already been made. Gitignoring it would work mechanically but reinstates the rejected
`local/` pattern ([§no-escape-hatch](#no-escape-hatch)) — local state hiding inside a public repo. So **`inbox/mining/` is
removed**; mining stages in the working directory beside the source corpus, which is where
rule 2 above already said the material stays by default, and candidates enter through
`inbox/proposals/` after their exact proposed content is screened at the repository boundary.

<a id="ensemble-numbers"></a>
### 6.3a. Ensemble-scoped numbers: decided per class, at the moment of import

`[operator]` The publishability of numbers tied to specific ensembles is decided
**case-by-case**: a session proposing to admit such numbers must flag them as *close to
unpublished results*, and confirm with the operator before continuing. Four constraints keep
that from decaying into a rubber stamp.

**1. Batch by class, never by item.** Slice 5 will produce candidate numbers by the
hundred. Two hundred prompts guarantee reflexive approval, and consent theatre is worse than
no gate because it manufactures a record of having asked. Group candidates into classes that
share a single decision — *solve timings on the 0.09 ensembles*, *spectrum characteristics
on named ensembles*, *dimensionless cost ratios* — and ask once per class.

**2. Most of it is not actually a judgement call.** The sharp filter: **is this a published
property of the ensemble, or a measurement we made?** Volume, β, quark masses, lattice
spacing and the papers introducing an ensemble are already public — free to use, no decision
needed. Timings, iteration counts, setup cost and spectrum measurements are *our* data.
Applying this first reduces case-by-case review to a small exception set rather than a
per-fact ceremony.

**3. Present the cost of "no", not just the request.** The decision content is not "may I
add this" but what the handbook loses without it — typically that a heuristic drops from
`reproduced` to `inferred` ([§evidence-vocabulary](#evidence-vocabulary)), because the numbers are what make the rule checkable.
State that, so the trade is visible in both directions.

**4. Record the class decision in the working directory, not in the handbook.** A note
reading *"timings on ensemble X are not publishable"* itself discloses that unpublished work
on X exists — so the record belongs with the staged extraction, not in the public repo. It
persists there for the next session, which is what stops the question being re-asked and
answered differently.

**And the default stays out because the asymmetry demands it.** Adding a number to a public
repo is irreversible — history, clones, mirrors, indexing — while holding one back costs a
later commit. The prompt should be phrased so that "no" is the cheap answer.

<a id="agent-privacy-rule"></a>
### 6.4. The rule an agent applies

Before any commit, the agent states, per added fact: (a) which deny-list category it was
checked against, (b) its `evidence:` kind and `observations:` ([§evidence-vocabulary](#evidence-vocabulary)), and (c) whether it generalises
beyond one lucky occasion. **A fix that worked once is an `incidents/` entry, not a build
instruction** — which is now the enforceable rule that `evidence: observed` cannot be
written as a rule, rather than an appeal to judgement. That distinction is the main defence
against the folklore accumulation called out in the requirements.

> **Flag for the operator:** mining an unpublished tuning corpus into a *public* repo
> publishes results from that campaign. That is the operator's call, not the agent's —
> taken **per class, at the moment of import** ([§ensemble-numbers](#ensemble-numbers)),
> not as one decision before slice 5. When the answer is "not yet", the fallback is not a
> private store: the facts stay in the working directory and the handbook goes without them
> until publication.

---

<a id="modes"></a>
## 7. Modes

<a id="work-modes"></a>
### 7.1. Work modes (five, from the requirements)

One is in force at a time, loaded from `modes/`; it may change during a session ([§work-mode-currency](#work-mode-currency)).
Each states: what the agent must ask for up front, what it may do unprompted, what it must
never do, which tools and playbooks apply, and what "done" looks like. Sketch of the
distinguishing content:

- **debugging** — needs the problem statement and where the code is; must ask whether it
  is analysis-only or hands-on (build/run/edit/recompile); `compute-sanitizer`,
  `valgrind4hpc`; **may submit jobs only under an explicit node-hour budget** ([§budget-rule](#budget-rule)).
- **performance** — Nsight Systems / RocProfiler Systems output; harvests PerfAdvisor.
- **benchmarking** — needs a frozen candidate and workload, the target quantity, the
  benchmark intent (fixed solver or component comparison, or workflow-cost estimation), a
  correctness reference, and the division of labour (prepare+submit+analyze, or
  analyze-only). Warm-up and setup are included, excluded, or separately amortized according
  to the production state being estimated; there is no universal first-solve discard rule.
  **Predict before running** ([§predict-compare-loop](#predict-compare-loop)), report uncertainty, and state which components become
  negligible at production scale. Changing a measured parameter ends the benchmark series
  and returns the decision to tuning.
- **tuning** — needs the hypothetical production campaign, machine, objective, constraints,
  and tunable parameter space. It adaptively searches node placement, decomposition, solver,
  build, runtime, and workflow choices and produces a candidate by following
  `playbooks/tune-solver.md` when applicable, with the relevant
  `software/<name>/solvers/`, resolved build profile and stack, ensemble knowledge, and
  memory model. **Predict before every allocation-consuming trial**
  ([§predict-compare-loop](#predict-compare-loop)). Tuning measurements are exploratory; the selected candidate requires a
  frozen confirmatory benchmark before it supports a benchmark or production-cost claim.
- **production** — parameters are already settled; the job is monitoring, submission
  automation, and failure triage. Lowest write-privilege mode. **Live campaign state is not
  handbook knowledge** — job IDs, which gauge configurations have completed, retry counts, missing
  outputs, walltime consumed. Those are working-directory contents by [§no-escape-hatch](#no-escape-hatch), and the handbook
  holds only how to *structure* that state, how to interpret it, and how to recover from
  failure. Otherwise the repo becomes a distributed job database as well as a knowledge base.

The mode follows the **immediate decision**, not the presence of a timer or profiler. Measuring
a candidate while deciding what to try next is tuning. Measuring a fixed candidate to estimate
its performance or cost is benchmarking. A campaign may pass through debugging, performance,
tuning, benchmarking, and production in sequence; exactly one governs each phase.

<a id="work-mode-currency"></a>
### 7.2. Work mode is *current*, not permanent — and mostly not asked about

**It may change mid-session.** Real work slides from debugging into performance analysis,
tuning, confirmatory benchmarking, and production without anyone starting a new session, and
a mode that could only be set once would either route wrongly after the task moved or force
pointless restarts.

**But it changes only by explicit declaration.** The agent states the mode it is operating
under and reloads that mode doc when it changes; it never drifts silently, because the
conventions differ in ways that would otherwise be applied to the wrong work. The agent may
identify a phase boundary and recommend the exact next mode, but it remains under the current
mode until the operator declares the transition.

**What the session asks for, it asks for only once, and only when it cannot know.**

| | How it is established |
|---|---|
| machine | **detected** — `tools/detect-machine.sh` |
| software + version | **detected** — `pwd`, `git remote -v`, `git rev-parse HEAD` |
| nearest validated stack | **derived** — current environment vs. `machines/<name>/stacks/` ([§stacks](#stacks)) |
| work mode | **asked** — not inferable, see below |
| handbook mode | **defaulted to user**; developer is declared, never inferred ([§handbook-modes](#handbook-modes)) |

`lqcd-start-session` reports what it detected and asks only about what is left. In practice
that is one question, not three. **Work mode is the one thing the filesystem cannot reveal**
— "run this benchmark" and "debug why this benchmark is wrong" are indistinguishable from
the environment and carry different conventions. Removing one mandatory exchange from every
session is a real saving across hundreds of sessions; asking the one question that carries
information is not.

<a id="handbook-modes"></a>
### 7.3. Handbook modes (two, orthogonal to the above)

One work mode **and** one handbook mode are in force at all times. The handbook mode
decides what the agent may *write*; the work mode decides what it is *doing*.

- **user mode** (default) — the handbook is read-only. The agent may write to `inbox/`
  and nowhere else in the repo, *even under auto-accept permissions*. Before creating an
  inbox entry it screens only that proposed file, never the working project around it. On
  finding an error or a better method it says so and offers to file a proposal; it does not
  edit existing handbook content.
- **developer mode** (explicitly declared) — the agent and operator are actively building
  the handbook. Full specification in [§developer-mode-spec](#developer-mode-spec), because this is the mode the project lives in
  for its first several months and the only one with write access to a public repo.

Declared in the opening exchange; canonical `AGENTS.md` states the default is user mode.
A wrong guess in user mode wastes a turn; a wrong guess in developer mode is a bad commit
to a public repository, so the default is never inferred from context.

<a id="developer-phases"></a>
### 7.4. Developer mode has two phases, not two modes

The rules are the same; what differs is how expensive restructuring is. Rather than make
the operator restate it every session, the repo declares its own posture in
`handbook.yaml` (`phase: bootstrap | maintenance`) and the agent reads it.

| | **bootstrap** | **maintenance** |
|---|---|---|
| Architecture | provisional; `ARCHITECTURE.md` is the authority | settled; deviations need a stated reason |
| Typical change | whole directories, mass import from source corpora | one fact, one correction, drain `inbox/` |
| Restructuring | cheap and encouraged | expensive; propose before doing |
| May edit this plan | yes, and must, when reality diverges | rarely, and it becomes a changelog |
| Dominant risk | **importing episode-tier or unscoped material** ([§admission-test](#admission-test)) | **silent staleness** |

**The flag flips once, after slice 5 is accepted** — not after slice 4. Slice 5 is the
mining slice and the largest single content import in the plan; declaring restructuring
expensive *before* it would be backwards. It is a one-line commit.

<a id="developer-mode-spec"></a>
### 7.5. Developer mode, specified

<a id="developer-obligations"></a>
#### 7.5a. Standing obligations

Before any handbook write, pass the freshness gate in
[§freshness-model](#freshness-model): require current HEAD and a clean tracked tree, with
qualifying new untracked inbox entries as the only standing exception. The gate concerns
drift the session did not author; a change already shown, approved, and applied earlier in
the same session does not re-trigger it. Without that scoping, obligation 1 below would be
unsatisfiable: it requires amending this document and then letting the tree follow within
one session, while obligation 3 leaves the amendment uncommitted until the operator acts.

Apply handbook privacy screening only to the exact inbox entry or direct repository diff
being proposed. It does not govern working-project files: preserve local paths, allocation
records, unpublished results, and other operational evidence there under the project's own
instructions.

1. **`ARCHITECTURE.md` is the authority; `ROADMAP.md` is the state.** Read both before
   acting ([§plan-ships-with-handbook](#plan-ships-with-handbook)). When reality diverges from the architecture, **amend `ARCHITECTURE.md`
   first, in the same session, with the reason** — then let the tree follow. A tree that
   has drifted from an unamended plan is the failure this document exists to prevent, and
   an undocumented deviation is indistinguishable from a mistake six months later.
2. **Operator approval precedes every change.** Before creating, modifying, deleting, or
   renaming any handbook file, present the exact proposed diff—or a numbered batch in which
   every edit is shown—and obtain explicit operator approval. Approval of a goal, slice, or
   general direction does not authorize unlisted edits. This includes privacy cleaning,
   formatting, refactoring, generated output, and mechanical rewrites. If implementation
   reveals an additional necessary change, stop and request approval for it.

3. **The operator owns commits.** After applying and verifying an approved change, stop
   with the resulting working-tree diff. Never create a commit unless the operator
   explicitly requests that specific commit. Permission to edit, approval of a proposed
   diff, or a request to complete a slice does not include permission to commit.

4. **Never mine and admit in the same step.** Extract a candidate → classify its tier
   ([§admission-test](#admission-test)) → justify it against the admission test → *then* write. This single ordering is
   the main defence against wholesale copying, which is the natural failure when the source
   is a well-written corpus.
5. **Raw extractions are quarantined outside the repo, and the default is to stay out.**
   Mining output stages **in the working directory beside the source corpus**, never in the
   handbook, and is promoted one fact at a time through `inbox/proposals/`. Nothing moves
   from a source corpus into `machines/`, `software/`, or `ensembles/` by copy,
   and **an unclassified candidate is not admitted** — absence of a publishability decision
   means it stays where it is ([§validator-not-clearance](#validator-not-clearance)).
6. **Run `tools/validate-knowledge.py` before every commit.** Schema, provenance,
   staleness, privacy deny-list. Developer mode is the only mode that can violate the
   privacy rule, so it carries the check.
7. **One fact-class per commit**, so a bad import is revertible without collateral.
8. **Re-read as a stranger at every slice boundary.** Open canonical `AGENTS.md` with no prior
   context: is the next action unambiguous, is anything stale, does every new file have an
   `INDEX.md` line? This check caught six defects in a prior investigation.
9. **Measure the tier budgets at every slice boundary** (P1). If Tier 0 grew, content
   leaked upward into the router; move it down before adding anything else.
10. **End-of-slice protocol**: update `INDEX.md`; update `ROADMAP.md` — slice status,
   acceptance results, and **the next action**; append to the decision log in
   `ARCHITECTURE.md` if a design choice was made or reopened; record what was rejected and
   why, not only what was admitted. The rejection list is what stops the next session from
   re-litigating the same import.

<a id="admission-test"></a>
#### 7.5b. The admission test

**Narrow scope is not a defect.** A fact that holds for exactly one ensemble on exactly
one machine is admissible and often the most valuable kind — it is what a session working
on that ensemble came for. What disqualifies a fact is not how few objects it covers but
whether those objects still exist.

A candidate must pass all four:

1. **Durability.** Is the fact about something that **will exist again** — an ensemble, a
   machine, a software version, a solver, a hardware generation — or about an **episode**
   that happened once? "this ensemble needs a larger coarsest grid than the current hierarchy delivers" is
   durable: that ensemble is still there and someone will run it again. "A past sweep ran
   a defective eigensolve" is an episode. Episodes are evidence,
   not knowledge — see [§scope-levels](#scope-levels).
2. **Scope, declared.** Every fact names the objects it holds for, in its `scope:`
   frontmatter: `all`, `software:quda@<commit-range>`, `machine:frontier`,
   `ensemble:<ensemble-id>`, or a conjunction. **An undeclared scope is an automatic
   rejection**, because an unscoped narrow fact is indistinguishable from a wrong
   universal one — and that is the actual mechanism by which folklore accumulates.
3. **Mechanism, or an explicit flag that there is none.** A fact with a reason behind it
   can be *extended* to a neighbouring case; one without can only be *repeated*. Both are
   admissible, but they are not the same object and must not read alike. A ratio with no
   story is labelled an empirical observation, never a rule.
4. **Actionability.** Does it change what an agent does, or only explain what happened?
   Explanation belongs to the source corpus; the handbook holds what alters a decision.

Carrying cost does **not** appear as a gate, because it is handled structurally: scope
determines placement, placement determines load tier, and an `ensemble:<id>` fact living
in that ensemble's record costs nothing to a session that never opens it. A narrow fact in a
broad file is a *filing* error, not an admission error — fix the filing.

<a id="scope-levels"></a>
#### 7.5c. Scope levels, and the one rejection tier

Classify before writing. Scope decides **where it lives and when it loads**; only the
bottom row decides admission.

| Scope | Holds for | Illustrative source example | Destination |
|---|---|---|---|
| **universal** | HISQ/LQCD work generally | "no performance claim is meaningful without a solve count"; "discard the first solve by default only in a homogeneous steady-state solver series"; "`mflops` is not comparable across solvers" | `conventions/` |
| **software × solver** | one software implementation of a solver | "QUDA multigrid setup cost must be amortized over a declared solve count" | `software/<name>/solvers/` |
| **software** | one code, a commit range | "option X is unstable on `<commit-a>`, clean on `<commit-b>`; no mechanism known" | `software/quda/` |
| **machine** | one system | queue limits, binding scripts, `MPICH_*` settings that cost a factor of 2.7 | `machines/<name>/` |
| **stack** | one validated machine × software × toolchain | "QUDA `<commit>` builds under `<toolchain-a>` with this profile and passes named tests" | `machines/<name>/stacks/` ([§stacks](#stacks)) |
| **ensemble** | one ensemble | "the heavy masses do not cross solver break-even in the target solve regime" | `ensembles/` |
| **ensemble × machine** | one pair | a settled parameter set with the node count it fits in | `ensembles/`, cross-referenced |
| **episode** | one past run or campaign | "a past sweep ran a defective eigensolve"; per-run citations; "several jobs exhausted memory" | **Not admitted as knowledge** — convert ([§scope-levels](#scope-levels)-i) or leave in the source corpus |

**[§scope-levels](#scope-levels)-i — converting an episode.** Episode material is not worthless; it is the evidence
that durable facts are made from. The conversion question is: *what would I want to know
if I hit this again?* Usually the answer is a durable fact one level up —

> episode: "one run died while allocating a level-2 coarse-link field"
> → **software × solver fact**: "level-2 coarse-link memory scales as
> `V_local(l2) × (2·nvec_1)²`, ×2 for `use_mma`, ×4 copies — check it before choosing a
> decomposition" → and, better still, `tools/check_decomposition.py` ([§prefer-a-tool](#prefer-a-tool)).

When an episode resists conversion — a one-off failure with no generalisable cause — it
becomes an `incidents/` entry under whichever object it attaches to (machine, software, or
ensemble), explicitly labelled as an unexplained occurrence. **An incident is never
promoted to a build instruction or a tuning rule without a mechanism.** That is the line
between institutional memory and folklore.

<a id="prefer-a-tool"></a>
#### 7.5d. Prefer a tool to a document

**This section is about authoring time.** It governs how a *fact* enters the handbook. The
working-practice counterpart — when a procedure a campaign performs repeatedly should become
a tool, and how that gets noticed mid-campaign rather than at orientation — is
`conventions/repeated-work.md`, reached from every work mode. The two are kept separate
because they answer different questions: this one asks what form knowledge should take, that
one asks what an operator should stop doing by hand. Widening this section to cover both
would conflate a carrying-cost argument with a defect-rate argument.

The most token-efficient form of a mined fact is executable. `memory_model.py` encodes a
large body of validated knowledge at effectively zero carrying cost — a session pays only
when it invokes it, and it pays nothing to *know it exists* beyond one `INDEX.md` line.
Where a finding can be expressed as a script plus a one-line pointer, it must be. A
formula written into prose is a formula every reader pays for and most readers do not use.

<a id="non-public-evidence"></a>
#### 7.5e. Citing evidence that is not public

The handbook **may not cite an unpublished source by path.** A relative path into a
directory that exists on one machine is worse than useless to any other reader — including
the operator's own agent on a different system — and [§deny-list](#deny-list) forbids it.

It does **not** follow that the claim must stand on mechanism alone. An earlier draft said
so and it was wrong: a plausible mechanism is not evidence that an empirical claim is true,
and a well-observed result with private supporting runs is more trustworthy than a
mechanism-only assertion. Requiring mechanism *instead of* evidence would have thrown away
the best-supported facts and kept the most confidently argued ones.

The fix is a descriptive source, not a path ([§no-escape-hatch](#no-escape-hatch)):

```yaml
evidence: reproduced
observations: 12
sources:
  - operator's screened tuning records
observed: "2026-08-12"
```

The operator and their agents work inside those working directories, so this resolves for
the people who need it and dangles for nobody. Where a public source exists — a paper, an
upstream issue, a merged PR, a public repo — cite it directly instead. Publishing the
underlying analysis upgrades a descriptive source to a citable one, and that decision is
the operator's ([§validator-not-clearance](#validator-not-clearance)).

**Mechanism remains admission test #3, on its own terms**: a fact with a mechanism can be
*extended* to a neighbouring case, one without can only be *repeated*. That is a statement
about how far a fact travels, not about whether it is true.

<a id="budget-rule"></a>
### 7.6. The job-submission budget rule

An agent may submit to a scheduler **only** when a node-hour or GPU-hour ceiling has been
stated explicitly by the operator. It tracks consumption against that ceiling and stops at
it. No ceiling stated ⇒ the agent prepares the job and hands the submit command to the
operator. This lives in `conventions/running.md` and is restated in canonical `AGENTS.md` because it
is the one rule with irreversible consequences.

**Granted in the opening message; scoped to the campaign; tracked in the working
directory.** `[operator]` Those three are separate, and conflating them is what makes
budgets leak:

- **The grant is a session act** — stated in the opening message. Zero machinery, and it is
  how the operator would naturally say it anyway.
- **The ceiling is per-campaign**, not per-session or per-job. Operationally the campaign
  *is* the working directory, which is also what makes the next part work.
- **Consumption is a ledger in the working directory**, so the ceiling does not silently
  reset each session. This is the failure that ruled out putting a bare number in a file: a
  200 node-hour ceiling re-read across six sessions authorises 1200 while looking like a
  limit. With a ledger the agent reports a *balance*, not a ceiling — "reserving 40; 112 of
  200 remain after this" — which is what makes the number real to the operator.

**The handbook ships the format and the rule; it never ships the numbers.** Same division
as predictions ([§records-in-working-directory](#records-in-working-directory)): budget state is working-directory state, like every other episode
fact.

**Debit at submit, reconcile at completion.** A job's true cost is known only when it ends,
but an agent can submit twenty jobs before any of them finish. So the ledger is debited at
**submit** time with the *reserved* worst case — nodes × requested walltime — and reconciled
**down** against `sacct` when the job completes. The two failure directions are deliberately
asymmetric: a session that ends before reconciling leaves the ledger over-counting, which is
safe. Never debit only on completion.

**Append-only.** Every entry is a row; the balance is a fold over rows. An agent that can
rewrite the ledger can erase its own mistakes, and the operator loses the audit trail that
is the point. Absent ledger ⇒ no budget tracked ⇒ the default above applies.

**Two limits, stated rather than engineered around.** Concurrent sessions in one working
directory can both read a balance and both submit — the same class as [§freshness-model](#freshness-model)'s concurrency
question, with the same answer: the operator is one person, so report it, do not build
locking. And **the ledger is accounting, not enforcement** — it makes overspend visible, not
impossible. Enforcement remains deferred ([§deferred-decisions](ROADMAP.md#deferred-decisions)); this does not un-park it.

<a id="account-rule"></a>
### 7.7. The chargeable account is never inferred

[§budget-rule](#budget-rule) governs *how much* may be spent. This governs *whose allocation
pays*, and it is the second rule in this document with irreversible consequences: a wrong
ceiling overspends the operator's own allocation, a wrong account spends someone else's.

`[operator]` Operators routinely hold several submission accounts. An agent that picks one —
because it was the scheduler default, the only row an accounting query returned, or the
string in a script it found nearby — has made an accounting decision it had no standing to
make, and the charge is not reversible.

**Declared, never derived.** Not from a scheduler or environment default, not from the first
row of an accounting query, not from another script in the working directory, and not from an
archived campaign script — historical scripts are exactly where a stale account survives
longest. Enumerating the accounts available to the operator and presenting them is expected
and useful; selecting one is not. **A single visible account is still not a declaration**: the
set an agent can see is not necessarily the set the operator may charge for this campaign.

**It is campaign state, so it lives beside the ledger** in the working directory
([§no-escape-hatch](#no-escape-hatch)) and never in the handbook, where allocation and project
codes are denied outright ([§deny-list](#deny-list)). That has a specific consequence for
tooling: a checker reports whether an account option is present and where, and **never echoes
the value it found**, because a lint that prints an allocation code into a log that is later
committed breaches the rule it was written to enforce.

<a id="batch-scripts"></a>
### 7.8. Batch submission scripts

A batch script is the one artifact an agent writes that later executes with the operator's
full credentials, outside whatever constrains the agent's own tool calls. That is true under
every frontend, so the guidance is frontend-agnostic; it is true under every scheduler, so it
reads [§scheduler-surface](#scheduler-surface) rather than naming directives.

**Placement: one universal Tier-2 leaf, reached from a Tier-0 pointer.** The requirement is
that it load *only* before batch-script work and *every* time, and those pull opposite ways —
Tier 0 guarantees "every time" and cannot afford the content (P1), while a Tier-2 leaf affords
the content and needs a trigger. The resolution is the one `conventions/filesystem-discovery.md`
already uses: the leaf holds the rules, and a single Tier-0 standing-rule line names the
trigger and points at it. Its `load_when` covers writing, modifying, and reviewing a script
*and* preparing a submit command, so the no-ceiling handoff of [§budget-rule](#budget-rule) is
covered rather than exempt.

**Amended 2026-08-29: a Tier-0 pointer alone does not achieve "every time".** In a tuning
session on Perlmutter an agent wrote three launchers and submitted three jobs without opening
the leaf. Nothing was missing: the Tier-0 line was in context for the whole session and
`conventions/INDEX.md` indexed the leaf with a matching `load_when`. The failure is that the
routing an agent *executes* at task time is not the routing it *loaded* at session start. The
task-time surfaces — `modes/*.md` "Tools and routing", the playbooks' task-triggered routing
tables, and the working project's own submission checklist — each named some conventions and
not this one, and a list that names two conventions reads as complete.

The revised decision keeps the Tier-0 pointer and adds the trigger to every task-time surface
that can reach batch-script work. The Tier-0 line still guarantees the rule is *present*; the
task-time surfaces are what make it *fire*. This does not weaken P1: the leaf still holds the
content and Tier 0 still holds only the pointer.

**The invariant is positive; the prohibited list is illustrative.** A batch script is
**append-only with respect to inputs and shared data** — read what exists, create what does
not. Run-owned mutable state is the deliberate exception: a tunecache, checkpoint, or restart
file inside the run root is rewritten by design, and a blanket "never modify anything that
exists" would forbid the warm-state contract tuning mode requires. Any enumeration of
destructive commands stays explicitly non-exhaustive, because an agent reading a long specific
list infers that absence means permission; the case that decides the commands nobody
enumerated is *name the approved writable root this write lands under, or do not write it*.

**Checkable rules become a tool.** [§prefer-a-tool](#prefer-a-tool) applies directly. Whether
`set -euo pipefail` is present, whether the script submits another job, whether the working
directory and output targets are pinned rather than inherited, and whether a referenced
variable is one the profile declares are all decidable — and several are decidable only
against `machine.yaml`. Whether a writable root is genuinely approved, whether an invoked
program is safe, and intent are not, and the leaf says so rather than implying coverage.

**`tools/check-batch-script.py` is advisory lint, never a sandbox.** It cannot stop a script
being written unchecked; only interception can, which is Slice 7's `PreToolUse` guard and the
same conclusion [§deferred-decisions](ROADMAP.md#deferred-decisions) already reached about
enforcing the budget. It is calibrated against scripts already trusted in the working project,
because a lint that fires on known-good input trains the operator to ignore it —
[§tolerances](#tolerances) applied to a checker.

---

<a id="predict-compare-loop"></a>
## 8. The predict → compare → capture loop

The requirements ask for this twice (benchmarking and tuning). It is one of the two rot
detectors of P5, and it is mandatory in both of those work modes.

<a id="records-in-working-directory"></a>
### 8.1. The records live in the working directory, not the handbook

> **The handbook holds calibrated models and durable conclusions. The working directory
> holds the observations that calibrated them.**

This is the same durable-vs-episode cut as [§no-escape-hatch](#no-escape-hatch) and [§admission-test](#admission-test), applied a third time. A
prediction record is an observation about one run on one day — it is evidence, not
knowledge. Keeping the ledger in the handbook would have three costs and no benefit: it
publishes performance results from possibly unpublished work into a public repo; it grows
the repo with thousands of records that almost no session opens; and it puts high-churn
files in a repo cloned across many machines.

Nothing is lost by moving it out. The accumulated records *are* calibration data, and they
remain exactly where an agent working on that project can reach them. When they justify a
model change, the change enters the handbook citing them as
`evidence: reproduced, observations: 12` ([§evidence-vocabulary](#evidence-vocabulary)).

<a id="the-loop"></a>
### 8.2. The loop

1. **Before** a benchmarking or tuning run, the agent writes a prediction record **into the
   working directory**: wall time, device memory per rank, host memory, iteration counts —
   each naming the handbook file and rule it came from.
2. **After** the run, `lqcd-capture-learning` records the measured values beside the
   predictions.
3. **On a miss beyond the metric's tolerance** ([§tolerances](#tolerances)), the agent diagnoses *why* — stale
   fact, missing fact, wrong model, or a genuine machine change — and files an `inbox/`
   proposal naming the handbook file and line that was wrong. It does not edit the handbook
   in user mode.
4. Durable output — a corrected constant, a widened tolerance, a note that a model does not
   hold on this hardware — is proposed for the handbook. Everything else stays put.

**Tuning observations are exploratory evidence.** The next candidate may depend on the
previous result, so the selected winner is exposed to selection noise and to unequal run
conditions. After selection, benchmark the frozen candidate independently with the declared
production state, repetitions, correctness checks, and uncertainty treatment. A reserved
confirmation set whose candidate and protocol were fixed before its results were observed may
satisfy this requirement; an exploratory winning run may not be relabeled after the fact.

**A measured-series parameter change is a mode boundary.** Once a solver, decomposition,
node count, build option, runtime parameter, workload definition, or warm-state contract is
changed adaptively, the current evidence belongs to tuning. A new benchmarking series begins
only after the candidate and measurement contract are frozen and the operator explicitly
declares benchmarking mode.

**Not every prediction record earns a handbook change.** Step 4 is a judgement about value
and durability, made against [§admission-test](#admission-test), not an automatic promotion.

<a id="tolerances"></a>
### 8.3. Tolerances are per metric, and one of them is absolute

A single 10 % threshold across all quantities is too blunt in both directions. These
quantities do not have comparable variability:

| Metric | Tolerance | Why |
|---|---|---|
| device memory | **absolute** (e.g. ±0.5 GiB) | deterministic; a 10 % miss means the model is wrong, and a relative tolerance misbehaves as the value approaches zero |
| iteration counts | tight relative | near-deterministic for a fixed problem |
| solver wall time | wide relative, or an interval | fabric congestion alone produced **60 % RSD** across nominal repeats in the adjacent multigrid corpus, against 2.1 % when the network was quiet |
| total job wall time | widest | includes queue, startup, I/O |

```yaml
predicted:
  solver_time:       {value: 12.4, interval: [11.5, 13.5]}
  device_memory_gib: {value: 32.0, tolerance_gib: 0.5} # illustrative
```

The 10 % figure in the requirements is a good default for *model* quantities and a bad one
for anything the network touches. **A tolerance that is exceeded on ordinary noise trains
the operator to ignore the alarm**, which costs more than having no alarm.

---
