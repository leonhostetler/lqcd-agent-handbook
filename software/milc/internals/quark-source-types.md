---
title: MILC quark-source types and parity
summary: All base-source keywords accepted by MILC's generic parser, their construction and support status, subset behavior, and staggered parity.
scope: [software:milc]
load_when: Constructing or debugging a MILC base quark source, determining its staggered parity, or selecting an inverter for it.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/include/generic_quark_types.h#L25-L83
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/quark_source.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/libraries/gaussrand.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic/ranstuff.c
  - https://github.com/milc-qcd/milc_qcd/commit/9683296ca73334d0805bc3f2ba0feec22594e0bd
observed: "2026-08-19"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# MILC quark-source types and parity

This page covers base-source keywords accepted by MILC's generic
`ask_quark_source` parser. The larger `enum source_type` also includes source and
sink operators; those are not additional base-source input choices.

For staggered fields, site parity is

```text
p = (x + y + z + t) mod 2
```

A source is **even** or **odd** only when every nonzero site has that parity.
Otherwise it is **mixed**. File-backed and multi-point sources are
data-dependent unless their contents are inspected.

## Analytic and complex-field sources

| Input keyword | Construction | Parity at fixed `t0` |
| --- | --- | --- |
| `point` | Unit complex field at one requested four-coordinate, replicated into the requested source color/spin. | `(x0+y0+z0+t0) mod 2` |
| `multi_point` | Equal-weight sum of `num_points` requested four-coordinate delta functions. | Pure only if every point has the same parity; otherwise mixed. |
| `corner_wall` or `corner_wall_0` | Unit field where `x`, `y`, and `z` are all even on the selected time slice. | `t0 mod 2` |
| `corner_wall_x` | Unit field with spatial residue bits `100`. | `(t0+1) mod 2` |
| `corner_wall_y` | Unit field with spatial residue bits `010`. | `(t0+1) mod 2` |
| `corner_wall_xy` | Unit field with spatial residue bits `110`. | `t0 mod 2` |
| `corner_wall_z` | Unit field with spatial residue bits `001`. | `(t0+1) mod 2` |
| `corner_wall_zx` | Unit field with spatial residue bits `101`. | `t0 mod 2` |
| `corner_wall_yz` | Unit field with spatial residue bits `011`. | `t0 mod 2` |
| `corner_wall_xyz` | Unit field with spatial residue bits `111`. | `(t0+1) mod 2` |
| `even_wall` | `+1` on every even site of the selected time slice and zero elsewhere. | Even |
| `evenandodd_wall` | `+1` on every site of the selected time slice. | Mixed |
| `evenminusodd_wall` | `+1` on even sites and `-1` on odd sites. | Mixed |
| `gaussian` | Deterministic spatial field `exp(-(r/r0)^2)` centered at the requested origin. | With `subset full`, mixed on an ordinary time slice. With `subset corner`, parity is `t0 mod 2`. |
| `random_complex_wall` | Independent complex Gaussian values on the time slice, each normalized to unit modulus. | With `subset full`, mixed. With `subset corner`, parity is `t0 mod 2`. |
| `wavefunction` | ASCII wavefunction interpolated using the requested lattice spacing and origin. | Data-dependent with `subset full`; `t0 mod 2` with `subset corner`. |
| `complex_field` | QIO complex field, reused for each source color/spin and optionally momentum phased. | File-data-dependent. |
| `complex_field_fm` | FNAL-format complex field, reused for each source color/spin and optionally momentum phased. | File-data-dependent. |

For a corner wall, the suffix names which spatial residue bits are odd. If
`t0 == ALL_T_SLICES`, time varies and the corner-wall source is mixed. An
`even_wall` remains even because its test uses full four-dimensional parity.

The generic interactive prompt does not list `multi_point` or the specialized
corner-wall keywords, but the parser accepts them at the observed revision.

## Color-vector and propagator sources

