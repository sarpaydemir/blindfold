#!/usr/bin/env python3
"""
11_card_order.py -- the order in which the 306 observation cards are given to a
                    watcher, and the batches a watcher reads them in.

What it does
------------
1. Rebuilds the card list from data/moments/moments.csv. The card number is the
   1-based position of the row in that file (the numbering scheme written in
   cards/INDEX.md by 09_write_cards.py). Every derived (card, coin, kind, start
   hour) tuple is cross-checked against the card table in cards/INDEX.md, and
   every card file is checked to exist. A mismatch stops the script.

2. Produces ONE order over all 306 cards satisfying TACTICS 4:

       "Cards are given in shuffled order: large moments and calm moments
        interleaved."

   Implemented as the strictest reading of "interleaved": the large cards are
   shuffled among themselves, the calm cards are shuffled among themselves, and
   the two shuffled lists are then merged strictly alternating, so no two
   neighbours in the order share a kind. Which kind holds position 1 is drawn
   from the seed, not chosen by hand. The counts happen to be exactly 153 large
   and 153 calm, so the alternation is perfect and leaves no tail.

   NOTE: "interleaved" also admits a weaker reading (merely mixed, not grouped
   by kind), which a plain uniform shuffle of all 306 would already satisfy.
   The stricter reading implemented here satisfies the weaker one too. This is
   flagged as an open question (RULES 33) in data/card-order/order-manifest.md;
   this script does not settle it, it only implements the stricter reading.

3. Splits the order into batches of BATCH_SIZE, purely by position in the order.
   The coin, the kind and the date of a card have no influence on which batch it
   lands in. The script verifies that every card appears in exactly one batch.

Input
-----
  data/moments/moments.csv     the moments, in card-number order
  cards/INDEX.md               the card table, used only as a cross-check
  cards/C###.md                existence and byte size only; contents not read

Output
------
  data/card-order/order.csv            position, card number
  data/card-order/batches/batch-NN.md  one file per batch, card numbers in order
  data/card-order/order-manifest.md    seed, batch sizes, measurements, checks,
                                       SHA-256 of every file written

Rules implemented
-----------------
  TACTICS 4  shuffled order, large and calm interleaved
  RULES 29   the run number is the fingerprint of the input; same input, same
             number, same result
  RULES 30   append-only: if a file already exists with different content the
             script stops, it never overwrites
  RULES 19   no unmeasured number is written without the word "estimate"
  RULES 23   the clock is read from the system, not guessed

Randomness
----------
  Exactly one source of randomness: random.Random(SEED), SEED derived from the
  laboratory's draw number and the fingerprint of the input (see SEED_SOURCE
  below). No other call to random anywhere in this file.
"""

import csv
import hashlib
import os
import re
import random
import sys
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Constants. Each one says where it came from.
# --------------------------------------------------------------------------

# TACTICS 1: "Draw number: 20260913. Written before the draw; it does not
# change." The laboratory's one written-down number. Not invented here.
DRAW_NUMBER = "20260913"

# Batch size. Chosen from the measured card bytes; the reasoning, the
# measurement and the assumptions are written into the manifest and repeated
# here so the number is not bare:
#   - measured: the largest of the 306 cards is 9077 bytes (see MEASURED block
#     printed by this script);
#   - ASSUMPTION (estimate, no tokenizer on this machine): 3.0 bytes per token
#     for these number-heavy markdown tables, i.e. at most ~3026 tokens/card;
#   - ASSUMPTION: a watcher has a 200_000-token context window;
#   - ASSUMPTION: the cards themselves may take at most half of that window,
#     leaving the other half for the instruction, the tool overhead, the
#     watcher's reasoning and its 1 note line per card.
#   Worst case if all 34 cards were the largest: 34 * 3026 = 102_884 tokens,
#   ~51% of 200_000. The actual largest batch measures 297_421 bytes, ~99_140
#   tokens on the same estimate, just inside the 100_000 budget. 306 = 9 * 34
#   exactly, so the batches are all the same size and no card is left over.
BATCH_SIZE = 34

