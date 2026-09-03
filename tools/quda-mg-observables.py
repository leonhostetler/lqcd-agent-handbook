#!/usr/bin/env python3
"""Extract staggered-MG observables from a MILC/QUDA application log.

Implements the handbook observable-extraction contract
(software/quda/solvers/staggered-multigrid/diagnostics.md#observable-extraction-contract)
for the source revision quda b6998853 / milc 6b9b8a06.

Read-only. Streams the log, so a multi-hundred-MB application.out costs no more
memory than one line. Emits one TSV row per hierarchy-build event, because the
contract forbids silently averaging across events.

Level-count agnostic. The coarsest (deflation) level is derived from the log, not
assumed: a three-level hierarchy deflates level 2, a four-level hierarchy level 3.
The handbook corpus is four-level, so its `nvec_3`/`l3_res_max` field names refer
to the COARSEST level, which is `nvec 2` in a three-level MILC parameter file.
Field names here are level-neutral (`coarsest_*`) and `coarsest_level` records
which QUDA level supplied them.

An observable that cannot be recovered is reported as `unavailable`, never as 0.

Usage:
  quda-mg-observables.py LOG [LOG ...] --mgparams FILE [--format tsv|report]

`--mgparams` is REQUIRED and supplies `setup_maxiter_1`, which the contract requires
be read from the literal MILC parameter file rather than inferred. It is not derived
from the log path: a workspace may hold one parameter file per run, one shared by
many, or any other arrangement, so a guessed path can silently bind the WRONG file and
report a confident, wrong cap. A missing field is recoverable; a wrongly attributed one
is not. A cap is never borrowed from another level, run, or hierarchy build.

VERSION HISTORY.
  1.4.0  2026-09-03  --mgparams is REQUIRED and path discovery is removed. Locating the
                     parameter file by directory convention assumed one workspace
                     layout; a different arrangement, including a single shared file,
                     would have bound the wrong cap silently. Requiring it also makes
                     the 1.2.0 defect -- a caller omitting the file -- impossible rather
                     than merely detectable. Before 2026-09-02 this script carried no version at all, which left
tools/trial-report.py -- which imports it -- stamping only its own. A behaviour change
here was therefore invisible in the provenance of a generated table.

  1.3.0  2026-09-02  Replaced `rho_setup` with `setup_l1_capped_fraction`. Two reasons.
                     (a) The name elided its level: `setup_l1_iters` and `setup_maxiter_1`
                     both say level 1, but the ratio built from them did not, so at four
                     levels it was unclear whether it described the level-1 or level-2
                     setup. (b) It was lossy. A capped stream contributes exactly `cap` to
                     the mean, so the ratio saturates: trials with 16/32, 32/48, 48/64,
                     64/64 and 64/64 capped streams reported 0.963, 0.975, 0.982, 1.000
                     and 1.000 -- indistinguishable -- while the fraction reports 0.500,
                     0.667, 0.750, 1.000, 1.000. A campaign results schema carrying the same
                     quantity under another name should record which it stores.
  1.2.0  2026-09-02  Two setup-cap defects, found when a campaign was asked for its
                     rho_setup evidence and every stored observables.tsv said
                     `unavailable`. (a) The cap was only reported alongside a level-1
                     iteration counter, so a run that LOADED near-null vectors reported
                     a knowable parameter-file literal as unrecoverable; the two are now
                     independent and only rho_setup needs both. (b) Callers had to pass
                     --mgparams and tools/reconcile-trial.py never did, so every stored
                     row lost rho_setup even where the trial generated its own vectors
                     and the cap sat one directory away. Resolved by requiring the
                     caller to pass the parameter file; see 1.4.0.
  1.1.0  2026-09-02  Added coarsest_eig_progress_last / _kind, closing the tool gap
                     opened by a trial killed DURING
                     the coarsest eigensolve completes no eigensolve event, so every
                     contract observable is correctly `unavailable` while the log still
                     records how far the solve got. Progress markers only; they are NOT
                     contract-governed and never substitute for eigvec_delivered or
                     trlm_restarts. Verified: trial-report.py output is byte-identical
                     on a committed baseline, so existing tables stay comparable.
  1.0.0  --          State as of the deflating-vectors fields added 2026-08-29,
                     versioned retrospectively. No behaviour is attributed to it.

HANDBOOK NOTE. This tool executes the observable extraction contract in
software/quda/solvers/staggered-multigrid/diagnostics.md, which documents the literal
log lines each field is read from. The contract, not this script, is the specification:
if a QUDA or MILC build changes a message format the parse degrades silently, so confirm
the contract still matches the log before trusting a field, and update both together.
Message formats observed at QUDA b6998853f / MILC 6b9b8a06e. Field names use the
role-based `coarsest_*` naming required of handbook knowledge, not a level index.
"""

