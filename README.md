# LQCD Agent Handbook

A portable, public knowledge base for agent-assisted lattice-QCD work across HPC systems.
The handbook separates machine capabilities, software knowledge, validated stacks, solver
knowledge, and task playbooks so a session loads only the context it needs. HISQ is the
default fermion convention unless the operator says otherwise.

## Starting a session

Clone the repository, set `LQCD_HANDBOOK` to the clone, and launch through:

```bash
export LQCD_HANDBOOK=/path/to/lqcd-agent-handbook
"$LQCD_HANDBOOK/tools/lqcd-claude"
# or
"$LQCD_HANDBOOK/tools/lqcd-codex"
```

Both launchers intentionally have no default path. They preserve the working project's
own instructions while loading the same handbook Tier 0 and startup workflow. When called
without arguments, both supply the same neutral initial prompt so orientation begins
immediately; caller-supplied arguments pass through unchanged. The Codex launcher works
without installation; `tools/install-codex-skills` may optionally expose the startup skill
in Codex's user skill directory.

The optional Codex link is intended for sessions in other repositories. Inside this
handbook repository, Codex may show both the repository skill and the same user-scoped
skill because same-named skills are not merged. The link records the clone's absolute path;
if the clone moves, remove the obsolete link and rerun the installer.

## Development status

The project is in bootstrap phase. `ARCHITECTURE.md` contains durable design decisions;
`ROADMAP.md` alone records slice state and the next action. Developer mode must be declared
explicitly before editing. Run `python3 tools/validate-knowledge.py` before committing.

This repository contains transferable knowledge only. Read `PRIVACY.md` before proposing
content mined from another project.
