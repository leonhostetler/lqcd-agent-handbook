# LQCD Agent Handbook — Roadmap

**Status:** Slices 1 through 3 are accepted. Slice 0c is accepted: its full cold-session
matrix, including both Claude cases, has passed. Slice 4 remains in progress. The
operator-directed solver import through Stage 5 is published; solver-import Stage 6 is
indefinitely deferred while split-grid deflated CG remains in development, testing, and
tuning.

**NEXT ACTION:** Complete Slice 4's remaining scheduler-placement, capture, and
budget-ledger work, then run its cold-session acceptance test.

This document owns mutable build state, acceptance evidence, pending decisions, and the single next action.

<a id="current-slice-state"></a>
## Current slice state

Slice 0 was committed and published at `1352ba5`. Slice 0b was committed and published at
`b06c7d1` on 2026-08-15, and the zero-argument startup repair was committed and published
at `fa9001a`. Slice 1 began with the Perlmutter machine profile, operational notes, machine
detector, and focused tests committed and published at `b116b8f` on 2026-08-15.

On 2026-08-18 Slice 4 began by defining tuning and benchmarking as consecutive rather than
hybrid modes: tuning adaptively selects a candidate setup, and benchmarking confirms a frozen
candidate and workload. MILC application guides now keep `ks_spectrum`, `ks_measure`,
`ks_imp_rhmc`, and `wilson_flow` input/output and timing semantics out of the software-independent
modes. The `ks_spectrum` guide incorporates screened operational lessons; `ks_measure` and
`ks_imp_rhmc` begin with source-backed structure and retain explicit production-benchmark
coverage gaps. MILC timing instrumentation is required for tuning and benchmarking builds and
normally remains enabled.

On 2026-08-19 the `wilson_flow` guide was reconciled with the implementation now present in
upstream MILC `develop`, replacing its former dependency on a personal `quda_gauge_flow` branch.
A fresh DeltaAI build established a `wilson-flow-quda` MILC profile composed with the existing
QUDA `milc-cg` profile. The first GNU/OpenMP link exposed command-line `LDFLAGS` precedence:
`LDFLAGS=-g` suppressed the Makefile's OpenMP additions, while explicitly retaining
`-fopenmp -lgomp` produced both Luescher and BBB executables. An operator-submitted four-rank,
four-GPU smoke test then reloaded a SciDAC gauge field through QIO and completed two BBB Wilson-
flow steps through QUDA at the intended endpoint. It used `forget`, a fresh tunecache, and one
node; saved/continued fields, CPU/QUDA numerical equivalence, Symanzik flow, multi-node behavior,
and production performance remain outside the validated scope.

Also on 2026-08-18, the shared measurement convention defined one observed workflow-cost ledger
per run and a separate production projection, with explicit timer boundaries, accounting roles,
recurrence scopes, resource cost, and residual rules. The MILC timing guide now treats
`exit - start` as a whole-application cross-check between scheduler elapsed time and
application input-set totals.

The same Slice 4 convention now requires a predeclared expected-artifact manifest, isolated
run-owned outputs, exact missing and unexpected set comparison, and separate structural,
numerical, and scientific validity. The `ks_spectrum` guide specializes the rule for inline and
FNAL correlator output, repeated destinations, grouped meson records, append-only writers, and
writer-error fallback.

The shared running convention is now seeded with compact outcome reconciliation. It combines
scheduler, runtime, application, artifact, and correctness evidence; assigns one of five broad
dispositions; separates disposition from causal attribution; and keeps every allocation-
consuming run in the cost ledger while admitting only accepted runs to confirmatory performance
statistics. Scheduler placement, capture, and budget-ledger portions remain Slice 4 work.

Three user-facing contracts remain intentional future additions rather than current handbook
capabilities. Slice 4 will add the append-only submission-budget-ledger format and the shared
prediction schema and capture workflow. Slice 6 will add `modes/performance.md` and the profile-
analysis playbook. Until those files land, their absence does not relax the submission ceiling
or ledger safeguards, and startup must report that performance mode has no recorded conventions.

Also on 2026-08-19, the public-source foundation of Slice 5 was pulled forward without changing
the current Slice 4 next action. The MILC HISQ catalog records the 24 isospin-symmetric ensembles
documented in arXiv:1712.09262, source-attested suffix-free ensemble names, mass-independent
`p4s` spacings, and published pion characteristics. Operator-selected physical-mass defaults
resolve unqualified spacing references; stream suffixes remain subordinate to ensemble identity,
and the 0.03 fm group remains explicitly without a physical-mass default.

Later on 2026-08-19, the operator approved making the staged QUDA solver import the current next
action while Slice 4 remains unfinished. Three source-backed overview atoms now distinguish the
actual MILC-facing implementations: parity-normal-equation native CG, the same native CG with an
attached eigensolver deflation space, and a full-system outer GCR solve with a multigrid
preconditioner. They record operator contracts, setup and reuse state, build gates, cost
components, suitability and disqualifiers, dominant memory objects, runtime confirmation, and
exact-current limitations. No private-corpus timings, crossovers, fitted memory constants, run
paths, or ensemble-specific optima were admitted. The later capability audit keeps compiled
features distinct from the behavior each stack actually exercised.

On 2026-08-20 the operator locked complete test builds as the handbook default. A QUDA
multigrid build had explicitly overridden QUDA's upstream all-tests defaults to `OFF`, so a
required validation executable was absent after three allocation-limited build attempts. The
shared build playbook now requires an explicit operator instruction before reducing the compiled
test set, while allowing the executed validation subset to remain focused. The QUDA profile and
reproduction commands now keep `QUDA_BUILD_ALL_TESTS` and `QUDA_INSTALL_ALL_TESTS` enabled, and a
regression test enforces the policy. Existing QUDA stack cost records remain historical: their
scope now states that the measured builds predated this policy and compiled focused tests
separately.

Later on 2026-08-20, the operator-submitted Perlmutter run established the first
`mg-staggered` stack. QUDA
`b6998853f6b605e22d67ea2ddfa3cab0d752679a` on `develop` used CUDA 13.2,
`sm_80`, staggered operators, GCR-MG, the MILC and QDP interfaces, QMP, and QIO.
The install completed across three resumable one-hour `gpu-a100-40` allocation attempts;
the final build command took 40m08.88s. Because the historical cache excluded the complete
test suite, `staggered_invert_test` was built separately; the current reproduction profile
keeps all tests enabled, and the historical cost is not an all-tests estimate. A four-rank
native QUDA run completed an optimized-KD-to-aggregation hierarchy on a
`16 x 16 x 16 x 32` synthetic unit-gauge asqtad system. MG setup took 273.019s, the
outer GCR solve took 18 iterations and 3.74901s, and QUDA and host checks agreed on an
L2 relative residual of `7.260597e-07` against a `1e-6` request. The fresh-tunecache
run validates only this native hierarchy on the 40 GB A100 node type; it is neither a
linked MILC validation nor benchmark evidence.

