---
title: HadronsMILC low-mode-improvement (LMI) application guide
summary: How the light-quark g-2 LMI workflow is generated with pyfm and executed by HadronsMILC — the module chain, mass and residual conventions, Lanczos sizing and the Chebyshev bound, legal decompositions, the meson-field global sum (one host MPI_Allreduce of gigabytes per block), and how to check a build or a decomposition.
scope: [software:hadronsmilc, software:pyfm, fermion:staggered]
load_when: Generating, sizing, launching, validating or interpreting a HadronsMILC LMI job (pyfm task_type lmi or lma_new), including choosing Lanczos parameters and an MPI decomposition.
evidence: source
sources:
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyfm/tasks/hadrons/lmi.py#L193-L200
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyfm/tasks/hadrons/highmode/strategy.py#L170-L262
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyfm/tasks/hadrons/modules.py#L140-L155
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyfm/tasks/hadrons/modules.py#L526-L540
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyfm/nanny/config.py#L85-L89
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/pyproject.toml#L60-L76
  - https://github.com/Michael628/pyfm/blob/9282eac110f95e536607ac9acfee26024677cd13/example/params_files/params_l144288.yaml
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Modules/MAction/ImprovedStaggered.hpp#L117-L121
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Modules/MSolver/MixedPrecisionCG.hpp#L137-L194
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/Modules/MSolver/ImplicitlyRestartedLanczos.hpp#L106-L179
  - https://github.com/Michael628/HadronsMILC/blob/4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e/src/A2AMatrix.hpp#L707
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/GridMilc/a2a/A2AWorker.h#L278-L291
  - https://github.com/milc-qcd/Grid/blob/d67dd2079bea125138502a13120858aa58997379/Grid/communicator/Communicator_mpi3.cc#L333-L338
  - https://github.com/Michael628/HadronsMILC/commit/d355c8f
  - https://github.com/Michael628/HadronsMILC/commit/17a20c7
observed: "2026-10-27"
observed_on:
  software:
    hadronsmilc:
      commit: 4a19a1515b52bc2590d2c03a4fc62d6e6de61a5e
      branch: main
    pyfm:
      commit: 9282eac110f95e536607ac9acfee26024677cd13
      branch: main
    hadrons:
      commit: 3a0980157914dd54e96744fccaf0fbf88620b5a5
      branch: feature/LMI-develop
      forked_from_default: 28d2806401806592f9caddc8eeedd4277efd341d
    grid:
      commit: d67dd2079bea125138502a13120858aa58997379
      branch: feature/LMI-develop
      forked_from_default: 87baaf1d378f92fc8729c4f05a6836d3c764ee87
  toolchain: {gcc: "15.3", cuda: "13.3", openmpi: "5.0.11"}
---

# HadronsMILC LMI application guide

LMI computes light-quark two-point functions (pion, local and one-link vector currents for the
g-2 hadronic vacuum polarisation) by splitting the propagator at a low-mode cut. The low-mode
part is exact: Lanczos eigenvectors are contracted into all-to-all meson fields, which pyfm
contracts offline into `a2aLL` correlators. The rest is stochastic: random-wall sources are
solved with mixed-precision CG starting from their low-mode projection. Releases pair:
HadronsMILC 0.X with pyfm 0.X, at the Grid and Hadrons commits HadronsMILC pins.

## Generating the inputs with pyfm

- **Install pyfm in editable mode** (`pip install -e <pyfm>`, Python ≥ 3.12). A plain
  `pip install` of 0.3.0 omits `pyfm.tasks.hadrons.highmode_v2` from its package list
  (`pyproject.toml`), and every command then fails with an ImportError about a partially
  initialised module.
- `pyfm nanny generate -p params.yaml -j <step> -s <series> -n <config>` writes the XML, a
  schedule file and, for the `contract` step, a YAML. It needs a `submit.resources` stanza and
  `files.eig`/`files.eigdir` entries even when nothing is submitted or saved. Start from
  pyfm's `example/params_files/`; `params_l144288.yaml` is the 0.04 fm ensemble.
- **`task_type: lmi`** generates the Legacy module chain (`StagGaugePropLegacy`,
  `StagMesonLegacy`, `StagA2AMesonFieldLegacy`) and warns that it is on a deprecation path;
  **`lma_new`** targets the gamma-map (`SpinTaste`) API. Run the chain that produced any
  reference you will compare against, and record which one a benchmark uses.
- `action_type: smearv5` loads a MILC v5 lattice (`MIO::LoadMilc`, checksums and plaquette
  logged) and HISQ-smears it in the same job.
- Module order in the generated XML is not stable between generations; compare two inputs
  module by module, by name.
- `pyfm audit output -j <job-a> <job-b> …` compares two jobs' outputs.

## The `lmi` chain

For each mass, the generated input runs: lattice load and `HISQSmear`; `ImprovedStaggeredMILC`
actions (a massless one for the eigensolve, the target mass in double and single precision);
`StagFermionIRL` on the Schur operator, then `ModifyEigenPackMILC` to the target mass and
`EigenPackExtractEvals`; `StagA2AMesonFieldLegacy` for each gamma group (pion local, vector
local, vector one-link); per source time a `StagRandomWall`; a `ranLL` propagator from
`MSolver::StagLMA` (`projector: false`, the eigenvalue-weighted low-mode solution) and an
`ama` propagator from `StagMixedPrecisionCG` guessed from it; and `StagMesonLegacy`
contractions writing `ranLL` and `ama` correlators. An 8⁴, one-mass, four-source, three-gamma
input has 69 modules.

