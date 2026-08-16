# User-wide Session Logging

Use this playbook only after startup has identified the active frontend and checked
logging state. The feature is user-wide on the current account and machine; it is not an
administrator-managed installation for every system user.

## Contract

The frontend's global `Stop` hook rewrites one text log after every assistant turn:
`<launch-dir>/session_<YYYY-MM-DD>_<session-id>.log`. Logs contain user text and visible
assistant text. They exclude tool calls and tool outputs, but they do not scrub secrets.
They are operator-facing provenance backups and agents must not read them unless the
operator explicitly asks.

The handbook ships two adapters behind one contract:

- Claude Code copies `tools/log-session-claude.sh` into `~/.claude/` and registers a
  global `Stop` command in `settings.json`. It requires Bash and `jq`.
- Codex copies `tools/log-session-codex.py` into `~/.codex/` and registers a global
  `Stop` command in either `hooks.json` or existing inline TOML hooks. It requires
  Python 3.10 or newer and persisted transcripts. Inspecting or merging an existing
  `config.toml` requires Python 3.11+ or the `tomli` package. Codex's transcript JSONL
  is not a stable interface, so re-verify logging after major Codex upgrades.

Both adapters write atomically with mode `0600`. The installer copies them instead of
linking into the handbook so unrelated agent sessions do not depend on a clone remaining
at one path.

## Startup check and offer

After handbook identity and freshness are established, run:

```bash
python3 "$LQCD_HANDBOOK/tools/check-session-logging.py" \
  --frontend "$LQCD_HANDBOOK_FRONTEND"
```

The check is diagnostic, not a freshness gate. Report its state in the orientation
summary:

- `enabled` or `configured`: do not offer reinstallation. For Codex, trust remains a
  user-interface decision and cannot be proven by inspecting configuration.
- `missing`, `stale`, or `broken`: include one non-blocking offer:
  "Session logging is <state>. Say \"enable session logging\" to install or repair it
  for this user account."

Do not add a second mandatory startup question and do not persist a declined offer.

## Install only after explicit consent

Installing changes user-level agent configuration outside the handbook. Never install
automatically. After the operator explicitly agrees, run:

```bash
python3 "$LQCD_HANDBOOK/tools/install-session-logging.py" \
  --frontend "$LQCD_HANDBOOK_FRONTEND"
```

The installer is idempotent, backs up changed files, preserves unrelated hooks, and
refuses malformed or ambiguous configuration rather than guessing. It does not alter a
global Git ignore file. Offer that as a separate explicit action if the operator wants
`session_*.log` ignored in every repository.

### Claude activation

Claude Code loads hook configuration at session start. Reload through `/hooks` or restart
Claude Code, then complete another assistant turn.

### Codex activation and trust

Codex requires review and trust for every new or changed non-managed command hook. Tell the
operator to open `/hooks`, select the `Stop` hook that runs
`~/.codex/log_session.py`, review it, and choose **Trust**. Never edit `trusted_hash`
manually and never use a hook-trust bypass as installation.

If the current client does not reload after trust, restart Codex, resume the session, and
complete another turn.

## Verification

In a fresh or reloaded session:

1. Complete at least two assistant turns.
2. Confirm one nonempty `session_*_*.log` exists in the launch directory.
3. Confirm its modification time advances after the second turn without invoking the
   logger manually.
4. Confirm distinctive text from the latest user and assistant messages appears once.
5. Confirm the file mode is `600`.
6. Confirm tool output is absent.

Warn the operator that the logs are verbatim, can contain secrets, and appear in every
launch directory. A session crossing local midnight can leave logs under two date names.
