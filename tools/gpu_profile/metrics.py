"""Compute structured metrics from a Profile.

Each function is a focused computation that returns data for one section of ProfileSummary.
All vendor-specific SQL is contained in the Profile implementations (NsysProfile, RocpdProfile).
Analysis functions are vendor-neutral: they call only Profile Protocol methods.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict

from .base import KernelRow, MarkerAgg, MemcpyRow, MpiOpAgg, Profile

from ._utils import (
    _normalize_demangled,
    busy_time_ns,
    intersect_duration_ns,
    interval_gaps_ns,
    merge_intervals,
    subtract_intervals,
)
from .models import (
    DeviceInfo,
    GapBucket,
    IdleAttribution,
    IdleCategory,
    KernelSummary,
    MarkerRangeSummary,
    MemcpySummary,
    MpiOpSummary,
    PhaseSummary,
    ProfileSummary,
    StreamSummary,
    GeometryRow,
    KernelGeometry,
    LaunchGeometry,
    TransferOverlap,
    TransferUnion,
    WindowBin,
    WindowBreakdown,
    WindowCategory,
    WindowEvent,
)
from .phases import (
    PhaseWindow,
    _PhaseState,
    compute_phase_state_and_cost_curve,
    detect_phases,
    finalize_phases_from_state,
)

# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------


def compute_profile_span(profile: Profile) -> float:
    """True wall-clock duration from first to last captured event."""
    t0, t1 = profile.profile_bounds_ns()
    return (t1 - t0) / 1e9 if t1 > t0 else 0.0


def compute_gpu_kernel_time(profile: Profile) -> float:
    """Total kernel *work*: the sum of individual kernel durations.

    Kernels executing concurrently on different streams each contribute their
    full duration, so this can exceed the wall-clock span. That is intentional —
    it is the correct denominator for per-kernel shares of total kernel work.
    Use ``compute_gpu_busy_time`` for anything wall-clock (e.g. utilization).
    """
    if not profile.capabilities.has_kernels:
        return 0.0
    return sum(e.duration_ns for e in profile.kernel_events()) / 1e9


def compute_gpu_busy_time(profile: Profile) -> float:
    """Wall-clock time during which at least one kernel was executing.

    Overlapping kernels are merged, so this is bounded by the profile span and
    is the correct numerator for GPU utilization.
    """
    if not profile.capabilities.has_kernels:
        return 0.0
    return busy_time_ns((e.start_ns, e.end_ns) for e in profile.kernel_events()) / 1e9


def compute_gpu_memcpy_time(profile: Profile) -> float:
    if not profile.capabilities.has_memcpy:
        return 0.0
    return sum(e.duration_ns for e in profile.memcpy_events()) / 1e9


def compute_gpu_sync_time(profile: Profile) -> float:
    return profile.gpu_sync_time_s()


def compute_cpu_sync_time(profile: Profile, span_s: float) -> tuple[float, float]:
    return profile.cpu_sync_blocked_s(span_s)


def _compute_launch_overhead(profile: Profile) -> dict[str, tuple[float, float]]:
    return profile.launch_overhead()


def compute_top_kernels(
    profile: Profile,
    limit: int = 15,
    device_info: DeviceInfo | None = None,
    launch_overhead: dict[str, tuple[float, float]] | None = None,
) -> list[KernelSummary]:
    if not profile.capabilities.has_kernels:
        return []
    total_gpu_s = compute_gpu_kernel_time(profile)
    evts = profile.kernel_events()
    return _aggregate_kernel_summaries(evts, total_gpu_s, limit, device_info, launch_overhead)


def _population_variance(values: list[int], mean: float) -> float:
    """Population variance via a two-pass sum of squared deviations.

    The previous form, ``sum(x*x)/n - mean**2``, subtracts two large nearly
    equal quantities. In ns units on long kernels the summands reach ~1e18 and
    the result loses several digits — enough that it could go negative, which
    was masked by a ``max(0.0, ...)`` clamp. Accumulating deviations from the
    mean keeps the summands small, so no clamp is needed and the result is
    non-negative by construction.

    Two-pass is used rather than Welford because the mean is already computed
    and the values are materialised; it is both simpler and more accurate.
    """
    n = len(values)
    if n < 2:
        return 0.0
    return sum((v - mean) ** 2 for v in values) / n


def _aggregate_kernel_summaries(
    evts: list[KernelRow],
    total_gpu_s: float,
    limit: int,
    device_info: DeviceInfo | None,
    launch_overhead: dict[str, tuple[float, float]] | None,
) -> list[KernelSummary]:
    groups: dict[str, list[KernelRow]] = defaultdict(list)
    for e in evts:
        groups[_normalize_demangled(e.name)].append(e)

    sm_count = device_info.sm_count if device_info else None
    max_threads_per_sm = device_info.max_threads_per_sm if device_info else None

    result: list[KernelSummary] = []
    for norm_name, grp in groups.items():
        n = len(grp)
        durations = [e.duration_ns for e in grp]
        total_ns = sum(durations)
        avg_ns = total_ns / n
        variance = _population_variance(durations, avg_ns)
        std_dev_ms = math.sqrt(variance) / 1e6
        avg_ms = avg_ns / 1e6
        cv = round(std_dev_ms / avg_ms, 3) if avg_ms > 0 else 0.0

        avg_registers = sum(e.registers_per_thread or 0 for e in grp) / n
        avg_shared = sum(e.shared_mem_bytes or 0 for e in grp) / n
        threads_vals = [e.total_threads for e in grp if e.total_threads is not None]
        avg_total_threads = sum(threads_vals) / len(threads_vals) if threads_vals else 0.0

        # Fraction of one full device wave the launch geometry fills. Deliberately
        # not called occupancy: it ignores register and shared-memory limits (the
        # usual occupancy limiters) and saturates at 1.0 for any multi-wave grid.
        # True occupancy would need the per-SM register file size and max blocks
        # per SM with compute-capability-specific allocation granularity, none of
        # which the profile's device metadata provides.
        wave_fill_ratio = None
        if sm_count and max_threads_per_sm and avg_total_threads > 0:
            wave_fill_ratio = round(
                min(1.0, avg_total_threads / (sm_count * max_threads_per_sm)), 3
            )

        short_name = grp[0].short_name
        short = short_name if short_name and short_name != norm_name else None
        oh = (launch_overhead or {}).get(norm_name)

        result.append(
            KernelSummary(
                name=norm_name,
                short_name=short,
                calls=n,
                total_s=round(total_ns / 1e9, 4),
                avg_ms=round(avg_ms, 4),
                min_ms=round(min(durations) / 1e6, 4),
                max_ms=round(max(durations) / 1e6, 4),
                pct_of_gpu_time=round(100.0 * total_ns / 1e9 / total_gpu_s, 1)
                if total_gpu_s
                else 0.0,
                std_dev_ms=round(std_dev_ms, 4),
                cv=cv,
                avg_registers_per_thread=int(round(avg_registers)),
                avg_shared_mem_bytes=int(round(avg_shared)),
                wave_fill_ratio=wave_fill_ratio,
                avg_launch_overhead_us=oh[0] if oh else None,
                max_launch_overhead_us=oh[1] if oh else None,
            )
        )

    result.sort(key=lambda k: k.total_s, reverse=True)
    return result[:limit]


def compute_memcpy_by_kind(
    profile: Profile,
    peak_bandwidth_GBs: float | None = None,
) -> list[MemcpySummary]:
    if not profile.capabilities.has_memcpy:
        return []
    evts = profile.memcpy_events()
    by_dir: dict[str, dict] = {}
    for e in evts:
        d = e.direction
        if d not in by_dir:
            by_dir[d] = {"count": 0, "total_ns": 0, "total_bytes": 0}
        by_dir[d]["count"] += 1
        by_dir[d]["total_ns"] += e.duration_ns
        by_dir[d]["total_bytes"] += e.bytes
    result = []
    for direction, s in by_dir.items():
        total_s = s["total_ns"] / 1e9
        eff_GBs = s["total_bytes"] / s["total_ns"] if s["total_ns"] > 0 else 0.0
        result.append(
            MemcpySummary(
                kind=direction,
                transfers=s["count"],
                total_bytes=s["total_bytes"],
                total_s=round(total_s, 4),
                effective_GBs=round(eff_GBs, 2),
                pct_of_peak_bandwidth=(
                    round(100.0 * eff_GBs / peak_bandwidth_GBs, 1)
                    if peak_bandwidth_GBs and eff_GBs > 0
                    else None
                ),
            )
        )
    result.sort(key=lambda m: m.total_s, reverse=True)
    return result


_GAP_BUCKET_EDGES_NS: list[tuple[str, float]] = [
    ("<10us", 10_000),
    ("10-100us", 100_000),
    ("100us-1ms", 1_000_000),
    ("1-10ms", 10_000_000),
    ("10-100ms", 100_000_000),
    (">100ms", math.inf),
]


def _bucket_gaps(gaps: list[int]) -> tuple[float, list[GapBucket]]:
    """Bucket idle gaps (ns) into the standard histogram.

    Returns (total_idle_s, non-empty buckets in ascending order).
    """
    buckets_raw: dict[str, list[int]] = {label: [] for label, _ in _GAP_BUCKET_EDGES_NS}
    for g in gaps:
        for label, upper in _GAP_BUCKET_EDGES_NS:
            if g < upper:
                buckets_raw[label].append(g)
                break
    # Rounded to microseconds, not milliseconds: the two smallest buckets span
    # sub-millisecond gaps and would otherwise always report total_s == 0.0.
    buckets = [
        GapBucket(label=label, count=len(vs), total_s=round(sum(vs) / 1e9, 6))
        for label, _ in _GAP_BUCKET_EDGES_NS
        for vs in [buckets_raw[label]]
        if vs
    ]
    return sum(b.total_s for b in buckets), buckets


def _kernel_gaps_ns(evts: list[KernelRow]) -> list[int]:
    """Idle gaps between kernels, computed from merged execution intervals.

    Merging first is essential: with concurrent streams the previous event in
    start order is not the one that finished last, so differencing against it
    invents gaps that never existed.
    """
    return interval_gaps_ns((e.start_ns, e.end_ns) for e in evts)


def compute_gap_histogram(profile: Profile) -> tuple[float, list[GapBucket]]:
    """Return (total_idle_s, gap_histogram) for GPU idle time between kernels."""
    if not profile.capabilities.has_kernels:
        return 0.0, []
    return _bucket_gaps(_kernel_gaps_ns(profile.kernel_events()))


# ---------------------------------------------------------------------------
# Idle attribution and transfer overlap
#
# Both answer questions ARCHITECTURE.md §profile-analysis requires the tool rather
# than the session to answer: they are interval algebra over hundreds of thousands
# of rows, where an ad-hoc version returns a plausible number and no reader can tell.
# Both reuse merge_intervals, so neither can drift from gpu_busy_s.
# ---------------------------------------------------------------------------

_RESIDUAL_CAVEAT = (
    "Residual is an upper bound on host compute: it also holds any host-side call the "
    "capture did not trace, including CUDA/HIP API calls skipped by the profiler."
)

# A window packed with kernels leaves a negligible remainder outside the kernel span;
# one that is mostly startup, teardown or a stall leaves most of itself there. Warn
# above this fraction, where the idle split stops describing the window it was given.
_OUTSIDE_SPAN_WARN_FRACTION = 0.10


def _clip(
    intervals: list[tuple[int, int]], start_ns: int, end_ns: int
) -> list[tuple[int, int]]:
    out = []
    for s, e in intervals:
        s, e = max(s, start_ns), min(e, end_ns)
        if e > s:
            out.append((s, e))
    return out


def _idle_intervals(
    evts: list[KernelRow], start_ns: int, end_ns: int
) -> tuple[list[tuple[int, int]], int]:
    """Merged inter-kernel gaps inside the window, and the merged busy time.

    Idle is measured *between* kernels, matching compute_gap_histogram: time before
    the first kernel and after the last is not idle, it is outside the work.
    """
    kernels = merge_intervals(
        _clip([(k.start_ns, k.end_ns) for k in evts], start_ns, end_ns)
    )
    busy = sum(e - s for s, e in kernels)
    gaps = [(kernels[i - 1][1], kernels[i][0]) for i in range(1, len(kernels))]
    return [g for g in gaps if g[1] > g[0]], busy


_WINDOW_BIN_DEFAULT = 8

# Categories that label a window rather than describe activity inside it.
#
# `mpi`, `host_api` and `os_runtime` each name what a thread was *doing*, so time they
# occupy is time the window is accounted for. A marker range names which annotated
# region the code was in, which is not the same claim: an outer range wrapping a whole
# run covers every window completely while explaining none of it. Folding markers into
# coverage therefore drives `uncovered_s` to ~0 on exactly the captures where the
# uncovered remainder is the finding. Measured on one 88.0 s startup window whose single
# enclosing range covered 87.286 s: reported 0.199 s uncovered (0.23%) where the traced
# activity categories in fact left 69.218 s (78.66%) unexplained, and that time was the
# run's largest bottleneck.
#
# Markers stay in `categories`, `top_events` and `bins` -- knowing which range a window
# falls in is useful. They are excluded only from the coverage arithmetic.
_ANNOTATION_ONLY_CATEGORIES = frozenset({"markers"})


def _kernel_span_ns(profile: Profile) -> tuple[int, int] | None:
    evts = profile.kernel_events()
    if not evts:
        return None
    return min(e.start_ns for e in evts), max(e.end_ns for e in evts)


def _named_sources(profile: Profile):
    """Traced categories that can occupy a window, with their availability reasons."""
    caps = profile.capabilities
    return [
        ("mpi", caps.has_mpi, "no MPI events in this capture",
         profile.mpi_ranges if caps.has_mpi else None),
        ("host_api", caps.has_runtime_api, "no GPU runtime/driver API events in this capture",
         profile.host_api_ranges if caps.has_runtime_api else None),
        ("os_runtime", caps.has_os_runtime, "no OS-runtime tracing in this capture",
         profile.os_runtime_ranges if caps.has_os_runtime else None),
        ("markers", caps.has_markers, "no marker annotations in this capture",
         profile.marker_ranges if caps.has_markers else None),
    ]


def compute_window_breakdown(
    profile: Profile,
    start_ns: int | None = None,
    end_ns: int | None = None,
    bins: int = _WINDOW_BIN_DEFAULT,
    top: int = 10,
    region: str = "head",
) -> WindowBreakdown:
    """Describe what traced activity occupies a window, by category and over time.

    ``compute_idle_attribution`` reports how much of a window lies outside the kernel
    span and cannot describe it: inter-kernel idle is empty there by construction, so
    every category intersected against it is zero. This answers the other half.

    The default region is the window before the first kernel, which is where that
    unaccounted time usually sits. Occupancy is merged per category, so a category
    can never exceed the window; categories are reported separately rather than
    summed, because one thread inside an MPI call inside a traced API call belongs to
    both and adding them would over-account.
    """
    bounds = profile.profile_bounds_ns()
    span = _kernel_span_ns(profile)
    if start_ns is not None and end_ns is not None:
        win_start, win_end, region = int(start_ns), int(end_ns), "custom"
    elif span is None:
        win_start, win_end, region = bounds[0], bounds[1], "whole_profile"
    elif region == "tail":
        win_start, win_end = span[1], bounds[1]
    else:
        win_start, win_end, region = bounds[0], span[0], "head"

    win_end = max(win_end, win_start)
    window_ns = win_end - win_start

    categories: list[WindowCategory] = []
    all_intervals: list[tuple[int, int]] = []
    named: dict[tuple[str, str], list[tuple[int, int]]] = {}

    for name, available, reason, accessor in _named_sources(profile):
        if not available or accessor is None:
            categories.append(
                WindowCategory(
                    name=name, available=False, total_s=None,
                    pct_of_window=None, events=None, unavailable_reason=reason,
                )
            )
            continue
        rows = [r for r in accessor() if r.end_ns > win_start and r.start_ns < win_end]
        clipped = _clip([(r.start_ns, r.end_ns) for r in rows], win_start, win_end)
        merged = merge_intervals(clipped)
        covered = sum(e - s for s, e in merged)
        categories.append(
            WindowCategory(
                name=name, available=True,
                total_s=round(covered / 1e9, 6),
                pct_of_window=round(100.0 * covered / window_ns, 2) if window_ns else 0.0,
                events=len(rows),
            )
        )
        if name not in _ANNOTATION_ONLY_CATEGORIES:
            all_intervals.extend(clipped)
        for r in rows:
            key = (r.name, name)
            named.setdefault(key, []).append(
                (max(r.start_ns, win_start), min(r.end_ns, win_end))
            )

    covered_ns = sum(e - s for s, e in merge_intervals(all_intervals))
    uncovered_ns = max(0, window_ns - covered_ns)

    top_events = sorted(
        (
            WindowEvent(
                name=n, category=c,
                total_s=round(sum(e - s for s, e in merge_intervals(iv)) / 1e9, 6),
                calls=len(iv),
            )
            for (n, c), iv in named.items()
        ),
        key=lambda e: e.total_s,
        reverse=True,
    )[:top]

    bin_rows: list[WindowBin] = []
    if bins > 0 and window_ns > 0:
        width = window_ns / bins
        for i in range(bins):
            b_start = win_start + int(i * width)
            b_end = win_start + int((i + 1) * width) if i < bins - 1 else win_end
            per: dict[str, float] = {}
            for name, available, _reason, accessor in _named_sources(profile):
                if not available or accessor is None:
                    continue
                iv = _clip(
                    [(r.start_ns, r.end_ns) for r in accessor()
                     if r.end_ns > b_start and r.start_ns < b_end],
                    b_start, b_end,
                )
                per[name] = round(sum(e - s for s, e in merge_intervals(iv)) / 1e9, 6)
            bin_rows.append(
                WindowBin(index=i, start_ns=b_start, end_ns=b_end, by_category_s=per)
            )

    caveats = [
        "Occupancy is merged per category and categories are not summed: an event "
        "inside another traced call belongs to both, so the parts may overlap.",
    ]
    annotated = [
        c.name for c in categories
        if c.available and c.name in _ANNOTATION_ONLY_CATEGORIES
    ]
    if annotated:
        caveats.append(
            "Coverage counts traced activity only; "
            + ", ".join(sorted(annotated))
            + " is reported beside it but excluded, because an annotation says which "
            "region the window falls in and not what occupied it. An enclosing range "
            "would otherwise report the window as fully covered while explaining none "
            "of it."
        )
    if any(not c.available for c in categories):
        caveats.append(
            "A category reported as unavailable was not traced. That is not the same "
            "as zero, and the uncovered remainder below may belong to it."
        )
    if window_ns == 0:
        caveats.append("This window has zero duration; nothing lies inside it.")

    return WindowBreakdown(
        region=region,
        start_ns=win_start,
        end_ns=win_end,
        window_s=round(window_ns / 1e9, 6),
        categories=categories,
        covered_s=round(covered_ns / 1e9, 6),
        uncovered_s=round(uncovered_ns / 1e9, 6),
        uncovered_pct=round(100.0 * uncovered_ns / window_ns, 2) if window_ns else 0.0,
        top_events=top_events,
        bins=bin_rows,
        caveats=caveats,
    )


def compute_idle_attribution(
    profile: Profile, start_ns: int | None = None, end_ns: int | None = None
) -> IdleAttribution:
    """Split inter-kernel GPU idle into MPI, host-API and OS-runtime time.

    Whatever none of them covers is the residual — host-side work the capture
    located in time but did not name.
    """
    bounds = profile.profile_bounds_ns()
    win_start = bounds[0] if start_ns is None else start_ns
    win_end = bounds[1] if end_ns is None else end_ns
    caps = profile.capabilities

    gaps, busy_ns = _idle_intervals(profile.kernel_events(), win_start, win_end)
    idle_ns = sum(e - s for s, e in gaps)
    # Idle is measured between kernels, so busy + idle spans only first-kernel-start to
    # last-kernel-end. Whatever the window holds outside that is not idle and is not
    # described by the split below; name it rather than leaving the window unaccounted.
    outside_ns = max(0, (win_end - win_start) - busy_ns - idle_ns)

    sources: list[tuple[str, bool, str, list[tuple[int, int]]]] = [
        (
            "mpi",
            caps.has_mpi,
            "no MPI events in this capture",
            [(r.start_ns, r.end_ns) for r in profile.mpi_ranges()] if caps.has_mpi else [],
        ),
        (
            "host_api",
            caps.has_runtime_api,
            "no GPU runtime/driver API events in this capture",
            [(r.start_ns, r.end_ns) for r in profile.host_api_ranges()]
            if caps.has_runtime_api
            else [],
        ),
        (
            "os_runtime",
            caps.has_os_runtime,
            "no OS-runtime tracing in this capture",
            [(r.start_ns, r.end_ns) for r in profile.os_runtime_ranges()]
            if caps.has_os_runtime
            else [],
        ),
    ]

    categories: list[IdleCategory] = []
    available_intervals: list[tuple[int, int]] = []
    absorbs: list[str] = []
    for name, available, reason, raw in sources:
        if not available:
            categories.append(
                IdleCategory(
                    name=name,
                    available=False,
                    total_s=None,
                    pct_of_idle=None,
                    unavailable_reason=reason,
                )
            )
            absorbs.append(name)
            continue
        clipped = _clip(raw, win_start, win_end)
        covered = intersect_duration_ns(gaps, clipped)
        categories.append(
            IdleCategory(
                name=name,
                available=True,
                total_s=round(covered / 1e9, 6),
                pct_of_idle=round(100.0 * covered / idle_ns, 2) if idle_ns else 0.0,
            )
        )
        available_intervals.extend(clipped)

    # Union first, then intersect: categories overlap each other (an MPI call on a
    # thread also inside a traced API call), and summing them would over-account.
    accounted_ns = intersect_duration_ns(gaps, available_intervals)
    residual_intervals = subtract_intervals(gaps, available_intervals)
    residual_ns = sum(e - s for s, e in residual_intervals)
    _, residual_buckets = _bucket_gaps([e - s for s, e in residual_intervals])

    caveats = [_RESIDUAL_CAVEAT]
    window_ns = win_end - win_start
    if window_ns and outside_ns / window_ns >= _OUTSIDE_SPAN_WARN_FRACTION:
        caveats.append(
            f"{outside_ns / 1e9:.3f} s of this {window_ns / 1e9:.3f} s window "
            f"({100.0 * outside_ns / window_ns:.1f}%) lies before the first kernel or "
            "after the last, where idle is not measured. The split below describes "
            "only the remainder, so it does not account for this window."
        )
    if absorbs:
        caveats.append(
            "Residual also absorbs "
            + ", ".join(absorbs)
            + ": those categories are untraced here, so their share is unknown rather "
            "than zero."
        )

    return IdleAttribution(
        window_s=round((win_end - win_start) / 1e9, 6),
        kernel_busy_s=round(busy_ns / 1e9, 6),
        gpu_idle_s=round(idle_ns / 1e9, 6),
        outside_kernel_span_s=round(outside_ns / 1e9, 6),
        categories=categories,
        accounted_s=round(accounted_ns / 1e9, 6),
        residual_s=round(residual_ns / 1e9, 6),
        residual_pct_of_idle=round(100.0 * residual_ns / idle_ns, 2) if idle_ns else 0.0,
        residual_absorbs=absorbs,
        residual_buckets=residual_buckets,
        caveats=caveats,
    )


def compute_transfer_overlap(
    profile: Profile, start_ns: int | None = None, end_ns: int | None = None
) -> list[TransferOverlap]:
    """Per-direction transfer time hidden behind kernels, and the part that is not.

    The question this exists for: a transfer class can be the largest by volume and
    cost nothing, because it ran while kernels ran. Volume alone cannot distinguish
    that from the opposite, and volume is what an ad-hoc query reaches for.
    """
    bounds = profile.profile_bounds_ns()
    win_start = bounds[0] if start_ns is None else start_ns
    win_end = bounds[1] if end_ns is None else end_ns

    kernels = merge_intervals(
        _clip(
            [(k.start_ns, k.end_ns) for k in profile.kernel_events()], win_start, win_end
        )
    )

    by_direction: dict[str, list[tuple[int, int]]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for m in profile.memcpy_events():
        s, e = max(m.start_ns, win_start), min(m.end_ns, win_end)
        if e <= s:
            continue
        by_direction[m.direction].append((s, e))
        counts[m.direction] += 1

    out: list[TransferOverlap] = []
    for direction, intervals in by_direction.items():
        # Merged, because transfers on different streams overlap in wall-clock and
        # the question is how much *time* is exposed, not how many bytes moved.
        merged = merge_intervals(intervals)
        total = sum(e - s for s, e in merged)
        overlapped = intersect_duration_ns(merged, kernels)
        out.append(
            TransferOverlap(
                direction=direction,
                transfers=counts[direction],
                total_s=round(total / 1e9, 6),
                overlapped_s=round(overlapped / 1e9, 6),
                exposed_s=round((total - overlapped) / 1e9, 6),
                pct_overlapped=round(100.0 * overlapped / total, 2) if total else 0.0,
            )
        )
    out.sort(key=lambda t: t.exposed_s, reverse=True)
    return out


def compute_transfer_union(
    profile: Profile, start_ns: int | None = None, end_ns: int | None = None
) -> TransferUnion | None:
    """Exposed transfer time across all directions, merged rather than summed.

    `compute_transfer_overlap` answers "does *this* class cost anything". This
    answers "how much of the window was spent moving data at all", and the two
    differ whenever directions overlap each other, which on a multi-stream run is
    always. Adding the per-direction column is the arithmetic this exists to make
    unnecessary; `directions_sum_exposed_s` reports what that sum would have been
    so the discrepancy is visible in the same output.

    Returns None when the capture records no transfers, so an absent measurement
    is not reported as zero.
    """
    bounds = profile.profile_bounds_ns()
    win_start = bounds[0] if start_ns is None else start_ns
    win_end = bounds[1] if end_ns is None else end_ns

    kernels = merge_intervals(
        _clip(
            [(k.start_ns, k.end_ns) for k in profile.kernel_events()], win_start, win_end
        )
    )

    intervals: list[tuple[int, int]] = []
    count = 0
    for m in profile.memcpy_events():
        s, e = max(m.start_ns, win_start), min(m.end_ns, win_end)
        if e <= s:
            continue
        intervals.append((s, e))
        count += 1
    if not intervals:
        return None

    merged = merge_intervals(intervals)
    total = sum(e - s for s, e in merged)
    overlapped = intersect_duration_ns(merged, kernels)
    per_direction = compute_transfer_overlap(profile, start_ns=start_ns, end_ns=end_ns)
    return TransferUnion(
        transfers=count,
        total_s=round(total / 1e9, 6),
        overlapped_s=round(overlapped / 1e9, 6),
        exposed_s=round((total - overlapped) / 1e9, 6),
        pct_overlapped=round(100.0 * overlapped / total, 2) if total else 0.0,
        directions_sum_exposed_s=round(sum(d.exposed_s for d in per_direction), 6),
    )


def _volume_groups(geometries: list[tuple]) -> list[list[tuple]]:
    """Cluster geometries that can share one tune key's problem size.

    QUDA derives the x grid from the x block: `advanceBlockDim` sets
    `grid.x = (minThreads + block.x - 1) / block.x` whenever the grid is not itself
    tuned. Inverting that, one launch bounds its own minThreads to
    `((grid.x - 1) * block.x, grid.x * block.x]`, and two launches can belong to the
    same tune key only if those bounds overlap *and* their y and z extents match.

    This is what separates a tuning sweep from ordinary variety. Without it, a kernel
    launched at several problem sizes -- which is normal, and is what the multi-blas
    kernels do on every run -- looks exactly like one being swept.
    """
    buckets: dict[tuple, list[tuple]] = defaultdict(list)
    for g in geometries:
        grid_x, grid_y, grid_z, block_x, block_y, block_z = g
        buckets[(grid_y * block_y, grid_z * block_z)].append(g)

    groups: list[list[tuple]] = []
    for members in buckets.values():
        spans = sorted(
            ((g[0] - 1) * g[3] + 1, g[0] * g[3], g) for g in members
        )
        current: list[tuple] = []
        current_hi = -1
        for lo, hi, g in spans:
            if current and lo <= current_hi:
                current.append(g)
                current_hi = min(current_hi, hi) if hi >= lo else current_hi
            else:
                if current:
                    groups.append(current)
                current, current_hi = [g], hi
        if current:
            groups.append(current)
    return groups


def compute_launch_geometry(
    profile: Profile, *, top: int = 15, max_geometries: int = 10
) -> LaunchGeometry:
    """Distinct launch geometries per kernel, for the autotune-warmth gate.

    `software/quda/profiling.md` makes establishing tunecache warmth mandatory before
    reading call counts, launch geometry or duration spread, because a cold cache
    inflates all three: every candidate in a tuning sweep is a real launch the
    profiler records. Until 2026-09-15 the extraction collapsed the six extents into
    `total_threads`, so the column that answers the question was not carried at all.

    **This supplies the evidence and does not return a verdict**, because the profile
    cannot carry one. A tune key is a functor, a problem size *and* an `aux` string
    holding the communication policy, the shared-memory carve-out and the multi-blas
    vector count; none of that is in a kernel name. So two launches that look like one
    key being swept may be two keys, and the only way to settle it is the tunecache
    the run wrote. The session applies the gate; the tool supplies the extents.
    """
    if not profile.capabilities.has_launch_geometry:
        return LaunchGeometry(
            available=False,
            unavailable_reason=(
                "this capture's kernel table does not record grid and block extents"
            ),
            kernels=[],
            caveats=[
                "Unavailable is not uniform: no claim about launch geometry, call "
                "counts or duration spread is supported by this capture, and none "
                "that the autotune cache was warm.",
            ],
        )

    by_name: dict[str, dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(list))
    for k in profile.kernel_events():
        extents = (k.grid_x, k.grid_y, k.grid_z, k.block_x, k.block_y, k.block_z)
        if any(e is None for e in extents):
            continue
        by_name[k.name][extents].append(k.duration_ns)

    kernels: list[KernelGeometry] = []
    for name, geometries in by_name.items():
        launches = sum(len(v) for v in geometries.values())
        groups = _volume_groups(list(geometries))
        rows = [
            GeometryRow(
                grid=(g[0], g[1], g[2]),
                block=(g[3], g[4], g[5]),
                launches=len(durations),
                total_s=round(sum(durations) / 1e9, 6),
                mean_ms=round(sum(durations) / len(durations) / 1e6, 4),
            )
            for g, durations in geometries.items()
        ]
        rows.sort(key=lambda r: r.launches, reverse=True)
        kernels.append(
            KernelGeometry(
                name=name,
                launches=launches,
                distinct_geometries=len(geometries),
                distinct_problem_sizes=len(groups),
                max_block_x_at_one_problem_size=max(
                    (len({m[3] for m in g}) for g in groups), default=0
                ),
                min_launches_per_geometry=min(len(v) for v in geometries.values()),
                block_x_values=sorted({g[3] for g in geometries}),
                block_y_values=sorted({g[4] for g in geometries}),
                block_y_varies=len({g[4] for g in geometries}) > 1,
                grid_y_always_one=all(g[1] == 1 for g in geometries),
                geometries=rows[:max_geometries],
            )
        )
    kernels.sort(
        key=lambda k: (k.max_block_x_at_one_problem_size, k.launches), reverse=True
    )

    flagged = [k for k in kernels if k.max_block_x_at_one_problem_size > 1]
    caveats = [
        "block.x is the dimension Tunable::advanceBlockDim steps, and grid.x is "
        "derived from it, so block.x moving *at one problem size* is the shape a "
        "tuning sweep leaves. Several problem sizes with one block.x each is ordinary "
        "variety and is reported as distinct_problem_sizes, not as a sweep.",
        "Read max_block_x_at_one_problem_size together with min_launches_per_geometry "
        "or it will mislead. A tuning candidate runs once to warm up plus "
        "candidate_iter() timed launches, so a sweep is many geometries with a handful "
        "of launches each; a few geometries with hundreds of launches each is call "
        "sites, whatever block.x does.",
        "block.y is not a free tuning parameter. Where grid_y_always_one holds, block.y "
        "is the kernel's y problem size, so several values are several call sites -- "
        "batch-size variation, not a sweep and not load imbalance.",
        "A flag here is consistent with a sweep and does not establish one. The tune "
        "key also carries an aux string -- communication policy, shared-memory "
        "carve-out, multi-blas vector count -- that no kernel name records, and two "
        "keys differing only there are indistinguishable in a profile. Settle warmth "
        "against the tunecache the run wrote.",
    ]
    if flagged:
        caveats.append(
            f"{len(flagged)} of {len(kernels)} kernels show more than one block.x at a "
            "single problem size; check their launch counts before reading any as a "
            "sweep."
        )
    else:
        caveats.append(
            "No kernel varies in block.x at a single problem size. That is consistent "
            "with a warm cache and does not establish one: a sweep before the capture "
            "window leaves no trace inside it."
        )
    return LaunchGeometry(
        available=True, unavailable_reason=None, kernels=kernels[:top], caveats=caveats
    )


def compute_streams(profile: Profile) -> list[StreamSummary]:
    if not profile.capabilities.has_kernels:
        return []
    total_gpu_s = compute_gpu_kernel_time(profile)
    by_stream: dict[int, dict] = {}
    for e in profile.kernel_events():
        sid = e.stream_id if e.stream_id is not None else -1
        if sid not in by_stream:
            by_stream[sid] = {"count": 0, "total_ns": 0}
        by_stream[sid]["count"] += 1
        by_stream[sid]["total_ns"] += e.duration_ns
    result = [
        StreamSummary(
            stream_id=sid,
            kernel_calls=s["count"],
            total_gpu_s=round(s["total_ns"] / 1e9, 4),
            pct_of_gpu_time=round(100.0 * s["total_ns"] / 1e9 / total_gpu_s, 1)
            if total_gpu_s
            else 0.0,
        )
        for sid, s in by_stream.items()
    ]
    result.sort(key=lambda x: x.total_gpu_s, reverse=True)
    return result


def _marker_aggs_to_summaries(aggs: list[MarkerAgg]) -> list[MarkerRangeSummary]:
    return [
        MarkerRangeSummary(
            name=a.name,
            calls=a.calls,
            total_s=round(a.total_ns / 1e9, 3),
            avg_ms=round(a.total_ns / a.calls / 1e6, 3) if a.calls else 0.0,
        )
        for a in aggs
    ]


def _mpi_aggs_to_summaries(aggs: list[MpiOpAgg]) -> list[MpiOpSummary]:
    return [
        MpiOpSummary(
            op=a.op,
            calls=a.calls,
            total_s=round(a.total_ns / 1e9, 3),
            avg_ms=round(a.total_ns / a.calls / 1e6, 3) if a.calls else 0.0,
            max_ms=round(a.max_ns / 1e6, 3),
        )
        for a in aggs
    ]


def compute_marker_ranges(profile: Profile, limit: int = 20) -> list[MarkerRangeSummary]:
    """Return aggregated marker ranges (NVTX or rocTX), sorted by total time."""
    if not profile.capabilities.has_markers:
        return []
    return _marker_aggs_to_summaries(profile.marker_aggregates(limit=limit))


def compute_device_info(profile: Profile) -> DeviceInfo:
    return profile.device_info()


def compute_mpi_ops(profile: Profile, limit: int = 10) -> list[MpiOpSummary]:
    if not profile.capabilities.has_mpi:
        return []
    return _mpi_aggs_to_summaries(profile.mpi_op_aggregates(limit=limit))


def _compute_all_mpi_stats(
    profile: Profile,
    phases: list[PhaseWindow],
    global_limit: int = 10,
    phase_limit: int = 5,
) -> tuple[list[MpiOpSummary], list[list[MpiOpSummary]]]:
    """Compute global and per-phase MPI stats via SQL-side aggregation.

    Issues N+1 GROUP BY queries (one global + one per phase) rather than
    materialising the full MPI event list in Python.  The per-phase queries
    use the same indexed scan as the global one with a windowing predicate.
    """
    if not profile.capabilities.has_mpi:
        return [], [[] for _ in phases]
    global_ops = _mpi_aggs_to_summaries(profile.mpi_op_aggregates(limit=global_limit))
    per_phase = [
        _mpi_aggs_to_summaries(
            profile.mpi_op_aggregates(start_ns=p.start_ns, end_ns=p.end_ns, limit=phase_limit)
        )
        for p in phases
    ]
    return global_ops, per_phase


# ---------------------------------------------------------------------------
# Per-phase metric helpers (operate on pre-cached event lists)
# ---------------------------------------------------------------------------


def _overlaps(event: KernelRow | MemcpyRow, start_ns: int, end_ns: int) -> bool:
    """True if the event intersects [start_ns, end_ns) at all.

    Used instead of full containment so events straddling a phase boundary are
    attributed to the phases they actually span rather than dropped from both.
    """
    return event.start_ns < end_ns and event.end_ns > start_ns


def _clipped_duration_ns(event: KernelRow | MemcpyRow, start_ns: int, end_ns: int) -> int:
    """Portion of the event's duration that falls inside the window."""
    return max(0, min(event.end_ns, end_ns) - max(event.start_ns, start_ns))


