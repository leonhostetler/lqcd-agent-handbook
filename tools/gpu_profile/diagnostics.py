"""Capability-gap notes: surface missing profile data before analysis runs."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Format, ProfileCapabilities


@dataclass
class CapabilityNote:
    code: str
    message: str  # plain text; caller wraps in Rich markup


def capability_notes(fmt: Format, caps: ProfileCapabilities) -> list[CapabilityNote]:
    """Return ordered info notes for any missing profile capabilities.

    Notes are ordered by impact on PerfAdvisor usefulness, most impactful first.
    Callers are responsible for printing; this function only constructs messages.
    """
    notes: list[CapabilityNote] = []

    if fmt is Format.NSYS:
        if not caps.has_mpi:
            notes.append(CapabilityNote(
                code="N1",
                message=(
                    "No MPI events found — comm/compute overlap, rank-imbalance, and "
                    "collective breakdown are unavailable.\n"
                    "  Re-profile with: "
                    "nsys profile -t cuda,nvtx,mpi,osrt --mpi-impl=<mpich|openmpi> ..."
                ),
            ))
        if not caps.has_markers:
            notes.append(CapabilityNote(
                code="N2",
                message=(
                    "No NVTX markers found — phase names will be auto-derived from kernel "
                    "names; user-defined region labels are unavailable.\n"
                    "  Re-profile with: nsys profile -t cuda,nvtx ..."
                ),
            ))
        if not caps.has_memcpy or not caps.has_runtime_api:
            notes.append(CapabilityNote(
                code="N3",
                message=(
                    "No CUDA memcpy/runtime events found — H2D/D2H bandwidth, CPU-GPU "
                    "overlap, and launch overhead are unavailable.\n"
                    "  Re-profile with: nsys profile -t cuda ..."
                ),
            ))
        if not caps.has_os_runtime:
            notes.append(CapabilityNote(
                code="N5",
                message=(
                    "No OS-runtime tracing found — idle time the host spends blocked in "
                    "the OS cannot be separated from host compute, so the idle-attribution "
                    "residual absorbs it and is an upper bound.\n"
                    "  Re-profile with: nsys profile -t cuda,nvtx,mpi,osrt ..."
                ),
            ))
        if not caps.has_pmc_counters:
            notes.append(CapabilityNote(
                code="N4",
                message=(
                    "No hardware performance counters found — memory-bound vs. "
                    "compute-bound classification will use heuristics only.\n"
                    "  Re-profile with: nsys profile --gpu-metrics-device=all ..."
                ),
            ))

    elif fmt is Format.ROCPD:
        if not caps.has_mpi:
            notes.append(CapabilityNote(
                code="R1",
                message=(
                    "No MPI events found — comm/compute overlap, rank-imbalance, and "
                    "collective breakdown are unavailable.\n"
                    "  Re-profile with: rocprof-sys-sample --trace --mpi -- <app> <args>"
                ),
            ))
        if not caps.has_memcpy or not caps.has_runtime_api:
            notes.append(CapabilityNote(
                code="R2",
                message=(
                    "No memory transfer or HIP/HSA API events found — H2D/D2H bandwidth, "
                    "CPU-GPU overlap, and launch overhead are unavailable.\n"
                    "  Re-profile with: rocprof-sys-sample --trace -- <app> <args>"
                ),
            ))
        if not caps.has_markers:
            notes.append(CapabilityNote(
                code="R3",
                message=(
                    "No ROCTX markers found — phase names will be auto-derived from kernel "
                    "names; user-defined region labels are unavailable.\n"
                    "  Re-profile with: rocprof-sys-sample --trace -- <app> <args>\n"
                    "  (and ensure the application calls roctxRangePush/roctxRangePop)"
                ),
            ))
        if not caps.has_os_runtime:
            notes.append(CapabilityNote(
                code="R5",
                message=(
                    "No OS-level regions found — rocprofv3 traces none, so idle time the "
                    "host spends blocked in the OS cannot be separated from host compute "
                    "and the idle-attribution residual absorbs it.\n"
                    "  Re-profile with: rocprof-sys-sample --trace -- <app> <args>"
                ),
            ))
        if not caps.has_pmc_counters:
            notes.append(CapabilityNote(
                code="R4",
                message=(
                    "No hardware performance counters found — memory-bound vs. "
                    "compute-bound classification will use heuristics only; occupancy and "
                    "cache hit rates are unavailable.\n"
                    "  Re-profile with: "
                    "rocprof-sys-sample --trace --hardware-counters <counters> -- <app> <args>"
                ),
            ))

    return notes
