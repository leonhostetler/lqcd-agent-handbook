"""Pydantic data models for profile analysis output.

These models are the structured representation that the Claude agent reasons over.
All times are in seconds, all sizes in bytes unless noted.
"""

from __future__ import annotations

import re
from typing import Literal, get_args

from dataclasses import asdict, dataclass, field


@dataclass(kw_only=True)
class KernelSummary:
    name: str
    #: Short display name from StringIds (e.g. 'Kernel3D'); name holds the full normalized
    #: demangled name
    short_name: str | None = None
    calls: int
    total_s: float
    avg_ms: float
    min_ms: float
    max_ms: float
    #: Fraction of total GPU kernel time (0–100)
    pct_of_gpu_time: float
    std_dev_ms: float = 0.0
    #: Coefficient of variation (std_dev / avg); high value signals load imbalance or wavefront
    #: irregularity
    cv: float = 0.0
    avg_registers_per_thread: int = 0
    avg_shared_mem_bytes: int = 0
    #: How much of one full device wave the launch geometry fills (0–1): avg launch threads /
    #: (device units × max threads per unit), capped at 1.0. This is NOT occupancy: it ignores
    #: register and shared-memory limits, and any kernel launching more than one wave saturates at
    #: 1.0. A low value means the launch is too small to fill the device; a value of 1.0 says only
    #: that the grid is at least one wave, not that achieved occupancy is high.
    wave_fill_ratio: float | None = None
    #: Avg CPU-to-GPU enqueue latency in µs: time from launch API call on CPU to kernel start on
    #: GPU
    avg_launch_overhead_us: float | None = None
    #: Max CPU-to-GPU enqueue latency in µs across all launches of this kernel
    max_launch_overhead_us: float | None = None


@dataclass(kw_only=True)
class MemcpySummary:
    kind: str  # e.g. "Host-to-Device", "Peer-to-Peer"
    transfers: int
    total_bytes: int
    total_s: float
    effective_GBs: float
    #: Effective bandwidth as % of device peak (requires TARGET_INFO_GPU)
    pct_of_peak_bandwidth: float | None = None


@dataclass(kw_only=True)
class GapDetail:
    """One large GPU-idle gap, with what the host was doing inside it.

    A residual total says how much idle no traced category explains; its bucket
    histogram says whether that is diffuse per-launch overhead or a few structural
    stalls. Neither says what a structural stall *is*, and one histogram bucket can hold
    two unrelated mechanisms whose per-gap composition differs completely. Sampling a
    single gap is what separates them; sampling the enclosing phase averages them back
    together.
    """

    rank: int  # 1 = longest gap in the window
    start_ns: int
    end_ns: int
    duration_s: float
    #: Traced-category coverage of the gap, from the same accounting window-breakdown
    #: uses: annotation-only categories are excluded from covered_s.
    covered_s: float
    uncovered_s: float
    uncovered_pct: float
    #: Leading host-sample symbols inside the gap: (symbol, module, pct_of_samples).
    top_symbols: list[tuple[str, str | None, float]]
    samples: int
    threads_sampled: int


@dataclass(kw_only=True)
class GapDetails:
    """The largest GPU-idle gaps in a window, each named rather than only sized."""

    available: bool
    unavailable_reason: str | None
    window_s: float
    min_gap_s: float
    gaps_considered: int
    total_gap_s: float
    gaps: list[GapDetail]
    caveats: list[str]


@dataclass(kw_only=True)
class ResidencyRow:
    """One transfer direction split by the memory residency of each end.

    A direction is not one population. A device-to-device copy whose destination is
    managed memory that is not device-resident is served by page migration and can run
    orders of magnitude below a copy of the same direction and comparable volume whose
    ends are both ordinary device memory. Grouping by direction alone averages the two
    into a single unremarkable rate.
    """

    kind: str  # the transfer direction, e.g. "Device-to-Device"
    src_kind: str  # residency of the source end, e.g. "Device", "Managed"
    dst_kind: str  # residency of the destination end
    transfers: int
    total_bytes: int
    total_s: float
    effective_GBs: float


