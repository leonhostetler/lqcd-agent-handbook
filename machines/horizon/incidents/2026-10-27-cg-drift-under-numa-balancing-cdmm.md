---
title: Staggered CG slowed down within each process under automatic NUMA balancing on CDMM-mode boards; numactl --localalloc removed it
summary: On gpu-gb200 boards whose GPU driver was in CDMM mode, a long MILC/QUDA staggered CG solve got about 30 % slower per iteration within each process under the default memory policy and ran flat under numactl --localalloc, with identical answers. After a site maintenance put the boards in NUMA mode, the slowdown was absent in a rerun of the same 27-board case and in a 144-board pair, and --localalloc cost 0.93–0.96× for CG.
scope: [machine:horizon, software:milc, software:quda]
load_when: A MILC/QUDA staggered CG solve on Horizon gets slower per iteration within one process while its iteration count stays the same; deciding whether to launch ranks under numactl --localalloc; or reading Horizon CG timings taken before the late-October 2026 maintenance.
evidence: observed
sources:
  - operator-submitted MILC/QUDA CG diagnostic jobs on 27 gpu-gb200 boards, with in-job per-rank memory-policy probes, per-node vmstat and nvidia-smi records and per-thread kernel samplers, 2026-10-26 to 2026-10-27, reviewed in the working directory
  - an operator-submitted MILC/QUDA CG and staggered-multigrid job on 144 gpu-gb200 boards, with per-rank memory-policy probes and per-node vmstat records, 2026-10-28, reviewed in the working directory
  - an operator-submitted rerun of the 27-board CG pair with a per-board memory-mode, thermal-zone and driver audit, per-rank memory-policy probes and per-node kernel samplers, 2026-10-29, reviewed in the working directory
observed: "2026-10-29"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
  toolchain:
    cuda: "13.3"
    openmpi: "5.0.11"
    ucx: "1.22.0"
    nvidia-driver: "615.71.09 (CDMM-mode pair); 610.57.04 (NUMA-mode pair)"
---

# Staggered CG slowed down within each process under automatic NUMA balancing on CDMM-mode boards

**Three controlled pairs: one on CDMM-mode boards, two on NUMA-mode boards.** Not a rule. How to read a board's memory mode is in
[`../notes.md`](../notes.md), "Check each board's GPU memory mode before timing".

The runs were MILC `ks_spectrum_hisq` with QUDA mixed-precision staggered CG on fine HISQ lattices at physical
light-quark mass, the light-mass solve, six colour solves per process. Four ranks per board, one per GPU, launched with
`ibrun` and `--map-by slot:PE=36 --bind-to core`; `QUDA_ENABLE_GDR=1`. `kernel.numa_balancing` was 1 on every compute
node read. Within each pair, the only variable was the memory policy: the default, or every rank under
`numactl --localalloc`.

## On CDMM-mode boards: a slowdown within each process

27 boards. Every rank's `Mems_allowed_list` was `0-1` (no GPU NUMA nodes), and every node ran driver 615.71.09.

1. **Under the default policy, each colour solve took more time per iteration than the one before**, up to **+30 %**
   above the first solve by the fourth, with **identical iteration counts**. In earlier jobs on other node sets, the
   same solve rose by 23–39 %. Each new process started fast again.
2. **Under `numactl --localalloc` the cost per iteration was flat** (within 0.2 %). It was about **31 %** below the
   default at the plateau, and **12 %** below it even in the first solve. Correlators were bitwise identical.
3. **The knob applied, shown by an outcome other than the timing.** Every rank reported `policy: local`, and each node's
   `numa_pte_updates` during the `--localalloc` leg were at most 0.03 % of the default leg's.
4. **The cost is waiting, not host CPU time.** MILC threads spent about 0.05 % of wall time in the kernel, and that did
   not track the slowdown. GPU utilisation fell by a quarter under the default policy and held under `--localalloc`. An
   earlier every-rank Nsight Systems profile of the same solve put the whole rise in `MPI_Allreduce` wait. The wait was a
   growing population of ~3 ms episodes in which one rank stops completing messages while its main thread is in the
   kernel. GPU kernel time per iteration stayed constant.
5. A coarser ensemble's light solve, run as a dose control, rose only 3.6 %.

## The same 27-board case on NUMA-mode boards: no slowdown

The same inputs, legs and placement, after the site maintenance. This was the first job to read the driver files.
Every board showed `CoherentGPUMemoryMode` `numa`, `uvm_disable_sam_migration` `N`, driver 610.57.04 and
`Mems_allowed_list` `0-2,10,18,26`, and every thermal zone read `disabled`.

