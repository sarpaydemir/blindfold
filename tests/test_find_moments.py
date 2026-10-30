"""Moment finding (scripts/06_find_moments.py), TACTICS 2.

Large moments: the biggest 24-hour moves, at most 20 a year, one per 18 days of
life, never closer than 48 hours. Calm moments: as many, drawn at random, at
least 72 hours from any large moment.
"""

import math
import random

from helpers import load_script

fm = load_script("06_find_moments.py")
H = fm.HOUR_MS


def bars_for(days, jumps=(), start=None):
    """Hourly closes with small noise and a few sharp jumps (hour offset -> factor)."""
    start = fm.PERIOD_START_MS if start is None else start
    rng = random.Random(11)
    price, bars = 100.0, {}
    jumps = dict(jumps)
    for k in range(days * 24):
        price *= 1 + rng.uniform(-0.002, 0.002)
        price *= jumps.get(k, 1.0)
        bars[start + k * H] = {"close": price, "count": 10}
    return bars


def kinds(result, kind):
    return [m for m in result["moments"] if m["kind"] == kind]


def test_counts_spacing_and_calm_distance():
    bars = bars_for(80, jumps={24 * 10: 1.3, 24 * 30: 0.7, 24 * 50: 1.25, 24 * 70: 0.8})
    result = fm.find_for_symbol("TESTUSDT", bars, random.Random(fm.SEED))
    note = result["note"]
    assert note["n_large_target"] == min(fm.MAX_LARGE_PER_YEAR,
                                         math.floor(note["lifetime_days"] / fm.DAYS_PER_MOMENT))
    large, calm = kinds(result, "large"), kinds(result, "calm")
    assert len(large) == note["n_large_target"] == 4
    assert len(calm) == len(large)
    starts = sorted(m["start_ms"] for m in large)
    assert all(b - a >= fm.SEPARATION_LARGE_H * H for a, b in zip(starts, starts[1:]))
    for c in calm:
        assert all(abs(c["start_ms"] - s) >= fm.SEPARATION_CALM_FROM_LARGE_H * H for s in starts)


def test_the_largest_move_is_ranked_first():
    bars = bars_for(80, jumps={24 * 10: 1.3, 24 * 30: 0.6, 24 * 50: 1.25, 24 * 70: 0.8})
    result = fm.find_for_symbol("TESTUSDT", bars, random.Random(fm.SEED))
    top = [m for m in kinds(result, "large") if m["rank_in_coin"] == 1][0]
    assert top["move_24h"] < -0.35          # the 0.6 jump


def test_the_same_seed_gives_the_same_calm_moments():
    bars = bars_for(80, jumps={24 * 10: 1.3, 24 * 40: 0.7})
    a = fm.find_for_symbol("TESTUSDT", bars, random.Random(fm.SEED))
    b = fm.find_for_symbol("TESTUSDT", bars, random.Random(fm.SEED))
    assert a["moments"] == b["moments"]


def test_a_short_life_gives_no_moment_and_says_why():
    result = fm.find_for_symbol("TESTUSDT", bars_for(12), random.Random(fm.SEED))
    assert result["moments"] == []
    assert "18-day rule" in result["note"]["reason_no_moments"]


def test_a_coin_that_never_traded_is_named_with_the_reason():
    bars = {t: {"close": 1.0, "count": 0} for t in bars_for(30)}
    result = fm.find_for_symbol("TESTUSDT", bars, random.Random(fm.SEED))
    assert result["moments"] == []
    assert result["note"]["reason_no_moments"] == "no hour with a trade inside the period"
