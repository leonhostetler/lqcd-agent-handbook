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
