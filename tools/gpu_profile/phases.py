"""Phase detection: partition a profile timeline into non-overlapping sequential phases.

Algorithm (distribution-based):
1. Compute profile bounds from all event tables.
2. Build a kernel vocabulary: top _TOP_K kernels by total GPU time (demangled names).
3. Bin the timeline into fixed-width windows; aggregate kernel and memcpy GPU time per bin.
4. Normalize each bin into a probability distribution over the vocabulary (active bins);
   at the segment level, idle bins contribute an "__idle__" token so GPU utilization
   is implicitly encoded in the distribution.
5. Collect candidate phase boundaries from:
   - Adjacent-bin JS divergence peaks (top _N_CANDIDATES_FACTOR × max_phases pairs)
   - Active/idle transition edges (guaranteed capture of GPU-idle stretches)
   - Start/end of marker top-level ranges that appear <= max_phases times
   - End-of-cluster timestamps from MPI_Barrier bursts
   - GPU kernel MIN(start) / MAX(end)
6. Merge nearby boundary candidates (within 50ms or 0.5% of profile span);
   lower-priority candidates are discarded, no averaging.
7. Fingerprint each segment: dominant kernel, total kernel time, kernel distribution.
8. Pre-pass: merge adjacent segments with JS divergence < _PREPASS_THRESHOLD.
9. Optimal k-segmentation via DP: globally optimal partition; k selected by elbow on cost curve.
10. Label each segment using marker coverage, then GPU activity patterns.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .base import Profile

from ._utils import _normalize_demangled

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOP_K = 20
_N_BINS = 500
_BIN_WIDTH_FLOOR_NS = 50_000_000  # 50 ms
_BIN_WIDTH_CEIL_NS = 500_000_000  # 500 ms
_N_CANDIDATES_FACTOR = 5
_PREPASS_THRESHOLD = 0.10
_DP_ELBOW_THRESHOLD = 0.05  # min fractional cost reduction to justify one more phase
_IDLE_LABEL_UTIL_THRESHOLD = 1.0  # gpu_util% below which a segment is labeled "idle"

# Source priorities for candidate boundaries (higher = more authoritative).
# When two candidates are within the merge tolerance, the lower-priority one
# is discarded so the surviving boundary stays at an actual event timestamp.
_PRI_DIST = 2  # distribution-detected and idle-transition boundaries
_PRI_MPI = 2  # end of an MPI_Barrier cluster
_PRI_MARKER = 3  # marker range start/end (NVTX or rocTX)
_PRI_GPU_EDGE = 4  # first/last kernel timestamp

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PhaseWindow:
    """A named, non-overlapping time window representing one execution phase."""

    name: str
    start_ns: int
    end_ns: int


@dataclass
class _Seg:
    start_ns: int
    end_ns: int
    kernel_ns: int
    dominant_kernel: str | None
    distribution: dict[str, float] = field(default_factory=dict)

    @property
    def duration_ns(self) -> int:
        return self.end_ns - self.start_ns

    @property
    def gpu_util(self) -> float:
        return 100.0 * self.kernel_ns / self.duration_ns if self.duration_ns > 0 else 0.0


@dataclass
class _PhaseState:
    """Compact intermediate state cached between analysis passes in multi-rank mode.

    Stores the pre-pass-merged segment list and DP tables so that
    ``_finalize_from_state`` can produce labeled PhaseWindows for any k without
    re-loading the profile or re-running the O(n²) fingerprinting step.
    Peak size is O(n_segs × K) — a few KB per rank at most.
    """

    segs: list[_Seg]  # pre-pass-merged segments (typically 10–100)
    all_markers: list[tuple[int, int, str]]  # long marker ranges for labeling
    dp: list[list[float]]  # DP cost table (K+1 × n_segs); [] if trivial
    split: list[list[int]]  # DP split table (K+1 × n_segs); [] if trivial
    K: int  # effective max k used in DP
    costs: list[float]  # dp[k][n_segs-1] for k=1..K
    best_k: int  # elbow-selected k (per-rank)


# ---------------------------------------------------------------------------
# Profile bounds — delegate to Profile Protocol
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Vocabulary and binning
# ---------------------------------------------------------------------------


def _kernel_vocab(kernel_evts: list, top_k: int) -> list[str]:
    """Return the top_k kernel demangled names by total GPU time across the profile."""
    by_name: dict[str, int] = {}
    for e in kernel_evts:
        norm = _normalize_demangled(e.name)
        by_name[norm] = by_name.get(norm, 0) + e.duration_ns
    return [n for n, _ in sorted(by_name.items(), key=lambda x: x[1], reverse=True)[:top_k]]


def _bin_profile(
    kernel_evts: list,
    memcpy_evts: list,
    t0: int,
    t1: int,
    bin_width_ns: int,
) -> list[dict[str, int]]:
    """Aggregate kernel and memcpy GPU time into fixed-width time bins.

    Center-based attribution: a kernel/transfer whose midpoint (start+end)/2
    falls in bin i is attributed entirely to bin i. Returns a list of raw
    dicts: bins[i] maps demangled kernel name (or "__memcpy__") to nanoseconds.
    Bins with no activity are empty dicts.
    """
    n_bins = math.ceil((t1 - t0) / bin_width_ns)
    bins: list[dict[str, int]] = [{} for _ in range(n_bins)]

    for e in kernel_evts:
        mid = (e.start_ns + e.end_ns) // 2
        if t0 <= mid < t1:
            idx = (mid - t0) // bin_width_ns
            if 0 <= idx < n_bins:
                name = _normalize_demangled(e.name)
                bins[idx][name] = bins[idx].get(name, 0) + e.duration_ns

    for e in memcpy_evts:
        if e.start_ns is None or e.end_ns is None:
            continue
        mid = (e.start_ns + e.end_ns) // 2
        if t0 <= mid < t1:
            idx = (mid - t0) // bin_width_ns
            if 0 <= idx < n_bins:
                bins[idx]["__memcpy__"] = bins[idx].get("__memcpy__", 0) + e.duration_ns

    return bins


# ---------------------------------------------------------------------------
# Feature vectors and JS divergence
# ---------------------------------------------------------------------------


def _make_distribution(
    bin_data: dict[str, int],
    vocab: list[str],
) -> dict[str, float]:
    """Normalize a raw bin dict into a probability distribution over vocab.

    Vocab kernels, "__memcpy__", "__idle__" (empty-bin time), and "__other__"
    (everything outside the vocab) each receive a share of total time.
    Only non-zero shares are included (sparse representation).
    Bins with no activity and no idle marker return {}.
    """
    total_ns = sum(bin_data.values())
    if total_ns == 0:
        return {}
    vocab_set = set(vocab)
    dist: dict[str, float] = {}
    other_ns = 0
    for name, ns in bin_data.items():
        if name in ("__idle__", "__memcpy__"):
            dist[name] = ns / total_ns
        elif name in vocab_set:
            dist[name] = ns / total_ns
        else:
            other_ns += ns
    if other_ns:
        dist["__other__"] = other_ns / total_ns
    return dist


def _js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Jensen-Shannon divergence between two sparse probability distributions.

    Returns a value in [0, 1] (log base 2). Two empty dicts → 0.0.
    One empty and one non-empty → 1.0.
    """
    if not p and not q:
        return 0.0
    if not p or not q:
        return 1.0
    all_keys = set(p) | set(q)
    m = {k: (p.get(k, 0.0) + q.get(k, 0.0)) / 2.0 for k in all_keys}
    kl_p = sum(p[k] * math.log2(p[k] / m[k]) for k in p if p[k] > 0)
    kl_q = sum(q[k] * math.log2(q[k] / m[k]) for k in q if q[k] > 0)
    return (kl_p + kl_q) / 2.0


