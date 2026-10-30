#!/usr/bin/env python3
"""
16_identity_audit.py -- does a card tell you which coin it is, and when?

What it does
------------
Runs three fixed attacks against a folder of cards, using ONLY what an exam
candidate can see (the Before section: its bullet lines and its table), and
measures each attack against a chance line built by permutation.

  T1 · coin identification. Leave-one-out nearest neighbour over a family of
       features: is the nearest card the same coin? Chance line: the same
       measurement after the coin labels are shuffled 1,000 times.
  T2 · coin linkage. Over every pair of cards, can the distance tell a
       same-coin pair from a different-coin pair (area under the ROC curve)?
       Same chance line.
  T3 · clock-hour linkage. Do two cards print three consecutive rows that are
       identical in a given column set? Measured against the true shared-hour
       map, so it reports a detection rate and a false-positive rate.

It reports per feature family, so that a family that leaks can be named.

Input   : a folder of cards (default `cards/`), plus a truth file mapping card
          -> coin, kind, start hour. For the raw cards the truth is on the card
          itself; for a blinded set it is passed with --truth.
Output  : <out>/identity-audit.csv
          <out>/identity-audit.md
          <out>/runs/<run16>.json   (append-only)

Rules implemented
-----------------
RULES 9  : "In the exam the coin name and the date are hidden." This script
           measures whether that holds in fact, rather than assuming it.
RULES 12 : 1,000 shuffles, the boundary of the best 1%. Both numbers come from
           that rule.
RULES 19 : every number is counted; nothing is estimated.
RULES 20 : where an attack finds nothing, the attack and its inputs are still
           written down, so "no leak" is not a bare claim.
RULES 23 : the clock is read from the system.
RULES 29 / 30 : run number = SHA-256 of the inputs; records are append-only.

Constants -- where each came from
---------------------------------
SHUFFLES = 1000      RULES 12.
TOP_FRACTION = 0.01  RULES 12.
SEED = 20260913      TACTICS 1's draw number.
RUN_LEN = 3          T3 asks for three consecutive identical rows. Three is the
                     same length the canteen book's B-4 uses for "a repeated
                     value", taken from there so that no new number is invented
                     here; it is the shortest run any watcher card-verified.

No threshold, score or trading rule is defined anywhere in this file.

Changes made in the second-fix run (2026-10-01), acting on exam-prep/REVIEW.md
------------------------------------------------------------------------------
The version reviewed is git commit 7735d08 (SHA-256 4c4928b8...a371); its runs
and outputs in exam-prep/identity/ are kept untouched.
  1. Repeat-structure features (REVIEW §3.2 and §3.6 item 2, criterion K-2 of
     exam-prep/second-fix/criteria-written-before-measuring.md): for every
     column printed in the before table except `h`, the number of distinct
     printed values over the 24 rows and the largest number of rows sharing
     one printed value. One family per column group, `repeat-<group>`.
     `repeat-chg` reads `chg%`, which is printed unchanged for the frozen
     book's S-1, so it is forced and stays out of `ALL-removable`; every other
     `repeat-*` family is removable and is inside it.
  2. FORCED_FAMILIES names, once, the families left out of `ALL-removable`;
     18_residual_diagnostic.py reads it from here instead of retyping it.
  3. T3 gains a bullet-line row: the US release line, exact match, the
     default "none" text excluded (REVIEW §1.1: the reviewed T3 looked at
     columns only).
  4. T4, new: release names that occur on exactly one calendar day of the
     card set, and the cards that carry one (REVIEW §3.4). It needs the truth
     file; it is a count, not an attack with a chance line.
  5. The report prints the gate rows (`ALL-removable`, both attacks) in a
     section of their own and does not say which attack decides the gate:
     that is open question JQ-R04-GATE
     (exam-prep/second-fix/juror-questions/JQ-R04-GATE.md).
  6. Outputs go to <out>/run-<run16>/ and are never overwritten (RULES 30).

Changes made in the third-fix run (2026-10-01), acting on exam-prep/REVIEW-2.md
--------------------------------------------------------------------------------
The version reviewed by REVIEW-2 has SHA-256 4dfd9fd1...7a91 (recorded in
exam-prep/review-2/FINGERPRINTS.md); its runs and outputs are kept untouched.
Criteria written before these changes were measured:
exam-prep/third-fix/criteria-written-before-measuring.md (K-5, K-6, K-7).
  7. Nearest neighbour without card-order dependence (REVIEW-2 §4.1, K-6).
     The reviewed nearest-neighbour score breaks distance ties by the lowest
     card index, so with whole-number features it is a property of the card
     numbering. That score is still computed and printed unchanged (column
     `nn_same_coin_accuracy`), and next to it:
       - `nn_tie_free`: for every card, the share of its equally-nearest other
         cards that are the same coin, averaged over cards -- the exact mean of
         the reviewed score over every tie-break; it does not depend on card
         order. Its own chance line is computed from the same 1,000 label
         shuffles (`nn_tie_free_chance_1pct`).
       - `nn_tie_low` / `nn_tie_high`: the lowest and highest value the
         reviewed score can take over all tie-breaks, and
         `cards_with_tied_nn`, the number of cards whose nearest neighbour is
         not unique.
     Where there are no ties the three scores are equal.
  8. The K-4 granularity probe joins the audit as family `granularity-close`
     (REVIEW-2 §4.2, K-5): the smallest non-zero difference between two
     printed `close` values of a card's before table, computed on the printed
     decimal text with exact decimal arithmetic -- not on parsed floats, which
     is the defect REVIEW-2 found in 25_instrument_checks.py E-3. `close` is
     not printed unchanged (it is rebased), so by K-2's rule the family is
     removable and sits inside `ALL` and `ALL-removable`.
  9. T4 also counts by the day a release falls (card start hour + the printed
     offset), not only by the day the card starts (REVIEW-2 §4.4). A name
     printed without an offset is keyed by the card's start day, as stated
     in the report. Both are within-set counts, not publication frequency.
 10. T3 strips the unit suffix of a blinded column name (`quote vol r` ->
     `quote vol`), as card_features() already did, so its `quote vol` row
     sees the ranked column on a blinded set instead of reporting it as not
     printed (SECOND-FIX §4 item 3 named this blind spot and left it).
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
from collections import defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cards  # noqa: E402

SHUFFLES = 1000
TOP_FRACTION = 0.01
SEED = 20260913
RUN_LEN = 3

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def safelog(x):
    if x is None:
        return None
    return math.log10(x) if x > 0 else None


# ---------------------------------------------------------------------------
# Features.  Every one is read off the Before section only.
# ---------------------------------------------------------------------------

def card_features(c):
    import re
    # A blinded card renames a column to say what unit it is in (`quote vol x`,
    # `taker buy% dev`). The audit must attack the same quantity whatever the
    # header says, so the suffix is stripped here.
    col = {}
    for k, v in c["cols"].items():
        col[re.sub(r" (x|r|dev)$", "", k)] = v
    b = c["bullets"]
    f = {}

    def has(name):
        return name in col

    if has("close"):
        f["price:log_median_close"] = safelog(median(col["close"]))
    if has("chg%"):
        ch = col["chg%"]
        f["volatility:mean_abs_chg"] = mean([abs(x) for x in ch])
        f["volatility:max_abs_chg"] = max(abs(x) for x in ch)
        f["volatility:sd_chg"] = sd(ch)
    if has("quote vol"):
        f["volume:log_median_vol"] = safelog(median(col["quote vol"]))
    if has("trades"):
        f["trades:log_median_trades"] = safelog(median(col["trades"]))
    if has("open int"):
        f["openint:log_median_oi"] = safelog(median(col["open int"]))
    if has("depth -1%"):
        f["depth:log_median_depth_bid"] = safelog(median(col["depth -1%"]))
    if has("depth +1%"):
        f["depth:log_median_depth_ask"] = safelog(median(col["depth +1%"]))
    for name, key in (("L/S acct", "ratio:log_median_ls_acct"),
                      ("top L/S pos", "ratio:log_median_top_ls"),
                      ("taker L/S", "ratio:log_median_taker_ls")):
        if has(name):
            f[key] = safelog(median(col[name]))
    if has("taker buy%"):
        f["takerbuy:mean"] = mean(col["taker buy%"])
        f["takerbuy:sd"] = sd(col["taker buy%"])
    if has("BTC"):
        f["btceth:mean_btc"] = mean(col["BTC"])
        f["btceth:sd_btc"] = sd(col["BTC"])
    if has("ETH"):
        f["btceth:mean_eth"] = mean(col["ETH"])
        f["btceth:sd_eth"] = sd(col["ETH"])

    # previous-7-day line
    p7 = b.get("Previous 7 days", "")
    m = re.search(r"price ([-+][\d.]+)%", p7)
    if m:
        f["p7:price_pct"] = float(m.group(1))
    m = re.search(r"high-low range ([\d.]+)%", p7)
    if m:
        f["p7:range_pct"] = float(m.group(1))
    m = re.search(r"avg hourly volume ([\d.]+[kMGB]?)", p7)
    if m:
        f["p7:log_avg_vol"] = safelog(lab_cards.parse_number(m.group(1)))
    m = re.search(r"avg hourly trades ([\d.]+[kMGB]?)", p7)
    if m:
        f["p7:log_avg_trades"] = safelog(lab_cards.parse_number(m.group(1)))

    # funding line
    fund = b.get("Funding", "")
    m = re.search(r"interval (\S+) h", fund)
    if m:
        txt = m.group(1)
        f["funding:interval_hours"] = (float(txt.split("/")[-1])
                                       if "/" in txt else float(txt))
    m = re.search(r"^(\d+) payment", fund)
    if m:
        f["funding:payment_count"] = float(m.group(1))
    rates = re.findall(r"([-+][\d.]+)%", fund)
    if rates:
        rr = [float(x) for x in rates]
        f["funding:mean_rate"] = mean(rr)
        f["funding:sd_rate"] = sd(rr) if len(rr) > 1 else 0.0
        f["funding:max_abs_rate"] = max(abs(x) for x in rr)

    # Scale-free shape of each level-carrying column. These statistics do NOT
    # change when the whole column is multiplied by a constant, so they are
    # exactly what survives a "divide by the card's own median" blinding. They
    # are in the audit so that the audit cannot be passed by a transform that
    # only hides the level.
    for name, tag in (("quote vol", "vol"), ("trades", "trades"),
                      ("open int", "oi"), ("depth -1%", "depth_bid"),
                      ("depth +1%", "depth_ask"), ("L/S acct", "ls_acct"),
                      ("top L/S pos", "top_ls"), ("taker L/S", "taker_ls")):
        if not has(name):
            continue
        xs = col[name]
        if any(x is None or x <= 0 for x in xs):
            continue
        ls = [math.log10(x) for x in xs]
        f["shape:sd_log_" + tag] = sd(ls)
        m = mean(ls)
        num = sum((ls[i] - m) * (ls[i + 1] - m) for i in range(len(ls) - 1))
        den = sum((v - m) ** 2 for v in ls)
        if den > 0:
            f["shape:acf1_log_" + tag] = num / den

    # the blinded funding renderings, so that the audit attacks them too
    m = re.search(r"all payments in this window are equal: (yes|no)", fund)
    if m:
        f["funding:all_equal"] = 1.0 if m.group(1) == "yes" else 0.0
    m = re.search(r"relative spread of the payments: ([\d.]+)", fund)
    if m:
        f["funding:rel_spread"] = float(m.group(1))
    m = re.search(r"the payment count matches the stated interval: (yes|no|"
                  r"not applicable)", fund)
    if m:
        f["funding:count_matches"] = {"yes": 1.0, "no": 0.0,
                                      "not applicable": -1.0}[m.group(1)]
    m = re.search(r"the interval changed inside this window: (yes|no)", fund)
    if m:
        f["funding:interval_changed"] = 1.0 if m.group(1) == "yes" else 0.0

    # wikipedia: presence alone, no number
    wiki = b.get("Wikipedia page views")
    f["wikipedia:present"] = (0.0 if wiki is None
                              else (0.0 if wiki.startswith("MISSING") else 1.0))

    # repeat structure of every printed column (second-fix run, K-2)
    for name in sorted(col):
        if name == "h" or name not in REPEAT_GROUP:
            continue
        vals = [repr(x) for x in col[name]]
        tag = REPEAT_GROUP[name]
        f["rep-%s:%s:distinct" % (tag, name)] = float(len(set(vals)))
        f["rep-%s:%s:maxrepeat" % (tag, name)] = float(
            max(vals.count(v) for v in set(vals)))

    # granularity of the printed `close` (third-fix run, K-5): exact decimal
    # arithmetic on the printed text, never on parsed floats
    if has("close"):
        toks = exact_before_tokens(c["path"], "close")
        vals = sorted({v for v in toks if v is not None})
        steps = [b2 - a2 for a2, b2 in zip(vals, vals[1:]) if b2 - a2 > 0]
        f["gran-close:min_step"] = float(min(steps)) if steps else 0.0
    return f


def _exact_number(tok):
    """The printed number as an exact Decimal ('122.69k' -> 122690)."""
    tok = tok.strip()
    if tok in (".", "", "-"):
        return None
    mult = {"k": Decimal(1000), "M": Decimal(10) ** 6,
            "G": Decimal(10) ** 9, "B": Decimal(10) ** 9}
    if tok[-1] in mult:
        return Decimal(tok[:-1]) * mult[tok[-1]]
    return Decimal(tok)


def exact_before_tokens(path, colname):
    """The printed values of one column of the before table, as exact
    Decimals, read from the card text itself (third-fix run, K-5)."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    i0 = lines.index("## Before")
    for i in range(i0, len(lines)):
        if lines[i].startswith("| h |"):
            head = [x.strip() for x in lines[i].strip().strip("|").split("|")]
            # a blinded header may carry a unit suffix; `close` never does
            k = head.index(colname)
            out = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                cells = [x.strip() for x in
                         lines[j].strip().strip("|").split("|")]
                out.append(_exact_number(cells[k]))
                j += 1
            if len(out) != 24:
                die("%s: before table has %d rows" % (path, len(out)))
            return out
    die("%s: no before table" % path)


