---
title: QIO and MILC parallel single-file writes lose data on NFS — open upstream defect
summary: "OPEN DEFECT (QIO #19, QUDA #1655): a shared file written by several nodes without byte-range locks comes back with zeroed ranges on NFS. That covers every QUDA gauge save and single-file vector save, MILC's save_parallel_* keywords including propagators and eigenvectors, and MILC's non-QIO save_parallel. Vista's $HOME and $SCRATCH are NFS; $WORK (Lustre) is clean. Safe on NFS: save_mpiio through ROMIO's locking NFS driver, one writer, or partfile. Damaged SciDAC files abort MILC and QUDA on read."
scope: [software:qio, software:milc, machine:vista]
load_when: Writing or reading a QIO file from more than one rank; saving a gauge field, propagator, eigenvectors, or near-null vectors from QUDA or MILC on more than one node; choosing a MILC save keyword or a filesystem for lattice files on Vista; or diagnosing a QIO_compare_checksum mismatch (status -14) on read-back.
evidence: experiment
sources:
  - https://github.com/usqcd-software/qio/issues/19
  - https://github.com/lattice/quda/issues/1655
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/qio_field.cpp#L93-L113
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/qio_field.cpp#L400-L431
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/lib/qio/QIO_open_write.c#L203-L214
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_scidac.c#L380-L410
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_scidac.c#L494-L500
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_lat4.c#L2021-L2043
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_lat4.c#L829
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_ansi.c#L20-L37
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/com_qmp.c#L483-L490
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/io_helpers_ks.c#L849-L892
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/io_helpers_ks_eigen.c#L367-L373
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/tests/io_test.cpp#L245-L278
  - https://github.com/torvalds/linux/blob/v5.14/fs/nfs/write.c#L1319-L1352
  - https://github.com/torvalds/linux/blob/v5.14/fs/nfs/write.c#L1377-L1380
  - https://github.com/torvalds/linux/blob/v5.14/fs/nfs/file.c#L352-L380
  - https://vastnfs.vastdata.com/version/4.0.34/source/vastnfs-4.0.34.tar.xz
  - operator's screened diagnostic-rig records
observed: "2026-09-30"
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
  toolchain:
    mpi: openmpi/5.0.9, MPI-IO through ROMIO (the site module sets OMPI_MCA_io=^ompio)
    nfs_client: VAST vastnfs 4.0.34
---

# QIO and MILC parallel single-file writes lose data on NFS

