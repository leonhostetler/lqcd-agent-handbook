---
title: LQCD orientation and vocabulary
summary: Default HISQ convention and shared meanings used throughout the handbook
scope: [universal]
load_when: beginning any LQCD handbook session
evidence: operator
observed: "2026-08-14"
observed_on:
  requirements: handbook-bootstrap
review_by: "2027-08-14"
---

# Orientation

Assume highly improved staggered quarks (HISQ) unless the operator explicitly selects a
different fermion formulation. State any departure before applying solver, memory, or
measurement guidance.

Use these terms consistently:

- **solve** — one inversion for one right-hand side; performance claims must state how many
  solves share one-time costs;
- **setup** — solver preparation paid before the measured solve sequence;
- **sweep** — a coordinated set of runs over masses, parameters, configurations, or nodes;
- **stack** — a machine × software × toolchain × build-profile combination that was
  actually built and run;
- **episode** — one past run or campaign, retained as evidence rather than promoted to a
  reusable rule.

Evidence kinds are `source`, `docs`, `observed`, `reproduced`, `experiment`, `operator`,
and `inferred`; use the contract in `ARCHITECTURE.md`. Never read `session_*.log`: those
files are an operator-facing provenance backup, not agent-readable evidence.
