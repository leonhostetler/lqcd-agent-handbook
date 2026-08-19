---
title: MILC HISQ naming and spacing defaults
summary: Resolves ensemble names, generation streams, and unqualified lattice-spacing references.
scope:
  - ensemble:milc-hisq
load_when: selecting or identifying a MILC HISQ ensemble from a name, stream, or approximate lattice spacing
evidence: operator
observed: "2026-08-19"
observed_on:
  ensemble_catalog: milc-hisq
review_by: "2027-02-19"
sources:
  - https://arxiv.org/abs/1712.09262
  - https://arxiv.org/abs/2206.03156
  - https://docs.google.com/spreadsheets/d/1luGfChiPg9XY78ibbU6AavOr1QLHPLG2CwbFNYs_kAQ/edit
---

# MILC HISQ naming and spacing defaults

[`milc-hisq.yaml`](milc-hisq.yaml) is canonical for ensemble names, parameters,
physical-mass flags, spacing aliases, and spacing defaults.

## Ensemble names and streams

The suffix-free MILC `l...` label identifies the ensemble. A trailing lowercase letter
identifies one generation stream of that ensemble; it is not part of the ensemble name.
Preserve an explicit stream suffix when the operator supplies one, but use the suffix-free
name for ensemble-scoped knowledge and comparisons across streams.

## Resolving an operator reference

Apply selectors in this order:

1. An explicit ensemble name, stream, quark mass, paper key, or lattice geometry overrides
   every default.
2. For a spacing-only reference, find the alias in `operator_resolution.spacing_defaults`
   and select that record's `ensemble`.
3. The colloquial `0.04` and the more precise `0.042` refer to the same spacing group.
4. A null default `ensemble` means no physical-mass ensemble is published in this catalog
   at that spacing. Do not describe another ensemble as physical. If the group has one entry
   and a concrete choice is needed, state its mass regime when selecting it; otherwise ask
   the operator to resolve the ambiguity.

Short analysis aliases from downstream papers are secondary names. Do not replace the
suffix-free MILC ensemble name with a short alias.
