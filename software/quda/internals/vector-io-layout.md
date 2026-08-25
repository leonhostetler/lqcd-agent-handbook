---
title: QUDA vector I/O layout binding
summary: A partfile-format field is readable only under the rank-grid factorization that wrote it; single-file carries no sitelist and no such binding.
scope: [software:quda, software:qio]
load_when: Saving or loading QUDA vector fields such as near-null vectors or eigenvectors, choosing a save format for fields intended to outlive one job, or changing rank decomposition for a run that reuses stored fields.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/qio_field.cpp#L205-L217
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/qio_field.cpp#L250-L290
  - https://github.com/lattice/quda/blob/b6998853f6b605e22d67ea2ddfa3cab0d752679a/lib/qio_field.cpp#L391-L440
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/lib/qio/QIO_utils.c#L695-L720
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/lib/dml/DML_utils.c#L282-L291
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/lib/dml/DML_utils.c#L511-L595
  - operator's screened tuning records
observed: "2026-08-25"
observed_on:
  software:
    quda:
      commit: b6998853f6b605e22d67ea2ddfa3cab0d752679a
      branch: develop
    qio:
      commit: 273841537392f9465d229c957228755e923408eb
      branch: master
---

# QUDA vector I/O layout binding

A QUDA field written through QIO in **partfile** format can only be read back by a job whose
rank decomposition reproduces the writing job's I/O layout. Matching global lattice,
hierarchy, block sizes, vector count, precision, executable, and gauge field do not make
such a field loadable under a different factorization, and **matching the total rank count
is not sufficient either** — the factorization itself must match.

A **single-file** save carries no such binding.

## Which writes are bound

`write_spinor_field` selects the format from its `partfile` argument: `QIO_PARTFILE` when
set, `QIO_SINGLEFILE` otherwise. This is the path used for near-null vectors and
eigenvectors, so it is the one that matters for reusable solver state.

`write_gauge_field` is hard-coded to `QIO_SINGLEFILE`. Gauge configurations written by QUDA
therefore never carry this binding, which is why a placement change can break a stored
vector set while the gauge field it was built from continues to load.

## Mechanism

Partfile output produces one `.volNNNN` file per I/O partition. Each part embeds a DML
sitelist enumerating the global sites that part holds — a record of the writing layout.

On read, `set_layout()` builds the layout from the **current** job's geometry:
`lattice_size[d] = comm_dim(d) * X[d]`, with the node count from QMP. The layout is thus a
function of the rank grid, not of the global lattice alone. Two jobs with the same total
rank count but different factorizations produce different layouts and different sitelists.

`read_spinor_field` and `read_gauge_field` both open with `volfmt = QIO_UNKNOWN`, so QIO
autodetects the on-disk format. **Format autodetection is not a compatibility check**:
detection succeeds first, and the layout check fails afterwards.

`QIO_read_sitelist` then dispatches on the detected format. For `QIO_PARTFILE` each I/O node
calls `DML_read_sitelist`, which reads the embedded list and requires it to agree with the
current layout **exactly** — `DML_compare_sitelists` returns non-zero on the first differing
entry. On mismatch it prints that the sitelist does not conform to the I/O layout, the open
fails, and QUDA raises `Open file failed` from `qio_field.cpp`, aborting the job.

The failure lands at **file-open time, before any field data is consumed**, so it is
deterministic and costs the full job launch.

## Why single-file is exempt

`QIO_read_sitelist` returns success immediately for `QIO_SINGLEFILE`:

> `/* SINGLEFILE format has no sitelist */`

A single-file record holds the whole field in one file rather than one file per partition,
so no per-partition sitelist exists for a reader to reject, and no layout comparison runs.
Single-file fields are therefore readable under a different rank decomposition.

**The cost is I/O time that grows with rank count.** That direction is operator-supplied
practitioner knowledge and is deliberately unquantified here: no threshold, coefficient, or
crossover rank count is established, and none should be inferred. Measure it on the target
stack and workload if the tradeoff is close.

## Consequences

- **Choose the save format from the intended lifetime of the field, not from write speed.**
  If a stored field may ever be read at a different decomposition, partfile makes that
  impossible without regeneration, and the constraint is only discovered later.
- **Treat the writing rank geometry as part of a stored partfile field's identity**, and
  record it wherever the artifact is referenced. A stored set whose part count differs from
  the reading job's I/O-node count will not load — and equal counts still do not guarantee
  a load, because the factorization is the binding quantity.
- **Reusing saved partfile vectors constrains placement independently of hierarchy
  legality.** A decomposition or memory preflight that validates block legality, aggregate
  limits, compiled coarse colours, and capacity does not cover stored I/O layout, and will
  pass a configuration that cannot load its own inputs.
- **When a study must vary rank decomposition over stored fields there are three options**,
  with different costs: match the writing placement, regenerate the fields under the new
  placement, or hold the fields in single-file format and pay the I/O time. Price the option
  against the study rather than assuming regeneration is the only route.

## Screening this offline

The binding is not fully decidable outside a job: the part count is visible from the stored
set, but the factorization that produced it is recorded only inside the sitelists. A cheap
**necessary** check is that the stored part count equals the planned job's I/O-node count; a
mismatch is a guaranteed failure, while agreement is not a guarantee of success. Treat
stored-field placement as a recorded property of the artifact rather than something to be
recovered by inspection.

## Not claimed

- No quantitative claim about single-file I/O cost.
- No claim about the cost, quality, or reproducibility of regenerating near-null vectors
  under a new placement.
- No claim about QUDA or MILC I/O paths beyond the `qio_field.cpp` functions named above.
- No performance, memory, or hierarchy conclusion follows from this failure mode.