def _window_kernel_time(evts: list[KernelRow], start_ns: int, end_ns: int) -> float:
    """Kernel work within the window, with boundary-straddling kernels clipped.

    Clipping (rather than requiring containment) means per-phase times sum to
    the profile total instead of silently losing every event that crosses a
    phase boundary.
    """
    return sum(_clipped_duration_ns(e, start_ns, end_ns) for e in evts) / 1e9


def _window_memcpy_time(evts: list[MemcpyRow], start_ns: int, end_ns: int) -> float:
    return sum(_clipped_duration_ns(e, start_ns, end_ns) for e in evts) / 1e9


def _window_idle_time(
    evts: list[KernelRow], start_ns: int, end_ns: int
) -> tuple[float, list[GapBucket]]:
    """Return (total_idle_s, gap_histogram) for GPU idle gaps within a time window."""
    clipped = [
        (max(e.start_ns, start_ns), min(e.end_ns, end_ns))
        for e in evts
        if _overlaps(e, start_ns, end_ns)
    ]
    return _bucket_gaps(interval_gaps_ns(clipped))


def _window_busy_time(evts: list[KernelRow], start_ns: int, end_ns: int) -> float:
    """Wall-clock time within the window during which at least one kernel ran."""
    return (
        busy_time_ns(
            (max(e.start_ns, start_ns), min(e.end_ns, end_ns))
            for e in evts
            if _overlaps(e, start_ns, end_ns)
        )
        / 1e9
    )


