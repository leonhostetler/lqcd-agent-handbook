---
title: Where staggered-MG setup memory actually goes
summary: Six source-exact facts about which fields QUDA allocates while building a staggered multigrid hierarchy, including a 16x setup-workspace step set by a divisibility test no input file exposes.
scope: [software:quda, software:milc, solver:multigrid, fermion:staggered]
load_when: Sizing, auditing, or explaining device memory during staggered-MG setup, or reasoning about which fields a coarse level allocates.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface_internal.cpp#L310-L325
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/multigrid.cpp#L1275-L1330
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/multigrid.cpp#L400-L425
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/inv_cg_quda.cpp#L30-L62
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/inv_cgnr.cpp#L22-L31
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/coarse_op.in.cu#L215-L248
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/dirac_coarse.cpp#L55-L215
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/block_orthogonalize.in.cu#L51-L95
observed: "2026-09-21"
observed_on:
  software:
    quda: {commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc, branch: develop}
    milc: {commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72, branch: develop}
---

# Where staggered-MG setup memory actually goes

Six facts, each read from the source at the observed revision. They are stated because each
one contradicts a reasonable assumption, and four of them were got wrong by inspection during
the investigation that produced this page.

## The setup batch width is 16 or 1, decided by a divisibility test

The MILC interface sets it; no input file, multigrid parameter file, or build option exposes it:

```cpp
n_vec_batch[i] = (i == 0) ? 1 : (n_vec[i] % 16 == 0 ? 16 : 1);
```

Near-null generation then solves in batches of that width, and every field it needs is sized
to it. Per right-hand side, at the setup precision: `b`, `x` from the caller, `r`, `y`
from CG, `br` from CGNR, and one `MdagM` temporary. At the preconditioner precision:
`p`, `Ap`, `r_sloppy`, and a sloppy `MdagM` temporary. **Ten fields per right-hand
side.**

**So the setup workspace changes by a factor of 16 on whether `nvec` divides by 16**, and
nothing in the run's inputs records the choice. `nvec_1 = 32` and `nvec_1 = 24` differ by
eight vectors and by the whole batch step. Check the divisibility before attributing a setup
memory change to the vector count itself.

`x_sloppy` is never among them: `use_sloppy_partial_accumulator` is hard-coded to false
immediately before it would be allocated.

## AV is not allocated for staggered

The coarse-operator build takes `uv` and `av`. Only `uv` is always created:

```cpp
// if we are coarsening a preconditioned clover or twisted-mass operator we need
// an additional vector to store the cloverInv * V field, else just alias v
ColorSpinorField *av = ((matpc != QUDA_MATPC_INVALID && clover) || (dirac == QUDA_TWISTED_MASSPC_DIRAC)) ?
  ColorSpinorField::Create(UVparam) : &const_cast<ColorSpinorField &>(T.Vectors());
```

HISQ carries no clover, so `av` aliases the transfer vectors. Counting UV and AV as two
fields double-counts one that does not exist, and `UV` itself "has the same structure as V"
rather than being larger.

## The smoother and its sloppy variant allocate no coarse gauge

A level's coarse operator is built once and shared. `DiracCoarse`'s copy constructor takes
the `shared_ptr`s — `Y_d`, `X_d`, `Yhat_d`, `Xinv_d` and their AoS copies — and has
an **empty body**. So `diracCoarseResidual`, `diracCoarseSmoother` and
`diracCoarseSmootherSloppy` are three operators over **one** set of coarse links, not three
sets. With MMA, `need_aos_gauge_copy` adds exactly **one** MILC-order copy of each field,
not two.

## Which operator a level gets depends on the level below it

```cpp
if (param.mg_global.smoother_solve_type[param.level + 1] == QUDA_DIRECT_PC_SOLVE) {
    diracCoarseSmoother = new DiracCoarsePC(...);   // needs Yhat and Xinv
} else {
    diracCoarseSmoother = new DiracCoarse(...);
}
```

`coarse_solve_type ... direct-pc` is conventionally set on the **coarsest** level. The
consequence is easy to miss: **the same level-2 build produces a different operator at three
levels than at four**, because at three levels level 2 is the coarsest and at four it is not.
A per-level memory estimate that does not know the total level count cannot be right for both.

## Construction temporaries are scalar geometry, not coarse

When the coarse link precision is below single, the build allocates single-precision atomic
accumulators — and both are built from the **X** parameter:

```cpp
GaugeFieldParam param(X); // use X since we want scalar geometry
Yatomic = GaugeField::Create(param);
Xatomic = GaugeField::Create(param);
```

Scalar geometry is one site direction against the coarse geometry's eight, so these are an
eighth the sites of a coarse link field, not two extra copies of one. Both are deleted
immediately after the coarse operator is calculated.

## Block orthogonalisation allocates nothing

`BlockOrtho` holds `ColorSpinorField &V` and `const std::vector<ColorSpinorField> &B` —
references — and orthonormalises in place. The `aggregate_size > 1024` error is a kernel
block and shared-memory limit, not a workspace bound, and shared memory does not appear in
QUDA's device counter. **A large aggregate costs no additional device allocation**; the cap
exists for a different reason than memory capacity.
