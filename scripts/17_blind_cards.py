#!/usr/bin/env python3
"""
17_blind_cards.py -- turn a card into a card that does not say which coin it
is or when it happened.

What it does
------------
Reads the cards of a folder and writes a blinded copy of each one, keeping
only the Before section (TACTICS 6) and replacing every field whose ABSOLUTE
LEVEL is a coin's signature with the same quantity expressed against the
card's own scale. It writes a manifest recording exactly what it did to each
field, and a truth file so that `16_identity_audit.py` can attack the result.

It is run here on the 306 observation cards, as a proof. The exam cards are
built by a different run in a different mode; this script is the instrument it
should use, not the exam itself. Nothing under `exam/` is read or written.

Input   : a folder of cards (default `cards/`)
Output  : <out>/cards/B###.md       the blinded cards
          <out>/truth-<label>.csv   B### -> coin, kind, start hour
          <out>/blind-manifest.md   what was done to every field, with counts
          <out>/runs/<run16>.json   append-only run record

Rules implemented
-----------------
RULES 9  : "In the exam the coin name and the date are hidden." Everything
           below serves that sentence.
RULES 6  : the canteen book is frozen. No transform here may destroy a
           quantity the frozen book needs; the script COUNTS whether each of
           those quantities survived, and stops if one did not.
RULES 19 : every number in the manifest is counted.
RULES 23 : the clock is read from the system.
RULES 28 : free disk space is read and recorded.
RULES 29 / 30 : run number = SHA-256 of the inputs; records are append-only.
TACTICS 3 : "Numbers are rounded and the card is kept short."
TACTICS 6 : the hide-list this script implements and extends. Every extension
            beyond TACTICS 6's five bullets is listed in the manifest by name.

Constants -- where each came from
---------------------------------
SEED = 20260913     TACTICS 1's draw number; used only to shuffle the output
                    card numbers so their order carries no time information.
RATIO_DP = 3        chosen by measurement, not by taste: it is the smallest
                    number of decimals at which the rounding creates no new
                    run of three identical consecutive values in a `depth`
                    column that the raw card did not already have (the
                    canteen book's B-4 reads exactly that pattern). The script
                    measures 2, 3 and 4 decimals on every run and writes the
                    counts into the manifest, so the choice is checkable.
RUN_LEN = 3         the run length B-4 uses; taken from the frozen book.
CLOSE_DP_REVIEWED = 2
                    the rebased-`close` decimals of the version reviewed in
                    exam-prep/REVIEW.md. `--close-dp 2` reproduces it exactly.
CLOSE_DP_SEARCH_MAX = 10
                    a safety stop, not a threshold: `--close-dp no-new-ties`
                    searches upward from 2 and stops the script if no number
                    of decimals up to this one manufactures zero ties. The
                    number actually needed depends on the card set (the raw
                    card prints `close` to 6 significant figures, and how far
                    the price sits from its h-24 value matters) and is
                    computed, not assumed.

Change made in the second-fix run (2026-10-01), acting on exam-prep/REVIEW.md
------------------------------------------------------------------------------
The version reviewed is git commit 7735d08 (SHA-256 ee064204...9515). One
option is added, `--close-dp`, default `2` = the reviewed rendering, so every
earlier command line still produces the same card text (checked by
scripts/25_instrument_checks.py). `--close-dp no-new-ties` implements
criterion K-1 of exam-prep/second-fix/criteria-written-before-measuring.md:
the rebased `close` is printed at the smallest number of decimals, uniform
over the card set, at which no card prints two equal rebased values where
the raw card printed two different ones (REVIEW §3.2: the reviewed rendering
manufactures such ties, and they are a coin signature).

Change made in the third-fix run (2026-10-01), acting on exam-prep/REVIEW-2.md
--------------------------------------------------------------------------------
The version REVIEW-2 reviewed has SHA-256 b2853b66...0dbed. One option is
added, `--rank-source`, default `printed` = the existing behaviour, so every
earlier command line produces the same card text. `--rank-source unrounded`
implements criterion K-10 of exam-prep/third-fix/criteria-written-before-
measuring.md: with `--levels rank` (and `--takerbuy rank`), each ranked column
is ranked on the value the card writer had BEFORE it rounded it -- the hourly
klines (quote volume, trade count, taker-buy share) and the card writer's own
hourly caches of the 5-minute metrics and the order-book depth, read from
data/observation/ and never written. Guards, each stopping the script:
every source value, formatted with scripts/09_write_cards.py's own functions,
must give exactly the token the raw card prints; the before-window hours
printing an open-interest zero (B-3) and the before-window hours inside a run
of three or more identical depth values (B-4) must be the same on the raw and
the blinded card.

No threshold, score or trading rule is defined anywhere in this file.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cards  # noqa: E402

SEED = 20260913
RATIO_DP = 3
RUN_LEN = 3
CLOSE_DP_REVIEWED = 2
CLOSE_DP_SEARCH_MAX = 10

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Columns whose absolute level is a coin's signature and which are therefore
# printed against the card's own scale. The list is every numeric column of
# the card table except `h`, `close` (TACTICS 6 rebases it), `chg%` (frozen:
# the canteen book's S-1 reads it at 5.00% absolute), `taker buy%` (a share,
# handled separately) and BTC / ETH (handled separately).
LEVEL_COLUMNS = ["quote vol", "trades", "open int", "L/S acct",
                 "top L/S pos", "taker L/S", "depth -1%", "depth +1%"]

LEGEND = ("Legend: every column marked `x` is that hour's value divided by "
          "this card's own median of the same column over the 24 rows, so a "
          "value of 1.000 is this card's typical hour. `close` starts at "
          "100.00. `chg%` is the plain hourly percentage change. A zero is "
          "printed as a zero.")

LEGEND_RANK = ("Legend: every column marked `r` is that hour's rank among the "
               "24 rows of this card, 1 = smallest, ties share the average "
               "rank; an exact zero is printed as `0`. `close` starts at "
               "100.00. `chg%` is the plain hourly percentage change.")

ANNOUNCE_LINE = ("MISSING - no exchange announcement source could be reached "
                 "for any card of this set. This is a fetch failure, never a "
                 "\"no announcement\" (RULES 20, 21).")

DEPTH_LINE = ("median notional resting within 1% of mid, per hour, in the "
              "two `depth` columns below, on this card's own scale.")


def die(msg):
    sys.stderr.write("STOP: %s\n" % msg)
    sys.exit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def scale_denominator(vals):
    """The card's own median of the positive values of a column. Zeros are
    left out of the denominator so that a printed zero (the canteen book's
    B-3) stays a zero and does not move the scale."""
    pos = [v for v in vals if v is not None and v > 0]
    if not pos:
        return None
    return median(pos)


def ranks(vals):
    """Average ranks, 1 = smallest. Equal values get equal ranks, so a frozen
    constant (B-4) stays visible as a repeated value."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def longest_equal_run(vals):
    best = cur = 1
    for i in range(1, len(vals)):
        cur = cur + 1 if vals[i] == vals[i - 1] else 1
        best = max(best, cur)
    return best


