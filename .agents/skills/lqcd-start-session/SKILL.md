---
name: lqcd-start-session
description: Orient an LQCD session by validating handbook loading and freshness, detecting machine and software state, and establishing modes. Use at the start of every session using this handbook.
---

# Start an LQCD session in Codex

Before project work, follow `$LQCD_HANDBOOK/playbooks/start-session.md` exactly. It routes
first through `$LQCD_HANDBOOK/playbooks/start-session-codex.md`.

## Preconditions and independent safeguards

The session must have been started through `$LQCD_HANDBOOK/tools/lqcd-codex`. If
`LQCD_HANDBOOK_LAUNCHED=1`, `LQCD_HANDBOOK_FRONTEND=codex`, or
`LQCD_HANDBOOK_CODEX_BOOTSTRAP=1` is absent, report partial loading and stop; do not proceed
under procedures without Tier-0 rules.

Until orientation completes:

- default to user mode and do not edit handbook files outside new unique `inbox/` entries;
- do not submit scheduler jobs without an explicit campaign-scoped node/GPU-hour ceiling;
- do not admit private, unpublished, credential, allocation, or local-path material;
- do not guess which handbook clone, machine, node type, software, stack, or mode applies.

Report detected facts and ask only for the current work mode. Developer mode is accepted
only when the operator declares it explicitly.
