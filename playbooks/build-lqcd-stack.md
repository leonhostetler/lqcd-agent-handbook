# Build an LQCD Stack

Use this playbook when building or rebuilding a machine × software × toolchain × profile
combination. A stack is recorded only after an actual build and compute-node run succeed.

## 1. Require completed orientation

Do not start here until `lqcd-start-session` has verified handbook identity and freshness,
detected the machine and checkout state, and established the current work mode. Preserve
all instructions from the working project.

Resolve the intended compute-node type before continuing. An explicit operator declaration
wins; without one, use the sole `node_types` entry in the matching machine profile as the
default. If the profile has multiple entries, require the operator to select one. A login
host alone cannot supply a node type. Load the matching machine profile, software
`project.yaml`, `build-profiles.yaml`, the requested application's guide, and the nearest
stack when one exists. When a selected profile declares `application_guide`, follow that
pointer instead of rediscovering the application's build entry point.

## 2. Reuse or acquire source deliberately

When the requested software checkout already exists, prefer using it. First inspect its
revision, status, project instructions, and the exact paths the build will write. Reuse is
appropriate when the checkout satisfies the requested revision, the planned build does not
overlap unrelated modifications, and no instruction or operator requirement calls for a
pristine reproduction. A build request authorizes normal generated objects and application
artifacts in an otherwise compatible checkout; it does not authorize overwriting a differing
tracked or operator-created file. Preserve such a file and stop if the build cannot proceed
around it.

Use a disposable checkout only when exact clean-checkout reproduction is itself required,
the requested revision cannot be selected without disturbing the existing checkout, planned
writes overlap existing changes or incompatible artifacts, or the operator asks to keep the
checkout pristine. Do not create a second checkout solely because an upstream build writes
ordinary artifacts into its source tree.

If the software checkout is absent, read its canonical repository URL and `default_branch`
from `software/<name>/project.yaml`. Offer to clone it before performing any network or
filesystem write. The offer must state the repository URL, destination, full-history
behavior, and branch or revision that will be selected. Use a destination in the working
project, never inside the handbook, and require that it does not already exist.

Unless the operator requests another branch or commit, select the latest remote tip of the
software's recorded default branch at clone time:

```bash
git clone --branch <default-branch> -- <repository-url> <destination>
```

An explicitly requested branch replaces the recorded default in that command. Only select
a tested stack commit when the operator specifically asks to reproduce that stack; the
existence of a nearest stack is not such a request. For explicit reproduction, propose a
full clone followed by the exact tested commit from `stack.yaml`:

```bash
git clone -- <repository-url> <destination>
git -C <destination> checkout --detach <tested-commit>
```

Do not use a shallow clone: the session-start and build workflows need history for commit
ancestry checks. After cloning, verify the canonical remote, exact commit, recorded branch
context, and clean worktree before building. A detached checkout is intentional for exact
stack reproduction; do not present it as the current tip of the recorded branch.

Never substitute another remote or revision after a failure, and do not pull, switch, or
replace an existing checkout as though it were absent. If cloning requires network
authorization, request it explicitly and stop cleanly if it is declined.

## 3. Resolve the requested capability

Select an existing named build profile by capability. Do not invent a profile taxonomy for
one build. If no profile supplies the requested capability, report the gap before deriving
a new option set. Load the profile's `application_guide` when present; the guide owns the
portable application directory and target recipe, while the profile owns the exact option
set and compiled-capability claims.

Use the composition fast path when the requested application has no validated stack on the
current machine but does have a portable application recipe or a validated stack elsewhere:

1. take the application directory, target, and profile from the application guide and nearest
   application stack;
2. take compilers, target architecture, dependency prefixes, flags, and placement from the
   current-machine stack; and
3. confirm that the current-machine dependency stack references the dependency profile named
   by `composes`, whose declared capabilities satisfy `required_capabilities`.

That resolved capability contract is sufficient for the first build attempt. The absence of a
same-machine application run means the combined runtime path is unvalidated; it does not by
itself make an already declared dependency capability unknown. Do not inspect dependency source,
compare implementation histories, probe exported symbols, or rebuild the dependency merely to
re-prove the contract before compiling. Escalate to those diagnostics only after a compile or
link failure, a revision outside the profile's stated evidence, or contradictory local evidence.
Treat build and link as the cheapest compatibility probe.

Inspect the live checkout's remote, commit, branch, cleanliness, and relationship to the
nearest stack commit. Report whether it descends from, predates, or diverges from the
validated commit; do not replace ancestry with a commit-count distance. This is provenance,
not a reason to re-prove a capability already resolved from a compatible profile and stack.

## 4. Plan placement and cost

Use the machine profile to choose login, interactive, or batch placement and to cap build
parallelism. A compute-node build consumes scheduler resources. Without an explicit
campaign-scoped node-hour or GPU-hour ceiling, prepare the job and hand its submission
command to the operator.

Before configuring, state the source directory, new out-of-source build directory or exact
in-tree build paths, install prefix, dependency acquisition method, toolchain, target architecture,
profile, and exact options. Preserve unrelated working-tree changes and never clean or overwrite
an existing build directory without explicit authorization.

## 5. Configure and build

Follow the software's `build.md` and the selected application guide, combining profile-owned
options and the portable target recipe with machine-owned toolchain and target values. Capture
the resolved cache, module list, compiler and accelerator-toolkit versions, elapsed build time,
parallelism, and carefully labelled memory measurement. Do not describe maximum per-process
RSS as aggregate build memory.

For a library project, build only the focused validation executables after the library and
install target succeed. For an application suite, build only the selected application targets and
their required libraries.

## 6. Validate on the resolved node type

Prepare the smallest run that exercises the profile's claimed capabilities. Reconcile the
resolved node type with in-job accelerator telemetry. Record the rank/GPU mapping,
decomposition, tunecache state, test filters, numerical tolerances and residuals, I/O
statuses where applicable, and terminal result.

A tuning-population run is validation, not a benchmark. Keep raw scheduler outputs, job
identifiers, allocation data, and user-specific paths in the working directory. Do not
submit without the budget authority from step 4.

## 7. Record only demonstrated scope

After success, a developer-mode session may propose a stack record with exact tested
commits and branch context, toolchain, node types actually exercised, build cost, validation
results, and explicit scope limits. Record the portable application recipe, the current-machine
dependency stack, any cross-machine application stack used to select the recipe, and which
claims were inherited versus newly demonstrated. Follow the exact-diff approval gate before any
handbook write. Enabling an application interface without linking and running that application
must remain a stated limitation, not be promoted to integration validation.
