# Tactics — step by step

## 0 · Period and universe

- **Period:** 2025-09-01 → 2026-08-31. If something is found, it is tested a
  second time over 2024-09-01 → 2025-08-31.
- **Universe:** every Binance USDT perpetual futures contract that traded during
  this period. The list is built from the archive (`data.binance.vision`), not
  from today's exchange, so that coins which died during the period are included
  too.

## 1 · The draw

- Coins are split into four groups:
  - **new:** first trade falls inside the period. Assigned **first and
    exclusively** — a new coin is not also ranked by volume.
  - **large / mid / small:** every other coin, ranked by its median daily
    trading volume (`quote_volume`) over the period and cut into **three
    groups of equal size**; where the count does not divide by three, the
    remainder goes to the lower-volume groups. Ties are broken by symbol name
    ascending, so the ranking is reproducible.
- **Draw number:** `20260913`. Written before the draw; it does not change.
- **Observation:** 10 coins (3 large · 3 mid · 2 small · 2 new)
- **Exam:** a different 20 coins (6 · 6 · 4 · 4)
- **Money test:** all remaining coins
- The group totals, the cut values, the seed and the fingerprint of each list
  are written into `LEDGER.md`, together with the names of the **10 observation
  coins**. The **exam and money-test names are not written into `LEDGER.md`**;
  they live in `exam/draw/`, which the watcher, canteen chair and skeptic
  definitions close. Watchers do not see the names of the exam and money-test
  coins, and `LEDGER.md` is a root document a watcher can be pointed at.

## 2 · Moments

- Hourly closing prices are used.
- **Large-movement moment:** the places where the coin rose or fell the most
  within 24 hours.
  - The largest 20 of the year are taken for each coin.
  - Of two moments closer than 48 hours to each other, only the larger counts.
  - For a coin that did not trade all year this count shrinks in proportion to
    its lifetime: one moment per 18 days.
- **Calm moment:** the same number as the large moments, chosen at random. At
  least 72 hours away from any large movement.
- A moment's start is the hour at which the 24-hour movement began.

## 3 · The card

One page per moment. It has two sections:

- **Before:** the 24 hours before the start, hour by hour; plus a one-line
  summary of the previous 7 days.
- **After:** the 24 hours after the start. Shown only in free observation, never
  in the exam.

**What is on the card** (where data exists):
- price, volume, trade count, taker buy/sell pressure
- open interest, long/short ratios (5-minute archive)
- funding rate, payment interval and its changes
- order book depth (only the moment days are downloaded; the files are large)
- Binance and Korean exchange announcements (listing, delisting, warning)
- bitcoin and ethereum, over the same hours
- US release calendar (inflation, employment, rate decision)
- number of people viewing the page on Wikipedia (daily)
- the price of the relevant prediction market, if any

**What is not on the card**, because there is no history or it cannot be
reached: Google searches, Reddit, Twitter, the history of leverage limits, a
world news archive. The news archive could not be reached from this machine; if
a way is found it will be added.

Numbers are rounded and the card is kept short. The AI never sees raw seconds.

## 4 · Free observation

- **Pilot:** the same 10 cards are read at two effort levels. Note quality and
  the token difference are written into `LEDGER.md`, and the effort level is
  chosen accordingly.
- The four watchers (Ingrid, Kenji, Amara, Lukas) read all the cards of the 10
  coins. Each takes notes from their own field of view.
- Cards are given in shuffled order: large moments and calm moments interleaved.
- Note format: `card no · what I saw · why I think so · how sure I am (1–5)`.
  A note without a card number does not count.

## 5 · The canteen

- **Round 1:** everybody writes their notes into the `canteen/` folder.
- **Round 2:** everybody reads the other three's notes and agrees or disagrees
  while citing card numbers.
- **Viktor** attacks every idea.
- **Sofia** writes down the survivors:
  - (a) **mechanical rules:** trigger · direction · exit; measurable by script
  - (b) **score recipe:** how many points each signal is worth, at what score to
    buy, at what score to sell. Written in ledger form (RULES 31).
- At most two rounds. Then the canteen book freezes and its fingerprint is
  written into `LEDGER.md`.

## 6 · The blind exam

- Nadia has 400 cards prepared from the exam coins: 200 before a large movement,
  200 calm moments. The cards contain only the "before" section.
- **What is hidden:**
  - the coin name
  - the date and time
  - the price itself (converted to a number starting from 100)
  - the coin name inside announcements
  - the Wikipedia number itself (given as a ratio to the coin's own average)
  - the date in the release calendar
- The answer key is written to a separate file. Its fingerprint goes into
  `LEDGER.md` before the exam.
- **Who sits the exam** (all get the same 400 cards):
  1. Hana, with Sofia's score recipe
  2. Tomás, with no recipe, on common sense alone
  3. Greta, applying Sofia's mechanical rules by script
  4. the simple rule: the direction of the last 24 hours continues
  5. a coin flip
- **Answer format:** `card no · up / down / stays calm · confidence 0–100`.
  Hana and Greta also fill in the score ledger for each card: score, raising
  signals, blockers, unknowns.

## 7 · Scoring (Greta)

- Two questions are asked:
  1. Could it separate large movements from calm moments?
  2. In the large movements, did it get the direction right?
- **Chance line:** the answers are shuffled 1,000 times; the boundary of the
  best 1% is the line.
- A moment appearing in several cards in the same hour counts as a single event.
- Every exam and money run is recorded with its number, and the record cannot be
  changed (RULES 29–30).
- **Passing condition** (written before the result): the paper with a recipe
  (Hana or Greta)
  - beats the chance line, **and**
  - beats Tomás, **and**
  - beats the simple rule.

  Whether it beat its rivals is also tested by the shuffling method, at the 1%
  boundary.

## 8 · The money test

- Only rules that passed the exam enter.
- Run by script on the money-test coins (never observed, never in the exam),
  across the whole period. Only the data the rule uses is downloaded.
- **Entry:** the first price of the hour after the signal.
- **Costs** (assumption): 0.05% fee + 0.05% slippage per side, 0.20% round trip.
  Funding is calculated from the real payments.
- **Rival:** the same number of trades, of the same duration, at random times
  (1,000 times).
- **What is measured:**
  - compound return and its daily equivalent
  - the two halves of the period separately
  - the worst drawdown from the peak
  - the number of trades that zeroed the account
  - 1x, 3x and 5x leverage
- **Passing condition:**
  - compound return positive in both halves, **and**
  - beats 99% of the random rival, **and**
  - the account is not zeroed at at least one leverage level up to 5x.
- **Compass:** 1% per day. This is not a passing grade, it shows where we stand.

## 9 · The report

- Plain first: what we asked, what came out, what it means, what is next.
- Technical after: numbers, file paths, fingerprints.
- Everything left open is listed by name.

The plain section is written in Turkish by the reporter (Derya). Everything else
in the laboratory is English. See `TEAM.md`.

## 10 · The screen (later)

Cards, notes, votes and objections will be watched on a single page. To be built
after the laboratory produces its first results.