@dataclass(kw_only=True)
class TransferResidency:
    """Per-direction transfer rows split by end residency, with the rate-split check.

    ``rate_splits`` is the executed form of a discriminator that was previously prose:
    where one direction holds two residency populations whose effective rates differ by
    at least an order of magnitude, that difference is not contention and not clock
    behaviour, and the slow population is named rather than left for the reader to find.
    """

    available: bool
    unavailable_reason: str | None
    rows: list[ResidencyRow]
    rate_splits: list[str]
    caveats: list[str]


@dataclass(kw_only=True)
class MpiOpSummary:
    op: str  # e.g. "MPI_Barrier", "MPI_Allreduce"
    calls: int
    total_s: float
    avg_ms: float
    max_ms: float


@dataclass(kw_only=True)
class MarkerRangeSummary:
    name: str
    calls: int
    total_s: float
    avg_ms: float


@dataclass(kw_only=True)
class GapBucket:
    label: str  # e.g. "<10us", "1-10ms"
    count: int
    total_s: float


@dataclass(kw_only=True)
class IdleCategory:
    """One host-side category of GPU idle time.

    ``total_s`` is ``None``, never ``0.0``, when the capture cannot observe the
    category. The two are opposite facts — "measured, and it was zero" versus "not
    measured" — and collapsing them is how an untraced subsystem becomes a confident
    finding about the one that was traced.
    """

    name: str
    available: bool
    total_s: float | None
    pct_of_idle: float | None
    unavailable_reason: str | None = None


@dataclass(kw_only=True)
class WindowCategory:
    """One traced category's merged occupancy of a window.

    ``total_s`` is ``None``, never ``0.0``, when the capture cannot observe the
    category — the same distinction ``IdleCategory`` draws, for the same reason.
    Occupancy is merged, not summed: overlapping events of one category are one
    occupied interval, because a window is wall-clock and cannot hold more.
    """

    name: str
    available: bool
    total_s: float | None
    pct_of_window: float | None
    events: int | None
    unavailable_reason: str | None = None


@dataclass(kw_only=True)
class WindowEvent:
    """One named event kind inside the window, by merged occupancy."""

    name: str
    category: str
    total_s: float
    calls: int


@dataclass(kw_only=True)
class WindowBin:
    """Occupancy per category over one equal slice of the window.

    Bins answer *when* inside the window, which a single total cannot: a window
    half-covered throughout and one covered entirely in its first half report the
    same total and mean different things.
    """

    index: int
    start_ns: int
    end_ns: int
    by_category_s: dict[str, float]


@dataclass(kw_only=True)
class WindowBreakdown:
    """What traced activity occupies a window, by category, over time.

    This exists for the window that lies outside the kernel span — before the first
    kernel or after the last — which ``IdleAttribution`` reports the size of and
    cannot describe, because inter-kernel idle is empty there by construction.

    ``covered_s`` is the merged occupancy of the **activity** categories only — the
    ones naming what a thread was doing. Annotation-only categories are listed in
    ``categories`` and excluded from it; see ``_ANNOTATION_ONLY_CATEGORIES`` in
    ``metrics.py`` for why. So ``uncovered_s`` means "no traced activity accounts for
    this", which is the reading the playbook acts on, and not "no event overlaps it".
    """

    region: str
    start_ns: int
    end_ns: int
    window_s: float
    categories: list[WindowCategory]
    covered_s: float
    uncovered_s: float
    uncovered_pct: float
    top_events: list[WindowEvent] = field(default_factory=list)
    bins: list[WindowBin] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class IdleAttribution:
    """Inter-kernel GPU idle split into host-side categories, plus what is left.

    Categories are intersected against the merged idle set and against each other, so
    the parts never sum to more than the whole: a thread inside an MPI call that is
    itself inside a traced API call contributes its time once.

    Two identities hold, and only the second one closes the window. Within the idle
    set, ``accounted_s + residual_s == gpu_idle_s``. Across the window itself,
    ``kernel_busy_s + gpu_idle_s + outside_kernel_span_s == window_s``: idle is
    measured *between* kernels, so a window that is largely before the first kernel
    or after the last is mostly outside what the idle split describes, and
    ``outside_kernel_span_s`` is that part.
    """

    window_s: float
    kernel_busy_s: float
    gpu_idle_s: float
    outside_kernel_span_s: float
    categories: list[IdleCategory]
    accounted_s: float
    residual_s: float
    residual_pct_of_idle: float
    residual_absorbs: list[str]
    residual_buckets: list[GapBucket]
    caveats: list[str]


