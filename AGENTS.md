# LQCD Agent Handbook

This public repository is a routing layer for durable, transferable LQCD knowledge.
Keep live campaign state, unpublished results, credentials, allocation data, and local
paths in the working directory where the work occurs.
Handbook privacy screening applies only to the exact material proposed for this repository:
a user-mode inbox entry or a direct developer-mode change. It does not govern files in the
working project; preserve project-local evidence under that project's instructions.

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
  Screen only that proposed entry under `PRIVACY.md`, never the working project around it.
- **Developer mode must be explicit.** Before editing, read `ARCHITECTURE.md`, `ROADMAP.md`,
  `handbook.yaml`, and `modes/developer.md`, then require a clean, current tree.

## Standing safeguards

- Never recursively traverse `/`, a filesystem or mount root, a shared top-level directory,
  a system prefix, or another unbounded directory. Before searching, choose a bounded root
  inside the current workspace or a known project or data directory; constrain depth and
  filename patterns where possible, and stop to ask when no bounded root is known. This
  applies on login and compute nodes to every tool or language. Locate software through
  shell, module, package, or known-prefix metadata rather than a mounted-filesystem scan.
  Never bypass an installed traversal guard by changing tools, moving to a compute node, or
  requesting approval for an equivalent broad scan. See `conventions/filesystem-discovery.md`.
- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour
  ceiling. Without one, prepare the job and hand the submit command to the operator.
  Never infer the chargeable account. Before writing, modifying, or reviewing a batch
  script, or preparing a submit command, read `conventions/batch-scripts.md`.
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
- Prefer a tool over prose when a durable rule can be executed. At each study or phase
  closure and each work-mode change, apply that to the work itself: see
  `conventions/repeated-work.md`.
- When modifying software, load `software/<name>/development.md` when present and
  complete its required formatting and post-edit checks before handoff.

## Route each task

Orientation loads Tier 1, not all task-specific knowledge. Before substantive
LQCD analysis or action, and whenever the task narrows or changes, derive named
applications, solvers, ensembles, and the immediate decision from the operator
request and active project instructions. Use `INDEX.md` and only the matching
domain indices to load the smallest Tier-2 leaves whose `load_when` matches.

Interpret solver mechanisms, parameters, failures, campaign evidence, or next
candidates only after this check. Report when no matching leaf exists.
Developer-only planning must not be opened in user mode.