# Which repeat-structure family each printed column belongs to (K-2).
REPEAT_GROUP = {"close": "close", "chg%": "chg", "quote vol": "volume",
                "trades": "trades", "taker buy%": "takerbuy",
                "open int": "openint", "L/S acct": "ratio",
                "top L/S pos": "ratio", "taker L/S": "ratio",
                "depth -1%": "depth", "depth +1%": "depth",
                "BTC": "btceth", "ETH": "btceth"}


FAMILIES = {
    "price-level": ["price:"],
    "volatility-frozen": ["volatility:"],
    "volume-level": ["volume:", "p7:log_avg_vol"],
    "trades-level": ["trades:", "p7:log_avg_trades"],
    "openint-level": ["openint:"],
    "depth-level": ["depth:"],
    "ratio-level": ["ratio:"],
    "taker-buy": ["takerbuy:"],
    "funding-line": ["funding:"],
    "wikipedia-presence": ["wikipedia:"],
    "p7-shape": ["p7:price_pct", "p7:range_pct"],
    "btc-eth": ["btceth:"],
    "shape-scale-free": ["shape:"],
    "repeat-close": ["rep-close:"],
    "repeat-chg": ["rep-chg:"],
    "repeat-volume": ["rep-volume:"],
    "repeat-trades": ["rep-trades:"],
    "repeat-takerbuy": ["rep-takerbuy:"],
    "repeat-openint": ["rep-openint:"],
    "repeat-ratio": ["rep-ratio:"],
    "repeat-depth": ["rep-depth:"],
    "repeat-btceth": ["rep-btceth:"],
    "granularity-close": ["gran-close:"],
}

