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
