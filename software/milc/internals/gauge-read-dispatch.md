---
title: MILC gauge read-path dispatch and the SciDAC format check
summary: Which reload keywords detect a SciDAC/LIME gauge configuration and which read it as MILC binary regardless, and why the failure produces no error.
scope: [software:milc]
load_when: Choosing or auditing a MILC reload keyword, reading a SciDAC or ILDG gauge configuration, or writing a launcher guard over a gauge input.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_lat4.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_lat_utils.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/file_types.h
observed: "2026-09-21"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC gauge read-path dispatch and the SciDAC format check

MILC's reload keywords are not three implementations of one read. **Two of them detect a
SciDAC/LIME gauge configuration and hand it to QIO; the third reads whatever it is given as MILC's
own binary format.** Choosing between them is therefore a correctness decision, not a
performance one, and the wrong choice on a SciDAC file does not announce itself.

## What each keyword does

| Input keyword | Entry point | Detects LIME? |
|---|---|---|
| `reload_serial` | `restore_serial` | **yes** — and its reader guards internally as well |
| `reload_parallel` | `restore_parallel` | **yes** — the entry point branches after the reader returns |
| `reload_mpiio` | `restore_mpiio` | **no** |

`restore_serial` and `restore_parallel` compare the header's magic number against
`LIME_MAGIC_NO` and, on a match, close the file, discard the header and re-read through
`restore_serial_scidac` / `restore_parallel_scidac`. Both require `HAVE_QIO`; built without it
they print that the file looks like SciDAC and terminate, which is a clear failure.

`restore_mpiio` performs no such comparison. It calls the parallel reader and then the MPI-IO
reader unconditionally, so a SciDAC file is parsed as MILC binary.

## Why nothing fails

The format check that would catch it has already been skipped by the time the data is read.
`read_gauge_hdr` recognises the LIME magic number and **returns immediately**, by design — its
own comment is *"We do not read any further here: Set flag and return"*. It sets the header's
magic number and nothing else, so the field order, dimensions and byte offsets stay unset.

**The asymmetry is inside the readers, not only at the entry points.** The serial reader checks
the flag after broadcasting the header and returns before reading the site list. **The parallel
reader has no such check**: it broadcasts the unpopulated header and calls `read_site_list`,
which branches on a field order that was never assigned. This is why `restore_parallel` must do
its own test and re-open the file, and why `restore_mpiio` — which uses the same reader and
omits the test — has nothing standing between it and the data.

**The log does not read as a failure. It reads as a success.** `read_gauge_hdr` prints
*"Reading as a SciDAC formatted file"* before returning. Under `reload_mpiio` that line appears
and is then ignored: the run proceeds to read the file as MILC binary. **A reader scanning the
output sees the format correctly identified**, which is worse than silence, because it is
evidence pointing the wrong way.

## What to do about it

**Use `reload_parallel` for a SciDAC or ILDG gauge configuration.** `reload_mpiio` is valid only for
MILC's own binary formats.

**Put the guard in the launcher or the input generator, not in a convention.** There is no
format check to fail and no error text to match, so a rule that is only written down cannot
catch a copied-forward input file. Assert the keyword the job will actually use.

**Determine the format from the file, not its name.** A SciDAC/LIME file begins with the four
bytes `45 67 89 ab`; an extension or a directory convention is not evidence. Note also that the
same magic number is accepted byte-reversed, so a check on the file's own bytes must allow both
orders.

## Scope and limits

**Evidence: source**, at the commit recorded above, read directly rather than inferred from
behaviour. **No runtime observation exists** — nobody has deliberately run `reload_mpiio` on a
LIME file to record what it produces. The dispatch and the missing check are certain; the
precise downstream symptom is not documented here because it has not been observed, and it
should not be guessed at from the code path.

This is a property of MILC's generic I/O layer, so it applies to any application that reloads a
lattice, not to one application family. Re-check it on a MILC upgrade: it is a three-line
difference between two functions, and nothing in the code prevents it being closed.