1. **Under the default policy the cost per iteration rose only 3.3 %**, against +30 % on CDMM-mode boards. Iteration
   counts were identical, and correlators were bitwise equal to the CDMM-mode runs.
2. **Under `--localalloc` it was flat** (+0.9 %), at 0.96× the default at the median of solves 2–6 and below it in every
   solve (0.956–0.980). There was no in-job repeat, so no measured floor.
3. The knob applied: 108/108 ranks `policy: local`, and PTE updates at most 0.12 % of the default leg's on every board.
   Under `--localalloc` the per-process NUMA scan sequence advanced *faster* than under the default, as it had on CDMM-mode
   boards: the scanner still runs its passes but finds nothing to unmap `[inferred]`.
4. **Apart from the slowdown, the speed matched healthy pre-maintenance jobs at this placement.** A heavier-mass solve
   on the coarser control lattice ran at the same cost per iteration. The light-mass first solve ran at about 0.86–0.97×
   of its earlier cost. The 144-board job below was
   about 2× faster than its predecessors, but that is not reproduced at this size.

## A 144-board pair on NUMA-mode boards: no slowdown

144 boards, the first job after a site maintenance. Every rank's `Mems_allowed_list` was `0-2,10,18,26` on all 144
boards, and the batch node ran driver 610.57.04. A second, larger fine lattice was used.

1. **Under the default policy the CG cost per iteration rose only 3.0 %** over six solves, against +64 % for the same
   solve on the same lattice before the maintenance (216 boards).
2. **`--localalloc` was still cheaper:** CG median solve 0.93×, staggered-multigrid recurring solve 0.78×, multigrid
   setup 0.88×. Answers were bitwise equal and multigrid work counts identical. There was no in-job repeat, so these
   differences have no measured floor. A background checksum of the gauge file overlapped the default CG leg, and it is
   not separable from that leg's cost.
3. The knob applied: 576/576 ranks `policy: local`, and per-node PTE updates at most 0.24 % of the default legs'.
4. **The whole job ran about 2× faster than 144- and 216-board jobs before the maintenance, with the same work.** The
   same multigrid hierarchy, placement and loaded vectors took 0.50× the recurring solve time and 0.36× the setup time,
   with identical apply, halo and reduction counts. Neither job throttled. At 27 boards no such speedup appeared (above).
   What made the large earlier jobs slow is not established.

## Mechanism

**`[inferred]`, partly confirmed by outcome.** Automatic NUMA balancing periodically unmaps a process's pages so that
the next access takes a hinting fault. On these boards the faults were almost all local and almost nothing migrated, so
the scanning, not placement, is the candidate cost. `numactl --localalloc` sets an explicit task policy. Placement is
unchanged, but upstream kernels do not scan memory under an explicit policy. The collapse of PTE updates confirms that
here. **Open:**
- how hinting faults became multi-millisecond stalls in a GPU-coupled MPI process;
- why they did so on CDMM-mode boards and not on NUMA-mode ones, at 27 or at 144 boards;
- whether the memory mode, the driver change, or a thermal setting removed it. All three changed together, and
  thermal-zone state was not recorded before the maintenance.

`tools/horizon-gb200-bind.sh` binds memory with `numactl --membind`, also an explicit task policy. By the same
mechanism it should opt out of scanning `[inferred]`. Not measured.

## What to do

- **Read the boards' memory mode first.** The slowdown was measured on CDMM-mode boards, or on boards before the
  maintenance whose mode was not recorded, in every job that looked for it. On NUMA-mode boards it was absent in both
  pairs.
- **Where it appears, test `numactl --localalloc` against the default in one job on one node set**, the default leg
  first. Confirm the knob by outcome: run `numactl --show` from a probe under the same launcher and policy, and compare
  the per-node `numa_pte_updates` deltas in `/proc/vmstat`.
- **The option changed nothing numerically and was never slower.** It is the operator's default for MILC and QUDA
  runs on this machine ([`../notes.md`](../notes.md), "Launch MPI deliberately"). Its benefit without a slowdown is
  small (0.93–0.96× for CG) and has no measured floor.
- **Do not compare Horizon timings across the late-October 2026 maintenance** without re-measuring a reference on each
  side.
- Report the first solve, the per-solve sequence and the median separately: a median over later solves contains part
  of any rise.

**Not yet tested:** another application, launcher or binding; and the no-ramp slowdowns other applications showed on
this machine.