def _window_top_kernels(
    evts: list[KernelRow],
    start_ns: int,
    end_ns: int,
    total_kernel_s: float,
    limit: int = 5,
    device_info: DeviceInfo | None = None,
    launch_overhead: dict[str, tuple[float, float]] | None = None,
) -> list[KernelSummary]:
    # Selected by overlap rather than containment so a kernel crossing a phase
    # boundary still appears. Per-kernel durations are reported unclipped (they
    # describe the kernel, not the window); kernels are orders of magnitude
    # shorter than phases, so the boundary effect on the table is negligible.
    window = [e for e in evts if _overlaps(e, start_ns, end_ns)]
    return _aggregate_kernel_summaries(window, total_kernel_s, limit, device_info, launch_overhead)


def _window_mpi_ops(
    profile: Profile, start_ns: int, end_ns: int, limit: int = 5
) -> list[MpiOpSummary]:
    return _mpi_aggs_to_summaries(
        profile.mpi_op_aggregates(start_ns=start_ns, end_ns=end_ns, limit=limit)
    )


def _window_memcpy_by_kind(
    evts: list[MemcpyRow],
    start_ns: int,
    end_ns: int,
    peak_bandwidth_GBs: float | None = None,
) -> list[MemcpySummary]:
    window = [e for e in evts if _overlaps(e, start_ns, end_ns)]
    by_dir: dict[str, dict] = {}
    for e in window:
        d = e.direction
        if d not in by_dir:
            by_dir[d] = {"count": 0, "total_ns": 0, "total_bytes": 0}
        by_dir[d]["count"] += 1
        by_dir[d]["total_ns"] += e.duration_ns
        by_dir[d]["total_bytes"] += e.bytes
    result = []
    for direction, s in by_dir.items():
        total_s = s["total_ns"] / 1e9
        eff_GBs = s["total_bytes"] / s["total_ns"] if s["total_ns"] > 0 else 0.0
        result.append(
            MemcpySummary(
                kind=direction,
                transfers=s["count"],
                total_bytes=s["total_bytes"],
                total_s=round(total_s, 4),
                effective_GBs=round(eff_GBs, 2),
                pct_of_peak_bandwidth=(
                    round(100.0 * eff_GBs / peak_bandwidth_GBs, 1)
                    if peak_bandwidth_GBs and eff_GBs > 0
                    else None
                ),
            )
        )
    result.sort(key=lambda m: m.total_s, reverse=True)
    return result


