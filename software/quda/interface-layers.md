---
title: QUDA's layers, and where a MILC-facing change belongs
summary: QUDA core, the public C API, and the MILC adapter each own different things; anything that reads, writes, or accumulates data in QUDA's own field storage belongs in the core behind a public entry point, and the adapter only translates MILC's host conventions.
scope: [software:quda, software:milc]
load_when: Adding or changing a MILC-to-QUDA call, a QUDA MILC-interface entry point, or a public QUDA API function, or reviewing code in lib/milc_interface.cpp.
evidence: source
sources:
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda.h#L1-L33
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/check_params.h#L51-L52
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/interface_quda.cpp#L6196-L6257
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/quda_milc_interface.h#L40-L97
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L1-L80
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L1156
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L1558-L1762
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L1764
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/milc_interface.cpp#L1978-L1979
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/CMakeLists.txt#L108
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/lib/CMakeLists.txt#L678-L680
  - https://github.com/lattice/quda/blob/00c7ef33dacadfb94860e3ca1cc06862926182dc/include/instantiate.h#L52-L58
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quda.h#L7-L12
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/milc_to_quda_utilities.c#L13-L58
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/d_congrad5_fn_quda.c#L115-L150
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Makefile#L591-L629
  - upstream QUDA maintainer guidance on the interface boundary, relayed by the operator
observed: "2026-10-05"
observed_on:
  software:
    quda:
      commit: 00c7ef33dacadfb94860e3ca1cc06862926182dc
      branch: develop
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# QUDA's layers, and where a MILC-facing change belongs

A MILC call into QUDA crosses three layers, and each owns something different. A change put in
the wrong layer can compile, pass a typical-value test, and still be wrong, because the layer it
landed in makes assumptions only another layer is entitled to make.

## The three layers

| Layer | Files | Owns |
|---|---|---|
| **Core** (QUDA proper) | `lib/*.cu`, `lib/*.cpp` other than the adapters; internal headers such as `color_spinor_field.h`, `gauge_field.h`, `blas_quda.h`, `dirac_quda.h`, `contract_quda.h` | field storage: precision, field order, fixed-point norms, ghost zones, and the conversion between QUDA storage and every host order it accepts |
| **Public API** | `include/quda.h`, implemented in `lib/interface_quda.cpp`; defaults and checks in `lib/check_params.h`; Fortran mirrors | an `extern "C"` surface of `*Quda` functions and parameter structs. It takes host pointers plus a struct that describes their layout and precision |
| **Application adapters** | MILC: `include/quda_milc_interface.h`, `lib/milc_interface.cpp`, and `milc_interface_internal.{hpp,cpp}` for the multigrid input struct. Also openQCD's adapter and `lib/interface/` | translating one application's conventions into public-API calls, and the application-level state kept between calls |

The public API is where host formats meet QUDA storage. A typical entry point wraps each host
pointer as a CPU-location *reference* field, assigns it to a device field, computes on the
device, and assigns back. The assignment between host and device fields is what converts order
and precision, so the caller only ever deals in host types. `contractFTQuda` is a short
example.

## The rule: anything that touches QUDA's own storage belongs in the core

The adapter speaks the application's host formats: IEEE `float` or `double` at the precision the
application was built with, in the application's site order. Code that must read, write,
accumulate, or reduce data **in QUDA's storage** belongs in the core, behind a public entry
point that accepts and returns host types. The adapter then only wraps that entry point.

This is upstream maintainer guidance, relayed by the operator. The mechanism behind it can be
read from source. How a device field stores its data depends on its precision and field order.
For half and quarter precision it also depends on a separate norm array. All of this is QUDA's
to change. Adapter code that copies a device buffer to the host and reinterprets it, choosing
`std::complex<float>` or `std::complex<double>` from `Precision()`, hard-codes an assumption
QUDA never promised. It stays correct only until the storage behind a given precision changes,
and then it misreads data with no error.

**At the observed revision the MILC adapter does not follow this rule throughout.** The
qualifier "at the observed revision" governs everything in this section:

- Most `qudaXxx` adapter functions are thin. They fill parameter structs and call one public
  entry point.
- `qudaProject`, `qudaGetDeflationSpace`, `qudaLoadDeflationSpace` and `qudaExactCurrent`
  instead construct QUDA fields, and in some cases operators and BLAS calls, inside the
  adapter.
