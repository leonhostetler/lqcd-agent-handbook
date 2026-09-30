#!/bin/bash
#
# Intel GPU memory as the five device fields tools/monitor-gpu.sh and
# tools/gpu-memory-sampler.sh prefix with a timestamp and a node:
#
#     <index>,<uuid>,<name>,<memory used MiB>,<memory total MiB>
#
# the same fields, in the same order, that those tools ask nvidia-smi for. It is the one
# parse of xpu-smi in the handbook, so the monitor and the sampler cannot drift apart.
#
#     xpu-smi-memory-rows.sh                     one sample, then exit
#     xpu-smi-memory-rows.sh --stream <seconds>  one sample every <seconds>, until killed
#
# Streaming exists because each xpu-smi call costs seconds: on Aurora one sample taken
# as a discovery call plus a dump call took about 7 s, so a monitor sleeping 2 s between
# them sampled about every 9 s. One long-lived `xpu-smi dump -i` delivered samples at the
# requested period. Discovery runs once, before either mode.
#
# ESTABLISHED against xpu-smi 1.3.5 on ALCF Aurora (Data Center GPU Max 1550), 2026-09-30:
#   xpu-smi discovery --dump 1,2,4,16   Device ID,Device Name,SOC UUID,Memory Physical Size
#                                       0,"<name>","<uuid>","131072.00 MiB"
#   xpu-smi dump -d -1 -m 18 ...        Timestamp, DeviceId, GPU Memory Used (MiB)
#                                       20:06:17.218,    0, 78.17
# Metric 18 is per device, the sum of its tiles, and it moved by the amount held when a
# known allocation was held on a whole GPU and on one tile. xpu-smi 1.2.43 prints "N/A"
# for every device's size, so under it this prints nothing: load xpu-smi 1.3.5.
#
# Memory used is fractional MiB; it is rounded UP, so a peak is never understated. A row
# whose value is not a number (N/A) is dropped rather than written as zero, because a
# zero is a measurement and an N/A is not. Prints nothing, and exits 0, when xpu-smi is
# absent or reports no device with a known size: the caller reports the absence.

set -uo pipefail

mode=once
if [ "${1:-}" = --stream ]; then
  mode=stream
  interval=${2:?usage: xpu-smi-memory-rows.sh [--stream <seconds>]}
fi

command -v xpu-smi >/dev/null 2>&1 || exit 0

# Devices with a numeric size, normalised to <index>,<uuid>,<name>,<total MiB>.
devices=$(xpu-smi discovery --dump 1,2,4,16 2>/dev/null | awk -F, '
  function trim(s) { gsub(/^[ \t"]+|[ \t"]+$/, "", s); return s }
  NF == 4 {
    id = trim($1); size = trim($4); sub(/ MiB$/, "", size)
    if (id ~ /^[0-9]+$/ && size ~ /^[0-9]+(\.[0-9]+)?$/)
      print id "," trim($3) "," trim($2) "," int(size)
  }') || true
[ -n "$devices" ] || exit 0

join_rows() {
  XPU_DEVICES="$devices" awk -F, '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    BEGIN {
      n = split(ENVIRON["XPU_DEVICES"], lines, "\n")
      for (i = 1; i <= n; i++) {
        split(lines[i], f, ",")
        uuid[f[1]] = f[2]; name[f[1]] = f[3]; total[f[1]] = f[4]
      }
    }
    NF == 3 {
      id = trim($2); used = trim($3)
      if (!(id in total) || used !~ /^[0-9]+(\.[0-9]+)?$/) next
      mib = int(used); if (used + 0 > mib) mib++
      print id "," uuid[id] "," name[id] "," mib "," total[id]
      fflush()
    }'
}

if [ "$mode" = once ]; then
  xpu-smi dump -d -1 -m 18 -n 1 2>/dev/null | join_rows || true
else
  # Line-buffer xpu-smi where coreutils allows it, so each sample reaches the caller when
  # it is taken rather than when a pipe buffer fills.
  buffer=()
  command -v stdbuf >/dev/null 2>&1 && buffer=(stdbuf -oL)
  # xpu-smi runs as this script's own child, so this script can stop it: a query left
  # running after its monitor stops cannot be told from a live one. stdbuf execs its
  # command, so the child's pid is xpu-smi's.
  "${buffer[@]}" xpu-smi dump -d -1 -m 18 -i "$interval" 2>/dev/null > >(join_rows) &
  producer=$!
  trap 'kill "$producer" 2>/dev/null; exit 0' TERM INT HUP
  wait "$producer" || true
fi
exit 0
