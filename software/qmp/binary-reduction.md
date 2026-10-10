---
title: QMP_binary_reduction sums multi-byte values wrongly on more than one rank — MILC's NERSC checksum
summary: "QMP's MPI backend runs QMP_binary_reduction as an MPI_Allreduce of raw bytes with a user operation that ignores the length MPI passes it. Open MPI 5.0 hands that operation pieces of the buffer, so one 32-bit sum was wrong in 488 of 1,000 trials on 2 ranks and in every trial on 4. In MILC built on QMP the only caller is the NERSC checksum: the CKSUM that MILC prints is meaningless on more than one rank, and a NERSC archive file saved from more than one rank carries a wrong header checksum. MILC's file-integrity checksums use a native XOR reduction and are unaffected."
scope: [software:qmp, software:milc]
load_when: Reading or comparing the CKSUM in MILC's CHECK NERSC LINKTR line; fingerprinting a gauge field across rank counts; saving a NERSC archive file (save_serial_archive) from more than one rank, or seeing an archive checksum violation on reading one; or calling QMP_binary_reduction.
evidence: experiment
sources:
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/lib/mpi/QMP_comm_mpi.c#L295-L327
  - https://github.com/usqcd-software/qmp/blob/3010fef5b5784b3e6eeec9fff38cb9954a28ad42/lib/mpi/QMP_comm_mpi.c#L252-L259
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/com_qmp.c#L611-L620
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/com_qmp.c#L725-L731
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/com_mpi.c#L780-L790
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/nersc_cksum.c#L28-L55
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_helpers.c#L232-L250
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_lat4.c#L2096-L2124
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/io_lat4.c#L795-L811
  - operator's screened Horizon test-program run, probe run and production outputs, 2026-10-10
observed: "2026-10-10"
observed_on:
  machine: horizon
  node_type: gpu-gb200
  software:
    qmp:
      commit: 3010fef5b5784b3e6eeec9fff38cb9954a28ad42
      branch: master
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
  toolchain:
    mpi: openmpi/5.0.11 with ucx/1.22.0
---

# QMP_binary_reduction sums multi-byte values wrongly on more than one rank

> **WARNING — QMP defect; upstream status not checked.** On more than one rank, MILC built on
> QMP prints a NERSC `CKSUM` that does not identify the field, and writes a wrong `CHECKSUM` into
> a NERSC archive header. **Never compare that CKSUM across runs or rank counts.**

## Mechanism

`QMP_binary_reduction(buffer, count, func)` reduces an opaque buffer of `count` bytes with a
caller's function. QMP's MPI backend creates an `MPI_Op` around that function and calls
`MPI_Allreduce` with `count` elements of `MPI_BYTE` (`QMP_comm_mpi.c` L295–L327). MPI may apply
an operation to any segment of the elements, and says how many through its length argument; QMP's
wrapper ignores the length and calls the caller's function on the segment's address, which then
adds a whole value at every segment.

**Observed** with a test program linked against the stack's `libqmp`, 1,000 trials per rank count,
each rank contributing values chosen so the sum carries between bytes:

| Ranks | Bytes per operation call | `QMP_binary_reduction` wrong |
|---|---|---|
| 2 | 2 | 488 of 1,000 (when the low half carried) |
| 4 | 1 | 1,000 of 1,000 |

A plain-MPI replica of QMP's pattern was wrong in the same trials, and MPI's own `MPI_UNSIGNED`
sum was right in all. How Open MPI segments depends on its algorithm choice, so a correct result at
some rank count proves nothing: the probe's 8-rank point happened to print the one-rank value.

## What it reaches in MILC

With QMP, MILC's `g_uint32sum` calls `QMP_binary_reduction` (`com_qmp.c` L611–L620); MILC built
on MPI alone sums with a native `MPI_UNSIGNED` reduction (`com_mpi.c` L780–L790) and is not
affected. The one caller is `nersc_cksum` (`nersc_cksum.c` L28–L55), so:

- **The printed CKSUM is meaningless on more than one rank.** MILC prints it with the plaquette
  after every load, fresh or warm start (`io_helpers.c` L232–L250). `[observed]`: the probe's
  consistency leg printed four checksums for one field at 1, 4, 8 and 16 ranks, while its
  plaquette, link trace and correlators agreed; two production campaigns on 4 ranks printed
  different checksums for every lattice file both had read.
- **A NERSC archive saved from more than one rank carries a wrong header checksum.**
  `save_serial_archive` writes `nersc_cksum()` into the header (`io_lat4.c` L2096–L2124). MILC's
  own archive reader sums on the reading node alone, prints `Archive style checksum violation`, and
  continues (L795–L811); another reader may refuse the file. `[inferred]` from source; no archive
  was written.
- **File integrity checks are unaffected.** MILC's own file checksums reduce with `g_xor32`
  (`com_qmp.c` L725–L731), which QMP runs as a native `MPI_BXOR` (`QMP_comm_mpi.c` L252–L259).
  `[observed]`: every finished production read on 4 and 8 ranks printed `Checksums … OK`.

## What to do

- To fingerprint a field across runs or rank counts, compare the plaquette and link trace to a
  relative limit; they are floating-point sums whose order varies, so not exactly.
- Save gauge fields in a format whose checksum survives: MILC's own or SciDAC formats, not
  `save_serial_archive` from more than one rank.
- Before relying on any other `QMP_binary_reduction` caller with values wider than one byte,
  treat its result as suspect on more than one rank. The likely fix in QMP is to reduce one element
  of a contiguous datatype spanning the whole buffer, which MPI cannot split; it has not been
  tested here.
