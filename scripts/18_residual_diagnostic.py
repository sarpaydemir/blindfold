#!/usr/bin/env python3
"""
18_residual_diagnostic.py -- where does the leftover coin signal come from?

What it does : 16_identity_audit.py reports that on a blinded card set the
               nearest-neighbour attack still finds the same coin slightly
               more often than chance. Two cards of the SAME coin that cover
               overlapping clock hours are near-duplicates whatever the
               blinding does, so this script repeats the nearest-neighbour
               attack twice: once as the audit runs it, and once with every
               time-overlapping card forbidden as a neighbour. The difference
               says how much of the residual is the overlap and how much is
               not.

Input   : a blinded card folder and its truth file
Output  : <out>/residual-diagnostic-<label>.md
          <out>/runs/<run16>.json  (append-only)

Rules implemented
-----------------
RULES 12 : 1000 shuffles, boundary of the best 1%.
RULES 19 : every number counted.
RULES 23 : the clock is read.
RULES 29 / 30 : run number = SHA-256 of the inputs; records are append-only.

Constants: SHUFFLES, TOP_FRACTION, SEED and the overlap width all come from
the same places as in 15_event_collapse.py and 16_identity_audit.py; none is
chosen here.  No trading rule, threshold or score is defined in this file.

Change made in the second-fix run (2026-10-01): the families left out of
`ALL-removable` are read from 16_identity_audit.FORCED_FAMILIES instead of
being typed here a second time, so the two scripts cannot disagree; outputs
go to <out>/run-<run16>/ and are never overwritten (RULES 30). The version
reviewed is git commit 7735d08 (SHA-256 52ebb0a1...2015).
"""

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab_cards  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ia", os.path.join(HERE, "16_identity_audit.py"))
ia = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ia)

SHUFFLES = ia.SHUFFLES
TOP_FRACTION = ia.TOP_FRACTION
SEED = ia.SEED
CARD_SPAN_GAP_HOURS = 47      # two 48-hour card spans intersect (TACTICS 3)

