#!/usr/bin/env python3
"""
04_draw.py -- the draw. Splits the universe into observation / exam / money test.

What it does : draws, without replacement and in a fixed order, 10 observation
               symbols and then 20 exam symbols from what remains; everything
               left over is the money-test set. Checks the three sets are
               disjoint and that every quota was filled.
Input        : data/universe/universe.csv   (written by 03_build_universe.py)
Output       : data/draw/observation-coins.txt   -- 10 symbols, one per line
               data/draw/draw-manifest.md        -- seed, method, sizes, cuts,
                                                    fingerprints, disjointness.
                                                    Names ONLY the observation
                                                    symbols.
               exam/draw/exam-coins.txt          -- 20 symbols
               exam/draw/money-test-coins.txt    -- the remainder
Rules        : TACTICS 1 (draw number, group quotas)
               RULES 29 (every run has a number: the fingerprint of its input)
               RULES 30 (append-only: a second run producing different content
                         under the same input fingerprint stops the script)

Reproducibility: the only source of randomness is random.Random(SEED) with the
seed below, consumed in a fixed order over alphabetically sorted pools. The same
universe.csv therefore always yields the same three lists.

Usage:
  04_draw.py                 write into the laboratory's real folders
  04_draw.py --out <dir>     write the same output into <dir> instead, for the
                             repeatability check (writes nothing to the real
                             folders)
"""

import argparse
import csv
import hashlib
import json
import os
import random
from datetime import datetime, timezone

# ---------------------------------------------------------------- constants --
# Draw number. Written in TACTICS 1 before the draw; it does not change.
SEED = 20260913

