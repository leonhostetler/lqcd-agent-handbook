---
title: MILC staggered inverter types
summary: The four staggered inv_type choices, their normal-equation paths, parity behavior, set dispatch, initial guesses, and backend requirements.
scope: [software:milc, solver:staggered-inverter]
load_when: Selecting, debugging, or comparing a MILC staggered inv_type or interpreting its parity work.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quark_types.h#L175-L213
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L203-L365
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L436-L708
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L723-L1305
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn.c#L15-L108
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_multicg.c#L763-L823
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/setup.c#L530-L835
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/make_prop.c#L72-L341
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/setup.c#L583-L601
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/setup.c#L770
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/setup.c#L809-L827
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/params.h#L113
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quark_types.h#L182-L187
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L650-L653
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L1081-L1084
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_multicg.c#L784-L787
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L748-L826
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/mat_invert.c#L645-L656
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/mat_invert.c#L1087-L1094
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/d_congrad5_fn_quda.c#L136-L160
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/mat_invert.c#L480-L507
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/d_congrad5_fn_quda.c#L158-L169
  - operator's screened benchmark records (2026)
observed: "2026-10-07"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
---

# MILC staggered inverter types

MILC's generic staggered interface defines four `enum inv_type` values. In
`ks_spectrum` they are selected by the input strings `CG`, `CGZ`, `UML`, and
`MG`. This page covers the staggered `generic_ks` implementations, not Wilson or
clover inverters that reuse the same control structure.

## Algorithm and parity behavior

| Input | Implementation | Solve structure | Initial state and parity consequence |
| --- | --- | --- | --- |
| `CG` | `mat_invert_cg_field` | Forms `Mdag * src`, then solves the normal equation independently on even and odd sites. | Supports a supplied destination as an initial guess. At nonzero mass, applying `Mdag` to a parity-pure source generally populates both parities, so source parity does not normally remove one solve. |
| `CGZ` | `mat_invert_cgz_field` | Solves the even and odd systems directly from `src`, then applies `Mdag` to obtain the full solution. | Allocates a zero high-mode guess; optional deflation may seed low modes. A parity with exactly zero source norm is returned as a zero solution with zero iterations. |
| `UML` | `mat_invert_uml_field` | Forms `Mdag * src`, solves the even system, reconstructs the odd solution from the even solution and source, then polishes the odd system. | The primary solve parity is always even. Reconstruction divides by `2 * mass`, so this implementation is not a mass-zero path. With an even-pure source the polish converges in at most one iteration; with any odd support it is a real solve (see below). |
| `MG` | QUDA multigrid wrappers | Solves the full staggered Dirac system through QUDA rather than exposing separate MILC even- and odd-normal-equation solves. | Requires the QUDA GPU multigrid build path. A source that is merely parity-pure is still one full-system solve; only a completely zero source is trivial. |

`CG`, `CGZ`, and `UML` overwrite `qic->parity` while executing their internal
even and odd phases. `ks_spectrum` sets the propagator control parity to
`EVENANDODD`; its input does not select which internal parity these algorithms
solve first.

The zero-source shortcut is exact: the selected parity norm is globally summed.
If it is zero, MILC zeros that parity of the destination, marks the solve
converged, and reports zero iterations. For a block solve, the norm is summed
over every right-hand side, so the parity is skipped only when all block sources
are zero there.

## Choosing with source parity

Classify the source using
[`quark-source-types.md`](quark-source-types.md) before reasoning about parity
work.

- `CGZ` is the only choice whose normal-equation right-hand side is the original
  source. A fresh parity-pure source can therefore eliminate the absent-parity
  solve through the zero-source check.
- `CG` first applies `Mdag`; its parity support is not generally the same as the
  original source.
- `UML` always pays for the even primary solve and uses the odd system only for
  reconstruction and polishing. Do not assume that exchanging even and odd
  source support gives symmetric work: an even-pure source makes the polish
  free, an odd-pure one makes both parities real solves (next section).
- `MG` is a full-system QUDA solve. Treat source parity as a property of the
  right-hand side, not as a request for a different MG solve parity.

These mechanisms predict solver work, not wall-clock ordering. Benchmark the
executed path before making a performance choice, and retain convergence and
correctness checks.

### UML with an even-pure source: the odd polish costs at most one iteration

`[source]` `mat_invert_uml_field` rebuilds the odd solution from the even one as
`dst_o = (src_o - Dslash_oe dst_e) / (2 mass)` and then polishes it with a CG call on the
odd normal equation, whose right-hand side is `(Mdag src)_o`. Whatever the source, the
rebuilt odd residual is `-Dslash_oe r_e / (2 mass)`, with `r_e` the residual the even solve
stopped at. How much the polish then has to do is set by the size of the odd right-hand side:

