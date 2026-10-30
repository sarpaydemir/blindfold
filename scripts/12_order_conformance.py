#!/usr/bin/env python3
"""
12_order_conformance.py -- check a card order against the RATIFIED requirement
                           of TACTICS 4.

What it does
------------
Takes an order file (position,card_number) and answers, test by test, yes or no,
whether that order meets the requirement ratified in
`decisions/2026-09-19-card-order-requirement/verdict.md`.

The requirement is not restated in this script's own words where it can be
quoted. The verdict's own check-list is (verdict.md, section 4):

  - Inspect the sequence: are both kinds present? If one is absent, fail.
  - Check whether the sequence matches any derived order (coin ID, timestamp,
    kind, chronology). If yes, fail (not shuffled).
  - Look for segregation: do all cards of one kind precede all of the other, or
    fall into kind-blocks? If yes, fail.
  - Check for positional rules: does the position predict the kind? (Does every
    even card, every third card, every other card, etc. match a pattern?) If
    yes, fail.

and the verdict's statement of the requirement itself reads:

  "a shuffled permutation of all cards of the 10 observation coins, with
   large-movement and calm-moment cards mixed through one sequence rather than
   segregated, and with no positional rule that allows the watcher to read a
   card's kind from its position."

How each check is made answerable without trusting this script
-------------------------------------------------------------
T0  Permutation. The multiset of card numbers in the order equals the set of
    306 card numbers derived from data/moments/moments.csv. Counted.
T1  Both kinds present. Counted.
T2  Not a derived order. The order is compared for equality against an
    enumerated list of orders derivable from card properties, each in ascending
    and in descending form (card number, chronology, coin, kind, 24h move, and
    the on-disk file listing). The list of orders tested is printed in full, so
    a reader can see exactly what was ruled out. NOTE the limit, which juror 3
    stated and the verdict did not overturn: this test can only FALSIFY
    "shuffled". It can never confirm it. Confirmation is only possible against
    the production record -- the script, its seed and its input -- not against
    the sequence.
T3  Not grouped by coin. The number of maximal runs of one coin is compared
    with the number of distinct coins. If they are equal, every coin's cards
    are contiguous, i.e. the order is a coin-by-coin grouping -> fail.
T4  Not segregated by kind. The number of maximal runs of one kind is counted.
    If it is 1 or 2 then each kind occupies one unbroken block (all of one kind
    then all of the other) -> fail. This is the cut-point test and needs no
    threshold: 2 blocks is segregation, more than 2 is not total segregation.
T5  No positional rule for the kind. For every period p from 2 to N//2, and for
    every residue r in 0..p-1, the kinds of the positions congruent to r mod p
    are collected. If for some p EVERY residue class holds only one kind, then
    the kind is a function of (position mod p): the position predicts the kind
    -> fail, and that p is printed. p stops at N//2 because above it some
    residue class holds a single card and is pure for arithmetic reasons only,
    which would make the test vacuous rather than informative.
T6  No delivery is single-kind. Only when --batches is given. The verdict
    forbids the kinds being "delivered as separate groups or streams". A batch
    is a delivery, so each batch is checked to contain both kinds. This is the
    one place where this script applies the verdict's words to an object the
    verdict does not name (a batch); it is flagged here and in the report.

Measurements that are NOT tests (no threshold exists for them, RULES 33): the
adjacent same-kind pair count, the longest same-kind run and the run-length
histogram are printed as numbers only. The verdict leaves the question of how
long a run may be explicitly unsettled, so this script does not pass or fail an
order on them.

Input
-----
  <order.csv>                  position,card_number  (header + one row per card)
  data/moments/moments.csv     card number = 1-based row position; kind; coin
  --batches <dir>              optional: batch-NN.md files, to run T6

Output
------
  A table of checks on stdout, one line per check, each ending in PASS or FAIL,
  and a final CONFORMS / DOES NOT CONFORM line. Exit status 0 if it conforms,
  2 if it does not.  --md <path> writes the same table as markdown.

Rules implemented
-----------------
  TACTICS 4  as ratified in decisions/2026-09-19-card-order-requirement/
  RULES 19   no unmeasured number written without the word "estimate"
  RULES 23   the clock is read from the system, not guessed
  RULES 30   append-only: never overwrites a file with different content

Randomness
----------
  None. This script draws nothing and uses no random number generator.
"""