# Quotas, from TACTICS 1 / this run's instruction.
GROUP_ORDER = ["large", "mid", "small", "new"]
OBSERVATION_QUOTA = {"large": 3, "mid": 3, "small": 2, "new": 2}   # 10
EXAM_QUOTA = {"large": 6, "mid": 6, "small": 4, "new": 4}          # 20

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIVERSE_CSV = os.path.join(ROOT, "data", "universe", "universe.csv")
GROUPS_JSON = os.path.join(ROOT, "data", "universe", "universe-groups.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_list(path: str, symbols) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "".join(s + "\n" for s in symbols)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            old = fh.read()
        if old != body:
            raise SystemExit(
                "STOP (RULES 30): %s already exists with different content. "
                "Records are append-only; refusing to overwrite." % path)
        return hashlib.sha256(body.encode()).hexdigest()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return hashlib.sha256(body.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="write output under this directory instead of the "
                         "laboratory folders (repeatability check)")
    args = ap.parse_args()

    out_root = args.out or ROOT
    draw_dir = os.path.join(out_root, "data", "draw")
    exam_dir = os.path.join(out_root, "exam", "draw")

    # ------------------------------------------------------------- input ----
    universe_sha = sha256_file(UNIVERSE_CSV)
    run_number = universe_sha[:16]          # RULES 29: the run's number is the
                                            # fingerprint of its input
    with open(UNIVERSE_CSV, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with open(GROUPS_JSON, "r", encoding="utf-8") as fh:
        groups_info = json.load(fh)

    pools = {g: sorted(r["symbol"] for r in rows if r["group"] == g) for g in GROUP_ORDER}
    for g in GROUP_ORDER:
        need = OBSERVATION_QUOTA[g] + EXAM_QUOTA[g]
        if len(pools[g]) < need:
            print("STOP: group '%s' holds %d symbols but the quotas need %d. "
                  "No substitution is made from another group."
                  % (g, len(pools[g]), need))
            return 2

    # -------------------------------------------------------------- draw ----
    rng = random.Random(SEED)
    observation, exam = [], []
    obs_by_group, exam_by_group = {}, {}
    for g in GROUP_ORDER:                       # pass 1: observation
        pick = rng.sample(pools[g], OBSERVATION_QUOTA[g])
        obs_by_group[g] = pick
        observation.extend(pick)
    for g in GROUP_ORDER:                       # pass 2: exam, from what remains
        remaining = sorted(set(pools[g]) - set(obs_by_group[g]))
        pick = rng.sample(remaining, EXAM_QUOTA[g])
        exam_by_group[g] = pick
        exam.extend(pick)

    drawn = set(observation) | set(exam)
    money = sorted(r["symbol"] for r in rows if r["symbol"] not in drawn)

    # ---------------------------------------------------------- the checks --
    checks = {
        "observation_count": len(observation),
        "exam_count": len(exam),
        "money_test_count": len(money),
        "universe_count": len(rows),
        "counts_add_up": len(observation) + len(exam) + len(money) == len(rows),
        "observation_has_no_duplicate": len(set(observation)) == len(observation),
        "exam_has_no_duplicate": len(set(exam)) == len(exam),
        "money_has_no_duplicate": len(set(money)) == len(money),
        "observation_x_exam_overlap": sorted(set(observation) & set(exam)),
        "observation_x_money_overlap": sorted(set(observation) & set(money)),
        "exam_x_money_overlap": sorted(set(exam) & set(money)),
    }
    checks["disjoint"] = (not checks["observation_x_exam_overlap"]
                          and not checks["observation_x_money_overlap"]
                          and not checks["exam_x_money_overlap"])
    if not (checks["disjoint"] and checks["counts_add_up"]):
        print("STOP: draw checks failed: " + json.dumps(checks, indent=1))
        return 3

    # ------------------------------------------------------------- write ----
    obs_path = os.path.join(draw_dir, "observation-coins.txt")
    exam_path = os.path.join(exam_dir, "exam-coins.txt")
    money_path = os.path.join(exam_dir, "money-test-coins.txt")
    man_path = os.path.join(draw_dir, "draw-manifest.md")

    obs_sha = write_list(obs_path, observation)        # draw order
    exam_sha = write_list(exam_path, exam)             # draw order
    money_sha = write_list(money_path, money)          # alphabetical remainder

    group_of = {r["symbol"]: r["group"] for r in rows}
    vol_of = {r["symbol"]: r["median_daily_quote_volume"] for r in rows}
    first_of = {r["symbol"]: r["first_day_archive"] for r in rows}
    last_of = {r["symbol"]: r["last_day_with_trades_in_period"] for r in rows}
    tdays_of = {r["symbol"]: r["days_with_trades"] for r in rows}

    lines = []
    A = lines.append
    A("# Draw manifest")
    A("")
    A("Written by `scripts/04_draw.py`. This file names the **observation**")
    A("symbols only. The exam and money-test symbols are deliberately absent,")
    A("so this file can be read by roles that must not see those names")
    A("(TACTICS 1).")
    A("")
    A("## Run")
    A("")
    A("| field | value |")
    A("|---|---|")
    A("| run number (fingerprint of input, RULES 29) | `%s` |" % run_number)
    A("| input `data/universe/universe.csv` SHA-256 | `%s` |" % universe_sha)
    A("| drawn at (system clock, UTC) | %s |" % utc_now_iso())
    A("| **draw number / random seed** | **`%d`** |" % SEED)
    A("| randomness | Python `random.Random(%d)`, `rng.sample` |" % SEED)
    A("")
    A("## Method")
    A("")
    A("1. Every symbol in `universe.csv` sits in exactly one of four groups.")
    A("   `new` was assigned first and is exclusive; the rest were ranked by")
    A("   median daily `%s` over the period and cut into three groups of equal"
      % groups_info["volume_column"])
    A("   size, the remainder going to the lower-volume groups.")
    A("2. One `random.Random(%d)` is created and consumed in one fixed order:" % SEED)
    A("   first the observation draw over the groups large, mid, small, new;")
    A("   then the exam draw over the same groups, from what remains. Each pool")
    A("   is sorted alphabetically before sampling, so the same `universe.csv`")
    A("   always gives the same three lists.")
    A("3. The money-test set is every symbol not drawn into the other two.")
    A("")
    A("## Sizes")
    A("")
    A("| group | in universe | observation | exam | money test |")
    A("|---|---|---|---|---|")
    for g in GROUP_ORDER:
        n_money = sum(1 for s in money if group_of[s] == g)
        A("| %s | %d | %d | %d | %d |"
          % (g, len(pools[g]), OBSERVATION_QUOTA[g], EXAM_QUOTA[g], n_money))
    A("| **total** | **%d** | **%d** | **%d** | **%d** |"
      % (len(rows), len(observation), len(exam), len(money)))
    A("")
    A("## The two cut values")
    A("")
    A("Volume column: `%s` (the documented kline column 8, value traded in USDT)."
      % groups_info["volume_column"])
    A("Ranked symbols (`new` excluded): %d. Tertile sizes large/mid/small: %d / %d / %d."
      % (groups_info["ranked_count_excluding_new"],
         groups_info["tertile_sizes"]["large"],
         groups_info["tertile_sizes"]["mid"],
         groups_info["tertile_sizes"]["small"]))
    A("Remainder rule: %s." % groups_info["remainder_rule"])
    A("")
    A("| cut | lowest median volume still in the upper group | highest median volume in the lower group |")
    A("|---|---|---|")
    A("| large / mid | %r | %r |" % (groups_info["cut_large_mid_lowest_large"],
                                     groups_info["cut_large_mid_highest_mid"]))
    A("| mid / small | %r | %r |" % (groups_info["cut_mid_small_lowest_mid"],
                                     groups_info["cut_mid_small_highest_small"]))
    A("")
    A("Ties straddling a cut: %s"
      % (groups_info["ties_straddling_a_cut"] or "none"))
    A("")
    A("## Fingerprints of the four list files")
    A("")
    A("| file | lines | SHA-256 |")
    A("|---|---|---|")
    A("| `data/universe/universe.csv` | %d | `%s` |" % (len(rows) + 1, universe_sha))
    A("| `data/draw/observation-coins.txt` | %d | `%s` |" % (len(observation), obs_sha))
    A("| `exam/draw/exam-coins.txt` | %d | `%s` |" % (len(exam), exam_sha))
    A("| `exam/draw/money-test-coins.txt` | %d | `%s` |" % (len(money), money_sha))
    A("")
    A("## Disjointness check (computed in `04_draw.py`)")
    A("")
    A("```json")
    A(json.dumps(checks, indent=1, sort_keys=True))
    A("```")
    A("")
    A("## The 10 observation symbols")
    A("")
    A("| # | symbol | group | first day in archive | last day WITH TRADES in period "
      "| days with trades in period | median daily quote volume (USDT) |")
    A("|---|---|---|---|---|---|---|")
    for i, s in enumerate(observation, 1):
        A("| %d | %s | %s | %s | %s | %s | %s |"
          % (i, s, group_of[s], first_of[s], last_of[s], tdays_of[s], vol_of[s]))
    A("")

    body = "\n".join(lines)
    os.makedirs(draw_dir, exist_ok=True)
    if os.path.exists(man_path):
        with open(man_path, "r", encoding="utf-8") as fh:
            old = fh.read()
        old_k = "\n".join(l for l in old.splitlines() if "drawn at" not in l)
        new_k = "\n".join(l for l in body.splitlines() if "drawn at" not in l)
        if old_k != new_k:
            raise SystemExit("STOP (RULES 30): %s exists with different content." % man_path)
    else:
        with open(man_path, "w", encoding="utf-8") as fh:
            fh.write(body)

    print("run number: %s" % run_number)
    print("seed: %d" % SEED)
    print(json.dumps(checks, indent=1, sort_keys=True))
    print("observation: %s" % " ".join(observation))
    print("sha256 observation-coins.txt : %s" % obs_sha)
    print("sha256 exam-coins.txt        : %s" % exam_sha)
    print("sha256 money-test-coins.txt  : %s" % money_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