# The families a blinding may NOT remove, and why (the reviewed version typed
# the first three inline; `repeat-chg` is added by K-2):
#   volatility-frozen  the frozen book's S-1 reads `chg%` at 5.00% absolute
#   funding-line       B-5, U-2 and U-3 are answered from it
#   p7-shape           TACTICS 3 puts a previous-7-day summary on the card
#   repeat-chg         it reads the same unchanged `chg%` column
FORCED_FAMILIES = ("volatility-frozen", "funding-line", "p7-shape",
                   "repeat-chg")
# "ALL" and "ALL-except-frozen" are built from the families, not typed again.


def select(feats, prefixes):
    keys = []
    for k in sorted(feats):
        for p in prefixes:
            if k.startswith(p):
                keys.append(k)
                break
    return keys


def standardise(rows, keys):
    """z-score each key across the card set; a key that is constant or absent
    on any card contributes nothing (it is dropped, and that is reported)."""
    usable = []
    for k in keys:
        vals = [r.get(k) for r in rows]
        if any(v is None for v in vals):
            continue
        s = sd(vals)
        if s is None or s == 0:
            continue
        usable.append(k)
    out = []
    stats = {}
    for k in usable:
        vals = [r[k] for r in rows]
        stats[k] = (mean(vals), sd(vals))
    for r in rows:
        out.append([(r[k] - stats[k][0]) / stats[k][1] for k in usable])
    return out, usable


