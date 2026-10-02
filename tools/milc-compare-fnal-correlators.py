#!/usr/bin/env python3
"""Check MILC FNAL-format correlator files structurally, then compare them value by value.

    milc-compare-fnal-correlators.py --nt NT --job-id ID [ID ...] --lattice X,Y,Z,T
                                     [--max-relative-difference D] FILE [FILE ...]

The structural contract is software/milc/applications/ks-spectrum.md's: the writers open
their destinations in APPEND mode, so a file can carry stale or duplicated records and still
look complete. Every file is checked for

  - the expected JobID and lattice_size in every metadata block. One --job-id applies to every
    file; a correctness comparison of a tested run against a separate reference run carries two
    different JobIDs, so --job-id may instead give exactly one value per file, in file order.
    Any other count is a usage error rather than a guess at the pairing;
  - a correlator_key on every correlator block, and no key twice (a stale append);
  - exactly NT rows per correlator, with time indices 0..NT-1 in order;
  - finite numbers throughout.

Nonzero values are deliberately NOT a criterion: a symmetry channel or a component can
legitimately vanish.

With more than one file, the first is the reference. Every other file must hold exactly the
reference's key set, and each value is compared as

    max(|re_a - re_b|, |im_a - im_b|) / max over t of max(|re_ref|, |im_ref|)

that is, against the reference correlator's own scale, so a component that is zero to
rounding cannot inflate a relative error. The largest such difference and its key are
reported. Without --max-relative-difference the numbers are reported, not judged; with it, a
file whose largest difference exceeds D fails. Choose D from the files' printed precision:
seven significant digits cannot agree better than a few parts in 1e7.

Exit status: 0 when every file passes every structural check, every key set matches, and no
difference exceeds a given limit; 1 otherwise; 2 on a usage error or an unreadable file.
The standard library only, so it runs wherever the handbook's interpreter does.
"""
from __future__ import annotations

import argparse
import math
import sys

VERSION = "1.1.0"


def parse(path: str, nt: int, job_id: str, lattice: str) -> tuple[dict, list[str]]:
    problems: list[str] = []
    corrs: dict[str, list[tuple[float, float]]] = {}
    seen_meta = False
    with open(path) as handle:
        text = handle.read()
    for block in text.split("\n---\n"):
        head, _, body = block.partition("\n...\n")
        fields: dict[str, str] = {}
        for line in head.splitlines():
            if ":" in line and not line.startswith("---"):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        if "correlator_key" not in fields:
            if "JobID" in fields:
                seen_meta = True
                if fields["JobID"] != job_id:
                    problems.append(f"metadata JobID {fields['JobID']!r}, expected {job_id!r}")
                if fields.get("lattice_size") != lattice:
                    problems.append(f"metadata lattice_size {fields.get('lattice_size')!r}, expected {lattice!r}")
            continue
        key = fields["correlator_key"]
        if not seen_meta:
            problems.append(f"{key}: correlator block before any metadata block")
        if key in corrs:
            problems.append(f"{key}: appears twice (a stale append?)")
        rows = [ln.split() for ln in body.strip().splitlines() if ln.strip() and not ln.startswith("...")]
        try:
            times = [int(r[0]) for r in rows]
            values = [(float(r[1]), float(r[2])) for r in rows]
        except (IndexError, ValueError):
            problems.append(f"{key}: a data row is not 't re im'")
            continue
        if times != list(range(nt)):
            problems.append(f"{key}: {len(times)} rows with time indices "
                            f"{times[:2]}..{times[-2:] if times else []}, expected 0..{nt - 1}")
        if not all(math.isfinite(a) and math.isfinite(b) for a, b in values):
            problems.append(f"{key}: non-finite value")
        corrs[key] = values
    if not corrs:
        problems.append("no correlator records")
    return corrs, problems


def largest_difference(ref: dict, other: dict) -> tuple[float, str | None]:
    worst, worst_key = 0.0, None
    for key, ref_values in ref.items():
        scale = max(max(abs(re), abs(im)) for re, im in ref_values) or 1.0
        for (re_a, im_a), (re_b, im_b) in zip(ref_values, other[key]):
            diff = max(abs(re_a - re_b), abs(im_a - im_b)) / scale
            if diff > worst:
                worst, worst_key = diff, key
    return worst, worst_key


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nt", type=int, required=True, help="temporal extent: rows per correlator")
    ap.add_argument("--job-id", required=True, nargs="+",
                    help="the input's JobID: one for every file, or one per file in file order")
    ap.add_argument("--lattice", required=True, help="lattice_size as the file prints it, e.g. 16,16,16,32")
    ap.add_argument("--max-relative-difference", type=float,
                    help="fail a file whose largest difference from the first file exceeds this")
    ap.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    if len(args.job_id) not in (1, len(args.files)):
        ap.error(f"--job-id takes one value or one per file: got {len(args.job_id)} "
                 f"for {len(args.files)} files")
    job_ids = args.job_id * len(args.files) if len(args.job_id) == 1 else args.job_id

    print(f"milc-compare-fnal-correlators {VERSION}")
    ok = True
    parsed = []
    for path, job_id in zip(args.files, job_ids):
        try:
            corrs, problems = parse(path, args.nt, job_id, args.lattice)
        except OSError as exc:
            print(f"{path}: cannot read ({exc})")
            return 2
        print(f"{path}: {len(corrs)} correlators, {len(problems)} structural problem(s)")
        for problem in problems:
            print(f"  PROBLEM {problem}")
        ok = ok and not problems
        parsed.append((path, corrs))

    ref_path, ref = parsed[0]
    for path, corrs in parsed[1:]:
        if set(corrs) != set(ref):
            ok = False
            print(f"{path}: key set differs from {ref_path}: "
                  f"missing {sorted(set(ref) - set(corrs))}, extra {sorted(set(corrs) - set(ref))}")
            continue
        worst, key = largest_difference(ref, corrs)
        verdict = ""
        if args.max_relative_difference is not None:
            if worst > args.max_relative_difference:
                ok = False
                verdict = f"  EXCEEDS {args.max_relative_difference:.3e}"
            else:
                verdict = f"  within {args.max_relative_difference:.3e}"
        print(f"{path} vs {ref_path}: {len(ref)} keys matched; "
              f"largest |difference| / correlator scale = {worst:.3e} ({key}){verdict}")

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