# ---------------------------------------------------------------------------
# Boundary candidate sources
# ---------------------------------------------------------------------------


def _distribution_boundaries(
    dists: list[dict[str, float]],
    t0: int,
    bin_width_ns: int,
    n_candidates: int,
) -> list[tuple[int, int]]:
    """Return boundary candidates from distribution divergence peaks and idle transitions.

    Combines Step 5a (top JS divergence peaks between adjacent bins) and Step 5b
    (active/idle transition edges). Returns (timestamp_ns, priority) pairs.
    """
    tagged: list[tuple[int, int]] = []

    # Step 5a: top n_candidates adjacent-bin divergence peaks
    divergences = [(i, _js_divergence(dists[i], dists[i + 1])) for i in range(len(dists) - 1)]
    divergences.sort(key=lambda x: x[1], reverse=True)
    for i, _ in divergences[:n_candidates]:
        tagged.append((t0 + (i + 1) * bin_width_ns, _PRI_DIST))

    # Step 5b: active/idle transition boundaries (guaranteed capture)
    for i in range(1, len(dists)):
        was_idle = not bool(dists[i - 1])
        is_idle = not bool(dists[i])
        if not was_idle and is_idle:
            tagged.append((t0 + i * bin_width_ns, _PRI_DIST))
        elif was_idle and not is_idle:
            tagged.append((t0 + i * bin_width_ns, _PRI_DIST))

    return tagged


