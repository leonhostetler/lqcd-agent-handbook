#!/usr/bin/env python3
"""Offline GPU profile extraction.

Reads an Nsight Systems SQLite export and emits structured metrics as JSON. Makes
no model call, opens no socket, needs no key, and imports nothing outside the
standard library, so it runs on a login node behind MFA and cannot fail to import
because a package is absent.

Every subcommand is an aggregation a session would otherwise recompute by hand and
get wrong in a way that reads as plausible -- summing kernel durations returns work
where the reader wanted elapsed time. ``query`` is the escape hatch, not the
method: it is read-only, row-capped and interruptible. See ARCHITECTURE.md
§profile-analysis, and modes/performance.md for what the numbers may and may not be
read to say.

The profile is opened read-only. This tool never writes to a profile.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpu_profile import open_profile  # noqa: E402
from gpu_profile.cross_rank import (  # noqa: E402
    align_phases,
    compute_cross_rank_summary,
    parse_rank_ids,
    select_consensus_k,
    select_primary_rank,
)
from gpu_profile.diagnostics import capability_notes  # noqa: E402
from gpu_profile.metrics import (  # noqa: E402
    _compute_launch_overhead,
    _window_idle_time,
    _window_kernel_time,
    _window_marker_ranges,
    _window_memcpy_by_kind,
    _window_mpi_ops,
    _window_streams,
    _window_top_kernels,
    compute_device_info,
    compute_gap_histogram,
    compute_gpu_busy_time,
    compute_gpu_kernel_time,
    compute_marker_ranges,
    compute_memcpy_by_kind,
    compute_mpi_ops,
    compute_profile_span,
    compute_profile_summary,
    compute_profile_summary_and_state,
    compute_streams,
    compute_top_kernels,
)

DEFAULT_ROW_LIMIT = 200


def _plain(obj):
    """Render dataclasses, rows and nested containers as JSON-safe values."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    return obj


def _window(args) -> tuple[int, int] | None:
    if args.start_ns is None or args.end_ns is None:
        return None
    if args.end_ns <= args.start_ns:
        raise SystemExit("error: --end-ns must be greater than --start-ns")
    return int(args.start_ns), int(args.end_ns)


def cmd_summary(profile, args) -> dict:
    summary = compute_profile_summary(profile, max_phases=args.max_phases)
    out = asdict(summary)
    out["capability_notes"] = _plain(capability_notes(profile.format, profile.capabilities))
    return out


def cmd_phases(profile, args) -> dict:
    summary = compute_profile_summary(profile, max_phases=args.max_phases)
    return {"phases": [asdict(p) for p in summary.phases]}


def cmd_kernels(profile, args) -> dict:
    device_info = compute_device_info(profile)
    overhead = _compute_launch_overhead(profile)
    win = _window(args)
    if win:
        evts = profile.kernel_events()
        total = _window_kernel_time(evts, *win)
        kernels = _window_top_kernels(
            evts, *win, total, limit=args.top, device_info=device_info, launch_overhead=overhead
        )
    else:
        kernels = compute_top_kernels(
            profile, limit=args.top, device_info=device_info, launch_overhead=overhead
        )
    return {"kernels": _plain(kernels)}


def cmd_gaps(profile, args) -> dict:
    win = _window(args)
    total_idle_s, buckets = (
        _window_idle_time(profile.kernel_events(), *win) if win else compute_gap_histogram(profile)
    )
    return {"total_idle_s": round(total_idle_s, 3), "buckets": _plain(buckets)}


def cmd_memcpy(profile, args) -> dict:
    win = _window(args)
    transfers = (
        _window_memcpy_by_kind(profile.memcpy_events(), *win)
        if win
        else compute_memcpy_by_kind(profile)
    )
    return {"transfers": _plain(transfers)}


def cmd_mpi(profile, args) -> dict:
    win = _window(args)
    ops = _window_mpi_ops(profile, *win) if win else compute_mpi_ops(profile)
    return {"mpi_present": profile.capabilities.has_mpi, "ops": _plain(ops)}


def cmd_streams(profile, args) -> dict:
    win = _window(args)
    streams = _window_streams(profile.kernel_events(), *win) if win else compute_streams(profile)
    return {"streams": _plain(streams)}


def cmd_markers(profile, args) -> dict:
    win = _window(args)
    ranges = (
        _window_marker_ranges(profile, *win, limit=args.top)
        if win
        else compute_marker_ranges(profile, limit=args.top)
    )
    return {"markers_present": profile.capabilities.has_markers, "ranges": _plain(ranges)}


def cmd_schema(profile, args) -> dict:
    if args.table:
        if args.table not in profile.tables:
            raise SystemExit(f"error: no table named {args.table!r} in this profile")
        rows = profile.query(f"PRAGMA table_info({args.table})")
        return {"table": args.table, "columns": [r["name"] for r in rows]}
    return {"tables": sorted(profile.tables)}


def cmd_query(profile, args) -> dict:
    rows = profile.query_safe(args.sql, row_limit=args.max_rows)
    return {
        "row_limit": args.max_rows,
        "row_count": len(rows),
        "truncated": len(rows) >= args.max_rows,
        "rows": [dict(r) for r in rows],
    }


