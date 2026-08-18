# Benchmarking Mode

Benchmarking mode measures the performance or cost of a candidate setup and workload frozen
before the measured series begins. A candidate setup is the combination of solver and build
choices, runtime parameters, resource placement, decomposition, batching, I/O, and other
workflow choices being measured. A gauge configuration is part of the workload, not a synonym
for this setup. The mode changes only when the operator explicitly declares a different work
mode. If the next candidate depends on a measured result, the work is tuning, not benchmarking.

## Establish the benchmark contract

Before preparing, submitting, or analyzing a measured series:

1. Declare the benchmark intent:
   - **solver or component comparison** — characterize one fixed candidate or compare a
     predeclared set under equivalent conditions; or
   - **workflow-cost estimation** — estimate the elapsed time and resource cost of a fixed,
     production-shaped workflow, which may be explicitly truncated.
2. State the decision the benchmark will support, the target quantity, the production work
   unit, and the comparison or acceptance threshold. Examples of work units include one solve,
   one source, one gauge configuration, or one complete job payload.
3. Establish the division of labour: analyze-only, prepare-and-handoff, or
   prepare+submit+analyze. Permission to benchmark does not authorize project edits, rebuilds,
   Git actions, or scheduler submission unless the operator included those actions in scope.
4. Detect the software commit and branch, working-tree state, machine, node type, nearest
   validated stack, build capabilities, runtime environment, and tunecache state. Report every
   unvalidated dimension.
5. Freeze the set of candidate setups, workload, node and process placement, solver and runtime
   parameters, input and output definitions, warm-state contract, metrics, repetition plan, and
   correctness checks. Record them in the working directory before observing the measured
   results.
6. Write a prediction record before the first allocation-consuming run. Predict the quantities
   that matter to the decision, including elapsed time, node- or GPU-hours, device and host
   memory, iterations, and relevant component costs, with metric-appropriate tolerances or
   intervals.

## Boundary with tuning

A benchmark may compare a fixed, predeclared candidate set, but it does not adapt the set from
the observed results. Changing a solver, decomposition, node count, build option, runtime
parameter, workload definition, or warm-state contract ends the current measured series. The
agent should recommend tuning mode and remain in benchmarking mode until the operator explicitly
declares the transition.

Measurements collected while choosing the next candidate are exploratory tuning evidence. The
selected winner requires an independent confirmatory benchmark; it may not be relabeled after
the fact. A reserved confirmation set is independent only when its candidate and protocol were
fixed before its results were observed.

## Warm state and cost classes

Record four cost classes separately whenever they exist:

1. **autotuning or tunecache population** — generally keyed to the exact software, node type,
   solver, precision, right-hand-side shape, and decomposition;
2. **algorithm setup** — eigenspace construction, multigrid setup, or other work whose
   recurrence and reuse scope must be declared;
3. **steady component cost** — solves, I/O, contractions, or another repeated operation after
   the declared warm state is reached; and
4. **recurring workflow cost** — the end-to-end work that each production unit or job pays.

For a steady-state solver comparison, populate the required tunecache and run multiple
homogeneous solves under the same solver and candidate setup, differing only in source or
right-hand-side content. Exclude the first solve by default because it may contain allocation,
initialization, or autotuning overhead, and summarize the remaining solves. A single solve is
not representative steady-state evidence. A material solver, precision, batching, decomposition,
or other solve change begins another homogeneous series. Report excluded work and setup
separately. When cold-start performance is the target, measure it as its own declared series.

For workflow-cost estimation, reproduce the state that production will actually have. Do not
discard a cost that recurs once per gauge configuration or job merely because it appears in the
first solve. If a tunecache or setup is prepared once and reused across a campaign, report the
one-time cost, its reuse scope, and the amortized recurring estimate separately. If production
starts cold each time, include the cold cost.

## Measurement method

1. Create isolated outputs and run state for every candidate and repetition. Freeze an
   expected-artifact manifest from the final generated input and application semantics before
   launch, then compare exact missing and unexpected sets after the run. Never reuse a directory
   in a way that allows truncated, failed, or previous outputs to satisfy the current
   completeness checks.
2. Capture the exact environment, executable identity, input, resource request, placement,
   decomposition, binding, tunecache state, and relevant overrides. Reconcile the planned node
   type with accelerator telemetry from the running job.
3. Verify what the application actually executed. Requested-setting labels and solver
   modes are not runtime evidence; check solver, precision, batching, device placement,
   convergence, and tuning diagnostics in the output.
4. Apply the frozen correctness checks before accepting performance data. Establish structural
   artifact validity separately from numerical and scientific validity. Compare true residuals
   or equivalent invariants and reference results with a metric that remains meaningful near
   zero.
