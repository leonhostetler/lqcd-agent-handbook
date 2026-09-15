# LQCD Agent Handbook — Roadmap

**Status:** Slices 1 through 3 are accepted. Slice 0c is accepted: its full cold-session
matrix, including both Claude cases, has passed. Slice 4 remains in progress. **Slice 6 is accepted**
(2026-09-15): Stages 0 through 5 landed on 2026-09-14, its three acceptance checks were
exercised five times — 2026-09-14, and four times on
2026-09-15, and **all three are accepted**. Check 1 was operator-graded on the fourth exercise.
**Checks 2 and 3 were operator-graded on the fifth**, which was the first to put either under
load, and did so on a capture that arrived unconstructed rather than one built for the purpose.
Qualifications on all three grades are recorded in the Slice 6 section rather than waived; the
one they share is that each grade was taken on evidence reported by the session under test.
A fourth check, which would have re-pointed the source suite's scored scenarios at a handbook
hypothesis record, was **specified and removed**; the Slice 6 section records why, and what each
exercise produced. The operator-directed solver import through Stage 5 is published; solver-import
Stage 6 is indefinitely deferred while split-grid deflated CG remains in development, testing, and
tuning.

**NEXT ACTION:** Close the remaining automation the acceptance exercises generated, then return
to Slice 4. **The pre-first-kernel window breakdown landed 2026-09-15** as
`gpu-profile-summary.py window-breakdown`, with the definition in
`conventions/profile-metrics.md` and the step in `playbooks/analyze-profile.md`; it describes
what `idle-attribution` can only size, and three controls cover it — summing categories instead
of merging, reporting an untraced category as `0.0`, and dropping the untraced caveat — each
asserting its perturbation landed. **Two items remain owed.** One crossed [§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s threshold during the
exercises and is owed rather than optional. **The untraced-control comparison was reassigned to
Slice 4 on 2026-09-15**, where `tools/extract-milc-timings.py` — a Slice 4 deliverable that has
not been written — is the run-log reader it will be built into; one floating item remains.

**Launch-geometry extraction for the tunecache-warmth gate** — owed on the next QUDA
performance session rather than now. `software/quda/profiling.md` makes it a mandatory gate
before reading call counts, launch geometry or duration spread, and it is presently satisfied by
hand. It is not a one-line addition: `KernelRow` carries only `total_threads`, the six extents
being collapsed in `nsys.py`'s SQL and absent from rocpd entirely, so it needs the row type
extended and an `available: False` path. **The parallel rank loader is deliberately not
on this list** — three observations crossed a counter built for silent arithmetic errors, and a
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

<a id="current-slice-state"></a>
## Current slice state

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

**The untraced-control comparison lands here** (assigned 2026-09-15), not in Slice 6. A Slice 6
acceptance session performed it by hand six times, which crosses
[§prefer-a-tool](ARCHITECTURE.md#prefer-a-tool)'s threshold, and it carries a failure that
reverses its own conclusion: including the control's first solve moves its mean roughly
four-fold and yields "tracing is nearly free", the opposite of what the data says — arithmetic
that looks entirely ordinary. It is not a profile subcommand, because it combines a profile
figure with an application run-log figure, and `tools/extract-milc-timings.py` above is the
run-log reader it needs. Building it as part of that tool rather than beside it is what keeps one
canonical reader of MILC timing output. `conventions/measurement.md`'s first-solve rule is what
the tool must apply, and is the rule the hand passes kept getting wrong.

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
tools. Linked MILC MG runtime validation landed on 2026-09-02 for one hierarchy and
placement. Deflated-CG runtime validation, ensemble-scoped operational imports, and the slice
acceptance checks remain pending. A mechanistic MRHS memory model
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
`modes/performance.md`, `playbooks/analyze-profile.md`, and the offline profile-extraction and
diff tools, harvested from the operator's PerfAdvisor working tree with the exact proposed
handbook additions screened at intake. [§profile-analysis](ARCHITECTURE.md#profile-analysis)
governs the split: extraction ships as a tool, interpretation as leaves, no second agent is
wrapped.

The import is staged. **Stage 0** recorded the architecture decision. **Stage 1** landed
`modes/performance.md`. **Stage 2** adds the extraction tool, carrying the ingestion and metric
layers with the agent, provider, caching and preflight layers dropped; its subcommands must cover
every aggregation a session would otherwise recompute by hand, and its raw-query path is
read-only, row-capped and interruptible. **Stage 3** adds the analysis playbook, a shared
metric-definition convention, and the hypothesis record schema. **Stage 4** adds the
software-scoped layer the source analyzer could not hold at all: kernel-name-to-source
resolution, the cold-autotune-cache reading of duration spread, and application-driven phase
boundaries. **Stage 5** gives tuning mode the code-change axis and closes the prediction loop on
a hypothesis's claimed runtime fraction. A **Stage 6** was planned, to re-point the source
suite's scored scenarios at a handbook session's hypothesis record; it was withdrawn on
2026-09-15 with the fourth acceptance check, for the reasons recorded there.

Stages 3 through 5 landed 2026-09-14. Stage 5 closed the loop the earlier stages only described:
`tools/hypothesis-record.py` derives a hypothesis's speedup bounds instead of trusting them and
refuses a figure naming no query it came from, which removed performance mode's last standing
limitation. Tuning mode gained source changes as a declared search axis, a section on what makes
a source trial different — it costs a rebuild that is itself a job, it can change the result, and
it invalidates warm state selectively — and a section on acting on a hypothesis, where the
claimed fraction is treated as a standing prediction and the realised change is compared against
its bounds. A fraction inflated across trials is recorded as a defect in the attribution rule
rather than absorbed by widening a tolerance.

The loop stops at submission, and that is where it stays. A self-resubmitting loop was the one
structural gap between this chain and a fully hands-off one, and it was **set aside on
2026-09-15** rather than deferred toward: its use is hypothetical, and if it is ever wanted the
operator specifies it up front. The interim behaviour is recorded as zero machinery that cannot
overspend, which is precisely the property such a loop removes — so the trade would need stating,
not discovering.

**The calibration harness stays outside the handbook.** The source suite's injected-bottleneck
profiles, ground truth and scorer hold one property — a profile-blind baseline scores near zero —
and the handbook has no equivalent, its acceptance tests being qualitative. They remain in the
working directory as the observations that calibrate the contract, under
[§records-in-working-directory](ARCHITECTURE.md#records-in-working-directory); the handbook ships
the rule and never the numbers. A baseline on the current analyser was owed only to give the
withdrawn Stage 6 a before-number, and is owed no longer.

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

### Slice 7 — automation and enforcement
`tools/log-session-*.{sh,py}`, the offer-only installer, and the detect-and-offer check
landed early in Slice 0c ([§session-logging](ARCHITECTURE.md#session-logging)). Slice 7 retains
knowledge-capture hooks and the user-mode write guard, and adds a `PreToolUse` guard that
intercepts a write to a batch script and runs `tools/check-batch-script.py` before the write
lands ([§batch-scripts](ARCHITECTURE.md#batch-scripts)). Until it exists the checker is
advisory and agent-invoked, which is the same interim posture the budget rule already takes:
only intercepting the call enforces, and an installer is required either way.
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

**Settled 2026-09-15, recorded so they are not reopened.** Three questions the third Slice 6
exercise raised, and the operator's rulings on them. *Check 1's `derived_by_hand` clause* tests
declaration, not emptiness — which the 2026-09-14 amendment had already settled, so the ruling
restores it rather than changing it, and the clause is now enforced per figure instead of
trusted. *An untraced control run* is recommended and not required, because it cannot be
retrofitted onto a capture already taken; the labelling of uncontrolled figures is required,
because it is free. *Cold* is defined at check 1 above: no access to a prior analysis of the
capture under test, with application and software knowledge explicitly not contamination. The
operator also ruled that the acceptance re-run happens in a fresh session rather than in the one
that produced the analysis, which is why the next action names a new profile.

**Settled 2026-09-15 (fifth exercise), recorded so it is not reopened.** *Whether bounding an
untraced category from the idle residual is gap-reporting or is reasoning past the gap.* **It is
gap-reporting, and the ruling is narrow.** What the residual bounds is the untraced category's
contribution to GPU-stalling idle within the window, as an upper bound and never a measurement;
the bound is admissible only when the capability gap is reported alongside it and no hypothesis
is ranked on it. It says nothing about time the category spent overlapping kernel execution,
nothing about imbalance, which is cross-rank, and nothing about the category's total. A reading
wide enough to support a communication finding is the failure check 2 exists to catch, so the
mechanism is written into `conventions/profile-metrics.md` with the three exclusions attached
rather than left to be re-derived.

---

<a id="deferred-decisions"></a>
## 11. Deferred decisions

Parked deliberately, each with the **trigger** that should un-park it rather than a slice
number. A deferred decision is only safe when the interim behaviour is conservative; that
column is the test. On the move into the repo ([§plan-ships-with-handbook](ARCHITECTURE.md#plan-ships-with-handbook)) this section travels with `ROADMAP.md`.

| Decision | Interim behaviour | Un-park when |
|---|---|---|
| **Enforcement of the job-submission budget** — agent instruction, a `lqcd-submit` wrapper, or a hook | [§budget-rule](ARCHITECTURE.md#budget-rule)'s default: **no budget stated ⇒ the agent prepares the job and hands the operator the submit command.** Zero machinery, cannot overspend | **Operator-initiated only** (ruled 2026-09-15). The operator declares, up front and in full, what an unattended submission loop would do — its ceiling, its ledger discipline, and the stop that fires at the ceiling — before any of it is built. It is not un-parked by an agent finding a loop convenient, nor by a tuning or performance workflow reaching the point where submission is the only manual step. The conservative default costs nothing, and the case for changing it has not arisen |
| **Enforcement of user-mode write protection** — instruction, file permissions, worktree, or a `PreToolUse` hook | The P6 instruction of [§handbook-modes](ARCHITECTURE.md#handbook-modes), plus `lqcd-start-session` reporting an unclean handbook tree at session start so a stray edit surfaces the same day | The repo stops changing daily. Read-only permissions fight developer mode, which is *most* sessions during bootstrap. Hooks need an installer regardless ([§loading-invariants](ARCHITECTURE.md#loading-invariants)), so this rides with slice 7 |
| **Sub-file provenance** — claim IDs with metadata stored separately, versus file-level frontmatter | File-level frontmatter ([§knowledge-atom](ARCHITECTURE.md#knowledge-atom)), and **knowledge files are kept small and atomic** so it stays adequate | A file starts accumulating claims from materially different dates, versions or evidence kinds. Not needed at slice 0, and the machinery costs more than the problem until then |
| **Whether any part of the handbook should be served over MCP** rather than as files, skills and scripts | **None.** Knowledge stays as markdown and YAML read directly; procedures stay as skills plus `tools/` scripts. Works on every machine with no runtime | Any of three: (a) the handbook needs to reach data **too large to commit** — a cross-machine run database is plausible, and would be a *separate* server the handbook talks to, not handbook infrastructure; (b) something genuinely **remote** becomes necessary, such as live job status across machines from one session; (c) slice 6 finds **PerfAdvisor is already service-shaped**, making this a question about preserving an existing shape rather than adding one |
| **Whether session logging should also archive the raw transcript JSONL** for full provenance, tool I/O included ([§session-logging](ARCHITECTURE.md#session-logging)) | **Prose-only.** The shipped logger stays as the operator wrote it; the JSONL under `~/.claude/projects/` is the true last resort where it survives | The prose record proves insufficient to reconstruct an episode the operator needed back — or a machine rebuild/scratch purge destroys a JSONL that was wanted. Note the cost before adopting: much larger files in the working directory, and a far bigger privacy surface, since the JSONL contains every file read and every command run |
| **Whether the handbook is measurably cheaper than the rediscovery it replaces** | No measurement. Cold-session tests stay qualitative | The handbook becomes big enough to feel slow to navigate. **If implemented, it is the lightweight version** (below) — not an A/B harness |
| **A retained validation set for the fitted tool models** — a small, screened set of `(inputs -> measured counter)` rows committed as test fixtures, so a fit's published error is re-derivable in-repo | **None committed.** `tools/quda-staggered-memory.py` carries its population and error strings as prose, and the corpus behind them is not in this repository ([§non-public-evidence](ARCHITECTURE.md#non-public-evidence)). The 2026-09-02 regression test pins the documented examples to the model's **own output**, so it detects drift but cannot detect that a model was wrong to begin with. Under [§decisions-knowledge-contract](ARCHITECTURE.md#decisions-knowledge-contract) no fit may be revised meanwhile, which is conservative but leaves known one-sided errors uncorrected | A fit needs revising rather than annotating — the open case is whether the MG model's phase A genuinely peaks before the coarsest eigensolve, or whether its fitted setup-workspace constant absorbs an eigenspace term that was near-constant across the corpus; those imply opposite repairs and no in-repo evidence distinguishes them. Needs a publishability decision on the fact class first ([§ensemble-numbers](ARCHITECTURE.md#ensemble-numbers)) |
| **A controlled vocabulary for a hypothesis's `bottleneck` field** — a fixed enum versus free text | **Free text**, per `schemas/hypothesis.schema.json`. The obvious vocabulary to adopt is the source analyzer's eight-value enum, and that project's own evaluation shows it is too coarse to discriminate: three distinct scenarios all legitimately take one value, which is why its scorer needs a second keyword gate on top of the enum. Adopting it here would import a known defect into a schema, where it is expensive to correct. The cost of deferring is real — nothing groups records mechanically, and two analyses may name one pathology differently | Enough hypothesis records exist to show which names actually recur. The vocabulary should then be derived from them rather than guessed, and it is a `schema_version` bump |
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
