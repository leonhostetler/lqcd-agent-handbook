---
title: QMP
summary: Role and routing guidance for the USQCD message-passing layer used by composed stacks.
scope: [software:qmp]
load_when: Resolving QMP communication requirements or interpreting a stack's QMP dependency.
evidence: source
sources:
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/CMakeLists.txt
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/include/qmp.h
observed: "2026-08-17"
observed_on:
  software:
    qmp:
      commit: 3010fef5b5784b3e6eeec9fff38cb9954a28ad42
      branch: master
---

# QMP

QMP supplies the USQCD message-passing API. It can use MPI for multi-rank execution or a
single-node backend. In the validated QUDA and MILC stacks, QUDA acquired and built QMP
with its MPI backend; QMP was a dependency rather than the primary software profile.

Use `project.yaml` for the repository, intrinsic interfaces, and build-option meanings.
The consuming stack records the exact tested revision, acquisition mode, MPI toolchain,
and runtime evidence.