def _marker_phase_boundaries(
    profile: Profile,
    span_ns: int,
    max_phases: int,
) -> tuple[list[int], list[tuple[int, int, str]]]:
    """Return (boundary_timestamps, all_long_marker_ranges_for_labeling).

    Only ranges that appear <= max_phases times contribute boundaries;
    frequently-repeated ranges are iterations, not phase transitions.
    The duration filter is pushed into SQL so we never materialise the full
    marker table in Python.
    """
    if not profile.capabilities.has_markers:
        return [], []

    min_dur_ns = max(int(span_ns * 0.02), 100_000_000)  # >= 2% of span or >= 100ms
    long_rows = profile.long_marker_ranges(min_duration_ns=min_dur_ns, limit=200)
    if not long_rows:
        return [], []

    all_long = [(r.start_ns, r.end_ns, r.name) for r in long_rows]
    top_level = [
        (s, e, n)
        for i, (s, e, n) in enumerate(all_long)
        if not any(
            j != i and all_long[j][0] <= s and all_long[j][1] >= e for j in range(len(all_long))
        )
    ]
    name_counts: Counter[str] = Counter(n for _, _, n in top_level)
    boundaries = [ts for s, e, n in top_level if name_counts[n] <= max_phases for ts in (s, e)]
    return boundaries, all_long


def _mpi_cluster_boundaries(profile: Profile) -> list[int]:
    """Return end-of-cluster timestamps for MPI_Barrier bursts.

    Only Barrier end timestamps are fetched from SQL — the rest of the MPI
    table (typically dominated by P2P sends/recvs) is never materialised.
    """
    if not profile.capabilities.has_mpi:
        return []
    ends = profile.mpi_event_ends_by_name("MPI_Barrier")
    if not ends:
        return []
    boundaries: list[int] = []
    cluster_end = ends[0]
    for t in ends[1:]:
        if t - cluster_end > 500_000_000:  # 500ms gap = new cluster
            boundaries.append(cluster_end)
        cluster_end = t
    boundaries.append(cluster_end)
    return boundaries


def _merge_nearby(tagged: list[tuple[int, int]], tolerance_ns: int) -> list[int]:
    """Collapse tagged candidates within tolerance_ns of each other.

    Each element is (timestamp_ns, priority). When two candidates are within
    tolerance, the lower-priority one is discarded; ties keep the existing
    entry. No new synthetic timestamps are introduced.
    """
    if not tagged:
        return []
    result: list[tuple[int, int]] = [min(tagged, key=lambda x: x[0])]
    for ts, pri in sorted(tagged, key=lambda x: x[0])[1:]:
        last_ts, last_pri = result[-1]
        if ts - last_ts <= tolerance_ns:
            if pri > last_pri:
                result[-1] = (ts, pri)
        else:
            result.append((ts, pri))
    return [ts for ts, _ in result]


# ---------------------------------------------------------------------------
# Segment fingerprinting and merging
# ---------------------------------------------------------------------------


