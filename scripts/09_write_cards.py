#!/usr/bin/env python3
"""
09_write_cards.py -- write one card per moment (TACTICS 3).

What it does
------------
For every moment in data/moments/moments.csv it writes cards/C###.md with two
sections:

  Before : the 24 hours ending at the start hour, hour by hour, plus a one-line
           summary of the 7 days before that.
  After  : the 24 hours from the start hour, hour by hour. This section also
           carries the moment's kind (large / calm) and its measured 24-hour
           move, because both are facts about the after window and must not sit
           where a reader of the before section can see them.

Fields on the card, from TACTICS 3, where the data exists:
  price, volume, trade count, taker buy pressure            (hourly klines)
  open interest, long/short ratios                          (5-minute metrics)
  funding rate, payment interval and its changes            (fundingRate)
  order book depth                                          (bookDepth, +-1%)
  bitcoin and ethereum over the same hours                  (hourly klines)
  US release calendar                                       (BLS + FOMC)
  Wikipedia daily page views                                (Wikimedia REST)
  prediction market price                                   (Polymarket)
  Binance and Korean exchange announcements                 (see below)

The wall between the two sections
---------------------------------
Every value that goes into the before section passes through TimeGuard.before(),
which refuses any timestamp whose hour does not end at or before the start hour.
Every value in the after section passes through TimeGuard.after(). The script
also checks, per card, that max(before timestamp) < min(after timestamp) and
that the two timestamp sets do not intersect. A violation stops the script; the
counts are written into cards/INDEX.md.

Missing vs empty (RULES 20)
---------------------------
  MISSING  - the source was never fetched, or it answered with an error. The
             reason is printed next to the word.
  none     - the source was fetched and holds nothing for these hours.
  .        - inside a table: the source covers this coin but published no value
             for that hour.
Every card ends with a "Fields not on this card" block naming each absent field
and the reason. cards/INDEX.md collects all of them.

Card numbering
--------------
Moments are sorted by (symbol, start hour, kind) - the order of
data/moments/moments.csv, which is itself fingerprinted. The card number is the
1-based position in that order, C001 .. C###. The same moments.csv therefore
always produces the same card numbers. Each card also carries the SHA-256 of
its own text in INDEX.md, and the script refuses to overwrite an existing card
file whose content differs (RULES 30).

Input   : data/moments/moments.csv
          data/observation/klines_1h/, metrics/, bookDepth/, fundingRate/
          data/observation/external/*.json
Output  : cards/C###.md
          cards/INDEX.md
          data/observation/derived/metrics-hourly/<SYM>.json   (cache)
          data/observation/derived/bookdepth-hourly/<SYM>.json (cache)
Rules   : RULES 19, 20, 21, 23, 29, 30
No randomness in this script.
"""

import csv
import io
import json
import os
import statistics
import sys
import zipfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import sha256_file, utc_now_iso  # noqa: E402

# ---------------------------------------------------------------- constants --
HOUR_MS = 3600 * 1000
BEFORE_H = 24          # TACTICS 3
AFTER_H = 24           # TACTICS 3
LOOKBACK_D = 7         # TACTICS 3, the one-line summary
DEPTH_LEVEL = 1.00     # order book depth level shown, +-1% from mid
REFERENCE = ["BTCUSDT", "ETHUSDT"]   # TACTICS 3: bitcoin and ethereum

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS_CSV = os.path.join(ROOT, "data", "moments", "moments.csv")
OBS = os.path.join(ROOT, "data", "observation")
DERIVED = os.path.join(OBS, "derived")
EXT = os.path.join(OBS, "external")
CARDS = os.path.join(ROOT, "cards")


# ------------------------------------------------------------------ loading --
def read_zip_csv(path):
    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            text = z.read(member).decode("utf-8", "replace")
            for row in csv.reader(io.StringIO(text)):
                if row:
                    yield row


def load_klines(symbol):
    out = {}
    d = os.path.join(OBS, "klines_1h", symbol)
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if name.endswith(".zip"):
            for row in read_zip_csv(os.path.join(d, name)):
                if row[0] == "open_time":
                    continue
                qv = float(row[7])
                tbqv = float(row[10])
                out[int(row[0])] = {
                    "close": float(row[4]), "qvol": qv, "count": int(row[8]),
                    "taker_buy_pct": (100.0 * tbqv / qv) if qv > 0 else None,
                }
    return out


