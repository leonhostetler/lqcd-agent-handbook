"""Compute a structured diff between two ProfileSummary objects.

compute_profile_diff() aligns kernels, memcpy kinds, and MPI ops between
two profiles, computes per-field deltas, and determines the appropriate
comparison mode:

  phase_aware       — phases match (same count + same names); full per-phase analysis
  summary           — phases differ but kernel overlap >= 20%;
                      overall comparison with per-kernel diff
  summary_no_kernel — phases differ and kernel overlap < 20%; top-level metrics only
"""

from __future__ import annotations

from pathlib import Path

from .models import (
    KernelDiff,
    MemcpyDiff,
    MpiDiff,
    PhaseDiff,
    ProfileDiff,
    ProfileSummary,
    ScalarDiff,
)

_KERNEL_OVERLAP_THRESHOLD = 20.0  # Jaccard % below which per-kernel diff is skipped


def _sdiff(a: float, b: float) -> ScalarDiff:
    delta_pct = round((b - a) / a * 100, 1) if a != 0 else None
    return ScalarDiff(a=a, b=b, delta_pct=delta_pct)


def _sdiff_opt(a: float | None, b: float | None) -> ScalarDiff | None:
    """Like _sdiff but returns None when both inputs are None.

    When only one side is None it is treated as 0.0 so the diff is still
    informative (e.g., cpu_sync_blocked_s present in one profile but not the other).
    """
    if a is None and b is None:
        return None
    return _sdiff(a if a is not None else 0.0, b if b is not None else 0.0)