- **Even-pure source** (`src_o = 0`): the even right-hand side is `2 mass src_e` and the odd
  one `-Dslash_oe src_e`, so the rebuilt odd solution already meets the same *relative*
  tolerance the even solve met. The polish converges at entry or after one iteration.
  `[reproduced ×2819]` every UML solve of one 2026 benchmark series on a 144³×288 HISQ
  ensemble — three gauge configurations, eleven masses, 27 to 288 nodes, with and without
  even-space deflation — reported `iters = 0` or `iters = 1` on its odd `CONGRAD5` line, with
  the odd `final_rsq` at or below the even one; the polish ran undeflated throughout (MILC
  before `d17e9559`).
- **Any source with odd support**: the odd right-hand side gains a `2 mass src_o` term and the
  even one a `Dslash_eo src_o` term, so the rebuilt odd relative residual exceeds the even
  one by a factor of order `|Dslash| / (2 mass)` or more — `[inferred]` from the same
  identity. The polish is then a real solve, and for an odd-pure source the even solve is one
  too, since its right-hand side `-Dslash_eo src_o` carries no small factor.

**What follows for cost accounting.** With even-pure sources — a `point` source at an even
site, `even_wall`, a corner wall at even `t0` — a UML propagator costs one parity solve, and
its second `CONGRAD5` line is the polish converging, not the zero-source shortcut: the odd
right-hand side is not zero. A comparison of the CG family against multigrid on such sources
charges the CG side one parity solve per propagator against multigrid's full-system solve, so
**state the source parity with the comparison**: a source with odd support adds a real odd
solve to the CG side and nothing to the multigrid side. `inv_type CG` gains nothing from an
even-pure source; its odd solve starts from the supplied guess against the same nonzero
right-hand side.

**What follows for deflation.** From `d17e9559` the QUDA call site requests deflation for
every parity of a propagator that says `deflate yes`, and QUDA builds the odd space from the
even one at the first odd solve
([`staggered-deflated-cg.md`](../../quda/solvers/staggered-deflated-cg.md)); with an even-pure
source that first odd solve is the polish above. `[inferred]` A deflated UML propagator from
an even-pure source then pays the odd-space reconstruction, and its memory, for a solve that
needs at most one iteration. The trade is unmeasured, and the propagator block has no
per-parity switch: `n_ev_deflate` is set from `deflate` for both parities and zeroed only by a
nonzero relative residual. Through `6b9b8a06` the polish is undeflated and no odd space is
built.

## Propagator-set dispatch

`ks_spectrum` groups propagators into sets. The set type changes how the selected
`inv_type` is reached:

| `set_type` | Dispatch |
| --- | --- |
| `single` | Calls the selected single-source field inverter for each source/color entry. |
| `multisource` | Uses the selected block inverter for several sources at one mass. |
| `multicolorsource` | Uses the selected block inverter across source colors at one mass. |
| `multimass` | Uses separate selected single-mass inverters when there are at most two masses or eigenvectors are enabled. With more than two masses and no eigenvectors, `mat_invert_multi` instead executes the multimass CG path on even and odd sites, regardless of the requested `inv_type`. |

Every member of one set must have the same requested inverter type, initial-load
status, precision, and other set-wide controls required by the application.

If any propagator is loaded as an initial guess, `ks_spectrum` changes the
execution to `single` and `CG`. This avoids UML's odd-site reconstruction
overwriting a preloaded odd solution. Therefore the input `inv_type` is not
proof of the executed inverter when an initial propagator is supplied.

## Multigrid rebuild modes

For `MG`, the accepted rebuild strings are:

| Input | Behavior |
| --- | --- |
| `FULL` | Request a full multigrid rebuild. |
| `THIN` | Request the lower-overhead thin rebuild, which may produce a less effective preconditioner. |
| `CG` | Bypass multigrid for that call. The observed dispatch invokes MILC's UML implementation and warns that forced solves should be moved to a different set. |

The `CG` rebuild label should not be confused with `inv_type CG`: the current
fallback implementation is UML. Without the compiled multigrid path,
`ks_spectrum` initializes the rebuild choice to this fallback. **With** the
multigrid path compiled the default is `FULL`: the choice lives in a
zero-initialised global and `FULLREBUILD` is the enum's first value.

### Which sets' `rebuild_type` reaches the solver depends on the checkout

`[source]` The keyword is read in two places and stored in two different fields.
For `multisource` and `multicolorsource` sets it is parsed once per set into a
**per-set array** (`param.mg_rebuild_type[k]`); for `multimass` sets it is parsed,
per propagator, into the inverter control block
(`param.qic[nprop].mg_rebuild_type`). The solver reads only the control block.

