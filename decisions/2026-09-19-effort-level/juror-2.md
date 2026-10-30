# Juror answer — the effort level for the observation run

Open question: which effort level does `TACTICS.md` section 4 select for the
observation run, on the evidence the pilot produced?

Juror 2 · 2026-09-19 · model `opus` · effort high · written without seeing any
other juror's answer.

---

## 1 · Answer

On the evidence the pilot produced, `TACTICS.md` section 4 selects **effort
high** for the observation run: the high arm produced 2.6x as many countable
notes (68 against 26) for 12.4% more tokens (101,346 against 90,152) —
both figures measured, the multiples arithmetic on them — and section 4's
criterion is exactly those two quantities.

## 2 · What it rests on

**The criterion is fixed by section 4 itself.** `TACTICS.md` line 75:

> - **Pilot:** the same 10 cards are read at two effort levels. Note quality and
>   the token difference are written into `LEDGER.md`, and the effort level is
>   chosen accordingly.

So there are exactly two inputs — *note quality* and *the token difference* —
and nothing else in section 4 or elsewhere weighs them. I do not get to invent a
weighting (RULES 33 forbids me a threshold), so I can only answer where the two
inputs point the same way or where one moves a lot and the other barely moves.
Here the second is the case.

**What "a note" is, and therefore what counts as quality, is defined in the same
section.** `TACTICS.md` line 81–82:

> - Note format: `card no · what I saw · why I think so · how sure I am (1–5)`.
>   A note without a card number does not count.

This is the laboratory's own unit of watcher output. The measured artefact
counts exactly that unit. `data/pilot/2026-09-19-pilot-measurements.md` line 22:

> | lines beginning with a card number | 26 | 68 |

with `data/pilot/2026-09-19-pilot-measurements.md` line 23 showing the coverage
is equal on both sides, so the 68 is not concentration on fewer cards:

> | distinct cards cited | 10 | 10 |

**The token difference.** `data/pilot/2026-09-19-pilot-measurements.md` line 11:

> | subagent tokens | 90,152 | 101,346 |

Difference 11,194 tokens, high/medium = 1.124 **[computed from the two measured
values]**. Notes per 1,000 subagent tokens: medium 0.288, high 0.671
**[computed]** — 2.33x.

**I also read both notes files rather than trusting the line counts.** The
difference is not padding. The high arm writes one line per card with its method
stated and marks its own arithmetic, e.g.
`notes/2026-09-19-round1-price-high.md` line 30:

> C005 · Before-window mean volume 4.055M **[computed]** vs baseline 960.13k =
> 4.22x **[computed]** — the largest expansion of the ten. Card is large.

and it refuses to fill a slot it cannot fill —
`notes/2026-09-19-round1-price-high.md` line 99:

> **BLOCKER CANDIDATE — direction deliberately absent.** … I am NOT calling this
> an idea: it has no buy/sell direction, so under RULES 8 it does not qualify,
> and I say so rather than inventing a direction to fill the slot.

The medium arm's per-card work is largely collapsed into aggregate
`C001–C010` lines and it eyeballs where the high arm computes —
`notes/2026-09-19-round1-price-medium.md` line 27:

> Last-before-hour quote volume divided by the before-window median volume
> (medians eyeballed — **estimate**)

Both arms are honest under RULES 19; the medium arm is honest *about having
estimated*, the high arm did the arithmetic instead. For Sofia, who "Cannot:
invent an idea. Every rule rests on at least one watcher note and a card number"
(`TEAM.md` line 54–55), a note carrying a computed per-card number is worth more
than one carrying an eyeballed aggregate.

**The two arms are otherwise identical**, which is what makes the comparison
readable at all. `data/pilot/2026-09-19-pilot-measurements.md` line 5–6 says the
two instructions "differ in four lines (title, role, effort, output path)", and
I checked that claim myself against
`instructions/2026-09-19-0720-watcher-round1-price-medium.md` and
`…-high.md`: they differ in the title line, the role line, `effort: medium` vs
`effort: high`, and the output path. Field of view, card list, wall text and
reporting format are word-for-word the same.

