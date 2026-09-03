---
title: Selecting a QUDA staggered solver through MILC
summary: Compatibility gates, reuse-scoped cost models, measurement requirements, and stop rules for choosing among plain CG, deflated CG, and multigrid.
scope: [software:quda, software:milc, fermion:staggered]
load_when: Choosing among plain CG, deflated CG, and multigrid for a MILC staggered workload with a stated compatible-solve count.
evidence: inferred
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/milc_interface.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/solver.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/leonhostetler/lqcd-agent-handbook/blob/7abade7bc3a2c1ca6ce33027dca2691970cbcbb2/machines/perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/stack.yaml
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn_quda.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c
observed: "2026-08-20"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# Selecting a QUDA staggered solver through MILC

Choose a solver only after fixing the mathematical solve, compatible reuse scope,
production solve count, objective, and hard constraints. Plain CG, deflated CG, and
multigrid expose different operators and reusable state; a timing rank without those
conditions is not a portable solver recommendation.

Use [`staggered-cg.md`](staggered-cg.md),
[`staggered-deflated-cg.md`](staggered-deflated-cg.md), and
[`staggered-multigrid.md`](staggered-multigrid.md) for the implementation contracts.
Use [`../../../playbooks/tune-solver.md`](../../../playbooks/tune-solver.md) to run the
selection procedure.

## Apply the compatibility gates first

| Candidate | Mathematical path | Reusable state | Current handbook coverage and remaining gate |
|---|---|---|---|
| Plain CG | selected-parity Hermitian staggered normal equation | no eigenspace or hierarchy; ordinary process and autotuning state may still recur | `milc-cg` and `ks-spectrum-hisq-quda` compile the path; native QUDA and linked MILC stacks exercise plain CG with true-residual checks |
| Deflated CG | the same selected-parity normal equation with a low-mode projection attached to native CG | an eigenspace valid for the exact links, action, parity, mass-shift contract, and interface lifecycle | `milc-cg`, `mg-staggered`, and `ks-spectrum-hisq-quda` compile the path, but no current stack exercises eigensolve or load, projection, deflated solve, or reuse; treat it as experimental |
| Multigrid | full staggered system solved by outer GCR with a multigrid preconditioner | a hierarchy valid for the exact operator, parameter set, update policy, and decomposition | `mg-staggered` and the Perlmutter CUDA 13 native stack validate one unit-gauge hierarchy and solve; `ks-spectrum-hisq-quda-mg` and the Perlmutter linked-MILC MG stack additionally validate one production-gauge hierarchy through the MILC caller, with stored setup state loaded rather than generated |

Reject a candidate before performance work when its mathematical path does not satisfy
the application contract. Then require a named build profile whose compiled capabilities
cover the path and a machine stack whose runtime validation covers the behavior being
claimed. Distinguish linked-application validation, narrower native-harness validation,
and compiled-only capability; evidence from one layer does not silently satisfy another.

Two multigrid stacks now exist and they validate different layers. The
[`mg-staggered` stack](../../../machines/perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/notes.md)
covers QUDA's own native Perlmutter path on a synthetic unit-gauge system. The
[linked-MILC MG stack](../../../machines/perlmutter/stacks/milc-cuda13-quda-ks-spectrum-mg-2026q3/notes.md)
covers one hierarchy on a production gauge configuration through the MILC caller, with a
predeclared cross-solver correctness criterion against plain CG at the same placement.

Neither licenses a different hierarchy, placement, level count, or node type, and neither is
benchmark evidence: the native run populated a fresh tunecache and the linked run reused a
warm one. The linked stack additionally loaded stored near-null and eigenvector sets, so
hierarchy setup from scratch is not what it validates, and its repeatability gate was met by
an operator-accepted substitute rather than by a repeat. Deflated CG remains compiled but
runtime-unvalidated in the current catalog.

Apply memory, local-geometry, decomposition, and operator-lifecycle constraints before
timing. Failure to fit, an invalid aggregation hierarchy, or an eigenspace that cannot
remain exact over the intended reuse scope is a feasibility result, not a slow benchmark.

## Count compatible solves, not nominal solves

Let `N` be the number of solves that can legally reuse one solver setup. Count it inside
the narrowest invalidation boundary: gauge field, links and phases, action parameters,
parity, mass contract, decomposition, process lifetime, and any solver-specific update
policy. Do not amortize one setup over application solves that would require rebuilding
the eigenspace or hierarchy.