**Through `6b9b8a06`, nothing copied the per-set array into the control block** —
the neighbouring `inv_type[k]` was copied, the rebuild choice was left out when
the feature was added — and `single` sets never read the keyword. So a
`multisource` or `multicolorsource` set's `rebuild_type THIN` was accepted,
echoed, and ignored, and the set took a full update like a `single` set. The
recipe for such a checkout: **to obtain a thin update, use `set_type multimass`
sets of one mass.** A multimass set with at most two masses and no eigenvectors
dispatches to the single-source inverter for each mass, which reads the control
block's rebuild choice, takes the single-source MG path, and prints the
`fn_QUDA_MG` timer label; `block_solver_batch_size` does not apply on that path.
The multisource restructure that looks equivalent is not, and its failure is
silent: MILC's own proofreading mode accepts the input, and the only evidence is
the `full` update line at the first solve.

**From merge `db6adc7d` (PR #100, 2026-10-06) the per-set value is copied into
every propagator's control block**, so the recipe is no longer needed, and
`single` sets read `rebuild_type` per propagator exactly as `multimass` sets do.
A `single` MG input written for an earlier checkout therefore fails to parse
until the line is added after each propagator's inverter controls. Every MG
propagator now echoes `effective_mg_rebuild_type propagator <n> FULL|THIN|CG`,
in proofread mode too, so the value that reaches the inverter can be checked
before submission rather than inferred from the first update line.

The same merge changes the first solve after `qudaMultigridCreate`. Before it,
the fresh-link signal (`num_iters = -1`) set before the create was still in
force at the first solve, so that solve invalidated the gauge field and ran an
MG update, full or thin per the rebuild choice, on the hierarchy just built.
Now the create consumes the signal and the inverter prints
`fresh-link signal consumed by hierarchy creation; no first-solve MG update`.
A later link change still signals, because it does not enter the create branch.
A before/after comparison of first-solve time or update counts across that merge
must allow for one fewer update.

Why the thin update matters for memory and when it is exact is owned by
[`../../quda/solvers/staggered-multigrid.md`](../../quda/solvers/staggered-multigrid.md).

## Deflation interaction

The MILC `CG`, `CGZ`, and `UML` implementations can apply their CPU low-mode
deflation step on both parities. When the QUDA deflation path is compiled, those
CPU deflation calls are skipped and deflation ownership moves to QUDA. Through
`6b9b8a06` the QUDA path deflated only the even-parity call; from `d17e9559`
it deflates every parity whose propagator says `deflate yes`, so `UML`'s odd
polish and `CGZ`'s odd solve are deflated too, with QUDA building the odd space
from the even one on first use, and a nonzero relative residual switches QUDA
deflation off for that propagator.

Deflation does not change the parity algorithms above:

- `CGZ` may begin from an exact low-mode component rather than an entirely zero
  vector, but its high-mode guess remains zero and its right-hand side remains
  `src`.
- `UML` still solves even first and reconstructs odd.
- block zero-source detection still considers all right-hand sides together.

For preserved QUDA-space ownership, mass shifting, and invalidation, load
[`../../quda/internals/milc-deflation-space.md`](../../quda/internals/milc-deflation-space.md).

## Runtime confirmation

Confirm the executed path from output rather than the input label alone.
Relevant messages identify plain CG, zero-guess CG, UML, multigrid, multimass,
and block calls. Also record:

- set type and right-hand-side count;
- mass count and whether eigenvectors forced separate inversions;
- source parity and whether a zero-source parity reported zero iterations;
- initial-propagator use and any forced `single`/`CG` substitution;
- MG rebuild choice and whether the UML fallback ran;
- **how many `CONGRAD5` timer lines the inverter emitted per delivered propagator**; and
- backend, precision, convergence, residuals, and elapsed time.

### The timer-line count differs by inverter type, and a comparison built per line is wrong

The parity structure above has a measurement consequence that the algorithm description
alone does not make obvious:

> **`inv_type CG` and `UML` emit TWO `CONGRAD5` timer lines per delivered propagator — one
> per parity, with unequal iteration counts — while `inv_type MG` emits ONE.** A CG-versus-MG
> comparison built per timer line therefore mis-states the ratio by about a factor of two,
> in multigrid's favour. **Build the comparison per delivered propagator**, attributing and
> summing every `CONGRAD5` line belonging to one propagator before averaging.

This follows directly from the mechanism already on this page: `CG` forms `Mdag * src` and
then solves the normal equation independently on even and odd sites, while `MG` solves the
full staggered system through QUDA without exposing separate parity solves. The unequal
split is what the `Mdag`-populates-both-parities behaviour predicts. A `UML` second line
reporting zero or one iteration is the polish converging at entry on an even-pure source
(above), not a missing solve and not the zero-source shortcut, whose right-hand side would
have to be zero.

The failure mode is quiet, which is why it belongs here: a benchmarker who divides by timer
lines does not get an obviously wrong answer, but a plausible one that flatters multigrid
by roughly `2x`.

This source-backed page deliberately makes no universal speed ranking among the
four choices.
