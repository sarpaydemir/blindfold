# Juror 3 — open question: the effort level for the observation run

Question: which effort level does `TACTICS.md` section 4 select for the
observation run, on the evidence the pilot produced?

Scope check (RULES 33): this is a procedure/operations choice about how the
observation step is run. It is not a trading rule, not a threshold, not a score,
and it changes no rule in `RULES.md` — TACTICS 4 already provides for a choice,
so applying it is not amending it. In scope.

---

## 1 · Answer

**Effort `high`** — on the two criteria TACTICS 4 names, the pilot's measured
quality proxies favour `high` on three counts, tie on one and favour `medium` on
one, while the token difference is +12.4% ([computed] from the pilot file), so
"chosen accordingly" selects `high`.

## 2 · What it rests on

**The criterion.** `TACTICS.md` line 75:

> "**Pilot:** the same 10 cards are read at two effort levels. Note quality and
> the token difference are written into `LEDGER.md`, and the effort level is
> chosen accordingly."

Two terms, no formula: *note quality* and *the token difference*. TACTICS 4
supplies no weighting, so the choice is made by reading the measured values
against what the laboratory's own documents say a note is for.

**What counts as a note.** `TACTICS.md` line 81-82:

> "Note format: `card no · what I saw · why I think so · how sure I am (1–5)`.
> A note without a card number does not count."

So the countable deliverable of step 4 is the card-numbered line. The pilot file
measured exactly that.

**The token difference.** `data/pilot/2026-09-19-pilot-measurements.md` lines
11-14:

> "| subagent tokens | 90,152 | 101,346 |
> | tool uses | 14 | 14 |
> | duration (ms) | 223,683 | 344,796 |"

`high` costs **+11,194 subagent tokens on ten cards** [computed], i.e. **1.124x**
[computed]. Tool uses are identical. Wall-clock is 1.54x [computed] — relevant to
RULES 26 scheduling, not to cost.

**The quality measurements.** Same file, lines 20-25:

> "| lines in file | 74 | 101 |
> | bytes in file | 12,104 | 19,721 |
> | lines beginning with a card number | 26 | 68 |
> | distinct cards cited | 10 | 10 |
> | occurrences of the word "estimate" | 3 | 1 |
> | notes the agent itself reported writing | not stated | 56 |"

Against TACTICS 4's own definition of a note that counts: **26 vs 68**, i.e.
**2.6x** [computed]. Format-independent volume: **12,104 vs 19,721 bytes**,
**1.63x** [computed]. Coverage ties at 10 of 10 cards. Yield per token:
0.134 vs 0.195 bytes/token [computed].

**Why note count is the right proxy here, not idea count.** The watcher's
product is the raw material for the canteen, and `TEAM.md` lines 50-51 say of
Sofia:

> "**Cannot:** invent an idea. Every rule rests on at least one watcher note and
> a card number."

and `RULES.md` line 37:

> "7. Free observation produces ideas, not evidence."

So a watcher who delivers more card-numbered, measured observations has
delivered more of what step 5 consumes; the watcher's own tally of finished
ideas is not the binding output.

**The one countable metric that favours `medium`,** stated honestly — pilot file
line 35-36:

> "Complete ideas produced (trigger · direction · exit, RULES 8): medium 2, both
> flagged weak; high 1, flagged thin, plus 2 written with the direction slot
> deliberately left empty."

2 vs 1. But the two direction-empty items in `notes/2026-09-19-round1-price-high.md`
(lines 99-100) are labelled **BLOCKER CANDIDATE**, and RULES 31 makes blockers a
required element of every score ledger:

> "**blockers:** if even one is present there is no trade, whatever the score"

and line 99 of that note refuses to fill the slot:

> "it has no buy/sell direction, so under RULES 8 it does not qualify, and I say
> so rather than inventing a direction to fill the slot."

Declining to invent a direction is compliance with RULES 8, not a shortfall, so
the 2-vs-1 gap is narrower than the raw count reads.