**Nothing else in the rules overrides this.** RULES 24 is the only cost rule
that bears on the choice:

> 24. The model is chosen explicitly for every task. Smaller model first; a
>     medium or large model with a reason.

It speaks of *model*, and `TEAM.md` line 10–11 says "the distinction is
otherwise made by **effort level**, not model size", so the nearest reading of
RULES 24 by analogy demands a *reason* for the larger setting. The reason is on
the table and measured: 2.6x countable notes for 1.12x tokens. Read strictly as
written, RULES 24 does not constrain effort at all and is silent here.

**Two consequences I record but do not decide.** `TEAM.md` line 156 defines
`watcher-high` "for TACTICS 4's pilot only", and `TEAM.md` lines 26, 32, 39, 44
give Ingrid, Kenji, Amara and Lukas "effort medium". Acting on this answer means
editing `TEAM.md`, not `RULES.md`. Whether and how that edit is made is the
coordinator's, not mine (RULES 33).

## 3 · The strongest case against my answer

**(a) One run per arm is one sample per arm.** The pilot has n=1 on each side.
Nothing in the artefact separates "effort high writes more notes" from "this
particular run wrote more notes". Two `opus` runs at the *same* effort could
plausibly differ by 26 vs 68 lines; the pilot never measured that, so the
within-arm spread is unknown. This is the objection I find hardest to answer,
and it is not fully answerable from the files I was given. What blunts it: the
gap is 2.6x, not 10%, and it is accompanied by a structural difference in how
the notes are written (per-card computed lines vs aggregated eyeballed lines),
which is a difference in kind, not only in count.

**(b) By the one output that RULES 8 calls testable, medium won.**
`data/pilot/2026-09-19-pilot-measurements.md` line 35–37:

> Complete ideas produced (trigger · direction · exit, RULES 8): medium 2, both
> flagged weak; high 1, flagged thin, plus 2 written with the direction slot
> deliberately left empty.

RULES 8: "Every idea is written in three parts … If one is missing it is not an
idea, because it cannot be tested." On that count it is 2–1 to medium, and a
juror who reads "note quality" as "how many testable ideas came out" must select
medium. My reason for not reading it that way: section 4 defines the watcher's
deliverable as *notes* in the format quoted above, and TACTICS 5 assigns the
writing of rules to Sofia, not to the watchers — so ideas are the canteen's
output measure, not the watcher's. Also, the high arm's two direction-empty
items are a correct application of RULES 8 rather than a failure of it; counting
them against high rewards an agent for inventing a direction it did not have.
But I concede this reading is available on the text and is not silly.

**(c) The cost gap is larger than the token gap suggests.** Line 13:
`| duration (ms) | 223,683 | 344,796 |` — high took 54% longer **[computed]**.
Wall-clock is not what section 4 names, and 344,796 ms is under the 10-minute
mark at which RULES 26 demands checkpoints, but four watchers over the full card
set multiply it. If the laboratory's binding constraint turns out to be time
rather than tokens, the pilot's headline 12.4% understates the price of high.

**(d) The evidence might select nothing.** Section 4 gives two criteria and no
exchange rate between them, and a juror could say honestly: "the rules do not
settle this — the coordinator must ask the user for a weighting." I rejected
that because a weighting is only needed when the two criteria conflict
materially; here one moves 2.6x and the other 1.12x in the opposite direction,
so every monotone weighting that treats a countable note as a good and a token
as a cost of the same rough order selects high. If someone holds a weighting
under which 11,194 tokens outweigh 42 additional grounded notes, they should
state it, because it is not in any file I read.

**(e) One coin, one field of view.** Both arms read ten cards that are all
`AVGOUSDT` and three of which are one continuous episode — both agents found
this independently (measurements line 32–34; `…-price-high.md` line 16). The
pilot therefore measured effort on an unusually thin card set, in one of four
fields of view (price). Ingrid's, Kenji's and Amara's fields were never piloted.
The finding is being generalised across watchers on no measurement.

