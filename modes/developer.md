# Developer Mode

Developer mode is explicit; never infer it from a request or from an editable checkout.
Read `ARCHITECTURE.md`, `ROADMAP.md`, and `handbook.yaml` before changing the handbook.
`ARCHITECTURE.md` is the design authority, while `ROADMAP.md` alone owns mutable state
and the next action. `DEVLOG.md` holds the episode record and is **not** read at session
start; open it by name only when you need the evidence behind a decision.

## Before editing

1. Require current HEAD and a clean tracked Git tree. New untracked files may remain under
   `inbox/proposals/` or `inbox/rejections/` only when they qualify as pending intake under
   `ARCHITECTURE.md` §4.3. Committed entries in those directories are pending intake as
   well and need no exception, because they leave the tree clean. List both directories
   rather than relying on `git status`, report every entry in either state, and compare each
   `base_handbook_commit` with current HEAD. Stop on every other dirty or divergent state.
   This gate concerns drift the session did not author: changes already shown, approved, and
   applied in the current session do not re-trigger it.
2. Apply `PRIVACY.md` only to the exact inbox entry or direct handbook diff being proposed.
   Do not scan, redact, or rewrite the working project under handbook privacy rules; preserve
   its operational evidence under its own instructions.
3. Apply the operator-approval gate in `ARCHITECTURE.md` §7.5a. Show the exact proposed
   diff and obtain explicit approval before any handbook write.
4. Treat commits **and the index** as operator-owned. After applying and verifying an
   approved change, stop with the working-tree diff, unstaged. Never stage and never commit
   unless the operator explicitly requests that specific action. Staging is not a harmless
   preparatory step: it leaves `git diff` empty, so the operator's review reports an
   unchanged tree.
5. Check the current `phase` in `handbook.yaml`. Restructuring is expected during
   `bootstrap`; during `maintenance`, propose architectural changes first.
6. For mined material, extract outside this repository. Classify scope, durability,
   mechanism, actionability, evidence, and publishability before admitting a fact.
7. Treat material from prior corpora as non-publishable until the operator affirmatively
   clears its fact class. Never import an episode merely because it is well documented.

## While editing

- Amend `ARCHITECTURE.md` first when implementation reality contradicts the design, and
  record the reason with the affected decision.
- Keep knowledge atomic and scoped. Prefer executable tools to repeated formulas.
- Use one canonical home per value; other documents should point to it.
- Keep each commit to one fact class so a faulty import can be reverted cleanly.
- Record an episode in `DEVLOG.md`, never in `ARCHITECTURE.md` or `ROADMAP.md`. When a
  decision changes, rewrite the rule in place rather than appending a dated amendment.
- **An edit made against an incident must reconcile with what the leaf already says.** Before
  writing, list every existing statement in that leaf — and in any other leaf the domain index
  routes to for the same task — about the object the incident concerns: the variable, option,
  directive, file, or step. In the `DEVLOG.md` entry, name each one and say whether it was
  confirmed, amended, or deleted. "No other statement" is a claim to be checked, never a
  default. Two entries that were each right about their own incident once left a recipe and a
  rule in one leaf that contradicted each other — one resolved a job directory from the
  submission-directory variable, the other required a directive that makes that variable never
  the job directory — and a launcher that followed the recipe died after a two-day queue wait.
  Neither entry had mentioned the other.
- Do not read `session_*.log` unless the operator explicitly requests it.
  Authorized review still follows mined-material classification, privacy, and publishability gates.
- Run `tools/run-change-proposal` before every commit. It performs the whole sequence a
  proposal owes — diff, index regeneration, validator, test suite, and a scoped privacy
  surface — and reports what each step examined rather than only what it concluded. Two of
  those steps fail silently when skipped: a stale index is well-formed and plausible, and a
  privacy sweep that never ran is indistinguishable from one that found nothing. Run
  `tools/run-validator` on its own only when the narrower check is what is wanted; the
  harness runs it either way. Neither is publication clearance: the harness ends by naming
  the `PRIVACY.md` categories no pattern can decide and leaving them to you.

## Slice boundary

Re-read canonical `AGENTS.md` and `INDEX.md` cold. Confirm routing is unambiguous, measure the
Tier-0 byte budget, update slice status and acceptance evidence in `ROADMAP.md`, and set
exactly one next action there. Update the architecture decision log only when a decision
was added, changed, or deliberately reopened. Record rejected imports as well as accepted
ones.
