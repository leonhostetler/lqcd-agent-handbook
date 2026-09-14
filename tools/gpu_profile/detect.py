"""Format detection and open_profile() factory."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .base import Format
from .nsys import NsysProfile
from .rocpd import RocpdProfile


def detect_format(path: str | Path) -> Format:
    """Sniff a SQLite profile's schema to determine whether it is nsys or rocpd.

    Detection heuristic:
    - Nsight Systems: has ``StringIds`` table AND at least one ``CUPTI_*`` table.
    - rocpd: has ``rocpd_string`` table or view (present even in truncated files).

    Raises ValueError for non-SQLite inputs or unrecognised schemas.
    """
    path = Path(path)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Not a valid SQLite file: {path}") from exc

    if "StringIds" in names and any(n.startswith("CUPTI_") for n in names):
        return Format.NSYS

    if "rocpd_string" in names:
        return Format.ROCPD

    raise ValueError(
        f"Unrecognized SQLite profile format at {path}. "
        "Expected an Nsight Systems export (StringIds + CUPTI_* tables) "
        "or a rocpd file (rocpd_string table or view)."
    )


def open_profile(path: str | Path) -> NsysProfile | RocpdProfile:
    """Open a GPU profile file, auto-detecting its format.

    Raises ValueError for ``.nsys-rep`` inputs (must be exported to SQLite first),
    unrecognised formats, and non-SQLite files.
    """
    path = Path(path)
    if path.suffix == ".nsys-rep":
        raise ValueError(
            f"{path.name} is an Nsight Systems report file; export to SQLite first:\n"
            f"  nsys export --type sqlite --output {path.stem}.sqlite {path}"
        )
    fmt = detect_format(path)
    if fmt == Format.NSYS:
        return NsysProfile(path)
    return RocpdProfile(path)
