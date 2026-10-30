"""The event-collapse engine and the RULES 12 chance line (scripts/15_event_collapse.py).

RULES 13: moments in several coins in the same hour count as one event.
RULES 12: the chance line is the best 1% of 1,000 shuffles.
The engine collapses first and shuffles whole events, and refuses to compute a
chance line from anything it cannot re-derive.
"""

import random
from datetime import datetime, timedelta, timezone

import pytest

from helpers import load_script

ec = load_script("15_event_collapse.py")

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
CONFIGS = [(d, r, s) for d in ec.DEFINITIONS for r in ec.RESOLUTIONS for s in ec.SCOPES]


def moment(mid, coin, hour):
    return {"id": mid, "coin": coin, "start_dt": BASE + timedelta(hours=hour)}


def random_moments(n=60, coins=6, span_hours=24 * 30, seed=7):
    rng = random.Random(seed)
    return [moment("C%03d" % i, "COIN%d" % rng.randrange(coins), rng.randrange(span_hours))
            for i in range(1, n + 1)]


def ids(event_map):
    return sorted(sorted(ev) for ev in event_map)


# ---------------------------------------------------------------- collapse --

@pytest.mark.parametrize("definition,resolution,scope", CONFIGS)
def test_every_configuration_is_a_partition_it_can_re_derive(definition, resolution, scope):
    ms = random_moments()
    em = ec.collapse(ms, definition, resolution, scope)
    flat = [c for ev in em for c in ev]
    assert sorted(flat) == sorted(m["id"] for m in ms)
    assert len(flat) == len(set(flat))
    assert em.config == "%s/%s/%s" % (definition, resolution, scope)
    assert ec.verify_event_map(em) is True


@pytest.mark.parametrize("gap,definition,merged", [
    (0, "start-hour", True), (1, "start-hour", False),
    (23, "move-window", True), (24, "move-window", False),
    (47, "card-span", True), (48, "card-span", False),
])
def test_each_reading_of_same_hour_joins_at_its_own_gap(gap, definition, merged):
    ms = [moment("A", "X", 0), moment("B", "Y", gap)]
    em = ec.collapse(ms, definition, "component", "any")
    assert len(em) == (1 if merged else 2)


def test_component_chains_where_greedy_clique_does_not():
    # A-B and B-C share card-span hours, A-C do not.
    ms = [moment("A", "X", 0), moment("B", "Y", 30), moment("C", "Z", 60)]
    assert ids(ec.collapse(ms, "card-span", "component", "any")) == [["A", "B", "C"]]
    assert len(ec.collapse(ms, "card-span", "greedy-clique", "any")) == 2


def test_cross_coin_never_merges_two_moments_of_one_coin():
    ms = [moment("A", "X", 0), moment("B", "X", 1), moment("C", "Y", 1)]
    assert ids(ec.collapse(ms, "move-window", "component", "any")) == [["A", "B", "C"]]
    for ev in ec.collapse(ms, "move-window", "greedy-clique", "cross-coin"):
        coins = [m["coin"] for m in ms if m["id"] in ev]
        assert len(coins) == len(set(coins))


def test_keep_latest_exists_only_where_the_question_does():
    ms = random_moments(10)
    with pytest.raises(ValueError):
        ec.collapse(ms, "start-hour", "component", "any", same_coin_keep="latest")
    em = ec.collapse(ms, "card-span", "greedy-clique", "cross-coin", same_coin_keep="latest")
    assert em.config.endswith("+latest")
    assert ec.verify_event_map(em) is True


def test_a_start_time_off_the_hour_is_refused():
    with pytest.raises(ValueError):
        ec._whole_hour_index(BASE + timedelta(minutes=30))


def test_unknown_configuration_is_refused():
    with pytest.raises(ValueError):
        ec.collapse(random_moments(5), "same-day", "component", "any")


# ----------------------------------------------------------- block shuffle --

def test_block_shuffle_keeps_every_event_whole():
    events = [["a"], ["b"], ["c", "d"], ["e", "f"], ["g", "h", "i"]]
    order = list("abcdefghi")
    report = ec.check_block_shuffle(events, order, draws=1000)
    assert report["permutation_ok"] == report["event_constant_preserved"] == 1000
    # The size-3 event has no partner of its size, so it can never move.
    assert report["immovable_events"] == 1
    assert report["cards_in_immovable_events"] == 3


def test_the_defect_the_blind_review_found_is_caught_by_the_check():
    # The first version paired card positions index by index across events of
    # different sizes. Re-created here: such a draw is a permutation, but an
    # event reads its answers from more than one source event.
    events = [["a"], ["b", "c"], ["d", "e", "f"]]
    order = list("abcdef")
    blocks = ec._blocks(events, order)

    def index_by_index(rng):
        src = list(range(len(blocks)))
        rng.shuffle(src)
        flat_src = [p for k in src for p in blocks[k]]
        flat_tgt = [p for b in blocks for p in b]
        out = [None] * len(order)
        for t, s in zip(flat_tgt, flat_src):
            out[t] = s
        return out

    rng = random.Random(ec.SEED)
    verdicts = [ec._check_one_draw(index_by_index(rng), blocks, len(order))[0]
                for _ in range(200)]
    assert not all(verdicts)