# The assumptions above, kept as named numbers so the manifest prints the same
# values the arithmetic used.
ASSUMED_BYTES_PER_TOKEN = 3.0        # estimate - no tokenizer available
ASSUMED_CONTEXT_TOKENS = 200_000     # assumption - watcher model window
ASSUMED_CARD_SHARE_OF_CONTEXT = 0.50  # assumption - cards get at most half

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOMENTS = os.path.join(ROOT, "data", "moments", "moments.csv")
CARDS_DIR = os.path.join(ROOT, "cards")
INDEX_MD = os.path.join(CARDS_DIR, "INDEX.md")
OUT_DIR = os.path.join(ROOT, "data", "card-order")
BATCH_DIR = os.path.join(OUT_DIR, "batches")


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
    """RULES 30: append-only. Never overwrite with different content.

    ignore_re names a line pattern that is allowed to differ between runs --
    used only for the manifest's "written at <clock>" line, which is different
    on every run by construction. If the two files differ only in such lines,
    the file already on disk is kept untouched, so it keeps the clock of the
    first write. If anything else differs, the script stops.
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
        if existing == text:
            return "unchanged"
        if ignore_re is not None:
            strip = lambda s: "\n".join(
                l for l in s.splitlines() if not re.search(ignore_re, l))
            if strip(existing) == strip(text):
                return "unchanged apart from the clock line; the first " \
                       "write's clock is kept"
        die("%s already exists with different content. Refusing to overwrite "
            "(RULES 30)." % path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return "written"


# --------------------------------------------------------------------------
# 1 - rebuild the card list and cross-check it against cards/INDEX.md
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
        cards.append({
            "no": "C%03d" % i,
            "coin": r["symbol"].strip(),
            "kind": kind,
            "start": r["start_hour_utc"].strip(),
        })
    return cards


def cross_check_index(cards):
    """cards/INDEX.md carries one row per card: | `C001` | COIN | kind | date |
    Compare it, row for row, with what we derived from moments.csv."""
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
        # moments.csv writes 2026-05-07T20:00Z, INDEX.md writes 2026-05-07 20:00
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
# 2 - the order (TACTICS 4)
# --------------------------------------------------------------------------

def build_order(cards, rng):
    large = [c["no"] for c in cards if c["kind"] == "large"]
    calm = [c["no"] for c in cards if c["kind"] == "calm"]
    if len(large) != len(calm):
        die("strict alternation needs equal counts; got %d large and %d calm. "
            "The instruction does not say what to do with the remainder, so "
            "this script stops rather than deciding (RULES 22)."
            % (len(large), len(calm)))
    rng.shuffle(large)
    rng.shuffle(calm)
    # which kind takes position 1 is drawn, not chosen
    first_is_large = rng.random() < 0.5
    a, b = (large, calm) if first_is_large else (calm, large)
    order = []
    for x, y in zip(a, b):
        order.append(x)
        order.append(y)
    return order, ("large" if first_is_large else "calm")


def check_alternates(order, kind_of):
    for i in range(1, len(order)):
        if kind_of[order[i]] == kind_of[order[i - 1]]:
            die("positions %d and %d are both %s; the order is not "
                "interleaved." % (i, i + 1, kind_of[order[i]]))
    return True


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # RULES 23

    cards = load_cards()
    n_index = cross_check_index(cards)
    sizes = check_files_exist(cards)
    kind_of = {c["no"]: c["kind"] for c in cards}
    n_large = sum(1 for c in cards if c["kind"] == "large")
    n_calm = len(cards) - n_large

    # ---- the run number and the seed (RULES 29) --------------------------
    moments_sha = sha256_file(MOMENTS)
    # the true input to the order: every card number with its kind, in card
    # order. Fingerprinting this and not the whole index means the order does
    # not move when an unrelated line of INDEX.md is edited.
    card_kind_blob = "\n".join("%s,%s" % (c["no"], c["kind"]) for c in cards)
    card_kind_sha = sha256_text(card_kind_blob)

    SEED_SOURCE = ("card-order|draw=%s|moments_sha256=%s|card_kinds_sha256=%s"
                   % (DRAW_NUMBER, moments_sha, card_kind_sha))
    RUN_ID = sha256_text(SEED_SOURCE)
    SEED = int(RUN_ID[:16], 16)
    rng = random.Random(SEED)

    order, first_kind = build_order(cards, rng)

    # ---- checks on the order ---------------------------------------------
    if len(order) != len(cards):
        die("order has %d entries, expected %d." % (len(order), len(cards)))
    if len(set(order)) != len(cards):
        die("the order repeats a card.")
    if set(order) != set(kind_of):
        die("the order is not the same set of cards as the card list.")
    check_alternates(order, kind_of)

    # ---- the batches ------------------------------------------------------
    batches = [order[i:i + BATCH_SIZE] for i in range(0, len(order), BATCH_SIZE)]
    # every card in exactly one batch
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
    print("  batches              : %d of %d cards" % (len(batches), BATCH_SIZE))
    print("  batch bytes min/max  : %d / %d" % (min(batch_bytes),
                                                max(batch_bytes)))
    print("SEED")
    print("  source string        : %s" % SEED_SOURCE)
    print("  run id (sha256)      : %s" % RUN_ID)
    print("  seed (int)           : %d" % SEED)
    print("  first position kind  : %s" % first_kind)

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
                 "`data/card-order/order.csv`." % (len(b), first, last))
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
        text = "\n".join(t)
        status[p] = write_once(p, text)
        batch_paths.append(p)

    # ---- the manifest -----------------------------------------------------
    order_sha = sha256_file(order_path)
    batch_shas = [(os.path.basename(p), sha256_file(p)) for p in batch_paths]

    tok_card_max = max_b / ASSUMED_BYTES_PER_TOKEN
    tok_batch_max = max(batch_bytes) / ASSUMED_BYTES_PER_TOKEN
    budget = ASSUMED_CONTEXT_TOKENS * ASSUMED_CARD_SHARE_OF_CONTEXT

    m = []
    m.append("# Card order and batches - manifest")
    m.append("")
    m.append("Written by `scripts/11_card_order.py` at %s (system clock, "
             "RULES 23)." % now)
    m.append("")
    m.append("Implements TACTICS 4: *\"Cards are given in shuffled order: "
             "large moments and calm moments interleaved.\"* This run writes "
             "no card and changes none.")
    m.append("")
    m.append("## The seed and where it came from")
    m.append("")
    m.append("The seed is not invented. It is derived from the laboratory's "
             "one written-down number and the fingerprint of this run's input "
             "(RULES 29: the run's number is the fingerprint of its input).")
    m.append("")
    m.append("| part | value | where it came from |")
    m.append("|---|---|---|")
    m.append("| draw number | `%s` | TACTICS 1: \"Draw number: `20260913`. "
             "Written before the draw; it does not change.\" |" % DRAW_NUMBER)
    m.append("| `data/moments/moments.csv` SHA-256 | `%s` | measured this run |"
             % moments_sha)
    m.append("| card-number+kind list SHA-256 | `%s` | measured this run; the "
             "sha256 of the 306 lines `C###,kind` in card order |"
             % card_kind_sha)
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
    m.append("| generator | Python `random.Random(seed)`, the only randomness "
             "in the script |")
    m.append("| kind drawn into position 1 | `%s` |" % first_kind)
    m.append("")
    m.append("Same `moments.csv` in, same order out.")
    m.append("")
    m.append("## How the order was built")
    m.append("")
    m.append("1. The %d large card numbers are shuffled among themselves; the "
             "%d calm card numbers are shuffled among themselves."
             % (n_large, n_calm))
    m.append("2. Which kind takes position 1 is drawn from the same generator.")
    m.append("3. The two shuffled lists are merged strictly alternating, so no "
             "two neighbours share a kind. The counts are exactly equal "
             "(%d = %d), so the alternation is perfect and nothing is left "
             "over." % (n_large, n_calm))
    m.append("")
    m.append("**Open question, not settled here (RULES 33).** \"Interleaved\" "
             "can be read two ways: strictly alternating, or merely mixed and "
             "not grouped by kind. This script implements the strict reading, "
             "which also satisfies the weaker one. It is recorded here so a "
             "jury can settle it rather than the data engineer settling it "
             "alone.")
    m.append("")
    m.append("Nothing in the order depends on a card's coin or its date. The "
             "only inputs are the card numbers and their kinds.")
    m.append("")
    m.append("## The measurement the batch size rests on")
    m.append("")
    m.append("Measured, exactly, from the %d files `cards/C001.md` .. "
             "`cards/C306.md`:" % len(cards))
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
             "installed on this machine (`tiktoken`, `transformers` and "
             "`anthropic` all raise `ModuleNotFoundError`), and the token "
             "count of the watcher model cannot be obtained without calling "
             "an API this script does not call. Every token number below is "
             "therefore an **estimate** and is labelled one.")
    m.append("")
    m.append("| assumption | value | why it is an assumption |")
    m.append("|---|---|---|")
    m.append("| bytes per token | %.1f (**estimate**) | the cards are "
             "number-heavy markdown tables, which tokenize worse than prose; "
             "no tokenizer available to measure it |"
             % ASSUMED_BYTES_PER_TOKEN)
    m.append("| watcher context window | %s tokens (**assumption**) | the "
             "watcher's model and window are not named in TACTICS 4 or in "
             "this run's instruction |" % f"{ASSUMED_CONTEXT_TOKENS:,}")
    m.append("| share of the window the cards may take | %d%% "
             "(**assumption**) | the rest is left for the instruction, tool "
             "overhead, the watcher's reasoning and its one note line per "
             "card (TACTICS 4 note format) |"
             % int(ASSUMED_CARD_SHARE_OF_CONTEXT * 100))
    m.append("")
    m.append("Arithmetic on those assumptions (**all estimates**): largest "
             "card ~%.0f tokens; largest batch of %d cards ~%.0f tokens, "
             "against a card budget of %.0f tokens (%.0f%% of the assumed "
             "window). Left for everything that is not a card - the "
             "instruction, tool overhead, the watcher's reasoning and its "
             "%d note lines - about %.0f tokens, i.e. the other %.0f%% of the "
             "window plus the %.0f tokens the cards did not use."
             % (tok_card_max, BATCH_SIZE, tok_batch_max, budget,
                ASSUMED_CARD_SHARE_OF_CONTEXT * 100, BATCH_SIZE,
                ASSUMED_CONTEXT_TOKENS - tok_batch_max,
                (1 - ASSUMED_CARD_SHARE_OF_CONTEXT) * 100,
                budget - tok_batch_max))
    m.append("")
    m.append("The total for all %d cards, on the same estimate, is ~%.0f "
             "tokens - which is why they cannot be read in one context and "
             "have to be batched at all."
             % (len(cards), total_bytes / ASSUMED_BYTES_PER_TOKEN))
    m.append("")
    m.append("A separate thing this run could **not** use: the pilot measured "
             "the real token cost of reading 10 cards (RULES 25). Those "
             "figures live outside the set of files this run was permitted to "
             "read, so they are not used here. If they were applied the "
             "bytes-per-token assumption above could be replaced by a "
             "measurement.")
    m.append("")
    m.append("## The batches")
    m.append("")
    m.append("%d batches of %d cards. A card's batch is decided by its "
             "position in the order and by nothing else - not its coin, not "
             "its kind, not its date." % (len(batches), BATCH_SIZE))
    m.append("")
    m.append("| batch | cards | positions | card bytes | file |")
    m.append("|---|---|---|---|---|")
    for bi, b in enumerate(batches, start=1):
        first = (bi - 1) * BATCH_SIZE + 1
        last = first + len(b) - 1
        m.append("| %02d | %d | %d-%d | %d | `data/card-order/batches/"
                 "batch-%02d.md` |" % (bi, len(b), first, last,
                                       batch_bytes[bi - 1], bi))
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
    m.append("| no two neighbours in the order share a kind | pass, %d "
             "adjacent pairs checked |" % (len(order) - 1))
    m.append("| the batches concatenated reproduce the order exactly | pass |")
    m.append("| **every card in exactly one batch** | **%s** - %d cards, %d "
             "batch slots, 0 duplicates, 0 missing |"
             % ("pass" if every_card_exactly_once else "FAIL",
                len(cards), len(flat)))
    m.append("")
    m.append("## Fingerprints")
    m.append("")
    m.append("| file | SHA-256 |")
    m.append("|---|---|")
    m.append("| `data/card-order/order.csv` | `%s` |" % order_sha)
    for name, sha in batch_shas:
        m.append("| `data/card-order/batches/%s` | `%s` |" % (name, sha))
    m.append("")
    m.append("Input fingerprints are in the seed table above.")
    m.append("")
    manifest_text = "\n".join(m)
    manifest_path = os.path.join(OUT_DIR, "order-manifest.md")
    status[manifest_path] = write_once(
        manifest_path, manifest_text,
        ignore_re=r"^Written by `scripts/11_card_order\.py` at ")

    print("WROTE")
    for p, s in status.items():
        print("  %-52s %s" % (os.path.relpath(p, ROOT), s))
    print("  every card in exactly one batch: %s" % every_card_exactly_once)
    print("  order.csv sha256: %s" % order_sha)
    if not every_card_exactly_once:
        sys.exit(1)


if __name__ == "__main__":
    main()