The subsequent Stage-2 audit records deflated CG as a compiled capability of both QUDA
profiles. At the observed MILC revision, `WANT_FN_CG_GPU` forces `WANT_EIG_GPU`, so the
composed `ks-spectrum-hisq-quda` profile also compiles native-CG deflation. All nine
eigensolver-enabled stacks now bound that broader profile claim: four native QUDA CG stacks
and four linked MILC stacks exercised plain CG only, while the included `mg-staggered` stack
exercised GCR-MG only. No current stack validates a deflated solve. The native MG stack closes
the earlier source-only gap for its exact Perlmutter test path, but it does not establish a
linked MILC MG application stack.

Stage 3 adds a cross-solver selection leaf and a solver-tuning playbook. They distinguish
linked-application, native-harness-only, and compiled-only evidence; gate mathematical
compatibility, feasibility, correctness, and runtime proof before performance; and evaluate
`C_s(N) = I_s + N R_s` only over the legal compatible-reuse scope. Setup-dominated, mixed,
and throughput-dominated regimes come from measured workload crossovers rather than fixed
corpus thresholds. The import admits no private timing, crossover, fitted-memory, run-path,
ensemble-optimum, or campaign-forensics value.

Stage 4 adds a shared staggered-memory leaf and two deterministic command-line tools while
preserving the evidence boundary in their interfaces. Source-exact modes reproduce current
native field allocation and QUDA transfer block adjustment. Separately labelled corpus
modes admit the Perlmutter A100 plain-CG, retained-deflation, communication-pool,
page-locked-host, and four-level MG high-water calibrations. Agent-loaded text carries
only short scope caveats; detailed fit populations, errors, support sets, and historical
changes live beside the constants in the Python calculator. Its public path targets
current QUDA only. The MG estimate remains a maximum over allocation phases, and capacity
output is advisory rather than a guaranteed fit.

The same calculator exposes two- and three-level hierarchies, MG precision, and the fitted
workspace/copy controls as explicitly unvalidated what-if modes. These modes emit loud
warnings and never inherit the four-level error statistics. Its preferred global-geometry
path derives local dimensions and partitioning, applies QUDA block adjustment, and passes
the effective hierarchy directly to the model. `mg-search` exhaustively enumerates every
rank-grid factorization below an exclusive node bound and classifies each source-valid
decomposition against a named machine advisory; it does not select only one cube-like
layout.

The decomposition tool keeps source errors independent from an opt-in empirical screen.
That screen reports the provisional `V3 >= 10000` and coarsest-cell aspect `<= 1.5`
heuristics mined from four ensembles; it cannot turn either threshold into a QUDA legality
rule. The source audit also corrects the deeper aggregate-space bound: current MILC's
coarse `ColorSpinorField` has `Ncolor = nvec_1` and `Nspin = 2`, so the next transfer
bounds `nvec_2` by `nvec_1*b2`, not by the coarse-gauge color `2*nvec_1`. No existing
corpus configuration is close to that bound. Raw run paths, job identifiers, accounts,
and allocation data remain outside the public repository.

Stage 5 admits the operator-approved dimensionless hierarchy and eigensolver-quality
class as a public calibration manifest plus four staggered-MG action leaves. They keep
source constraints separate from a named Perlmutter A100 retrospective calibration;
define `nu3 = nvec_3/V3`; publish the
coarse-spectrum fit only with its population, error, mass/`nu3` envelope, and `nvec_2`
confound; and make setup-cap ratio, filter margin, worst-vector residual, and asymmetric
TRLM restart behavior the diagnostic feedback. The tuning leaf orders source, memory,
setup, eigensolver, workload, and correctness gates. A deflation schedule is derived
from matched setup and recurring measurements and stored as `nu3(m)`, never copied as a
bare-mass table.

A cold-reader review then made the import independently usable without the source
corpus: it added the advisory-specific calibration populations and literal mass
convention, the hierarchy/index/tool crosswalk, raw-log observable extraction rules,
explicit build-capability status, defined MMA, working-directory-independent commands,
and unambiguous memory evidence and headroom labels.

The same stage admits the matched MRHS validation class. A narrow `mrhs-cg-delta`
command implements the current unsplit double/half MATPC/direct-PC CG device increment
from active batch width and labels its three-cell validation scope. The memory leaf also
records a source-derived four-level MG marginal field slope and the historical width-2
to width-3 validation, while an unexplained width-activation term deliberately blocks an
absolute MRHS-MG calculator. Numerical solver timing and crossover values remain outside
the public handbook; only their target-workload measurement procedure is admitted.

The exact Stage 5 change was published as
`d8af6bb8d4e1f227b47aaa923c93edda76f4c803`. Solver-import Stage 6, split-grid deflated
CG, is indefinitely deferred while its execution path remains in development, testing,
and tuning. No composed-strategy guidance is admitted until implementation and validation
evidence exist.

On 2026-08-15 the operator explicitly pulled the session-logging adapter forward from
Slice 7 as Slice 0c. It adds a shared startup check and non-blocking offer, frontend-specific
Claude and Codex loggers, an offer-only user-config installer, manifest validation, and
focused tests. The remaining Slice-7 enforcement and capture mechanisms stay deferred.

Also on 2026-08-15, a hands-on Perlmutter build established the first QUDA stack. QUDA
`7733f60bb744204576f82574ece8d8bd454fbcfd` on `develop` was configured for CUDA 12.9,
`sm_80`, staggered CG, the MILC and QDP interfaces, QMP, and QIO, with multigrid disabled.
The final login-node rebuild used eight-way parallelism and completed in 9m14.68s. An
operator-submitted four-GPU run on `gpu-a100-40` passed staggered dslash comparison,
double-precision CG residual verification, and double- and single-precision QIO write/read
tests. This validates QUDA's native tests with the MILC interface compiled; it does not yet
validate a linked MILC executable.

