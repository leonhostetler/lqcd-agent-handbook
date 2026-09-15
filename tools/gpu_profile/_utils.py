from __future__ import annotations

import re
from collections.abc import Iterable


def merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent [start, end) intervals into a disjoint, sorted list.

    GPU kernels run concurrently across streams (and across devices sharing one
    profile), so summing individual durations double-counts wall-clock time.
    Merging first gives the true occupied span.

    Zero-length and inverted intervals are dropped; adjacent intervals that
    merely touch (``prev_end == start``) are coalesced, since there is no idle
    time between them.
    """
    ordered = sorted((s, e) for s, e in intervals if e > s)
    if not ordered:
        return []
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))
    return merged


def busy_time_ns(intervals: Iterable[tuple[int, int]]) -> int:
    """Total wall-clock time covered by at least one of ``intervals``."""
    return sum(e - s for s, e in merge_intervals(intervals))


def interval_gaps_ns(intervals: Iterable[tuple[int, int]]) -> list[int]:
    """Idle gaps between merged intervals.

    Computed from the merged set, so a long kernel overlapping shorter ones can
    no longer produce a phantom gap: gaps are measured from the running maximum
    end, not from the previous event in start order.
    """
    merged = merge_intervals(intervals)
    return [merged[i][0] - merged[i - 1][1] for i in range(1, len(merged))]


def intersect_duration_ns(
    a: Iterable[tuple[int, int]], b: Iterable[tuple[int, int]]
) -> int:
    """Total time covered by both interval sets.

    Both sides are merged first, so an input that double-covers a nanosecond
    contributes it once. That is the same rule ``busy_time_ns`` applies, and it
    is why idle attribution cannot exceed the idle it is attributing: overlapping
    MPI calls on different threads merge rather than sum.
    """
    left = merge_intervals(a)
    right = merge_intervals(b)
    total = 0
    i = j = 0
    while i < len(left) and j < len(right):
        lo = max(left[i][0], right[j][0])
        hi = min(left[i][1], right[j][1])
        if hi > lo:
            total += hi - lo
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return total


def subtract_intervals(
    base: Iterable[tuple[int, int]], cut: Iterable[tuple[int, int]]
) -> list[tuple[int, int]]:
    """``base`` minus ``cut``, both merged first; returns disjoint remainder."""
    merged_base = merge_intervals(base)
    merged_cut = merge_intervals(cut)
    out: list[tuple[int, int]] = []
    j = 0
    for start, end in merged_base:
        cursor = start
        while j < len(merged_cut) and merged_cut[j][1] <= cursor:
            j += 1
        k = j
        while k < len(merged_cut) and merged_cut[k][0] < end:
            cut_start, cut_end = merged_cut[k]
            if cut_start > cursor:
                out.append((cursor, min(cut_start, end)))
            cursor = max(cursor, min(cut_end, end))
            k += 1
        if cursor < end:
            out.append((cursor, end))
    return out


def _normalize_demangled(name: str) -> str:
    """Strip CUDA/QUDA template boilerplate from a demangled kernel name.

    Two passes:
    1. Strip SFINAE return-type prefix:
       "std::enable_if<..., void>::type " — common in QUDA and other CUDA
       template libraries that use enable_if to gate kernel instantiation.
    2. Strip trailing "(T2)" argument placeholder injected by nvcc mangling.

    For non-QUDA or already-clean names neither pass fires, so this is a
    no-op for generic CUDA kernels.
    """
    name = re.sub(r"^.*?void>::type\s+", "", name)
    name = re.sub(r"\s*\(T2\)\s*$", "", name)
    return name.strip()
