---
title: Staggered multigrid tuning procedure
summary: Ordered source, hierarchy, setup, eigensolver, memory, and workload gates for tuning MILC-facing QUDA staggered multigrid.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Running a staggered-MG tuning campaign after solver selection, or deciding which parameter class to change next.
evidence: inferred
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_block_trlm.cpp
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

# Staggered multigrid tuning procedure

Tune in dependency order. A downstream timing cannot repair an illegal hierarchy,
setup pinned at its cap, or a partially converged coarse eigenspace. Keep a ledger of
requested and executed parameters, build identity, reuse state, counter scope, and
correctness for every trial.

## 1. Declare the decision

State the operator, residual contract, masses, source count, active batch width,
compatible hierarchy-reuse scope, target solve count, memory limit, and objective.
Separate setup/update cost from recurring solve cost. If selecting among solver
families, begin with
[`../staggered-solver-selection.md`](../staggered-solver-selection.md); this procedure
assumes MG has passed those gates.

## 2. Establish source legality and stack proof

Confirm the outer GCR-MG contract, build options, compiled coarse colours and MRHS
shapes, local lattice, effective transfer blocks, aggregate-space limits, and long-link
rules. Run the decomposition preflight, then compare its effective blocks with QUDA's
runtime messages. A native QUDA harness does not by itself validate the linked MILC path.

If the trial reuses stored near-null vectors, also confirm that the planned rank
decomposition matches the one that wrote them, or that they were saved in single-file
format; the decomposition preflight does not cover stored I/O layout. See
[`../../internals/vector-io-layout.md`](../../internals/vector-io-layout.md).

Stop if the executed operator, fallback path, residual, or hierarchy differs from the
declared decision.

## 3. Choose hierarchy candidates under memory

For every source-valid candidate, record global `V3`, coarsest-cell shape, `nu3`, and
the memory prediction tier. Confirm that the target matches the applicable row of the
[`calibration manifest`](calibration.md). Use
[`hierarchy-and-setup.md`](hierarchy-and-setup.md) for the empirical ordering and
[`../staggered-memory.md`](../staggered-memory.md) for capacity. Retain alternatives
when a larger `V3`, better cell shape, and memory headroom pull in different directions.

Measure the final candidate on the target stack. A prediction inside an error or
advisory band is unresolved, not a safe fit.

## 4. Stabilize setup before timing production

Locate the level-1 setup-tolerance knee with the counters defined by the
[`observable extraction contract`](diagnostics.md#observable-extraction-contract):
`setup_l1_iters/setup_maxiter_1`. Check that the setup does not repeatedly hit its cap
and that the resulting residual improves when the tolerance is tightened. Hold blocks,
near-null counts, stack, and setup cap fixed during this scan.

After a hierarchy or near-null-count change, repeat this step; cached vectors from the
old hierarchy are not evidence for the new one.

## 5. Stabilize coarse deflation

Express the requested eigenspace as `nu3`, predict or probe `eval_max`, set an explicit
`deflate_a_min/eval_max` margin, and inspect `l3_res_max` and TRLM restarts. Tune
`deflate_poly_deg`, `deflate_a_min`, and `deflate_n_kr` through that joint diagnostic,
using the corpus bands only inside their declared scope.

Do not optimize a coarse eigensolve merely for fewer restarts. Very few restarts can be
a symptom of aggressive filtering and under-resolved vectors.

## 6. Derive the workload schedule

At each mass that can change the decision, compare matched deflated and undeflated
configurations and compute the setup/recurring crossover for the declared solve count.
Store the result as `nu3(m)`, not as a transferable bare-mass table. Do not interpolate
an entire schedule from an unmeasured pair.

Pooled measurements must keep hierarchy reuse compatible. Combining setup from one
operator state with solve time from another does not define a crossover.

## 7. Validate production behavior

For finalists, record setup/update, recurring solve, iteration and residual diagnostics,
all QUDA memory counters, whole-device high-water, host RSS, and application correctness.
Repeat enough matched trials to separate a parameter effect from run noise. Re-run after
changing machine stack, rank geometry, active batch width, or reuse lifecycle.

The handbook intentionally supplies no numerical solver timing or crossover threshold.
Those values depend on ensemble, hierarchy, node count, binding, build, setup reuse,
solve count, and objective; the measurement procedure is the transferable result.

## Stop rules

Stop or return to an earlier gate when:

- QUDA adjusts a requested block or selects a fallback path unexpectedly;
- setup or coarse solves hit their iteration ceilings without the required residual;
- the spectrum prediction is used outside its envelope without a refit;
- a coarse eigensolve reports few restarts but poor worst-vector residual;
- an upper restart count is judged without checking convergence and `l3_res_max`;
- memory lands inside the uncertainty/advisory band or MRHS-MG relies on an absolute
  width model that does not exist;
- the claimed benefit disappears when setup is amortized over the declared compatible
  solve count; or
- correctness or reproducibility fails.
