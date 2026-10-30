#!/usr/bin/env python3
"""
06_find_moments.py -- find the large-movement and calm moments of the 10
                      observation coins (TACTICS 2).

What it does
------------
Reads the hourly klines downloaded by 05_download_hourly.py and, for each of the
10 observation symbols:

  * builds the hourly closing-price series (TACTICS 2: "Hourly closing prices
    are used");
  * measures, for every candidate start hour t0, the 24-hour move
        move(t0) = close(t0+23h) / close(t0-1h) - 1
    i.e. the move over the 24 hours t0 .. t0+23 inclusive, from the closing
    price immediately before them to the closing price at their end. A moment's
    start is t0, "the hour at which the 24-hour movement began" (TACTICS 2);
  * takes the largest moves by absolute size, keeping only the larger of any two
    moments closer than 48 hours (TACTICS 2);
  * takes that many calm moments at random, each at least 72 hours away from
    every large moment (TACTICS 2).

Input   : data/observation/klines_1h/<SYMBOL>/*.zip   (from 05)
          data/draw/observation-coins.txt
Output  : data/moments/moments.csv          -- one row per moment
          data/moments/moment-manifest.md   -- method, seed, counts, SHA-256
          data/moments/lifetimes.json       -- measured per-coin lifetime
Rules   : RULES 19 (nothing unmeasured is written; the lifetime, the move and
                    every count in the manifest are computed here)
          RULES 20 (a coin that yields no moment is named with the reason)
          RULES 23 (clock read from the system)
          RULES 29/30 (the output carries the SHA-256 of its own input; the
                    script refuses to overwrite an existing moments.csv whose
                    content differs)

Randomness
----------
Seed = 20260913, the laboratory's draw number (TACTICS 1). It is a constant of
this laboratory, written down before any result was seen; no new number is
invented here. One random.Random(20260913) is created and consumed in a single
fixed order: the symbols in alphabetical order, one rng.sample() call per
symbol. The same input therefore always gives the same calm moments.

Readings of TACTICS 2 that the text leaves open (reported, not hidden)
----------------------------------------------------------------------
R1  "The largest 20 ... Of two moments closer than 48 hours to each other, only
    the larger counts." Taken as: walk the candidate hours in order of
    decreasing |move| and accept one when it is at least 48 h away from every
    already-accepted moment, until N are accepted. Taking the top 20 hours first
    and only then dropping neighbours would leave two or three moments, because
    one price event occupies ~24 consecutive start hours; that cannot be what
    "one moment per 18 days" means.
R2  "one moment per 18 days" -> N = min(20, floor(lifetime_days / 18)).
    floor, because a full year gives 365/18 = 20.3 -> 20, which is the stated
    cap.
R3  lifetime = the span from the coin's first *traded* hour to its last traded
    hour inside the period ("traded" = kline trade count > 0). Candles that the
    exchange keeps publishing after the last trade, flat and with zero volume,
    are not lifetime.
R4  Every candidate window (the 24 h before t0 and the 24 h from t0) must lie
    inside that traded lifetime. Without this a dead contract's calm moments
    would be hours in which nothing traded at all.
R5  TACTICS 2 puts no minimum distance between two *calm* moments. None is
    imposed here. How many calm pairs ended up closer than 48 h is measured and
    written into the manifest.
"""

import csv
import hashlib
import io
import json
import math
import os
import random
import sys
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import sha256_file, utc_now_iso  # noqa: E402

# ---------------------------------------------------------------- constants --
SEED = 20260913                     # TACTICS 1, the laboratory's draw number

HOUR_MS = 3600 * 1000
PERIOD_START_MS = 1756684800000     # 2025-09-01T00:00:00Z, TACTICS 0
PERIOD_END_MS = 1788220800000       # 2026-09-01T00:00:00Z, exclusive, TACTICS 0

