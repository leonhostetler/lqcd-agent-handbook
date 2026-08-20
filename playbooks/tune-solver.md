# Tune and select an LQCD solver

Use this playbook to select and tune a solver for a declared production workload. It
specializes tuning mode; it does not replace [`../modes/tuning.md`](../modes/tuning.md),
the working project's instructions, or software-specific solver pages.

## 1. Establish the decision

Complete session orientation and require tuning mode. State:

- the application and correctness-equivalent mathematical solve;
- the representative workload and production solve count;
- the exact scope across which setup may be reused and every invalidation event;
- the objective and its unit, such as elapsed time, GPU-hours, memory fit, throughput, or
  a declared combination;
- hard correctness, memory, placement, decomposition, and campaign-budget constraints;
  and
- whether the work is analysis-only, prepare-and-handoff, or authorized to submit.

Load the detected machine and node type, application guide, software build profiles,
nearest stacks, [`../conventions/measurement.md`](../conventions/measurement.md),
[`../conventions/running.md`](../conventions/running.md), and the candidate solver pages.
For MILC-facing QUDA staggered solves, also load
[`../software/quda/solvers/staggered-solver-selection.md`](../software/quda/solvers/staggered-solver-selection.md).

## 2. Build the candidate matrix

For each solver, record:

1. mathematical compatibility with the required operator and solution;
2. compiled capabilities in a named build profile;
3. runtime evidence layer—linked application, narrower native harness, or compiled only—and
   the behaviors actually demonstrated by the nearest stack;
4. reusable setup state and its exact invalidation boundary;
5. memory, local-geometry, decomposition, and process-lifecycle feasibility; and
6. the runtime messages and correctness checks that prove the intended path executed.

Remove hard-incompatible candidates. Keep compiled-only candidates explicitly labelled as
experimental. Keep native-harness-only candidates separate from application-validated
ones; validating the intended caller is a separate decision and may require a build or
stack workflow before performance selection. Never generalize a narrower stack beyond its
recorded scope.

The included Perlmutter
[`mg-staggered` stack](../machines/perlmutter/stacks/quda-cuda13-mg-staggered-2026q3/notes.md)
is a native GCR-MG reproduction seed. For a MILC workload it establishes bounded QUDA
feasibility, not linked-application validation.

## 3. Freeze the measurement contract

Before an allocation-consuming run, write the baseline, prediction, and measurement
contract in the working directory. Hold the application workload, tolerances, precision,
source semantics, output products, resources, binding, decomposition, and correctness
checks fixed across comparable candidates.

Give every candidate isolated outputs, process state, and tunecache identity. Declare
whether production starts cold, reuses an established tunecache, loads reusable solver
state, or builds it in process. A fair comparison reproduces that contract; it does not
give one candidate a warm state that production or its competitors do not have.

## 4. Establish one correct baseline per viable solver

Measure and record separately:

- application and gauge/link preparation common to all candidates;
- solver-specific first use, autotuning, setup, load, or update;
- a homogeneous series of recurring solves;
- solver-specific projection, residual verification, vector I/O, and cleanup when
  present; and
- whole-workflow elapsed and resource cost.

Apply the shared measurement convention to first-use treatment and retained samples.
Confirm the actual solver, operator, precision, batching, decomposition, setup creation or
reuse, convergence, true residual, and application output. If the nearest evidence is a
native harness but production uses an application interface, reproduce the bounded native
case first and then establish a separate correct application baseline.
Rejected, incomplete, and indeterminate runs stay in the cost ledger but do not enter performance statistics.

## 5. Price the production workload

For each viable solver, form the reuse-scoped model

```text
C_s(N) = I_s + N R_s
```

in every objective unit that matters. `I_s` is solver-specific one-time cost and `R_s`
is recurring cost per compatible solve. Use the production `N`, not the number of solves
in a convenient test. Perform sensitivity checks at the plausible low and high values of
`N`, setup reuse, and measurement uncertainty.

Calculate pairwise crossovers only where one candidate trades greater one-time cost for
lower recurring cost. A crossover outside the legal reuse scope does not justify that
candidate. A mixed workload may require a per-mass or per-system schedule rather than one
global solver.

## 6. Tune the term that controls the decision

Identify whether feasibility, one-time setup, or recurring solve cost determines the
production ranking. Change one variable per trial when possible, predict its mechanism
and expected decision impact before running, and compare against the original objective.

- **Plain CG:** establish the non-deflated baseline and tune placement, precision, reliable
  behavior, and batching only when they remain correctness-equivalent and decision-relevant.
- **Deflated CG:** validate eigenspace exactness and lifecycle first. Price generation or
  load, resident vectors, every projection, remaining CG, and preserved-space reuse
  separately. Do not select vector counts or repeated-projection policy without measuring
  the resulting production objective.
- **Multigrid:** verify compiled coarse-color and MRHS coverage, memory headroom, executed
  aggregation blocks, hierarchy health, and reuse or update semantics before parameter
  search. Reproduce the nearest stack's exact hierarchy before changing one dimension, and
  do not reuse its validation timing as benchmark or linked-application evidence.
  Separate near-null and coarse-eigensolver setup from recursive preconditioner
  and outer-solve work. Do not lengthen iteration ceilings until the upstream cause of a
  ceiling is identified.

When a parameter affects setup quality rather than measured solve time directly, declare
the quieter mechanism metric that will decide the trial before running it. A quality
improvement with no production-cost consequence is diagnostic evidence, not automatically
a faster candidate.

## 7. Apply stop rules

Stop a candidate immediately when it fails operator compatibility, compiled-capability,
memory/decomposition, execution-path, convergence, true-residual, or application-
correctness gates.

Stop its performance search when any of these is true:

- it is dominated in both one-time and recurring cost for the declared objective;
- its positive crossover is beyond the compatible production solve count;
- even the best plausible remaining change cannot alter the production ranking;
- controlled effects remain below measured variability and no decision-relevant quieter
  metric exists;
- repeated failures reproduce without a new causal hypothesis; or
- the next trial exceeds the declared allocation budget or costs more than the decision
  is worth.

Stop the overall search when a correct candidate satisfies all constraints and its choice
is stable over the plausible solve-count and uncertainty range, or when the remaining
alternatives are explicitly infeasible, dominated, unvalidated, or outside scope. “Do not
use the more elaborate solver for this workload” is a valid outcome.

## 8. Record and hand off

Write the candidate matrix, prediction and comparison records, rejected-run dispositions,
cost models, crossover sensitivity, selected setup, and untested alternatives in the
working directory. State the selected solver and parameters together with `N`, reuse
scope, validated stack, objective, resource placement, warm state, correctness evidence,
and uncertainty.

The winner is a tuning candidate, not a benchmark result. Freeze it, define independent
confirmation, and recommend an explicit transition to benchmarking mode.