- `qudaExactCurrent` accumulates on the device and then copies each accumulator into a host
  staging buffer and reinterprets it by precision. The comment beside that code gives the
  reason: QUDA's generic spinor copy does not support the one-colour field shape the
  accumulator uses.

**Treat these as existing debt, not as templates.** When QUDA's conversion lacks the shape or
order a feature needs, extend the conversion in the core. Do not decode the buffer in the
adapter.

## Where a new MILC-facing capability goes

1. **A public entry point already does it.** Add or extend an adapter function that fills the
   parameter structs and calls it. Nothing in the core changes.
2. **It needs new device work.** Implement it in the core. Expose it through a public `*Quda`
   entry point in `include/quda.h` and `lib/interface_quda.cpp`, taking and returning host
   types. Then add a thin adapter function declared in `quda_milc_interface.h`.
   [`development.md`](development.md) owns the obligations a `quda.h` change brings: the
   `check_params.h` entries and the Fortran mirrors. A host-reference test of the public entry
   point belongs in QUDA's own tests. A MILC run exercises only one caller of it.
3. **It needs a host order or field shape QUDA cannot convert.** Extend the core conversion. The
   MILC host gauge orders are themselves core code, compiled only when `QUDA_INTERFACE_MILC`
   defines `BUILD_MILC_INTERFACE`. That option does **not** decide whether the adapter source is
   compiled: `lib/milc_interface.cpp` is built either way.

## What crosses the boundary from MILC

- **Two precisions travel separately.** MILC passes `MILC_PRECISION`, the precision of its host
  `Real`, and a solver precision, as integers. Every host array and every scalar passed through a
  `void *` has MILC's `Real` type. The adapter must interpret it at the external precision, as
  `qudaExactCurrent` does for its mass array. A `double` read of a single-precision MILC buffer
  is the host-side twin of the storage bug above.
- **MILC reaches QUDA through one header and one initializer.** `include/generic_quda.h`,
  guarded by `HAVE_QUDA`, includes `quda_milc_interface.h`, and that header includes `quda.h`.
  `initialize_quda()` in `generic/milc_to_quda_utilities.c` is lazy and idempotent, and the
  QUDA-calling routines invoke it first. Makefile `WANT_*_GPU` switches become `USE_*_GPU`
  defines; `WANT_FN_CG_GPU`, for example, becomes `USE_CG_GPU`. Enabling QUDA CG also forces the
  eigensolver switch on. The header's helpers, the pinned site lattice, and how the switches
  compose are in [`../milc/quda-host-helpers.md`](../milc/quda-host-helpers.md).
- **Some state is signalled in band.** MILC sets `num_iters = -1` before a solve to tell the
  adapter its links changed, and the adapter then invalidates the resident gauge field. Changing
  a solver call's argument handling can break that signal silently.
- **The adapter keeps state across calls.** File-scope statics in `milc_interface.cpp` track
  resident-gauge validity, the multigrid preconditioner, and the preserved deflation spaces.
  *Inferred from source, not tested:* a MILC call that goes straight to a public `quda.h`
  function and changes one of those resources leaves the adapter's flags stale. Prefer the
  adapter function when one manages the resource.

## The adapter signature is a contract between two repositories

A `qudaXxx` declaration in `quda_milc_interface.h` is compiled into both projects. Changing it
needs coordinated changes in QUDA and MILC, and a relink of every MILC executable. A MILC
executable binds the QUDA it was linked against; see
[`../milc/quda-linkage.md`](../milc/quda-linkage.md).

- **Prefer adding an entry point to changing one.** The adapter already keeps compatibility
  wrappers: `qudaInvert` remains as a wrapper around `qudaInvertDeflatable` for older MILC.
- **Size guards are partial.** The `quda.h` parameter structs carry `struct_size`, and
  `check_params.h` rejects a mismatch. In the MILC header, `QudaEigensolverArgs_t` carries one,
  but only some entry points check it, and `QudaInvertArgs_t` carries none. A member added to an
  unguarded struct that is passed by value goes undetected until results are wrong.
- **The two sides land at different times.** At the observed revisions QUDA `develop` defines
  `qudaExactCurrent`, and MILC `develop` has no caller of it; its caller lives on a MILC feature
  branch. Check each side's branch separately before assuming an entry point is in use.
