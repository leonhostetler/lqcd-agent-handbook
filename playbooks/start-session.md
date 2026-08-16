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
`inbox/rejections/`, its name follows `<ISO8601>-<machine>-<uuid>.yaml`, and it was
privacy-screened before creation. Report every pending path. Any other status entry is a
hard gate.

Fetch the configured upstream when available. If local HEAD matches upstream, continue.
If upstream is a fast-forward and the tree is clean or contains only pending intake, pull
with `git pull --ff-only`. On an incoming-path collision, other dirtiness, an ahead branch,
a missing upstream, or divergence, report the state and stop before using potentially
stale knowledge. Developer mode additionally requires a clean tracked tree; pending intake
is the sole exception.

## 3. Check user-wide session logging

Run `python3 "$LQCD_HANDBOOK/tools/check-session-logging.py" --frontend
"$LQCD_HANDBOOK_FRONTEND"` after freshness is established. This is a diagnostic, not a
hard gate. Do not install or repair user-level hooks automatically.

Record the reported state for the final orientation summary. When it is `missing`,
`stale`, or `broken`, include one non-blocking offer: "Session logging is <state>. Say
\"enable session logging\" to install or repair it for this user account." Do not ask a
second mandatory startup question. On explicit acceptance, follow
`playbooks/session-logging.md`.

## 4. Detect context

Report rather than ask:

- machine evidence from hostname, scheduler commands, and any matching profile below
  `machines/`; report `unknown` when no profile exists;
- working-directory software from `git remote -v`, `git rev-parse HEAD`, branch, and
  recognizable project files;
- the nearest validated stack, or explicitly `no matching validated stack`.

A login host cannot reveal the intended node type. Treat node type as declared intent and
reconcile it with accelerator telemetry once a job runs.

## 5. Establish modes

Default the handbook mode to **user**. Accept **developer** only when explicitly declared;
then read `ARCHITECTURE.md`, `ROADMAP.md`, `handbook.yaml`, and `modes/developer.md`.

Ask one question only: which current work mode applies — debugging, performance,
benchmarking, tuning, or production? State it after the operator answers. A mode changes
only on another explicit declaration. If its mode document has not landed during bootstrap,
report that limitation and use no unrecorded conventions.

End with a compact orientation report: frontend, handbook identity/freshness, handbook
mode, work mode, machine, software/commit, node type, nearest stack, and any staleness
warning, plus the session-logging state and offer when applicable.
