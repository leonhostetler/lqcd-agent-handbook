"""Shared geometry engine for the public staggered-MG decomposition tools.

The command-line wrappers deliberately share this implementation so a memory estimate
cannot accidentally use requested aggregation blocks after QUDA would have adjusted
them.  Source checks reproduce QUDA b6998853f behavior; empirical screens remain
separate and never change source validity.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass


SOURCE_REVISION = "quda-b6998853f"
# The full hash behind SOURCE_REVISION. Every source citation in this module is a permanent
# link pinned to it, so a claim can still be checked after the lines have moved.
SOURCE_COMMIT = "b6998853f6b605e22d67ea2ddfa3cab0d752679a"

# HOW SOURCE CLAIMS ARE CITED HERE, AND WHY IT IS NOT BOOKKEEPING
#
# Every predicate below that can set `source_status` carries a github blob URL pinned to
# SOURCE_COMMIT with the line range it reproduces -- not a bare `file.cuh:1217`, which goes
# stale silently. Between the modelled revision and the build this handbook's campaigns
# currently run, the two rules in coarse_op.cuh moved by 50 and 56 lines; a citation that has
# drifted reads exactly like a citation to nothing.
#
# The cost is on record. The KD per-axis even rule in `source_checks` shipped uncited, and
# has twice been searched for in QUDA, not found, and reported as having no source: once on
# 2026-08-29, caught within the same session, and again on 2026-09-21, caught only because
# the operator remembered otherwise and the earlier session's log still existed. Both
# searches had coarse_op.cuh open at the long-link rule, which sits about 180 lines BELOW the
# rule being looked for in the same file. A permalink would have ended either search in one
# click. Do not add a predicate here without one.

# QUDA instantiates MMA coarse-operator kernels only for these coarse gauge colors. The
# coarse gauge field combines spin and color as N = 2 * nvec_(L-1), so the restriction acts
# on a DERIVED quantity.
# https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/coarse_op_preconditioned_mma_launch.h#L156
# Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc, same line.
MMA_COARSE_GAUGE_COLORS = (12, 48, 64, 128, 192)
# Fine staggered colour. Enters coarse_fine_work as N_c^2 and is a property of the
# staggered operator, not of any fitted population.
FINE_COLOURS = 3

CORPUS_V3_MIN = 10_000
CORPUS_ASPECT_MAX = 1.5
# Every corpus band in this module was fitted on four-level hierarchies. This constant is the
# single place that fact is stated in code, and the guard below is the only place it is applied.
# See software/quda/solvers/staggered-multigrid.md#level-naming: renaming a quantity to a
# role-based name does not rescope the band attached to it.
CORPUS_FITTED_LEVELS = 4
CORPUS_NU3_MIN = 0.022
CORPUS_NU3_MAX = 0.250


class GeometryError(ValueError):
    """Invalid dimensions or hierarchy arguments supplied to the geometry engine."""


@dataclass(frozen=True)
class AdjustedBlock:
    requested: list[int]
    effective: list[int]
    adjustments: list[dict[str, object]]


def product(values: list[int] | tuple[int, ...]) -> int:
    return math.prod(values)


def require_four_positive(name: str, values: list[int]) -> None:
    if len(values) != 4 or any(value <= 0 for value in values):
        raise GeometryError(f"{name} must contain four positive integers")


def derive_local(global_dims: list[int], ranks: list[int]) -> tuple[list[int] | None, list[str]]:
    require_four_positive("global dimensions", global_dims)
    require_four_positive("rank geometry", ranks)
    local: list[int] = []
    errors: list[str] = []
    for axis, (extent, rank_extent) in enumerate(zip(global_dims, ranks)):
        if extent % rank_extent:
            errors.append(
                f"axis {axis}: global extent {extent} is not divisible by "
                f"rank-geometry extent {rank_extent}"
            )
        else:
            local.append(extent // rank_extent)
    return (local if len(local) == 4 else None), errors


def transfer_adjust(dims: list[int], requested: list[int]) -> AdjustedBlock:
    """Emulate Transfer::Transfer's per-axis repeated halving loop."""
    require_four_positive("local dimensions", dims)
    require_four_positive("requested block", requested)
    effective = list(requested)
    adjustments: list[dict[str, object]] = []
    for axis in range(4):
        while effective[axis] > 0:
            size = effective[axis]
            coarse = dims[axis] // size
            if axis == 0 and dims[axis] == size:
                reason = "x extent cannot collapse to one block"
            elif (coarse + 1) % 2 == 0:
                reason = f"coarse extent {coarse} is odd"
            elif coarse * size != dims[axis]:
                reason = f"block {size} does not divide extent {dims[axis]}"
            else:
                break
            replacement = size // 2
            adjustments.append(
                {"axis": axis, "from": size, "to": replacement, "reason": reason}
            )
            effective[axis] = replacement
    return AdjustedBlock(list(requested), effective, adjustments)


