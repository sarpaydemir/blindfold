#!/usr/bin/env python3
"""
10_verify_cards.py -- check the written cards against the raw archive, without
                      reusing 09_write_cards.py's own numbers.

What it does
------------
For every card it re-reads the hourly klines straight out of the monthly zips
and checks, independently of the card writer:

  1. the "before" table has exactly 24 rows, labelled -24 .. -1, and row -k
     carries the close of the hour t0 - k*1h;
  2. the "after" table has exactly 24 rows, labelled +0 .. +23, and row +k
     carries the close of the hour t0 + k*1h;
  3. no hour at or after t0 appears anywhere in the before section, and no hour
     before t0 appears as a row of the after table;
  4. the 24-hour move printed in the after section equals
     close(t0+23h)/close(t0-1h) - 1, and equals the value in moments.csv;
  5. the kind (large / calm) and the move appear only after the "## After"
     heading;
  6. the card file's SHA-256 matches the one recorded in cards/INDEX.md.

Input   : cards/C*.md, cards/INDEX.md, data/moments/moments.csv,
          data/observation/klines_1h/
Output   : prints a report; exits non-zero if any check fails.
Rules   : RULES 21 (a technical failure is reported as a failure)
No randomness in this script.
"""

import csv
import glob
import io
import os
import re
import sys
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab_archive import sha256_file  # noqa: E402

HOUR_MS = 3600 * 1000
TOL_PRICE = 1e-9          # closes are compared after the card's %.6g rounding
TOL_MOVE_PCT = 5.1e-3     # the card prints the move to 2 decimals of a percent,
                          # so half a last digit (0.005) is the honest tolerance
TOL_MOVE_CSV = 5.1e-5     # moments.csv carries 4 decimals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, "cards")
MOMENTS = os.path.join(ROOT, "data", "moments", "moments.csv")
KL = os.path.join(ROOT, "data", "observation", "klines_1h")


def load_closes(symbol):
    out = {}
    d = os.path.join(KL, symbol)
    for name in sorted(os.listdir(d)):
        if not name.endswith(".zip"):
            continue
        with zipfile.ZipFile(os.path.join(d, name)) as z:
            for member in z.namelist():
                for row in csv.reader(io.StringIO(z.read(member).decode("utf-8", "replace"))):
                    if row and row[0] != "open_time":
                        out[int(row[0])] = float(row[4])
    return out


def main() -> int:
    with open(MOMENTS, "r", encoding="utf-8") as fh:
        moments = list(csv.DictReader(fh))
    index_sha = {}
    for ln in open(os.path.join(CARDS, "INDEX.md"), encoding="utf-8"):
        m = re.match(r"\| `(C\d+)` \| (\S+) \| (\w+) \| ([0-9: \-]+) \| `([0-9a-f]{64})` \|", ln)
        if m:
            index_sha[m.group(1)] = (m.group(2), m.group(3), m.group(4), m.group(5))

    closes = {}
    fails, checked = [], 0
    for i, mom in enumerate(moments, start=1):
        no = "C%03d" % i
        sym, t0 = mom["symbol"], int(mom["start_ms"])
        if sym not in closes:
            closes[sym] = load_closes(sym)
        cl = closes[sym]
        path = os.path.join(CARDS, "%s.md" % no)
        if not os.path.exists(path):
            fails.append("%s: file missing" % no)
            continue
        text = open(path, encoding="utf-8").read()

        # -- 6. fingerprint -------------------------------------------------
        rec = index_sha.get(no)
        if not rec:
            fails.append("%s: not listed in INDEX.md" % no)
        else:
            if rec[0] != sym:
                fails.append("%s: INDEX.md says coin %s, moments.csv says %s" % (no, rec[0], sym))
            if rec[4 - 1] != sha256_file(path):
                fails.append("%s: SHA-256 in INDEX.md does not match the file" % no)

        # -- split the two sections ------------------------------------------
        if "\n## After\n" not in text:
            fails.append("%s: no '## After' heading" % no)
            continue
        before_txt, after_txt = text.split("\n## After\n", 1)

        # -- 5. kind and move must not be in the before section ---------------
        if re.search(r"Moment kind|Measured 24-hour move", before_txt):
            fails.append("%s: kind or move appears before the After heading" % no)
        if mom["kind"] not in after_txt:
            fails.append("%s: kind %s not found in the after section" % (no, mom["kind"]))

        # -- 1/2/3. the two tables -------------------------------------------
        def rows(block):
            return re.findall(r"^\| ([+-]\d+) \| ([0-9.eE+-]+|\.) \|", block, re.M)

        b_rows, a_rows = rows(before_txt), rows(after_txt)
        if [r[0] for r in b_rows] != ["%+d" % -k for k in range(24, 0, -1)]:
            fails.append("%s: before table row labels wrong (%d rows)" % (no, len(b_rows)))
        if [r[0] for r in a_rows] != ["%+d" % k for k in range(0, 24)]:
            fails.append("%s: after table row labels wrong (%d rows)" % (no, len(a_rows)))

        for lab, val in b_rows:
            h = t0 + int(lab) * HOUR_MS
            if h >= t0:
                fails.append("%s: before table holds hour %s at or after the start" % (no, lab))
            want = cl.get(h)
            if want is None or abs(float(val) - float("%.6g" % want)) > TOL_PRICE:
                fails.append("%s: before row %s close %s != archive %s" % (no, lab, val, want))
        for lab, val in a_rows:
            h = t0 + int(lab) * HOUR_MS
            if h < t0:
                fails.append("%s: after table holds hour %s before the start" % (no, lab))
            want = cl.get(h)
            if want is None or abs(float(val) - float("%.6g" % want)) > TOL_PRICE:
                fails.append("%s: after row %s close %s != archive %s" % (no, lab, val, want))

        # -- 4. the move ------------------------------------------------------
        m = re.search(r"Measured 24-hour move.*?([+-][0-9.]+)%", after_txt, re.S)
        if not m:
            fails.append("%s: no measured move line" % no)
        else:
            base, end = cl.get(t0 - HOUR_MS), cl.get(t0 + 23 * HOUR_MS)
            recomputed = 100.0 * (end / base - 1.0)
            if abs(float(m.group(1)) - recomputed) > TOL_MOVE_PCT:
                fails.append("%s: move %s%% != recomputed %.4f%%" % (no, m.group(1), recomputed))
            if abs(float(mom["move_24h_pct"]) - recomputed) > TOL_MOVE_CSV:
                fails.append("%s: moments.csv move %s%% != recomputed %.4f%%"
                             % (no, mom["move_24h_pct"], recomputed))
        checked += 1

    print("cards checked: %d" % checked)
    print("failures: %d" % len(fails))
    for f in fails[:40]:
        print("  " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
