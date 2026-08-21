#!/usr/bin/env python3
"""Check a current QUDA optimized-KD staggered-MG decomposition.

Source errors reproduce QUDA b6998853f behavior. Optional corpus advisories are
separate tuning evidence and never change the process exit status. All geometry is
derived from required command-line dimensions; no ensemble or lattice spacing is built in.
"""

from __future__ import annotations

import argparse
import json

from quda_staggered_geometry import GeometryError, evaluate_decomposition


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__)
    out.add_argument(
        "--global", dest="global_dims", nargs=4, type=int, required=True,
        metavar=("LX", "LY", "LZ", "LT"), help="global lattice extents",
    )
    out.add_argument(
        "--ranks", nargs=4, type=int, required=True,
        metavar=("RX", "RY", "RZ", "RT"), help="four-dimensional rank grid",
    )
    out.add_argument(
        "--levels", type=int, choices=(2, 3, 4), default=4,
        help="total QUDA levels; 4 means levels 0, 1, 2, and 3",
    )
    out.add_argument(
        "--block1", nargs=4, type=int, metavar=("BX", "BY", "BZ", "BT"),
        help="MILC geo_block_size 1: aggregate QUDA level 1 into level 2",
    )
    out.add_argument(
        "--block2", nargs=4, type=int, metavar=("BX", "BY", "BZ", "BT"),
        help="MILC geo_block_size 2: aggregate QUDA level 2 into level 3",
    )
    out.add_argument("--nvec1", type=int, default=0, help="MILC nvec 1 coarse color count")
    out.add_argument("--nvec2", type=int, default=0, help="MILC nvec 2 coarse color count")
    out.add_argument(
        "--nvec3", type=int,
        help="MILC nvec 3 coarsest-deflation count; not a compiled coarse color",
    )
    out.add_argument(
        "--compiled-nvecs", nargs="+", type=int,
        help=(
            "values in QUDA_MULTIGRID_NVEC_LIST; omit to leave build capability "
            "explicitly unchecked"
        ),
    )
    out.add_argument(
        "--lattice-spacing-fm", type=float,
        help="optional spacing used only to report coarsest-cell physical extents",
    )
    out.add_argument(
        "--corpus-advisories",
        action="store_true",
        help="apply the provisional four-level V3/aspect screen",
    )
    return out


def main() -> int:
    command = parser()
    args = command.parse_args()
    try:
        if args.nvec1 < 0 or args.nvec2 < 0 or (args.nvec3 is not None and args.nvec3 < 0):
            raise GeometryError("nvec values must be nonnegative")
        payload = evaluate_decomposition(
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
    except GeometryError as exc:
        command.error(str(exc))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 2 if payload["source_status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
