"""ROCm rocpd (rocprofv3 / rocprof-sys) SQLite profile reader.

rocpd schema_version=3: each session produces GUID-suffixed concrete tables
(``rocpd_kernel_dispatch_<guid>``) plus un-suffixed passthrough views
(``rocpd_kernel_dispatch = SELECT * FROM rocpd_kernel_dispatch_<guid>``) plus
convenience views (``kernels``, ``regions``, ``memory_copies``, …).

All queries here go through the un-suffixed views so they are GUID-agnostic.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .base import (
    Format,
    KernelRow,
    MarkerAgg,
    MemcpyRow,
    MpiOpAgg,
    ProfileCapabilities,
    RangeRow,
)

if TYPE_CHECKING:
    from .models import DeviceInfo

# Region categories that are NOT user markers, covering both rocprofv3 and rocprof-sys names.
#   rocprofv3:    HIP_RUNTIME_API_EXT, HIP_COMPILER_API_EXT, HSA_CORE_API, HSA_AMD_EXT_API
#   rocprof-sys:  rocm_hip_api, rocm_marker_api, rocm_hsa_api, timer_sampling, numa, pthread, host
#
# rocprof-sys records every HIP API call under *both* rocm_hip_api and rocm_marker_api; the
# latter must also be excluded or HIP function names (hipLaunchKernel etc.) leak into phase
# labels as if they were ROCTX user markers.
_ROCPD_API_CATEGORIES: frozenset[str] = frozenset(
    {
        # rocprofv3
        "HSA_CORE_API",
        "HSA_AMD_EXT_API",
        "HIP_RUNTIME_API_EXT",
        "HIP_COMPILER_API_EXT",
        # rocprof-sys
        "rocm_hip_api",
        "rocm_marker_api",
        "rocm_hsa_api",
        "timer_sampling",
        "numa",
        "pthread",
        "host",
    }
)

# MPI category names: rocprofv3 uses "MPI", rocprof-sys uses "mpi".
_ROCPD_MPI_CATEGORIES: frozenset[str] = frozenset({"MPI", "mpi"})

# Pre-built SQL IN-clause literals (constants, not user input — safe to interpolate).
_ROCPD_NON_MARKER_SQL = ",".join(
    f"'{c}'" for c in sorted(_ROCPD_API_CATEGORIES | _ROCPD_MPI_CATEGORIES)
)
_ROCPD_MPI_SQL = ",".join(f"'{c}'" for c in sorted(_ROCPD_MPI_CATEGORIES))


def _rocpd_short_name(display_name: str) -> str | None:
    """Extract a short base function name from a rocpd display_name for terminal display.

    E.g. "dslash_function<Dslash3D,int>" → "dslash_function"
         "void QUDA::dslashKernel<float>(int)" → "dslashKernel"
         "std::enable_if<...>::type quda::Kernel3D<...>" → "Kernel3D"
    Returns None when no shortening is possible (name is already bare).
    """
    name = display_name
    # Strip SFINAE return-type prefix used by QUDA/CUDA template kernels:
    # "std::enable_if<(device::use_kernel_arg<...>)(), void>::type quda::Kernel3D<...>"
    # Without this step, splitting on "::" picks the last segment deep inside the
    # template argument list (e.g. "quda::DDNo") rather than the actual kernel name.
    name = re.sub(r"^.*?void>::type\s+", "", name)
    # strip leading return type word (e.g. "void ")
    name = re.sub(r"^\s*\w+\s+", "", name)
    # strip template parameters and argument list BEFORE splitting on "::" so that
    # template arguments containing "::" (e.g. "quda::DDNo" inside <...>) are gone
    name = re.sub(r"[<(\[].*", "", name).strip()
    # take last :: segment (strip namespace prefix)
    if "::" in name:
        name = name.split("::")[-1].strip()
    return name if name and name != display_name else None


# Map rocpd direction strings to the same vocabulary used by Nsight Systems.
_MEMCPY_DIRECTION: dict[str, str] = {
    "MEMORY_COPY_DEVICE_TO_DEVICE": "Device-to-Device",
    "MEMORY_COPY_HOST_TO_DEVICE": "Host-to-Device",
    "MEMORY_COPY_DEVICE_TO_HOST": "Device-to-Host",
    "MEMORY_COPY_PEER_TO_PEER": "Peer-to-Peer",
}


@dataclass(frozen=True)
class RocpdEmptiness:
    """Diagnostics populated at open time; read by preflight to print actionable hints.

    Distinguishes "no data captured" (narrow flag set or SIGTERM-killed writer)
    from "feature not enabled" so preflight can emit precise remediation text.
    """

    empty_tables: frozenset[str]
    observed_categories: frozenset[str]
    writer_truncation_suspected: bool


class RocpdProfile:
    """Thin wrapper around a rocpd SQLite file written by rocprofv3 or rocprof-sys."""

    format: Format = Format.ROCPD

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Profile not found: {self.path}")
        try:
            self._conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            self._conn.execute("SELECT * FROM sqlite_master LIMIT 1")
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"Not a valid SQLite file: {self.path}") from exc
        self._conn.row_factory = sqlite3.Row
        try:
            file_size = self.path.stat().st_size
        except OSError:
            file_size = 64 * 1024 * 1024
        cache_kb = max(16 * 1024, min(file_size // (1024 * 4), 512 * 1024))
        # mmap: capped at 256 MB. A larger cap reduces cold-cache scan latency but
        # keeps file-backed pages resident, which combines badly with parallel
        # multi-rank analysis on memory-constrained hosts.
        mmap_size = min(file_size, 256 * 1024**2)
        self._conn.execute(f"PRAGMA cache_size = -{cache_kb}")
        self._conn.execute(f"PRAGMA mmap_size = {mmap_size}")
        self._tables: set[str] | None = None
        self._string_cache: dict[int, str] = {}
        self._capabilities: ProfileCapabilities | None = None
        self._emptiness: RocpdEmptiness | None = None
        self._schema_version: str = self._read_schema_version()
        self._kernel_events_cache: list | None = None
        self._memcpy_events_cache: list | None = None
        self._marker_ranges_cache: list | None = None
        self._mpi_ranges_cache: list | None = None

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    @property
    def tables(self) -> set[str]:
        """All table and view names; includes un-suffixed passthrough views."""
        if self._tables is None:
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
            self._tables = {r[0] for r in rows}
        return self._tables

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def columns(self, table: str) -> list[str]:
        """Return column names for table or view, or [] if absent."""
        if table not in self.tables:
            return []
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r["name"] for r in rows]

    def _read_schema_version(self) -> str:
        try:
            row = self._conn.execute(
                "SELECT value FROM rocpd_metadata WHERE tag = 'schema_version'"
            ).fetchone()
            return str(row[0]) if row else "unknown"
        except sqlite3.OperationalError:
            return "unknown"

    def _table_has_data(self, table: str) -> bool:
        """Return True only if the table/view exists AND contains at least one row."""
        return self.has_table(table) and bool(
            self._conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        )

    def _get_observed_categories(self) -> frozenset[str]:
        """Distinct category strings observed in rocpd_region for this file."""
        if not self.has_table("rocpd_region") or not self.has_table("rocpd_event"):
            return frozenset()
        try:
            rows = self._conn.execute("""
                SELECT DISTINCT RS.string
                FROM rocpd_region R
                INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
                INNER JOIN rocpd_string RS ON RS.id = E.category_id AND RS.guid = E.guid
                WHERE RS.string IS NOT NULL
            """).fetchall()
            return frozenset(r[0] for r in rows)
        except sqlite3.OperationalError:
            return frozenset()

    # ------------------------------------------------------------------
    # Capabilities and diagnostics
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> ProfileCapabilities:
        if self._capabilities is None:
            cats = self._get_observed_categories()
            self._capabilities = ProfileCapabilities(
                has_kernels=self._table_has_data("rocpd_kernel_dispatch"),
                has_memcpy=self._table_has_data("rocpd_memory_copy"),
                has_runtime_api=bool(cats & _ROCPD_API_CATEGORIES),
                has_markers=bool(cats - _ROCPD_API_CATEGORIES - _ROCPD_MPI_CATEGORIES),
                has_mpi=bool(cats & _ROCPD_MPI_CATEGORIES),
                has_cpu_samples=self._table_has_data("rocpd_sample"),
                has_pmc_counters=self._table_has_data("rocpd_pmc_event"),
                has_sysmetrics=False,
                schema_version=self._schema_version,
            )
        return self._capabilities

    @property
    def emptiness(self) -> RocpdEmptiness:
        if self._emptiness is None:
            self._emptiness = self._compute_emptiness()
        return self._emptiness

    def _compute_emptiness(self) -> RocpdEmptiness:
        _key_tables = ("rocpd_kernel_dispatch", "rocpd_memory_copy", "rocpd_memory_allocate")
        empty = frozenset(
            t
            for t in _key_tables
            if self.has_table(t) and not self._conn.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone()
        )
        cats = self._get_observed_categories()
        wal = self.path.with_suffix(self.path.suffix + "-wal")
        journal = self.path.with_suffix(self.path.suffix + "-journal")
        return RocpdEmptiness(
            empty_tables=empty,
            observed_categories=cats,
            writer_truncation_suspected=wal.exists() or journal.exists(),
        )

    # ------------------------------------------------------------------
    # String resolution
    # ------------------------------------------------------------------

    def resolve_string(self, sid: int) -> str:
        """Resolve a rocpd_string integer id to its text value."""
        if sid not in self._string_cache:
            row = self._conn.execute(
                "SELECT string FROM rocpd_string WHERE id = ?", (sid,)
            ).fetchone()
            self._string_cache[sid] = row[0] if row else f"<id:{sid}>"
        return self._string_cache[sid]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Execute SQL and return all rows.

        Returns [] when the query references a missing table or view.
        All other OperationalErrors are re-raised.
        """
        try:
            return self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            msg = str(exc)
            if "no such table" in msg or "no such column" in msg:
                return []
            raise

    def query_safe(
        self,
        sql: str,
        stop_event: threading.Event | None = None,
        row_limit: int = 200,
    ) -> list[sqlite3.Row]:
        """Execute SQL with interrupt support and a row cap (for LLM-originated queries)."""
        if stop_event is not None:

            def _progress() -> int:
                return 1 if stop_event.is_set() else 0

            self._conn.set_progress_handler(_progress, 1000)
        try:
            return self._conn.execute(sql).fetchmany(row_limit)
        finally:
            if stop_event is not None:
                self._conn.set_progress_handler(None, 0)

    # ------------------------------------------------------------------
    # Vendor-neutral event helpers
    # ------------------------------------------------------------------

    def kernel_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[KernelRow]:
        if where is None and limit is None:
            if self._kernel_events_cache is None:
                self._kernel_events_cache = self._fetch_kernel_events()
            return self._kernel_events_cache
        return self._fetch_kernel_events(where=where, limit=limit)

    def _fetch_kernel_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[KernelRow]:
        if not self.has_table("rocpd_kernel_dispatch"):
            return []
        where_clause = f"WHERE {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT K.start, K.end, S.display_name AS name,
                   JSON_EXTRACT(S.extdata, '$.truncated_kernel_name') AS truncated_name,
                   K.agent_id AS device_id, K.stream_id
            FROM rocpd_kernel_dispatch K
            INNER JOIN rocpd_info_kernel_symbol S
                ON S.id = K.kernel_id AND S.guid = K.guid
            {where_clause}
            {limit_clause}
        """)
        result = []
        for r in rows:
            full_name = r["name"] or ""
            tn = r["truncated_name"]
            if tn:
                tn = tn.removesuffix(".kd")
                short = tn if tn != full_name else None
            else:
                short = _rocpd_short_name(full_name)
            result.append(
                KernelRow(
                    start_ns=r["start"],
                    end_ns=r["end"],
                    name=full_name,
                    short_name=short,
                    device_id=r["device_id"],
                    stream_id=r["stream_id"],
                    duration_ns=r["end"] - r["start"],
                )
            )
        return result

    def memcpy_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[MemcpyRow]:
        if where is None and limit is None:
            if self._memcpy_events_cache is None:
                self._memcpy_events_cache = self._fetch_memcpy_events()
            return self._memcpy_events_cache
        return self._fetch_memcpy_events(where=where, limit=limit)

    def _fetch_memcpy_events(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[MemcpyRow]:
        if not self.has_table("rocpd_memory_copy"):
            return []
        where_clause = f"WHERE {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT M.start, M.end, S.string AS direction_raw, M.size AS bytes
            FROM rocpd_memory_copy M
            INNER JOIN rocpd_string S ON S.id = M.name_id AND S.guid = M.guid
            {where_clause}
            {limit_clause}
        """)
        return [
            MemcpyRow(
                start_ns=r["start"],
                end_ns=r["end"],
                direction=_MEMCPY_DIRECTION.get(
                    r["direction_raw"] or "", r["direction_raw"] or "Unknown"
                ),
                bytes=r["bytes"] or 0,
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    def marker_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        """Return user marker ranges (rocTX), excluding HIP/HSA API and MPI regions."""
        if where is None and limit is None:
            if self._marker_ranges_cache is None:
                self._marker_ranges_cache = self._fetch_marker_ranges()
            return self._marker_ranges_cache
        return self._fetch_marker_ranges(where=where, limit=limit)

    def _fetch_marker_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.capabilities.has_markers:
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT R.start, R.end, NS.string AS name, CS.string AS category
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string NOT IN ({_ROCPD_NON_MARKER_SQL})
            {and_clause}
            {limit_clause}
        """)
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"] or "",
                category=r["category"],
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    def mpi_ranges(self, *, where: str | None = None, limit: int | None = None) -> list[RangeRow]:
        """Return MPI call ranges (only present when captured via rocprof-sys)."""
        if where is None and limit is None:
            if self._mpi_ranges_cache is None:
                self._mpi_ranges_cache = self._fetch_mpi_ranges()
            return self._mpi_ranges_cache
        return self._fetch_mpi_ranges(where=where, limit=limit)

    def _fetch_mpi_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.capabilities.has_mpi:
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT R.start, R.end, NS.string AS name
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string IN ({_ROCPD_MPI_SQL})
            {and_clause}
            {limit_clause}
        """)
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"] or "",
                category="MPI",
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # SQL-side aggregations (avoid materialising whole tables in Python)
    # ------------------------------------------------------------------

    def mpi_op_aggregates(
        self,
        *,
        start_ns: int | None = None,
        end_ns: int | None = None,
        limit: int = 10,
    ) -> list[MpiOpAgg]:
        if not self.capabilities.has_mpi:
            return []
        # Select regions that *overlap* the window and clip to it rather than
        # requiring full containment, so a long collective straddling a phase
        # boundary does not vanish from both phases.
        window = ""
        dur = "(R.end - R.start)"
        params: tuple[Any, ...] = ()
        if start_ns is not None and end_ns is not None:
            window = "AND R.start < ? AND R.end > ?"
            dur = "(MIN(R.end, ?) - MAX(R.start, ?))"
            # Two placeholders per use of `dur` in the SELECT list (SUM then MAX),
            # followed by the WHERE predicate's pair.
            params = (end_ns, start_ns, end_ns, start_ns, end_ns, start_ns)
        rows = self._conn.execute(
            f"""
            SELECT NS.string AS name,
                   COUNT(*) AS calls,
                   SUM{dur} AS total_ns,
                   MAX{dur} AS max_ns
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string IN ({_ROCPD_MPI_SQL})
              AND R.end > R.start
              {window}
            GROUP BY NS.string
            ORDER BY total_ns DESC
            LIMIT ?
            """,
            params + (limit,),
        ).fetchall()
        return [
            MpiOpAgg(
                op=r["name"] or "",
                calls=int(r["calls"]),
                total_ns=int(r["total_ns"] or 0),
                max_ns=int(r["max_ns"] or 0),
            )
            for r in rows
        ]

    def marker_aggregates(
        self,
        *,
        start_ns: int | None = None,
        end_ns: int | None = None,
        limit: int = 20,
    ) -> list[MarkerAgg]:
        if not self.capabilities.has_markers:
            return []
        # Overlap + clip (see mpi_op_aggregates).
        window = ""
        dur = "(R.end - R.start)"
        params: tuple[Any, ...] = ()
        if start_ns is not None and end_ns is not None:
            window = "AND R.start < ? AND R.end > ?"
            dur = "(MIN(R.end, ?) - MAX(R.start, ?))"
            params = (end_ns, start_ns, end_ns, start_ns)
        rows = self._conn.execute(
            f"""
            SELECT NS.string AS name,
                   COUNT(*) AS calls,
                   SUM{dur} AS total_ns
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string NOT IN ({_ROCPD_NON_MARKER_SQL})
              AND R.end > R.start
              {window}
            GROUP BY NS.string
            ORDER BY total_ns DESC
            LIMIT ?
            """,
            params + (limit,),
        ).fetchall()
        return [
            MarkerAgg(
                name=r["name"] or "",
                calls=int(r["calls"]),
                total_ns=int(r["total_ns"] or 0),
            )
            for r in rows
        ]

    def mpi_event_ends_by_name(self, name: str) -> list[int]:
        """Return sorted end_ns timestamps for MPI events matching ``name`` exactly."""
        if not self.capabilities.has_mpi:
            return []
        rows = self._conn.execute(
            f"""
            SELECT R.end
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string IN ({_ROCPD_MPI_SQL})
              AND NS.string = ?
              AND R.end IS NOT NULL
            ORDER BY R.end
            """,
            (name,),
        ).fetchall()
        return [int(r[0]) for r in rows]

    def long_marker_ranges(self, *, min_duration_ns: int, limit: int = 200) -> list[RangeRow]:
        """Return the longest marker ranges with duration >= ``min_duration_ns``."""
        if not self.capabilities.has_markers:
            return []
        rows = self.query(
            f"""
            SELECT R.start, R.end, NS.string AS name, CS.string AS category
            FROM rocpd_region R
            INNER JOIN rocpd_event E ON E.id = R.event_id AND E.guid = R.guid
            INNER JOIN rocpd_string NS ON NS.id = R.name_id AND NS.guid = R.guid
            INNER JOIN rocpd_string CS ON CS.id = E.category_id AND CS.guid = E.guid
            WHERE CS.string NOT IN ({_ROCPD_NON_MARKER_SQL})
              AND R.end > R.start
              AND (R.end - R.start) >= {int(min_duration_ns)}
            ORDER BY (R.end - R.start) DESC
            LIMIT {int(limit)}
            """
        )
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"] or "",
                category=r["category"],
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Profile-level aggregate methods (vendor-neutral Protocol methods)
    # ------------------------------------------------------------------

    def profile_bounds_ns(self) -> tuple[int, int]:
        sources = []
        if self.has_table("rocpd_kernel_dispatch"):
            sources.append("SELECT start, end FROM rocpd_kernel_dispatch")
        if self.has_table("rocpd_memory_copy"):
            sources.append(
                "SELECT start, end FROM rocpd_memory_copy "
                "WHERE start IS NOT NULL AND end IS NOT NULL"
            )
        if self.has_table("rocpd_region"):
            sources.append(
                "SELECT start, end FROM rocpd_region "
                "WHERE start IS NOT NULL AND end IS NOT NULL AND end > start"
            )
        if not sources:
            return 0, 0
        union_sql = " UNION ALL ".join(sources)
        row = self._conn.execute(
            f"SELECT MIN(start) AS t0, MAX(end) AS t1 FROM ({union_sql})"
        ).fetchone()
        return int(row["t0"] or 0), int(row["t1"] or 0)

    def gpu_sync_time_s(self) -> float:
        return 0.0

    def launch_overhead(self) -> dict[str, tuple[float, float]]:
        return {}

    def cpu_sync_blocked_s(self, span_s: float) -> tuple[float | None, float | None]:
        return None, None

    def _hostname(self) -> str | None:
        """Capture host from rocpd_info_node, or None if unrecorded.

        See NsysProfile._hostname — same purpose, different metadata table.
        """
        if not self.has_table("rocpd_info_node"):
            return None
        rows = self.query("SELECT hostname FROM rocpd_info_node WHERE hostname IS NOT NULL LIMIT 1")
        if not rows:
            return None
        value = rows[0]["hostname"]
        return str(value) if value else None

    def device_info(self) -> DeviceInfo:
        """Return hardware info for the first GPU agent, plus the capture host.

        Maps AMD CUs → DeviceInfo.sm_count and max_waves_per_cu × wave_front_size
        → DeviceInfo.max_threads_per_sm so downstream analysis treats CUs the
        same as NVIDIA SMs for wave-fill estimation.
        """
        from .models import DeviceInfo  # lazy to avoid circular import

        hostname = self._hostname()
        if not self.has_table("rocpd_info_agent"):
            return DeviceInfo(hostname=hostname)
        rows = self.query("""
            SELECT product_name, model_name, vendor_name, type, extdata
            FROM rocpd_info_agent
            WHERE type = 'GPU'
            LIMIT 1
        """)
        if not rows:
            return DeviceInfo(hostname=hostname)
        r = rows[0]
        try:
            ext: dict = json.loads(r["extdata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            ext = {}

        def _int(k: str) -> int | None:
            v = ext.get(k)
            return int(v) if v is not None else None

        cu_count = _int("cu_count")
        wave_front_size = _int("wave_front_size") or 64
        max_waves_per_cu = _int("max_waves_per_cu")
        max_threads_per_cu = wave_front_size * max_waves_per_cu if max_waves_per_cu else None
        clock_mhz = _int("max_engine_clk_fcompute")

        # rocprof-sys leaves extdata={} — fall back to product_name/model_name from main columns.
        gpu_name = r["product_name"] or r["model_name"]
        return DeviceInfo(
            vendor="amd",
            hostname=hostname,
            name=gpu_name,
            compute_capability=None,
            sm_count=cu_count,
            max_threads_per_sm=max_threads_per_cu,
            peak_memory_bandwidth_GBs=None,
            total_memory_GiB=None,
            l2_cache_MiB=None,
            max_threads_per_block=None,
            max_registers_per_block=None,
            max_shared_mem_per_block_KiB=None,
            max_shared_mem_per_block_optin_KiB=None,
            clock_rate_MHz=float(clock_mhz) if clock_mhz else None,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> RocpdProfile:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"RocpdProfile({self.path.name!r})"