import argparse
import csv
import hashlib
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS = os.path.join(ROOT, "data", "moments", "moments.csv")
CARDS_DIR = os.path.join(ROOT, "cards")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def die(msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(1)


def load_cards():
    """Card number = 1-based row position in moments.csv -- the numbering
    scheme 09_write_cards.py used for cards/INDEX.md."""
    if not os.path.exists(MOMENTS):
        die("%s not found." % MOMENTS)
    with open(MOMENTS, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    cards = []
    for i, r in enumerate(rows, start=1):
        kind = r["kind"].strip()
        if kind not in ("large", "calm"):
            die("row %d of moments.csv has kind %r." % (i, kind))
        try:
            move = float(r["move_24h_pct"])
        except (KeyError, ValueError):
            move = None
        cards.append({
            "no": "C%03d" % i,
            "coin": r["symbol"].strip(),
            "kind": kind,
            "start": r["start_hour_utc"].strip(),
            "move": move,
        })
    return cards


def load_order(path):
    if not os.path.exists(path):
        die("%s not found." % path)
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "card_number" not in rows[0]:
        die("%s has no card_number column." % path)
    seq = []
    for i, r in enumerate(rows, start=1):
        if int(r["position"]) != i:
            die("%s: row %d carries position %s." % (path, i, r["position"]))
        seq.append(r["card_number"].strip())
    return seq


def runs(seq_labels):
    """maximal runs of an equal label: returns a list of (label, length)."""
    out = []
    for lab in seq_labels:
        if out and out[-1][0] == lab:
            out[-1][1] += 1
        else:
            out.append([lab, 1])
    return [(a, b) for a, b in out]


def derived_orders(cards):
    """Every order derivable from a card property, by name. Ascending only --
    the caller also tests each one reversed."""
    by_no = {c["no"]: c for c in cards}
    nos = [c["no"] for c in cards]
    out = []

    def add(name, key):
        out.append((name, [c["no"] for c in sorted(cards, key=key)]))

    add("card number", lambda c: c["no"])
    add("start hour, then card number", lambda c: (c["start"], c["no"]))
    add("coin, then card number", lambda c: (c["coin"], c["no"]))
    add("coin, then start hour", lambda c: (c["coin"], c["start"]))
    add("kind, then card number", lambda c: (c["kind"], c["no"]))
    add("kind, then start hour", lambda c: (c["kind"], c["start"], c["no"]))
    add("kind, then coin, then card number",
        lambda c: (c["kind"], c["coin"], c["no"]))
    if all(c["move"] is not None for c in cards):
        add("24h move, signed, then card number",
            lambda c: (c["move"], c["no"]))
        add("24h move, absolute, then card number",
            lambda c: (abs(c["move"]), c["no"]))
    # the on-disk listing of cards/
    if os.path.isdir(CARDS_DIR):
        listed = [f[:-3] for f in os.listdir(CARDS_DIR)
                  if re.fullmatch(r"C\d{3}\.md", f)]
        if sorted(listed) == sorted(nos):
            out.append(("cards/ directory listing, as returned by the OS",
                        listed))
    assert by_no  # keeps the lookup referenced; every name above uses cards
    return out


def check(order, cards, batches=None):
    """Returns (rows, conforms, measurements). rows: (id, question, detail,
    verdict) with verdict in {'PASS','FAIL'}."""
    kind_of = {c["no"]: c["kind"] for c in cards}
    coin_of = {c["no"]: c["coin"] for c in cards}
    n = len(cards)
    rows = []
    meas = {}

    # ---- T0 permutation -------------------------------------------------
    ok = (len(order) == n and len(set(order)) == n
          and set(order) == set(kind_of))
    rows.append(("T0",
                 "Is the order a permutation of the %d cards -- every card "
                 "once, no card twice, no card missing?" % n,
                 "order length %d, distinct %d, card list %d, symmetric "
                 "difference %d" % (len(order), len(set(order)), n,
                                    len(set(order) ^ set(kind_of))),
                 "PASS" if ok else "FAIL"))
    if not ok:
        return rows, False, meas

    kinds = [kind_of[c] for c in order]

    # ---- T1 both kinds present ------------------------------------------
    n_large = kinds.count("large")
    n_calm = kinds.count("calm")
    ok = n_large > 0 and n_calm > 0
    rows.append(("T1", "Are both kinds present in the sequence?",
                 "large %d, calm %d" % (n_large, n_calm),
                 "PASS" if ok else "FAIL"))
    meas["n_large"], meas["n_calm"] = n_large, n_calm

    # ---- T2 not a derived order ------------------------------------------
    dos = derived_orders(cards)
    hits = []
    for name, seq in dos:
        if order == seq:
            hits.append(name + " (ascending)")
        if order == list(reversed(seq)):
            hits.append(name + " (descending)")
    ok = not hits
    rows.append(("T2",
                 "Does the order equal any order derivable from a card "
                 "property? (%d orders tested, each ascending and "
                 "descending)" % len(dos),
                 "matches: %s" % ("none" if not hits else "; ".join(hits)),
                 "PASS" if ok else "FAIL"))
    meas["derived_orders_tested"] = [nm for nm, _ in dos]

    # ---- T3 not grouped by coin ------------------------------------------
    coin_runs = runs([coin_of[c] for c in order])
    n_coins = len(set(coin_of.values()))
    ok = len(coin_runs) != n_coins
    rows.append(("T3",
                 "Is the order a coin-by-coin grouping (every coin's cards "
                 "contiguous)?",
                 "%d distinct coins, %d maximal coin runs; equal would mean "
                 "grouped" % (n_coins, len(coin_runs)),
                 "PASS" if ok else "FAIL"))
    meas["coin_runs"] = len(coin_runs)
    meas["n_coins"] = n_coins

    # ---- T4 not segregated by kind ---------------------------------------
    kind_runs = runs(kinds)
    ok = len(kind_runs) > 2
    rows.append(("T4",
                 "Do all cards of one kind precede all of the other, i.e. does "
                 "the sequence fall into one block per kind?",
                 "%d maximal kind runs; 1 or 2 would mean one block per kind"
                 % len(kind_runs),
                 "PASS" if ok else "FAIL"))
    meas["kind_runs"] = len(kind_runs)

    # ---- T5 no positional rule -------------------------------------------
    bad_p = []
    for p in range(2, n // 2 + 1):
        pure = True
        for r in range(p):
            cls = {kinds[i] for i in range(r, n, p)}
            if len(cls) > 1:
                pure = False
                break
        if pure:
            bad_p.append(p)
    ok = not bad_p
    rows.append(("T5",
                 "Is the kind a function of the position? For every period p "
                 "in 2..%d, is every residue class mod p of one kind only?"
                 % (n // 2),
                 "periods tested %d..%d; periods where the position predicts "
                 "the kind: %s" % (2, n // 2,
                                   "none" if not bad_p else str(bad_p)),
                 "PASS" if ok else "FAIL"))
    meas["positional_periods"] = bad_p
    meas["periods_tested"] = (2, n // 2)

    # ---- T6 no single-kind delivery --------------------------------------
    if batches is not None:
        bad_b = []
        for name, b in batches:
            ks = {kind_of[c] for c in b}
            if len(ks) < 2:
                bad_b.append("%s (%s only)" % (name, list(ks)[0]))
        ok = not bad_b
        rows.append(("T6",
                     "Is any single delivery (batch) made of one kind only?",
                     "%d batches checked; single-kind batches: %s"
                     % (len(batches),
                        "none" if not bad_b else "; ".join(bad_b)),
                     "PASS" if ok else "FAIL"))
        meas["batch_kind_counts"] = [
            (name, sum(1 for c in b if kind_of[c] == "large"),
             sum(1 for c in b if kind_of[c] == "calm"))
            for name, b in batches]

    # ---- measurements, not tests -----------------------------------------
    meas["adjacent_same_kind"] = sum(
        1 for i in range(1, n) if kinds[i] == kinds[i - 1])
    hist = {}
    for _, ln in kind_runs:
        hist[ln] = hist.get(ln, 0) + 1
    meas["run_hist"] = dict(sorted(hist.items()))
    meas["longest_run"] = max(ln for _, ln in kind_runs)
    meas["even_pos_kinds"] = sorted({kinds[i] for i in range(0, n, 2)})
    meas["odd_pos_kinds"] = sorted({kinds[i] for i in range(1, n, 2)})

    conforms = all(r[3] == "PASS" for r in rows)
    return rows, conforms, meas


def load_batches(d):
    out = []
    if not os.path.isdir(d):
        die("%s is not a directory." % d)
    for f in sorted(os.listdir(d)):
        if not re.fullmatch(r"batch-\d{2}\.md", f):
            continue
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            text = fh.read()
        m = re.search(r"## Card numbers, in order\n\n(.+?)\n", text)
        if not m:
            die("%s: no '## Card numbers, in order' line." % f)
        out.append((f, [x.strip() for x in m.group(1).split(",")]))
    if not out:
        die("no batch-NN.md files in %s" % d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("order")
    ap.add_argument("--batches", default=None)
    ap.add_argument("--md", default=None,
                    help="also write the table to this markdown file")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # RULES 23
    order_path = os.path.abspath(a.order)
    if not order_path.startswith(ROOT + os.sep):
        die("refusing to read outside %s (RULES 1)." % ROOT)

    cards = load_cards()
    order = load_order(order_path)
    batches = load_batches(os.path.abspath(a.batches)) if a.batches else None
    rows, conforms, meas = check(order, cards, batches)

    label = a.label or os.path.relpath(order_path, ROOT)
    print("Conformance of %s against the ratified TACTICS 4 requirement" % label)
    print("checked at %s" % now)
    print("order sha256 %s" % sha256_file(order_path))
    print("moments.csv sha256 %s" % sha256_file(MOMENTS))
    print("")
    for rid, q, detail, v in rows:
        print("%-3s %-4s %s" % (rid, v, q))
        print("         %s" % detail)
    print("")
    print("MEASUREMENTS (no threshold exists for these; the verdict leaves "
          "run length unsettled)")
    for k in ("adjacent_same_kind", "longest_run", "run_hist",
              "even_pos_kinds", "odd_pos_kinds"):
        if k in meas:
            print("  %-20s %s" % (k, meas[k]))
    print("")
    print("RESULT: %s" % ("CONFORMS" if conforms else "DOES NOT CONFORM"))

    if a.md:
        md_path = os.path.abspath(a.md)
        if not md_path.startswith(ROOT + os.sep):
            die("refusing to write outside %s." % ROOT)
        out = []
        out.append("# Conformance of `%s` against the ratified TACTICS 4 "
                   "requirement" % label)
        out.append("")
        out.append("Checked by `scripts/12_order_conformance.py` at %s "
                   "(system clock, RULES 23)." % now)
        out.append("")
        out.append("Requirement: `decisions/2026-09-19-card-order-requirement/"
                   "verdict.md`, ratified 3-0. The checks below are the "
                   "verdict's own check-list, one test per bullet, plus a "
                   "permutation test.")
        out.append("")
        out.append("| # | question | measured | verdict |")
        out.append("|---|---|---|---|")
        for rid, q, detail, v in rows:
            out.append("| %s | %s | %s | **%s** |" % (rid, q, detail, v))
        out.append("")
        out.append("**RESULT: %s**"
                   % ("CONFORMS" if conforms else "DOES NOT CONFORM"))
        out.append("")
        out.append("## Measurements that are not tests")
        out.append("")
        out.append("The verdict leaves unsettled whether a shuffle that "
                   "produces a long run of one kind must be re-drawn, and "
                   "RULES 33 forbids setting the number that would be needed "
                   "to test it. These are therefore printed as numbers and "
                   "nothing is passed or failed on them.")
        out.append("")
        out.append("| measurement | value |")
        out.append("|---|---|")
        out.append("| positions whose next card is the same kind | %d |"
                   % meas["adjacent_same_kind"])
        out.append("| longest run of one kind | %d |" % meas["longest_run"])
        out.append("| run-length histogram | `%s` |" % meas["run_hist"])
        out.append("| distinct kinds at even positions (0-indexed) | `%s` |"
                   % ", ".join(meas["even_pos_kinds"]))
        out.append("| distinct kinds at odd positions | `%s` |"
                   % ", ".join(meas["odd_pos_kinds"]))
        out.append("")
        if "batch_kind_counts" in meas:
            out.append("| batch | large | calm |")
            out.append("|---|---|---|")
            for nm, l, c in meas["batch_kind_counts"]:
                out.append("| `%s` | %d | %d |" % (nm, l, c))
            out.append("")
        out.append("## Input fingerprints")
        out.append("")
        out.append("| file | SHA-256 |")
        out.append("|---|---|")
        out.append("| `%s` | `%s` |" % (os.path.relpath(order_path, ROOT),
                                        sha256_file(order_path)))
        out.append("| `data/moments/moments.csv` | `%s` |"
                   % sha256_file(MOMENTS))
        vp = os.path.join(ROOT, "decisions",
                          "2026-09-19-card-order-requirement", "verdict.md")
        if os.path.exists(vp):
            out.append("| `decisions/2026-09-19-card-order-requirement/"
                       "verdict.md` | `%s` |" % sha256_file(vp))
        out.append("")
        out.append("## The orders ruled out by T2")
        out.append("")
        out.append("Each was tested ascending and descending:")
        out.append("")
        for nm in meas.get("derived_orders_tested", []):
            out.append("- %s" % nm)
        out.append("")
        text = "\n".join(out)
        if os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as fh:
                existing = fh.read()
            strip = lambda s: "\n".join(
                l for l in s.splitlines() if "at 20" not in l)
            if existing != text and strip(existing) != strip(text):
                die("%s already exists with different content. Refusing to "
                    "overwrite (RULES 30)." % md_path)
            if existing != text:
                print("markdown unchanged apart from the clock line; kept")
                sys.exit(0 if conforms else 2)
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s" % os.path.relpath(md_path, ROOT))

    sys.exit(0 if conforms else 2)


if __name__ == "__main__":
    main()
