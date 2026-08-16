---
name: lqcd-build-stack
description: Build or rebuild an LQCD software stack using a declared machine node type, named build profile, bounded build placement, and compute-node validation. Use when configuring, compiling, installing, or validating a handbook-managed stack.
---

# Build an LQCD stack in Codex

Require a completed `lqcd-start-session` orientation, then follow
`$LQCD_HANDBOOK/playbooks/build-lqcd-stack.md` exactly. Load only the selected machine,
software, profile, and nearest-stack records it routes to.

Do not infer a compute-node type from the login host. Do not submit a build or validation
job without an explicit campaign-scoped node-hour or GPU-hour ceiling. In developer mode,
show the exact proposed handbook diff and obtain operator approval before writing it.
