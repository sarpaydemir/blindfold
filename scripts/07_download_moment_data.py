#!/usr/bin/env python3
"""
07_download_moment_data.py -- download the per-moment Binance archive data the
                              card needs (TACTICS 3).

What it does
------------
For the 10 observation symbols:
  * funding rate          monthly  data/futures/um/monthly/fundingRate/<SYM>/
                          all 13 months of the card window. Small files, so the
                          whole window is taken rather than single days; the
                          card needs the payment *interval* and its changes,
                          which can only be seen across a run of payments.
  * metrics (5-minute)    daily    data/futures/um/daily/metrics/<SYM>/
                          open interest and the long/short ratios, TACTICS 3.
  * order book depth      daily    data/futures/um/daily/bookDepth/<SYM>/
                          only the moment days, because the files are large
                          (TACTICS 3 says so explicitly).

A "moment day" is every UTC calendar day touched by a card, i.e. by the window
[t0 - 24h, t0 + 23h] of any moment of that symbol.

Before downloading it measures free disk space and the exact byte size of every
file it is about to fetch, from the archive's own listing (RULES 28), and writes
both to data/observation/disk-check-moment-data.json. If it does not fit it
stops without downloading anything.

Input   : data/moments/moments.csv          (from 06)
Output  : data/observation/fundingRate/<SYM>/*.zip
          data/observation/metrics/<SYM>/*.zip
          data/observation/bookDepth/<SYM>/*.zip
          data/observation/manifest.jsonl   (append-only, shared with 05)
          data/observation/disk-check-moment-data.json
          data/observation/missing-archive-files.json  -- every file that the
                          archive does not have or that failed, by name
Rules   : RULES 2, 20, 21, 23, 26, 28, 30 (as in 05)

Re-runnable: yes, and cheap to re-run; a verified file is never fetched twice.
No randomness in this script.
"""

import csv
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import (  # noqa: E402
    FetchError, Manifest, download_verified, list_prefix, utc_now_iso,
)

# ---------------------------------------------------------------- constants --
MONTHS = ["2025-08",
          "2025-09", "2025-10", "2025-11", "2025-12",
          "2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08"]

FUNDING_PREFIX = "data/futures/um/monthly/fundingRate/%s/"
METRICS_PREFIX = "data/futures/um/daily/metrics/%s/"
BOOKDEPTH_PREFIX = "data/futures/um/daily/bookDepth/%s/"

CARD_BEFORE_H = 24      # TACTICS 3: the 24 hours before the start
CARD_AFTER_H = 24       # TACTICS 3: the 24 hours after the start

DISK_HEADROOM_FACTOR = 2.5    # order book files dominate; 2.5x measured bytes
DISK_MIN_FREE_BYTES = 500 * 1024 * 1024
DOWNLOAD_WORKERS = 8

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS_CSV = os.path.join(ROOT, "data", "moments", "moments.csv")
OUT_DIR = os.path.join(ROOT, "data", "observation")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
DISK_PATH = os.path.join(OUT_DIR, "disk-check-moment-data.json")
MISSING_PATH = os.path.join(OUT_DIR, "missing-archive-files.json")

HOUR_MS = 3600 * 1000


