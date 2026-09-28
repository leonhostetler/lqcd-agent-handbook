---
title: QIO parallel single-file writes lose data on NFS — open upstream defect
summary: "OPEN DEFECT (QIO #19, QUDA #1655): multi-rank QIO_SINGLEFILE + QIO_PARALLEL writes, which QUDA uses for every gauge-field save and every single-file vector save, silently zero part of one rank's data wherever two ranks' byte ranges share a page on NFS. Vista's $HOME and $SCRATCH are NFS; $WORK (Lustre) is clean. Write on Lustre, write through one I/O node, or use partfile; the failure appears only as a checksum mismatch on read."
scope: [software:qio, machine:vista]
load_when: Writing or reading a QIO file from more than one rank; saving a gauge field, eigenvectors, or near-null vectors from QUDA or MILC on more than one node; choosing a filesystem or save mode for lattice files on Vista; or diagnosing a QIO_compare_checksum mismatch (status -14) on read-back.
evidence: experiment
sources:
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/qio_field.cpp#L93-L113
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/qio_field.cpp#L400-L431
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/lib/qio/QIO_open_write.c#L203-L214
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_scidac.c#L380-L410
  - operator's screened diagnostic-rig records
observed: "2026-09-28"
observed_on:
  machine: vista
  node_type: gpu-gh200
  software:
    qio:
      commit: 273841537392f9465d229c957228755e923408eb
      branch: master
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# QIO parallel single-file writes lose data on NFS

> **WARNING — open upstream defect.** Tracked as
> [usqcd-software/qio#19](https://github.com/usqcd-software/qio/issues/19) and
> [lattice/quda#1655](https://github.com/lattice/quda/issues/1655). A multi-rank QIO
> **single-file** write in **parallel** mode can come back with part of one rank's data
> replaced by zeros when the file is on NFS. The write reports success; the damage surfaces
> only as `QIO_compare_checksum ... Checksum mismatch` (status `-14`) when the file is read.
> On Vista, `$HOME` and `$SCRATCH` are NFS. **Do not write multi-rank QIO single-file output
> there from more than one node** — use `$WORK`, one writer, or partfile (below).
> **Keep this warning until the issue that covers the path in use is fixed upstream and the
> fix is validated on Vista by a multi-node write on NFS.**

## What is affected

Any write that opens a file with `QIO_SINGLEFILE` and `QIO_PARALLEL` while more than one node
is an I/O node. QMP's default makes every node its own I/O node, so each rank writes its own
byte range of the shared file. `[source]`
- **QUDA, always:** `write_gauge_field` hard-codes `QIO_SINGLEFILE` + `QIO_PARALLEL`, and
  `write_spinor_field` uses `QIO_PARALLEL` with `QIO_SINGLEFILE` unless `partfile` is set. It
  passes no I/O-node function, and nothing selects serial mode. This covers every gauge-field
  save, and every single-file save of eigenvectors or near-null vectors. QUDA's `io_test`
  fails for the same reason.
- **MILC, when chosen:** `save_parallel_scidac` and `save_parallel_ildg` (and their `_dp`
  forms) take the same path. The `save_serial_*` variants use `QIO_SERIAL`; they are not
  exposed to this, and are not validated here either.
- **Not affected:** partfile and multifile formats, where each component file has one writer,
  and single-rank or single-node writes, where one NFS client holds the whole file.

## Where

**Observed** on Vista's VAST NFSv3 mounts (`$HOME`, `$SCRATCH`), which use 64 KiB pages.
**Not observed** on Vista's `$WORK` (Lustre). Any NFS mount is **expected** to behave the same
way `[inferred]`: NFS promises only close-to-open consistency between nodes, and this write
pattern needs more. A POSIX-coherent parallel filesystem does not show it.

## What to do until it is fixed

- **Put multi-rank QIO single-file output on a coherent parallel filesystem** — `$WORK` on
  Vista — or run the writer on one node.
- **Or have one I/O node write.** For MILC, use `save_serial_*`. QUDA has no option; overriding
  `QMP_io_node` to return the master node made its `io_test` pass. That override is a
  diagnostic, not a supported configuration.
- **Or save vectors as partfile**, accepting the layout binding in
  [`../quda/internals/vector-io-layout.md`](../quda/internals/vector-io-layout.md).
- **Treat a multi-rank read-back checksum mismatch on NFS as this defect** until shown
  otherwise. The data on disk is damaged; re-reading does not help.

## Mechanism

Where two ranks' byte ranges meet inside one page, one rank's part of that page comes back as
zeros. Every damaged range starts exactly on a page boundary and ends exactly at another
writer's first byte: the next rank's range, or the checksum record the master writes after
the data. `[experiment]`

**The trigger is a writing node whose cached end-of-file is stale.** With writers taking
turns, only a write through a handle opened before another node extended the file was
damaged. A reopen between writers removed the damage, and so did page-aligned ranges.
`[experiment]` Why a stale end-of-file produces zeros is **inferred**, not read from kernel
source: the writing client treats the part of the page beyond its cached end of file as
empty and flushes the whole page, overwriting the other node's bytes with zeros. QIO's
checksum is computed by each sender before its data leaves, so the file carries the correct
checksum of data that never reached disk intact. A reader therefore reports the file faithfully,
and the mismatch is real.

## Evidence

A standalone C/MPI program reproduced QIO's write order at the geometry of a 2-rank QUDA
`io_test`, with no QIO, QUDA, or GPU involved. It ran on 2 × `gpu-gh200` with one writer per
node, and every byte was verified by a second node that wrote none of the files.

| Filesystem | QIO's write order | Stale-handle write |
|---|---|---|
| `$HOME` (VAST NFS) | 350/400 and 184/200 files damaged | 400/400 and 200/200 |
| `$WORK` (Lustre) | 0/400 | 0/400 |

Also on NFS: writers taking turns, each reopening, 0/200; page-aligned ranges 0/200.

QUDA `io_test` at 2 ranks on NFS failed 2/2 as built, and passed 5/5 with a single writer.
Five earlier failing runs on 2 and 4 nodes, on both Vista stacks, had left the written file
on disk. Each showed the same shape: zero runs at page starts, ending at a writer's first
byte. Each checksum recomputed from the file equalled the reader's "Found" value.

## Not claimed

- No kernel code path is cited; the zero-fill mechanism is inferred from the damage pattern.
- Only 2 nodes and one geometry were tested systematically, with 2 and 4 nodes for `io_test`.
- NFS mounts other than Vista's are not tested.
- MILC's `save_serial_*` and its non-QIO `save_parallel` path were not exercised here.
