"""Cross-rank analysis for multi-rank MPI profiles.

Provides utilities to:
  - Parse rank IDs from a set of filenames
  - Select the primary (outlier) rank
  - Align execution phases across ranks
  - Compute cross-rank imbalance metrics
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path

from .models import (
    CollectiveImbalance,
    CrossRankPhaseSummary,
    CrossRankSummary,
    ProfileSummary,
    RankOverview,
    RankPhaseStats,
)
from .phases import _DP_ELBOW_THRESHOLD

# A rank is considered an outlier if its GPU idle time exceeds the median by
# more than this fraction.
OUTLIER_IDLE_THRESHOLD = 0.20

# Phases are considered duration-matched (for index-order fallback) if every
# rank's phase duration is within this fraction of the cross-rank mean.
PHASE_DURATION_TOLERANCE = 0.20


# ---------------------------------------------------------------------------
# Rank ID parsing
# ---------------------------------------------------------------------------


def parse_rank_ids(paths: list[Path]) -> tuple[list[int], bool]:
    """Derive rank IDs from a list of profile file paths.

    Strategy: extract all integers from each filename, then find which
    positional slot varies across the set.  If exactly one slot varies,
    use those values as rank IDs.  Otherwise fall back to [0, 1, 2, …].

    Returns (rank_ids, parsed_ok) where parsed_ok is False when the
    fallback was used.
    """
    names = [p.stem for p in paths]
    # Extract all non-negative integers from each stem, in order.
    int_seqs: list[list[int]] = [[int(m) for m in re.findall(r"\d+", name)] for name in names]

    # All stems must yield the same number of integer tokens to compare slots.
    lengths = {len(seq) for seq in int_seqs}
    if len(lengths) == 1 and lengths != {0}:
        n_slots = lengths.pop()
        varying = [i for i in range(n_slots) if len({seq[i] for seq in int_seqs}) > 1]
        if len(varying) == 1:
            slot = varying[0]
            return [seq[slot] for seq in int_seqs], True

    # Fallback: index order
    return list(range(len(paths))), False


# ---------------------------------------------------------------------------
# Primary rank selection
# ---------------------------------------------------------------------------


def select_primary_rank(
    summaries: dict[int, ProfileSummary],
) -> tuple[int, str]:
    """Choose the primary (outlier) rank based on GPU idle time.

    Returns (rank_id, reason) where reason is a human-readable string
    suitable for printing to the user.
    """
    idle_by_rank = {rid: s.total_gpu_idle_s for rid, s in summaries.items()}
    rank_ids = sorted(idle_by_rank)
    idle_values = [idle_by_rank[r] for r in rank_ids]
    med = statistics.median(idle_values)

    if med > 0:
        outliers = [r for r in rank_ids if idle_by_rank[r] > med * (1 + OUTLIER_IDLE_THRESHOLD)]
    else:
        outliers = []

    if outliers:
        primary = max(outliers, key=lambda r: idle_by_rank[r])
        idle = idle_by_rank[primary]
        pct_above = 100.0 * (idle - med) / med
        reason = (
            f"GPU idle {idle:.1f}s vs. median {med:.1f}s across ranks "
            f"({pct_above:.0f}% above median)"
        )
        return primary, reason

    # No clear outlier — use the lowest rank ID.
    primary = rank_ids[0]
    reason = (
        f"no clear outlier (all ranks within {int(OUTLIER_IDLE_THRESHOLD * 100)}%"
        f" of median GPU idle {med:.1f}s) — defaulting to rank {primary}"
    )
    return primary, reason


# ---------------------------------------------------------------------------
# Phase alignment
# ---------------------------------------------------------------------------


def align_phases(
    summaries: dict[int, ProfileSummary],
) -> tuple[str, str | None]:
    """Check that phases are consistent across ranks.

    Returns (alignment_mode, message) where:
      - alignment_mode is one of:
          "name_match"     — all ranks agree on phase names; proceed normally
          "index_order"    — names differ but durations match; use index order
          "failed"         — alignment cannot be established; abort cross-rank
      - message is None on success, or a human-readable description of the
        problem (and how the program will proceed) for display to the user.
    """
    rank_ids = sorted(summaries)
    phase_name_lists = {rid: [p.name for p in summaries[rid].phases] for rid in rank_ids}
    phase_counts = {rid: len(names) for rid, names in phase_name_lists.items()}

    # --- Check 1: all ranks must have the same number of phases ---
    if len(set(phase_counts.values())) > 1:
        detail_lines = [f"  rank {r}: {phase_counts[r]} phases" for r in rank_ids]
        detail = "\n".join(detail_lines)
        msg = "Phase count differs across ranks — cross-rank analysis cannot proceed.\n" + detail
        return "failed", msg

    # --- Check 2: phase names ---
    reference_names = phase_name_lists[rank_ids[0]]
    names_match = all(phase_name_lists[r] == reference_names for r in rank_ids[1:])

    # --- Check 3: duration divergence (always run) ---
    n_phases = phase_counts[rank_ids[0]]
    duration_warn: str | None = None
    for phase_idx in range(n_phases):
        durations = [summaries[r].phases[phase_idx].duration_s for r in rank_ids]
        mean_dur = statistics.mean(durations)
        if mean_dur <= 0:
            continue
        if any(abs(d - mean_dur) / mean_dur > PHASE_DURATION_TOLERANCE for d in durations):
            worst_rank = max(
                rank_ids,
                key=lambda r: abs(summaries[r].phases[phase_idx].duration_s - mean_dur) / mean_dur,
            )
            worst_dur = summaries[worst_rank].phases[phase_idx].duration_s
            if names_match:
                duration_warn = (
                    f"Phase {phase_idx} durations diverge beyond "
                    f"{int(PHASE_DURATION_TOLERANCE * 100)}% tolerance "
                    f"(rank {worst_rank}: {worst_dur:.2f}s vs. mean {mean_dur:.2f}s) — "
                    f"phase alignment may be unreliable despite matching names."
                )
                break
            else:
                msg = (
                    f"Phase names differ across ranks and phase {phase_idx} durations diverge "
                    f"beyond {int(PHASE_DURATION_TOLERANCE * 100)}% tolerance "
                    f"(rank {worst_rank}: {worst_dur:.2f}s vs. mean {mean_dur:.2f}s) — "
                    f"this likely indicates a phase detection artifact. "
                    f"Cross-rank analysis cannot proceed."
                )
                return "failed", msg

    if names_match:
        return "name_match", duration_warn

    # Names differ but durations agree — use index-order alignment.
    mismatched = [r for r in rank_ids[1:] if phase_name_lists[r] != reference_names]
    msg = (
        f"Phase names differ across ranks (ranks {mismatched} disagree with rank {rank_ids[0]}) "
        f"but phase durations agree within {int(PHASE_DURATION_TOLERANCE * 100)}%. "
        f"Proceeding with index-order phase alignment."
    )
    return "index_order", msg


# ---------------------------------------------------------------------------
# Consensus k selection for multi-rank phase detection
# ---------------------------------------------------------------------------

# Maximum spread between per-rank elbow-selected k values before aborting.
_K_SPREAD_THRESHOLD = 2

# Maximum fractional cost excess at consensus k vs. a rank's optimal k before aborting.
# Positive excess means consensus_k < rank's optimal k (forcing fewer phases than ideal).
_COST_EXCESS_THRESHOLD = 0.15


def select_consensus_k(
    cost_curves: dict[int, dict[int, float]],
    selected_ks: dict[int, int],
    max_phases: int,
    k_spread_threshold: int = _K_SPREAD_THRESHOLD,
    cost_excess_threshold: float = _COST_EXCESS_THRESHOLD,
    verbose: bool = False,
) -> tuple[int | None, str | None]:
    """Select a consensus k to use across all ranks for multi-rank phase detection.

    Two sequential checks guard the consensus:

    Check 1 (pre-consensus): if the spread of per-rank elbow-selected k values exceeds
    k_spread_threshold, the ranks have structurally different workloads and cross-rank
    analysis cannot proceed.

    Check 2 (post-consensus): if forcing any rank to use consensus_k results in a cost
    excess > cost_excess_threshold relative to that rank's own optimal cost, the rank's
    data does not fit well into consensus_k phases.

    Returns (consensus_k, None) on success, or (None, abort_message) on failure.
    """
    rank_ids = sorted(selected_ks)
    k_vals = [selected_ks[r] for r in rank_ids]
    k_min, k_max = min(k_vals), max(k_vals)
    spread = k_max - k_min

    if verbose:
        ks_str = "   ".join(f"rank {r}: k={selected_ks[r]}" for r in rank_ids)
        print(f"[phase consensus] Per-rank k selections: {ks_str}")

    # Check 1: pre-consensus spread
    if spread > k_spread_threshold:
        detail = "\n".join(f"  rank {r}: k={selected_ks[r]}" for r in rank_ids)
        msg = (
            f"Per-rank phase-count selections span {spread} (threshold: {k_spread_threshold}).\n"
            f"{detail}\n"
            f"This likely indicates structurally different workloads across ranks."
        )
        if verbose:
            print(
                f"[phase consensus] Spread {spread} exceeds threshold {k_spread_threshold}"
                " — aborting cross-rank analysis"
            )
        return None, msg

    if verbose:
        print(
            f"[phase consensus] Spread {spread} ≤ threshold {k_spread_threshold}"
            " — within tolerance, computing consensus"
        )

    # Fast path: all ranks agree
    if len(set(k_vals)) == 1:
        if verbose:
            print(f"[phase consensus] All ranks agree on k={k_vals[0]} — no averaging needed")
        return k_vals[0], None

    # Compute averaged cost curve over the common k range
    k_common_max = min(max(curve.keys()) for curve in cost_curves.values())
    avg_costs = [
        statistics.mean(cost_curves[r][k] for r in rank_ids if k in cost_curves[r])
        for k in range(1, k_common_max + 1)
    ]

    if verbose:
        cost_str = "   ".join(f"k={k}: {avg_costs[k - 1]:.3e}" for k in range(1, k_common_max + 1))
        print(f"[phase consensus] Averaged cost curve: {cost_str}")

    total_range = avg_costs[0] - avg_costs[-1]
    consensus_k = 1
    if total_range > 0:
        for k in range(2, k_common_max + 1):
            gain = (avg_costs[k - 2] - avg_costs[k - 1]) / total_range
            if gain >= _DP_ELBOW_THRESHOLD:
                consensus_k = k

    if verbose:
        if total_range > 0:
            gain_str = "   ".join(
                f"k={k}: {100 * (avg_costs[k - 2] - avg_costs[k - 1]) / total_range:.1f}%"
                for k in range(2, k_common_max + 1)
            )
            print(
                f"[phase consensus] Marginal gains: {gain_str}"
                f"   (threshold: {100 * _DP_ELBOW_THRESHOLD:.0f}%)"
            )
        print(f"[phase consensus] Consensus k={consensus_k}")

    # Check 2: post-consensus cost excess
    # Only applies when consensus_k < a rank's optimal k (forcing fewer phases).
    offenders: list[str] = []
    for r in rank_ids:
        opt_k = selected_ks[r]
        if consensus_k >= opt_k:
            if verbose:
                print(
                    f"[phase consensus]   rank {r}: optimal k={opt_k},"
                    f" consensus k={consensus_k} ≥ optimal → 0.0% excess"
                )
            continue
        curve = cost_curves[r]
        if consensus_k not in curve or opt_k not in curve:
            continue
        cost_at_consensus = curve[consensus_k]
        cost_at_optimal = curve[opt_k]
        if cost_at_optimal <= 0:
            continue
        excess = (cost_at_consensus - cost_at_optimal) / cost_at_optimal
        if verbose:
            print(
                f"[phase consensus]   rank {r}: optimal k={opt_k},"
                f" consensus k={consensus_k}"
                f" → {100 * excess:.1f}% cost excess"
                f" (threshold: {100 * cost_excess_threshold:.0f}%)"
            )
        if excess > cost_excess_threshold:
            offenders.append(
                f"  rank {r}: cost at k={consensus_k} is {100 * excess:.1f}% above"
                f" optimal k={opt_k} (threshold: {100 * cost_excess_threshold:.0f}%)"
            )

    if offenders:
        detail = "\n".join(offenders)
        msg = (
            f"Consensus k={consensus_k} forces poor segmentation on"
            f" {len(offenders)} rank(s):\n{detail}\n"
            f"This indicates structurally different workloads across ranks."
        )
        return None, msg

    return consensus_k, None


# ---------------------------------------------------------------------------
# Cross-rank aggregation
# ---------------------------------------------------------------------------


def _mpi_wait_s(summary: ProfileSummary, phase_idx: int) -> float:
    """Sum of all MPI op total_s for a given phase."""
    if phase_idx >= len(summary.phases):
        return 0.0
    return sum(op.total_s for op in summary.phases[phase_idx].mpi_ops)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def _imbalance(values: list[float]) -> float:
    """(max - min) / mean; 0 when mean is 0."""
    if not values:
        return 0.0
    mean = statistics.mean(values)
    if mean == 0:
        return 0.0
    return (max(values) - min(values)) / mean


def compute_cross_rank_summary(
    summaries: dict[int, ProfileSummary],
    primary_rank_id: int,
    phase_alignment: str,
) -> CrossRankSummary:
    """Compute cross-rank imbalance metrics from per-rank ProfileSummary objects."""
    rank_ids = sorted(summaries)

    # --- Per-rank overview (whole-profile) ---
    overviews = []
    for rid in rank_ids:
        s = summaries[rid]
        mpi_wait = sum(op.total_s for op in s.mpi_ops)
        overviews.append(
            RankOverview(
                rank_id=rid,
                hostname=s.device_info.hostname if s.device_info else None,
                gpu_kernel_s=s.gpu_kernel_s,
                gpu_idle_s=s.total_gpu_idle_s,
                mpi_wait_s=mpi_wait,
                gpu_utilization_pct=s.gpu_utilization_pct,
            )
        )

    # --- Derived node topology ---
    # Computed here rather than left to the model: "are these ranks co-located?"
    # is a pure function of the hostname list, and the right fix for a host-staged
    # exchange depends on the answer (peer access / IPC for GPUs sharing a node,
    # GPU-Direct RDMA once the hop crosses the network). Inferring it from timing
    # instead is unreliable — a blocking MPI_Sendrecv on a ring spends most of its
    # duration waiting for the neighbour, so the measurement tracks rank skew
    # rather than link bandwidth and can rank an intra-node exchange as the slower
    # of the two.
    hosts = {
        rid: summaries[rid].device_info.hostname if summaries[rid].device_info else None
        for rid in rank_ids
    }
    if all(h for h in hosts.values()):
        ranks_per_node: dict[str, list[int]] = {}
        for rid in rank_ids:
            ranks_per_node.setdefault(hosts[rid], []).append(rid)
        num_nodes = len(ranks_per_node)
        # Adjacent pairs only — ring and halo exchanges communicate with (r±1),
        # so this is what decides whether the exchange crosses the network.
        neighbor_colocated: bool | None = (
            all(hosts[a] == hosts[b] for a, b in zip(rank_ids, rank_ids[1:], strict=False))
            if len(rank_ids) > 1
            else None
        )
    else:
        # Partial hostnames are treated as absent: a grouping built from a subset
        # would look authoritative while being wrong about the missing ranks.
        ranks_per_node = {}
        num_nodes = None
        neighbor_colocated = None

    # --- Per-phase cross-rank stats ---
    n_phases = len(summaries[rank_ids[0]].phases)
    phase_summaries: list[CrossRankPhaseSummary] = []

    for phase_idx in range(n_phases):
        phase_name = summaries[rank_ids[0]].phases[phase_idx].name

        gpu_kernel_vals = [summaries[r].phases[phase_idx].gpu_kernel_s for r in rank_ids]
        mpi_wait_vals = [_mpi_wait_s(summaries[r], phase_idx) for r in rank_ids]

        gpu_mean = statistics.mean(gpu_kernel_vals)
        mpi_mean = statistics.mean(mpi_wait_vals)

        gpu_slowest = rank_ids[gpu_kernel_vals.index(max(gpu_kernel_vals))]
        mpi_slowest = rank_ids[mpi_wait_vals.index(max(mpi_wait_vals))]

        # Per-collective imbalance: gather all op names present across ranks
        all_ops: set[str] = set()
        for r in rank_ids:
            for op in summaries[r].phases[phase_idx].mpi_ops:
                all_ops.add(op.op)

        collective_imbalances: list[CollectiveImbalance] = []
        for op_name in sorted(all_ops):
            op_vals = []
            for r in rank_ids:
                matching = [
                    o.total_s for o in summaries[r].phases[phase_idx].mpi_ops if o.op == op_name
                ]
                op_vals.append(matching[0] if matching else 0.0)
            op_mean = statistics.mean(op_vals)
            if op_mean == 0:
                continue
            slowest_r = rank_ids[op_vals.index(max(op_vals))]
            collective_imbalances.append(
                CollectiveImbalance(
                    op=op_name,
                    imbalance_score=round(_imbalance(op_vals), 3),
                    slowest_rank_id=slowest_r,
                    mean_s=round(op_mean, 4),
                    min_s=round(min(op_vals), 4),
                    max_s=round(max(op_vals), 4),
                )
            )
        # Sort by imbalance score descending so the worst offender is first
        collective_imbalances.sort(key=lambda x: x.imbalance_score, reverse=True)

        per_rank = [
            RankPhaseStats(
                rank_id=r,
                gpu_kernel_s=round(summaries[r].phases[phase_idx].gpu_kernel_s, 4),
                gpu_idle_s=round(summaries[r].phases[phase_idx].total_gpu_idle_s, 4),
                mpi_wait_s=round(_mpi_wait_s(summaries[r], phase_idx), 4),
            )
            for r in rank_ids
        ]

        phase_summaries.append(
            CrossRankPhaseSummary(
                phase_index=phase_idx,
                phase_name=phase_name,
                gpu_kernel_mean_s=round(gpu_mean, 4),
                gpu_kernel_std_s=round(_std(gpu_kernel_vals), 4),
                gpu_kernel_min_s=round(min(gpu_kernel_vals), 4),
                gpu_kernel_max_s=round(max(gpu_kernel_vals), 4),
                gpu_kernel_imbalance=round(_imbalance(gpu_kernel_vals), 3),
                gpu_kernel_slowest_rank_id=gpu_slowest,
                mpi_wait_mean_s=round(mpi_mean, 4),
                mpi_wait_std_s=round(_std(mpi_wait_vals), 4),
                mpi_wait_min_s=round(min(mpi_wait_vals), 4),
                mpi_wait_max_s=round(max(mpi_wait_vals), 4),
                mpi_wait_imbalance=round(_imbalance(mpi_wait_vals), 3),
                mpi_wait_slowest_rank_id=mpi_slowest,
                collective_imbalance=collective_imbalances,
                per_rank=per_rank,
            )
        )

    return CrossRankSummary(
        num_ranks=len(rank_ids),
        rank_ids=rank_ids,
        primary_rank_id=primary_rank_id,
        phase_alignment=phase_alignment,
        per_rank_overview=overviews,
        phases=phase_summaries,
        num_nodes=num_nodes,
        ranks_per_node=ranks_per_node,
        neighbor_ranks_colocated=neighbor_colocated,
    )
