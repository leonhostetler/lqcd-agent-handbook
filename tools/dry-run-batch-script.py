#!/usr/bin/env python3
"""Execute a batch script on a login node with every external effect stubbed, under the
environment the scheduler will actually present, and write a receipt the submission guard
reads.

This is step 9 of `conventions/batch-scripts.md`, shipped rather than described. Every
workspace that submits often had rebuilt it privately, and a private harness written by the
session that wrote the launcher shares the launcher's assumptions: one such pair agreed that
a job directory resolved from the scheduler's submission-directory variable was fine, and the
job died ten seconds into a two-day queue wait because under a pinned working directory that
variable is never the job directory. The machine presented a case neither harness had modelled.

So the environment model is the point, and it is deliberately unlike the shell it runs in:

  * the working directory is the one the script's own directive pins; when none pins it, it
    is where the scheduler's surface says an unpinned job starts -- the home directory, or a
    directory that is NOT the job directory standing for wherever the submit command ran;
  * the scheduler's submission-directory variable names a directory that is NOT the job
    directory, because a script is normally submitted by absolute path from elsewhere;
  * the script that runs is a copy in a spool directory, so `$0` resolves there;
  * the job-id variable is set, and so is the per-task CPU variable where the surface records
    one and the script's directive requests a count; nothing else the scheduler exports is, so
    an undeclared variable aborts here rather than on the machine;
  * the environment is otherwise empty (`env -i`), so a startup file or an exported shell
    function cannot put a real command back ahead of a stub.

Modules are a shell function, as Lmod's are, defined in a harness-owned file passed through
BASH_ENV. It records what the script loads and, when the script runs `module reset` or
`module load`, exports each `--module-env KEY=VALUE` into the script's own shell. An
executable stub cannot do that: a child process cannot change its parent's environment, so a
script that runs a real dynamic-library check after `module reset` -- `ldd` on its executables,
say -- found none of the site's libraries and failed a positive control the machine would pass.
`--env` is the wrong substitute, because it sets the value before the script's own reset, which
on the machine would rebuild it. Take the values from the machine itself, for example
`bash -lc 'module reset >/dev/null 2>&1; printf %s "$LD_LIBRARY_PATH"'`. PATH is refused: a
module-provided PATH would put real commands back ahead of the stubs.

Stubs replace the submit and interactive commands (they refuse), the parallel launcher (it
logs the step and, where the surface records an overlap option, models step-allocation
contention), a site launcher the machine profile records under `scheduler.site_launcher`
(logged and modelled from that record, never from the parallel launcher's), scheduler
queries, the modules system, the accelerator query tool the machine profile's vendor implies,
and `sleep`. A refused launcher step fails the positive control even when the script
tolerates the failed leg and exits 0, because on the machine that step waits for the
allocation until the walltime runs out. A launcher stub runs nothing; `--launcher-output TEXT` makes every launcher stub
print TEXT after its log line, for guards that read launched output. Anything else the script
needs can be stubbed with `--stub NAME=TEXT`, which replaces any stub of that name. The modules
stub answers `-t list` (on stderr, as Lmod does) and `is-loaded`, both from the same listing,
so a drift guard written either way can be made to fire.

Arguments the submit command would pass to the script are given with `--arg`, once per
argument, and each receipt entry records them. The receipt still certifies the script text, not
an argument list: the guard does not compare them.

The script runs in its own process group with its output in a file. When it exits, anything it
left running in the background is killed and reported as a note, as the scheduler kills a job's
processes when its script ends; a background monitor without a trap therefore no longer hangs
the harness. A script that has not exited after `--timeout` seconds is killed and counts as a
failed positive control or an unfired negative test: a hang is not a guard firing.

Sparse stand-ins satisfy byte-count guards for inputs that are not checksummed. They are
CONFINED to the sandbox: a declaration that is relative, contains an unexpanded shell
expansion, or resolves outside the sandbox after root rewriting is refused before anything is
created, because an earlier harness created them wherever the declaration pointed and left
375 GB of apparent, zero-block files in a workspace root.

Three run kinds, one receipt:

  positive control   the script must run to completion (exit 0) on correct inputs;
  --negative F EXPR  perturb one input in the sandbox copy with a sed expression and require
                     a non-zero exit; a no-op expression is an error, not a pass;
  --omit-stand-in P  withhold one stand-in and require a non-zero exit (absence guards);
  --short-stand-in P build one stand-in a byte short and require a non-zero exit;
  --module-drift M   omit module M from the stub's list and require a non-zero exit.

The receipt `<script>.dry-run-receipt.json` records the script's sha256, the harness version,
the latest positive control and every negative run against that exact script text. A changed
script starts a fresh receipt. `tools/submission-guard.py` refuses to submit a script whose
receipt is missing, stale, failed, or carries no fired negative test.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

VERSION = "1.6.0"

# Frontend tooling paths an agent sandbox materialises as unreadable placeholders in whatever
# directory the session's shell stands in -- including a job directory. They are never job
# files, and copying one kills the copy with a permission error, so they are never copied. The
# same names are declared non-content in the repository's .gitignore; extend both together.
TOOLING_NAMES = (".claude", ".agents", ".mcp.json")
HANDBOOK = pathlib.Path(__file__).resolve().parents[1]
RECEIPT_SUFFIX = ".dry-run-receipt.json"

_spec = importlib.util.spec_from_file_location("check_batch_script",
                                               HANDBOOK / "tools" / "check-batch-script.py")
_CBS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_CBS)


class Refusal(SystemExit):
    """A harness refusal: the run did not happen, and this is not a launcher result."""

    def __init__(self, message: str):
        print(f"HARNESS REFUSED (nothing was run): {message}", file=sys.stderr)
        super().__init__(2)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receipt_path(script: pathlib.Path) -> pathlib.Path:
    return script.with_name(script.name + RECEIPT_SUFFIX)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ arguments
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("script", type=pathlib.Path)
    ap.add_argument("--machine", required=True,
                    help="machine profile; supplies the scheduler surface and accelerator vendor")
    ap.add_argument("--rewrite-root", action="append", default=[], metavar="REAL=NAME",
                    help="map an absolute root the script names onto a sandbox directory; "
                         "the script's own directory is always mapped")
    ap.add_argument("--stand-in", action="append", default=[], metavar="PATH:BYTES",
                    help="sparse file of exactly BYTES at PATH (after rewriting); repeatable")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME",
                    help="directory or file name not to copy from the job directory, in addition "
                         "to the frontend tooling paths, which are never copied")
    ap.add_argument("--module", action="append", default=[], metavar="NAME",
                    help="module the stub reports as loaded, besides those the script loads")
    ap.add_argument("--module-env", action="append", default=[], metavar="KEY=VALUE",
                    help="variable the module function exports into the script's shell when the "
                         "script runs `module reset` or `module load`; repeatable; PATH is refused")
    ap.add_argument("--stub", action="append", default=[], metavar="NAME=TEXT",
                    help="extra command stub printing TEXT and exiting 0")
    ap.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                    help="extra environment variable for the run (the environment is otherwise empty)")
    ap.add_argument("--gpu-model", default="STUB-ACCELERATOR", help="model the accelerator stub reports")
    ap.add_argument("--gpu-count", type=int, default=4)
    ap.add_argument("--gpu-memory-mib", type=int, default=40960)
    ap.add_argument("--launcher-output", default=None, metavar="TEXT",
                    help="text every launcher stub prints after its log line, for guards that "
                         "read the launched program's output")
    ap.add_argument("--arg", action="append", default=[], dest="script_args", metavar="VALUE",
                    help="positional argument passed to the script, as the submit command would; "
                         "repeat once per argument, in order")
    ap.add_argument("--timeout", type=float, default=300.0, metavar="SECONDS",
                    help="kill the script and fail the run if it has not exited after this long "
                         "(default 300; sleep is stubbed, so a real run takes seconds)")
    ap.add_argument("--allow-sequential-steps", action="store_true",
                    help="let a non-overlapping launcher step proceed after earlier steps")
    kind = ap.add_mutually_exclusive_group()
    kind.add_argument("--negative", nargs=2, metavar=("FILE", "SED-EXPR"))
    kind.add_argument("--omit-stand-in", metavar="PATH")
    kind.add_argument("--short-stand-in", metavar="PATH")
    kind.add_argument("--module-drift", metavar="NAME")
    ap.add_argument("--no-receipt", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the sandbox and print its path")
    ap.add_argument("--tail", type=int, default=25)
    return ap.parse_args(argv)


# ------------------------------------------------------------------ sandbox
def make_stub(bin_dir: pathlib.Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text("#!/usr/bin/env bash\n" + body)
    path.chmod(0o755)


MODULE_ENV_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def write_module_function(sandbox: pathlib.Path, bin_dir: pathlib.Path, specs: list[str]) -> list[str]:
    """Write the BASH_ENV file defining `module` as a shell function over the stub, and the
    file of exports it applies at `module reset` and `module load`. Returns the keys."""
    exports, keys = [], []
    for spec in specs:
        key, sep, value = spec.partition("=")
        if not sep or not MODULE_ENV_KEY.fullmatch(key):
            raise Refusal(f"--module-env needs KEY=VALUE with a shell variable name, got {spec!r}")
        if key == "PATH" or key == "BASH_ENV" or key.startswith("DRYRUN_"):
            raise Refusal(f"--module-env may not set {key}: it would undo the stubs or the harness")
        exports.append(f"export {key}={shlex.quote(value)}")
        keys.append(key)
    env_file = sandbox / "module-env.sh"
    env_file.write_text("".join(line + "\n" for line in exports))
    stub = shlex.quote(str(bin_dir / "module"))
    (sandbox / "module-function.sh").write_text(f'''module() {{
  {stub} "$@"
  local rc=$?
  case "${{1:-}}" in reset|load|add) . {shlex.quote(str(env_file))} ;; esac
  return $rc
}}
''')
    return keys


def launcher_stub(bin_dir: pathlib.Path, name: str, overlap: str, never_overlaps: bool,
                  output: str | None) -> None:
    """Log each call as a step and model step-allocation contention.

    `overlap` is the option that lets a step share the allocation. With none recorded the
    parallel launcher is not modelled (no refusal); a site launcher recorded with a null
    overlap option can never pass one, so it is refused whenever an earlier step exists.
    """
    modelled = "yes" if (overlap or never_overlaps) else "no"
    refusal = "cannot share it" if never_overlaps else f"did not pass {overlap}"
    echo = ""
    if output is not None:
        # A file, not an inline literal: the text reaches the script byte for byte.
        (bin_dir / f".{name}.output").write_text(output if output.endswith("\n") else output + "\n")
        echo = f'cat "{bin_dir / f".{name}.output"}"\n'
    make_stub(bin_dir, name, f'''steps="${{DRYRUN_STEPS:?}}"
overlap=no
for a in "$@"; do [ -n "{overlap}" ] && [ "$a" = "{overlap}" ] && overlap=yes; done
echo "[stub {name}] $*"
held=0; [ -s "$steps" ] && held=$(wc -l < "$steps")
if [ "{modelled}" = yes ] && [ "$overlap" = no ] && [ "$held" -gt 0 ] && [ "${{DRYRUN_ALLOW_SEQUENTIAL_STEPS:-0}}" != 1 ]; then
  echo "[stub {name}] STEP CREATION REFUSED: $held step(s) already hold this allocation and this step {refusal}" >&2
  printf '%s\\n' "{name} $*" >> "${{DRYRUN_REFUSED:?}}"
  exit 1
fi
printf '%s\\toverlap=%s\\n' "{name} $*" "$overlap" >> "$steps"
for a in "$@"; do case "$a" in *.out) : > "$a" 2>/dev/null || true;; esac; done
{echo}exit 0
''')


def write_stubs(bin_dir: pathlib.Path, surface: dict, vendors: set[str], args,
                site_launcher: dict | None = None) -> None:
    refuse = ('echo "[stub {name}] REFUSED: a batch script must not submit or allocate another '
              'job" >&2\nexit 99\n')
    for key in ("submit_command", "interactive_command"):
        name = surface.get(key)
        if name:
            make_stub(bin_dir, name, refuse.format(name=name))

    launcher = surface.get("parallel_launcher")
    if launcher:
        launcher_stub(bin_dir, launcher, surface.get("launcher_overlap_option") or "", False,
                      args.launcher_output)
    if site_launcher:
        name = site_launcher["command"]
        if name == launcher:
            raise Refusal(f"site launcher {name!r} would replace the parallel launcher's stub")
        # A launcher whose concurrent launches share the allocation with no option at all
        # has no contention to model; otherwise a null overlap option means it never can.
        shares = bool(site_launcher.get("steps_share_allocation"))
        launcher_stub(bin_dir, name, site_launcher.get("overlap_option") or "",
                      site_launcher.get("overlap_option") is None and not shares,
                      args.launcher_output)

    for key in ("query_command", "queues_command", "control_command",
                "accounting_command", "live_step_command"):
        name = surface.get(key)
        if name and not (bin_dir / name).exists():
            make_stub(bin_dir, name, f'echo "[stub {name}] $*"\nexit 0\n')

    # The stub RECORDS what the script loads at run time -- through a variable, a loop, or
    # a literal alike -- and lists that plus whatever --module adds (modules a site loads
    # implicitly). --module-drift NAME withholds NAME from the listing, so a drift guard
    # can be made to fire on purpose.
    modules_text = "\\n".join(args.module)
    drift = args.module_drift or ""
    make_stub(bin_dir, "module", f'''loaded="${{DRYRUN_MODULES:?}}"
listing() {{ {{ printf '{modules_text}\\n'; cat "$loaded"; }} | sed '/^$/d' | grep -vxF -- "{drift}" || true; }}
if [ "${{1:-}}" = "is-loaded" ]; then
  # As Lmod: true only when every name given is loaded, matching NAME or NAME/VERSION.
  shift; [ "$#" -gt 0 ] || exit 1
  mods=$(listing)
  for want in "$@"; do
    hit=1
    while IFS= read -r m; do
      if [ "$m" = "$want" ] || [ "${{m%%/*}}" = "$want" ]; then hit=0; break; fi
    done <<< "$mods"
    [ "$hit" = 0 ] || exit 1
  done
  exit 0
fi
case "${{1:-}}" in
  load|add) shift; for m in "$@"; do printf '%s\\n' "$m" >> "$loaded"; done; exit 0 ;;
  unload|rm|purge|swap|use|reset) exit 0 ;;
esac
if [ "${{1:-}}" = "-t" ] && [ "${{2:-}}" = "list" ]; then
  # On STDERR, as Lmod prints it. A launcher capturing only stderr must see the list.
  listing >&2
  exit 0
fi
exit 0
''')

    if "nvidia" in vendors:
        make_stub(bin_dir, "nvidia-smi", f'''model="{args.gpu_model}"; count={args.gpu_count}; total={args.gpu_memory_mib}
query=""
for a in "$@"; do case "$a" in --query-gpu=*) query=${{a#--query-gpu=}};; esac; done
if [ -n "$query" ]; then
  i=0
  while [ "$i" -lt "$count" ]; do
    line=""
    IFS=',' read -ra fields <<< "$query"
    for f in "${{fields[@]}}"; do
      case "${{f// /}}" in
        index) v="$i";; name) v="$model";; memory.total) v="$total MiB";;
        memory.used) v="0 MiB";; uuid) v="GPU-stub-$i";; *) v="[stub unknown field]";;
      esac
      case "$*" in *nounits*) v=${{v% MiB}};; esac
      if [ -z "$line" ]; then line="$v"; else line="$line, $v"; fi
    done
    echo "$line"; i=$((i + 1))
  done
  exit 0
fi
i=0; while [ "$i" -lt "$count" ]; do echo "|  $i  $model   |  0MiB / ${{total}}MiB |"; i=$((i + 1)); done
exit 0
''')
    if "amd" in vendors:
        for name in ("rocm-smi", "amd-smi"):
            make_stub(bin_dir, name, f'echo "[stub {name}] $*"\nexit 0\n')
    if "intel" in vendors:
        # The two queries tools/xpu-smi-memory-rows.sh makes, in the CSV layout xpu-smi 1.3.5
        # printed on Aurora; anything else is logged and answered with nothing.
        make_stub(bin_dir, "xpu-smi", f'''model="{args.gpu_model}"; count={args.gpu_count}; total={args.gpu_memory_mib}
case "${{1:-}}" in
  discovery)
    echo "Device ID,Device Name,SOC UUID,Memory Physical Size"
    i=0; while [ "$i" -lt "$count" ]; do
      echo "$i,\"$model\",\"00000000-0000-0000-0000-00000000000$i\",\"$total.00 MiB\""; i=$((i + 1))
    done ;;
  dump)
    echo "Timestamp, DeviceId, GPU Memory Used (MiB)"
    i=0; while [ "$i" -lt "$count" ]; do echo "00:00:00.000,    $i, 0.00"; i=$((i + 1)); done ;;
  *) echo "[stub xpu-smi] $*" ;;
esac
exit 0
''')

    make_stub(bin_dir, "sleep", "exec /bin/sleep 0.1\n")
    for spec in args.stub:
        name, _, text = spec.partition("=")
        if not name:
            raise Refusal(f"--stub needs NAME=TEXT, got {spec!r}")
        make_stub(bin_dir, name, f"printf '%s\\n' {json.dumps(text)}\nexit 0\n")


def rewrite_text_files(root: pathlib.Path, rewrites: list[tuple[str, str]]) -> int:
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > (1 << 20):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        for real, fake in rewrites:
            new = new.replace(real, fake)
        if new != text:
            mode = stat.S_IMODE(path.stat().st_mode)
            path.write_text(new)
            path.chmod(mode)
            changed += 1
    return changed


def apply_rewrites(value: str, rewrites: list[tuple[str, str]]) -> str:
    for real, fake in rewrites:
        value = value.replace(real, fake)
    return value


def confined_path(declared: str, rewrites, sandbox_real: pathlib.Path, origin: str) -> pathlib.Path:
    if "$" in declared or "`" in declared:
        raise Refusal(f"{origin} {declared!r} contains an unexpanded shell expansion; declarations "
                      "are read literally and never expanded")
    rewritten = apply_rewrites(declared, rewrites)
    if not rewritten.startswith("/"):
        raise Refusal(f"{origin} {declared!r} is relative, so it would land under the harness's "
                      f"working directory instead of the sandbox")
    resolved = pathlib.Path(os.path.realpath(rewritten))
    try:
        resolved.relative_to(sandbox_real)
    except ValueError:
        raise Refusal(f"{origin} {declared!r} resolves to {resolved}, outside the sandbox "
                      f"{sandbox_real}; map its root with --rewrite-root REAL=NAME")
    return resolved


def kill_group(pgid: int) -> int:
    """Kill every process left in the run's process group; return how many there were."""
    members = 0
    for entry in pathlib.Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = entry.read_text().rpartition(")")[2].split()
        except OSError:
            continue
        if len(fields) > 2 and fields[2] == str(pgid):
            members += 1
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return members


