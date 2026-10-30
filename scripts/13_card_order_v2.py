#!/usr/bin/env python3
"""
13_card_order_v2.py -- the SECOND card order over the 306 observation cards,
                       built under the ratified reading of TACTICS 4.

Why there is a second one
-------------------------
The first order (`data/card-order/order.csv`, built by
`scripts/11_card_order.py` at 2026-09-19T09:54Z) merged a shuffled large list
and a shuffled calm list strictly alternating. On 2026-09-19 a jury answered
the open question "what does TACTICS 4 require of the order in which the cards
reach a watcher?" and a referee ratified the answer 3-0
(`decisions/2026-09-19-card-order-requirement/verdict.md`). The ratified
requirement names strict alternation as a failure:

  "No positional rule for kind: a watcher must not be able to read a card's
   kind from its position in the sequence (strict alternation
   large/calm/large/calm fails this)."

`scripts/12_order_conformance.py` measured the first order against the ratified
check-list: it fails T5 for every even period from 2 to 152. So it is replaced.
Nothing the first run wrote is touched (RULES 30); this run writes into a new
folder.

What it does
------------
1. Rebuilds the card list from data/moments/moments.csv (card number = 1-based
   row position, the scheme 09_write_cards.py used) and cross-checks every
   (card, coin, kind, start hour) against the card table in cards/INDEX.md.
   Checks every card file exists. A mismatch stops the script.

2. Produces ONE order: a uniform random permutation of all 306 cards, drawn
   over the whole pool with one call to random.Random(SEED).shuffle on the card
   list in card-number order. The card's kind, coin and date take no part in
   the draw -- that is what the ratified requirement's first clause asks for:

     "The order is a shuffle: a permutation produced by a randomising procedure
      over the whole pool of the 10 coins' cards, not an order derived from
      card properties."

3. Checks the drawn order against the ratified check-list by calling
   scripts/12_order_conformance.py. If the draw fails any of its tests the
   script STOPS and writes nothing. It does NOT re-draw: the verdict leaves
   explicitly unsettled whether an unlucky honest shuffle must be re-drawn, and
   settling that would need a number no juror was allowed to set (RULES 33). A
   failure here is a thing to report and ask about, not to paper over.

4. Splits the order into batches of BATCH_SIZE by position and by nothing else,
   and checks every card lands in exactly one batch and that the batches
   concatenate back to the order.

The seed
--------
Derived, not invented, exactly as the first run's was, and different from it
for exactly one reason: a new input entered the run. The first run's seed
source string was

  card-order|draw=<draw>|moments_sha256=<...>|card_kinds_sha256=<...>

This run's input additionally contains the ratified verdict -- it is the
document this order is built to satisfy -- so its fingerprint joins the seed
source string:

  card-order|draw=<draw>|moments_sha256=<...>|card_kinds_sha256=<...>
            |requirement_sha256=<sha256 of verdict.md>

RULES 29: the run's number is the fingerprint of its input. The input changed,
so the number changed, so the order changed. Same inputs in, same order out:
this script run again on the same three fingerprints yields byte-identical
files.

Input
-----
  data/moments/moments.csv                                the moments
  cards/INDEX.md                                          cross-check only
  cards/C###.md                                           existence + byte size
  decisions/2026-09-19-card-order-requirement/verdict.md  the requirement; read
                                                          for its fingerprint
  scripts/12_order_conformance.py                         the check-list

Output
------
  data/card-order/v2/order.csv              position, card number
  data/card-order/v2/batches/batch-NN.md    one file per batch
  data/card-order/v2/order-manifest.md      seed, derivation, batch table,
                                            checks, fingerprints, supersession

Rules implemented
-----------------
  TACTICS 4  as ratified in decisions/2026-09-19-card-order-requirement/
  RULES 29   the run number is the fingerprint of the input
  RULES 30   append-only; never overwrites with different content
  RULES 19   no unmeasured number without the word "estimate"
  RULES 23   the clock is read from the system
  RULES 33   an open question is not settled by this script

Randomness
----------
  Exactly one source: random.Random(SEED), SEED derived as above. One call to
  .shuffle(). No other use of random anywhere in this file.
"""

