#!/usr/bin/env python3
"""Offline GPU profile extraction.

Reads an Nsight Systems SQLite export and emits structured metrics as JSON. Makes
no model call, opens no socket, needs no key, and imports nothing outside the
standard library, so it runs on a login node behind MFA and cannot fail to import
because a package is absent.

Every subcommand is an aggregation a session would otherwise recompute by hand and
get wrong in a way that reads as plausible -- summing kernel durations returns work
where the reader wanted elapsed time. ``query`` is the escape hatch, not the
method: it is read-only, row-capped, plan-checked and deadline-bounded.

The row cap bounds output, never work: a single scan of a five-million-row event
table costs under a second, so a *scan* was never the hazard. A **nested loop** is
-- an nsys export carries no index on any CUPTI table, so a correlated subquery
re-scans the inner table once per outer row. One such query on a real capture asked
for 4.75M x 5.07M row visits to derive a 260-row constant, returned a single row,
and could not finish. ``--max-seconds`` bounds the loss and the plan check predicts
it, which costs milliseconds. See ARCHITECTURE.md §profile-analysis, and
modes/performance.md for what the numbers may and may not be read to say.

The profile is opened read-only. This tool never writes to a profile.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gpu_profile import open_profile  # noqa: E402
from gpu_profile.cross_rank import (  # noqa: E402
    align_phases,
    compute_cross_rank_summary,
    compute_rank_overviews,
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
    compute_host_samples,
    compute_idle_attribution,
    compute_launch_geometry,
    compute_marker_ranges,
    compute_memcpy_by_kind,
    compute_mpi_ops,
    compute_profile_span,
    compute_profile_summary,
    compute_profile_summary_and_state,
    compute_streams,
    compute_window_breakdown,
    compute_top_kernels,
    compute_transfer_overlap,
    compute_transfer_union,
)

DEFAULT_ROW_LIMIT = 200

# A query is stopped after this many seconds unless --max-seconds says otherwise.
# Grounded rather than guessed: every hand-written query in the session that
# produced this guard ran in 0.11-0.69 s, and the one that motivated it exceeded
# 600 s without finishing. Three orders of magnitude separate the two populations,
# so the value needs no tuning -- anything in 10-120 s catches the runaway and
# touches nothing legitimate.
DEFAULT_QUERY_DEADLINE_S = 120.0

# A table scanned on the inner side of a correlated step is reported as a hazard
# above this row count. Below it the nested loop is affordable even unindexed.
NESTED_SCAN_ROW_THRESHOLD = 100_000


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
    """The phase table on its own.

    **`summary` already contains this**, under the same key and with the same
    contents; this command exists to return it without the rest. It is not cheaper:
    it computes the whole `ProfileSummary` and discards everything but `.phases`,
    because the per-phase rows carry kernel and transfer figures that need the same
    data. Measured on one capture, `summary` and `phases` each cost 48.7 s and
    segmentation was 15.5 s of that -- so running both to follow a two-step
    procedure pays the full price twice. Read `phases` out of a `summary` you have
    already run.

    `phase_segmentation` is emitted here and by `summary` so the two can be
    reconciled: phase windows depend on `--max-phases`, and a `--start-ns`/`--end-ns`
    pair lifted from one segmentation is meaningless against another.
    """
    summary = compute_profile_summary(profile, max_phases=args.max_phases)
    return {
        "phases": [asdict(p) for p in summary.phases],
        "phase_segmentation": _plain(summary.phase_segmentation),
    }


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


def cmd_idle_attribution(profile, args) -> dict:
    win = _window(args)
    result = compute_idle_attribution(profile, *(win or (None, None)))
    return _plain(result)


def cmd_launch_geometry(profile, args) -> dict:
    """Distinct grid and block extents per kernel — the autotune-warmth gate.

    software/quda/profiling.md requires cache warmth to be established before call
    counts, launch geometry or duration spread are read, because a cold cache makes
    all three describe the tuning search instead of the run. The extents are what
    answer it, and until 2026-09-15 they were collapsed into `total_threads`.
    """
    return _plain(compute_launch_geometry(profile, top=args.top))


def cmd_transfer_overlap(profile, args) -> dict:
    win = _window(args)
    bounds = win or (None, None)
    return {
        "directions": _plain(compute_transfer_overlap(profile, *bounds)),
        # Emitted beside the per-direction rows because those rows must not be
        # added up: directions overlap each other in wall-clock. The tool does
        # the merge so prose does not have to forbid the addition.
        "union": _plain(compute_transfer_union(profile, *bounds)),
    }


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
    """List the profile's tables, or one table's columns.

    Reads `args.table_name`, not `args.table`. The positional was called `table`
    until 2026-09-15 and therefore shared a dest with the top-level `--table`
    rendering flag, which argparse resolves by letting the subparser's default win.
    Two things followed and both were silent: `--table schema <profile>` dropped the
    rendering request and returned JSON, and `schema <profile> <NAME>` rendered a
    human-readable table *whether or not* `--table` was given, because the renderer
    tests the same attribute -- so that one form could not produce JSON at all,
    against a tool whose every other subcommand defaults to it.
    """
    name = args.table_name
    if name:
        if name not in profile.tables:
            raise SystemExit(f"error: no table named {name!r} in this profile")
        rows = profile.query(f"PRAGMA table_info({name})")
        return {"table": name, "columns": [r["name"] for r in rows]}
    return {"tables": sorted(profile.tables)}


def _plan_hazard(profile, sql: str) -> str | None:
    """Name the plan shape that makes a query on a profile database unfinishable.

    EXPLAIN QUERY PLAN yields (id, parent, aux, detail). A node whose detail
    begins "SCAN <name>" is a full table scan; an ancestor whose detail contains
    "CORRELATED" means that scan is re-run once per outer row. An nsys export
    carries no index on any CUPTI table, so the product of those two is the whole
    hazard -- and planning costs milliseconds, so it is always worth asking.

    This is a guard, not a proof, and it errs in both directions. A scan reported
    under an alias or a derived-table name cannot be sized against `profile.tables`
    and is passed over -- which is why the deadline in `query_safe` remains and is
    not optional. In the other direction EXPLAIN QUERY PLAN carries no row
    estimates, so the *outer* cardinality is unknown and a correlated scan of a
    large table is flagged even where few outer rows make it cheap. That is the
    deliberate direction to err: the refusal is one flag to override, and the
    failure it prevents cost 26 minutes and produced nothing.
    """
    try:
        plan = profile.explain_plan(sql)
    except sqlite3.Error:
        return None  # a plan we cannot obtain is not a plan we can judge

    nodes = {row[0]: (row[1], str(row[3])) for row in plan}

    def ancestor_details(node_id: int):
        """Walk outwards, stopping at a MATERIALIZE.

        A scan feeding a materialisation runs once however many correlated steps
        enclose it: SQLite derives the table, then re-scans the *materialised*
        result per outer row. Measured on the fixture below, the same query costs
        0.06 s materialised against a full re-scan inlined. Without this stop the
        guard refuses the very rewrite its own error message recommends -- which
        is what the control in tests/test_gpu_profile_query_guard.py caught.
        """
        seen: set[int] = set()
        cur = nodes.get(node_id, (0, ""))[0]
        while cur in nodes and cur not in seen:
            seen.add(cur)
            detail = nodes[cur][1]
            if detail.startswith("MATERIALIZE"):
                return
            yield detail
            cur = nodes[cur][0]

    hazards: list[tuple[str, int]] = []
    for node_id, (_parent, detail) in nodes.items():
        if not detail.startswith("SCAN "):
            continue
        name = detail.split()[1]
        if name not in profile.tables:
            continue
        if not any("CORRELATED" in a for a in ancestor_details(node_id)):
            continue
        rows = profile.query(f"SELECT COUNT(*) AS n FROM {name}")[0]["n"]
        if rows > NESTED_SCAN_ROW_THRESHOLD:
            hazards.append((name, rows))

    if not hazards:
        return None
    listed = "; ".join(f"{name} ({rows:,} rows)" for name, rows in sorted(hazards))
    hint = (
        "If the inner side is a CTE, SQLite has inlined it: declare it "
        "WITH <name> AS MATERIALIZED (...) so it is derived once. Otherwise invert "
        "the query so the small side is the outer one."
    )
    return (
        f"the plan re-scans {listed} once per outer row, inside a correlated "
        f"subquery, and no CUPTI table carries an index. " + hint
    )


def cmd_query(profile, args) -> dict:
    hazard = None if args.allow_nested_scan else _plan_hazard(profile, args.sql)
    if hazard is not None:
        raise SystemExit(
            f"error: refusing to run this query -- {hazard}\n"
            "  Re-run with --allow-nested-scan to execute it anyway; --max-seconds "
            "still applies."
        )
    deadline = args.max_seconds or None
    started = time.monotonic()
    try:
        rows = profile.query_safe(args.sql, row_limit=args.max_rows, deadline_s=deadline)
    except sqlite3.OperationalError as exc:
        if "interrupted" not in str(exc):
            raise
        raise SystemExit(
            f"error: query stopped at --max-seconds {args.max_seconds:g}. The row cap "
            "bounds output, not work -- check the plan rather than raising the cap."
        ) from exc
    return {
        "row_limit": args.max_rows,
        "row_count": len(rows),
        "truncated": len(rows) >= args.max_rows,
        "elapsed_s": round(time.monotonic() - started, 3),
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
        # `consensus_note` is the cause and `alignment_note` is its symptom: when
        # consensus is refused the per-rank phase counts necessarily differ, and
        # reporting only that reads as a tool limitation. The note carries the
        # margin -- observed once as "15.8% above optimal (threshold: 15%)", a
        # 0.8-point miss that --max-phases would have settled -- so a session that
        # sees only the symptom hand-rolls a comparison it did not need to.
        #
        # The per-rank overview is emitted rather than discarded. `align_phases`
        # is handed the very ProfileSummary objects it is built from, so refusing
        # the phase comparison is no reason to throw away the whole-profile one:
        # the alternative is a session re-running `summary` once per rank to
        # recover numbers this process already has. Measured on one four-rank
        # capture, that re-derivation cost ~47 s per rank after the refusal had
        # already spent ~190 s computing them.
        return {
            "cross_rank_available": False,
            "reason": alignment_note,
            "consensus_note": consensus_note,
            "selected_k_by_rank": {str(r): selected_ks[r] for r in sorted(selected_ks)},
            "rank_ids": sorted(summaries),
            "primary_rank_id": primary_rank_id,
            "primary_rank_reason": primary_reason,
            "per_rank_overview": _plain(compute_rank_overviews(summaries)),
            "caveats": [
                "Phase alignment was refused, so no per-phase comparison is available. "
                "The whole-profile figures below are the ones this run had already "
                "derived; they are reported rather than discarded.",
                "A whole-profile comparison is weaker than the per-phase one it stands "
                "in for. Imbalance confined to one phase can be cancelled by the "
                "opposite imbalance in another, so ranks that agree here are not "
                "thereby shown to be balanced -- read agreement as the absence of "
                "gross whole-run skew, nothing more.",
                "Forcing a common segmentation with --max-phases <k> may let the "
                "per-phase comparison proceed -- selected_k_by_rank and consensus_note "
                "say which k each rank chose and by how much consensus missed. It is "
                "not guaranteed: equalising k clears only the phase-count check, and a "
                "set whose phases then diverge in name and duration is refused again, "
                "which is a finding about the workloads rather than a tool limit.",
            ],
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



def cmd_host_samples(profile, args) -> dict:
    """Name what the host CPU was executing inside a window.

    `idle-attribution` sizes host time it cannot name (`residual`) and
    `window-breakdown` sizes the part of a window no traced activity covers. Both
    stop at an upper bound on an unnamed quantity, because the time is
    unattributed precisely when no traced call is in progress. Sampling is the
    only instrument in the capture that can say which code was running, and on one
    profile it named a 55 s stretch that every traced category reported as empty.
    """
    win = _window(args)
    return _plain(
        compute_host_samples(
            profile,
            start_ns=win[0] if win else None,
            end_ns=win[1] if win else None,
            top=args.top,
        )
    )


def cmd_window_breakdown(profile, args) -> dict:
    """Describe the window that lies outside the kernel span.

    `idle-attribution` reports how large that window is and cannot describe it:
    inter-kernel idle is empty before the first kernel, so every category
    intersected against it reads zero. This answers what is actually in there.
    """
    win = _window(args)
    breakdown = compute_window_breakdown(
        profile,
        start_ns=win[0] if win else None,
        end_ns=win[1] if win else None,
        bins=args.bins,
        top=args.top,
        region=args.region,
    )
    return _plain(breakdown)


def _render_table(payload: dict) -> str:
    lines = []
    for key, value in payload.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{key}:")
            cols = list(value[0].keys())
            lines.append("  " + " | ".join(cols))
            for row in value:
                lines.append("  " + " | ".join(str(row.get(c, "")) for c in cols))
        elif isinstance(value, list) and value:
            # Lists of scalars -- notably the idle-attribution caveats and the names of
            # categories the residual absorbs. Dropping these in table mode would hide
            # the warnings that stop an untraced category being read as a measured zero.
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        elif isinstance(value, dict):
            # Nested objects -- the transfer-overlap union, say. Before 2026-09-15
            # this branch did not exist and `--table` dropped them in silence, so a
            # section present in the JSON was absent from the output a session
            # actually reads. A renderer that hides a field is the same defect as a
            # tool that never computed it.
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        elif not isinstance(value, list):
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
    add("idle-attribution", cmd_idle_attribution, window=True)
    add("transfer-overlap", cmd_transfer_overlap, window=True)
    add("memcpy", cmd_memcpy, window=True)
    add("mpi", cmd_mpi, window=True)
    add("streams", cmd_streams, window=True)
    add("markers", cmd_markers, window=True, top=20)
    add("host-samples", cmd_host_samples, window=True, top=20)

    p = add("window-breakdown", cmd_window_breakdown, window=True, top=10)
    p.add_argument("--bins", type=int, default=8, help="time slices across the window")
    p.add_argument(
        "--region",
        choices=["head", "tail"],
        default="head",
        help="which side of the kernel span (ignored when --start-ns/--end-ns are given)",
    )

    p = sub.add_parser("cross-rank")
    p.add_argument("profiles", nargs="+", help="per-rank profiler databases")
    p.add_argument("--max-phases", type=int, default=8, help="phase cap (1 disables)")
    p.set_defaults(func=cmd_cross_rank, multi=True)

    add("launch-geometry", cmd_launch_geometry, top=15)

    p = add("schema", cmd_schema)
    # dest is `table_name`, not `table`: the top-level `--table` rendering flag owns
    # that dest, and a subparser sharing it silently overwrites the flag. metavar
    # keeps the documented command line unchanged.
    p.add_argument(
        "table_name", nargs="?", metavar="table",
        help="table to describe; omit to list tables",
    )

    p = add("query", cmd_query)
    p.add_argument("--sql", required=True, help="read-only SQL to execute")
    p.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_ROW_LIMIT,
        help="row cap -- bounds output, not work (default: %(default)s)",
    )
    p.add_argument(
        "--max-seconds",
        type=float,
        default=DEFAULT_QUERY_DEADLINE_S,
        help="wall-clock cap; 0 disables (default: %(default)g)",
    )
    p.add_argument(
        "--allow-nested-scan",
        action="store_true",
        help="run even when the plan re-scans a large table inside a correlated subquery",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for attr, default in (("start_ns", None), ("end_ns", None), ("top", 15), ("max_phases", 8),
                          ("bins", 8), ("region", "head")):
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