MAX_LARGE_PER_YEAR = 20             # TACTICS 2
DAYS_PER_MOMENT = 18                # TACTICS 2
SEPARATION_LARGE_H = 48             # TACTICS 2
SEPARATION_CALM_FROM_LARGE_H = 72   # TACTICS 2
WINDOW_H = 24                       # TACTICS 2/3: the move window and the card

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_LIST = os.path.join(ROOT, "data", "draw", "observation-coins.txt")
KLINES_DIR = os.path.join(ROOT, "data", "observation", "klines_1h")
OUT_DIR = os.path.join(ROOT, "data", "moments")
MOMENTS_CSV = os.path.join(OUT_DIR, "moments.csv")
MANIFEST_MD = os.path.join(OUT_DIR, "moment-manifest.md")
LIFETIMES_JSON = os.path.join(OUT_DIR, "lifetimes.json")


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def load_hourly(symbol: str) -> dict:
    """Return {open_time_ms: row_dict} from every monthly zip we hold."""
    out = {}
    d = os.path.join(KLINES_DIR, symbol)
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if not name.endswith(".zip"):
            continue
        with zipfile.ZipFile(os.path.join(d, name)) as z:
            for member in z.namelist():
                text = z.read(member).decode("utf-8")
                rdr = csv.reader(io.StringIO(text))
                for row in rdr:
                    if not row or row[0] == "open_time":
                        continue
                    t = int(row[0])
                    out[t] = {
                        "open": float(row[1]), "high": float(row[2]),
                        "low": float(row[3]), "close": float(row[4]),
                        "volume": float(row[5]), "quote_volume": float(row[7]),
                        "count": int(row[8]),
                        "taker_buy_volume": float(row[9]),
                        "taker_buy_quote_volume": float(row[10]),
                    }
    return out


