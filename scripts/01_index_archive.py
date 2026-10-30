#!/usr/bin/env python3
"""
01_index_archive.py -- build the index of every USDT perpetual contract in the
                       Binance USD-M futures archive, and of which monthly 1d
                       kline files each one has.

What it does : (1) lists data/futures/um/monthly/klines/ to get every symbol
                   folder the archive has ever held;
               (2) keeps the USDT perpetual contracts (filter below);
               (3) lists each kept symbol's 1d folder to learn which months
                   exist, which is what decides "first trade in the archive".
Input        : the public archive only (see lab_archive.py for the addresses).
Output       : data/universe/archive-index.json   -- checkpointed, resumable
               data/universe/listing-log.jsonl    -- one line per symbol listed,
                                                     with the time it was read
Rules        : TACTICS 0 (universe built from the archive, not from today's
                          exchange, so contracts that died are included)
               RULES 23 (clock read from the system)
               RULES 26 (checkpointed; a re-run resumes and re-lists nothing)
               RULES 27 (documented addresses only)

Re-runnable: yes. Running it again only fills in symbols not yet indexed.
"""

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import FetchError, list_prefix, utc_now_iso  # noqa: E402

# ---------------------------------------------------------------- constants --
# Period. Written in TACTICS 0 and repeated in this run's instruction.
PERIOD_START = "2025-09-01"
PERIOD_END = "2026-08-31"

# Archive location of USD-M (USDT-margined) futures klines. Documented layout.
KLINES_PREFIX = "data/futures/um/monthly/klines/"
INTERVAL = "1d"          # this run downloads daily klines only, nothing else

# Concurrency. Only affects speed, not any number this script produces.
LIST_WORKERS = 12
CHECKPOINT_EVERY = 25

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "universe")
INDEX_PATH = os.path.join(OUT_DIR, "archive-index.json")
LOG_PATH = os.path.join(OUT_DIR, "listing-log.jsonl")


def is_usdt_perpetual(folder: str) -> bool:
    """The universe filter, stated once.

    A USDT perpetual contract folder name ends in 'USDT' and carries no
    underscore. The underscore marks the archive's dated contracts
    (BTCUSDT_210326, ICPUSDT_SETTLED). Names ending 'USDC'/'BUSD' are other
    quote currencies; names ending 'USDTSETTLED' are settlement leftovers of a
    delisted contract and are not themselves a contract -- the contract's own
    folder (e.g. SXPUSDT) is present separately.
    """
    return folder.endswith("USDT") and "_" not in folder


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)

    index = {"symbols": {}}
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as fh:
            index = json.load(fh)
    index.setdefault("symbols", {})
    index.setdefault("runs", [])

    # -- step 1: every symbol folder ------------------------------------------
    if "all_folders" not in index:
        t0 = utc_now_iso()
        res = list_prefix(KLINES_PREFIX)
        folders = sorted(p.rstrip("/").rsplit("/", 1)[-1] for p in res["dirs"])
        index["all_folders"] = folders
        index["all_folders_listed_at_utc"] = t0
        index["klines_prefix"] = KLINES_PREFIX
        with open(INDEX_PATH, "w", encoding="utf-8") as fh:
            json.dump(index, fh, indent=1, sort_keys=True)
    folders = index["all_folders"]
    symbols = sorted(s for s in folders if is_usdt_perpetual(s))
    index["usdt_perpetual_symbols"] = symbols
    print("symbol folders in archive: %d" % len(folders))
    print("USDT perpetual contracts  : %d" % len(symbols))

    # -- step 2: each symbol's 1d monthly folder ------------------------------
    todo = [s for s in symbols if s not in index["symbols"]]
    print("already indexed: %d   to list: %d" % (len(symbols) - len(todo), len(todo)))

    lock = threading.Lock()
    done = [0]
    log = open(LOG_PATH, "a", encoding="utf-8")

    def work(sym):
        prefix = "%s%s/%s/" % (KLINES_PREFIX, sym, INTERVAL)
        at = utc_now_iso()
        try:
            res = list_prefix(prefix)
            months = sorted(
                k["key"].rsplit("-", 2)[-2] + "-" + k["key"].rsplit("-", 2)[-1][:2]
                for k in res["files"] if k["key"].endswith(".zip")
            )
            sizes = {k["key"]: k["size"] for k in res["files"] if k["key"].endswith(".zip")}
            rec = {"months": months, "listed_at_utc": at, "prefix": prefix,
                   "zip_bytes_total": sum(sizes.values()), "error": None}
        except FetchError as exc:
            rec = {"months": [], "listed_at_utc": at, "prefix": prefix,
                   "zip_bytes_total": 0, "error": str(exc)}
        with lock:
            index["symbols"][sym] = rec
            log.write(json.dumps({"symbol": sym, **rec}, sort_keys=True) + "\n")
            done[0] += 1
            if done[0] % CHECKPOINT_EVERY == 0:
                log.flush()
                with open(INDEX_PATH + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump(index, fh, indent=1, sort_keys=True)
                os.replace(INDEX_PATH + ".tmp", INDEX_PATH)
                print("  checkpoint: %d/%d" % (done[0], len(todo)), flush=True)

    with ThreadPoolExecutor(max_workers=LIST_WORKERS) as pool:
        list(pool.map(work, todo))
    log.close()

    index["runs"].append({"finished_at_utc": utc_now_iso(), "listed_now": len(todo)})
    with open(INDEX_PATH + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1, sort_keys=True)
    os.replace(INDEX_PATH + ".tmp", INDEX_PATH)

    failed = [s for s, r in index["symbols"].items() if r.get("error")]
    empty = [s for s, r in index["symbols"].items() if not r.get("error") and not r["months"]]
    print("listing failures: %d %s" % (len(failed), failed[:10]))
    print("symbols with no 1d monthly file: %d %s" % (len(empty), empty[:10]))
    print("index written: %s" % INDEX_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
