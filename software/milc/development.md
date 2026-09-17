---
title: Developing MILC
summary: Software-specific rules for modifying MILC source, starting with the shared-source blast radius and the near-identical QUDA link-load file that no target compiles.
scope: [software:milc]
load_when: Modifying MILC source, adding an application-side call into QUDA, or preparing a MILC change for review.
evidence: source
sources:
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/Make_template_combos
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/Make_template
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/fermion_links_fn_load_quda.c
  - https://github.com/milc-qcd/milc_qcd/blob/6b9b8a06eec5746187bbfd197eac2629ab8d8e72/generic_ks/fermion_links_hisq_load_quda.c
observed: "2026-09-17"
observed_on:
  software:
    milc:
      commit: 6b9b8a06eec5746187bbfd197eac2629ab8d8e72
      branch: develop
---

# Developing MILC

MILC composes each application from shared source directories through makefile variables rather
than from a per-application source tree. Two consequences dominate any source change, and both are
invisible from the file you are editing.

## Confirm which object the target actually builds

**A file's name does not establish that the target you are building compiles it.** The
directories carry near-identical files whose selection is made in a makefile, and the intuitive
name can be the one nothing builds.

The recorded instance is the QUDA fermion-link load path. `generic_ks/` carries both
`fermion_links_fn_load_quda.c` and `fermion_links_hisq_load_quda.c`, and at this revision they
differ by exactly one line. `Make_template_combos` binds **both** the FN and the HISQ QUDA
link variables to `fermion_links_fn_load_quda.o`:

```make
FLINKS_FN_QUDA = fermion_links_milc.o fermion_links_fn_load_quda.o ...

FLINKS_HISQ_QUDA = fermion_links.o fermion_links_fn_load_quda.o ...
```

`fermion_links_hisq_load_quda.c` is referenced by no makefile anywhere in the tree. It is dead
code in every build, and it is the file a reader reaches for when changing a HISQ application.
An edit made there compiles cleanly, links cleanly, changes nothing, and produces a run whose
behaviour matches the unmodified binary exactly — which reads as the change having had no effect
rather than as the change not being present.

**So before editing any file under a shared directory, establish which object the target builds.**
The build log names the objects it compiles and the link line names what it linked; either settles
it in one grep, and neither requires reasoning about the makefile variables. Do this even when the
filename appears to match the application, because that is precisely the case this trap is built
from.

## A shared-directory edit reaches every target built from the tree

`generic_ks/` and its siblings are compiled into **every** application built from that tree that
enables the relevant path — not only the application you are working on. A change there is
therefore not scoped to your run by virtue of being in a file your run uses: a gauge-generation
target built later from the same tree picks it up, in a regime where its cost or its side effects
may be entirely different.

Two rules follow.

- **State the blast radius in terms of targets, not files.** "One line in one file" is not a scope
  statement when the file is shared source.
- **Gate new behaviour behind an environment check when the change suits one application and not
  another.** A static flag read once from the environment costs nothing, keeps the default
  behaviour unchanged for every other target built from the tree, and allows the modified and
  unmodified paths to be compared in a single job without a rebuild — which also makes it a
  cheaper trial. Collapse the gate afterwards or keep it; both are defensible once the comparison
  exists.

The recorded instance is a QUDA device-memory pool flush added after the link build: correct for a
spectrum application, where links are built once per gauge configuration, and actively harmful in
gauge generation, where the links are rebuilt every molecular-dynamics step and flushing would
discard the solver's cached working set on each one. Same line, same file, opposite verdicts — and
the makefile gives it to both.

## Calling into QUDA from the application

QUDA's public API is reachable from MILC source that already includes the MILC-facing QUDA
interface header: that header includes `quda.h`, and `quda.h` declares its public entry points
inside its own `extern "C"` block. An application-side call to a public QUDA entry point therefore
usually needs no new include and no QUDA change at all.

Prefer that to a QUDA-side change when both would work. A QUDA change reaches every installation
and every application that links it, and needs an upstream review that the application-side line
does not; the application-side line reaches only the targets built from this tree, which the
previous section already bounds. Where the QUDA behaviour is genuinely defective rather than merely
unhelpful here, the application-side line is a local remedy and not a substitute for the upstream
fix — record it as such so the fix is not considered done.

For what the QUDA side of such a call costs and when it is worth making, see
[`../quda/internals/device-memory-pool.md`](../quda/internals/device-memory-pool.md); for the rules
governing a change to QUDA itself, see [`../quda/development.md`](../quda/development.md).
