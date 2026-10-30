#!/usr/bin/env python3
"""
03_build_universe.py -- build the universe table and assign every symbol to one
                        of the four groups.

What it does : reads the verified 1d kline zips, keeps the rows whose day falls
               inside the period, and writes one row per symbol: first/last
               trading day, number of days with data, median daily volume, and
               the assigned group.
Input        : data/universe/archive-index.json
               data/universe/manifest.jsonl
               data/universe/klines/<SYMBOL>/*.zip
Output       : data/universe/universe.csv
               data/universe/universe-groups.json  (sizes and the two cut values)
Rules        : TACTICS 0 (period and universe)
               TACTICS 1 (four groups)
               RULES 19 (no unmeasured number)
               RULES 21 (a file that failed verification is excluded and named,
                         never silently treated as absent data)

Group assignment -- the two points of TACTICS 1 wording were resolved by the
coordinator in this run's instruction, and are implemented exactly as written
there:
  1. 'new' is assigned first and is exclusive: a symbol whose first trade in the
     archive falls inside the period is 'new' and is not also ranked.
  2. the remaining symbols are ranked by median daily volume over the period and
     the ranked list is cut into three groups of EQUAL SIZE (tertiles); where
     the count does not divide by three, the remainder goes to the lower-volume
     groups.

Two different "last day" columns, because they are genuinely different facts:
  last_day_in_period            last day with a 1d kline ROW inside the period
  last_day_with_trades_in_period  last day on which at least one trade happened
A contract delisted mid-period keeps receiving frozen placeholder rows (price
unchanged, volume and count 0) until the end of the period, so for it the first
column reads 2026-08-31 and only the second says when it actually stopped.

Volume column: 'quote_volume' (column 8 of the documented kline CSV), the value
traded in USDT. Base-asset 'volume' is not comparable across contracts, because
one unit means a different amount of money in each of them.

Re-runnable: yes, and it reads only files already on disk.
"""

import csv
import io
import json
import os
import statistics
import zipfile
from datetime import datetime, timezone

# ---------------------------------------------------------------- constants --
PERIOD_START = "2025-09-01"          # TACTICS 0, inclusive, UTC
PERIOD_END = "2026-08-31"            # TACTICS 0, inclusive, UTC
PERIOD_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12",
                 "2026-01", "2026-02", "2026-03", "2026-04",
                 "2026-05", "2026-06", "2026-07", "2026-08"]

VOLUME_COLUMN = "quote_volume"       # documented kline column 8 (index 7)
N_GROUPS = 3                         # large / mid / small

# Minimum number of trades inside the period for a contract to count as having
# TRADED inside the period.
#
# This is not a tuning threshold and it was not chosen by judgement: it is the
# instruction's own sentence, "contracts that TRADED at any point inside the
# period" (and TACTICS 0, "every contract that traded during this period"),
# written as code. One trade is enough.
#
# It is needed because the archive keeps publishing a placeholder 1d kline row
# for a delisted contract: the price is frozen at its last value and volume,
# quote_volume and count are all 0 for every day. Such a contract has a full
# 365 rows in the period and has not traded once. Contracts excluded by this
# line are written out by name to excluded-no-trades.txt, never dropped
# silently (RULES 20, 22).
MIN_TRADES_IN_PERIOD = 1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "universe")
INDEX_PATH = os.path.join(OUT_DIR, "archive-index.json")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
KLINES_DIR = os.path.join(OUT_DIR, "klines")
UNIVERSE_CSV = os.path.join(OUT_DIR, "universe.csv")
GROUPS_JSON = os.path.join(OUT_DIR, "universe-groups.json")

KLINE_HEADER = ["open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "count", "taker_buy_volume",
                "taker_buy_quote_volume", "ignore"]


def day_of_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def read_zip_rows(path: str):
    """Yield dict rows from one monthly kline zip, header row tolerated."""
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        text = zf.read(name).decode("utf-8")
    for parts in csv.reader(io.StringIO(text)):
        if not parts or parts[0] == "open_time":
            continue
        row = dict(zip(KLINE_HEADER, parts))
        yield row


