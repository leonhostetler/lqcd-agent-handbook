# Codex Session Preflight

Run this preflight before the shared start-session playbook continues.

Require all of:

```bash
test "${LQCD_HANDBOOK_LAUNCHED:-}" = 1
test "${LQCD_HANDBOOK_FRONTEND:-}" = codex
test "${LQCD_HANDBOOK_CODEX_BOOTSTRAP:-}" = 1
test -n "${LQCD_HANDBOOK:-}"
test -f "$LQCD_HANDBOOK/AGENTS.md"
test -f "$LQCD_HANDBOOK/.agents/skills/lqcd-start-session/SKILL.md"
```

Codex does not discover an added directory's `AGENTS.md` through the working project's
instruction chain. The launcher therefore supplies an additive instruction pointing to the
handbook entrypoint while preserving the working project's own `AGENTS.md` files. A failed
check means that complete loading is unverified; report partial loading and stop.

The optional user-skill symlink created by `tools/install-codex-skills` is a convenience,
not a precondition and not evidence that Tier 0 loaded.
