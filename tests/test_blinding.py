"""Blinding and the attack on it.

scripts/17_blind_cards.py hides a card's coin and date: prices rebased, levels
put on the card's own scale, release dates stripped. scripts/16_identity_audit.py
then attacks the result: can the nearest card tell you the coin? These tests
cover the pieces both scripts are built from.
"""

import pytest

from helpers import load_script

blind = load_script("17_blind_cards.py")
audit = load_script("16_identity_audit.py")
engine = load_script("15_event_collapse.py")


# ---------------------------------------------------------------- blinding --

@pytest.mark.parametrize("line", [
    "Productivity and Costs (P) for First Quarter 2026 (-8 h)",
    "Employment Situation for April 2026 (+16 h)",
    "FOMC statement on 2026-03-18 (-3 h)",
    "Consumer Price Index for September 2025 (+2 h)",
])
def test_release_lines_lose_their_date_and_keep_their_offset(line):
    out = blind.strip_release_dates(line)
    assert blind.release_date_leak(out) is None
    assert out.endswith("h)")


@pytest.mark.parametrize("line,reason", [
    ("Employment Situation 2026", "a four-digit year survived"),
    ("Employment Situation for April", "the month name April survived"),
    ("GDP, Third Quarter", "the calendar period 'Third Quarter' survived"),
])
def test_the_leak_check_names_what_survived(line, reason):
    assert blind.release_date_leak(line) == reason


def test_a_birth_cohort_title_is_masked_too():
    out = blind.strip_release_dates("Employment of those Born 1980-1984 (+4 h)")
    assert "1980" not in out and blind.release_date_leak(out) is None


def test_scale_is_the_cards_own_median_of_positive_values():
    assert blind.scale_denominator([0, None, 2.0, 4.0, 6.0]) == 4.0
    assert blind.scale_denominator([0, 0, None]) is None


def test_ties_keep_equal_ranks_so_a_frozen_value_stays_visible():
    assert blind.ranks([3, 1, 2, 2]) == [4.0, 1.0, 2.5, 2.5]
    assert blind.longest_equal_run([1, 1, 2, 2, 2, 3]) == 3


# ------------------------------------------------------------------ attack --

def clustered(n_per=5):
    """Two coins whose cards sit far apart: an attack must find them."""
    vecs, labels = [], []
    for k in range(n_per):
        vecs.append([0.0 + 0.01 * k, 0.0])
        labels.append("A")
        vecs.append([10.0 + 0.01 * k, 10.0])
        labels.append("B")
    return vecs, labels


def test_nearest_neighbour_finds_the_coin_when_cards_carry_it():
    vecs, labels = clustered()
    nn = audit.nearest_neighbours(audit.pair_distances(vecs))
    assert audit.nn_accuracy(nn, labels) == 1.0
    rank, total = audit.pair_ranks(audit.pair_distances(vecs))
    assert audit.pair_auc(rank, total, labels) == 1.0


def test_with_no_signal_the_pair_auc_is_one_half():
    vecs = [[0.0]] * 6                       # every pair at the same distance
    labels = ["A", "A", "A", "B", "B", "B"]
    rank, total = audit.pair_ranks(audit.pair_distances(vecs))
    assert audit.pair_auc(rank, total, labels) == pytest.approx(0.5)


def test_ties_are_reported_as_a_range_not_a_lucky_pick():
    vecs = [[0.0], [1.0], [2.0]]             # card 1 is equally near 0 and 2
    labels = ["A", "A", "B"]
    tsets = audit.nearest_tie_sets(audit.pair_distances(vecs))
    assert tsets[1] == [0, 2]
    lo, hi = audit.nn_tie_range(tsets, labels)
    assert lo < hi
    assert lo <= audit.nn_tie_free(tsets, labels) <= hi


def test_the_attack_and_the_engine_use_the_same_chance_line_boundary():
    values = [i / 100 for i in range(1000)]
    assert audit.SHUFFLES == engine.SHUFFLES == 1000
    assert audit.quantile_top(values, audit.TOP_FRACTION) == \
        engine.quantile_top(values, engine.TOP_FRACTION)