def _delta_pct(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return round((b - a) / a * 100, 1)


def compute_profile_diff(
    summary_a: ProfileSummary,
    summary_b: ProfileSummary,
) -> ProfileDiff:
    """Align two ProfileSummary objects and return a structured ProfileDiff.

    The comparison_mode field of the returned diff determines how cmd_compare
    should present results and what to include in the LLM prompt.
    """
    # ------------------------------------------------------------------
    # Phase match check
    # ------------------------------------------------------------------
    phases_match = (
        len(summary_a.phases) == len(summary_b.phases)
        and len(summary_a.phases) > 0
        and all(pa.name == pb.name for pa, pb in zip(summary_a.phases, summary_b.phases))
    )

    # ------------------------------------------------------------------
    # Kernel overlap (Jaccard similarity)
    # ------------------------------------------------------------------
    names_a = {k.name for k in summary_a.top_kernels}
    names_b = {k.name for k in summary_b.top_kernels}
    union = names_a | names_b
    intersection = names_a & names_b
    kernel_overlap_pct = round(100 * len(intersection) / len(union), 1) if union else 100.0

    # ------------------------------------------------------------------
    # Determine comparison mode
    # ------------------------------------------------------------------
    if phases_match:
        comparison_mode = "phase_aware"
    elif kernel_overlap_pct >= _KERNEL_OVERLAP_THRESHOLD:
        comparison_mode = "summary"
    else:
        comparison_mode = "summary_no_kernel"

    # ------------------------------------------------------------------
    # Kernel diffs (skipped for summary_no_kernel)
    # ------------------------------------------------------------------
    kernel_diffs: list[KernelDiff] = []
    if comparison_mode != "summary_no_kernel":
        kernels_a = {k.name: k for k in summary_a.top_kernels}
        kernels_b = {k.name: k for k in summary_b.top_kernels}

        # Sort by descending total time in whichever profile has the kernel
        def _sort_key(name: str) -> float:
            ka = kernels_a.get(name)
            kb = kernels_b.get(name)
            return -((ka.total_s if ka else 0.0) + (kb.total_s if kb else 0.0))

        for name in sorted(union, key=_sort_key):
            ka = kernels_a.get(name)
            kb = kernels_b.get(name)
            kernel_diffs.append(
                KernelDiff(
                    name=name,
                    short_name=(ka or kb).short_name,  # type: ignore[union-attr]
                    only_in_a=kb is None,
                    only_in_b=ka is None,
                    calls_a=ka.calls if ka else None,
                    calls_b=kb.calls if kb else None,
                    total_s_a=ka.total_s if ka else None,
                    total_s_b=kb.total_s if kb else None,
                    avg_ms_a=ka.avg_ms if ka else None,
                    avg_ms_b=kb.avg_ms if kb else None,
                    pct_gpu_time_a=ka.pct_of_gpu_time if ka else None,
                    pct_gpu_time_b=kb.pct_of_gpu_time if kb else None,
                    total_s_delta_pct=_delta_pct(
                        ka.total_s if ka else None,
                        kb.total_s if kb else None,
                    ),
                )
            )

    # ------------------------------------------------------------------
    # Memcpy diffs
    # ------------------------------------------------------------------
    memcpy_a = {m.kind: m for m in summary_a.memcpy_by_kind}
    memcpy_b = {m.kind: m for m in summary_b.memcpy_by_kind}
    memcpy_diffs: list[MemcpyDiff] = []
    for kind in sorted(memcpy_a.keys() | memcpy_b.keys()):
        ma = memcpy_a.get(kind)
        mb = memcpy_b.get(kind)
        memcpy_diffs.append(
            MemcpyDiff(
                kind=kind,
                only_in_a=mb is None,
                only_in_b=ma is None,
                total_s_a=ma.total_s if ma else None,
                total_s_b=mb.total_s if mb else None,
                effective_GBs_a=ma.effective_GBs if ma else None,
                effective_GBs_b=mb.effective_GBs if mb else None,
                total_s_delta_pct=_delta_pct(
                    ma.total_s if ma else None,
                    mb.total_s if mb else None,
                ),
            )
        )

    # ------------------------------------------------------------------
    # MPI diffs
    # ------------------------------------------------------------------
    mpi_a = {m.op: m for m in summary_a.mpi_ops}
    mpi_b = {m.op: m for m in summary_b.mpi_ops}
    mpi_diffs: list[MpiDiff] = []
    for op in sorted(mpi_a.keys() | mpi_b.keys()):
        opa = mpi_a.get(op)
        opb = mpi_b.get(op)
        mpi_diffs.append(
            MpiDiff(
                op=op,
                only_in_a=opb is None,
                only_in_b=opa is None,
                calls_a=opa.calls if opa else None,
                calls_b=opb.calls if opb else None,
                total_s_a=opa.total_s if opa else None,
                total_s_b=opb.total_s if opb else None,
                avg_ms_a=opa.avg_ms if opa else None,
                avg_ms_b=opb.avg_ms if opb else None,
                total_s_delta_pct=_delta_pct(
                    opa.total_s if opa else None,
                    opb.total_s if opb else None,
                ),
            )
        )

    # ------------------------------------------------------------------
    # CPU–GPU overlap diffs
    # ------------------------------------------------------------------
    cpu_sync_blocked_s_diff = _sdiff_opt(summary_a.cpu_sync_blocked_s, summary_b.cpu_sync_blocked_s)
    cpu_sync_blocked_pct_diff = _sdiff_opt(
        summary_a.cpu_sync_blocked_pct, summary_b.cpu_sync_blocked_pct
    )

    # ------------------------------------------------------------------
    # Stream topology
    # ------------------------------------------------------------------
    stream_count_a = len(summary_a.streams)
    stream_count_b = len(summary_b.streams)
    dominant_stream_pct_a = (
        max((s.pct_of_gpu_time for s in summary_a.streams), default=None)
        if summary_a.streams
        else None
    )
    dominant_stream_pct_b = (
        max((s.pct_of_gpu_time for s in summary_b.streams), default=None)
        if summary_b.streams
        else None
    )

    # ------------------------------------------------------------------
    # Per-phase diffs (phase_aware mode only)
    # ------------------------------------------------------------------
    phase_diffs: list[PhaseDiff] = []
    if phases_match:
        for idx, (pa, pb) in enumerate(zip(summary_a.phases, summary_b.phases)):
            phase_diffs.append(
                PhaseDiff(
                    phase_name=pa.name,
                    phase_index=idx,
                    duration_s=_sdiff(pa.duration_s, pb.duration_s),
                    gpu_utilization_pct=_sdiff(pa.gpu_utilization_pct, pb.gpu_utilization_pct),
                    gpu_kernel_s=_sdiff(pa.gpu_kernel_s, pb.gpu_kernel_s),
                    gpu_memcpy_s=_sdiff(pa.gpu_memcpy_s, pb.gpu_memcpy_s),
                    total_gpu_idle_s=_sdiff(pa.total_gpu_idle_s, pb.total_gpu_idle_s),
                )
            )

    return ProfileDiff(
        profile_a_name=Path(summary_a.profile_path).name,
        profile_b_name=Path(summary_b.profile_path).name,
        comparison_mode=comparison_mode,
        phases_match=phases_match,
        kernel_overlap_pct=kernel_overlap_pct,
        profile_span_s=_sdiff(summary_a.profile_span_s, summary_b.profile_span_s),
        gpu_utilization_pct=_sdiff(summary_a.gpu_utilization_pct, summary_b.gpu_utilization_pct),
        gpu_kernel_s=_sdiff(summary_a.gpu_kernel_s, summary_b.gpu_kernel_s),
        gpu_memcpy_s=_sdiff(summary_a.gpu_memcpy_s, summary_b.gpu_memcpy_s),
        gpu_sync_s=_sdiff(summary_a.gpu_sync_s, summary_b.gpu_sync_s),
        total_gpu_idle_s=_sdiff(summary_a.total_gpu_idle_s, summary_b.total_gpu_idle_s),
        cpu_sync_blocked_s=cpu_sync_blocked_s_diff,
        cpu_sync_blocked_pct=cpu_sync_blocked_pct_diff,
        stream_count_a=stream_count_a,
        stream_count_b=stream_count_b,
        dominant_stream_pct_a=dominant_stream_pct_a,
        dominant_stream_pct_b=dominant_stream_pct_b,
        kernel_diffs=kernel_diffs,
        memcpy_diffs=memcpy_diffs,
        mpi_diffs=mpi_diffs,
        phase_diffs=phase_diffs,
    )
