#!/usr/bin/env bash
#
# Reference accelerator-memory sampler for conventions/batch-scripts.md.
#
# The leaf states six properties a sampler must satisfy. Each one is a line of
# code here rather than an instruction, because the properties were written after
# a workspace-local sampler got four of them wrong at once: it sampled one node,
# used a period longer than the phase that failed, wrote unparseable tables, and
# looped forever.
#
#   every node           run it under the parallel launcher, one task per node
#   deliberate period    --interval is REQUIRED and is echoed into the header
#   machine-readable     fixed field order, header written once per task
#   dies with the job    --max-seconds deadline AND signal traps; no endless loop
#   cannot fail the job  every failure degrades the record; this script exits 0
#   vendor from profile  --vendor is REQUIRED and is never guessed from the host
#
# OUTPUT, on stdout, one line per device per sample:
#
#     <utc>,<node>,<index>,<uuid>,<name>,<memory used MiB>,<memory total MiB>
#
# Field 6 is used memory. That position is fixed by the query string below, not
# by any vendor default, so it cannot drift with a tool's own output ordering.
# Exactly one header line per task carries `telemetry_start`; a reader skips it.
#
# USAGE, from a batch script's run section:
#
#     <parallel-launcher> --label -N "$nodes" -n "$nodes" --ntasks-per-node=1 \
#         "$handbook/tools/gpu-memory-sampler.sh" \
#         --vendor nvidia --interval 15 --max-seconds 14700 \
#         > raw/gpu-telemetry.out &
#     sampler=$!
#     trap 'kill "$sampler" 2>/dev/null || true' EXIT
#
# Resolve the launcher name and its line-labelling option from the scheduler
# surface record, and the vendor from the machine profile. Both are shown here as
# Slurm for concreteness; neither is hardcoded in this script.
#
# The labelling option is what prefixes each line with its task id, which is the
# `<rank>: ` prefix a reader strips. Without it every node's lines are
# indistinguishable.

set -uo pipefail

vendor=
interval=
max_seconds=

die() { printf 'gpu-memory-sampler: %s\n' "$1" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --vendor)      vendor=${2:-}; shift 2 ;;
    --interval)    interval=${2:-}; shift 2 ;;
    --max-seconds) max_seconds=${2:-}; shift 2 ;;
    -h|--help)     sed -n '2,41p' "$0"; exit 0 ;;
    *)             die "unknown argument: $1" ;;
  esac
done

# All three are required on purpose. A default period would be this handbook
# asserting a sampling rate it has not measured, and the leaf explicitly asserts
# none; a default deadline would be the unbounded loop the leaf forbids, wearing
# a number. Both belong to the run, so the run states them.
[ -n "$vendor" ]      || die "--vendor is required (resolve it from the machine profile)"
[ -n "$interval" ]    || die "--interval is required (choose it from the run's phase structure)"
[ -n "$max_seconds" ] || die "--max-seconds is required (bound it by the job's own time limit)"

case "$interval" in    ''|*[!0-9]*) die "--interval must be a whole number of seconds" ;; esac
case "$max_seconds" in ''|*[!0-9]*) die "--max-seconds must be a whole number of seconds" ;; esac
[ "$interval" -gt 0 ] || die "--interval must be greater than zero"

node=$(hostname -s 2>/dev/null || echo unknown)
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Field order is chosen HERE, so it is a property of this script rather than of
# the vendor tool's defaults. `fields` is how many the query returns, and every
# line that does not carry exactly that many is dropped: a vendor tool may print
# a driver or permission error ON STDOUT, and prose in a data file is the
# unparseable output this sampler exists to avoid.
case "$vendor" in
  nvidia)
    sampler_command=nvidia-smi
    fields=5
    sample() {
      nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total \
                 --format=csv,noheader,nounits 2>/dev/null
    }
    ;;
  amd)
    # Deliberately not implemented. `rocm-smi`'s memory field names and column
    # order have moved between ROCm releases, and this handbook does not ship a
    # parse it has not run against the installed tool -- which is the same rule
    # the leaf states for periods and field layouts. Establish it on an AMD
    # machine, then replace this branch with a verified query.
    printf '%s,%s,telemetry_start,unimplemented-vendor,amd,0,0\n' "$(now)" "$node"
    printf 'gpu-memory-sampler: amd sampling is not implemented; no samples written\n' >&2
    exit 0
    ;;
  *)
    die "unknown vendor: $vendor (expected one the machine profile declares)"
    ;;
esac

if ! command -v "$sampler_command" >/dev/null 2>&1; then
  # Absence degrades the record and never costs the allocation.
  printf '%s,%s,telemetry_start,absent-tool,%s,0,0\n' "$(now)" "$node" "$sampler_command"
  printf 'gpu-memory-sampler: %s not found on %s; no samples written\n' \
         "$sampler_command" "$node" >&2
  exit 0
fi

running=1
stop() { running=0; }
trap stop TERM INT HUP

# One header per task. It carries the period and the bound, so a peak read from
# this file can always be qualified by how often it was sampled -- the leaf's
# "a peak read at an unrecorded period is not a bound".
printf '%s,%s,telemetry_start,interval_s=%s,max_seconds=%s,0,0\n' \
       "$(now)" "$node" "$interval" "$max_seconds"

deadline=$(( $(date -u +%s) + max_seconds ))
complained=0

while [ "$running" -eq 1 ] && [ "$(date -u +%s)" -lt "$deadline" ]; do
  stamp=$(now)
  # `|| true` is load-bearing twice over: a command substitution takes the status
  # of the pipeline inside it, and a transient query failure must neither end
  # sampling nor fail the job.
  rows=$(sample | awk -F, -v ts="$stamp" -v nd="$node" -v want="$fields" \
                        'NF == want { print ts "," nd "," $0 }') || true
  if [ -n "$rows" ]; then
    printf '%s\n' "$rows"
  elif [ "$complained" -eq 0 ]; then
    # Say it once. A per-sample complaint would bury the run's real stderr.
    printf 'gpu-memory-sampler: %s returned no parseable rows on %s; continuing\n' \
           "$sampler_command" "$node" >&2
    complained=1
  fi
  sleep "$interval" || break
done

exit 0