5. Measure the declared work unit and component boundaries. Record elapsed time, node- or
   GPU-hours, memory, solve and iteration counts, setup, I/O, contractions, and excluded time as
   applicable. Write one observed workflow ledger per run using
   `conventions/measurement.md`; retain parent clocks and mark nested diagnostics so they are
   not double counted. Do not use operation rate alone to compare algorithms that perform
   different work.
6. Run the predeclared repetitions and preserve failures and anomalous placements. Reconcile
   scheduler, runtime, application, artifact, and correctness evidence and assign the disposition
   defined in `conventions/running.md`. Do not drop a slow run without a recorded, evidence-backed
   exclusion reason.
7. Complete the predict → run → compare record for every allocation-consuming run. Diagnose
   misses as stale knowledge, a wrong model, a workload mismatch, ordinary variability, or an
   environmental change before revising the prediction.
8. Report a distribution, interval, or explicitly limited single observation appropriate to
   the metric. Near-deterministic iteration counts and noisy distributed wall times require
   different uncertainty treatment.
9. State every unmeasured optimization, unresolved correctness issue, and difference between
   the measured workload and production. A performance-complete but physics-unverified workflow
   receives only a provisional cost estimate.

## Solver or component comparison

- Hold the operator, source, solve mix, masses, tolerances, precision, correctness criteria,
  resource placement, and warm-state contract fixed unless the predeclared comparison is
  explicitly about one of them.
- Compare production-weighted cost, not only the fastest individual solve. Report setup and its
  break-even solve count for deflation, eigenspaces, multigrid, or other reusable state.
- Separate algorithm work from launch, tuning, and fixed workflow overhead. Fewer solves do not
  imply less work when iteration counts, batching, or operator applications differ.
- When candidates are statistically indistinguishable under the declared repetitions and
  tolerances, report a tie or bounded difference instead of selecting a winner from noise.

## Workflow-cost estimation

- Keep one observed ledger per run and build the production projection separately from accepted
  runs. Assign every term a boundary, accounting role, recurrence scope, and evidence source
  before scaling it.
- Use the full production-shaped payload when affordable. A truncated workflow must name the
  truncated dimensions and classify each extrapolated component as fixed, proportional,
  empirically modeled, or not safely extrapolatable.
- Establish memory feasibility and the minimum viable resource shape before costing the final
  candidate setup. Report both elapsed time and node- or GPU-hours so faster execution with more
  resources is not mistaken for greater efficiency.
- Break the total into recurring components such as setup, input, lattice or field loading,
  link construction, solves, contractions, output, and unaccounted time. State which components
  become negligible or dominant at production scale.
- Scale to a campaign only from a declared per-unit estimate, number of gauge configurations,
  concurrency assumption, one-time cost, and uncertainty model. Keep the resulting campaign
  prediction and live budget in the working directory.

## Permissions and safeguards

- Never submit a scheduler job without an explicit campaign-scoped node-hour or GPU-hour ceiling
  and a working-directory budget ledger. Without both, prepare the job and give the submit
  command to the operator.
- Before each proposed submission, compare purpose, node count, walltime, and concurrency with
  the selected machine profile. Record the selected scheduler class and why it is appropriate;
  this never overrides site policy or the budget rule.
- Keep predictions, raw outputs, measurements, exclusions, and campaign estimates in the
  working directory. They are run evidence and live campaign state, not handbook knowledge.
- Do not modify project code or parameters to improve a measured result while remaining in
  benchmarking mode. Report the opportunity and recommend tuning, performance, or debugging
  mode as appropriate.
- Treat absent stack validation and unresolved correctness as explicit limitations. A benchmark
  does not establish production readiness outside the capabilities and paths it exercised.

## Tools and routing

Use the working project's instructions, detected software profile, selected machine profile,
nearest validated stack, build profile, relevant application guide, and relevant solver
documents. Load `conventions/measurement.md` for the steady-state solve series, observed
workflow ledger, artifact manifest, and production projection, and load
`conventions/running.md` for run disposition and evidence reconciliation. Prefer reusable
timing, environment-capture, memory, and decomposition tools when present. Use the shared
prediction record and keep all run-specific data outside the handbook.

Route reusable measurement rules to `conventions/`; software mechanisms to
`software/<name>/`; machine-specific behavior to `machines/<name>/`; and validated combinations
to stacks. A campaign result is evidence for a durable proposal only after it passes admission,
privacy, and publishability review.

## Done

Benchmarking is done when the frozen contract and environment are recorded; the required
correctness checks and repetitions are complete; exact artifact checks have no unresolved
missing or unexpected entries; warm, setup, recurring, and excluded costs are distinguished;
accepted runs have observed ledgers; any production projection is separate and states its
recurrence model; prediction misses and uncertainty are explained; and the result answers the
declared comparison or workflow-cost question without claiming beyond the measured scope. Any
adaptive follow-up requires an explicit transition to tuning, performance, debugging, or
production mode.
