#!/usr/bin/env python3
"""
15_event_collapse.py -- the event-collapse engine RULES 13 / TACTICS 7 need.

What it does
------------
Turns a list of moments (id, coin, kind, start hour) into a PARTITION into
events, under every candidate reading of "the same hour" that the written
rules allow, and measures each reading. It then calibrates what collapsing
does to a shuffle: the 1% boundary of the null distribution under a card-level
shuffle (what TACTICS 7 says today, uncollapsed) against a cluster-level
(block) shuffle over the events.

It also exposes `collapse()`, `identity_map()`, `block_shuffle_indices()`,
`check_block_shuffle()` and `chance_line()` so the later judge script imports
the same code instead of writing the rule a second time.

Input   : cards/C###.md  (default)  -- or --moments CSV with columns
          id,coin,kind,start_hour_utc  (ISO, e.g. 2026-05-07T20:00Z)
Output  : <out>/run-<run16>/events.csv
          <out>/run-<run16>/collapse-summary.csv
          <out>/run-<run16>/shuffle-calibration.csv
          <out>/run-<run16>/collapse-manifest.md
          <out>/runs/<run16>.json   (append-only)
          (<out> defaults to exam-prep/collapse.)

Changes made in the second-fix run (2026-10-01), acting on exam-prep/REVIEW.md
------------------------------------------------------------------------------
The version reviewed is git commit 7735d08, SHA-256 f3de2358...fb12; its run
`386d234b85269a21` and its outputs in exam-prep/collapse/ are kept untouched.
  1. block_shuffle_indices() is replaced (REVIEW §4.2). The reviewed version
     paired card positions index by index across events of different sizes,
     so it did not keep events whole. The replacement moves an event only onto
     an event of the same size, so every event reads all its answers from one
     source event and keeps its internal pattern. An event whose size no other
     event shares cannot move; check_block_shuffle() counts those.
  2. check_block_shuffle() tests the contract the docstring states (REVIEW
     §4.5 item 2). main() runs it on every configuration and on the review's
     three-event example before measuring, and stops on any failure.
     chance_line() also checks every block draw it makes.
  3. collapse() returns an EventMap: a list of events that also carries the
     configuration that made it and the moments it was made from.
     chance_line() refuses anything else, re-derives the map from its own
     moments and configuration before using it, and returns a record that
     carries the configuration, the event-map fingerprint and the counts
     (REVIEW §4.3, §4.5 item 4). The uncollapsed map can still be had, but
     only as identity_map(), which labels itself `none/none/none`.
  4. representative mode takes the full event map plus the caller's choice of
     one representative per event, instead of a pre-reduced list, so that the
     configuration survives into the record. Which card represents an event,
     and what label an event holding both kinds carries, remain open
     questions (exam-prep/second-fix/juror-questions/JQ-N1.md); this file
     does not choose either.
  5. Outputs go to a per-run directory and are never overwritten (RULES 30).
  6. The summary gains: events holding two or more cards of one coin, the
     largest such count (REVIEW §4.4), and the events and cards a block
     shuffle cannot move.

Changes made in the third-fix run (2026-10-01), acting on exam-prep/REVIEW-2.md
--------------------------------------------------------------------------------
The version REVIEW-2 reviewed has SHA-256 a0bcc600...8280 (recorded in
exam-prep/review-2/FINGERPRINTS.md); its run `756cf4ea156d92c3` and outputs
in exam-prep/collapse/run-756cf4ea156d92c3/ are kept untouched.
  7. chance_line() takes a REQUIRED keyword argument `key_moments_sha256` and
     refuses to run unless it equals the fingerprint of the moments the event
     map was made from (REVIEW-2 §4.3: an event map built by collapse() from
     forged moments was accepted under a collapsed label). The judge computes
     that value with moments_fingerprint() from the moments read out of the
     SEALED ANSWER KEY -- never from the event map itself, which would check
     nothing. The record carries `key_moments_sha256` and
     `key_check: "matched"`. This makes the comparison impossible to forget;
     it cannot by itself prove that the caller read the key, which is why
     exam-prep/HANDED-FORWARD.md requires it of the judge's script.
  8. moments_fingerprint(moments): the same canonical fingerprint as
     EventMap.moments_sha256(), computable from a plain moment list.
  9. main() passes the fingerprint of the moments it read (the cards, or the
     --moments CSV) and nothing else changed; events.csv, the summary and the
     calibration are expected byte-identical to run 756cf4ea156d92c3.

Changes made in the fourth-fix run (2026-10-01), acting on exam-prep/REVIEW-3.md
---------------------------------------------------------------------------------
The version REVIEW-3 reviewed has SHA-256 e59cecb7...2fe6; its run
`bec532fa008e0e01` and outputs are kept untouched. Criteria written before
measuring: exam-prep/fourth-fix/criteria-written-before-measuring.md (K-14,
K-15).
 10. The key check no longer reads a method of the object it checks
     (REVIEW-3 §4.2: replacing moments_sha256() on the instance, or
     overriding it in a subclass, let a map built from forged moments through
     with the true key). chance_line() and verify_event_map() refuse any
     object whose type is not exactly EventMap -- no subclass -- and
     chance_line() computes the moments fingerprint, the event-map
     fingerprint and the record from module functions over the map's data
     (_tuple_fingerprint(), event_map_fingerprint()), never from a method of
     the map. verify_event_map() also refuses a map whose configuration label
     is not the one its own fields make. What no in-process check can stop --
     a caller who edits this module's functions, or writes his own shuffle --
     is why exam-prep/HANDED-FORWARD.md also requires an independent
     recomputation of the event-map fingerprint from the sealed key.
 11. "Keep the latest" as worded (REVIEW-3 §4.3). collapse() takes
     `same_coin_keep`: "earliest" (default; the existing code path, unchanged)
     or "latest", allowed only with greedy-clique and cross-coin. "latest" is
     _greedy_literal(): JQ-N1 part 2 read word for word, over EVERY clock hour
     -- in each round the hour covered by the most coins among the still-
     unassigned moments wins, ties to the earliest hour; of each coin's
     moments covering that hour, the latest (start hour, then card number)
     joins the event. It is NOT the engine's anchored-window loop with the
     choice reversed, which REVIEW-3 q1 showed is a different rule. The
     configuration label of such a map ends in "+latest". Checked against
     REVIEW-3 q1's and REVIEW-2 p1b's literal implementations
     (scripts/30_fourth_fix_checks.py, H-2).

Rules implemented
-----------------
RULES 13  : "Moments occurring in several coins in the same hour count as a
            single event."  This script does not CHOOSE which reading of that
            sentence is right -- it builds all of them and measures them. The
            choice is an open question under RULES 33 and is named in
            exam-prep/N-1-collapse.md.
TACTICS 7 : "A moment appearing in several cards in the same hour counts as a
            single event."  Same sentence, same treatment.
RULES 12  : the shuffle count (1000) and the 1% boundary come from this rule,
            not from here.
RULES 19  : every number written is counted; nothing is estimated.
RULES 23  : the clock is read from the system.
RULES 28  : free disk space is read and recorded (no download happens).
RULES 29  : the run number is the SHA-256 of the inputs, including this file.
RULES 30  : the run record is append-only; differing content stops the script.

Constants -- where each came from
---------------------------------
SHUFFLES = 1000        RULES 12: "the answers are shuffled 1,000 times".
TOP_FRACTION = 0.01    RULES 12: "the real result must fall inside the best 1%".
SEED = 20260913        TACTICS 1's draw number, "written before the draw; it
                       does not change". Not a number chosen here.
MOVE_WINDOW_HOURS = 24 TACTICS 2: a moment is a 24-hour movement.
CARD_SPAN_HOURS  = 48  TACTICS 3 / the card text: before 24 h + after 24 h.
SELFTEST_DRAWS = 1000  the number of block draws each self-test makes: RULES
                       12's shuffle count, so the test sees every draw a
                       chance line would make.

No threshold, score or trading rule is defined anywhere in this file.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import shutil
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab_cards  # noqa: E402

SHUFFLES = 1000
TOP_FRACTION = 0.01
SEED = 20260913
MOVE_WINDOW_HOURS = 24
CARD_SPAN_HOURS = 48
SELFTEST_DRAWS = 1000

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DIR = os.path.join(REPO, "cards")
OUT_DIR = os.path.join(REPO, "exam-prep", "collapse")
RUNS_DIR = os.path.join(OUT_DIR, "runs")
ENGINE_PATH = os.path.abspath(__file__)

# The candidate readings of "in the same hour".  Each is a (name, rule) pair.
#   start-hour  : the moments begin in the same clock hour.
#                 (TACTICS 2: "A moment's start is the hour at which the
#                  24-hour movement began.")
#   move-window : the 24-hour movements themselves share a clock hour,
#                 i.e. |start gap| <= 23 h.
#   card-span   : the 48-hour card spans share a clock hour, i.e.
#                 |start gap| <= 47 h.  This is the relation measured by
#                 14_overlap_map.py.
DEFINITIONS = {
    "start-hour": 0,
    "move-window": MOVE_WINDOW_HOURS - 1,
    "card-span": CARD_SPAN_HOURS - 1,
}

# How an overlap relation that is not transitive is turned into a partition.
#   component    : transitive closure -- anything chained together is one event.
#   greedy-clique: repeatedly take the clock hour covered by the most
#                  still-unassigned moments (ties: earliest hour, then lowest
#                  id), make those moments one event, remove them, repeat.
#                  A stated convention, not an observation: some rule is needed
#                  because a set of overlapping intervals has no unique
#                  partition into "groups sharing an hour".
RESOLUTIONS = ("component", "greedy-clique")

# Whether two moments of the SAME coin may be merged.
#   any        : yes.
#   cross-coin : no -- RULES 13 says "in several coins", and same-coin spacing
#                is the separate open question Sofia refuses to answer (her §8).
SCOPES = ("any", "cross-coin")


def die(msg):
    sys.stderr.write("STOP: %s\n" % msg)
    sys.exit(1)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hour(s):
    s = s.strip().replace("Z", "")
    if len(s) == 16:                       # 2026-05-07T20:00
        s += ":00"
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=dt.timezone.utc)


def fmt_hour(t):
    return t.strftime("%Y-%m-%dT%H:00Z")


# ---------------------------------------------------------------------------
# The engine.  These are the functions a later script imports.
# ---------------------------------------------------------------------------

class EventMap(list):
    """A partition of moment ids into events that remembers how it was made.

    It is a list of events (each a sorted list of ids), so it can be used
    wherever the reviewed version's plain list was used. It also carries:
      .definition .resolution .scope .config   the configuration
      .moments   a tuple of (id, coin, start hour) it was made from
    chance_line() accepts nothing else, and re-derives the map from
    .moments and the configuration before using it.
    """

    def __init__(self, events, definition, resolution, scope, moments,
                 same_coin_keep="earliest"):
        super().__init__([sorted(ev) for ev in events])
        self.definition = definition
        self.resolution = resolution
        self.scope = scope
        self.same_coin_keep = same_coin_keep
        self.config = config_label(definition, resolution, scope,
                                   same_coin_keep)
        self.moments = tuple(sorted((m["id"], m["coin"],
                                     fmt_hour(m["start_dt"]))
                                    for m in moments))

    def moments_sha256(self):
        return hashlib.sha256(json.dumps(
            list(self.moments)).encode()).hexdigest()

    def sha256(self):
        """Fingerprint of the configuration, the moments and the events."""
        return hashlib.sha256(json.dumps(
            {"config": self.config, "moments": list(self.moments),
             "events": sorted(list(ev) for ev in self)},
            sort_keys=True).encode()).hexdigest()


def config_label(definition, resolution, scope, same_coin_keep="earliest"):
    """The configuration string. "earliest" adds nothing, so every label
    written before the fourth-fix run is unchanged; "latest" adds "+latest".
    """
    lab = "%s/%s/%s" % (definition, resolution, scope)
    return lab + "+latest" if same_coin_keep == "latest" else lab


def _tuple_fingerprint(tup):
    """SHA-256 of a moments tuple, by the formula moments_sha256() uses."""
    return hashlib.sha256(json.dumps(list(tup)).encode()).hexdigest()


def event_map_fingerprint(em):
    """SHA-256 of an EventMap's configuration, moments and events, by the
    formula EventMap.sha256() uses, computed without calling a method of the
    map (fourth-fix run, REVIEW-3 §4.2)."""
    return hashlib.sha256(json.dumps(
        {"config": em.config, "moments": list(em.moments),
         "events": sorted(list(ev) for ev in list.__iter__(em))},
        sort_keys=True).encode()).hexdigest()


def identity_map(moments):
    """The un-collapsed map: every moment its own event. It exists so that a
    card-level line can be computed on purpose and labelled as such; its
    configuration is `none/none/none` and every record made from it says so.
    """
    return EventMap([[m["id"]] for m in moments], "none", "none", "none",
                    moments)


def moments_fingerprint(moments):
    """The fingerprint EventMap.moments_sha256() carries, computed from a
    plain list of moments (dicts with id, coin, start_dt). The judge calls
    this on the moments read from the sealed answer key and passes the result
    to chance_line() as `key_moments_sha256` (third-fix run, REVIEW-2 §4.3).
    """
    tup = sorted((m["id"], m["coin"], fmt_hour(m["start_dt"]))
                 for m in moments)
    return hashlib.sha256(json.dumps(tup).encode()).hexdigest()


def _moments_from_tuple(tup):
    return [{"id": i, "coin": c, "start_dt": parse_hour(t)} for i, c, t in tup]


def verify_event_map(em):
    """Re-derive an EventMap from its own moments and configuration and
    refuse it if the events differ. A map edited by hand, or one carrying a
    configuration that did not make it, is refused."""
    # fourth-fix run: exactly EventMap, no subclass (REVIEW-3 §4.2)
    if type(em) is not EventMap:
        raise TypeError("events must be an EventMap returned by collapse() "
                        "or identity_map(), not a %s" % type(em).__name__)
    keep = getattr(em, "same_coin_keep", "earliest")
    if em.config != config_label(em.definition, em.resolution, em.scope,
                                 keep):
        raise ValueError("the event map's configuration label %r is not the "
                         "one its own fields make" % em.config)
    ms = _moments_from_tuple(em.moments)
    if em.config == "none/none/none":
        again = identity_map(ms)
    else:
        again = collapse(ms, em.definition, em.resolution, em.scope,
                         same_coin_keep=keep)
    if sorted(list(ev) for ev in again) != \
            sorted(list(ev) for ev in list.__iter__(em)):
        raise ValueError("the event map does not match what its own "
                         "configuration %s makes from its own moments"
                         % em.config)
    return True


def collapse(moments, definition="start-hour", resolution="component",
             scope="any", same_coin_keep="earliest"):
    """moments: list of dicts with id, coin, start_dt (datetime).

    Returns an EventMap: a list of events, each a list of moment ids, that
    partition the input exactly once, carrying the configuration that made
    it. Deterministic: no randomness.

    same_coin_keep (fourth-fix run): under greedy-clique with cross-coin,
    which moment of a coin joins an event when two or more of that coin's
    moments cover the chosen hour -- "earliest" (default, the existing path)
    or "latest" (_greedy_literal()). Refused with any other configuration.
    """
    return EventMap(_collapse_lists(moments, definition, resolution, scope,
                                    same_coin_keep),
                    definition, resolution, scope, moments, same_coin_keep)


def _whole_hour_index(t):
    """A start time as an integer clock-hour index; refuses a time that is
    not on the hour (a "clock hour" is then not defined)."""
    # utctimetuple(): an aware time is converted to UTC, a naive one is read
    # as it stands -- never through the machine's local time zone
    import calendar
    tt = t.utctimetuple()
    if tt.tm_min or tt.tm_sec or t.microsecond:
        raise ValueError("start time %s is not on a whole hour" % t)
    return calendar.timegm(tt) // 3600


def _greedy_literal(moments, gap, keep):
    """Greedy-clique under cross-coin, read word for word from JQ-N1 part 2
    (fourth-fix run, REVIEW-3 §4.3): in each round EVERY clock hour from the
    earliest still-unassigned start to the latest start plus `gap` is a
    candidate; a moment starting at hour s covers hours s .. s+gap (for
    card-span this is the card's span shifted by a constant 24 h, which
    changes neither the coverage counts nor which hour is earliest); the
    hour covered by the most COINS wins, ties to the earliest hour (at one
    hour there is only one set, so the card-number tie-break is never
    reached); of each coin's moments covering that hour, the `keep` one
    ("latest" or "earliest", by start hour, then card number) joins the
    event; repeat. The engine uses this for "latest"; "earliest" is here
    only so the check script can compare it with the engine's own path.
    """
    import bisect
    if keep not in ("earliest", "latest"):
        raise ValueError("same_coin_keep must be 'earliest' or 'latest'")
    left = sorted(((_whole_hour_index(m["start_dt"]), m["id"], m["coin"])
                   for m in moments))
    events = []
    while left:
        hs = [x[0] for x in left]
        best = None
        for H in range(hs[0], hs[-1] + gap + 1):
            lo = bisect.bisect_left(hs, H - gap)
            hi = bisect.bisect_right(hs, H)
            if lo >= hi:
                continue
            n_coins = len({x[2] for x in left[lo:hi]})
            if best is None or (-n_coins, H) < best[0]:
                best = ((-n_coins, H), lo, hi)
        _, lo, hi = best
        chosen = {}
        for x in left[lo:hi]:            # sorted by (start hour, id)
            if keep == "earliest":
                chosen.setdefault(x[2], x)
            else:
                chosen[x[2]] = x         # the last one seen is the latest
        ids = {x[1] for x in chosen.values()}
        events.append(sorted(ids))
        left = [x for x in left if x[1] not in ids]
    events.sort(key=lambda g: g[0])
    return events


def _collapse_lists(moments, definition, resolution, scope,
                    same_coin_keep="earliest"):
    """The reviewed collapse() body, unchanged for "earliest": returns plain
    lists. "latest" goes to _greedy_literal() (fourth-fix run)."""
    if definition not in DEFINITIONS:
        raise ValueError("unknown definition %r" % definition)
    if resolution not in RESOLUTIONS:
        raise ValueError("unknown resolution %r" % resolution)
    if scope not in SCOPES:
        raise ValueError("unknown scope %r" % scope)
    if same_coin_keep not in ("earliest", "latest"):
        raise ValueError("unknown same_coin_keep %r" % same_coin_keep)

    gap = DEFINITIONS[definition]
    if same_coin_keep == "latest":
        if not (resolution == "greedy-clique" and scope == "cross-coin"
                and definition != "start-hour"):
            raise ValueError("same_coin_keep='latest' exists only for "
                             "greedy-clique with cross-coin under move-window "
                             "or card-span; %s/%s/%s has no such choice"
                             % (definition, resolution, scope))
        return _greedy_literal(moments, gap, "latest")
    items = sorted(moments, key=lambda m: (m["start_dt"], m["id"]))

    def joinable(a, b):
        if scope == "cross-coin" and a["coin"] == b["coin"]:
            return False
        d = abs((a["start_dt"] - b["start_dt"]).total_seconds()) / 3600.0
        return d <= gap

    if resolution == "component" or definition == "start-hour":
        # union-find over the joinable relation
        parent = {m["id"]: m["id"] for m in items}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[max(rx, ry)] = min(rx, ry)

        for i, a in enumerate(items):
            for b in items[i + 1:]:
                d = (b["start_dt"] - a["start_dt"]).total_seconds() / 3600.0
                if d > gap:
                    break
                if joinable(a, b):
                    union(a["id"], b["id"])
        groups = defaultdict(list)
        for m in items:
            groups[find(m["id"])].append(m["id"])
        events = [sorted(v) for v in groups.values()]
        events.sort(key=lambda g: g[0])
        return events

    # greedy-clique
    left = list(items)
    events = []
    while left:
        # candidate clock hours: every moment's start hour, and every hour a
        # moment's window reaches back to. A covering window of width `gap`
        # only needs to be tried with its left edge at some moment's start.
        best = None
        for anchor in left:
            lo = anchor["start_dt"]
            members = [m for m in left
                       if 0 <= (m["start_dt"] - lo).total_seconds() / 3600.0
                       <= gap]
            if scope == "cross-coin":
                seen, keep = set(), []
                for m in members:            # at most one card per coin
                    if m["coin"] in seen:
                        continue
                    seen.add(m["coin"])
                    keep.append(m)
                members = keep
            key = (-len(members), lo, members[0]["id"])
            if best is None or key < best[0]:
                best = (key, members)
        members = best[1]
        events.append(sorted(m["id"] for m in members))
        ids = {m["id"] for m in members}
        left = [m for m in left if m["id"] not in ids]
    events.sort(key=lambda g: g[0])
    return events


def _blocks(events, id_order):
    pos = {cid: i for i, cid in enumerate(id_order)}
    return [sorted(pos[c] for c in ev) for ev in events]


def block_shuffle_indices(events, id_order, rng):
    """One cluster-level (block) permutation.

    Returns a list of positions: position i of the returned list says which
    card's answer is read for card i. Whole events keep their internal
    pattern; only whole events are moved. This is what a shuffle must do when
    the cards inside an event are not independent observations (RULES 13).

    How (second-fix run, replacing the reviewed version -- REVIEW §4.2): an
    event is moved only onto an event of the SAME SIZE, because only then can
    every card of the target read one card of the source. Inside a pair of
    events the k-th card (in `id_order` position) reads the k-th card. Sizes
    are visited in the order in which they first occur in `events`; for each
    size the events of that size are shuffled once with `rng`.

    Consequence, stated rather than hidden: an event whose size no other
    event shares cannot move at all. check_block_shuffle() counts those
    events and the cards in them.
    """
    blocks = _blocks(events, id_order)
    bysize = {}
    for k, b in enumerate(blocks):
        bysize.setdefault(len(b), []).append(k)
    out = [None] * len(id_order)
    for size, ks in bysize.items():
        tgt = list(ks)
        rng.shuffle(tgt)
        for a, b in zip(ks, tgt):
            for s, d in zip(blocks[a], blocks[b]):
                out[s] = d
    if any(o is None for o in out):
        raise ValueError("block shuffle left a card without a source; the "
                         "events do not cover id_order")
    return out


def _check_one_draw(idx, blocks, n):
    """True if a draw is a permutation in which every event reads all its
    answers from exactly one source event of the same size."""
    if sorted(idx) != list(range(n)):
        return False, "not a permutation of the card positions"
    owner = {}
    for k, b in enumerate(blocks):
        for p in b:
            owner[p] = k
    for b in blocks:
        src = {owner[idx[p]] for p in b}
        if len(src) != 1:
            return False, "an event read its answers from %d source events" \
                % len(src)
        if len(blocks[src.pop()]) != len(b):
            return False, "an event read from a source of a different size"
    return True, ""


def check_block_shuffle(events, id_order, draws=SELFTEST_DRAWS, seed=SEED):
    """The test REVIEW §4.5 item 2 asks for, and two more.

    On `draws` draws of block_shuffle_indices():
      (a) every draw is a permutation of the card positions;
      (b) every event reads all its answers from one source event of its own
          size;
      (c) an answer vector that is constant inside each event (a different
          value per event) is still constant inside each event.
    Raises ValueError on the first failure. Returns the counts, plus how many
    events (and cards) can never move because no other event shares their
    size.
    """
    blocks = _blocks(events, id_order)
    n = len(id_order)
    const = [None] * n
    for k, b in enumerate(blocks):
        for p in b:
            const[p] = k
    rng = random.Random(seed)
    for t in range(draws):
        idx = block_shuffle_indices(events, id_order, rng)
        ok, why = _check_one_draw(idx, blocks, n)
        if not ok:
            raise ValueError("block shuffle draw %d: %s" % (t, why))
        permuted = [const[i] for i in idx]
        for b in blocks:
            if len({permuted[p] for p in b}) != 1:
                raise ValueError("block shuffle draw %d: an event-constant "
                                 "vector stopped being event-constant" % t)
    sizes = Counter(len(b) for b in blocks)
    immovable = [b for b in blocks if sizes[len(b)] == 1]
    return {"draws": draws, "seed": seed,
            "permutation_ok": draws, "single_source_ok": draws,
            "event_constant_preserved": draws,
            "events": len(blocks),
            "immovable_events": len(immovable),
            "cards_in_immovable_events": sum(len(b) for b in immovable)}


def quantile_top(values, fraction):
    """The boundary of the best `fraction` of a null distribution: the value
    such that only `fraction` of draws are >= it. RULES 12's "best 1%"."""
    s = sorted(values, reverse=True)
    idx = max(0, int(round(fraction * len(s))) - 1)
    return s[idx]


