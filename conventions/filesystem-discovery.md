---
title: Bounded filesystem discovery
summary: Universal safeguards for file, directory, software, and data discovery on shared systems.
scope: [universal]
load_when: Searching for files, directories, software, or data on a shared system.
evidence: operator
sources:
  - https://docs.nersc.gov/development/coding-agents/
observed: "2026-08-20"
observed_on:
  requirements: bounded-filesystem-discovery
review_by: "2027-08-20"
---

# Bounded filesystem discovery

Treat filesystem traversal as scoped work. A broader sandbox, an approval path, or a compute
allocation may change where or how a command runs; none makes an unbounded scan acceptable.

## Establish a bounded root

Before recursive discovery, identify an explicit root inside the current workspace, a named
source, build, or installation directory, or a known project or data directory already within
the task scope. A filesystem or mount root, a shared top-level directory, a parent spanning
unrelated users or projects, or a broad system prefix is not bounded. If no bounded root is
known, stop and ask the operator.

Use explicit paths and constrain traversal depth, filename patterns, and file types where
practical. Pattern or output filtering does not make a shared top-level root acceptable when
the tool must still enumerate the broader tree.

## Apply the boundary to every traversal mechanism

Never begin recursive traversal at an unbounded root. This includes `find`, `bfs`, `fd`,
`tree`, recursive `du`, `rg --files`, recursive `grep` or `ls`, globstar expansion, and
recursive traversal written in Python or another language. These tools remain appropriate
inside a bounded root; changing the tool, splitting the scan, delegating it, or requesting
approval for an equivalent broad scan does not change the boundary.

Do not disable, remove, or evade an installed filesystem-traversal guard. When a guard blocks a
command, narrow the root or ask the operator to identify one; do not translate the same scan
into an unguarded mechanism.

## Locate software from metadata

Locate executables and installations with `command -v`, `type -a`, the site's module query
such as `module spider`, package metadata, loaded-environment prefixes, build metadata, or an
already known installation prefix. Inspect a known narrow prefix when necessary, but do not
search mounted filesystems for executable names.

## Keep the same boundary on compute nodes

A compute allocation is permission to use reserved compute resources, not permission to scan a
shared filesystem without bounds. First establish the bounded root. Route the search through a
site-documented compute mechanism only when the bounded traversal is computationally
substantial. Any scheduler submission remains subject to the campaign budget rule; machine
notes own site-specific routing names and limits.