@dataclass(kw_only=True)
class TransferOverlap:
    """How much of one transfer direction's time is hidden behind kernel execution.

    ``exposed_s`` is the part that is not: the only part that lengthens the run.
    """

    direction: str
    transfers: int
    total_s: float
    overlapped_s: float
    exposed_s: float
    pct_overlapped: float


@dataclass(kw_only=True)
class GeometryRow:
    """One distinct launch geometry of one kernel, with how often it was launched."""

    grid: tuple[int, int, int]
    block: tuple[int, int, int]
    launches: int
    total_s: float
    mean_ms: float


@dataclass(kw_only=True)
class KernelGeometry:
    """Every distinct launch geometry recorded for one demangled kernel name.

    Two fields carry the autotune-warmth evidence and **neither is a verdict**, because
    the profile cannot support one.

    `max_block_x_at_one_problem_size` counts how many distinct `block.x` values share a
    single problem size. `Tunable::advanceBlockDim` steps `block.x` and derives `grid.x`
    from it, so a sweep moves block.x *while the problem size is fixed*; a kernel
    launched at several problem sizes has several block.x values legitimately, which is
    what the multi-blas kernels do on every run.

    `min_launches_per_geometry` is what separates the sweep from the ordinary case, and
    omitting it was the second wrong version of this field. A tuning candidate is
    launched once to warm up plus `candidate_iter()` times to be timed, so a sweep is
    **many geometries with a handful of launches each**. Two geometries with 72 and 24
    launches is two call sites, not a search — measured on a known-warm capture, where
    the first version of these fields flagged 25 of 153 kernels and the second 21.

    `block_y_varies` is deliberately reported separately and means something else.
    The y extent is not a free tuning parameter -- `TunableKernel2D/3D` raises
    `block.y` only while it is below `vector_length_y` -- so where `grid_y_always_one`
    holds, `block.y` *is* the kernel's y problem size and several values of it are
    several call sites, not a sweep. Reading that as a sweep, or as load imbalance,
    is the standard wrong turn.
    """

    name: str
    launches: int
    distinct_geometries: int
    distinct_problem_sizes: int
    max_block_x_at_one_problem_size: int
    min_launches_per_geometry: int
    block_x_values: list[int]
    block_y_values: list[int]
    block_y_varies: bool
    grid_y_always_one: bool
    geometries: list[GeometryRow]


@dataclass(kw_only=True)
class LaunchGeometry:
    """Launch geometry per kernel, or an explicit statement that it is unavailable.

    `available: False` is not the same as an empty table. A capture whose kernel
    table lacks the six extents supports no claim about launch geometry, and equally
    none that the geometry was uniform -- which is exactly the reading a silently
    empty result invites.
    """

    available: bool
    unavailable_reason: str | None
    kernels: list[KernelGeometry]
    caveats: list[str]


@dataclass(kw_only=True)
class HostSampleRow:
    """One leaf symbol (or module) and how many host samples landed in it."""

    name: str
    module: str | None
    samples: int
    pct_of_samples: float


@dataclass(kw_only=True)
class HostSampleState:
    """Thread state at sample time, counted."""

    state: str
    samples: int
    pct_of_samples: float


@dataclass(kw_only=True)
class HostSamples:
    """What the host CPU was executing inside a window, from periodic sampling.

    This answers the question no traced category can: `idle-attribution` reports
    host time it located but could not name as `residual`, and `window-breakdown`
    reports the part of a window no traced activity covers. Both size the unknown.
    Sampling is what names it.

    `samples` is a **count, never a duration**. See `caveats` on the instance and
    `conventions/profile-metrics.md`; the short version is that the count is of
    periodic thread samples across every sampled thread, attributed to the leaf
    frame only, and no seconds conversion is offered.
    """

    available: bool
    unavailable_reason: str | None
    start_ns: int
    end_ns: int
    window_s: float
    total_samples: int
    threads_sampled: int
    by_symbol: list[HostSampleRow]
    by_module: list[HostSampleRow]
    by_thread_state: list[HostSampleState]
    caveats: list[str]


