# Contributing

The handbook currently assumes one operator and direct commits to `main` in explicit
developer mode. Additional contributors are a documented trigger to revisit that policy.

## User-mode proposals

User mode may create, but never edit, one uniquely named YAML file under `inbox/proposals/`
or `inbox/rejections/`:

```text
<ISO8601>-<machine>-<uuid>.yaml
```

Include `created`, `machine`, `base_handbook_commit`, proposed scope, evidence, observation
context, and why the fact changes an action. Do not put mined raw evidence in the inbox.
Every inbox file is public repository content. Screen the exact proposed file according to
`PRIVACY.md` before creation; do not apply that screen to the working project from which the
candidate was distilled. A conforming new file may remain untracked between sessions;
startup reports it as pending intake.

## Developer flow

1. Require current HEAD and a clean tracked tree, then read `ARCHITECTURE.md` plus
   `ROADMAP.md`. Qualifying new untracked inbox entries are the sole exception: report
   them as pending intake and compare each `base_handbook_commit` with current HEAD.
2. Apply `PRIVACY.md` to the exact inbox entry or direct handbook diff, never to the working
   project that holds its source evidence.
3. Follow the operator-approval gate in `ARCHITECTURE.md` §7.5a. Do not write until the
   exact proposed diff has been approved.
4. Leave approved changes uncommitted for the operator. An agent may commit only when the
   operator explicitly requests that specific commit.
5. Classify durability, scope, mechanism, actionability, evidence, and publishability.
6. Keep each knowledge file atomic and each commit limited to one fact class.
7. Run `python3 tools/build-index.py`, review the generated changes, then run
   `python3 tools/validate-knowledge.py`.
8. At a slice boundary, record acceptance evidence and exactly one next action in
   `ROADMAP.md`; update the architecture decision log only when a decision changed.

Automated validation reports what it checked. The operator remains responsible for
publication clearance.
