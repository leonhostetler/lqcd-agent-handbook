---
title: Perlmutter communication-stack defects
summary: Two reproduced defects in the Perlmutter communication stack — silent whole-message loss on the CXI provider's CUDA DMABUF path when the libfabric registration cache is disabled, and a cray-mpich MPI_Init node-map failure sized by the encoded PMI_process_mapping string — with their triggers, mechanisms, workarounds, and the knobs that look relevant and are inert.
scope: [machine:perlmutter]
load_when: A GPU-aware MPI job on Perlmutter loses data silently, aborts inside MPI_Init, or is about to adopt an FI_MR_* registration setting or MPICH_RANK_REORDER_METHOD.
evidence: reproduced
observations: 9
sources:
  - operator's screened split-grid deflation campaign records
  - https://ofiwg.github.io/libfabric/main/man/fi_mr.3.html
  - https://github.com/ofiwg/libfabric/issues/9315
observed: "2026-09-17"
observed_on:
  machine: perlmutter
  toolchain:
    cpe: "25.09"
    cray-mpich: "9.0.1 and 9.1.0"
    libfabric: "1.22.0"
    cray-pmi: "6.1.17"
---

# Perlmutter communication-stack defects

Both defects below are in vendor software, not in any application. Both are reproduced, both have
minimal reproducers that need no lattice code, and both were reported to the site. Neither is
expected to be fixed soon, so the workarounds are the operative content.

Node names, job identifiers, ticket references, and run paths are campaign state and are
deliberately absent; they live in the working project. Variable and symbol names are not — a
session meeting either failure needs to grep for the exact string.

## Disabling the libfabric registration cache silently loses whole messages

**Trigger.** Either of two documented libfabric settings, used exactly as documented:

- `FI_MR_CACHE_MAX_COUNT=0` — `fi_mr(3)`: *"Setting this to zero will disable registration
  caching."*
- `FI_MR_CUDA_CACHE_MONITOR_ENABLED=0`, with `FI_MR_CACHE_MAX_COUNT` left at its default.

Both produce bit-identical failures.

**Symptom — the worst class there is.** Whole messages are never delivered. `MPI_Waitall` returns
`MPI_SUCCESS`, no MPI error is raised, libfabric logs nothing, and the destination region still
holds whatever was there before the exchange. Not stale data, not a partial write, not torn at a
boundary: **whole messages, cleanly missing**, with wrong-element counts that are exact multiples
of one message. At and above 65536 bytes per direction, exactly one message of eight arrives.
A `grep -iE 'libfabric|cxi|warn|fallback|register'` over a failing run returns nothing.

**What it requires.**

- **Device memory.** Host buffers are clean at every size tested.
- **Inter-node traffic.** A single-node run never initialises libfabric MR at all — its
  `MPICH_ENV_DISPLAY=1` dump carries zero `FI_` lines.
- **At least two concurrently outstanding non-blocking transfers.** One per direction is clean at
  every size tested.

It spans both eager and rendezvous, so the protocol is not the discriminator, and reusing buffers
versus reallocating them every iteration fails identically, so address churn is not either.

**Where it lives.** `FI_CXI_DISABLE_DMABUF_CUDA=1` makes every configuration clean *while the cache
is still disabled*. The CXI provider enables DMABUF for CUDA **by default**, so this path is live
for every GPU-aware job on the machine; it is only reached in the broken form when the cache is
bypassed.

**This is not a resource limit.** `FI_MR_CACHE_MAX_COUNT` of 1, 2, 4, 8 and 64 are all
bit-identical clean. A cache of eight entries is tiny — if the failure were "too few registrations
retained", eight would be far worse than zero is bad. Zero selects a *different code path*, and
that path is what is broken.

**Workaround.** Never set `FI_MR_CACHE_MAX_COUNT=0`, and never set
`FI_MR_CUDA_CACHE_MONITOR_ENABLED=0`. Any count of one or more is clean, including small bounded
values, so a bounded count remains available as a mitigation for registration growth. If the
disabled path is genuinely needed, set `FI_CXI_DISABLE_DMABUF_CUDA=1` alongside it.

**The residual risk, which is the reason the report was worth filing.** Nothing observable from
user space says whether the same uncached DMABUF path is ever taken with the cache nominally
*enabled* — on eviction, on cache exhaustion, on a failed registration, after `fork`, or when
`FI_MR_CACHE_MAX_SIZE` is hit. If it is, this is a production silent-corruption risk and not merely
a diagnostic-only one. Everything measurable says the cache being on is sufficient protection;
nothing measurable says why.