**Estimates.** RULES 19 line 71-72: "An unmeasured number is not written down. If
it is an estimate, 'estimate' is written next to the number." Both arms comply.
`high` carries 1 estimate across 68 notes against `medium`'s 3 across 26, so the
estimate *density* is lower in the arm with more numbers — `high` measured more
of what it reported.

**Cost discipline does not overturn it.** RULES 24 (line 84-85) — "Smaller model
first; a medium or large model with a reason" — is written about *model*, and
`TEAM.md` lines 9-11 confirm the model is fixed:

> "Model is `opus` everywhere except the **referee** ... the distinction is
> otherwise made by **effort level**, not model size."

Read in its spirit — cheaper first, dearer with a reason — the reason is present
and measured: 2.6x the countable notes for 1.124x the tokens.

**A rider, not a choice of mine.** RULES 25 (lines 84-86) still binds whichever
effort is picked:

> "The tokens spent on the first 10 cards are measured. The estimate for the full
> run is written into `LEDGER.md` and told to the user in a single sentence
> before starting."

So `high` may start only after the full-run estimate has been given to the user
in one sentence. I did not read `LEDGER.md` (outside my permitted list), so I
cannot confirm whether that has been done.

**Reversibility.** `high` is the *reversible-but-costly* reading: if the
observation run at `high` proves wasteful, the fix is to re-run at `medium`,
which costs a second full observation pass. The per-10-cards, per-watcher gap is
the measured 11,194 tokens; scaled to four watchers over the full card set the
extra spend is `11,194 x (cards / 10) x 4` — I have not measured the card count
(no file I may read states it), so any figure for it would be an **estimate** and
I do not write one. `medium` is the cheaper-but-thinner reading: its
irreversible cost is the notes never written, which the canteen cannot recover
because Sofia cannot invent an idea (`TEAM.md` line 50).

## 3 · The strongest case against my answer

Four real objections, the first two serious.

