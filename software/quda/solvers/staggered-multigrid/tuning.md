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

**Screen legality and capacity as two questions, in that order.** First establish which node
counts are legal for the candidate's aggregation blocks, then the device high-water floor at
each. They are separate because a block change moves the first and not the second: at a
placement already chosen the floor is set by fine local volume and does not respond to level
count, blocks, coarse counts or MMA — see
[`../staggered-memory.md`](../staggered-memory.md). Run them together and a hierarchy change
gets credited with a memory improvement that actually came from the placement change it
enabled.

The legality screen is not a formality: an aggregation block extent that is not a power of
two propagates its odd factors into the legal rank counts, and can leave a node ladder with
no rung between two counts you have already run — see
[the geometry constraints](../staggered-multigrid.md). Enumerate the ladder with the
decomposition tool rather than assuming an intermediate node count exists.

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

**The squeeze, and why it is not about lattice spacing.** A single aggregation on a small
lattice cannot make `coarse_fine_work` small *and* keep the coarsest volume adequate at the
same time. Coarsen gently and the ratio stays of order one; coarsen hard and the coarsest
volume falls below the adequacy floor of
[`hierarchy-and-setup.md`](hierarchy-and-setup.md). The two screens close on each other, and
depth is what opens the gap between them. That squeeze — not the lattice spacing directly —
is why a fixed-degree terminal preconditioner can fail on a coarse lattice and succeed on a
fine one: the fine lattice has enough sites to spend on depth.

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
240-iteration candidate `8.4%` **faster**. Iterations falling with slowness, and rising
with speed, bracket the failure from both sides.

**Always report the per-iteration cost that links an iteration count to a time**, and never
rank V-cycle work changes on either factor alone. The quoted factors are one candidate
pair each and do not transfer; what transfers is that their product decides. This does not
weaken the rule above — a measured outer-iteration count is still required before selecting
from a cost screen. It says that count is a *convergence* observable, not a cost one.

**Depth can only move one of the two factors.** A hierarchy that adds a level *below* an
existing coarsest grid cannot converge in fewer outer iterations than the hierarchy it
replaces: it demotes an accurately solved grid to an intermediate one solved to a finite
iteration cap, substituting an approximate solve for an exact one. Formally, if `B` is `A`
with `A`'s coarsest level demoted, then `n_B >= n_A` at fixed lattice, gauge, mass, transfer
and smoother. **So a deeper hierarchy buys per-iteration cost, never iteration count, and
must win on the cost term alone** — which also means its per-iteration budget has to beat
`n_A` before a trial is worth buying. Read the inequality, not any particular `n_A`: that is
a per-candidate measurement and moves with mass. Evidence: derived from the hierarchy's
own structure and **not yet independently tested**; the inequality is arithmetic, its
usefulness as a screen is not yet demonstrated.

**A measured instance of the same cancellation, with its limit.** Across an aggregation-block
scan at fixed lattice, mass and near-null counts, outer iteration count and recurring solve
time moved in **opposite** directions, and total cost stayed inside a narrow band while the
iteration count more than tripled. **The cancellation is bounded.** It holds only while
per-outer cost is still falling; once per-outer cost saturates, the iteration term dominates
and cost tracks it — in the recorded scan, total recurring cost then jumped to roughly three
times the band. **Do not screen or rank aggregation-block candidates on iteration count**,
and do not assume flat cost outside the sampled regime either.

**Before costing a coarsest-side candidate, bound what it can win.** A change acting only on
the coarsest level cannot reduce recurring solve time by more than that level's share `f` of
it, so it cannot close a deficit larger than `1/(1-f)`. The break-even share is
`f* = 1 - t_target/t_current`; compare the deficit against `f*` before paying for the trial.

