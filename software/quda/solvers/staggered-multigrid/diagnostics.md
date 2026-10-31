---
title: Staggered multigrid diagnostic chains
summary: Ordered setup, coarse-eigensolver, hierarchy, and measurement checks with explicitly scoped corpus advisory bands.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: A staggered-MG setup, eigensolve, convergence result, or performance comparison looks unhealthy or inconsistent.
evidence: experiment
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/multigrid.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/eig_block_trlm.cpp
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/eig_block_trlm.cpp#L186
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/eig_block_trlm.cpp#L205-L226
  - https://github.com/lattice/quda/blob/f2df42ac4caa0cd51b96b01006a1c25c8d753425/lib/solver.cpp#L483-L520
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/inv_gcr_quda.cpp#L289-L411
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/multigrid.in.hpp#L32-L41
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dslash_coarse.in.cpp#L105-L121
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/field_cache.h#L17-L41
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface_internal.cpp#L133-L134
  - https://github.com/lattice/quda/issues/1664
  - https://github.com/lattice/quda/pull/1666
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/multigrid.cpp#L1298-L1299
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/inv_cg_quda.cpp#L242-L304
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/inv_cg_quda.cpp#L338-L361
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/solver.cpp#L440-L454
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/include/kernels/dslash_coarse.cuh#L168-L193
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/include/reliable_updates.h#L205-L221
  - operator's screened tuning records
observed: "2026-10-07"
observed_on:
  software:
    quda:
      commit: f2df42ac4caa0cd51b96b01006a1c25c8d753425
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# Staggered multigrid diagnostic chains

Diagnose in dependency order and preserve the raw counters. The reference values here
come from the `perlmutter-a100-staggered-mg-2024-2026` four-level retrospective. Its
[`calibration manifest`](calibration.md) defines “closely matched” separately for each
advisory. The bands are not QUDA error conditions, universal healthy ranges, or
substitutes for target-stack validation.

## Quick reference