import argparse
import pathlib
import re
import sys

VERSION = "1.4.0"
UNAVAIL = "unavailable"

RE_BLOCK = re.compile(r"MG level (\d+) \(GPU\): Transfer: using block size ((?:\d+ x ){3}\d+)")
# Level-1 near-null setup streams carry the "n = <j>" field; solve-side calls do not.
RE_SETUP_CG = re.compile(r"MG level 1 \(GPU\): CG:\s+(\d+) iterations, n = (\d+),")
RE_EVAL = re.compile(
    r"MG level (\d+) \(GPU\): Eval\[(\d+)\] = \(([+-][\d.eE+-]+),.*?Residual = ([+-][\d.eE+-]+)"
)
RE_TRLM = re.compile(r"MG level (\d+) \(GPU\):.*?(\d+) restart steps")
RE_BLOCKED_OPS = re.compile(r"(\d+) BLOCKED OP\*x operations")
RE_COARSE_CONV = re.compile(
    r"MG level (\d+) \(GPU\): (CG|CGNR|GCR|CA-GCR|BiCGstab): Convergence at (\d+) iterations,"
    r" L2 relative residual: iterated = ([\d.eE+-]+) \(requested = ([\d.eE+-]+)\)"
)
RE_COARSE_CAP = re.compile(r"MG level (\d+) \(GPU\): WARNING: Exceeded maximum iterations (\d+)")
RE_OUTER = re.compile(
    r"^GCR: Convergence at (\d+) iterations, L2 relative residual: iterated = ([\d.eE+-]+),"
    r" true = ([\d.eE+-]+) \(requested = ([\d.eE+-]+)\)"
)
RE_SETUP_START = re.compile(r"setting up the MG inverter")
RE_SETUP_DONE = re.compile(r"MG inverter setup complete\. Time = ([\d.eE+-]+)")
RE_UPDATE = re.compile(r"Performing a (thin|full) MG solver update")
RE_CONGRAD5 = re.compile(r"CONGRAD5: time = ([\d.eE+-]+) \(([^)]+)\).*?iters = (\d+)")
RE_MULTISRC = re.compile(r"invertMultiSrcQuda Total time =\s+([\d.eE+-]+)")
RE_FALLBACK = re.compile(r"(fn_QUDA_CG|UML fallback|falling back)", re.IGNORECASE)
# Eigensolver progress marker. QUDA prints this as the Lanczos factorisation advances,
# independently of whether the eigensolve ever converges, so it survives a wall-clock
# kill that leaves no convergence summary. Both the block and plain variants are matched;
# the leading whitespace after the colon is doubled in the observed output.
RE_EIG_PROGRESS = re.compile(r"MG level (\d+) \(GPU\):\s+starting (\w*[Ll]anczosStep) (\d+)")
RE_MGLEVELS = re.compile(r"^\s*mg_levels\s+(\d+)")
RE_SETUP_MAXITER1 = re.compile(r"^\s*setup_maxiter\s+1\s+(\d+)")
RE_NVEC = re.compile(r"^\s*nvec\s+(\d+)\s+(\d+)")
# Coarse deflation application. Two message forms exist and they are NOT the same
# quantity: CG-family solvers deflate eigenvectors of the normal operator ("N
# vectors"), while CA-GCR deflates left/right singular vectors of M ("N left and
# right singular vectors", eigensolve_quda.cpp:578 vs 657). The kind is reported
# alongside the count so a reader cannot silently compare across them.
RE_DEFLATE = re.compile(
    r"MG level (\d+) \(GPU\): Deflating (\d+) (left and right singular vectors|vectors)")

