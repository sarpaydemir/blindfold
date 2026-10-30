# Observation and the canteen: a scoring system that says "do nothing"

Source: the private repository's `LEDGER.md`, entries 2026-09-18 21:01 UTC to 2026-09-19 13:33 UTC, and the files they fingerprint. Numbers are the ledger's; every token count is the harness's own report at the end of a run, summed, never extrapolated.

## The question

Find a scoring rule for Binance USDT perpetual futures by watching first: what happens before a sharp 24-hour move, and what happens in a calm stretch. Ideas come from free observation. Evidence comes only from a blind exam and a money test later (`RULES.md` 7, `TACTICS.md` 6–8).

## The universe and the draw (2026-09-18)

- **795 contracts.** Of 1,018 archive folders, 864 are USDT perpetuals, 837 have daily rows in the period (2025-09-01 → 2026-08-31), and 795 traded at least once. The list came from the archive, not today's exchange, so contracts that died in the period are in it (`TACTICS.md` 0).
- **8,567 of 8,567** daily kline files verified against the archive's own `.CHECKSUM`, 0 mismatches.
- Four groups: large 160, mid 160, small 161 by median daily `quote_volume`, and new 314. Draw number `20260913`, written before the draw.
- **Observation 10 coins (3·3·2·2), exam 20 (6·6·4·4), money test 765.** The draw was run a second time into a scratch folder and came out byte-identical; the append-only guard was made to fire. The exam names were written only under `exam/`, which the watchers, the canteen chair and the skeptic could not open.
- Cost: 129,194 tokens, 33 minutes.

## The cards (2026-09-19 06:43)

**306 cards**: 153 large-movement moments and 153 calm ones for the 10 observation coins (20 + 20 for each full-year coin; one coin lived 21.4 days and gave 1 + 1). Each card shows the 24 hours before the start and the 24 hours after, hour by hour, plus a 7-day summary line. 1,917 archive files for the cards, all verified against their checksums. A `TimeGuard` in `scripts/09_write_cards.py` refuses any value from the After window in the Before section.

## The pilot and the effort level

The same 10 cards were read at two effort levels. Medium: 90,152 tokens, 26 note lines opening with a card number. High: 101,346 tokens, 68 such lines. A jury of three ruled 3–0 that `TACTICS.md` 4 selects effort `high` (2.6× the countable notes for 1.124× the tokens). The jury's answers, the referee's verdict and the instructions they were given are in [`decisions/2026-09-19-effort-level/`](../decisions/2026-09-19-effort-level/) and [`instructions/`](../instructions/).

## Round 1: four watchers, 306 cards each

Four watchers, each with a different field of view (exchange behaviour, the crowd, the outside world, price itself), read all 306 cards in shuffled batches. Each run started in a fresh context and saw neither another watcher's notes nor its own earlier ones.

| watcher | field of view | tokens | per card |
|---|---|---|---|
| Ingrid | exchange behaviour | 1,296,517 | 4,237 |
| Lukas | price itself | 2,262,894 | 7,395 |
| Kenji | the crowd | 2,172,718 | 7,101 |
| Amara | the outside world | 2,303,017 | 7,526 |
| **round 1** | 36 runs | **8,035,146** | **6,565** |

The lab had estimated the cost three times on the way. Two estimates were labelled upper bounds and were (by 35% and 13%). The third, 7.47 million, was 7% low and had not been flagged as possibly low; the ledger says it should have been.

## Round 2: the ideas died outside their own batch

Each watcher read the other three's 27 files and tested named ideas on cards their authors had not seen. Ingrid: *"I looked for one trigger that was measured in more than one batch and kept its sign; there is none."* Amara tested eleven directional ideas and killed nine with cards: *"No directional idea from round 1 survives a card drawn from outside the batch that proposed it."* In one case the same card fired two rules by the same author in opposite directions.

## The overlap map: 306 cards, 10 independent

`RULES.md` 13 says moments in several coins in the same hour are one event. The data engineer measured it with a script (`scripts/14_overlap_map.py`, run `12ce59e2902a0034`):

| | |
|---|---|
| pairs of cards sharing at least one clock hour | **495** |
| cards overlapping at least one other | **296 of 306** |
| cards in no overlap | **10** |
| largest chain of linked cards | **20** |
| largest group all sharing one hour | **7** (seven coins, all large, 20 hours in common) |

It checked all 12,579 shared hours against the bitcoin and ethereum columns printed on both cards: 0 mismatches. It added a negative control nobody asked for (100,000 random pairs of different hours: 0.014% match on both columns), and rebuilt the map a second way, from the moment list alone, with identical numbers.

A watcher reading card headers found the same seven-card group the script found from timestamps, without contact between them.

## The canteen: 90 items, 52 red stamps, an empty list

The skeptic (Viktor) read all 40 watcher files and opened 8 cards to check his own objections. **90 items examined, 52 directional ideas stopped with a reasoned red stamp, one survivor**: a gate that says a large move may be coming but not in which direction. He weakened that survivor himself by opening four calm cards and finding all four fire it. He put look-ahead first: three ideas died on whether they could be entered at all. Two rested on the After window, which the exam never shows, and one entered at a release hour published in advance, which `RULES.md` 16 forbids as a fill.

He also found what nobody had joined up: *"Nothing has been collapsed for RULES 13, in any of the 40 files"*, so *"a shuffle over 306 un-collapsed cards will give a chance line that is too easy to beat."* That became problem `N-1` and the event-collapse engine (`scripts/15_event_collapse.py`).

The canteen chair (Sofia) wrote the book, frozen by SHA-256:

> "Directional rules: the list is empty. No rule in this book says buy or sell."

The score recipe has two scores kept apart, Movement (0..1) and Direction (0..0), one raising signal, six blockers and eleven unknowns. Its buy and sell lines are empty, "because D = 0 on every card by construction. The recipe's instruction on every card is *do nothing*." She looked for a red stamp she could challenge on the material and found none. She listed eight ideas that occurred to her and that she refused to write, each with the reason: several watchers stated the principle, none filed the trigger, so building one would have been her construction, not an observation.

**The lab was built to find a scoring system. It produced one whose every instruction is "do nothing", and recorded why.**