Every band below was fitted on **four-level** hierarchies. A numbered symbol is an executed
level index, so at three levels the coarsest grid is level 2 and these bands do not apply to it
until refitted — see [level naming](../staggered-multigrid.md#level-naming). The `Fitted at`
column exists so a band cannot be added here without answering that question.

| Observable | Corpus reference | Fitted at | Correct interpretation |
|---|---:|---:|---|
| `setup_l1_capped_fraction` | `0` is healthy | structural | any nonzero share of level-1 streams stopped by the cap; not a fitted band |
| `coarsest_vector_density` | fit envelope `0.022...0.250` | 4 levels | spectrum-calibration domain, not a legality or universal health band |
| TRLM restarts | `4...9` | 4 levels | stable middle reference; the two edges are asymmetric |
| TRLM restarts | `1...2` | 4 levels | under-resolution warning in the fitted corpus; **not reproduced** in a later 0.09 fm population — check `coarsest_res_max` directly |
| restarts far above band, cap NOT reached, **empty** `Eval[...]` prefix | — | 4 levels | stalled filter, not a slow solve; see the eigensolve triage below |
| `coarsest_res_max` | about `1.5e-4` | 4 levels | middle-band reference at the two fitted spacings; scale and tolerance remain problem-specific |

The decomposition tool's separate `coarsest_global_volume >= 10000` and coarsest-cell
aspect `<= 1.5` screens are likewise provisional three-ensemble advisories. Source
legality always has priority.

<a id="observable-extraction-contract"></a>
## Observable extraction contract

The retrospective field names are derived quantities, not literal QUDA labels. For the
source revision in this page's frontmatter, extract them as follows. If a later build
changes a message format, preserve the raw lines and update this contract before using
the old numerical bands.

**This contract is executable.** `tools/quda-mg-observables.py` implements it over one or
more application logs and an optional MILC multigrid parameter file:

```bash
python3 "$LQCD_HANDBOOK/tools/quda-mg-observables.py" <log> --mgparams <mgparams.txt>
```

`--mgparams` is required and is never guessed from the log's location. A workspace may
keep one parameter file per run, one shared across many, or any other arrangement, so a
path inferred from a directory convention can bind the wrong file and report a confident,
wrong cap — and a wrongly attributed value is worse than a missing one.

Prefer it to a hand read, and prefer its output to a remembered value. **The contract below
remains the specification and the tool is its implementation**, which matters because a
message-format change degrades the parse *silently*: the fields simply stop matching and
report `unavailable` or, worse, match something adjacent. Confirm the literal lines below
still appear in the log before trusting a field from a new build, and update contract and
tool together. A field the tool reports `unavailable` is missing data, never a zero.

- **`setup_l1_iters`:** within one completed hierarchy-build event, take each level-1
  near-null stream's final count from its end-of-solve summary,
  `MG level 1 (GPU): CG: Convergence at <N> iterations, n = <j>, L2 relative residual ...`
  (without `n = <j>, ` at batch width 1). QUDA prints it once per right-hand side whether the
  solve converged or hit its cap, so `N` is exact `[source]`. Then take the arithmetic mean of
  those counts. Under `setup_inv 1 ca-cgnr` the line reads `CA-CG:`. Never read the `CGNR:`
  summary the wrapper prints beside it. For a build cut off before its summaries, fall back
  to the trace: read the ordered lines matching
  `MG level 1 (GPU): CG: <k> iterations, n = <j>, ...` (or `CA-CG:`). A reset of `k` to zero
  starts a new level-1 near-null CG stream; take the terminal printed `k` before the next
  reset or the end of the build. The CA trace is printed once per basis block, so its
  terminal `k` can sit below the true final count, and a capped CA stream can read as
  uncapped from the trace alone.
  Do not add one to the printed counter and do not substitute solve-side level-1 GCR
  iterations. **The `n = <j>` field appears only when the level generates its near-null
  vectors in batches**, and the batch width is 16 only when the level's `nvec` is divisible
  by 16 ([`../../internals/staggered-mg-setup-allocation.md`](../../internals/staggered-mg-setup-allocation.md)).
  At width 1 the same streams print `MG level 1 (GPU): CG: <k> iterations, <r,r> = ...`
  with no index, one stream at a time, so the reset rule alone delimits them; read that
  shape only before `MG inverter setup complete`. A parser matching only the batched shape
  reports these fields unavailable for every such build, which reads as missing data rather
  than as the capped setup it may be.
- **`setup_maxiter_1`:** read the literal MILC parameter-file value
  `setup_maxiter 1` used for the same hierarchy build. If it cannot be recovered, report
  `setup_l1_capped_fraction` as unavailable rather than borrowing a cap from another
  level or run.
- **`eval_max` and `coarsest_res_max`:** for one coarsest eigensolve event, collect its
  lines matching `MG level <C> (GPU): Eval[NNNN] = (+real,imag) ... Residual = <r>`, where
  `<C>` is the executed index of the **coarsest** level — `3` in a four-level hierarchy,
  `2` in a three-level one and `4` in a five-level one. Reading a fixed `MG level 3` prefix
  silently returns nothing at three levels and the wrong level at five. `eval_max` is the
  maximum printed real eigenvalue and `coarsest_res_max` is the maximum printed `Residual`
  over the same delivered prefix; it is measured on the unfiltered operator and is not
  comparable with `deflate_tol`, which TRLM tests on the filtered one when
  `deflate_use_poly_acc` is on
  ([`../eigensolver.md`](../eigensolver.md)). Count the `Eval[...]` lines
  and compare that count with the requested coarsest deflation count — `nvec 3` in a
  four-level MILC parameter file, `nvec 2` in a three-level one, `nvec 4` in a five-level
  one — and the event's
  convergence summary; a short prefix is partial delivery, not a smaller complete
  spectrum.
- **TRLM restarts:** from the summary for that same event, parse the integer immediately
  before `restart steps`. Current variants include
  `TRLM computed the requested ... vectors in <R> restart steps ...` and
  `BLOCK TRLM ... in <R> restart steps with ...`. An absent summary is missing data,
  not zero restarts. Block TRLM (`deflate_block_size > 1`) prints its summary at
  `QUDA_SUMMARIZE` when it converges, and a named warning or error when it does not
  ([`../eigensolver.md`](../eigensolver.md)). Where neither appears, the eigensolve did not
  finish, and the count up to the cut is reconstructed from the `blockLanczosStep` sequence,
  which descends once per restart and so forms a sawtooth. That reconstruction is a fallback,
  not an equivalent source.

- **Capped coarse solves:** count a coarse GCR solve as capped when its printed iteration
  count equals that level's `coarse_solver_maxiter`, never by counting
  `MG level <n> (GPU): WARNING: Exceeded maximum iterations` lines. At `00c7ef33d` GCR tests
  `k`, the iterations since its last solution update, against `maxiter`, not the running
  total, and resets `k` at every restart and reliable update, so a solve that updated once
  before reaching its cap prints no warning (`lib/inv_gcr_quda.cpp`) `[source]`. Observed
  once: `428` warnings against `430` capped level-2 solves `[observed]`. The warning count
  is a lower bound only.

- **`first_cycle_contraction`:** from the **outer** GCR trace — the lines with no
  `MG level` prefix, `GCR: <k> iterations, <r,r> = <s>, |r|/|b| = <v>` — take `<v>` at
  `k = 1`. The `k = 0` line prints `|r|/|b| = 1.000000e+00`, so that single value already
  is the first cycle's contraction of the initial residual. Read it per solve and never
  across solves; an inner-level line carrying the same shape is a different quantity. The
  tool emits one value per solve of the build event, `;`-joined in log order.

Keep separate records when a log contains multiple hierarchy builds or eigensolve
events; never maximize or average across them silently. Compute `coarsest_global_volume`
and `coarsest_vector_density` from the global lattice and QUDA's executed blocks with the
decomposition tool, not from the per-rank coarse volume or requested blocks.

## An eigensolve delivers nothing: check restarts and the prefix first

When a coarsest eigensolve fails or delivers no vectors, read the **restart count and the
delivered `Eval[...]` prefix together, before** any setup-cap, spectrum, or filter-window
analysis. That one pair separates "stalled" from "slow" immediately, and it is cheap; the
alternative is spending a second submission to learn the same thing. This gate is scoped
to that symptom and does not displace the dependency order for the others.

| restarts | delivered prefix | reading |
|---|---|---|
| inside `4...9` | full | eigensolve healthy; look elsewhere |
| far above band, cap **not** reached | **empty** | **stalled** — the filter is not separating. Re-derive the window from a measured `eval_max` before spending more walltime |
| cap reached | partial or none | request too large, or the eigensolver controls are wrong |
| `1...2` | full | under-resolution warning; see below |

Two things make this gate work, and both are general eigensolver behaviour rather than
staggered-MG specifics — see [`../eigensolver.md`](../eigensolver.md): eigenvalues print
**only on completion**, so a stalled run yields no spectrum to inspect, and a filter window
placed below the largest requested eigenvalue causes **non-convergence** rather than merely
poor vectors. A stall with an empty prefix therefore points at the window before it points
at anything else. The MILC multigrid spelling of that window is `deflate_a_min`; see
[`coarse-deflation.md`](coarse-deflation.md) for what is specific to the coarsest level.

Before concluding that a coarse solver is unhealthy, also confirm which **mode** it is in:
a CA coarse solver with `Nkrylov == maxiter` runs as a fixed-degree preconditioner that
applies no stopping test and reports `iterated = 1.000000e+00 (requested =
0.000000e+00)`. See
[`the MG overview`](../staggered-multigrid.md). That output is a mode signature, not a
failure.

## A one-cycle screen is valid for V-cycle work and invalid for deflation

`first_cycle_contraction` is cheap — one solve, one line — which makes it tempting as a
general screen. **It is a legitimate screen for one parameter class and actively
misleading for another, and the two must be stated together**; either half alone gives the
wrong instruction.

- **Valid for V-cycle work.** Across a ladder varying smoother sweeps and an intermediate
  level's iteration cap at a fixed hierarchy and eigenspace, the first-cycle contraction
  ordered monotonically with the eventual outer iteration count. Work added inside the
  cycle changes what one cycle achieves, so one cycle can see it.
- **Blind to coarse deflation.** Across a deflation ladder from none to a large coarsest
  eigenspace at one hierarchy, the first-cycle contraction moved by a fraction of a
  percent **in the adverse direction** while the multi-cycle behaviour and the recurring
  solve cost improved substantially.

**Mechanism, and it is the transferable part.** Deflation does not change what a single
V-cycle achieves on the initial residual; it removes the slowly-converging modes that
otherwise dominate the outer Krylov recurrence over *many* cycles. A one-cycle statistic
cannot observe an effect defined across cycles. Work placed inside the cycle is the
opposite case, which is why the same number is diagnostic for one and null for the other.

**Actionable consequence.** Screen V-cycle work changes with the first cycle if you like,
but **never screen a deflation candidate on it** — and never read a flat or slightly
adverse first cycle as evidence that deflation is not helping. Use a multi-cycle
contraction or the outer iteration count with its per-iteration cost instead.

**Scope and evidence.** Empirical, one ensemble at one spacing, three-level hierarchies,
one hierarchy per ladder; the mechanism is expected to transfer and the magnitudes are not
quoted because the sign and the ordering are the content. Invalidated by a change of
smoother or terminal solver, or by a hierarchy in which the coarsest apply is a small
minority of per-cycle work.

## Do not blame the eigenspace for a stagnating coarsest solve

When a coarsest-level solve stagnates in a run that **loads** a persisted eigenspace, the
eigenspace is the intuitive suspect and is often the wrong one.

Two runs loading the **same** eigenspace file, whose worst loaded-eigenvector residual
agreed to every printed digit, behaved oppositely: one converged, the other stagnated with
nearly every coarsest invocation pinned at its iteration cap. Identical input vectors
cannot explain a difference in outcome, so the cause lay in the coarsest solver and its
parameters, not in the vectors. In the same episode a third run loading that file reported
an elevated worst residual and remains unexplained — recorded as unexplained rather than
attributed.

**Actionable consequence.** Before spending a trial on eigensolver quality —
`deflate_a_min`, `deflate_n_kr`, `deflate_poly_deg`, or a larger request — establish
independently that the vectors differ. The cheapest test is the one above: compare the
worst loaded-eigenvector residual across the runs being contrasted. **If it is identical,
eigenspace quality is excluded and the coarsest solver is the place to look.** This
complements the adequacy chain in
[`hierarchy-and-setup.md`](hierarchy-and-setup.md), where a coarsest grid that is too
*small* also presents as healthy at the coarsest level.

**Scope and evidence.** The argument is a controlled comparison rather than a fitted
result and does not depend on ensemble, mass or level count; it holds wherever an
eigenspace is loaded rather than regenerated. Invalidated if the compared runs differ in
terminal solver or cap other than the variable under test, or if the eigenspace is
regenerated in one of them.

## Setup pinned at its ceiling

1. Confirm the denominator is the matching level-1 setup cap and that the counter is
   from the current hierarchy build rather than a reuse event.
2. Compute `setup_l1_capped_fraction` — the share of level-1 streams that ended **at**
   the cap — and check repeated trials, not only one row. Do not average the iteration
   counts instead: a capped stream contributes exactly the cap, so a mean-to-cap ratio
   saturates near 1 and hides how much of the setup actually converged.
3. If pinned, loosen the requested work or repair hierarchy quality before interpreting
   downstream solve behavior. A capped setup does not prove that the requested setup
   tolerance was achieved.
4. After the change, confirm the setup residual and iteration ratio move in the expected
   direction, then regenerate any cached near-null vectors.

Do not begin by tuning the coarsest polynomial when the level-1 setup is already capped.

<a id="negative-rr-setup"></a>
## Negative `<r,r>` lines in batched near-null setup

The near-null setup CG can print lines such as
`MG level 2 (GPU): CG:  5953 iterations, n = 8, <r,r> = -2.654982e-03, |r|/|b| = nan` — in a
four-level hierarchy `MG level 2` is the level above the coarsest, and a five-level hierarchy
whose first two levels were loaded rather than generated showed them at `MG level 3`, again the
level above the coarsest. **The printed `<r,r>` is a recurrence
estimate, not a computed norm, and the line is not a health signal.**

Mechanism, `[source]` at QUDA `ba501e4f8`:

- Near-null generation forces a pipelined CG for every setup solver except BiCGStab
  (`solverParam.pipeline = 4`, `lib/multigrid.cpp:1298-1299`) and solves the level's streams in
  batches, indexed by `n = <j>` (batch width as in the extraction contract above).
- In the pipelined branch each iteration starts from a true `|r|^2`, but the value carried
  forward and printed is `sigma = alpha (alpha |Ap|^2 - <p,Ap>)` with `alpha = |r|^2 / <p,Ap>`
  (`lib/inv_cg_quda.cpp:242-271`). That equals `|r - alpha Ap|^2` only while
  `<r,Ap> = <p,Ap>`, which needs a Hermitian operator and intact conjugacy. After a step that
  contracts the residual strongly it is a small difference of large terms and can go negative.
- The fallback to a true norm tests only the batch's first system,
  `if (sigma[0] < 0.0 || ...)` (`lib/inv_cg_quda.cpp:265`). Systems `n = 1` and up keep a
  negative value: it is printed, it makes that system's `beta = sigma / |r_old|^2` negative for
  one step (line 304), and `convergenceL2` counts it as below tolerance (`lib/solver.cpp:450`).
- A batch cannot stop on it. When the recurrence makes every system look converged, a reliable
  update is forced (`lib/inv_cg_quda.cpp:300`) and recomputes every true residual (lines
  338-340) before the convergence test.
- The coarse dslash applies `M^dagger` from a separately stored link array: the forward hop
  reads `Y(d+4)` for `M` and `Y(d)` for `M^dagger` (`include/kernels/dslash_coarse.cuh:168-193`).
  With fixed-point (half) coarse-link storage the two arrays are quantised separately, so the
  normal operator the setup CG applies is Hermitian only to storage precision. That breaks the
  identity above independently of `dagger_approximation` `[inferred]`.

Observed at QUDA `ba501e4f8` and MILC `a5f8f9fa` on one ensemble, two gauge configurations,
four- and five-level hierarchies `[reproduced]`, six runs with the signature, seven batched
setups traced iteration by iteration:

- 73 negative lines and **none at `n = 0`** (if spread evenly over 16 systems the chance of
  that is `(15/16)^73`, about 0.009);
- all transient: 64 were positive at the next iteration, the other 9 were runs of two to four
  consecutive negatives in one system, then positive;
- present with `dagger_approximation true` and `false`; 63 lines in one hierarchy with
  half-precision coarse storage and none with `preconditioner_precision single`, one run each
  (that key also changes null-vector and smoother-halo precision);
- more lines where the setup solve runs longer: 63 in a hierarchy whose streams needed 8457 to
  the 10000 cap on one gauge configuration, none for the same file at about 2700 on the other;
- **no measurable iteration cost.** A batch of 16 ends when its slowest system converges. In
  every batch all 16 converged within 161 iterations of one another (at most 2 % of the batch),
  systems that broke down were not the last (2 of 6 batches in the hierarchy with 63 lines,
  about what chance gives), and in the 100 iterations around an event the affected system's
  residual fell faster than the batch median in 34 of 54 cases.

At another build, on one hierarchy and placement, the count depended on the mass (nonzero at one
of seven), on the gauge configuration (zero on two of three at that mass) and on the job (two
jobs on one file about a quarter apart) `[reproduced]`. At `ba501e4f8` a second job on the same
file, gauge configuration and build repeated the count, and every near-null iteration count,
exactly (see [`measurement.md`](../../../../conventions/measurement.md), "Determinism inside one
job is not determinism across jobs").

**Actionable consequence.** Do not read the lines as evidence for `dagger_approximation`, an
indefinite operator or an unhealthy hierarchy, and do not change either key to remove them.
Judge the setup by its per-stream iteration counts and final residuals ("Setup pinned at its
ceiling", and the next section) and the solve by outer convergence and the true residual. A
rising count tracks longer setup solves on a low-precision coarse operator, so it can accompany a
harder gauge configuration, but it is a symptom and costs nothing measurable by itself. No
summary line carries the count: take it from the raw log, per job.

<a id="setup-streams-above-tolerance"></a>
## Batched setup streams can finish above `setup_tol`

In a batched near-null setup the CG takes its reliable-update decisions from the batch's first
system (`ru.update_rNorm(sqrt(r2[0]))`, `lib/inv_cg_quda.cpp:295`), including the stagnation
exit `ru.reliable_break(r2[0], stop[0], ...)` (line 361), which logs
`solver exiting due to too many true residual norm increases` (`include/reliable_updates.h:205-221`)
and stops the whole batch. The other streams then print their summary,
`Convergence at <N> iterations, n = <j>, L2 relative residual: iterated = <v>, true = <v>`, with
`<v>` possibly above the requested `setup_tol`. `[source]` at `ba501e4f8`.

Observed at the same build `[reproduced]`, seven four-level hierarchies on two gauge
configurations, 672 streams on the level above the coarsest (`MG level 2` in the log): 78
finished with a true residual above `setup_tol 5e-6`, the largest `1.1e-5`. Every one was in a
batch that took this exit or reached `setup_maxiter`; no normally ended batch had one. The exit
ended every batch of one healthy hierarchy, and the hierarchy with the most such streams (38)
had the healthiest solve of the three runs with its aggregation on its gauge configuration.

**Actionable consequence.** The summary says `Convergence` either way, so read `true =` against
the requested tolerance and count the level's exit warnings before calling a setup converged to
`setup_tol`. A stream up to about twice `setup_tol` after this exit is not by itself a failed
setup; a batch at `setup_maxiter` is the case "Setup pinned at its ceiling" covers. The same
`reliable_break` stops MILC propagator solves
([`ks-spectrum.md`](../../../milc/applications/ks-spectrum.md), "A normal exit does not mean every
solve converged"); there MILC flags the solve, while in setup nothing does.

## Too few TRLM restarts

1. Confirm that the eigensolver converged the requested prefix and did not merely stop.
2. Read `coarsest_res_max`, not only the mean residual or `eval_max`.
3. Compute `deflate_a_min/eval_max`; a requested eigenvalue near the Chebyshev window
   edge is weakly discriminated.
4. Reduce filter aggressiveness through one of `deflate_poly_deg`, `deflate_a_min`, or
   `deflate_n_kr` while holding the other two fixed, then repeat.

One or two restarts were worse in every spacing sampled by the fit. This is a warning
about vector quality, not an instruction to maximize restart count — and it is
**unconfirmed outside that fit**: a later 0.09 fm population did not reproduce the
direction. See [`coarse-deflation.md`](coarse-deflation.md) before acting on a low count
alone. Read `coarsest_res_max` first either way; the residual is the quantity of interest
and the restart count is only its proxy.

## Many TRLM restarts

Inspect convergence and `coarsest_res_max` before acting. Ten or more restarts accompanied
both good and failed eigensolves in different fitted populations. If the vectors are
good and the cap was not hit, the count alone is not a failure. If residuals are poor or
the cap was reached, change the joint eigensolver controls or reduce the requested
eigenspace and repeat.

## Spectrum prediction misses

Check, in order:

1. the run used the recorded effective hierarchy and `coarsest_global_volume`;
2. `coarsest_vector_density` and mass are inside the fitted envelope;
3. `nvec_2` matches the calibration or `A` was refitted;
4. the ensemble-specific mass coefficient was measured locally; and
5. the eigensolver delivered a converged prefix with acceptable `coarsest_res_max`.

A large one-sided miss outside the envelope is not evidence for extrapolating the fit.
Inside the envelope, a printed `eval_max` biased low together with few restarts and poor
worst-vector residual can indicate a partially delivered eigenspace.

## Comparing a failing hierarchy against one that converges

Align the two by **position relative to the coarsest level**, never by absolute level
index. At three levels the coarsest is level 2 and at four it is level 3, so lining up
equal indices sets a coarsest level beside a non-coarsest one and misreads the result —
this is [level naming](../staggered-multigrid.md#level-naming) applied to a comparison.
Use two aligned positions: coarsest against coarsest, and level-directly-above-coarsest
against level-directly-above-coarsest.

At each aligned position, record for **both** hierarchies:

- the residual actually reached;
- that level's requested tolerance;
- the iteration limit granted to it; and
- how many of its invocations hit that limit.

Then record each hierarchy's outer GCR iteration count.

**What this buys, and what it does not.** The alignment **eliminates** candidate causes: a
limit hit in both hierarchies is normal and cannot explain a difference between them. It
**cannot attribute** the remaining difference while the two coarsest positions differ in
more than one property. So enumerate the differing properties first; if more than one
differs, attribution needs a controlled trial that holds the suspected-irrelevant property
fixed and moves the other alone. Reporting an attribution from the aligned comparison alone,
with several properties differing, is the failure this procedure exists to prevent.

The reference hierarchy must be **independently known to converge** on the same lattice. A
comparison against one that merely has not yet been shown to fail carries no information.

**Evidence and scope.** Mechanism. Observed across three- and four-level hierarchies on one
ensemble at one global lattice and two masses; the alignment rule is expected to transfer,
and it is invalidated by a level-count change that alters which level is coarsest without
updating the position mapping, or by a coarsest-operator change.

## A non-convergence result is bounded by the budget it was drawn at

An outer-iteration bound is part of any conclusion drawn under it. A candidate that fails to
converge within the bound has not been shown not to converge — it has been shown not to
converge *within that budget*, and the two are different claims.

The distinction is not academic. In one recorded case an apparent adequacy **cliff** — a
coarsest volume below which hierarchies did not converge, and above which they did — turned
out to be an artefact of the outer bound in use. Raised, the same candidates converged, one of
them well past the original limit. What had looked like a property of the coarsest grid was a
property of the budget.

So before reporting a boundary in any hierarchy parameter, re-run at least one failing
candidate at a materially larger bound. If it converges, the boundary was the budget. Record
the bound alongside the result either way; a non-convergence result quoted without it cannot
be interpreted later, and cannot be compared against a result taken under a different one.

<a id="padded-batch-stall"></a>
## A blocked solve plateaus a few `1e-8` above the one-RHS trace

**The tell.** A blocked (multi-right-hand-side) solve whose outer residual follows the
one-RHS trace of the same hierarchy — at or a little below it, since a batched coarse solve
over-solves all but its slowest member ([batched GCR](../staggered-multigrid.md#batched-gcr)) —
for about ten iterations, then flattens onto a floor
near `|r|/|b| ~ 2-3e-8` and runs to its outer cap, with the level-1 and level-2 coarse solves
pinned at their caps on most outer iterations. It is never a silently wrong answer: the outer
true residual is computed in double, and the solve reports non-convergence.

**Mechanism, at QUDA `00c7ef33d` `[source]`, confirmed by prediction in both directions.**
With `use_mma` on the coarse dslash, a batch is copied into temporaries of the next
instantiated width in `QUDA_MULTIGRID_MRHS_LIST` (with `8,16,32,64`, widths 9-15 pad to 16
and width 6 pads to 8). The temporaries come from QUDA's field cache, which returns a cached field
with its contents, under a key that does not include the actual batch width
(`lib/multigrid.in.hpp`, `include/field_cache.h`). The forward block transpose writes only
the real columns (`lib/dslash_coarse.in.cpp`), so the padding columns keep whatever an
earlier full-width user wrote. The half-precision block-float coarse halo takes one scale
per site across all columns, padding included, so `O(1)` stale padding sets the scale and
quantises the small real residual components. The confirmed earlier user is the coarsest
eigensolver's SVD, which applies the coarse operator in batches of
`compute_evals_batch_size`; QUDA's MILC interface sets that batch to `16` when the coarsest
`nvec` is a multiple of `16` and to `1` otherwise (`lib/milc_interface_internal.cpp`). On a
one-node reproducer, changing only that batch moved the stall `[observed]`: batch `1` made
width 15 converge, and batch `8` made width 6 stall at the same floor. Other earlier users —
near-null generation in batches of 16, a full-width solve before a padded one, the remainder
chunk of a width above the largest instantiation — are inferred from source and not run.

**What to do.** Each of these was observed at `00c7ef33d` on `gpu-a100-40`:

- **Workaround, no rebuild:** make the coarsest deflation count not a multiple of `16`
  (`3064` rather than `3072`), so the SVD batches by `1`, and regenerate the coarsest
  eigenspace at the new count. Through MILC on a multi-node production hierarchy that had
  stalled at width 15, width 15 then converged in the one-RHS outer iteration count
  `[observed]` once. The count and the batch change together.
- Keep blocked widths at or below `8` with the default SVD batch; or turn the coarse-dslash
  MMA off for wider batches, at about `1.7x` the per-iteration cost of MMA on at width 15
  `[observed]`.
- **Upstream fix:** [lattice/quda#1664](https://github.com/lattice/quda/issues/1664) reports
  the stall; [lattice/quda#1666](https://github.com/lattice/quda/pull/1666) zero-fills the
  padding columns in the forward transpose and was merged into `develop` on 2026-10-29 as
  `2e7dd818` (fix commit `de61c2935`). **This section describes QUDA through `00c7ef33d`
  and `develop` before `2e7dd818`.** Applied to
  `00c7ef33d` on the one-node reproducer, with the unpatched library stalling in the same job,
  it removed the stall at widths 15 and 12 and at width 6 with an 8-wide SVD batch; each
  converged in the one-RHS count `[observed]`. It is not verified at production scale. The
  batched SVD reaches the forward transpose at every solve width, so the fix also changes
  setup at width 1; do not expect width-1 residual histories to be bit-identical across it.

**Not claimed:** that a working wide block is faster than a narrower one; behaviour on other
architectures or with a single-precision coarse halo; that the merged fix removes the stall in
a production MILC run (not yet observed).

## A performance comparison looks surprising

Before attributing it to a tuning knob, match the operator, mass, hierarchy, rank
geometry, build, binding, setup/update lifecycle, active batch width, source count,
residual, and correctness. Separate setup from recurring work and state the compatible
solve count. Do not compare GCR-MG and parity-CG iteration numbers as equal units of
work.

No numerical solver timing or crossover from the retrospective corpus is published in
this leaf. Reconstruct the decision from matched measurements using the solver-selection
cost model.

## Minimum incident record

Keep the parameter file, executable and source revisions, build cache, machine/queue, global
and local lattice, rank geometry, requested and effective blocks, all `nvec` values,
`coarsest_global_volume`, `coarsest_vector_density`, setup iteration ratios, `eval_max`,
filter margin, restart count, `coarsest_res_max`, convergence messages, setup/reuse state,
memory counters, and correctness result. Without that record, a future run cannot
distinguish a parameter effect from a different executed solver.
