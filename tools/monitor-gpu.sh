#!/bin/bash
#
# Accelerator memory monitor for conventions/batch-scripts.md.
#
# A plain background process in the batch script's own shell -- NOT a job step.
# Launching a sampler across the allocation through the parallel launcher creates
# a second job step, steps do not share an allocation by default, and a job has
# been lost that way: the application step could not be created for the whole
# walltime while the sampler recorded an empty device on every node.
#
#     "$handbook/tools/monitor-gpu.sh" 10 > "$run_root/gpu-telemetry.out" 2>&1 &
#     monitor=$!
#     trap 'kill "$monitor" 2>/dev/null || true' EXIT
#
# The optional second argument is the accelerator vendor, resolved from the machine
# profile: nvidia (the default) or intel. Intel reads xpu-smi through
# tools/xpu-smi-memory-rows.sh, and needs xpu-smi 1.3.5 or later loaded first; 1.2.43
# answers N/A, which this reports on stderr as unreadable telemetry.
#
# Intel streams rather than polls. One xpu-smi query costs seconds, so a poll-and-sleep
# loop samples at the query cost plus the interval, not at the interval this header
# records. One long-lived query delivers samples at the interval, and each line is
# stamped as it arrives. Stopping this monitor stops the stream too: it signals the
# helper, and the helper stops its own xpu-smi, so no query outlives the monitor.
#
# The interval is required because it is the one property of this instrument the
# script's author decides per run, and it is recorded in the header: a peak read
# at an unrecorded period is not a bound.
#
# OUTPUT, one line per device per sample, the same seven fields
# tools/gpu-memory-sampler.sh writes, so one reader serves both:
#
#     <utc>,<node>,<index>,<uuid>,<name>,<memory used MiB>,<memory total MiB>
#
# The field order is fixed by the query string below rather than by the vendor
# tool's own table layout. That matters: the table is a PRESENTATION format that
# moves between driver releases, while --query-gpu is a machine interface whose
# order we choose. Parsing the table would take the same exposure this handbook
# refuses for rocm-smi.
#
# Read it with tools/extract-gpu-telemetry.py -- a monitor with no reader is a
# log, not an instrument. NVIDIA and Intel; there is no AMD monitor yet.

set -uo pipefail

interval=${1:?usage: monitor-gpu.sh <interval-seconds> [nvidia|intel]}
vendor=${2:-nvidia}
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
case "$vendor" in
  nvidia|intel) ;;
  *) # Unusable, but a monitor never fails its job.
     printf 'monitor-gpu: no monitor for vendor %s; no telemetry written\n' "$vendor" >&2
     exit 0 ;;
esac
node=$(hostname -s 2>/dev/null || echo unknown)
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
complained=0

printf '%s,%s,telemetry_start,interval_s=%s,monitor-gpu-%s,0,0\n' "$(now)" "$node" "$interval" "$vendor"

if [ "$vendor" = intel ]; then
  stamp() { while IFS=, read -r a b c d e extra; do
              [ -n "$e" ] && [ -z "$extra" ] && printf '%s,%s,%s,%s,%s,%s,%s\n' "$(now)" "$node" "$a" "$b" "$c" "$d" "$e"
            done; }
  "$here/xpu-smi-memory-rows.sh" --stream "$interval" > >(stamp) &
  stream=$!
  trap 'kill "$stream" 2>/dev/null; exit 0' TERM INT HUP
  wait "$stream"
  # Reached only when the stream ends by itself: no xpu-smi, or no device with a known size.
  printf 'monitor-gpu: the xpu-smi stream ended on %s; telemetry is unreadable or incomplete\n' \
         "$node" >&2
  exit 0
fi

while true; do
  # A vendor tool can be installed and still fail -- a node with the binary but
  # no working driver prints an error instead of rows. Keep only lines with the
  # expected field count, so prose never lands in a data file, and say once on
  # stderr that the telemetry will be unreadable rather than leaving the run to
  # discover it at extraction.
  rows=$(nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total \
                    --format=csv,noheader,nounits 2>/dev/null \
         | awk -F, -v ts="$(now)" -v nd="$node" 'NF == 5 { print ts "," nd "," $0 }') || true

  if [ -n "$rows" ]; then
    printf '%s\n' "$rows"
  elif [ "$complained" -eq 0 ]; then
    printf 'monitor-gpu: nvidia-smi returned no device rows on %s; telemetry will be unreadable\n' \
           "$node" >&2
    complained=1
  fi

  sleep "$interval"
done