@dataclass(kw_only=True)
class TransferUnion:
    """Exposed and overlapped transfer time across *all* directions at once.

    This exists because the per-direction rows above must not be added up.
    Transfers in different directions run concurrently -- a device-to-device copy
    and a unified-memory migration occupy the same nanosecond -- so summing the
    `exposed_s` column returns work rather than elapsed time, exactly the error
    `total_s` guards against *within* a direction. Measured on one capture the
    columns summed to 66.44 s where the union was 48.48 s, a 37% overstatement
    that reads as perfectly plausible.

    `directions_sum_exposed_s` is carried beside `exposed_s` so the gap is
    visible rather than merely avoided: a reader who was about to add the column
    can see what that would have produced.
    """

    transfers: int
    total_s: float
    overlapped_s: float
    exposed_s: float
    pct_overlapped: float
    directions_sum_exposed_s: float


@dataclass(kw_only=True)
class StreamSummary:
    stream_id: int
    kernel_calls: int
    total_gpu_s: float
    pct_of_gpu_time: float


@dataclass(kw_only=True)
class DeviceInfo:
    """Hardware and host properties extracted from the profile's metadata tables.

    Mostly device properties, plus the host the capture ran on — both come from
    profiler-written metadata and are read at the same point, so they share a
    carrier rather than warranting a second one.

    All fields are optional: they will be None if the metadata table is absent
    or the profile format does not expose a given property.
    """

    #: GPU vendor: 'nvidia' or 'amd'
    vendor: str | None = None
    #: Host the profile was captured on. For a multi-rank job this is what distinguishes an
    #: intra-node exchange from one crossing the network — a distinction that is otherwise not
    #: reliably inferable, since blocking MPI call durations reflect rank skew more than link
    #: bandwidth.
    hostname: str | None = None
    #: GPU device name (e.g., 'NVIDIA A100-SXM4-40GB' or 'AMD Instinct MI250X')
    name: str | None = None
    #: CUDA compute capability (NVIDIA only), e.g. '8.0'
    compute_capability: str | None = None
    #: Number of SMs (NVIDIA) or compute units / CUs (AMD)
    sm_count: int | None = None
    #: Max concurrent threads per SM or CU (maxWarpsPerSm × threadsPerWarp)
    max_threads_per_sm: int | None = None
    #: Peak HBM/DRAM bandwidth in GB/s
    peak_memory_bandwidth_GBs: float | None = None
    #: Total GPU memory in GiB
    total_memory_GiB: float | None = None
    #: L2 cache size in MiB
    l2_cache_MiB: float | None = None
    #: Maximum threads per block
    max_threads_per_block: int | None = None
    #: Maximum registers per block
    max_registers_per_block: int | None = None
    #: Standard shared memory limit per block in KiB
    max_shared_mem_per_block_KiB: float | None = None
    #: Opt-in (carveout) shared memory limit per block in KiB
    max_shared_mem_per_block_optin_KiB: float | None = None
    #: GPU clock rate in MHz
    clock_rate_MHz: float | None = None


@dataclass(kw_only=True)
class CaptureTimeBase:
    """What a profile's timestamps are relative to, and whether they can be
    correlated with application output after the fact.

    See conventions/profile-capture.md: a format carrying no wall-clock anchor
    cannot be aligned to stdout absolutely unless the capture recorded one.
    """

    #: 'session_relative' (timestamps offset from a recorded session start) or
    #: 'monotonic' (a clock with no recorded wall-clock origin).
    kind: str = "unknown"
    #: UTC epoch nanoseconds of the time origin; None when the file carries none.
    utc_epoch_ns: int | None = None
    #: Human-readable form of the same origin, when the file records one.
    utc_time: str | None = None
    #: Stated when no anchor is present, so the gap reads as a gap.
    note: str | None = None