def test_block_shuffle_refuses_events_that_do_not_cover_the_cards():
    with pytest.raises((ValueError, KeyError)):
        ec.block_shuffle_indices([["a"], ["b"]], list("abc"), random.Random(1))


# -------------------------------------------------------------- chance line --

def exam_like(n_events=40, seed=3):
    """Moments in coin-overlapping clusters, answers and labels per card."""
    rng = random.Random(seed)
    ms, k = [], 0
    for e in range(n_events):
        size = rng.choice([1, 1, 2, 3])
        hour = e * 100
        for j in range(size):
            k += 1
            ms.append(moment("C%03d" % k, "COIN%d" % j, hour))
    order = [m["id"] for m in ms]
    labels = [rng.choice(["large", "calm"]) for _ in order]
    answers = [rng.choice(["large", "calm"]) for _ in order]
    return ms, order, labels, answers


def test_chance_line_record_names_what_produced_it():
    ms, order, labels, answers = exam_like()
    em = ec.collapse(ms, "start-hour", "component", "any")
    key = ec.moments_fingerprint(ms)
    rec = ec.chance_line(answers, labels, em, order, "block", key_moments_sha256=key)
    assert rec["config"] == "start-hour/component/any"
    assert rec["key_check"] == "matched"
    assert rec["events"] == 40 and rec["cards"] == len(order)
    assert rec["identity_partition"] is False
    assert len(rec["null"]) == ec.SHUFFLES == 1000
    assert rec["boundary"] == ec.quantile_top(rec["null"], ec.TOP_FRACTION)
    again = ec.chance_line(answers, labels, em, order, "block", key_moments_sha256=key)
    assert again["null"] == rec["null"]


def test_the_uncollapsed_line_exists_only_under_its_own_label():
    ms, order, labels, answers = exam_like()
    em = ec.identity_map(ms)
    rec = ec.chance_line(answers, labels, em, order, "block",
                         key_moments_sha256=ec.moments_fingerprint(ms))
    assert rec["config"] == "none/none/none"
    assert rec["identity_partition"] is True


def test_representative_mode_needs_one_named_card_per_event():
    ms, order, labels, answers = exam_like()
    em = ec.collapse(ms, "start-hour", "component", "any")
    key = ec.moments_fingerprint(ms)
    with pytest.raises(ValueError):
        ec.chance_line(answers, labels, em, order, "representative", key_moments_sha256=key)
    reps = [ev[0] for ev in em]
    rec = ec.chance_line(answers, labels, em, order, "representative",
                         representatives=reps, key_moments_sha256=key)
    assert rec["n_in_null"] == len(em)
    with pytest.raises(ValueError):
        ec.chance_line(answers, labels, em, order, "representative",
                       representatives=reps[:-1] + [reps[0]], key_moments_sha256=key)


def test_chance_line_refuses_a_plain_list():
    ms, order, labels, answers = exam_like()
    events = [list(ev) for ev in ec.collapse(ms, "start-hour", "component", "any")]
    with pytest.raises(TypeError):
        ec.chance_line(answers, labels, events, order, "block",
                       key_moments_sha256=ec.moments_fingerprint(ms))


def test_chance_line_refuses_a_subclass():
    ms, order, labels, answers = exam_like()

    class Forged(ec.EventMap):
        pass

    em = ec.collapse(ms, "start-hour", "component", "any")
    forged = Forged(list(em), em.definition, em.resolution, em.scope, ms)
    with pytest.raises(TypeError):
        ec.chance_line(answers, labels, forged, order, "block",
                       key_moments_sha256=ec.moments_fingerprint(ms))


def test_chance_line_refuses_a_map_not_made_from_the_answer_key():
    ms, order, labels, answers = exam_like()
    em = ec.collapse(ms, "start-hour", "component", "any")
    other = [dict(m) for m in ms]
    other[0]["start_dt"] = other[0]["start_dt"] + timedelta(hours=1)
    with pytest.raises(ValueError):
        ec.chance_line(answers, labels, em, order, "block",
                       key_moments_sha256=ec.moments_fingerprint(other))


def test_chance_line_refuses_a_map_edited_by_hand():
    ms, order, labels, answers = exam_like()
    em = ec.collapse(ms, "start-hour", "component", "any")
    big = max(range(len(em)), key=lambda i: len(em[i]))
    moved = em[big].pop()
    em.append([moved])
    with pytest.raises(ValueError):
        ec.chance_line(answers, labels, em, order, "block",
                       key_moments_sha256=ec.moments_fingerprint(ms))


def test_chance_line_has_no_card_level_mode():
    ms, order, labels, answers = exam_like()
    em = ec.collapse(ms, "start-hour", "component", "any")
    with pytest.raises(ValueError):
        ec.chance_line(answers, labels, em, order, "card",
                       key_moments_sha256=ec.moments_fingerprint(ms))


def test_best_one_percent_boundary():
    values = list(range(1, 101))
    assert ec.quantile_top(values, 0.01) == 100
    assert ec.quantile_top(values, 0.05) == 96


def test_fingerprint_from_a_plain_list_matches_the_map():
    ms = random_moments(20)
    em = ec.collapse(ms, "move-window", "component", "cross-coin")
    assert ec.moments_fingerprint(ms) == em.moments_sha256()
    assert ec.event_map_fingerprint(em) == em.sha256()
