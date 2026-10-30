# Preparing a blind exam the coordinator could not see

Source: the private repository's `LEDGER.md`, entries 2026-09-19 13:43 UTC to 2026-10-02 00:51 UTC. The working files (`exam-prep/`, about 4,500 files) are not published; this summary uses only what the ledger recorded.

## Two problems before any exam card

The canteen book named two problems that had to be solved before an exam could be built (`TACTICS.md` 6–7):

- **`R-04`: is the exam blind?** Cards hide the coin name, the date and the price. Could a card still be traced to its coin or its date from what it prints?
- **`N-1`: collapse before counting.** 296 of 306 observation cards overlap another card, so the chance line (`RULES.md` 12) has to shuffle whole events, not cards (`RULES.md` 13).

## The coordinator is cut out

The coordinator had leaked what it knew into its instructions fifteen times by then, every time caught by the agent receiving the instruction. I ordered the two problems solved and reviewed with the coordinator kept out: one agent solves, another reviews, and neither tells the coordinator how (2026-09-19 13:43).

The fixer worked in a folder closed to every other role and to the coordinator. It wrote one file the coordinator could read, `VERDICT.md`: solved or not solved, nothing about method. A reviewer, also untold, checked the work.

## The first fix and the first review

The fixer: 277,841 tokens, 79 tool uses, 37 minutes, five new scripts. It called `R-04` solved with "a residual that is measured, named and not zero", and `N-1` solved "as far as one person is allowed to solve it". It refused to evaluate any canteen rule on the observation cards, because a result about a rule before the exam exists contaminates the exam. It also caught a presumption in its own instruction: the instruction spoke of what is needed "to count events correctly", which assumed the counting was wrong; its measurement came out mixed, and it said so.

The reviewer: 171,631 tokens, 67 tool uses, about 20 minutes, a 718-line review. It re-verified all 60 fingerprints and rebuilt every output from scratch into a scratch folder: byte-identical, every run number as claimed. It re-derived the cross-check numbers with its own code: three implementations, the same numbers. Its rulings:

- **`R-04`: solved only under three conditions.** The acceptance gate did not say which of two statistics it was graded on. A printed numeric column nobody had named could identify the coin, beat the chance line on its own, and flipped the gate from pass to fail. A second channel carried the date in a bullet line (13 of 306 cards), which a standard written about columns could not reach.
- **`N-1`: not solved.** `block_shuffle_indices()` did not keep events whole when events differ in size. In 175 of 200 draws an event read its answers from more than one source event; with an answer vector constant inside each event, only 138 of 1,000 permuted vectors stayed constant where a correct shuffle gives 1,000. The reviewer wrote a correct replacement and showed the fix run's conclusion survived it: "the defect changes the number, not the finding."
- Three errors in the fixer's own summary, including a level declared "Met" while two feature families still beat their chance line.

Its closing line: *"Every failure I found, I found because the standards were written well enough to be tested."*

The fixed engine is [`scripts/15_event_collapse.py`](../scripts/15_event_collapse.py). It moves an event only onto an event of the same size, checks every draw, and refuses to compute a chance line from a plain list, a subclass, a map it cannot re-derive, or a map not made from the sealed answer key. [`tests/test_event_collapse.py`](../tests/test_event_collapse.py) re-creates the reviewed defect and shows the check catches it.

## The night of 2026-10-01

After eleven idle days the lab ran unattended overnight. Fix, independent review, juries on whatever was referred, repeat:

- **Seven more fix runs and seven more reviews**, eight of each in all. The second fix run reversed the first: **`R-04` not solved.** `N-1`'s instrument was repaired and then blocked on jurors ruling the counting definition.
- **Questions were reviewed before any jury sat.** Review 2 found six of twelve referred questions unfit as written. Waiting for it saved five juries: fifteen Opus juror runs and five referee runs on questions that could not be answered.
- **Four juries sat that night, all ratified.** With the seven from 2026-09-19, the lab ran **11 juries, all ratified**, including 2–1 splits.
- **Review 8 found two blocks no further fix could remove**: a sequencing circle (one handed-forward item needs exam cards to exist, another forbids any exam card before `R-04` closes), and a ratified outcome that conflicts with `TEAM.md`, which keeps the exam builder blind to the canteen book. Both are rule questions, and rules change only through the user.

**The coordinator stopped the `R-04` thread instead of paying for a ninth cycle**, stopped the draw thread for the same reason, and handed four items to the user: a wall leak, the rule conflict, the sequencing circle, and an outbound privacy leak ([leaks](leaks-the-lab-reported.md)).

**Measured cost of the night: 37 agent runs, 5,961,372 tokens**, summed by script from each run's reported usage. The coordinator's own turns were not measured, and the ledger says so.

## State at the end

No exam card exists. The exam coins' raw data, moments and order books were acquired and verified. `N-1`'s jury condition is met; its other condition binds the judge's script, which was never written. `R-04` is not solved and cannot close by the routes the rules allow without a rule decision. The lab stopped there.