def strip_release_dates(text):
    """TACTICS 6: 'the date in the release calendar' is hidden. The relative
    offset in hours stays, because it is relative and not a date."""
    out = re.sub(r"\s+for\s+(?:[A-Z][A-Za-z-]*\s+)*\d{4}", "", text)
    out = re.sub(r"\s+on\s+\d{4}-\d{2}-\d{2}", "", out)
    # Anything date-shaped that is left is part of a series TITLE rather than
    # this card's calendar date (the one case in the 306 observation cards is
    # a birth cohort, "those Born 1980-1984"). It is masked anyway, because a
    # blinding that keeps "some years but not others" is not checkable.
    out = re.sub(r"\d{4}", "YYYY", out)
    for mn in MONTHS:
        out = re.sub(r"\b%s\b" % mn, "<month>", out)
    out = re.sub(r"\b(First|Second|Third|Fourth) Quarter\b", "<quarter>", out)
    return out


MONTHS = ("January February March April May June July August September "
          "October November December").split()


def release_date_leak(text):
    """Returns a reason string if a date survived the strip, else None."""
    if re.search(r"\d{4}", text):
        return "a four-digit year survived"
    if re.search(r"\b(19|20)\d\d\b", text):
        return "a year survived"
    for mn in MONTHS:
        if re.search(r"\b%s\b" % mn, text):
            return "the month name %s survived" % mn
    for q in ("First Quarter", "Second Quarter", "Third Quarter",
              "Fourth Quarter"):
        if q in text:
            return "the calendar period %r survived" % q
    # A bare "Annual" or "Biennial" is the periodicity of the series, not a
    # date, and is left alone.
    return None


def funding_summary(c):
    """The blinded funding line. It prints three yes/no facts and one
    scale-free number, and prints neither the interval, nor the payment
    count, nor any rate. Each of the three facts is one the frozen canteen
    book asks a candidate for:
      - all payments equal      -> U-3, the baseline-funding state
      - count matches interval  -> B-5, the short funding window
      - interval changed        -> U-2, the funding-interval change
    """
    rates = c["funding_rates"]
    changed = c["funding_interval_changed"] == "yes"
    all_equal = len(set(rates)) <= 1
    if all_equal:
        spread = 0.0
    else:
        scale = sum(abs(r) for r in rates) / len(rates)
        spread = (max(rates) - min(rates)) / scale if scale > 0 else 0.0
    if changed or "/" in c["funding_interval_text"]:
        matches = "not applicable — the interval changed inside this window"
    else:
        iv = float(c["funding_interval_text"])
        matches = "yes" if c["funding_count"] == round(24 / iv) else "no"
    return ("all payments in this window are equal: %s · relative spread of "
            "the payments: %.2f · the payment count matches the stated "
            "interval: %s · the interval changed inside this window: %s"
            % ("yes" if all_equal else "no", spread, matches,
               "yes" if changed else "no"))