**(a) The line count flatters `high` because the two arms format differently.**
`medium` packs whole cross-card tables into single notes —
`notes/2026-09-19-round1-price-medium.md` line 21 carries all ten mean-absolute-
hourly-change values, the 0.50 cut, the 3-of-4 count and the caveat in *one*
line, where `high` spends ten lines plus a summary on the equivalent material
(that file's section B, lines 26-36). So 26-vs-68 is partly a formatting artefact,
not 2.6x the content. Bytes (1.63x) are a fairer measure, and even that partly
reflects one-fact-per-line repetition ("· Same method. · 4"). If the honest
content ratio is nearer 1.2-1.4x, it roughly matches the 1.124x token ratio and
the pilot stops selecting anything.

**(b) The contrast may be confounded.** The pilot file line 5-6 says the two
instructions "differ in four lines (title, role, effort, output path)", and
`TEAM.md` line 156 shows the arms ran under **two different agent definitions**
(`watcher` and `watcher-high`). If those definitions differ in any text beyond
effort — briefing, note-format guidance, number of points in the brief — then
what the pilot measured is definition + effort, not effort. The `high` note cites
"point 3 of my brief" (line 83) and "point 2 of my brief" (line 87); the `medium`
note cites "my definition's point 2" (line 46). Those numbers do not obviously
line up, which is exactly the shape a briefing difference would take. I could not
check: `.claude/agents/` is outside my permitted file list. **This is the
objection most likely to overturn my answer.**

**(c) The one output RULES 8 actually defines, `medium` won.** Ideas are what
step 4 exists to produce (`RULES.md` line 37; `README.md` line 49). Counted by
complete ideas, it is medium 2, high 1. My reply — that blocker candidates are
RULES 31 material — is an interpretation, not a measurement, and a reader who
weighs TACTICS 4's "note quality" as "ideas that survive to the canteen" gets the
opposite answer to mine.

**(d) `high` mis-counted its own notes.** The pilot file line 25 records `high`
self-reporting 56 notes against 68 card-numbered lines measured. Under the
laboratory's counting discipline (RULES 23: "The clock is not guessed, it is
read"), an agent whose own tally of its output is wrong is weak evidence for
"higher effort means more careful". It is an under-count rather than an
inflation, which blunts but does not remove the point.

**(e) Duration.** 1.54x wall-clock [computed] is the largest measured gap of the
three harness figures, and RULES 26 ("Work longer than 10 minutes is written with
intermediate checkpoints") makes duration an operational cost, not a free
variable, for a four-watcher full run.

## 4 · Confidence, and what would change my mind

**Confidence: 4 of 5.** The direction of the evidence is consistent across every
volume and coverage measure the pilot took, and the price of it is small and
measured.

What would move me to **`medium`**, or to "the pilot does not select":

- **The agent definitions differ beyond effort.** If `watcher` and
  `watcher-high` carry different briefs, the pilot is confounded and selects
  nothing; the honest outcome is then "re-run the pilot with one definition", not
  a choice. This alone would take me to 1.
- **A ruling that "note quality" means finished ideas.** Then the evidence
  points to `medium` (2 vs 1) and my answer is wrong.
- **A full-run token estimate that breaches a budget the user set.** TACTICS 4
  weighs quality against "the token difference"; a difference that is 12.4% per
  arm but breaks a stated ceiling across four watchers and the whole card set
  changes the weighing. I have not seen such a ceiling in `RULES.md`,
  `TACTICS.md`, `README.md` or `TEAM.md`.
- **A blind quality read of the two notes files by someone who does not know
  which arm is which.** That is the measurement TACTICS 4 really wants and the
  pilot did not take; it would beat every proxy I used.

What would *not* move me: the 1.54x duration alone. RULES 26 answers it with
checkpoints rather than with a cheaper effort level.

---

## Files read

- `RULES.md`
- `TACTICS.md`
- `README.md`
- `TEAM.md`
- `data/pilot/2026-09-19-pilot-measurements.md`
- `notes/2026-09-19-round1-price-medium.md`
- `notes/2026-09-19-round1-price-high.md`
- `instructions/2026-09-19-0720-watcher-round1-price-medium.md`
- `instructions/2026-09-19-0720-watcher-round1-price-high.md`

No file under `exam/`, `decisions/`, `cards/`, `canteen/`, `reports/`,
`scripts/`, `LEDGER.md`, or outside this folder was opened. No other juror's
answer was seen. No folder-wide glob was run.

## Assumptions I had to make, by name

1. **That "note quality" in TACTICS 4 is to be judged through the proxies the
   pilot file measured.** TACTICS 4 defines neither the term nor a way to measure
   it. I read TACTICS 4's own note definition (line 82, "A note without a card
   number does not count") as the nearest thing to an in-house definition and
   used the card-numbered line count as the primary proxy. Objection (a) is the
   cost of that assumption.
2. **That the `watcher` and `watcher-high` agent definitions differ only in
   effort.** I could not verify this — `.claude/agents/` was not in my permitted
   list. Objection (b) rests on it.
3. **That RULES 24's "smaller first, larger with a reason" carries over from
   model to effort level.** RULES 24 says model; `TEAM.md` lines 9-11 say the
   distinction between tasks is made by effort. I treated the cost discipline as
   applying to effort by analogy. If it does not apply, nothing in `RULES.md`
   constrains the token side at all, which would strengthen `high`.
4. **That I may state the RULES 25 rider** (full-run estimate to the user before
   starting) without having read `LEDGER.md` to see whether it was satisfied. I
   state it as a condition, not as a finding about what has happened.

## Steer in the instruction

One thing to report, minor and not a result-leak.

The instruction states: "Its two arms read the same ten cards with the same
field of view and the same instruction, differing only in effort level." The
artefact is more careful than that — the pilot file (line 5-6) says the two
instructions "differ in four lines (title, role, effort, output path)", and
`TEAM.md` line 156 shows two distinct agent definitions were used. The
instruction's "differing only in effort level" asserts as settled the very thing
my objection (b) says is unverified, and it points the juror away from asking
about the confound. It does not state a result, name a winner, or compute
anything, so it is not a RULES 3 result-leak; it is an over-tidy premise. I
answered without relying on it and flagged the confound instead.

Otherwise the instruction was balanced: it named both arms neutrally, computed
no ratio, and explicitly offered "If the evidence does not select an effort
level, say so."