def main() -> int:
    with open(INDEX_PATH, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    manifest = {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                manifest[r["path"]] = r

    unverified = [r for r in manifest.values() if not r["checksum_verified"]]
    if unverified:
        print("files that did NOT verify (%d) -- excluded and named (RULES 21):"
              % len(unverified))
        for r in unverified:
            print("  %s  %s" % (r["path"], r["error"]))

    rows_out = []
    problems = []
    never_traded = []

    for sym in index["usdt_perpetual_symbols"]:
        rec = index["symbols"].get(sym)
        if not rec or rec.get("error") or not rec["months"]:
            continue
        months = rec["months"]
        if not any(m in PERIOD_MONTHS for m in months):
            continue                      # did not trade inside the period

        # --- exact first trading day in the archive --------------------------
        first_month = months[0]
        first_day_archive = None
        fm_rel = os.path.join("klines", sym, "%s-1d-%s.zip" % (sym, first_month))
        fm_path = os.path.join(OUT_DIR, fm_rel)
        if manifest.get(fm_rel, {}).get("checksum_verified") and os.path.exists(fm_path):
            times = [int(r["open_time"]) for r in read_zip_rows(fm_path)]
            if times:
                first_day_archive = day_of_ms(min(times))
        if first_day_archive is None:
            problems.append("%s: first archive month %s not available verified"
                            % (sym, first_month))

        # --- the period's daily rows ----------------------------------------
        days, vols, zero_trade_days, missing_months = [], [], 0, []
        trading_days = []          # days on which at least one trade happened
        total_trades = 0
        for m in [x for x in months if x in PERIOD_MONTHS]:
            rel = os.path.join("klines", sym, "%s-1d-%s.zip" % (sym, m))
            path = os.path.join(OUT_DIR, rel)
            if not (manifest.get(rel, {}).get("checksum_verified") and os.path.exists(path)):
                missing_months.append(m)
                continue
            for r in read_zip_rows(path):
                day = day_of_ms(int(r["open_time"]))
                if day < PERIOD_START or day > PERIOD_END:
                    continue
                days.append(day)
                vols.append(float(r[VOLUME_COLUMN]))
                n_trades = int(r["count"])
                total_trades += n_trades
                if n_trades == 0:
                    zero_trade_days += 1
                else:
                    trading_days.append(day)
        if missing_months:
            problems.append("%s: period months missing/unverified %s" % (sym, missing_months))
        if not days:
            problems.append("%s: no usable kline row inside the period" % sym)
            continue
        if total_trades < MIN_TRADES_IN_PERIOD:
            # kline rows exist, but not one trade happened: did not trade in
            # the period. Recorded by name below.
            never_traded.append({
                "symbol": sym, "days_with_data": len(days),
                "total_trades_in_period": total_trades,
                "first_day_archive": first_day_archive or "",
                "last_day_in_period": max(days),
            })
            continue

        rows_out.append({
            "symbol": sym,
            "first_day_archive": first_day_archive or "",
            "first_day_in_period": min(days),
            "last_day_in_period": max(days),
            "days_with_data": len(days),
            "days_with_zero_trades": zero_trade_days,
            "days_with_trades": len(days) - zero_trade_days,
            "first_day_with_trades_in_period": min(trading_days),
            "last_day_with_trades_in_period": max(trading_days),
            "total_trades_in_period": total_trades,
            "median_daily_quote_volume": statistics.median(vols),
            "last_month_in_archive": months[-1],
            "period_months_missing": ";".join(missing_months),
        })

    # -------------------------------------------------------------- groups ---
    # 1. 'new' first, and exclusive.
    for r in rows_out:
        fda = r["first_day_archive"]
        r["group"] = "new" if (fda and PERIOD_START <= fda <= PERIOD_END) else None

    rest = [r for r in rows_out if r["group"] is None]
    # 2. rank by median daily volume, largest first; ties broken by symbol so
    #    the ranking is deterministic and the draw is reproducible.
    rest.sort(key=lambda r: (-r["median_daily_quote_volume"], r["symbol"]))

    n = len(rest)
    base, rem = divmod(n, N_GROUPS)
    # remainder goes to the LOWER-volume groups: 'small' takes the first extra,
    # then 'mid'. ('large' never grows.)
    n_large = base
    n_mid = base + (1 if rem == 2 else 0)
    n_small = base + (1 if rem >= 1 else 0)
    assert n_large + n_mid + n_small == n, (n_large, n_mid, n_small, n)

    for i, r in enumerate(rest):
        r["volume_rank"] = i + 1
        r["group"] = "large" if i < n_large else ("mid" if i < n_large + n_mid else "small")
    for r in rows_out:
        r.setdefault("volume_rank", "")

    v = [r["median_daily_quote_volume"] for r in rest]
    cut_large_mid = v[n_large - 1] if n_large else None      # lowest volume still 'large'
    first_mid = v[n_large] if n_large < n else None          # highest volume in 'mid'
    cut_mid_small = v[n_large + n_mid - 1] if n_mid else None  # lowest volume still 'mid'
    first_small = v[n_large + n_mid] if n_large + n_mid < n else None

    ties = []
    if cut_large_mid is not None and cut_large_mid == first_mid:
        ties.append("large/mid boundary: identical median volume on both sides")
    if cut_mid_small is not None and cut_mid_small == first_small:
        ties.append("mid/small boundary: identical median volume on both sides")

    # -------------------------------------------------------------- output ---
    rows_out.sort(key=lambda r: r["symbol"])
    fields = ["symbol", "first_day_archive", "last_day_with_trades_in_period",
              "days_with_data", "median_daily_quote_volume", "group",
              "first_day_with_trades_in_period",
              "last_day_in_period", "first_day_in_period",
              "days_with_zero_trades", "days_with_trades", "total_trades_in_period",
              "volume_rank", "last_month_in_archive",
              "period_months_missing"]
    with open(UNIVERSE_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows_out:
            r = dict(r)
            r["median_daily_quote_volume"] = repr(r["median_daily_quote_volume"])
            w.writerow(r)

    excl_path = os.path.join(OUT_DIR, "excluded-no-trades.txt")
    with open(excl_path, "w", encoding="utf-8") as fh:
        fh.write("# Contracts with 1d kline rows inside the period but not one\n"
                 "# trade in it (frozen placeholder rows of a delisted contract).\n"
                 "# Excluded from the universe because the instruction and\n"
                 "# TACTICS 0 both say 'contracts that TRADED'. Named here, not\n"
                 "# dropped silently (RULES 20, 22).\n")
        fh.write("symbol,days_with_data,total_trades_in_period,first_day_archive,last_day_in_period\n")
        for r in sorted(never_traded, key=lambda x: x["symbol"]):
            fh.write("%s,%d,%d,%s,%s\n" % (r["symbol"], r["days_with_data"],
                     r["total_trades_in_period"], r["first_day_archive"],
                     r["last_day_in_period"]))

    sizes = {}
    for r in rows_out:
        sizes[r["group"]] = sizes.get(r["group"], 0) + 1
    summary = {
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "volume_column": VOLUME_COLUMN,
        "universe_size": len(rows_out),
        "group_sizes": sizes,
        "ranked_count_excluding_new": n,
        "tertile_sizes": {"large": n_large, "mid": n_mid, "small": n_small},
        "remainder_rule": "count %% 3 = %d; remainder given to the lower-volume groups"
                          " (small first, then mid)" % rem,
        "cut_large_mid_lowest_large": cut_large_mid,
        "cut_large_mid_highest_mid": first_mid,
        "cut_mid_small_lowest_mid": cut_mid_small,
        "cut_mid_small_highest_small": first_small,
        "ties_straddling_a_cut": ties,
        "min_trades_in_period_to_be_in_universe": MIN_TRADES_IN_PERIOD,
        "excluded_never_traded_count": len(never_traded),
        "excluded_never_traded": sorted(r["symbol"] for r in never_traded),
        "contracts_with_zero_median_daily_volume": sorted(
            r["symbol"] for r in rows_out if r["median_daily_quote_volume"] == 0),
        "files_not_verified": len(unverified),
        "problems": problems,
    }
    with open(GROUPS_JSON, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)

    print(json.dumps({k: v for k, v in summary.items() if k != "problems"},
                     indent=1, sort_keys=True))
    print("problems: %d" % len(problems))
    for p in problems[:20]:
        print("  " + p)
    print("written: %s" % UNIVERSE_CSV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