def funding_normalised(c):
    rates = c["funding_rates"]
    changed = c["funding_interval_changed"] == "yes"
    if len(set(rates)) <= 1:
        body = "%d payment(s), all equal" % len(rates)
    else:
        scale = sum(abs(r) for r in rates) / len(rates)
        body = ("%d payment(s), each as a multiple of the window's mean "
                "absolute payment: %s"
                % (len(rates), " ".join("%+.3f" % (r / scale)
                                        for r in rates)))
    return body + " · the interval changed inside this window: %s" % (
        "yes" if changed else "no")


def funding_raw(c):
    return c["before_bullets"]["Funding"]


def funding_flags(c):
    """The narrowest funding line that still answers every funding question
    the FROZEN canteen book asks a candidate: B-5 (does the payment count
    match the stated interval), U-3 (is the whole window at one rate) and U-2
    (did the interval change). It prints no rate, no count, no interval and no
    dispersion, because the frozen book asks for none of those on an exam
    card."""
    rates = c["funding_rates"]
    changed = c["funding_interval_changed"] == "yes"
    all_equal = len(set(rates)) <= 1
    if changed or "/" in c["funding_interval_text"]:
        matches = "not applicable"
    else:
        iv = float(c["funding_interval_text"])
        matches = "yes" if c["funding_count"] == round(24 / iv) else "no"
    return ("all payments in this window are equal: %s · the payment count "
            "matches the stated interval: %s · the interval changed inside "
            "this window: %s"
            % ("yes" if all_equal else "no", matches,
               "yes" if changed else "no"))


FUNDING = {"summary": funding_summary,
           "flags": funding_flags,
           "normalised": funding_normalised,
           "raw": funding_raw}


def rebased_close(c):
    col = c["before"]
    base = col["close"][0]
    if base is None or base <= 0:
        raise ValueError("%s: cannot rebase price, h-24 close is %r"
                         % (c["card"], base))
    return [v / base * 100.0 for v in col["close"]]


def manufactured_ties(c, dp):
    """Pairs of before-window hours that print the same rebased `close` at
    `dp` decimals although the raw card printed two different values."""
    raw = c["before"]["close"]
    reb = ["%.*f" % (dp, v) for v in rebased_close(c)]
    n = 0
    for i in range(len(raw)):
        for j in range(i + 1, len(raw)):
            if reb[i] == reb[j] and raw[i] != raw[j]:
                n += 1
    return n


def choose_close_dp(cards, mode):
    """Returns (dp, table) where table maps each dp tried to the number of
    cards on which it manufactures at least one tie."""
    table = {}
    for dp in range(CLOSE_DP_REVIEWED, CLOSE_DP_SEARCH_MAX + 1):
        table[dp] = sum(1 for c in cards if manufactured_ties(c, dp) > 0)
        if mode == "no-new-ties" and table[dp] == 0:
            return dp, table
        if mode != "no-new-ties" and dp >= max(int(mode), 4):
            break
    if mode == "no-new-ties":
        die("no number of decimals up to %d stops the rebased close from "
            "manufacturing ties" % CLOSE_DP_SEARCH_MAX)
    return int(mode), table


def run_hours(vals):
    """The positions that sit inside a run of RUN_LEN or more identical
    consecutive values (B-4's pattern)."""
    out = set()
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        if j - i + 1 >= RUN_LEN:
            out.update(range(i, j + 1))
        i = j + 1
    return out


