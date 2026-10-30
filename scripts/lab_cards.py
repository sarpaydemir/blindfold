#!/usr/bin/env python3
"""
lab_cards.py -- shared card reader for the exam-preparation scripts.

What it does : parses an observation card written by 09_write_cards.py into a
               plain dict, so that 15_event_collapse.py, 16_identity_audit.py
               and 17_blind_cards.py all read the same text the same way.
Input        : one card file, cards/C###.md
Output       : a dict (in memory). Writes nothing.

Rules implemented
-----------------
RULES 19 : nothing here estimates a number. Every value returned is a literal
           read off the card, converted only by the documented k/M/G suffix
           expansion that 09_write_cards.py used to write it.
RULES 29 : the SHA-256 of each card file is returned with the card, so that a
           caller can fold it into its run number.

Nothing in this module chooses a threshold, a score or a rule. It reads.
"""

import hashlib
import os
import re

# The single table header shared by all 612 tables of the 306 cards, verified
# at parse time. Column order comes from that header, not from judgement.
TABLE_HEADER = ("| h | close | chg% | quote vol | trades | taker buy% | "
                "open int | L/S acct | top L/S pos | taker L/S | depth -1% | "
                "depth +1% | BTC | ETH |")

COLUMNS = ["h", "close", "chg%", "quote vol", "trades", "taker buy%",
           "open int", "L/S acct", "top L/S pos", "taker L/S", "depth -1%",
           "depth +1%", "BTC", "ETH"]

BEFORE_OFFSETS = tuple(range(-24, 0))    # card rows -24 .. -1
AFTER_OFFSETS = tuple(range(0, 24))      # card rows +0 .. +23

# Suffixes 09_write_cards.py uses when it shortens a number. Read off the
# cards: only k and M occur in the 306 observation cards; G and B are listed
# because the writer can emit them and a later card set may contain them.
SUFFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "B": 1e9}

_NUM_RE = re.compile(r"^[-+]?[0-9]*\.?[0-9]+([kMGB])?$")