## Conventions

- **Mass.** `ImprovedStaggeredMILC` constructs Grid's operator with mass `2 × mass` and imports
  the links verbatim (`ImprovedStaggered.hpp:117-121`), giving exactly MILC's `M = 2m + D`.
  Put the MILC bare mass in `mass`; do not double or halve it. Eigenvalues of the Schur
  operator are `4m² + D†D` in MILC normalisation (`D†D` for the massless eigensolve action).
- **Mixed-precision CG.** `StagMixedPrecisionCG` solves the full-lattice normal equations and
  sets the inner tolerance to `max(residual, 1e-7)` (d355c8f): float inner solves stop at a
  relative 1e-7 and the double outer loop supplies the rest, so a `residual` below 1e-7 does not
  tighten the float solves. It logs `Final true residual` as `|M x − b|/|b|`, which is not Grid's
  `True residual` line (normal-equation residual relative to `|M†b|`); quote both, labelled. It
  also publishes `<name>_subtract`, the solution minus the guess.
- **Correlator outputs** are written per source time; pyfm's `contract` step adds the `a2aLL`
  correlators from the meson fields.

## Lanczos: memory and the Chebyshev bound

- `StagFermionIRL` keeps all `Nm` basis vectors resident in **double precision** on one
  checkerboard (Grid's default precision is always double; `Io32` changes only file I/O), then
  truncates to `Nstop` (`ImplicitlyRestartedLanczos.hpp:175-179`). Since 17a20c7 the eigenpack
  holds only `Nstop` vectors until `execute`, which lowers the footprint between setup and
  execution but not the peak.
- One field is `V/2 × 3 × 16 B`. For 144³×288 (V/2 = 429,981,696 sites) that is 20.6 GB, so
  `Nm = 4900` needs about **101 TB** for the basis alone, not the 50 TB a single-precision
  estimate gives (arithmetic, not measured). Add the Grid device-cache cap and the comms
  buffer per GPU (`software/grid/runtime-environment.md`) before choosing a node count.
- **`alpha` must lie above the `Nstop`-th eigenvalue** of the Schur operator, or the eigensolve
  stalls and runs on NaN instead of failing, until pyfm's `MaxIt` of 5000
  (`software/grid/solvers/staggered.md` has the signature and how to read the spectrum off a
  failed run). Check a production `alpha` (the 0.04 fm example uses 0.00085 for `Nstop` 4000)
  against the spectrum of that ensemble before spending a large allocation, and give the job a
  stall watch.

## Decompositions that work

Mixed-precision solves build a single-precision red-black grid with two SIMD lanes in each of
dimensions 1–3 on a 64-byte GPU build, so every local extent in dimensions 1–3 must be a
multiple of 4 (`software/grid/runtime-environment.md`). For 144³×288: never split a spatial
dimension 8, 16 or 24 ways, nor time 16 or 32 ways. Splitting time is fine otherwise: on 8⁴, 4
GPUs as `1.1.2.2` (time split) and `2.2.1.1` reproduced the 1-GPU results; `1.1.1.4` (local time
extent 2) aborted at grid construction. One rank per GPU, each bound to its GPU by a wrapper
(`software/grid/runtime-environment.md`).

## The meson-field global sum is one large host allreduce per block

`StagA2AMesonFieldLegacy` computes each meson-field block on the device, copies it to the host,
and sums it over every rank with one in-place `MPI_Allreduce` of doubles
(`GridMilc/a2a/A2AWorker.h` L278–L291, **fork-only**). That call is Grid's `GlobalSumVector`
(`Communicator_mpi3.cc` L333–L338), and it is the same call on upstream `develop`. The log
reports each block's sum as `Global Sum Time: <t> us.` (`A2AMatrix.hpp` L707). The buffer is
the whole block for every time slice and gamma, so at production volume one call moves
gigabytes: 3.456 GB and 4.608 GB per call, by module, in one 144³×288 run.

Its cost is therefore set by the MPI library's collective algorithm for large host buffers,
not by the contraction kernel. Read the per-block `Global Sum Time` lines before attributing
a slow meson-field step to the kernel. On Horizon, Open MPI's default collective component made
this sum about 20 times slower than the alternative: see
[`../../../machines/horizon/notes.md`](../../../machines/horizon/notes.md), "Open MPI's HAN
component and large host-buffer allreduces", before launching a meson-field job there. An MPI
setting chosen for this step applies to every collective in the process, the Lanczos and the
solves included.

## Checking a build or a decomposition

Compare **correlators, eigenvalues and `a2aLL` contractions**, not meson fields: each
eigenvector's phase is arbitrary, so meson fields legitimately differ between runs while their
contractions do not. On the 8⁴ chain above, 4-GPU decompositions agreed with 1 GPU to
4.5 × 10⁻¹⁰ relative and a CPU build agreed to 5 × 10⁻⁹ over every correlator, eigenvalue and
`a2aLL` dataset. Before any comparison, read each job's banner for the three commits and
`Dependency pins=match`, and confirm every expected output file exists (`../validation.md`
explains why exit codes are not enough).