FIELDS = [
    "log", "event", "levels_detected", "coarsest_level", "effective_blocks",
    "setup_seconds", "setup_l1_streams", "setup_l1_iters", "setup_maxiter_1",
    "setup_l1_capped_fraction",
    "update_type",
    "eigvec_delivered", "eigvec_requested", "eval_max", "eval_min", "coarsest_res_max",
    "trlm_restarts", "blocked_op_count",
    "coarsest_solver", "coarsest_calls", "coarsest_target_hits", "coarsest_cap_hits",
    "coarsest_iters_mean", "coarsest_iters_min", "coarsest_iters_max",
    "coarsest_worst_residual", "coarsest_requested_tol",
    "coarsest_fixed_iter_calls", "coarsest_setup_phase_calls", "coarsest_calls_per_outer_iter",
    "outer_solves", "outer_iterations", "outer_true_residual_worst", "outer_requested_tol",
    "congrad5_calls", "congrad5_seconds_total", "invert_multisrc_seconds",
    "fallback_observed",
    # Added 2026-08-29. Gate-D class observable: whether coarse deflation was
    # actually applied at the coarsest level, how many vectors, how many times,
    # and which of the two message forms. Previously recoverable only from
    # trial-report.py, which is why a formatter defect once made a study gate
    # unverifiable. Appended at the end so name-based readers are unaffected.
    "deflating_vectors_applied", "deflating_vectors_kind", "deflate_invocations",
    # Added 2026-09-02. A trial that times out DURING the coarsest eigensolve completes no
    # eigensolve event, so every contract-governed eigensolver field is correctly
    # `unavailable` -- but the log still records how far the solve actually got, and
    # that was readable only by hand. These two fields make an incomplete-setup trial
    # non-blind without weakening the contract: they are progress markers, NOT
    # contract-governed observables, and must never substitute for `eigvec_delivered`
    # or `trlm_restarts`. Absent markers report `unavailable`; step 0 is a legitimate
    # value and is reported as 0. Appended at the end so name-based readers are
    # unaffected.
    "coarsest_eig_progress_last", "coarsest_eig_progress_kind",
]


class Event:
    """One hierarchy-build event and the solve phase that follows it."""

    def __init__(self, index):
        self.index = index
        self.blocks = {}
        self.setup_seconds = None
        self.update_type = None
        self.setup_done = False
        self.l1_open = {}         # stream index n -> running printed k
        self.l1_coarsest = []     # coarsest printed k, one per completed stream
        self.evals = {}           # level -> list of (real, residual)
        self.trlm = {}            # level -> restarts
        self.blocked_ops = None
        self.coarse = {}          # level -> list of (iters, residual, requested)
        self.deflate = {}         # level -> dict(count -> invocations)
        self.deflate_kind = {}    # level -> set of message kinds
        self.coarse_setup_phase = {}
        self.caps = {}            # level -> count of explicit cap warnings
        self.eig_progress = {}    # level -> (last step, marker name); progress, not a contract observable
        self.outer = []           # (iters, true, requested)
        self.congrad5 = []
        self.multisrc = None
        self.fallback = False

    # -- level-1 near-null streams -------------------------------------------------
    def setup_cg(self, k, n):
        """Record the running iteration count for near-null stream index n.

        The contract's rule is that a reset of k to zero starts a new stream. That
        rule must be applied PER STREAM INDEX: block/MRHS setup interleaves several
        concurrent streams and reuses the same n across successive batches, so a
        build with nvec_1 = 64 solved 16 at a time shows n = 0..15 four times over.
        Keying on n alone would merge the batches and keep only the last one; using
        k-resets alone would merge the interleaved streams. Both together give one
        coarsest value per near-null vector.
        """
        prev = self.l1_open.get(n)
        if prev is not None and k < prev:
            self.l1_coarsest.append(prev)
        self.l1_open[n] = k

    def close_l1(self):
        for v in self.l1_open.values():
            self.l1_coarsest.append(v)
        self.l1_open = {}

    # -- derived -------------------------------------------------------------------
    def coarsest_level(self):
        if self.evals:
            return max(self.evals)
        if self.trlm:
            return max(self.trlm)
        # Coarse deflation runs only at the coarsest level, so a progress marker
        # identifies the coarsest level directly. This is what lets a trial killed
        # mid-eigensolve still report which level it died on.
        if self.eig_progress:
            return max(self.eig_progress)
        if self.coarse:
            return max(self.coarse)
        if self.blocks:
            return max(self.blocks) + 1
        return None

    def levels(self):
        t = self.coarsest_level()
        return t + 1 if t is not None else None