def cmd_cross_rank(_unused, args) -> dict:
    """Align per-rank profiles and report where the ranks disagree.

    Imbalance is a cross-rank quantity: on a single rank, a rank waiting on its
    neighbours is indistinguishable from a rank with a problem of its own. That is
    why this is a separate subcommand rather than a field on `summary`.
    """
    paths = [Path(p) for p in args.profiles]
    if len(paths) < 2:
        raise SystemExit("error: cross-rank needs at least two profiles")

    rank_ids, parsed_ok = parse_rank_ids(paths)
    by_rank = dict(zip(rank_ids, paths))

    # A mixed-format run is rejected rather than merged: the two profilers record
    # different things, so an imbalance computed across them is not a measurement.
    formats = {}
    for rid, path in sorted(by_rank.items()):
        with open_profile(path) as prof:
            formats[rid] = prof.format.value
    if len(set(formats.values())) > 1:
        detail = ", ".join(f"rank {r}: {formats[r]}" for r in sorted(formats))
        raise SystemExit(f"error: mixed-format profiles ({detail})")

    summaries, states, selected_ks, cost_curves = {}, {}, {}, {}
    for rid, path in sorted(by_rank.items()):
        with open_profile(path) as prof:
            (
                summaries[rid],
                states[rid],
                selected_ks[rid],
                cost_curves[rid],
            ) = compute_profile_summary_and_state(prof, max_phases=args.max_phases)

    consensus_k, consensus_note = select_consensus_k(cost_curves, selected_ks, args.max_phases)
    if consensus_k is not None:
        for rid, path in sorted(by_rank.items()):
            if selected_ks[rid] != consensus_k:
                with open_profile(path) as prof:
                    summaries[rid] = compute_profile_summary(
                        prof,
                        max_phases=args.max_phases,
                        forced_k=consensus_k,
                        _phase_state=states[rid],
                    )

    primary_rank_id, primary_reason = select_primary_rank(summaries)
    alignment, alignment_note = align_phases(summaries)
    if alignment == "failed":
        return {
            "cross_rank_available": False,
            "reason": alignment_note,
            "rank_ids": sorted(summaries),
            "primary_rank_id": primary_rank_id,
        }

    summary = compute_cross_rank_summary(summaries, primary_rank_id, alignment)
    out = asdict(summary)
    out["cross_rank_available"] = True
    out["rank_ids_parsed_from_filenames"] = parsed_ok
    out["primary_rank_reason"] = primary_reason
    out["phase_alignment_note"] = alignment_note
    out["consensus_k"] = consensus_k
    out["consensus_note"] = consensus_note
    return out


def _render_table(payload: dict) -> str:
    lines = []
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{key}:")
            cols = list(value[0].keys())
            lines.append("  " + " | ".join(cols))
            for row in value:
                lines.append("  " + " | ".join(str(row.get(c, "")) for c in cols))
        elif not isinstance(value, (list, dict)):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gpu-profile-summary.py",
        description="Extract structured metrics from a GPU profiler database (offline).",
    )
    ap.add_argument("--table", action="store_true", help="human-readable output (default: JSON)")
    sub = ap.add_subparsers(dest="command", required=True)

    def add(name, fn, *, window=False, top=None, phases=False):
        p = sub.add_parser(name)
        p.add_argument("profile", help="path to a profiler SQLite database")
        if window:
            p.add_argument("--start-ns", type=int, help="window start (absolute ns)")
            p.add_argument("--end-ns", type=int, help="window end (absolute ns)")
        if top is not None:
            p.add_argument("--top", type=int, default=top, help=f"entries to return (default {top})")
        if phases:
            p.add_argument("--max-phases", type=int, default=8, help="phase cap (1 disables)")
        p.set_defaults(func=fn)
        return p

    add("summary", cmd_summary, phases=True)
    add("phases", cmd_phases, phases=True)
    add("kernels", cmd_kernels, window=True, top=15)
    add("gaps", cmd_gaps, window=True)
    add("memcpy", cmd_memcpy, window=True)
    add("mpi", cmd_mpi, window=True)
    add("streams", cmd_streams, window=True)
    add("markers", cmd_markers, window=True, top=20)

    p = sub.add_parser("cross-rank")
    p.add_argument("profiles", nargs="+", help="per-rank profiler databases")
    p.add_argument("--max-phases", type=int, default=8, help="phase cap (1 disables)")
    p.set_defaults(func=cmd_cross_rank, multi=True)

    p = add("schema", cmd_schema)
    p.add_argument("table", nargs="?", help="table to describe; omit to list tables")

    p = add("query", cmd_query)
    p.add_argument("--sql", required=True, help="read-only SQL to execute")
    p.add_argument("--max-rows", type=int, default=DEFAULT_ROW_LIMIT, help="row cap")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for attr, default in (("start_ns", None), ("end_ns", None), ("top", 15), ("max_phases", 8)):
        if not hasattr(args, attr):
            setattr(args, attr, default)
    if getattr(args, "multi", False):
        profile = None
    else:
        try:
            profile = open_profile(args.profile)
        except (ValueError, NotImplementedError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    try:
        payload = args.func(profile, args)
    except sqlite3.Error as exc:
        # A rejected write lands here: the profile is opened read-only, so an
        # attempted modification is refused by SQLite rather than by a check.
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(_render_table(payload) if args.table else json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