def _f(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_metrics_hourly(symbol):
    """{hour_ms: {...}} from the 5-minute metrics files. Cached."""
    cache = os.path.join(DERIVED, "metrics-hourly", "%s.json" % symbol)
    d = os.path.join(OBS, "metrics", symbol)
    files = sorted(f for f in os.listdir(d)) if os.path.isdir(d) else []
    if os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as fh:
            c = json.load(fh)
        if c.get("files") == files:
            return {int(k): v for k, v in c["hours"].items()}
    buckets = {}
    for name in files:
        if not name.endswith(".zip"):
            continue
        for row in read_zip_csv(os.path.join(d, name)):
            if row[0] == "create_time":
                continue
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            h = int(ts.timestamp() // 3600 * 3600 * 1000)
            b = buckets.setdefault(h, {"oi": None, "oi_value": None, "ls_acct": None,
                                       "top_ls_acct": None, "top_ls_pos": None,
                                       "taker_ls": [], "n": 0})
            b["n"] += 1
            for key, idx in (("oi", 2), ("oi_value", 3), ("top_ls_acct", 4),
                             ("top_ls_pos", 5), ("ls_acct", 6)):
                v = _f(row[idx])
                if v is not None:
                    b[key] = v                       # last sample of the hour
            v = _f(row[7])
            if v is not None:
                b["taker_ls"].append(v)
    hours = {}
    for h, b in buckets.items():
        hours[h] = {"oi": b["oi"], "oi_value": b["oi_value"], "ls_acct": b["ls_acct"],
                    "top_ls_acct": b["top_ls_acct"], "top_ls_pos": b["top_ls_pos"],
                    "taker_ls": (statistics.fmean(b["taker_ls"]) if b["taker_ls"] else None),
                    "samples": b["n"]}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"files": files, "hours": {str(k): v for k, v in hours.items()}}, fh)
    return hours


def load_bookdepth_hourly(symbol):
    """{hour_ms: {bid1, ask1, samples}} - median notional at -1% / +1%. Cached."""
    cache = os.path.join(DERIVED, "bookdepth-hourly", "%s.json" % symbol)
    d = os.path.join(OBS, "bookDepth", symbol)
    files = sorted(f for f in os.listdir(d)) if os.path.isdir(d) else []
    if os.path.exists(cache):
        with open(cache, "r", encoding="utf-8") as fh:
            c = json.load(fh)
        if c.get("files") == files:
            return {int(k): v for k, v in c["hours"].items()}
    buckets = {}
    for name in files:
        if not name.endswith(".zip"):
            continue
        for row in read_zip_csv(os.path.join(d, name)):
            if row[0] == "timestamp":
                continue
            pct = _f(row[1])
            if pct is None or abs(abs(pct) - DEPTH_LEVEL) > 1e-9:
                continue
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            h = int(ts.timestamp() // 3600 * 3600 * 1000)
            b = buckets.setdefault(h, {"bid": [], "ask": []})
            b["ask" if pct > 0 else "bid"].append(_f(row[3]) or 0.0)
    hours = {}
    for h, b in buckets.items():
        hours[h] = {"bid1": statistics.median(b["bid"]) if b["bid"] else None,
                    "ask1": statistics.median(b["ask"]) if b["ask"] else None,
                    "samples": len(b["bid"]) + len(b["ask"])}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"files": files, "hours": {str(k): v for k, v in hours.items()}}, fh)
    return hours


def load_funding(symbol):
    out = []
    d = os.path.join(OBS, "fundingRate", symbol)
    if not os.path.isdir(d):
        return out
    for name in sorted(os.listdir(d)):
        if name.endswith(".zip"):
            for row in read_zip_csv(os.path.join(d, name)):
                if row[0] == "calc_time":
                    continue
                out.append({"t": int(row[0]), "interval_h": int(float(row[1])),
                            "rate": float(row[2])})
    out.sort(key=lambda r: r["t"])
    return out


# ---------------------------------------------------------------- formatting -
def human(x, nd=2):
    if x is None:
        return "."
    a = abs(x)
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= lim:
            return "%.*f%s" % (nd, x / lim, suf)
    if a >= 1:
        return "%.*f" % (nd, x)
    return "%.4g" % x