def chance_line(answers, labels, events, id_order, mode,
                representatives=None, shuffles=SHUFFLES,
                fraction=TOP_FRACTION, seed=SEED, *, key_moments_sha256):
    """The RULES 12 chance line, computed so that it CANNOT be computed
    without an event map, and so that its result carries the map.

    answers / labels : one entry per id, in `id_order`.
    events           : an EventMap from collapse() or identity_map(). A plain
                       list is refused. The map is re-derived from its own
                       moments and configuration before use.
    mode             : "block"          -- keep every card, permute whole
                                           events (cluster-level permutation);
                       "representative" -- keep one card per event; the
                                           caller names it in
                                           `representatives` (one id per
                                           event). Which card that is, and
                                           which label an event holding both
                                           kinds carries (pass it as that
                                           card's entry in `labels`), are
                                           open questions this function does
                                           not answer.
    There is deliberately no card-level mode and no default mode: TACTICS 7
    says a moment appearing in several cards in the same hour counts as a
    single event. The un-collapsed line can only be had by passing
    identity_map(), and the record then says `none/none/none` and
    `identity_partition: true`.

    Returns a dict (the second-fix run changed this from a 3-tuple, REVIEW
    §4.5 item 4): observed, boundary, null, and the record of what produced
    them -- mode, config, event_map_sha256, moments_sha256, cards, events,
    n_in_null, identity_partition, immovable_events, cards_in_immovable_events
    (block mode), representatives_sha256 (representative mode), shuffles,
    top_fraction, seed, engine_sha256, key_moments_sha256, key_check.

    key_moments_sha256 (required, keyword only; third-fix run): the
    moments_fingerprint() of the moments read from the sealed answer key. The
    function refuses unless the event map was made from exactly those moments.
    """
    if mode not in ("block", "representative"):
        raise ValueError("mode must be 'block' or 'representative'")
    # fourth-fix run (REVIEW-3 §4.2): exactly EventMap, and every fingerprint
    # computed here by module functions, never by a method of the map
    if type(events) is not EventMap:
        raise TypeError("events must be an EventMap returned by collapse() "
                        "or identity_map(), not a %s" % type(events).__name__)
    verify_event_map(events)
    map_moments_sha = _tuple_fingerprint(events.moments)
    if not isinstance(key_moments_sha256, str) or \
            key_moments_sha256 != map_moments_sha:
        raise ValueError("the event map was not made from the moments of the "
                         "answer key: its moments fingerprint %s is not the "
                         "key's %r" % (map_moments_sha[:16],
                                       str(key_moments_sha256)[:16]))
    if not (len(answers) == len(labels) == len(id_order)):
        raise ValueError("answers, labels and id_order must be the same length")
    flat = sorted(c for ev in events for c in ev)
    if flat != sorted(id_order) or len(set(id_order)) != len(id_order):
        raise ValueError("the events do not partition id_order exactly")
    if sorted(m[0] for m in events.moments) != sorted(id_order):
        raise ValueError("the event map was made from different moments")
    rec = {"mode": mode, "config": events.config,
           "event_map_sha256": event_map_fingerprint(events),
           "moments_sha256": map_moments_sha,
           "cards": len(id_order), "events": len(events),
           "identity_partition": all(len(ev) == 1 for ev in events),
           "shuffles": shuffles, "top_fraction": fraction, "seed": seed,
           "engine_sha256": sha256_file(ENGINE_PATH),
           "key_moments_sha256": key_moments_sha256,
           "key_check": "matched"}
    rng = random.Random(seed)
    null = []
    if mode == "block":
        observed = sum(1 for a, l in zip(answers, labels)
                       if a == l) / len(labels)
        blocks = _blocks(events, id_order)
        for t in range(shuffles):
            idx = block_shuffle_indices(events, id_order, rng)
            ok, why = _check_one_draw(idx, blocks, len(id_order))
            if not ok:
                raise ValueError("block draw %d: %s" % (t, why))
            null.append(sum(1 for i, l in zip(idx, labels)
                            if answers[i] == l) / len(labels))
        sizes = Counter(len(b) for b in blocks)
        rec["immovable_events"] = sum(1 for b in blocks if sizes[len(b)] == 1)
        rec["cards_in_immovable_events"] = sum(len(b) for b in blocks
                                               if sizes[len(b)] == 1)
        rec["n_in_null"] = len(id_order)
    else:
        if representatives is None:
            raise ValueError("representative mode needs `representatives`: "
                             "one id per event, chosen by the caller")
        reps = list(representatives)
        owner = {c: k for k, ev in enumerate(events) for c in ev}
        if (len(reps) != len(events) or len(set(reps)) != len(reps)
                or any(r not in owner for r in reps)
                or len({owner[r] for r in reps}) != len(events)):
            raise ValueError("`representatives` must name exactly one card "
                             "of every event")
        pos = {c: i for i, c in enumerate(id_order)}
        rep_sorted = sorted(reps, key=lambda c: pos[c])
        r_answers = [answers[pos[c]] for c in rep_sorted]
        r_labels = [labels[pos[c]] for c in rep_sorted]
        observed = sum(1 for a, l in zip(r_answers, r_labels)
                       if a == l) / len(r_labels)
        perm = list(r_answers)
        for _ in range(shuffles):
            rng.shuffle(perm)
            null.append(sum(1 for a, l in zip(perm, r_labels)
                            if a == l) / len(r_labels))
        rec["representatives_sha256"] = hashlib.sha256(
            json.dumps(rep_sorted).encode()).hexdigest()
        rec["n_in_null"] = len(rep_sorted)
    rec["observed"] = observed
    rec["boundary"] = quantile_top(null, fraction)
    rec["null"] = null
    return rec


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moments", default=None,
                    help="CSV with id,coin,kind,start_hour_utc; "
                         "default: read the 306 observation cards")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    started = dt.datetime.now(dt.timezone.utc)
    free_bytes = shutil.disk_usage(REPO).free

    # ---- input -------------------------------------------------------------
    input_desc = []
    moments = []
    if args.moments:
        with open(args.moments, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                moments.append({"id": row["id"], "coin": row["coin"],
                                "kind": row["kind"],
                                "start_dt": parse_hour(row["start_hour_utc"])})
        input_desc.append((os.path.relpath(args.moments, REPO),
                           sha256_file(args.moments)))
    else:
        cards = lab_cards.load_all(CARDS_DIR)
        for c in cards:
            moments.append({"id": c["card"], "coin": c["coin"],
                            "kind": c["kind"],
                            "start_dt": parse_hour(c["start_hour_utc"])})
            input_desc.append(("cards/%s.md" % c["card"], c["sha256"]))
    if not moments:
        die("no moments read")
    ids = [m["id"] for m in moments]
    if len(set(ids)) != len(ids):
        die("duplicate moment ids in the input")
    by_id = {m["id"]: m for m in moments}
    id_order = sorted(ids)
    # third-fix run: the fingerprint of the moments this run read (the cards,
    # or the --moments CSV); every chance_line() call is checked against it
    key_sha = moments_fingerprint(moments)

    # ---- run number (RULES 29) --------------------------------------------
    script_sha = sha256_file(os.path.abspath(__file__))
    h = hashlib.sha256()
    h.update(("script:" + script_sha + "\n").encode())
    h.update(("module:" + sha256_file(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "lab_cards.py")) + "\n").encode())
    h.update(("shuffles:%d;top:%s;seed:%d\n"
              % (SHUFFLES, TOP_FRACTION, SEED)).encode())
    for name, sha in sorted(input_desc):
        h.update(("%s:%s\n" % (name, sha)).encode())
    run_full = h.hexdigest()
    run16 = run_full[:16]

    # ---- every configuration ----------------------------------------------
    configs = [("none", "none", "none")]
    for d in ("start-hour", "move-window", "card-span"):
        for r in (["component"] if d == "start-hour" else list(RESOLUTIONS)):
            for s in SCOPES:
                configs.append((d, r, s))

    # ---- the block-shuffle self-test on the review's own example ----------
    # (REVIEW §4.2: events [[c0,c1,c2],[c3],[c4,c5]].) Run before anything
    # is measured; any failure stops the script.
    try:
        ex_moments = [{"id": "c%d" % i, "coin": "x", "kind": "calm",
                       "start_dt": parse_hour("2026-01-01T00:00Z")}
                      for i in range(6)]
        ex_ids = ["c0", "c1", "c2", "c3", "c4", "c5"]
        ex_events = EventMap([["c0", "c1", "c2"], ["c3"], ["c4", "c5"]],
                             "example", "example", "example", ex_moments)
        selftest_example = check_block_shuffle(ex_events, ex_ids)
    except ValueError as e:
        die("block-shuffle self-test failed on the review's example: %s" % e)

    event_rows = []
    summary_rows = []
    partitions = {}
    selftests = {}
    for (d, r, s) in configs:
        cfg = "%s/%s/%s" % (d, r, s)
        if d == "none":
            events = identity_map(moments)
        else:
            events = collapse(moments, d, r, s)
        if events.config != cfg:
            die("configuration label mismatch: %s vs %s" % (events.config,
                                                             cfg))
        # the partition must be exact -- check it, do not assume it
        flat = [c for ev in events for c in ev]
        if sorted(flat) != id_order:
            die("configuration %s did not partition the moments exactly" % cfg)
        partitions[cfg] = events
        try:
            selftests[cfg] = check_block_shuffle(events, id_order)
        except ValueError as e:
            die("block-shuffle self-test failed on %s: %s" % (cfg, e))

        sizes = Counter(len(ev) for ev in events)
        same_coin = [max(Counter(by_id[c]["coin"] for c in ev).values())
                     for ev in events]
        mixed_kind = sum(1 for ev in events
                         if len({by_id[c]["kind"] for c in ev}) > 1)
        mixed_coin = sum(1 for ev in events
                         if len({by_id[c]["coin"] for c in ev}) > 1)
        singletons = sizes.get(1, 0)
        largest = max(len(ev) for ev in events)
        # design effect: how many cards one event holds on average
        summary_rows.append({
            "config": cfg,
            "definition": d, "resolution": r, "scope": s,
            "cards": len(id_order),
            "events": len(events),
            "cards_per_event_mean": round(len(id_order) / len(events), 4),
            "events_of_size_1": singletons,
            "largest_event": largest,
            "events_holding_both_kinds": mixed_kind,
            "events_holding_more_than_one_coin": mixed_coin,
            "cards_in_events_of_size_1": singletons,
            "size_histogram": " ".join("%d:%d" % (k, sizes[k])
                                       for k in sorted(sizes)),
            "events_holding_2plus_cards_of_one_coin":
                sum(1 for x in same_coin if x >= 2),
            "largest_same_coin_count_in_one_event": max(same_coin),
            "block_immovable_events": selftests[cfg]["immovable_events"],
            "block_cards_in_immovable_events":
                selftests[cfg]["cards_in_immovable_events"],
            "event_map_sha256": events.sha256(),
        })
        for i, ev in enumerate(sorted(events, key=lambda g: (
                min(by_id[c]["start_dt"] for c in g), g[0])), 1):
            eid = "E%04d" % i
            kinds = sorted({by_id[c]["kind"] for c in ev})
            for c in ev:
                event_rows.append({
                    "config": cfg, "event_id": eid, "event_size": len(ev),
                    "card": c, "coin": by_id[c]["coin"],
                    "kind": by_id[c]["kind"],
                    "start_hour_utc": fmt_hour(by_id[c]["start_dt"]),
                    "event_kinds": "+".join(kinds),
                    "event_first_hour_utc": fmt_hour(
                        min(by_id[c2]["start_dt"] for c2 in ev)),
                    "event_last_hour_utc": fmt_hour(
                        max(by_id[c2]["start_dt"] for c2 in ev)),
                })

    # ---- shuffle calibration ----------------------------------------------
    # Two SYNTHETIC answer vectors, drawn from the fixed seed and labelled
    # synthetic. They are calibration input for the instrument, not a result
    # about any rule: no rule from the canteen book is evaluated here.
    labels = [1 if by_id[c]["kind"] == "large" else 0 for c in id_order]
    calib_rows = []
    for cfg, events in partitions.items():
        for predictor in ("synthetic-iid", "synthetic-event-constant"):
            rng = random.Random(SEED)
            if predictor == "synthetic-iid":
                answers = [rng.randint(0, 1) for _ in id_order]
            else:
                # one draw per event of THIS configuration, repeated inside it
                answers = [None] * len(id_order)
                pos = {c: i for i, c in enumerate(id_order)}
                for ev in events:
                    v = rng.randint(0, 1)
                    for c in ev:
                        answers[pos[c]] = v
            observed = sum(1 for a, l in zip(answers, labels)
                           if a == l) / len(labels)

            rng_card = random.Random(SEED)
            null_card = []
            perm = list(answers)
            for _ in range(SHUFFLES):
                rng_card.shuffle(perm)
                null_card.append(sum(1 for a, l in zip(perm, labels)
                                     if a == l) / len(labels))

            # The block column goes through chance_line(), the interface a
            # judge imports, so the record it returns is exercised here too.
            blk = chance_line(answers, labels, events, id_order, "block",
                              key_moments_sha256=key_sha)
            if blk["config"] != cfg or abs(blk["observed"] - observed) > 1e-12:
                die("chance_line record disagrees with the calibration on %s"
                    % cfg)
            null_block = blk["null"]

            # Mode A -- representative collapse: keep ONE card per event
            # (the earliest start hour, ties by lowest id) and shuffle over
            # that reduced set. This is the reading of RULES 13 that literally
            # replaces an event by a single observation, and it is the one
            # that changes the width of the null the most, because the null
            # is then drawn over n = events, not n = cards.
            reps = [sorted(ev, key=lambda c: (by_id[c]["start_dt"], c))[0]
                    for ev in events]
            rep_labels = [1 if by_id[c]["kind"] == "large" else 0
                          for c in reps]
            rng_rep = random.Random(SEED)
            rep_answers = [rng_rep.randint(0, 1) for _ in reps]
            null_rep = []
            for _ in range(SHUFFLES):
                rng_rep.shuffle(rep_answers)
                null_rep.append(sum(1 for a, l in zip(rep_answers, rep_labels)
                                    if a == l) / len(rep_labels))

            calib_rows.append({
                "config": cfg,
                "predictor": predictor,
                "representative_n": len(reps),
                "representative_shuffle_1pct_boundary": round(
                    quantile_top(null_rep, TOP_FRACTION), 6),
                "shuffles": SHUFFLES,
                "seed": SEED,
                "observed_accuracy": round(observed, 6),
                "card_shuffle_1pct_boundary": round(
                    quantile_top(null_card, TOP_FRACTION), 6),
                "card_shuffle_max": round(max(null_card), 6),
                "block_shuffle_1pct_boundary": round(
                    quantile_top(null_block, TOP_FRACTION), 6),
                "block_shuffle_max": round(max(null_block), 6),
                "block_immovable_events": blk["immovable_events"],
                "block_cards_in_immovable_events":
                    blk["cards_in_immovable_events"],
                "event_map_sha256": blk["event_map_sha256"],
            })

    # ---- write (RULES 30: a run directory is written once) ------------------
    import io

    def csv_text(rows):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()),
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    data = {"events.csv": csv_text(event_rows),
            "collapse-summary.csv": csv_text(summary_rows),
            "shuffle-calibration.csv": csv_text(calib_rows)}
    data_sha = {k: hashlib.sha256(v.encode("utf-8")).hexdigest()
                for k, v in data.items()}

    runs_dir = os.path.join(args.out, "runs")
    run_dir = os.path.join(args.out, "run-" + run16)
    core = {
        "run": run16, "input_fingerprint": run_full,
        "moments": len(id_order), "configurations": len(configs),
        "shuffles": SHUFFLES, "seed": SEED, "top_fraction": TOP_FRACTION,
        "events_by_config": {r["config"]: r["events"] for r in summary_rows},
        "event_map_sha256_by_config": {r["config"]: r["event_map_sha256"]
                                       for r in summary_rows},
        "block_shuffle_selftest": {"review_example": selftest_example,
                                   "by_config": selftests},
        "output_sha256": data_sha,
        "output_dir": os.path.relpath(run_dir, REPO),
        "script_sha256": script_sha,
        "key_moments_sha256": key_sha,
    }
    rec_path = os.path.join(runs_dir, run16 + ".json")
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as fh:
            old = json.load(fh)
        differ = [k for k, v in json.loads(json.dumps(core)).items()
                  if old.get(k) != v]
        if differ:
            die("run record %s exists and disagrees on %s (RULES 30: records "
                "are append-only); no output file was touched"
                % (rec_path, ", ".join(sorted(differ))))
        for name, text in data.items():
            p = os.path.join(run_dir, name)
            if not os.path.exists(p) or sha256_file(p) != data_sha[name]:
                die("run %s is recorded but %s is missing or differs"
                    % (run16, p))
        sys.stderr.write("run %s is already recorded with identical outputs; "
                         "nothing written\n" % run16)
        return
    for name in data:
        p = os.path.join(run_dir, name)
        if os.path.exists(p) and sha256_file(p) != data_sha[name]:
            die("%s exists with different content and no run record "
                "(RULES 30)" % p)
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(runs_dir, exist_ok=True)
    prior = sorted(f[:-5] for f in os.listdir(runs_dir) if f.endswith(".json"))
    if run16 not in prior:
        prior.append(run16)
    for name, text in data.items():
        with open(os.path.join(run_dir, name), "w", encoding="utf-8",
                  newline="") as fh:
            fh.write(text)
    ev_path = os.path.join(run_dir, "events.csv")
    sm_path = os.path.join(run_dir, "collapse-summary.csv")
    cb_path = os.path.join(run_dir, "shuffle-calibration.csv")

    # ---- manifest ----------------------------------------------------------
    A = []
    A.append("# Collapse manifest — the event map RULES 13 needs")
    A.append("")
    A.append("Written by `scripts/15_event_collapse.py`. It builds every "
             "candidate reading of RULES 13's \"the same hour\" and measures "
             "each. **It chooses none of them.** The choice is an open "
             "question under RULES 33; see "
             "`exam-prep/second-fix/juror-questions/JQ-N1.md`.")
    A.append("")
    A.append("## Run")
    A.append("")
    A.append("| field | value |")
    A.append("|---|---|")
    A.append("| run number (SHA-256 of the inputs, RULES 29) | `%s` |" % run16)
    A.append("| full input fingerprint | `%s` |" % run_full)
    A.append("| written at (system clock, UTC, RULES 23) | %s |"
             % started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    A.append("| free disk space at start (bytes) | %d |" % free_bytes)
    A.append("| moments read | %d |" % len(id_order))
    A.append("| input | %s |" % ("`%s`" % os.path.relpath(args.moments, REPO)
                                 if args.moments
                                 else "the %d cards in `cards/`"
                                      % len(id_order)))
    A.append("| shuffles (RULES 12) | %d |" % SHUFFLES)
    A.append("| boundary (RULES 12) | best %s%% |" % (TOP_FRACTION * 100))
    A.append("| seed (TACTICS 1 draw number) | `%d` |" % SEED)
    A.append("| `scripts/15_event_collapse.py` SHA-256 | `%s` |" % script_sha)
    A.append("")
    A.append("Run records live in `runs/`, one JSON per run number, "
             "append-only (RULES 30). Records present when this manifest was "
             "written: %s. The outputs of run `386d234b85269a21` (the version "
             "reviewed in `exam-prep/REVIEW.md`) are the files directly in "
             "`exam-prep/collapse/` and are not touched by later runs; every "
             "later run writes into its own `run-<number>/` directory."
             % ", ".join("`%s`" % p for p in prior))
    A.append("")
    A.append("## The block-shuffle self-test")
    A.append("")
    A.append("Before anything is measured the script checks, on %d draws per "
             "event map (seed `%d`), that every block draw is a permutation, "
             "that every event reads all its answers from one source event "
             "of its own size, and that an event-constant answer vector stays "
             "event-constant. It stops on the first failure. It passed on the "
             "review's three-event example and on all %d configurations."
             % (SELFTEST_DRAWS, SEED, len(configs)))
    A.append("")
    A.append("## The candidate readings")
    A.append("")
    A.append("| name | what counts as \"the same hour\" | largest start gap "
             "that still merges |")
    A.append("|---|---|---|")
    A.append("| `start-hour` | the two moments begin in the same clock hour "
             "(TACTICS 2: a moment's start is the hour the 24-hour movement "
             "began) | 0 h |")
    A.append("| `move-window` | the two 24-hour movements share a clock hour "
             "| 23 h |")
    A.append("| `card-span` | the two 48-hour card spans share a clock hour "
             "— the relation `14_overlap_map.py` measured | 47 h |")
    A.append("")
    A.append("`component` = anything chained together is one event. "
             "`greedy-clique` = repeatedly take the clock hour covered by the "
             "most still-unassigned moments (ties: earliest hour, then lowest "
             "id). `greedy-clique` is a **stated convention**, not an "
             "observation: overlapping intervals have no unique partition into "
             "\"groups sharing an hour\", so some deterministic rule is needed "
             "and this one is written down so it can be disagreed with.")
    A.append("")
    A.append("`any` = two moments of the same coin may be joined directly. "
             "`cross-coin` = two moments of the same coin are never joined "
             "**directly**. Under `greedy-clique` that means no event holds "
             "two moments of one coin. Under `component` it does **not**: a "
             "component is a chain, and two moments of one coin still land in "
             "one event when both are joined to a moment of another coin. The "
             "column \"events holding 2+ cards of one coin\" below counts it.")
    A.append("")
    A.append("## What each reading counts")
    A.append("")
    A.append("| configuration | events | cards per event | events of size 1 | "
             "largest event | events holding both kinds | events holding more "
             "than one coin | events holding 2+ cards of one coin | largest "
             "same-coin count | block: events that cannot move | block: cards "
             "in them |")
    A.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in summary_rows:
        A.append("| `%s` | %d | %.2f | %d | %d | %d | %d | %d | %d | %d | %d |"
                 % (r["config"], r["events"], r["cards_per_event_mean"],
                    r["events_of_size_1"], r["largest_event"],
                    r["events_holding_both_kinds"],
                    r["events_holding_more_than_one_coin"],
                    r["events_holding_2plus_cards_of_one_coin"],
                    r["largest_same_coin_count_in_one_event"],
                    r["block_immovable_events"],
                    r["block_cards_in_immovable_events"]))
    A.append("")
    A.append("\"Events holding both kinds\": an event holding a `large` card "
             "and a `calm` card has no single label. \"Block: events that "
             "cannot move\": an event whose size no other event shares is "
             "mapped onto itself in every block draw.")
    A.append("")
    A.append("## What collapsing does to a shuffle")
    A.append("")
    A.append("RULES 12 fixes the shuffle at 1,000 draws and the line at the "
             "best 1%%. The two answer vectors below are **synthetic**, drawn "
             "from seed `%d`: `synthetic-iid` is one independent coin flip per "
             "card, `synthetic-event-constant` is one coin flip per event of "
             "the same configuration, repeated on every card in it. No rule "
             "from the canteen book is evaluated here and no result about any "
             "rule is produced. The block column is computed through "
             "`chance_line()`. The representative column keeps, for this "
             "calibration only, the earliest card of each event (ties: lowest "
             "id); that is not a ruling on which card represents an event."
             % SEED)
    A.append("")
    A.append("| configuration | predictor | n cards | card-level shuffle · "
             "1% boundary | cluster-level (block) shuffle · 1% boundary | "
             "n events | representative-collapse shuffle · 1% boundary |")
    A.append("|---|---|---|---|---|---|---|")
    for r in calib_rows:
        A.append("| `%s` | %s | %d | %.4f | %.4f | %d | %.4f |"
                 % (r["config"], r["predictor"], len(id_order),
                    r["card_shuffle_1pct_boundary"],
                    r["block_shuffle_1pct_boundary"],
                    r["representative_n"],
                    r["representative_shuffle_1pct_boundary"]))
    A.append("")
    A.append("## Fingerprints")
    A.append("")
    A.append("| file | rows | SHA-256 |")
    A.append("|---|---|---|")
    for p, n in ((ev_path, len(event_rows)), (sm_path, len(summary_rows)),
                 (cb_path, len(calib_rows))):
        A.append("| `%s` | %d | `%s` |"
                 % (os.path.relpath(p, REPO), n, sha256_file(p)))
    A.append("")
    man_path = os.path.join(run_dir, "collapse-manifest.md")
    with open(man_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(A) + "\n")
    with open(man_path + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(sha256_file(man_path) + "  collapse-manifest.md\n")

    with open(rec_path, "w", encoding="utf-8") as fh:
        json.dump(core, fh, indent=1, sort_keys=True)
        fh.write("\n")
    sys.stderr.write("run %s: %d moments, %d configurations -> %s\n"
                     % (run16, len(id_order), len(configs),
                        os.path.relpath(run_dir, REPO)))


if __name__ == "__main__":
    main()
