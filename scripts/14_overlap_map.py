#!/usr/bin/env python3
"""
14_overlap_map.py -- the overlap map of the 306 observation cards.

What it does : For every card in cards/ it establishes the clock hours its
               *before* window covers and the clock hours its *after* window
               covers, then finds every pair of cards whose covered hours
               intersect, every group of three or more cards that share a
               common clock hour, and the connected components of the pair
               graph. It then cross-checks the map against the BTC and ETH
               columns printed on the cards themselves.

Input        : cards/C001.md .. cards/C306.md   (card's own data)
               cards/INDEX.md                   (third source for coin/kind/hour)
               data/moments/moments.csv         (moment list)
Output       : data/overlap/pairs.csv
               data/overlap/groups.csv
               data/overlap/cross-check-mismatches.csv
               data/overlap/overlap-manifest.md
               data/overlap/runs/<run16>.json   (append-only run record)

Rules implemented
-----------------
RULES 13 / TACTICS 7 : "Moments occurring in several coins in the same hour
                        count as a single event." This script does not apply
                        that rule -- it measures which cards share hours, so
                        that the rule *can* be applied. It draws no conclusion.
RULES 19 : every number written here is counted from the files, none estimated.
RULES 23 : the clock is read from the system, never guessed.
RULES 29 : the run number is the SHA-256 of the inputs.
RULES 30 : the run record is append-only; different content under an existing
           run number stops the script.
RULES 28 : no download happens here, so no disk check is required; free space
           is still recorded.

Definitions -- all of them come from the card text, not from judgement
----------------------------------------------------------------------
Each card prints:  "sections | before = the 24 h ending at the start hour ·
                    after = the 24 h from it"
and numbers its rows h = -24..-1 (before) and h = +0..+23 (after).
Row h therefore carries the clock hour  t0 + h  hours, where t0 is the card's
printed start hour. Hence

    BEFORE_OFFSETS = -24 .. -1   -> clock hours [t0-24h , t0-1h]
    AFTER_OFFSETS  =  +0 .. +23  -> clock hours [t0     , t0+23h]
    card span      = 48 consecutive clock hours, [t0-24h , t0+23h]

"Share a clock hour" means: the two 48-hour spans have at least one hour in
common. An hour is identified by its UTC hour stamp, the same stamp the card
row carries.

No threshold and no score is used anywhere in this script. Randomness appears
in exactly one place -- the negative control of the cross-check, which draws
pairs of *different* clock hours to measure how often two different hours
happen to print the same BTC value. Its seed is `20260913`, the draw number
written in TACTICS 1; it is not a number chosen here.
"""

import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import sys
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Constants.  Every one of these is read off the cards, not chosen here.
# ---------------------------------------------------------------------------

# Row offsets, as printed in the card tables (verified per card at parse time).
BEFORE_OFFSETS = tuple(range(-24, 0))     # from the card's "## Before" table
AFTER_OFFSETS = tuple(range(0, 24))       # from the card's "## After" table
HOURS_PER_WINDOW = 24                     # len of each of the two tables
CARD_SPAN_HOURS = len(BEFORE_OFFSETS) + len(AFTER_OFFSETS)   # = 48

# Column positions inside a card data row, from the single table header that
# all 612 tables share:
# | h | close | chg% | quote vol | trades | taker buy% | open int | L/S acct |
# | top L/S pos | taker L/S | depth -1% | depth +1% | BTC | ETH |
COL_H = 0
COL_BTC = 12
COL_ETH = 13
N_COLS = 14

EXPECTED_CARDS = 306          # cards/INDEX.md, "cards written | 306"

# Negative control of the cross-check.  Seed: TACTICS 1, "Draw number:
# 20260913. Written before the draw; it does not change."  Sample size is a
# plain count of draws, not a threshold: nothing is compared against it.
CONTROL_SEED = 20260913
CONTROL_DRAWS = 100000

REPO = os.path.dirname(os.path.abspath(os.path.dirname(__file__)))
CARDS_DIR = os.path.join(REPO, "cards")
MOMENTS_CSV = os.path.join(REPO, "data", "moments", "moments.csv")
INDEX_MD = os.path.join(CARDS_DIR, "INDEX.md")
OUT_DIR = os.path.join(REPO, "data", "overlap")
RUNS_DIR = os.path.join(OUT_DIR, "runs")

