---
title: QIO
summary: Role and routing guidance for the USQCD lattice-data I/O layer used by composed stacks.
scope: [software:qio]
load_when: Resolving QIO linkage, parallel-build requirements, or a stack's demonstrated I/O scope.
evidence: source
sources:
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/CMakeLists.txt
  - https://github.com/usqcd-software/qio/blob/273841537392f9465d229c957228755e923408eb/README
observed: "2026-08-17"
observed_on:
  software:
    qio:
      commit: 273841537392f9465d229c957228755e923408eb
      branch: master
---

# QIO

> **WARNING — open upstream defect
> ([qio#19](https://github.com/usqcd-software/qio/issues/19),
> [quda#1655](https://github.com/lattice/quda/issues/1655)).** Multi-rank `QIO_SINGLEFILE` +
> `QIO_PARALLEL` writes lose data on NFS, and QUDA uses that mode for every gauge-field save.
> See [`parallel-singlefile-writes.md`](parallel-singlefile-writes.md) before writing a QIO
> file from more than one node. Keep this warning until that issue is fixed upstream and
> validated.

QIO supplies portable USQCD lattice-data file I/O and can be built for scalar or
QMP-enabled parallel use. Its CMake build includes a bundled C-LIME implementation unless
an external one is selected.

Use `project.yaml` for intrinsic capabilities and option meanings. A consuming stack must
separate linkage from runtime evidence: an application linked against QIO has not validated
QIO reads or writes unless its recorded test actually performs them.

## Partfile and single-file layout binding

QIO's partfile format embeds a per-partition DML sitelist, so a partfile record is readable
only under the I/O layout that wrote it; single-file records carry no sitelist and no such
binding. Because the consequence is a save-format decision made in the calling library, that
mechanism is documented once in
[`software/quda/internals/vector-io-layout.md`](../quda/internals/vector-io-layout.md).