def moment_days() -> dict:
    """{symbol: sorted list of 'YYYY-MM-DD' touched by any card window}."""
    days = {}
    with open(MOMENTS_CSV, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sym = row["symbol"]
            t0 = int(row["start_ms"])
            lo = t0 - CARD_BEFORE_H * HOUR_MS
            hi = t0 + (CARD_AFTER_H - 1) * HOUR_MS
            d = datetime.fromtimestamp(lo / 1000, timezone.utc).date()
            end = datetime.fromtimestamp(hi / 1000, timezone.utc).date()
            while d <= end:
                days.setdefault(sym, set()).add(d.isoformat())
                d += timedelta(days=1)
    return {s: sorted(v) for s, v in days.items()}


def listing(prefix: str) -> dict:
    """{filename: (key, size)} for one archive folder."""
    res = list_prefix(prefix)
    out = {}
    for f in res["files"]:
        name = f["key"].rsplit("/", 1)[-1]
        if name.endswith(".zip"):
            out[name] = (f["key"], f["size"])
    return out


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    days = moment_days()
    symbols = sorted(days)

    wanted = []          # (kind, symbol, key, size, dest_rel)
    missing = []         # files the archive does not hold
    listing_errors = []

    for sym in symbols:
        plans = [
            ("fundingRate", FUNDING_PREFIX % sym,
             ["%s-fundingRate-%s.zip" % (sym, m) for m in MONTHS]),
            ("metrics", METRICS_PREFIX % sym,
             ["%s-metrics-%s.zip" % (sym, d) for d in days[sym]]),
            ("bookDepth", BOOKDEPTH_PREFIX % sym,
             ["%s-bookDepth-%s.zip" % (sym, d) for d in days[sym]]),
        ]
        for kind, prefix, names in plans:
            try:
                have = listing(prefix)
            except FetchError as exc:
                listing_errors.append({"kind": kind, "symbol": sym,
                                       "prefix": prefix, "error": str(exc)})
                missing.extend({"kind": kind, "symbol": sym, "file": n,
                                "reason": "folder listing failed: %s" % exc}
                               for n in names)
                continue
            for n in names:
                if n in have:
                    key, size = have[n]
                    wanted.append((kind, sym, key, size,
                                   os.path.join(kind, sym, n)))
                else:
                    missing.append({"kind": kind, "symbol": sym, "file": n,
                                    "reason": "not present in the archive folder "
                                              "(listing returned %d zips)" % len(have)})
        print("listed %s" % sym, flush=True)

    est = sum(w[3] for w in wanted)
    usage = shutil.disk_usage(OUT_DIR)
    required = max(int(est * DISK_HEADROOM_FACTOR), DISK_MIN_FREE_BYTES)
    by_kind = {}
    for kind, _s, _k, size, _d in wanted:
        e = by_kind.setdefault(kind, {"files": 0, "bytes": 0})
        e["files"] += 1
        e["bytes"] += size
    disk = {
        "checked_at_utc": utc_now_iso(),
        "path": OUT_DIR,
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "files_to_fetch": len(wanted),
        "measured_download_bytes": est,
        "size_note": "not an estimate: byte sizes come from the archive's own listing",
        "by_kind": by_kind,
        "required_free_bytes_with_headroom": required,
        "headroom_factor": DISK_HEADROOM_FACTOR,
        "moment_days_per_symbol": {s: len(days[s]) for s in symbols},
        "listing_errors": listing_errors,
        "files_not_in_archive": len(missing),
    }
    with open(DISK_PATH, "w", encoding="utf-8") as fh:
        json.dump(disk, fh, indent=1, sort_keys=True)
    with open(MISSING_PATH, "w", encoding="utf-8") as fh:
        json.dump(missing, fh, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in disk.items()
                      if k != "moment_days_per_symbol"}, indent=1))

    if usage.free < required:
        print("STOP (RULES 28): free %d < required %d. Nothing downloaded."
              % (usage.free, required))
        return 2

    manifest = Manifest(MANIFEST_PATH)
    state = {"n": 0, "failed": []}

    def job(item):
        _kind, _sym, key, _size, dest_rel = item
        row = download_verified(key, os.path.join(OUT_DIR, dest_rel), manifest)
        state["n"] += 1
        if not row.get("checksum_verified"):
            state["failed"].append({"key": key, "error": row.get("error")})
        if state["n"] % 100 == 0:
            print("  %d/%d" % (state["n"], len(wanted)), flush=True)
        return row

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        list(pool.map(job, wanted))

    print(json.dumps({"finished_at_utc": utc_now_iso(),
                      "files_requested": len(wanted),
                      "files_failed": len(state["failed"]),
                      "failures": state["failed"][:20]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
