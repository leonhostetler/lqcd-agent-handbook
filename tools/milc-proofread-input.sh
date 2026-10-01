#!/usr/bin/env bash
# Proofread a MILC input file with the application's own parser, before submission.
#
# MILC ships an input-validation mode: `prompt 2`, which its source calls
# "proofreading". Under it the application parses the whole input set and performs
# no physics. It costs seconds on one rank and needs no allocation.
#
# THIS TOOL EXISTS BECAUSE THE MODE IS NOT UNIVERSAL AND MISUSING IT IS EXPENSIVE.
# `get_prompt` (generic/io_helpers.c) accepts the value 2 unconditionally, but only
# some applications act on it. An application without the guard reads the input
# exactly as if `prompt 0` and then RUNS THE REAL CALCULATION. Setting `prompt 2`
# on ks_imp_rhmc starts gauge generation. So this tool works from an allowlist and
# refuses anything not on it, rather than trying the run and seeing what happens.
#
# RUN IT WHEN THE SCRIPT AND INPUT ARE WRITTEN, NOT WHEN THE JOB RUNS. MILC already
# parses its whole input set before doing physics, so a proofread inside the batch
# script duplicates a failure the application would produce seconds later anyway. It
# saves no queue wait and no submission. The entire value is at authoring time.
#
# A PARSE-ONLY RUN NEEDS NO GPU, SO THE GPU RUNTIME IS KEPT OUT OF IT. A QUDA-linked
# executable on a GPU-less login node otherwise dies before reading a line: first the
# driver's libcuda.so.1 is absent, and with the toolkit's stub libraries in its place
# the MPI library's CUDA support asks the stub for a device count, gets CUDA error 34
# (stub library), and the first collective fails. The run below therefore disables
# Open MPI's accelerator component, its UCC collectives, and UCX's CUDA transports,
# and, when the executable's libcuda.so.1 or libnvidia-ml.so.1 cannot be resolved,
# links the toolkit's stubs under those names in a private directory. The variables
# are ignored by other MPI libraries. Proofreading returns before setup_layout(), so
# no GPU or halo code runs either way.
#
# A SYCL-linked executable dies earlier still, at library load: the SYCL QUDA library
# constructs a static device, and with no GPU the SYCL runtime throws "No device of
# requested type available" before main. When the executable links libsycl, the parse
# therefore runs with ONEAPI_DEVICE_SELECTOR=opencl:cpu, which overrides a site default
# such as level_zero:gpu. That needs the oneAPI CPU OpenCL runtime; without it the run
# still dies, and the verdict below reports it as indeterminate, never as a pass.
#
# Core dumps are disabled for the run. A GPU-less abort is expected here, not a fault to
# debug, and a core file written into the caller's directory costs hundreds of megabytes.
set -euo pipefail

VERSION="1.2.0"

usage() {
  cat >&2 <<'USAGE'
usage: milc-proofread-input.sh --exe PATH --input PATH [--app NAME]
                               [--launcher "CMD ..."] [--timeout SECONDS]
                               [--keep-output PATH]

  --app         MILC application name. Inferred from the executable basename when
                unambiguous; required otherwise.
  --launcher    Parallel launcher prefix, e.g. "srun -n 1". Default: none. One rank
                is enough -- the supported applications return before setup_layout(),
                so the input's node_geometry is read but never acted on.
  --timeout     Seconds before the proofread is abandoned. Default 120.
  --keep-output Write the proofread log here instead of a temporary file.

exit: 0 proofread clean | 1 input rejected | 2 refused or indeterminate
USAGE
  exit 2
}

# Applications whose control.c and setup.c act on `prompt == 2`, with the evidence
# each rests on. Derived from MILC 6b9b8a06; re-derive after a MILC upgrade with
#   grep -rl 'prompt *== *2' <milc>/*/control.c
# Anything absent from this list is REFUSED, because the failure mode of guessing
# is running the job.
SUPPORTED_APPS="ks_spectrum ks_measure ks_eigen ks_imp_utilities clover_invert2 ext_src file_combine gauge_utilities hvy_qpot rcorr"
EXECUTION_VERIFIED="ks_spectrum"

