---
title: MILC lattice I/O cost is a keyword choice, not a filesystem problem
summary: reload_parallel redistributes a lattice site by site over the message layer after reading it, so it is slow for reasons striping cannot fix; reload_mpiio maps each rank's sub-block onto the file with one collective read and costs a local-volume host buffer to do it.
scope: [software:milc]
load_when: Choosing a MILC reload or save keyword for a large lattice, diagnosing slow gauge configuration I/O, or sizing host memory for a run that reads or writes a lattice.
evidence: experiment
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_lat4.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/io_helpers.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/milc_datatypes.h
observed: "2026-09-21"
observed_on:
  machine: perlmutter
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC lattice I/O cost is a keyword choice, not a filesystem problem

`reload_parallel` and `reload_mpiio` both read one shared file with every rank participating,
and they are not two spellings of the same thing. On a `96^3 x 192` single-precision gauge
configuration — `45.6` GiB — at 8 ranks on 2 nodes, with the same file, the same executable,
the same `node_geometry` and the same striping, only the keyword changing:

| keyword | `Time to reload gauge configuration` |
|---|---|
| `reload_parallel` | `713.9` s |
| `reload_mpiio` | `24.82` s |

Both verified their checksums. A second, independent `reload_mpiio` read of the same gauge
configuration at 144 ranks took `3.835` s, also checksum-verified, so the MPI-IO path keeps
improving with rank count rather than saturating.

## Why, and it is not the read

The tempting reading is that one path issues better-shaped reads than the other. The dominant
cost is downstream of the read entirely.

`r_parallel` divides the file equally among ranks **in file order**, so the block a rank reads
is not the block it owns. It then redistributes the lattice **site by site over the message
layer**, in groups of four sites, each carried in a struct holding the site's `x, y, z, t` and
its four links, because the arrival order is not guaranteed to match the deal order. MILC's own
comment on that loop reads *"We don't know if this pattern is generally optimal."*

`r_mpiio` does no redistribution at all. It builds a seven-dimensional subarray view —
`{nt, nz, ny, nx, 4, 3, 3}`, with the rank's sub-block taken from its logical grid coordinate —
commits it as the file view, and issues a collective `MPI_File_read_all`. Every rank reads
exactly the sites it owns, and the MPI-IO layer is free to aggregate and reorder the underlying
transfers.

So the gap is an all-to-all site exchange against no exchange at all, and it grows with the
lattice rather than with anything about the filesystem.

## Striping is not the alternative remedy

This is worth stating because it is the first thing a reader reaches for, and it was tried.
The same file at `stripe_count 1` and at `stripe_count 48` gave `>560` s (unfinished) and
`713.9` s under `reload_parallel` — no improvement in either direction. Measured single-stream
bandwidth on that file was `1.1` GB/s, so raw bandwidth was never the binding constraint.

**A site-by-site redistribution cannot be restriped away.** Reach for the keyword first, and
treat a striping experiment as a way to confirm bandwidth is not the problem rather than as a
fix.

## What the MPI-IO path costs in host memory

It allocates the rank's entire local gauge field, in single precision, as one transient buffer,
freed when the read completes:

```c
size_t gauge_node_size = sites_on_node * 4 * sizeof(fsu3_matrix);
fsu3_matrix *buf = (fsu3_matrix *)malloc(gauge_node_size);
```

`fsu3_matrix` is `fcomplex e[3][3]`, so **`288` bytes per site**, four links at `72` bytes each.
`r_parallel`'s buffer is instead a fixed `MAX_BUF_LENGTH = 4096` sites, `1.125` MiB, independent
of local volume.

The difference is therefore large, one-directional and countable rather than something to
measure:

| ranks over `96^3 x 192` | sites per rank | `reload_mpiio` buffer | `reload_parallel` buffer |
|---|---|---|---|
| 8 | `21,233,664` | `5.70` GiB | `1.125` MiB |
| 144 | `1,179,648` | `324` MiB | `1.125` MiB |

**Budget it at few ranks.** The buffer is a per-rank local-volume object, so it shrinks as the
job grows; the expensive case is a large lattice read by a small job, which is exactly the shape
of a preparatory or single-node run. Nothing here says the whole run's peak is higher under
MPI-IO — only that this buffer exists and how big it is.

## The write side

`w_mpiio` is the same construction in reverse: the same seven-dimensional subarray view, the
same `sites_on_node * 4 * sizeof(fsu3_matrix)` buffer, and a collective write in place of a
collective read. The mechanism and the memory cost therefore transfer.

**The write timing does not, because it has not been measured.** No `save_parallel` comparison
has completed, so there is no observed factor for the save side and none should be assumed from
the read side.

## Scope and limits

**The direction is well-supported; the factor is not portable.** `28.8x` is one controlled pair,
one lattice, one machine, one placement, 8 ranks, single precision, one MILC commit, one
measurement per arm with no repeats. Carry the scope whenever the number travels, and do not
turn it into a rule of thumb. What generalises is the mechanism and the sign, not the ratio.

**Read only.** Both timings above are reloads.

**`reload_mpiio` is not a universal replacement.** It does not detect a SciDAC or LIME file and
will read one as MILC binary — see
[`gauge-read-dispatch.md`](gauge-read-dispatch.md), which owns that correctness question. The
performance argument here applies to MILC's own binary formats, and it never overrides the
format constraint. Built without MPI, `r_mpiio` prints an error and terminates rather than
falling back, so the keyword is a hard requirement on the build as well.