For candidate `s`, model cost in the declared objective unit as

```text
C_s(N) = I_s + N R_s
```

where `I_s` is solver-specific initialization and setup paid once per compatible reuse
scope, and `R_s` is recurring cost per production solve. Keep common application work in
the workflow ledger rather than silently assigning it to a solver.

For plain CG, `I_s` is normally small but may include first-use allocation and autotuning.
For deflated CG, separate eigenspace generation or load from projection and remaining CG
work; projection remains recurring even when setup is reused. For multigrid, separate
hierarchy construction or update from the recursive preconditioner and outer solve.

For candidates `a` and `b`, a positive crossover exists only when

```text
N* = (I_a - I_b) / (R_b - R_a)
```

is defined, positive, and lies inside a reuse scope the workload will actually reach. If
a candidate has both greater setup and no lower recurring cost, it is dominated for that
objective. Recompute the model for elapsed time and resource cost when they can rank the
candidates differently.

## Use workload-relative regimes

Do not publish one universal solve-count threshold. Classify the declared workload
relative to its measured crossovers:

- **setup-dominated:** `N` lies below the relevant positive crossovers, so minimizing
  one-time work usually decides the choice;
- **mixed:** `N` crosses some candidates or some masses but not others, so a per-system
  or per-mass solver schedule can beat one solver for the whole workload; and
- **throughput-dominated:** `N` is large enough that recurring cost controls the ranking,
  while setup, residency, and invalidation still remain in the accounting.

The regime is an output of the measured cost model, not a label inferred from an ensemble
name or an imported campaign threshold.

## Measure candidates on equal terms

Follow [`../../../conventions/measurement.md`](../../../conventions/measurement.md).
Freeze one correctness-equivalent workload, objective, resource unit, warm-state contract,
and repetition plan. Measure solver-specific first use and setup separately from a
homogeneous solve series, retain per-solve variability, and project the production count
without rewriting the observed ledger. For a MILC decision, native-harness evidence may
establish build and solver feasibility, but the final comparison must execute through the
linked MILC path unless the declared workload is itself the native test.

**Where a memory or decomposition floor keeps one candidate off the placement that makes
another cheap — which is the normal case for multigrid against plain CG — report the
production comparison and the matched-placement comparison separately, and never let one
stand in for the other.** They have been measured pointing in opposite directions. See
[`../../../conventions/measurement.md`](../../../conventions/measurement.md).

Confirm the execution path from runtime evidence. Solver names in an input file do not
prove that deflation was active, that a preserved space was restored, that the requested
MG blocks were used, or that the intended precision and batching path executed. Do not
compare iteration counts or nominal FLOP rates across CG and GCR-MG as though they
represented equal work.

**Count timer lines per delivered propagator, not per line.** MILC's `inv_type CG` emits
two `CONGRAD5` lines per propagator, one per parity, while `inv_type MG` emits one, so a
comparison built per line understates CG by about a factor of two and silently favours
multigrid. See
[`MILC staggered inverter types`](../../milc/internals/staggered-inverter-types.md).

## Decision and stop rules

Apply these gates in order:

1. **Contract:** reject a mathematically incompatible path.
2. **Evidence:** reject a missing compiled capability; then classify the intended caller as
   linked-application validated, native-harness-only validated, or compiled-only. Only claim
   the strongest layer actually demonstrated.
3. **Feasibility:** reject a candidate that cannot fit with headroom, form a legal
   decomposition or hierarchy, or preserve exact reusable state.
4. **Correctness:** reject a wrong execution path, failed convergence, unacceptable true
   residual, or failed application-level check before comparing performance.
5. **Economics:** reject a dominated candidate or one whose positive crossover exceeds
   the compatible production solve count.
6. **Resolution:** when the ranking is smaller than the measured variability, repeat or
   report the choice as unresolved; do not select the fastest single observation.

Stop tuning a candidate when a hard gate fails, when its best plausible remaining setup
or recurring-cost improvement cannot change the production decision, or when the next
trial costs more than the decision is worth. Stop tuning a parameter when controlled
trials show no decision-relevant effect and no quieter mechanism metric has been declared.
Repeated timeouts or iteration ceilings require a new causal hypothesis, not a longer
series of the same trial.

Record the selected solver, `N`, reuse and invalidation scope, objective, crossover or
dominance result, memory and decomposition status, validated stack, warm state,
correctness evidence, uncertainty, and untested alternatives. The tuning winner remains
a candidate until independent benchmarking confirms it.
