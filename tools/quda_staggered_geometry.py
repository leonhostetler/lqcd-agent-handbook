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
# coarse_op_preconditioned_mma_launch.h:156 -- QUDA instantiates MMA coarse-operator
# kernels only for these coarse gauge colors.  The coarse gauge field combines spin and
# color as N = 2 * nvec_(L-1), so the restriction acts on a DERIVED quantity.
MMA_COARSE_GAUGE_COLORS = (12, 48, 64, 128, 192)
CORPUS_V3_MIN = 10_000
CORPUS_ASPECT_MAX = 1.5


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
        errors.append(f"level {level}: Transfer would error: unable to block a dimension")
        return None, errors, {}
    coarse = [extent // size for extent, size in zip(dims, block)]
    block_volume = product(block)
    if block_volume == 1:
        errors.append(f"level {level}: invalid MG aggregate size 1")
    if block_volume % 2:
        errors.append(f"level {level}: MG aggregate size {block_volume} must be even")
    if block_volume > 1024:
        errors.append(f"level {level}: MG aggregate size {block_volume} must be <= 1024")
    if level == 1:
        for axis, size in enumerate(block):
            if size % 2:
                errors.append(f"level 1 axis {axis}: KD aggregation size {size} must be even")
        # coarse_op.cuh:1217-1220 -- an asqtad-family operator refuses to coarsen long
        # links when an aggregation extent is below three, because the long links span
        # three sites.  The branch is gated on the asqtad diracs, so it binds on this
        # FIRST aggregation, where the improved operator still carries long links, and
        # never on a coarse-to-coarse stage.  allow_truncation defaults to false in QUDA
        # (check_params.h:1080); without it the rejection is a hard errorQuda, not the
        # silent halving that transfer_adjust models.
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
        if corpus_advisories:
            if levels != 4:
                advisories.append(
                    "the provisional V3/aspect screen was calibrated only for four-level MG"
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

    hierarchy.update(
        {
            "global_dims": list(global_dims),
            "rank_geometry": list(ranks),
            "total_ranks": product(ranks),
            "partitioned": [int(value > 1) for value in ranks],
            "metrics": metrics,
            "empirical_screen": {
                "enabled": corpus_advisories,
                "evidence": "retrospective four-ensemble corpus; threshold provisional",
                "V3_min": CORPUS_V3_MIN if corpus_advisories else None,
                "aspect_max": CORPUS_ASPECT_MAX if corpus_advisories else None,
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
