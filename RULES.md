# Rules

These rules do not change. If one must change, the user is asked first, and then
it is written into `LEDGER.md`.

## A · The wall — nothing leaks in from the old project

1. Balıkçıl reads only its own folder. No file, result, note, or number is read
   or copied from the rest of the repository (old experiments, status files, old
   memory).
2. Data is downloaded from scratch, from publicly available sources. For every
   file, where and when it was downloaded is recorded, and a fingerprint
   (SHA-256) is taken. The Binance archive is verified against its own checksum
   file.
3. Agents are not told what to look for, only what they may look at. An
   instruction contains no result, no prediction, and no "pay attention to X"
   steer.
4. The full text of every instruction given to an agent is copied into the
   `instructions/` folder. The user can check for leaks at any time.
5. Balıkçıl is always run from **a session opened in its own folder.** The wall
   settings (`.claude/settings.json`) only work when opened that way:
   - the old rule file in the parent folder is not loaded
   - reading the old folders is blocked
   - Balıkçıl's memory is kept separate

   Every agent launched from the old project's session carries the old rule
   file. That is why Balıkçıl's work is not run from there.

   There is one hole the settings cannot close: reading files from the command
   line. Rule 1 applies there, and every instruction forbids it explicitly.

## B · Not deceiving ourselves

6. The rule is written first, the result is opened second. A rule is not changed
   after looking at a result. If it is changed it counts as a new rule, carries
   the "afterwards" label, and is tested again.
7. Free observation produces ideas, not evidence.
8. Every idea is written in three parts: on what condition (trigger), in which
   direction (buy or sell), when to get out (exit). If one is missing it is not
   an idea, because it cannot be tested.
9. In the exam the coin name and the date are hidden. The answer key is sealed
   before the exam: its fingerprint is written into `LEDGER.md`.
10. An agent sitting the exam cannot use tools and cannot read files. A paper
    where tool use is observed is void.
11. Every result is measured against three rivals:
    - a coin flip
    - a simple rule: whichever direction the last 24 hours went, continue that way
    - somebody who has not watched at all (Tomás)

    A finding that cannot beat all three does not count as "learned".
12. The chance line is not invented. The answers are shuffled 1,000 times, and
    the real result must fall inside the best 1%.
13. Moments occurring in several coins in the same hour count as a single event.
    If the whole market moved together, that is one event.

## C · Money

14. The money test is run with costs: trading fee, slippage, funding payment.
15. The account grows by multiplying, not by adding. Returns are compounded. Even
    a single trade that zeroes the account is counted separately.
16. Entry happens at the first real price after the signal. At a moment known in
    advance (a payment time, an announcement time) the candle's open price does
    not count as the fill price, because nobody could buy at it.
17. Leverage is at most 5x. Liquidation is calculated against the candle's
    extreme price.
18. The result is shown separately for the two halves of the period. If one half
    wins and the other loses, that is not a finding.

## D · Honesty

19. An unmeasured number is not written down. If it is an estimate, "estimate" is
    written next to the number.
20. Before saying "none", where we looked and what error we got is written down.
    A connection error does not mean "no data".
21. A technical failure is not a result.
22. In the report, unresolved things are listed one by one, by name. "Could not
    be measured" never turns into "no problem".
23. The clock is not guessed, it is read.

## E · Cost and operation

24. The model is chosen explicitly for every task. Smaller model first; a medium
    or large model with a reason.
25. The tokens spent on the first 10 cards are measured. The estimate for the
    full run is written into `LEDGER.md` and told to the user in a single
    sentence before starting.
26. Work longer than 10 minutes is written with intermediate checkpoints and
    started in a way that survives the session closing.
27. Only publicly available, documented data is used. Addresses are not searched
    for by guessing.
28. Free disk space is checked before downloading.

## F · Records and the score ledger

29. Every run has a number: the fingerprint of its input. The same input gives
    the same number and the same result.
30. Records are append-only. If something tries to write different content under
    an existing number, the script stops.
31. Every score is written in ledger form:
    - **total score**
    - **raising signals:** how many points each one contributed, next to it
    - **blockers:** if even one is present there is no trade, whatever the score
    - **unknowns:** things that could not be measured. This line cannot be left
      empty; if there genuinely are none, why there are none is written.
32. An objection is made with reasoning. An unreasoned "no" does not count; and
    nobody can override a reasoned blocker.

---

## G · Open questions

Added 2026-09-19 on the user's decision. An **open question** is a point the
written rules do not settle by themselves: a wording that can be read two ways,
a gap an instruction did not cover, a choice that changes the numbers.

33. **An open question is never answered by one person** — and least of all by
    the coordinator alone. **At least three jurors answer it independently**, in
    separate contexts, without seeing each other's answers. Three answers that
    saw each other are one answer. A juror decides procedure and definition
    only: never a trading rule, never a threshold or score, and never a change
    to a rule in this file.
34. **Every answer cites what it rests on** — a file and a line, quoted. An
    answer citing nothing does not count and is struck out before the count is
    taken. This is the same discipline as a watcher note without a card number.
35. **A mini referee ratifies or refuses.** It checks six things: count,
    independence, grounding, the split, the reasoned objection (RULES 32), and
    scope. **It never answers the question itself** — if all the jurors are
    wrong it refuses and says why. A tie is no outcome. Ratification and
    refusal are both written into `LEDGER.md` with the split in numbers.

    The referee runs on a small model on purpose. A referee that reasons its way
    to a preference has stopped being a referee. This is the single exception to
    the 2026-09-18 decision that every role runs on `opus`.

---

## Note on language · 2026-09-18

This file was originally written in Turkish as `KURALLAR.md`. On the user's
decision the laboratory's working language is English, and this English text is
now **the authoritative version.** Rule numbers are unchanged, so references of
the form "RULES 12" still point at the same rule.

The only Turkish output in the laboratory comes from the reporter (Derya), who
writes the account for the user. See `TEAM.md`.
