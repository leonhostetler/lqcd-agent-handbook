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
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/coarse_op.cuh
  - operator's screened tuning records
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

For every source-valid candidate, record `coarsest_global_volume`, coarsest-cell shape,
`coarsest_vector_density`, and the memory prediction tier. Confirm that the target matches
the applicable row of the [`calibration manifest`](calibration.md). Use
[`hierarchy-and-setup.md`](hierarchy-and-setup.md) for the empirical ordering and
[`../staggered-memory.md`](../staggered-memory.md) for capacity. Retain alternatives when a
larger `coarsest_global_volume`, better cell shape, and memory headroom pull in different
directions.

Measure the final candidate on the target stack. A prediction inside an error or
advisory band is unresolved, not a safe fit.

**An absolute coarsest volume is necessary but not sufficient.** It measures whether the
coarse *problem* is well posed; it carries no information about whether the coarse *grid* is
cheap relative to the fine grid, and cost turns on the latter. Screen additionally on the
coarse/fine work ratio

```text
coarse_fine_work = (coarsest global volume * (2 * nvec_(L-1))^2)
                 / (fine global volume * N_c^2)
```

with `N_c = 3` for the staggered fine operator and `2 * nvec_(L-1)` the coarse gauge colour
defined in [`the MG overview`](../staggered-multigrid.md). The ratio is dimensionless and
reads directly: its value is **how many full fine-operator applications one coarsest apply
costs.**

**Mechanism.** The coarse operator is dense in coarse colour. Aggregation cuts sites but
raises per-site work by `(2 * nvec_(L-1))^2 / N_c^2`, and for a **single** aggregation stage
the volume reduction is very nearly cancelled by that density growth. **Depth, not block
size, is therefore the lever**: each additional level multiplies the volume reduction, while
`nvec` grows only once per level. That asymmetry is the reason a three-level hierarchy can
be terminal-dominated where a four-level one built on the same fine problem is not.

For scale, on one operator corpus the ratio was near `4.7` for a three-level hierarchy at
0.09 fm — the coarsest apply costing several full fine applications — against roughly `0.13`
for a four-level hierarchy at 0.04 fm, a factor of order thirty. Those two numbers are
illustrative of the spread, not a band: compute the ratio for the candidate in hand.

> **Proxy caveat, and it is not optional.** This is an **uninstrumented `volume x dof^2`
> proxy**. The mechanism is source-backed; **the number is not measured.** It counts neither
> the smoother, the transfer operators, communication, nor any per-level efficiency
> difference, and it has never been calibrated against a profiler on any machine. Treat it
> as `mechanism` tier: sound enough to *order* candidates and to explain a measured terminal
> share after the fact, never sufficient to certify one. In particular it must not be
> reported as a predicted cost or converted into a time.

**A cost model ranks candidates; it cannot promote one.** A screening model that predicts
coarse-grid *per-iteration* work — anything built from the coarsest global volume and the
coarse colour, whatever local symbol it is given — says nothing about how many outer
iterations the resulting hierarchy will need, and convergence is a separate axis it does
not model. **Never select a hierarchy from such a screen without a measured outer-iteration
count.**

The failure has been observed in two distinct forms, which is what makes it worth stating
rather than treating as bad luck:

- **The model is right and the candidate still loses.** Reducing the terminal-defining
  near-null count at three levels dropped per-iteration cost *exactly* as predicted, twice
  at two different counts, and the outer iteration count rose enough to destroy the gain
  both times — in the second case stalling outright.
- **The model is wrong, because its own validity moved.** Repeating the reduction at four
  levels, the predicted per-iteration saving did not materialise: the coarsest apply was
  only a minority of per-outer work there (order `40%`), against the great majority at
  three levels (order `95%`). A terminal-cost model calibrated where the terminal dominates
  silently stops applying when it does not.

So before trusting a terminal-cost model at a new level count, **measure what fraction of
per-outer work the coarsest apply actually represents.** Both observations are empirical,
from one ensemble at one spacing; the mechanism — a cost axis and a convergence axis that
the screen does not connect — is what transfers.

**And the converse holds, which is what makes this a single rule rather than two cautions.**
An outer-iteration count is not a cost proxy either. Recurring cost is
`outer iterations x per-iteration cost`, and **neither factor predicts the product**: a
V-cycle change moves both, usually in opposite directions, because work added per iteration
is what buys the iteration reduction. A measured case cut outer iterations `22 -> 8` — a
factor of `2.75` — and came out **`10.7%` slower**, per-iteration cost having risen `3.05x`.
A separate pair went the other way: `104` against `240` outer iterations, with the
240-iteration configuration `8.4%` **faster**. Iterations falling with slowness, and rising
with speed, bracket the failure from both sides.

**Always report the per-iteration cost that links an iteration count to a time**, and never
rank V-cycle work changes on either factor alone. The quoted factors are one configuration
pair each and do not transfer; what transfers is that their product decides. This does not
weaken the rule above — a measured outer-iteration count is still required before selecting
from a cost screen. It says that count is a *convergence* observable, not a cost one.

## 4. Stabilize setup before timing production

Locate the level-1 setup-tolerance knee with the counters defined by the
[`observable extraction contract`](diagnostics.md#observable-extraction-contract):
`setup_l1_capped_fraction`. Check that the setup does not repeatedly hit its cap
and that the resulting residual improves when the tolerance is tightened. Hold blocks,
near-null counts, stack, and setup cap fixed during this scan.

After a hierarchy or near-null-count change, repeat this step; cached vectors from the
old hierarchy are not evidence for the new one.

## 5. Stabilize coarse deflation

Express the requested eigenspace as `coarsest_vector_density`, predict or probe
`eval_max`, set an explicit `deflate_a_min/eval_max` margin, and inspect
`coarsest_res_max` — the worst residual over the delivered coarsest eigenvector prefix —
and TRLM restarts. Tune
`deflate_poly_deg`, `deflate_a_min`, and `deflate_n_kr` through that joint diagnostic,
using the corpus bands only inside their declared scope.

Do not optimize a coarse eigensolve merely for fewer restarts. Very few restarts can be
a symptom of aggressive filtering and under-resolved vectors.

## 6. Derive the workload schedule

At each mass that can change the decision, compare matched deflated and undeflated
configurations and compute the setup/recurring crossover for the declared solve count. Store
the result as `coarsest_vector_density(m)`, not as a transferable bare-mass table. Do not
interpolate an entire schedule from an unmeasured pair.

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

- a candidate was ranked by a cost or terminal-volume screen and no outer-iteration count
  has been measured for it;
- QUDA adjusts a requested block or selects a fallback path unexpectedly;
- setup or coarse solves hit their iteration ceilings without the required residual;
- the spectrum prediction is used outside its envelope without a refit;
- a coarse eigensolve reports few restarts but poor worst-vector residual;
- an upper restart count is judged without checking convergence and `coarsest_res_max`;
- memory lands inside the uncertainty/advisory band or MRHS-MG relies on an absolute
  width model that does not exist;
- the claimed benefit disappears when setup is amortized over the declared compatible
  solve count; or
- correctness or reproducibility fails.
