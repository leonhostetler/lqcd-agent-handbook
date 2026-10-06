# LQCD Agent Handbook

A portable, public knowledge base for agent-assisted lattice-QCD work across HPC systems.
The handbook separates machine capabilities, software knowledge, validated stacks, solver
knowledge, and task playbooks so a session loads only the context it needs. HISQ is the
default fermion convention unless the operator says otherwise.

## What the handbook is for

### Motivation

Lattice-QCD work on HPC systems depends on a large body of practical knowledge that is
rarely written down in one place: which modules and build options work on a given machine,
how QUDA and MILC fit together, what a solver parameter actually controls, which scheduler
behaviour quietly breaks a batch script, and how to read an application's output without
misleading yourself. AI coding agents can do much of this work, but every session starts
cold. Without a shared memory, an agent rediscovers the same facts, repeats the same
mistakes, and presents guesses with the same confidence as verified results.

The handbook is that shared memory. It records knowledge that carries over between
campaigns and machines, together with the evidence behind it, so a session on any supported
system starts from what has already been learned. It is written for agents first, but it is
plain Markdown, YAML and scripts that a person can read, check and correct.

### How it works

- **Loaded in tiers.** Reading the whole handbook every session would cost more than it
  saves. A small entrypoint (`AGENTS.md`, mirrored as `CLAUDE.md`) holds only standing rules
  and a routing table and is always loaded. At session start the agent adds the documents
  for the detected machine, the software in front of it, the nearest validated build and
  the current work mode. Everything else is loaded on demand through generated per-domain
  indices.
- **Organised by subject.** `machines/` holds site capabilities, node types and validated
  software stacks; `software/` holds QUDA, MILC and their dependencies, including solver
  knowledge and application guides; `ensembles/` holds the gauge-ensemble catalog;
  `conventions/` holds rules that apply everywhere; `modes/` says how to work in each work
  mode; and `playbooks/` holds step-by-step procedures. Procedures read machine and
  software profiles rather than hard-coding them, so adding a machine does not mean
  rewriting procedures.
- **Every fact carries provenance.** Each knowledge file declares its scope, the kind of
  evidence behind it (source code, documentation, a single observation, a reproduced one, a
  controlled experiment, operator policy, or inference) and the machine and software
  versions it was observed on. A one-off observation is filed as an incident, never as a
  rule. When the current environment differs from what a fact was observed on, the session
  says so.
- **Stacks are records, not recommendations.** A stack is a combination of machine,
  software, toolchain and build profile that was actually built and run. Nothing is listed
  because it ought to work.
- **Tools over prose.** Where a rule or model can be executed, such as a memory or
  decomposition estimate, a batch-script check, or a profile extraction, it ships as a
  script in `tools/` rather than as a formula to be re-derived by hand.
- **Safeguards for irreversible actions.** An agent does not submit jobs without an
  explicit campaign-scoped node-hour or GPU-hour ceiling, and never chooses the charge
  account itself. With the optional submission guard installed, an agent's submit command is
  refused unless the batch script has passed the checker and a dry run.
- **Campaign state stays out.** The handbook is public. Job IDs, allocation codes, budgets,
  unpublished results and local paths stay in the project directory where the work happens.
  Only durable, transferable, publishable knowledge enters the handbook; see `PRIVACY.md`.

### How it is used

1. Clone the handbook on each machine you work on and set `LQCD_HANDBOOK` to the clone
   (see "Starting a session" below).
2. Start your agent from your own project directory through the launcher. The handbook adds
   to the project's own instructions without replacing them, and the project stays the
   working directory.
3. The session orients itself. It checks that the handbook loaded completely and is current
   with upstream, fast-forwarding it when that is safe; detects the machine and software;
   reports the nearest validated stack; and asks one question: the current work mode
   (debugging, engineering, performance, benchmarking, tuning or production). The mode
   changes only when you declare a new one.
4. As the task develops, the agent loads the specific machine, software, solver and
   convention documents it needs.
5. Sessions run in **user mode** by default, in which the handbook is read-only. When the
   agent learns something worth keeping, or finds an entry that is wrong, it files a new
   proposal under `inbox/` instead of editing. **Developer mode**, which must be declared
   explicitly, is for maintaining the handbook: proposals are reviewed against an admission
   test, every edit is shown and approved before it is made, and commits stay with the
   operator. See `CONTRIBUTING.md`.

## Starting a session

Clone the repository, set `LQCD_HANDBOOK` to the clone, and launch through:

```bash
export LQCD_HANDBOOK=/path/to/lqcd-agent-handbook
"$LQCD_HANDBOOK/tools/lqcd-claude"
# or
"$LQCD_HANDBOOK/tools/lqcd-codex"
```

Both launchers intentionally have no default path. They preserve the working project's
own instructions while loading the same handbook Tier 0 and startup workflow. When called
without arguments, both supply the same neutral initial prompt so orientation begins
immediately; caller-supplied arguments pass through unchanged. The Codex launcher works
without installation and points to the handbook without requesting another writable root,
so it does not conflict with a read-only profile by requesting write access.
`tools/install-codex-skills` may optionally expose the startup skill in Codex's user skill
directory.

The optional Codex link is intended for sessions in other repositories. Inside this
handbook repository, Codex may show both the repository skill and the same user-scoped
skill because same-named skills are not merged. The link records the clone's absolute path;
if the clone moves, remove the obsolete link and rerun the installer.
