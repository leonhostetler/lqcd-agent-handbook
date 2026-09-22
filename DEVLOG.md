# LQCD Agent Handbook — Development Log

This file is the episode record: session narratives, defect forensics, measured figures and
acceptance evidence. It is developer-mode material and is **not** read at session start —
`ARCHITECTURE.md` §3.1 and `modes/developer.md` both say so. Open it by name when you need
the evidence behind a decision recorded in `ARCHITECTURE.md`, or behind a status recorded in
`ROADMAP.md`.

Entries are appended, never rewritten. Nothing here is a rule. A rule lives in
`ARCHITECTURE.md`, in a knowledge leaf, or in a control; an entry found to carry one has
been filed in the wrong place, and the fix is to move the rule, not to cite this file.

The sections below were moved verbatim from `ROADMAP.md` on 2026-09-16. Source order is
preserved rather than re-sorted by date, so the move is checkable byte for byte against the
commit that made it.

<a id="defect-repairs-and-imports"></a>
## Defect repairs and imports

**The capture gap is closed (2026-09-16).** `conventions/profile-capture.md` now carries the
planning-time recipe — what to request from Nsight Systems, rocprofv3 and rocprof-sys, the
`nsys export --type sqlite` step every tool here requires, the per-rank naming rule, and what no
tracer setting supplies — and the machine profiles carry profiler availability as an optional
`profilers:` block, present on Perlmutter and Frontier and deliberately absent on DeltaAI, where
it was never established. The import also found that the tool's own rocpd re-profile commands
produced an unreadable artifact; see the eighth-session entry below, which records that, the
per-rank constraint behind the naming rule, and one newly owed item in `diagnostics.py`.

**The change-proposal harness landed 2026-09-15** as `tools/run-change-proposal`, discharging
the owed item recorded below. `modes/developer.md` now names it as the pre-commit step, with
`run-validator` kept for the narrower case. It reports what each step *examined*, not only what
it concluded, because the two failures it exists for are silent ones.

**Host-sample naming landed 2026-09-15** as `gpu-profile-summary.py host-samples`, with the
reading in `conventions/profile-metrics.md`, the step in `playbooks/analyze-profile.md` and the
routing in `modes/performance.md`. It closes the gap both other window tools leave: they *size*
unattributed host time and cannot name it, because it is unattributed exactly when no traced
call is in progress. `nsys.py` reported `has_cpu_samples=False` unconditionally until this
change, so the one instrument that can name host compute declared itself absent on every
capture that had it.