**The relation is arithmetic; `f` is not a coefficient.** It is a per-candidate ratio and
must be measured for the candidate in hand. One campaign's internal estimates for `f`
spanned roughly `0.44` to `0.69` — a range wide enough to flip the conclusion — and none of
them was a measurement: they derived from QUDA profile times, which report stored tuning time
multiplied by call count rather than current-run time
([`../../internals/autotuning.md`](../../internals/autotuning.md)). A later direct measurement
on that candidate put `f` above `0.95`, which makes the ceiling nearly vacuous there.
**Use this rule to make `f` a measurement target, never to declare a candidate dominated
before `f` is known.** Where `f` approaches one the ceiling stops binding and the constraint
is again the product `n_outer x cost_per_outer`, whose two terms move in opposite directions
with coarsest-level accuracy.

### Pricing a parameter change through the chain it actually moves

Two parameters look like single knobs and are not. Price both through their chain before
attributing a result to them.

**An intermediate level's `coarse_solver_maxiter` multiplies coarsest-solver invocations.**
Raising it raises the number of coarsest solves per outer iteration by the ratio of
*achieved* intermediate iterations, and per-outer cost follows, because the coarsest operator
dominates that cost. In one measured three-level case a cap raised from `2` to `8` took
coarsest calls per outer iteration from `2.0` to `6.9` and per-iteration cost up by `3.0x` —
matching a prediction stated before the run to about one percent.

**It is the achieved ratio that multiplies, not the cap ratio.** Raising the intermediate
tolerance alongside the cap breaks the arithmetic in the favourable direction, because the
intermediate solve then exits early and never reaches the new cap. Record achieved
intermediate iterations, not the cap, when pricing the change. Note also that `maxiter` and
the CA basis size jointly select the coarse solver's execution mode, so a cap change can
silently change what the solver *is* — see
[`the MG overview`](../staggered-multigrid.md).

**Post-smoothing is nearly free on an intermediate level and is not on the fine level.**
The two are not interchangeable knobs. In one measured pair, quadrupling the post-smoother
sweep count on the level below the fine grid changed per-outer-iteration cost by about
`-2%` while cutting outer iterations from `22` to `19`; doubling it on the **fine** level
cost over `12%` per iteration. The asymmetry follows the grid the smoother runs on — fine-grid
work is full-operator work, and no iteration saving on that level is free. Price a smoothing
change against the level it acts on before treating an iteration reduction as a gain.

**Changing the coarsest-defining near-null count is never a one-variable move.** It moves
three things at once, and two of them are invisible in a parameter-file diff:

1. **Coarsest cost**, source-derived and quadratic — it is the `nvec_(L-1)` in
   `coarse_fine_work` above.
2. **The coarsest spectrum.** The coarse space dimension is
   `coarsest_global_volume * 2 * nvec_(L-1)`, so a smaller coarse colour pushes the same
   deflation request further up a smaller spectrum and `eval_max` moves. **`deflate_a_min`
   must therefore be re-derived from a measured `eval_max` on the new hierarchy; carrying it
   across is a convergence failure, not a quality regression** — see
   [`coarse-deflation.md`](coarse-deflation.md).
3. **Coarse-space quality.** Fewer near-null vectors give a poorer coarse space and more
   outer iterations, and that degradation can be a collapse rather than a slope.

Effects 1 and 3 oppose. So price such a candidate on measured recurring cost *only after*
re-deriving `deflate_a_min` and confirming the outer solve still converges — a comparison
made without both is not measuring the parameter it claims to.

**Which count is coarsest-defining depends on level count:** `nvec 1` at three levels,
`nvec 2` at four ([level naming](../staggered-multigrid.md#level-naming)). At four levels a
`nvec 1` change leaves the coarsest cost term untouched but still perturbs the coarsest
spectrum indirectly, by altering the level-2 operator its near-null vectors are generated
from. Re-derive `deflate_a_min` there too.

Evidence for the three-effect decomposition: effect 1 is source-derived; effects 2 and 3 rest
on two points of one three-level hierarchy at one mass, so treat their magnitudes as
indicative and the coupling itself as the transferable part.

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
candidates and compute the setup/recurring crossover for the declared solve count. Store
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