**Reversibility.** Selecting **high** is the reversible branch: if it proves
wasteful, the observation run is re-run at medium, and free observation "produces
ideas, not evidence" (RULES 7), so nothing downstream — exam, answer key, money
test — is contaminated by the discarded notes. Reversal cost is roughly four
watcher runs of pilot size, order 400k subagent tokens — **estimate**,
extrapolated from the per-arm measured figures times four watchers, and the
extrapolation is mine, not the artefact's. Selecting **medium** is equally
reversible in principle and slightly cheaper to reverse, but carries the quieter
irreversible risk: thin notes go into the canteen, Sofia's rules rest on them,
and the exam is then built and sat against rules grounded in 26 notes rather
than 68 — by the time that shows, the canteen book is frozen with its
fingerprint in `LEDGER.md` (TACTICS 5, line 94–95) and unwinding it costs the
whole canteen stage, not just the notes.

## 4 · Confidence and what would change my mind

**Confidence: 4 of 5.**

Four, not five, because of objection (a): a single run per arm cannot separate
effort from run-to-run variance, and because the ideas count (objection b) runs
the other way and rests on the same artefact I am citing.

What would change my mind:

- **A repeat arm.** Two runs at the same effort, same cards, showing a spread in
  countable notes comparable to 26 vs 68. That would dissolve the entire signal
  and my answer becomes "the pilot does not select an effort level".
- **A stated weighting.** If the user or a rule fixes a token budget under which
  11,194 extra tokens per watcher-run is not affordable, medium follows
  mechanically and I would say so.
- **A reading of "note quality" I have not seen** grounded in a line of
  `TACTICS.md` or `TEAM.md` that makes testable ideas rather than grounded notes
  the watcher's quality measure. Objection (b) is that argument in embryo; a
  cited line would make it win.
- **Evidence that the high arm's extra 42 lines are restatement.** I read both
  files and judged they are not — the high arm's extra lines are per-card
  computed values (sections B, C, D, E of `…-price-high.md`) rather than
  repetition — but that judgement is mine, unmeasured, and someone could show
  otherwise by content analysis.

Nothing in this answer decides a trigger, a direction, an exit, a threshold or a
score, and it changes no rule in `RULES.md` (RULES 33).

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

Nothing else was opened or listed. `exam/`, `decisions/` (other than this file,
which I created and did not read around), `LEDGER.md`, `cards/`, `canteen/`,
`reports/`, `scripts/` and the rest of `data/` and `instructions/` were not
touched. No folder-wide glob was run; every read was a named path. No memory or
session-log search was run.

## Assumptions the instruction did not cover

1. **That I may do arithmetic on the measured values.** The pilot file states
   raw values and declines to compare them. The question asks which level the
   evidence selects, which cannot be answered without dividing 68 by 26 and
   101,346 by 90,152. I treated that arithmetic as mine, marked it
   **[computed]**, and kept the raw values visible beside it.
2. **That "note quality" is measured on the unit TACTICS 4 defines** — a line
   beginning with a card number — rather than on ideas, bytes or lines. I argued
   this from the text rather than assuming it silently, and put the competing
   reading in part 3.
3. **That the pilot's price field of view stands in for the other three
   watchers.** The pilot measured only Lukas's field; extending the choice to
   Ingrid, Kenji and Amara is an assumption, and I flagged it as objection (e).
4. **That the choice is between exactly `medium` and `high`.** `TEAM.md` line 65
   shows a third setting exists in the laboratory (`skeptic` · effort xhigh).
   The pilot did not test it and section 4 says "two effort levels", so I did
   not consider it.
5. **That the harness-measured 68 governs, not the agent's self-reported 56**
   (measurements line 25: "notes the agent itself reported writing … 56"). I
   used the measured line count for both arms, since a self-report exists for
   only one arm and RULES 19 prefers the measured number.

## Steer check

I looked for a steer in the instruction (RULES 3): a stated result, a comparison,
a ratio, or a "pay attention to X". I found none. The instruction states
"This instruction states none of it, draws no comparison and computes no ratio",
and having now read the evidence I can confirm that is true of its text — it
names the files and neither quotes nor summarises their contents. It also offers
the null outcome explicitly ("If the evidence does not select an effort level,
say so"), which cuts against rather than towards either arm. I saw no other
juror's answer and read no file in `decisions/`.
