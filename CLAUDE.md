# LQCD Agent Handbook

This public repository is a routing layer for durable, transferable LQCD knowledge.
Keep live campaign state, unpublished results, credentials, allocation data, and local
paths in the working directory where the work occurs.

## Start every session

Run the `lqcd-start-session` workflow before doing project work. The active frontend
adapter must verify complete loading, validate handbook identity and freshness, detect the
machine and software state, report the nearest validated stack when one exists, and ask
only for the current work mode.
Do not infer a node type from a login host. If the matched machine profile has exactly one
`node_types` entry, use that sole type as the default; otherwise require explicit operator
declaration.

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
- Authorization to change project code does not authorize commits or publication. Unless
  the operator explicitly requests the specific action, do not commit, push, or open or
  update a pull or merge request. After implementing and validating changes, leave the
  working tree uncommitted, summarize the validation, and suggest a commit message.
- Never commit allocation codes, usernames, user-specific paths, internal hostnames,
  email addresses, secrets, private-repository material, embargoed data, unpublished
  ensemble results, job IDs, or live campaign state. See `PRIVACY.md`.
- Mined material stays outside this repository until its fact class is affirmatively
  judged publishable. Validation is not publication clearance.
- A fact needs declared scope, evidence, observation context, durability, mechanism or an
  explicit empirical label, and an actionable consequence. Episodes remain with their
  source evidence; a one-off may become an incident, never a rule.
- Do not read `session_*.log` unless the operator explicitly requests it. Even then,
  treat the transcript as private evidence, not canonical knowledge.
- Prefer a tool over prose when a durable rule can be executed.
- When modifying software, load `software/<name>/development.md` when present and
  complete its required formatting and post-edit checks before handoff.

Use `INDEX.md` only to route to the smallest relevant document. Developer-only planning
must not be opened in user mode.
