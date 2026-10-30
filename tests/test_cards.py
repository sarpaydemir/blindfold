"""Cards: the wall between Before and After, and the shared card reader.

scripts/09_write_cards.py passes every value through a TimeGuard so nothing
from the 24 hours after the start can land in the Before section.
scripts/lab_cards.py reads a card back the same way for every later script.
The card below is synthetic: no market data is published in this repository.
"""

import pytest

from helpers import load_script

w9 = load_script("09_write_cards.py")
lc = load_script("lab_cards.py")
H = w9.HOUR_MS
T0 = 1_780_000_000_000 - (1_780_000_000_000 % H)


# --------------------------------------------------------------- TimeGuard --

def test_before_section_refuses_the_start_hour_itself():
    g = w9.TimeGuard(T0)
    g.before(T0 - H, "klines")
    g.before(T0, "klines")
    assert len(g.violations) == 1 and "before-section" in g.violations[0]


def test_an_hourly_bar_belongs_before_only_if_it_ends_by_the_start():
    g = w9.TimeGuard(T0)
    g.before_hour(T0 - H, "klines")            # ends exactly at the start: allowed
    g.before_hour(T0 - H + 1, "klines")        # ends one millisecond after: refused
    assert len(g.violations) == 1


def test_after_section_is_exactly_the_next_24_hours():
    g = w9.TimeGuard(T0)
    for ts in (T0, T0 + 23 * H):
        g.after(ts, "klines")
    for ts in (T0 - 1, T0 + 24 * H):
        g.after(ts, "klines")
    assert len(g.violations) == 2


def test_check_catches_sections_that_meet():
    g = w9.TimeGuard(T0)
    g.before_ts.append(T0)                      # forced past the guard
    g.after(T0, "klines")
    found = g.check()
    assert any("before max" in v for v in found)
    assert "timestamp present in both sections" in found


def test_none_passes_through_without_a_record():
    g = w9.TimeGuard(T0)
    assert g.before(None, "x") is None and g.after(None, "x") is None
    assert g.check() == []


# ------------------------------------------------- the writer and the reader --

@pytest.mark.parametrize("value", [0.5, 7.0, 425.43, 11_520.0, 2_520_000.0, 3.4e9])
def test_the_reader_reads_what_the_writer_wrote(value):
    printed = w9.human(value)
    assert lc.parse_number(printed) == pytest.approx(value, rel=0.01)


def test_a_dot_is_no_value_and_junk_is_refused():
    assert lc.parse_number(".") is None
    assert lc.parse_number("+0.49") == 0.49
    with pytest.raises(lc.CardError):
        lc.parse_number("12x")


@pytest.mark.xfail(strict=True, raises=lc.CardError, reason=(
    "Found while preparing this copy: the writer prints values of 1e12 and up "
    "with a T suffix, which the reader does not know. No card value came near it."))
def test_the_reader_reads_the_writers_largest_suffix():
    assert lc.parse_number(w9.human(2.5e12)) == pytest.approx(2.5e12)


def table(offsets):
    rows = [lc.TABLE_HEADER, "|" + "---|" * 14]
    for h in offsets:
        cells = [str(h), "100.5", "+0.10", "11.52k", "167", "45.8", "2.52k", "2.43",
                 "0.81", "8.97", "122.69k", "121.02k", "-0.05", "+0.11"]
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def synthetic_card(kind="large"):
    lines = [
        "# Card C001", "", "| | |", "|---|---|",
        "| coin | `TESTUSDT` |",
        "| start hour (UTC) | 2026-05-07 20:00 |",
        "| sections | before = the 24 h ending at the start hour · after = the 24 h from it |",
        "", "## Before", "",
        "- **Previous 7 days** (h-192..h-25): price +4.08% · high-low range 7.15% · "
        "avg hourly volume 47.72k · avg hourly trades 603",
        "- **Funding:** 3 payment(s), rate +0.0100% +0.0000% -0.0050% · interval 8 h · "
        "interval changed: no",
        "",
        *table(lc.BEFORE_OFFSETS),
        "", "## After", "",
        "- **Moment kind:** %s" % kind,
        "",
        *table(lc.AFTER_OFFSETS),
        "",
    ]
    return "\n".join(lines)


def test_a_card_is_read_into_its_parts(tmp_path):
    path = tmp_path / "C001.md"
    path.write_text(synthetic_card(), encoding="utf-8")
    card = lc.parse_card(str(path))
    assert card["coin"] == "TESTUSDT"
    assert card["start_hour_utc"] == "2026-05-07T20:00Z"
    assert card["kind"] == "large"
    assert card["before"]["h"] == list(lc.BEFORE_OFFSETS)
    assert card["before"]["quote vol"][0] == pytest.approx(11_520.0)
    assert card["funding_rates"] == [0.01, 0.0, -0.005]
    assert card["p7_avg_vol"] == pytest.approx(47_720.0)
    assert len(card["before_rows_text"]) == 24


def test_a_card_with_a_wrong_answer_line_is_refused(tmp_path):
    path = tmp_path / "C001.md"
    path.write_text(synthetic_card(kind="maybe"), encoding="utf-8")
    with pytest.raises(lc.CardError):
        lc.parse_card(str(path))


def test_a_card_missing_an_hour_is_refused(tmp_path):
    path = tmp_path / "C001.md"
    text = synthetic_card().replace("\n| -24 |", "\n| -25 |", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(lc.CardError):
        lc.parse_card(str(path))


def test_a_blinded_card_reads_without_coin_date_or_answer(tmp_path):
    text = synthetic_card()
    text = text.replace("| coin | `TESTUSDT` |\n", "").replace(
        "| start hour (UTC) | 2026-05-07 20:00 |\n", "")
    text = text[:text.index("## After")]
    path = tmp_path / "B001.md"
    path.write_text(text, encoding="utf-8")
    card = lc.parse_any_card(str(path))
    assert card["coin"] is None and card["start_hour_utc"] is None and card["kind"] is None
    assert card["cols"]["h"] == list(lc.BEFORE_OFFSETS)
