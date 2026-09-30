#!/usr/bin/env python3
"""Summarise the multi-GPU dslash policy entries in QUDA tunecache files.

    quda-tunecache-policies.py [--expect-gdr 0|1] [--max-policy-seconds S] TUNECACHE [...]

A multi-GPU dslash is tuned as a *policy*: its tunecache row carries the communication
settings in force and the best time found across the policies QUDA tried, halo exchange
included. That makes the policy rows the place to read two things a run log cannot be trusted
for (software/quda/runtime-environment.md):

  - whether GPU-Direct RDMA and peer-to-peer were in force: `gdr=` and `p2p=` are stamped on
    every policy key from the same state QUDA acted on, while QUDA's announcement line cannot
    print at all under the QMP backend;
  - whether a multi-GPU dslash was pathologically slow: the slowest policy time is a direct
    per-application cost, independent of how many iterations a solver ran.

A policy row is one whose aux string begins `policy,`. The `policy_kernel=` rows are the
kernels inside a policy and are not counted. The time is the field before the trailing
comment, in seconds.

For each file it prints the number of policy rows, each distinct (p2p, gdr) pair with its
count, the distinct commDim masks, and the slowest and fastest policy time with its kernel and
volume. Checks, each optional:

  --expect-gdr V        fail unless the file has communicating policy rows and every one
                        carries gdr=V. Only rows with a partitioned dimension count: QUDA
                        stamps gdr= on a single-GPU policy too (commDim=0000), where nothing
                        crosses a link, so such a row shows nothing about GDR. A file with no
                        communicating row fails: nothing was shown either way.
  --max-policy-seconds S  fail if any policy time exceeds S.

Exit status: 0 when every requested check passes on every file, 1 when one fails, 2 on a
usage error or an unreadable file. The standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

VERSION = "1.0.0"
FIELD = re.compile(r"(?:^|,)(p2p|gdr|commDim)=([^,]+)")


def policy_rows(path: str) -> list[dict]:
    rows = []
    with open(path) as handle:
        for line in handle:
            if line.startswith(("tunecache", "#", "comment")) or not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 5 or not fields[2].startswith("policy,"):
                continue
            try:
                seconds = float(fields[-2])
            except ValueError:
                continue
            tags = dict(FIELD.findall(fields[2]))
            rows.append({"volume": fields[0].strip(), "kernel": fields[1], "seconds": seconds,
                         "p2p": tags.get("p2p", "?"), "gdr": tags.get("gdr", "?"),
                         "commDim": tags.get("commDim", "?")})
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--expect-gdr", choices=["0", "1"],
                    help="fail unless every policy row carries this gdr value")
    ap.add_argument("--max-policy-seconds", type=float,
                    help="fail if any policy time exceeds this many seconds")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    print(f"quda-tunecache-policies {VERSION}")
    ok = True
    for path in args.files:
        try:
            rows = policy_rows(path)
        except OSError as exc:
            print(f"{path}: cannot read ({exc})")
            return 2
        print(f"{path}: {len(rows)} policy row(s)")
        if rows:
            pairs = Counter((r["p2p"], r["gdr"]) for r in rows)
            print("  p2p/gdr: " + ", ".join(f"p2p={p},gdr={g} x{n}" for (p, g), n in sorted(pairs.items())))
            print("  commDim: " + ", ".join(sorted({r["commDim"] for r in rows})))
            slow = max(rows, key=lambda r: r["seconds"])
            fast = min(rows, key=lambda r: r["seconds"])
            print(f"  slowest policy: {slow['seconds']:.3e} s  {slow['kernel']}  vol {slow['volume']}")
            print(f"  fastest policy: {fast['seconds']:.3e} s  {fast['kernel']}  vol {fast['volume']}")
        if args.expect_gdr is not None:
            comms = [r for r in rows if r["commDim"].strip("0") not in ("", "?")]
            wrong = [r for r in comms if r["gdr"] != args.expect_gdr]
            if not comms:
                ok = False
                print(f"  FAIL no policy row with a partitioned dimension, so gdr={args.expect_gdr} was not shown")
            elif wrong:
                ok = False
                print(f"  FAIL {len(wrong)} policy row(s) without gdr={args.expect_gdr}")
        if args.max_policy_seconds is not None and rows:
            over = [r for r in rows if r["seconds"] > args.max_policy_seconds]
            if over:
                ok = False
                print(f"  FAIL {len(over)} policy row(s) slower than {args.max_policy_seconds:.3e} s")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
