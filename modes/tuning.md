# Tuning Mode

Tuning mode searches for an efficient candidate for a declared production workload. A
candidate is the combination of solver and build choices, runtime parameters, resource
placement, decomposition, batching, I/O, and other workflow choices being evaluated. A gauge
configuration is part of the workload and never a synonym for a candidate; and `setup` in
this handbook means a solver's setup phase, which is why a candidate is not called one. The mode changes only when
the operator explicitly declares a different work mode. Measurements made while selecting the
next candidate are exploratory; they do not become benchmark claims merely because one candidate
wins.

## Establish the task

Before changing a build, parameter, decomposition, or runtime setting:

1. State the production decision to be made, the representative workload, and the objective:
   elapsed time, node- or GPU-hours, memory fit, throughput, time to solution, or a declared
   combination. Name every hard constraint separately from the optimization objective.
2. Establish the division of labour: analysis-only, prepare-and-handoff, or
   prepare+submit+analyze. Permission to tune does not authorize project edits, rebuilds, Git
   actions, or scheduler submission unless the operator included those actions in scope.
3. Detect the software commit and branch, working-tree state, machine, node type, nearest
   validated stack, build capabilities, runtime environment, and tunecache state. Report every
   unvalidated dimension instead of treating a nearby stack as coverage.
4. Freeze the correctness reference and identify which workload properties must remain fixed:
   operator, source and sink definitions, masses, tolerances, precision, solve mix, output
   products, and any production-equivalence checks. A faster candidate that changes the required
   result is not a tuning improvement.
5. Declare the tunable search space and starting candidate. Include solver and setup parameters,
   build capabilities, node count, rank and thread placement, decomposition, batching, I/O,
   source changes, and other workflow choices only when they are in scope. A source change is
   in scope only when the operator put it there; see below for what makes it a different kind
   of trial.
6. Write the initial prediction record in the working directory before any
   allocation-consuming trial. Record expected runtime, resource cost, memory, iterations, and
   the reason the proposed change should help.

## Tuning method

1. Establish a correct baseline with isolated outputs and a recorded environment. If the
   baseline cannot complete or fit in memory, treat feasibility as a constraint and find the
   minimum viable resource setup before optimizing performance.
2. Choose each trial to answer one decision. Prefer changing one variable at a time. When a
   coupled change is unavoidable, label the bundle and do not attribute its effect to one member
   without an independent comparison.
3. Keep workload and correctness checks fixed across comparable trials. Truncated workloads are
   allowed for search only when their relationship to the production workload is stated; confirm
   the final candidate on the production-shaped case.
4. Give every candidate isolated run state, outputs, and tunecache identity. Never let a short
   test leave files that a later full trial can mistake for its own results.
5. Verify what the application actually executed. Requested solver names, set types, precision,
   batching, and device placement are inputs, not evidence that the intended path ran.
6. Compare the declared objective, not a convenient proxy. Solve count, iteration count, kernel
   rate, or elapsed time alone may rank candidates differently; node- or GPU-hours and memory fit
   remain part of the decision when they constrain production.
7. Separate autotuning, algorithm setup, recurring solve cost, I/O, contractions, and other
   workflow components. For eigenspace, multigrid, or similar setup, report the expected
   amortization regime and break-even solve count.
8. Apply a fair warm-state contract. A new solver, precision, right-hand-side shape,
   decomposition, or node type may trigger tuning after other kernels are warm. Either bring
   every candidate to the same declared steady state or include the cold cost that production
   will actually pay.
9. Complete the predict → run → compare record for every allocation-consuming trial. Diagnose
   misses before choosing the next candidate; do not silently tune the prediction after seeing
   the result.
10. Repeat close or noisy comparisons. Treat a single fast trial, an anomalous machine, and a
    tuning-contaminated first occurrence as insufficient evidence for selection.
11. Select the candidate against the original objective and constraints. Report tradeoffs,
    untested alternatives, sensitivity to workload assumptions, and any parameter whose physics
    or numerical correctness still requires operator review.

## Trials that change source

A source change is a trial like any other and a more expensive one, in three ways that decide
how it is run rather than merely how long it takes.

**It costs a rebuild before it can be measured**, and on a machine where the build itself is a
job, that rebuild is an allocation-consuming step under the same ceiling and ledger as the trial
it enables. Budget it as part of the trial, not as overhead outside it.

**It can change the result.** A parameter trial leaves the computation alone; a source trial may
not. Re-run the correctness reference rather than assuming it still holds, and treat a candidate
that is faster and different as a rejected candidate, not a win with a caveat.

**It invalidates warm state selectively.** Where the software autotunes, a change that moves a
kernel's shape, instantiation or launch geometry makes the cache cold for exactly those keys and
leaves the rest warm. A trial measured across that boundary compares a warm baseline with a
partly cold candidate. Re-establish the declared warm state before the measurement counts, and
say which keys were re-tuned.

Load `software/<name>/development.md` before making the change, and keep the boundary the
handbook already draws: a change that alters **what** is computed is an algorithm trial and
belongs in a different comparison from one that alters only **how**.

Performance analysis may be used inside tuning when it is subordinate to choosing the next
candidate. If the immediate deliverable becomes explaining a bottleneck rather than selecting a
candidate, recommend performance mode. Timing a candidate does not by itself change the
current mode to benchmarking.