def source_checks(
    dims: list[int],
    adjusted: AdjustedBlock,
    level: int,
    nvec: int,
    fine_color: int,
    spin_block: int,
    allow_truncation: bool = False,
) -> tuple[list[int] | None, list[str], dict[str, object]]:
    errors: list[str] = []
    block = adjusted.effective
    if any(value == 0 for value in block):
        # The halving loop divides by two until the block is valid or reaches zero, and zero
        # is a hard error rather than a fallback.
        # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp#L41-L53
        # Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc, same lines.
        errors.append(f"level {level}: Transfer would error: unable to block a dimension")
        return None, errors, {}
    coarse = [extent // size for extent, size in zip(dims, block)]
    block_volume = product(block)
    # Three predicates on the block PRODUCT -- not on any single extent. They are checked in
    # block orthogonalization, which runs for every aggregation transfer and, because
    # Transfer::reset() returns early for the three KD transfer types, never for a KD one.
    # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/block_orthogonalize.in.cu#L92-L94
    # Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc, same lines.
    if block_volume == 1:
        errors.append(f"level {level}: invalid MG aggregate size 1")
    if block_volume % 2:
        errors.append(f"level {level}: MG aggregate size {block_volume} must be even")
    if block_volume > 1024:
        errors.append(f"level {level}: MG aggregate size {block_volume} must be <= 1024")
    if level == 1:
        # Coarsening a Kahler-Dirac operator requires an even aggregation extent in EVERY
        # direction, which is strictly stronger than the even-product rule above. The check
        # is gated on the KD-family diracs, which is exactly why it binds on this FIRST
        # aggregation -- where ASQTADKD is the operator that block1 coarsens -- and never on
        # a coarse-to-coarse stage. QUDA's own message is mirrored below.
        # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/coarse_op.cuh#L1022-L1026
        # Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc,
        # coarse_op.cuh:1072-1077. THIS RULE IS REAL; see the module note above for the two
        # occasions it was searched for, missed, and wrongly reported as spurious.
        for axis, size in enumerate(block):
            if size % 2:
                errors.append(f"level 1 axis {axis}: KD aggregation size {size} must be even")
        # An asqtad-family operator refuses to coarsen long links when an aggregation extent
        # is below three, because the long links span three sites.  The branch is gated on
        # the asqtad diracs, so it binds on this FIRST aggregation, where the improved
        # operator still carries long links, and never on a coarse-to-coarse stage.
        # allow_truncation defaults to false in QUDA; without it the rejection is a hard
        # errorQuda, not the silent halving that transfer_adjust models.
        # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/coarse_op.cuh#L1196-L1220
        # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/check_params.h#L1080
        # Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc,
        # coarse_op.cuh:1252 and :1276; check_params.h:1080 unchanged. Combined with the KD
        # rule above, a first-aggregation extent must be even and at least three, hence at
        # least four and even.
        if not allow_truncation:
            for axis, size in enumerate(block):
                if size < 3:
                    errors.append(
                        f"level 1 axis {axis}: long-link aggregation size {size} is below "
                        "3; QUDA aborts improved-staggered long-link coarsening unless "
                        "allow_truncation is enabled"
                    )
    aggregate_size = block_volume * fine_color
    aggregate_size = aggregate_size // 2 if spin_block == 0 else aggregate_size * spin_block
    # The coarse space cannot exceed the degrees of freedom in an aggregate. Note that QUDA
    # calls THIS quantity `aggregate_size` too, while block orthogonalization gives the same
    # name to the bare geometric product; the two differ by the fine colour and spin factors
    # and both appear in errors that say "aggregate size".
    # https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/transfer.cpp#L77-L83
    # Re-verified 2026-09-21 at 00c7ef33dacadfb94860e3ca1cc06862926182dc, same lines.
    if nvec > aggregate_size:
        errors.append(
            f"level {level}: requested coarse space {nvec} exceeds aggregate size "
            f"{aggregate_size}"
        )
    detail = {
        "requested_block": adjusted.requested,
        "effective_block": block,
        "request_exact": not adjusted.adjustments,
        "adjustments": adjusted.adjustments,
        "fine_local": dims,
        "coarse_local": coarse,
        "block_volume": block_volume,
        "fine_color_for_transfer": fine_color,
        "spin_block": spin_block,
        "aggregate_space_capacity": aggregate_size,
        "long_link_truncation_allowed": allow_truncation if level == 1 else None,
    }
    return coarse, errors, detail


def evaluate_local_hierarchy(
    local_dims: list[int],
    levels: int,
    block1: list[int] | None,
    block2: list[int] | None,
    nvec1: int,
    nvec2: int,
    compiled_nvecs: list[int] | None = None,
    allow_truncation: bool = False,
    use_mma: bool | None = None,
) -> dict[str, object]:
    """Adjust and validate every aggregation step for a supplied local lattice."""
    require_four_positive("local dimensions", local_dims)
    if levels not in (2, 3, 4):
        raise GeometryError("levels must be 2, 3, or 4")
    if levels >= 3 and (block1 is None or nvec1 <= 0):
        raise GeometryError("three- and four-level MG require block1 and positive nvec1")
    if levels == 4 and (block2 is None or nvec2 <= 0):
        raise GeometryError("four-level MG requires block2 and positive nvec2")
    if levels < 4 and block2 is not None:
        raise GeometryError(f"block2 is not used by a {levels}-level hierarchy")
    if levels == 2 and block1 is not None:
        raise GeometryError("block1 is not used by a two-level KD-only hierarchy")

    errors: list[str] = []
    level_details: list[dict[str, object]] = []
    current = list(local_dims)
    effective_blocks: list[list[int]] = []
    steps = []
    if levels >= 3:
        steps.append((1, block1, nvec1, 3, 0))
    if levels == 4:
        steps.append((2, block2, nvec2, nvec1, 1))
    for level, requested, nvec, fine_color, spin_block in steps:
        assert requested is not None
        adjusted = transfer_adjust(current, requested)
        coarse, step_errors, detail = source_checks(
            current, adjusted, level, nvec, fine_color, spin_block, allow_truncation
        )
        errors.extend(step_errors)
        level_details.append(detail)
        if coarse is None:
            break
        effective_blocks.append(adjusted.effective)
        current = coarse

    hierarchy = {
        "source_revision": SOURCE_REVISION,
        "source_status": "error" if errors else "pass",
        "source_errors": errors,
        "levels_count": levels,
        "local_dims": list(local_dims),
        "coarsest_local_dims": current if not errors else None,
        "effective_blocks": effective_blocks,
        "levels": level_details,
        "requested_blocks_changed": any(
            detail and not detail.get("request_exact", True) for detail in level_details
        ),
        "runtime_confirmation": "confirm every `Transfer: using block size ...` line",
    }
    hierarchy = attach_compiled_nvec_check(
        hierarchy, levels, nvec1, nvec2, compiled_nvecs
    )
    return attach_mma_capability_check(hierarchy, levels, nvec1, nvec2, use_mma)


def compiled_nvec_check(
    levels: int,
    nvec1: int,
    nvec2: int,
    compiled_nvecs: list[int] | None,
) -> dict[str, object]:
    """Describe a QUDA_MULTIGRID_NVEC_LIST check without implying it ran."""
    required = []
    if levels >= 3:
        required.append({"parameter": "nvec1", "value": nvec1})
    if levels == 4:
        required.append({"parameter": "nvec2", "value": nvec2})
    supplied = sorted(set(compiled_nvecs)) if compiled_nvecs is not None else None
    missing = (
        [item for item in required if item["value"] not in supplied]
        if supplied is not None
        else []
    )
    return {
        "status": "unchecked" if supplied is None else ("fail" if missing else "pass"),
        "required": required,
        "supplied": supplied,
        "missing": missing,
        "scope": (
            "nvec1/nvec2 construct coarse colors; nvec3 is a coarsest-deflation "
            "count and is not checked against this list"
        ),
    }


def attach_compiled_nvec_check(
    hierarchy: dict[str, object],
    levels: int,
    nvec1: int,
    nvec2: int,
    compiled_nvecs: list[int] | None,
) -> dict[str, object]:
    """Attach the build check and make a checked failure source-invalid."""
    check = compiled_nvec_check(levels, nvec1, nvec2, compiled_nvecs)
    hierarchy["build_capability"] = {"QUDA_MULTIGRID_NVEC_LIST": check}
    if check["status"] == "fail":
        for item in check["missing"]:
            hierarchy["source_errors"].append(
                f"{item['parameter']}={item['value']} is absent from the supplied "
                "QUDA_MULTIGRID_NVEC_LIST"
            )
        hierarchy["source_status"] = "error"
    return hierarchy


def mma_capability_check(
    levels: int,
    nvec1: int,
    nvec2: int,
    use_mma: bool | None,
) -> dict[str, object]:
    """Describe QUDA's MMA coarse-gauge-color restriction without implying it ran.

    The restriction acts on the derived coarse gauge color N = 2 * nvec_(L-1), not on
    the requested near-null count, which is why a value can be a legal aggregation AND
    a compiled coarse color and still abort in coarse-operator construction.  It is
    independent of QUDA_MULTIGRID_NVEC_LIST.
    """
    required = []
    if levels >= 3:
        required.append(
            {"parameter": "nvec1", "value": nvec1, "coarse_gauge_color": 2 * nvec1}
        )
    if levels == 4:
        required.append(
            {"parameter": "nvec2", "value": nvec2, "coarse_gauge_color": 2 * nvec2}
        )
    if use_mma is None:
        status, unsupported = "unchecked", []
    elif not use_mma:
        status, unsupported = "not-applicable", []
    else:
        unsupported = [
            item
            for item in required
            if item["coarse_gauge_color"] not in MMA_COARSE_GAUGE_COLORS
        ]
        status = "fail" if unsupported else "pass"
    return {
        "status": status,
        "required": required,
        "supported_coarse_gauge_colors": list(MMA_COARSE_GAUGE_COLORS),
        "supported_nvec": [value // 2 for value in MMA_COARSE_GAUGE_COLORS],
        "unsupported": unsupported,
        "scope": (
            "binds only when MILC use_mma is true; acts on the derived coarse gauge "
            "color 2*nvec and is independent of QUDA_MULTIGRID_NVEC_LIST"
        ),
    }


def attach_mma_capability_check(
    hierarchy: dict[str, object],
    levels: int,
    nvec1: int,
    nvec2: int,
    use_mma: bool | None,
) -> dict[str, object]:
    """Attach the MMA check and make a checked failure source-invalid."""
    check = mma_capability_check(levels, nvec1, nvec2, use_mma)
    capability = hierarchy.setdefault("build_capability", {})
    capability["QUDA_MMA_COARSE_GAUGE_COLOR"] = check
    if check["status"] == "fail":
        for item in check["unsupported"]:
            hierarchy["source_errors"].append(
                f"{item['parameter']}={item['value']} gives coarse gauge color "
                f"N={item['coarse_gauge_color']}, for which QUDA builds no MMA "
                "coarse-operator kernel; use_mma aborts in coarse-operator construction"
            )
        hierarchy["source_status"] = "error"
    return hierarchy


def evaluate_decomposition(
    global_dims: list[int],
    ranks: list[int],
    levels: int,
    block1: list[int] | None,
    block2: list[int] | None,
    nvec1: int,
    nvec2: int,
    nvec3: int | None = None,
    compiled_nvecs: list[int] | None = None,
    lattice_spacing_fm: float | None = None,
    corpus_advisories: bool = False,
    allow_truncation: bool = False,
    use_mma: bool | None = None,
) -> dict[str, object]:
    """Derive local geometry, adjust blocks, and keep source errors separate from advice."""
    local, errors = derive_local(global_dims, ranks)
    hierarchy: dict[str, object]
    if local is None:
        hierarchy = {
            "source_revision": SOURCE_REVISION,
            "source_status": "error",
            "source_errors": errors,
            "levels_count": levels,
            "local_dims": None,
            "coarsest_local_dims": None,
            "effective_blocks": [],
            "levels": [],
            "requested_blocks_changed": False,
            "runtime_confirmation": "confirm every `Transfer: using block size ...` line",
        }
    else:
        hierarchy = evaluate_local_hierarchy(
            local, levels, block1, block2, nvec1, nvec2, compiled_nvecs,
            allow_truncation, use_mma,
        )
        hierarchy["source_errors"] = errors + list(hierarchy["source_errors"])
        hierarchy["source_status"] = "error" if hierarchy["source_errors"] else "pass"

    if local is None:
        attach_compiled_nvec_check(hierarchy, levels, nvec1, nvec2, compiled_nvecs)
        attach_mma_capability_check(hierarchy, levels, nvec1, nvec2, use_mma)

    metrics: dict[str, object] = {}
    advisories: list[str] = []
    if hierarchy["source_status"] == "pass" and local is not None:
        effective_blocks = hierarchy["effective_blocks"]
        total_block = [
            product([block[axis] for block in effective_blocks])
            if effective_blocks
            else 1
            for axis in range(4)
        ]
        coarsest_global_volume = product(global_dims) // product(total_block)
        coarsest_local_dims = hierarchy["coarsest_local_dims"]
        aspect = max(total_block) / min(total_block)
        metrics.update(
            {
                "coarsest_global_volume": coarsest_global_volume,
                "coarsest_local_volume": product(coarsest_local_dims),
                "coarsest_cell_sites": total_block,
                "coarsest_cell_aspect": aspect,
            }
        )
        if levels == 4:
            metrics["V3_global"] = coarsest_global_volume
            metrics["V3_local"] = product(coarsest_local_dims)
        elif levels == 3:
            metrics["V2_global"] = coarsest_global_volume
            metrics["V2_local"] = product(coarsest_local_dims)
        if lattice_spacing_fm is not None:
            if lattice_spacing_fm <= 0:
                raise GeometryError("lattice-spacing-fm must be positive")
            metrics["coarsest_cell_fm"] = [
                lattice_spacing_fm * value for value in total_block
            ]
        if nvec3 is not None:
            metrics["coarsest_vector_density"] = nvec3 / coarsest_global_volume
            if levels == 4:
                metrics["nu3"] = nvec3 / coarsest_global_volume

        # coarse_fine_work: how many full fine-operator applications one coarsest apply
        # costs. The solver-tuning procedure requires this screen -- an adequate coarsest
        # volume says the coarse problem is well posed and says nothing about whether the
        # coarse grid is cheap relative to the fine one -- and until now no tool emitted it,
        # so every campaign following the gate computed it by hand.
        #
        # The trap it removes is which count to use. The coarse gauge colour is
        # 2 * nvec_(L-1), and L-1 is a LEVEL INDEX, not a role: that is nvec_2 at four
        # levels and nvec_1 at three. nvec_3 is a deflation count and never a coarse colour.
        # Getting this wrong at three levels silently squares the wrong number.
        #
        # This is a dimensionless ratio derived from the lattice, the executed blocks and
        # the coarse colour -- a quantity, not a fitted band -- so unlike the corpus screens
        # it is not scoped to a level count and carries no population. It is emitted
        # wherever the coarsest-defining count is unambiguous, and declined elsewhere rather
        # than guessed.
        #
        # It is computed from the EFFECTIVE blocks, not the requested ones. The formula holds
        # no rank geometry, so two placements running the same hierarchy price identically --
        # but a placement whose local extents force QUDA to halve a requested block runs a
        # DIFFERENT hierarchy, and this ratio moves accordingly. That is the executed
        # hierarchy being priced, which is the one worth pricing; check
        # `requested_blocks_changed` before comparing two placements.
        coarsest_defining_nvec = {4: nvec2, 3: nvec1}.get(levels)
        if coarsest_defining_nvec:
            coarse_gauge_colour = 2 * coarsest_defining_nvec
            metrics["coarse_gauge_colour"] = coarse_gauge_colour
            metrics["coarse_fine_work"] = (
                coarsest_global_volume * coarse_gauge_colour ** 2
            ) / (product(global_dims) * FINE_COLOURS ** 2)
            metrics["coarse_fine_work_basis"] = (
                f"2*nvec_{levels - 2}={coarse_gauge_colour} over N_c={FINE_COLOURS}"
            )
        else:
            # Two levels has no aggregation-built coarsest operator, so there is no coarse
            # colour to square. Saying so beats omitting the key, which reads as "computed
            # and unremarkable".
            metrics["coarse_fine_work"] = None
            metrics["coarse_fine_work_basis"] = (
                f"not evaluated: no unambiguous coarsest-defining nvec at {levels} levels"
            )
        if corpus_advisories:
            if levels != CORPUS_FITTED_LEVELS:
                # Not a warning about this candidate: a refusal to evaluate. Every corpus band
                # here was fitted at CORPUS_FITTED_LEVELS levels, so at any other level count
                # the honest output is "not applicable", never a pass.
                advisories.append(
                    f"corpus screens not evaluated: every band was fitted at "
                    f"{CORPUS_FITTED_LEVELS} levels and this hierarchy has {levels}"
                )
            else:
                if coarsest_global_volume < CORPUS_V3_MIN:
                    advisories.append(
                        f"V3_global={coarsest_global_volume} is below the provisional "
                        f"corpus screen {CORPUS_V3_MIN}"
                    )
                if aspect > CORPUS_ASPECT_MAX:
                    advisories.append(
                        f"coarsest-cell aspect={aspect:.3g} exceeds the provisional "
                        f"corpus screen {CORPUS_ASPECT_MAX}"
                    )
                density = metrics.get("coarsest_vector_density")
                if density is not None and not (
                    CORPUS_NU3_MIN <= density <= CORPUS_NU3_MAX
                ):
                    advisories.append(
                        f"nu3={density:.4g} is outside the fitted spectrum envelope "
                        f"{CORPUS_NU3_MIN}...{CORPUS_NU3_MAX}; the coarse-spectrum law is "
                        f"an extrapolation here"
                    )

    hierarchy.update(
        {
            "global_dims": list(global_dims),
            "rank_geometry": list(ranks),
            "total_ranks": product(ranks),
            "partitioned": [int(value > 1) for value in ranks],
            "metrics": metrics,
            "empirical_screen": {
                "enabled": corpus_advisories,
                "evidence": "retrospective three-ensemble corpus; threshold provisional",
                # fitted_levels and evaluated exist so a consumer can tell "screens ran and
                # this candidate passed" from "screens never ran". Both otherwise produce an
                # empty advisories list, and the second silently reads as a pass.
                "fitted_levels": CORPUS_FITTED_LEVELS,
                "evaluated": bool(
                    corpus_advisories and levels == CORPUS_FITTED_LEVELS
                ),
                "V3_min": CORPUS_V3_MIN if corpus_advisories else None,
                "aspect_max": CORPUS_ASPECT_MAX if corpus_advisories else None,
                "nu3_envelope": (
                    [CORPUS_NU3_MIN, CORPUS_NU3_MAX] if corpus_advisories else None
                ),
                "advisories": advisories,
            },
        }
    )
    return hierarchy


def divisors_with_min_local(global_extent: int, min_local: int) -> list[int]:
    if global_extent <= 0 or min_local <= 0:
        raise GeometryError("global extents and min-local must be positive")
    return [
        value
        for value in range(1, global_extent + 1)
        if global_extent % value == 0 and global_extent // value >= min_local
    ]


def rank_geometries(
    global_dims: list[int], total_ranks: int, min_local: int = 1
) -> list[list[int]]:
    """Return every rank-grid factorization that tiles the lattice exactly."""
    require_four_positive("global dimensions", global_dims)
    if total_ranks <= 0:
        raise GeometryError("total ranks must be positive")
    choices = [divisors_with_min_local(extent, min_local) for extent in global_dims]
    results = [
        list(candidate)
        for candidate in itertools.product(*choices)
        if product(candidate) == total_ranks
    ]

    def score(ranks: list[int]) -> tuple[float, int, tuple[int, ...]]:
        local = [extent // rank for extent, rank in zip(global_dims, ranks)]
        surface = sum(product(local) // extent for extent in local)
        return max(local) / min(local), surface, tuple(ranks)

    return sorted(results, key=score)
