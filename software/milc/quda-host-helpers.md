---
title: MILC's QUDA host-side helpers and build switches
summary: What include/generic_quda.h and milc_to_quda_utilities.c provide, which helpers are live, why the whole site lattice is pinned under QUDA, how QUDA reads the site struct in place, when "managed" memory silently becomes pinned, how WANT_*_GPU switches act through object selection and guards, and the unchecked local copies of QUDA declarations.
scope: [software:milc, software:quda]
load_when: Adding or changing MILC code that calls QUDA, allocates host memory for QUDA, passes the site struct or momentum to QUDA, or adds a WANT_*_GPU switch or USE_*_GPU guard.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quda.h
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/milc_to_quda_utilities.c#L13-L58
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/include/generic_quda.h
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic/milc_to_quda_utilities.c#L50-L140
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile#L1419-L1422
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/Makefile#L604-L619
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/CMakeLists.txt#L207-L217
  - https://github.com/milc-qcd/milc_qcd/blob/a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785/generic_ks/ks_meson_mom_quda.c#L337-L385
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/make_lattice.c#L25-L30
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/make_lattice.c#L67-L71
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_spectrum/control.c#L1197-L1200
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_imp_rhmc/lattice.h#L31
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/ks_imp_rhmc/update_rhmc.c#L150-L156
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/ranmom.c#L42-L46
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L593-L617
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L776-L786
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L1278-L1344
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L1422-L1428
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/gauge_stuff.c#L257
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L1161-L1164
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Make_template_combos#L121-L128
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/ks_meson_mom_quda.c#L68-L113
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/contraction_cpu.c#L205-L231
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda_milc_interface.h#L169-L176
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda_milc_interface.h#L1333-L1334
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/enum_quda.h#L588-L591
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L975-L1113
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/mat_invert.c#L1279-L1296
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda_milc_interface.h#L15-L19
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda_define.h.in#L9-L14
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L396-L407
observed: "2026-10-07"
observed_on:
  software:
    milc:
      commit: a5f8f9fa2b473abb2cf2b4465a34ae4b71c5e785
      branch: develop
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
---

# MILC's QUDA host-side helpers and build switches

MILC's side of the QUDA boundary has two pieces:

- `include/generic_quda.h`, which every QUDA-calling file includes;
- `generic/milc_to_quda_utilities.c`, which starts and stops QUDA.

Where the work itself belongs, in QUDA's core or in its MILC adapter, is decided in
[`../quda/interface-layers.md`](../quda/interface-layers.md). This leaf covers the host-side
plumbing a MILC change has to fit into.

## What the header provides

