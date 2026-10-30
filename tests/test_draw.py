"""The draw (scripts/04_draw.py): observation, exam and money-test coins.

TACTICS 1: a fixed draw number, fixed quotas per volume group, and the exam
names kept out of every file a watcher can read. RULES 29-30: the same input
gives the same lists, and different content under an existing file stops.
"""

import csv
import json
import sys

import pytest

from helpers import load_script

draw = load_script("04_draw.py")

GROUP_SIZES = {"large": 12, "mid": 12, "small": 8, "new": 8}


def write_universe(folder, sizes=GROUP_SIZES):
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for group, n in sizes.items():
        for i in range(n):
            rows.append({"symbol": "%s%02dUSDT" % (group.upper(), i), "group": group,
                         "median_daily_quote_volume": str(1000 * (i + 1)),
                         "first_day_archive": "2025-01-01",
                         "last_day_with_trades_in_period": "2026-08-31",
                         "days_with_trades": "365"})
    universe = folder / "universe.csv"
    with open(universe, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    groups = folder / "universe-groups.json"
    groups.write_text(json.dumps({
        "volume_column": "quote_volume", "ranked_count_excluding_new": 32,
        "tertile_sizes": {"large": 12, "mid": 12, "small": 8},
        "remainder_rule": "to the lower-volume groups",
        "cut_large_mid_lowest_large": 1.0, "cut_large_mid_highest_mid": 0.9,
        "cut_mid_small_lowest_mid": 0.5, "cut_mid_small_highest_small": 0.4,
        "ties_straddling_a_cut": []}), encoding="utf-8")
    return universe, groups, rows


@pytest.fixture
def run_draw(monkeypatch, tmp_path):
    universe, groups, rows = write_universe(tmp_path / "in")
    monkeypatch.setattr(draw, "UNIVERSE_CSV", str(universe))
    monkeypatch.setattr(draw, "GROUPS_JSON", str(groups))

    def run(out):
        monkeypatch.setattr(sys, "argv", ["04_draw.py", "--out", str(out)])
        return draw.main()

    run.rows = rows
    return run


def read_lines(path):
    return path.read_text(encoding="utf-8").split()


def test_quotas_are_filled_and_the_three_sets_are_disjoint(run_draw, tmp_path):
    out = tmp_path / "out"
    assert run_draw(out) == 0
    obs = read_lines(out / "data" / "draw" / "observation-coins.txt")
    exam = read_lines(out / "exam" / "draw" / "exam-coins.txt")
    money = read_lines(out / "exam" / "draw" / "money-test-coins.txt")
    assert len(obs) == 10 and len(exam) == 20
    assert len(obs) + len(exam) + len(money) == len(run_draw.rows)
    assert not (set(obs) & set(exam) or set(obs) & set(money) or set(exam) & set(money))
    group_of = {r["symbol"]: r["group"] for r in run_draw.rows}
    for group in GROUP_SIZES:
        assert sum(group_of[s] == group for s in obs) == draw.OBSERVATION_QUOTA[group]
        assert sum(group_of[s] == group for s in exam) == draw.EXAM_QUOTA[group]


def test_the_same_universe_gives_byte_identical_lists(run_draw, tmp_path):
    assert run_draw(tmp_path / "a") == 0
    assert run_draw(tmp_path / "b") == 0
    for rel in ("data/draw/observation-coins.txt", "exam/draw/exam-coins.txt",
                "exam/draw/money-test-coins.txt"):
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes()


def test_the_manifest_names_no_exam_or_money_test_coin(run_draw, tmp_path):
    out = tmp_path / "out"
    run_draw(out)
    manifest = (out / "data" / "draw" / "draw-manifest.md").read_text(encoding="utf-8")
    hidden = read_lines(out / "exam" / "draw" / "exam-coins.txt") + \
        read_lines(out / "exam" / "draw" / "money-test-coins.txt")
    assert not [s for s in hidden if s in manifest]
    assert "`%d`" % draw.SEED in manifest


def test_a_rerun_over_its_own_output_is_allowed(run_draw, tmp_path):
    out = tmp_path / "out"
    assert run_draw(out) == 0
    assert run_draw(out) == 0


def test_different_content_under_an_existing_list_stops(run_draw, tmp_path):
    out = tmp_path / "out"
    run_draw(out)
    exam = out / "exam" / "draw" / "exam-coins.txt"
    exam.write_text("TAMPEREDUSDT\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="RULES 30"):
        run_draw(out)


def test_a_short_group_stops_without_substitution(monkeypatch, tmp_path):
    universe, groups, _ = write_universe(tmp_path / "in", {**GROUP_SIZES, "new": 5})
    monkeypatch.setattr(draw, "UNIVERSE_CSV", str(universe))
    monkeypatch.setattr(draw, "GROUPS_JSON", str(groups))
    monkeypatch.setattr(sys, "argv", ["04_draw.py", "--out", str(tmp_path / "out")])
    assert draw.main() == 2
    assert not (tmp_path / "out").exists()