**Transfer residency, `gap-detail` and `--phase N` landed 2026-09-16**, from a seventh-session
analysis of the same B200 capture. All three crossed
[§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s counter in that one session and were closed in
it. The first is the one that mattered: `MemcpyRow` read `copyKind` and `bytes` only, so a
device-to-device row **averaged an unprefetched-managed population against an ordinary one** and
reported a single unremarkable rate — the tool was not silent on
`software/quda/internals/managed-memory.md`'s discriminator, it concealed it, and `memcpy` now
splits by `srcKind`/`dstKind` and names a split above an order of magnitude itself. `gap-detail`
names the individual structural stalls inside an idle residual, from **merged** kernel intervals
rather than consecutive launches, so it does not inherit the hand query's unstated
no-concurrency precondition. `--phase N` removes the `--start-ns`/`--end-ns` transcription that
`phase_segmentation` had only made *detectable*, and resolves through `detect_phases` rather
than a full summary — the same waste `cmd_phases` was corrected for. Readings in
`conventions/profile-metrics.md` and the QUDA leaf, steps in `playbooks/analyze-profile.md`,
routing in `modes/performance.md`. Full suite 396 passing, validator unchanged at 17 P2
advisories and Tier 0 5844/6144 bytes.

**Launch-geometry extraction for the tunecache-warmth gate landed 2026-09-15** as
`gpu-profile-summary.py launch-geometry`, discharging the item owed on the next QUDA
performance session. `KernelRow` now carries the six extents on both formats, with
`ProfileCapabilities.has_launch_geometry` and an `available: False` path; the reading is in
`software/quda/profiling.md` and the vendor-convention rule in `conventions/profile-metrics.md`.
**The parallel rank loader is deliberately not on this list** — three observations crossed a counter built for silent arithmetic errors, and a
serial loader is slow rather than wrong, so it is ordinary ergonomics and not a defect-rate
obligation. Then Slice 4's remaining scheduler-placement, capture, and budget-ledger work.

This document owns mutable build state, acceptance evidence, pending decisions, and the single next action.

On 2026-08-28 two session-start defects were repaired without changing the Slice 4 next
action. An agent sandbox on Perlmutter wrote placeholders over ten tooling paths under the
handbook root; Git reported them as `??` and stage 2 stopped orientation on an apparently
dirty tree. Those paths are now ignored in `.gitignore` and `ARCHITECTURE.md` §4.3 gained
rule 3a. The rule records why the fix is a declaration rather than a test on the placeholder:
the same sandbox represented the same paths first as character devices owned by `nobody` and
then as empty unwritable regular files owned by the operator, so ownership, size, mode, and
file type were all unreliable. Separately, that session could not fetch upstream because the
sandbox `HOME` is read-only, so rule 6 and the playbook now prescribe one
`git -c credential.helper=` retry and an explicit stop when freshness stays unverified. The
eleven tests that copy the repository were failing on the same placeholders and now route
their copies through `tests/support.py`.

On 2026-08-29 a routing defect was repaired without changing the Slice 4 next action. An agent
wrote and submitted three batch scripts without loading `conventions/batch-scripts.md`, although
the Tier-0 pointer and `conventions/INDEX.md` were both correct. `ARCHITECTURE.md` §7.8 was
amended to record that a Tier-0 pointer alone does not achieve "every time", and the trigger was
added to the four `modes/*.md` routing sections, `playbooks/tune-solver.md`, and
`playbooks/start-session.md` stage 6.

On 2026-09-02 the staggered memory-model toolchain was repaired without changing the Slice 4
next action. Three defects were fixed, all found by comparing predictions with measured QUDA
counters on an independent 0.09-fm target. (1) `mg-fit` reported a total that is flat in
`nvec_3` whenever the winning allocation phase does not carry the coarsest eigenspace, which
includes the page's own 0.04-fm example at the strongest prediction tier; it now reports
`detail.deflation_enters_total` and warns. (2) `quda_staggered_geometry.py` omitted QUDA's
asqtad long-link rule, so a level-1 aggregation extent below three was reported
`source_status: pass` although QUDA aborts on it; `--allow-truncation` exposes the truncated
space deliberately. (3) Neither tool checked QUDA's MMA coarse-gauge-colour restriction, under
which `2*nvec_(L-1)` must be one of 12, 48, 64, 128, 192 — a constraint on a derived quantity
that a legal, compiled `nvec` can still violate at runtime.

**No fitted constant was changed and no predicted value moved.** The empirical accuracy
observations from that target are recorded on the memory page as scoped observations, never as
correction factors: their population is one workspace, one build, and one ensemble, and the
corpus that justifies the published errors is not in this repository, so a refit could not be
re-validated — only asserted. A new regression test pins the documented 0.04-fm and 0.06-fm
examples so a later model change cannot move them silently. One pre-existing fixture in
`tests/test_slice5_memory.py` asserted that a hierarchy with a level-1 extent of two was
source-valid; it was corrected to a legal geometry, preserving the test's arbitrary-lattice
intent.

Later on 2026-09-02 the remaining deferred feedback from the same 0.09-fm campaign was
triaged and admitted, again without changing the Slice 4 next action. Eight items landed
across five fact classes: coarse-deflation solver support and its silent-disable branch, the
`deflate_a_min` convergence gate with a two-method probe recipe and its measured
low-bias limitation, and `deflate_block_size` (`coarse-deflation.md`); the CA coarse solver's
`Nkrylov == maxiter` mode selection (`staggered-multigrid.md`) and an eigensolve triage gate
that reads restart count and delivered prefix before anything else (`diagnostics.md`); the
`CONGRAD5` timer-line asymmetry between MILC's CG and MG inverters, with the rule to build
comparisons per delivered propagator (`staggered-inverter-types.md`, cross-referenced from
`staggered-solver-selection.md`), plus the tunecache `aux`-field inference trap and
warmth-is-per-shape-and-colour (`autotuning.md`); Slurm host-selection options
(`scheduler-surfaces.yaml`, with `schemas/scheduler-surface.schema.json` extended to admit
them as optional); and a cost model ranks candidates but cannot promote one
(`staggered-multigrid/tuning.md` and `playbooks/tune-solver.md`).

Four candidates were **rejected or folded** rather than admitted, and the reasons are the
reusable part: a strong-scaling figure from one ensemble at two node counts stayed an
episode; a duplicate timer-line entry was folded into the inverter-types fact so there is one
canonical home; a sandbox subprocess defect was not LQCD knowledge at all; and a proposal to
give the work modes a periodic "what should now be a tool" checkpoint is a design change to
`ARCHITECTURE.md` §7.5d's scope rather than a fact, so it is left for its own decision.
Empirical items carry explicit labels — the `deflate_block_size` note is mechanism-plus-caveat
on one uncontrolled observation, and the coarse-deflation silent-disable branch is
source-derived and has never been observed at runtime.

A review of that batch then corrected two placement and naming defects, and both are worth
recording because they are the same class of error. **First, a campaign-local extractor field
name reached the handbook**: an actionable check was written against `deflating_vectors_applied`,
which exists only in the working project's own tooling, so a reader had no way to obtain it. It is
now expressed as the literal `Deflating <N> ...` lines QUDA emits, including the distinction that
the two wordings are **not** the same quantity. A campaign cost-model symbol reached
`staggered-multigrid/tuning.md` the same way and now uses the handbook's own `V3`. Every
identifier in the batch was then re-checked against QUDA/MILC source or an existing handbook
definition.

**Second, general eigensolver knowledge had been filed under staggered multigrid.** The
completion-only printing rule, the deflation-application log forms, the filter-window
convergence gate, the two window-establishment methods, and the block-variant diagnostics apply
to every QUDA eigensolver caller, so they moved to `software/quda/solvers/eigensolver.md`, with
`staggered-multigrid/coarse-deflation.md` reduced to what is specific to the coarsest level of an
MG hierarchy plus pointers. That move exposed a naming hazard worth its own section: **the same
parameter has a different name at every entry point.** The MILC multigrid parameter file's
`deflate_` prefix is not a QUDA field prefix, the standalone and MG-embedded test CLIs use
`--eig-*` and `--mg-eig-*`, and MILC's non-multigrid deflation path uses unprefixed members with
an `n_ev_deflate` that has no `deflate_`-prefixed counterpart at all. `eigensolver.md` now carries
the mapping table, and guidance written in one spelling must be translated before it is applied
through another.

A second review pass then found that **`V3` was ambiguous and the handbook contradicted itself
about it.** The MG overview defined `V2`/`V3` as executed-level indices while
`hierarchy-and-setup.md` defined `V3` as "the global coarsest-grid extents" — readings that
coincide only at four levels, since a three-level hierarchy's coarsest grid is level 2. The
decomposition tool had it right all along, emitting role-based `coarsest_global_volume` and
`coarsest_vector_density` always and the numbered aliases `V3_global`/`nu3` only at four levels,
so the prose was corrected to match the tool: role-based names first, `V3`/`nu3` labelled as the
four-level spellings with the three-level mapping given, and an explicit warning that every
numerical band on those pages was fitted at four levels.

The same pass admitted the **coarse/fine work ratio** the campaign had been screening on,
`(coarsest global volume x (2*nvec_(L-1))^2) / (fine global volume x N_c^2)`, at `mechanism`
tier in `staggered-multigrid/tuning.md`. It is dimensionless and reads as how many full
fine-operator applications one coarsest apply costs, and its mechanism — the coarse operator is
dense in coarse colour, so aggregation cuts sites while raising per-site work, making **depth
rather than block size** the lever — is source-backed. It carries a mandatory proxy caveat: an
uninstrumented `volume x dof^2` count, never calibrated against a profiler, excluding smoother,
transfer, communication and per-level efficiency, and therefore sufficient to order candidates
but never to certify one or to be converted into a time. That caveat is the reason it sits
beside, not instead of, the rule that a cost model cannot promote a candidate.

On 2026-09-02 the last deferred item from the 0.09-fm campaign was admitted, as two rules
rather than one, without changing the Slice 4 next action. **Ordering** went into
`conventions/running.md`: run the contract-governed extractor first and analyse its output,
because a hand pass performed first makes the *uncontracted* reading decisive and produces a
defect class — transcription between adjacent records, aggregation over the wrong subset — that
an executed contract does not. **The periodic audit** became `conventions/repeated-work.md`,
with the checkpoint named in the `Done` and `Tools and routing` sections of all four work-mode
documents, so a work-mode change fires it mechanically rather than by memory.

The design point worth keeping is why it is a checkpoint and not a trigger. Every other routing
obligation attaches to an event; this one cannot, because the set of repeated actions is not
visible when a campaign starts and changes shape as its phase changes. Study or phase closure
and work-mode change are the recurring anchors, chosen because they are exactly when that set
has just shifted. `ARCHITECTURE.md` §7.5d was clarified rather than widened: it governs
authoring time, the new convention governs working practice, and merging them would conflate a
carrying-cost argument with a defect-rate argument.

The Tier-0 standing rule that already preferred a tool to prose now also names the recurring
trigger and points at the leaf, following §7.8's resolution of the same tension: Tier 0
guarantees "every time" and cannot afford the content, the leaf affords the content and needs
a trigger. That cost 129 bytes, leaving the entrypoint at 4866 of 5120 and Tier 0 at 5512 of
6144; `CLAUDE.md` was re-mirrored byte-for-byte, which the frontend preflight checks.

The convention ships with a counterweight, because the rule otherwise manufactures its own
failure mode. The same campaign recorded a wrapper script that had never worked going
undetected for a day, and a verification harness that reported success while modifying nothing
after its negative control was silently dropped in a rewrite. So a new tool is not trusted on a
passing run: it must be perturbed until it fails, a no-op negative test is vacuous, and
"leave it manual, reviewed at the next checkpoint" is a recorded outcome rather than a failure.

Later on 2026-09-02 the first linked-MILC staggered-multigrid stack was admitted, without
changing the Slice 4 next action. It closes the gap this document recorded on 2026-08-20: the
native `mg-staggered` stack established QUDA's own GCR-MG path but not a linked MILC MG
application stack. A new `ks-spectrum-hisq-quda-mg` MILC profile was required first, because a
stack references a profile and the existing `ks-spectrum-hisq-quda` compiles no MG dispatch —
`MULTIGRID` is a `KSCGMULTI` preprocessor define in the Make path, not a `WANT_*` switch, so a
build that sets every `WANT_*` variable correctly still silently takes the CG fallback.

The stack records a deliberate deviation rather than a correction. Its composed QUDA
installation predates the 2026-08-20 all-tests policy and was configured with
`QUDA_BUILD_ALL_TESTS` and `QUDA_INSTALL_ALL_TESTS` `OFF`; every other option matches the
`mg-staggered` profile. Rebuilding to conform would produce a different installation that the
validation does not cover, and — because `ks_spectrum_hisq` bakes `DT_RPATH` rather than
`DT_RUNPATH` with an absolute path to the QUDA it linked against — the executable would have to
be relinked, not redirected by environment. That linkage fact is recorded in the stack notes
because it governs how two QUDA configurations can coexist at all.

Three limits are recorded in `scope_limits` rather than smoothed over: the run loaded stored
near-null and eigenvector sets, so hierarchy setup from scratch is not validated; the tunecache
was warm, so this is not cold-start or benchmark evidence; and the repeatability gate was met
by an operator-accepted determinism observation taken on a different, four-level configuration
rather than by a repeat. No solver timing, iteration count, setup cost, or crossover was
admitted — those remain campaign measurements in the working directory. The recorded build cost
is an instrumented rebuild of the same recipe in a copy of the application directory, narrower
in scope than the sibling `ks-spectrum-hisq-quda` cost because the dependent MILC libraries were
already present; the two figures land within a second of each other while measuring different
work, and the notes say so.

On 2026-09-03 an operator-directed import brought the adjacent 0.09-fm hierarchy campaign's
exportable heuristics in, **without changing the Slice 4 next action**. Twenty-eight of that
campaign's fifty rules are now here; nine more were found already carried, two are partial by
operator decision, one was declined, and ten remain with the campaign awaiting a second
observation. The dedup was the highest-yield part of the exercise: two rules had been
re-derived by the campaign after this handbook already documented them, which is why the
campaign registry now carries an enforced `handbook_status` column.

**Three defects in published leaves were found by the import rather than by review.** A
statement that only `nvec_1` and `nvec_2` select compiled coarse colours is false at three
levels, where `nvec 2` is the coarsest deflation count and must *not* appear in
`QUDA_MULTIGRID_NVEC_LIST` — and the same error appeared twice, in the crosswalk and in the
build requirements. The observable extraction contract keyed its eigenvalue lines to a fixed
`MG level 3` prefix, which silently returns nothing at three levels. And `calibration.md`
asserted a four-spacing corpus including 0.12 fm, where multigrid had never run; the MG
memory fit's declared population repeated the same claim, and neither was guarded by a test.

**Two naming rules were added because the import kept tripping over them.**
[§role-not-index](ARCHITECTURE.md#role-not-index) forbids naming a hierarchy quantity by level index: the
coarsest grid is level 3 at four levels and level 2 at three, so `V3`, `nu3`, `nvec_3` and
`l3_res_max` named a different grid depending on a fact the symbol did not carry. They are
purged in favour of `coarsest_*` role names. The trap worth recording is that the *obvious*
fix is a regression — renaming a quantity does not rescope the band attached to it, so every
band now carries its fitted level count inline and the decomposition tool refuses to evaluate
one off four levels, reporting `evaluated: false` rather than an empty advisory list.
[§reserved-terms](ARCHITECTURE.md#reserved-terms) reserves `configuration` for gauge configurations and
`setup` for a solver setup phase; the parameter set is a `candidate`, and the mode documents'
former "candidate setup" is retired for colliding with the second. Both rules are enforced by
tests, because this document already records that a correctly indexed pointer does not fire at
the moment it applies.

**Two guard tests were failing against reality and were rewritten, not deleted.**
`test_native_mg_validation_is_not_promoted_to_linked_milc` asserted that no stack validated a
linked MILC MG executable — true when written, false once one did — and now asserts the
linked stack's own scope limits instead, which is the overclaim actually available. A second
pinned a claim to comma placement rather than to its content. A third defect class appeared
twice during the work and is worth naming: a negative control that does not perturb anything
proves nothing, and both instances were phrase replacements that silently matched nothing
because the phrase wrapped across a line.

The `test_session_logging.py::test_validator_rejects_missing_declared_logger` failure predates
this work; it was failing at `65652ce` and is unrelated to the import.

On 2026-09-14 the deferred decision that `modes/performance.md` does not exist was closed by its
own stated trigger: a session declared performance mode, orientation reported the mode document
absent, and the work that closes it ran in that session. Two changes landed, in the order
[§developer-obligations](ARCHITECTURE.md#developer-obligations) requires — the authority first,
the tree after.

`ARCHITECTURE.md` gained [§profile-analysis](ARCHITECTURE.md#profile-analysis) and two
locked-decision rows. The question was how to absorb a profile-analysis capability built outside
the handbook as a standalone analyzer with its own model calls, and the answer splits it on what
each half **is**. Deterministic extraction — vendor SQL, string-table joins, concurrency-aware
interval merging, phase segmentation, cross-rank alignment — is code and ships as an offline
tool under [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool). The interpretation contract is
knowledge and ships as leaves. **The handbook does not wrap a second agent**: a session already
is one, and calling another across a network adds a key, a provider, an egress path and a verdict
the session cannot audit — the same reasoning that rejected a served handbook in
[§deferred-decisions](#deferred-decisions).

Two consequences were recorded because neither follows from the decision alone. The extraction
tool **owns the correct aggregations** rather than merely exposing the database, because an
ad-hoc query returns work where the reader wanted elapsed time and the error reads as plausible;
raw query access stays as a read-only, row-capped escape hatch. And a hypothesis **records the
queries its evidence came from**, because the prose session log deliberately omits tool output —
so in the one mode where the queries *are* the evidence, that record is the only durable trace.

The second change separates **diagnosis from search**. Performance mode produces a ranked,
evidenced hypothesis list; applying a change and remeasuring is adaptive search, which is tuning
by the definition [§decisions-operation](ARCHITECTURE.md#decisions-operation) already locks. A
profile-driven optimisation loop therefore crosses a declared mode boundary instead of becoming
a hybrid mode, and the performance → tuning → benchmarking chain gains its first link.

`modes/performance.md` then landed against the specification the deferred row had written in
advance, and that is the part worth keeping: the row named the required sections and the two
cross-cutting triggers before anyone wrote the file, so the file was checkable against it rather
than reviewed on taste. The `conventions/batch-scripts.md` trigger and the
`conventions/repeated-work.md` automation checkpoint now reach all five work modes rather than
four.

The mode's substantive content is what a **tracer** can and cannot establish. Nsight Systems and
ROCm Systems Profiler record API calls, launches, durations, transfers and annotation ranges;
without deliberately collected counters they do not record achieved bandwidth, cache behaviour,
coalescing, or achieved occupancy. Memory-boundedness, occupancy claims, and the health of an
uninstrumented subsystem are therefore questions for a counter-collecting run, never findings
from a trace. That rule is why the source benchmark suite deleted its bandwidth, compute-bound
and occupancy scenarios rather than keeping them, and it transfers as a mode rule rather than as
a benchmark note.

**Nothing measured was admitted.** Kernel timings, call counts and phase breakdowns from the
source working tree are episode tier and stay there; what crossed is metric definitions,
mechanisms, and the capture-hazard class. The QUDA cold-cache reading of duration spread was
deliberately *routed to* rather than stated in the mode document, because it is a software-scoped
fact and belongs in `software/quda/internals/autotuning.md` under its own approval.

Two stale records were found. The automated-evidence block below reported 227 references, 156
checks and Tier 0 at 5,383 bytes, all of which predate HEAD; it is refreshed below. And
`test_validator_rejects_missing_declared_logger`, recorded above as failing at `65652ce`, **passes
at HEAD** — the failure no longer reproduces.

A gap was found and then closed. The validator's reference check resolved only links carrying an
`#anchor`, because `CROSS_LINK_RE` requires both a `#` and a `.md` suffix — so a plain
`](../conventions/foo.md)` link was checked nowhere, as was every link to a schema or a tool.
The existence check already sat in that loop; it simply never saw those links. A
`RELATIVE_LINK_RE` pass now resolves the target of every relative link in every Markdown file,
the long documents included, whose path-style links to leaves that loop had skipped. The
reported count went from 274 to 571.

**It found a committed broken link on its first run**: `staggered-memory.md` pointed at
`../staggered-multigrid.md`, one directory above the file that exists. It had shipped, and a
reader following it got nothing. That is the same defect class as the 2026-09-03 amendment,
which widened this check's *scope* to the task-time surfaces but not its *pattern* — a guard
can be correctly scoped and still blind. Two tests pin the fix: one plants an anchorless broken
link and requires the validator to reject it, and one asserts the reference count stays above
400, because a pass that silently matches nothing is the failure mode this session hit twice
while writing negative controls.

On 2026-09-15 a QUDA performance session on an operator-supplied Blackwell capture provoked
three tooling defects, all repaired without changing the Slice 4 next action. Each was found by
the analysis failing rather than by review, and each had shipped.

**First, the `query` escape hatch advertised two properties it did not have, and named the wrong
hazard.** `ARCHITECTURE.md` §profile-analysis said "read-only, row-capped and interruptible,
because an uncapped scan of a multi-gigabyte profile is the ordinary accident". Measured, a
single scan of a 5,066,637-row event table costs **0.23 s** — scans were never the accident. A
**nested loop** is: no profiler export carries an index on any event table, so a correlated
subquery re-scans the inner table once per outer row. A session query whose CTE SQLite chose to
inline asked for 4.75M x 5.07M row visits to re-derive a 260-row constant; it returned one row,
so the cap bounded nothing, and `cmd_query` passed no `stop_event`, so "interruptible" named a
parameter no caller supplied. It cost 26 minutes and produced nothing. The repair is ordered by
what the failure showed: **planning is free**, so `EXPLAIN QUERY PLAN` runs first and the shape
is refused with the rewrite named, in 0.42 s on the capture that provoked it; `--max-seconds`
(default 120 s) is the backstop for what the plan check cannot size; and the prose in
`ARCHITECTURE.md` and `playbooks/analyze-profile.md` now names the nested loop rather than the
scan. **The guard's own control caught a false positive in it**: a scan under a `MATERIALIZE`
runs once however many correlated steps enclose it, so without stopping the ancestor walk there
the guard refused the very rewrite its error message recommends.

**Second, `cross-rank` computed the diagnostic and discarded it.** On the four-rank capture it
derived "cost at k=5 is 15.8% above optimal k=7 (threshold: 15%)" and reported only "Phase count
differs across ranks", because the failure payload omitted `consensus_note`. The second is a
consequence of the first and reads as a tool limitation rather than as a 0.8-point miss that
`--max-phases` would settle, so the session spent 211 s to be told nothing and then hand-rolled
a four-rank comparison it did not need. The payload now carries `consensus_note` and
`selected_k_by_rank`. **A straggler fixture cannot exercise this path** — stretching kernels
scales a rank's cost curve without changing its shape, so the ranks still agree on k; the new
fixture adds distinct late structure to one rank, which moves its elbow from 4 to 7.

**Third, the per-direction `transfer-overlap` rows invited an addition that is wrong, and
`--table` hid the fix.** Directions run concurrently, so summing `exposed_s` returns work: on the
capture it summed to 66.44 s where the merged union was 48.48 s, a 37% overstatement that reads
as plausible. `conventions/profile-metrics.md` forbade summing *within* a direction and said
nothing about *across* them. The extraction now emits `union`, carrying
`directions_sum_exposed_s` beside `exposed_s` so the gap is visible rather than merely avoided —
and `_render_table` silently dropped every nested object, so the new section was absent from the
output a session actually reads. **A renderer that hides a field is the same defect as a tool
that never computed it**, and the first perturbation written against it was a no-op that
`repeated-work.md` warns about: disabling the dict branch let the value fall through to the
scalar branch and every assertion still passed.

Sixteen controls landed across `tests/test_gpu_profile_query_guard.py` and the two existing
gpu-profile test files; each of the five fixes was reverted in turn and confirmed to break its
control, and the suite stands at 96 tests with no skips.

One knowledge leaf was admitted, `software/quda/internals/managed-memory.md`: QUDA reaches
managed memory by two independent routes and `is_prefetch_enabled()` reads only one of them, so
memory obtained through the MILC-facing `qudaAllocateManaged` entry point can never be
prefetched unless the application also converts every QUDA device allocation to managed. It is
source-derived at `b6998853`, present in both the CUDA and HIP targets, and carries the profile
signature that identifies it — a device-to-device copy far below device bandwidth with
unified-memory migration events inside its interval. `software/quda/profiling.md` points at it
from the symptom. **The measured seconds stay in the working directory**: the leaf records the
mechanism and no figure from the capture.

**Two items came due and were again paid by hand, and neither is now owed differently.**
Launch-geometry extraction for the tunecache-warmth gate was owed "on the next QUDA performance
session"; this was that session, and warmth was established instead from the run-log pair and
the tunecache mtime, which the gate accepts but which is not what was owed. The parallel rank
loader remains deliberately excluded as ergonomics, with one datum added: the serial loader cost
187.4 s across four ranks at ~47 s each, and on this capture the whole of it was spent before a
refusal. That is a worse trade than recorded, not a defect, and reversing the decision is the
operator's call.

**A fourth defect was reported in that session and was not one, which is worth recording
because the correction is the reusable part.** `tools/extract-milc-timings.py` does not exist,
and four documents name it; the session called all four wrong. Only one is. `ARCHITECTURE.md`
§3 opens by declaring itself "the target completed-bootstrap layout, not an inventory of files
currently present", and `ROADMAP.md`'s Slice 4 scope list and its untraced-control rationale
both name the tool as something Slice 4 builds. The single false claim was the word **already**
in the NEXT ACTION block, which turned a deliverable into an existing asset and made the Slice 6
to Slice 4 reassignment read as costless; it is corrected above. An audit of all 67 files named
in §3 found nine absent and four skill directories absent, **every one of them a legitimate
future addition** — which is why no validator check was added: a guard firing nine times on
correct content is the noisy guard [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s
counterweight warns against.

Later on 2026-09-15 the launch-geometry item was delivered, and **both technical claims in the
sentence that scoped it were wrong** — which is the second time in one session that an owed item
was described inaccurately by this document.

It said `KernelRow` carries only `total_threads`, "the six extents being collapsed in `nsys.py`'s
SQL and **absent from rocpd entirely**". The first half was right. The second was not:
`rocpd_kernel_dispatch` declares `workgroup_size_{x,y,z}` and `grid_size_{x,y,z}` `NOT NULL`, and
`rocpd.py` simply never read them. So the `available: False` path is not the rocpd path it was
written to be — rocpd supplies the geometry — and what rocpd actually needed was a
**normalisation**: it records the grid in *work-items* where CUDA records it in blocks, so the
same launch reads 110592 or 864 depending on which backend you ask. Mapping it across raw would
have overstated every extent by the workgroup size, and the resulting numbers are large and
entirely plausible. `available: False` is retained for its real case, an nsys kernel table
without the extent columns, and is what distinguishes a capture that cannot show geometry from
one whose geometry was uniform.

**The reading went wrong twice before it went right, both times caught by running it against a
capture whose warmth was already established by other means.** Version one flagged any kernel
whose `block.x` varied; `advanceBlockDim` steps block.x, so that looked sound, and it reported
25 of 153 kernels of a known-warm capture as swept. Inverting `grid.x = ceil(minThreads/block.x)`
bounds a tune key's problem size from one launch, and grouping on that showed the multi-blas
rows were five *different* vector counts rather than one kernel being swept. Version two grouped
correctly and still flagged 21, because it ignored launch counts: a tuning candidate runs once to
warm up plus `candidate_iter()` timed launches, so a sweep is many geometries with a handful of
launches each, and two geometries with 72 and 24 launches are two call sites. The shipped version
reports `max_block_x_at_one_problem_size` and `min_launches_per_geometry` and **renders no
verdict at all**, because a tune key also carries an `aux` string — policy, carve-out, vector
count — that no kernel name records, so two keys differing only there cannot be told apart in a
profile. The gate remains the session's to apply against the tunecache; what was owed and is now
delivered is the extraction.

Fifteen controls landed in `tests/test_gpu_profile_launch_geometry.py`, including the
vendor-convention one that fails if rocpd's work-item grid is mapped across as workgroups, and
the problem-size grouping perturbed in three directions. Each was reverted in turn and confirmed
to break; the first perturbation written against the grouping was a no-op that collapsed the y/z
bucket while leaving the x clustering to do the work, and a control for a differing z extent was
added because a real capture had one.

The closing automation checkpoint for that session, under
[`conventions/repeated-work.md`](conventions/repeated-work.md), surfaced two candidates and
records a third as already owed.

**A perturbation runner is owed rather than optional.** Confirming that each fix's control
actually fails when the fix is reverted was done by hand across two batches and eleven
reversions, and its failure mode is silent: a vacuous perturbation reports `OK`, which is
indistinguishable from a guard that works. **Two of the eleven were vacuous on the first
attempt** — one disabled a renderer's dict branch and let the value fall through to the scalar
branch below it, and one collapsed a grouping's y/z bucket while the x clustering it was meant
to test still did the work. Both were caught by reading the output rather than by anything that
would catch them next time. A tool taking (fix anchor, replacement, named test) triples and
asserting each replacement breaks its own test is the shape; `repeated-work.md`'s own rule that
a harness which cannot fail is the same defect as a guard that cannot fire is the reason it is
owed.

**Withdrawn 2026-09-16: the tool was already in the tree when this was written.** The shape
named above is a description of `WindowBreakdownControls.perturb`, committed in `c327813` some
two and a half hours before this paragraph landed in `079ff6d`, and copied into two more test
files the same night. This paragraph counted eleven hand reversions and none of the helpers
already performing them. The in-test form is also
better than the runner it asked for — a standalone runner checks once, at authoring time, while
a control carrying its own perturbation re-checks on every suite run, which is the only thing
that would have caught a control going inert *later*. See the ninth-session entry.

**A change-proposal harness qualifies**: overlay a scratch tree, regenerate the indices, run the
validator and the suite, emit a diffstat and a privacy sweep. Performed three times in the
session, fixed at every step, and two of those steps fail quietly — an index left unregenerated
passes the eye, and a skipped privacy sweep produces no output either way.

**Deliberately left manual**: resolving a kernel's template arguments against the revision that
built the binary, which needs the decomposition cross-check and therefore judgement at each step.
**Already owed elsewhere**: MILC run-log timing extraction, which is Slice 4's
`tools/extract-milc-timings.py`.

<a id="build-and-validation-episodes"></a>
## Build and validation episodes

Slice 0 was committed and published at `1352ba5`. Slice 0b was committed and published at
`b06c7d1` on 2026-08-15, and the zero-argument startup repair was committed and published
at `fa9001a`. Slice 1 began with the Perlmutter machine profile, operational notes, machine
detector, and focused tests committed and published at `b116b8f` on 2026-08-15.

On 2026-08-18 Slice 4 began by defining tuning and benchmarking as consecutive rather than
hybrid modes: tuning adaptively selects a candidate, and benchmarking confirms a frozen
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
prediction schema and capture workflow. Slice 6 will add the profile-analysis playbook and the
offline extraction tool. Until those files land, their absence does not relax the submission
ceiling or ledger safeguards. `modes/performance.md` landed on 2026-09-14, so startup no longer
reports performance mode as lacking a mode document; the mode's own limitation paragraph states
which contracts are still outstanding.

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

Also on 2026-08-28, the scheduler submission surface was admitted as a per-type record
rather than a per-machine one. Preparing the machine-profile edit showed that all three
profiled machines are Slurm and their `scheduler:` blocks were byte-identical, so writing
the directive prefix, option names, and job-id variables into each profile would have
restated three dozen values that cannot differ by site. `conventions/scheduler-surfaces.yaml`
now holds one entry per scheduler type, bound to `schemas/scheduler-surface.schema.json`;
machine profiles name their `type` and carry only site-specific fields. Option and variable
names were verified against the installed Slurm manual pages. Perlmutter records
`node_local_tmp_variable: null` from a live check; Frontier and DeltaAI leave it unrecorded
because neither was available to verify, and an unrecorded field obliges a consumer to ask
rather than assume. No machine schema bump was needed: the profiles lost restated fields and
gained only an optional one.

Also on 2026-08-28, `conventions/batch-scripts.md` admitted the operator's batch-script
safety policy, adapted to the handbook's constraints. It is frontend-agnostic, takes every
directive and variable name from the scheduler-type surface record rather than naming a
scheduler, and names no site filesystem variable: a script may reference only what a machine
profile declares. The prohibited-operation list is explicitly non-exhaustive and now includes
truncating redirection, because an agent reading a long specific list infers that absence
means permission; the case that decides the rest is whether the write lands under a named
approved root. The append-only invariant is scoped to inputs and shared data so that it does
not forbid the run-owned tunecache the warm-state contract requires. The leaf also carries the
four pre-writing resolutions, the never-inferred account rule, the ban on nested submission,
and an ordered review gate that puts the irreversible checks first. Tier 0 gains a pointer and
the account rule folded into the existing ceiling safeguard rather than a new bullet.

Also on 2026-08-28, `tools/check-batch-script.py` mechanised the decidable half of the
batch-script convention. It reads directive and option names from the scheduler-type surface
record rather than carrying scheduler knowledge, treats nested submission and destructive
operations as errors, treats missing hardening and unpinned directives as warnings, and
enumerates truncating redirections for the reviewer instead of guessing which are unsafe. It
never prints an account value. Calibration against the working project's two real batch
scripts and its validation driver produced no false errors, and exposed a gap in the surface
record: both scripts declare their account with the short form, so the record now carries
short aliases alongside the long options. The tool is advisory, and its status line names the
approved-root, invoked-program, and intent checks it does not perform.

Two defects surfaced during the batch-script work. `6c8e9f9` split
`select-python` out of the session-logging runner without updating that runner's tests, so
three checks were red for two commits before a bisect found them; the fix landed in
`ee8517d`, and the lesson is that a tool change must run its own tests, not only the
validator. Separately, `.gitignore` covered `session_*.log` but nothing under `.claude/`, so a
developer-mode session whose frontend mounts configuration paths into this repository tripped
its own clean-tree gate and broke eleven tests that copy the tree. Both halves were fixed
on 2026-08-28: the gate half by ignoring the frontend tooling paths, and the copying tests
by routing through `tests/support.py`, since `.gitignore` has no effect on
`shutil.copytree`. That helper repeats the same declaration in executable form and keeps
the handbook-owned `skills/` directories the validator needs.

Latest automated evidence:

- `tools/run-validator`: twenty-nine schema objects valid, fifty-three provenance records
  complete, four generated indices current, sixteen pre-existing P2 advisories, two frontend
  adapters and six session-logging assets valid, 571 references resolved, no
  deny-list match, and Tier 0 at 5,759/6,144 bytes;
- `python3 -m unittest discover -s tests -v`: all 171 checks pass, including detector-first
  bounded startup routing, task-time solver routing, the bounded native staggered-MG stack,
  the batch-script checker and its dispatcher runner, and focused solver-import,
  memory/decomposition, and cold-reader interface regressions;
- `bash -n` over the two launchers, the Codex skill installer, the machine detector, the
  Claude session logger, `select-python`, and all three dispatcher runners; Python compilation
  of the validator, indexer, and batch-script checker;
  `python3 tools/sync-agent-entrypoints.py --check`, `tools/build-index.py --check`, and
  `git diff --check` complete cleanly.

The validator is now invoked through `tools/run-validator` rather than a bare `python3`,
because on a module-based system no interpreter on `PATH` carries `jsonschema`; the runner
discovers one. One caveat on the suite: the 2026-09-14 counts were observed on a workstation
under Python 3.13.9 on `PATH`, which needed no module; earlier counts were taken under 3.11,
3.12 and 3.14 modules with identical results. The eleven errors that used to appear
inside a working tree where an agent frontend has mounted placeholders over `.mcp.json` or
`.claude/` paths were fixed on 2026-08-28.

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

<a id="slice-6-record"></a>
## Slice 6 — performance analysis: acceptance exercises and defect record

*Accept:* three checks, and the two that can fail are the point.

A cold session given only a profile and "find out where the time goes" declares performance
mode, extracts with the tool rather than by querying the database by hand, and produces a
ranked hypothesis record that `tools/hypothesis-record.py` accepts — with no re-teaching, every
figure traceable to a named command, and every quantity the extraction did not emit declared in
`extraction.derived_by_hand` (amended 2026-09-14 with
[§profile-analysis](ARCHITECTURE.md#profile-analysis); the original wording forbade hand-derived
figures outright, which the schema has always permitted).

**An empty `derived_by_hand` is not the criterion, and reading it as one has now cost two
exercises.** The amendment above settled that, and the emptiness reading came back anyway
through the next action and the exercise notes. It is also unreachable: the playbook recommends
comparing a capture against an untraced control run, and such a comparison combines a profile
figure with an application timer, which no subcommand that reads a profiler database can ever
emit. What is required is declaration — and since 2026-09-15 that is **mechanically enforced**
per figure rather than trusted, because it was not: emptying the list while citing hand-derived
figures passed with zero errors until `tools/hypothesis-record.py` learned to read it.

**Cold means the session has no access to a prior analysis *of the capture under test*** — no
conclusions, no figures, no ranked findings, whether beside the profile, in project
instructions, or in session memory. Knowledge of the application, machine and software stack is
**not** contamination: it is the routing the handbook requires, a session cannot be made ignorant
of the software whose leaves it is told to load, and check 3 depends on the opposite case. That
definition separates the second exercise, which read the capture's own conclusions before
extracting anything, from the third, which did not.

**Given a capture lacking the instrumentation its question needs, the session reports the gap
instead of producing hypotheses.** This is the handbook-side analogue of the source suite's
profile-blind property, and it is the check the rest rests on: a confident answer drawn from a
capture that cannot support one is the expensive failure in this mode, it reads exactly like a
good answer, and nothing downstream detects it. A session that names what the capture cannot
observe has passed; one that reasons past the gap has failed regardless of whether its
conclusion happens to be right.

**A performance session on a profile from software with no profiling leaf loads no QUDA-scoped
material at all.** That is the check that software-scoped knowledge was filed rather than
inlined into the mode or the metric convention — the same test Slice 5 applies to
ensemble-scoped material, and it would fail today if the kernel-naming or tunecache facts had
been written into `modes/performance.md` where they would have been convenient.

**A fourth check was specified and removed, 2026-09-15.** It would have re-pointed the source
suite's scored scenarios at a handbook hypothesis record and required a profile-blind control to
score near zero. Three reasons, recorded so it is not re-proposed.

**The five acceptance exercises found more than a score could.** Three guards that could not
fire, three tool defects that were confidently wrong, a tracing effect that inverts the sign of
an A/B, and two claims in `ARCHITECTURE.md` that were never true. A detection rank reports
whether the injected bottleneck was named and says nothing about any of them.

**The profile-blind property is held by the source suite's own scoring tests** — a unit test on
the scorer, not a run against a clean profile, and that suite has no optimal-path control. So
re-pointing the scorer is the only thing that would have put that property at risk.

**And the scored scenarios are synthetic microbenchmarks with injected bottlenecks**, while this
handbook's work is real captures with no ground truth. That suite's own documentation states it
measures recall and not precision; a recall number on those eight is a weak proxy for this
domain.

What replaces it is not another harness.
[§predict-compare-loop](ARCHITECTURE.md#predict-compare-loop) is already the rot detector: a
claimed runtime fraction is a prediction, and a fraction inflated across trials is a defect in
the attribution rule. **The residual is named rather than hidden.**
`tools/hypothesis-record.py` validates form and not truth, and all three grades were taken on
evidence reported by the session under test, so nothing independently checks that a conclusion
is correct. The handbook's answer is use: a leaf that is wrong is caught by the next session
relying on it, which is how every defect this slice recorded was in fact found.

**Why no acceptance exercise found the capture gap.** Check 1 specifies a session *"given only
a profile"*, so every exercise began with a capture already taken. The wording that made the
check tractable is the same wording that excluded the half of performance mode which was never
built. This qualifies no grade — capture was out of scope for all five — but it is the second
time this slice recorded a guard that could not fire, and the first time the guard was an
acceptance criterion rather than a line of code.

*State:* **accepted 2026-09-15** on its three checks. Stages 0, 1 and 2 landed 2026-09-14. Stage 2 ports ingestion, metrics, phase
segmentation, cross-rank alignment and the structural diff for both Nsight Systems and rocpd as
stdlib-only modules — 8,307 lines across 18 files — whose summary output was verified
field-for-field against the source implementation on both formats. Every guard carries a
negative control. Two of those controls initially passed when they should have failed: one
`sed` pattern silently matched nothing, and one perturbation hit a function the assertion did
not route through, so a perturbation is now verified to have landed *and* to have reached the
path under test. Rank loading is serial; the source implementation's worker pool was left out
as a separate change rather than bundled into a port.

Stage 3 landed the same day: `conventions/profile-metrics.md` takes canonical ownership of the
metric definitions and the tracer limits, `playbooks/analyze-profile.md` owns the procedure, and
`schemas/hypothesis.schema.json` fixes the record format. The mode document keeps the one-line
rule and points at the convention rather than restating it, which is the P2 correction Stage 3
existed to make: those definitions had three homes — a prompt string in the source analyzer,
`#:` comments in the ported models, and the mode document — and now have one. Stages 4 and 5
landed the same day as well, as the paragraph above records; **Stage 6 was later
withdrawn with the fourth acceptance check, so Stages 0 through 5 are the whole import.** An
earlier revision of this paragraph said "Stages 4 through 6 remain" while the paragraph above
said Stages 3 through 5 had landed. The two contradicted each other for a day and the stale
NEXT ACTION above was derived from the wrong one; `software/quda/profiling.md`,
`tools/hypothesis-record.py`, `tools/gpu-profile-diff.py` and `modes/tuning.md` settle it.

**Acceptance, first exercised 2026-09-14** on a MILC/QUDA capture from a 32-rank GB200 run. No
check is accepted; two produced defects worth more than a pass would have been.

**Coverage gap closed 2026-09-14** (same day, second change). `tools/gpu-profile-summary.py`
gains `idle-attribution` and `transfer-overlap`, and `conventions/profile-metrics.md` gains the
definitions they emit. Both reuse `merge_intervals`, so neither can drift from `gpu_busy_s`.
Replayed against the capture that exposed the gap, the tool reproduces the hand analysis to
within rounding on every figure — MPI 7.0117 s vs 7.012, host API 2.9781 vs 2.978, OS 0.3888 vs
0.389, residual 8.6969 vs 8.697 — and **corrects one error in it**: the hand pass summed
peer-to-peer transfer durations instead of merging them, overstating the total by 28% (3.560 s
against 2.772 s). The conclusion held, the number did not, and that is the defect class
`conventions/repeated-work.md` predicts for values moved by hand.

Two design corrections came out of building it, both found by running the tool against a real
capture rather than the fixture. **OS-runtime attribution is restricted to threads that drive
the GPU**: unfiltered, a communication progress thread parked in `poll` covered every idle gap
and reported the application as OS-blocked 18.691 s of 18.691 s, against 0.389 s for the thread
actually issuing launches — a wrong answer the tool would have produced confidently, which is
worse than the hand pass it replaces. And **the `--table` renderer silently dropped lists of
strings**, which would have hidden exactly the caveats saying a category was untraced rather
than zero. Four deliberate breakages — dropping the thread filter, reporting an untraced
category as `0.0`, summing categories instead of unioning them, assuming every transfer is
hidden — each fail the control written for them; the degradation control fails on that
breakage alone.

*Check 1 — failed as first exercised, on tool coverage and on the guard behind it. Both repaired
the same day; the check has not been re-run, so it stays unaccepted until a cold session
reaches it.* The session declared the mode
from the skill without re-teaching and produced a ranked record the checker accepts. But the two
aggregations that carried the analysis — decomposing inter-kernel GPU idle into MPI, host-API,
OS and residual, and measuring what fraction of each transfer direction overlaps kernel
execution — have no subcommand, so the session wrote them by hand and read 305k rows through a
direct `sqlite3` connection, bypassing the row cap the escape hatch exists to impose. Stage 2's
own criterion is that subcommands cover every aggregation a session would otherwise recompute by
hand; these were the counter-examples, and closing them is recorded above. Separately, and worse,
**the provenance guard could not fire**: `tools/hypothesis-record.py` read
`if src and queries and ...`, so a record with an empty `queries` list skipped the check
entirely — a record whose every figure was fabricated passed with zero errors. Repaired the same
day with the negative control that reproduces it, per
[`conventions/repeated-work.md`](conventions/repeated-work.md); a guard that cannot fire is the
same defect as a harness that cannot fail.

*Check 2 — not exercised.* The capture supported the hypotheses drawn from it, so the
gap-reporting behaviour was never put under load. One partial signal in its favour: the session's
largest single cost was unattributable without CPU sampling, and it named that missing capture
rather than guessing. One failure against it: the top-ranked hypothesis was *named* for an
attribution the trace cannot make (which side of a host/library boundary the time belongs to)
while carrying `confidence: high`, which is the naming half of reasoning past a gap even though
the body and `refuted_by` hedged correctly. The confidence was corrected to `medium` in the
working-directory record after this paragraph was written; the bottleneck *name* still asserts
the attribution, so the criticism stands on the half that was not repaired. A capture that
genuinely lacks what its question needs is still required before this check can be called.

*Check 3 — not exercised, with positive evidence on the filing question.* The profile was a QUDA
profile, so the negative case remains untested. What it did establish is that the filing is
right: `conventions/profile-metrics.md` is software-neutral throughout, and the facts the session
needed — group by demangled name, what a cold cache does to spread — were in
`software/quda/profiling.md` and nowhere else. One blemish: `modes/performance.md` glosses that
leaf's conclusion ("which records why a cold tunecache inflates all four") rather than only
pointing at it, a second home for a value the leaf owns. Left as-is deliberately; Tier-1 churn
costs more than the duplication does, and `AGENTS.md` has seven bytes of headroom against its
5 KB ceiling, so Tier-0/1 edits are not free.

The session also returned durable residue, admitted the same day: `software/quda/profiling.md`
gains the warm-cache reading of the y block extent — `advanceBlockDim` bounds
`block.y ≤ vector_length_y` and every setter recomputes
`grid.y = ceil(vector_length_y / block.y)`, so `grid.y == 1` makes `block.y` the y problem size
exactly, and a duration spread that is linear in it is batch-size variation rather than any of
the four causes the metric convention lists. Verified against the QUDA revision the leaf already
cites. Its measured numbers stayed in the working directory.

**Second exercise, 2026-09-15**, on the same MILC/QUDA capture. The run does **not** advance any
check, and the reason is itself the finding: the profile sat beside the previous session's
`analysis-notes.md` and hypothesis record, and the session read the notes — which state the
conclusions and the headline figures — before running any extraction. A check that asks what a
cold session produces cannot be run against a capture carrying its own answer key, so the
isolation is now written into the NEXT ACTION above.

What it did establish, narrowly. The two subcommands added the previous day were used *as
subcommands*, and the `query` escape hatch stayed row-capped throughout, so check 1's specific
2026-09-14 failure did not recur. `extraction.derived_by_hand` gained three more entries — noted
at the time as though a non-empty list were itself the failure, which the 2026-09-14 amendment
had already settled it is not. Corrected 2026-09-15 by the third exercise.
And `software/quda/profiling.md`'s warm-cache rule — `grid.y == 1` makes
`block.y` the y problem size — got its first field use and settled the `MultiBlas_` spread as
batch-size variation, which is positive evidence for check 3's filing question on a profile that
still cannot exercise check 3 itself.

*A third coverage defect, found and closed the same day.* `idle-attribution` under-accounted any
window that is mostly not kernel execution, and reported a closed-looking account while doing it.
Idle is measured between kernels, so `kernel_busy + gpu_idle` spans only first-kernel-start to
last-kernel-end; on the capture's 25.881 s startup phase that is 1.286 s, and the tool reported
the split over **5% of the window** with `accounted + residual == idle` balancing exactly and
nothing naming the other 24.594 s. Across the profile the unnamed term totalled 28.249 s, 24.0%
of the run, concentrated in three phases (95.0%, 85.2% and 28.7% of themselves) and negligible
— 0.2% and 0.3% — in the two solve phases where the metric is sound. `conventions/profile-metrics.md`
already documented the exclusion correctly; the tool did not surface it and
`playbooks/analyze-profile.md` asserted that `idle-attribution` is what closes the account. The
knowledge was filed right and did not fire where it was read, which is the failure
`modes/performance.md` names in its own words.

`IdleAttribution` gains `outside_kernel_span_s = window − kernel_busy − gpu_idle` and a caveat
above 10% of the window; the convention gains the window-level identity beside the idle-level
one; the playbook's step 3 closes on the window. Five controls in
`tests/test_gpu_profile_idle_attribution.py`, each paired with the perturbation that must move it
— guard silenced, guard always firing, and the term hardcoded to zero all fail the suite, and a
sub-threshold overhang must *not* warn. Every perturbation asserts it landed, which is the defect
the 2026-09-14 round hit with a `sed` pattern that silently matched nothing. This is the same
class as the OS-thread-filter correction: arithmetically correct, confidently wrong, and worse
than the hand pass it replaces.

*The hand-derivation counter, updated 2026-09-15 by the third exercise.* **The pre-first-kernel
window characterisation has reached three and crossed
[§profile-analysis](ARCHITECTURE.md#profile-analysis)'s "more than twice", so it is now a missing
subcommand rather than a standing practice.** `outside_kernel_span_s` detects the window; what is
still hand work is characterising what lies inside it. The third session binned
`MPI_COLLECTIVES_EVENTS` by wall-clock through the raw-query escape hatch and read application
timers beside it, to establish that 54.3% of a capture lying before the first kernel was one
collective synchronisation per 32 lattice sites. A subcommand owes the binned breakdown of that
window by traced category, so a session is not left composing it from a raw query each time.

Note what the same amendment exempts: the counter now applies only to aggregations over profile
data, because arithmetic that crosses out of the profile can never be emitted by a tool that
reads a profiler database. The window breakdown is squarely inside it and does cross the rule.

*The two that remain at two* — the MPI collective size breakdown that separates fabric latency
from rank skew, and the launch-geometry check for tunecache warmth — are recorded here so the
next occurrence trips the rule instead of being re-litigated. The third session took tunecache
warmth from the tool's own coefficient of variation and from a run-log line rather than from
hand-computed launch geometry, so that one did not advance. The second is the odd one out and
may not need the count: `software/quda/profiling.md` makes it a **mandatory gate** before
reading call counts, launch geometry or duration spread, so every QUDA performance session must
run it, and the
Tier-0 prefer-a-tool rule covers a durable rule that can be executed. It is not a one-line
addition — `KernelRow` carries only `total_threads`, the six extents being collapsed in
`nsys.py`'s SQL and absent from rocpd entirely — so it needs the row type extended, an
`available: False` path for rocpd, and its own change. Deliberately not bundled with the fix
above, per the one-fact-class rule.

**Third exercise, 2026-09-15** (same day, later session), on a MILC/QUDA staggered CG capture
from an 8-rank 2-node A100 run. **The isolation precondition was met for the first time**: the
capture carried no analysis notes and no hypothesis record, and the one non-run file beside it
was a header-only tool log for a different job step containing no conclusions or figures, opened
only after the analysis closed. The session was cold on the *capture* and warm on the
*application*, because the working project's instructions characterise a sibling capture — which
the definition added to the check above settles as not contamination, and which prompted writing
that definition down.

*Check 1 — not accepted, but the criterion was misread rather than unmet.* Every clause the
check states passed: the mode was declared from the skill with no re-teaching, extraction went
through subcommands with two `query` calls that stayed row-capped and read-only, no direct
database connection was opened, and `tools/hypothesis-record.py` accepts the record with bounds
derived rather than asserted. `extraction.derived_by_hand` held five entries, which the session
first reported as a failure — repeating the emptiness reading the 2026-09-14 amendment had
already removed. Four of those five combine a profile figure with an *application run-log*
figure, which the extraction cannot emit by construction.

**What it did find is that the declaration clause had no guard.** Emptying
`extraction.derived_by_hand` while leaving every hand-derived figure cited produced zero errors
from the checker. That is the defect class already recorded twice in this slice — the
`if src and queries` bug in the same tool, and the verification harness that certified the
guards it was built to test. Closed the same day: the schema gains a per-figure `hand_derived`
flag, `tools/hypothesis-record.py` rejects a figure whose `from` is not a command shipped in
`tools/` unless it is flagged, and rejects a flag with no declaration and a declaration covering
no flagged figure. Run against the session's own record the guard produced **20 errors where the
shipped checker produced 0**. Seven controls in `tests/test_hypothesis_record.py`, including the
two that perturb the tool — guard silenced and guard always firing — each asserting the
perturbation landed. The first draft of the silencing control was confounded, failing for a
second reason with the guard disabled, and the suite caught it. The residual is named rather than
hidden: this catches inconsistency, not dishonesty, since a record that flags nothing still
passes.

Also exposed: `schemas/hypothesis.schema.json` described `evidence[].from` as "Subcommand or
query index that produced it", which reads as licensing the locators the checker refuses — the
session's first submission was rejected with 41 provenance errors for writing `"Q4
idle-attribution"` where a command was required. The guard fired loudly and on every offending
figure, which is the Stage 5 repair working. The description now states the exact-match rule.

*Check 2 — still not exercised, and the same naming failure recurred.* The capture answered its
question, so gap-reporting was never put under load. Positive: with no hardware counters the
session declined to classify memory- versus compute-bound and recorded it as a question for a
counter-collecting run, and with host sampling disabled it stated the residual as an upper bound
on host compute rather than a measurement of it. Against it: a hypothesis named its kernels "the
interior dslash", interpreting an enum template argument the session could not resolve — the
QUDA revision was not available locally, and the same record said so. This is the identical
failure the 2026-09-14 exercise recorded, where the repair was to lower a confidence value and
leave the name standing. **Recurrence is why it became a rule**: `software/quda/profiling.md`
gains the section saying an enum template argument is a discriminator and not a name.

*Check 3 — still not exercised, with new positive evidence on filing.* A QUDA profile again, so
the negative case remains untested. New this round:
`software/quda/solvers/staggered-solver-selection.md` had its first field use inside a
*performance* session and changed the answer, turning the obvious recommendation — enable the
deflation the job existed to test — into a measured rejection at a crossover of roughly 104
compatible solves against 6 delivered. Its cost model and its per-delivered-propagator counting
rule are both leaf-resident and neither is inlined in the mode or the metric convention, so the
filing held under a second kind of load. Routing reached it by `load_when` match from
`software/INDEX.md`, not from a pointer in `modes/performance.md`, which is the behaviour check 3
exists to protect.

*Durable residue, admitted the same day.* The largest item closes a gap the handbook had nowhere:
**nothing anywhere said a traced run differs from an untraced one.** A tracer is charged per
intercepted event, so its cost tracks traced-call density rather than elapsed time and falls
unevenly — measured against an untraced control performing identical iteration counts at 1.91x
end to end, 2.80x on an MPI-dense file read, 1.55x on the solves, and 1.05x and 0.97x on the two
GPU-dense stages making few host calls. Read profile-only, that run spent 46% of its solve phase
GPU-idle; against the control, nearer 17%. `PROFILER_OVERHEAD` reported 1.458 s against a
measured +47.5 s and is therefore not the measurement. `conventions/profile-capture.md` takes the
procedure, `conventions/profile-metrics.md` the reading rule, and `playbooks/analyze-profile.md`
step 2 makes it a step. **The control is recommended and the labelling required** — a control
cannot be added to a capture already taken, which is most of them, but saying that no control
exists costs nothing. Carried as `[inferred]` from mechanism with the magnitudes as
illustration: two variables besides the tracer moved in the comparison, a cold autotune cache and
a cold page cache, both penalising the control, so the figures bound the inflation from below
rather than establishing it, and [§evidence-vocabulary](ARCHITECTURE.md#evidence-vocabulary)
confines a single observation to `incidents/`.

*One more data point for a parked decision.* `cross-rank` over eight captures of roughly 490 MB
each ran about six and a half minutes serially — the second observation of the friction the
serial rank loader causes, recorded rather than acted on.

**Fourth exercise, 2026-09-15** (same day, third session), on a MILC/QUDA staggered CG capture
from a **different** 8-rank 2-node A100 job than the third: a three-arm communication A/B whose
peer-to-peer-disabled arm no session had analysed. Isolation held — no analysis notes and no
hypothesis record beside the capture, and the working project's instructions characterise a
capture from another job entirely, which the definition above settles as not contamination.

*Check 1 — **ACCEPTED**, operator-graded 2026-09-15.* Every clause was met: performance mode
declared from the skill with no re-teaching; extraction through subcommands, with two `query`
calls that stayed row-capped and read-only and no direct database connection opened; a ranked
record `tools/hypothesis-record.py` accepts with bounds derived rather than asserted; every
figure naming a command; and thirteen hand-derived quantities declared, which the 2026-09-14
amendment settles is not a failure. The per-figure guard added by the third exercise fired on
first submission with three errors, all of a kind no previous exercise produced — source-code
citations carried in `evidence[]` unflagged — and that finding became the schema change recorded
below.

**Two qualifications are recorded rather than waived, because acceptance is the moment they stop
being visible.** First, the check specifies a session *"given only a profile and 'find out where
the time goes'"*; this session's prompt also supplied the location of the QUDA source tree and
asked for recommended fixes. The extra input is what made the revision-resolution residue below
reachable, so it was not inert. Second, the session that produced the analysis is the one that
reported the evidence, which the previous next action had asked to avoid; the grade is the
operator's, taken on that reported evidence rather than on an independent re-run. Neither
qualification was found to change a clause's outcome. **If check 1 is reopened, these are the two
places to look first**, and the cheap repair for both is one independent run on a bare prompt.

*Check 2 — still not exercised, a fourth time.* The capture answered its question, so
gap-reporting was never put under load. Positive signals, both consistent with the previous
rounds: with no hardware counters the session declined to classify memory- versus compute-bound,
and with `--sample=none` it stated the idle residual as an upper bound on host compute rather
than a measurement. The naming failure recorded in the second and third exercises did **not**
recur — no hypothesis was named for an attribution the evidence could not carry, and the
`software/quda/profiling.md` rule the third exercise wrote is the reason, which is that rule's
first field use. Four attempts with no exercise is what moves the constructed capture into the
next action.

*Check 3 — still not exercised, a fourth time.* A QUDA profile again. New positive evidence on
filing: the session reached `conventions/profile-metrics.md` and `software/quda/profiling.md` by
`load_when` match, and every QUDA-specific fact it needed — the launcher-versus-computation
naming rule, the enum-discriminator rule, the tunecache policy keys — came from the software leaf
rather than the mode or the convention. But the negative case remains untested, and a fourth
QUDA capture cannot test it.

*Durable residue, admitted the same day.* Three items, each its own change.

**The tracing-inflation rule gains an axis and an evidence upgrade.**
`conventions/profile-metrics.md` recorded inflation as non-uniform *across a run*. It is also
non-uniform *across configurations*: three arms of one job, identical but for one communication
environment variable each, inflated 1.55x, 2.95x and 4.00x on the solve phase. The consequence is
sharper than the existing rule and is now stated as its own prohibition — **a traced A/B distorts
the effect it exists to measure and can reverse its sign**. In these arms the traced captures
reported +86.4% and +177.9% against the default where untraced the figures were -2.3% (inside a
2-3% run-to-run spread, so no effect) and +7.6%: one overstated by 23x, the other inverted.
`conventions/profile-capture.md` takes the capture-time rule that follows — capture the arms
untraced and trace only to explain a difference already measured.

This also upgrades evidence on a claim the handbook already carried. The existing figures are
`[inferred]`, bounded from below because a cold autotune cache and a cold page cache both
penalised that control. This job removes both **for the solve phase** — the control's first solve
absorbs the tuning sweep and is excluded, and the solve phase does no file I/O — making it
`[experiment]` with one variable moved, and its 1.55x **reproduces the recorded solve-phase figure
from a different job and a differently structured control**.

**A QUDA profile's build revision is usually recoverable, and the leaf said it was not.**
`software/quda/profiling.md` stated that nothing in the profile identifies the revision that built
the binary — true of the database, and misleading in practice, because a run that wrote a
tunecache writes the Git descriptor into its header, which `internals/autotuning.md` already
documented from the other side. The leaf now says to look there first and cross-links the two, and
keeps the template-argument-plus-decomposition fallback for when neither is available. The session
resolved the enum at the build revision and *also* ran the decomposition cross-check — the
exterior values present were exactly those the rank grid permits, with the unpartitioned
dimension's value absent — so the leaf now recommends running the cross-check even with the
revision in hand, since a cache header can belong to a different build than the one profiled.

**`grounding.basis` declared an enum that nothing read.** Found while giving source facts a home:
the checker collects enums from `hypotheses.items.properties`, and `basis` sits one level below
that inside `grounding`, so every value passed — including a typo. This is the third instance in
this slice of a guard that could not fire, after the `if src and queries` short-circuit and the
unread declaration list. `schemas/hypothesis.schema.json` gains `grounding.sources` for
source-code citations, with the reason stated in the schema: a source fact is *read*, not derived,
so flagging it `hand_derived` files it as a derivation it is not, and the analysis playbook makes
source cross-referencing the step carrying most of the value while the record had nowhere to put
its result. `basis` gains `source` and stays single-valued, with `sources` legal beside any basis
rather than adding a value per combination. The checker now validates `basis` and requires
`leaves` and `sources` where the basis names them. Seven controls in
`tests/test_hypothesis_record.py`, including both perturbations of the new guard — silenced and
always-firing — each asserting the perturbation landed, and two positive cases so the rejections
are not passing merely because the tool dislikes an unfamiliar `grounding`.

*The by-hand counter's exemption was narrowed, not applied.* The session performed the
untraced-control comparison by hand six times, which the 2026-09-15 exemption placed outside the
counter because no profiler-database reader can emit it. That reasoning does not reach its
conclusion — a run-log reader can — and the procedure carries the quiet failure
`conventions/repeated-work.md` makes decisive: including the control's first solve moves its mean
roughly four-fold and yields an inflation factor near 1.0, which reads as "tracing is nearly
free", the opposite conclusion, through arithmetic that looks ordinary.
[§profile-analysis](ARCHITECTURE.md#profile-analysis) now scopes the exemption to procedures **no
tool in `tools/` could execute**. The control comparison is therefore a counter candidate at six
occurrences, and the working directory's own automation checkpoint independently nominated it.

*Third observation of the serial rank loader, and it should stop being an observation.*
`cross-rank` over eight captures totalling 7.4 GB ran about ten minutes, against the second
observation's six and a half minutes over 3.9 GB. Stage 2 deliberately left the source
implementation's worker pool out of the port as a separate change; three observations crosses the
same "more than twice" threshold the by-hand counter uses, so the pool is now owed its own change
rather than another line here.

**Fifth exercise, 2026-09-15** (same day, fourth session), on a single-rank Nsight Systems
capture of the working project's **synthetic CUDA benchmark** — not QUDA, not MILC — from a
4-rank 1-node A100 job. The operator supplied a path and two questions: what the bottlenecks
are, and whether there are MPI issues. Isolation held: no ground truth, no sibling rank and no
analysis notes accompanied the capture, and session memory covered a different profile of a
different application.

**Checks 2 and 3 were both put under load for the first time, and neither was arranged.** The
previous next action had concluded that such a capture would not turn up and asked for one to be
constructed; one turned up unbidden, carrying both properties at once. **Both are accepted,
operator-graded 2026-09-15.**

*Check 1 — met again, not re-graded.* Performance mode was declared at orientation rather than in
response to the profile, which is weaker than the check's *"given only a profile"* wording, so
this run is not offered as an independent second grade. Everything else held: extraction through
subcommands with four `query` calls that stayed row-capped and read-only, a two-hypothesis ranked
record `tools/hypothesis-record.py` accepts with bounds derived, every figure naming a command,
and six hand-derived quantities declared. The record was rejected once on `grounding.basis` —
`both` used for profile-plus-source, where it denotes profile-plus-leaf — and the guard, not the
session, caught it. That is the second consecutive exercise in which the per-figure provenance
guard fired on first submission.

*Check 2 — **ACCEPTED**, operator-graded 2026-09-15.* The capture carries `cuda` and `osrt` but
**no `mpi` and no `nvtx`**, while the binary is MPI-linked and ran 4 ranks, so the operator's
second question was aimed squarely at instrumentation the capture does not hold. The session
named the gap — capability note N1, no MPI hypothesis emitted, and the explicit statement that
the capture supports no MPI finding **and no claim that MPI is healthy** — and declined to rank
communication. Two things are recorded rather than waived. First, the recipe the previous next
action prescribed was `-t cuda` alone; `osrt` is present here, so OS attribution was available
and only the communication instrumentation was missing. The check is written about *the
instrumentation its question needs*, and the question asked was communication, which is why the
deviation did not change the outcome. Second, the session did not stop at "unknown": it bounded
MPI's contribution from the idle residual. **The operator ruled that bound to be gap-reporting
rather than reasoning past the gap**, and the ruling is recorded in
[§open-questions](#open-questions) with the reasoning that makes it narrow, because a wider
reading of it would license exactly the failure this check exists to catch.

*Check 3 — **ACCEPTED**, operator-graded 2026-09-15.* The profiled software is
`synthetic_cuda_benchmark_mpi`, which has no handbook profiling leaf and is not the application
any handbook leaf describes. **No QUDA-scoped material was loaded at any point**: `software/quda/`
was never opened, and the one directory listing of `software/` read names only. The routing that
did fire was `conventions/profile-metrics.md` and `conventions/profile-capture.md` by `load_when`
match, plus the mode and the playbook — all universal-scope. This is the negative case four QUDA
captures could not supply, and it confirms from the opposite direction what the third and fourth
exercises showed positively: the kernel-naming and tunecache facts are in the software leaf, and a
session that does not need them does not load them.

**The qualification all three grades share.** Each was taken on evidence reported by the session
under test rather than on an independent re-run, which the third exercise's ruling had asked to
avoid. For check 1 that was recorded at the fourth exercise; it applies unchanged to checks 2 and
3 here. **If any of the three is reopened, this is the first place to look**, and the cheap repair
is unchanged: one independent run on a bare prompt. What reduces the exposure for checks 2 and 3
specifically is that both turn on *absence* — no MPI hypothesis, no QUDA leaf loaded — which is
cheaper to verify from the record after the fact than a positive claim would be.

*Durable residue.* Two items, each its own change. **`conventions/profile-capture.md` gains the
capture-scope-gating hazard** (landed 2026-09-15): the benchmark brackets its timed loop in
`cudaProfilerStart`/`cudaProfilerStop` and the bracket was not honoured — 38.9% of the window lay
outside the kernel span, carrying process startup and teardown — because the profiler was not
launched with `--capture-range=cudaProfilerApi`. `playbooks/analyze-profile.md` already named the
defect class in one clause; the capture convention had no coverage of it and no detection signal,
and `outside_kernel_span_s` is that signal. **`conventions/profile-metrics.md` gains what the idle
residual still bounds**, admitted on the check 2 ruling and deliberately held until it was given,
because writing it from the session whose grade turned on that reasoning would have contaminated
the grade.

**Coverage defect found in use, 2026-09-15** (sixth session), on a MILC `su3_rhmd_hisq` RHMC
capture from a 4-rank single-node JLSE B200 run. Not an acceptance exercise — Slice 6 is
accepted, and this is the first defect the accepted tooling produced against a real analysis.
The isolation precondition was **not** met and no grade is claimed from this session: two prior
hypothesis records and their transcripts sat in the capture directory. Their filenames were
visible in a directory listing and none was opened, but that is weaker than the third exercise's
standard and is recorded rather than waived.

*The defect.* `compute_window_breakdown` accumulated **every** category into `all_intervals`,
including `markers`, so `covered_s` counted annotation ranges as accounted time. On the capture's
88.0 s startup window a single `qudaInit` range covering 87.286 s drove the output to **0.199 s
uncovered, 0.23%** — a window reading as fully accounted for. With annotations excluded the same
window reports **69.218 s uncovered, 78.66%**. That 69.2 s was the largest bottleneck in the run:
single-threaded MILC host code, found by CPU sampling through the raw-query escape hatch, not by
the field built to point at it. The failure is the reassuring direction — `uncovered_s` is the
one number the playbook reads to decide a window is *not* explained, and an outer range silences
it on exactly the captures where it matters. `mpi`, `host_api` and `os_runtime` name what a
thread was doing; a marker names which region the code was in, and that is not the same claim.
`_ANNOTATION_ONLY_CATEGORIES` now gates the coverage arithmetic, markers stay in `categories`,
`top_events` and `bins`, a caveat states the exclusion, and
`conventions/profile-metrics.md` gains **"An annotation bounds a window; it does not account for
it."**

*The second defect, which is the more transferable one.* The fix silently made
`test_summing_categories_instead_of_merging_is_caught` inert, and it caught itself: after the
change, summing and merging returned the same 0.16005 s. The synthetic nsys fixture's **only**
interval overlap was an NVTX range over a `cudaLaunchKernel`, so the merge-versus-sum control had
always been resting on the very category the fix removes from coverage. **A control that
exercises an invariant only through a category a later change may exclude is resting on a
coincidence, and nothing marks it as such while it passes.** Repaired in the fixture rather than
in the control: a third `MPI_Allreduce` `[795 ms, 815 ms]` now encloses the existing
`cuStreamSynchronize [800, 810]`, giving a genuine activity-on-activity overlap — the CUDA-aware
collective case `conventions/profile-metrics.md` already describes — so merge and sum differ
without any annotation. This is the fourth time in this repository a control has been found
vacuous, and the first found by the control's own landing assertion rather than by reading
output.

*Controls.* Three added — an annotation must not raise coverage, emptying
`_ANNOTATION_ONLY_CATEGORIES` must raise it (so the constant is shown to be consulted rather than
decoration beside a guard that would exclude markers anyway), and dropping the exclusion caveat
is caught — plus the repaired merge-versus-sum control, six in total. Each was reverted and
confirmed to break. Full suite 317 passing; validator unchanged from baseline at 17 P2 advisories
and Tier 0 5844/6144 bytes.

*Queued from the same session's review, each owed as its own change under the one-fact-class
rule.* `cross-rank` discards the per-rank `ProfileSummary` objects it already holds when phase
alignment refuses, so a session re-derives them at ~47 s per rank — `align_phases` receives them,
and emitting them alongside the refusal costs nothing. The `phases` subcommand returns a payload
byte-identical to `summary["phases"]` at the same ~48.7 s, which `playbooks/analyze-profile.md`
induces by prescribing both in consecutive steps. `schema`'s `--table <NAME>` branch is
unreachable, the only `--table` being the global boolean, which is silently ignored for that
subcommand. And the **windowed CPU-sampling leaf-symbol breakdown reached three hand uses in one
session**, crossing [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s threshold: it is the
instrument that named this session's largest finding, it has two silent failure modes — omitting
`stackDepth = 0` counts every frame of every stack, and omitting `MATERIALIZED` re-derives the
window CTE per outer row — and it is squarely a profiler-database aggregation, so the 2026-09-15
narrowing does not exempt it. Owed as a subcommand.

**Refusal payload defect, 2026-09-15** (sixth session, second change). `cross-rank` discarded
the per-rank `ProfileSummary` objects it had already built whenever phase alignment refused.
`align_phases` is handed those objects and rejects its own precondition, not the data; the
session that hit this then re-ran `summary` once per rank — ~47 s each — to recover numbers the
refused process had spent ~190 s computing. `compute_rank_overviews` is split out of
`compute_cross_rank_summary` because it needs no alignment, and the refusal now carries
`per_rank_overview`, `primary_rank_reason` (dropped on that path for the same reason, one field
over) and three caveats. On the four-rank B200 capture the refusal now reports what the session
derived by hand: four ranks at 124.8–125.9 s kernel time and 37.9–38.2% utilisation, with
`no clear outlier (all ranks within 20% of median GPU idle 126.5s)`.

*The caveat was written wrong first and corrected by testing it.* The draft claimed
`--max-phases <k>` "may let the per-phase comparison proceed". On the synthetic divergent pair
that is false in a way the draft would have hidden: forcing k equalises the counts and the run
is then refused by a *second* check, on name and duration divergence. On the real capture it is
true — `--max-phases 5` unblocks the full per-phase view. Both were measured before the sentence
was settled, and the shipped wording names both outcomes. **An untested "may" in a caveat is the
same defect class as an untested number in a hypothesis**, and it was one edit away from
shipping.

*What the unblocked comparison then showed, recorded because it qualifies a reading rather than
adding one.* Phase 2 reports a kernel imbalance of **4.000**, which is `(max - min) / mean` over
0.057 s against a mean of 0.0143 s: rank 2 ran 57 ms of kernel work in a 5 s window where the
other three ran none. The score is arithmetically correct and describes 57 ms, so it overturns
nothing — and it explains the refusal itself, since that burst is exactly the extra timeline
structure that drove rank 2 to k=7 while its peers chose k=5. A ratio whose denominator is near
zero is reported without a floor; that is pre-existing behaviour on the success path, is **not**
changed here, and is recorded so the next occurrence is not read as a large imbalance.

*Controls.* Four assertions — the refusal carries an overview covering every rank; those figures
equal what `summary` returns per rank, which is the re-derivation the change removes; the
outlier reason survives; the caveats bound what whole-profile agreement proves. Two controls:
emptying `compute_rank_overviews` must empty **both** the refusal and the success payload, which
pins that one builder serves both and they cannot drift apart again; and an aligned pair must
still succeed, so the refusal has not become unconditional. `conventions/profile-metrics.md`
gains the durable residue under "One rank's profile is one rank's view" — whole-profile agreement
bounds gross skew and nothing finer.

**Host-sample naming, 2026-09-15** (sixth session, third change). Discharges the by-hand
counter item the first entry of this session recorded as owed: the windowed CPU-sampling
breakdown had been written by hand four times in one session, it is a profiler-database
aggregation so the 2026-09-15 narrowing does not exempt it, and it carries two silent failure
modes — omitting `stackDepth = 0` counts every frame of every stack, and omitting `MATERIALIZED`
on the window CTE makes SQLite re-derive it per outer row of a multi-million-row table, which is
the nested-loop shape the query guard exists to refuse.

*Why it is not a convenience.* `idle-attribution` reports host time it located but could not
attribute as `residual`; `window-breakdown` reports the part of a window no traced activity
covers. Both are upper bounds on an unnamed quantity and neither can ever name it, because the
time is unattributed precisely when no CUDA or OS call is in progress. On the capture that
prompted this, a 55 s stretch of an 88 s startup window carried no traced activity at all;
sampling identified it as MILC gather-table construction, host reunitarisation and host RNG,
which was the largest single cost in the run. The new subcommand reproduces that result in 3.2 s.

*A second defect found on the way.* `nsys.py` hardcoded `has_cpu_samples=False`. Real captures
carry millions of callchain rows — 6.1M on the one observed — so the capability flag was not
merely unset but wrong, and any future consumer gating on it would have been silently disabled.
Fixed to detect `COMPOSITE_EVENTS` and `SAMPLING_CALLCHAINS` together, since the first alone
carries no symbols.

*What is deliberately not implemented.* rocpd returns `None` rather than a guess.
`rocpd_sample` carries `(nid, pid, tid, start, end, event_id, extdata)` and no symbol or module
column; resolving a sample to a function means following `event_id` into a stack representation
no real capture has been checked against here. A join written from the schema alone would emit
plausible symbol names nothing could verify, which is the failure the evidence rules exist to
prevent. `None` makes the caller say **"not implemented for this format"**, which is a different
statement from **"no samples"** — the second is a claim about the run — and a control pins that
the two do not collapse into each other.

*Three readings the output refuses to allow, because each would be wrong in a plausible
direction.* A count is not a duration and no seconds conversion is offered: the observed capture
records `RATE_HZ = 0` beside a perf `SAMPLING_PERIOD` of 1950000, so counts track cycles
consumed rather than elapsed time. Only the leaf frame is counted, so a share is work in that
function and not inclusive of callees. Samples are summed across every sampled thread — 13 on
the observed window — so a share is of sampled host thread-work, not of the window. Each is a
caveat on the payload and a rule in the convention, and the thread-state split is reported
because a sample on a blocked thread is not a computing one.

*Controls, and a vacuous one caught before it shipped.* Six: counting every frame instead of the
leaf must surface a depth-1 caller the fixture plants on every sample; a hardcoded capability
must turn the result unavailable; a format that cannot resolve symbols must not report zero
instead; and three caveat-removal controls. **The first version of the "not a duration" control
was vacuous** — it perturbed `nsys.py` by replacing a string with itself and then asserted the
caveat was still present, so it would have passed whatever the code did. The caveat lives in
`metrics.py`. This is the fifth vacuous control recorded here and the first caught in a
session's own new test before landing rather than afterwards; the repair also added a
before-assertion so the control now proves the caveat was there to remove. Full suite 340
passing, validator unchanged at 17 P2 advisories and Tier 0 5844/6144 bytes.

**Duplicated phase computation and missing segmentation provenance, 2026-09-15** (sixth
session, fourth change). `cmd_phases` called `compute_profile_summary` and returned
`{"phases": ...}`, discarding the other eleven fields — so `summary` followed by `phases`, which
is what steps 2 and 3 of `playbooks/analyze-profile.md` prescribed in consecutive paragraphs,
computed the entire summary twice. Measured on the B200 capture: 48.7 s each, and the two
`phases` payloads are byte-identical. Segmentation is 15.5 s of that 48.7 s (`--max-phases 1`
runs in 33.2 s), and the per-phase rows carry `gpu_memcpy_s` and `top_kernels`, so **a leaner
`phases` would have to drop fields it already emits** — the duplication cannot be optimised away
and the fix is not to run both. The playbook now says to read the table out of the summary, and
the subcommand's docstring says it is not the cheaper half.

*The larger half of this was not the time.* Neither payload recorded the `--max-phases` cap, and
both commands accept it. Phase boundaries are a property of the capture **and** the cap, so two
calls at different caps return different windows — on the synthetic fixture, 4 phases against 2 —
and a `--start-ns`/`--end-ns` pair lifted from one is silently meaningless against the other.
Every windowed figure in a hypothesis record is derived from such a pair, and
`playbooks/analyze-profile.md` requires each to name the command that produced it; the command
string alone did not settle it. `ProfileSummary` gains `phase_segmentation` — the cap, the
selected k, any forced k, and a note — emitted by `summary` and `phases` alike. The note fires
when `selected_k == max_phases`, because the elbow may then lie above the cap and the
segmentation is partly an artefact of the flag rather than of the run.

*A latent NameError was introduced and caught before it shipped.* The first version populated the
field from `forced_k` in both constructors, but `compute_profile_summary_and_state` has no such
parameter — it passes `forced_k=None` to the segmenter explicitly. The multi-rank path runs
through that function, so `cross-rank` would have raised on every invocation. Caught by reading
the grep output for the symbol rather than by a test, which is worth recording: the single-profile
tests would all have passed.

*Controls.* Five: `summary["phases"]` and `phases["phases"]` must be equal, which is what keeps
the playbook's "read it from the summary" instruction true; the segmentation record must match
the table it describes; two caps must produce two segmentations **and** two differing records,
which is the negative control against the field being decoration; k at the cap must be flagged;
and disabled segmentation must say so. Full suite 345 passing, validator unchanged.

**CLI dest collision, 2026-09-15** (sixth session, fifth change). `schema`'s positional was
declared as `table`, the same dest as the top-level `--table` rendering flag. argparse resolves
that by letting the subparser's default win, and two failures followed, both silent and in
opposite directions: `--table schema <profile>` dropped the rendering request and returned JSON
reporting success, and `schema <profile> <NAME>` rendered a human-readable table **whether or
not** `--table` was passed, because `main` tests the same attribute — so that one form could not
emit JSON at all, in a tool whose every other subcommand defaults to it. Renamed to `table_name`
with `metavar="table"`, so the documented command line is unchanged.

*The review that opened this item described it wrongly, which is the part worth recording.* It
reported the per-table branch as **dead code and unreachable**, on the strength of reading
`cmd_schema` and grepping for `add_argument("--table"`. The branch is reached perfectly well by
the positional form `schema <profile> <NAME>`; the grep could not see it because the argument is
positional and named without dashes. **Reading a consumer and grepping for one spelling of its
producer is not reading the wiring**, and the resulting claim was confident, specific and false.
Only the second half of the report — that the global flag is silently ignored for `schema` — was
correct, and the real defect is a superset of it that the wrong diagnosis would have left in
place, since deleting "dead" code would have removed a working feature.

*Behaviour change, flagged rather than buried.* `schema <profile> <NAME>` now returns JSON by
default instead of rendered text. That aligns it with every other subcommand and makes the form
scriptable for the first time, and it will break anyone parsing the old text output. Judged worth
it for a diagnostic subcommand in a tool with a JSON-default contract.

*Controls, and the guard is structural rather than case-specific.* The shipped test does not
check `schema`; it walks `build_parser()` and asserts that **no** subcommand declares a dest
already owned by a top-level option, because the next collision will be somewhere else. Two
controls prove it can fail: restoring `table` as the positional's dest must make the guard report
`schema:table`, and the same perturbation plus the old reader must reproduce the silent-JSON
behaviour end to end — so the guard is pinned against the exact shape that shipped rather than
against a hypothetical one. Full suite 352 passing, validator unchanged.

**Routing gap on the tunecache-warmth gate, 2026-09-15** (sixth session, sixth change).
`software/quda/profiling.md` makes tunecache warmth a **mandatory gate** before call counts,
launch geometry or duration spread may be read, and delegates how to execute it to
`internals/autotuning.md` in four places. That leaf's `load_when` read *"...for tuning or
benchmarking"* — which excludes performance mode, the one mode that runs the gate as mandatory.
Task-time routing matches on `load_when`, so a session doing exactly what `profiling.md` requires
could read that line and correctly conclude the leaf did not apply. Two surfaces disagreed:
`modes/performance.md` says to load the profiled software's autotuning leaf, the leaf's own
`load_when` said not in this mode. The mode is right, so the clause was widened; the index was
regenerated and no other index moved.

*Where the software condition does **not** go.* The obvious fix — writing "for QUDA profiles"
into `load_when` — was rejected. `scope: [software:quda]` already decides that, and
`tools/build-index.py` groups strictly by scoped object, so the row only ever appears under
`## quda`. Restating it in `load_when` would put one fact in two places that could disagree, with
no rule about which wins, which is exactly what P2 forbids. **`scope` says which software;
`load_when` says which situation within it**, and only the second half was wrong.

*The larger gap the question exposed, which the `load_when` fix alone would have left in place.*
Routing to the `## quda` group requires already knowing the capture is a QUDA profile. Tier 0
derives named software "from the operator request and active project instructions", and a request
that is a path names none — on this session the application was identified from the `quda::`
prefix on every row of `top_kernels`, after the first extraction. So **the routing trigger for a
profile session is the extraction output, not the request**, and that ordering was written down
nowhere. `playbooks/analyze-profile.md` step 2 now states it, generalised past QUDA: identify the
profiled software from the extraction, do it before step 3, because the leaves it selects govern
how step 3's figures may be read.

*Two proposals from the same review, rejected rather than deferred, recorded so they are not
re-litigated.* **Deduplicating `software/INDEX.md`** was dropped. 6,848 of its 20,820 bytes are
20 leaves listed twice, but every one is scoped to two software projects — "QUDA staggered CG
through MILC" belongs under both — so deduplication means choosing a group to break, and the
byte argument runs against a locked decision whose stated reopen trigger is legibility and
explicitly not size. **A framework detector on the extraction** was dropped too: the evidence is
already in the first output, since every `top_kernels` row carries the namespace, and a detector
would be a second rottable list restating what the session can read, against this repository's
own preference for supplying evidence rather than a verdict.

*No new test, and the reason is that there is nothing mechanical to pin.* The change is one
frontmatter clause and three paragraphs of prose. The validator already covers both halves that
can rot: generated-index currency catches a `load_when` edited without regeneration, and
reference resolution catches the two new playbook links. A test asserting particular wording
would pin prose rather than behaviour and would fail on the next honest rephrasing. Full suite
352 passing, validator current with references 623 to 625.

**Change-proposal harness, 2026-09-15** (sixth session, seventh change). Discharges the item
this document already recorded as qualifying on three hand runs; this session performed the same
sequence six more times, for nine in total. `tools/propose-change.py` runs the diff, regenerates
the indices, runs the validator, runs the suite, and writes the proposal's added lines to a
review file, with `tools/run-change-proposal` selecting a new-enough interpreter the way
`run-validator` does.

*The design rule is that a step must report what it examined.* The two quiet failures named when
this was first owed are a stale index — well-formed and plausible, so the eye passes it — and a
privacy sweep that never ran, which produces output identical to one that found nothing. The
second cannot be fixed by checking harder; it is fixed by printing the count of lines read, so
"0 matches" and "did not run" stop looking alike. Every step follows that rule: the validator's
own summary line, the test count, the lines scanned. A validator that exits 0 while printing no
summary is treated as a failure for the same reason.

*What it refuses to do.* It renders no publication verdict. The validator's deny list is regular
expressions over home paths, emails, keys and scheduler accounts; `PRIVACY.md` also forbids
internal hostnames, job identifiers, unpublished measurements and live campaign state, none of
which is a pattern. So the privacy step ends by naming those categories and handing over the
diff. A harness that claimed to clear a proposal would be the worst available place to be wrong,
and `validator-not-clearance` already settles that the validator is a safety net rather than
clearance.

*Two defects in the harness, both found by using it rather than by reading it.* The validator
prints its summary to stdout and its P2 advisories to stderr; the first draft read the last
stderr line and reported an unrelated file's advisory as the result — visibly wrong on the first
real run, and now pinned by a control. And **the test file tripped the deny list it exists to
test**: a literal planted home path and a literal git-config email made the repository fail its
own privacy check. The placeholder forms the validator exempts — `<user>`, `$HOME` — cannot serve
here, because they are exempt precisely by not matching and so could not prove the check fires.
Both strings are now assembled at runtime and never appear contiguously in the source, with the
reason recorded beside them.

*Negative testing, as `conventions/repeated-work.md` requires before a tool replaces a hand
procedure.* Nineteen checks, and every one asserting a step passes is paired with one making the
same step fail: a failing validator, a validator that exits 0 silently, a failing suite, a
generator that errors, and — the control that matters — an index quietly rewritten under the
harness, which must be reported as stale and named. The end-to-end check plants a real home path
in a copy of the tree and runs the **real** validator, because a fake runner cannot prove the
step whose failure matters most actually fires. `added_lines` is pinned to see untracked files,
since a new leaf is the likeliest place for unpublishable material and `git diff` does not see
it, and the vacuity guard is that a clean tree must yield no added lines at all. The harness was
then run on its own proposal and passed. Full suite 371 passing.

**Transfer residency, gap naming, and phase-indexed windows, 2026-09-16** (seventh session).
An analysis of the B200 capture in performance mode, then developer mode on its residue. Three
items crossed the by-hand counter in the one session and all three landed; the operator cleared
the fact class first, for illustrative magnitudes with identifying and physics detail excluded.

*The residency split is the one that changes a conclusion, because the old output was not
neutral.* Grouping transfers by `copyKind` alone merged two populations whose aggregate rates
stood about **400x** apart inside a single device-to-device row, and reported their average —
a figure that reads as an unremarkable mid-range bandwidth and quietly refutes the very
signature the QUDA leaf exists to name. The leaf's previous discriminator asked for *two copies
of identical size* and grouping by enclosing annotation range; residency needs neither and is
one `GROUP BY`, so the leaf now leads with it and keeps the size formulation as superseded.
Two further readings were added to it: a zero count of *user-prefetch* migrations is positive
profile-side evidence the gate never fired, complementing the log-side absence test; and the
migration direction is explained by the **managed end** not being device-resident, where the
text had said "the source was never resident" — the observed slow population was
destination-managed, so the old reason did not cover it.

*`gap-detail` exists because the residual's histogram stops one level short.* It separates
diffuse from structural and cannot separate two structural mechanisms from each other. In one
phase the >10 ms slices held a host `memset` and application vector arithmetic; per gap they
were about 89% and 46-61% of samples, and over the enclosing phase the same two symbols read
4.5% and 11.2% — "some host work", with nothing indicating there were two. So the subcommand
samples the gap, and `conventions/profile-metrics.md` now says to sample the gap rather than
the phase that contains it.

*Two defects were introduced and caught before the diff was shown.* `--phase` first resolved
through `compute_profile_summary`, reproducing exactly the waste `cmd_phases` had been corrected
for a day earlier — caught by timing it (over 120 s against 48 s) and repaired to `detect_phases`,
with a control that fails if it regresses. And the QUDA leaf's new link to
`conventions/profile-metrics.md` was written at two levels up from a three-level-deep file; the
validator's reference check caught it. The second is the argument for the harness being mandatory
rather than advisory: nothing about the wrong path looks wrong.

*Controls.* Twenty-five across three files, each paired with the perturbation that must move it,
and all seven perturbations were run and confirmed to fail distinctly: raising the split factor
must stop the split firing; forcing `has_transfer_residency` true must break the
unavailable path; an INNER JOIN on the memory-kind enum must drop an Unknown end; using sorted
rather than merged intervals must produce a phantom gap under kernel overlap; zeroing the gap
floor must break the floor control; renaming `--phase` must break the registration sweep; and
resolving through a full summary must break the cost control. The negative control for the rate
split flattens the two populations and asserts the split *disappears* while the rows remain,
because a check that always fires is indistinguishable from one that never runs.

*Rejected, and recorded so it is not re-litigated.* A MILC RHMC host-cost-structure fact — that
the rational-function reconstruction runs on the host and leaves a serial tail after each
offloaded multi-shift solve. It is the largest single cost in the capture and it is **not
admitted**: the mechanism is inferred from sampled symbol names alone, with no read of
`ks_imp_rhmc` source, from one capture of a collaborator's unpublished run. Obligation 4 forbids
mining and admitting in one step. It stays in the working directory until someone reads the
source; if that happens the fact belongs in `software/milc/applications/ks-imp-rhmc.md`.

*Also left alone deliberately.* The capture had no MPI tracing, which cost its analysis every
communication reading. That is not a handbook fact: the extraction's own capability note already
prints the re-profile command, so the executable form exists and prose would only duplicate it.

**Amended 2026-09-16 by the eighth session: the executable form existed and was wrong.** The
reasoning above holds for Nsight Systems and failed for rocpd — every rocpd re-profile command
the capability notes printed omitted `ROCPROFSYS_USE_ROCPD=true`, so following one produced a
capture this repository cannot open. "The tool already prints it" is a sound reason to decline
prose only once the printed command has been checked, which this entry did not do.

**Capture recipe, profiler availability, and an unreadable re-profile command, 2026-09-16**
(eighth session). Closes the capture gap the 2026-09-16 review opened, in the two changes that
review specified plus a third the work turned up. Nothing measured was admitted; the fact class
cleared by the operator beforehand was profiler invocation and output-format settings, carrying
no allocation, path, host, run-identifier or measurement detail.

*The recipe.* `conventions/profile-capture.md` gains what to request from Nsight Systems,
rocprofv3 and rocprof-sys, the `nsys export --type sqlite` step every tool here requires, and a
section stating that no tracer setting supplies achieved bandwidth, cache behaviour or
occupancy — counter collection is a separate job, because replay distorts the durations a timing
capture exists to measure. The leaf opens by naming `tools/gpu_profile/diagnostics.py` canonical
for the remedial mapping and declining to restate it, because the two are not the same object:
the tool runs on a profile and this runs when there is not one yet. That distinction is what
separates this from the prose the seventh session correctly rejected as duplication.

*The third change, and it is why the second sentence above needed writing.* The seventh-session
entry closed by leaving MPI-capture prose out, on the grounds that the extraction already prints
the re-profile command. It does — and **on ROCm that command produced a file this repository
cannot open.** rocprof-sys writes a perfetto trace unless `ROCPROFSYS_USE_ROCPD=true` is set, and
none of R1, R2, R3, R4 or R5 mentioned it; a session following the tool's own advice would have
spent an allocation and received an artifact `open_profile()` rejects. R1 additionally needed
`ROCPROFSYS_USE_MPIP=true`, without which the MPI ranges it exists to recover are absent. The
flags themselves — `--trace`, `--mpi` — were **left alone**: the evidence shows they are
insufficient, not wrong, and rewriting an unverified flag is the overclaim this document keeps
recording. `tests/test_gpu_profile_capability_notes.py` pins it **structurally**, walking every
rocpd note rather than asserting on the five by name, so the next note added is covered.

*The per-rank convention turned out to be a constraint rather than a convention.* `[source]`
`parse_rank_ids` extracts every integer from each stem, requires all stems to yield the same
count, and requires exactly one position to vary. A name carrying a second varying integer — a
node ID is the obvious one — silently falls back to positional order, so every per-rank figure
is attributed to whichever file globbed first. The payload says so in
`rank_ids_parsed_from_filenames`, and the leaf now says to read that field before any per-rank
number. This is the one part of the capture gap that was not visible from the outside: the
ROADMAP recorded "no per-rank output convention", and what was missing was a rule about what may
not appear in the name.

*Machine side, and the absence is deliberate.* `schemas/machine.schema.json` gains an optional,
permissive `profilers` object — no `schema_version` bump, on the 2026-08-28 precedent where
profiles gained only an optional field. Perlmutter records Nsight Systems under `cudatoolkit`;
Frontier records `rocprofv3` and `rocprof-sys-sample` under `rocm`, the second flagged
`module_version_sensitive`. **DeltaAI records nothing.** It is NVIDIA and CUDA, so `nsys` is very
likely present — and that is exactly the interpolation [§stacks](ARCHITECTURE.md#stacks) rule 1
forbids. An absent key means nobody established it, which is the true statement.

*Filing, decided against the first draft.* The Frontier module-pin fact — a lone `rocm/<version>`
pin conflicts with `PrgEnv-amd`'s own `amd/<version>` default and resolves silently to the older
one — was drafted into the new capture leaf and moved to `machines/frontier/notes.md`, because it
governs any pinned ROCm work rather than profiling specifically. The capture leaf cites it and
keeps only what is capture-specific: a correct pin can still land on a module that does not ship
the profiler, and that failure presents as a job that merely ran without profiling. Both new
facts are tagged `[inferred]` rather than `reproduced` — each rests on one observation plus a
mechanism, and `observed` would have forced a durable rule into `incidents/`.

*Rejected, recorded so it is not re-litigated.* The source reference's capability matrix claims
memory bandwidth as a percentage of peak and a GPU occupancy estimate for both formats. Both
contradict the tracer rule `modes/performance.md` and
[§profile-analysis](ARCHITECTURE.md#profile-analysis) already carry, so the rows were dropped and
the opposite section written instead. Importing a matrix wholesale is how a known overclaim
enters a convention. A `capture_notes:` pointer field in the machine profiles was also drafted
and dropped: the validator resolves Markdown links and not bare YAML strings, so it would have
rotted unchecked.

*Newly owed.* **`diagnostics.py`'s N4 offers a remedy that the mode forbids reading.** It tells a
session to re-profile with `--gpu-metrics-device=all` so that memory-bound versus compute-bound
classification need not "use heuristics only" — while `modes/performance.md` and
[§profile-analysis](ARCHITECTURE.md#profile-analysis) both rule that question out of a tracer
entirely and send it to a counter-collecting run. The note invites precisely the reading the mode
exists to prevent. Not fixed here: it is a different fact class from the output-format defect,
and whether the sampled device-wide metrics that flag collects can support any part of that
classification is a judgement this session could not verify offline. R4's rocpd twin carries the
same wording.

*Controls.* Five in the new file, and all five perturbations were run and confirmed to fail
distinctly: the fix reverted entirely (two failures), the constant present but emptied, MPIP
dropped from R1 alone, the whole ROCPD branch disabled (three failures, the vacuity guard), and
a ROCm variable leaked into an nsys note. The emptied-constant case is the one worth naming — it
is the shape of the five vacuous controls this document already records, and it distinguishes a
constant that is consulted from one sitting decoratively beside the guard. The schema addition
got the same treatment outside the suite: removed, both machine profiles fail validation;
restored, they pass. Full suite 401 passing, validator unchanged at 17 P2 advisories and Tier 0
5844/6144 bytes, references 625 to 635.

**The perturbation runner was withdrawn and its helper extracted instead, 2026-09-16**
(ninth session). The operator asked whether the runner recorded above was really necessary. It
was not, and the ordering is the reusable part: **the tool it asked for was already in the tree
when the item was written.** `WindowBreakdownControls.perturb` — assert the anchor matched,
rewrite the source, run the real tool, assert the behaviour moved, restore in `tearDown` — is
exactly the (anchor, replacement, named test) triple that paragraph specified, and it landed in
`c327813`, roughly two and a half hours before `079ff6d` recorded the need for it. It was then
copied into `test_gpu_profile_cross_rank.py` and `test_gpu_profile_host_samples.py` the same
night, the same error string verbatim in all three, while the item went on reading as owed.

*Why the existing form is better than the one that was asked for, rather than merely equivalent.*
A standalone runner checks a control once, when it is written. A control carrying its own
perturbation re-checks on every suite run. The most valuable catch of this class this document
records — `test_summing_categories_instead_of_merging_is_caught` going inert because a *later,
unrelated* fix removed the only overlapping category its fixture had — happened long after
authoring time, and a one-shot runner would never have seen it. The owed item was aimed at the
wrong moment.

*What was actually owed.* Extraction and adoption. `tests/support.py` gains `PerturbationMixin`,
the three copies now use it, and `tests/test_gpu_profile_capability_notes.py` — written the day
before with its five perturbations run by hand — carries them as controls that run in CI.

*The rest of the suite needed almost nothing, and an earlier draft of this entry said otherwise.*
That draft claimed ten of fourteen control files still hand-perturb and that their controls
prove nothing once their session ends. **Measured, that is false.** Those files carry
*fixture-variation* controls — vary the input, assert the output moves — which run on every
suite like any other test. Eight fixes this document records as hand-verified were reverted in
turn and **seven were caught by controls already committed**: gap-detail's merged intervals, the
residency rate split, the overhang warning, the hardcoded outside-span term, the query guard's
nested-scan threshold, the per-figure `hand_derived` guard, and rocpd's work-item grid
normalisation. Source perturbation earns its place where a guard concerns output shape or
wording, which no fixture distinguishes from a hardcoded value; where a control can discriminate
through the public interface it already does, and adding a second layer would be ceremony.

*The eighth was a real gap, and three wrong turns reaching it are the useful part.* The
transfer-overlap path merges kernel intervals and **nothing caught reverting that merge**. First
diagnosis, that the control was missing, was wrong twice over. The first probe perturbed
`compute_transfer_overlap` while running `gap_detail`'s tests — the wrong function for the
module under test, and the reported miss was the probe's fault rather than the suite's. The
control then written passed without catching anything, because `intersect_duration_ns` merges
both its arguments internally, so the call-site merge alone decides nothing. Correcting the
geometry did not fix it either: the walk revisits a kernel only when a transfer *spans* several,
and the first fixture put the transfer *inside* them. **The two merges are redundant with each
other**, so dropping either alone moves no number and only dropping both does — which is
precisely why this was missing rather than weak, and why a reader meeting either call would
reasonably take it for the load-bearing one. One control now covers the pair, and it is the only
test in the suite that exercises concurrent kernels at all: the shared nsys fixture has none.
Suite 407.

*What the sweep did not cover, so the seven-of-eight is not read as a clean bill.* Eight fixes
were probed, across `metrics.py`, `rocpd.py`, the query guard and the hypothesis record. **Not
probed:** `test_gpu_profile.py`'s four recorded breakages — the one remaining file that rewrites
source, and so the likeliest place for another gap — `propose-change`'s nineteen fixture-based
checks, and the session-logging and slice-0 controls. The sweep also probes only fixes this
document happens to record; a fix that was never written up cannot be probed for, and most of
the suite predates the practice of recording them.

*The extraction is not a pure move, and the difference is the point.* All three copies checked
only `assertIn(old, original)` before writing, so a replacement **equal to** the text it
replaces passed and wrote nothing — which is exactly how the fifth vacuous control recorded
above got in, a string replaced with itself. `perturb` now fails on a no-op edit. It reports
that in one line rather than through `assertNotEqual`, whose failure output renders both copies
of the file: the first version of this check emitted 138 KB around a one-line finding.
Restoration is now `addCleanup` plus an `atexit` hook rather than `tearDown` alone, so a raising
test and an interrupted run both put the source back. Neither survives `SIGKILL`, so
`tools/run-change-proposal` printing its diff *before* it runs the suite remains the backstop,
and the helper says so where someone changing it will read it.

*Controls, and the meta-control that matters here.* Disabling `perturb` so it writes nothing
must break the controls that depend on it: **13 failures across the three converted files**, and
exactly **4** in the new capability-notes file — its four perturbation controls — while its fifth,
which asserts the source is pristine between tests, correctly still passes. That split is what
distinguishes controls that depend on the perturbation from controls that would fail for any
reason. The no-op-edit check was separately verified by making one control's replacement
identical to its original and confirming the named failure. Full suite 406 passing, validator
unchanged at 17 P2 advisories and Tier 0 5844/6144 bytes.

*The transferable finding, and it is about the checkpoint rather than about this item.*
`repeated-work.md` asks whether a repeated action should become a tool. It does not ask whether
one already exists, and on this occasion one did, in the same session, committed hours earlier.
**A by-hand count establishes that a procedure is repeated, never that nothing performs it** —
so the search for an existing implementation belongs at the moment the item is written, when the
count is taken. **Amending `conventions/repeated-work.md` to require an owed item to name what
it searched was considered and declined** — one missed search does not carry a convention
change, and the checkpoint stands as written. Two later sessions then duplicated
that implementation without the owed item registering either event, which is the sharper half:
nothing re-reads an owed item against the work that follows it, so an item can be silently
satisfied and still read as outstanding. The nearest recorded relative is the `schema`
dead-code report below, where reading a consumer and grepping one spelling of its producer
produced a claim that was confident, specific and false.

---

<a id="debugging-knowledge-import"></a>
## Debugging-knowledge import, and the test-interpreter repair (2026-09-17)

Two episodes from one session. The first admitted knowledge mined from an operator campaign; the
second repaired the suite that was supposed to be guarding it, and which had been red on `main`
long enough to read as normal.

### The import

The source was a split-grid deflation campaign in an operator working project: eighteen
investigation documents totalling about 1.1 MB, and thirty-five session transcripts totalling
about 1.6 MB, read under an explicit operator instruction to include the transcripts.
`ARCHITECTURE.md` §session-logging permits that as a narrow exception and requires the transcript
be treated as private evidence rather than as canonical knowledge; it was. Extraction staged in
the working project beside the corpus, never in this repository, per
[§validator-not-clearance](ARCHITECTURE.md#validator-not-clearance).

Thirty-five candidates passed the admission test and landed as five commits, one fact class each:
`conventions/diagnostic-rigs.md` with six new `modes/debugging.md` method items; the batch-script
facts; the QUDA autotuning facts; the QUDA development facts with one memory-leaf addition; and
`machines/perlmutter/communication-defects.md`.

*What was rejected, which is the half that stops the next session re-litigating.* Every campaign
timing, speedup ratio, per-rank memory figure and iteration count — **episode tier** under
[§scope-levels](ARCHITECTURE.md#scope-levels) *and* unpublished measurement under `PRIVACY.md`.
The `1133` corruption defect itself, for the same reason; its method residue was admitted as six
of the new debugging-method items, the defect was not. The split-grid scheme and its cost model,
which describe an unmerged feature branch and are not debugging knowledge. A single-bad-node
episode, whose transferable residue was too thin to carry. And `grep -ci nan` matching a MILC
`EVENANDODD` token, which `conventions/running.md` already covers as the anchor-your-patterns
rule — admitting the token would have put one rule in two places.

*Publishability was decided per class at the moment of import*, as
[§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers) requires: method and mechanism publishable;
vendor-defect mechanism publishable after redaction; campaign measurements out; and of three
borderline single figures, only the vendor PMI byte limit admitted, the two that were measurements
of the operator's own application left out. The two admitted vendor defects carry their variable
and symbol names deliberately — an operator ruling, taken after the first draft had genericised
them, on the grounds that a session meeting either failure needs to grep for the exact string.
Node names, job and ticket identifiers, run-directory names and paths stayed out in every draft.

*One published position was reversed.* `software/quda/internals/autotuning.md` stated that manual
tunecache row removal "is not a handbook-supported selective-invalidation method". The corpus
contains a worked instance: thirty-two placement-sensitive dslash-policy rows identified from
source by their `p2p=` field, stripped, and the resulting run showing exactly those rows retuning
and nothing else, inside the discarded first solve. The sentence now keeps the caution, names the
instance, and states the obligations that come with it. The new fact underneath it is that `p2p=`
is a globally reduced boolean rather than placement, so the key is byte-identical across two
placements whose tuned answers differ — which is why the gap had never been noticed.

*What the checks caught that review had not.* `tests/test_reserved_terms.py` found five uses of
`configuration` where §reserved-terms requires `candidate`, in text written by someone who had
read that section the same session. The validator found a `review_by` on a file whose
`observed_on` carried a version anchor. Both are the case for mechanical enforcement of a naming
rule, and neither was visible on re-reading.

*The transferable finding, and it is about the transcripts.* The distilled investigation documents
carried nearly everything; of the candidates admitted, exactly **one** — that piping a module
command into another command runs it in a subshell, so the environment change is discarded and the
check reports on an environment that was never established — came from the 1.6 MB of transcripts
and from nowhere else. Every other transcript passage that looked like a finding was a restatement
of something a document already owned, usually better. That is one admitted fact per 1.6 MB, against
thirty-four per 1.1 MB, and it is direct support for
[§session-logging](ARCHITECTURE.md#session-logging)'s claim that verbatim transcript is the least
dense form of the knowledge it contains. **It is not an argument against ever reading them** — the
one fact was real, and cheap once authorised — but it prices the exception, and the price is why
the rule is do-not-read-unless-asked rather than read-if-present.

### The test-interpreter repair

The suite was red on upstream `f1876d6`: five failures and seven collection errors, unrelated to
the import. Establishing that took three attempts, and the first two were invalid in ways worth
recording. A `git archive` export of `HEAD` compared against the modified tree appeared to show one
extra error — an artifact of the export lacking the agent sandbox's unreadable `.mcp.json`
placeholder, which `shutil.copytree` dies on. A hand-made copy of the modified tree then appeared
to show a different extra failure — an artifact of that copy excluding `.claude` and `.agents`, so
the validator correctly reported the frontend skills missing. **Only the third comparison, with
identical exclusions on both sides, was evidence**; it showed the two trees byte-identical in
outcome, and so the import introducing nothing.

*The cause was one thing.* `tools/run-validator` has never invoked the validator through
`sys.executable`; it goes through `tools/select-python`, which probes for an interpreter carrying
the caller's declared modules, including module-provided ones. The suite never adopted that
contract: eleven test files subprocessed dependency-carrying tools with `sys.executable`, and seven
modules imported `jsonschema` in process. PyYAML was present on this machine and `jsonschema` was
not, which is exactly the seven. The rule the two cases differ by is now stated in
`tests/support.py`: inside a tool already launched through `select-python`, `sys.executable` is
correct, because it inherits a dependency set something established; inside a test it is not.

*What the repair was worth: 341 collected tests became 414.* The seven unloadable modules had been
hiding seventy-three tests, and among them three genuinely broken call sites — `test_slice0.py`
invoking the validator through a bare `python3`, which on this system is 3.6 and too old to parse
the file at all, the precise thing `run-validator`'s own comment warns against. A fourth un-adopted
copy of `handbook_copy_ignore` was found in `test_propose_change.py`; `tests/support.py`'s comment
already recorded that three near-identical copies existed before the helper was extracted, and this
was one the extraction missed. **A collection error is not one failure. It is an unknown number of
tests that did not run**, and nothing in a summary line distinguishes the two.

*The guard was made to fail on purpose, and that is what caught the defect in the guard.* Run under
an interpreter lacking `jsonschema`, `interpreter_for` and `require_importable` skip loudly rather
than falling back — a fallback reinstates the original defect wearing a different error message —
and the first version printed its banner **seven times**, once per module, because several test
modules load `support.py` through `spec_from_file_location` and each got its own copy of the
module-level dedupe state. Seven repeated banners is the cry-wolf failure `conventions/running.md`
names, not a loud warning; the registry now hangs off `sys`, the one object guaranteed shared, and
the banner was verified to appear exactly once. `run_suite`'s new fail-on-skip branch was exercised
directly against all three outcomes rather than assumed, because the degraded run genuinely reports
`OK (skipped=7)`, which reads as success to anything checking only a return code.

*The transferable finding.* A permanently red suite is the cry-wolf failure applied to the one
instrument that would otherwise catch a regression, and it had been red long enough that its
redness carried no information — which is how three real defects sat inside it unnoticed. The
mechanism is worth separating from the moral: nothing here failed to try. The suite ran, reported,
and was read; what it reported was a missing module, and a missing module reads as an environment
problem rather than as an unexercised check. **An environment-shaped failure message is the most
effective way to make a real defect invisible**, because it invites exactly one response, which is
to ignore it.

*What is owed rather than done.* Both conventions the repair establishes are held by habit alone —
nothing prevents the next test from reaching for `sys.executable`, or for a bare `ignore_patterns`,
and a reintroduction passes on any machine whose default interpreter happens to carry the
dependency. Recorded as `ROADMAP.md` X.4. The suite already enforces two naming conventions this
way, in `tests/test_reserved_terms.py` and `tests/test_role_not_index.py`, so the shape exists.

*Scope, stated rather than implied.* The stdlib-only `sys.executable` call sites were deliberately
left alone; only the five tools with third-party imports are in scope, plus three legitimate uses —
a fixture shebang and two assertions about what the session-logging installer pins. The suite was
verified green under the interpreter `select-python` selects and loud under one that fails its
requirements; it has not been exercised on a machine where **no** satisfying interpreter exists,
so the skip path is proven by construction and by the negative test, not by that environment.

## Tuning and QUDA-development import from the same campaign (2026-09-17)

A second pass over the corpus the debugging import had just finished with, run the same day, at the
operator's request and again with the transcripts explicitly in scope. The question was different —
tuning practice and QUDA/MILC development knowledge rather than debugging method — which is the only
reason a second pass over an exhausted corpus was worth anything.

Seven candidates landed as three commits, one fact class each: the QUDA device-memory internals leaf
with pointers from the staggered-memory and eigensolver leaves; the new MILC development leaf; and
three tuning-practice rules across `conventions/diagnostic-rigs.md`, `conventions/measurement.md`
and `modes/tuning.md`. Extraction staged in the working project beside the corpus throughout.

*What made them admissible at all, given the standing deferral.* `ROADMAP.md` parks split-grid
deflation solver knowledge, and the corpus is a split-grid campaign, so the governing question for
every candidate was whether it survives without the branch. Each source claim was therefore verified
against upstream `develop` — `quda f2df42ac4`, `milc 6b9b8a0` — rather than against the operator's
checkout, and only claims present there were admitted. That check paid for itself immediately: the
pooled allocator, the `computeEvals` grow, the one-field-at-a-time deflation space and the duplicate
MILC link-load file are all upstream behaviour, reproducible by anyone with no access to the branch,
while `tol_cycle` — the parameter that turns a restart tolerance into a cycle count — exists only on
the branch.

*The substantive result is a pair, not a fact.* QUDA's pool charges a live allocation the whole
reused block, which the device counter includes and a field total does not; and every allocation is
rounded to the driver's granularity, which the counter excludes because it records requested bytes.
The two run in opposite directions, so the counter is neither an upper nor a lower bound on what the
driver holds, and a residual between a computed total and a measured high-water mark is not
automatically an error in the field formulas. Neither half is useful alone: one would have read as a
reason to distrust the counter upward, the other downward.

*A judgement call worth recording because it will look like an omission.* The band rule in
`diagnostic-rigs.md` — that a knob reaching the behaviour under test only through an integer-valued
comparison has reachable settings that collapse into bands — came from a real four-point fit, and it
is stated with **no worked example**. Naming the parameter it came from would send a reader on stock
QUDA looking for cycles that do not exist there, which is the parked dependency re-entering through
an illustration rather than through a claim. The rule loses concreteness and keeps its
independence; that was the trade, and it was deliberate.

*What was rejected.* Every campaign timing, speedup, iteration count, memory figure and node-hour —
episode tier, and unpublished measurement. The split-grid cycle mapping and every `tol_restart` band
figure, per the deferral above. Split-grid iteration reporting, whose generalisable residue could not
be stated without describing the unmerged orchestrator. The rank-order placement protocol, because
`conventions/measurement.md` already owns that fact and the corpus case differs only in the shared
setting being chooseable rather than constraint-imposed — at most a clause, and admitting it would
put one rule in two places. The campaign's Python tools, of which the pool simulator is the most
generalisable, deferred as a `prefer-a-tool` decision rather than admitted. And retained-mapping
caches as a memory-accounting term, deferred because `machines/perlmutter/communication-defects.md`
already owns those variables as a correctness matter and a second framing would split one object
across two leaves.

*The transcript finding reproduces, and that is the point of recording it again.* The debugging pass
reported one admitted fact from 1.6 MB of transcript against thirty-four from 1.1 MB of documents.
This pass asked a genuinely different question of the same transcripts and admitted **none** from
them: every candidate was carried by an investigation document and verified against public source.
Two passes, two fact classes, one shared conclusion — which is stronger evidence for
[§session-logging](ARCHITECTURE.md#session-logging)'s do-not-read-unless-asked rule than either pass
alone, because the obvious objection to the first result was that it asked the wrong question.

*Two errors caught in drafting, both by checking rather than by reading.* A claim that the MILC-facing
QUDA header includes `quda.h` inside its own `extern "C"` block was wrong — it includes it before
opening that block, and `quda.h` supplies its own linkage. And the trim hazard on `computeEvals` was
stated in the corpus as six deflated Krylov solvers; upstream `develop` now has seven. Both were
one command to check and neither was visible on re-reading the prose.

*Scope, stated rather than implied.* The leaves record mechanisms, not magnitudes; the only measured
quantity admitted anywhere is a 2 MiB allocation granularity, labelled `[observed]` and flagged as a
driver property rather than a QUDA constant. The pooled-reuse and granularity terms have **not** been
separated by experiment — they were derived from source and from a reconciliation between computed
totals and measured high-water marks, which cannot attribute a residual to one alone. And two of the
admitted items correspond to repairs the campaign itself has deferred on blast radius, so the
handbook now records mechanism and repair hazard for changes nobody has made; a session that picks
either up should check the leaf against what it actually finds rather than trusting it.

*What is owed.* `modes/tuning.md` grew by about 800 bytes, on a Tier-1 document already at 13 KB
against P1's 10–15 KB budget for the whole tier. The addition was accepted because a gate on whether
a search starts is useless if it only loads once someone goes looking for it, but the mode document
is now the obvious candidate if Tier 1 has to be cut.

<a id="trial-versus-production"></a>
## The trial-versus-production rule, and why the existing one never fired (2026-09-18)

*The episode.* A tuning session working a staggered-MG campaign divided a trial's setup cost by
its total cost, obtained a share in the high nineties, and reasoned forward from it: *so
solve-side candidates cannot matter.* The trial ran a handful of solves per setup. The share was
arithmetically correct and described the instrument. The operator identified it immediately, and
noted this was not the first time the distinction had been litigated — which is what moved the
response from a correction to a handbook change.

*The forensics, which decided where the fix went.* The rule already existed. `playbooks/tune-solver.md`
§5 said "use the production `N`, not the number of solves in a convenient test"; `modes/tuning.md`
§1 and `software/quda/solvers/staggered-multigrid/tuning.md` gate 1 both required a declared solve
count. All three were loaded in that session and the error happened anyway. So the defect was not a
missing rule but a **placement** one: the rule was stated once, as an input to declare at gate 1,
with nothing guarding the point of use three gates later where a share is actually computed. A rule
that fires only at the start of a procedure does not survive the middle of it.

*A second finding, from the same audit.* The regime vocabulary — setup-dominated, mixed,
throughput-dominated — already existed in `staggered-solver-selection.md`, imported at Stage 3 and
recorded in the Stage-3 entry above. It had never propagated out of the leaf that chooses **between
solver families** into the conventions, the mode documents, or the MG tuning gates, so a session
tuning one solver never met it. Propagation, not invention, was most of the work.

*The first draft was wrong and was rejected.* It required a declared production solve count before
tuning could start. The operator rejected that: it would tax every campaign setup, and it is wrong
about exploratory tuning, where the regimes are an **output** of the measured crossovers rather than
an input. The accepted form leads with the purpose of a trial — a cheap instrument for pricing the
terms of a cost model — and handles the unknown case by reporting `C(N) = I + N·R` and the crossover,
which is strictly more informative than a winner and needs no declaration at all. `ARCHITECTURE.md`
§7.1a carries an explicit clause saying an agent that blocks on the number has misread the section;
`ROADMAP.md` §6 records the rejection so a future session does not tighten it back.

*Acceptance evidence.* Nine files: `ARCHITECTURE.md` (§7.1 mode sketches, new §7.1a, one §1.4
decision row), `ROADMAP.md`, `conventions/measurement.md`, both work-mode documents, the MG overview
and its tuning leaf, plus `tools/amortize-cost.py` and `tests/test_amortize_cost.py`. The harness
reported 9 changed files, indices current, 669 references resolved, 422 tests passing, Tier 0
unchanged at 5844/6144 bytes and developer documents at 196479/200000.

*The tool is the half with teeth, and it was made to fail on purpose.* `amortize-cost.py` reports
pairwise crossovers with **no** solve count supplied, and reports shares, per-solve costs and
rankings **only** at counts it is explicitly given; there is no default and none is inferred. Per
[§decisions-operation](ARCHITECTURE.md#decisions-operation)'s rule that a new tool is not trusted on
a passing run, `--solves` was perturbed to default to a small count — reintroducing exactly the
defect — and 2 of its 7 tests failed, including the behavioural one rather than only the source-text
assertion. Restoring passed all 7.

*A privacy defect caught in the hand pass, not by the harness.* The first version of the test
fixture used a real campaign's measured setup total, solve total and node count as its example
inputs. Under [§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)'s sharp filter those are
measurements we made rather than published properties of an ensemble, and they would have been
irreversible in a public repository. They were replaced with synthetic round values that exercise
the same property — a setup share that is dominant at a small solve count and a minority at a large
one — at no cost to the test. The mechanical checks passed both before and after, which is the point
of the harness ending by naming the categories it cannot decide.

*Scope and what is owed.* The three regime names are reused from the existing leaf rather than
coined, so nothing needs refitting. No numerical band was added anywhere. The MG gate-1 claim that
multigrid has the widest one-time-to-recurring ratio of the three staggered solvers is a structural
statement about what setup builds, not a measured ratio, and is deliberately unquantified. Still
owed: the working-directory analysis that triggered this still frames its candidate ordering off a
trial-derived share and should be re-cut against the new rule before anyone acts on it; that is
project work under the project's own instructions, not handbook material.

## The suite took minutes because every interpreter start searched a shared filesystem (2026-09-21)

A developer-mode session reported that `tools/run-change-proposal` took about seven minutes on a
Perlmutter login node, which makes an ordinary documentation change impractical. It now takes
**55 seconds**, and the suite alone went from roughly **420 seconds to 49**. Three changes did it;
none of them touched what is tested.

*The dominant cause was an unexamined consequence of an earlier correctness fix.* On 2026-08-28
`--allow-module-load` was added because the validator could not run at all: the only interpreter on
`PATH` carried PyYAML but not `jsonschema`. That entry checks the validator returns identical
results under 3.11, 3.12 and 3.14, and says nothing about cost — reasonably, since the alternative
was a tool that did not run. But a `module load` injects `PYTHONPATH` entries, and on this machine
they were `/global/common/software/nersc9/numba-cuda-580-patch/patch` and `/opt/nersc/pymon`. Both
exist to place `usercustomize` / `sitecustomize` hooks, which Python imports at every interpreter
start, and both sit on a shared filesystem that Python then searches ahead of everything else on
every import. Measured over three rounds, the validator took **1.26 s with `PYTHONPATH` unset
against 3.38 s with it** — 2.7x, paid once per subprocess. `tools/select-python` now drops those
entries, but only after proving with that same interpreter that the caller's declared requirements
still import without them; a caller that declares nothing keeps whatever it was given, because a
bare version check passes regardless and would be dropping the path untested. One module through
the dispatcher went from 43 s to 13 s.

*This repository cannot be harmed by that drop, and the check is recorded so a later reader need
not redo it.* Every import across `tools/` is stdlib or one of `yaml`, `jsonschema`, `tomli` — all
declared requirements the probe tests — and nothing imports numba, CUDA or the site monitor. The
monitor's removal is the stronger form of a decision already taken: the dispatcher has exported
`NERSC_PYMON_DISABLE=1` since 2026-08-17, after PyMon appended MUNGE text to otherwise valid
checker JSON. That export stays, and the forced-monitoring regression still covers it, because the
regression turns on the variable rather than on the path. The failure mode if a future tool does
need an undeclared site module is a loud `ImportError`, not a wrong answer; the residual unknown is
that this was measured on Perlmutter only, and the guard is machine-independent by construction
rather than by test.

*The second change was the validator parsing YAML in pure Python, 3.2 times over.* Profiling put
58 % of its runtime inside PyYAML's scanner, with 266 parses of about 84 distinct documents.
libyaml was present and unused. `tools/validate-knowledge.py` now selects `CSafeLoader` when the
build has it and memoises on document text, which is exact because nothing rewrites a file while a
validation runs; callers mutate what they get back, so the cached object is never handed out
directly. The tool went from 3.69 s to 1.22 s with **byte-identical output**.

*The third was a latent fragility the investigation exposed rather than caused.*
`tests/test_amortize_cost.py` imported `support` without putting `tests/` on `sys.path`, relying on
`unittest discover -s tests` to have done it. It was the only one of the fifteen modules importing
`support` that did so. Under any invocation naming the module directly it raised
`ModuleNotFoundError` and its seven tests did not run — 416 reported instead of 422 — and inside an
experimental parallel runner it loaded or failed **depending on which modules shared its worker**.
A test result that depends on scheduling is worse than a slow suite.

*A rejected approach, recorded because the reasoning is the transferable part.* The session first
built a parallel runner splitting modules across workers, with the modules that rewrite real files
through `PerturbationMixin` held back to a serial phase. Measured back to back it was **slower** —
280 s against 100 s — for two reasons that outlast the experiment: the perturbing modules cannot
overlap anything, and cost hints taken from in-test time do not predict wall time, which is
dominated by subprocess latency. The comparison was also confounded, since runs issued directly did
not pay the `PYTHONPATH` penalty that runs through the dispatcher did. It was removed. What remains
useful is the measurement behind it: the suite makes **322 subprocess launches accounting for 95 %
of its wall time**, so at about 0.056 s per interpreter start roughly 18 s is a floor for the
current test design, and the way past it is fewer launches rather than more workers. Merging test
modules would not help at all — all 34 already import in one process, in 0.6 s.

*Still owed.* Two further reductions were identified and deliberately not taken: 132 launches of
`gpu-profile-summary.py` costing about 20 s could largely move in-process, and `select-python`'s own
7 invocations cost 11.8 s because each re-runs module discovery. The first trades away testing the
CLI as a program, which is the same isolation `propose-change.py` deliberately keeps for the
validator; the second needs a cache whose staleness would fail confusingly. Both were judged to cost
more than the remaining ~20 s is worth, and neither is blocked if that judgement changes. The suite
step also reports only `unittest`'s internal timing, which is why a fourfold environmental swing
read as a constant seven minutes and cost a long investigation to see through; giving it a
wall-clock line is a cheap thing a later session should do.

## 2026-09-21 — Staggered-MG device memory model: investigation, five refuted repairs, no fix

**Trigger.** A campaign measured `endQuda Device` 19.4% above `mg-fit` at 0.06 fm on a
four-level hierarchy the tool rated inside its envelope. The operator rejected a refit and
asked for a cause.

**What was established.** The model under-predicts four-level runs and over-predicts
three-level ones, reproducibly, on an independent 0.09 fm campaign at the model's own anchor
revision: 16 candidates, 54 trials. Neither direction lies inside the published
`rms 3.9%, maximum 10.7%`. The three-level error is worst at `nvec_1` outside the fitted 64.
Six source-exact allocation facts came out of it and are recorded in
`software/quda/internals/staggered-mg-setup-allocation.md`; a seventh, reconstruct forcing a
gauge copy in the KD build, is in `milc-gauge-reconstruct.md`.

**Five repairs were proposed, implemented and refuted by test.** Recorded so they are not
re-attempted:

1. *KD-build transients.* The KD inverse build co-allocates four KD-sized fields where the
   model counts one. Fits the four-level shortfall at 0.09 fm almost exactly, but the model is
   constant across those candidates, so the agreement does not discriminate it from any
   other constant of similar size. Unresolved rather than wrong.
2. *A complete-hierarchy resident phase.* Implemented. It is the **smallest** phase, never
   wins, and changes no prediction.
3. *Union of construction cohorts instead of `max`.* Improves three-level, makes four-level
   worse (rms 8.9% to 11.5%).
4. *Setup workspace scaling with `n_vec_batch`.* Refuted directly: the `nvec_1 = 24` (batch 1)
   against `nvec_1 = 32` (batch 16) pair differs by 906 MiB where the hypothesis needs ~12,500.
5. *Block-orthogonalisation workspace.* Refuted from source — it allocates nothing.

**What was not established, and matters most.** Three fitted constants — `setup_ws`,
`copy_factor`, `cg_equiv` — each exceed the field inventory that can be counted from source,
by 5.8x, 2.8x, and an amount the leaf already flags as a lower bound. A mechanism was
proposed (QUDA's pooled `device_free_` never decrements the device counter, so the counter
reports retained blocks rather than co-residency) but **never tested**, and it should not be
repeated as a conclusion. The discriminating experiment is one short run with
`QUDA_ENABLE_DEVICE_MEMORY_POOL=0`, where frees reach the driver and the counter becomes the
instantaneous high-water the model actually predicts. Prediction on record: at 0.09 fm,
`nvec_1 = 64`, `b1 = 4 4 4 6`, the figure should fall from about 24 GiB to about 16.

**The one change that improved the model was tried, and it breaks the calibrated regime.**
Replacing `setup_ws` with its source-counted value (ten fields per right-hand side,
batch-scaled, `3,072 B` per site against the fitted `17,787 B`) takes three-level mean from
+11.02% to +0.22% and rms from 15.25% to 10.81%, and is inert across the independent
four-level set. On that evidence it looked safe. It is not: in both of the memory leaf's own
published worked examples -- four levels, `nvec_1 = 64`, MMA, on the two largest documented
lattices -- the counted value is small enough that **the winning phase changes from A to B**,
and the device estimate falls by `12.7%` and `11.2%`. Both moves are downward, the
under-prediction direction for a capacity decision, and they land in the regime the published
error was fitted on. Worse, phase A ceasing to win contradicts the standing section that names
phase A the floor at a fixed placement and derives its invariance to level count, aggregation
blocks, coarse near-null counts and MMA -- invariances that are properties of phase A, not of
phase B.

So the `5.8x` gap is not slack in an under-determined parameter. The fitted coefficient is
load-bearing exactly where the fit was validated, and the independent set that looked
indifferent to the change is indifferent only because phase A rarely wins there. A source
count that is right about what the workspace contains and wrong about its size by `5.8x` is
evidence that something else is inside phase A, not a licence to shrink it. Revisit with the
pool experiment, which bears directly on whether a phase total is a co-residency figure at
all; do not ship the counted value as a substitution.

**Method note.** Four structural hypotheses were proposed before the cheapest discriminating
measurement was run, and two claimed results were later found to rest on vacuous tests — a
lint that exited early, and a model that was constant across the candidates being used to
validate a correction. Test the discriminator first.

## 2026-09-21 — A real rule, uncited, was twice reported as spurious; citations are now permalinks

`quda_staggered_geometry.py` and `quda-staggered-memory.py` both reject a first-aggregation
block with an odd extent in any direction. Neither carried a citation. The rule is real:

```cpp
// check if we can safely coarsen the KD op
if (dirac == QUDA_STAGGEREDKD_DIRAC || dirac == QUDA_ASQTADKD_DIRAC)
  for (int d = 0; d < 4; d++)
    if (geo_bs[d] % 2 != 0)
      errorQuda("Invalid aggregation size geo_bs[%d] = %d for KD operator, "
                "aggregation size must be even", d, geo_bs[d]);
```

It is gated on the KD-family diracs, which is precisely why it binds at level 1, where
`ASQTADKD` is the operator `block1` coarsens, and never below it. The tools were right, and
their error wording already mirrored QUDA's.

**It has now been searched for, missed, and reported as having no source twice.** Once on
2026-08-29, caught within the same session. Again on 2026-09-21, caught only because the
operator remembered the rule had been added deliberately and the earlier session's log still
existed. Both searches had `coarse_op.cuh` open — at the long-link rule, which sits about
180 lines below the rule being looked for, in the same file. The second search also reported
three separate greps as exhaustive when each had been truncated by `head` or run against a
glob that omitted `*.cuh`.

**A supporting run was misread as confirming the dismissal.** `staggered_invert_test` with a
first-aggregation block of `3 3 3 6` printed `Transfer: using block size 3 x 3 x 3 x 6` and
`Transfer operator done`, and that was taken as proof QUDA accepts the block. It is not: the
KD check runs in the coarse-operator build, downstream of transfer construction, so the log
lines that were grepped could not have shown it either way. An observation that cannot
distinguish the hypotheses is not evidence for one of them.

**What changed.** Every source-derived predicate in both tools now carries a github blob URL
pinned to the full 40-character hash of the revision the tools model, with a line range, plus
a dated re-verification against the revision the campaigns actually build. Bare `file:line`
citations are the defect being fixed, not the format being extended: between those two
revisions the two `coarse_op.cuh` rules moved by 50 and 56 lines, and a drifted citation
reads exactly like a missing one. The existing `coarse_op.cuh:1217-1220` citation for the
long-link rule was correct at the modelled revision and wrong against the build, which is the
failure mode in miniature. `tests/test_source_citations.py` pins the convention: every QUDA
link resolves to a full commit rather than a branch, both tools cite the revision they claim
to model, and the KD rule is cited by name in both.

**No behaviour changed.** The predicates, their messages, and every exit status are identical;
this commit is comments and tests.

## 2026-09-21 — The 1024 aggregate cap: three corrections and a margin field

The overview's statement of QUDA's aggregate cap was wrong in three ways at once, and the
combination is what let a candidate's margin be misread.

1. **One predicate, where source has three.** Block orthogonalization requires the block
   product to be not `1`, even, and at most `1024`. Only the last was documented.
2. **The requested block, where source uses the executed one.** The page said the cap binds
   "the product of the requested block extents", three lines after saying that the requested
   `geo_block_size` is not necessarily the executed one. A requested product above `1024` is
   not by itself illegal: `4 6 6 8`, product `1152`, aborts where the local `t` extent is `48`
   and passes where it is `24`, because the `t` block halves to `4` and the executed product
   is `576`. Screening the requested block rejects candidates QUDA would run.
3. **The first aggregation, where source binds every one.** `Transfer::reset` calls block
   orthogonalization for each aggregation transfer, and returns early for the three KD types —
   which is also why "optimized KD requires unit geometric block volume" and "an aggregate may
   not be `1`" are not in conflict, a pairing the page stated without reconciling.

**The mechanism behind the original misreading is a name collision in QUDA.** Two different
quantities are called `aggregate_size`, in errors that both say "aggregate size": block
orthogonalization's bare geometric product, which the cap binds, and the transfer
constructor's product times the fine colour and spin factors, which bounds `nvec`. The
decomposition tool already named them apart, as `block_volume` and `aggregate_space_capacity`,
but reported both at every level and said which the cap binds nowhere. A four-level candidate
was recorded as `∏block1 = 256 <= 1024` when its first-aggregation block volume was `1024`,
exactly at the cap; the `256` was the second aggregation's space capacity. It stayed legal, so
nothing failed — only the margin, from an apparent 75 percent headroom to none.

**The fix is a field, not a sentence.** Each level now reports `block_volume_cap` and
`block_volume_headroom` next to `block_volume`, and nothing comparable next to
`aggregate_space_capacity`, so the substitution that produced the error has no shape to take.
On that candidate the first aggregation now reads `block_volume_headroom: 0`. The cap also
moved into a named constant beside its permalink rather than appearing as a bare `1024` in a
comparison.

**Method note.** The perturbation checks that this handbook requires of a modified tool were
briefly fooled by stale bytecode: a `sed` edit of `1024` to `2048` is byte-for-byte the same
length, and the `__pycache__` entry outlived the restore, so a suite run reported failures
against a file that was already correct. Clear `__pycache__` between perturbations, or the
procedure that exists to catch vacuous tests can manufacture spurious ones.