def snapshot(root: pathlib.Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


# ------------------------------------------------------------------ receipt
def load_receipt(script: pathlib.Path, digest: str) -> dict:
    path = receipt_path(script)
    if path.is_file():
        try:
            existing = json.loads(path.read_text())
        except ValueError:
            existing = {}
        if existing.get("script_sha256") == digest:
            return existing
    return {"harness": "dry-run-batch-script.py", "harness_version": VERSION,
            "script": str(script), "script_sha256": digest,
            "positive": None, "negatives": []}


def save_receipt(script: pathlib.Path, receipt: dict) -> pathlib.Path:
    path = receipt_path(script)
    receipt["harness_version"] = VERSION
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return path


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    args = parse_args(argv)
    script = args.script.resolve()
    if not script.is_file():
        raise Refusal(f"no such script: {script}")
    surface, profile_scheduler = _CBS.load_surface(args.machine)
    site_launcher = (profile_scheduler or {}).get("site_launcher")
    vendors = _CBS.accelerator_vendors(args.machine) or set()
    prefix = surface["directive_prefix"]

    tmp_root = pathlib.Path(os.environ.get("TMPDIR") or tempfile.gettempdir())
    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="dry-run.", dir=tmp_root))
    sandbox_real = pathlib.Path(os.path.realpath(sandbox))
    job = sandbox / "job"
    spool = sandbox / "spool"
    submitted_from = sandbox / "submitted-from-here"
    bin_dir = sandbox / "bin"
    for d in (spool, submitted_from, bin_dir, sandbox / "tmp", sandbox / "home", sandbox / "roots"):
        d.mkdir(parents=True)

    try:
        # -- copy the job directory, never run the real one --------------------
        real_dir = script.parent
        ignore = shutil.ignore_patterns(*TOOLING_NAMES, *args.exclude)
        shutil.copytree(real_dir, job, symlinks=True, ignore=ignore)

        rewrites = [(str(real_dir), str(job))]
        for spec in args.rewrite_root:
            real, _, name = spec.partition("=")
            if not real.startswith("/") or not name or "/" in name:
                raise Refusal(f"--rewrite-root needs /absolute/real=name, got {spec!r}")
            target = sandbox / "roots" / name
            target.mkdir(exist_ok=True)
            rewrites.append((real.rstrip("/"), str(target)))
        rewrites.sort(key=lambda pair: -len(pair[0]))  # longest real prefix first
        rewritten_files = rewrite_text_files(job, rewrites)

        # -- perturbation, applied to the copy, verified to have changed it ----
        kind, detail = "positive", None
        if args.negative:
            rel, expr = args.negative
            target = job / rel
            if not target.is_file():
                raise Refusal(f"--negative target not in the job directory: {rel}")
            before = sha256(target)
            subprocess.run(["sed", "-i", expr, str(target)], check=True)
            if sha256(target) == before:
                raise Refusal(f"--negative expression {expr!r} matched nothing in {rel}; the input "
                              "was never perturbed and the run would prove nothing")
            kind, detail = "negative", f"{rel}: {expr}"
        elif args.omit_stand_in:
            kind, detail = "omit-stand-in", args.omit_stand_in
        elif args.short_stand_in:
            kind, detail = "short-stand-in", args.short_stand_in
        elif args.module_drift:
            kind, detail = "module-drift", args.module_drift

        # -- stand-ins, confined -----------------------------------------------
        for spec in args.stand_in:
            declared, _, size = spec.rpartition(":")
            if not declared or not size.isdigit():
                raise Refusal(f"--stand-in needs PATH:BYTES, got {spec!r}")
            if args.omit_stand_in and declared == args.omit_stand_in:
                continue
            resolved = confined_path(declared, rewrites, sandbox_real, "--stand-in")
            nbytes = int(size)
            if args.short_stand_in and declared == args.short_stand_in:
                nbytes = max(nbytes - 1, 0)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with resolved.open("wb") as handle:
                handle.truncate(nbytes)
        if args.omit_stand_in and args.omit_stand_in not in [s.rpartition(":")[0] for s in args.stand_in]:
            raise Refusal(f"--omit-stand-in names no declared --stand-in: {args.omit_stand_in}")
        if args.short_stand_in and args.short_stand_in not in [s.rpartition(":")[0] for s in args.stand_in]:
            raise Refusal(f"--short-stand-in names no declared --stand-in: {args.short_stand_in}")

        # -- the environment the scheduler presents ----------------------------
        # Directives are read from the job copy, after the rewrites and the perturbation: a
        # --negative that edits a directive must reach the environment the run is given, or the
        # run tests the unperturbed script and reports the guard as never firing.
        directives = [l for l in (job / script.name).read_text().splitlines()
                      if l.strip().startswith(prefix)]
        chdir_value = None
        if surface["chdir_option"]:
            chdir_value = _CBS.directive_value(directives, surface["chdir_option"],
                                               surface.get("chdir_option_short"))
        if chdir_value:
            cwd = confined_path(chdir_value, rewrites, sandbox_real,
                                f"the {surface['chdir_option']} directive")
            if not cwd.is_dir():
                raise Refusal(f"the {surface['chdir_option']} directive names {chdir_value}, which "
                              "does not exist in the copied job directory"
                              + ("; the harness does not model what the scheduler does with a "
                                 "missing working directory, so perturb it to another directory "
                                 "that exists" if kind == "negative" else ""))
        elif surface.get("unpinned_start_directory") == "home":
            # PBS starts an unpinned job in the home directory, which is never the job
            # directory, so a script relying on its start directory fails here too.
            cwd = sandbox / "home"
        else:
            cwd = submitted_from
        spool_copy = spool / script.name
        shutil.copy2(job / script.name, spool_copy)

        write_stubs(bin_dir, surface, vendors, args, site_launcher)
        (sandbox / "modules").write_text("")
        module_env_keys = write_module_function(sandbox, bin_dir, args.module_env)

        env = {
            "PATH": f"{bin_dir}:/usr/bin:/bin",
            "HOME": str(sandbox / "home"),
            "TMPDIR": str(sandbox / "tmp"),
            "LANG": "C",
            "USER": os.environ.get("USER", "dryrun"),
            "DRYRUN_STEPS": str(sandbox / "steps"),
            "DRYRUN_REFUSED": str(sandbox / "refused"),
            "DRYRUN_MODULES": str(sandbox / "modules"),
            "DRYRUN_ALLOW_SEQUENTIAL_STEPS": "1" if args.allow_sequential_steps else "0",
            "BASH_ENV": str(sandbox / "module-function.sh"),
            surface["job_id_variable"]: "999999",
            surface["submit_dir_variable"]: str(submitted_from),
        }
        # The scheduler exports the per-task CPU count only when a directive requests one, so a
        # guard that passes when the variable is unset is testable only if this follows the
        # (possibly perturbed) directive.
        cpus_variable = surface.get("cpus_per_task_variable")
        if cpus_variable and surface.get("cpus_per_task_option"):
            cpus = _CBS.directive_value(directives, surface["cpus_per_task_option"],
                                        surface.get("cpus_per_task_option_short"))
            if cpus:
                env[cpus_variable] = cpus
        for spec in args.env:
            key, _, value = spec.partition("=")
            if not key:
                raise Refusal(f"--env needs KEY=VALUE, got {spec!r}")
            env[key] = value
        (sandbox / "steps").write_text("")
        (sandbox / "refused").write_text("")

        before_files = snapshot(job)
        print(f"=== dry run {VERSION}: {script.name}  [{kind}{': ' + detail if detail else ''}]")
        where = ("pinned by directive" if chdir_value else
                 "NOT pinned (the home directory)" if cwd == sandbox / "home" else
                 "NOT pinned (a non-job directory)")
        print(f"    machine {args.machine}; cwd {where};"
              f" {surface['submit_dir_variable']} is not the job directory; $0 is a spool copy;"
              f" {rewritten_files} copied file(s) had roots rewritten")
        print(f"    module env at reset/load: {', '.join(module_env_keys) or 'none'}")
        if args.script_args:
            print(f"    script arguments: {shlex.join(args.script_args)}")
        # Output goes to a file, not a pipe: a background child the script leaves running would
        # hold a pipe open and hang the harness after the script itself had exited.
        out_path = sandbox / "out"
        timed_out = False
        with out_path.open("w") as out_handle:
            proc = subprocess.Popen(["/usr/bin/env", "-i"] + [f"{k}={v}" for k, v in env.items()]
                                    + ["bash", str(spool_copy), *args.script_args],
                                    cwd=cwd, stdin=subprocess.DEVNULL, stdout=out_handle,
                                    stderr=subprocess.STDOUT, start_new_session=True)
            try:
                proc.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            leftover = kill_group(proc.pid)
            proc.wait()
        rc = proc.returncode
        if timed_out:
            leftover = 0
        output = out_path.read_text(errors="replace")

        lines = output.splitlines()
        print("\n".join(lines[-args.tail:]))
        print("-" * 70)
        created = sorted(snapshot(job) - before_files)
        print(f"files the run created under the job copy: {len(created)}")
        for rel in created[:40]:
            print(f"  {rel}")
        steps = (sandbox / "steps").read_text().splitlines()
        print(f"launcher steps created: {len(steps)}")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
        # A script that tolerates a failed leg exits 0 past a refusal, so the exit code alone
        # cannot show it; on the machine that step waits for the allocation until walltime.
        refused = (sandbox / "refused").read_text().splitlines()
        print(f"launcher steps refused: {len(refused)}")
        for i, step in enumerate(refused, 1):
            print(f"  {i}. {step}")
        if leftover:
            print(f"note: {leftover} background process(es) outlived the script and were killed, "
                  "as the scheduler kills a job's processes when its script ends")
        print("-" * 70)
        print(f"exit code: {rc}" + (f" (killed after --timeout {args.timeout:g} s)" if timed_out else ""))

        if timed_out:
            passed = False
            verdict = (f"{'POSITIVE CONTROL' if kind == 'positive' else 'NEGATIVE TEST'} FAILED: the "
                       f"script had not exited after {args.timeout:g} s and was killed. A hang is "
                       "neither a completed run nor a guard firing; find what it waits on. Do not "
                       "submit.")
        elif kind == "positive":
            passed = rc == 0 and not refused
            if refused:
                verdict = (f"POSITIVE CONTROL FAILED: {len(refused)} launcher step(s) were refused "
                           f"although the script exited {rc}. On the machine a refused step waits "
                           "for the allocation until the walltime ends. Launch legs one at a time "
                           "and pass --allow-sequential-steps, or give each concurrent step the "
                           "overlap option. Do not submit.")
            else:
                verdict = ("POSITIVE CONTROL PASSED: ran to completion under the scheduler's environment"
                           if passed else
                           "POSITIVE CONTROL FAILED: the script does not run to completion on correct "
                           "inputs. This is a defect in the script, not the harness. Do not submit.")
        else:
            passed = rc != 0 and not refused
            if refused:
                verdict = (f"NEGATIVE TEST FAILED: {len(refused)} launcher step(s) were refused, so "
                           f"[{kind}: {detail}] was not tested on the path it guards. Fix the "
                           "launch first.")
            else:
                verdict = (f"NEGATIVE TEST PASSED: the guard fired (non-zero) on [{kind}: {detail}]"
                           if passed else
                           f"NEGATIVE TEST FAILED: the run completed although [{kind}: {detail}] should "
                           "have stopped it. A guard that never fires is not a guard.")
        print(verdict)

        if not args.no_receipt:
            digest = sha256(script)
            receipt = load_receipt(script, digest)
            entry = {"utc": utc_now(), "kind": kind, "detail": detail, "rc": rc,
                     "machine": args.machine, "step_refusals": len(refused),
                     "module_env": module_env_keys, "script_args": args.script_args,
                     "timed_out": timed_out, "leftover_processes": leftover}
            if kind == "positive":
                entry["passed"] = passed
                receipt["positive"] = entry
            else:
                entry["fired"] = passed
                receipt["negatives"].append(entry)
            print(f"receipt: {save_receipt(script, receipt)}")
        return 0 if passed else 1
    finally:
        if args.keep:
            print(f"sandbox kept: {sandbox}")
        else:
            shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
