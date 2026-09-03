---
title: LQCD orientation and vocabulary
summary: Default HISQ convention and shared meanings used throughout the handbook
scope: [universal]
load_when: beginning any LQCD handbook session
evidence: operator
observed: "2026-08-18"
observed_on:
  requirements: handbook-bootstrap
review_by: "2027-08-18"
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
and `inferred`; each knowledge file declares one in its frontmatter, and the full contract
behind them is developer-mode reading rather than something to open while working.
Do not read `session_*.log` unless the
operator explicitly requests it. An authorized review treats the transcript as private
evidence, not canonical knowledge, and does not bypass privacy or publishability gates.
