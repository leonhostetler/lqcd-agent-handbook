---
title: The staggered-CG throughput probe
summary: A portable probe of staggered CG throughput on one device, one node, two and four nodes, with a MILC leg and QUDA's own tests at every point, so a machine's stacks compare across machines and a drop localizes; its parameters live in tools/milc-quda-cg-probe.py.
scope: [software:milc, software:quda]
load_when: Measuring, comparing or checking solver throughput on a machine, preparing or analyzing a probe run, or writing performance.yaml probe rows.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L206-L208
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L751-L773
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L232-L250
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/ranstuff.c#L123-L136
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/make_lattice.c#L49
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/layout_hyper_prime.c#L122-L135
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/layout_hyper_prime.c#L494-L508
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/ks_spectrum/setup.c#L517-L529
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/lib/mpi/QMP_topology_mpi.c#L51-L62
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/utils/command_line_params.cpp#L654-L658
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/utils/command_line_params.cpp#L529
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/staggered_invert_test.cpp#L279
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/staggered_invert_test.cpp#L404-L428
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/lib/timer.cpp#L297-L298
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/staggered_dslash_test_utils.h#L478-L495
observed: "2026-10-10"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e
      branch: develop
---

# The staggered-CG throughput probe

The probe measures staggered CG throughput on a stack in a way that is the same on every
machine, so a machine's `performance.yaml` probe rows compare with another machine's, and a run
that comes in below its rows can be located. It is deliberately small: it compares and detects
at one device, one node, two and four nodes, and it does not license extrapolation to large jobs.

**`tools/milc-quda-cg-probe.py` is the one home of its parameters.** `describe` prints every
frozen value (volumes, seed, sets, right-hand-side counts, precision, reconstruction, solve
counts, the ladder and the statistic); this page explains them and restates none. Changing any
of them makes a new probe version, and rows of different versions are never compared.

**Status: version 0.x, not yet frozen.** The mass and tolerance are fixed once, by a
calibration run that chooses a mass giving solves of 1000–3000 iterations on one device; that
choice is made from a measurement, so it is tuning work, and the probe becomes 1.0.0 when the
values are written into the tool. Until then `inputs` writes inputs only for a calibration run,
and `analyze` emits no performance rows.

## What it holds fixed, and why

- **A generated, disordered gauge field.** MILC's `warm` start (`generic/io_helpers.c`
  L206–L208, L751–L773) puts Gaussian noise of width 0.7 on every link and reunitarizes. Each
  site's generator is seeded from the input seed and the site's global lexicographic index
  (`ranstuff.c` L123–L136, `make_lattice.c` L49), so a given seed and global volume build the
  same field at every geometry. No file is shipped or written. **Never a unit gauge**: the free
  operator's degenerate spectrum lets CG converge in a handful of iterations for structured
  sources, and identical links hide layout and halo errors from a correctness check.
- **A hypercubic local volume per rank** under weak scaling, sized for a 40 GB A100 by
  `tools/quda-staggered-memory.py` with margin for its fit error, so face sizes do not depend
  on which dimension is split. Whether one such rank fills a larger device is a measurement,
  not a property of the choice.
- **Two right-hand-side counts.** 1, from a `single` set, which MILC solves one colour at a
  time; and 12, from `multicolorsource` sets of four same-parity corner-wall sources, solved as
  one block (`ks_spectrum/setup.c` L517–L529). 12 is a multiple of every multi-RHS tile in use,
  so no stack ends on a partial tile.
- **The first solve of each kind is excluded** from every statistic, because it can carry
  allocation and tuning; the tuning itself is a separate, earlier run.

## The geometry ladder

The tool computes each point's `node_geometry` and the dimensions whose neighbours sit on
another node, for any ranks-per-node the volumes divide into, and refuses one they do not. A
node's ranks fill the fastest-varying dimensions, and each later point adds node splits in the
slowest: two nodes put t off node, four put z and t off node, and the on-node layout is the same
at every multi-rank point. That rests on two facts:

