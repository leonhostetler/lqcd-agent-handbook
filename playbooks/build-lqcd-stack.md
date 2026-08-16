# Build an LQCD Stack

Use this playbook when building or rebuilding a machine × software × toolchain × profile
combination. A stack is recorded only after an actual build and compute-node run succeed.

## 1. Require completed orientation

Do not start here until `lqcd-start-session` has verified handbook identity and freshness,
detected the machine and checkout state, and established the current work mode. Preserve
all instructions from the working project.

Require the operator to declare the intended compute-node type. A login host cannot supply
it. Load the matching machine profile, software `project.yaml`, `build-profiles.yaml`, and
the nearest stack when one exists.

## 2. Acquire missing source deliberately

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
a new option set.

Inspect the live checkout's remote, commit, branch, cleanliness, and relationship to the
nearest stack commit. Report whether it descends from, predates, or diverges from the
validated commit; do not replace ancestry with a commit-count distance.

## 4. Plan placement and cost

Use the machine profile to choose login, interactive, or batch placement and to cap build
parallelism. A compute-node build consumes scheduler resources. Without an explicit
campaign-scoped node-hour or GPU-hour ceiling, prepare the job and hand its submission
command to the operator.

Before configuring, state the source directory, new out-of-source build directory, install
prefix, dependency acquisition method, toolchain, target architecture, profile, and exact
options. Preserve unrelated working-tree changes and never clean or overwrite an existing
build directory without explicit authorization.

## 5. Configure and build

Follow the software's `build.md`, combining profile-owned options with machine-owned
toolchain and target values. Capture the resolved cache, module list, compiler and
accelerator-toolkit versions, elapsed build time, parallelism, and carefully labelled
memory measurement. Do not describe maximum per-process RSS as aggregate build memory.

Build only the focused validation executables required by the selected profile after the
library and install target succeed.

## 6. Validate on the declared node type

Prepare the smallest run that exercises the profile's claimed capabilities. Reconcile the
declared node type with in-job accelerator telemetry. Record the rank/GPU mapping,
decomposition, tunecache state, test filters, numerical tolerances and residuals, I/O
statuses where applicable, and terminal result.

A tuning-population run is validation, not a benchmark. Keep raw scheduler outputs, job
identifiers, allocation data, and user-specific paths in the working directory. Do not
submit without the budget authority from step 4.

## 7. Record only demonstrated scope

After success, a developer-mode session may propose a stack record with exact tested
commits and branch context, toolchain, node types actually exercised, build cost, validation
results, and explicit scope limits. Follow the exact-diff approval gate before any handbook
write. Enabling an application interface without linking and running that application must
remain a stated limitation, not be promoted to integration validation.
