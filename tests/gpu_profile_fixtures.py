#!/usr/bin/env python3
"""Synthetic profiler-database fixtures, CI-safe and self-contained.

Two families, matching the two formats the extraction tool ingests:

- Nsight Systems: a minimal CUPTI-schema SQLite database.
- rocpd (rocprofv3): a minimal schema_version=3 database, built with GUID-suffixed
  tables plus un-suffixed views, exactly as rocprofv3 writes them.

Ported from the source analyzer's pytest conftest to the handbook's stdlib
``unittest`` convention: module-level builders rather than session fixtures, so the
suite acquires no third-party test dependency. Real captures are multi-gigabyte and
machine-specific, and their paths and job identifiers may not enter this repository;
every check runs against these generated databases instead.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Nsight Systems
# ---------------------------------------------------------------------------

def _build_synthetic_db(path: Path) -> None:
    """Create a minimal but realistic Nsight Systems SQLite fixture.

    Timeline (all timestamps in nanoseconds from an arbitrary epoch):

    MEMCPY  H2D:   [900_000_000 .. 900_100_000]   1 MB  (~10 GB/s)
    NVTX range:    [950_000_000 .. end_of_kernels] "computePhase"
    MPI_Barrier:   [500_000_000 .. 600_000_000]    100 ms
    MPI_Allreduce: [700_000_000 .. 750_000_000]    50 ms
    CPU sync:      [800_000_000 .. 810_000_000]    10 ms

    Kernel timeline:
      Kernel3D  ×10: 2 ms each, 5 µs inter-kernel gap  (<10 µs bucket)  → 20 ms total
      Reduction2D ×2: 5 ms each, 1.1 ms gap before each (1–10 ms bucket) → 10 ms total

    Total GPU kernel time  = 30 ms = 0.030 s   (Kernel3D dominates)
    Profile span (min→max across all event sources) > 0.5 s (MPI events push span wider)
    """
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()

    # --- StringIds ---
    cur.execute("CREATE TABLE StringIds (id INTEGER PRIMARY KEY, value TEXT)")
    cur.executemany(
        "INSERT INTO StringIds VALUES (?, ?)",
        [
            (1, "Kernel3D"),
            (2, "void myKernel3D<MyFunctor>()"),
            (3, "Reduction2D"),
            (4, "void myReduction2D()"),
            (5, "MPI_Barrier"),
            (6, "MPI_Allreduce"),
            (7, "cuStreamSynchronize"),
            (8, "cudaLaunchKernel"),
            (9, "computePhase"),
        ],
    )

    # --- CUPTI_ACTIVITY_KIND_KERNEL ---
    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL (
            start INTEGER, end INTEGER,
            shortName INTEGER, demangledName INTEGER,
            gridX INTEGER, gridY INTEGER, gridZ INTEGER,
            blockX INTEGER, blockY INTEGER, blockZ INTEGER,
            registersPerThread INTEGER,
            staticSharedMemory INTEGER, dynamicSharedMemory INTEGER,
            sharedMemoryExecuted INTEGER,
            streamId INTEGER, correlationId INTEGER
        )
    """)
    # 10 × Kernel3D (shortName=1, demangledName=2)  on stream 7
    # Columns: start, end, shortName, demangledName,
    #          gridX, gridY, gridZ, blockX, blockY, blockZ,
    #          registersPerThread, staticSharedMemory, dynamicSharedMemory,
    #          sharedMemoryExecuted, streamId, correlationId
    k3d_rows = []
    base = 1_000_000_000
    for i in range(10):
        s = base + i * 2_005_000  # each kernel: 2ms + 5µs gap
        e = s + 2_000_000  # 2 ms duration
        k3d_rows.append((s, e, 1, 2, 1, 1, 1, 128, 1, 1, 32, 0, 0, None, 7, i + 1))
    # 2 × Reduction2D (shortName=3, demangledName=4) on stream 7
    # first starts 1.1 ms after last Kernel3D ends → 1-10ms gap bucket
    r_base = k3d_rows[-1][1] + 1_100_000  # 1.1 ms gap
    r2d_rows = []
    for i in range(2):
        s = r_base + i * 6_100_000  # 5ms kernel + 1.1ms gap
        e = s + 5_000_000  # 5 ms duration
        r2d_rows.append((s, e, 3, 4, 4, 1, 1, 256, 1, 1, 40, 2048, 0, None, 7, i + 11))
    cur.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        k3d_rows + r2d_rows,
    )

    # --- CUPTI_ACTIVITY_KIND_MEMCPY ---
    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_MEMCPY (
            start INTEGER, end INTEGER, bytes INTEGER, copyKind INTEGER
        )
    """)
    cur.execute(
        "INSERT INTO CUPTI_ACTIVITY_KIND_MEMCPY VALUES (?,?,?,?)",
        (900_000_000, 900_100_000, 1_048_576, 1),  # H2D, 1 MB, 100 µs → ~10 GB/s
    )

    # --- ENUM_CUDA_MEMCPY_OPER ---
    cur.execute("CREATE TABLE ENUM_CUDA_MEMCPY_OPER (id INTEGER PRIMARY KEY, label TEXT)")
    cur.executemany(
        "INSERT INTO ENUM_CUDA_MEMCPY_OPER VALUES (?, ?)",
        [
            (1, "Host-to-Device"),
            (2, "Device-to-Host"),
            (8, "Peer-to-Peer"),
        ],
    )

    # --- TARGET_INFO_GPU (A100-like) ---
    cur.execute("""
        CREATE TABLE TARGET_INFO_GPU (
            smCount INTEGER, maxWarpsPerSm INTEGER, threadsPerWarp INTEGER,
            memoryBandwidth INTEGER
        )
    """)
    cur.execute(
        "INSERT INTO TARGET_INFO_GPU VALUES (?, ?, ?, ?)",
        (108, 64, 32, 2_000_000_000_000),  # 2 TB/s HBM
    )

    # --- TARGET_INFO_SESSION_START_TIME ---
    # Real captures carry this in every profile inspected; it is the anchor that
    # makes trace timestamps correlatable with application output.
    cur.execute("""
        CREATE TABLE TARGET_INFO_SESSION_START_TIME (
            utcEpochNs INTEGER, utcTime TEXT, localTime TEXT
        )
    """)
    cur.execute(
        "INSERT INTO TARGET_INFO_SESSION_START_TIME VALUES (?, ?, ?)",
        (1_784_597_271_426_118_694, "2026-07-21T01:27:51", "2026-07-20T18:27:51"),
    )

    # --- NVTX_EVENTS ---
    cur.execute("""
        CREATE TABLE NVTX_EVENTS (
            start INTEGER, end INTEGER, text TEXT, eventType INTEGER
        )
    """)
    # eventType=59 is the "range" event type used by compute_nvtx_ranges
    cur.execute(
        "INSERT INTO NVTX_EVENTS VALUES (?, ?, ?, ?)",
        (950_000_000, r2d_rows[-1][1], "computePhase", 59),
    )

    # --- MPI_COLLECTIVES_EVENTS ---
    cur.execute("""
        CREATE TABLE MPI_COLLECTIVES_EVENTS (
            start INTEGER, end INTEGER, textId INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO MPI_COLLECTIVES_EVENTS VALUES (?, ?, ?)",
        [
            (500_000_000, 600_000_000, 5),  # MPI_Barrier  100 ms
            (700_000_000, 750_000_000, 6),  # MPI_Allreduce 50 ms
        ],
    )

    # --- CUPTI_ACTIVITY_KIND_RUNTIME (for launch overhead + CPU sync) ---
    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_RUNTIME (
            start INTEGER, end INTEGER, nameId INTEGER, correlationId INTEGER
        )
    """)
    # cudaLaunchKernel for Kernel3D k3d_1 → overhead = kernel.start - rt.start
    rt_k1_start = k3d_rows[0][0] - 100_000  # 100 µs before kernel start
    cur.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_RUNTIME VALUES (?, ?, ?, ?)",
        [
            (rt_k1_start, rt_k1_start + 50_000, 8, 1),  # cudaLaunchKernel corr=1
            (800_000_000, 810_000_000, 7, 10),  # cuStreamSynchronize 10 ms
        ],
    )

    conn.commit()
    conn.close()




def build_synthetic_nsys_db(path: Path) -> Path:
    """Write the synthetic Nsight Systems profile to ``path`` and return it."""
    _build_synthetic_db(Path(path))
    return Path(path)


# ---------------------------------------------------------------------------
# rocpd (rocprofv3)
# ---------------------------------------------------------------------------


# Fixed synthetic GUID — dashes in metadata/data, underscores in table names.
_ROCPD_GUID = "deadbeef-0000-0000-0000-000000000001"
_ROCPD_GUID_SUFFIX = "deadbeef_0000_0000_0000_000000000001"

# All table names in insertion dependency order (children after parents).
_ROCPD_CONCRETE_TABLES = [
    "rocpd_metadata",
    "rocpd_string",
    "rocpd_info_node",
    "rocpd_info_process",
    "rocpd_info_thread",
    "rocpd_info_agent",
    "rocpd_info_queue",
    "rocpd_info_stream",
    "rocpd_info_code_object",
    "rocpd_info_kernel_symbol",
    "rocpd_info_pmc",
    "rocpd_event",
    "rocpd_region",
    "rocpd_kernel_dispatch",
    "rocpd_memory_copy",
    "rocpd_memory_allocate",
    "rocpd_arg",
    "rocpd_track",
    "rocpd_sample",
    "rocpd_pmc_event",
]


def _rocpd_tbl(base: str) -> str:
    return f"`{base}_{_ROCPD_GUID_SUFFIX}`"


def _build_synthetic_rocpd_db(path: Path) -> None:  # noqa: C901 — long but linear
    """Create a minimal but schema-correct rocpd SQLite fixture.

    Mirrors exactly what rocprofv3 --sys-trace --output-format rocpd writes:
    GUID-suffixed concrete tables + un-suffixed SELECT-* views over them +
    the convenience views (kernels, regions, memory_copies, …).

    Timeline (nanoseconds, arbitrary epoch):

      Regions (CPU API calls):
        HSA_CORE_API      ×2: [1_000_100_000 … 1_000_200_000], [1_000_300_000 … 1_000_400_000]
        HSA_AMD_EXT_API   ×2: [1_000_500_000 … 1_000_600_000], [1_000_700_000 … 1_000_800_000]
        HIP_RUNTIME_API_EXT ×2: [1_000_900_000 … 1_001_000_000], [1_001_100_000 … 1_001_200_000]
        HIP_COMPILER_API_EXT ×2: [1_001_300_000 … 1_001_400_000], [1_001_500_000 … 1_001_600_000]

      Kernel dispatches (GPU):
        dslash_function ×4: 2 ms each, 5 µs inter-kernel gap  (<10 µs bucket)
        reduce_kernel   ×1: 5 ms, 2 ms gap after last dslash  (1–10 ms bucket)

      Memory copies:
        D2D: 50 µs, 1 MB
        H2D: 100 µs, 256 KB
        D2H: 50 µs, 256 KB

      Memory allocations:
        ALLOC REAL 4 MB
        FREE  REAL 4 MB

    Expected derived values:
      Total GPU kernel time = 4×2 ms + 5 ms = 13 ms = 0.013 s
      3 inter-kernel gaps of 5 µs  → "<10µs" bucket
      1 pre-reduce gap of 2 ms     → "1-10ms" bucket
      Top kernel: dslash_function (8 ms, ≈61.5 %)
      2nd kernel: reduce_kernel   (5 ms, ≈38.5 %)
    """
    G = _ROCPD_GUID
    S = _ROCPD_GUID_SUFFIX

    # Scalar helpers so SQL strings stay readable.
    def tbl(base: str) -> str:
        return f"`{base}_{S}`"

    conn = sqlite3.connect(str(path))
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Concrete GUID-suffixed tables (insertion order respects FKs)
    # ------------------------------------------------------------------

    # rocpd_metadata — no FKs
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_metadata")} (
            "id"    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "tag"   TEXT NOT NULL,
            "value" TEXT NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_metadata')} (tag, value) VALUES (?, ?)",
        [
            ("schema_version", "3"),
            ("uuid", f"_{S}"),
            ("guid", G),
        ],
    )

    # rocpd_string — no FKs
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_string")} (
            "id"    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"  TEXT DEFAULT '{G}' NOT NULL,
            "string" TEXT NOT NULL UNIQUE ON CONFLICT ABORT
        )""")
    # Strings are inserted with explicit ids to keep references readable.
    # Ids 1–4: HIP region names (1 doubles as kernel_dispatch.region_name_id)
    # Ids 5–8: HSA region names
    # Ids 9–12: event category labels
    # Ids 13–15: memory-copy direction labels
    _strings = [
        (1, G, "hipLaunchKernel"),
        (2, G, "hipMemcpyAsync"),
        (3, G, "__hipRegisterFatBinary"),
        (4, G, "hipModuleGetFunction"),
        (5, G, "hsa_queue_create"),
        (6, G, "hsa_signal_wait_scacquire"),
        (7, G, "hsa_amd_memory_async_copy"),
        (8, G, "hsa_amd_agent_iterate_memory_pools"),
        (9, G, "HSA_CORE_API"),
        (10, G, "HSA_AMD_EXT_API"),
        (11, G, "HIP_RUNTIME_API_EXT"),
        (12, G, "HIP_COMPILER_API_EXT"),
        (13, G, "MEMORY_COPY_DEVICE_TO_DEVICE"),
        (14, G, "MEMORY_COPY_HOST_TO_DEVICE"),
        (15, G, "MEMORY_COPY_DEVICE_TO_HOST"),
    ]
    cur.executemany(f"INSERT INTO {tbl('rocpd_string')} VALUES (?, ?, ?)", _strings)

    # rocpd_info_node — no FKs; id=1 is used as nid everywhere.
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_node")} (
            "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"         TEXT DEFAULT '{G}' NOT NULL,
            "hash"         BIGINT NOT NULL UNIQUE,
            "machine_id"   TEXT NOT NULL UNIQUE,
            "system_name"  TEXT,
            "hostname"     TEXT,
            "release"      TEXT,
            "version"      TEXT,
            "hardware_name" TEXT,
            "domain_name"  TEXT
        )""")
    cur.execute(
        f"INSERT INTO {tbl('rocpd_info_node')} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,
            G,
            1234567890,
            "synthetic-machine-id",
            "Linux",
            "synthetic-host",
            "6.0.0",
            "#1 SMP",
            "x86_64",
            "",
        ),
    )

    # rocpd_info_process — FK → node(id)
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_process")} (
            "id"          INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"        TEXT DEFAULT '{G}' NOT NULL,
            "nid"         INTEGER NOT NULL,
            "ppid"        INTEGER,
            "pid"         INTEGER NOT NULL,
            "init"        BIGINT,
            "fini"        BIGINT,
            "start"       BIGINT,
            "end"         BIGINT,
            "command"     TEXT,
            "environment" TEXT DEFAULT '{{}}' NOT NULL,
            "extdata"     TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.execute(
        f"INSERT INTO {tbl('rocpd_info_process')} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,
            G,
            1,
            1000,
            12345,
            1_000_000_000,
            2_000_000_000,
            1_000_000_000,
            2_000_000_000,
            "./synthetic_app",
            "{}",
            "{}",
        ),
    )

    # rocpd_info_thread — FK → node, process
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_thread")} (
            "id"      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"    TEXT DEFAULT '{G}' NOT NULL,
            "nid"     INTEGER NOT NULL,
            "ppid"    INTEGER,
            "pid"     INTEGER NOT NULL,
            "tid"     INTEGER NOT NULL,
            "name"    TEXT,
            "start"   BIGINT,
            "end"     BIGINT,
            "extdata" TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_info_thread')} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, G, 1, 1000, 1, 12345, None, None, None, "{}"),  # main thread
            (2, G, 1, 1000, 1, 12346, None, None, None, "{}"),  # HSA worker
        ],
    )

    # rocpd_info_agent — FK → node, process; id=1 CPU, id=2 GPU
    _GPU_EXTDATA = (
        '{"cu_count":110,"simd_count":440,"wave_front_size":64,'
        '"max_waves_per_cu":32,"lds_size_in_kb":64,'
        '"gfx_target_version":90010,"max_engine_clk_fcompute":1700}'
    )
    _CPU_EXTDATA = '{"cu_count":8,"cpu_cores_count":8,"gfx_target_version":0}'
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_agent")} (
            "id"             INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"           TEXT DEFAULT '{G}' NOT NULL,
            "nid"            INTEGER NOT NULL,
            "pid"            INTEGER NOT NULL,
            "type"           TEXT CHECK ("type" IN ('CPU','GPU')),
            "absolute_index" INTEGER,
            "logical_index"  INTEGER,
            "type_index"     INTEGER,
            "uuid"           INTEGER,
            "name"           TEXT,
            "model_name"     TEXT,
            "vendor_name"    TEXT,
            "product_name"   TEXT,
            "user_name"      TEXT,
            "extdata"        TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_info_agent')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                1,
                G,
                1,
                1,
                "CPU",
                0,
                0,
                0,
                None,
                "AMD EPYC",
                "",
                "CPU",
                "AMD EPYC",
                None,
                _CPU_EXTDATA,
            ),
            (
                2,
                G,
                1,
                1,
                "GPU",
                1,
                1,
                0,
                None,
                "gfx90a",
                "aldebaran",
                "AMD",
                "AMD Instinct MI250X",
                None,
                _GPU_EXTDATA,
            ),
        ],
    )

    # rocpd_info_queue — FK → node, process
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_queue")} (
            "id"      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"    TEXT DEFAULT '{G}' NOT NULL,
            "nid"     INTEGER NOT NULL,
            "pid"     INTEGER NOT NULL,
            "name"    TEXT,
            "extdata" TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.execute(
        f"INSERT INTO {tbl('rocpd_info_queue')} VALUES (?, ?, ?, ?, ?, ?)",
        (1, G, 1, 1, "Default Queue", "{}"),
    )

    # rocpd_info_stream — FK → node, process
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_stream")} (
            "id"      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"    TEXT DEFAULT '{G}' NOT NULL,
            "nid"     INTEGER NOT NULL,
            "pid"     INTEGER NOT NULL,
            "name"    TEXT,
            "extdata" TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.execute(
        f"INSERT INTO {tbl('rocpd_info_stream')} VALUES (?, ?, ?, ?, ?, ?)",
        (1, G, 1, 1, "Default Stream", "{}"),
    )

    # rocpd_info_code_object — FK → node, process, agent
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_code_object")} (
            "id"           INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"         TEXT DEFAULT '{G}' NOT NULL,
            "nid"          INTEGER NOT NULL,
            "pid"          INTEGER NOT NULL,
            "agent_id"     INTEGER,
            "uri"          TEXT,
            "load_base"    BIGINT,
            "load_size"    BIGINT,
            "load_delta"   BIGINT,
            "storage_type" TEXT CHECK ("storage_type" IN ('FILE','MEMORY')),
            "extdata"      TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.execute(
        f"INSERT INTO {tbl('rocpd_info_code_object')} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, G, 1, 1, 2, "memory://12345#offset=0x1000&size=4096", None, None, None, "MEMORY", "{}"),
    )

    # rocpd_info_kernel_symbol — FK → node, process, code_object
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_kernel_symbol")} (
            "id"                       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"                     TEXT DEFAULT '{G}' NOT NULL,
            "nid"                      INTEGER NOT NULL,
            "pid"                      INTEGER NOT NULL,
            "code_object_id"           INTEGER NOT NULL,
            "kernel_name"              TEXT,
            "display_name"             TEXT,
            "kernel_object"            INTEGER,
            "kernarg_segment_size"     INTEGER,
            "kernarg_segment_alignment" INTEGER,
            "group_segment_size"       INTEGER,
            "private_segment_size"     INTEGER,
            "sgpr_count"               INTEGER,
            "arch_vgpr_count"          INTEGER,
            "accum_vgpr_count"         INTEGER,
            "extdata"                  TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_info_kernel_symbol')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            # dslash_function: HBM-bandwidth-bound stencil kernel
            (
                1,
                G,
                1,
                1,
                1,
                "dslash_function<Dslash3D,int>.kd",
                "dslash_function<Dslash3D,int>",
                None,
                512,
                64,
                0,
                0,
                96,
                128,
                4,
                "{}",
            ),
            # reduce_kernel: compute-bound reduction
            (
                2,
                G,
                1,
                1,
                1,
                "reduce_kernel<float>.kd",
                "reduce_kernel<float>",
                None,
                256,
                64,
                16384,
                0,
                48,
                64,
                4,
                "{}",
            ),
        ],
    )

    # rocpd_info_pmc — empty table (PMC counters not captured)
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_info_pmc")} (
            "id"   INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid" TEXT DEFAULT '{G}' NOT NULL,
            "name" TEXT,
            "description" TEXT
        )""")

    # rocpd_event — FK → string(category_id); must exist before region/dispatch/copy
    # Events 1–8: one per region (2 per category × 4 categories)
    # Events 9–13: one per kernel dispatch
    # Events 14–16: one per memory copy
    # Events 17–18: one per memory allocation
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_event")} (
            "id"               INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"             TEXT DEFAULT '{G}' NOT NULL,
            "category_id"      INTEGER,
            "stack_id"         INTEGER,
            "parent_stack_id"  INTEGER,
            "correlation_id"   INTEGER,
            "call_stack"       TEXT DEFAULT '{{}}' NOT NULL,
            "line_info"        TEXT DEFAULT '{{}}' NOT NULL,
            "extdata"          TEXT DEFAULT '{{}}' NOT NULL
        )""")
    _events = []
    # Category-bearing events for regions (category_id → string ids 9–12)
    for cat_sid in [9, 9, 10, 10, 11, 11, 12, 12]:  # ids 1–8
        _events.append((None, G, cat_sid, None, None, 0, "{}", "{}", "{}"))
    # No-category events for dispatches + copies + allocs (ids 9–18)
    for _ in range(10):
        _events.append((None, G, None, None, None, 0, "{}", "{}", "{}"))
    cur.executemany(f"INSERT INTO {tbl('rocpd_event')} VALUES (?,?,?,?,?,?,?,?,?)", _events)

    # rocpd_region — FK → node, process, thread, string(name_id), event
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_region")} (
            "id"       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"     TEXT DEFAULT '{G}' NOT NULL,
            "nid"      INTEGER NOT NULL,
            "pid"      INTEGER NOT NULL,
            "tid"      INTEGER NOT NULL,
            "start"    BIGINT NOT NULL,
            "end"      BIGINT NOT NULL,
            "name_id"  INTEGER NOT NULL,
            "event_id" INTEGER,
            "extdata"  TEXT DEFAULT '{{}}' NOT NULL
        )""")
    # 2 regions per category; name_ids match string table; event_ids 1–8.
    _regions = [
        # HSA_CORE_API ×2
        (None, G, 1, 1, 1, 1_000_100_000, 1_000_200_000, 5, 1, "{}"),
        (None, G, 1, 1, 1, 1_000_300_000, 1_000_400_000, 6, 2, "{}"),
        # HSA_AMD_EXT_API ×2
        (None, G, 1, 1, 1, 1_000_500_000, 1_000_600_000, 7, 3, "{}"),
        (None, G, 1, 1, 1, 1_000_700_000, 1_000_800_000, 8, 4, "{}"),
        # HIP_RUNTIME_API_EXT ×2
        (None, G, 1, 1, 1, 1_000_900_000, 1_001_000_000, 1, 5, "{}"),
        (None, G, 1, 1, 1, 1_001_100_000, 1_001_200_000, 2, 6, "{}"),
        # HIP_COMPILER_API_EXT ×2
        (None, G, 1, 1, 1, 1_001_300_000, 1_001_400_000, 3, 7, "{}"),
        (None, G, 1, 1, 1, 1_001_500_000, 1_001_600_000, 4, 8, "{}"),
    ]
    cur.executemany(f"INSERT INTO {tbl('rocpd_region')} VALUES (?,?,?,?,?,?,?,?,?,?)", _regions)

    # rocpd_kernel_dispatch — FK → node, process, thread, agent, kernel_symbol,
    #                               queue, stream, string(region_name_id), event
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_kernel_dispatch")} (
            "id"                  INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"                TEXT DEFAULT '{G}' NOT NULL,
            "nid"                 INTEGER NOT NULL,
            "pid"                 INTEGER NOT NULL,
            "tid"                 INTEGER,
            "agent_id"            INTEGER NOT NULL,
            "kernel_id"           INTEGER NOT NULL,
            "dispatch_id"         INTEGER NOT NULL,
            "queue_id"            INTEGER NOT NULL,
            "stream_id"           INTEGER NOT NULL,
            "start"               BIGINT NOT NULL,
            "end"                 BIGINT NOT NULL,
            "private_segment_size" INTEGER,
            "group_segment_size"  INTEGER,
            "workgroup_size_x"    INTEGER NOT NULL,
            "workgroup_size_y"    INTEGER NOT NULL,
            "workgroup_size_z"    INTEGER NOT NULL,
            "grid_size_x"         INTEGER NOT NULL,
            "grid_size_y"         INTEGER NOT NULL,
            "grid_size_z"         INTEGER NOT NULL,
            "region_name_id"      INTEGER,
            "event_id"            INTEGER,
            "extdata"             TEXT DEFAULT '{{}}' NOT NULL
        )""")
    # 4× dslash_function (2 ms each, 5 µs gaps) + 1× reduce_kernel (5 ms, 2 ms gap)
    _dslash_base = 1_100_000_000
    _dispatches = []
    for i in range(4):
        s = _dslash_base + i * 2_005_000  # 2 ms + 5 µs stride
        e = s + 2_000_000
        _dispatches.append(
            (
                None,
                G,
                1,
                1,
                1,
                2,
                1,
                i + 1,
                1,
                1,
                s,
                e,
                0,
                0,
                128,
                1,
                1,
                110592,
                1,
                1,
                1,
                9 + i,
                "{}",
            )
        )
    # reduce_kernel: 2 ms gap after last dslash
    _r_start = _dslash_base + 4 * 2_005_000 + 2_000_000  # end of last dslash + 2 ms
    _dispatches.append(
        (
            None,
            G,
            1,
            1,
            1,
            2,
            2,
            5,
            1,
            1,
            _r_start,
            _r_start + 5_000_000,
            0,
            16384,
            256,
            1,
            1,
            4096,
            1,
            1,
            1,
            13,
            "{}",
        )
    )
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_kernel_dispatch')} VALUES "
        f"(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        _dispatches,
    )

    # rocpd_memory_copy — FK → node, process, thread, string(name_id),
    #                          agent(dst), agent(src), queue, stream, event
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_memory_copy")} (
            "id"              INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"            TEXT DEFAULT '{G}' NOT NULL,
            "nid"             INTEGER NOT NULL,
            "pid"             INTEGER NOT NULL,
            "tid"             INTEGER,
            "start"           BIGINT NOT NULL,
            "end"             BIGINT NOT NULL,
            "name_id"         INTEGER NOT NULL,
            "dst_agent_id"    INTEGER,
            "dst_address"     INTEGER,
            "src_agent_id"    INTEGER,
            "src_address"     INTEGER,
            "size"            INTEGER NOT NULL,
            "queue_id"        INTEGER,
            "stream_id"       INTEGER,
            "region_name_id"  INTEGER,
            "event_id"        INTEGER,
            "extdata"         TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_memory_copy')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            # D2D: GPU→GPU, 1 MB, 50 µs
            (
                None,
                G,
                1,
                1,
                1,
                1_200_000_000,
                1_200_050_000,
                13,
                2,
                None,
                2,
                None,
                1_048_576,
                1,
                1,
                None,
                14,
                "{}",
            ),
            # H2D: CPU→GPU, 256 KB, 100 µs
            (
                None,
                G,
                1,
                1,
                1,
                1_201_000_000,
                1_201_100_000,
                14,
                2,
                None,
                1,
                None,
                262_144,
                1,
                1,
                None,
                15,
                "{}",
            ),
            # D2H: GPU→CPU, 256 KB, 50 µs
            (
                None,
                G,
                1,
                1,
                1,
                1_202_000_000,
                1_202_050_000,
                15,
                1,
                None,
                2,
                None,
                262_144,
                1,
                1,
                None,
                16,
                "{}",
            ),
        ],
    )

    # rocpd_memory_allocate — FK → node, process, thread, agent, queue, stream, event
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_memory_allocate")} (
            "id"       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"     TEXT DEFAULT '{G}' NOT NULL,
            "nid"      INTEGER NOT NULL,
            "pid"      INTEGER NOT NULL,
            "tid"      INTEGER,
            "agent_id" INTEGER,
            "type"     TEXT CHECK ("type" IN ('ALLOC','FREE','REALLOC','RECLAIM')),
            "level"    TEXT CHECK ("level" IN ('REAL','VIRTUAL','SCRATCH')),
            "start"    BIGINT NOT NULL,
            "end"      BIGINT NOT NULL,
            "address"  INTEGER,
            "size"     INTEGER NOT NULL,
            "queue_id" INTEGER,
            "stream_id" INTEGER,
            "event_id" INTEGER,
            "extdata"  TEXT DEFAULT '{{}}' NOT NULL
        )""")
    cur.executemany(
        f"INSERT INTO {tbl('rocpd_memory_allocate')} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            (
                None,
                G,
                1,
                1,
                1,
                2,
                "ALLOC",
                "REAL",
                1_300_000_000,
                1_300_001_000,
                None,
                4_194_304,
                None,
                None,
                17,
                "{}",
            ),
            (
                None,
                G,
                1,
                1,
                1,
                2,
                "FREE",
                "REAL",
                1_900_000_000,
                1_900_001_000,
                None,
                4_194_304,
                None,
                None,
                18,
                "{}",
            ),
        ],
    )

    # rocpd_arg — FK → event
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_arg")} (
            "id"       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"     TEXT DEFAULT '{G}' NOT NULL,
            "event_id" INTEGER NOT NULL,
            "position" INTEGER NOT NULL,
            "type"     TEXT NOT NULL,
            "name"     TEXT NOT NULL,
            "value"    TEXT,
            "extdata"  TEXT DEFAULT '{{}}' NOT NULL
        )""")

    # rocpd_track — FK → node, process, thread, string
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_track")} (
            "id"      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"    TEXT DEFAULT '{G}' NOT NULL,
            "nid"     INTEGER NOT NULL,
            "pid"     INTEGER,
            "tid"     INTEGER,
            "name_id" INTEGER,
            "extdata" TEXT DEFAULT '{{}}' NOT NULL
        )""")

    # rocpd_sample — empty (no CPU sampling)
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_sample")} (
            "id"       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"     TEXT DEFAULT '{G}' NOT NULL,
            "nid"      INTEGER NOT NULL,
            "pid"      INTEGER NOT NULL,
            "tid"      INTEGER NOT NULL,
            "start"    BIGINT NOT NULL,
            "end"      BIGINT NOT NULL,
            "event_id" INTEGER,
            "extdata"  TEXT DEFAULT '{{}}' NOT NULL
        )""")

    # rocpd_pmc_event — empty (no PMC counters)
    cur.execute(f"""
        CREATE TABLE {tbl("rocpd_pmc_event")} (
            "id"          INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            "guid"        TEXT DEFAULT '{G}' NOT NULL,
            "nid"         INTEGER NOT NULL,
            "pid"         INTEGER NOT NULL,
            "tid"         INTEGER,
            "agent_id"    INTEGER,
            "pmc_id"      INTEGER,
            "dispatch_id" INTEGER,
            "start"       BIGINT,
            "end"         BIGINT,
            "value"       REAL,
            "extdata"     TEXT DEFAULT '{{}}' NOT NULL
        )""")

    # ------------------------------------------------------------------
    # 2. Un-suffixed passthrough views (SELECT * FROM guid-suffixed table)
    # ------------------------------------------------------------------
    for base in _ROCPD_CONCRETE_TABLES:
        cur.execute(f"CREATE VIEW `{base}` AS SELECT * FROM {tbl(base)}")

    # ------------------------------------------------------------------
    # 3. Convenience views (verbatim from real rocprofv3 output,
    #    referencing the un-suffixed views created above)
    # ------------------------------------------------------------------

    cur.execute("""
        CREATE VIEW `kernels` AS
        SELECT
            K.id, K.guid, T.tid,
            (SELECT string FROM `rocpd_string` RS
             WHERE RS.id = E.category_id AND RS.guid = E.guid) AS category,
            R.string AS region,
            S.display_name AS name,
            K.nid, P.pid,
            A.absolute_index AS agent_abs_index,
            A.logical_index  AS agent_log_index,
            A.type_index     AS agent_type_index,
            A.type           AS agent_type,
            S.code_object_id, K.kernel_id, K.dispatch_id,
            K.stream_id, K.queue_id,
            Q.name AS queue, ST.name AS stream,
            K.start, K.end, (K.end - K.start) AS duration,
            K.grid_size_x AS grid_x, K.grid_size_y AS grid_y, K.grid_size_z AS grid_z,
            K.workgroup_size_x AS workgroup_x, K.workgroup_size_y AS workgroup_y,
            K.workgroup_size_z AS workgroup_z,
            K.group_segment_size AS lds_size,
            K.private_segment_size AS scratch_size,
            S.arch_vgpr_count AS vgpr_count,
            S.accum_vgpr_count, S.sgpr_count,
            S.group_segment_size AS static_lds_size,
            S.private_segment_size AS static_scratch_size,
            E.stack_id, E.parent_stack_id,
            E.correlation_id AS corr_id
        FROM `rocpd_kernel_dispatch` K
        INNER JOIN `rocpd_info_agent` A ON A.id = K.agent_id AND A.guid = K.guid
        INNER JOIN `rocpd_event` E ON E.id = K.event_id AND E.guid = K.guid
        INNER JOIN `rocpd_string` R ON R.id = K.region_name_id AND R.guid = K.guid
        INNER JOIN `rocpd_info_kernel_symbol` S ON S.id = K.kernel_id AND S.guid = K.guid
        LEFT  JOIN `rocpd_info_stream` ST ON ST.id = K.stream_id AND ST.guid = K.guid
        LEFT  JOIN `rocpd_info_queue`  Q  ON Q.id  = K.queue_id  AND Q.guid  = K.guid
        INNER JOIN `rocpd_info_process` P ON P.id = Q.pid AND P.guid = Q.guid
        INNER JOIN `rocpd_info_thread`  T ON T.id = K.tid  AND T.guid = K.guid
    """)

    cur.execute("""
        CREATE VIEW `regions` AS
        SELECT
            R.id, R.guid,
            (SELECT string FROM `rocpd_string` RS
             WHERE RS.id = E.category_id AND RS.guid = E.guid) AS category,
            S.string AS name,
            R.nid, P.pid, T.tid,
            R.start, R.end, (R.end - R.start) AS duration,
            R.event_id, E.stack_id, E.parent_stack_id,
            E.correlation_id AS corr_id,
            E.extdata, E.call_stack, E.line_info
        FROM `rocpd_region` R
        INNER JOIN `rocpd_event` E ON E.id = R.event_id AND E.guid = R.guid
        INNER JOIN `rocpd_string` S ON S.id = R.name_id AND S.guid = R.guid
        INNER JOIN `rocpd_info_process` P ON P.id = R.pid AND P.guid = R.guid
        INNER JOIN `rocpd_info_thread`  T ON T.id = R.tid AND T.guid = R.guid
    """)

    cur.execute("""
        CREATE VIEW `memory_copies` AS
        SELECT
            M.id, M.guid,
            (SELECT string FROM `rocpd_string` RS
             WHERE RS.id = E.category_id AND RS.guid = E.guid) AS category,
            M.nid, P.pid, T.tid,
            M.start, M.end, (M.end - M.start) AS duration,
            S.string AS name,
            R.string AS region_name,
            M.stream_id, M.queue_id,
            ST.name AS stream_name, Q.name AS queue_name,
            M.size,
            dst.name AS dst_device,
            dst.absolute_index AS dst_agent_abs_index,
            dst.logical_index  AS dst_agent_log_index,
            dst.type_index     AS dst_agent_type_index,
            dst.type           AS dst_agent_type,
            M.dst_address,
            src.name AS src_device,
            src.absolute_index AS src_agent_abs_index,
            src.logical_index  AS src_agent_log_index,
            src.type_index     AS src_agent_type_index,
            src.type           AS src_agent_type,
            M.src_address,
            E.stack_id, E.parent_stack_id, E.correlation_id AS corr_id
        FROM `rocpd_memory_copy` M
        INNER JOIN `rocpd_string` S ON S.id = M.name_id AND S.guid = M.guid
        LEFT  JOIN `rocpd_string` R ON R.id = M.region_name_id AND R.guid = M.guid
        INNER JOIN `rocpd_info_agent` dst ON dst.id = M.dst_agent_id AND dst.guid = M.guid
        INNER JOIN `rocpd_info_agent` src ON src.id = M.src_agent_id AND src.guid = M.guid
        LEFT  JOIN `rocpd_info_queue`  Q  ON Q.id  = M.queue_id  AND Q.guid  = M.guid
        LEFT  JOIN `rocpd_info_stream` ST ON ST.id = M.stream_id AND ST.guid = M.guid
        INNER JOIN `rocpd_event` E ON E.id = M.event_id AND E.guid = M.guid
        INNER JOIN `rocpd_info_process` P ON P.id = M.pid AND P.guid = M.guid
        INNER JOIN `rocpd_info_thread`  T ON T.id = M.tid AND T.guid = M.guid
    """)

    cur.execute("""
        CREATE VIEW `memory_allocations` AS
        SELECT
            M.id, M.guid,
            (SELECT string FROM `rocpd_string` RS
             WHERE RS.id = E.category_id AND RS.guid = E.guid) AS category,
            M.nid, P.pid, T.tid,
            M.start, M.end, (M.end - M.start) AS duration,
            M.type, M.level,
            A.name AS agent_name,
            A.absolute_index AS agent_abs_index,
            A.logical_index  AS agent_log_index,
            A.type_index     AS agent_type_index,
            A.type           AS agent_type,
            M.address, M.size,
            M.queue_id, Q.name AS queue_name,
            M.stream_id, ST.name AS stream_name,
            E.stack_id, E.parent_stack_id, E.correlation_id AS corr_id
        FROM `rocpd_memory_allocate` M
        LEFT  JOIN `rocpd_info_agent`  A  ON M.agent_id = A.id AND M.guid = A.guid
        LEFT  JOIN `rocpd_info_queue`  Q  ON Q.id = M.queue_id  AND Q.guid = M.guid
        LEFT  JOIN `rocpd_info_stream` ST ON ST.id = M.stream_id AND ST.guid = M.guid
        INNER JOIN `rocpd_event` E ON E.id = M.event_id AND E.guid = M.guid
        INNER JOIN `rocpd_info_process` P ON P.id = M.pid AND P.guid = M.guid
        INNER JOIN `rocpd_info_thread`  T ON T.id = M.tid AND P.guid = M.guid
    """)

    cur.execute("""
        CREATE VIEW `kernel_symbols` AS
        SELECT
            KS.id, KS.guid, KS.nid, P.pid,
            KS.code_object_id, KS.kernel_name, KS.display_name,
            KS.kernel_object, KS.kernarg_segment_size, KS.kernarg_segment_alignment,
            KS.group_segment_size, KS.private_segment_size,
            KS.sgpr_count, KS.arch_vgpr_count, KS.accum_vgpr_count,
            JSON_EXTRACT(KS.extdata, '$.size')         AS kernel_symbol_size,
            JSON_EXTRACT(KS.extdata, '$.kernel_id')    AS kernel_id,
            JSON_EXTRACT(KS.extdata, '$.formatted_kernel_name')  AS formatted_kernel_name,
            JSON_EXTRACT(KS.extdata, '$.demangled_kernel_name')  AS demangled_kernel_name,
            JSON_EXTRACT(KS.extdata, '$.truncated_kernel_name')  AS truncated_kernel_name,
            JSON_EXTRACT(KS.extdata, '$.kernel_address.handle')  AS kernel_address
        FROM `rocpd_info_kernel_symbol` KS
        INNER JOIN `rocpd_info_process` P ON KS.pid = P.id AND KS.guid = P.guid
    """)

    cur.execute("""
        CREATE VIEW `code_objects` AS
        SELECT
            CO.id, CO.guid, CO.nid, P.pid,
            A.absolute_index AS agent_abs_index,
            CO.uri, CO.load_base, CO.load_size, CO.load_delta,
            CO.storage_type AS storage_type_str,
            JSON_EXTRACT(CO.extdata, '$.size')         AS code_object_size,
            JSON_EXTRACT(CO.extdata, '$.storage_type') AS storage_type,
            JSON_EXTRACT(CO.extdata, '$.memory_base')  AS memory_base,
            JSON_EXTRACT(CO.extdata, '$.memory_size')  AS memory_size
        FROM `rocpd_info_code_object` CO
        INNER JOIN `rocpd_info_agent`   A ON CO.agent_id = A.id AND CO.guid = A.guid
        INNER JOIN `rocpd_info_process` P ON CO.pid = P.id AND CO.guid = P.guid
    """)

    cur.execute("""
        CREATE VIEW `processes` AS
        SELECT
            N.id AS nid, N.machine_id, N.system_name, N.hostname,
            N.release AS system_release, N.version AS system_version,
            P.guid, P.ppid, P.pid, P.init, P.start, P.end, P.fini, P.command
        FROM `rocpd_info_process` P
        INNER JOIN `rocpd_info_node` N ON N.id = P.nid AND N.guid = P.guid
    """)

    cur.execute("""
        CREATE VIEW `threads` AS
        SELECT
            N.id AS nid, N.machine_id, N.system_name, N.hostname,
            N.release AS system_release, N.version AS system_version,
            P.guid, P.ppid, P.pid, T.tid, T.start, T.end, T.name
        FROM `rocpd_info_thread` T
        INNER JOIN `rocpd_info_process` P ON P.id = T.pid AND N.guid = T.guid
        INNER JOIN `rocpd_info_node`    N ON N.id = T.nid AND N.guid = T.guid
    """)

    cur.execute("""
        CREATE VIEW `top_kernels` AS
        SELECT
            S.display_name AS name,
            COUNT(K.kernel_id) AS total_calls,
            SUM(K.end - K.start) / 1000.0 AS total_duration,
            (SUM(K.end - K.start) / COUNT(K.kernel_id)) / 1000.0 AS average,
            SUM(K.end - K.start) * 100.0 / (
                SELECT SUM(A.end - A.start) FROM `rocpd_kernel_dispatch` A
            ) AS percentage
        FROM `rocpd_kernel_dispatch` K
        INNER JOIN `rocpd_info_kernel_symbol` S ON S.id = K.kernel_id AND S.guid = K.guid
        GROUP BY name
        ORDER BY total_duration DESC
    """)

    conn.commit()
    conn.close()


def build_synthetic_rocpd_db(path: Path) -> Path:
    """Write the synthetic rocpd v3 database to ``path`` and return it."""
    _build_synthetic_rocpd_db(Path(path))
    return Path(path)


# ---------------------------------------------------------------------------
# Idle attribution / transfer overlap
# ---------------------------------------------------------------------------

# One GPU-driving thread plus one background progress thread. The second exists so the
# OS-runtime filter has something to exclude: unfiltered, a progress thread parked in
# poll() for the whole run covers every idle gap and reports ~100% OS-blocked time.
_ATTRIB_GPU_TID = 1001
_ATTRIB_BACKGROUND_TID = 2002


def build_idle_attribution_nsys_db(
    path: Path,
    *,
    mpi_window: tuple[int, int] = (1_003_000_000, 1_007_000_000),
    api_window: tuple[int, int] = (1_015_000_000, 1_018_000_000),
    os_window: tuple[int, int] = (1_019_000_000, 1_020_000_000),
    exposed_memcpy: tuple[int, int] = (1_008_000_000, 1_009_000_000),
    hidden_memcpy: tuple[int, int] = (1_000_500_000, 1_001_500_000),
) -> Path:
    """A timeline with exactly known idle attribution, and knobs to perturb it.

    Kernels (2 ms each) with two 10 ms gaps::

        K1 [1.000 .. 1.002]  gap A [1.002 .. 1.012]
        K2 [1.012 .. 1.014]  gap B [1.014 .. 1.024]
        K3 [1.024 .. 1.026]

    kernel busy = 6 ms, inter-kernel idle = 20 ms. With default windows:
    mpi = 4 ms (in gap A), host_api = 3 ms (gap B), os_runtime = 1 ms (gap B),
    residual = 12 ms. Every window is a parameter so a test can move one event and
    assert the bucket it belongs to moves with it.
    """
    path = Path(path)
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()

    cur.execute("CREATE TABLE StringIds (id INTEGER PRIMARY KEY, value TEXT)")
    cur.executemany(
        "INSERT INTO StringIds VALUES (?, ?)",
        [
            (1, "Kernel3D"),
            (2, "void attribKernel()"),
            (3, "MPI_Allreduce"),
            (4, "cuCtxSynchronize"),
            (5, "poll"),
            (6, "cudaLaunchKernel"),
        ],
    )

    cur.execute("""
        CREATE TABLE TARGET_INFO_GPU (
            smCount INTEGER, maxWarpsPerSm INTEGER, threadsPerWarp INTEGER,
            memoryBandwidth INTEGER
        )
    """)
    cur.execute(
        "INSERT INTO TARGET_INFO_GPU VALUES (?, ?, ?, ?)", (108, 64, 32, 2_000_000_000_000)
    )

    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_KERNEL (
            start INTEGER, end INTEGER,
            shortName INTEGER, demangledName INTEGER,
            gridX INTEGER, gridY INTEGER, gridZ INTEGER,
            blockX INTEGER, blockY INTEGER, blockZ INTEGER,
            registersPerThread INTEGER,
            staticSharedMemory INTEGER, dynamicSharedMemory INTEGER,
            sharedMemoryExecuted INTEGER,
            streamId INTEGER, correlationId INTEGER
        )
    """)
    kernels = [
        (1_000_000_000, 1_002_000_000),
        (1_012_000_000, 1_014_000_000),
        (1_024_000_000, 1_026_000_000),
    ]
    cur.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_KERNEL VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(s, e, 1, 2, 64, 1, 1, 256, 1, 1, 32, 0, 0, 0, 7, i + 1)
         for i, (s, e) in enumerate(kernels)],
    )

    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_MEMCPY (
            start INTEGER, end INTEGER, bytes INTEGER, copyKind INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_MEMCPY VALUES (?,?,?,?)",
        [
            (hidden_memcpy[0], hidden_memcpy[1], 1 << 20, 1),   # H2D, hidden behind K1
            (exposed_memcpy[0], exposed_memcpy[1], 1 << 20, 2),  # D2H, exposed in gap A
        ],
    )

    cur.execute("CREATE TABLE ENUM_CUDA_MEMCPY_OPER (id INTEGER PRIMARY KEY, label TEXT)")
    cur.executemany(
        "INSERT INTO ENUM_CUDA_MEMCPY_OPER VALUES (?, ?)",
        [(1, "Host-to-Device"), (2, "Device-to-Host"), (8, "Device-to-Device")],
    )

    cur.execute("""
        CREATE TABLE MPI_COLLECTIVES_EVENTS (start INTEGER, end INTEGER, textId INTEGER)
    """)
    cur.execute("INSERT INTO MPI_COLLECTIVES_EVENTS VALUES (?,?,?)", (*mpi_window, 3))

    cur.execute("""
        CREATE TABLE CUPTI_ACTIVITY_KIND_RUNTIME (
            start INTEGER, end INTEGER, eventClass INTEGER, globalTid INTEGER,
            correlationId INTEGER, nameId INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO CUPTI_ACTIVITY_KIND_RUNTIME VALUES (?,?,?,?,?,?)",
        [
            (api_window[0], api_window[1], 0, _ATTRIB_GPU_TID, 50, 4),
            # A launch call, so the GPU-driving thread is identifiable.
            (999_900_000, 999_950_000, 0, _ATTRIB_GPU_TID, 1, 6),
        ],
    )

    cur.execute("""
        CREATE TABLE OSRT_API (
            start INTEGER, end INTEGER, eventClass INTEGER, globalTid INTEGER, nameId INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO OSRT_API VALUES (?,?,?,?,?)",
        [
            (os_window[0], os_window[1], 0, _ATTRIB_GPU_TID, 5),
            # Background progress thread parked across the whole timeline. It must be
            # excluded, or it alone accounts for every idle nanosecond.
            (999_000_000, 1_030_000_000, 0, _ATTRIB_BACKGROUND_TID, 5),
        ],
    )

    conn.commit()
    conn.close()
    return path