### Knobs that look relevant here and are inert

This defect is the recorded instance behind
[`conventions/diagnostic-rigs.md`](../../conventions/diagnostic-rigs.md)'s rule that only an
outcome *change* proves a setting applied. Four legs were spent on settings that established
nothing, and the specific names are worth carrying because each is a plausible thing to reach for:

| setting | why the leg was void |
| --- | --- |
| `FI_MR_CACHE_MONITOR=disabled` | governs `FI_HMEM_SYSTEM` — **host** memory. The device-memory knob is `FI_MR_CUDA_CACHE_MONITOR_ENABLED`. |
| `FI_HMEM_DISABLE_P2P` | the CXI provider **does not honour it at all** (libfabric issue #9315, closed as not planned). |
| `FI_HMEM_CUDA_USE_DMABUF` | the name in the upstream `fi_cxi(7)` man page. **It does not exist in libfabric 1.22.0 on this system** — the working name is `FI_CXI_DISABLE_DMABUF_CUDA`. Had the man-page name been used, the leg that actually found the mechanism would have been a silent no-op. |
| `FI_CXI_DISABLE_HMEM_DEV_REGISTER`, `FI_CXI_SAFE_DEVMEM_COPY_THRESHOLD`, `FI_CXI_RDZV_THRESHOLD` | all three left the failure bit-identical, so they exonerate nothing. |

**`fi_info -p cxi -e` lists what this build actually accepts. Check it first, every time**, rather
than an upstream man page or a newer release's documentation. `MPICH_ENV_DISPLAY=1` then confirms
what reached the process; keep it on.

### How the corrupted region was identified before any reproducer existed

Worth keeping as technique. The application aborted on a unitarity check with a fixed error count
of 32768. That count was **invariant under local volume** — identical at 3 ranks (65536 local
sites) and at 2 ranks (98304) — while matching the **halo**, which is 16384 sites in both. A count
that does not move with the interior but is fixed by the halo identifies the *received* data as the
corrupt thing, using only a number the application already prints.

Generalise it: to separate a fault in received data from a fault in computed data, vary a parameter
that scales the interior while the halo is fixed, and read the error count.

**And a note on luck.** The missing bytes happened to land in a field QUDA checks for unitarity, so
the job aborted. Nothing detected the loss itself — the abort was a downstream consistency check
noticing the numbers could not be right. Had the same bytes gone missing in a propagator, the run
would have produced wrong physics and finished cleanly.

## cray-mpich 9.1.0 `MPI_Init` fails to build its node map above an encoded-string limit

**Trigger.** `MPICH_RANK_REORDER_METHOD=3` — the method that reads a `MPICH_RANK_ORDER` file —
under cray-mpich 9.1.0. With `MPICH_RANK_REORDER_METHOD` unset, the same binary starts.

**What actually fails.** `MPIR_pmi_build_nodemap` cannot populate node ids from
`PMI_process_mapping` and MPICH declares a fatal internal error before `MPI_Init` returns:

```
Abort(...): Fatal error in internal_Init_thread: Internal MPI error!, error stack:
MPII_Init_thread(215)......:
MPIR_build_nodemap(146)....:
MPIR_pmi_build_nodemap(330): Internal MPI error!  unable to populate node ids
                             from PMI_process_mapping
```

**The size that matters is the byte length of the encoded mapping string against a hard-coded
1024-byte buffer** — not the node or rank count. `MPIR_pmi_build_nodemap+0x24` does
`buf = malloc(pmi_max_val_size)` with `movl $0x400`, then calls `PMI2_Info_GetJobAttr` with
`buflen=1024`. That accessor **refuses an over-length value rather than truncating it**: it returns
`found=0` and leaves the buffer untouched. `MPL_rankmap_str_to_array` then rejects the empty buffer
at byte 0 — it fails only on `str == NULL`, `str[0] == '\0'`, or a string not beginning with
`"(vector"`, and never on running out of ranks — and line 330 raises.

Held at **two nodes** with only the rank count varying, 252 ranks encode to 1016 bytes and pass;
254 encode to 1024 and fail. Two ranks apart, which no resource limit behaves like. The usable
maximum is 1023 bytes plus the NUL.

**Why a rank-order file makes it much worse.** A `grid_order`-style permutation scatters
consecutive ranks across *non-consecutive* node ids, which the `(start_node, num_nodes,
ranks_per_node)` triples cannot fold, so those strings cost ~8–9 bytes per rank rather than ~4. The
same job therefore fails at a far lower node count with a reorder file than without one — the
observed threshold sits between 16 and 32 nodes for this campaign's files.

**Two regimes, and only one of them is diagnosable.** At 32 and 64 nodes the path fails without
damaging the heap and MPICH's real message survives, in about three seconds with no core. From 144
nodes up the same path has also corrupted the heap by then, so when
`MPIU_CRAY_err_printf_wcname` formats the error line its `ctime_r` → `/etc/localtime` → stdio
buffer allocation is the first `malloc` to walk the damage, and glibc aborts with
`malloc(): invalid size (unsorted)` — **killing the process before the real message is ever
written**. `MPICH ERROR`, `Internal MPI error` and `PMI_process_mapping` appear **zero** times in
any 288-node log of this failure. The allocator abort that is the face of this at scale is a
secondary casualty in the error-reporting path, not the fault.

This is the recorded instance behind [`../../modes/debugging.md`](../../modes/debugging.md)'s rule
about reducing scale to find the regime where the diagnostic survives.

**Attribution.** A three-leg, two-node, forty-second test with only the linked MPI moving — and
`cray-pmi/6.1.17`, the *producer* of the value, held fixed — isolates it to the MPI library.
`MPIR_pmi_build_nodemap`, `MPIR_build_nodemap` and `MPIR_pmi_build_nodemap_fallback` **do not exist
in 9.0.1 at all**; both libraries carry `MPL_rankmap_str_to_array` and
`mpid_cray_pmi_get_nidlist_ptr`, and both hard-code `movl $0x400`, so the buffer size is a
pre-existing condition and not the regression. The `_fallback` variant is evidently not reached on
this path: the disassembly shows a NULL return from `get_jobattr` branching away while a non-NULL
but unparseable buffer goes straight to `MPIR_Err_create_code`. **What 9.0.1 does instead is not
traced and is inside vendor source — treat the mechanism claim as inferred and the byte threshold
as measured.**

### Workarounds, ranked

| | workaround | rebuild? | status |
| --- | --- | --- | --- |
| **W1** | unset `MPICH_RANK_REORDER_METHOD` | no | **proven at 288 nodes**; costs the `grid_order` placement |
| **W2** | `MPICH_RANK_REORDER_METHOD=1` (SMP) or `=2` (folded) | no | pass at 256 ranks; unproven at 1152 |
| **W3** | pin `cpe/25.09` + `cray-mpich/9.0.1` + `cudatoolkit/12.9` | **yes, everything** | **proven at 288 nodes with `METHOD=3`**; has a shelf life |
| **W4** | swap the MPI library at runtime only | no | **do not** |

**W1** gives up only placement, which is a performance question rather than a correctness one, and
makes measuring what the reorder was worth a two-leg experiment rather than a blocker. Keep the
rank-order files; W2 and W3 both want them.

**W2** works because methods 1 and 2 apply a built-in permutation, never open `MPICH_RANK_ORDER`,
and place ranks *contiguously*, so the mapping folds to a handful of triples and never approaches
1024 bytes. Note that `METHOD=0` (round-robin) is the exception among the built-ins and **does
fail**, precisely because round-robin is maximally scattered — it is the configuration the
two-node threshold measurement above used. Add `MPICH_RANK_REORDER_DISPLAY=1` when comparing a
built-in placement against `grid_order`'s.

**W3** is the only option that keeps `METHOD=3` and therefore keeps the placement a timing campaign
is measuring; the older modules remain installed and loadable, 26.03 is merely the default. Three
costs are real: a full rebuild of every dependent repository; explicit module pinning in every
submit script, because `module reset` loads the *current* site default and re-arms the
start-time-resolution trap in
[`conventions/batch-scripts.md`](../../conventions/batch-scripts.md); and a deliberate tunecache
clear, because `QUDA_TUNE_VERSION_CHECK=0` in a submit script will **silently reuse** a cache
written under the newer toolchain — see
[`QUDA autotuning and tunecache reuse`](../../software/quda/internals/autotuning.md). A partial
rollback that swaps only `cray-mpich` is adequate for a standalone test program and is not a
supported combination for production.

**W4** nearly works and should not be done. Every MPI symbol imported by the application and its
libraries is defined in 9.0.1; the only mechanical obstacle is the soname — the binaries need
`libmpi_gnu.so.12` and 9.0.1 ships `libmpi_gnu_123.so.12`, which a symlink would satisfy. It is a
backwards minor-version swap under a binary compiled against 9.1.0 headers, with the CUDA GTL layer
and libfabric expected to match, unsupported by the vendor and unvouchable if a large run then
produces odd numbers.
