"""Vendor-neutral ingestion abstractions: Protocol, row types, capabilities."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol

if TYPE_CHECKING:
    from .models import DeviceInfo


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
    has_pmc_counters: bool
    has_sysmetrics: bool
    schema_version: str


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
    # Launch-parameter stats populated only by NsysProfile (None for rocpd)
    registers_per_thread: int | None = None
    shared_mem_bytes: int | None = None
    total_threads: float | None = None  # gridX*gridY*gridZ × blockX*blockY*blockZ


@dataclass(slots=True)
class MemcpyRow:
    """One memory transfer, direction normalised to vendor-neutral vocabulary."""

    start_ns: int
    end_ns: int
    direction: str  # "Host-to-Device" | "Device-to-Host" | "Device-to-Device" | "Peer-to-Peer"
    bytes: int
    duration_ns: int


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
    ) -> list[sqlite3.Row]: ...

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

    def mpi_event_ends_by_name(self, name: str) -> list[int]: ...

    def long_marker_ranges(self, *, min_duration_ns: int, limit: int = 200) -> list[RangeRow]: ...

    def device_info(self) -> DeviceInfo: ...

    def profile_bounds_ns(self) -> tuple[int, int]: ...

    def gpu_sync_time_s(self) -> float: ...

    def launch_overhead(self) -> dict[str, tuple[float, float]]: ...

    def cpu_sync_blocked_s(self, span_s: float) -> tuple[float | None, float | None]: ...

    def close(self) -> None: ...
