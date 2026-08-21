#!/usr/bin/env python3
"""Source-exact object sizes and corpus-calibrated staggered-solver memory estimates.

All sizes are per rank.  Source-object commands reproduce allocation formulas at QUDA
b6998853f.  The plain-CG MRHS command derives a production-width increment from the
same source and carries a separately named matched-width validation.  Fit commands use
the Perlmutter A100 retrospective calibration documented in
software/quda/solvers/staggered-memory.md.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Iterable

from quda_staggered_geometry import (
    GeometryError,
    evaluate_decomposition,
    evaluate_local_hierarchy,
    product as geometry_product,
    rank_geometries,
)


MIB = 1024**2
GIB = 1024**3
ALIGN_REQ = 128
PRECISION = {"double": 8, "single": 4, "half": 2, "quarter": 1}
GEOMETRY = {"scalar": 1, "vector": 4, "tensor": 6, "coarse": 8, "kdinverse": 16}

CG_DEVICE_CONST_MIB = 616.2
CG_DEVICE_BYTES_PER_SITE = 3003.0
CG_HOST_CONST_MIB = 625.2
CG_HOST_BYTES_PER_SITE = 5014.0
DEFLATION_DEVICE_FACTOR = 1.03
MG_SETUP_WS_BYTES_PER_SITE = 17787.0
MG_COARSE_COPY_FACTOR = 1.718
# Current-code calibration.  Builds represented by the older corpus era used
# 73,920 B per partitioned checkerboarded surface site instead.  That historical
# value is intentionally not a public runtime choice: this tool sizes future runs.
CURRENT_POOL_BYTES_PER_SURFACE_SITE = 26812.0

PERLMUTTER_A100 = {
    "name": "perlmutter-a100-40",
    "description": "Perlmutter GPU node with four A100-40 GPUs",
    "ranks_per_node": 4,
    "gpu_gib": 40.0,
    "host_gib_per_node": 256 / 1.073741824,
    "advisory_margin_gib": 4.0,
}
MACHINE_PROFILES = {PERLMUTTER_A100["name"]: PERLMUTTER_A100}

# Component-wise support of the 57-group device calibration.  A combination assembled
# from these sets was not necessarily run as one cell; the assessment says
# "calibrated envelope", not "measured configuration".  Keep these here, rather than
# in the agent-loaded page, so a future refit has a concrete place to update them.
CALIBRATED_LOCAL_DIMS = {
    (24, 48, 24, 32),
    (24, 48, 24, 36),
    (32, 32, 32, 16),
    (48, 24, 24, 32),
    (48, 36, 24, 24),
    (96, 24, 24, 16),
}
CALIBRATED_RANK_GEOMETRIES = {
    (1, 2, 2, 2),
    (1, 4, 4, 12),
    (2, 2, 2, 6),
    (2, 4, 4, 6),
    (3, 4, 6, 12),
    (4, 2, 4, 6),
    (6, 3, 6, 8),
}
CALIBRATED_BLOCK1 = {
    (4, 4, 4, 4),
    (4, 4, 4, 16),
    (4, 4, 8, 4),
    (4, 6, 4, 8),
    (4, 6, 6, 4),
    (4, 6, 6, 6),
    (4, 8, 8, 2),
    (6, 6, 6, 4),
    (8, 4, 4, 2),
    (8, 4, 4, 8),
}
CALIBRATED_BLOCK2 = {
    (1, 3, 3, 2),
    (2, 2, 2, 2),
    (2, 2, 2, 4),
    (2, 3, 2, 3),
    (2, 4, 4, 1),
    (3, 1, 3, 2),
    (3, 2, 2, 2),
    (3, 2, 2, 3),
    (3, 2, 3, 2),
    (3, 3, 3, 2),
    (4, 1, 2, 4),
    (4, 2, 1, 4),
    (4, 2, 2, 2),
    (6, 1, 3, 2),
    (6, 3, 3, 1),
}
CALIBRATED_NVEC2 = {64, 96, 128}
CALIBRATED_NVEC3 = {0, 600, 800, 1000, 1024, 1536, 2000, 2048, 2500, 3000, 3072, 4000}

# Current QUDA removed a historical 4x KD-inverse allocation in 0006627c1.  The
# corpus MG fit was formed against the historical allocation, while a later 0.04-fm
# same-allocation A-B-A measurement found that the QUDA Device high-water fell
# by 4374.0 MiB rather than the nominal 4920.75 MiB.  Express the current-code model
# directly as the source-exact current field plus the residual pool reservation.
# There is no public pre-fix selector; this comment preserves the forensic bridge.
HISTORICAL_KDINV_OVERALLOC = 4
CURRENT_KD_REDUCTION_REALIZATION = 4374.0 / 4920.75
CURRENT_KD_HIGH_WATER_FACTOR = 1.0 + (HISTORICAL_KDINV_OVERALLOC - 1) * (
    1.0 - CURRENT_KD_REDUCTION_REALIZATION
)

CALIBRATION = {
    "name": "perlmutter-a100-staggered-2024-2026",
    "machine": "Perlmutter A100-40",
    "software_scope": "MILC HISQ with QUDA staggered solvers",
    "precision_scope": "half-precision MG preconditioner; single-precision deflation vectors",
    "mg_population": (
        "57 multi-rank groups, four lattice spacings, 2-216 nodes, about 20 "
        "decompositions, 11 QUDA builds; four MG levels; nvec_1 fixed at 64"
    ),
    "mg_accuracy": "QUDA Device counter: rms 3.9%, maximum 10.7%",
    "mg_validated_contract": (
        "four levels, half null/preconditioner precision, single setup precision, "
        "nvec_1=64, default fitted constants, multi-rank Perlmutter A100-40"
    ),
    "mg_unvalidated_extensions": (
        "two- and three-level phase models, other MG precisions, and custom fitted "
        "constants are structural extrapolations with no empirical error bound"
    ),
    "cg_population": "12 measurements over fine local volume 5.2e5 to 8.0e6 sites",
    "cg_accuracy": "device rms 7.2%, maximum 12.6%; QUDA host rms 3.5%, maximum 8.2%",
    "deflation_population": "three independent retained-eigenvector cases",
    "deflation_accuracy": "combined device estimate about 1%; host increment 0.02%",
    "pool_population": "current-code corpus era; partitioned fine surfaces supplied",
    "pool_accuracy": "current-code fit: maximum 4.4%",
    "mg_page_locked_population": "55 multi-rank groups with a recorded build",
    "mg_page_locked_accuracy": "QUDA Page-locked host counter: rms 3.7%, maximum 5.7%",
    "kd_current_population": "one same-allocation 0.04-fm A-B-A measurement",
    "kd_current_accuracy": (
        "4374.0 MiB Device-counter reduction versus 4920.75 MiB nominal; "
        "other local volumes use the measured ratio as an extrapolation"
    ),
    "outside_scope": [
        "single-rank jobs",
        "non-A100 machines",
        "MG precisions other than half-null/single-setup (available only as warned extrapolations)",
        "MG hierarchies other than four levels (available only as warned extrapolations)",
        "fermion discretizations other than staggered HISQ",
        "whole-process scheduler RSS",
    ],
}

MRHS_CG_VALIDATION = {
    "name": "perlmutter-a100-plain-cg-mrhs-2026",
    "profile": (
        "unsplit MATPC/direct-PC CG, double precise, half sloppy, "
        "solution_accumulator_pipeline=1"
    ),
    "population": (
        "three matched active-width 1-to-3 cells over local volumes "
        "746496, 884736, and 7962624 sites"
    ),
    "version_scope": (
        "one pair records QUDA d61517229 and retains the relevant allocation structure "
        "at b6998853f; two pairs omit their source revision and extend only the "
        "volume/decomposition check"
    ),
    "device_accuracy": "maximum absolute per-additional-RHS error 0.04%",
    "counter_observations": (
        "Pinned device and Page-locked host counters were unchanged; Total host was "
        "unchanged to 0.1 MiB; these observations do not define host or RSS formulas"
    ),
    "excluded_regime": (
        "unversioned older cells with a different bytes-per-site slope are a source/path "
        "discontinuity and are not fitted into this current-profile law"
    ),
}


class ModelError(ValueError):
    """An input is outside a source formula or calibrated model contract."""


@dataclass(frozen=True)
class Fit:
    device_gib: float | None
    host_gib: float | None
    detail: dict[str, object]


def product(values: Iterable[int]) -> int:
    return math.prod(values)


def volume(dims: list[int]) -> int:
    if len(dims) != 4 or any(value <= 0 for value in dims):
        raise ModelError("local dimensions must be four positive integers")
    return product(dims)


def align_up(value: int, alignment: int = ALIGN_REQ) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def surface_cb(dims: list[int]) -> list[int]:
    v = volume(dims)
    surfaces = [v // value for value in dims]
    if any(value % 2 for value in surfaces):
        raise ModelError("checkerboarded surface formulas require even 3-volumes")
    return [value // 2 for value in surfaces]


def coarse_pad(dims: list[int]) -> int:
    return 2 * max(surface_cb(dims))


def color_spinor_bytes(
    dims: list[int], ncolor: int, nspin: int, precision: int, subset: str, count: int = 1
) -> int:
    """Current native ColorSpinorField allocation, excluding shared communication buffers."""
    v = volume(dims)
    if v % 2:
        raise ModelError("checkerboarded color-spinor allocation requires even local volume")
    if ncolor <= 0 or nspin <= 0 or count <= 0:
        raise ModelError("ncolor, nspin, and count must be positive")
    site_subset = {"parity": 1, "full": 2}[subset]
    volume_cb = v // 2
    raw = site_subset * volume_cb * ncolor * nspin * 2 * precision
    if precision < PRECISION["single"]:
        raw += site_subset * volume_cb * 4
    one = site_subset * align_up(raw // site_subset)
    return count * one


def gauge_field_bytes(
    dims: list[int],
    ncolor: int,
    precision: int,
    geometry: str,
    pad: int = 0,
    count: int = 1,
) -> int:
    """Native unreconstructed GaugeField allocation, excluding shared ghost buffers."""
    v = volume(dims)
    if v % 2:
        raise ModelError("native gauge allocation requires even local volume")
    if ncolor <= 0 or pad < 0 or count <= 0:
        raise ModelError("ncolor and count must be positive and pad nonnegative")
    site_dim = GEOMETRY[geometry]
    ninternal = ncolor * ncolor * 2
    length = 2 * site_dim * (v // 2 + pad) * ninternal
    one = 2 * align_up(length * precision // 2)
    return count * one


def gauge_aos_ghost_bytes(dims: list[int], ncolor: int, precision: int) -> int:
    ninternal = ncolor * ncolor * 2
    return sum(2 * (2 * surface) * ninternal * precision for surface in surface_cb(dims))


def cg_fit(dims: list[int]) -> Fit:
    v0 = volume(dims)
    device = (CG_DEVICE_CONST_MIB * MIB + CG_DEVICE_BYTES_PER_SITE * v0) / GIB
    host = (CG_HOST_CONST_MIB * MIB + CG_HOST_BYTES_PER_SITE * v0) / GIB
    return Fit(device, host, {"V0": v0})


def mrhs_cg_delta(dims: list[int], width: int, reference_width: int) -> dict[str, object]:
    """Current-profile QUDA Device increment for plain-CG active batch width."""
    if width < 1 or reference_width < 1:
        raise ModelError("active and reference widths must be positive")
    if width < reference_width:
        raise ModelError("active width must be greater than or equal to reference width")
    precise_field = color_spinor_bytes(
        dims, 3, 1, PRECISION["double"], "parity"
    )
    sloppy_field = color_spinor_bytes(
        dims, 3, 1, PRECISION["half"], "parity"
    )
    per_rhs = 5 * precise_field + 5 * sloppy_field
    increment = (width - reference_width) * per_rhs
    return {
        "V0": volume(dims),
        "active_batch_width": width,
        "reference_batch_width": reference_width,
        "additional_active_rhs": width - reference_width,
        "profile": {
            "solver": "unsplit MATPC/direct-PC CG",
            "precise_precision": "double",
            "sloppy_precision": "half",
            "solution_accumulator_pipeline": 1,
            "precise_parity_fields_per_rhs": 5,
            "sloppy_parity_fields_per_rhs": 5,
        },
        "precise_parity_field_bytes": precise_field,
        "sloppy_parity_field_bytes": sloppy_field,
        "device_bytes_per_additional_rhs": per_rhs,
        "device_increment_bytes": increment,
        "device_increment_gib": increment / GIB,
    }


def deflated_fit(dims: list[int], vectors: int) -> Fit:
    if vectors <= 0:
        raise ModelError("vectors must be positive")
    base = cg_fit(dims)
    payload = vectors * 12 * volume(dims) / GIB
    return Fit(
        base.device_gib + DEFLATION_DEVICE_FACTOR * payload,
        base.host_gib + payload,
        {
            "V0": volume(dims),
            "retained_vector_payload_gib": payload,
            "device_workspace_factor": DEFLATION_DEVICE_FACTOR,
            "vector_scope": "single precision, one parity, three staggered colors",
        },
    )


def validate_effective_block(
    dims: list[int], block: list[int], level: int, nvec: int, fine_color: int, spin_block: int
) -> list[int]:
    if len(block) != 4 or any(value <= 0 for value in block):
        raise ModelError(f"effective block {level} must contain four positive integers")
    for axis, (extent, size) in enumerate(zip(dims, block)):
        if extent % size:
            raise ModelError(
                f"effective block {level}[{axis}]={size} does not divide local extent {extent}; "
                "run quda-staggered-decomposition.py on requested blocks first"
            )
        if extent // size % 2:
            raise ModelError(
                f"effective block {level}[{axis}]={size} leaves unsupported odd coarse extent "
                f"{extent // size}"
            )
    block_volume = product(block)
    if block_volume == 1 or block_volume % 2 or block_volume > 1024:
        raise ModelError(
            f"effective block {level} product must be even, greater than 1, and at most 1024"
        )
    if level == 1 and any(value % 2 for value in block):
        raise ModelError("the first aggregate block must be even per dimension for a KD operator")
    aggregate_size = block_volume * fine_color
    aggregate_size = aggregate_size // 2 if spin_block == 0 else aggregate_size * spin_block
    if nvec > aggregate_size:
        raise ModelError(
            f"nvec_{level}={nvec} exceeds aggregate coarse-space capacity {aggregate_size}"
        )
    return [extent // size for extent, size in zip(dims, block)]


def coarse_nc(nvec: int) -> int:
    return 2 * nvec


def model_spinor_bytes(
    dims: list[int], ncolor: int, nspin: int, precision: int, count: int = 1
) -> int:
    return color_spinor_bytes(dims, ncolor, nspin, precision, "full", count)


def mg_corpus_fit(
    dims: list[int],
    block1: list[int] | None,
    block2: list[int] | None,
    nvec1: int,
    nvec2: int,
    nvec3: int,
    use_mma: bool,
    levels: int = 4,
    prec_null: int = PRECISION["half"],
    prec_setup: int = PRECISION["single"],
    setup_ws: float = MG_SETUP_WS_BYTES_PER_SITE,
    copy_factor: float = MG_COARSE_COPY_FACTOR,
) -> Fit:
    """QUDA Device high-water model, with a validated four-level default.

    Levels two and three, non-default precisions, and modified fit constants are
    intentionally available for planning.  They are structural extrapolations with no
    empirical error bound and callers must surface the returned warnings.
    """
    if levels not in (2, 3, 4):
        raise ModelError("levels must be 2, 3, or 4")
    if nvec3 < 0:
        raise ModelError("nvec3 must be nonnegative")
    if levels >= 3 and (nvec1 <= 0 or block1 is None):
        raise ModelError("three- and four-level MG require positive nvec1 and block1")
    if levels == 4 and (nvec2 <= 0 or block2 is None):
        raise ModelError("four-level MG requires positive nvec2 and block2")
    if levels < 4 and block2 is not None:
        raise ModelError(f"block2 is not used by a {levels}-level hierarchy")
    if levels == 2 and block1 is not None:
        raise ModelError("block1 is not used by a two-level KD-only hierarchy")
    if prec_null not in PRECISION.values() or prec_setup not in PRECISION.values():
        raise ModelError("unsupported MG precision")
    if setup_ws < 0 or copy_factor <= 0:
        raise ModelError("setup workspace must be nonnegative and copy factor positive")

    # Level 0 -> 1 is the KD transfer and does not coarsen the lattice.  The two
    # optional blocks are the true level 1 -> 2 and level 2 -> 3 aggregations.
    x2 = (
        validate_effective_block(dims, block1, 1, nvec1, 3, 0)
        if levels >= 3 and block1 is not None
        else None
    )
    x3 = (
        validate_effective_block(x2, block2, 2, nvec2, nvec1, 1)
        if levels == 4 and x2 is not None and block2 is not None
        else None
    )
    v0 = volume(dims)
    v2 = volume(x2) if x2 else 0
    v3 = volume(x3) if x3 else 0
    nc2 = coarse_nc(nvec1) if levels >= 3 else 0
    nc3 = coarse_nc(nvec2) if levels == 4 else 0
    n_aos = 2 if use_mma else 0

    base = cg_fit(dims)
    resident = {
        "cg_equiv": base.device_gib * GIB,
        "xInvKD_current_high_water": CURRENT_KD_HIGH_WATER_FACTOR
        * gauge_field_bytes(dims, 3, prec_setup, "kdinverse"),
        "xInvKD_sloppy_current_high_water": CURRENT_KD_HIGH_WATER_FACTOR
        * gauge_field_bytes(dims, 3, prec_null, "kdinverse"),
    }
    if levels >= 3:
        resident["B_l1"] = model_spinor_bytes(dims, 3, 1, prec_setup, nvec1)

    def y_set(x: list[int], nc: int, native: int, ghosts: int) -> float:
        return copy_factor * (
            native
            * gauge_field_bytes(x, nc, prec_null, "coarse", coarse_pad(x))
            + ghosts * gauge_aos_ghost_bytes(x, nc, prec_null)
        )

    def x_set(x: list[int], nc: int, half: int, single: int) -> int:
        return half * gauge_field_bytes(x, nc, prec_null, "scalar") + single * gauge_field_bytes(
            x, nc, PRECISION["single"], "scalar"
        )

    def coarsest_deflation(x: list[int], nc: int, nvec_fine: int) -> float:
        # Inferred and never validated.  B_coarse and the 1.5*nvec3 Krylov estimate
        # are the two private-model bounds; use the larger for capacity screening.
        if nvec3 == 0:
            return 0.0
        b_coarse = model_spinor_bytes(x, nc, 2, prec_setup, max(nvec_fine, nvec3))
        n_kr = int(1.5 * nvec3)
        krylov = n_kr * (volume(x) // 2) * nvec_fine * 2 * 2 * PRECISION["single"]
        return max(b_coarse, krylov)

    phases: dict[str, dict[str, float]] = {}
    if levels == 2:
        phase_a = dict(resident)
        if nvec3:
            phase_a["deflation_l1_unvalidated"] = coarsest_deflation(dims, 3, 3)
        phases["A"] = phase_a
    else:
        phases["A"] = dict(resident, setup_ws=setup_ws * v0)
        assert x2 is not None
        phase_b = dict(resident)
        phase_b.update(
            {
                "V_l1": model_spinor_bytes(dims, 3 * nvec1, 1, prec_null),
                "geomap": 2 * v0 * 4 + 2 * v2 * 4,
                "uv_av": 2 * model_spinor_bytes(dims, 3 * nvec1, 2, prec_null),
                "Y_l2": y_set(x2, nc2, 4 + n_aos, 2 + n_aos),
                "X_l2": x_set(x2, nc2, 2 + n_aos, 2),
            }
        )
        if levels == 3:
            phase_b["deflation_l2_unvalidated"] = coarsest_deflation(x2, nc2, nvec1)
        phases["B"] = phase_b

        if levels == 4:
            assert x3 is not None
            phase_c = dict(resident)
            phase_c.update(
                {
                    "V_l1": phase_b["V_l1"],
                    "geomap": phase_b["geomap"],
                    "B_l2": model_spinor_bytes(x2, nc2, 2, prec_setup, nvec2),
                    "V_l2": model_spinor_bytes(x2, nc2 * nvec2, 2, prec_null),
                    "Y_l2": y_set(x2, nc2, 2 + n_aos, n_aos),
                    "X_l2": x_set(x2, nc2, 2 + n_aos, 0),
                    "Y_l3": y_set(x3, nc3, 4 + n_aos, 2 + n_aos),
                    "X_l3": x_set(x3, nc3, 2 + n_aos, 2),
                    "B_l3": model_spinor_bytes(
                        x3, nc3, 2, prec_setup, max(nvec2, nvec3)
                    ),
                }
            )
            phase_c["uv_av"] = 2 * phase_c["V_l2"]
            phases["C"] = phase_c

    totals = {name: sum(terms.values()) for name, terms in phases.items()}
    peak = max(totals, key=totals.get)
    precision_names = {value: name for name, value in PRECISION.items()}
    extrapolations: list[str] = []
    if levels != 4:
        extrapolations.append(
            f"LOUD WARNING: {levels}-level MG high-water has never been empirically validated"
        )
    if levels >= 3 and nvec1 != 64:
        extrapolations.append("nvec_1 differs from 64, the only completed corpus value")
    if prec_null != PRECISION["half"] or prec_setup != PRECISION["single"]:
        extrapolations.append(
            "LOUD WARNING: non-default MG precision is source-formula extrapolation and "
            "has never been empirically validated"
        )
    if setup_ws != MG_SETUP_WS_BYTES_PER_SITE or copy_factor != MG_COARSE_COPY_FACTOR:
        extrapolations.append(
            "LOUD WARNING: fitted workspace/copy constants were overridden; published "
            "error statistics no longer apply"
        )
    extrapolations.append(
        "current-code KD high-water factor uses one 0.04-fm A-B-A measurement and is volume-scaled"
    )
    return Fit(
        totals[peak] / GIB,
        None,
        {
            "V0": v0,
            "V2": v2,
            "V3_local": v3,
            "x2": x2,
            "x3": x3,
            "mg_levels": levels,
            "four_level_empirically_validated": levels == 4,
            "winning_phase": peak,
            "phase_gib": {name: value / GIB for name, value in totals.items()},
            "winning_terms_gib": {name: value / GIB for name, value in phases[peak].items()},
            "model_controls": {
                "null_precision": precision_names[prec_null],
                "setup_precision": precision_names[prec_setup],
                "setup_ws_bytes_per_site": setup_ws,
                "coarse_copy_factor": copy_factor,
            },
            "software_era": "QUDA at or after 0006627c1",
            "current_kd_high_water_factor": CURRENT_KD_HIGH_WATER_FACTOR,
            "extrapolations": extrapolations,
        },
    )


def pool_fit(dims: list[int], partitioned: list[int]) -> Fit:
    if len(partitioned) != 4 or any(value not in (0, 1) for value in partitioned):
        raise ModelError("partitioned must contain four values, each 0 or 1")
    surfaces = surface_cb(dims)
    selected = sum(surface for surface, active in zip(surfaces, partitioned) if active)
    value = CURRENT_POOL_BYTES_PER_SURFACE_SITE * selected / GIB if selected else 0.0
    return Fit(
        value,
        value,
        {
            "surface_cb_partitioned": selected,
            "software_era": "current-code corpus calibration",
            "bytes_per_surface_cb": CURRENT_POOL_BYTES_PER_SURFACE_SITE,
        },
    )


def mg_page_locked_host_fit(dims: list[int], partitioned: list[int]) -> Fit:
    """Predict QUDA's Page-locked host counter, not total host or scheduler RSS."""
    base = cg_fit(dims)
    # Current-code CG and MG use the same calibrated fine-surface pool.  Retain the
    # subtraction/addition explicitly because this is the mechanism and the place a
    # target-build pool recalibration would enter.
    cg_pool = pool_fit(dims, partitioned).host_gib
    mg_pool = pool_fit(dims, partitioned).host_gib
    page_locked = base.host_gib - cg_pool + mg_pool
    return Fit(
        None,
        page_locked,
        {
            "cg_quda_host_gib": base.host_gib,
            "cg_pool_gib": cg_pool,
            "mg_pool_gib": mg_pool,
            "identity": "CG QUDA host - CG host-pool + MG host-pool",
            "counter_scope": "QUDA Page-locked host memory used",
            "not_predicted": ["QUDA Total host memory used", "scheduler MaxRSS"],
        },
    )