@dataclass(kw_only=True)
class PhaseSummary:
    """Metrics for a single execution phase within a profile.

    Note: ``total_gpu_idle_s`` counts only gaps *between* kernel execution
    intervals within the phase window. Idle time before the first kernel or
    after the last kernel in the phase is not included — it contributes to the
    denominator of ``gpu_utilization_pct`` but not to ``total_gpu_idle_s``.

    Events straddling a phase boundary are attributed to every phase they
    overlap: time totals are clipped to the window (so per-phase times sum to
    the profile total), while the breakdown tables report unclipped per-event
    durations, which describe the event rather than the window.
    """

    name: str
    start_s: float  # seconds from profile start
    end_s: float
    duration_s: float
    start_ns: int  # absolute timestamp (nanoseconds); pass to windowed tools
    end_ns: int
    #: gpu_busy_s / duration_s * 100
    gpu_utilization_pct: float
    #: Sum of kernel durations; exceeds gpu_busy_s when kernels run concurrently
    gpu_kernel_s: float
    #: Wall-clock time with at least one kernel running (overlaps merged)
    gpu_busy_s: float = 0.0
    gpu_memcpy_s: float
    total_gpu_idle_s: float
    gap_histogram: list[GapBucket] = field(default_factory=list)
    top_kernels: list[KernelSummary]
    mpi_ops: list[MpiOpSummary] = field(default_factory=list)


@dataclass(kw_only=True)
class PhaseSegmentation:
    """Which segmentation produced a phase table.

    Phase boundaries are not a property of the capture; they are a property of the
    capture *and the cap the caller passed*. Two runs at different `--max-phases`
    return different windows, and a `--start-ns`/`--end-ns` pair lifted from one is
    silently meaningless against the other. Until 2026-09-15 no payload recorded the
    cap, so a phase figure quoted in a hypothesis record could not be reconciled
    against the run that produced it -- and `summary` and `phases` each emit a phase
    table, so holding two inconsistent ones took only a differing flag.
    """

    max_phases: int
    selected_k: int
    forced_k: int | None = None
    note: str | None = None


@dataclass(kw_only=True)
class ProfileSummary:
    """Top-level summary of a single GPU profile.

    This is the primary input to the hypothesis-generation agent.
    """

    # Source
    profile_path: str

    # Overall timing
    profile_span_s: float  # wall-clock duration captured in profile
    #: Total kernel work: the sum of individual kernel durations. Kernels running concurrently on
    #: different streams each contribute their full duration, so this can exceed profile_span_s.
    #: It is the denominator for per-kernel work shares.
    gpu_kernel_s: float
    #: Wall-clock time during which at least one kernel was executing, with overlapping kernels
    #: merged. Bounded by profile_span_s.
    gpu_busy_s: float = 0.0
    #: gpu_kernel_s / gpu_busy_s. 1.0 means kernels never overlapped; higher values indicate
    #: concurrent execution across streams (or devices sharing this profile).
    kernel_concurrency_factor: float | None = None
    gpu_memcpy_s: float  # total time spent in memory transfers
    gpu_sync_s: float  # total time in GPU sync operations
    #: gpu_busy_s / profile_span_s * 100
    gpu_utilization_pct: float

    # GPU idle
    total_gpu_idle_s: float  # sum of gaps between merged kernel execution intervals
    gap_histogram: list[GapBucket]

    # Breakdown tables
    top_kernels: list[KernelSummary]
    memcpy_by_kind: list[MemcpySummary]
    streams: list[StreamSummary]
    marker_ranges: list[MarkerRangeSummary] = field(default_factory=list)

    #: What the timestamps above are relative to.
    capture_time_base: CaptureTimeBase = field(default_factory=CaptureTimeBase)

    # GPU hardware info (absent in older or format-limited profiles)
    #: Hardware properties from device metadata; injected into the agent system prompt
    device_info: DeviceInfo = field(default_factory=DeviceInfo)
    #: Device peak memory bandwidth in GB/s
    peak_memory_bandwidth_GBs: float | None = None

    # CPU–GPU overlap (absent if runtime API tracing was not captured)
    #: Wall-clock time the host was blocked in GPU sync calls (*Synchronize). Concurrent calls
    #: across host threads are merged, not summed, so this is bounded by profile_span_s
    cpu_sync_blocked_s: float | None = None
    #: cpu_sync_blocked_s as a percentage of profile_span_s (0–100); a high value means the host
    #: spent much of the run stalled waiting on the GPU
    cpu_sync_blocked_pct: float | None = None

    # MPI (absent if profile has no MPI tables)
    mpi_ops: list[MpiOpSummary] = field(default_factory=list)
    mpi_present: bool = False
    phases: list[PhaseSummary] = field(default_factory=list)
    #: What produced `phases`. Quote it beside any per-phase figure; see PhaseSegmentation.
    phase_segmentation: PhaseSegmentation | None = None