On 2026-08-17 the second QUDA stack was built and run on Frontier. QUDA
`7733f60bb744204576f82574ece8d8bd454fbcfd` on `develop` used ROCm 7.1.1, HIP 7.1.52802,
`gfx90a`, Cray MPICH 9.1.0, and the same `milc-cg` profile. Its clean four-way login-node
build and install completed in 14m10.22s. An operator-submitted eight-rank run on
`gpu-mi250x` passed staggered dslash comparison, double-precision CG true-residual
verification, and double- and single-precision QIO write/read checks. The run used a fresh
tunecache and `QUDA_ENABLE_P2P=0`; it is correctness rather than benchmark evidence, and no
linked MILC executable was run. The first submission also exposed a workflow defect:
Slurm inherited the handbook submission directory. The reproduction notes now pin both
`--chdir` and `--output` to the working project so scheduler output cannot land in the
handbook merely because the operator submitted from there.

Also on 2026-08-17, the Frontier half of Slice 3 built and ran the first composed MILC
application stack. MILC `6b9b8a06eec5746187bbfd197eac2629ab8d8e72` on `develop` built
`ks_spectrum_hisq` against the validated QUDA `milc-cg` installation in a fresh disposable
checkout. The single-job login-node build completed in 25.97s. An operator-submitted
eight-rank run on one `gpu-mi250x` node completed its application payload, constructed HISQ
links through QUDA, and produced the expected correlator structure. All 24 QUDA CG solves
reported convergence and their maximum true residual remained below the requested
`1e-8`. The outer wrapper then false-failed because it required positive MILC `total_iters`;
at this MILC commit that local counter is returned without being incremented even though
QUDA reports the real iterations. The stack therefore records the application payload and
wrapper outcomes separately and accepts the numerical run. QIO was linked but not exercised
by the warm-gauge application sample, P2P remained disabled, and the fresh tunecache makes
the run correctness rather than benchmark evidence. Slice 3 remains in progress until the
corresponding Perlmutter MILC stack is built and validated.

Later on 2026-08-17, the Perlmutter half of Slice 3 built and ran the corresponding MILC
application stack. A full-history MILC checkout at
`6b9b8a06eec5746187bbfd197eac2629ab8d8e72` on `develop` built `ks_spectrum_hisq`
against the validated Perlmutter QUDA `milc-cg` installation. The fresh single-job
login-node build completed in 41.16s. An operator-submitted four-rank run on one
`gpu-a100-40` node completed its application payload, exercised P2P, constructed HISQ
links through QUDA, and produced the expected correlator structure. All 24 QUDA CG solves
reported convergence and their maximum true residual remained below the requested `1e-8`.
The outer harness then false-failed because its HISQ marker pattern omitted punctuation and
intervening fields present in the literal output; payload and wrapper outcomes are recorded
separately. QIO was linked but not exercised by the warm-gauge sample, and the fresh
tunecache makes the run correctness rather than benchmark evidence.

Also on 2026-08-17, DeltaAI became the first post-slice machine onboarded under the
Slice 2 schema. Its documentation-backed profile records the four-way NVIDIA GH200 node,
shared-node accounting, Slurm partitions, storage choices, Cray build environment, and
public login aliases. Detection recognizes the DeltaAI login nodes without conflating
them with Delta.

Later on 2026-08-17, the first DeltaAI software stack was built and run. QUDA
`b6998853f6b605e22d67ea2ddfa3cab0d752679a` on `develop` used CUDA 12.9.41, `sm_90`,
Cray MPICH 9.0.1, and the `milc-cg` profile. Its clean eight-way login-node build and
install completed in 7m50.59s. An operator-submitted four-rank run on one `gpu-gh200` node
in `ghx4-interactive` passed staggered dslash comparison, double-precision CG L2-residual
verification, and double- and single-precision QIO write/read checks. The run populated a
fresh tunecache and emitted a tuning-candidate regression warning, so it is correctness
rather than benchmark evidence. The MILC interface was compiled, but no MILC executable
was linked or run.

The same developer session advanced the machine schema to version 2 and made documented
`sizing.installed_nodes` mandatory for every node type. Perlmutter now distinguishes its
CPU, 40 GB A100, and 80 GB A100 inventories; Frontier and DeltaAI record their respective
accelerator-node inventories. These values are upper-bound planning context, not live
scheduler capacity.

On 2026-08-21 a cold-start routing audit aligned the shared playbook with the existing
architecture contract. Startup now invokes `tools/detect-machine.sh` directly, opens no
machine profile or stack when detection returns `unknown`, waits for the declared work mode
before loading Tier-1 context, and restricts known-machine resolution to the one matching
profile and that machine's stack candidates. Full `ARCHITECTURE.md` and `ROADMAP.md` loading
in developer mode remains intentional even when no immediate edit is planned.

Later on 2026-08-21, a live user-mode tuning session exposed an intake-scope defect: a
repository privacy screen was mistakenly applied to ordinary working-directory planning.
User mode retains its unique-file `inbox/` capability, while both user- and developer-mode
guidance now screen only the exact material proposed for the handbook. Startup classifies
pending intake structurally without treating that classification as clearance, and Tier-0
routing plus a focused regression protect working-project evidence from handbook screening.

On 2026-08-22, a live Codex tuning session exposed a task-time routing defect:
orientation loaded Tier 1, but a later solver-specific campaign summary and an explanation
of coarsest-grid deflator density did not trigger the indexed staggered-multigrid Tier-2
leaves until operator correction. Tier 0 now requires a routing checkpoint before substantive
LQCD analysis or action, tuning mode invokes the solver-tuning playbook for solver-specific
analysis, and that playbook maps task signals to the smallest relevant leaves without making
skill installation a prerequisite.

On 2026-08-28 a Perlmutter developer session found that the mandatory pre-commit validator
could not run at all. `tools/select-python` scans `PATH` only, and the sole candidate there,
the distribution `python3.11`, carries PyYAML but not `jsonschema`; the unversioned `python3`
is 3.6.15. Session logging was unaffected because its requirements are PyYAML plus stdlib
`tomllib`, so the defect was invisible until the validator was invoked. The no-module rule
turned out to be scoped to output integrity for the JSON-parsed session-logging checker
rather than to interpreter selection generally, so `run-validator` now passes
`--allow-module-load` and the dispatcher discovers module-provided interpreters from the
module system, in its existing version-preference order, probing each with the caller's own
requirements. No module name enters the tool. With the dispatcher's existing NERSC PyMon
suppression the preferred `python/3.11-24.1.0` probes cleanly and is selected, and the
validator returns identical results under 3.11, 3.12, and 3.14. Rejected candidates are now
reported with the specific reason rather than discarded, because a silent scan cannot
distinguish a missing package from a too-old interpreter.

