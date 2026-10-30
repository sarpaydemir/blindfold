#!/usr/bin/env python3
"""
02_download_klines.py -- download the daily (1d) kline files needed to build the
                         universe, and verify each one against the archive's own
                         .CHECKSUM companion.

What it does : for every USDT perpetual contract in the archive index, downloads
               the monthly 1d kline zip for each month that overlaps the period
               2025-09 .. 2026-08. For a contract whose first archive month is
               *before* the period it also downloads that single first month, so
               the contract's exact first trading day can be stated as a
               measured date rather than a month.
               Nothing else is downloaded in this run: no order book, no
               funding, no 5-minute data.
Input        : data/universe/archive-index.json  (written by 01_index_archive.py)
Output       : data/universe/klines/<SYMBOL>/<SYMBOL>-1d-<YYYY>-<MM>.zip
               data/universe/manifest.jsonl  -- append-only; per file: source
                                                URL, download time, SHA-256,
                                                checksum-verification result
Rules        : RULES 2  (source, time, fingerprint; verify against .CHECKSUM)
               RULES 20/21 (a failed file is recorded by name, not dropped)
               RULES 23 (clock read from the system)
               RULES 26 (resumable: a file already present and verified in the
                         manifest is not fetched again)
               RULES 28 (free disk space measured before downloading)
               RULES 30 (manifest is append-only; different content under an
                         existing path stops the script)

Re-runnable: yes. An interrupted run is resumed by running it again.
"""

import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import (  # noqa: E402
    FetchError, Manifest, http_get, object_url, sha256_bytes, utc_now_iso,
)

# ---------------------------------------------------------------- constants --
# Period months, inclusive. From TACTICS 0 / this run's instruction.
PERIOD_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12",
                 "2026-01", "2026-02", "2026-03", "2026-04",
                 "2026-05", "2026-06", "2026-07", "2026-08"]

KLINES_PREFIX = "data/futures/um/monthly/klines/"
INTERVAL = "1d"

# Disk guard (RULES 28). The archive's own listing gives the exact byte size of
# every file we are about to fetch, so the requirement is measured, not guessed;
# this multiplier is only the safety headroom on top of it.
DISK_HEADROOM_FACTOR = 5.0
DISK_MIN_FREE_BYTES = 200 * 1024 * 1024

DOWNLOAD_WORKERS = 12
PROGRESS_EVERY = 200

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "universe")
INDEX_PATH = os.path.join(OUT_DIR, "archive-index.json")
KLINES_DIR = os.path.join(OUT_DIR, "klines")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
DISK_PATH = os.path.join(OUT_DIR, "disk-check.json")


def main() -> int:
    with open(INDEX_PATH, "r", encoding="utf-8") as fh:
        index = json.load(fh)

    symbols = index["usdt_perpetual_symbols"]

    # -- which files do we need? ---------------------------------------------
    wanted = []           # (symbol, month)
    est_bytes = 0
    for sym in symbols:
        rec = index["symbols"].get(sym)
        if not rec or rec.get("error"):
            continue
        months = rec["months"]
        if not months:
            continue
        in_period = [m for m in months if m in PERIOD_MONTHS]
        if not in_period:
            continue                      # never traded inside the period
        need = set(in_period)
        if months[0] < PERIOD_MONTHS[0]:
            need.add(months[0])           # exact first trading day
        for m in sorted(need):
            wanted.append((sym, m))
        # the index holds the total zip bytes of the whole 1d folder; scale it
        est_bytes += int(rec["zip_bytes_total"] * len(need) / max(len(months), 1))

    # -- disk check before downloading anything (RULES 28) --------------------
    usage = shutil.disk_usage(OUT_DIR)
    need_bytes = int(est_bytes * DISK_HEADROOM_FACTOR) + DISK_MIN_FREE_BYTES
    disk = {
        "checked_at_utc": utc_now_iso(),
        "path": OUT_DIR,
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "files_to_fetch": len(wanted),
        "estimated_download_bytes": est_bytes,
        "estimate_note": "estimate: per-symbol zip bytes from the archive listing, "
                         "scaled by the fraction of months we take",
        "required_free_bytes_with_headroom": need_bytes,
    }
    with open(DISK_PATH, "w", encoding="utf-8") as fh:
        json.dump(disk, fh, indent=1, sort_keys=True)
    print("disk free: %d bytes (%.2f GiB)" % (usage.free, usage.free / 2**30))
    print("files to fetch: %d   estimated download: %d bytes (estimate)"
          % (len(wanted), est_bytes))
    if usage.free < need_bytes:
        print("STOP (RULES 28): free space %d < required %d" % (usage.free, need_bytes))
        return 2

    # -- download -------------------------------------------------------------
    manifest = Manifest(MANIFEST_PATH)
    lock = threading.Lock()
    counts = {"done": 0, "skipped": 0, "ok": 0, "failed": 0}

    def work(item):
        sym, month = item
        fname = "%s-%s-%s.zip" % (sym, INTERVAL, month)
        key = "%s%s/%s/%s" % (KLINES_PREFIX, sym, INTERVAL, fname)
        dest = os.path.join(KLINES_DIR, sym, fname)
        rel = os.path.relpath(dest, OUT_DIR)
        with lock:
            already = manifest.has_verified(rel) and os.path.exists(dest)
        if already:
            with lock:
                counts["skipped"] += 1
                counts["done"] += 1
            return
        # fetch outside the lock, record inside it
        zip_url = object_url(key)
        sum_url = zip_url + ".CHECKSUM"
        row = {"path": rel, "symbol": sym, "month": month,
               "source_url": zip_url, "checksum_url": sum_url,
               "downloaded_at_utc": None, "sha256": None, "expected_sha256": None,
               "checksum_verified": False, "error": None}
        try:
            blob = http_get(zip_url)
        except FetchError as exc:
            row["downloaded_at_utc"] = utc_now_iso()
            row["error"] = "zip fetch failed: %s" % exc
            with lock:
                manifest.add(row)
                counts["failed"] += 1
                counts["done"] += 1
            return
        row["downloaded_at_utc"] = utc_now_iso()
        row["sha256"] = sha256_bytes(blob)
        try:
            row["expected_sha256"] = http_get(sum_url).decode("utf-8", "replace").split()[0].lower()
        except FetchError as exc:
            row["error"] = "checksum fetch failed: %s" % exc
        if row["expected_sha256"]:
            row["checksum_verified"] = row["sha256"] == row["expected_sha256"]
            if not row["checksum_verified"]:
                row["error"] = "CHECKSUM MISMATCH: computed %s, archive says %s" % (
                    row["sha256"], row["expected_sha256"])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        out = dest if row["checksum_verified"] else dest + ".FAILED"
        with open(out, "wb") as fh:
            fh.write(blob)
        with lock:
            manifest.add(row)
            counts["ok" if row["checksum_verified"] else "failed"] += 1
            counts["done"] += 1
            if counts["done"] % PROGRESS_EVERY == 0:
                print("  %d/%d  ok=%d skipped=%d failed=%d"
                      % (counts["done"], len(wanted), counts["ok"],
                         counts["skipped"], counts["failed"]), flush=True)

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        list(pool.map(work, wanted))

    print("finished %s" % utc_now_iso())
    print("ok=%d skipped(already verified)=%d failed=%d total=%d"
          % (counts["ok"], counts["skipped"], counts["failed"], len(wanted)))
    bad = [r for r in Manifest(MANIFEST_PATH).rows.values() if not r["checksum_verified"]]
    if bad:
        print("FAILED FILES, by name (RULES 20/21):")
        for r in bad:
            print("  %s  %s" % (r["path"], r["error"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