| Input keyword | Construction and support | Parity |
| --- | --- | --- |
| `random_color_wall` | Normalized random three-component color vector at each selected site. | Mixed with `subset full`; `t0 mod 2` with `subset corner`. |
| `vector_field` | QIO sequence of color-vector fields with requested `ncolor`. Requires QIO support. | File-data-dependent. |
| `vector_field_fm` | Accepted by the parser, but its FNAL reader branch is commented out at the observed revision. Do not treat it as a working source path. | Not applicable until the reader is implemented and validated. |
| `vector_propagator_file` | Takes immutable source records from the QIO KS propagator being reloaded rather than constructing a new source. | Embedded-source-dependent. |

Complex-field sources are diagonal in source color and spin. A color-vector
source carries its own color components instead of replicating one complex
field.

## Dirac-field sources

| Input keyword | Construction and support | Parity |
| --- | --- | --- |
| `dirac_field` | QIO series of Dirac fields through the Dirac-source entry point. The KS base-source input entry point rejects it. | File-data-dependent. |
| `dirac_field_fm` | Accepted by the parser, but its FNAL reader branch is commented out at the observed revision. Do not treat it as a working source path. | Not applicable until the reader is implemented and validated. |
| `dirac_propagator_file` | Takes immutable source records from the QIO Dirac propagator being reloaded. | Embedded-source-dependent. |

Parser recognition, application support, and a functioning constructor are
separate conditions. In particular, the two `_fm` field keywords above remain
visible in input parsing even though their construction code is disabled.

## `subset` behavior for staggered sources

The accepted values are:

- `full`: do not apply a spatial residue mask; and
- `corner`: retain only sites with even `x`, `y`, and `z`.

For the KS color-vector construction path, the `corner` mask is applied during
construction of `gaussian`, `random_complex_wall`, `wavefunction`, and
`random_color_wall`. At fixed `t0`, these masked sources have parity
`t0 mod 2`.

The field is parsed for all source records, but the KS construction path does
not apply this generic mask to point sources, explicit corner/even wall
sources, or loaded complex/vector fields. Do not infer their parity from the
`subset` input token.

Momentum insertion multiplies existing source values by phases and does not
change which sites are nonzero, so it does not change parity support.

## Current `develop` Gaussian-origin defect

The deterministic `gaussian` source does not use the Gaussian random-number
routine and is not affected by this defect.

`random_complex_wall` and `random_color_wall` call
`complex_gaussian_rand_no`. At the observed `develop` revision, its polar
transformation rejects only `r >= 1`:

```c
do {
  v1 = 2.0 * myrand(prn_pt) - 1.0;
  v2 = 2.0 * myrand(prn_pt) - 1.0;
  r = v1*v1 + v2*v2;
} while (r >= 1.0);
fac = sqrt(-log((double)r)/(double)r);
```

`myrand` returns values on a 24-bit grid that includes exactly `0.5`. If both
draws are `0.5`, then `v1 == v2 == 0` and `r == 0`. The accepted origin makes
the scale singular and can put a NaN into the MILC source before any inverter
or QUDA call.

Upstream commit `9683296ca73334d0805bc3f2ba0feec22594e0bd` adds the missing
`r == 0.0` rejection to the active complex routine on a feature branch, but
that commit is not an ancestor of the observed `develop` tip. Similar scalar
and legacy loops also omit the origin guard.

For an affected checkout:

1. inspect the Gaussian rejection loop rather than assuming a branch name
   contains the fix;
2. require both `r >= 1.0` and `r == 0.0` to be rejected;
3. when debugging a random-wall NaN, check the source immediately after MILC
   constructs it, before investigating solver kernels; and
4. do not claim all Gaussian variants are fixed merely because the complex
   feature-branch patch is present.

## Inverter consequence

A fresh parity-pure source can allow `CGZ` to skip the absent parity exactly.
Mixed sources require both CGZ parity systems. Other inverter types transform
or reconstruct the source differently, so source parity alone does not predict
their complete solve cost. See
[`staggered-inverter-types.md`](staggered-inverter-types.md).