def pair_distances(vecs):
    n = len(vecs)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        vi = vecs[i]
        for j in range(i + 1, n):
            vj = vecs[j]
            s = 0.0
            for a, b in zip(vi, vj):
                s += (a - b) * (a - b)
            s = math.sqrt(s)
            d[i][j] = s
            d[j][i] = s
    return d


def nearest_neighbours(dists):
    """The index of the closest other card, for every card. Ties go to the
    lower index, so the answer does not depend on iteration order. Distances
    do not change when the coin labels are shuffled, so this is computed once
    and reused for every shuffle."""
    n = len(dists)
    out = []
    for i in range(n):
        row = dists[i]
        best, bj = None, None
        for j in range(n):
            if j == i:
                continue
            if best is None or row[j] < best:
                best, bj = row[j], j
        out.append(bj)
    return out


def nn_accuracy(nn_idx, labels):
    return sum(1 for i, j in enumerate(nn_idx)
               if labels[j] == labels[i]) / len(labels)


def nearest_tie_sets(dists):
    """For every card, ALL other cards at its smallest distance (third-fix
    run, K-6). Distances do not change when labels are shuffled, so this is
    computed once."""
    n = len(dists)
    out = []
    for i in range(n):
        row = dists[i]
        best = min(row[j] for j in range(n) if j != i)
        out.append([j for j in range(n) if j != i and row[j] == best])
    return out


def nn_tie_free(tsets, labels):
    """Mean over cards of the share of equally-nearest cards that are the
    same coin: the exact average of nn_accuracy() over every tie-break, and
    independent of card order (K-6)."""
    s = 0.0
    for i, t in enumerate(tsets):
        li = labels[i]
        s += sum(1 for j in t if labels[j] == li) / len(t)
    return s / len(labels)


def nn_tie_range(tsets, labels):
    """The lowest and highest value nn_accuracy() can take over all
    tie-breaks (K-6)."""
    lo = sum(1 for i, t in enumerate(tsets)
             if all(labels[j] == labels[i] for j in t))
    hi = sum(1 for i, t in enumerate(tsets)
             if any(labels[j] == labels[i] for j in t))
    return lo / len(labels), hi / len(labels)


def pair_ranks(dists):
    """Average rank of every pair distance, smallest first. Ranks do not
    change when the labels are shuffled."""
    n = len(dists)
    flat = []
    for i in range(n):
        for j in range(i + 1, n):
            flat.append((dists[i][j], i, j))
    flat.sort()
    rank = [[0.0] * n for _ in range(n)]
    i = 0
    r = 1
    while i < len(flat):
        j = i
        while j + 1 < len(flat) and flat[j + 1][0] == flat[i][0]:
            j += 1
        avg = (r + (r + (j - i))) / 2.0
        for k in range(i, j + 1):
            _, a, b = flat[k]
            rank[a][b] = avg
            rank[b][a] = avg
        r += (j - i + 1)
        i = j + 1
    return rank, len(flat)


def pair_auc(rank, total_pairs, labels):
    """AUC for 'small distance means same coin'. 0.5 is no information."""
    groups = defaultdict(list)
    for i, l in enumerate(labels):
        groups[l].append(i)
    rsum = 0.0
    n1 = 0
    for g in groups.values():
        for a in range(len(g)):
            ra = rank[g[a]]
            for b in range(a + 1, len(g)):
                rsum += ra[g[b]]
                n1 += 1
    n0 = total_pairs - n1
    if n1 == 0 or n0 == 0:
        return None
    u = rsum - n1 * (n1 + 1) / 2.0
    return 1.0 - u / (n1 * n0)


def quantile_top(values, fraction):
    s = sorted(values, reverse=True)
    return s[max(0, int(round(fraction * len(s))) - 1)]


# ---------------------------------------------------------------------------
# T3 -- clock-hour linkage from repeated rows
# ---------------------------------------------------------------------------