def _fmt(x, nd=None):
    if x is None:
        return UNAVAIL
    if isinstance(x, float):
        return f"{x:.6g}" if nd is None else f"{x:.{nd}f}"
    return str(x)


def parse_mgparams(path):
    out = {"setup_maxiter_1": None, "mg_levels": None, "nvec": {}}
    if not path:
        return out
    p = pathlib.Path(path)
    if not p.is_file():
        print(f"warning: mgparams {path} not readable; setup_maxiter_1 unavailable",
              file=sys.stderr)
        return out
    for line in p.read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0]
        m = RE_SETUP_MAXITER1.match(line)
        if m:
            out["setup_maxiter_1"] = int(m.group(1))
        m = RE_MGLEVELS.match(line)
        if m:
            out["mg_levels"] = int(m.group(1))
        m = RE_NVEC.match(line)
        if m:
            out["nvec"][int(m.group(1))] = int(m.group(2))
    return out


def parse_log(path, mg):
    events = []
    cur = Event(1)
    events.append(cur)
    started = False

    with open(path, "r", errors="replace") as fh:
        for line in fh:
            if RE_SETUP_START.search(line):
                # A second build in one log starts a new event record.
                if started and (cur.setup_done or cur.blocks):
                    cur.close_l1()
                    cur = Event(len(events) + 1)
                    events.append(cur)
                started = True
                continue

            m = RE_SETUP_DONE.search(line)
            if m:
                cur.close_l1()
                cur.setup_seconds = float(m.group(1))
                cur.setup_done = True
                continue

            m = RE_UPDATE.search(line)
            if m:
                cur.update_type = m.group(1)
                continue

            m = RE_BLOCK.search(line)
            if m:
                cur.blocks[int(m.group(1))] = m.group(2).replace(" x ", "x")
                continue

            m = RE_SETUP_CG.search(line)
            if m:
                cur.setup_cg(int(m.group(1)), int(m.group(2)))
                continue

            m = RE_EIG_PROGRESS.search(line)
            if m:
                # Keep the LAST marker seen, not the maximum. The counter RESETS on every
                # TRLM restart, so a max would silently report the deepest factorisation
                # of some earlier cycle rather than where the solve actually stood when
                # the wall killed it -- which is the whole point of this field. Verified
                # in one observed case: last 1568, max 2024, and 1568 is the answer.
                lvl, kind, step = int(m.group(1)), m.group(2), int(m.group(3))
                cur.eig_progress[lvl] = (step, kind)
                continue

            m = RE_EVAL.search(line)
            if m:
                cur.evals.setdefault(int(m.group(1)), []).append(
                    (float(m.group(3)), float(m.group(4)))
                )
                continue

            m = RE_TRLM.search(line)
            if m:
                cur.trlm[int(m.group(1))] = int(m.group(2))
                mo = RE_BLOCKED_OPS.search(line)
                if mo:
                    cur.blocked_ops = int(mo.group(1))
                continue

            m = RE_DEFLATE.search(line)
            if m:
                lvl, n, kind = int(m.group(1)), int(m.group(2)), m.group(3)
                d = cur.deflate.setdefault(lvl, {})
                d[n] = d.get(n, 0) + 1
                cur.deflate_kind.setdefault(lvl, set()).add(kind)
                continue

            m = RE_COARSE_CAP.search(line)
            if m:
                lvl = int(m.group(1))
                cur.caps[lvl] = cur.caps.get(lvl, 0) + 1
                continue

            m = RE_COARSE_CONV.search(line)
            if m:
                lvl = int(m.group(1))
                rec = (int(m.group(3)), float(m.group(4)), float(m.group(5)), m.group(2))
                if cur.setup_done:
                    cur.coarse.setdefault(lvl, []).append(rec)
                else:
                    cur.coarse_setup_phase.setdefault(lvl, []).append(rec)
                continue

            m = RE_OUTER.match(line)
            if m:
                cur.outer.append((int(m.group(1)), float(m.group(3)), float(m.group(4))))
                continue

            m = RE_CONGRAD5.search(line)
            if m:
                cur.congrad5.append((float(m.group(1)), m.group(2), int(m.group(3))))
                continue

            m = RE_MULTISRC.search(line)
            if m:
                cur.multisrc = float(m.group(1))
                continue

            if RE_FALLBACK.search(line):
                cur.fallback = True

    cur.close_l1()
    return [e for e in events if e.blocks or e.outer or e.evals or e.congrad5 or e.eig_progress]


