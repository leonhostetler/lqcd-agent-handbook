---
title: The staggered-CG throughput probe
summary: A portable probe of staggered CG throughput on one device, one node, two and four nodes, with a MILC leg and QUDA's own invert test at every point, so a machine's stacks compare across machines and a drop localizes; its parameters live in tools/milc-quda-cg-probe.py.
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
  - https://github.com/lattice/quda/blob/ba501e4f8c661a84e73ac0f50ab56bfecbcdd28e/tests/staggered_dslash_test_utils.h#L349-L476
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/nersc_cksum.c#L28-L55
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/com_qmp.c#L611-L620
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/lib/mpi/QMP_comm_mpi.c#L295-L327
  - operator's screened Horizon probe run and dslash-iteration trial, 2026-10-10
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

**Status: version 1.1.0, frozen.** The mass was chosen by one calibration on a GB200, as tuning
work: the scanned mass whose single-RHS solves on one device took closest to 2000 iterations within
1000–3000. The tolerance is the light-quark residual of the campaigns the probe was built beside,
fixed on that reasoning rather than measured. A tool whose mass is unset is an unfrozen probe, and
then `inputs` writes only calibration inputs and `analyze` drafts no rows.

**1.1.0 removed the QUDA dslash legs; nothing else changed.** `staggered_dslash_test` times its
calls as one interval after a single untimed call (`staggered_dslash_test_utils.h` L349–L476), and
on a GB200 its rate rose with the call count: 1,400 GFLOPS over 100 calls, 2,600 over 1,000, 3,650
over 10,000, and the slowest windows ran with the SM clock at its maximum. The cause was not found, no count gave a
figure that held its repeats within 2 % at both one device and one node, and a figure that depends
on how long it is timed cannot be compared across machines `[observed]`. The invert test, whose
solves each run thousands of iterations, repeats within 0.2 %.

**A version that only removes legs still analyzes runs of the version before it.** The tool lists
such versions, and `analyze` admits one of their runs only after regenerating every remaining
input — each MILC input file the run read, each QUDA command line — and finding it identical; it
then reports the run as the current version and ignores the removed legs. A version that changes
a remaining leg needs new runs.

## What it holds fixed, and why

- **A generated, disordered gauge field.** MILC's `warm` start (`generic/io_helpers.c`
  L206–L208, L751–L773) puts Gaussian noise of width 0.7 on every link and reunitarizes. Each
  site's generator is seeded from the input seed and the site's global lexicographic index
  (`ranstuff.c` L123–L136, `make_lattice.c` L49), so a given seed and global volume build the
  same field at every geometry. No file is shipped or written. **Never a unit gauge**: the free
  operator's degenerate spectrum lets CG converge in a handful of iterations for structured
  sources, and identical links hide layout and halo errors from a correctness check.
- **A hypercubic local volume per rank** under weak scaling, so face sizes do not depend on
  which dimension is split, and sized so the whole probe fits a 40 GB A100. **The size came from
  a measurement, not from `tools/quda-staggered-memory.py`.** On the calibration, every leg's device
  footprint was about 1.6 times that tool's plain-CG estimate, at two volumes alike: the probe
  carries QUDA's HISQ link construction and a 12-RHS block, which lie outside the fit's
  calibration. The next calibrated volume up did not fit. On the largest devices one rank at this
  volume runs slightly below their plateau; rows stay comparable because every machine runs the
  same volume.
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
| MILC consistency | `ks_spectrum_hisq`, one fixed global volume | correctness only |

The QUDA 12-RHS invert runs with `--nsrc-tile 12`. Without a tile above 1 the test loops its
sources one at a time (`staggered_invert_test.cpp` L279); with it, each block goes through
`invertMultiSrcQuda` (L404–L428), the entry the MILC interface uses.

**Reading a drop across the legs.** Both legs slower on one device points at the device or its
node; one device fine and one node slower, at on-node links, peer-to-peer or binding; one node
fine and two or four slower, at the network or the MPI transport; QUDA's invert fine and MILC's
`CONGRAD5` slower, at the MILC side — host work, layout, launch, or the interface's copies.

## Correctness

Under weak scaling each point has its own global lattice and so its own field, which is why a
**consistency leg** runs one fixed global volume with the same seed at every point. MILC prints the
field's `CHECK PLAQ` after a warm start too (`io_helpers.c` L232–L250). **The plaquette, a
floating-point sum whose order is not fixed, is compared to a relative limit**: two runs of one
input on one rank have given plaquettes differing in the last digit.

**MILC's NERSC checksum is not compared, and cannot be on a QMP build.** It is the unsigned sum
of the links' bits (`nersc_cksum.c` L28–L55), reduced over ranks by `g_uint32sum`, which with QMP
calls `QMP_binary_reduction` (`com_qmp.c` L611–L620). QMP does that as `MPI_Allreduce` of 4
`MPI_BYTE` with a user operation that ignores the length it is given (`QMP_comm_mpi.c`
L295–L327). Open MPI 5.0 on Horizon handed that operation 2 bytes at a time on 2 ranks and 1 byte
on 4, and the sum of one word came out wrong in 488 of 1,000 trials and in all 1,000
respectively `[observed]`. The probe's consistency leg printed four different checksums at its
four points for one field whose plaquette, link trace and correlators agreed.

Each meson's correlator file must agree with the first point's, within the probe's limit, through
`tools/milc-compare-fnal-correlators.py`. Each meson writes its own file: the
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
   each point's figures. Keep the inputs beside the manifest: for a run of an earlier version,
   the identity check reads them there. For a frozen probe, given `--stack`, the loaded-library file and the
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
