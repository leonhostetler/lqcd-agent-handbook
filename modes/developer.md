# Developer Mode

Developer mode is explicit; never infer it from a request or from an editable checkout.
Read `ARCHITECTURE.md`, `ROADMAP.md`, and `handbook.yaml` before changing the handbook.
`ARCHITECTURE.md` is the design authority, while `ROADMAP.md` alone owns mutable state
and the next action.

## Before editing

1. Require current HEAD and a clean tracked Git tree. New untracked files may remain under
   `inbox/proposals/` or `inbox/rejections/` only when they qualify as pending intake under
   `ARCHITECTURE.md` §4.3. Report them and compare each `base_handbook_commit` with current
   HEAD. Stop on every other dirty or divergent state.
2. Apply the operator-approval gate in `ARCHITECTURE.md` §7.5a. Show the exact proposed
   diff and obtain explicit approval before any handbook write.
3. Treat commits as operator-owned. After applying and verifying an approved change, stop
   with the working-tree diff. Never commit unless the operator explicitly requests that
   specific commit.
4. Check the current `phase` in `handbook.yaml`. Restructuring is expected during
   `bootstrap`; during `maintenance`, propose architectural changes first.
5. For mined material, extract outside this repository. Classify scope, durability,
   mechanism, actionability, evidence, and publishability before admitting a fact.
6. Treat material from prior corpora as non-publishable until the operator affirmatively
   clears its fact class. Never import an episode merely because it is well documented.

## While editing

- Amend `ARCHITECTURE.md` first when implementation reality contradicts the design, and
  record the reason with the affected decision.
- Keep knowledge atomic and scoped. Prefer executable tools to repeated formulas.
- Use one canonical home per value; other documents should point to it.
- Keep each commit to one fact class so a faulty import can be reverted cleanly.
- Never read `session_*.log`; those transcripts are operator-only provenance backups.
- Run `python3 tools/validate-knowledge.py` before every commit. Its privacy scan is a
  safety net, not publication clearance.

## Slice boundary

Re-read `CLAUDE.md` and `INDEX.md` cold. Confirm routing is unambiguous, measure the
Tier-0 byte budget, update slice status and acceptance evidence in `ROADMAP.md`, and set
exactly one next action there. Update the architecture decision log only when a decision
was added, changed, or deliberately reopened. Record rejected imports as well as accepted
ones.