class CardError(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_number(tok):
    """'122.69k' -> 122690.0 ; '.' -> None ; '+0.49' -> 0.49"""
    tok = tok.strip()
    if tok in (".", "", "-"):
        return None
    m = _NUM_RE.match(tok)
    if not m:
        raise CardError("not a number: %r" % tok)
    if m.group(1):
        return float(tok[:-1]) * SUFFIX[m.group(1)]
    return float(tok)


def _cells(line):
    parts = line.split("|")
    if len(parts) < 3:
        raise CardError("not a table row: %r" % line)
    return [p.strip() for p in parts[1:-1]]


def parse_card(path):
    """Read one card file. Returns a dict; raises CardError on any surprise."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")

    card = {
        "path": path,
        "card": os.path.basename(path)[:-3],
        "sha256": sha256_file(path),
        "raw_text": text,
    }

    # --- header block -------------------------------------------------------
    for ln in lines[:12]:
        m = re.match(r"^\| coin \| `(.+)` \|$", ln)
        if m:
            card["coin"] = m.group(1)
        m = re.match(r"^\| start hour \(UTC\) \| (\d{4}-\d{2}-\d{2}) "
                     r"(\d{2}):00 \|$", ln)
        if m:
            card["start_hour_utc"] = m.group(1) + "T" + m.group(2) + ":00Z"
    for key in ("coin", "start_hour_utc"):
        if key not in card:
            raise CardError("%s: no %s in header" % (path, key))

    # --- section boundaries -------------------------------------------------
    try:
        i_before = lines.index("## Before")
        i_after = lines.index("## After")
    except ValueError:
        raise CardError("%s: missing ## Before / ## After" % path)

    def section_bullets(lo, hi):
        out = {}
        for ln in lines[lo:hi]:
            m = re.match(r"^- \*\*(.+?):?\*\*\s*(.*)$", ln)
            if m:
                out[m.group(1).rstrip(":")] = m.group(2).strip()
            else:
                m = re.match(r"^- \*\*(.+?)\*\* (\(h-192\.\.h-25\)): (.*)$", ln)
                if m:
                    out[m.group(1)] = m.group(3).strip()
        return out

    card["before_bullets"] = section_bullets(i_before, i_after)
    card["after_bullets"] = section_bullets(i_after, len(lines))

    # --- the two tables -----------------------------------------------------
    tables = []
    for i, ln in enumerate(lines):
        if ln.strip() == TABLE_HEADER:
            rows = []
            j = i + 2                     # skip the |---| separator line
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(_cells(lines[j]))
                j += 1
            tables.append((i, rows))
    if len(tables) != 2:
        raise CardError("%s: %d tables, expected 2" % (path, len(tables)))

    def to_table(rows, offsets, label):
        if len(rows) != len(offsets):
            raise CardError("%s: %s table has %d rows, expected %d"
                            % (path, label, len(rows), len(offsets)))
        cols = {c: [] for c in COLUMNS}
        for off, cells in zip(offsets, rows):
            if len(cells) != len(COLUMNS):
                raise CardError("%s: %s row has %d cells" % (path, label,
                                                             len(cells)))
            if int(cells[0]) != off:
                raise CardError("%s: %s row offset %s, expected %d"
                                % (path, label, cells[0], off))
            cols["h"].append(off)
            for name, tok in zip(COLUMNS[1:], cells[1:]):
                cols[name].append(parse_number(tok))
        return cols

    card["before"] = to_table(tables[0][1], BEFORE_OFFSETS, "before")
    card["after"] = to_table(tables[1][1], AFTER_OFFSETS, "after")
    card["before_rows_text"] = [ln for ln in
                                lines[tables[0][0] + 2:
                                      tables[0][0] + 2 + 24]]

    # --- the after block's two answer lines (never shown in an exam) --------
    kind = card["after_bullets"].get("Moment kind")
    if kind not in ("large", "calm"):
        raise CardError("%s: moment kind %r" % (path, kind))
    card["kind"] = kind

    # --- previous-7-day line ------------------------------------------------
    p7 = card["before_bullets"].get("Previous 7 days")
    if p7 is None:
        raise CardError("%s: no Previous 7 days line" % path)
    p7 = re.sub(r"^\(h-192\.\.h-25\):\s*", "", p7)
    m = re.match(r"^price ([-+][\d.]+)% · high-low range ([\d.]+)% · "
                 r"avg hourly volume ([\d.]+[kMGB]?) · "
                 r"avg hourly trades ([\d.]+[kMGB]?)"
                 r"(?: · (\d+) hour\(s\) missing)?$", p7)
    if not m:
        raise CardError("%s: cannot parse Previous 7 days: %r" % (path, p7))
    card["p7_price_pct"] = float(m.group(1))
    card["p7_range_pct"] = float(m.group(2))
    card["p7_avg_vol"] = parse_number(m.group(3))
    card["p7_avg_trades"] = parse_number(m.group(4))
    card["p7_hours_missing"] = int(m.group(5)) if m.group(5) else 0

    # --- funding line -------------------------------------------------------
    fund = card["before_bullets"].get("Funding")
    if fund is None:
        raise CardError("%s: no Funding line" % path)
    m = re.match(r"^(\d+) payment\(s\)(?:, rate (.*?))? · interval (\S+) h · "
                 r"interval changed: (yes|no)$", fund)
    if not m:
        raise CardError("%s: cannot parse Funding: %r" % (path, fund))
    card["funding_count"] = int(m.group(1))
    card["funding_rates"] = [float(x.rstrip("%"))
                             for x in (m.group(2) or "").split()]
    card["funding_interval_text"] = m.group(3)
    card["funding_interval_changed"] = m.group(4)
    return card


def load_all(cards_dir):
    """Every C###.md in the folder, in card-number order."""
    names = sorted(f for f in os.listdir(cards_dir)
                   if re.fullmatch(r"C\d{3}\.md", f))
    return [parse_card(os.path.join(cards_dir, n)) for n in names]


# ---------------------------------------------------------------------------
# A reader that also copes with a blinded card: no coin, no start hour, no
# After section, and possibly fewer table columns. Used by
# 16_identity_audit.py so that the same attack can be run against the raw and
# the blinded card set without two different parsers.
# ---------------------------------------------------------------------------

def parse_any_card(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")
    out = {"path": path,
           "card": os.path.basename(path).rsplit(".", 1)[0],
           "sha256": sha256_file(path),
           "coin": None, "start_hour_utc": None, "kind": None}

    for ln in lines[:14]:
        m = re.match(r"^\| coin \| `(.+)` \|$", ln)
        if m:
            out["coin"] = m.group(1)
        m = re.match(r"^\| start hour \(UTC\) \| (\d{4}-\d{2}-\d{2}) "
                     r"(\d{2}):00 \|$", ln)
        if m:
            out["start_hour_utc"] = m.group(1) + "T" + m.group(2) + ":00Z"

    try:
        i_before = lines.index("## Before")
    except ValueError:
        raise CardError("%s: no ## Before" % path)
    i_end = len(lines)
    for marker in ("## After", "## Fields not on this card"):
        if marker in lines:
            i_end = min(i_end, lines.index(marker))

    bullets = {}
    for ln in lines[i_before:i_end]:
        m = re.match(r"^- \*\*(.+?):?\*\*\s*(.*)$", ln)
        if m:
            key = m.group(1).rstrip(":")
            val = re.sub(r"^\(h-192\.\.h-25\):\s*", "", m.group(2).strip())
            bullets[key] = val
    out["bullets"] = bullets

    # the before table: the first table between ## Before and the section end
    hdr_i = None
    for i in range(i_before, i_end):
        if lines[i].startswith("| h |"):
            hdr_i = i
            break
    if hdr_i is None:
        raise CardError("%s: no before table" % path)
    names = _cells(lines[hdr_i])
    cols = {n: [] for n in names}
    j = hdr_i + 2
    n_rows = 0
    while j < len(lines) and lines[j].startswith("|"):
        cells = _cells(lines[j])
        if len(cells) != len(names):
            raise CardError("%s: row %d has %d cells, header has %d"
                            % (path, j, len(cells), len(names)))
        for n, tok in zip(names, cells):
            cols[n].append(int(tok) if n == "h" else parse_number(tok))
        n_rows += 1
        j += 1
    if n_rows != len(BEFORE_OFFSETS):
        raise CardError("%s: before table has %d rows" % (path, n_rows))
    if cols["h"] != list(BEFORE_OFFSETS):
        raise CardError("%s: before row offsets are not -24..-1" % path)
    out["cols"] = cols

    # the after block's answer line, when the file has one (raw cards only)
    for ln in lines[i_end:]:
        m = re.match(r"^- \*\*Moment kind:\*\* (large|calm)$", ln)
        if m:
            out["kind"] = m.group(1)
            break
    return out
