"""Vendor-neutral ingestion abstractions: Protocol, row types, capabilities."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

if TYPE_CHECKING:
    from .models import CaptureTimeBase, DeviceInfo


class MpiOpAgg(NamedTuple):
    """SQL-side aggregation of MPI calls by operation name."""

    op: str
    calls: int
    total_ns: int
    max_ns: int


class MarkerAgg(NamedTuple):
    """SQL-side aggregation of marker (NVTX/rocTX) ranges by name."""

    name: str
    calls: int
    total_ns: int


class Format(Enum):
    NSYS = "nsys"
    ROCPD = "rocpd"


@dataclass(frozen=True)
class ProfileCapabilities:
    """Feature flags derived from schema + data at open time."""

    has_kernels: bool
    has_memcpy: bool
    has_runtime_api: bool
    has_markers: bool
    has_mpi: bool
    has_cpu_samples: bool
    has_os_runtime: bool
    has_pmc_counters: bool
    has_sysmetrics: bool
    has_launch_geometry: bool
    #: Whether transfers record the *memory residency* of each end, not just a direction.
    #: One direction can hold two populations whose rates differ by orders of magnitude,
    #: and a per-direction row averages them into one unremarkable figure.
    has_transfer_residency: bool
    schema_version: str


@dataclass(slots=True)
class HostSampleAggregates:
    """Backend-side counts for one window: (name, module, samples) triples."""

    total_samples: int
    threads_sampled: int
    by_symbol: list[tuple[str, str | None, int]]
    by_module: list[tuple[str, int]]
    by_thread_state: list[tuple[str, int]]


@dataclass(slots=True)
class KernelRow:
    """One GPU kernel dispatch, normalised across both profile formats."""

    start_ns: int
    end_ns: int
    name: str
    short_name: str | None
    device_id: int | None
    stream_id: int | None
    duration_ns: int
    # Launch parameters. registers/shared memory are NsysProfile-only; the six
    # extents are populated by both backends when the capture records them, and are
    # None together when it does not -- see ProfileCapabilities.has_launch_geometry.
    registers_per_thread: int | None = None
    shared_mem_bytes: int | None = None
    total_threads: float | None = None  # grid (in blocks) × block (in threads)
    # **Normalised to the CUDA convention**: grid_* counts blocks/workgroups and
    # block_* counts threads per block, so total_threads is their product. rocpd
    # records grid_size_* in *work-items* rather than workgroups, and is divided
    # down on the way in; mapping it across raw would overstate each extent by the
    # workgroup size. See conventions/profile-metrics.md.
    grid_x: int | None = None
    grid_y: int | None = None
    grid_z: int | None = None
    block_x: int | None = None
    block_y: int | None = None
    block_z: int | None = None


@dataclass(slots=True)
class MemcpyRow:
    """One memory transfer, direction normalised to vendor-neutral vocabulary."""

    start_ns: int
    end_ns: int
    direction: str  # "Host-to-Device" | "Device-to-Host" | "Device-to-Device" | "Peer-to-Peer"
    bytes: int
    duration_ns: int
    #: Memory residency of each end, where the format records it: "Device", "Managed",
    #: "Pinned", "Pageable", ... ``None`` means the format carries no such column, which
    #: is not the same as the ends being ordinary device memory.
    src_kind: str | None = None
    dst_kind: str | None = None


@dataclass(slots=True)
class RangeRow:
    """One annotated time range (NVTX, rocTX, or MPI call)."""

    start_ns: int
    end_ns: int
    name: str
    category: str | None
    duration_ns: int


class Profile(Protocol):
    """Structural interface satisfied by NsysProfile and RocpdProfile.

    Analysis code should call only these methods; vendor-specific SQL is
    contained in the concrete implementations.
    """

    path: Path
    format: Format
    capabilities: ProfileCapabilities

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]: ...

    def query_safe(
        self,
        sql: str,
        stop_event: threading.Event | None = None,
        row_limit: int = 200,
        deadline_s: float | None = None,
    ) -> list[sqlite3.Row]: ...

    def explain_plan(self, sql: str) -> list[sqlite3.Row]: ...

    def columns(self, table: str) -> list[str]: ...

    def has_table(self, name: str) -> bool: ...

    def resolve_string(self, sid: int) -> str: ...

    def kernel_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[KernelRow]: ...

    def memcpy_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[MemcpyRow]: ...

    def marker_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]: ...

    def mpi_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]: ...

    def host_api_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]: ...

    def os_runtime_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]: ...

    def mpi_op_aggregates(
        self,
        *,
        start_ns: int | None = None,
        end_ns: int | None = None,
        limit: int = 10,
    ) -> list[MpiOpAgg]: ...

    def marker_aggregates(
        self,
        *,
        start_ns: int | None = None,
        end_ns: int | None = None,
        limit: int = 20,
    ) -> list[MarkerAgg]: ...

    def host_sample_aggregates(
        self,
        *,
        start_ns: int | None = None,
        end_ns: int | None = None,
        limit: int = 20,
    ) -> HostSampleAggregates | None:
        """Leaf-frame host samples grouped by symbol and module inside a window.

        Returns ``None`` when this format's sampling cannot be read, which is not
        the same as a window with no samples: the caller reports the two
        differently. Aggregated in the backend rather than returned as rows
        because a real capture carries millions of callchain entries -- 6.1M on
        one observed profile -- and materialising them to count them is the
        avoidable cost.
        """
        ...

    def mpi_event_ends_by_name(self, name: str) -> list[int]: ...

    def long_marker_ranges(self, *, min_duration_ns: int, limit: int = 200) -> list[RangeRow]: ...

    def device_info(self) -> DeviceInfo: ...

    def capture_time_base(self) -> CaptureTimeBase: ...

    def profile_bounds_ns(self) -> tuple[int, int]: ...

    def gpu_sync_time_s(self) -> float: ...

    def launch_overhead(self) -> dict[str, tuple[float, float]]: ...

    def cpu_sync_blocked_s(self, span_s: float) -> tuple[float | None, float | None]: ...

    def close(self) -> None: ...
