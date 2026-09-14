"""Offline GPU profile extraction.

Deterministic extraction from a profiler database: no model call, no network, no
third-party import. See ARCHITECTURE.md §profile-analysis for why this half is a
tool and the interpretation contract is a leaf.
"""

from .base import Format, ProfileCapabilities
from .detect import detect_format, open_profile
from .nsys import NsysProfile
from .rocpd import RocpdProfile

__all__ = [
    "Format",
    "NsysProfile",
    "ProfileCapabilities",
    "RocpdProfile",
    "detect_format",
    "open_profile",
]