def px(x):
    if x is None:
        return "."
    return "%.6g" % x


def pct(x, nd=2):
    return "." if x is None else "%+.*f" % (nd, x)


def num(x, nd=2):
    return "." if x is None else "%.*f" % (nd, x)


def hhmm(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def day_of(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y%m%d")


# --------------------------------------------------------------- time guard --
class TimeGuard:
    """Refuses to let a value cross between the two sections of a card."""

    def __init__(self, t0):
        self.t0 = t0
        self.before_ts = []
        self.after_ts = []
        self.violations = []

    def before(self, ts, what):
        """ts is the opening instant of an hour (or an event instant)."""
        if ts is None:
            return None
        if ts >= self.t0:
            self.violations.append("before-section value from %s at %s >= start %s"
                                   % (what, hhmm(ts), hhmm(self.t0)))
        else:
            self.before_ts.append(ts)
        return ts

    def before_hour(self, h, what):
        """An hourly bar belongs to the before section only if it ends by t0."""
        if h is None:
            return None
        if h + HOUR_MS > self.t0:
            self.violations.append("before-section hour from %s starting %s ends after %s"
                                   % (what, hhmm(h), hhmm(self.t0)))
        else:
            self.before_ts.append(h)
        return h

    def after(self, ts, what):
        if ts is None:
            return None
        if ts < self.t0 or ts >= self.t0 + AFTER_H * HOUR_MS:
            self.violations.append("after-section value from %s at %s outside [%s, +24h)"
                                   % (what, hhmm(ts), hhmm(self.t0)))
        else:
            self.after_ts.append(ts)
        return ts

    def check(self):
        if self.before_ts and self.after_ts:
            if max(self.before_ts) >= min(self.after_ts):
                self.violations.append("before max %s >= after min %s"
                                       % (hhmm(max(self.before_ts)), hhmm(min(self.after_ts))))
            if set(self.before_ts) & set(self.after_ts):
                self.violations.append("timestamp present in both sections")
        return self.violations


# ------------------------------------------------------------- card sections -
HEADER = ("| h | close | chg% | quote vol | trades | taker buy% | open int | "
          "L/S acct | top L/S pos | taker L/S | depth -1% | depth +1% | BTC | ETH |")
SEP = "|" + "---|" * 14


def hour_rows(hours, rel0, bars, met, bd, refbars, guard, sect, what):
    """One row per hour. `chg%` is measured against the hour before the row,
    which for the first row of a table is the hour just outside it; that hour is
    always *earlier* than the row, so the before section never reaches forward."""
    rows = []
    for i, h in enumerate(hours):
        (guard.before_hour if sect == "before" else guard.after)(h, what)
        b = bars.get(h)
        m = met.get(h) or {}
        d = bd.get(h) or {}
        prevb = bars.get(h - HOUR_MS)
        chg = None
        if b and prevb and prevb["close"] > 0:
            chg = 100.0 * (b["close"] / prevb["close"] - 1.0)
        ref = []
        for r in REFERENCE:
            rb, rp = refbars.get(r, {}).get(h), refbars.get(r, {}).get(h - HOUR_MS)
            ref.append(100.0 * (rb["close"] / rp["close"] - 1.0) if rb and rp and rp["close"] else None)
        rows.append("| %+d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            rel0 + i,
            px(b["close"]) if b else ".",
            pct(chg),
            human(b["qvol"]) if b else ".",
            human(float(b["count"]), 0) if b else ".",
            num(b["taker_buy_pct"], 1) if b else ".",
            human(m.get("oi")),
            num(m.get("ls_acct")),
            num(m.get("top_ls_pos")),
            num(m.get("taker_ls")),
            human(d.get("bid1")),
            human(d.get("ask1")),
            pct(ref[0]), pct(ref[1])))
    return rows


def funding_line(funding, lo, hi, guard, sect, absent):
    if not funding:
        absent.append(("funding rate", "MISSING - no fundingRate file for this coin "
                                       "in the archive for these months"))
        return "- **Funding:** MISSING - no fundingRate file in the archive for this coin."
    pays = [f for f in funding if lo <= f["t"] < hi]
    for f in pays:
        (guard.before if sect == "before" else guard.after)(f["t"], "funding")
    if not pays:
        return "- **Funding:** none - no payment fell in these 24 hours."
    ivs = sorted({f["interval_h"] for f in pays})
    prev_iv = [f["interval_h"] for f in funding if f["t"] < lo]
    changed = "yes" if (len(ivs) > 1 or (prev_iv and prev_iv[-1] != ivs[0])) else "no"
    rates = " ".join("%+.4f%%" % (f["rate"] * 100) for f in pays)
    return ("- **Funding:** %d payment(s), rate %s · interval %s h · interval changed: %s"
            % (len(pays), rates, "/".join(str(i) for i in ivs), changed))


def releases_line(cal, lo, hi, guard, sect, absent):
    if cal is None:
        absent.append(("US release calendar", "MISSING - calendar file was not written"))
        return "- **US releases:** MISSING - calendar file was not written."
    hits, undated = [], []
    for e in cal["releases"]:
        if e.get("utc"):
            t = int(datetime.strptime(e["utc"], "%Y-%m-%dT%H:%MZ")
                    .replace(tzinfo=timezone.utc).timestamp() * 1000)
            if lo <= t < hi:
                (guard.before if sect == "before" else guard.after)(t, "release")
                hits.append("%s (%+d h)" % (e["release"], (t - lo) // HOUR_MS - (BEFORE_H if sect == "before" else 0)))
        else:
            d0 = int(datetime.strptime(e["local_date"], "%Y-%m-%d")
                     .replace(tzinfo=timezone.utc).timestamp() * 1000)
            if lo <= d0 < hi or lo <= d0 + 24 * HOUR_MS - 1 < hi:
                undated.append("%s on %s (the calendar publishes no clock time)"
                               % (e["release"], e["local_date"]))
    parts = hits + undated
    return "- **US releases:** " + ("; ".join(parts) if parts else "none in these hours.")


def wiki_line(w, t0, sect, absent):
    if w is None:
        absent.append(("Wikipedia page views", "MISSING - wikipedia.json was not written"))
        return "- **Wikipedia page views:** MISSING - wikipedia.json was not written."
    if w.get("error") or not w.get("daily"):
        reason = w.get("error") or "no daily values returned"
        if sect == "before":
            absent.append(("Wikipedia page views", "MISSING - %s" % reason))
        return "- **Wikipedia page views:** MISSING - %s" % reason
    end = datetime.fromtimestamp(t0 / 1000, timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)
    if sect == "before":
        days = [(end - timedelta(days=k)).strftime("%Y%m%d") for k in range(7, 0, -1)]
    else:
        days = [(end + timedelta(days=k)).strftime("%Y%m%d") for k in range(0, 2)]
    vals = [(d, w["daily"].get(d)) for d in days]
    if all(v is None for _d, v in vals):
        return "- **Wikipedia page views** (`%s`): none - the API returned no value for these days." % w["article"]
    txt = " ".join(human(float(v), 1) if v is not None else "." for _d, v in vals)
    label = "7 full days before" if sect == "before" else "the start day and the day after"
    return "- **Wikipedia page views** (`%s`, daily, %s): %s" % (w["article"], label, txt)


def market_line(p, lo, hi, guard, sect, absent):
    if p is None:
        absent.append(("prediction market price", "MISSING - prediction-market.json was not written"))
        return "- **Prediction market:** MISSING - prediction-market.json was not written."
    if p.get("errors") and not p.get("markets_matched"):
        if sect == "before":
            absent.append(("prediction market price", "MISSING - Polymarket search failed"))
        return ("- **Prediction market:** MISSING - search failed: %s"
                % p["errors"][0].get("error"))
    lines = []
    for slug, s in (p.get("series") or {}).items():
        pts = {int(k): v for k, v in s["hourly"].items() if lo <= int(k) < hi}
        for t in pts:
            (guard.before if sect == "before" else guard.after)(t, "prediction market")
        if pts:
            first, last = min(pts), max(pts)
            lines.append("`%s` %.2f -> %.2f" % (slug, pts[first], pts[last]))
    if lines:
        return "- **Prediction market:** " + "; ".join(lines)
    n_match = len(p.get("markets_matched") or [])
    n_over = sum(1 for r in (p.get("markets_matched") or []) if r.get("overlaps_card_span"))
    if sect == "before":
        absent.append(("prediction market price",
                       "empty - Polymarket was reached and searched; no market mentioning "
                       "this coin had a price point in these hours"))
    return ("- **Prediction market:** none - Polymarket search over %s returned %d markets, "
            "%d mentioning this coin, %d overlapping this coin's card span, none with a "
            "price point in these hours."
            % (", ".join("`%s`" % q for q in p.get("queries", [])),
               p.get("markets_seen", 0), n_match, n_over))


def seven_day_line(bars, t0, guard, absent):
    lo = t0 - (BEFORE_H + 24 * LOOKBACK_D) * HOUR_MS
    hi = t0 - BEFORE_H * HOUR_MS
    hs = [h for h in range(lo, hi, HOUR_MS) if h in bars]
    for h in hs:
        guard.before_hour(h, "7-day summary")
    if len(hs) < 24:
        absent.append(("previous 7 days summary",
                       "MISSING - only %d of the %d hours before the table exist for this "
                       "coin (it had not been trading that long)" % (len(hs), 24 * LOOKBACK_D)))
        return ("- **Previous 7 days:** MISSING - only %d of the %d hours exist for this coin."
                % (len(hs), 24 * LOOKBACK_D))
    closes = [bars[h]["close"] for h in hs]
    chg = 100.0 * (closes[-1] / closes[0] - 1.0)
    rng = 100.0 * (max(closes) / min(closes) - 1.0) if min(closes) > 0 else None
    vol = statistics.fmean(bars[h]["qvol"] for h in hs)
    trd = statistics.fmean(bars[h]["count"] for h in hs)
    miss = 24 * LOOKBACK_D - len(hs)
    tail = "" if not miss else " · %d hour(s) missing" % miss
    return ("- **Previous 7 days** (h-%d..h-%d): price %s%% · high-low range %s%% · "
            "avg hourly volume %s · avg hourly trades %s%s"
            % (BEFORE_H + 24 * LOOKBACK_D, BEFORE_H + 1, pct(chg), num(rng), human(vol),
               human(trd, 0), tail))


# ------------------------------------------------------------------- driver --
def main() -> int:
    os.makedirs(CARDS, exist_ok=True)
    with open(MOMENTS_CSV, "r", encoding="utf-8") as fh:
        moments = list(csv.DictReader(fh))

    def load_json(name):
        p = os.path.join(EXT, name)
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)

    cal = load_json("us-calendar.json")
    wiki = load_json("wikipedia.json")
    poly = load_json("prediction-market.json")
    ann = load_json("announcements.json")
    if ann:
        by_ex = {}
        for p in ann["probes"]:
            why = p["error"] or p.get("note") or "answered but carries no history"
            by_ex.setdefault(p["exchange"], [])
            if why not in by_ex[p["exchange"]]:
                by_ex[p["exchange"]].append(why)
        ann_note = ("MISSING - no announcement source could be reached: "
                    + "; ".join("%s: %s" % (e, " / ".join(v)) for e, v in sorted(by_ex.items()))
                    + ". Full probe log: `data/observation/external/announcements.json`.")
        ann_short = ("MISSING - every address probed failed or carries no history "
                     "(%s); see data/observation/external/announcements.json"
                     % ", ".join(sorted(by_ex)))
    else:
        ann_note = "MISSING - announcements.json was not written"
        ann_short = ann_note

    refbars = {r: load_klines(r) for r in REFERENCE}
    for r in REFERENCE:
        if not refbars[r]:
            print("WARNING: no hourly klines for reference symbol %s" % r)

    symbols = sorted({m["symbol"] for m in moments})
    cache = {}
    for s in symbols:
        print("loading %s" % s, flush=True)
        cache[s] = {"bars": load_klines(s), "met": load_metrics_hourly(s),
                    "bd": load_bookdepth_hourly(s), "fund": load_funding(s)}

    index_rows, absent_all = [], {}
    total_guard = {"before_points": 0, "after_points": 0, "violations": 0}

    for i, m in enumerate(moments, start=1):
        sym = m["symbol"]
        t0 = int(m["start_ms"])
        no = "C%03d" % i
        c = cache[sym]
        guard = TimeGuard(t0)
        absent = []

        before_hours = [t0 - (BEFORE_H - k) * HOUR_MS for k in range(BEFORE_H)]
        after_hours = [t0 + k * HOUR_MS for k in range(AFTER_H)]

        if not c["met"]:
            absent.append(("open interest / long-short ratios",
                           "MISSING - no metrics file for this coin in the archive"))
        if not c["bd"]:
            absent.append(("order book depth",
                           "MISSING - no bookDepth file for this coin in the archive"))
        for r in REFERENCE:
            if not refbars[r]:
                absent.append((r, "MISSING - reference klines were not fetched"))

        L = []
        A = L.append
        A("# Card %s" % no)
        A("")
        A("| | |")
        A("|---|---|")
        A("| coin | `%s` |" % sym)
        A("| start hour (UTC) | %s |" % hhmm(t0))
        A("| sections | before = the 24 h ending at the start hour · after = the 24 h from it |")
        A("")
        A("Legend: `MISSING` = the source could not be fetched (reason given) · "
          "`none` = the source was fetched and holds nothing for these hours · "
          "`.` = no value published for that hour.")
        A("")
        A("## Before")
        A("")
        A(seven_day_line(c["bars"], t0, guard, absent))
        A(funding_line(c["fund"], t0 - BEFORE_H * HOUR_MS, t0, guard, "before", absent))
        A("- **Order book depth:** median notional resting within 1% of mid, per hour, "
          "in the two `depth` columns below." if c["bd"] else
          "- **Order book depth:** MISSING - no bookDepth file for this coin.")
        A(releases_line(cal, t0 - BEFORE_H * HOUR_MS, t0, guard, "before", absent))
        A(wiki_line((wiki or {}).get(sym), t0, "before", absent))
        A(market_line((poly or {}).get(sym), t0 - BEFORE_H * HOUR_MS, t0, guard, "before", absent))
        A("- **Exchange announcements:** %s" % ann_note)
        absent.append(("Binance and Korean exchange announcements", ann_short))
        A("")
        A(HEADER)
        A(SEP)
        L.extend(hour_rows(before_hours, -BEFORE_H, c["bars"], c["met"], c["bd"],
                           refbars, guard, "before", "before table"))
        A("")
        A("## After")
        A("")
        A("- **Moment kind:** %s" % m["kind"])
        A("- **Measured 24-hour move** (close before the start hour to the close 24 h later): "
          "%s%%" % pct(float(m["move_24h_pct"])))
        A(funding_line(c["fund"], t0, t0 + AFTER_H * HOUR_MS, guard, "after", []))
        A(releases_line(cal, t0, t0 + AFTER_H * HOUR_MS, guard, "after", []))
        A(wiki_line((wiki or {}).get(sym), t0, "after", []))
        A(market_line((poly or {}).get(sym), t0, t0 + AFTER_H * HOUR_MS, guard, "after", []))
        A("")
        A(HEADER)
        A(SEP)
        L.extend(hour_rows(after_hours, 0, c["bars"], c["met"], c["bd"],
                           refbars, guard, "after", "after table"))
        A("")

        # measured per-cell gaps
        gaps, gap_index = [], []
        for label, src in (("open interest / long-short ratios", c["met"]),
                           ("order book depth", c["bd"]),
                           ("price / volume / trade count", c["bars"])):
            if src:
                miss = sum(1 for h in before_hours + after_hours if h not in src)
                if miss:
                    gaps.append("**%s** - empty for %d of the 48 hours: the source covers "
                                "this coin but published no value for those hours" % (label, miss))
                    gap_index.append((label,
                                      "empty on some hours - the source covers this coin but "
                                      "published no value for every hour; the exact count is "
                                      "on each card"))

        A("## Fields not on this card")
        A("")
        if absent or gaps:
            for name, why in absent:
                A("- **%s** - %s" % (name, why))
            for g in gaps:
                A("- %s" % g)
        else:
            A("- none: every field named in TACTICS 3 that this laboratory could reach is above.")
        A("")

        v = guard.check()
        total_guard["before_points"] += len(guard.before_ts)
        total_guard["after_points"] += len(guard.after_ts)
        total_guard["violations"] += len(v)
        if v:
            raise SystemExit("STOP: section leak on card %s (%s):\n  %s"
                             % (no, sym, "\n  ".join(v)))

        text = "\n".join(L)
        path = os.path.join(CARDS, "%s.md" % no)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                if fh.read() != text:
                    raise SystemExit("STOP (RULES 30): %s exists with different content" % path)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)

        for name, why in absent + gap_index:
            absent_all.setdefault((name, why), set()).add(sym)
        index_rows.append({"no": no, "symbol": sym, "kind": m["kind"],
                           "start": hhmm(t0), "sha256": sha256_file(path)})
        if i % 25 == 0:
            print("  %d/%d cards" % (i, len(moments)), flush=True)

    # ------------------------------------------------------------- INDEX.md --
    per_coin = {}
    for r in index_rows:
        e = per_coin.setdefault(r["symbol"], {"large": 0, "calm": 0})
        e[r["kind"]] += 1

    L = []
    A = L.append
    A("# Cards — index\n")
    A("Written by `scripts/09_write_cards.py` (TACTICS 3) at %s (system clock).\n" % utc_now_iso())
    A("## Numbering scheme\n")
    A("Moments are read from `data/moments/moments.csv`, whose rows are sorted by")
    A("`(symbol, start hour, kind)`. The card number is the 1-based position in that")
    A("order: `C001` .. `C%03d`. The moment file is fingerprinted, so the same input" % len(index_rows))
    A("always yields the same card numbers. A card file is never overwritten: if a")
    A("card with the same number already exists with different text the script stops")
    A("(RULES 30).\n")
    A("| input | SHA-256 |")
    A("|---|---|")
    A("| `data/moments/moments.csv` | `%s` |" % sha256_file(MOMENTS_CSV))
    A("")
    A("## Section wall — the measured check\n")
    A("Every value placed in the *before* section passes `TimeGuard.before()`, which")
    A("rejects any hour that does not end at or before the start hour; every value in")
    A("the *after* section passes `TimeGuard.after()`. Per card the script also checks")
    A("that `max(before timestamp) < min(after timestamp)` and that the two timestamp")
    A("sets do not intersect. Any violation stops the script before the card is")
    A("written.\n")
    A("| check | value |")
    A("|---|---|")
    A("| cards written | %d |" % len(index_rows))
    A("| timestamps guarded into the before section | %d |" % total_guard["before_points"])
    A("| timestamps guarded into the after section | %d |" % total_guard["after_points"])
    A("| **violations** | **%d** |" % total_guard["violations"])
    A("")
    A("The moment's kind (`large` / `calm`) and its measured 24-hour move are printed")
    A("**inside the after section only**, because both are facts about the after")
    A("window.\n")
    A("## Missing and empty\n")
    A("`MISSING` means the source could not be fetched and the reason is printed next")
    A("to it. `none` means the source was fetched and holds nothing for those hours.")
    A("`.` inside a table means the source covers the coin but published no value for")
    A("that hour. A card never implies a measurement that was not made (RULES 20).\n")
    A("## Fields missing or empty, by name\n")
    if absent_all:
        A("| field | missing or empty, and why | coins affected |")
        A("|---|---|---|")
        for (name, why), syms in sorted(absent_all.items()):
            n = sum(per_coin[s]["large"] + per_coin[s]["calm"] for s in syms)
            A("| %s | %s | %s (%d cards) |" % (name, why.replace("|", "/"),
                                               ", ".join(sorted(syms)), n))
    else:
        A("None.")
    A("")
    A("TACTICS 3 also names Google searches, Reddit, Twitter, the history of leverage")
    A("limits and a world news archive as things that are *not* on the card because")
    A("there is no history or they cannot be reached. None of them was attempted here.")
    A("")
    A("## Count per coin\n")
    A("| coin | large | calm | total |")
    A("|---|---|---|---|")
    for s in sorted(per_coin):
        e = per_coin[s]
        A("| %s | %d | %d | %d |" % (s, e["large"], e["calm"], e["large"] + e["calm"]))
    A("| **total** | **%d** | **%d** | **%d** |" % (
        sum(e["large"] for e in per_coin.values()),
        sum(e["calm"] for e in per_coin.values()), len(index_rows)))
    A("")
    A("## Cards\n")
    A("| card | coin | kind | start hour (UTC) | SHA-256 |")
    A("|---|---|---|---|---|")
    for r in index_rows:
        A("| `%s` | %s | %s | %s | `%s` |" % (r["no"], r["symbol"], r["kind"],
                                              r["start"], r["sha256"]))
    A("")
    with open(os.path.join(CARDS, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    print(json.dumps({"cards": len(index_rows), "guard": total_guard,
                      "finished_at_utc": utc_now_iso()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
