---
title: Working under an agent sandbox
summary: How sandbox restrictions present as machine, scheduler, or permission faults, the invocation shapes that decide whether a site query succeeds, and what that means for tool design.
scope: [universal]
load_when: A command fails, hangs, or leaves a half-written file in a way that suggests a machine, scheduler, or permission fault while the session runs under an agent sandbox; or before writing a tool that shells out to a site service.
evidence: reproduced
observations: 2
observed: "2026-09-21"
observed_on:
  requirements: agent-sandbox-constraints
review_by: "2027-09-21"
---

# Working under an agent sandbox

Most agent sessions against this handbook run inside a sandbox: an isolation layer the
**frontend harness** imposes, restricting which paths may be written, which hosts may be
reached, and how a command is executed. It is not a property of the machine. It travels with
the agent to every machine, and it is present whether or not anyone mentions it.

**The single rule worth carrying: a sandbox restriction imitates a fault in something else.**
It surfaces as a scheduler that appears down, a filesystem that appears broken, a permission
error on a file that is plainly writable, or a command that simply never returns. Every one of
those has been read as a real machine problem and reported as one. Before concluding that a
site service is unavailable, establish whether the sandbox is what stopped you — the
distinguishing evidence is given per case below, and a session that skips this step can burn
hours attributing its own environment to the cluster.

**Say which layer failed when you report it.** "The scheduler is unreachable" and "I cannot
reach the scheduler from here" are different claims, and only the second is supportable from
inside a sandbox.

## A site query may succeed or fail on the shape of the command alone

Slurm's `sacct` is the recurring instance, and the one that has cost the most: it is how a
completed job's elapsed time, node count and final state are recovered, so reconciliation needs
it and cannot proceed without it.

**It succeeds only when the query is the entire command.** Anything wrapped around it fails,
including shapes that change nothing about what actually runs:

| Invocation | Result |
|---|---|
| `sacct` and its arguments, alone, with nothing else | **works** |
| `sacct … > file` — a stdout redirect | fails |
| `sacct … 2>/dev/null` — a **stderr** redirect | fails |
| `VAR=value sacct …` — an environment prefix | fails |
| a pipe, a `timeout` wrapper, or one command among several in a script | fails |
| spawned from a shell script, or from a language runtime's subprocess call | fails |

This is narrower than "run it directly". An environment prefix is enough to break it.

**Recognise the signature.** The failure reports an unsupported address family and a socket
address of `family = 0, port = 0`: no address was resolved, rather than a connection refused
or timed out. The output is a header with no data rows, and the exit status is non-zero. **A
real outage does not look like this** — it reports an inability to contact the controller, or
it times out. Treat the address-family signature as sandbox, not cluster.

**A hang is the same cause wearing a different face.** Commands that query the controller
rather than the accounting database, and even a plain hostname lookup, hang instead of failing
fast. A query that never returns is this, not a busy scheduler, and a watch built on one will
wait forever.

**The dangerous shape is the one that half-works.** The redirect form exits non-zero *and still
writes a file containing the header row*. That file is indistinguishable from a real record to
whoever reads it next. **Before treating a captured record as evidence, confirm it has data
rows and not just a header.**

**So the capture is three commands, not one pipeline:** run the query bare, read its output,
then write the file in a separate command.

## A tool must take site data as an input, not fetch it

Any program that shells out for the scheduler record inherits this failure, because a tool's
own subprocess is never the bare command. **A reconciliation tool should accept the captured
output as a file argument and say plainly when it has none**, rather than fetching it and
silently reporting an estimate.

The corollary is the part that keeps being rediscovered: a per-trial helper script that wraps
the query **cannot work**, however convenient it looks. One campaign carried such a helper that
never once produced a file, and reconciled from an estimate for a day before anyone noticed
that the helper's failure and an absent record looked identical.

This generalises past any one harness. A program that cannot reliably reach the data it needs
has no way to distinguish *unavailable* from *empty*, so the fetch belongs outside it.

## A path the sandbox denies writes to may not simply be absent

A denied path can be **materialised as a placeholder** — a character device, or an unreadable
empty file — rather than left missing. It therefore exists, and fails on use rather than on a
existence check. Two consequences seen in practice:

- **A recursive copy of a repository dies** with a permission error on the placeholder, not on
  anything the copy was about. Copy routines need an ignore list covering the tooling paths,
  which is why this handbook's test suite carries one.
- **Version-control operations fail obscurely.** A placeholder where a lock file would go
  produces an error about being unable to take a lock, which reads as a stale lock rather than
  as a denied write. `playbooks/start-session.md` carries the specific retry this handbook
  uses for its own freshness check.

## Where the neighbouring rules already live

This leaf owns the recognition discipline and the site-query rule. It deliberately does not
restate what is already canonical elsewhere:

- bounding a search, and why a broader sandbox does not relax it —
  [`filesystem-discovery.md`](filesystem-discovery.md);
- the freshness check's credential-lock retry, and the tooling paths that carry placeholders —
  [`../playbooks/start-session.md`](../playbooks/start-session.md);
- why a completion watch must not decide a job has ended from a scheduler query, and what it
  should use instead — [`running.md`](running.md).

## Evidence, scope and what will not last

**Evidence:** reproduced. The invocation rule was recorded by one campaign after it produced a
day-long provisional charge, and re-established independently in a later session by testing each
shape in the table. The placeholder behaviour was observed directly, from outside the test suite
that already documented it.

**Scope:** one agent harness, on Slurm machines, over about two months. The harness may also be
frontend-specific in places — one observed restriction denied a path to shell commands while a
different tool in the same session could write it — so check the behaviour rather than assuming
it is uniform across adapters.

**What is durable is the recognition discipline and the tool-design rule.** The table of
breaking shapes describes a harness that can be upgraded: treat a shape not in it as untested
rather than safe, and re-check the table after a harness change. Where no sandbox is present,
none of this applies and the ordinary command works.
