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
# log, not an instrument. NVIDIA only; there is no AMD monitor yet.

set -uo pipefail

interval=${1:?usage: monitor-gpu.sh <interval-seconds>}
node=$(hostname -s 2>/dev/null || echo unknown)
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
complained=0

printf '%s,%s,telemetry_start,interval_s=%s,monitor-gpu,0,0\n' "$(now)" "$node" "$interval"

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