def row_for(path, ev, mg):
    t = ev.coarsest_level()
    r = {f: UNAVAIL for f in FIELDS}
    r["log"] = str(path)
    r["event"] = str(ev.index)
    r["levels_detected"] = _fmt(ev.levels())
    r["coarsest_level"] = _fmt(t)
    r["effective_blocks"] = (
        ";".join(f"L{k}={ev.blocks[k]}" for k in sorted(ev.blocks)) if ev.blocks else UNAVAIL
    )
    r["setup_seconds"] = _fmt(ev.setup_seconds)
    r["update_type"] = ev.update_type or "none"

    # setup_maxiter_1 is a literal from the parameter file and is knowable whenever
    # that file was read, including for a run that LOADED its near-null vectors and
    # therefore has no level-1 setup stream. Reporting it only alongside the iteration
    # counter conflated two independent observables and made a knowable cap look
    # unrecoverable. rho_setup still requires both.
    cap = mg.get("setup_maxiter_1")
    if cap:
        r["setup_maxiter_1"] = str(cap)
    if ev.l1_coarsest:
        vals = ev.l1_coarsest
        r["setup_l1_streams"] = str(len(vals))
        r["setup_l1_iters"] = _fmt(sum(vals) / len(vals))
        if cap:
            # Fraction of streams that ENDED AT the cap, not the mean-to-cap ratio the
            # earlier `rho_setup` reported. A capped stream contributes exactly `cap` to
            # the mean, so that ratio saturates near 1 once a minority cap out and stops
            # discriminating: five observed trials spanning 16/32 to 64/64 capped streams
            # all reported 0.963-1.000. The fraction spans 0.500-1.000 over the same runs.
            r["setup_l1_capped_fraction"] = _fmt(
                sum(1 for v in vals if v >= cap) / len(vals)
            )

    if t is not None and t in ev.evals:
        vals = ev.evals[t]
        r["eigvec_delivered"] = str(len(vals))
        r["eval_max"] = _fmt(max(v[0] for v in vals))
        r["eval_min"] = _fmt(min(v[0] for v in vals))
        r["coarsest_res_max"] = _fmt(max(v[1] for v in vals))
        req = mg.get("nvec", {}).get(t)
        if req:
            r["eigvec_requested"] = str(req)
    if t is not None and t in ev.trlm:
        r["trlm_restarts"] = str(ev.trlm[t])
    if ev.blocked_ops is not None:
        r["blocked_op_count"] = str(ev.blocked_ops)

    if t is not None and t in ev.deflate:
        counts = ev.deflate[t]
        # A single distinct count is the healthy case. More than one means the
        # applied vector count changed during the run; report them all rather
        # than a maximum, because a short prefix is a Gate-D failure.
        r["deflating_vectors_applied"] = ",".join(str(c) for c in sorted(counts))
        r["deflate_invocations"] = str(sum(counts.values()))
        r["deflating_vectors_kind"] = ",".join(sorted(ev.deflate_kind.get(t, ())))

    if t is not None and t in ev.eig_progress:
        step, kind = ev.eig_progress[t]
        r["coarsest_eig_progress_last"] = str(step)
        r["coarsest_eig_progress_kind"] = kind

    if t is not None and t in ev.coarse:
        allcalls = ev.coarse[t]
        # A requested tolerance of 0 means a fixed-iteration application (CA-GCR
        # polynomial), not a targeted solve; target and cap hits are undefined for it.
        calls = [c for c in allcalls if c[2] > 0]
        fixed = [c for c in allcalls if c[2] == 0]
        r["coarsest_fixed_iter_calls"] = str(len(fixed))
        solvers = sorted({c[3] for c in allcalls})
        r["coarsest_solver"] = ",".join(solvers)
        if calls:
            hits = [c for c in calls if c[1] <= c[2]]
            iters = [c[0] for c in calls]
            r["coarsest_calls"] = str(len(calls))
            r["coarsest_target_hits"] = str(len(hits))
            r["coarsest_cap_hits"] = str(len(calls) - len(hits))
            r["coarsest_iters_mean"] = _fmt(sum(iters) / len(iters))
            r["coarsest_iters_min"] = str(min(iters))
            r["coarsest_iters_max"] = str(max(iters))
            r["coarsest_worst_residual"] = _fmt(max(c[1] for c in calls))
            r["coarsest_requested_tol"] = _fmt(calls[0][2])
            if ev.outer:
                tot_outer = sum(o[0] for o in ev.outer)
                if tot_outer:
                    r["coarsest_calls_per_outer_iter"] = _fmt(len(calls) / tot_outer)
        else:
            for f in ("coarsest_calls", "coarsest_target_hits", "coarsest_cap_hits",
                      "coarsest_iters_mean", "coarsest_iters_min", "coarsest_iters_max",
                      "coarsest_worst_residual", "coarsest_requested_tol"):
                r[f] = "not-applicable"
        if ev.outer:
            tot_outer = sum(o[0] for o in ev.outer)
            if tot_outer:
                r["coarsest_calls_per_outer_iter"] = _fmt(len(allcalls) / tot_outer)
    if t is not None and t in ev.coarse_setup_phase:
        r["coarsest_setup_phase_calls"] = str(len(ev.coarse_setup_phase[t]))

    if ev.outer:
        r["outer_solves"] = str(len(ev.outer))
        its = sorted({o[0] for o in ev.outer})
        r["outer_iterations"] = ";".join(str(i) for i in its)
        r["outer_true_residual_worst"] = _fmt(max(o[1] for o in ev.outer))
        r["outer_requested_tol"] = _fmt(ev.outer[0][2])

    if ev.congrad5:
        r["congrad5_calls"] = str(len(ev.congrad5))
        r["congrad5_seconds_total"] = _fmt(sum(c[0] for c in ev.congrad5))
    r["invert_multisrc_seconds"] = _fmt(ev.multisrc)
    r["fallback_observed"] = "yes" if ev.fallback else "no"
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--mgparams", required=True,
                    help="MILC MG parameter file supplying setup_maxiter_1 and requested "
                         "nvec; required, and never guessed from the log path")
    ap.add_argument("--version", action="version", version=f"quda-mg-observables.py {VERSION}")
    ap.add_argument("--format", choices=("tsv", "report"), default="tsv")
    args = ap.parse_args()

    mg = parse_mgparams(args.mgparams)
    rows = []
    for log in args.logs:
        p = pathlib.Path(log)
        if not p.is_file():
            print(f"warning: {log} not readable; skipped", file=sys.stderr)
            continue
        for ev in parse_log(p, mg):
            rows.append(row_for(p, ev, mg))

    if not rows:
        print("no hierarchy-build or solve events found", file=sys.stderr)
        return 1

    if args.format == "tsv":
        print("\t".join(FIELDS))
        for r in rows:
            print("\t".join(r[f] for f in FIELDS))
    else:
        for r in rows:
            print(f"=== {r['log']}  event {r['event']} ===")
            for f in FIELDS[2:]:
                print(f"  {f:26s} {r[f]}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
