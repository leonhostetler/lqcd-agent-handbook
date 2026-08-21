# Start Session Playbook

Use this playbook before any project action. Report each stage concisely and stop on a hard
gate rather than guessing.

## 1. Verify the frontend preflight

Require `LQCD_HANDBOOK_FRONTEND` to identify a supported adapter, then follow its preflight:

- `claude`: `playbooks/start-session-claude.md`
- `codex`: `playbooks/start-session-codex.md`

A missing or unknown frontend marker means handbook loading is unverified. Report partial
loading and stop. Never repair it by assuming that another frontend's loading rules apply.

## 2. Validate identity and freshness

Resolve `LQCD_HANDBOOK` with `realpath`. Confirm `handbook.yaml` names
`lqcd-agent-handbook`, canonical `AGENTS.md` exists, and the active frontend's entrypoint
and skill named in `launcher.frontends` exist. Confirm every declared entrypoint mirror is
byte-for-byte equal to `AGENTS.md`.

If `repository.canonical_remote` is set, require `origin` to match it exactly. During
bootstrap, when it is unset, report that exact remote identity cannot yet be checked; if
`origin` exists, its repository basename must still be `lqcd-agent-handbook`.

Inspect `git status --porcelain=v1 --untracked-files=all`. Classify a path as pending
intake only when Git reports `??`, the path is directly under `inbox/proposals/` or
`inbox/rejections/`, and its name follows `<ISO8601>-<machine>-<uuid>.yaml`. This status
classification is structural: it does not inspect or clear the file's contents. Report
every pending path. Any other status entry is a hard gate.

Fetch the configured upstream when available. If local HEAD matches upstream, continue.
If upstream is a fast-forward and the tree is clean or contains only pending intake, pull
with `git pull --ff-only`. On an incoming-path collision, other dirtiness, an ahead branch,
a missing upstream, or divergence, report the state and stop before using potentially
stale knowledge. Developer mode additionally requires a clean tracked tree; pending intake
is the sole exception.

## 3. Check user-wide session logging

Run `"$LQCD_HANDBOOK/tools/run-session-logging-python"
"$LQCD_HANDBOOK/tools/check-session-logging.py" --frontend
"$LQCD_HANDBOOK_FRONTEND"` after freshness is established. The runner selects a compatible
versioned interpreter without changing the module environment. This is a diagnostic, not a
hard gate. Do not install or repair user-level hooks automatically.

Record the reported state for the final orientation summary. When it is `missing`,
`stale`, or `broken`, include one non-blocking offer: "Session logging is <state>. Say
\"enable session logging\" to install or repair it for this user account." Do not ask a
second mandatory startup question. On explicit acceptance, follow
`playbooks/session-logging.md`.

## 4. Detect machine and software

Report rather than ask. Run the handbook detector exactly once:

```bash
"$LQCD_HANDBOOK/tools/detect-machine.sh"
```

Record its exact output as the detected machine. The detector owns machine-profile
selection; do not identify the machine by listing or reading profiles. If it reports
`unknown`, report that result and do not open `machines/INDEX.md`, any
`machines/*/machine.yaml`, or any stack record. The node type is then undeclared and there
is no matching validated stack.

Detect working-directory software and version from `git remote -v`, `git rev-parse HEAD`,
branch, and recognizable project files. If the working directory is not a Git checkout,
use the already-loaded project instructions and a bounded check of top-level project
markers; do not recursively inventory the workspace. At this stage do not load a machine
profile, software profile, stack, or work-mode document.

## 5. Establish modes

Default the handbook mode to **user**. Accept **developer** only when explicitly declared;
then read `ARCHITECTURE.md`, `ROADMAP.md`, `handbook.yaml`, and `modes/developer.md`.

Ask one question only: which current work mode applies — debugging, performance,
benchmarking, tuning, or production? State it after the operator answers. A mode changes
only on another explicit declaration. After the operator answers, read exactly
`modes/<work-mode>.md` when it exists. If that mode document has not landed during
bootstrap, report that limitation and use no unrecorded conventions.

## 6. Resolve targeted Tier-1 context

Only after the current work mode is stated:

- when the detected machine is not `unknown`, open only
  `machines/<machine>/machine.yaml`; do not open `machines/INDEX.md` or any other machine
  profile;
- when the working-directory software is recognized and its profile exists, open only the
  matching `software/<software>/project.yaml`;
- derive the nearest validated stack only from the detected machine's `stacks/` and the
  detected software and environment. Do not inspect stacks for any other machine, and load
  only the nearest matching `stack.yaml` when one exists. Otherwise report
  `no matching validated stack`.

A login host alone cannot reveal the intended node type. An explicit operator declaration
wins; without one, resolve the sole `node_types` entry in the matching machine profile as
the default. If the profile has multiple entries, leave node type undeclared until the
operator selects one. Reconcile the resolved type with accelerator telemetry once a job
runs.

End with a compact orientation report: frontend, handbook identity/freshness, handbook
mode, work mode, machine, software/commit, node type, nearest stack, and any staleness
warning, plus the session-logging state and offer when applicable.