> **WARNING — open upstream defect.** Tracked as
> [usqcd-software/qio#19](https://github.com/usqcd-software/qio/issues/19) and
> [lattice/quda#1655](https://github.com/lattice/quda/issues/1655). When several nodes write
> their own byte ranges of one shared file **without byte-range locks**, the file can come back
> from NFS with ranges replaced by zeros. The write reports success. On Vista, `$HOME` and
> `$SCRATCH` are NFS. **Do not write such files there from more than one node** — use
> `save_mpiio` for MILC gauge fields, `$WORK`, one writer, or partfile (below).
> **Keep this warning until the issue that covers the path in use is fixed upstream and the
> fix is validated on Vista by a multi-node write on NFS.**

## What is affected

**QIO single-file parallel writes.** A file opened with `QIO_SINGLEFILE` and `QIO_PARALLEL`
while more than one node is an I/O node. QMP's default makes every node its own I/O node, so
each rank writes its own byte range. `[source]`
- **QUDA, always:** `write_gauge_field` hard-codes `QIO_SINGLEFILE` + `QIO_PARALLEL`, and
  `write_spinor_field` uses `QIO_PARALLEL` with `QIO_SINGLEFILE` unless `partfile` is set. It
  passes no I/O-node function, and nothing selects serial mode. This covers every gauge-field
  save, and every single-file save of eigenvectors or near-null vectors.
- **MILC, by keyword:** `save_parallel_scidac`, `save_parallel_ildg` (and their `_dp` forms),
  `save_parallel_scidac_ksprop`, `save_parallel_ks_eigen`, `save_parallel_packed_ks_eigen`, and
  `save_parallel_scidac_wprop`.

**MILC's `save_parallel` too, which does not use QIO.** Each node writes its own contiguous chunk
of the MILC binary format through C stdio, `fseeko` and `fwrite` wrapped by `generic/io_ansi.c`
`[source]`, and it fails the same way `[experiment]`.

**Not affected on Vista's NFS** `[experiment]`, 2 to 8 nodes, one rank per node:
- **`save_mpiio`** (MILC binary, one collective MPI-IO write): 0 damaged of about 1,100 files, at
  local volumes up to `32^4` (1.2 GB files) and with the nodes' regions interleaved. This holds
  for the MPI-IO path the site selects, **ROMIO**, whose NFS driver takes an `fcntl` byte-range
  lock around each write. The locks are the protection: the same saves through OMPIO with its
  data-write lock switched off (`fs_ufs_lock_algorithm=1`) damaged 136 of 200 files, against
  0 of 200 with it.
- **One writer:** `save_serial`, `save_serial_scidac`, and `save_parallel_scidac` with an
  `ionode_geometry` of one I/O node.
- **One file per writer:** `save_partfile_scidac`, and QUDA partfile vectors.
- **Any writer on `$WORK` (Lustre)**, including `save_parallel_scidac` on 8 nodes at local `32^4`.
- **Single-rank and single-node writes**, where one NFS client holds the whole file.

## How often

`[experiment]` The counts are damaged files out of files written, on `$SCRATCH` (Vista VAST NFS).

| Writer | Setup (nodes, local volume, split dimension) | Damaged |
|---|---|---|
| `save_parallel` | 2, `8^4`, t | 43-66% of files, per run of 200 |
| `save_parallel` | 2 or 4, `32^4`, t | about 0.2% of node boundaries |
| `save_parallel` | 8, `32^4`, t | 40/150 files |
| `save_parallel_scidac` | 2, `8^4`, t | 56-72% of files |
| `save_parallel_scidac` | 4 or 8, `32^4`, t | every file (460/460): the head page of every node from the third on |
| `save_parallel_scidac` | 2-8, `8^4`, any split other than t | every file, roughly half the data or more |
| `save_parallel_scidac_ksprop` | 2-8, `8^4`, t, x and xyz | 1,400/1,400 files |
| `save_parallel_scidac_ksprop` | 2 and 4, `32^4`, t | 145/150 and 95/100 files |
| QUDA gauge save (`io_test` `Gauge/GaugeIOTest`) | 2 and 4 ranks | 14/20 and 15/15 failed read-back |
| QUDA single-file vector save | 2 ranks | 5/5 failed read-back |

**Local volume protects only two nodes with a t split.** There, damage falls steeply from local
`8^4` to `32^4`. It does not protect QIO files at 3 or more nodes, propagators, or any other
split. A propagator file has six records, each with its own boundaries and record end, and was
damaged at every setup tested. Treat every multi-node NFS write through an affected keyword as
damaged until it is read back.

## What to do until it is fixed

| Object | Use on NFS | Avoid on NFS |
|---|---|---|
| MILC gauge field | **`save_mpiio`** (MILC binary; reload with `reload_mpiio`, or `reload_parallel`); `save_serial`; `save_partfile_scidac`; `save_serial_scidac`; any writer on `$WORK` | `save_parallel`, `save_parallel_scidac`, `save_parallel_ildg` |
| MILC KS propagator | `save_serial_scidac_ksprop`, `save_partfile_scidac_ksprop`, `save_partfile_dir_scidac_ksprop`, `save_multifile_scidac_ksprop`, or `$WORK` | `save_parallel_scidac_ksprop` |
| MILC KS eigenvectors | `save_serial_ks_eigen`, `save_serial_packed_ks_eigen`, `save_partfile_ks_eigen`, or `$WORK` | `save_parallel_ks_eigen`, `save_parallel_packed_ks_eigen` |
| QUDA vectors (eigenvectors, near-null vectors) | partfile, accepting the layout binding in [`../quda/internals/vector-io-layout.md`](../quda/internals/vector-io-layout.md) | single-file |
| QUDA gauge save | `$WORK`, or save the field through MILC with a writer above | QUDA's gauge save on NFS: it has no safe mode. Overriding `QMP_io_node` to return the master node made `io_test` pass, but that is a diagnostic, not a supported configuration |

- **MILC has `save_mpiio` for gauge fields only.** Propagators and eigenvectors have no MPI-IO
  writer, so on NFS they need one writer or one file per writer. Their safe keywords above are
  single-writer-per-file by construction, which is what kept the gauge equivalents clean; they
  were not themselves tested.
- **`save_mpiio` depends on MPI-IO taking byte-range locks.** Keep the site's ROMIO selection,
  and re-check after any change of Open MPI module, of `OMPI_MCA_io`, or of ROMIO hints that
  disable locking. OMPIO without locks fails like `save_parallel`.
- **Relative cost** `[experiment]`, 8 nodes, local `32^4`, 1.2 GB, as MILC reports its save time:
  `save_mpiio` was the fastest, `save_serial` and partfile took a few times longer, and one QIO
  I/O node or `save_serial_scidac` took tens of times longer. MILC's figure may be taken before
  the data reaches the server, so use it to rank writers, not to budget walltime.
- **Treat a multi-rank read-back checksum mismatch on NFS as this defect** until shown
  otherwise. The data on disk is damaged; re-reading does not help.

## What a damaged file does on read

- **MILC SciDAC gauge and KS-propagator reads abort the job.** `[experiment]` 15 of 15 damaged
  files, including data damage under an intact checksum record, stopped in seconds. Rank 0
  reports `QIO_compare_checksum ... Checksum mismatch`, MILC reports `Failed to read file` or
  `Failed to reload propagator`, and calls `terminate(1)`. A SciDAC-capable multi-rank MILC is
  built with QMP, whose `terminate()` calls `QMP_abort` and so `MPI_Abort` `[source]`. The gauge
  read stops on the checksum, before the unitarity check.
- **QUDA reads abort the job** through `errorQuda`. `[source]`
- **Only the master compares the checksum**, and QIO hands every rank its data before the
  comparison. `[source]` An application that ignores the master's status can use damaged data.
  MILC's own CPU eigenvector reload (`reload_ks_eigen_file`) and the Wilson-propagator reload are
  such callers `[source]`; neither is exercised on the Vista stacks.
- **MILC-format readers** print `Checksum violation` and continue `[source]`. For a gauge field,
  the unitarity check then stops the run `[observed]`.

A damaged file therefore usually costs a failed job rather than a wrong answer. It does not
repair files already written, and a file nobody reads raises nothing.

## Mechanism

**Two damage shapes.** `[experiment]` Each zeroed range lies inside one 64 KiB page shared by two
writers:
- **Tail zeros** run from the page start to the next writer's first byte, destroying the end of
  the previous writer's range. This is the common shape at small volume, for every affected
  writer.
- **Head zeros** run from a writer's first byte to the next page boundary. With one contiguous
  range per node (a t split), they are seen only for QIO gauge files from 3 or more nodes, at the
  start of the third node's range and every later one; at 2 nodes the same shape appears only past
  the last node's data, where it zeroes the SciDAC checksum record. Where the nodes' ranges
  interleave (other splits), both shapes occur throughout the file. Head zeros are not seen on
  Lustre, for t-split propagator files, for `save_parallel`, or with byte-range locks.

**The NFS client writes whole pages.** `[source]` The Linux NFS client, and VAST's `vastnfs`
client that Vista uses, treat a page that lies beyond the file size the client has cached as
empty: they zero-fill it and mark it up to date without reading it. On writeback they extend each
partial-page write to the whole page, bounded by that cached size. They do not extend while the
file holds a POSIX or flock lock (other than one whole-file write lock), or when it was opened
`O_DSYNC`. So a node whose cached size is stale sends the bytes it did not write as zeros, and
whichever copy of the shared page reaches the server last wins `[inferred]`.

`[experiment]` A standalone writer on 4 nodes showed each non-first writer's client sending
exactly the bytes between the page start and its own first byte on every file, beyond what the
application wrote. With `fcntl` byte-range locks held, it sent none and no file was damaged. That
extension produces the tail shape. **What makes a writer extend forward, producing the head
shape, and why the second node is exempt, is not established**: nothing in QIO's write path
refreshes the cached size, and the standalone writer never reproduced it.

**Consequences for a fix:** a writer that takes byte-range locks, opens `O_DSYNC`, writes through
one node, or writes page-aligned ranges avoids the extension. VAST documents a `noextend` mount
option for `vastnfs` that turns the extension off for multi-client NFSv3 use; it is a site-level
setting, absent from a Vista login node's mount options when checked, and untested here. QIO's
checksum is computed by each sender before its data leaves, so the file carries the correct
checksum of data that never reached disk intact, and the mismatch a reader reports is real.

## Checking a fix

The warning's removal needs a multi-node write on Vista's NFS, validated by read-back. With
QUDA's `io_test`, use `Gauge/GaugeIOTest.*` for the gauge path. **At QUDA `00c7ef33` the
`ColorSpinorIOTest` names state the file format backwards** `[source]`: the name gets
`_singlefile` when the `partfile` parameter is true and `_partfile` when it is false, so a test
named `..._singlefile_...` writes partfile and passes on NFS. Confirm the format from the test's
own log line, `Start saving ... in PARTFILE format` or `in SINGLEFILE format`, before counting a
pass. The gtest summary line is colored; strip escape codes before matching it.

## Evidence

- A standalone C/MPI writer imitating QIO's write order, with no QIO, QUDA or GPU, on
  2 × `gpu-gh200`, every byte verified by a node that wrote none of the files: 350/400 and 184/200
  files damaged on `$HOME` (NFS), 0/400 on `$WORK` (Lustre). Writers taking turns and reopening
  between turns: 0/200. Page-aligned ranges: 0/200.
- MILC gauge, propagator and MPI-IO legs on 2, 4 and 8 × `gpu-gh200`, scored byte by byte against
  a single-writer reference and cross-checked from a node that wrote none of the files. The
  counts are in the table above.
- Every failing QUDA `io_test`'s file showed the tail shape, and each checksum recomputed from
  the file equalled the reader's "Found" value.

## Not claimed

- Why t-split QIO gauge files show head zeros from the third node on and never at the second; why
  t-split propagator files do not.
- Safety of `save_mpiio` under another MPI library, another MPI-IO component, or with locking
  disabled by a hint; beyond 8 nodes; or on NFS mounts other than Vista's.
- The propagator and eigenvector alternatives, which follow from single-writer construction and
  were not run.
- MILC-format readers of damaged propagators or eigenvectors: no parallel MILC-format write of
  those exists to produce one.
- NFS mounts other than Vista's are expected to behave the same way when their client extends
  writes to the page `[inferred]`; none was tested.
