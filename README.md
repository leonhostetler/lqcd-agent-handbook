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
```

The launcher intentionally has no default path. It enables root `CLAUDE.md` loading and
adds the handbook directory so `/lqcd-start-session` is available.

## Development status

The project is in bootstrap phase. `ARCHITECTURE.md` contains durable design decisions;
`ROADMAP.md` alone records slice state and the next action. Developer mode must be declared
explicitly before editing. Run `python3 tools/validate-knowledge.py` before committing.

This repository contains transferable knowledge only. Read `PRIVACY.md` before proposing
content mined from another project.