def unrounded_sources(cards):
    """K-10: the unrounded value of every ranked column for every before hour
    of every card, read from the same sources the card writer read, and
    checked token by token against the printed raw card. Returns
    ({card: {column: [24 values]}}, [(input name, sha256), ...])."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "w9", os.path.join(here, "09_write_cards.py"))
    w9 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w9)
    hour = w9.HOUR_MS
    inputs = [("scripts/09_write_cards.py",
               sha256_file(os.path.join(here, "09_write_cards.py")))]
    per_coin = {}

    def cache(kind, sym, raw_dir):
        path = os.path.join(w9.DERIVED, kind, "%s.json" % sym)
        d = os.path.join(w9.OBS, raw_dir, sym)
        files = sorted(os.listdir(d)) if os.path.isdir(d) else []
        with open(path, encoding="utf-8") as fh:
            cc = json.load(fh)
        if cc.get("files") != files:
            die("K-10: %s does not match the files in %s; it is not "
                "rebuilt here" % (path, d))
        inputs.append((os.path.relpath(path, REPO), sha256_file(path)))
        return {int(k): v for k, v in cc["hours"].items()}

    out = {}
    for c in cards:
        sym = c["coin"]
        if sym not in per_coin:
            kd = os.path.join(w9.OBS, "klines_1h", sym)
            for f in sorted(os.listdir(kd)):
                if f.endswith(".zip"):
                    inputs.append((os.path.relpath(os.path.join(kd, f), REPO),
                                   sha256_file(os.path.join(kd, f))))
            per_coin[sym] = (w9.load_klines(sym),
                             cache("metrics-hourly", sym, "metrics"),
                             cache("bookdepth-hourly", sym, "bookDepth"))
        bars, met, bd = per_coin[sym]
        t0 = int(dt.datetime.strptime(c["start_hour_utc"], "%Y-%m-%dT%H:%MZ")
                 .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        hours = [t0 - (24 - k) * hour for k in range(24)]
        src = {nm: [] for nm in ("quote vol", "trades", "taker buy%",
                                 "open int", "L/S acct", "top L/S pos",
                                 "taker L/S", "depth -1%", "depth +1%")}
        for i, hh in enumerate(hours):
            b = bars.get(hh)
            m = met.get(hh) or {}
            d = bd.get(hh) or {}
            vals = {"quote vol": b["qvol"] if b else None,
                    "trades": float(b["count"]) if b else None,
                    "taker buy%": b["taker_buy_pct"] if b else None,
                    "open int": m.get("oi"), "L/S acct": m.get("ls_acct"),
                    "top L/S pos": m.get("top_ls_pos"),
                    "taker L/S": m.get("taker_ls"),
                    "depth -1%": d.get("bid1"), "depth +1%": d.get("ask1")}
            fmt = {"quote vol": w9.human(vals["quote vol"])
                   if b else ".",
                   "trades": w9.human(vals["trades"], 0) if b else ".",
                   "taker buy%": w9.num(vals["taker buy%"], 1)
                   if b else ".",
                   "open int": w9.human(vals["open int"]),
                   "L/S acct": w9.num(vals["L/S acct"]),
                   "top L/S pos": w9.num(vals["top L/S pos"]),
                   "taker L/S": w9.num(vals["taker L/S"]),
                   "depth -1%": w9.human(vals["depth -1%"]),
                   "depth +1%": w9.human(vals["depth +1%"])}
            printed_row = c["before_rows_text"][i]
            cells = [x.strip() for x in printed_row.strip().strip("|")
                     .split("|")]
            names = lab_cards.COLUMNS
            for nm in src:
                tok = cells[names.index(nm)]
                if fmt[nm] != tok:
                    die("K-10 guard 1: %s h%+d `%s`: source formats as %r, "
                        "the card prints %r" % (c["card"], i - 24, nm,
                                                fmt[nm], tok))
                src[nm].append(vals[nm])
        out[c["card"]] = src
    return out, sorted(set(inputs))


def build_card(c, cid, levels, btceth, funding_mode, takerbuy_mode,
               p7_mode, close_dp=CLOSE_DP_REVIEWED, src=None):
    """Returns (text, diagnostics). `src` (third-fix, K-10): the unrounded
    source values of the ranked columns, one list of 24 per column name; when
    given, ranks are computed on them instead of on the printed values."""
    col = c["before"]
    n = len(col["h"])
    diag = {}
    rk_in = src if src is not None else col

    # --- price: TACTICS 6, "converted to a number starting from 100" -------
    close = rebased_close(c)

    # --- the level-carrying columns ----------------------------------------
    printed = {}
    for name in LEVEL_COLUMNS:
        vals = col[name]
        if levels == "rank":
            vals = rk_in[name]
            nonzero = [v for v in vals if v != 0]
            if nonzero:
                rk = ranks(vals)
                printed[name] = ["0" if v == 0 else "%.1f" % r
                                 for v, r in zip(vals, rk)]
            else:
                printed[name] = ["0"] * n
        else:
            den = scale_denominator(vals)
            if den is None:
                printed[name] = ["0"] * n
            else:
                printed[name] = ["%.*f" % (RATIO_DP, v / den) for v in vals]

    # --- taker buy% ---------------------------------------------------------
    if takerbuy_mode == "centred":
        med = median([v for v in col["taker buy%"]])
        taker = ["%+.1f" % (v - med) for v in col["taker buy%"]]
        taker_header = "taker buy% dev"
    elif takerbuy_mode == "rank":
        taker = ["%.1f" % r for r in ranks(rk_in["taker buy%"])]
        taker_header = "taker buy% r"
    else:
        taker = ["%.1f" % v for v in col["taker buy%"]]
        taker_header = "taker buy%"

    # --- header and columns -------------------------------------------------
    suffix = " r" if levels == "rank" else " x"
    headers = ["h", "close", "chg%"] + \
              [nm + suffix for nm in ("quote vol", "trades")] + \
              [taker_header] + \
              [nm + suffix for nm in ("open int", "L/S acct", "top L/S pos",
                                      "taker L/S", "depth -1%", "depth +1%")]
    if btceth == "keep":
        headers += ["BTC", "ETH"]

    rows = []
    for i in range(n):
        cells = ["%+d" % col["h"][i] if col["h"][i] < 0 else "+%d" % col["h"][i],
                 "%.*f" % (close_dp, close[i]), "%+.2f" % col["chg%"][i],
                 printed["quote vol"][i], printed["trades"][i], taker[i],
                 printed["open int"][i], printed["L/S acct"][i],
                 printed["top L/S pos"][i], printed["taker L/S"][i],
                 printed["depth -1%"][i], printed["depth +1%"][i]]
        if btceth == "keep":
            cells += ["%+.2f" % col["BTC"][i], "%+.2f" % col["ETH"][i]]
        rows.append("| " + " | ".join(cells) + " |")

    # --- the previous-7-day line -------------------------------------------
    den_vol = scale_denominator(col["quote vol"])
    den_tr = scale_denominator(col["trades"])
    if p7_mode == "no-scale":
        p7 = ("price %+.2f%% · high-low range %.2f%%"
              % (c["p7_price_pct"], c["p7_range_pct"]))
    else:
        p7 = ("price %+.2f%% · high-low range %.2f%% · avg hourly volume %s · "
              "avg hourly trades %s"
              % (c["p7_price_pct"], c["p7_range_pct"],
                 ("%.3f× this card's median hour"
                  % (c["p7_avg_vol"] / den_vol)) if den_vol else "n/a",
                 ("%.3f× this card's median hour"
                  % (c["p7_avg_trades"] / den_tr)) if den_tr else "n/a"))

    # --- the US release line ------------------------------------------------
    rel = c["before_bullets"].get("US releases", "none in these hours.")
    rel_blind = strip_release_dates(rel)
    leak = release_date_leak(rel_blind)
    if leak:
        raise ValueError("%s: the US release line still carries a date (%s): "
                         "%r" % (c["card"], leak, rel_blind))

    # --- assemble -----------------------------------------------------------
    A = []
    A.append("# Card %s" % cid)
    A.append("")
    A.append("| | |")
    A.append("|---|---|")
    A.append("| sections | before = the 24 h ending at the start hour |")
    A.append("")
    legend = LEGEND_RANK if levels == "rank" else LEGEND
    if close_dp != CLOSE_DP_REVIEWED:
        legend = legend.replace("`close` starts at 100.00",
                                "`close` starts at %.*f" % (close_dp, 100.0))
    A.append(legend)
    A.append("")
    A.append("## Before")
    A.append("")
    A.append("- **Previous 7 days** (h-192..h-25): %s" % p7)
    A.append("- **Funding:** %s" % FUNDING[funding_mode](c))
    A.append("- **Order book depth:** %s" % DEPTH_LINE)
    A.append("- **US releases:** %s" % rel_blind)
    A.append("- **Exchange announcements:** %s" % ANNOUNCE_LINE)
    A.append("")
    A.append("| " + " | ".join(headers) + " |")
    A.append("|" + "|".join(["---"] * len(headers)) + "|")
    A.extend(rows)
    A.append("")
    A.append("## Fields not on this card")
    A.append("")
    A.append("- **the coin name, the date and time, and the price level** - "
             "hidden (RULES 9, TACTICS 6)")
    A.append("- **the After section** - never shown in an exam (TACTICS 6)")
    A.append("- **Wikipedia page views** - not carried")
    A.append("- **prediction market price** - not carried")
    if btceth == "drop":
        A.append("- **the bitcoin and ethereum columns** - not carried")
    A.append("")

    # --- diagnostics the frozen book depends on ----------------------------
    diag["raw_depth_max_run"] = max(longest_equal_run(col["depth -1%"]),
                                    longest_equal_run(col["depth +1%"]))
    for dp in (2, 3, 4):
        runs = []
        for name in ("depth -1%", "depth +1%"):
            den = scale_denominator(col[name])
            if den is None:
                runs.append(len(col[name]))
                continue
            runs.append(longest_equal_run(["%.*f" % (dp, v / den)
                                           for v in col[name]]))
        diag["blind_depth_max_run_dp%d" % dp] = max(runs)
    diag["raw_oi_zero_rows"] = sum(1 for v in col["open int"] if v == 0)
    zero_printed = sum(1 for v in printed["open int"] if float(v) == 0.0)
    diag["blind_oi_zero_rows"] = zero_printed
    diag["printed_depth"] = {nm: printed[nm] for nm in ("depth -1%",
                                                        "depth +1%")}
    diag["printed_oi"] = printed["open int"]
    diag["raw_max_abs_chg"] = max(abs(v) for v in col["chg%"])
    diag["blind_max_abs_chg"] = max(abs(float(r.split("|")[3].strip()))
                                    for r in rows)
    return "\n".join(A) + "\n", diag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=os.path.join(REPO, "cards"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--levels", choices=("ratio", "rank"), default="ratio")
    ap.add_argument("--btceth", choices=("drop", "keep"), default="drop")
    ap.add_argument("--funding", choices=tuple(FUNDING), default="summary")
    ap.add_argument("--takerbuy", choices=("centred", "rank", "raw"),
                    default="centred")
    ap.add_argument("--p7", choices=("full", "no-scale"), default="full")
    ap.add_argument("--rank-source", choices=("printed", "unrounded"),
                    default="printed",
                    help="third-fix, K-10: rank the printed values (default, "
                         "the reviewed behaviour) or the unrounded source "
                         "values")
    ap.add_argument("--close-dp", default=str(CLOSE_DP_REVIEWED),
                    help="'2' (the reviewed rendering) or 'no-new-ties' "
                         "(criterion K-1)")
    args = ap.parse_args()
    if args.close_dp != "no-new-ties" and not args.close_dp.isdigit():
        die("--close-dp must be a whole number or 'no-new-ties'")

    started = dt.datetime.now(dt.timezone.utc)
    free_bytes = shutil.disk_usage(REPO).free

    cards = lab_cards.load_all(args.cards)
    if not cards:
        die("no cards in %s" % args.cards)

    close_dp, close_dp_table = choose_close_dp(cards, args.close_dp)
    config = ("levels=%s;btceth=%s;funding=%s;takerbuy=%s;p7=%s;ratio_dp=%d;"
              "close_dp=%s->%d"
              % (args.levels, args.btceth, args.funding, args.takerbuy,
                 args.p7, RATIO_DP, args.close_dp, close_dp))
    sources = {}
    source_inputs = []
    if args.rank_source == "unrounded":
        if args.levels != "rank":
            die("--rank-source unrounded needs --levels rank")
        config += ";rank_source=unrounded"
        sources, source_inputs = unrounded_sources(cards)
    script_sha = sha256_file(os.path.abspath(__file__))
    h = hashlib.sha256()
    h.update(("script:" + script_sha + "\n").encode())
    h.update(("module:" + sha256_file(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "lab_cards.py")) + "\n").encode())
    h.update(("config:" + config + ";seed:%d\n" % SEED).encode())
    for name, sha in source_inputs:
        h.update(("source:%s:%s\n" % (name, sha)).encode())
    for c in cards:
        h.update(("%s:%s\n" % (c["card"], c["sha256"])).encode())
    run_full = h.hexdigest()
    run16 = run_full[:16]

    # output card numbers are shuffled, so their order carries no time
    rng = random.Random(SEED)
    order = list(range(len(cards)))
    rng.shuffle(order)
    assign = {}
    for new_i, src_i in enumerate(order, 1):
        assign[cards[src_i]["card"]] = "B%03d" % new_i

    out_cards = os.path.join(args.out, "cards")
    os.makedirs(out_cards, exist_ok=True)
    runs_dir = os.path.join(args.out, "runs")
    os.makedirs(runs_dir, exist_ok=True)

    truth_rows = []
    diags = []
    for c in cards:
        cid = assign[c["card"]]
        try:
            text, diag = build_card(c, cid, args.levels, args.btceth,
                                    args.funding, args.takerbuy, args.p7,
                                    close_dp, sources.get(c["card"]))
        except ValueError as e:
            die(str(e))
        path = os.path.join(out_cards, cid + ".md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                if fh.read() != text:
                    die("%s already exists with different text (RULES 30: "
                        "records are append-only, never overwritten)" % path)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        truth_rows.append({"id": cid, "source_card": c["card"],
                           "coin": c["coin"], "kind": c["kind"],
                           "start_hour_utc": c["start_hour_utc"]})
        diag["card"] = cid
        diag["source_card"] = c["card"]
        diags.append(diag)

    # --- what survived, counted --------------------------------------------
    survived = {
        "cards_written": len(cards),
        "B-3 · cards printing an open-interest zero, raw":
            sum(1 for d in diags if d["raw_oi_zero_rows"] > 0),
        "B-3 · cards printing an open-interest zero, blinded":
            sum(1 for d in diags if d["blind_oi_zero_rows"] > 0),
        "B-4 · cards with a depth run of >= %d, raw" % RUN_LEN:
            sum(1 for d in diags if d["raw_depth_max_run"] >= RUN_LEN),
        "B-4 · cards with a depth run of >= %d, blinded (%d dp)"
        % (RUN_LEN, RATIO_DP):
            sum(1 for d in diags
                if d["blind_depth_max_run_dp%d" % RATIO_DP] >= RUN_LEN),
        "S-1 · cards whose largest |chg%| is unchanged":
            sum(1 for d in diags
                if abs(d["raw_max_abs_chg"] - d["blind_max_abs_chg"]) < 1e-9),
    }
    fabricated = [d["card"] for d in diags
                  if d["blind_depth_max_run_dp%d" % RATIO_DP] >= RUN_LEN
                  and d["raw_depth_max_run"] < RUN_LEN]
    lost_oi = [d["card"] for d in diags
               if d["raw_oi_zero_rows"] != d["blind_oi_zero_rows"]]
    lost_chg = [d["card"] for d in diags
                if abs(d["raw_max_abs_chg"] - d["blind_max_abs_chg"]) >= 1e-9]
    if args.rank_source == "unrounded":
        b3_moved, b4_moved = [], []
        for c, d in zip(cards, diags):
            col = c["before"]
            if [v == 0 for v in col["open int"]] != \
                    [t == "0" for t in d["printed_oi"]]:
                b3_moved.append(d["card"])
            for nm in ("depth -1%", "depth +1%"):
                if run_hours(col[nm]) != run_hours(d["printed_depth"][nm]):
                    b4_moved.append("%s(%s)" % (d["card"], nm))
        survived["B-3 · cards whose open-interest zero hours differ, raw vs "
                 "blinded (K-10)"] = len(b3_moved)
        survived["B-4 · depth columns whose run hours differ, raw vs "
                 "blinded (K-10)"] = len(b4_moved)
        if b3_moved:
            die("K-10 guard 2: the open-interest zero hours differ on %d "
                "card(s): %s" % (len(b3_moved), " ".join(b3_moved[:20])))
        if b4_moved:
            die("K-10 guard 3: the B-4 run hours differ on %d depth "
                "column(s): %s" % (len(b4_moved), " ".join(b4_moved[:40])))
    for d in diags:
        d.pop("printed_depth", None)
        d.pop("printed_oi", None)
    if lost_oi:
        die("the blinding destroyed the B-3 zero on %d card(s): %s"
            % (len(lost_oi), " ".join(lost_oi[:10])))
    if lost_chg:
        die("the blinding changed the largest |chg%%| on %d card(s): %s"
            % (len(lost_chg), " ".join(lost_chg[:10])))
    if fabricated and args.levels == "ratio":
        die("rounding to %d decimals fabricated a B-4 depth run on %d card(s):"
            " %s" % (RATIO_DP, len(fabricated), " ".join(fabricated[:10])))

    dp_table = {}
    for dp in (2, 3, 4):
        fab = [d["card"] for d in diags
               if d["blind_depth_max_run_dp%d" % dp] >= RUN_LEN
               and d["raw_depth_max_run"] < RUN_LEN]
        dp_table[dp] = len(fab)

    truth_path = os.path.join(args.out, "truth-%s.csv" % args.label)
    with open(truth_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(truth_rows[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(truth_rows, key=lambda r: r["id"]))

    core = {"run": run16, "input_fingerprint": run_full, "config": config,
            "label": args.label, "cards": len(cards), "seed": SEED,
            "survived": survived, "script_sha256": script_sha,
            "close_dp": close_dp,
            "close_dp_manufactured_ties": {str(k): v for k, v
                                           in close_dp_table.items()}}
    rec_path = os.path.join(runs_dir, run16 + ".json")
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as fh:
            old = json.load(fh)
        differ = [k for k, v in core.items() if old.get(k) != v]
        if differ:
            die("run record %s exists and disagrees on %s (RULES 30)"
                % (rec_path, ", ".join(sorted(differ))))

    A = []
    A.append("# Blinding manifest — card set `%s`" % args.label)
    A.append("")
    A.append("Written by `scripts/17_blind_cards.py`. It records what was done "
             "to every field and counts what survived. It draws no conclusion "
             "and reads nothing under `exam/`.")
    A.append("")
    A.append("| field | value |")
    A.append("|---|---|")
    A.append("| run number (RULES 29) | `%s` |" % run16)
    A.append("| full input fingerprint | `%s` |" % run_full)
    A.append("| written at (system clock, UTC, RULES 23) | %s |"
             % started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    A.append("| free disk space at start (bytes) | %d |" % free_bytes)
    A.append("| source cards | `%s`, %d cards |"
             % (os.path.relpath(args.cards, REPO), len(cards)))
    A.append("| configuration | `%s` |" % config)
    A.append("| card-number shuffle seed | `%d` (TACTICS 1 draw number) |"
             % SEED)
    A.append("| `scripts/17_blind_cards.py` SHA-256 | `%s` |" % script_sha)
    A.append("")
    A.append("## What was done to each field")
    A.append("")
    A.append("| field | before | after |")
    A.append("|---|---|---|")
    A.append("| coin name | printed in the header | removed (TACTICS 6) |")
    A.append("| start hour | printed in the header | removed (TACTICS 6) |")
    A.append("| card number | `C###`, in moment order | `B###`, shuffled "
             "with the draw seed, so the number carries no time |")
    A.append("| After section | printed | removed (TACTICS 6) |")
    A.append("| `close` | the coin's price | rebased so h-24 = %.*f, %d "
             "decimals (TACTICS 6; `--close-dp %s`) |"
             % (close_dp, 100.0, close_dp, args.close_dp))
    A.append("| `chg%` | hourly percentage change | **unchanged** — the frozen "
             "canteen book's S-1 reads it at 5.00% absolute (RULES 6) |")
    for nm in LEVEL_COLUMNS:
        A.append("| `%s` | the coin's own level | %s |"
                 % (nm, "rank among the card's 24 rows, exact zeros kept"
                    if args.levels == "rank"
                    else "divided by this card's median of the same column, "
                         "%d decimals, exact zeros kept" % RATIO_DP))
    A.append("| `taker buy%%` | a share, 0–100 | %s |"
             % {"centred": "deviation from this card's own median",
                "rank": "rank among the card's 24 rows",
                "raw": "unchanged"}[args.takerbuy])
    A.append("| `BTC`, `ETH` | the market's hourly change | %s |"
             % ("removed" if args.btceth == "drop" else "unchanged"))
    A.append("| previous-7-day volume and trades | the coin's own level | %s |"
             % ("not printed" if args.p7 == "no-scale"
                else "expressed against this card's median hour"))
    A.append("| funding line | count, every rate, the interval | `%s` "
             "rendering |" % args.funding)
    A.append("| US releases | release names carrying calendar dates | dates "
             "stripped, relative offsets kept (TACTICS 6); every card checked "
             "and the script stops if a year, a month name or a quarter "
             "survives |")
    A.append("| Wikipedia page views | present on some coins only | removed |")
    A.append("| prediction market | names the instrument in words | removed |")
    A.append("| exchange announcements | a per-card reason string | one "
             "canonical sentence on every card |")
    A.append("")
    A.append("## What the frozen canteen book needs, and whether it survived")
    A.append("")
    A.append("| quantity | count |")
    A.append("|---|---|")
    for k in sorted(survived):
        A.append("| %s | %s |" % (k, survived[k]))
    A.append("")
    A.append("The script stops rather than writing a card if a B-3 zero is "
             "lost, if the largest `|chg%|` moves, or if the rounding "
             "fabricates a B-4 depth run that the raw card did not have.")
    A.append("")
    A.append("## Choosing the number of decimals by measurement")
    A.append("")
    A.append("| decimals | cards where the rounding fabricates a run of %d "
             "identical depth values | " % RUN_LEN)
    A.append("|---|---|")
    for dp in (2, 3, 4):
        A.append("| %d | %d |" % (dp, dp_table[dp]))
    A.append("")
    A.append("`RATIO_DP` is set to %d." % RATIO_DP)
    A.append("")
    A.append("## The decimals of the rebased `close`")
    A.append("")
    A.append("| decimals | cards on which two hours print the same rebased "
             "`close` although the raw card printed two different values |")
    A.append("|---|---|")
    for dp in sorted(close_dp_table):
        A.append("| %d | %d |" % (dp, close_dp_table[dp]))
    A.append("")
    A.append("`--close-dp %s` -> %d decimals." % (args.close_dp, close_dp))
    A.append("")
    A.append("## Fingerprints")
    A.append("")
    A.append("| file | SHA-256 |")
    A.append("|---|---|")
    A.append("| `%s` | `%s` |" % (os.path.relpath(truth_path, REPO),
                                  sha256_file(truth_path)))
    card_hash = hashlib.sha256()
    for r in sorted(truth_rows, key=lambda r: r["id"]):
        card_hash.update((r["id"] + ":" + sha256_file(
            os.path.join(out_cards, r["id"] + ".md")) + "\n").encode())
    A.append("| the %d blinded cards, combined | `%s` |"
             % (len(truth_rows), card_hash.hexdigest()))
    A.append("")
    man_path = os.path.join(args.out, "blind-manifest-%s.md" % args.label)
    with open(man_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")
    core["blinded_cards_combined_sha256"] = card_hash.hexdigest()
    with open(rec_path, "w", encoding="utf-8") as fh:
        json.dump(core, fh, indent=1, sort_keys=True)
        fh.write("\n")
    sys.stderr.write("run %s: %d blinded cards written to %s\n"
                     % (run16, len(cards), out_cards))


if __name__ == "__main__":
    main()