Latest automated evidence:

- `python3 tools/validate-knowledge.py` in the Python 3.11 validation environment: twenty-six
  schema objects valid, forty-seven provenance records complete, four generated indices current,
  sixteen pre-existing P2 advisories, two frontend adapters and six session-logging assets
  valid, 207 long-document references resolved, no deny-list match, and Tier 0 at
  5,219/6,144 bytes;
- `python3 -m unittest discover -s tests -v`: all 142 checks pass, including detector-first
  bounded startup routing, task-time solver routing, the bounded native staggered-MG stack,
  and focused solver-import, memory/decomposition, and cold-reader interface regressions;
- `bash -n tools/lqcd-claude tools/lqcd-codex tools/install-codex-skills
  tools/detect-machine.sh tools/log-session-claude.sh` and the working-project Frontier and DeltaAI
  validation scripts, Python compilation of the validator, indexer, and Slice 2 and Slice 3 tests,
  `python3 tools/sync-agent-entrypoints.py --check`, `tools/build-index.py --check`, and
  `git diff --check` complete cleanly.

Accepted on 2026-08-15 by operator report: the Claude launcher in user mode, the Claude
launcher in developer mode, Claude invoked without the launcher, the Codex launcher in user
mode, the Codex launcher in developer mode, and the Codex user skill invoked without the
launcher/bootstrap all behaved as their acceptance cases require.

The first Claude user-mode attempt on 2026-08-15 opened an idle prompt because the launcher
loaded passive instructions but supplied no initial turn. Both launchers now inject the same
manifest-declared startup prompt only when called with zero arguments. The rerun and both
other Claude cases were accepted.

The first Codex launcher user-mode attempt on 2026-08-15 stopped before startup because the
launcher passed `--add-dir`, which Codex treats as a request for another writable root and
the effective permissions rejected. The Codex adapter now relies only on its additive
absolute-path instruction pointer and does not widen or override the caller's permissions.
The repaired launcher rerun and both other Codex cases were accepted on 2026-08-15.

A later Perlmutter Codex startup found that `tools/check-session-logging.py` was invoked by
the system `python3` (3.6.15), which cannot parse its future-annotations import. A Python
3.11 module runs the validator and focused Slice 1 tests, but loading that environment also
injects MUNGE diagnostics into several session-logging subprocess outputs. The shared
interpreter dispatcher prefers a compatible versioned command without loading a module,
and the Codex installer pins the selected executable. A later full-suite rerun exposed a
second edge: NERSC PyMon samples nondeterministically at interpreter exit, so a clean probe
could still be followed by MUNGE text appended to checker JSON. The dispatcher now disables
that monitor for its child process before both probe and execution; a forced-monitoring
regression covers the contract.

On 2026-08-17 the operator reported both remaining Claude cold-session cases accepted:
the logger-absent case, in which orientation offers installation without blocking or
adding a second mandatory question, and the install-accepted case, in which existing
settings survive and the next turn creates and updates a mode-`0600` log. Slice 0c is
accepted; its full cold-session matrix has now passed on both frontends. The
slice-boundary reread found routing unambiguous and Tier 0 unchanged at 2,908/6,144
bytes.

On 2026-08-17, a cold Perlmutter Codex startup exercised Slice 0c's current-logger path
through the interpreter dispatcher. Orientation reported the configuration as current
without offering reinstallation, and the trusted Stop hook produced a launch-directory
log at mode `0600`. Only metadata was inspected; the protected session log was not read.
This accepts the current-logger matrix case, not the four absent/install cases.

Also on 2026-08-17, the operator reported that the first cold Frontier Codex session began
with the logger absent. Orientation offered installation without blocking or adding a
second mandatory question, and the operator accepted the offer. This accepts the Codex
logger-absent matrix case. Later that day, the operator reported the separate Codex
install-accepted case accepted and verified: existing hooks survived, the exact Stop hook
was reviewed and trusted through `/hooks`, and subsequent turns created and updated a
mode-`0600` log. The agent did not read the protected session log.

The same cold Codex developer-mode session reproduced the recorded Slice 1 stack without
operator re-teaching. A full-history checkout detached at the tested QUDA commit configured
and installed the recorded `milc-cg` profile with eight-way parallelism in 9m34.91s, then
built the three focused validation executables. An operator-submitted four-rank, four-GPU
run on `gpu-a100-40` completed successfully: all ranks saw all four 40 GB A100 devices,
the dslash and true-residual CG checks reproduced the stack results, and double- and
single-precision QIO returned status 0. The fresh tunecache makes this validation rather
than benchmark evidence. Slice 1 is accepted; linked MILC execution remains outside its
demonstrated scope. The slice-boundary reread found routing unchanged and Tier 0 within
its declared budget.

A cold Perlmutter Codex developer-mode session completed the recorded Slice 3 work without
operator re-teaching. It cloned the recorded MILC default branch with full history, found
the tip identical to the Frontier-tested commit, composed the `ks-spectrum-hisq-quda`
profile with the validated local QUDA stack, and built the application in a disposable
checkout. An operator-submitted four-rank run confirmed four 40 GB A100 devices and
all-device visibility, completed the application payload, exercised the P2P-enabled path,
ran HISQ link construction through QUDA, converged all 24 solves below `1e-8`, and produced
the complete correlator structure. The batch wrapper's post-run literal-marker defect did
not overwrite the successful payload result. Slice 3 is accepted. The slice-boundary
reread found routing unambiguous and Tier 0 unchanged at 2,908/6,144 bytes.

A cold Frontier Codex developer-mode session reproduced the recorded Slice 2 stack without
operator re-teaching. The existing clean QUDA checkout at the tested commit configured and
installed the `milc-cg` profile in a new build directory with four-way parallelism in
13m28.75s, then built the three focused validation executables. An operator-submitted
eight-rank run on one `gpu-mi250x` node completed successfully: telemetry enumerated all
eight 64 GiB MI250X GCDs, every rank retained all-device visibility, the staggered dslash
check reproduced the recorded deviations, double-precision CG converged in 182 iterations
with a true residual below `1e-6`, and double- and single-precision QIO returned status 0.
The fresh tunecache and P2P-disabled path make this validation rather than benchmark
evidence; linked MILC execution remains outside the demonstrated scope. Slice 2 is
accepted. The slice-boundary reread found routing unchanged and Tier 0 at 2,908/6,144
bytes.