The whole header is guarded by `HAVE_QUDA` and includes QUDA's `quda_milc_interface.h`, which
in turn includes `quda.h`. Every helper in it is `static`, so each file that includes it gets
its own copy. Through `6b9b8a06` they were plain `static`, so a compiler warning about an
unused static function in such a file was noise, not a sign of a broken path; from `d17e9559`
(PR #99, 2026-10-06) they are `static inline`, which silences that warning.

| Helper | Does | Live at the observed revision |
|---|---|---|
| `initialize_quda()`, `finalize_quda()` | declared here, defined in `milc_to_quda_utilities.c` | yes |
| `newQudaMILCSiteArg()` | describes the site array to QUDA: base pointer, link and momentum byte offsets, `sizeof(site)` | yes, in gauge force, momentum, action, update, plaquette, Polyakov-loop, gauge-fixing and reunitarization callers |
| `create_G_from_site_quda()`, `destroy_G_quda()` | copy every site's four links into a separate pinned array, and free it | yes: `fermion_links_from_site.c`, `wilson_flow/integrate_quda.c` |
| `create_G_quda()`, `fast_copy()` | the pinned allocation and the `memcpy` the line above uses | internal only |
| `copy_to_site_from_G_quda()` and all four `*_M_quda` momentum helpers | the reverse copy, and the momentum equivalents | **no caller** |
| `load_quda_default_eig_args()`, `print_quda_eig_args()` | declared here from `d17e9559`, defined in `milc_to_quda_utilities.c`: fill a `QudaEigensolverArgs_t` from `param.eigen_param` for every deflation consumer, and dump it | yes: the QUDA CG wrapper, `load_evecs_quda`, and the exact-current caller |

The comments on `copy_to_site_from_G_quda` ("momentum") and `destroy_M_quda` ("gauge-field")
describe the wrong field. Read the body, not the comment.

## Starting and stopping QUDA

`initialize_quda()` is lazy and idempotent. On its first call it:

- passes MILC's communicator to QUDA (`qudaSetMPICommHandle(mycomm())`);
- sets the lattice and rank-grid sizes from `nx..nt` and `get_logical_dimensions()`;
- sets the verbosity from the `QUDA_VERBOSITY` make variable, through `SET_QUDA_*` defines;
- calls `qudaInit`.

The device field it sets to 0 is commented "only valid for single-gpu build".

`finalize_quda()` first frees QUDA-side MILC state: the deflation spaces (under `USE_CG_GPU`
through `6b9b8a06`; under any of `USE_CG_GPU`, `USE_EIG_GPU`, or `USE_CURRENT_GPU` from
`d17e9559`), and the multigrid hierarchy under `MULTIGRID` (and `USE_CG_GPU`, from
`d17e9559`). Only then does it call `qudaFinalize`. A new cache that MILC asks QUDA to keep
needs its cleanup added here, before `qudaFinalize`.

## Under QUDA the whole site lattice is pinned, and QUDA starts with it

In a `HAVE_QUDA` build, `make_lattice()` calls `initialize_quda()` and then allocates the
**entire site array** with `qudaAllocatePinned`. `free_lattice()` releases it with
`qudaFreePinned`, and the applications call it before `finalize_quda()`. So:

- QUDA is initialized when the lattice is made, before any measurement code runs. Code that
  must act before QUDA starts has to run before `make_lattice()`.
- Every byte of `sizeof(site) × sites_on_node` is page-locked host memory. A field added to an
  application's `site` struct grows the pinned footprint on every rank, and page-locked memory
  is not swappable.
- Keep the order `free_lattice()` then `finalize_quda()`. The pinned free goes through QUDA.

## QUDA reads the site struct in place

When `newQudaMILCSiteArg()` supplies `site`, the adapter selects QUDA's MILC *site* gauge order.
QUDA then reads links, and momentum where the call uses it, straight out of MILC's site array,
using the byte offsets and the site size. No copy is made.

- The offsets and size are computed at run time from the struct itself. Adding or reordering
  `site` members therefore needs no change on the QUDA side. The members QUDA reads must still
  be four contiguous `su3_matrix` links and four contiguous `anti_hermitmat` momenta.
- **Momentum depends on `MOM_SITE`.** When an application's `lattice.h` does not define
  `MOM_SITE`, the helper sets the momentum offset to 0 but still sets `site`. A
  momentum-reading call would then read whatever lies at the start of each site. The
  applications that call momentum-using QUDA entry points define `MOM_SITE` in their
  `lattice.h`. *Read from source, not exercised:* a new caller in an application without
  `MOM_SITE` would be wrong in exactly this way.

## "Managed" memory is pinned unless QUDA says otherwise

`generic_quda.h` maps `qudaAllocateManaged` and `qudaFreeManaged` to the pinned allocators
unless `USE_QUDA_MANAGED` is defined. That macro comes from QUDA's own installed header: QUDA
defines it for a CUDA target whose compute capability is 6.0 or higher. The compute capability
is defined in the generated `quda_define.h` and is visible to MILC's C compiler.

So one MILC source tree gets managed memory against a CUDA QUDA and pinned memory against a HIP
or SYCL QUDA, with no warning either way. At the observed revision the only caller is
`ks_imp_rhmc/update_rhmc.c`, which allocates its multi-mass solution vectors that way under
`USE_FF_GPU`. What managed memory obtained this way costs is in
[`../quda/internals/managed-memory.md`](../quda/internals/managed-memory.md).

## Build switches and guards

`software/milc/project.yaml` is canonical for what each `WANT_*_GPU` switch means and which
define it produces. A switch acts at two levels. It sets a `HAVE_*_GPU` make variable, which
`Make_template_combos` uses to swap whole object files. It also adds a `-DUSE_*_GPU` define,
which guards code inside files. Some switches act only at the first level: at the observed
revision no source file reads `USE_KS_CONT_GPU`, and the GPU contraction path exists only
because `HAVE_KS_CONT_GPU` links `ks_meson_mom_quda.o` in place of `ks_meson_mom.o`. To find
where a switch takes effect, search the makefiles as well as the sources. The object-selection
trap in [`development.md`](development.md) applies here too.

Five things about how the switches compose are not visible from any single switch:

1. **`USE_*_GPU` says "on the GPU", not "with QUDA".** The block that turns `WANT_*_GPU` into
   `-DUSE_*_GPU` is not conditional on `WANTQUDA`, and the Grid back end reads some of the same
   switches. QUDA code is guarded on both, for example
   `#if defined(HAVE_QUDA) && defined(USE_GA_GPU)`. Guard new QUDA calls the same way.
2. **Defaults are set inside the `WANTQUDA` block, and they are off.** The `?= #true` lines
   assign empty values, so every GPU switch is off unless the build sets it.
3. **Some switches turn on others.**
   - `WANT_FN_CG_GPU` forced `WANT_EIG_GPU` through `6b9b8a06`; from `d17e9559` the Makefile rule
     is commented out, while the CMake build at `a5f8f9fa` still sets `GPU_EIG` from `GPU_FN_CG`.
   - `WANT_CL_BCG_GPU` also defines `USE_GAUGEFIX_OVR_GPU`.
4. **`-DMULTIGRID` has two sources.** `WANT_MULTIGRID=true` adds it in a `WANTQUDA` build, and so
   does a `KSCGMULTI` value that carries it. Both multigrid solve paths in
   `generic_ks/mat_invert.c` are compiled only under it: the single-source path, and the block
   path that reaches `qudaInvertMsrcMG`. Some application makefiles still put `-DMULTISOURCE` in
   `KSCGMULTI`, but no source file reads that macro at the observed revision, and the top-level
   Makefile lists it as deprecated. Do not treat it as a switch.
5. **All of these reach the compiler through `CGPU`**, which `DARCH` puts into both `CFLAGS` and
   `CXXFLAGS`, except `WANT_CURRENT_GPU` (from `d17e9559`), whose `-DUSE_CURRENT_GPU` goes
   through `OCFLAGS`. Check a build's guards by reading the compile line or the generated
   object, not the make variables.

## A local copy of a QUDA declaration is unchecked

`generic_ks/ks_meson_mom_quda.c` does not include `quda_milc_interface.h`. The include is
commented out. Instead the file re-declares `QudaFFTSymmType`, `QudaContractArgs_t` and the
`qudaContractFT` prototype itself. At the observed revisions the copies match QUDA's header
member for member and value for value. Nothing makes them keep matching, though: a QUDA change
to that struct, enum or signature would compile cleanly in MILC and fail only at run time.
`generic_ks/contraction_cpu.c` carries a third, different `QudaContractArgs_t` beside a CPU
function that is also named `qudaContractFT`.

When changing a QUDA declaration that MILC uses, search MILC for local re-declarations of that
name, not only for `#include <quda_milc_interface.h>`. A new MILC-side call includes
`generic_quda.h` rather than copying the declaration.

From `d17e9559` the same file prints a line on every rank before and after each
`qudaContractFT` call and around the spin-taste and accumulation steps, so a `WANT_KS_CONT_GPU`
build writes several lines per rank per contraction.
