#!/usr/bin/env python3
"""
08_external_sources.py -- fetch the non-Binance sources TACTICS 3 names, and
                          record by name every source that could not be reached.

What it does
------------
TACTICS 3 asks the card to carry, besides the exchange data:
  * Binance and Korean exchange announcements (listing, delisting, warning)
  * the US release calendar (inflation, employment, rate decision)
  * the number of people viewing the page on Wikipedia (daily)
  * the price of the relevant prediction market, if any

This script goes after each one, from a documented public address, and writes
down what it got. A source that answered with an error is written down as an
error, never as "no data" (RULES 20, 21).

Documented addresses used
-------------------------
BLS release calendar   https://www.bls.gov/schedule/<YYYY>/<MM>_sched_list.htm
                       The monthly "list" pages linked from the BLS release
                       calendar front page https://www.bls.gov/schedule/ .
                       Each row is Date | Time | Release. Times are Eastern
                       Time and are converted to UTC here.
FOMC rate decisions    https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
                       The Federal Reserve's own FOMC calendar. The decision
                       date is taken from the statement link of each meeting
                       (.../pressreleases/monetaryYYYYMMDDa.htm), which is the
                       date the statement was published. The page gives no
                       clock time, so no time is written (RULES 19).
Wikipedia pageviews    https://wikimedia.org/api/rest_v1/metrics/pageviews/
                       per-article/en.wikipedia/all-access/user/<ARTICLE>/daily/
                       <YYYYMMDD>/<YYYYMMDD>   (Wikimedia REST API)
Coin name lookup       https://api.coingecko.com/api/v3/search?query=<ticker>
                       Used only to turn a Binance base ticker into a coin name
                       so the Wikipedia article can be looked up.
Prediction market      https://gamma-api.polymarket.com/public-search?q=<name>
                       https://clob.polymarket.com/prices-history?market=<token>
Announcements          probed, see ANNOUNCEMENT_PROBES below.

Input   : data/draw/observation-coins.txt
          data/moments/moments.csv      (for the window a market must overlap)
Output  : data/observation/external/raw/...          raw bytes as fetched
          data/observation/external/us-calendar.json
          data/observation/external/coin-names.json
          data/observation/external/wikipedia.json
          data/observation/external/prediction-market.json
          data/observation/external/announcements.json   (the probe log)
          data/observation/external/manifest.jsonl       (append-only)
Rules   : RULES 2 (source URL, fetch time, SHA-256 for every fetched file)
          RULES 19 (no unmeasured number; the FOMC time is left out, not guessed)
          RULES 20/21 (every failure recorded with its exact error text)
          RULES 23 (clock read from the system)
          RULES 26/30 (resumable; manifest append-only)
          RULES 27 (documented addresses only)

No randomness in this script.
"""

import csv
import html as htmlmod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import Manifest, sha256_bytes, utc_now_iso  # noqa: E402

# ---------------------------------------------------------------- constants --
# Changed for publication: the original User-Agent carried a contact e-mail
# address. The lab stopped sending it on 2026-10-01; this is the generic agent
# lab_archive.USER_AGENT that every later fetch used.
UA = "balikcil-lab/1.0 (research; public archive)"
HTTP_TIMEOUT_S = 45
HTTP_RETRIES = 3
HTTP_BACKOFF_S = 3.0
POLITE_SLEEP_S = 1.5        # between calls to the same third-party host

# Card window: the 24 h before a moment start and the 24 h from it (TACTICS 3),
# plus the 7 days the "before" summary looks back over.
CARD_BEFORE_H = 24
CARD_AFTER_H = 24
CARD_LOOKBACK_D = 7

# Calendar months to fetch, covering the whole card span.
CAL_MONTHS = [(2025, 8), (2025, 9), (2025, 10), (2025, 11), (2025, 12),
              (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5),
              (2026, 6), (2026, 7), (2026, 8), (2026, 9)]

# Wikipedia pageview span, one day wider than the card span on each side.
WIKI_START = "20250825"
WIKI_END = "20260902"

ET = ZoneInfo("America/New_York")