def _fingerprint(
    kernel_evts: list,
    start_ns: int,
    end_ns: int,
    bins: list[dict[str, int]],
    t0: int,
    bin_width_ns: int,
    vocab: list[str],
) -> _Seg:
    """Fingerprint a time segment: kernel_ns, dominant kernel, and distribution.

    kernel_ns uses clamped overlap for accuracy. distribution is computed from
    pre-loaded bin data via center-based attribution. dominant_kernel uses the
    short name (for labeling readability, not analysis precision).
    """
    # Total GPU time: clamped overlap so boundary-straddling kernels contribute partially
    overlapping = [e for e in kernel_evts if e.start_ns < end_ns and e.end_ns > start_ns]
    kernel_ns = sum(min(e.end_ns, end_ns) - max(e.start_ns, start_ns) for e in overlapping)

    # Dominant kernel: short name whose center falls inside the segment
    in_center = [
        e
        for e in kernel_evts
        if (e.start_ns + e.end_ns) // 2 >= start_ns and (e.start_ns + e.end_ns) // 2 < end_ns
    ]
    by_short: dict[str, int] = {}
    for e in in_center:
        n = e.short_name or e.name
        by_short[n] = by_short.get(n, 0) + e.duration_ns
    dominant_kernel = max(by_short, key=by_short.__getitem__) if by_short else None

    # Distribution: aggregate bins whose center falls inside the segment.
    # Idle bins contribute __idle__ time so utilization is encoded implicitly.
    combined: dict[str, int] = {}
    first_bin = max(0, int((start_ns - t0) / bin_width_ns))
    last_bin = min(len(bins) - 1, int((end_ns - t0 - 1) / bin_width_ns) + 1)
    for i in range(first_bin, last_bin):
        bin_center = t0 + (i + 0.5) * bin_width_ns
        if start_ns <= bin_center < end_ns:
            if bins[i]:
                for k, v in bins[i].items():
                    combined[k] = combined.get(k, 0) + v
            else:
                combined["__idle__"] = combined.get("__idle__", 0) + bin_width_ns
    distribution = _make_distribution(combined, vocab)

    return _Seg(
        start_ns=start_ns,
        end_ns=end_ns,
        kernel_ns=kernel_ns,
        dominant_kernel=dominant_kernel,
        distribution=distribution,
    )


def _similarity(a: _Seg, b: _Seg) -> float:
    """JS-based similarity between two segments (1.0 = identical, 0.0 = maximally different)."""
    return 1.0 - _js_divergence(a.distribution, b.distribution)


def _merge_segs(a: _Seg, b: _Seg) -> _Seg:
    total_kns = a.kernel_ns + b.kernel_ns
    dk = a.dominant_kernel if a.kernel_ns >= b.kernel_ns else b.dominant_kernel
    dur_a, dur_b = a.duration_ns, b.duration_ns
    total_dur = dur_a + dur_b
    if total_dur == 0:
        merged_dist: dict[str, float] = {}
    else:
        all_keys = set(a.distribution) | set(b.distribution)
        merged_dist = {
            k: (a.distribution.get(k, 0.0) * dur_a + b.distribution.get(k, 0.0) * dur_b) / total_dur
            for k in all_keys
        }
    return _Seg(
        start_ns=a.start_ns,
        end_ns=b.end_ns,
        kernel_ns=total_kns,
        dominant_kernel=dk,
        distribution=merged_dist,
    )


# ---------------------------------------------------------------------------
# Labeling
# ---------------------------------------------------------------------------


def _label(seg: _Seg, marker_ranges: list[tuple[int, int, str]]) -> str:
    """Choose a human-readable label: marker coverage first, then activity pattern.

    Aggregates overlap across all ranges sharing the same name, so that a phase
    covered by many repeated short ranges (e.g., 24 solver iterations) is still
    correctly labeled by that range's name.
    """
    window = seg.end_ns - seg.start_ns
    coverage: dict[str, int] = {}
    for rs, re, rn in marker_ranges:
        overlap = max(0, min(re, seg.end_ns) - max(rs, seg.start_ns))
        coverage[rn] = coverage.get(rn, 0) + overlap
    if coverage:
        best_name = max(coverage, key=lambda n: coverage[n])
        if coverage[best_name] >= 0.3 * window:
            return best_name
    if seg.gpu_util < _IDLE_LABEL_UTIL_THRESHOLD:
        return "idle"
    if seg.dominant_kernel:
        return seg.dominant_kernel
    return "unknown"