def _window_streams(evts: list[KernelRow], start_ns: int, end_ns: int) -> list[StreamSummary]:
    window = [e for e in evts if _overlaps(e, start_ns, end_ns)]
    total_ns = sum(e.duration_ns for e in window)
    by_stream: dict[int, dict] = {}
    for e in window:
        sid = e.stream_id if e.stream_id is not None else -1
        if sid not in by_stream:
            by_stream[sid] = {"count": 0, "total_ns": 0}
        by_stream[sid]["count"] += 1
        by_stream[sid]["total_ns"] += e.duration_ns
    result = [
        StreamSummary(
            stream_id=sid,
            kernel_calls=s["count"],
            total_gpu_s=round(s["total_ns"] / 1e9, 4),
            pct_of_gpu_time=round(100.0 * s["total_ns"] / total_ns, 1) if total_ns else 0.0,
        )
        for sid, s in by_stream.items()
    ]
    result.sort(key=lambda x: x.total_gpu_s, reverse=True)
    return result


def _window_marker_ranges(
    profile: Profile, start_ns: int, end_ns: int, limit: int = 20
) -> list[MarkerRangeSummary]:
    return _marker_aggs_to_summaries(
        profile.marker_aggregates(start_ns=start_ns, end_ns=end_ns, limit=limit)
    )


