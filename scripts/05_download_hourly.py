#!/usr/bin/env python3
"""
05_download_hourly.py -- download the hourly (1h) kline files the moment search
                         needs, and verify each one against the archive's own
                         .CHECKSUM companion.

What it does : for the 10 observation symbols plus the two reference symbols
               (BTCUSDT, ETHUSDT), downloads the monthly 1h kline zip for every
               month from 2025-08 through 2026-08.
               2025-08 is included although it is outside the period, because a
               card needs the 24 hours *before* the moment start and a one-line
               summary of the 7 days before that (TACTICS 3); for a moment that
               starts on 2025-09-01 those hours lie in August.
               Before downloading it measures free disk space and the exact byte
               size of every file it is about to fetch (RULES 28) and writes
               both to disk-check-hourly.json.
Input        : data/draw/observation-coins.txt   (the 10 observation symbols)
Output       : data/observation/klines_1h/<SYMBOL>/<SYMBOL>-1h-<YYYY>-<MM>.zip
               data/observation/manifest.jsonl   -- append-only; per file:
                                 source URL, download time, SHA-256, checksum
                                 verification result
               data/observation/disk-check-hourly.json
Rules        : RULES 2  (source, time, fingerprint; verified against .CHECKSUM)
               RULES 20/21 (a file that could not be fetched is recorded by
                            name with its error, never silently dropped)
               RULES 23 (clock read from the system)
               RULES 26 (resumable: a file already present and verified in the
                         manifest is not fetched again)
               RULES 28 (free disk space measured before downloading)
               RULES 30 (manifest append-only)

Re-runnable: yes. An interrupted run is resumed by running it again.
No randomness in this script.
"""

import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import (  # noqa: E402
    FetchError, Manifest, download_verified, list_prefix, utc_now_iso,
)

# ---------------------------------------------------------------- constants --
# Months to fetch, inclusive. Period is 2025-09 .. 2026-08 (TACTICS 0); 2025-08
# is the lookback month the card's "before" section needs (TACTICS 3).
MONTHS = ["2025-08",
          "2025-09", "2025-10", "2025-11", "2025-12",
          "2026-01", "2026-02", "2026-03", "2026-04",
          "2026-05", "2026-06", "2026-07", "2026-08"]

INTERVAL = "1h"
KLINES_PREFIX = "data/futures/um/monthly/klines/"

# The two reference symbols named by TACTICS 3 ("bitcoin and ethereum, over the
# same hours"). They are not observation coins; they are only context columns.
REFERENCE_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

# Disk guard (RULES 28). The archive listing gives the exact byte size of every
# file, so the requirement is measured; this factor is only safety headroom.
DISK_HEADROOM_FACTOR = 5.0
DISK_MIN_FREE_BYTES = 200 * 1024 * 1024

DOWNLOAD_WORKERS = 8

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_LIST = os.path.join(ROOT, "data", "draw", "observation-coins.txt")
OUT_DIR = os.path.join(ROOT, "data", "observation")
KLINES_DIR = os.path.join(OUT_DIR, "klines_1h")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
DISK_PATH = os.path.join(OUT_DIR, "disk-check-hourly.json")


def read_symbols() -> list:
    with open(OBS_LIST, "r", encoding="utf-8") as fh:
        obs = [ln.strip() for ln in fh if ln.strip()]
    return obs + [s for s in REFERENCE_SYMBOLS if s not in obs]


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    symbols = read_symbols()

    # -- what exists in the archive, and how big is it? ----------------------
    wanted = []        # (symbol, month, key, size)
    listing_errors = []
    available = {}
    for sym in symbols:
        prefix = "%s%s/%s/" % (KLINES_PREFIX, sym, INTERVAL)
        try:
            res = list_prefix(prefix)
        except FetchError as exc:
            listing_errors.append({"symbol": sym, "prefix": prefix, "error": str(exc)})
            continue
        sizes = {}
        for f in res["files"]:
            name = f["key"].rsplit("/", 1)[-1]
            if name.endswith(".zip"):
                month = name[:-len(".zip")].rsplit("-", 2)
                sizes["%s-%s" % (month[1], month[2])] = (f["key"], f["size"])
        available[sym] = sorted(sizes.keys())
        for m in MONTHS:
            if m in sizes:
                key, size = sizes[m]
                wanted.append((sym, m, key, size))

    est_bytes = sum(w[3] for w in wanted)
    usage = shutil.disk_usage(OUT_DIR)
    required = max(int(est_bytes * DISK_HEADROOM_FACTOR), DISK_MIN_FREE_BYTES)
    disk = {
        "checked_at_utc": utc_now_iso(),
        "path": OUT_DIR,
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "files_to_fetch": len(wanted),
        "measured_download_bytes": est_bytes,
        "size_note": "not an estimate: byte sizes come from the archive's own listing",
        "required_free_bytes_with_headroom": required,
        "headroom_factor": DISK_HEADROOM_FACTOR,
        "listing_errors": listing_errors,
        "months_available_per_symbol": available,
    }
    with open(DISK_PATH, "w", encoding="utf-8") as fh:
        json.dump(disk, fh, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in disk.items()
                      if k not in ("months_available_per_symbol",)}, indent=1))

    if usage.free < required:
        print("STOP (RULES 28): free %d < required %d" % (usage.free, required))
        return 2

    # -- download ------------------------------------------------------------
    manifest = Manifest(MANIFEST_PATH)
    done = {"n": 0, "failed": []}

    def job(item):
        sym, month, key, _size = item
        dest = os.path.join(KLINES_DIR, sym, key.rsplit("/", 1)[-1])
        row = download_verified(key, dest, manifest)
        done["n"] += 1
        if not row.get("checksum_verified"):
            done["failed"].append({"key": key, "error": row.get("error")})
        if done["n"] % 25 == 0:
            print("  %d/%d" % (done["n"], len(wanted)), flush=True)
        return row

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        list(pool.map(job, wanted))

    print(json.dumps({
        "finished_at_utc": utc_now_iso(),
        "files_requested": len(wanted),
        "files_failed": len(done["failed"]),
        "failures": done["failed"][:20],
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