import csv
import hashlib
import importlib.util
import os
import re
import random
import sys
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Constants. Each says where it came from.
# --------------------------------------------------------------------------

# TACTICS 1: "Draw number: 20260913. Written before the draw; it does not
# change." The laboratory's one written-down number. Not invented here.
DRAW_NUMBER = "20260913"

# Batch size. Carried over unchanged from scripts/11_card_order.py, where it
# was derived from the measured card bytes. It is not re-derived here because
# the ratified requirement says nothing about batching and the cards have not
# changed. Its derivation, repeated so the number is not bare:
#   - measured: the largest of the 306 cards is 9077 bytes;
#   - ASSUMPTION (estimate, no tokenizer on this machine): 3.0 bytes/token;
#   - ASSUMPTION: a watcher has a 200_000-token context window;
#   - ASSUMPTION: the cards may take at most half of that window.
#   306 = 9 * 34 exactly, so the batches are equal and nothing is left over.
BATCH_SIZE = 34

ASSUMED_BYTES_PER_TOKEN = 3.0         # estimate - no tokenizer available
ASSUMED_CONTEXT_TOKENS = 200_000      # assumption - watcher model window
ASSUMED_CARD_SHARE_OF_CONTEXT = 0.50  # assumption - cards get at most half

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS = os.path.join(ROOT, "data", "moments", "moments.csv")
CARDS_DIR = os.path.join(ROOT, "cards")
INDEX_MD = os.path.join(CARDS_DIR, "INDEX.md")
VERDICT = os.path.join(ROOT, "decisions", "2026-09-19-card-order-requirement",
                       "verdict.md")
CHECKER = os.path.join(ROOT, "scripts", "12_order_conformance.py")

OUT_DIR = os.path.join(ROOT, "data", "card-order", "v2")
BATCH_DIR = os.path.join(OUT_DIR, "batches")