<a id="build-order"></a>
## 9. Build order

Each slice has a **cold-session acceptance test**: a fresh agent, started through the
frontend launcher and given only the task, completes it without the operator re-teaching
anything. That test is the deliverable, not the file count.

### Slice 0 — rules and skeleton *(small; slice 1 writes YAML that needs a schema)*
`CLAUDE.md`, `INDEX.md`, **`ARCHITECTURE.md` + `ROADMAP.md`** (this document, split and
privacy-screened per [§plan-ships-with-handbook](ARCHITECTURE.md#plan-ships-with-handbook)), `handbook.yaml` (`phase: bootstrap`), `README.md`, `PRIVACY.md`,
`conventions/orientation.md`, **`modes/{user,developer}.md`**,
`schemas/{machine,project}.schema.json`, `tools/validate-knowledge.py`,
`inbox/proposals/` and `inbox/rejections/`, **`.claude/skills/lqcd-start-session/`
+ `playbooks/start-session.md`**, the launcher script of [§loading-chain](ARCHITECTURE.md#loading-chain), and
**`.gitignore` carrying `session_*.log`** ([§session-logging](ARCHITECTURE.md#session-logging)) — which must land in the *first* commit,
since developer-mode sessions run inside the repo and start dropping transcripts
immediately.

The Slice 0 validator scope is deliberately smaller than the completed contract in
[§validator-checks](ARCHITECTURE.md#validator-checks): schema meta-validation and explicit
bindings for `machine.yaml` and `project.yaml`; Markdown provenance, evidence placement, and
`review_by`; the privacy deny-list; long-document references; and Tier-0 budgets. Complete
`observed_on` semantics and the P2 restated-value heuristic are deferred below.

`modes/developer.md` is written **first**, before any content exists to govern — it is what
governs every subsequent slice, and writing it last would mean slices 1–4 were built
without it.

*Accept:* seven checks. A session started **through the launcher with no opening instruction
at all** orients itself — Tier 0 is in context and `/lqcd-start-session` is available. It
**detects machine and software rather than asking**, reports what it found, asks only for
the work mode ([§work-mode-currency](ARCHITECTURE.md#work-mode-currency)) before doing anything, and defaults
to user mode when the handbook mode is not stated. Tier 0 is under 6 KB. A cold
developer-mode session reads `ARCHITECTURE.md` + `ROADMAP.md` unprompted and can state the
next action, while a cold user-mode session opens neither. And **a session started
*without* the launcher — bare `claude --add-dir`, so skills load but `CLAUDE.md` does not —
is detected and reported by `lqcd-start-session` rather than proceeding unrestricted**
(trap T2). The final two check handbook location ([§locating-handbook](ARCHITECTURE.md#locating-handbook)): the launcher **fails with an
actionable message when `LQCD_HANDBOOK` is unset**, and `lqcd-start-session` validates the
handbook by content rather than by path. Verify here whether the invoked skill's own
location is recoverable — that decides whether the divergence check is exact or heuristic.

<a id="codex-frontend"></a>
### Slice 0b — agent-neutral frontends

This compatibility slice establishes one handbook behavior behind Claude Code and Codex:

- canonical Tier 0 is `AGENTS.md`; `CLAUDE.md` is an exact generated mirror enforced by
  `tools/sync-agent-entrypoints.py` and the validator;
- `handbook.yaml` declares the canonical entrypoint, mirrors, common launcher markers, and
  both frontend adapters, plus the shared zero-argument startup prompt;
- `playbooks/start-session.md` owns shared behavior, while
  `start-session-{claude,codex}.md` own only complete-loading preflights;
- matching `.claude/skills/` and `.agents/skills/` adapters remain thin;
- `tools/lqcd-claude` and `tools/lqcd-codex` preserve the caller's working directory and
  project instructions, and inject the shared startup prompt when no caller arguments are
  present. Codex uses additive `developer_instructions`, never `model_instructions_file`,
  and does not request an additional writable root or override the caller's permissions;
- `tools/install-codex-skills` optionally exposes the Codex skill through a conflict-safe,
  idempotent user symlink with documented duplicate-discovery and relocation tradeoffs. The
  launcher does not depend on installation.

*Automated acceptance:* the validator rejects frontend-manifest and entrypoint drift;
mirror synchronization is checkable and repairable; both launchers fail actionably without
`LQCD_HANDBOOK`; wrapper tests verify forwarded arguments, common and frontend markers,
shared zero-argument prompting, preserved working directory, and Codex's additive bootstrap;
the Codex wrapper test also rejects `--add-dir` and `--sandbox`. Installer tests cover first
install, idempotence, and conflict refusal.

**Deferred skill-installation portability:** First define the supported platform and Codex-surface
matrix, then replace the Unix-only optional symlink installer with a manifest-driven,
conflict-safe implementation. Preserve `$HOME/.agents/skills` as the Codex user scope;
evaluate managed-copy and symlink modes; preflight every target; never overwrite unmanaged
paths; and document relocation, update, and stale-install behavior. The handbook launcher
and Tier-0 routing must remain fully functional without skill installation. Acceptance
requires filesystem tests plus real Codex discovery checks on every supported Linux/HPC,
macOS, and Windows/WSL environment; unsupported combinations must be explicit.

*Cold-session acceptance matrix:*

| Frontend/case | Expected behavior | State |
|---|---|---|
| Claude launcher, user mode | Tier 0 and shared startup load; only work mode is asked | accepted 2026-08-15 |
| Claude launcher, developer mode | Architecture and roadmap load after explicit declaration | accepted 2026-08-15 |
| Codex launcher, user mode in a project with `AGENTS.md` | Project instructions remain active; Tier 0 and shared startup load | accepted 2026-08-15 |
| Codex launcher, developer mode | Same developer gate and orientation report as Claude | accepted 2026-08-15 |
| Claude without launcher | Partial loading is reported and work stops | accepted 2026-08-15 |
| Codex user skill explicitly invoked without launcher/bootstrap | Skill preflight reports partial loading and work stops | accepted 2026-08-15 |

All six cold cases are recorded and accepted. Functional parity means
the orientation, safeguards, routing, and stop conditions match; the frontend-specific
loading mechanism is allowed to differ.

### Slice 0c — user-wide session logging adapters

Pull only the already-designed session-logging mechanism forward from Slice 7:
`playbooks/session-logging.md`,
`tools/{check-session-logging.py,install-session-logging.py,session_logging.py,
log-session-claude.sh,log-session-codex.py}`, the detect-and-offer step in
`playbooks/start-session.md`, manifest/validator bindings, and focused tests.

The contract is shared and installation is frontend-specific. Startup checks after
freshness, reports `enabled`, `configured`, `missing`, `stale`, or `broken`, and
includes a non-blocking offer for repairable states without adding a second mandatory
question. Installation is never automatic: explicit consent precedes any user-config
write, existing hooks are preserved, changed files are backed up, Claude reloads hooks,
and Codex requires review and trust through `/hooks`.

*Automated acceptance:* both loggers retain user/assistant text while excluding tool I/O,
pin output to the launch directory, and write atomically at mode `0600`; checker fixtures
cover absent, current, stale, disabled, duplicate, JSON, and TOML states; installer
fixtures cover idempotence, backups, unrelated-hook preservation, malformed-config refusal,
and Claude-to-Codex replacement; the validator rejects missing or non-executable declared
assets.

*Cold-session acceptance matrix:*

| Frontend/case | Expected behavior | State |
|---|---|---|
| Claude, logger absent | Orientation offers installation without blocking or a second mandatory question | accepted 2026-08-17 (operator report) |
| Claude, install accepted | Existing settings survive; reload plus next turn creates and updates a mode-600 log | accepted 2026-08-17 (operator report) |
| Codex, logger absent | Orientation offers installation without blocking or a second mandatory question | accepted 2026-08-17 (Frontier, operator report) |
| Codex, install accepted | Existing hooks survive; `/hooks` trust plus next turn creates and updates a mode-600 log | accepted 2026-08-17 (operator report) |
| Either frontend, logger current | Orientation reports current state and does not offer reinstallation | accepted 2026-08-17 (Codex) |

### Slice 1 — the vertical slice: build QUDA on Perlmutter
`machines/perlmutter/{machine.yaml,notes.md}`, `software/quda/{project.yaml,README.md,
build.md}`, matching `.claude/skills/lqcd-build-stack/` and
`.agents/skills/lqcd-build-stack/` adapters + `playbooks/build-lqcd-stack.md`,
`tools/detect-machine.sh`, and **the first stack record**,
`machines/perlmutter/stacks/quda-cuda<v>-<profile>-2026q3/stack.yaml` — written as the
natural output of the build that actually succeeded.

**`software/quda/build-profiles.yaml` lands here too, with exactly one profile in it** — the
one this build used ([§build-profiles](ARCHITECTURE.md#build-profiles)). A stack references a profile, so
slice 1 cannot produce a well-formed stack without it. One entry, not a taxonomy: the second
profile is written when a second build needs it.

**`stacks/` gets no schema in this slice, deliberately.** A schema written from one instance
encodes Perlmutter's accidents as universals, and the first CUDA/ROCm divergence is exactly
where that breaks. Capture whatever this build genuinely needed as free-form YAML; the
schema is written in slice 2 from two data points.

Validator acceptance expands here: exercise the existing machine and project bindings on
their first instances, define complete `observed_on` semantics from the first real machine
and software facts, and implement that completeness check. `stack.yaml` and
`build-profiles.yaml` are explicit schema-free bootstrap exceptions: the stack exception
ends in slice 2 and the build-profile exception in slice 3.

*Accept:* a cold session builds QUDA correctly on Perlmutter with no re-teaching, and the
stack record it produces is sufficient for a later session to reproduce that build without
re-deriving anything.

*State:* accepted 2026-08-17.

### Slice 2 — second machine, same software: QUDA on Frontier
`machines/frontier/` including its first stack, plus **`schemas/stack.schema.json` and its
validator binding, now written from two instances rather than one.**

Also **`tools/build-index.py`**, and the [§indexing](ARCHITECTURE.md#indexing) decision it was waiting on: flat file table
or grouped by object. Two machines is the smallest content that makes the difference legible.

Two systems also make drifting restatements possible for the first time. Implement the P2
restated-value heuristic here, with advisory diagnostics and focused tests.

This is the real test of P3. **If adding Frontier forces an edit to
`playbooks/build-lqcd-stack.md`, machine knowledge has leaked into the task layer** — fix
the factoring before proceeding. Expect HIP/ROCm to stress it hardest, and expect the stack
record to be where the divergence actually shows up: a schema that survives both a CUDA and
a ROCm stack without optional-field sprawl is the thing being validated here.

*State:* accepted 2026-08-17. The shared build playbook required no machine-specific edit.
Domain indices are grouped by scoped object; the stack schema is bound to both CUDA and
HIP instances; and the P2 restatement heuristic is advisory with focused tests.

#### Machine onboarding order, and the one piece of insurance it needs

`[operator]` Live allocations: Perlmutter, Frontier, Aurora, Vista, DeltaAI, Big Red 200,
possibly more. Most used: **Perlmutter, Frontier, DeltaAI.** New systems will arrive.

Machines after Frontier are **not slices** — they are onboarded when needed. The order is
**Frontier → DeltaAI → Aurora**, and the reasoning is worth recording because the obvious
alternative looks better than it is:

- **Frontier second** breaks the vendor axis (AMD/HIP) while holding Slurm fixed. That
  isolates one cause, and it is the divergence most likely to have been silently baked into
  slice 1's free-form stack YAML as a false universal.
- **DeltaAI third** is deliberately the *easy* machine. NVIDIA and Slurm again, closest to
  Perlmutter, so it needs the least new knowledge — which is exactly what makes it the
  acceptance test for "I want to be able to add systems as they come along." An easy
  machine should be cheap; if it is not, the schema is wrong. That signal is only clean on
  a machine with nothing else going on.
- **Aurora later.** It is the most instructive single machine — Intel/SYCL *and* PBS, both
  axes at once — and for that reason the worst slice-2 candidate: two simultaneous causes,
  the least mature QUDA support of the three, and a real chance of stalling on a build
  problem that teaches nothing about knowledge structure. Scheduled where a hard machine
  can be absorbed, and flagged in advance as the one that may force a schema revision, so
  that revision is budgeted rather than a surprise.

This order also has the property that the three most-used machines are covered first, so
the handbook becomes useful in practice at the earliest point.

**The insurance:** three consecutive Slurm machines will encode Slurm as *structure* rather
than as a *value*, and Aurora then pays for it. Cheap fix, from slice 2: write
`machine.yaml`'s scheduler block as **discriminated on `type:`** — `{type: slurm, ...}` —
so that PBS arrives as a new value in an existing shape. The point is not to model PBS
correctly before seeing it; it is to ensure the shape has somewhere to put a second
scheduler. The same applies to `accelerator.vendor`, which Frontier exercises directly.

### Slice 3 — second software: MILC on both machines
`software/milc/`, including the QUDA-interface linkage — the first place where two project
profiles must compose. Adds `software/{qmp,qio}/` as dependencies, plus
`schemas/build-profiles.schema.json` and its validator binding, now derived from profiles
in two software contexts.

**State:** Accepted 2026-08-17. The Frontier and Perlmutter `ks_spectrum_hisq` stacks,
composed MILC and QUDA profiles, QMP and QIO project records, profile schema, validator
binding, and focused tests are recorded from their one-node application validations.

### Slice 4 — modes, benchmarking, and the prediction loop
All five `modes/*.md`, `conventions/{running,measurement}.md`,
`playbooks/{run-benchmark,capture-learning}.md`, `schemas/prediction.schema.json`,
the **budget-ledger format** of [§budget-rule](ARCHITECTURE.md#budget-rule) (append-only, debit-at-submit),
`tools/{extract-milc-timings.py,summarize-slurm-job.py,collect-environment.sh}`.
MILC-specific application semantics live under `software/milc/applications/`, with shared
build-time instrumentation guidance in `software/milc/timing.md`; neither is duplicated in the
generic modes or conventions.
Admit `memory_model.py` and `check_decomposition.py` from validated source versions after
screening the exact proposed handbook additions.

**Remaining future additions:** the submission-budget-ledger format, prediction schema,
prediction/capture playbooks and tooling, and the unfinished scheduler-placement guidance. The
current modes describe the semantic fields for local records but do not constitute the promised
shared formats.

Slice 4 must also make scheduler placement explicit in `conventions/running.md` and
`modes/debugging.md`. Before every submission, assess whether the job is appropriate for
debug/interactive placement by comparing its purpose, node count, walltime, and concurrency
against the selected machine profile's policy. When appropriate, prefer that partition or
QOS because its shorter queue waits give debugging and other short jobs faster turnaround.
Debugging mode makes the suitability check mandatory, not selection of the
debug/interactive class. The submission plan records the suitability decision, selected
class, and reason. Machine profiles remain canonical for names and limits, and this
directive never bypasses site policy or the explicit campaign budget rule.

*Accept:* a benchmarking session predicts runtime and memory before submitting, writes the
record **into the working directory**, and files the comparison — and a deliberately stale
fact gets caught by its metric's tolerance ([§tolerances](ARCHITECTURE.md#tolerances)) while ordinary fabric noise does not
trigger a false alarm.

### Slice 5 — software-local solvers and ensembles *(the mining slice; [§developer-mode-spec](ARCHITECTURE.md#developer-mode-spec) governs it)*
`software/<name>/solvers/` seeded from screened, transferable findings in the source tuning corpus;
`ensembles/milc-hisq.yaml`, plus `schemas/ensemble.schema.json` and its validator binding.
Publishability is settled **per class during the import**
([§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)), so the slice is no longer gated on a single up-front decision.

**State:** The public-source ensemble catalog, schema, validator binding, naming rule, and
spacing-default convention are prepared independently of the private tuning corpus. The solver
batch now includes source-backed staggered CG, deflated-CG, and multigrid overviews; audited
compiled-versus-runtime capability coverage; linked-application plain-CG and bounded native-MG
evidence; cross-solver selection and tuning procedures; and the staged memory/accounting
tools. Deflated-CG and linked MILC MG runtime validation, ensemble-scoped operational
imports, and the slice acceptance checks remain pending. A mechanistic MRHS memory model
is also an explicit future obligation: observed increments may guide its design but may
not be promoted as a transferable capacity formula without allocation-lifetime analysis
and validation across MRHS widths.

This is the slice where the admission test earns its keep. Run it strictly — stage
extractions **in the working directory beside the source corpus**, assign each candidate a
**scope** and a **durability** verdict
([§admission-test](ARCHITECTURE.md#admission-test)), admit one at a time, and record every rejection as its own file under
`inbox/rejections/` with which test it failed. Expect a wide spread of scopes: universal measurement hygiene, software × solver
cost structure, QUDA-scoped bugs pinned to commit ranges, and a substantial body of
ensemble-scoped parameter knowledge — **all admissible**, each filed where only the sessions
that need it will load it.

*Accept:* three checks. "Which solver stack for ensemble X on machine Y at N solves per
mass" is answered from the handbook alone, with regime and solve count stated. **Every
admitted fact carries a `scope:`, no admitted fact is scoped to an episode, and every
solver fact is filed beneath its software implementation.** And a
tuning session on an ensemble *not* in the corpus loads no ensemble-scoped material at all —
that is the check that narrow knowledge was filed rather than inlined.

### Slice 6 — performance analysis
`modes/performance.md`, `playbooks/analyze-profile.md`, harvested from the operator's PerfAdvisor
working tree with the exact proposed handbook additions screened at intake.

**Future addition:** `performance` is already a valid mode name for startup routing, but its mode
document and analysis playbook have not landed. Startup therefore reports the bootstrap limitation
and uses no unrecorded performance conventions when that mode is selected.

### Slice 7 — automation and enforcement
`tools/log-session-*.{sh,py}`, the offer-only installer, and the detect-and-offer check
landed early in Slice 0c ([§session-logging](ARCHITECTURE.md#session-logging)). Slice 7 retains
knowledge-capture hooks and the user-mode write guard.
**The `.gitignore` entry that logging makes necessary does not wait for this slice** — the
hazard exists from the first developer-mode session, so it lands in slice 0.

**All three need frontend-specific installers, not only repo files.** Hooks and subagents
are not activated merely by adding the handbook ([§loading-invariants](ARCHITECTURE.md#loading-invariants)), so anything enforcing rather than instructing has to be written into user settings by offer-only installers and versioned here separately from the knowledge. Revisit the loading decision at this point too — a plugin would carry hooks
and agents natively, and by now there is usage data to judge whether that is worth the
install step per machine.

---

<a id="open-questions"></a>
## 10. Open questions for the operator

Nothing here blocks Slice 0b acceptance. New questions land in this section as they arise.

---

<a id="deferred-decisions"></a>
## 11. Deferred decisions

Parked deliberately, each with the **trigger** that should un-park it rather than a slice
number. A deferred decision is only safe when the interim behaviour is conservative; that
column is the test. On the move into the repo ([§plan-ships-with-handbook](ARCHITECTURE.md#plan-ships-with-handbook)) this section travels with `ROADMAP.md`.

| Decision | Interim behaviour | Un-park when |
|---|---|---|
| **Enforcement of the job-submission budget** — agent instruction, a `lqcd-submit` wrapper, or a hook | [§budget-rule](ARCHITECTURE.md#budget-rule)'s default: **no budget stated ⇒ the agent prepares the job and hands the operator the submit command.** Zero machinery, cannot overspend | The first time an agent should submit **unattended**. Until then the conservative default costs nothing and the right mechanism is not yet obvious |
| **Enforcement of user-mode write protection** — instruction, file permissions, worktree, or a `PreToolUse` hook | The P6 instruction of [§handbook-modes](ARCHITECTURE.md#handbook-modes), plus `lqcd-start-session` reporting an unclean handbook tree at session start so a stray edit surfaces the same day | The repo stops changing daily. Read-only permissions fight developer mode, which is *most* sessions during bootstrap. Hooks need an installer regardless ([§loading-invariants](ARCHITECTURE.md#loading-invariants)), so this rides with slice 7 |
| **Sub-file provenance** — claim IDs with metadata stored separately, versus file-level frontmatter | File-level frontmatter ([§knowledge-atom](ARCHITECTURE.md#knowledge-atom)), and **knowledge files are kept small and atomic** so it stays adequate | A file starts accumulating claims from materially different dates, versions or evidence kinds. Not needed at slice 0, and the machinery costs more than the problem until then |
| **Whether any part of the handbook should be served over MCP** rather than as files, skills and scripts | **None.** Knowledge stays as markdown and YAML read directly; procedures stay as skills plus `tools/` scripts. Works on every machine with no runtime | Any of three: (a) the handbook needs to reach data **too large to commit** — a cross-machine run database is plausible, and would be a *separate* server the handbook talks to, not handbook infrastructure; (b) something genuinely **remote** becomes necessary, such as live job status across machines from one session; (c) slice 6 finds **PerfAdvisor is already service-shaped**, making this a question about preserving an existing shape rather than adding one |
| **Whether session logging should also archive the raw transcript JSONL** for full provenance, tool I/O included ([§session-logging](ARCHITECTURE.md#session-logging)) | **Prose-only.** The shipped logger stays as the operator wrote it; the JSONL under `~/.claude/projects/` is the true last resort where it survives | The prose record proves insufficient to reconstruct an episode the operator needed back — or a machine rebuild/scratch purge destroys a JSONL that was wanted. Note the cost before adopting: much larger files in the working directory, and a far bigger privacy surface, since the JSONL contains every file read and every command run |
| **Whether the handbook is measurably cheaper than the rediscovery it replaces** | No measurement. Cold-session tests stay qualitative | The handbook becomes big enough to feel slow to navigate. **If implemented, it is the lightweight version** (below) — not an A/B harness |
| **Optional follow-up mining from the `ks_spectrum` benchmark corpus** — detailed memory/telemetry analysis, numerical reference-correlator comparison, and broader gauge-I/O-path validation | The admitted guidance requires ordinary resource evidence and structural, numerical, and scientific checks, but claims no telemetry-analysis method, reference-correlator comparison recipe, or preferred gauge-I/O path. Gauge loading is only a candidate tuning dimension when it is a non-negligible production cost | Revisit an item independently when a concrete tuning or validation decision needs it and suitably scoped evidence is available. These investigations are optional; none blocks Slice 4 acceptance |


### Notes on deferred decisions


**On that last one, the form is already decided even though the timing is not.** A formal
"same task with and without the handbook" comparison is not affordable or trustworthy here:
it is n=1 per arm against a stochastic agent, where two handbook-free runs of the same build
can differ twofold depending on which wrong path is explored first, and the second arm is
not cold anyway — whoever ran the first one now knows things they leak into the second
through better prompting. It would produce noise that reads like data, which is worse than
no number.

The lightweight version instead, if and when it is wanted:

- **Operator interventions per cold-session test** — how many times the operator had to
  correct or supply something. Countable, low-variance, and it *is* the thing the project
  exists to reduce. Meaningful at n=1 because zero is zero; it needs no control arm.
- **Re-teaching defects** — each time a session had to be told something the handbook
  already contains. Not a metric but a **defect report**: it names a file that failed to be
  found or failed to be right, and it is actionable immediately.
- **Tier-1 bytes actually loaded before useful work began** — the leading indicator of
  navigation overhead, and cheap to observe.

**And a standing rule that needs no harness:** if a session spends more turns navigating the
handbook than doing the task, cut something. The mechanism count in this plan may go **down**
as well as up; [§developer-obligations](ARCHITECTURE.md#developer-obligations)'s slice-boundary review is the place to propose removals, and a
deleted mechanism is a legitimate slice outcome.

The asymmetry that orders the first two: a bad handbook commit costs a `git revert` and is
visible in `git status`; a runaway `sbatch` loop costs allocation that cannot be recovered.
Enforcement effort belongs where the mistake is irreversible.

**On MCP specifically, three arguments that look strong and are not** — recorded so they are
not re-derived:

- **It does not dodge the loading problem, it inherits it.** Skills are the only thing that
  crosses the `--add-dir` boundary ([§session-start](ARCHITECTURE.md#session-start)). MCP servers are
  configured in a project-scoped `.mcp.json` — discovered in the *working* directory, not
  the handbook — or in user settings. A `.mcp.json` shipped in the repo would not load, for
  the same reason hooks do not, and needs the same slice-7 installer.
- **A typed `submit_job` tool would not enforce the budget.** This is the tempting one,
  since it looks like a clean fourth option beside instruction/wrapper/hook. **The agent
  still has Bash**, so an MCP tool is a convention at high cost, not a control. Only
  intercepting the call — a `PreToolUse` hook — actually enforces, which is why the hook
  remains the live candidate.
- **Cross-machine queries are already solved, asynchronously and better.** The handbook is a
  git repo cloned everywhere; [§freshness-model](ARCHITECTURE.md#freshness-model) is exactly this problem
  solved offline. Replacing it with a live network path is a downgrade on login nodes behind
  MFA and restricted egress.

And the cost side is not theoretical: an MCP server is a process with a runtime, on six
heterogeneous login nodes with differing Python/Node environments, module systems, egress
rules and the CPU limits [§build-profiles](ARCHITECTURE.md#build-profiles) already establishes are real.
Markdown plus bash has none of those failure modes. On this fleet that is worth more than
elegance.

---
