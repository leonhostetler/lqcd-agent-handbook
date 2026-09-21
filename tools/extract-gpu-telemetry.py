#!/usr/bin/env python3
"""Report per-device memory peaks from an accelerator telemetry file.

VERSION 1.0.0

WHY THIS EXISTS. A monitor without a reader is a log, not an instrument. In the
campaign that produced this pair, a reconciliation tool reported "telemetry absent
or no parseable sample rows" against a complete, healthy file, and the peak had to
be recovered by hand. Shipping the collector without the reader is how a
measurement gets lost.

WHAT IT READS. The seven-field line that both tools/monitor-gpu.sh and
tools/gpu-memory-sampler.sh write, so one reader serves the prescribed single-node
monitor and the retained all-node sampler alike:

    <utc>,<node>,<index>,<uuid>,<name>,<memory used MiB>,<memory total MiB>

plus a `telemetry_start` header line per task carrying the sampling interval. The
field order is fixed by the collectors' query string, never by the vendor tool's
own table layout -- a presentation format that moves between driver releases.

THREE BEHAVIOURS THE LEAF REQUIRES OF ANY SUCH READER, each from a recorded defect:

1. A ZERO PEAK IS A MEASUREMENT, not missing data -- the devices were sampled and
   held nothing. Collapsing the two loses the distinction exactly when it matters,
   because they invite opposite next moves. This exits non-zero and says "missing
   data, not a zero peak" only when there are genuinely no rows.

2. IT STRIPS A PARALLEL-LAUNCHER RANK LABEL. A collector launched under a
   launcher's line-labelling option prefixes every line with `<rank>: `, and an
   unstripped prefix silently breaks every match -- producing the same empty
   result as an absent file.

3. IT REPORTS NO MARGIN VERDICT. The required operational headroom is a policy
   value, not a property of the telemetry; embedding one would make a policy
   change invisible. It reports capacity and headroom and lets the caller compare.

NODE COVERAGE IS NOT A PROPERTY OF THIS FILE. Run as the leaf prescribes, the
monitor samples one node, so its peak is a floor for the allocation. The hosts it
saw are reported so that is visible rather than assumed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

VERSION = "1.0.0"
FIELDS = 7
LABEL_RE = re.compile(r"^\s*\d+:\s?")
INTERVAL_RE = re.compile(r"interval_s=(\d+)")


def parse(stream):
    devices: dict[int, dict] = {}
    hosts: set[str] = set()
    intervals: set[int] = set()
    headers = 0
    malformed = 0

    for raw in stream:
        line = LABEL_RE.sub("", raw.strip())
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != FIELDS:
            malformed += 1
            continue

        stamp, node, third = parts[0], parts[1], parts[2]
        hosts.add(node)

        if third == "telemetry_start":
            headers += 1
            found = INTERVAL_RE.search(line)
            if found:
                intervals.add(int(found.group(1)))
            continue

        try:
            index, used, total = int(third), int(parts[5]), int(parts[6])
        except ValueError:
            malformed += 1
            continue

        record = devices.setdefault(
            index,
            {"index": index, "capacity_mib": total, "peak_used_mib": 0,
             "samples": 0, "models_seen": set()},
        )
        record["peak_used_mib"] = max(record["peak_used_mib"], used)
        record["capacity_mib"] = max(record["capacity_mib"], total)
        record["samples"] += 1
        record["models_seen"].add(parts[4])

    return devices, hosts, intervals, headers, malformed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Report per-device memory peaks from an accelerator telemetry file.")
    ap.add_argument("logfile", help="telemetry file, or '-' for stdin")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--expect-devices", type=int, default=None,
                    help="fail unless exactly this many distinct ordinals were sampled")
    ap.add_argument("--expect-model", default=None,
                    help="fail unless every sampled device reports this model substring")
    args = ap.parse_args()

    stream = sys.stdin if args.logfile == "-" else open(
        args.logfile, encoding="utf-8", errors="replace")
    try:
        devices, hosts, intervals, headers, malformed = parse(stream)
    finally:
        if stream is not sys.stdin:
            stream.close()

    if not devices:
        print(f"extract-gpu-telemetry.py {VERSION}: NO DEVICE ROWS "
              f"({headers} header(s), {malformed} unparseable line(s)). "
              "This is MISSING DATA, not a zero peak.", file=sys.stderr)
        return 2

    ordered = [devices[k] for k in sorted(devices)]
    for record in ordered:
        record["models_seen"] = sorted(record.pop("models_seen"))
        record["headroom_mib"] = record["capacity_mib"] - record["peak_used_mib"]

    peaks = [r["peak_used_mib"] for r in ordered]
    summary = {
        "tool_version": VERSION,
        "headers": headers,
        "hosts_sampled": sorted(hosts),
        "sampling_interval_s": sorted(intervals),
        "devices": ordered,
        "max_peak_used_mib": max(peaks),
        "peak_spread_mib": max(peaks) - min(peaks),
        "zero_peak_is_a_measurement": max(peaks) == 0,
        "malformed_lines": malformed,
        "node_coverage_note": (
            "Node coverage is a property of how the collector was launched, not of this "
            "file. Run as the leaf prescribes this is one node, so the peak is a floor."),
    }

    failures = []
    if args.expect_devices is not None and len(ordered) != args.expect_devices:
        failures.append(
            f"expected {args.expect_devices} distinct ordinals, sampled {len(ordered)}")
    if args.expect_model is not None:
        bad = [r for r in ordered
               if not any(args.expect_model in m for m in r["models_seen"])]
        if bad:
            failures.append(
                f"device model mismatch: expected substring {args.expect_model!r}, got "
                + "; ".join(f"[{r['index']}] {r['models_seen']}" for r in bad))
    summary["checks_failed"] = failures

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        interval = ", ".join(f"{i}s" for i in summary["sampling_interval_s"]) or "NOT RECORDED"
        print(f"extract-gpu-telemetry.py {VERSION}")
        print(f"  hosts {', '.join(summary['hosts_sampled']) or '-'}   "
              f"distinct ordinals {len(ordered)}   interval {interval}")
        print()
        print("  ordinal  samples  model                      peak MiB  capacity  headroom")
        for r in ordered:
            print(f"  {r['index']:>7}  {r['samples']:>7}  {r['models_seen'][0]:<24}  "
                  f"{r['peak_used_mib']:>8}  {r['capacity_mib']:>8}  {r['headroom_mib']:>8}")
        print()
        print(f"  max peak {summary['max_peak_used_mib']} MiB   spread across ordinals "
              f"{summary['peak_spread_mib']} MiB")
        if summary["zero_peak_is_a_measurement"]:
            print("  NOTE: peak is 0 MiB on every device. That is a MEASUREMENT -- the "
                  "devices were sampled and held nothing -- not missing telemetry.")
        if not intervals:
            print("  NOTE: no sampling interval recorded; the peak is unqualified by period.")
        if malformed:
            print(f"  NOTE: {malformed} unparseable line(s); investigate before trusting "
                  "the peak.")
        print("  SCOPE: node coverage depends on how the collector was launched.")
        for f in failures:
            print(f"  CHECK FAILED: {f}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