# ---------------------------------------------------------------------------
# Multi-rank / cross-rank models
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class RankOverview:
    """Whole-profile stats for a single MPI rank."""

    rank_id: int
    #: Host this rank ran on; None if the profile omits it
    hostname: str | None = None
    gpu_kernel_s: float
    gpu_idle_s: float
    mpi_wait_s: float
    gpu_utilization_pct: float


@dataclass(kw_only=True)
class RankPhaseStats:
    """Per-phase stats for a single MPI rank."""

    rank_id: int
    gpu_kernel_s: float
    gpu_idle_s: float
    mpi_wait_s: float


@dataclass(kw_only=True)
class CollectiveImbalance:
    """Cross-rank imbalance metrics for a single MPI collective operation."""

    op: str
    #: (max - min) / mean across ranks; 0 = perfectly balanced
    imbalance_score: float
    slowest_rank_id: int
    mean_s: float
    min_s: float
    max_s: float


@dataclass(kw_only=True)
class CrossRankPhaseSummary:
    """Cross-rank metrics for a single execution phase."""

    phase_index: int
    phase_name: str
    # GPU kernel time stats across ranks
    gpu_kernel_mean_s: float
    gpu_kernel_std_s: float
    gpu_kernel_min_s: float
    gpu_kernel_max_s: float
    #: (max - min) / mean; 0 = perfectly balanced
    gpu_kernel_imbalance: float
    gpu_kernel_slowest_rank_id: int
    # MPI wait time stats across ranks
    mpi_wait_mean_s: float
    mpi_wait_std_s: float
    mpi_wait_min_s: float
    mpi_wait_max_s: float
    mpi_wait_imbalance: float
    mpi_wait_slowest_rank_id: int
    # Per-collective breakdown
    collective_imbalance: list[CollectiveImbalance] = field(default_factory=list)
    # Raw per-rank data (for agent reasoning about specific ranks)
    per_rank: list[RankPhaseStats] = field(default_factory=list)


@dataclass(kw_only=True)
class CrossRankSummary:
    """Cross-rank analysis summary for a multi-rank MPI job."""

    num_ranks: int
    rank_ids: list[int]
    primary_rank_id: int
    #: 'name_match' | 'index_order' — how phases were aligned across ranks
    phase_alignment: str
    per_rank_overview: list[RankOverview]
    phases: list[CrossRankPhaseSummary]

    # Derived node topology. Computed rather than left to the model: "are these
    # ranks co-located?" is a pure function of the hostname list, and the fix for
    # a host-staged exchange differs by the answer (peer access / IPC when the
    # GPUs share a node; GPU-Direct RDMA when the hop crosses the network).
    #: Distinct hosts across ranks; 1 means every rank is co-located. None when the profile format
    #: does not report hostnames.
    num_nodes: int | None = None
    #: hostname -> rank IDs running on it; empty when hostnames are unavailable
    ranks_per_node: dict[str, list[int]] = field(default_factory=dict)
    #: Whether every adjacent rank pair (r, r+1) shares a host. False means a ring/halo exchange
    #: crosses the network on every hop — the case --distribution=cyclic produces. None when
    #: hostnames are unavailable or there is only one rank.
    neighbor_ranks_colocated: bool | None = None