def prediction_assessment(
    hierarchy: dict[str, object],
    machine: str,
    levels: int,
    nvec1: int,
    nvec2: int,
    nvec3: int,
    prec_null: int,
    prec_setup: int,
    setup_ws: float,
    copy_factor: float,
) -> dict[str, object]:
    """Classify a result without turning a calibration envelope into a guarantee."""
    local = tuple(hierarchy["local_dims"])
    rank_geometry = hierarchy.get("rank_geometry")
    effective = hierarchy["effective_blocks"]
    checks = {
        "machine_is_perlmutter_a100_40": machine == PERLMUTTER_A100["name"],
        "four_levels": levels == 4,
        "half_null_precision": prec_null == PRECISION["half"],
        "single_setup_precision": prec_setup == PRECISION["single"],
        "default_setup_workspace_fit": setup_ws == MG_SETUP_WS_BYTES_PER_SITE,
        "default_coarse_copy_fit": copy_factor == MG_COARSE_COPY_FACTOR,
        "nvec1_is_calibrated_64": nvec1 == 64,
        "nvec2_in_observed_set": levels != 4 or nvec2 in CALIBRATED_NVEC2,
        "nvec3_in_observed_set": nvec3 in CALIBRATED_NVEC3,
        "local_shape_observed": local in CALIBRATED_LOCAL_DIMS,
        "rank_geometry_observed": (
            tuple(rank_geometry) in CALIBRATED_RANK_GEOMETRIES
            if rank_geometry is not None
            else False
        ),
        "effective_block1_observed": (
            levels < 3 or (len(effective) >= 1 and tuple(effective[0]) in CALIBRATED_BLOCK1)
        ),
        "effective_block2_observed": (
            levels < 4 or (len(effective) >= 2 and tuple(effective[1]) in CALIBRATED_BLOCK2)
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    warnings: list[str] = []
    if levels != 4:
        tier = "unvalidated-structural-extrapolation"
        warnings.append(
            f"LOUD WARNING: {levels}-level MG has never been empirically validated; "
            "no measured error bound applies"
        )
    elif all(checks.values()):
        tier = "calibrated-envelope-current-code"
    else:
        tier = "caveated-extrapolation"
        warnings.append(
            "one or more inputs leave the component-wise four-level calibration envelope"
        )
    if prec_null != PRECISION["half"] or prec_setup != PRECISION["single"]:
        warnings.append(
            "LOUD WARNING: the selected MG precision has never been empirically validated"
        )
    if setup_ws != MG_SETUP_WS_BYTES_PER_SITE or copy_factor != MG_COARSE_COPY_FACTOR:
        warnings.append(
            "LOUD WARNING: custom calibration controls invalidate the published error statistics"
        )
    if machine != PERLMUTTER_A100["name"]:
        warnings.append("machine portability has not been empirically validated")
    if rank_geometry is not None and geometry_product(rank_geometry) == 1:
        warnings.append("single-rank MG is outside the calibrated population")
    warnings.append(
        "current-code KD correction is anchored by one 0.04-fm A-B-A measurement; "
        "its scaling to other local volumes is an explicit extrapolation"
    )
    return {
        "tier": tier,
        "reliable_screening_with_published_error": tier == "calibrated-envelope-current-code",
        "runtime_fit_guarantee": False,
        "published_device_error": (
            "rms 3.9%, maximum 10.7% for the historical four-level calibration, "
            "plus the separately caveated current-code KD correction"
            if tier == "calibrated-envelope-current-code"
            else None
        ),
        "envelope_checks": checks,
        "failed_envelope_checks": failed,
        "warnings": warnings,
    }


def build_mg_payload(
    hierarchy: dict[str, object],
    partitioned: list[int],
    machine: str,
    levels: int,
    nvec1: int,
    nvec2: int,
    nvec3: int,
    use_mma: bool,
    prec_null: int,
    prec_setup: int,
    setup_ws: float,
    copy_factor: float,
    gpu_gib: float | None = None,
    margin_gib: float | None = None,
) -> dict[str, object]:
    if hierarchy["source_status"] != "pass":
        raise ModelError("decomposition failed source checks; no memory estimate was produced")
    local = hierarchy["local_dims"]
    effective = hierarchy["effective_blocks"]
    block1 = effective[0] if levels >= 3 else None
    block2 = effective[1] if levels == 4 else None
    fit = mg_corpus_fit(
        local,
        block1,
        block2,
        nvec1,
        nvec2,
        nvec3,
        use_mma,
        levels,
        prec_null,
        prec_setup,
        setup_ws,
        copy_factor,
    )
    pool = pool_fit(local, partitioned)
    page_locked = mg_page_locked_host_fit(local, partitioned)
    total = fit.device_gib + pool.device_gib
    assessment = prediction_assessment(
        hierarchy,
        machine,
        levels,
        nvec1,
        nvec2,
        nvec3,
        prec_null,
        prec_setup,
        setup_ws,
        copy_factor,
    )
    warnings = list(dict.fromkeys(fit.detail["extrapolations"] + assessment["warnings"]))
    if hierarchy["requested_blocks_changed"]:
        warnings.append(
            "requested aggregation blocks were adjusted; confirm QUDA's runtime block messages"
        )
    payload: dict[str, object] = {
        "evidence": "corpus-calibrated-with-source-geometry",
        "calibration": CALIBRATION,
        "machine_scope": machine,
        "prediction_assessment": assessment,
        "warnings": warnings,
        "counter_scope": {
            "device_gib": "QUDA Device memory used",
            "pool_gib": "QUDA Pinned device memory used",
            "quda_visible_total_gib": "sum of the two disjoint device high-water counters",
            "page_locked_host_gib": "QUDA Page-locked host memory used",
        },
        "device_gib": fit.device_gib,
        "pool_gib": pool.device_gib,
        "quda_visible_total_gib": total,
        "page_locked_host_gib": page_locked.host_gib,
        "detail": fit.detail,
        "pool_detail": pool.detail,
        "page_locked_host_detail": page_locked.detail,
        "geometry": hierarchy,
    }
    if gpu_gib is not None or margin_gib is not None:
        if gpu_gib is None or margin_gib is None:
            raise ModelError("gpu-gib and margin-gib must be supplied together")
        payload["capacity_advisory"] = capacity_advisory(total, gpu_gib, margin_gib)
    return payload


def search_mg_decompositions(
    global_dims: list[int],
    nodes_lt: int,
    machine: dict[str, object],
    levels: int,
    block1: list[int] | None,
    block2: list[int] | None,
    nvec1: int,
    nvec2: int,
    nvec3: int,
    use_mma: bool,
    prec_null: int,
    prec_setup: int,
    setup_ws: float,
    copy_factor: float,
    min_nodes: int = 1,
    min_local: int = 1,
) -> dict[str, object]:
    """Enumerate every tiling rank geometry below an exclusive Perlmutter node bound."""
    if nodes_lt <= min_nodes:
        raise ModelError("nodes-lt must be greater than min-nodes")
    results: dict[str, list[dict[str, object]]] = {
        "outside_advisory_band": [],
        "inside_advisory_band": [],
        "over_capacity": [],
    }
    source_invalid = 0
    model_incompatible = 0
    total_rank_geometries = 0
    ranks_per_node = int(machine["ranks_per_node"])
    for nodes in range(min_nodes, nodes_lt):
        for ranks in rank_geometries(global_dims, nodes * ranks_per_node, min_local):
            total_rank_geometries += 1
            hierarchy = evaluate_decomposition(
                global_dims,
                ranks,
                levels,
                block1,
                block2,
                nvec1,
                nvec2,
                nvec3,
            )
            if hierarchy["source_status"] != "pass":
                source_invalid += 1
                continue
            try:
                payload = build_mg_payload(
                    hierarchy,
                    hierarchy["partitioned"],
                    str(machine["name"]),
                    levels,
                    nvec1,
                    nvec2,
                    nvec3,
                    use_mma,
                    prec_null,
                    prec_setup,
                    setup_ws,
                    copy_factor,
                    float(machine["gpu_gib"]),
                    float(machine["advisory_margin_gib"]),
                )
            except ModelError:
                # Keep exhaustive rank-grid accounting even when checkerboarded field
                # or surface requirements lie outside this model's representable domain.
                model_incompatible += 1
                continue
            status = payload["capacity_advisory"]["status"]
            key = status.replace("-", "_")
            row = {
                "nodes": nodes,
                "total_ranks": nodes * ranks_per_node,
                "rank_geometry": ranks,
                "local_dims": hierarchy["local_dims"],
                "requested_blocks_changed": hierarchy["requested_blocks_changed"],
                "effective_blocks": hierarchy["effective_blocks"],
                "device_gib": payload["device_gib"],
                "pool_gib": payload["pool_gib"],
                "quda_visible_total_gib": payload["quda_visible_total_gib"],
                "page_locked_host_gib_per_rank": payload["page_locked_host_gib"],
                "page_locked_host_gib_per_node": (
                    payload["page_locked_host_gib"] * ranks_per_node
                ),
                "page_locked_host_headroom_gib_per_node": (
                    float(machine["host_gib_per_node"])
                    - payload["page_locked_host_gib"] * ranks_per_node
                ),
                "gpu_headroom_gib": payload["capacity_advisory"]["estimated_headroom_gib"],
                "capacity_status": status,
                "prediction_tier": payload["prediction_assessment"]["tier"],
                "warnings": payload["warnings"],
            }
            results[key].append(row)
    return {
        "search_contract": {
            "node_bound": f"{min_nodes} <= nodes < {nodes_lt}",
            "complete_rank_geometry_enumeration": True,
            "min_local_extent": min_local,
            "machine": machine,
            "capacity_meaning": (
                "outside_advisory_band is a screening result, not a runtime fit guarantee"
            ),
        },
        "global_dims": global_dims,
        "parameters": {
            "levels": levels,
            "requested_block1": block1,
            "requested_block2": block2,
            "nvec1": nvec1,
            "nvec2": nvec2,
            "nvec3": nvec3,
            "use_mma": use_mma,
            "null_precision": {value: name for name, value in PRECISION.items()}[prec_null],
            "setup_precision": {value: name for name, value in PRECISION.items()}[prec_setup],
            "setup_ws_bytes_per_site": setup_ws,
            "coarse_copy_factor": copy_factor,
        },
        "counts": {
            "rank_geometries_considered": total_rank_geometries,
            "source_invalid_after_block_adjustment": source_invalid,
            "memory_model_incompatible": model_incompatible,
            "source_valid_and_modelled": (
                total_rank_geometries - source_invalid - model_incompatible
            ),
            **{name: len(rows) for name, rows in results.items()},
        },
        **results,
    }


def capacity_advisory(total_gib: float, gpu_gib: float, margin_gib: float) -> dict[str, object]:
    if gpu_gib <= 0 or margin_gib < 0:
        raise ModelError("gpu-gib must be positive and margin-gib nonnegative")
    headroom = gpu_gib - total_gib
    if headroom < 0:
        status = "over-capacity"
    elif headroom < margin_gib:
        status = "inside-advisory-band"
    else:
        status = "outside-advisory-band"
    return {
        "gpu_gib": gpu_gib,
        "requested_margin_gib": margin_gib,
        "estimated_headroom_gib": headroom,
        "status": status,
        "guarantee": False,
    }


def rounded(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(rounded(payload), indent=2, sort_keys=True))


def add_local(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--local", nargs=4, type=int, required=True, metavar=("X", "Y", "Z", "T"))


def add_capacity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--gpu-gib", type=float)
    parser.add_argument("--margin-gib", type=float)


def add_mg_parameters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--levels", type=int, choices=(2, 3, 4), default=4)
    parser.add_argument("--block1", nargs=4, type=int, metavar=("BX", "BY", "BZ", "BT"))
    parser.add_argument("--block2", nargs=4, type=int, metavar=("BX", "BY", "BZ", "BT"))
    parser.add_argument("--nvec1", type=int, default=0)
    parser.add_argument("--nvec2", type=int, default=0)
    parser.add_argument("--nvec3", type=int, default=0)
    mma = parser.add_mutually_exclusive_group(required=True)
    mma.add_argument("--mma", dest="mma", action="store_true")
    mma.add_argument("--no-mma", dest="mma", action="store_false")
    parser.add_argument("--null-precision", choices=PRECISION, default="half")
    parser.add_argument("--setup-precision", choices=PRECISION, default="single")
    parser.add_argument(
        "--setup-ws-bytes-per-site", type=float, default=MG_SETUP_WS_BYTES_PER_SITE
    )
    parser.add_argument("--coarse-copy-factor", type=float, default=MG_COARSE_COPY_FACTOR)


def resolve_mg_hierarchy(args: argparse.Namespace) -> tuple[dict[str, object], list[int]]:
    if args.global_dims is not None:
        if args.ranks is None:
            raise ModelError("--ranks is required with --global")
        if args.partitioned is not None:
            raise ModelError("--partitioned is derived from --ranks and may not be supplied")
        hierarchy = evaluate_decomposition(
            args.global_dims,
            args.ranks,
            args.levels,
            args.block1,
            args.block2,
            args.nvec1,
            args.nvec2,
            args.nvec3,
            args.compiled_nvecs,
            args.lattice_spacing_fm,
            args.corpus_advisories,
        )
        partitioned = hierarchy["partitioned"]
    else:
        if args.ranks is not None:
            raise ModelError("--ranks requires --global")
        if args.partitioned is None:
            raise ModelError("--partitioned is required with --local")
        hierarchy = evaluate_local_hierarchy(
            args.local,
            args.levels,
            args.block1,
            args.block2,
            args.nvec1,
            args.nvec2,
        )
        hierarchy.update(
            {
                "global_dims": None,
                "rank_geometry": None,
                "total_ranks": None,
                "partitioned": args.partitioned,
                "metrics": {},
                "empirical_screen": {
                    "enabled": False,
                    "advisories": [
                        "global coarse-grid advisories require --global and --ranks"
                    ],
                },
            }
        )
        partitioned = args.partitioned
    if hierarchy["source_status"] != "pass":
        raise ModelError("; ".join(hierarchy["source_errors"]))
    return hierarchy, partitioned


def emit_loud_warnings(warnings: list[str]) -> None:
    for warning in dict.fromkeys(warnings):
        if warning.startswith("LOUD WARNING:"):
            print(warning, file=sys.stderr)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    spinor = commands.add_parser("spinor", help="source-exact native ColorSpinorField allocation")
    add_local(spinor)
    spinor.add_argument("--ncolor", type=int, required=True)
    spinor.add_argument("--nspin", type=int, required=True)
    spinor.add_argument("--precision", choices=PRECISION, required=True)
    spinor.add_argument("--subset", choices=("full", "parity"), required=True)
    spinor.add_argument("--count", type=int, default=1)

    gauge = commands.add_parser("gauge", help="source-exact native unreconstructed GaugeField allocation")
    add_local(gauge)
    gauge.add_argument("--ncolor", type=int, required=True)
    gauge.add_argument("--precision", choices=PRECISION, required=True)
    gauge.add_argument("--geometry", choices=GEOMETRY, required=True)
    gauge.add_argument("--pad", type=int, default=0)
    gauge.add_argument("--coarse-pad", action="store_true")
    gauge.add_argument("--count", type=int, default=1)

    cg = commands.add_parser("cg-fit", help="corpus-calibrated plain-CG high-water estimate")
    add_local(cg)

    mrhs_cg = commands.add_parser(
        "mrhs-cg-delta",
        help="source-derived plain-CG QUDA Device increment for active batch width",
    )
    add_local(mrhs_cg)
    mrhs_cg.add_argument("--width", type=int, required=True, help="active batch width")
    mrhs_cg.add_argument(
        "--reference-width",
        type=int,
        default=1,
        help="active reference batch width; default 1",
    )

    deflated = commands.add_parser(
        "deflated-fit", help="corpus-calibrated deflated-CG high-water estimate"
    )
    add_local(deflated)
    deflated.add_argument("--vectors", type=int, required=True)

    mg = commands.add_parser(
        "mg-fit",
        help="integrated 2/3/4-level MG decomposition and high-water estimate",
    )
    mg_geometry = mg.add_mutually_exclusive_group(required=True)
    mg_geometry.add_argument("--local", nargs=4, type=int, metavar=("X", "Y", "Z", "T"))
    mg_geometry.add_argument(
        "--global", dest="global_dims", nargs=4, type=int, metavar=("X", "Y", "Z", "T")
    )
    mg.add_argument("--ranks", nargs=4, type=int, metavar=("RX", "RY", "RZ", "RT"))
    mg.add_argument("--partitioned", nargs=4, type=int, metavar=("X", "Y", "Z", "T"))
    mg.add_argument("--compiled-nvecs", nargs="+", type=int)
    mg.add_argument("--lattice-spacing-fm", type=float)
    mg.add_argument("--corpus-advisories", action="store_true")
    mg.add_argument(
        "--machine",
        choices=("unspecified", "other", *MACHINE_PROFILES),
        default="unspecified",
        help="select a calibrated machine scope; no machine is inferred",
    )
    add_mg_parameters(mg)
    add_capacity(mg)

    search = commands.add_parser(
        "mg-search",
        help="enumerate every valid rank geometry below an exclusive node limit",
    )
    search.add_argument("--global", dest="global_dims", nargs=4, type=int, required=True)
    search.add_argument("--nodes-lt", type=int, required=True)
    search.add_argument("--min-nodes", type=int, default=1)
    search.add_argument(
        "--min-local",
        type=int,
        default=1,
        help="optional explicit search filter; default 1 adds no heuristic local-extent cutoff",
    )
    search.add_argument("--machine", choices=MACHINE_PROFILES, required=True)
    add_mg_parameters(search)
    return root


def main() -> int:
    command = parser()
    args = command.parse_args()
    try:
        if args.command == "spinor":
            size = color_spinor_bytes(
                args.local,
                args.ncolor,
                args.nspin,
                PRECISION[args.precision],
                args.subset,
                args.count,
            )
            emit(
                {
                    "evidence": "source-exact-object",
                    "source_revision": "quda-b6998853f",
                    "scope": "native field allocation only; excludes shared communication buffers and process peak",
                    "bytes": size,
                    "gib": size / GIB,
                }
            )
        elif args.command == "gauge":
            pad = coarse_pad(args.local) if args.coarse_pad else args.pad
            size = gauge_field_bytes(
                args.local,
                args.ncolor,
                PRECISION[args.precision],
                args.geometry,
                pad,
                args.count,
            )
            emit(
                {
                    "evidence": "source-exact-object",
                    "source_revision": "quda-b6998853f",
                    "scope": "native unreconstructed field allocation only; excludes shared ghost buffers and process peak",
                    "pad": pad,
                    "bytes": size,
                    "gib": size / GIB,
                }
            )
        elif args.command == "mrhs-cg-delta":
            detail = mrhs_cg_delta(args.local, args.width, args.reference_width)
            emit(
                {
                    "evidence": "source-derived-with-corpus-validation",
                    "source_revision": "quda-b6998853f",
                    "scope": (
                        "plain unsplit MATPC/direct-PC CG production-width increment only; "
                        "active batch width, not total application source count"
                    ),
                    "counter_scope": {
                        "predicted": "QUDA Device increment",
                        "observed_without_width_term": [
                            "Pinned device memory used",
                            "Page-locked host memory used",
                            "Total host memory used within 0.1 MiB reporting precision",
                        ],
                        "not_modelled": [
                            "whole-process scheduler RSS",
                            "deflation-space storage",
                            "split grid",
                            "other inverter or precision profiles",
                        ],
                    },
                    "validation": MRHS_CG_VALIDATION,
                    "detail": detail,
                }
            )
        elif args.command in ("cg-fit", "deflated-fit"):
            fit = cg_fit(args.local) if args.command == "cg-fit" else deflated_fit(args.local, args.vectors)
            emit(
                {
                    "evidence": "corpus-calibrated",
                    "calibration": CALIBRATION,
                    "counter_scope": "QUDA Device and QUDA host high-water; communication pool excluded",
                    "device_gib": fit.device_gib,
                    "quda_host_gib": fit.host_gib,
                    "detail": fit.detail,
                }
            )
        elif args.command == "mg-fit":
            if args.nvec1 < 0 or args.nvec2 < 0 or args.nvec3 < 0:
                raise ModelError("nvec values must be nonnegative")
            hierarchy, partitioned = resolve_mg_hierarchy(args)
            gpu_gib, margin_gib = args.gpu_gib, args.margin_gib
            if args.machine in MACHINE_PROFILES and gpu_gib is None and margin_gib is None:
                profile = MACHINE_PROFILES[args.machine]
                gpu_gib = float(profile["gpu_gib"])
                margin_gib = float(profile["advisory_margin_gib"])
            payload = build_mg_payload(
                hierarchy,
                partitioned,
                args.machine,
                args.levels,
                args.nvec1,
                args.nvec2,
                args.nvec3,
                args.mma,
                PRECISION[args.null_precision],
                PRECISION[args.setup_precision],
                args.setup_ws_bytes_per_site,
                args.coarse_copy_factor,
                gpu_gib,
                margin_gib,
            )
            emit_loud_warnings(payload["warnings"])
            emit(payload)
        else:
            if args.nvec1 < 0 or args.nvec2 < 0 or args.nvec3 < 0:
                raise ModelError("nvec values must be nonnegative")
            requested_warnings: list[str] = []
            if args.levels != 4:
                requested_warnings.append(
                    f"LOUD WARNING: {args.levels}-level MG has never been empirically "
                    "validated; no measured error bound applies"
                )
            if args.null_precision != "half" or args.setup_precision != "single":
                requested_warnings.append(
                    "LOUD WARNING: the selected MG precision has never been empirically validated"
                )
            if (
                args.setup_ws_bytes_per_site != MG_SETUP_WS_BYTES_PER_SITE
                or args.coarse_copy_factor != MG_COARSE_COPY_FACTOR
            ):
                requested_warnings.append(
                    "LOUD WARNING: custom calibration controls invalidate the published "
                    "error statistics"
                )
            emit_loud_warnings(requested_warnings)
            payload = search_mg_decompositions(
                args.global_dims,
                args.nodes_lt,
                MACHINE_PROFILES[args.machine],
                args.levels,
                args.block1,
                args.block2,
                args.nvec1,
                args.nvec2,
                args.nvec3,
                args.mma,
                PRECISION[args.null_precision],
                PRECISION[args.setup_precision],
                args.setup_ws_bytes_per_site,
                args.coarse_copy_factor,
                args.min_nodes,
                args.min_local,
            )
            search_warnings: list[str] = []
            for category in (
                "outside_advisory_band",
                "inside_advisory_band",
                "over_capacity",
            ):
                for row in payload[category]:
                    search_warnings.extend(row["warnings"])
            emit_loud_warnings(search_warnings)
            emit(payload)
    except (KeyError, ModelError, GeometryError) as exc:
        command.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