- with QMP, MILC asks QMP for each rank (`layout_hyper_prime.c` L494–L508) and declares the
  topology without a dimension map (L122–L135), and QMP then numbers ranks with x fastest
  (`QMP_topology_mpi.c` L51–L62);
- the launcher places consecutive ranks on the same node. A batch script must make that so (a
  slot- or block-mapped launch), and record it.

**QUDA's tests default to t-fastest rank order** (`--rank-order`, default `col`,
`command_line_params.cpp` L654–L658), which at the same `node_geometry` would put a different
dimension off node. The probe passes `--rank-order row`, and `analyze` requires each QUDA log
to print the row-major line.

## The legs at every point

| Leg | Program | Metric |
|---|---|---|
| MILC throughput | `ks_spectrum_hisq`, the local volume per rank | `CONGRAD5` mflops, per rank; the number the campaigns report |
| QUDA invert | `staggered_invert_test`, `--dslash-type hisq` (which builds HISQ links from the test's random field, L529) | Gflops ÷ ranks: QUDA sums the solver's flops over ranks (`timer.cpp` L297–L298) |
| QUDA dslash | `staggered_dslash_test` | `GFLOPS` and `GBYTES`, per rank: the counters are per process (`staggered_dslash_test_utils.h` L478–L495) |
| MILC consistency | `ks_spectrum_hisq`, one fixed global volume | correctness only |

The QUDA 12-RHS invert runs with `--nsrc-tile 12`. Without a tile above 1 the test loops its
sources one at a time (`staggered_invert_test.cpp` L279); with it, each block goes through
`invertMultiSrcQuda` (L404–L428), the entry the MILC interface uses.

**Reading a drop across the legs.** QUDA's dslash slower on one device points at the device or
its node; one device fine and one node slower, at on-node links, peer-to-peer or binding; one
node fine and two or four slower, at the network or the MPI transport; QUDA fine and MILC's
`CONGRAD5` slower, at the MILC side — host work, layout, launch, or the interface's copies.

## Correctness

Under weak scaling each point has its own global lattice and so its own field, which is why a
**consistency leg** runs one fixed global volume with the same seed at every point. Its
`CHECK PLAQ` and NERSC checksum (`io_helpers.c` L232–L250), which MILC prints after a warm start
too, must be identical at every point, and each meson's correlator file must agree with the first
point's through `tools/milc-compare-fnal-correlators.py`. Each meson writes its own file: the
pions share source, operator and mass labels, so in one file their keys would collide. The QUDA
legs verify against the host on one device only, because host verification at the probe volume
is slow.

## Running it

1. `tools/milc-quda-cg-probe.py inputs --ranks-per-node R --out DIR` writes every point's MILC
   inputs, QUDA command lines and a manifest naming every output the run must produce. Proofread
   the MILC inputs with `tools/milc-proofread-input.sh` before submitting.
2. The batch script is machine-specific and follows the batch-script convention. For each point
   it runs a tuning pass, then the measured run, writing outputs under the manifest's names. It
   records each QUDA library the run loaded, as `<path> <sha256>` lines, exports the
   reconstruction settings the manifest lists, and binds each rank beside its device.
3. `tools/milc-quda-cg-probe.py analyze --manifest … --outputs DIR` checks completion,
   convergence, solve counts, rank order, the consistency leg and every artifact, and reports
   each point's figures. For a frozen probe, given `--stack`, the loaded-library file and the
   install prefix, it also prints draft `performance.yaml` rows whose device, binding, date and
   source still need filling in.

## Limits

- Four nodes is where off-node communication begins, not where it settles; global reductions
  keep growing and contention depends on placement. Probe rows support comparison and drop
  detection at small node counts only.
- A cross-machine comparison is between stacks on machines, never bare hardware: each machine
  runs its own build, toolchain and compiled multi-RHS tile.
- The QUDA legs use the test's own random field, not MILC's warm field, so their iteration
  counts differ from the MILC leg's; their per-iteration rates remain comparable.
- MILC's `CONGRAD5` figure is nominal and ignores precision (`../timing.md`), so it ranks runs
  of the same solver and right-hand-side shape and never solvers against each other.
