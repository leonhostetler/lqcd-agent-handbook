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

from ._utils import _normalize_demangled, busy_time_ns, interval_gaps_ns
from .models import (
    DeviceInfo,
    GapBucket,
    KernelSummary,
    MarkerRangeSummary,
    MemcpySummary,
    MpiOpSummary,
    PhaseSummary,
    ProfileSummary,
    StreamSummary,
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