REPO = os.path.dirname(HERE)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    started = dt.datetime.now(dt.timezone.utc)
    truth = {r["id"]: r for r in csv.DictReader(open(args.truth,
                                                     encoding="utf-8"))}
    names = sorted(f for f in os.listdir(args.cards) if f.endswith(".md"))
    cards = [lab_cards.parse_any_card(os.path.join(args.cards, n))
             for n in names]
    coins = [truth[c["card"]]["coin"] for c in cards]

    def t0(c):
        s = truth[c["card"]]["start_hour_utc"].replace("Z", "")
        if len(s) == 16:
            s += ":00"
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")

    ts = [t0(c) for c in cards]
    feats = [ia.card_features(c) for c in cards]
    allkeys = sorted({k for f in feats for k in f})
    # the same feature set the audit calls ALL-removable
    prefixes = sorted({p for k, v in ia.FAMILIES.items()
                       if k not in ia.FORCED_FAMILIES
                       for p in v})
    keys = ia.select({k: 1 for k in allkeys}, prefixes)
    vecs, used = ia.standardise(feats, keys)
    d = ia.pair_distances(vecs)
    n = len(cards)
    overlap = [[abs((ts[i] - ts[j]).total_seconds()) / 3600.0
                <= CARD_SPAN_GAP_HOURS for j in range(n)] for i in range(n)]

    rows = []
    for mask in (False, True):
        idx = []
        for i in range(n):
            best, bj = None, None
            for j in range(n):
                if j == i or (mask and overlap[i][j]):
                    continue
                if best is None or d[i][j] < best:
                    best, bj = d[i][j], j
            idx.append(bj)
        obs = sum(1 for i, j in enumerate(idx) if coins[j] == coins[i]) / n
        rng = random.Random(SEED)
        perm = list(coins)
        null = []
        for _ in range(SHUFFLES):
            rng.shuffle(perm)
            null.append(sum(1 for i, j in enumerate(idx)
                            if perm[j] == perm[i]) / n)
        line = ia.quantile_top(null, TOP_FRACTION) if hasattr(
            ia, "quantile_top") else sorted(null, reverse=True)[
                max(0, int(round(TOP_FRACTION * len(null))) - 1)]
        rows.append({
            "card_set": args.label,
            "time_overlapping_neighbours_forbidden": "yes" if mask else "no",
            "features_used": len(used),
            "nn_same_coin_accuracy": round(obs, 6),
            "chance_1pct": round(line, 6),
            "null_mean": round(sum(null) / len(null), 6),
            "beats_chance": "YES" if obs > line else "no"})

    script_sha = sha256_file(os.path.abspath(__file__))
    h = hashlib.sha256()
    h.update(("script:" + script_sha + "\n").encode())
    h.update(("audit:" + sha256_file(os.path.join(
        HERE, "16_identity_audit.py")) + "\n").encode())
    h.update(("truth:" + sha256_file(args.truth) + "\n").encode())
    for c in cards:
        h.update(("%s:%s\n" % (c["card"], c["sha256"])).encode())
    run_full = h.hexdigest()
    run16 = run_full[:16]

    runs_dir = os.path.join(args.out, "runs")
    run_dir = os.path.join(args.out, "run-" + run16)
    os.makedirs(runs_dir, exist_ok=True)
    core = {"run": run16, "input_fingerprint": run_full, "label": args.label,
            "cards": n, "rows": rows, "script_sha256": script_sha}
    rec = os.path.join(runs_dir, run16 + ".json")
    if os.path.exists(rec):
        with open(rec, encoding="utf-8") as fh:
            old = json.load(fh)
        differ = [k for k, v in core.items() if old.get(k) != v]
        if differ:
            sys.stderr.write("STOP: run record %s disagrees on %s (RULES 30)\n"
                             % (rec, ", ".join(sorted(differ))))
            sys.exit(1)
        sys.stderr.write("run %s already recorded; nothing written\n" % run16)
        return
    if os.path.exists(run_dir):
        sys.stderr.write("STOP: %s exists without a run record (RULES 30)\n"
                         % run_dir)
        sys.exit(1)
    os.makedirs(run_dir)

    A = ["# Residual diagnostic — card set `%s`" % args.label, "",
         "Written by `scripts/18_residual_diagnostic.py`. It asks one "
         "question: how much of the leftover nearest-neighbour signal on a "
         "blinded card set is simply two cards of the same coin covering "
         "overlapping clock hours, which no blinding can separate because "
         "they are near-copies of each other.", "",
         "| field | value |", "|---|---|",
         "| run number (RULES 29) | `%s` |" % run16,
         "| written at (system clock, UTC, RULES 23) | %s |"
         % started.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "| cards | %d |" % n,
         "| feature set | the audit's `ALL-removable` (forced families "
         "left out: %s) |" % ", ".join("`%s`" % f for f in ia.FORCED_FAMILIES),
         "| shuffles (RULES 12) | %d |" % SHUFFLES,
         "| seed | `%d` |" % SEED,
         "| `scripts/18_residual_diagnostic.py` SHA-256 | `%s` |" % script_sha,
         "",
         "| time-overlapping cards forbidden as neighbours | features | "
         "nearest-neighbour same-coin | chance line (best 1%) | mean of the "
         "null | beats chance |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        A.append("| %s | %d | %.4f | %.4f | %.4f | %s |"
                 % (r["time_overlapping_neighbours_forbidden"],
                    r["features_used"], r["nn_same_coin_accuracy"],
                    r["chance_1pct"], r["null_mean"], r["beats_chance"]))
    A.append("")
    with open(os.path.join(run_dir,
                           "residual-diagnostic-%s.md" % args.label),
              "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")
    with open(rec, "w", encoding="utf-8") as fh:
        json.dump(core, fh, indent=1, sort_keys=True)
        fh.write("\n")
    sys.stderr.write("run %s\n" % run16)


if __name__ == "__main__":
    main()