def _deduplicate_names(phases: list[PhaseWindow]) -> list[PhaseWindow]:
    counts: Counter[str] = Counter(p.name for p in phases)
    seen: Counter[str] = Counter()
    result = []
    for p in phases:
        if counts[p.name] > 1:
            seen[p.name] += 1
            result.append(PhaseWindow(f"{p.name} ({seen[p.name]})", p.start_ns, p.end_ns))
        else:
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Core pipeline: expensive half (steps 1–9) and fast half (traceback + labeling)
# ---------------------------------------------------------------------------


def _compute_phase_state(
    profile: Profile,
    max_phases: int,
    verbose: bool = False,
    rank: int | None = None,
) -> _PhaseState | None:
    """Run steps 1–9 and return compact state for deferred finalization.

    Returns None for empty profiles or when max_phases <= 1 (caller falls back
    to a single PhaseWindow).  All expensive work — event loading, binning,
    O(n_kernels × n_segments) fingerprinting, and O(n_segs² × K) DP — lives here.
    The returned _PhaseState is a few KB; it does NOT hold the raw event lists.
    """
    tag = f"[phase rank={rank}]" if rank is not None else "[phase]"

    def _s(ns: int) -> str:
        return f"{ns / 1e9:.3f}s"

    # Pre-load kernel and memcpy events once; phase fingerprinting needs random
    # access into them.  Marker and MPI tables are accessed via narrow SQL
    # fetchers below to avoid materialising millions of rows on heavy-MPI
    # rocprof-sys profiles.
    kernel_evts = profile.kernel_events()
    memcpy_evts = profile.memcpy_events()

    # Step 1 — Profile bounds
    t0, t1 = profile.profile_bounds_ns()
    if verbose:
        print(
            f"{tag} Step 1 — Find the earliest and latest event timestamps across all "
            f"tables to establish the profile time range.\n"
            f"         t0={_s(t0)}, t1={_s(t1)}, span={_s(t1 - t0)}"
        )
    if t0 == 0 and t1 == 0:
        return None
    if max_phases <= 1:
        return None

    span_ns = t1 - t0
    tolerance_ns = max(5_000_000, int(span_ns * 0.005))

    # Step 2 — Kernel vocabulary
    vocab = _kernel_vocab(kernel_evts, _TOP_K)
    if verbose:
        preview = vocab[:3]
        suffix = f" ... ({len(vocab) - 3} more)" if len(vocab) > 3 else ""
        print(
            f"{tag} Step 2 — Rank all kernels by total GPU time and take the top {_TOP_K} "
            f"demangled names as the feature vocabulary.\n"
            f"         {len(vocab)} kernels: {preview}{suffix}"
        )

    # Step 3 — Bin the timeline
    bin_width_ns = max(_BIN_WIDTH_FLOOR_NS, min(_BIN_WIDTH_CEIL_NS, span_ns // _N_BINS))
    bins = _bin_profile(kernel_evts, memcpy_evts, t0, t1, bin_width_ns)
    if verbose:
        n_active = sum(1 for b in bins if b)
        print(
            f"{tag} Step 3 — Divide the timeline into fixed-width bins and aggregate kernel "
            f"and memcpy GPU time per bin using center-based attribution.\n"
            f"         {len(bins)} bins × {bin_width_ns / 1e6:.1f}ms, {n_active} active"
        )

    # Step 4 — Feature vectors
    dists = [_make_distribution(b, vocab) for b in bins]
    if verbose:
        n_idle = sum(1 for d in dists if not d)
        print(
            f"{tag} Step 4 — Normalize each bin's raw GPU time into a probability "
            f"distribution over the vocabulary; idle bins become empty dicts.\n"
            f"         {n_idle}/{len(dists)} idle bins"
        )

    # Step 5 — Collect candidate boundaries
    tagged: list[tuple[int, int]] = []
    n_candidates = _N_CANDIDATES_FACTOR * max_phases
    dist_candidates = _distribution_boundaries(dists, t0, bin_width_ns, n_candidates)
    tagged.extend(dist_candidates)
    marker_boundaries, all_markers = _marker_phase_boundaries(profile, span_ns, max_phases)
    tagged.extend((t, _PRI_MARKER) for t in marker_boundaries)
    mpi_bounds = _mpi_cluster_boundaries(profile)
    tagged.extend((t, _PRI_MPI) for t in mpi_bounds)
    gpu_tagged: list[tuple[int, int]] = []
    if kernel_evts:
        gpu_start = min(e.start_ns for e in kernel_evts)
        gpu_end = max(e.end_ns for e in kernel_evts)
        gpu_tagged.append((gpu_start, _PRI_GPU_EDGE))
        gpu_tagged.append((gpu_end, _PRI_GPU_EDGE))
    tagged.extend(gpu_tagged)
    if verbose:
        display: list[tuple[int, int, str]] = (
            [(ts, pri, "dist") for ts, pri in dist_candidates]
            + [(t, _PRI_MARKER, "markers") for t in marker_boundaries]
            + [(t, _PRI_MPI, "mpi") for t in mpi_bounds]
            + [(ts, pri, "gpu") for ts, pri in gpu_tagged]
        )
        display.sort(key=lambda x: x[0])
        print(
            f"{tag} Step 5 — Collect candidate phase boundaries from JS divergence peaks, "
            f"active/idle transitions, marker ranges, MPI barriers, and GPU activity edges.\n"
            f"         {len(tagged)} raw candidates "
            f"(dist={len(dist_candidates)}, markers={len(marker_boundaries)}, "
            f"mpi={len(mpi_bounds)}, gpu={len(gpu_tagged)}):"
        )
        for ts, pri, src in display:
            print(f"           {_s(ts)}  pri={pri}  [{src}]")

    # Step 6 — Merge nearby candidates
    tagged = [
        (c, p) for c, p in tagged if t0 < c < t1 and c - t0 > tolerance_ns and t1 - c > tolerance_ns
    ]
    boundaries = sorted(set([t0] + _merge_nearby(tagged, tolerance_ns) + [t1]))
    if verbose:
        b_s = [f"{_s(b)}" for b in boundaries]
        print(
            f"{tag} Step 6 — Collapse candidates within {_s(tolerance_ns)} of each other, "
            f"keeping the higher-priority timestamp; drop candidates too close to profile edges.\n"
            f"         {len(boundaries)} boundaries: {b_s}"
        )

    # Step 7 — Fingerprint segments
    segs = [
        _fingerprint(kernel_evts, boundaries[i], boundaries[i + 1], bins, t0, bin_width_ns, vocab)
        for i in range(len(boundaries) - 1)
        if boundaries[i + 1] > boundaries[i]
    ]
    if not segs:
        return None
    if verbose:
        print(
            f"{tag} Step 7 — Compute each segment's total kernel time, dominant kernel, "
            f"and kernel distribution fingerprint.\n"
            f"         {len(segs)} initial segments:"
        )
        for i, s in enumerate(segs):
            print(
                f"           [{i}] {_s(s.start_ns)}–{_s(s.end_ns)}  "
                f"gpu_util={s.gpu_util:.1f}%  dominant={s.dominant_kernel!r}"
            )

    # Step 8 — Pre-pass: merge nearly identical adjacent segments
    if verbose:
        print(
            f"{tag} Step 8 — Unconditionally merge adjacent segment pairs whose JS divergence "
            f"is below {_PREPASS_THRESHOLD} (same bottleneck structure); repeat until stable."
        )
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(segs) - 1:
            js = _js_divergence(segs[i].distribution, segs[i + 1].distribution)
            if js < _PREPASS_THRESHOLD:
                if verbose:
                    print(
                        f"           merge segs[{i}]+[{i + 1}] "
                        f"(js={js:.3f})  {len(segs)} → {len(segs) - 1} segments"
                    )
                segs = segs[:i] + [_merge_segs(segs[i], segs[i + 1])] + segs[i + 2 :]
                changed = True
            else:
                i += 1
    if verbose:
        print(f"         {len(segs)} segments after pre-pass:")
        for i, s in enumerate(segs):
            print(
                f"           [{i}] {_s(s.start_ns)}–{_s(s.end_ns)}  "
                f"gpu_util={s.gpu_util:.1f}%  dominant={s.dominant_kernel!r}"
            )

    # Step 9 — Optimal k-segmentation via DP
    n_segs = len(segs)
    K = min(max_phases, n_segs)
    if verbose:
        print(
            f"{tag} Step 9 — Optimal k-segmentation: globally optimal partition of "
            f"{n_segs} segments into at most {max_phases} phases via dynamic programming."
        )

    if n_segs <= 1 or K < 2:
        if verbose:
            print(f"         {n_segs} segment(s) — no merging required")
        return _PhaseState(
            segs=segs,
            all_markers=all_markers,
            dp=[],
            split=[],
            K=n_segs,
            costs=[],
            best_k=n_segs,
        )

    # Precompute cost matrix: C[a][b] = duration-weighted JS inertia of segs[a..b]
    C: list[list[float]] = [[0.0] * n_segs for _ in range(n_segs)]
    for a in range(n_segs):
        merged_ab = segs[a]
        for b in range(a + 1, n_segs):
            merged_ab = _merge_segs(merged_ab, segs[b])
            C[a][b] = sum(
                segs[i].duration_ns * _js_divergence(segs[i].distribution, merged_ab.distribution)
                for i in range(a, b + 1)
            )

    # DP: dp[k][i] = min cost of partitioning segs[0..i] into k contiguous groups
    INF = float("inf")
    dp = [[INF] * n_segs for _ in range(K + 1)]
    split = [[-1] * n_segs for _ in range(K + 1)]
    for i in range(n_segs):
        dp[1][i] = C[0][i]
        split[1][i] = 0
    for k in range(2, K + 1):
        for i in range(k - 1, n_segs):
            for m in range(k - 1, i + 1):
                prev = dp[k - 1][m - 1] if m > 0 else 0.0
                c = prev + C[m][i]
                if c < dp[k][i]:
                    dp[k][i] = c
                    split[k][i] = m

    # Select k via elbow: add a phase only if its marginal gain >= _DP_ELBOW_THRESHOLD
    costs = [dp[k][n_segs - 1] for k in range(1, K + 1)]
    total_range = costs[0] - costs[-1]
    best_k = 1
    if total_range > 0:
        for k in range(2, K + 1):
            gain = (costs[k - 2] - costs[k - 1]) / total_range
            if gain >= _DP_ELBOW_THRESHOLD:
                best_k = k

    if verbose:
        cost_str = "   ".join(f"k={k}: {costs[k - 1]:.3e}" for k in range(1, K + 1))
        print(f"         Cost curve: {cost_str}")
        if total_range > 0:
            gain_str = "   ".join(
                f"k={k}: {100 * (costs[k - 2] - costs[k - 1]) / total_range:.1f}%"
                for k in range(2, K + 1)
            )
            print(
                f"         Marginal gains: {gain_str}"
                f"   (threshold: {100 * _DP_ELBOW_THRESHOLD:.0f}%)"
            )
        print(f"         Selected k={best_k}")

    return _PhaseState(
        segs=segs,
        all_markers=all_markers,
        dp=dp,
        split=split,
        K=K,
        costs=costs,
        best_k=best_k,
    )


def _finalize_from_state(
    state: _PhaseState,
    max_phases: int,
    forced_k: int | None = None,
    verbose: bool = False,
    rank: int | None = None,
) -> list[PhaseWindow]:
    """Run DP traceback and labeling from pre-computed state (steps 9b + 10).

    O(n_segs × k) — fast; no profile access required.
    """
    tag = f"[phase rank={rank}]" if rank is not None else "[phase]"

    def _s(ns: int) -> str:
        return f"{ns / 1e9:.3f}s"

    segs = state.segs

    # Trivial case: no DP was run (single segment or K < 2)
    if not state.dp:
        phases = [PhaseWindow(_label(s, state.all_markers), s.start_ns, s.end_ns) for s in segs]
        return _deduplicate_names(phases)

    n_segs = len(segs)
    K = state.K
    best_k = state.best_k

    if forced_k is not None:
        _forced_clamped = max(1, min(forced_k, K))
        if verbose and _forced_clamped != best_k:
            print(
                f"{tag}         forced_k={forced_k} overrides"
                f" elbow k={best_k} → using k={_forced_clamped}"
            )
        best_k = _forced_clamped

    # Traceback: recover the optimal partition boundaries
    groups: list[tuple[int, int]] = []
    idx = n_segs - 1
    k = best_k
    while k > 0:
        m = state.split[k][idx]
        groups.append((m, idx))
        idx = m - 1
        k -= 1
    groups.reverse()

    if verbose:
        for a, b in groups:
            seg_range = f"segs[{a}]" if a == b else f"segs[{a}..{b}]"
            print(f"           {seg_range}  {_s(segs[a].start_ns)}–{_s(segs[b].end_ns)}")

    # Merge each group into a single _Seg
    merged_segs: list[_Seg] = []
    for a, b in groups:
        seg = segs[a]
        for j in range(a + 1, b + 1):
            seg = _merge_segs(seg, segs[j])
        merged_segs.append(seg)

    # Step 10 — Label and deduplicate
    phases = [PhaseWindow(_label(s, state.all_markers), s.start_ns, s.end_ns) for s in merged_segs]
    result = _deduplicate_names(phases)

    if verbose:
        print(
            f"{tag} Step 10 — Assign a human-readable label to each segment using marker "
            f"coverage, dominant kernel, or idle/unknown fallbacks.\n"
            f"         {len(result)} labeled phases:"
        )
        for i, p in enumerate(result):
            sim_str = ""
            if i < len(merged_segs) - 1:
                sim = _similarity(merged_segs[i], merged_segs[i + 1])
                sim_str = f"  → sim_next={sim:.3f}"
            print(f"           {p.name!r}  {_s(p.start_ns)}–{_s(p.end_ns)}{sim_str}")

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_phases(
    profile: Profile,
    max_phases: int = 6,
    verbose: bool = False,
    rank: int | None = None,
    forced_k: int | None = None,
) -> list[PhaseWindow]:
    """Detect a flat, ordered, non-overlapping sequence of phases.

    Returns at most `max_phases` PhaseWindow objects covering the full profile span.
    Set max_phases=1 to skip segmentation and return a single phase.
    """
    state = _compute_phase_state(profile, max_phases, verbose=verbose, rank=rank)
    if state is None:
        t0, t1 = profile.profile_bounds_ns()
        if t0 == 0 and t1 == 0:
            return [PhaseWindow("unknown", 0, 0)]
        return [PhaseWindow("profile", t0, t1)]
    return _finalize_from_state(state, max_phases, forced_k=forced_k, verbose=verbose, rank=rank)


def compute_phase_state_and_cost_curve(
    profile: Profile,
    max_phases: int = 10,
    rank: int | None = None,
) -> tuple[_PhaseState | None, int, dict[int, float]]:
    """Run phase detection through k-selection; return state, selected_k, and cost_curve.

    The returned ``_PhaseState`` can be passed to ``finalize_phases_from_state`` to
    produce labeled PhaseWindows for any k without re-loading the profile or
    re-running the expensive fingerprinting and DP steps.
    """
    state = _compute_phase_state(profile, max_phases, verbose=False, rank=rank)
    if state is None or not state.costs:
        return None, 1, {1: 0.0}
    return state, state.best_k, {k: state.costs[k - 1] for k in range(1, state.K + 1)}


def finalize_phases_from_state(
    state: _PhaseState | None,
    max_phases: int = 10,
    forced_k: int | None = None,
) -> list[PhaseWindow]:
    """Traceback and label phases from a pre-computed ``_PhaseState``.

    Does not require the profile to be open.  O(n_segs × k) — fast.
    Returns a single ``PhaseWindow("profile", 0, 0)`` if state is None.
    """
    if state is None:
        return [PhaseWindow("profile", 0, 0)]
    return _finalize_from_state(state, max_phases, forced_k=forced_k, verbose=False, rank=None)
