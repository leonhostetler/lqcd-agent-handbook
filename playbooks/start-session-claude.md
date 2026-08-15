# Claude Code Session Preflight

Run this preflight before the shared start-session playbook continues.

Require all of:

```bash
test "${LQCD_HANDBOOK_LAUNCHED:-}" = 1
test "${LQCD_HANDBOOK_FRONTEND:-}" = claude
test "${CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD:-}" = 1
test -n "${LQCD_HANDBOOK:-}"
test -f "$LQCD_HANDBOOK/AGENTS.md"
test -f "$LQCD_HANDBOOK/CLAUDE.md"
test -f "$LQCD_HANDBOOK/.claude/skills/lqcd-start-session/SKILL.md"
cmp -s "$LQCD_HANDBOOK/AGENTS.md" "$LQCD_HANDBOOK/CLAUDE.md"
```

A failed check means Claude Code may have loaded the skill without the complete Tier-0
rules. Report partial loading and stop. Do not infer or reconstruct the missing rules.