# ---------------------------------------------------------------------------
# Profile comparison models
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class ScalarDiff:
    a: float
    b: float
    #: (b-a)/a*100; None when a==0
    delta_pct: float | None = None


@dataclass(kw_only=True)
class KernelDiff:
    name: str
    short_name: str | None = None
    only_in_a: bool = False
    only_in_b: bool = False
    calls_a: int | None = None
    calls_b: int | None = None
    total_s_a: float | None = None
    total_s_b: float | None = None
    avg_ms_a: float | None = None
    avg_ms_b: float | None = None
    pct_gpu_time_a: float | None = None
    pct_gpu_time_b: float | None = None
    total_s_delta_pct: float | None = None


@dataclass(kw_only=True)
class MemcpyDiff:
    kind: str
    only_in_a: bool = False
    only_in_b: bool = False
    total_s_a: float | None = None
    total_s_b: float | None = None
    effective_GBs_a: float | None = None
    effective_GBs_b: float | None = None
    total_s_delta_pct: float | None = None


@dataclass(kw_only=True)
class MpiDiff:
    op: str
    only_in_a: bool = False
    only_in_b: bool = False
    calls_a: int | None = None
    calls_b: int | None = None
    total_s_a: float | None = None
    total_s_b: float | None = None
    avg_ms_a: float | None = None
    avg_ms_b: float | None = None
    total_s_delta_pct: float | None = None


@dataclass(kw_only=True)
class PhaseDiff:
    """Per-phase scalar diffs between two matched phases (phase_aware mode only)."""

    phase_name: str
    phase_index: int
    duration_s: ScalarDiff
    gpu_utilization_pct: ScalarDiff
    gpu_kernel_s: ScalarDiff
    gpu_memcpy_s: ScalarDiff
    total_gpu_idle_s: ScalarDiff


@dataclass(kw_only=True)
class ProfileDiff:
    """Structured comparison between two ProfileSummary objects."""

    profile_a_name: str
    profile_b_name: str
    #: 'phase_aware' | 'summary' | 'summary_no_kernel'
    comparison_mode: str
    phases_match: bool
    #: Jaccard similarity of kernel names (|intersection|/|union| * 100)
    kernel_overlap_pct: float
    # Top-level scalar diffs
    profile_span_s: ScalarDiff
    gpu_utilization_pct: ScalarDiff
    gpu_kernel_s: ScalarDiff
    gpu_memcpy_s: ScalarDiff
    gpu_sync_s: ScalarDiff
    total_gpu_idle_s: ScalarDiff
    # CPU–GPU overlap (None when cpu_sync_blocked_s is absent from both profiles)
    cpu_sync_blocked_s: ScalarDiff | None = None
    cpu_sync_blocked_pct: ScalarDiff | None = None
    # Stream topology
    stream_count_a: int = 0
    stream_count_b: int = 0
    dominant_stream_pct_a: float | None = None
    dominant_stream_pct_b: float | None = None
    # Per-entity diffs (kernel_diffs empty for summary_no_kernel mode)
    kernel_diffs: list[KernelDiff] = field(default_factory=list)
    memcpy_diffs: list[MemcpyDiff] = field(default_factory=list)
    mpi_diffs: list[MpiDiff] = field(default_factory=list)
    # Per-phase diffs (populated only in phase_aware mode)
    phase_diffs: list[PhaseDiff] = field(default_factory=list)


@dataclass(kw_only=True)
class ComparisonDiff:
    metric: str
    #: Phase this difference belongs to. Use the exact phase name from phase_diffs when the
    #: difference is scoped to a specific phase; use 'whole_profile' for top-level or cross-phase
    #: metrics.
    phase: str = "whole_profile"
    profile_a: str
    profile_b: str
    magnitude_pct: float | None = None
    note: str


@dataclass(kw_only=True)
class ComparisonReport:
    """LLM output schema for profile comparison."""

    narrative: str
    key_differences: list[ComparisonDiff] = field(default_factory=list)