TABLE_HEADER = ("| h | close | chg% | quote vol | trades | taker buy% | "
                "open int | L/S acct | top L/S pos | taker L/S | depth -1% | "
                "depth +1% | BTC | ETH |")


def die(msg):
    sys.stderr.write("STOP: %s\n" % msg)
    sys.exit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def parse_hour(s):
    """'2026-05-07 20:00' or '2026-05-07T20:00Z' -> aware UTC datetime."""
    s = s.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})Z?$", s)
    if not m:
        die("unparseable hour stamp %r" % s)
    y, mo, d, hh, mi = (int(x) for x in m.groups())
    if mi != 0:
        die("start hour %r is not on the hour" % s)
    return dt.datetime(y, mo, d, hh, tzinfo=dt.timezone.utc)


def fmt_hour(t):
    return t.strftime("%Y-%m-%dT%H:00Z")


# ---------------------------------------------------------------------------
# 1. Parse the cards
# ---------------------------------------------------------------------------

ROW_RE = re.compile(r"^\|\s*([+-]?\d+)\s*\|")


def parse_card(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    card_no = os.path.basename(path)[:-3]

    m = re.search(r"^\| coin \| `([A-Z0-9]+)` \|$", text, re.M)
    if not m:
        die("%s: no coin line" % card_no)
    coin = m.group(1)

    m = re.search(r"^\| start hour \(UTC\) \| ([0-9: \-]+) \|$", text, re.M)
    if not m:
        die("%s: no start hour line" % card_no)
    t0 = parse_hour(m.group(1))

    m = re.search(r"^- \*\*Moment kind:\*\* (\w+)$", text, re.M)
    if not m:
        die("%s: no moment kind line" % card_no)
    kind = m.group(1)

    # split into the two sections
    if text.count("\n## Before\n") != 1 or text.count("\n## After\n") != 1:
        die("%s: expected exactly one '## Before' and one '## After'" % card_no)
    _, rest = text.split("\n## Before\n", 1)
    before_txt, after_txt = rest.split("\n## After\n", 1)
    if "\n## Fields not on this card" in after_txt:
        after_txt = after_txt.split("\n## Fields not on this card", 1)[0]

    def rows(section, label):
        if TABLE_HEADER not in section:
            die("%s: %s table header differs from the shared header" %
                (card_no, label))
        out = []
        for line in section.splitlines():
            if not ROW_RE.match(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != N_COLS:
                die("%s: %s row has %d cells, expected %d: %r"
                    % (card_no, label, len(cells), N_COLS, line))
            out.append(cells)
        return out

    b_rows = rows(before_txt, "before")
    a_rows = rows(after_txt, "after")

    if [int(r[COL_H]) for r in b_rows] != list(BEFORE_OFFSETS):
        die("%s: before offsets are not %s" % (card_no, list(BEFORE_OFFSETS)))
    if [int(r[COL_H]) for r in a_rows] != list(AFTER_OFFSETS):
        die("%s: after offsets are not %s" % (card_no, list(AFTER_OFFSETS)))

    hours = {}          # clock hour -> ("before"/"after", btc, eth)
    for off, r in zip(BEFORE_OFFSETS, b_rows):
        hours[t0 + dt.timedelta(hours=off)] = ("before", r[COL_BTC], r[COL_ETH])
    for off, r in zip(AFTER_OFFSETS, a_rows):
        t = t0 + dt.timedelta(hours=off)
        if t in hours:
            die("%s: hour %s appears in both sections" % (card_no, fmt_hour(t)))
        hours[t] = ("after", r[COL_BTC], r[COL_ETH])
    if len(hours) != CARD_SPAN_HOURS:
        die("%s: span is %d hours, expected %d" % (card_no, len(hours),
                                                   CARD_SPAN_HOURS))

    return {
        "card": card_no,
        "coin": coin,
        "kind": kind,
        "t0": t0,
        "lo": t0 + dt.timedelta(hours=BEFORE_OFFSETS[0]),
        "hi": t0 + dt.timedelta(hours=AFTER_OFFSETS[-1]),
        "hours": hours,
        "sha256": sha256_file(path),
    }


def main():
    started = dt.datetime.now(dt.timezone.utc)          # RULES 23
    free_bytes = shutil.disk_usage(REPO).free           # RULES 28

    card_paths = sorted(
        os.path.join(CARDS_DIR, f)
        for f in os.listdir(CARDS_DIR)
        if re.fullmatch(r"C\d{3}\.md", f)
    )
    if len(card_paths) != EXPECTED_CARDS:
        die("found %d card files, cards/INDEX.md says %d"
            % (len(card_paths), EXPECTED_CARDS))

    cards = [parse_card(p) for p in card_paths]
    by_no = {c["card"]: c for c in cards}

    # -----------------------------------------------------------------------
    # 2. Agreement check: card text vs moments.csv vs cards/INDEX.md
    # -----------------------------------------------------------------------
    with open(MOMENTS_CSV, newline="", encoding="utf-8") as fh:
        moments = list(csv.DictReader(fh))
    # cards/INDEX.md: "Moments are read from data/moments/moments.csv, whose
    # rows are sorted by (symbol, start hour, kind). The card number is the
    # 1-based position in that order."
    moments_sorted = sorted(
        moments, key=lambda r: (r["symbol"], r["start_hour_utc"], r["kind"]))

    idx_rows = {}
    with open(INDEX_MD, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(
                r"^\| `(C\d{3})` \| ([A-Z0-9]+) \| (\w+) \| "
                r"([0-9\- :]+) \| `([0-9a-f]{64})` \|$", line.strip())
            if m:
                idx_rows[m.group(1)] = (m.group(2), m.group(3),
                                        parse_hour(m.group(4)), m.group(5))

    agree = {"card_vs_moments": 0, "card_vs_index": 0}
    disagree = []
    for i, mrow in enumerate(moments_sorted, start=1):
        cno = "C%03d" % i
        c = by_no.get(cno)
        if c is None:
            disagree.append("%s: moment row %d has no card file" % (cno, i))
            continue
        if (c["coin"], c["kind"], c["t0"]) == (
                mrow["symbol"], mrow["kind"], parse_hour(mrow["start_hour_utc"])):
            agree["card_vs_moments"] += 1
        else:
            disagree.append(
                "%s: card says (%s,%s,%s), moments.csv row %d says (%s,%s,%s)"
                % (cno, c["coin"], c["kind"], fmt_hour(c["t0"]), i,
                   mrow["symbol"], mrow["kind"], mrow["start_hour_utc"]))
    for cno, c in by_no.items():
        ix = idx_rows.get(cno)
        if ix is None:
            disagree.append("%s: not listed in cards/INDEX.md" % cno)
            continue
        if (ix[0], ix[1], ix[2]) == (c["coin"], c["kind"], c["t0"]) \
                and ix[3] == c["sha256"]:
            agree["card_vs_index"] += 1
        else:
            disagree.append("%s: card text and cards/INDEX.md disagree" % cno)
    if disagree:
        for d in disagree:
            sys.stderr.write("DISAGREEMENT: %s\n" % d)
        die("card / moments.csv / INDEX.md do not agree; map not written")

    # -----------------------------------------------------------------------
    # 3. Run number (RULES 29): SHA-256 of the inputs plus the window definition
    # -----------------------------------------------------------------------
    # The script's own text is part of the fingerprint: RULES 29 asks that the
    # same number always yield the same result, and the result depends on the
    # code as well as on the cards. A changed script therefore gets a new run
    # number instead of colliding with an older one under RULES 30.
    window_def = ("before=t0-24h..t0-1h;after=t0..t0+23h;"
                  "span=48h;shared=span intersection")
    script_sha = sha256_file(os.path.abspath(__file__))
    h = hashlib.sha256()
    h.update(("window_def:" + window_def + "\n").encode())
    h.update(("script:" + script_sha + "\n").encode())
    h.update(("moments.csv:" + sha256_file(MOMENTS_CSV) + "\n").encode())
    for c in cards:
        h.update(("%s:%s\n" % (c["card"], c["sha256"])).encode())
    run_full = h.hexdigest()
    run16 = run_full[:16]

    # -----------------------------------------------------------------------
    # 4. Every pair that shares at least one clock hour
    # -----------------------------------------------------------------------
    order = sorted(cards, key=lambda c: (c["lo"], c["card"]))
    pairs = []
    mismatch_rows = []
    hours_compared = 0

    for i, a in enumerate(order):
        for b in order[i + 1:]:
            if b["lo"] > a["hi"]:
                break                      # sorted by lo -> nothing later can touch
            lo = max(a["lo"], b["lo"])
            hi = min(a["hi"], b["hi"])
            if lo > hi:
                continue
            shared = []
            t = lo
            while t <= hi:
                if t in a["hours"] and t in b["hours"]:
                    shared.append(t)
                t += dt.timedelta(hours=1)
            if not shared:
                continue

            def placement(card):
                w = {card["hours"][t][0] for t in shared}
                if w == {"before"}:
                    return "before", len(shared), 0
                if w == {"after"}:
                    return "after", 0, len(shared)
                nb = sum(1 for t in shared if card["hours"][t][0] == "before")
                return "across", nb, len(shared) - nb

            wa, a_before, a_after = placement(a)
            wb, b_before, b_after = placement(b)

            # cross-check against the BTC / ETH columns printed on both cards
            btc_mm = eth_mm = 0
            for t in shared:
                hours_compared += 1
                _, abtc, aeth = a["hours"][t]
                _, bbtc, beth = b["hours"][t]
                if abtc != bbtc:
                    btc_mm += 1
                    mismatch_rows.append([a["card"], b["card"], fmt_hour(t),
                                          "BTC", abtc, bbtc])
                if aeth != beth:
                    eth_mm += 1
                    mismatch_rows.append([a["card"], b["card"], fmt_hour(t),
                                          "ETH", aeth, beth])

            first, second = sorted((a, b), key=lambda c: c["card"])
            flip = first is b
            pairs.append({
                "card_a": first["card"], "card_b": second["card"],
                "coin_a": first["coin"], "coin_b": second["coin"],
                "kind_a": first["kind"], "kind_b": second["kind"],
                "same_coin": "yes" if a["coin"] == b["coin"] else "no",
                "shared_hours": len(shared),
                "shared_first_hour_utc": fmt_hour(shared[0]),
                "shared_last_hour_utc": fmt_hour(shared[-1]),
                "window_a": wb if flip else wa,
                "window_b": wa if flip else wb,
                "a_before_hours": b_before if flip else a_before,
                "a_after_hours": b_after if flip else a_after,
                "b_before_hours": a_before if flip else b_before,
                "b_after_hours": a_after if flip else b_after,
                "start_hour_a_utc": fmt_hour(first["t0"]),
                "start_hour_b_utc": fmt_hour(second["t0"]),
                "start_gap_hours": int(abs(
                    (second["t0"] - first["t0"]).total_seconds()) // 3600),
                "btc_mismatch_hours": btc_mm,
                "eth_mismatch_hours": eth_mm,
            })

    pairs.sort(key=lambda p: (p["card_a"], p["card_b"]))

    # -----------------------------------------------------------------------
    # 5. Groups
    #    (a) "shared-hour groups": every maximal set of cards that all cover
    #        one and the same clock hour.  Card spans are 48 contiguous hours,
    #        so a set of pairwise-overlapping cards always has a common hour
    #        (interval Helly property) -- these are the maximal cliques of the
    #        pair graph as well.
    #    (b) "chains": connected components of the pair graph, where A-B and
    #        B-C put A and C in one group even if A and C do not touch.
    # -----------------------------------------------------------------------
    hour_members = defaultdict(list)
    for c in cards:
        for t in c["hours"]:
            hour_members[t].append(c["card"])

    sets_by_hours = defaultdict(list)     # frozenset of cards -> hours
    for t, members in hour_members.items():
        if len(members) >= 2:
            sets_by_hours[frozenset(members)].append(t)

    maximal = []
    keys = sorted(sets_by_hours.keys(), key=lambda s: (-len(s), sorted(s)))
    for s in keys:
        if any(s < other for other in maximal):
            continue
        maximal.append(s)
    # a set can be covered by several different larger sets; drop the covered
    maximal = [s for s in maximal
               if not any(s < o for o in maximal if o is not s)]

    # union-find over the pair graph
    parent = {c["card"]: c["card"] for c in cards}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairs:
        ra, rb = find(p["card_a"]), find(p["card_b"])
        if ra != rb:
            parent[ra] = rb
    comps = defaultdict(list)
    for c in cards:
        comps[find(c["card"])].append(c["card"])
    chains = [sorted(v) for v in comps.values() if len(v) >= 2]

    group_rows = []
    for s in sorted(maximal, key=lambda s: (-len(s), sorted(s))):
        members = sorted(s)
        hrs = sorted(sets_by_hours[s])
        # hours covered by every member (not only those whose member set is
        # exactly s)
        common = sorted(set.intersection(*[set(by_no[m]["hours"]) for m in members]))
        group_rows.append({
            "group_id": "",
            "group_type": "shared-hour",
            "size": len(members),
            "cards": " ".join(members),
            "coins": " ".join(by_no[m]["coin"] for m in members),
            "kinds": " ".join(by_no[m]["kind"] for m in members),
            "common_hours": len(common),
            "common_first_hour_utc": fmt_hour(common[0]) if common else "",
            "common_last_hour_utc": fmt_hour(common[-1]) if common else "",
            "span_first_hour_utc": fmt_hour(min(by_no[m]["lo"] for m in members)),
            "span_last_hour_utc": fmt_hour(max(by_no[m]["hi"] for m in members)),
            "distinct_coins": len({by_no[m]["coin"] for m in members}),
            "_sortkey": hrs[0],
        })
    for members in sorted(chains, key=lambda v: (-len(v), v)):
        common = set.intersection(*[set(by_no[m]["hours"]) for m in members])
        group_rows.append({
            "group_id": "",
            "group_type": "chain",
            "size": len(members),
            "cards": " ".join(members),
            "coins": " ".join(by_no[m]["coin"] for m in members),
            "kinds": " ".join(by_no[m]["kind"] for m in members),
            "common_hours": len(common),
            "common_first_hour_utc": fmt_hour(min(common)) if common else "",
            "common_last_hour_utc": fmt_hour(max(common)) if common else "",
            "span_first_hour_utc": fmt_hour(min(by_no[m]["lo"] for m in members)),
            "span_last_hour_utc": fmt_hour(max(by_no[m]["hi"] for m in members)),
            "distinct_coins": len({by_no[m]["coin"] for m in members}),
            "_sortkey": min(by_no[m]["lo"] for m in members),
        })
    group_rows.sort(key=lambda g: (g["group_type"], -g["size"], g["_sortkey"]))
    for n, g in enumerate(group_rows, start=1):
        g["group_id"] = "G%03d" % n
        del g["_sortkey"]

    # -----------------------------------------------------------------------
    # 6. Counts (RULES 19: all counted, none estimated)
    # -----------------------------------------------------------------------
    involved = set()
    involved_cross_coin = set()
    for p in pairs:
        involved.add(p["card_a"])
        involved.add(p["card_b"])
        if p["same_coin"] == "no":
            involved_cross_coin.add(p["card_a"])
            involved_cross_coin.add(p["card_b"])
    alone = [c["card"] for c in cards if c["card"] not in involved]

    dist_all = Counter(p["shared_hours"] for p in pairs)
    dist_cross = Counter(p["shared_hours"] for p in pairs if p["same_coin"] == "no")
    dist_same = Counter(p["shared_hours"] for p in pairs if p["same_coin"] == "yes")
    win_combo = Counter((p["window_a"], p["window_b"]) for p in pairs)
    kind_combo = Counter(tuple(sorted((p["kind_a"], p["kind_b"]))) for p in pairs)

    shared_start_hours = defaultdict(list)
    for c in cards:
        shared_start_hours[c["t0"]].append(c["card"])
    same_start = {fmt_hour(t): sorted(v)
                  for t, v in shared_start_hours.items() if len(v) > 1}

    # -----------------------------------------------------------------------
    # 6b. Negative control for the cross-check: how often do two *different*
    #     clock hours print the same BTC / ETH value?  Measured, not assumed.
    # -----------------------------------------------------------------------
    hour_values = {}
    for c in cards:
        for t, (_w, btc, eth) in c["hours"].items():
            hour_values.setdefault(t, (btc, eth))
    hl = sorted(hour_values)
    rng = random.Random(CONTROL_SEED)
    ctl_btc = ctl_eth = ctl_both = 0
    for _ in range(CONTROL_DRAWS):
        i = rng.randrange(len(hl))
        j = rng.randrange(len(hl))
        while j == i:
            j = rng.randrange(len(hl))
        a_btc, a_eth = hour_values[hl[i]]
        b_btc, b_eth = hour_values[hl[j]]
        if a_btc == b_btc:
            ctl_btc += 1
        if a_eth == b_eth:
            ctl_eth += 1
        if a_btc == b_btc and a_eth == b_eth:
            ctl_both += 1

    max_clique = max((g["size"] for g in group_rows
                      if g["group_type"] == "shared-hour"), default=0)
    max_chain = max((g["size"] for g in group_rows
                     if g["group_type"] == "chain"), default=0)

    # -----------------------------------------------------------------------
    # 7. Write the outputs.
    #    RULES 30 first: if a record already sits under this run number and
    #    disagrees, stop *before* touching any output file.
    # -----------------------------------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RUNS_DIR, exist_ok=True)

    core = {
        "run": run16,
        "input_fingerprint": run_full,
        "window_def": window_def,
        "cards": len(cards),
        "pairs": len(pairs),
        "cards_in_an_overlap": len(involved),
        "cards_in_no_overlap": len(alone),
        "largest_shared_hour_group": max_clique,
        "largest_chain": max_chain,
        "shared_hours_compared": hours_compared,
        "btc_mismatch_hours": sum(p["btc_mismatch_hours"] for p in pairs),
        "eth_mismatch_hours": sum(p["eth_mismatch_hours"] for p in pairs),
        "control_seed": CONTROL_SEED,
        "control_draws": CONTROL_DRAWS,
        "control_same_btc": ctl_btc,
        "control_same_eth": ctl_eth,
        "control_same_btc_and_eth": ctl_both,
        "script_sha256": script_sha,
    }
    rec_path = os.path.join(RUNS_DIR, run16 + ".json")
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as fh:
            old_rec = json.load(fh)
        differing = [k for k, v in core.items() if old_rec.get(k) != v]
        if differing:
            die("run record %s already exists and disagrees on %s "
                "(RULES 30: records are append-only, never overwritten); "
                "no output file was touched"
                % (rec_path, ", ".join(sorted(differing))))
    prior_runs = sorted(f[:-5] for f in os.listdir(RUNS_DIR)
                        if f.endswith(".json"))
    if run16 not in prior_runs:
        prior_runs.append(run16)

    pairs_path = os.path.join(OUT_DIR, "pairs.csv")
    pair_fields = ["card_a", "card_b", "coin_a", "coin_b", "kind_a", "kind_b",
                   "same_coin", "shared_hours", "shared_first_hour_utc",
                   "shared_last_hour_utc", "window_a", "window_b",
                   "a_before_hours", "a_after_hours", "b_before_hours",
                   "b_after_hours", "start_hour_a_utc", "start_hour_b_utc",
                   "start_gap_hours", "btc_mismatch_hours", "eth_mismatch_hours"]
    with open(pairs_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=pair_fields, lineterminator="\n")
        w.writeheader()
        w.writerows(pairs)

    groups_path = os.path.join(OUT_DIR, "groups.csv")
    group_fields = ["group_id", "group_type", "size", "cards", "coins", "kinds",
                    "distinct_coins", "common_hours", "common_first_hour_utc",
                    "common_last_hour_utc", "span_first_hour_utc",
                    "span_last_hour_utc"]
    with open(groups_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=group_fields, lineterminator="\n")
        w.writeheader()
        w.writerows(group_rows)

    mm_path = os.path.join(OUT_DIR, "cross-check-mismatches.csv")
    with open(mm_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["card_a", "card_b", "clock_hour_utc", "column",
                    "value_on_card_a", "value_on_card_b"])
        w.writerows(mismatch_rows)

    def hist_md(counter):
        if not counter:
            return "_(empty)_\n"
        out = "| shared hours | pairs |\n|---|---|\n"
        for k in sorted(counter):
            out += "| %d | %d |\n" % (k, counter[k])
        return out

    manifest_path = os.path.join(OUT_DIR, "overlap-manifest.md")
    lines = []
    A = lines.append
    A("# Overlap manifest — which of the 306 cards share clock hours\n")
    A("Written by `scripts/14_overlap_map.py`. It measures the map that "
      "RULES 13 and TACTICS 7 need; it applies neither rule and draws no "
      "conclusion.\n")
    A("## Run\n")
    A("| field | value |")
    A("|---|---|")
    A("| run number (SHA-256 of the inputs, RULES 29) | `%s` |" % run16)
    A("| full input fingerprint | `%s` |" % run_full)
    A("| written at (system clock, UTC, RULES 23) | %s |"
      % started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    A("| free disk space at start (bytes) | %d |" % free_bytes)
    A("| randomness | only in the cross-check negative control; seed "
      "`%d` (TACTICS 1 draw number) |" % CONTROL_SEED)
    A("| inputs | 306 card files, `cards/INDEX.md`, `data/moments/moments.csv` |")
    A("| `data/moments/moments.csv` SHA-256 | `%s` |" % sha256_file(MOMENTS_CSV))
    A("| `scripts/14_overlap_map.py` SHA-256 (part of the run number) | `%s` |"
      % script_sha)
    A("")
    A("Run records live in `data/overlap/runs/`, one JSON file per run number, "
      "append-only (RULES 30). Records present when this manifest was written: "
      "%s. The files fingerprinted at the bottom of this manifest are the "
      "output of run `%s`; any other record is an earlier, superseded run kept "
      "for the history.\n"
      % (", ".join("`%s`" % n for n in sorted(prior_runs)) or "none", run16))
    A("## Window definition (read off the cards, not chosen here)\n")
    A("Each card prints `before = the 24 h ending at the start hour · after = "
      "the 24 h from it` and numbers its rows `-24..-1` and `+0..+23`. Row `h` "
      "therefore carries clock hour `t0 + h`.\n")
    A("| window | row offsets | clock hours |")
    A("|---|---|---|")
    A("| before | -24 .. -1 | `t0-24h` .. `t0-1h` (24 hours) |")
    A("| after | +0 .. +23 | `t0` .. `t0+23h` (24 hours) |")
    A("| card span | | 48 consecutive hours |")
    A("")
    A("Two cards *share a clock hour* when their 48-hour spans have at least "
      "one hour in common.\n")
    A("## Agreement check on the inputs\n")
    A("| check | value |")
    A("|---|---|")
    A("| cards parsed | %d |" % len(cards))
    A("| card text agrees with `moments.csv` (coin, kind, start hour) | %d / %d |"
      % (agree["card_vs_moments"], len(cards)))
    A("| card text and SHA-256 agree with `cards/INDEX.md` | %d / %d |"
      % (agree["card_vs_index"], len(cards)))
    A("| disagreements | %d |" % len(disagree))
    A("")
    A("## Counts\n")
    A("| measured | value |")
    A("|---|---|")
    A("| cards | %d |" % len(cards))
    A("| pairs sharing at least one clock hour | %d |" % len(pairs))
    A("| of those, pairs of two different coins | %d |"
      % sum(1 for p in pairs if p["same_coin"] == "no"))
    A("| of those, pairs inside one coin | %d |"
      % sum(1 for p in pairs if p["same_coin"] == "yes"))
    A("| cards taking part in at least one overlap | %d |" % len(involved))
    A("| cards taking part in no overlap | %d |" % len(alone))
    A("| cards overlapping a card of a *different* coin | %d |"
      % len(involved_cross_coin))
    A("| largest shared-hour group (cards all covering one clock hour) | %d |"
      % max_clique)
    A("| largest chain (connected component of the pair graph) | %d |" % max_chain)
    A("| shared-hour groups of size >= 2 | %d |"
      % sum(1 for g in group_rows if g["group_type"] == "shared-hour"))
    A("| shared-hour groups of size >= 3 | %d |"
      % sum(1 for g in group_rows
            if g["group_type"] == "shared-hour" and g["size"] >= 3))
    A("| chains of size >= 2 | %d |"
      % sum(1 for g in group_rows if g["group_type"] == "chain"))
    A("| chains of size >= 3 | %d |"
      % sum(1 for g in group_rows
            if g["group_type"] == "chain" and g["size"] >= 3))
    A("| distinct start hours carrying more than one card | %d |" % len(same_start))
    A("")
    A("## Distribution of overlap length, all pairs\n")
    A(hist_md(dist_all))
    A("## Distribution of overlap length, different-coin pairs\n")
    A(hist_md(dist_cross))
    A("## Distribution of overlap length, same-coin pairs\n")
    A(hist_md(dist_same))
    A("## Where the shared hours fall\n")
    A("| window on card A | window on card B | pairs |")
    A("|---|---|---|")
    for (x, y), n in sorted(win_combo.items(), key=lambda kv: (-kv[1], kv[0])):
        A("| %s | %s | %d |" % (x, y, n))
    A("")
    A("## Moment kinds in the overlapping pairs\n")
    A("| kinds | pairs |")
    A("|---|---|")
    for k, n in sorted(kind_combo.items(), key=lambda kv: (-kv[1], kv[0])):
        A("| %s + %s | %d |" % (k[0], k[1], n))
    A("")
    A("## Cross-check against the cards' own BTC and ETH columns\n")
    A("The map above is built only from the moment start hours. The cards also "
      "print a BTC and an ETH column for every hour. If two cards really cover "
      "the same clock hour, those two columns must carry the same value on "
      "both cards. Every shared hour of every pair was compared — not a "
      "sample, the whole map.\n")
    A("| check | value |")
    A("|---|---|")
    A("| pairs checked | %d |" % len(pairs))
    A("| shared hours compared | %d |" % hours_compared)
    A("| BTC values compared | %d |" % hours_compared)
    A("| ETH values compared | %d |" % hours_compared)
    A("| hours where the BTC value differed | %d |"
      % sum(p["btc_mismatch_hours"] for p in pairs))
    A("| hours where the ETH value differed | %d |"
      % sum(p["eth_mismatch_hours"] for p in pairs))
    A("| pairs with at least one differing value | %d |"
      % sum(1 for p in pairs
            if p["btc_mismatch_hours"] or p["eth_mismatch_hours"]))
    A("")
    A("Every differing value, if any, is listed in "
      "`data/overlap/cross-check-mismatches.csv`.\n")
    A("### Negative control — how much the cross-check can tell apart\n")
    A("A check that always passes proves nothing. To measure how often two "
      "*different* clock hours happen to print the same BTC value anyway, "
      "%d pairs of different clock hours were drawn at random "
      "(seed `%d`, the TACTICS 1 draw number) out of the %d distinct clock "
      "hours the cards cover, and their printed values compared.\n"
      % (CONTROL_DRAWS, CONTROL_SEED, len(hour_values)))
    A("| check | value |")
    A("|---|---|")
    A("| distinct clock hours covered by at least one card | %d |"
      % len(hour_values))
    A("| of those, covered by two or more cards | %d |"
      % sum(1 for v in hour_members.values() if len(v) >= 2))
    A("| random different-hour pairs drawn | %d |" % CONTROL_DRAWS)
    A("| of those, same BTC value | %d (%.2f%%) |"
      % (ctl_btc, 100.0 * ctl_btc / CONTROL_DRAWS))
    A("| of those, same ETH value | %d (%.2f%%) |"
      % (ctl_eth, 100.0 * ctl_eth / CONTROL_DRAWS))
    A("| of those, same BTC *and* ETH value | %d (%.2f%%) |"
      % (ctl_both, 100.0 * ctl_both / CONTROL_DRAWS))
    A("")
    A("## The cards taking part in no overlap\n")
    A("These %d cards share no clock hour with any other card.\n" % len(alone))
    A("| card | coin | kind | start hour (UTC) |")
    A("|---|---|---|---|")
    for cno in alone:
        c = by_no[cno]
        A("| `%s` | %s | %s | %s |"
          % (cno, c["coin"], c["kind"], fmt_hour(c["t0"])))
    A("")
    A("## Start hours carried by more than one card\n")
    A("```json")
    A(json.dumps(same_start, indent=1, sort_keys=True))
    A("```\n")
    A("## Fingerprints\n")
    A("| file | rows | SHA-256 |")
    A("|---|---|---|")
    manifest_text = "\n".join(lines) + "\n"

    out_files = [("data/overlap/pairs.csv", pairs_path, len(pairs)),
                 ("data/overlap/groups.csv", groups_path, len(group_rows)),
                 ("data/overlap/cross-check-mismatches.csv", mm_path,
                  len(mismatch_rows))]
    fps = {}
    tail = []
    for rel, path, n in out_files:
        s = sha256_file(path)
        fps[rel] = s
        tail.append("| `%s` | %d | `%s` |" % (rel, n, s))
    manifest_text += "\n".join(tail) + "\n"

    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write(manifest_text)
    # The manifest carries its own write time (RULES 23), so its bytes differ
    # between two runs of the same input. It is therefore fingerprinted into a
    # sidecar file rather than into the append-only run record, which must be
    # byte-identical when the input is.
    manifest_sha = sha256_file(manifest_path)
    with open(manifest_path + ".sha256", "w", encoding="utf-8") as fh:
        fh.write("%s  overlap-manifest.md\n" % manifest_sha)

    # -----------------------------------------------------------------------
    # 8. Append-only run record (RULES 30)
    # -----------------------------------------------------------------------
    record = dict(core)
    record["outputs"] = fps
    body = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as fh:
            old = fh.read()
        if old != body:
            die("run record %s already exists with different content "
                "(RULES 30: records are append-only, never overwritten)"
                % rec_path)
        sys.stderr.write("run %s already recorded, content identical\n" % run16)
    else:
        with open(rec_path, "w", encoding="utf-8") as fh:
            fh.write(body)
    record["manifest_sha256_this_run"] = manifest_sha

    print(json.dumps(record, indent=1, sort_keys=True))
    print("cards in no overlap: %s" % (" ".join(alone) if alone else "(none)"))


if __name__ == "__main__":
    main()
