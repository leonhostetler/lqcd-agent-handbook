"""Nsight Systems SQLite profile reader."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .base import (
    Format,
    KernelRow,
    MarkerAgg,
    MemcpyRow,
    MpiOpAgg,
    ProfileCapabilities,
    RangeRow,
)


class NsysProfile:
    """Thin wrapper around an Nsight Systems SQLite export.

    Handles string ID resolution, table presence detection, and raw queries.
    All name columns in CUPTI/NVTX tables are integer foreign keys into StringIds;
    use resolve_string() to get human-readable names.
    """

    format: Format = Format.NSYS

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
            file_size = 64 * 1024 * 1024  # fallback: 64 MB
        # Cache: up to 25% of file size, capped at 512 MB, minimum 16 MB
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
        self._kernel_events_cache: list | None = None
        self._memcpy_events_cache: list | None = None
        self._marker_ranges_cache: list | None = None
        self._host_api_ranges_cache: list | None = None
        self._os_runtime_ranges_cache: list | None = None
        self._mpi_ranges_cache: list | None = None
        self._launch_overhead_cache: dict[str, tuple[float, float]] | None = None

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    @property
    def tables(self) -> set[str]:
        if self._tables is None:
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            self._tables = {r[0] for r in rows}
        return self._tables

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def _table_has_data(self, table: str) -> bool:
        """Return True only if the table exists AND contains at least one row."""
        return self.has_table(table) and bool(
            self._conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        )

    def has_mpi(self) -> bool:
        return self.has_table("MPI_P2P_EVENTS") or self.has_table("MPI_COLLECTIVES_EVENTS")

    def has_nvtx(self) -> bool:
        return self.has_table("NVTX_EVENTS")

    def columns(self, table: str) -> list[str]:
        """Return column names for table, or [] if the table does not exist."""
        if table not in self.tables:
            return []
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r["name"] for r in rows]

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @property
    def capabilities(self) -> ProfileCapabilities:
        if self._capabilities is None:
            self._capabilities = ProfileCapabilities(
                has_kernels=self._table_has_data("CUPTI_ACTIVITY_KIND_KERNEL"),
                has_memcpy=self._table_has_data("CUPTI_ACTIVITY_KIND_MEMCPY"),
                has_runtime_api=self._table_has_data("CUPTI_ACTIVITY_KIND_RUNTIME"),
                has_markers=self._table_has_data("NVTX_EVENTS"),
                has_mpi=(
                    self._table_has_data("MPI_P2P_EVENTS")
                    or self._table_has_data("MPI_COLLECTIVES_EVENTS")
                ),
                has_cpu_samples=False,
                # OS attribution is only meaningful for GPU-driving threads, which are
                # identified from the runtime API table; without it the category is
                # unavailable rather than unfiltered.
                has_os_runtime=(
                    self._table_has_data("OSRT_API")
                    and self._table_has_data("CUPTI_ACTIVITY_KIND_RUNTIME")
                ),
                has_pmc_counters=self._table_has_data("CUPTI_ACTIVITY_KIND_METRIC"),
                has_sysmetrics=False,
                schema_version="nsys",
            )
        return self._capabilities

    # ------------------------------------------------------------------
    # String ID resolution
    # ------------------------------------------------------------------

    def resolve_string(self, string_id: int) -> str:
        """Resolve an integer StringIds foreign key to its text value."""
        if string_id not in self._string_cache:
            row = self._conn.execute(
                "SELECT value FROM StringIds WHERE id = ?", (string_id,)
            ).fetchone()
            self._string_cache[string_id] = row[0] if row else f"<id:{string_id}>"
        return self._string_cache[string_id]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Execute a SQL query and return all rows.

        No row limit is applied here — internal analysis callers are trusted to
        include appropriate SQL LIMIT clauses.  LLM-instigated queries must go
        through query_safe(), which enforces its own row cap.

        Returns [] if the query references a table that does not exist in this
        profile (e.g. CUPTI_ACTIVITY_KIND_KERNEL in a kernel-less MPI profile).
        All other OperationalErrors are re-raised.
        """
        try:
            cursor = self._conn.execute(sql, params)
            return cursor.fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                return []
            raise

    def query_safe(
        self,
        sql: str,
        stop_event: threading.Event | None = None,
        row_limit: int = 200,
        deadline_s: float | None = None,
    ) -> list[sqlite3.Row]:
        """Execute a SQL query under a row limit and a wall-clock deadline.

        Installs a SQLite progress handler that fires every 1000 VM instructions
        and aborts when stop_event is set or deadline_s has elapsed; SQLite then
        raises OperationalError('interrupted'), which propagates to the caller.

        **The row limit does not bound work.** fetchmany(row_limit) bounds what
        Python materialises, and nothing more: an aggregate returns one row and
        must still evaluate the whole plan. The deadline is the only bound on
        cost here, which is why it defaults to a value rather than to None at
        the CLI. Neither guard fires without being asked for -- before
        2026-09-15 the caller passed no stop_event, so a query that ran away had
        to be killed as a process.
        """
        deadline = None if deadline_s is None else time.monotonic() + deadline_s
        guarded = stop_event is not None or deadline is not None
        if guarded:

            def _progress() -> int:
                if stop_event is not None and stop_event.is_set():
                    return 1
                if deadline is not None and time.monotonic() > deadline:
                    return 1
                return 0

            self._conn.set_progress_handler(_progress, 1000)
        try:
            cursor = self._conn.execute(sql)
            return cursor.fetchmany(row_limit)
        finally:
            if guarded:
                self._conn.set_progress_handler(None, 0)

    def explain_plan(self, sql: str) -> list[sqlite3.Row]:
        """Return SQLite's query plan for `sql` without executing it.

        Planning is free -- milliseconds against the hours a bad plan costs --
        so the cost of a query is predictable before it is paid. See
        `_plan_hazard` in gpu-profile-summary.py for what is read out of it.
        """
        return self._conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()

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
        if not self.has_table("CUPTI_ACTIVITY_KIND_KERNEL"):
            return []
        kernel_cols = set(self.columns("CUPTI_ACTIVITY_KIND_KERNEL"))
        has_demangled = "demangledName" in kernel_cols
        demangled_join = (
            "LEFT JOIN StringIds sd ON k.demangledName = sd.id" if has_demangled else ""
        )
        name_expr = "COALESCE(sd.value, s.value)" if has_demangled else "s.value"
        has_dims = all(
            c in kernel_cols for c in ("gridX", "gridY", "gridZ", "blockX", "blockY", "blockZ")
        )
        dims_expr = (
            "CAST(k.gridX*k.gridY*k.gridZ*k.blockX*k.blockY*k.blockZ AS REAL)"
            if has_dims
            else "NULL"
        )
        has_regs = "registersPerThread" in kernel_cols
        regs_expr = "COALESCE(k.registersPerThread, 0)" if has_regs else "0"
        has_shmem = "sharedMemoryExecuted" in kernel_cols or "staticSharedMemory" in kernel_cols
        shmem_expr = (
            "COALESCE(k.sharedMemoryExecuted, k.staticSharedMemory + k.dynamicSharedMemory, 0)"
            if has_shmem
            else "0"
        )
        where_clause = f"WHERE {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT k.start, k.end, {name_expr} AS name, s.value AS short_name,
                   k.streamId AS stream_id,
                   {regs_expr} AS reg_per_thread,
                   {shmem_expr} AS shared_mem,
                   {dims_expr} AS total_threads
            FROM CUPTI_ACTIVITY_KIND_KERNEL k
            JOIN StringIds s ON k.shortName = s.id
            {demangled_join}
            {where_clause}
            {limit_clause}
        """)
        return [
            KernelRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"] or "",
                short_name=r["short_name"] if r["short_name"] != (r["name"] or "") else None,
                device_id=None,
                stream_id=r["stream_id"],
                duration_ns=r["end"] - r["start"],
                registers_per_thread=int(r["reg_per_thread"])
                if r["reg_per_thread"] is not None
                else None,
                shared_mem_bytes=int(r["shared_mem"]) if r["shared_mem"] is not None else None,
                total_threads=float(r["total_threads"]) if r["total_threads"] is not None else None,
            )
            for r in rows
        ]

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
        if not self.has_table("CUPTI_ACTIVITY_KIND_MEMCPY"):
            return []
        where_clause = f"WHERE {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT m.start, m.end, e.label AS direction, m.bytes
            FROM CUPTI_ACTIVITY_KIND_MEMCPY m
            JOIN ENUM_CUDA_MEMCPY_OPER e ON m.copyKind = e.id
            {where_clause}
            {limit_clause}
        """)
        return [
            MemcpyRow(
                start_ns=r["start"],
                end_ns=r["end"],
                direction=r["direction"] or "Unknown",
                bytes=r["bytes"] or 0,
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    def marker_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if where is None and limit is None:
            if self._marker_ranges_cache is None:
                self._marker_ranges_cache = self._fetch_marker_ranges()
            return self._marker_ranges_cache
        return self._fetch_marker_ranges(where=where, limit=limit)

    def _fetch_marker_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.has_nvtx():
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT start, end, text AS name
            FROM NVTX_EVENTS
            WHERE eventType = 59
              AND end IS NOT NULL
              AND end > start
              AND text IS NOT NULL
              {and_clause}
            {limit_clause}
        """)
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"],
                category="NVTX",
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    def mpi_ranges(self, *, where: str | None = None, limit: int | None = None) -> list[RangeRow]:
        if where is None and limit is None:
            if self._mpi_ranges_cache is None:
                self._mpi_ranges_cache = self._fetch_mpi_ranges()
            return self._mpi_ranges_cache
        return self._fetch_mpi_ranges(where=where, limit=limit)

    def _fetch_mpi_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.has_mpi():
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        ranges: list[RangeRow] = []
        for table in ("MPI_COLLECTIVES_EVENTS", "MPI_P2P_EVENTS", "MPI_START_WAIT_EVENTS"):
            if not self.has_table(table):
                continue
            rows = self.query(f"""
                SELECT e.start, e.end, s.value AS name
                FROM {table} e
                JOIN StringIds s ON e.textId = s.id
                WHERE e.end IS NOT NULL
                  {and_clause}
                ORDER BY e.start
                {limit_clause}
            """)
            ranges.extend(
                RangeRow(
                    start_ns=r["start"],
                    end_ns=r["end"],
                    name=r["name"],
                    category="MPI",
                    duration_ns=r["end"] - r["start"],
                )
                for r in rows
            )
        return ranges

    def host_api_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        """CUDA runtime/driver API calls on the host.

        These bound host time the GPU is waiting on, so they are one category of
        idle attribution. Nsight Systems may omit cheap calls when the capture set
        ``CUDA_SKIP_SOME_API_CALLS``; anything it omits lands in the residual, which
        is why the residual is documented as an upper bound rather than a
        measurement of application compute.
        """
        if where is None and limit is None:
            if self._host_api_ranges_cache is None:
                self._host_api_ranges_cache = self._fetch_host_api_ranges()
            return self._host_api_ranges_cache
        return self._fetch_host_api_ranges(where=where, limit=limit)

    def _fetch_host_api_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.capabilities.has_runtime_api:
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT r.start, r.end, s.value AS name
            FROM CUPTI_ACTIVITY_KIND_RUNTIME r
            JOIN StringIds s ON r.nameId = s.id
            WHERE r.end IS NOT NULL
              {and_clause}
            ORDER BY r.start
            {limit_clause}
        """)
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"],
                category="CUDA_API",
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    def os_runtime_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        """OS-level calls (``poll``, ``futex``, ``ioctl``, ...) from ``-t osrt``.

        **Restricted to threads that drive the GPU.** ``-t osrt`` records every thread,
        and a communication progress thread sits in ``poll``/``futex`` for essentially
        the whole run; unfiltered, that covers every idle gap and reports the
        application as blocked in the OS ~100% of the time. Measured on a real
        MILC/QUDA capture the unfiltered figure was 18.691 s of 18.691 s of idle
        against 0.389 s for the thread actually issuing the launches — a number that
        is both wrong and confident, which is the failure mode this tool exists to
        remove rather than automate.

        "Drives the GPU" is defined as appearing in the CUDA runtime API table, so a
        capture without API tracing yields no OS attribution rather than an
        unfiltered one.
        """
        if where is None and limit is None:
            if self._os_runtime_ranges_cache is None:
                self._os_runtime_ranges_cache = self._fetch_os_runtime_ranges()
            return self._os_runtime_ranges_cache
        return self._fetch_os_runtime_ranges(where=where, limit=limit)

    def _fetch_os_runtime_ranges(
        self, *, where: str | None = None, limit: int | None = None
    ) -> list[RangeRow]:
        if not self.capabilities.has_os_runtime or not self.capabilities.has_runtime_api:
            return []
        and_clause = f"AND {where}" if where else ""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self.query(f"""
            SELECT o.start, o.end, s.value AS name
            FROM OSRT_API o
            JOIN StringIds s ON o.nameId = s.id
            WHERE o.end IS NOT NULL
              AND o.globalTid IN (
                  SELECT DISTINCT globalTid FROM CUPTI_ACTIVITY_KIND_RUNTIME
              )
              {and_clause}
            ORDER BY o.start
            {limit_clause}
        """)
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"],
                category="OS_RUNTIME",
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
        if not self.has_mpi():
            return []
        # Select events that *overlap* the window and clip their duration to it,
        # rather than requiring full containment. A long collective straddling a
        # phase boundary would otherwise vanish from both phases entirely.
        window = ""
        dur_expr = "(e.end - e.start)"
        params: tuple[Any, ...] = ()
        if start_ns is not None and end_ns is not None:
            window = "AND e.start < ? AND e.end > ?"
            dur_expr = "(MIN(e.end, ?) - MAX(e.start, ?))"
            # Order must match the placeholders as they appear in the SQL text:
            # dur_expr comes first (SELECT list), then the WHERE predicate.
            params = (end_ns, start_ns, end_ns, start_ns)
        sub_selects: list[str] = []
        for table in ("MPI_COLLECTIVES_EVENTS", "MPI_P2P_EVENTS", "MPI_START_WAIT_EVENTS"):
            if not self.has_table(table):
                continue
            sub_selects.append(
                f"SELECT s.value AS name, {dur_expr} AS dur "
                f"FROM {table} e JOIN StringIds s ON e.textId = s.id "
                f"WHERE e.end IS NOT NULL AND e.end > e.start {window}"
            )
        if not sub_selects:
            return []
        union_sql = " UNION ALL ".join(sub_selects)
        # Each sub-select carries its own window predicate, so params repeat per sub-select.
        full_params: tuple[Any, ...] = params * len(sub_selects)
        rows = self._conn.execute(
            f"SELECT name, COUNT(*) AS calls, SUM(dur) AS total_ns, MAX(dur) AS max_ns "
            f"FROM ({union_sql}) "
            f"GROUP BY name "
            f"ORDER BY total_ns DESC "
            f"LIMIT ?",
            full_params + (limit,),
        ).fetchall()
        return [
            MpiOpAgg(
                op=r["name"],
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
        if not self.has_nvtx():
            return []
        # Overlap + clip (see mpi_op_aggregates): a marker range spanning a phase
        # boundary must contribute its in-window portion to each phase it covers.
        window = ""
        total_expr = "SUM(end - start)"
        params: tuple[Any, ...] = ()
        if start_ns is not None and end_ns is not None:
            window = "AND start < ? AND end > ?"
            total_expr = "SUM(MIN(end, ?) - MAX(start, ?))"
            params = (end_ns, start_ns, end_ns, start_ns)
        rows = self._conn.execute(
            f"SELECT text AS name, COUNT(*) AS calls, {total_expr} AS total_ns "
            f"FROM NVTX_EVENTS "
            f"WHERE eventType = 59 "
            f"  AND end IS NOT NULL "
            f"  AND end > start "
            f"  AND text IS NOT NULL "
            f"  {window} "
            f"GROUP BY text "
            f"ORDER BY total_ns DESC "
            f"LIMIT ?",
            params + (limit,),
        ).fetchall()
        return [
            MarkerAgg(name=r["name"], calls=int(r["calls"]), total_ns=int(r["total_ns"] or 0))
            for r in rows
        ]

    def mpi_event_ends_by_name(self, name: str) -> list[int]:
        """Return sorted end_ns timestamps for MPI events matching ``name`` exactly.

        Used by phase-boundary detection (e.g. MPI_Barrier clusters).  Pulls only
        the end column for matching events — orders of magnitude less memory than
        materialising all mpi_ranges() when only one event class is of interest.
        """
        if not self.has_mpi():
            return []
        ends: list[int] = []
        for table in ("MPI_COLLECTIVES_EVENTS", "MPI_P2P_EVENTS", "MPI_START_WAIT_EVENTS"):
            if not self.has_table(table):
                continue
            rows = self._conn.execute(
                f"SELECT e.end FROM {table} e "
                f"JOIN StringIds s ON e.textId = s.id "
                f"WHERE e.end IS NOT NULL AND s.value = ?",
                (name,),
            ).fetchall()
            ends.extend(int(r[0]) for r in rows)
        ends.sort()
        return ends

    def long_marker_ranges(self, *, min_duration_ns: int, limit: int = 200) -> list[RangeRow]:
        """Return the longest marker ranges with duration >= ``min_duration_ns``.

        Phase-boundary detection only needs long markers; pushing the duration
        filter into SQL keeps the result set bounded regardless of profile size.
        """
        if not self.has_nvtx():
            return []
        rows = self.query(
            f"SELECT start, end, text AS name "
            f"FROM NVTX_EVENTS "
            f"WHERE eventType = 59 "
            f"  AND end IS NOT NULL "
            f"  AND end > start "
            f"  AND text IS NOT NULL "
            f"  AND (end - start) >= {int(min_duration_ns)} "
            f"ORDER BY (end - start) DESC "
            f"LIMIT {int(limit)}"
        )
        return [
            RangeRow(
                start_ns=r["start"],
                end_ns=r["end"],
                name=r["name"],
                category="NVTX",
                duration_ns=r["end"] - r["start"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Profile-level aggregate methods (vendor-neutral Protocol methods)
    # ------------------------------------------------------------------

    def profile_bounds_ns(self) -> tuple[int, int]:
        sources = []
        if self.has_table("CUPTI_ACTIVITY_KIND_KERNEL"):
            sources.append("SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL")
        if self.has_table("CUPTI_ACTIVITY_KIND_MEMCPY"):
            sources.append("SELECT start, end FROM CUPTI_ACTIVITY_KIND_MEMCPY")
        if self.has_table("CUPTI_ACTIVITY_KIND_RUNTIME"):
            sources.append(
                "SELECT start, end FROM CUPTI_ACTIVITY_KIND_RUNTIME "
                "WHERE start IS NOT NULL AND end IS NOT NULL"
            )
        if self.has_nvtx():
            sources.append(
                "SELECT start, end FROM NVTX_EVENTS "
                "WHERE start IS NOT NULL AND end IS NOT NULL AND end > start"
            )
        if self.has_table("OSRT_API"):
            sources.append(
                "SELECT start, end FROM OSRT_API WHERE start IS NOT NULL AND end IS NOT NULL"
            )
        for tbl in ("MPI_OTHER_EVENTS", "MPI_COLLECTIVES_EVENTS", "MPI_P2P_EVENTS"):
            if self.has_table(tbl):
                sources.append(
                    f"SELECT start, end FROM {tbl} WHERE start IS NOT NULL AND end IS NOT NULL"
                )
        if not sources:
            return 0, 0
        union_sql = " UNION ALL ".join(sources)
        row = self._conn.execute(
            f"SELECT MIN(start) AS t0, MAX(end) AS t1 FROM ({union_sql})"
        ).fetchone()
        return int(row["t0"] or 0), int(row["t1"] or 0)

    def gpu_sync_time_s(self) -> float:
        if not self.has_table("CUPTI_ACTIVITY_KIND_SYNCHRONIZATION"):
            return 0.0
        row = self._conn.execute(
            "SELECT COALESCE(SUM(end - start), 0) / 1e9 AS t "
            "FROM CUPTI_ACTIVITY_KIND_SYNCHRONIZATION"
        ).fetchone()
        return float(row["t"] or 0.0)

    def launch_overhead(self) -> dict[str, tuple[float, float]]:
        """Return {kernel_name: (avg_launch_us, max_launch_us)} via correlationId join.

        Measures CPU-to-GPU enqueue latency: the time from when the CPU issued the
        launch API call to when the kernel actually started executing on the GPU.
        Returns an empty dict if RUNTIME is absent or lacks correlationId.

        Cached: this is a join over the full kernel and runtime tables, and the
        agent's tools call it on every top_kernels / phase_summary invocation.
        """
        if self._launch_overhead_cache is None:
            self._launch_overhead_cache = self._fetch_launch_overhead()
        return self._launch_overhead_cache

    def _fetch_launch_overhead(self) -> dict[str, tuple[float, float]]:
        if not self.has_table("CUPTI_ACTIVITY_KIND_RUNTIME"):
            return {}
        runtime_cols = set(self.columns("CUPTI_ACTIVITY_KIND_RUNTIME"))
        kernel_cols_set = set(self.columns("CUPTI_ACTIVITY_KIND_KERNEL"))
        if "correlationId" not in runtime_cols or "correlationId" not in kernel_cols_set:
            return {}
        has_demangled = "demangledName" in kernel_cols_set
        demangled_join = (
            "LEFT JOIN StringIds sd ON k.demangledName = sd.id" if has_demangled else ""
        )
        name_expr = "COALESCE(sd.value, s.value)" if has_demangled else "s.value"
        group_expr = "COALESCE(k.demangledName, k.shortName)" if has_demangled else "k.shortName"
        rows = self.query(f"""
            SELECT
                {name_expr}                                              AS name,
                COUNT(*)                                                 AS launches,
                AVG(CAST(k.start - rt.start AS REAL)) / 1000.0         AS avg_launch_us,
                MAX(k.start - rt.start) / 1000.0                        AS max_launch_us
            FROM CUPTI_ACTIVITY_KIND_KERNEL k
            JOIN CUPTI_ACTIVITY_KIND_RUNTIME rt ON k.correlationId = rt.correlationId
            JOIN StringIds s ON k.shortName = s.id
            {demangled_join}
            WHERE k.start >= rt.start
            GROUP BY {group_expr}
        """)
        from ._utils import _normalize_demangled

        # SQL groups by string id, but callers key on the *normalised* demangled
        # name, and distinct ids can normalise to the same key. Combine those
        # groups properly (launch-count-weighted mean, max of maxima) instead of
        # letting the last row silently win.
        acc: dict[str, tuple[float, float, int]] = {}
        for r in rows:
            if r["avg_launch_us"] is None or float(r["avg_launch_us"]) < 0:
                continue
            key = _normalize_demangled(r["name"])
            avg_us = float(r["avg_launch_us"])
            max_us = float(r["max_launch_us"])
            launches = int(r["launches"])
            if key in acc:
                prev_avg, prev_max, prev_n = acc[key]
                total_n = prev_n + launches
                avg_us = (prev_avg * prev_n + avg_us * launches) / total_n
                max_us = max(prev_max, max_us)
                launches = total_n
            acc[key] = (avg_us, max_us, launches)

        return {k: (round(avg, 2), round(mx, 2)) for k, (avg, mx, _) in acc.items()}

    def _hostname(self) -> str | None:
        """Capture host from TARGET_INFO_SYSTEM_ENV, or None if unrecorded.

        nsys writes this automatically; no capture flag is required. It is the
        only reliable way to tell an intra-node MPI exchange from one crossing
        the network, so it is read even when the GPU metadata table is absent.
        """
        if not self.has_table("TARGET_INFO_SYSTEM_ENV"):
            return None
        rows = self.query(
            "SELECT value FROM TARGET_INFO_SYSTEM_ENV WHERE name = 'Hostname' LIMIT 1"
        )
        if not rows:
            return None
        value = rows[0]["value"]
        return str(value) if value else None

    def capture_time_base(self):
        """Nsight timestamps are offsets from session start; the file records the origin.

        TARGET_INFO_SESSION_START_TIME.utcEpochNs plus an event's start gives an
        absolute time, which is what makes correlation with application output
        possible after the fact.
        """
        from .models import CaptureTimeBase

        if not self.has_table("TARGET_INFO_SESSION_START_TIME"):
            return CaptureTimeBase(
                kind="session_relative",
                note="no session-start row; timestamps cannot be anchored to wall clock",
            )
        cols = set(self.columns("TARGET_INFO_SESSION_START_TIME"))
        rows = self.query("SELECT * FROM TARGET_INFO_SESSION_START_TIME LIMIT 1")
        if not rows:
            return CaptureTimeBase(
                kind="session_relative",
                note="session-start table is empty; timestamps cannot be anchored",
            )
        row = rows[0]
        epoch = row["utcEpochNs"] if "utcEpochNs" in cols else None
        return CaptureTimeBase(
            kind="session_relative",
            utc_epoch_ns=int(epoch) if epoch else None,
            utc_time=row["utcTime"] if "utcTime" in cols else None,
            note=None if epoch else "no utcEpochNs column; timestamps cannot be anchored",
        )

    def device_info(self):
        """Query TARGET_INFO_GPU for hardware properties, plus the capture host."""
        from .models import DeviceInfo

        hostname = self._hostname()
        if not self.has_table("TARGET_INFO_GPU"):
            return DeviceInfo(hostname=hostname)
        cols = set(self.columns("TARGET_INFO_GPU"))
        rows = self.query("SELECT * FROM TARGET_INFO_GPU LIMIT 1")
        if not rows:
            return DeviceInfo(hostname=hostname)
        r = rows[0]

        def _int(col: str) -> int | None:
            return int(r[col]) if col in cols and r[col] is not None else None

        def _float(col: str) -> float | None:
            return float(r[col]) if col in cols and r[col] is not None else None

        sm_count = _int("smCount")
        max_threads_per_sm = None
        if "maxWarpsPerSm" in cols and "threadsPerWarp" in cols:
            warps = r["maxWarpsPerSm"]
            warp_size = r["threadsPerWarp"]
            if warps is not None and warp_size is not None:
                max_threads_per_sm = int(warps) * int(warp_size)

        peak_bw_GBs = None
        if "memoryBandwidth" in cols and r["memoryBandwidth"]:
            peak_bw_GBs = round(float(r["memoryBandwidth"]) / 1e9, 1)

        compute_cap = None
        major = _int("computeMajor")
        minor = _int("computeMinor")
        if major is not None and minor is not None:
            compute_cap = f"{major}.{minor}"

        total_mem_GiB = None
        if "totalMemory" in cols and r["totalMemory"]:
            total_mem_GiB = round(float(r["totalMemory"]) / (1024**3), 1)

        l2_MiB = None
        if "l2CacheSize" in cols and r["l2CacheSize"]:
            l2_MiB = round(float(r["l2CacheSize"]) / (1024**2), 1)

        clock_MHz = None
        if "clockRate" in cols and r["clockRate"]:
            clock_MHz = round(float(r["clockRate"]) / 1e6, 0)

        shmem_KiB = None
        if "maxShmemPerBlock" in cols and r["maxShmemPerBlock"]:
            shmem_KiB = round(float(r["maxShmemPerBlock"]) / 1024, 1)

        shmem_optin_KiB = None
        if "maxShmemPerBlockOptin" in cols and r["maxShmemPerBlockOptin"]:
            shmem_optin_KiB = round(float(r["maxShmemPerBlockOptin"]) / 1024, 1)

        return DeviceInfo(
            vendor="nvidia",
            hostname=hostname,
            name=r["name"] if "name" in cols and r["name"] else None,
            compute_capability=compute_cap,
            sm_count=sm_count,
            max_threads_per_sm=max_threads_per_sm,
            peak_memory_bandwidth_GBs=peak_bw_GBs,
            total_memory_GiB=total_mem_GiB,
            l2_cache_MiB=l2_MiB,
            max_threads_per_block=_int("maxThreadsPerBlock"),
            max_registers_per_block=_int("maxRegistersPerBlock"),
            max_shared_mem_per_block_KiB=shmem_KiB,
            max_shared_mem_per_block_optin_KiB=shmem_optin_KiB,
            clock_rate_MHz=clock_MHz,
        )

    def cpu_sync_blocked_s(self, span_s: float) -> tuple[float | None, float | None]:
        """Return (wall_clock_sync_s, pct_of_profile_span) for synchronization API calls.

        Intervals are merged rather than summed: a multi-threaded host can have
        several threads blocked in *Synchronize concurrently, and summing their
        durations can report more blocked time than the profile's wall clock.
        The merged figure answers the actionable question — how much of the run
        was the host stalled waiting on the GPU — and is bounded by the span.

        Returns (None, None) if RUNTIME is not present or lacks nameId.
        """
        if not self.has_table("CUPTI_ACTIVITY_KIND_RUNTIME"):
            return None, None
        if "nameId" not in set(self.columns("CUPTI_ACTIVITY_KIND_RUNTIME")):
            return None, None
        rows = self.query("""
            SELECT rt.start, rt.end
            FROM CUPTI_ACTIVITY_KIND_RUNTIME rt
            JOIN StringIds s ON rt.nameId = s.id
            WHERE s.value LIKE '%Synchronize%'
              AND rt.end IS NOT NULL
              AND rt.end > rt.start
        """)
        if not rows:
            return None, None
        from ._utils import busy_time_ns

        sync_s = round(busy_time_ns((r["start"], r["end"]) for r in rows) / 1e9, 3)
        pct = round(100.0 * sync_s / span_s, 1) if span_s > 0 else None
        return sync_s, pct

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> NsysProfile:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"NsysProfile({self.path.name!r})"
