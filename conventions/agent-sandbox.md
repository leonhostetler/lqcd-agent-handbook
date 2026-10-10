---
title: Working under an agent sandbox
summary: How sandbox restrictions present as machine, scheduler, device, or permission faults, the invocation shapes that decide whether a site query succeeds, and what that means for tool design.
scope: [universal]
load_when: A command fails, hangs, or leaves a half-written file in a way that suggests a machine, scheduler, network-service, or permission fault while the session runs under an agent sandbox; or before writing a tool that shells out to a site service.
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
| a submission client wrapped in anything — including a preceding directory change | fails, differently: see below |

This is narrower than "run it directly". An environment prefix is enough to break it.

**Recognise the signature.** The failure reports an unsupported address family and a socket
address of `family = 0, port = 0`: no address was resolved, rather than a connection refused
or timed out. The output is a header with no data rows, and the exit status is non-zero. Treat
the address-family signature as sandbox, not cluster. **The converse does not hold.** A real
outage reports an inability to contact the controller, or times out. But the sandbox has
produced the controller-contact message too (below), so that message alone does not establish
an outage either.

**The submission client fails differently again, and its symptom points at the site.** Where the
accounting client reports a socket error, a submission client wrapped in anything can report a
container-runtime *ownership* complaint about a root-owned configuration file and then die with a
**segmentation fault**. Nothing about that reads as a restriction on the agent: it reads as a
broken site install, and it has been reported as one. It is the sandbox's user-namespace mapping
showing through.

**It can also report that the controller is unreachable.** In one campaign a submission client
run inside a shell loop said it could not contact the controller three times, and twice more on
single submissions whose exact shape was not recorded. Nothing was submitted, and a bare retry
succeeded each time `[observed]`. That message reads as an outage, which is what makes this one
the most misleading face of the cause; the rule below covers it unchanged.

**The rule is not specific to the accounting client.** `sinfo`, which asks the controller for
partition state, listed partitions when run bare and failed with the controller-contact message
when piped into another command `[observed]`. Treat every scheduler client as subject to the
table until it has been shown otherwise.

**Submission usually still works, and assuming otherwise is expensive.** Because the bare command
is exempt, an agent that has authority to submit can normally submit — so a misdiagnosis here does
not merely mislabel a fault, it reaches for the no-authority fallback in
[`batch-scripts.md`](batch-scripts.md) and hands the operator a command to run by hand. That
converts working automation into a manual step and reads as helplessness rather than caution.
**Retry bare before concluding anything**: before reporting a service unavailable, before
recording an environment finding, and before handing over a submit command.

**A hang is the same cause wearing a different face.** Commands that query the controller
rather than the accounting database, and even a plain hostname lookup, hang instead of failing
fast. A query that never returns is this, not a busy scheduler, and a watch built on one will
wait forever.

**A `timeout` prefix did not break the queue listing on one machine** `[reproduced]`, Horizon,
2026-10-10. `timeout 60 squeue --me …` and `timeout 60 squeue -A <account> …` returned full
listings more than ten times, while the same listing redirected to a file hung until the timeout,
and a listing run from inside a script timed out. So the table's `timeout` row is not universal,
but its redirect and script rows held. A tool that must query the scheduler from a script
still cannot be tested from inside the sandbox; give it a way to read saved output instead.

**Select your own jobs with `--me`, not `-u <name>`.** On the same machine and day, `squeue -u
<user>` failed with `Invalid user` from inside the sandbox, hours after the same form had worked
`[observed]`. `-u` resolves a name through the user database, the lookup class that hangs here
`[inferred]`; `--me` uses the process's own user id.

**The dangerous shape is the one that half-works.** The redirect form exits non-zero *and still
writes a file containing the header row*. That file is indistinguishable from a real record to
whoever reads it next. **Before treating a captured record as evidence, confirm it has data
rows and not just a header.**

**So the capture is three commands, not one pipeline:** run the query bare, read its output,
then write the file in a separate command.

**Bare is necessary, not sufficient.** A bare accounting query that had worked failed later in
the same session with the address-family signature, and in that campaign every later re-query
failed `[observed]`. A record the job captured at teardown, where no sandbox applies, is the one
to rely on, as [`batch-scripts.md`](batch-scripts.md) already requires. A query from the sandbox
is a convenience.

**Some queries have no working shape at all.** A site's account-listing command and the
scheduler's administration client failed with the address-family signature even as bare
commands, and a filesystem quota query reported `Connection refused` `[observed]`. The operator
runs these from their own shell. Ask, and record that they did.

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
existence check. Three consequences seen in practice:

- **A recursive copy of a repository dies** with a permission error on the placeholder, not on
  anything the copy was about. Copy routines need an ignore list covering the tooling paths,
  which is why this handbook's test suite and its batch-script dry-run harness each carry one.
  The harness needs it because a session whose shell stands in a job directory leaves
  placeholders there as well.
- **Version-control operations fail obscurely.** A placeholder where a lock file would go
  produces an error about being unable to take a lock, which reads as a stale lock rather than
  as a denied write. `playbooks/start-session.md` carries the specific retry this handbook
  uses for its own freshness check.
- **The sandbox itself can fail to start.** With the shell standing in a project directory that
  already held placeholders, commands intermittently failed before running anything, the
  sandbox reporting that it could not create the parents of a placeholder path, a
  `.gitconfig` or `.claude` entry in that directory, on a read-only file system. The same
  command preceded by a change to a scratch directory ran `[observed]`. An error from the
  sandbox's own setup is not an error from the command.

## A full home filesystem stops every command

The sandbox writes its placeholders when it starts each command, and the working directory
usually lies on the home filesystem. When that filesystem is out of quota, the write fails and
**no command starts at all**: every tool call fails, including the ones that would diagnose why
`[observed]`. Nothing inside the session can show the cause, because the quota query is one of
the shapes above that fails, and nothing inside it can free space. So before a batch of large
writes into home, such as several build directories, ask the operator for the quota headroom.
Once it has happened, only the operator's own shell can recover it.

## A device the sandbox hides looks like a node without one

A sandbox can hide device files as well as paths. On one machine the GPU and network-adapter
device nodes were invisible inside it: a CUDA program reported no device, and the
communication library's device listing showed only host and shared-memory domains — no
network adapter, no GPU memory. Nothing about the node was wrong; the same commands on the same
node, from the operator's own shell, found both. `[reproduced ×2]`

So a GPU run, a fabric or GPU-memory probe, or anything that must open an accelerator is run
from a shell outside the sandbox, and the record says where it ran. Building, reading
binaries, and checking linkage still work inside it.

## A host allowlist does not follow redirects

A sandbox network allowlist matches the host a request is sent to, and many downloads are
redirected: a release file on a code-hosting site is typically served from a separate asset
host. The first host is allowed, the redirect target is refused, and the tool reports an HTTP
or download error that reads as a broken upstream or a bad checksum rather than as a denied
connection. `[observed]` once, in a build's configure step; the software-specific host list
belongs in that software's build leaf.

Before diagnosing the upstream, find where the request actually went. A header-only request
that follows redirects (`curl -sSIL <url>`) names the final host, and the sandbox's own denial
report, where it gives one, names the refused host. Allow that host for the command and retry;
never route around the allowlist.

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