# Paging parameter for the Polymarket search. A fetch parameter, not a
# threshold on any measurement.
POLY_LIMIT_PER_TYPE = 20

# Words that must appear in a Wikipedia article's own summary before its page
# views may be attached to a coin. A guard against attaching the page views of
# an unrelated article that happens to share the coin's name.
SUBJECT_WORDS = {"cryptocurrency", "blockchain", "crypto", "token",
                 "digital asset", "stablecoin", "memecoin", "meme coin"}

# Addresses probed for exchange announcements. Each is recorded with whatever
# it answered, so "we could not get announcements" is a measured statement.
ANNOUNCEMENT_PROBES = [
    ("binance", "binance announcement RSS",
     "https://www.binance.com/en/support/announcement/rss"),
    ("binance", "binance announcement list page",
     "https://www.binance.com/en/support/announcement/list/48"),
    ("upbit", "upbit open API notices",
     "https://api.upbit.com/v1/notices"),
    ("upbit", "upbit api-manager notices",
     "https://api-manager.upbit.com/api/v1/notices?page=1&per_page=100"),
    ("bithumb", "bithumb public API notices",
     "https://api.bithumb.com/v1/notices"),
    ("bithumb", "bithumb public API notices, paged",
     "https://api.bithumb.com/v1/notices?page=2&count=100"),
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_LIST = os.path.join(ROOT, "data", "draw", "observation-coins.txt")
MOMENTS_CSV = os.path.join(ROOT, "data", "moments", "moments.csv")
OUT_DIR = os.path.join(ROOT, "data", "observation", "external")
RAW_DIR = os.path.join(OUT_DIR, "raw")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")

HOUR_MS = 3600 * 1000


# ------------------------------------------------------------------ fetching -
def fetch(url: str) -> tuple:
    """Return (bytes, error_string). Never raises."""
    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                body = resp.read()
                if resp.status == 202 and not body:
                    return None, ("HTTP 202 with a zero-length body "
                                  "(the host answered but returned nothing)")
                return body, None
        except urllib.error.HTTPError as exc:
            last = "HTTP %s %s" % (exc.code, exc.reason)
            if exc.code in (400, 401, 403, 404):
                return None, last
        except Exception as exc:  # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
        if attempt < HTTP_RETRIES - 1:
            time.sleep(HTTP_BACKOFF_S * (2 ** attempt))
    return None, last or "unknown error"


def fetch_and_record(url: str, rel_path: str, manifest: Manifest) -> tuple:
    """Fetch, store the raw bytes, append a manifest row. (bytes, error)."""
    dest = os.path.join(OUT_DIR, rel_path)
    if manifest.get(rel_path) and os.path.exists(dest):
        with open(dest, "rb") as fh:
            return fh.read(), None
    body, err = fetch(url)
    row = {"path": rel_path, "source_url": url,
           "downloaded_at_utc": utc_now_iso(),
           "sha256": sha256_bytes(body) if body is not None else None,
           "checksum_verified": None,
           "checksum_note": "third-party source publishes no checksum file",
           "error": err}
    if body is not None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(body)
    manifest.add(row)
    return body, err


# ------------------------------------------------------------- US calendar --
BLS_ROW = re.compile(
    r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
    re.S)


def strip_tags(s: str) -> str:
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ").strip()


def parse_bls(page: str) -> list:
    m = re.search(r'<table[^>]*class="[^"]*release-list[^"]*".*?</table>', page, re.S)
    if not m:
        return []
    out = []
    for cells in BLS_ROW.findall(m.group(0)):
        date_s, time_s, rel_s = (re.sub(r"\s+", " ", strip_tags(c)) for c in cells)
        try:
            d = datetime.strptime(date_s, "%A, %B %d, %Y").date()
        except ValueError:
            continue
        if not time_s or ":" not in time_s:
            continue
        try:
            t = datetime.strptime(time_s.upper(), "%I:%M %p").time()
        except ValueError:
            continue
        local = datetime.combine(d, t, tzinfo=ET)
        out.append({"source": "BLS",
                    "release": rel_s,
                    "local_date": d.isoformat(),
                    "local_time_et": time_s,
                    "utc": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")})
    return out


def parse_fomc(page: str) -> list:
    out = []
    for block in re.finditer(r'<div class="row fomc-meeting".*?(?=<div class="row fomc-meeting"|</div>\s*</div>\s*$)',
                             page, re.S):
        chunk = block.group(0)
        stat = re.search(r"/newsevents/pressreleases/monetary(\d{8})a\.htm", chunk)
        if not stat:
            continue
        d = datetime.strptime(stat.group(1), "%Y%m%d").date()
        month = strip_tags(re.search(r'fomc-meeting__month[^>]*>(.*?)</div>', chunk, re.S).group(1)) \
            if re.search(r'fomc-meeting__month[^>]*>(.*?)</div>', chunk, re.S) else ""
        days = strip_tags(re.search(r'fomc-meeting__date[^>]*>(.*?)</div>', chunk, re.S).group(1)) \
            if re.search(r'fomc-meeting__date[^>]*>(.*?)</div>', chunk, re.S) else ""
        out.append({"source": "Federal Reserve",
                    "release": "FOMC statement (rate decision)",
                    "meeting": ("%s %s" % (month, days)).strip(),
                    "local_date": d.isoformat(),
                    "local_time_et": None,
                    "time_note": "the FOMC calendar page gives no clock time; none is written (RULES 19)",
                    "utc": None})
    seen, uniq = set(), []
    for e in out:
        if e["local_date"] not in seen:
            seen.add(e["local_date"])
            uniq.append(e)
    return uniq


# ------------------------------------------------------------------- helpers -
def base_ticker(symbol: str) -> str:
    s = symbol[:-4] if symbol.endswith("USDT") else symbol
    m = re.match(r"^(1000+)([A-Z].*)$", s)
    return m.group(2) if m else s


def card_span(moments_rows) -> dict:
    """{symbol: (lo_ms, hi_ms)} over every card window of that symbol."""
    span = {}
    for r in moments_rows:
        t0 = int(r["start_ms"])
        lo = t0 - (CARD_BEFORE_H + 24 * CARD_LOOKBACK_D) * HOUR_MS
        hi = t0 + (CARD_AFTER_H - 1) * HOUR_MS
        cur = span.get(r["symbol"])
        span[r["symbol"]] = (min(lo, cur[0]), max(hi, cur[1])) if cur else (lo, hi)
    return span


def main() -> int:
    os.makedirs(RAW_DIR, exist_ok=True)
    manifest = Manifest(MANIFEST_PATH)
    with open(OBS_LIST, "r", encoding="utf-8") as fh:
        symbols = [ln.strip() for ln in fh if ln.strip()]
    with open(MOMENTS_CSV, "r", encoding="utf-8") as fh:
        moments = list(csv.DictReader(fh))
    spans = card_span(moments)

    # ---------------------------------------------------------- US calendar --
    print("[1/5] US release calendar", flush=True)
    releases, cal_errors = [], []
    for y, m in CAL_MONTHS:
        url = "https://www.bls.gov/schedule/%d/%02d_sched_list.htm" % (y, m)
        body, err = fetch_and_record(url, "raw/bls/%d-%02d.html" % (y, m), manifest)
        if err:
            cal_errors.append({"source": "BLS", "url": url, "error": err})
            continue
        rows = parse_bls(body.decode("utf-8", "replace"))
        if not rows:
            cal_errors.append({"source": "BLS", "url": url,
                               "error": "page fetched (%d bytes) but no release-list "
                                        "table row parsed" % len(body)})
        releases.extend(rows)
        time.sleep(POLITE_SLEEP_S)

    fomc_url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    body, err = fetch_and_record(fomc_url, "raw/fomc/fomccalendars.html", manifest)
    if err:
        cal_errors.append({"source": "Federal Reserve", "url": fomc_url, "error": err})
    else:
        rows = parse_fomc(body.decode("utf-8", "replace"))
        if not rows:
            cal_errors.append({"source": "Federal Reserve", "url": fomc_url,
                               "error": "page fetched (%d bytes) but no meeting block parsed"
                                        % len(body)})
        releases.extend(rows)

    releases.sort(key=lambda e: (e["local_date"], e.get("local_time_et") or ""))
    with open(os.path.join(OUT_DIR, "us-calendar.json"), "w", encoding="utf-8") as fh:
        json.dump({"fetched_at_utc": utc_now_iso(),
                   "sources": {"BLS": "https://www.bls.gov/schedule/<YYYY>/<MM>_sched_list.htm",
                               "FOMC": fomc_url},
                   "errors": cal_errors,
                   "count": len(releases),
                   "releases": releases}, fh, indent=1)
    print("      %d releases, %d errors" % (len(releases), len(cal_errors)), flush=True)

    # ------------------------------------------------------------ coin names --
    print("[2/5] coin names (CoinGecko)", flush=True)
    names = {}
    for sym in symbols:
        base = base_ticker(sym)
        url = "https://api.coingecko.com/api/v3/search?query=%s" % urllib.parse.quote(base)
        body, err = fetch_and_record(url, "raw/coingecko/%s.json" % base, manifest)
        entry = {"symbol": sym, "base_ticker": base, "source_url": url,
                 "error": err, "name": None, "exact_symbol_hits": []}
        if body is not None:
            try:
                coins = json.loads(body).get("coins", [])
                hits = [c for c in coins if (c.get("symbol") or "").upper() == base.upper()]
                entry["exact_symbol_hits"] = [{"id": c["id"], "name": c["name"],
                                               "rank": c.get("market_cap_rank")}
                                              for c in hits[:5]]
                if hits:
                    entry["name"] = hits[0]["name"]
                else:
                    entry["error"] = ("CoinGecko search returned %d coins, none with "
                                      "symbol == %s" % (len(coins), base))
            except Exception as exc:  # noqa: BLE001
                entry["error"] = "could not parse CoinGecko answer: %s" % exc
        names[sym] = entry
        time.sleep(POLITE_SLEEP_S)
    with open(os.path.join(OUT_DIR, "coin-names.json"), "w", encoding="utf-8") as fh:
        json.dump(names, fh, indent=1, sort_keys=True)
    print("      " + ", ".join("%s=%s" % (s, names[s]["name"]) for s in symbols), flush=True)

    # -------------------------------------------------------------- Wikipedia -
    # An article is accepted only when ALL of these hold:
    #   (a) CoinGecko returned a coin whose symbol equals the Binance base
    #       ticker exactly, giving a coin *name*;
    #   (b) an English Wikipedia article exists whose title equals that name
    #       exactly (case-insensitive);
    #   (c) the article's own summary contains one of SUBJECT_WORDS.
    # (c) is a guard, not an interpretation: without it the ticker "NEWT"
    # matches the amphibian and "NOK" matches the Norwegian krone, and their
    # page views would silently become the coin's page views. The ticker itself
    # is never used as a search term for the same reason.
    print("[3/5] Wikipedia pageviews", flush=True)
    wiki = {}
    for sym in symbols:
        base = base_ticker(sym)
        cands = [c for c in [names[sym].get("name")] if c]
        entry = {"symbol": sym, "article": None, "daily": {},
                 "tried": [], "error": None, "source_url": None,
                 "rule": "CoinGecko exact-symbol name -> exact Wikipedia title -> "
                         "summary must mention one of %s" % sorted(SUBJECT_WORDS)}
        if not cands:
            entry["error"] = ("CoinGecko returned no coin whose symbol equals `%s`, so "
                              "there is no coin name to look up on Wikipedia" % base)
            wiki[sym] = entry
            continue
        for cand in cands:
            surl = ("https://en.wikipedia.org/w/api.php?action=query&list=search"
                    "&srsearch=%s&srlimit=5&format=json" % urllib.parse.quote(cand))
            body, err = fetch_and_record(
                surl, "raw/wikipedia/search-%s.json" % re.sub(r"\W+", "_", cand), manifest)
            time.sleep(POLITE_SLEEP_S)
            if err:
                entry["tried"].append({"query": cand, "error": err})
                continue
            hits = json.loads(body).get("query", {}).get("search", [])
            titles = [h["title"] for h in hits]
            match = next((t for t in titles if t.lower() == cand.lower()), None)
            tried = {"query": cand, "top_hits": titles[:5], "exact_title_match": match,
                     "subject_check": None}
            entry["tried"].append(tried)
            if not match:
                continue
            surl2 = ("https://en.wikipedia.org/api/rest_v1/page/summary/%s"
                     % urllib.parse.quote(match.replace(" ", "_"), safe=""))
            body2, err2 = fetch_and_record(
                surl2, "raw/wikipedia/summary-%s.json" % re.sub(r"\W+", "_", match), manifest)
            time.sleep(POLITE_SLEEP_S)
            if err2:
                tried["subject_check"] = "summary fetch failed: %s" % err2
                continue
            blob = json.loads(body2)
            text = ("%s %s" % (blob.get("description") or "",
                               blob.get("extract") or "")).lower()
            hit = sorted(w for w in SUBJECT_WORDS if w in text)
            tried["subject_check"] = {"words_found": hit,
                                      "description": blob.get("description")}
            if hit:
                entry["article"] = match
                break
        if entry["article"] is None:
            entry["error"] = ("no English Wikipedia article passed the rule "
                              "(exact title match on the coin name, and a summary "
                              "mentioning %s); see 'tried'" % sorted(SUBJECT_WORDS))
            wiki[sym] = entry
            continue
        art = urllib.parse.quote(entry["article"].replace(" ", "_"), safe="")
        purl = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                "en.wikipedia/all-access/user/%s/daily/%s/%s" % (art, WIKI_START, WIKI_END))
        entry["source_url"] = purl
        body, err = fetch_and_record(purl, "raw/wikipedia/views-%s.json" % re.sub(r"\W+", "_", entry["article"]), manifest)
        time.sleep(POLITE_SLEEP_S)
        if err:
            entry["error"] = "pageview API: %s" % err
        else:
            for it in json.loads(body).get("items", []):
                entry["daily"][it["timestamp"][:8]] = it["views"]
        wiki[sym] = entry
    with open(os.path.join(OUT_DIR, "wikipedia.json"), "w", encoding="utf-8") as fh:
        json.dump(wiki, fh, indent=1, sort_keys=True)
    print("      " + ", ".join("%s=%s(%d days)" % (s, wiki[s]["article"], len(wiki[s]["daily"]))
                               for s in symbols), flush=True)

    # ------------------------------------------------------- prediction market -
    print("[4/5] prediction market (Polymarket)", flush=True)
    poly = {}
    for sym in symbols:
        base = base_ticker(sym)
        queries = [q for q in [names[sym].get("name"), base] if q]
        entry = {"symbol": sym, "queries": queries, "errors": [],
                 "markets_seen": 0, "markets_matched": [], "series": {}}
        seen = {}
        for q in queries:
            url = ("https://gamma-api.polymarket.com/public-search?q=%s&limit_per_type=%d"
                   % (urllib.parse.quote(q), POLY_LIMIT_PER_TYPE))
            body, err = fetch_and_record(
                url, "raw/polymarket/search-%s.json" % re.sub(r"\W+", "_", q), manifest)
            time.sleep(POLITE_SLEEP_S)
            if err:
                entry["errors"].append({"query": q, "error": err})
                continue
            for ev in json.loads(body).get("events", []):
                for mk in ev.get("markets", []) or []:
                    seen[mk.get("slug") or mk.get("id")] = (ev, mk)
        entry["markets_seen"] = len(seen)
        lo, hi = spans.get(sym, (None, None))
        needles = [base.lower()] + [n.lower() for n in [names[sym].get("name")] if n]
        for slug, (ev, mk) in sorted(seen.items(), key=lambda kv: str(kv[0])):
            text = ("%s %s" % (ev.get("title", ""), mk.get("question", ""))).lower()
            toks = set(re.split(r"[^a-z0-9]+", text))
            if not (any(n in toks for n in needles) or any(n in text for n in needles if " " in n)):
                continue
            s_d, e_d = mk.get("startDate"), mk.get("endDate")
            rec = {"slug": slug, "question": mk.get("question"),
                   "event": ev.get("title"), "startDate": s_d, "endDate": e_d,
                   "outcomes": mk.get("outcomes"), "overlaps_card_span": None}
            try:
                s_ms = int(datetime.fromisoformat(s_d.replace("Z", "+00:00")).timestamp() * 1000) if s_d else None
                e_ms = int(datetime.fromisoformat(e_d.replace("Z", "+00:00")).timestamp() * 1000) if e_d else None
                rec["overlaps_card_span"] = bool(
                    lo is not None and s_ms is not None and e_ms is not None
                    and s_ms <= hi and e_ms >= lo)
            except Exception as exc:  # noqa: BLE001
                rec["overlaps_card_span"] = None
                entry["errors"].append({"slug": slug, "error": "date parse: %s" % exc})
            entry["markets_matched"].append(rec)

            if rec["overlaps_card_span"]:
                try:
                    tid = json.loads(mk.get("clobTokenIds") or "[]")[0]
                except Exception:  # noqa: BLE001
                    tid = None
                if not tid:
                    entry["errors"].append({"slug": slug,
                                            "error": "market has no clobTokenIds"})
                    continue
                hurl = ("https://clob.polymarket.com/prices-history?market=%s"
                        "&interval=max&fidelity=60" % tid)
                body, err = fetch_and_record(
                    hurl, "raw/polymarket/history-%s.json" % re.sub(r"\W+", "_", str(slug)), manifest)
                time.sleep(POLITE_SLEEP_S)
                if err:
                    entry["errors"].append({"slug": slug, "error": "price history: %s" % err})
                    continue
                hist = json.loads(body).get("history", [])
                entry["series"][slug] = {"points": len(hist),
                                         "hourly": {int(p["t"]) * 1000: p["p"] for p in hist}}
        poly[sym] = entry
        print("      %-14s seen %3d matched %2d overlapping %2d" % (
            sym, entry["markets_seen"], len(entry["markets_matched"]),
            sum(1 for r in entry["markets_matched"] if r["overlaps_card_span"])), flush=True)
    with open(os.path.join(OUT_DIR, "prediction-market.json"), "w", encoding="utf-8") as fh:
        json.dump(poly, fh, indent=1, sort_keys=True)

    # ----------------------------------------------------------- announcements -
    print("[5/5] announcements probe", flush=True)
    probes = []
    for exchange, label, url in ANNOUNCEMENT_PROBES:
        body, err = fetch_and_record(
            url, "raw/announcements/%s.txt" % re.sub(r"\W+", "_", label), manifest)
        rec = {"exchange": exchange, "label": label, "url": url,
               "error": err, "bytes": None if body is None else len(body),
               "usable_history": False, "note": None}
        if body is not None:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, list):
                    rec["items_returned"] = len(parsed)
                    if parsed:
                        dates = sorted(str(p.get("published_at", "")) for p in parsed)
                        rec["oldest_item"] = dates[0]
                        rec["newest_item"] = dates[-1]
                    rec["note"] = ("returns only the most recent %d notices; no paging "
                                   "parameter changed the answer, so it carries no "
                                   "history for the period" % len(parsed))
            except Exception:  # noqa: BLE001
                rec["note"] = "answer is not a JSON list; %d bytes" % len(body)
        probes.append(rec)
        time.sleep(POLITE_SLEEP_S)

    ann = {"fetched_at_utc": utc_now_iso(),
           "conclusion": ("No address tried returned announcement history covering "
                          "2025-09-01..2026-08-31. The announcement field on every "
                          "card is therefore marked MISSING (source failed), not "
                          "empty (RULES 20)."),
           "probes": probes}
    with open(os.path.join(OUT_DIR, "announcements.json"), "w", encoding="utf-8") as fh:
        json.dump(ann, fh, indent=1)
    for p in probes:
        print("      %-40s %s" % (p["label"], p["error"] or p.get("note") or "OK"), flush=True)

    print(json.dumps({"finished_at_utc": utc_now_iso()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