def find_for_symbol(symbol: str, bars: dict, rng: random.Random) -> dict:
    note = {"symbol": symbol, "reason_no_moments": None}

    traded = sorted(t for t, b in bars.items()
                    if PERIOD_START_MS <= t < PERIOD_END_MS and b["count"] > 0)
    if not traded:
        note["reason_no_moments"] = "no hour with a trade inside the period"
        return {"note": note, "moments": []}

    first_traded, last_traded = traded[0], traded[-1]
    lifetime_days = (last_traded - first_traded) / (24 * HOUR_MS)
    n_large = min(MAX_LARGE_PER_YEAR, int(math.floor(lifetime_days / DAYS_PER_MOMENT)))
    note.update({
        "first_traded_hour_utc": iso(first_traded),
        "last_traded_hour_utc": iso(last_traded),
        "lifetime_days": round(lifetime_days, 3),
        "traded_hours_in_period": len(traded),
        "n_large_target": n_large,
    })
    if n_large < 1:
        note["reason_no_moments"] = (
            "lifetime %.2f days is under the %d-day rule, so TACTICS 2 gives 0 moments"
            % (lifetime_days, DAYS_PER_MOMENT))
        return {"note": note, "moments": []}

    # -- candidate start hours (R4) ------------------------------------------
    cands = []
    t0 = first_traded + WINDOW_H * HOUR_MS          # needs 24 h of history
    while t0 + (WINDOW_H - 1) * HOUR_MS <= last_traded:
        base_t = t0 - HOUR_MS
        end_t = t0 + (WINDOW_H - 1) * HOUR_MS
        base = bars.get(base_t)
        end = bars.get(end_t)
        if base and end and base["close"] > 0 and end["close"] > 0:
            if t0 >= PERIOD_START_MS and end_t < PERIOD_END_MS:
                cands.append((t0, end["close"] / base["close"] - 1.0))
        t0 += HOUR_MS
    note["candidate_start_hours"] = len(cands)
    if not cands:
        note["reason_no_moments"] = "no candidate start hour had a complete 48-hour window"
        return {"note": note, "moments": []}

    # -- large moments: greedy by |move|, 48 h apart (R1) --------------------
    sep_large = SEPARATION_LARGE_H * HOUR_MS
    large = []
    for t, mv in sorted(cands, key=lambda x: (-abs(x[1]), x[0])):
        if all(abs(t - u) >= sep_large for u, _ in large):
            large.append((t, mv))
            if len(large) >= n_large:
                break
    large.sort()
    note["n_large_selected"] = len(large)
    if len(large) < n_large:
        note["large_shortfall_reason"] = (
            "only %d start hours could be kept 48 h apart inside the lifetime"
            % len(large))

    # -- calm moments: same count, >= 72 h from any large moment (R5) --------
    sep_calm = SEPARATION_CALM_FROM_LARGE_H * HOUR_MS
    eligible = [t for t, _ in cands
                if all(abs(t - u) >= sep_calm for u, _ in large)]
    note["calm_eligible_hours"] = len(eligible)
    k = min(len(large), len(eligible))
    calm_t = sorted(rng.sample(eligible, k)) if k else []
    note["n_calm_selected"] = len(calm_t)
    if len(calm_t) < len(large):
        note["calm_shortfall_reason"] = (
            "only %d start hours were at least %d h away from every large moment"
            % (len(eligible), SEPARATION_CALM_FROM_LARGE_H))

    mv_by_t = dict(cands)
    moments = []
    for rank, (t, mv) in enumerate(sorted(large, key=lambda x: -abs(x[1])), start=1):
        moments.append({"symbol": symbol, "kind": "large", "start_ms": t,
                        "move_24h": mv, "rank_in_coin": rank})
    for t in calm_t:
        moments.append({"symbol": symbol, "kind": "calm", "start_ms": t,
                        "move_24h": mv_by_t[t], "rank_in_coin": ""})
    moments.sort(key=lambda m: (m["start_ms"], m["kind"]))
    return {"note": note, "moments": moments}


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OBS_LIST, "r", encoding="utf-8") as fh:
        symbols = [ln.strip() for ln in fh if ln.strip()]

    input_fp = hashlib.sha256()
    input_files = []
    for sym in sorted(symbols):
        d = os.path.join(KLINES_DIR, sym)
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if name.endswith(".zip"):
                p = os.path.join(d, name)
                h = sha256_file(p)
                input_files.append((os.path.relpath(p, ROOT), h))
                input_fp.update((name + h).encode())
    input_fp.update(("seed=%d" % SEED).encode())
    run_fp = input_fp.hexdigest()

    rng = random.Random(SEED)
    all_moments, notes = [], []
    for sym in sorted(symbols):                      # fixed order: alphabetical
        bars = load_hourly(sym)
        res = find_for_symbol(sym, bars, rng)
        notes.append(res["note"])
        all_moments.extend(res["moments"])
        n = res["note"]
        print("%-14s lifetime %-8s large %-3s calm %-3s %s" % (
            sym, n.get("lifetime_days"), n.get("n_large_selected", 0),
            n.get("n_calm_selected", 0), n.get("reason_no_moments") or ""), flush=True)

    all_moments.sort(key=lambda m: (m["symbol"], m["start_ms"]))

    rows = [["moment_id", "symbol", "kind", "start_hour_utc", "start_ms",
             "move_24h_pct", "rank_in_coin"]]
    for m in all_moments:
        mid = "%s-%s-%s" % (m["symbol"], m["kind"][0].upper(),
                            iso(m["start_ms"]).replace("-", "").replace(":", "").replace("Z", ""))
        rows.append([mid, m["symbol"], m["kind"], iso(m["start_ms"]),
                     m["start_ms"], "%.4f" % (m["move_24h"] * 100.0),
                     m["rank_in_coin"]])

    body = io.StringIO()
    csv.writer(body, lineterminator="\n").writerows(rows)
    new_text = body.getvalue()
    if os.path.exists(MOMENTS_CSV):
        with open(MOMENTS_CSV, "r", encoding="utf-8") as fh:
            if fh.read() != new_text:
                raise SystemExit("STOP (RULES 30): %s exists with different content"
                                 % MOMENTS_CSV)
    else:
        with open(MOMENTS_CSV, "w", encoding="utf-8") as fh:
            fh.write(new_text)

    with open(LIFETIMES_JSON, "w", encoding="utf-8") as fh:
        json.dump(notes, fh, indent=1, sort_keys=True)

    # -- measurements for the manifest ---------------------------------------
    calm_ts = {}
    for m in all_moments:
        if m["kind"] == "calm":
            calm_ts.setdefault(m["symbol"], []).append(m["start_ms"])
    close_calm_pairs = 0
    for sym, ts in calm_ts.items():
        ts.sort()
        for i in range(len(ts) - 1):
            if ts[i + 1] - ts[i] < SEPARATION_LARGE_H * HOUR_MS:
                close_calm_pairs += 1

    hour_groups = {}
    for m in all_moments:
        hour_groups.setdefault(m["start_ms"], set()).add(m["symbol"])
    shared_hours = {iso(t): sorted(s) for t, s in hour_groups.items() if len(s) > 1}

    moments_sha = sha256_file(MOMENTS_CSV)
    n_large = sum(1 for m in all_moments if m["kind"] == "large")
    n_calm = sum(1 for m in all_moments if m["kind"] == "calm")

    lines = []
    A = lines.append
    A("# Moment manifest\n")
    A("Written by `scripts/06_find_moments.py`, which implements TACTICS 2.\n")
    A("## Run\n")
    A("| field | value |")
    A("|---|---|")
    A("| run number (SHA-256 of the hourly klines + the seed, RULES 29) | `%s` |" % run_fp[:16])
    A("| full input fingerprint | `%s` |" % run_fp)
    A("| written at (system clock, UTC) | %s |" % utc_now_iso())
    A("| **random seed** | **`%d`** (TACTICS 1 draw number) |" % SEED)
    A("| randomness | one `random.Random(%d)`, one `rng.sample` per symbol, symbols alphabetical |" % SEED)
    A("| input files | %d hourly kline zips, listed in `data/observation/manifest.jsonl` |" % len(input_files))
    A("")
    A("## Definitions used\n")
    A("- 24-hour move of start hour `t0` = `close(t0+23h) / close(t0-1h) - 1`,")
    A("  measured on hourly closing prices (TACTICS 2).")
    A("- Large moments: greedy by `|move|`, each at least %d h from every already" % SEPARATION_LARGE_H)
    A("  accepted moment, until `N = min(%d, floor(lifetime_days / %d))` are accepted." % (MAX_LARGE_PER_YEAR, DAYS_PER_MOMENT))
    A("- Calm moments: the same count, drawn at random from start hours at least")
    A("  %d h from every large moment." % SEPARATION_CALM_FROM_LARGE_H)
    A("- Lifetime: first to last hour with a trade (`count > 0`) inside the period.")
    A("- Every candidate window lies inside that lifetime.")
    A("")
    A("## Counts\n")
    A("| symbol | lifetime (days) | traded hours | candidate hours | large | calm | note |")
    A("|---|---|---|---|---|---|---|")
    for n in notes:
        A("| %s | %s | %s | %s | %s | %s | %s |" % (
            n["symbol"], n.get("lifetime_days", "-"), n.get("traded_hours_in_period", "-"),
            n.get("candidate_start_hours", "-"), n.get("n_large_selected", 0),
            n.get("n_calm_selected", 0),
            n.get("reason_no_moments") or n.get("calm_shortfall_reason")
            or n.get("large_shortfall_reason") or ""))
    A("| **total** | | | | **%d** | **%d** |  |" % (n_large, n_calm))
    A("")
    A("## Measured checks\n")
    A("| check | value |")
    A("|---|---|")
    A("| calm pairs inside one coin closer than %d h (TACTICS 2 sets no rule here) | %d |"
      % (SEPARATION_LARGE_H, close_calm_pairs))
    A("| start hours shared by more than one coin (RULES 13 applies downstream) | %d |"
      % len(shared_hours))
    if shared_hours:
        A("")
        A("Shared start hours:\n")
        A("```json")
        A(json.dumps(shared_hours, indent=1, sort_keys=True))
        A("```")
    A("")
    A("## Fingerprints\n")
    A("| file | rows | SHA-256 |")
    A("|---|---|---|")
    A("| `data/moments/moments.csv` | %d | `%s` |" % (len(rows) - 1, moments_sha))
    A("")
    with open(MANIFEST_MD, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(json.dumps({"run_fingerprint": run_fp[:16], "moments": len(all_moments),
                      "large": n_large, "calm": n_calm,
                      "moments_csv_sha256": moments_sha,
                      "close_calm_pairs": close_calm_pairs,
                      "shared_start_hours": len(shared_hours)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
