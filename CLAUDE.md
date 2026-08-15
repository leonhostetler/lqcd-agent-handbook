# LQCD Agent Handbook

This public repository is a routing layer for durable, transferable LQCD knowledge.
Keep live campaign state, unpublished results, credentials, allocation data, and local
paths in the working directory where the work occurs.

## Start every session

Invoke `/lqcd-start-session` before doing project work. It must verify that the launcher
was used, validate handbook identity and freshness, detect the machine and software state,
report the nearest validated stack when one exists, and ask only for the current work mode.
Do not infer a node type from a login host.

Exactly one work mode is current: debugging, performance, benchmarking, tuning, or
production. It changes only when the operator explicitly declares a change.

Exactly one handbook mode is current:

- **User mode is the default.** Treat the handbook as read-only. You may create a uniquely
  named file under `inbox/proposals/` or `inbox/rejections/`; do not edit existing files.
- **Developer mode must be explicit.** Before editing, read `ARCHITECTURE.md`, `ROADMAP.md`,
  `handbook.yaml`, and `modes/developer.md`, then require a clean, current tree.

## Standing safeguards

- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour
  ceiling. Without one, prepare the job and hand the submit command to the operator.
- Never commit allocation codes, usernames, user-specific paths, internal hostnames,
  email addresses, secrets, private-repository material, embargoed data, unpublished
  ensemble results, job IDs, or live campaign state. See `PRIVACY.md`.
- Mined material stays outside this repository until its fact class is affirmatively
  judged publishable. Validation is not publication clearance.
- A fact needs declared scope, evidence, observation context, durability, mechanism or an
  explicit empirical label, and an actionable consequence. Episodes remain with their
  source evidence; a one-off may become an incident, never a rule.
- Do not read `session_*.log`. These are operator-facing provenance backups.
- Prefer a tool over prose when a durable rule can be executed.

Use `INDEX.md` only to route to the smallest relevant document. Developer-only planning
must not be opened in user mode.