def compute_phase_summary(
    profile: Profile,
    phase: PhaseWindow,
    profile_start_ns: int,
    *,
    mpi_ops: list[MpiOpSummary] | None = None,
    device_info: DeviceInfo | None = None,
    launch_overhead: dict[str, tuple[float, float]] | None = None,
) -> PhaseSummary:
    """Compute full metrics for a single PhaseWindow.

    Pass ``mpi_ops`` to supply pre-computed MPI data (avoids an extra scan).
    Pass ``device_info`` (from compute_device_info) to enable wave-fill metrics.
    Pass ``launch_overhead`` (from profile.launch_overhead()) to annotate kernels.
    """
    all_kernel = profile.kernel_events()
    all_memcpy = profile.memcpy_events()

    kernel_s = _window_kernel_time(all_kernel, phase.start_ns, phase.end_ns)
    busy_s = _window_busy_time(all_kernel, phase.start_ns, phase.end_ns)
    memcpy_s = _window_memcpy_time(all_memcpy, phase.start_ns, phase.end_ns)
    idle_s, gap_histogram = _window_idle_time(all_kernel, phase.start_ns, phase.end_ns)
    duration_s = (phase.end_ns - phase.start_ns) / 1e9
    start_s = (phase.start_ns - profile_start_ns) / 1e9

    if mpi_ops is None:
        mpi_ops = _window_mpi_ops(profile, phase.start_ns, phase.end_ns)

    return PhaseSummary(
        name=phase.name,
        start_s=round(start_s, 3),
        end_s=round(start_s + duration_s, 3),
        duration_s=round(duration_s, 3),
        start_ns=phase.start_ns,
        end_ns=phase.end_ns,
        gpu_utilization_pct=round(100.0 * busy_s / duration_s, 1) if duration_s else 0.0,
        gpu_kernel_s=round(kernel_s, 3),
        gpu_busy_s=round(busy_s, 3),
        gpu_memcpy_s=round(memcpy_s, 3),
        total_gpu_idle_s=round(idle_s, 3),
        gap_histogram=gap_histogram,
        top_kernels=_window_top_kernels(
            all_kernel,
            phase.start_ns,
            phase.end_ns,
            kernel_s,
            device_info=device_info,
            launch_overhead=launch_overhead,
        ),
        mpi_ops=mpi_ops,
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def compute_profile_summary(
    profile: Profile,
    max_phases: int = 6,
    timings: dict[str, float] | None = None,
    verbose: bool = False,
    rank: int | None = None,
    forced_k: int | None = None,
    _phase_state: _PhaseState | None = None,
) -> ProfileSummary:
    """Compute all metrics for a profile and return a ProfileSummary.

    Set max_phases=1 to skip phase segmentation (returns a single phase).
    Pass a dict as ``timings`` to receive a breakdown:
    ``{"phase_detection_s": ..., "metrics_s": ...}``.
    Set forced_k to override the automatic elbow-based k selection in the DP
    segmentation step (used in multi-rank mode after cross-rank consensus).
    Pass ``_phase_state`` (from ``compute_profile_summary_and_state``) to skip
    re-fingerprinting: only the fast DP traceback + per-phase stats are re-run.
    """
    t_start = time.perf_counter()

    device_info = compute_device_info(profile)
    peak_bw = device_info.peak_memory_bandwidth_GBs

    span_s = compute_profile_span(profile)
    kernel_s = compute_gpu_kernel_time(profile)
    busy_s = compute_gpu_busy_time(profile)
    memcpy_s = compute_gpu_memcpy_time(profile)
    sync_s = compute_gpu_sync_time(profile)
    total_idle_s, gap_histogram = compute_gap_histogram(profile)
    loh = profile.launch_overhead()
    cpu_sync_s, cpu_sync_pct = profile.cpu_sync_blocked_s(span_s)

    t_phase = time.perf_counter()
    if _phase_state is not None:
        phases_windows = finalize_phases_from_state(
            _phase_state, max_phases=max_phases, forced_k=forced_k
        )
    else:
        phases_windows = detect_phases(
            profile, max_phases=max_phases, verbose=verbose, rank=rank, forced_k=forced_k
        )
    t_phase_done = time.perf_counter()

    profile_start_ns = phases_windows[0].start_ns if phases_windows else 0
    global_mpi_ops, all_phase_mpi = _compute_all_mpi_stats(profile, phases_windows)
    phase_summaries = [
        compute_phase_summary(
            profile,
            pw,
            profile_start_ns,
            mpi_ops=all_phase_mpi[i],
            device_info=device_info,
            launch_overhead=loh,
        )
        for i, pw in enumerate(phases_windows)
    ]

    if timings is not None:
        t_end = time.perf_counter()
        timings["phase_detection_s"] = t_phase_done - t_phase
        timings["metrics_s"] = (t_end - t_start) - (t_phase_done - t_phase)

    return ProfileSummary(
        capture_time_base=profile.capture_time_base(),
        profile_path=str(profile.path),
        device_info=device_info,
        profile_span_s=round(span_s, 3),
        gpu_kernel_s=round(kernel_s, 3),
        gpu_busy_s=round(busy_s, 3),
        kernel_concurrency_factor=round(kernel_s / busy_s, 2) if busy_s else None,
        gpu_memcpy_s=round(memcpy_s, 3),
        gpu_sync_s=round(sync_s, 3),
        gpu_utilization_pct=round(100.0 * busy_s / span_s, 1) if span_s else 0.0,
        total_gpu_idle_s=round(total_idle_s, 3),
        gap_histogram=gap_histogram,
        top_kernels=compute_top_kernels(profile, device_info=device_info, launch_overhead=loh),
        memcpy_by_kind=compute_memcpy_by_kind(profile, peak_bandwidth_GBs=peak_bw),
        streams=compute_streams(profile),
        marker_ranges=compute_marker_ranges(profile),
        mpi_ops=global_mpi_ops,
        mpi_present=profile.capabilities.has_mpi,
        phases=phase_summaries,
        peak_memory_bandwidth_GBs=peak_bw,
        cpu_sync_blocked_s=cpu_sync_s,
        cpu_sync_blocked_pct=cpu_sync_pct,
    )


def compute_profile_summary_and_state(
    profile: Profile,
    max_phases: int = 6,
    timings: dict[str, float] | None = None,
    verbose: bool = False,
    rank: int | None = None,
) -> tuple[ProfileSummary, _PhaseState | None, int, dict[int, float]]:
    """Compute all metrics in a single pass and also return the phase detection state.

    The returned ``_PhaseState`` can be passed to
    ``compute_profile_summary(..., _phase_state=state, forced_k=k)`` on a
    subsequent pass to skip re-fingerprinting: only the fast DP traceback and
    per-phase statistics are re-computed.  Used by the multi-rank path to run
    one disk read + one fingerprinting pass per rank instead of two.

    Returns ``(summary, state, selected_k, cost_curve)``.
    """
    t_start = time.perf_counter()

    device_info = compute_device_info(profile)
    peak_bw = device_info.peak_memory_bandwidth_GBs

    span_s = compute_profile_span(profile)
    kernel_s = compute_gpu_kernel_time(profile)
    busy_s = compute_gpu_busy_time(profile)
    memcpy_s = compute_gpu_memcpy_time(profile)
    sync_s = compute_gpu_sync_time(profile)
    total_idle_s, gap_histogram = compute_gap_histogram(profile)
    loh = profile.launch_overhead()
    cpu_sync_s, cpu_sync_pct = profile.cpu_sync_blocked_s(span_s)

    t_phase = time.perf_counter()
    state, selected_k, cost_curve = compute_phase_state_and_cost_curve(
        profile, max_phases=max_phases, rank=rank
    )
    phases_windows = finalize_phases_from_state(state, max_phases=max_phases, forced_k=None)
    t_phase_done = time.perf_counter()

    profile_start_ns = phases_windows[0].start_ns if phases_windows else 0
    global_mpi_ops, all_phase_mpi = _compute_all_mpi_stats(profile, phases_windows)
    phase_summaries = [
        compute_phase_summary(
            profile,
            pw,
            profile_start_ns,
            mpi_ops=all_phase_mpi[i],
            device_info=device_info,
            launch_overhead=loh,
        )
        for i, pw in enumerate(phases_windows)
    ]

    if timings is not None:
        t_end = time.perf_counter()
        timings["phase_detection_s"] = t_phase_done - t_phase
        timings["metrics_s"] = (t_end - t_start) - (t_phase_done - t_phase)

    summary = ProfileSummary(
        capture_time_base=profile.capture_time_base(),
        profile_path=str(profile.path),
        device_info=device_info,
        profile_span_s=round(span_s, 3),
        gpu_kernel_s=round(kernel_s, 3),
        gpu_busy_s=round(busy_s, 3),
        kernel_concurrency_factor=round(kernel_s / busy_s, 2) if busy_s else None,
        gpu_memcpy_s=round(memcpy_s, 3),
        gpu_sync_s=round(sync_s, 3),
        gpu_utilization_pct=round(100.0 * busy_s / span_s, 1) if span_s else 0.0,
        total_gpu_idle_s=round(total_idle_s, 3),
        gap_histogram=gap_histogram,
        top_kernels=compute_top_kernels(profile, device_info=device_info, launch_overhead=loh),
        memcpy_by_kind=compute_memcpy_by_kind(profile, peak_bandwidth_GBs=peak_bw),
        streams=compute_streams(profile),
        marker_ranges=compute_marker_ranges(profile),
        mpi_ops=global_mpi_ops,
        mpi_present=profile.capabilities.has_mpi,
        phases=phase_summaries,
        peak_memory_bandwidth_GBs=peak_bw,
        cpu_sync_blocked_s=cpu_sync_s,
        cpu_sync_blocked_pct=cpu_sync_pct,
    )
    return summary, state, selected_k, cost_curve