## Acting on a performance hypothesis

Performance mode hands over a ranked hypothesis list rather than a candidate. Each entry already
carries what a prediction record needs: the phase, the fraction of its elapsed time the
bottleneck is claimed to hold, and the speedup bounds that follow from that fraction — the lower
from halving the cost, the upper from removing it entirely.

**That claim is a standing prediction, so the trial testing it does not need a new one.** Record
which hypothesis the trial tests, carry its bounds into the trial's prediction record, and after
the run compare the realised change with `tools/gpu-profile-diff.py`. Three outcomes, and they
mean different things:

- **Within the bounds** — the hypothesis is supported, and the fix did roughly what the fraction
  said it could.
- **Below the lower bound** — either the fraction was inflated, or the change addressed only
  part of what the hypothesis named. Distinguish those before trying again: they call for
  opposite next moves.
- **Above the upper bound** — something moved that the hypothesis did not name. Suspect a
  confound in the comparison before crediting the change; a source trial that also re-tuned a
  cold cache is the common one.

**A fraction that is systematically inflated across trials is a defect in the analysis, not a
run of bad luck.** It means an attribution rule is wrong, and it is the signal the
predict-compare loop exists to produce. Report it against the leaf or the method that produced
it rather than quietly widening the tolerance.

Hypotheses that were not tested stay on the list with that status. An untested hypothesis is not
a refuted one, and a later session should not have to re-derive it.

## Handoff to benchmarking

The tuning winner is a candidate, not a benchmark result. Before making a performance or
production-cost claim:

1. Freeze the candidate, workload, warm-state contract, metrics, correctness checks, and
   repetition plan.
2. Reserve independent confirmation data or runs that were not used to select the winner.
3. Record the tuning search and selection rationale in the working directory so the benchmark
   does not have to reconstruct them.
4. Recommend a transition to benchmarking mode. Do not change modes until the operator
   explicitly declares it.

An exploratory trial may satisfy confirmation only when the candidate and confirmation protocol
were fixed before its result was observed. A winning run selected from the search may not be
relabeled as confirmatory after the fact.

## Permissions and safeguards

- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour ceiling
  and a working-directory budget ledger. Without both, prepare the job and give the submit
  command to the operator.
- Before each proposed submission, compare purpose, node count, walltime, and concurrency with
  the selected machine profile. Record the selected scheduler class and why it is appropriate;
  this never overrides site policy or the budget rule.
- Keep predictions, candidate matrices, raw outputs, tunecaches, measurements, and campaign
  recommendations in the working directory. They are run evidence and live campaign state, not
  handbook knowledge.
- Do not change project code merely to make one candidate faster unless code modification is
  explicitly in scope. Load `software/<name>/development.md` before any authorized software
  change when that document exists, and run it as the kind of trial described above rather than
  as a parameter change that happens to need a compiler.
- Treat absent solver, build-profile, ensemble, or validated-stack knowledge as an explicit
  limitation. Do not fill the gap with an unlabeled assumption.

## Tools and routing

Before analyzing a solver-specific tuning task, run the task-time Tier-2 routing
checkpoint. A task that selects a solver, summarizes or interprets a solver-tuning
campaign, diagnoses an unhealthy result, explains a solver parameter, or chooses
the next candidate must open the
[solver-tuning playbook](../playbooks/tune-solver.md) before analysis. Re-run
routing when the application, solver, hierarchy, parameter class, or immediate
decision changes.

Use the detected machine profile, software profile, nearest stack, build profile, relevant
application guide, and relevant solver documents when present. Use the working project's own
instructions throughout. Prefer executable memory and decomposition checks to informal scaling,
use `conventions/running.md` to reconcile each trial's outcome,
[`conventions/repeated-work.md`](../conventions/repeated-work.md) at each study or phase
closure and at each work-mode change to decide whether a procedure now repeated by hand
should become a tool,
`conventions/measurement.md` for per-run observed ledgers, `conventions/batch-scripts.md` before
writing, modifying, or reviewing any batch script or preparing a submit command,
[`conventions/campaign-records.md`](../conventions/campaign-records.md) when opening or
reorganising a multi-study campaign against an allocation, and the shared
prediction record for every trial.

When a trial tests a hypothesis from performance mode, check the record with
`tools/hypothesis-record.py` before acting on it — a speedup bound that was asserted rather
than derived makes the comparison meaningless — and compare captures with
`tools/gpu-profile-diff.py`.

Route reusable software mechanisms to `software/<name>/`; machine-specific placement and
runtime behavior to `machines/<name>/`; and durable measurement rules to `conventions/`.
Campaign-specific optima and search histories remain in the working directory.

## Done

Tuning is done when a candidate is selected against the declared objective and
constraints; its correctness scope, environment, resource cost, warm state, and sensitivity are
recorded; rejected and untested alternatives are named; and an independent confirmatory
benchmark is defined. Before closing, run the automation checkpoint in
[`conventions/repeated-work.md`](../conventions/repeated-work.md) and record its outcome,
including candidates deliberately left manual. A transition to benchmarking, production,
performance, or debugging requires another explicit operator declaration.