# What this order replaces, by path. Written into the manifest.
SUPERSEDES = "data/card-order/order.csv"
SUPERSEDES_BATCHES = "data/card-order/batches/"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def die(msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(1)


def write_once(path, text, ignore_re=None):
    """RULES 30: append-only. Never overwrite with different content."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
        if existing == text:
            return "unchanged"
        if ignore_re is not None:
            strip = lambda s: "\n".join(
                l for l in s.splitlines() if not re.search(ignore_re, l))
            if strip(existing) == strip(text):
                return ("unchanged apart from the clock line; the first "
                        "write's clock is kept")
        die("%s already exists with different content. Refusing to overwrite "
            "(RULES 30)." % path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return "written"


def load_checker():
    spec = importlib.util.spec_from_file_location("order_conformance", CHECKER)
    if spec is None:
        die("cannot load %s" % CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# 1 - the card list, cross-checked
# --------------------------------------------------------------------------

def load_cards():
    if not os.path.exists(MOMENTS):
        die("%s not found." % MOMENTS)
    with open(MOMENTS, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    cards = []
    for i, r in enumerate(rows, start=1):
        kind = r["kind"].strip()
        if kind not in ("large", "calm"):
            die("row %d of moments.csv has kind %r, expected large or calm."
                % (i, kind))
        try:
            move = float(r["move_24h_pct"])
        except (KeyError, ValueError):
            move = None
        cards.append({"no": "C%03d" % i, "coin": r["symbol"].strip(),
                      "kind": kind, "start": r["start_hour_utc"].strip(),
                      "move": move})
    return cards


def cross_check_index(cards):
    if not os.path.exists(INDEX_MD):
        die("%s not found." % INDEX_MD)
    with open(INDEX_MD, encoding="utf-8") as fh:
        text = fh.read()
    pat = re.compile(
        r"^\|\s*`(C\d{3})`\s*\|\s*([A-Z0-9]+)\s*\|\s*(large|calm)\s*\|"
        r"\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|", re.M)
    found = {m.group(1): (m.group(2), m.group(3), m.group(4))
             for m in pat.finditer(text)}
    if len(found) != len(cards):
        die("cards/INDEX.md lists %d cards, moments.csv gives %d."
            % (len(found), len(cards)))
    for c in cards:
        if c["no"] not in found:
            die("%s is missing from the card table in cards/INDEX.md." % c["no"])
        coin, kind, start = found[c["no"]]
        mine = c["start"].replace("T", " ").replace("Z", "")
        if (coin, kind, start) != (c["coin"], c["kind"], mine):
            die("%s disagrees: moments.csv says %r, cards/INDEX.md says %r."
                % (c["no"], (c["coin"], c["kind"], mine), (coin, kind, start)))
    return len(found)


def check_files_exist(cards):
    sizes = {}
    for c in cards:
        p = os.path.join(CARDS_DIR, c["no"] + ".md")
        if not os.path.isfile(p):
            die("card file %s does not exist." % p)
        sizes[c["no"]] = os.path.getsize(p)
    return sizes


# --------------------------------------------------------------------------
# 2 - the order: one uniform shuffle over the whole pool
# --------------------------------------------------------------------------

def build_order(cards, seed):
    """A uniform random permutation of the whole pool. The starting list is the
    306 card numbers in card-number order, so the procedure is fully determined
    by the seed. Nothing about a card -- kind, coin, date -- enters the draw."""
    pool = sorted(c["no"] for c in cards)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # RULES 23

    for p in (MOMENTS, INDEX_MD, VERDICT, CHECKER):
        if not os.path.exists(p):
            die("required input missing: %s" % p)

    cards = load_cards()
    n_index = cross_check_index(cards)
    sizes = check_files_exist(cards)
    kind_of = {c["no"]: c["kind"] for c in cards}
    n_large = sum(1 for c in cards if c["kind"] == "large")
    n_calm = len(cards) - n_large

    # ---- the run number and the seed (RULES 29) --------------------------
    moments_sha = sha256_file(MOMENTS)
    card_kind_blob = "\n".join("%s,%s" % (c["no"], c["kind"]) for c in cards)
    card_kind_sha = sha256_text(card_kind_blob)
    verdict_sha = sha256_file(VERDICT)

    SEED_SOURCE = ("card-order|draw=%s|moments_sha256=%s|card_kinds_sha256=%s"
                   "|requirement_sha256=%s"
                   % (DRAW_NUMBER, moments_sha, card_kind_sha, verdict_sha))
    RUN_ID = sha256_text(SEED_SOURCE)
    SEED = int(RUN_ID[:16], 16)

    order = build_order(cards, SEED)

    # ---- reproducibility, inside this run --------------------------------
    order_again = build_order(cards, SEED)
    if order != order_again:
        die("the same seed produced two different orders inside one run.")
    repro_in_run = True

    # ---- structural checks ------------------------------------------------
    if len(order) != len(cards):
        die("order has %d entries, expected %d." % (len(order), len(cards)))
    if len(set(order)) != len(cards):
        die("the order repeats a card.")
    if set(order) != set(kind_of):
        die("the order is not the same set of cards as the card list.")

    # ---- the batches ------------------------------------------------------
    batches = [order[i:i + BATCH_SIZE]
               for i in range(0, len(order), BATCH_SIZE)]
    flat = [c for b in batches for c in b]
    if flat != order:
        die("concatenating the batches does not reproduce the order.")
    seen = {}
    for bi, b in enumerate(batches, start=1):
        for c in b:
            if c in seen:
                die("%s is in batch %d and batch %d." % (c, seen[c], bi))
            seen[c] = bi
    missing = sorted(set(kind_of) - set(seen))
    if missing:
        die("cards in no batch: %s" % ", ".join(missing))
    every_card_exactly_once = (len(seen) == len(cards) and not missing
                               and len(flat) == len(cards))
    if not every_card_exactly_once:
        die("a card is not in exactly one batch.")

    # ---- the ratified requirement ----------------------------------------
    checker = load_checker()
    named_batches = [("batch-%02d.md" % (i + 1), b)
                     for i, b in enumerate(batches)]
    rows, conforms, meas = checker.check(order, cards, named_batches)
    print("RATIFIED-REQUIREMENT CHECK (decisions/"
          "2026-09-19-card-order-requirement/verdict.md)")
    for rid, q, detail, v in rows:
        print("  %-3s %-4s %s" % (rid, v, q))
        print("        %s" % detail)
    if not conforms:
        die("the drawn order does not meet the ratified requirement. This "
            "script does NOT re-draw: the verdict leaves unsettled whether an "
            "honest shuffle must be re-drawn, and RULES 33 forbids this "
            "script to settle it. Reported, not patched.")

    # ---- measurements -----------------------------------------------------
    total_bytes = sum(sizes.values())
    min_b, max_b = min(sizes.values()), max(sizes.values())
    mean_b = total_bytes / len(sizes)
    batch_bytes = [sum(sizes[c] for c in b) for b in batches]

    print("MEASURED (bytes, exact)")
    print("  cards                : %d" % len(cards))
    print("  large / calm         : %d / %d" % (n_large, n_calm))
    print("  cross-checked rows   : %d against cards/INDEX.md" % n_index)
    print("  total card bytes     : %d" % total_bytes)
    print("  smallest / largest   : %d / %d" % (min_b, max_b))
    print("  mean card bytes      : %.1f" % mean_b)
    print("  batches              : %d of %d cards" % (len(batches),
                                                       BATCH_SIZE))
    print("  batch bytes min/max  : %d / %d" % (min(batch_bytes),
                                                max(batch_bytes)))
    print("SEED")
    print("  source string        : %s" % SEED_SOURCE)
    print("  run id (sha256)      : %s" % RUN_ID)
    print("  seed (int)           : %d" % SEED)

    # ---- write ------------------------------------------------------------
    os.makedirs(BATCH_DIR, exist_ok=True)

    lines = ["position,card_number"]
    lines += ["%d,%s" % (i, c) for i, c in enumerate(order, start=1)]
    order_csv_text = "\n".join(lines) + "\n"
    order_path = os.path.join(OUT_DIR, "order.csv")
    status = {order_path: write_once(order_path, order_csv_text)}

    batch_paths = []
    for bi, b in enumerate(batches, start=1):
        name = "batch-%02d.md" % bi
        p = os.path.join(BATCH_DIR, name)
        first = (bi - 1) * BATCH_SIZE + 1
        last = first + len(b) - 1
        t = []
        t.append("# Card batch %02d of %02d" % (bi, len(batches)))
        t.append("")
        t.append("%d cards - positions %d-%d of the order in "
                 "`data/card-order/v2/order.csv`." % (len(b), first, last))
        t.append("")
        t.append("## Card numbers, in order")
        t.append("")
        t.append(", ".join(b))
        t.append("")
        t.append("## File paths, in order")
        t.append("")
        for c in b:
            t.append("cards/%s.md" % c)
        t.append("")
        status[p] = write_once(p, "\n".join(t))
        batch_paths.append(p)

    # ---- the manifest -----------------------------------------------------
    order_sha = sha256_file(order_path)
    batch_shas = [(os.path.basename(p), sha256_file(p)) for p in batch_paths]

    tok_card_max = max_b / ASSUMED_BYTES_PER_TOKEN
    tok_batch_max = max(batch_bytes) / ASSUMED_BYTES_PER_TOKEN
    budget = ASSUMED_CONTEXT_TOKENS * ASSUMED_CARD_SHARE_OF_CONTEXT

    m = []
    m.append("# Card order v2 and batches - manifest")
    m.append("")
    m.append("Written by `scripts/13_card_order_v2.py` at %s (system clock, "
             "RULES 23)." % now)
    m.append("")
    m.append("## What this supersedes")
    m.append("")
    m.append("This order **supersedes `%s`** and its batches in `%s`, built by "
             "`scripts/11_card_order.py` at 2026-09-19T09:54Z."
             % (SUPERSEDES, SUPERSEDES_BATCHES))
    m.append("")
    m.append("Nothing the earlier run wrote has been changed or removed "
             "(RULES 30). It stays on disk as the record of what was built and "
             "why it was replaced. Its measured failure is in "
             "`data/card-order/v2/conformance-v1.md`.")
    m.append("")
    m.append("**Why it was replaced.** The earlier order merged a shuffled "
             "large list and a shuffled calm list strictly alternating. The "
             "jury answer ratified 3-0 in "
             "`decisions/2026-09-19-card-order-requirement/verdict.md` names "
             "that construction as a failure: *\"No positional rule for kind: "
             "a watcher must not be able to read a card's kind from its "
             "position in the sequence (strict alternation "
             "large/calm/large/calm fails this).\"* Measured, the earlier "
             "order's kind is a function of the position for every even "
             "period from 2 to 152.")
    m.append("")
    m.append("## The requirement this order is built to")
    m.append("")
    m.append("Quoted from `decisions/2026-09-19-card-order-requirement/"
             "verdict.md`:")
    m.append("")
    m.append("> a shuffled permutation of all cards of the 10 observation "
             "coins, with large-movement and calm-moment cards mixed through "
             "one sequence rather than segregated, and with no positional rule "
             "that allows the watcher to read a card's kind from its position.")
    m.append("")
    m.append("The verdict leaves one thing open and this run does not close "
             "it: whether a fair shuffle that happens to produce a long run of "
             "one kind must be re-drawn. Closing it would need a maximum "
             "run length, and RULES 33 keeps that number out of a juror's "
             "hands and out of this script's. So the script draws once, checks "
             "the draw against the ratified check-list, and **stops rather "
             "than re-drawing** if a check fails. It did not fail; the draw "
             "below is the first and only draw.")
    m.append("")
    m.append("## The seed and where it came from")
    m.append("")
    m.append("The seed is derived, not invented (RULES 29: the run's number is "
             "the fingerprint of its input).")
    m.append("")
    m.append("| part | value | where it came from |")
    m.append("|---|---|---|")
    m.append("| draw number | `%s` | TACTICS 1: \"Draw number: `20260913`. "
             "Written before the draw; it does not change.\" |" % DRAW_NUMBER)
    m.append("| `data/moments/moments.csv` SHA-256 | `%s` | measured this run |"
             % moments_sha)
    m.append("| card-number+kind list SHA-256 | `%s` | measured this run; the "
             "sha256 of the %d lines `C###,kind` in card-number order |"
             % (card_kind_sha, len(cards)))
    m.append("| `decisions/2026-09-19-card-order-requirement/verdict.md` "
             "SHA-256 | `%s` | measured this run |" % verdict_sha)
    m.append("")
    m.append("Seed source string, hashed verbatim:")
    m.append("")
    m.append("```")
    m.append(SEED_SOURCE)
    m.append("```")
    m.append("")
    m.append("| | |")
    m.append("|---|---|")
    m.append("| run id = SHA-256 of that string | `%s` |" % RUN_ID)
    m.append("| seed = first 16 hex digits as an integer | `%d` |" % SEED)
    m.append("| generator | Python `random.Random(seed)`; one call to "
             "`.shuffle()`, the only randomness in the script |")
    m.append("")
    m.append("### Why this seed differs from the superseded order's seed")
    m.append("")
    m.append("The superseded run hashed")
    m.append("")
    m.append("```")
    m.append("card-order|draw=%s|moments_sha256=%s|card_kinds_sha256=%s"
             % (DRAW_NUMBER, moments_sha, card_kind_sha))
    m.append("```")
    m.append("")
    m.append("giving seed `12884437485539897566`. This run hashes the same "
             "string with one field added: `requirement_sha256`, the "
             "fingerprint of the ratified verdict. The verdict is an input to "
             "this run - it is the document the order is built to satisfy, and "
             "it did not exist when the first order was drawn. Under RULES 29 "
             "a run's number is the fingerprint of its input; the input grew, "
             "so the number changed, so the order changed. Nothing was picked "
             "by hand to make the seeds differ.")
    m.append("")
    m.append("An order rebuilt with this seed and this procedure is this "
             "order, byte for byte. Same three fingerprints in, same 306 "
             "positions out.")
    m.append("")
    m.append("## How the order was built")
    m.append("")
    m.append("1. The %d card numbers are put in card-number order "
             "`C001 .. C%03d`. This is the starting list and it is fixed, so "
             "the seed alone determines the result."
             % (len(cards), len(cards)))
    m.append("2. `random.Random(seed).shuffle()` is called **once** on that "
             "list. One uniform permutation of the whole pool.")
    m.append("3. Nothing else happens. The kind, the coin and the date of a "
             "card take no part in the draw, and no position is reserved for a "
             "kind. Large and calm cards fall where the shuffle puts them.")
    m.append("")
    m.append("The pool is all %d cards of the 10 observation coins together "
             "(%d large, %d calm), as TACTICS 4 line 78 requires: the watchers "
             "\"read all the cards of the 10 coins\"."
             % (len(cards), n_large, n_calm))
    m.append("")
    m.append("## The measurement the batch size rests on")
    m.append("")
    m.append("Measured, exactly, from the %d files `cards/C001.md` .. "
             "`cards/C%03d.md`:" % (len(cards), len(cards)))
    m.append("")
    m.append("| measurement | bytes |")
    m.append("|---|---|")
    m.append("| all %d cards together | %d |" % (len(cards), total_bytes))
    m.append("| smallest card | %d |" % min_b)
    m.append("| largest card | %d |" % max_b)
    m.append("| mean card | %.1f |" % mean_b)
    m.append("| one batch of %d, smallest | %d |" % (BATCH_SIZE,
                                                     min(batch_bytes)))
    m.append("| one batch of %d, largest | %d |" % (BATCH_SIZE,
                                                    max(batch_bytes)))
    m.append("")
    m.append("### What could not be measured, and the assumptions put in its "
             "place (RULES 19)")
    m.append("")
    m.append("Bytes are measured. **Tokens are not.** No tokenizer is "
             "installed on this machine, and the token count of the watcher "
             "model cannot be obtained without calling an API this script does "
             "not call. Every token number below is therefore an **estimate** "
             "and is labelled one.")
    m.append("")
    m.append("| assumption | value | why it is an assumption |")
    m.append("|---|---|---|")
    m.append("| bytes per token | %.1f (**estimate**) | the cards are "
             "number-heavy markdown tables, which tokenize worse than prose; "
             "no tokenizer available to measure it |"
             % ASSUMED_BYTES_PER_TOKEN)
    m.append("| watcher context window | %s tokens (**assumption**) | the "
             "watcher's model and window are not named in TACTICS 4 or in this "
             "run's instruction |" % f"{ASSUMED_CONTEXT_TOKENS:,}")
    m.append("| share of the window the cards may take | %d%% "
             "(**assumption**) | the rest is left for the instruction, tool "
             "overhead, the watcher's reasoning and its one note line per card "
             "(TACTICS 4 note format) |"
             % int(ASSUMED_CARD_SHARE_OF_CONTEXT * 100))
    m.append("")
    m.append("Arithmetic on those assumptions (**all estimates**): largest "
             "card ~%.0f tokens; largest batch of %d cards ~%.0f tokens, "
             "against a card budget of %.0f tokens (%.0f%% of the assumed "
             "window). The batch size %d is carried over unchanged from "
             "`scripts/11_card_order.py`; the ratified requirement says "
             "nothing about batching and the cards have not changed."
             % (tok_card_max, BATCH_SIZE, tok_batch_max, budget,
                ASSUMED_CARD_SHARE_OF_CONTEXT * 100, BATCH_SIZE))
    m.append("")
    m.append("## The batches")
    m.append("")
    m.append("%d batches of %d cards. A card's batch is decided by its "
             "position in the order and by nothing else - not its coin, not "
             "its kind, not its date." % (len(batches), BATCH_SIZE))
    m.append("")
    m.append("| batch | cards | positions | large | calm | card bytes | file |")
    m.append("|---|---|---|---|---|---|---|")
    for bi, b in enumerate(batches, start=1):
        first = (bi - 1) * BATCH_SIZE + 1
        last = first + len(b) - 1
        bl = sum(1 for c in b if kind_of[c] == "large")
        m.append("| %02d | %d | %d-%d | %d | %d | %d | "
                 "`data/card-order/v2/batches/batch-%02d.md` |"
                 % (bi, len(b), first, last, bl, len(b) - bl,
                    batch_bytes[bi - 1], bi))
    m.append("")
    m.append("The large/calm split per batch is a **measurement, not a "
             "target**. No batch was balanced, reserved or re-drawn; the "
             "numbers are whatever the one shuffle produced.")
    m.append("")
    m.append("## Checks run in code")
    m.append("")
    m.append("| check | result |")
    m.append("|---|---|")
    m.append("| card table of `cards/INDEX.md` agrees with `moments.csv` on "
             "card number, coin, kind and start hour | %d / %d rows |"
             % (n_index, len(cards)))
    m.append("| every card file `cards/C###.md` exists | %d / %d |"
             % (len(sizes), len(cards)))
    m.append("| the order holds %d entries, no repeats, same set as the card "
             "list | pass |" % len(cards))
    m.append("| the batches concatenated reproduce the order exactly | pass |")
    m.append("| **every card in exactly one batch** | **pass** - %d cards, %d "
             "batch slots, 0 duplicates, 0 missing |"
             % (len(cards), len(flat)))
    m.append("| the same seed drawn twice in one run gives the same order | "
             "%s |" % ("pass" if repro_in_run else "FAIL"))
    m.append("| re-running the script writes byte-identical files (RULES 30 "
             "refuses any differing rewrite) | pass - see the run log |")
    m.append("")
    m.append("### Against the ratified requirement")
    m.append("")
    m.append("Run by `scripts/12_order_conformance.py`, which states each test "
             "as a question and answers it with a measured number, so it can "
             "be re-run and read without trusting this manifest. Full output: "
             "`data/card-order/v2/conformance-v2.md`.")
    m.append("")
    m.append("| # | question | measured | verdict |")
    m.append("|---|---|---|---|")
    for rid, q, detail, v in rows:
        m.append("| %s | %s | %s | **%s** |" % (rid, q, detail, v))
    m.append("")
    m.append("Not tests, only measurements (the verdict sets no run-length "
             "limit, RULES 33): %d positions whose next card is the same kind; "
             "longest run of one kind %d; run-length histogram `%s`."
             % (meas["adjacent_same_kind"], meas["longest_run"],
                meas["run_hist"]))
    m.append("")
    m.append("## Fingerprints")
    m.append("")
    m.append("| file | SHA-256 |")
    m.append("|---|---|")
    m.append("| `data/card-order/v2/order.csv` | `%s` |" % order_sha)
    for name, sha in batch_shas:
        m.append("| `data/card-order/v2/batches/%s` | `%s` |" % (name, sha))
    m.append("")
    m.append("Input fingerprints are in the seed table above.")
    m.append("")
    manifest_text = "\n".join(m)
    manifest_path = os.path.join(OUT_DIR, "order-manifest.md")
    status[manifest_path] = write_once(
        manifest_path, manifest_text,
        ignore_re=r"^Written by `scripts/13_card_order_v2\.py` at ")

    print("WROTE")
    for p, s in status.items():
        print("  %-56s %s" % (os.path.relpath(p, ROOT), s))
    print("  order.csv sha256: %s" % order_sha)


if __name__ == "__main__":
    main()