def run_fingerprints(c, colnames):
    # third-fix run: a blinded card prints a ranked column as e.g.
    # `quote vol r`; the suffix is stripped as card_features() does, so T3
    # sees the column (SECOND-FIX §4 item 3 named this blind spot)
    col = {re.sub(r" (x|r|dev)$", "", k): v for k, v in c["cols"].items()}
    if any(cn not in col for cn in colnames):
        return set()
    n = len(col["h"])
    out = set()
    for i in range(n - RUN_LEN + 1):
        key = tuple(tuple(col[cn][i + k] for cn in colnames)
                    for k in range(RUN_LEN))
        out.add(key)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=os.path.join(REPO, "cards"))
    ap.add_argument("--truth", default=None,
                    help="CSV id,coin,kind,start_hour_utc; default: read the "
                         "coin and hour off the cards themselves")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", required=True,
                    help="a name for this card set, written into the report")
    args = ap.parse_args()

    started = dt.datetime.now(dt.timezone.utc)
    free_bytes = shutil.disk_usage(REPO).free

    names = sorted(f for f in os.listdir(args.cards) if f.endswith(".md")
                   and f != "INDEX.md")
    cards = [lab_cards.parse_any_card(os.path.join(args.cards, n))
             for n in names]
    if not cards:
        die("no cards in %s" % args.cards)

    truth = {}
    if args.truth:
        with open(args.truth, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                truth[row["id"]] = row
    for c in cards:
        t = truth.get(c["card"])
        if t:
            c["coin"] = t["coin"]
            c["start_hour_utc"] = t["start_hour_utc"]
            c["kind"] = t.get("kind")
        if not c["coin"] or not c["start_hour_utc"]:
            die("no truth (coin / start hour) for %s; pass --truth"
                % c["card"])

    coins = [c["coin"] for c in cards]
    feats = [card_features(c) for c in cards]
    allkeys = sorted({k for f in feats for k in f})

    # ---- run number --------------------------------------------------------
    script_sha = sha256_file(os.path.abspath(__file__))
    h = hashlib.sha256()
    h.update(("script:" + script_sha + "\n").encode())
    h.update(("module:" + sha256_file(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "lab_cards.py")) + "\n").encode())
    h.update(("shuffles:%d;top:%s;seed:%d;runlen:%d\n"
              % (SHUFFLES, TOP_FRACTION, SEED, RUN_LEN)).encode())
    if args.truth:
        h.update(("truth:" + sha256_file(args.truth) + "\n").encode())
    for c in cards:
        h.update(("%s:%s\n" % (c["card"], c["sha256"])).encode())
    run_full = h.hexdigest()
    run16 = run_full[:16]

    # ---- T1 / T2 per family ------------------------------------------------
    fam_specs = list(FAMILIES.items())
    fam_specs.append(("ALL", sorted({p for v in FAMILIES.values()
                                     for p in v})))
    fam_specs.append(("ALL-except-frozen-volatility",
                      sorted({p for k, v in FAMILIES.items()
                              if k != "volatility-frozen" for p in v})))
    # Everything that a blinding COULD still remove: the three families left
    # out here are forced to stay on the card -- `volatility-frozen` because
    # the frozen canteen book's S-1 reads `chg%` at 5.00% absolute (RULES 6),
    # `funding-line` because B-5, U-2 and U-3 are answered from it, and
    # `p7-shape` because TACTICS 3 puts a previous-7-day summary on the card.
    fam_specs.append(("ALL-removable",
                      sorted({p for k, v in FAMILIES.items()
                              if k not in FORCED_FAMILIES
                              for p in v})))

    rows = []
    for fam, prefixes in fam_specs:
        keys = select({k: 1 for k in allkeys}, prefixes)
        vecs, used = standardise(feats, keys)
        if not used:
            rows.append({
                "card_set": args.label, "test": "T1+T2", "family": fam,
                "features_used": 0, "feature_names": "",
                "cards": len(cards),
                "nn_same_coin_accuracy": "", "nn_chance_1pct": "",
                "nn_beats_chance": "no features left after blinding",
                "pair_auc": "", "auc_chance_1pct": "",
                "auc_beats_chance": "no features left after blinding",
                "cards_with_tied_nn": "", "nn_tie_low": "",
                "nn_tie_high": "", "nn_tie_free": "",
                "nn_tie_free_chance_1pct": "",
                "nn_tie_free_beats_chance":
                    "no features left after blinding"})
            continue
        dists = pair_distances(vecs)
        nn_idx = nearest_neighbours(dists)
        tsets = nearest_tie_sets(dists)
        rank, total_pairs = pair_ranks(dists)
        obs_nn = nn_accuracy(nn_idx, coins)
        obs_tf = nn_tie_free(tsets, coins)
        tie_lo, tie_hi = nn_tie_range(tsets, coins)
        obs_auc = pair_auc(rank, total_pairs, coins)
        rng = random.Random(SEED)
        perm = list(coins)
        null_nn, null_auc, null_tf = [], [], []
        for _ in range(SHUFFLES):
            rng.shuffle(perm)
            null_nn.append(nn_accuracy(nn_idx, perm))
            null_auc.append(pair_auc(rank, total_pairs, perm))
            null_tf.append(nn_tie_free(tsets, perm))
        nn_line = quantile_top(null_nn, TOP_FRACTION)
        auc_line = quantile_top(null_auc, TOP_FRACTION)
        tf_line = quantile_top(null_tf, TOP_FRACTION)
        rows.append({
            "card_set": args.label, "test": "T1+T2", "family": fam,
            "features_used": len(used), "feature_names": " ".join(used),
            "cards": len(cards),
            "nn_same_coin_accuracy": round(obs_nn, 6),
            "nn_chance_1pct": round(nn_line, 6),
            "nn_beats_chance": "YES" if obs_nn > nn_line else "no",
            "pair_auc": round(obs_auc, 6),
            "auc_chance_1pct": round(auc_line, 6),
            "auc_beats_chance": "YES" if obs_auc > auc_line else "no",
            "cards_with_tied_nn": sum(1 for t in tsets if len(t) > 1),
            "nn_tie_low": round(tie_lo, 6),
            "nn_tie_high": round(tie_hi, 6),
            "nn_tie_free": round(obs_tf, 6),
            "nn_tie_free_chance_1pct": round(tf_line, 6),
            "nn_tie_free_beats_chance": "YES" if obs_tf > tf_line else "no"})

    # ---- T3 ----------------------------------------------------------------
    def hourset(c):
        s = c["start_hour_utc"].replace("Z", "")
        if len(s) == 16:
            s += ":00"
        t0 = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        return t0

    t0s = [hourset(c) for c in cards]
    t3_rows = []
    for colset in (["BTC", "ETH"], ["chg%"], ["close"], ["quote vol"]):
        fps = [run_fingerprints(c, colset) for c in cards]
        if all(not f for f in fps):
            t3_rows.append({"card_set": args.label, "test": "T3",
                            "columns": "+".join(colset),
                            "pairs": 0, "truly_sharing_hours": 0,
                            "detected_of_those": 0, "detection_rate": "",
                            "false_positives": 0, "false_positive_rate": "",
                            "note": "column(s) not printed on this card set"})
            continue
        n = len(cards)
        shar = det = fp = nonshar = 0
        for i in range(n):
            for j in range(i + 1, n):
                gap = abs((t0s[i] - t0s[j]).total_seconds()) / 3600.0
                shares = gap <= 47
                hit = bool(fps[i] & fps[j])
                if shares:
                    shar += 1
                    det += 1 if hit else 0
                else:
                    nonshar += 1
                    fp += 1 if hit else 0
        t3_rows.append({"card_set": args.label, "test": "T3",
                        "columns": "+".join(colset),
                        "pairs": n * (n - 1) // 2,
                        "truly_sharing_hours": shar,
                        "detected_of_those": det,
                        "detection_rate": round(det / shar, 6) if shar else "",
                        "false_positives": fp,
                        "false_positive_rate": (round(fp / nonshar, 6)
                                                if nonshar else ""),
                        "note": "%d consecutive identical rows" % RUN_LEN})

    # ---- T3 on a bullet line: the US release line (second-fix run) -------
    NONE_REL = "none in these hours."
    rel = [c["bullets"].get("US releases", "") for c in cards]
    n = len(cards)
    shar = det = fp = nonshar = 0
    for i in range(n):
        for j in range(i + 1, n):
            gap = abs((t0s[i] - t0s[j]).total_seconds()) / 3600.0
            hit = rel[i] == rel[j] and rel[i] not in (NONE_REL, "")
            if gap <= 47:
                shar += 1
                det += 1 if hit else 0
            else:
                nonshar += 1
                fp += 1 if hit else 0
    t3_rows.append({"card_set": args.label, "test": "T3",
                    "columns": "bullet:US releases",
                    "pairs": n * (n - 1) // 2, "truly_sharing_hours": shar,
                    "detected_of_those": det,
                    "detection_rate": round(det / shar, 6) if shar else "",
                    "false_positives": fp,
                    "false_positive_rate": (round(fp / nonshar, 6)
                                            if nonshar else ""),
                    "note": "the whole bullet text identical, the default "
                            "'none' text excluded"})

    # ---- T4: release names that sit on one calendar day of this set -------
    names_by_card = []
    for txt in rel:
        if txt in (NONE_REL, ""):
            names_by_card.append([])
            continue
        names_by_card.append([re.sub(r"\s*\((?:[-+]\d+ h|the calendar "
                                     r"publishes no clock time)\)$", "",
                                     p.strip()) for p in txt.split(";")])
    days = defaultdict(set)
    for c, nm in zip(cards, names_by_card):
        for x in nm:
            days[x].add(c["start_hour_utc"][:10])
    one_day = sorted(x for x, d in days.items() if len(d) == 1)
    # third-fix run (REVIEW-2 §4.4): the same count by the day the release
    # falls, card start hour + printed offset. A name printed without an
    # offset is keyed by ("no offset", the card's start day).
    rdays = defaultdict(set)
    for c, txt in zip(cards, rel):
        if txt in (NONE_REL, ""):
            continue
        t0 = hourset(c)
        for p in txt.split(";"):
            p = p.strip()
            mo = re.search(r"\(([-+]\d+) h\)$", p)
            x = re.sub(r"\s*\((?:[-+]\d+ h|the calendar publishes no clock "
                       r"time)\)$", "", p)
            if mo:
                rdays[x].add((t0 + dt.timedelta(hours=int(mo.group(1))))
                             .strftime("%Y-%m-%d"))
            else:
                rdays[x].add("no offset " + c["start_hour_utc"][:10])
    one_rday = sorted(x for x, d in rdays.items() if len(d) == 1)
    t4 = {"cards_printing_a_release_name":
              sum(1 for nm in names_by_card if nm),
          "distinct_release_names": len(days),
          "names_on_exactly_one_calendar_day_of_this_set": one_day,
          "cards_carrying_such_a_name":
              sum(1 for nm in names_by_card if any(x in one_day for x in nm)),
          "names_on_exactly_one_release_day_of_this_set": one_rday,
          "cards_carrying_such_a_name_by_release_day":
              sum(1 for nm in names_by_card
                  if any(x in one_rday for x in nm))}

    # ---- write (RULES 30: a run directory is written once) ----------------
    import io

    def csv_text(rr):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rr[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rr)
        return buf.getvalue()

    run_dir = os.path.join(args.out, "run-" + run16)
    runs_dir = os.path.join(args.out, "runs")
    csv_name = "identity-audit-%s.csv" % args.label
    t3_name = "hour-linkage-%s.csv" % args.label
    data = {csv_name: csv_text(rows), t3_name: csv_text(t3_rows)}
    data_sha = {k: hashlib.sha256(v.encode("utf-8")).hexdigest()
                for k, v in data.items()}
    core = {"run": run16, "input_fingerprint": run_full,
            "card_set": args.label, "cards": len(cards),
            "shuffles": SHUFFLES, "seed": SEED, "top_fraction": TOP_FRACTION,
            "families_leaking":
                sorted(r["family"] for r in rows
                       if r["auc_beats_chance"] == "YES"),
            "families_leaking_nn":
                sorted(r["family"] for r in rows
                       if r["nn_beats_chance"] == "YES"),
            "families_leaking_nn_tie_free":
                sorted(r["family"] for r in rows
                       if r["nn_tie_free_beats_chance"] == "YES"),
            "forced_families": list(FORCED_FAMILIES),
            "t4_release_names": t4,
            "output_sha256": data_sha,
            "output_dir": os.path.relpath(run_dir, REPO),
            "script_sha256": script_sha}
    rec_path = os.path.join(runs_dir, run16 + ".json")
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as fh:
            old = json.load(fh)
        differ = [k for k, v in json.loads(json.dumps(core)).items()
                  if old.get(k) != v]
        if differ:
            die("run record %s exists and disagrees on %s (RULES 30)"
                % (rec_path, ", ".join(sorted(differ))))
        sys.stderr.write("run %s already recorded with identical results; "
                         "nothing written\n" % run16)
        return
    for name in data:
        pth = os.path.join(run_dir, name)
        if os.path.exists(pth) and sha256_file(pth) != data_sha[name]:
            die("%s exists with different content (RULES 30)" % pth)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)
    for name, text in data.items():
        with open(os.path.join(run_dir, name), "w", encoding="utf-8",
                  newline="") as fh:
            fh.write(text)
    csv_path = os.path.join(run_dir, csv_name)
    t3_path = os.path.join(run_dir, t3_name)

    A = []
    A.append("# Identity audit — card set `%s`" % args.label)
    A.append("")
    A.append("Written by `scripts/16_identity_audit.py`. It attacks the cards "
             "with what an exam candidate can see and measures the result "
             "against a permutation chance line. It applies no rule and "
             "proposes no fix.")
    A.append("")
    A.append("| field | value |")
    A.append("|---|---|")
    A.append("| run number (RULES 29) | `%s` |" % run16)
    A.append("| full input fingerprint | `%s` |" % run_full)
    A.append("| written at (system clock, UTC, RULES 23) | %s |"
             % started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    A.append("| free disk space at start (bytes) | %d |" % free_bytes)
    A.append("| card folder | `%s` |" % os.path.relpath(args.cards, REPO))
    A.append("| cards | %d |" % len(cards))
    A.append("| distinct coins | %d |" % len(set(coins)))
    A.append("| shuffles (RULES 12) | %d |" % SHUFFLES)
    A.append("| boundary (RULES 12) | best %s%% |" % (TOP_FRACTION * 100))
    A.append("| seed (TACTICS 1 draw number) | `%d` |" % SEED)
    A.append("| `scripts/16_identity_audit.py` SHA-256 | `%s` |" % script_sha)
    A.append("")
    A.append("## T1 and T2 — does the card say which coin it is?")
    A.append("")
    A.append("`nearest-neighbour` = leave one card out, find the closest other "
             "card in this family's features, ask whether it is the same coin. "
             "`pair AUC` = over all %d pairs, how well the distance separates "
             "a same-coin pair from a different-coin pair; 0.5 is no "
             "information. Both chance lines are the boundary of the best 1%% "
             "of %d coin-label shuffles."
             % (len(cards) * (len(cards) - 1) // 2, SHUFFLES))
    A.append("")
    A.append("| feature family | features | nearest-neighbour same-coin | "
             "chance line | beats chance | pair AUC | chance line | beats "
             "chance |")
    A.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        A.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |"
                 % (r["family"], r["features_used"],
                    r["nn_same_coin_accuracy"], r["nn_chance_1pct"],
                    r["nn_beats_chance"], r["pair_auc"],
                    r["auc_chance_1pct"], r["auc_beats_chance"]))
    A.append("")
    A.append("### Nearest neighbour and tied distances (third-fix run)")
    A.append("")
    A.append("The nearest-neighbour score above breaks a distance tie by the "
             "lowest card index, so where features tie it depends on how the "
             "cards are numbered (REVIEW-2 §4.1). `tie range` is the lowest "
             "and highest value that score can take over every tie-break; "
             "`tie-free` is its exact mean over every tie-break, which does "
             "not depend on card order, with its own chance line from the "
             "same %d shuffles. Where no card has a tied nearest neighbour "
             "the three agree." % SHUFFLES)
    A.append("")
    A.append("| feature family | cards with a tied nearest neighbour | "
             "nearest-neighbour (index tie-break) | tie range | tie-free | "
             "chance line | beats chance |")
    A.append("|---|---|---|---|---|---|---|")
    for r in rows:
        if r["features_used"] == 0:
            A.append("| `%s` | | | | | | %s |" % (r["family"],
                                                 r["nn_tie_free_beats_chance"]))
            continue
        A.append("| `%s` | %s | %s | %s – %s | %s | %s | %s |"
                 % (r["family"], r["cards_with_tied_nn"],
                    r["nn_same_coin_accuracy"], r["nn_tie_low"],
                    r["nn_tie_high"], r["nn_tie_free"],
                    r["nn_tie_free_chance_1pct"],
                    r["nn_tie_free_beats_chance"]))
    A.append("")
    A.append("## The gate rows — `ALL-removable`, both attacks")
    A.append("")
    A.append("`ALL-removable` is every family except the forced ones (%s). "
             "Both attacks are printed. **This report does not say which of "
             "them decides the acceptance gate**; that is open question "
             "JQ-R04-GATE (`exam-prep/third-fix/juror-questions/"
             "JQ-R04-GATE.md`)." % ", ".join("`%s`" % f
                                              for f in FORCED_FAMILIES))
    A.append("")
    A.append("| attack | observed | chance line (best 1%) | beats it |")
    A.append("|---|---|---|---|")
    for r in rows:
        if r["family"] == "ALL-removable":
            A.append("| nearest-neighbour same-coin | %s | %s | %s |"
                     % (r["nn_same_coin_accuracy"], r["nn_chance_1pct"],
                        r["nn_beats_chance"]))
            A.append("| nearest-neighbour same-coin, tie-free (%s cards with "
                     "a tied nearest neighbour) | %s | %s | %s |"
                     % (r["cards_with_tied_nn"], r["nn_tie_free"],
                        r["nn_tie_free_chance_1pct"],
                        r["nn_tie_free_beats_chance"]))
            A.append("| pair AUC | %s | %s | %s |"
                     % (r["pair_auc"], r["auc_chance_1pct"],
                        r["auc_beats_chance"]))
    A.append("")
    A.append("## T3 — does the card say which clock hours it covers?")
    A.append("")
    A.append("Two cards are \"detected\" as covering the same hours when they "
             "print %d consecutive rows that are identical in the named "
             "column(s). The truth is the start hours: two cards share a clock "
             "hour when their 48-hour spans intersect (the relation "
             "`14_overlap_map.py` measured)." % RUN_LEN)
    A.append("")
    A.append("| columns used | pairs | truly sharing an hour | detected | "
             "detection rate | false positives | false-positive rate | note |")
    A.append("|---|---|---|---|---|---|---|---|")
    for r in t3_rows:
        A.append("| `%s` | %d | %d | %d | %s | %d | %s | %s |"
                 % (r["columns"], r["pairs"], r["truly_sharing_hours"],
                    r["detected_of_those"], r["detection_rate"],
                    r["false_positives"], r["false_positive_rate"],
                    r["note"]))
    A.append("")
    A.append("## T4 — release names that sit on one calendar day of this set")
    A.append("")
    A.append("A count, not an attack: a release that a reader can date from "
             "public knowledge dates the card that prints it (REVIEW §3.4). "
             "Computed against the truth file.")
    A.append("")
    A.append("| quantity | count |")
    A.append("|---|---|")
    A.append("| cards printing at least one release name | %d of %d |"
             % (t4["cards_printing_a_release_name"], len(cards)))
    A.append("| distinct release names | %d |" % t4["distinct_release_names"])
    A.append("| names that occur on exactly one calendar day of this set | "
             "%d |" % len(one_day))
    A.append("| cards carrying such a name | %d |"
             % t4["cards_carrying_such_a_name"])
    A.append("| names that fall on exactly one release day of this set "
             "(card start hour + printed offset; a name printed without an "
             "offset is keyed by the card's start day) | %d |"
             % len(one_rday))
    A.append("| cards carrying such a name | %d |"
             % t4["cards_carrying_such_a_name_by_release_day"])
    A.append("")
    A.append("The first two rows of counts above are by the day the card "
             "starts (the second-fix definition); the last two by the day the "
             "release falls (third-fix). Both measure uniqueness **within this "
             "card set**, not how often a release is published.")
    A.append("")
    A.append("## Fingerprints")
    A.append("")
    A.append("| file | SHA-256 |")
    A.append("|---|---|")
    for p in (csv_path, t3_path):
        A.append("| `%s` | `%s` |" % (os.path.relpath(p, REPO),
                                      sha256_file(p)))
    A.append("")
    md_path = os.path.join(run_dir, "identity-audit-%s.md" % args.label)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")
    with open(rec_path, "w", encoding="utf-8") as fh:
        json.dump(core, fh, indent=1, sort_keys=True)
        fh.write("\n")
    sys.stderr.write("run %s: %d cards, %d families\n"
                     % (run16, len(cards), len(rows)))


if __name__ == "__main__":
    main()