# Named only to make the refusal specific. Absence from SUPPORTED_APPS is what
# refuses; this list adds the consequence. It is illustrative, never exhaustive.
DANGEROUS_APPS="ks_imp_rhmc wilson_flow ks_hl_spectrum pure_gauge ks_imp_dyn clover_invert"

exe=""; input=""; app=""; launcher=""; timeout_s=120; keep_output=""
while [ $# -gt 0 ]; do
  case "$1" in
    --exe) exe="${2:-}"; shift 2 ;;
    --input) input="${2:-}"; shift 2 ;;
    --app) app="${2:-}"; shift 2 ;;
    --launcher) launcher="${2:-}"; shift 2 ;;
    --timeout) timeout_s="${2:-}"; shift 2 ;;
    --keep-output) keep_output="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage ;;
  esac
done
[ -n "$exe" ] && [ -n "$input" ] || usage
[ -x "$exe" ] || { printf 'FATAL: not executable: %s\n' "$exe" >&2; exit 2; }
[ -r "$input" ] || { printf 'FATAL: cannot read input: %s\n' "$input" >&2; exit 2; }

# ---- resolve the application ------------------------------------------------
if [ -z "$app" ]; then
  base=$(basename -- "$exe")
  matches=""
  for candidate in $SUPPORTED_APPS $DANGEROUS_APPS; do
    case "$base" in "$candidate"*) matches="$matches $candidate" ;; esac
  done
  set -- $matches
  if [ $# -eq 1 ]; then
    app="$1"
  else
    printf 'FATAL: cannot infer the application from %s (matched:%s).\n' "$base" "${matches:- none}" >&2
    printf '       Pass --app explicitly. Guessing is not safe here: see below.\n' >&2
    exit 2
  fi
fi

supported=no
for candidate in $SUPPORTED_APPS; do
  [ "$candidate" = "$app" ] && supported=yes
done

if [ "$supported" != yes ]; then
  printf 'REFUSED: %s does not implement proofreading.\n\n' "$app" >&2
  printf '  `prompt 2` is accepted by the shared input reader but acted on only by:\n' >&2
  printf '    %s\n\n' "$SUPPORTED_APPS" >&2
  printf '  On %s it would parse the input as if `prompt 0` and then RUN THE REAL\n' "$app" >&2
  printf '  CALCULATION. This tool will not do that. For an unsupported application\n' >&2
  printf '  the cheap check is a short job in a debug class, not this tool.\n' >&2
  exit 2
fi

evidence="verified-by-source"
for candidate in $EXECUTION_VERIFIED; do
  [ "$candidate" = "$app" ] && evidence="verified-by-execution"
done

# ---- build the proofread input ----------------------------------------------
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
proof="$work/proofread.in"
# The prompt token is the first non-comment token MILC reads. Accept `prompt N`
# and the bare forms 0/1 that get_prompt also allows.
if grep -qE '^[[:space:]]*prompt[[:space:]]+[012][[:space:]]*$' "$input"; then
  sed -E 's/^[[:space:]]*prompt[[:space:]]+[012][[:space:]]*$/prompt 2/' "$input" > "$proof"
elif grep -qE '^[[:space:]]*[01][[:space:]]*$' "$input"; then
  sed -E '0,/^[[:space:]]*[01][[:space:]]*$/s//2/' "$input" > "$proof"
else
  printf 'FATAL: no prompt line found in %s.\n' "$input" >&2
  printf '       Expected a line `prompt 0` (or a bare 0/1) before the first keyword.\n' >&2
  exit 2
fi

out="${keep_output:-$work/proofread.out}"

# ---- keep the GPU runtime out of the parse-only run ---------------------------
runtime_env=("OMPI_MCA_accelerator=null" "OMPI_MCA_coll=^ucc,hcoll" "UCX_TLS=^cuda_copy,cuda_ipc,gdr_copy")
stubs_used="none needed"
sycl_device="not linked"
missing=""
if command -v ldd >/dev/null 2>&1; then
  ldd_out=$(ldd "$exe" 2>/dev/null || true)
  missing=$(awk '$2 == "=>" && $3 == "not" && ($1 == "libcuda.so.1" || $1 == "libnvidia-ml.so.1") {print $1}' <<< "$ldd_out" | sort -u || true)
  if grep -qE '^[[:space:]]*libsycl\.so' <<< "$ldd_out"; then
    runtime_env+=("ONEAPI_DEVICE_SELECTOR=opencl:cpu")
    sycl_device="opencl:cpu"
  fi
fi
if [ -n "$missing" ]; then
  stub_dir=""
  IFS=: read -r -a candidates <<< "${LIBRARY_PATH:-}${CUDA_HOME:+:$CUDA_HOME/lib64/stubs}"
  for candidate in "${candidates[@]}"; do
    if [ -n "$candidate" ] && [ -e "$candidate/libcuda.so" ]; then stub_dir="$candidate"; break; fi
  done
  if [ -z "$stub_dir" ]; then
    printf 'INDETERMINATE: %s cannot start here: %s not found,\n' "$exe" "$(echo $missing)"
    printf '  and no CUDA stub directory holding libcuda.so is on LIBRARY_PATH or under CUDA_HOME.\n'
    printf '  Load the CUDA module the executable was built with, then re-run. Nothing was proofread.\n'
    exit 2
  fi
  mkdir "$work/cudastub"
  for lib in $missing; do
    [ -e "$stub_dir/${lib%.1}" ] && ln -s "$stub_dir/${lib%.1}" "$work/cudastub/$lib"
  done
  runtime_env+=("LD_LIBRARY_PATH=$work/cudastub${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}")
  stubs_used="$(echo $missing) from $stub_dir"
fi

printf 'milc-proofread-input %s\n' "$VERSION"
printf 'proofreading %s\n  app %s (%s)\n  exe %s\n' "$input" "$app" "$evidence" "$exe"
printf '  gpu runtime disabled for the parse; cuda stubs: %s; sycl device: %s\n' "$stubs_used" "$sycl_device"

# ---- run --------------------------------------------------------------------
# The exit code is deliberately discarded. It is 0 on a compute node whether the
# input parsed or not -- MILC reaches normal_exit(0) either way -- and it can be
# non-zero on a login node for reasons that have nothing to do with the input,
# such as a GPU-less teardown in a linked accelerator library. The verdict comes
# from the log and only from the log.
set +e
# shellcheck disable=SC2086
(ulimit -c 0; env "${runtime_env[@]}" timeout "$timeout_s" $launcher "$exe" < "$proof" > "$out" 2>&1)
set -e

# ---- verdict ----------------------------------------------------------------
# MILC prints input errors in several shapes and NOT in one consistent case:
# setup.c prints lowercase `error in input:`, io_helpers.c prints uppercase
# `ERROR IN INPUT:` and a trailing `INPUT ERROR.`. A grep for any single one of
# these misses the others -- an uppercase-only match misses the fixing_command
# failure entirely. Matching case-insensitively is safe because none of these
# collide with MILC parameter names such as HISQ_REUNIT_SVD_REL_ERROR.
error_re='error in input|input error|is not a valid .* command|is not a valid phase label'

if grep -qiE "$error_re" "$out"; then
  printf 'FAIL: the application rejected this input.\n\n'
  grep -inE "$error_re" "$out" | sed 's/^/  /'
  if [ -n "$keep_output" ]; then
    printf '\n  Full log: %s\n' "$keep_output"
  else
    printf '\n  The full log was temporary and is now gone. Re-run with --keep-output PATH\n'
    printf '  to retain it. This tool does not write into the working directory uninvited.\n'
  fi
  exit 1
fi

# `EOF on input` is the clean-pass signature: control.c loops for another input
# set, readin reaches end-of-file, and the loop exits. Requiring it positively is
# what distinguishes "parsed to the end" from "died before printing anything",
# which a negative-only check cannot tell apart.
if grep -q 'EOF on input' "$out"; then
  printf 'PASS: parsed to end of input, no errors reported.\n'
  exit 0
fi

printf 'INDETERMINATE: no input error, but the parser never reached end of input.\n'
printf '  The proofread may have been killed, or the application may have stopped early.\n'
printf '  Treat this as NOT proofread. Last lines of the log:\n\n'
tail -n 20 "$out" | sed 's/^/    /'
if [ -n "$keep_output" ]; then
  printf '\n  Full log: %s\n' "$keep_output"
else
  printf '\n  The full log was temporary and is now gone. Re-run with --keep-output PATH\n'
  printf '  to retain it.\n'
fi
exit 2
