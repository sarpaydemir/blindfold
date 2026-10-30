# Open question — the effort level for the observation run

**Juror:** juror-1 · `juror` · model `opus` · effort `high`
**Date:** 2026-09-19
**Question:** which effort level does `TACTICS.md` section 4 select for the
observation run, on the evidence the pilot produced?

---

## 1 · Answer

On the evidence the pilot produced, `TACTICS.md` section 4 selects **effort
`high`** for the observation run: the high arm produced 2.6x as many notes that
count under section 4's own counting rule for 12.4% more subagent tokens.

---

## 2 · What it rests on

**The selection rule, and its two criteria.** `TACTICS.md` section 4, first
bullet:

> - **Pilot:** the same 10 cards are read at two effort levels. Note quality and
>   the token difference are written into `LEDGER.md`, and the effort level is
>   chosen accordingly.

So exactly two things decide it: **note quality** and **the token difference**.
Nothing else in section 4 bears on the choice. I take these in turn.

**The token difference.** `data/pilot/2026-09-19-pilot-measurements.md`,
"Reported by the harness":

> | subagent tokens | 90,152 | 101,346 |

101,346 ÷ 90,152 = **1.1242**, i.e. high costs **+12.42%** — +11,194 subagent
tokens over ten cards. (Arithmetic mine, on two measured values; not an
estimate.) The same table:

> | tool uses | 14 | 14 |
> | duration (ms) | 223,683 | 344,796 |

Tool uses are identical; wall-clock is 1.54x (arithmetic mine). Section 4 names
"the token difference", not duration, so duration is context, not a criterion.

**Note quality, measured — section 4 supplies its own counting rule.** Same
section, fourth bullet:

> - Note format: `card no · what I saw · why I think so · how sure I am (1–5)`.
>   A note without a card number does not count.

`data/pilot/2026-09-19-pilot-measurements.md`, "Measured from the notes files":

> | lines beginning with a card number | 26 | 68 |
> | distinct cards cited | 10 | 10 |

By section 4's own rule, medium produced **26** countable notes and high **68**
— **2.615x** (arithmetic mine). Per 1,000 subagent tokens: medium 0.288, high
0.671, i.e. **2.33x the countable notes per token** (arithmetic mine). This is
the single cleanest quality comparison available, because it is a count the
laboratory's own rule defines, not my taste.

**Note quality, read.** I read both notes files in full. Three things in the
high arm are absent from the medium arm and bear on what the observation run is
for:

- `notes/2026-09-19-round1-price-high.md` line 52 — a warning that the pattern
  may be an artefact of how moments were selected: "TACTICS §2 defines a
  moment's start as 'the hour at which the 24-hour movement began', so a quiet
  before-window may be built into how the moments were selected rather than
  being something the market does. It would be easy to mistake the selection
  procedure for a signal here."
- Same file, line 19 — "The coin's activity regime changed by roughly 40x inside
  these ten weeks … so thresholds in my field should be ratios, never levels."
  This constrains the form of any rule Sofia can write (TACTICS 5a).
- Same file, line 14 — "The ten start hours run 2026-05-07 20:00 to 2026-07-16
  00:00 — about ten weeks, not a year." A fact about the card set itself.

The medium arm carries findings the high arm lacks — the depth-asymmetry test
(line 36), the "depth column behaves like a one-off-large-resting-order
reading" note (line 37), and an explicit RULES 20 section G. So the difference
is not one-directional in content. It is one-directional in **volume of
grounded, card-numbered assertion**, which is what section 4 counts.

**The idea count does not reverse this.** `data/pilot/…-measurements.md`:

> - Complete ideas produced (trigger · direction · exit, RULES 8): medium 2,
>   both flagged weak; high 1, flagged thin, plus 2 written with the direction
>   slot deliberately left empty.

Read naively this favours medium 2-to-1. It does not, because `RULES.md` 8 says:

> 8. Every idea is written in three parts: on what condition (trigger), in which
>    direction (buy or sell), when to get out (exit). If one is missing it is not
>    an idea, because it cannot be tested.

The high arm declined to fill the direction slot and said so
(`notes/…-price-high.md` line 99): "it has no buy/sell direction, so under
RULES 8 it does not qualify, and I say so rather than inventing a direction to
fill the slot." Under RULES 8 that is compliance, not shortfall. And `README.md`
line 49 — "**Free observation produces ideas, not evidence.**" (also RULES 7) —
means the count of weak ideas is not the product being bought here; the notes
are, because TACTICS 5 has Sofia rest every rule "on at least one watcher note
and a card number" (`TEAM.md` line 51–52).

**The default that high must overcome, and why it is overcome.** `TEAM.md`
line 9–12: "Every task states its model and effort level explicitly. Model is
`opus` everywhere except the **referee** … the distinction is otherwise made by
**effort level**, not model size." `TEAM.md` line 154 lists `watcher` at effort
`medium`, and line 156 lists `watcher-high` as "the same four watchers at effort
high, for TACTICS 4's pilot only". `RULES.md` 24 — "Smaller model first; a
medium or large model with a reason" — is written about *model*, but its posture
is that the cheaper setting is the default and the dearer one needs a reason.
A 12.42% token premium for 2.615x the countable notes is that reason, and
TACTICS 4 is precisely the mechanism that was written in advance to supply it
(RULES 6: "The rule is written first, the result is opened second").

**Reversibility.** Selecting high is **reversible**: it changes which agent
definition and effort line the coordinator writes into the three remaining
round-1 watcher instructions. Nothing measured has to be thrown away — the
medium arm's notes already exist and stand as one watcher's round-1 output
whichever way this goes. The cost of reversing later is re-running watchers,
which the pilot measures at roughly 90k–101k subagent tokens per watcher per ten
cards; extrapolating that to the full card set is an estimate I am not
authorised to make and did not make. The **irreversible** reading would be
"select high and also delete or supersede the medium arm's notes" — nothing in
TACTICS 4 asks for that, and I am not proposing it.

**What I am not deciding.** Under `RULES.md` 33 a juror "decides procedure and
definition only: never a trading rule, never a threshold or score, and never a
change to a rule in this file." Nothing in `RULES.md` changes on this answer.
But note honestly: acting on "high" requires editing `TEAM.md` line 154/156 (the
`watcher` effort entry, and/or the "for TACTICS 4's pilot only" scope on
`watcher-high`). `TEAM.md` is not `RULES.md`, and TACTICS 4 explicitly
anticipates the effort level being set by this pilot — so that edit is bookkeeping
following a rule, not a rule change. It is still an edit somebody must make, and
I flag it rather than leave it implicit.

---

## 3 · The strongest case against my answer

**(a) The two arms are not a clean single-variable comparison, and I could not
verify that they are.** The instruction put to me says the arms differ "only in
effort level". The measured file is more careful —
`data/pilot/2026-09-19-pilot-measurements.md` line 5–6: the instructions "differ
in four lines (title, role, effort, output path)". **`role` is one of them**:
`instructions/…-price-medium.md` line 5 reads "`watcher` · watcher", while
`instructions/…-price-high.md` line 5 reads "`watcher-high` · watcher". Those
are two different agent definitions (`TEAM.md` line 154 and 156). If
`watcher-high` differs from `watcher` in anything beyond its effort line — a
longer brief, an extra instruction about computing, a different output
convention — then part of the 26-vs-68 gap belongs to the definition, not to
effort, and the pilot does not measure what section 4 asked it to measure.
**I could not check this: `.claude/agents/` is not among the files this
instruction permits me to read.** This is the strongest objection and I cannot
close it myself. Circumstantially it is weakened by the two arms recording 14
tool uses each and by both arms independently finding the C003/C004/C005
continuity — but circumstance is not verification.

**(b) n = 1 per arm, one field of view, one coin.** Both notes files state the
ten cards are all `AVGOUSDT` (`…-price-medium.md` line 5; `…-price-high.md` line
13). One watcher field ("price itself") was piloted; Ingrid's, Kenji's and
Amara's fields were not. There is no repetition, so 26-vs-68 is a single draw
from a stochastic process, not a mean. A second medium run might produce 60
notes. Section 4 prescribed exactly this pilot and no more, so this is a
weakness of the prescribed instrument, not a misreading of it — but it means my
answer rests on one measurement per arm, and I will not dress that up.

**(c) Line count is a proxy for quality, and a bad one is easy to game.** 68
lines is not 2.6x the *insight*; a good deal of the high arm's B and C sections
is one arithmetic operation repeated per card, ten lines where the medium arm
wrote one line holding all ten numbers (compare `…-price-high.md` lines 26–35
with `…-price-medium.md` line 21). On a per-*finding* count rather than a
per-*line* count the two arms are much closer, and I did not attempt a
per-finding count because any such count would be my judgement dressed as a
measurement (RULES 19). If the laboratory reads "note quality" as findings
rather than countable notes, this answer weakens considerably — though I think
section 4's own "A note without a card number does not count" points at counting
notes.

**(d) The honest zero-difference reading.** One could argue a 12.42% token
difference is small enough, and the substantive findings similar enough, that
the pilot simply fails to select — and that the TEAM.md default (medium) should
therefore stand untouched, which is also the cheaper and more conservative
outcome under RULES 24's posture. I considered this seriously. I reject it
because "note quality and the token difference" are the two criteria section 4
names, and on the one of them that the laboratory defines objectively the gap is
2.6x — far larger than the 1.12x cost gap. A 2.6x-for-1.12x trade is a selection,
not a wash.

---

## 4 · Confidence, and what would change my mind

**Confidence: 4 of 5.**

Four rather than 5 because of objection (a): I was not permitted to read the two
agent definitions and therefore could not confirm that effort is the only thing
that differed between the arms.

What would change my mind, each of these on its own:

1. **The `watcher` and `watcher-high` definitions differ in more than the effort
   line.** Then the pilot is confounded, my answer should be withdrawn, and the
   correct outcome is "the evidence does not select" until a clean arm is run.
   This is checkable in minutes by diffing two files in `.claude/agents/`, and
   somebody who is allowed to read them should.
2. **A measured full-run token estimate at high that crosses a cost limit the
   user has set.** RULES 25 requires the full-run estimate be told to the user
   before starting. I did not read `LEDGER.md` (closed to me) and computed no
   extrapolation. If high's full-run cost is unacceptable, cost beats a note
   count and the answer becomes medium.
3. **A second pilot pair that reverses or flattens the 26-vs-68 gap.** One
   additional arm per level would tell us whether the gap is the effort level or
   the draw.
4. **A per-finding recount, done by somebody other than me, showing the two arms
   substantively level.** That would move this to "does not select" (objection
   c/d), not to "medium".

What would *not* change my mind: the 1.54x wall-clock difference. Section 4 names
the token difference, and RULES 26 addresses long work with checkpoints rather
than by preferring speed.

---

## Files I read

- `RULES.md` (whole)
- `TACTICS.md` (whole)
- `README.md` (whole)
- `TEAM.md` (whole)
- `data/pilot/2026-09-19-pilot-measurements.md`
- `notes/2026-09-19-round1-price-medium.md`
- `notes/2026-09-19-round1-price-high.md`
- `instructions/2026-09-19-0720-watcher-round1-price-medium.md`
- `instructions/2026-09-19-0720-watcher-round1-price-high.md`

Nothing else. I opened no file under `exam/`, `decisions/`, `cards/`,
`canteen/`, `reports/`, `scripts/`, `LEDGER.md`, no other file under `data/` or
`instructions/`, and nothing outside `balikcil/`. I ran no folder-wide
glob and no search over past session logs. I read no other juror's answer and
did not list this folder.

## What I had to assume

1. **That `watcher` and `watcher-high` differ only in effort.** Assumed because
   the instruction asserts it and `TEAM.md` line 156 describes `watcher-high` as
   "the same four watchers at effort high". Not verified — `.claude/agents/` was
   not among my permitted files. See objection (a).
2. **That "the observation run" means the remaining round-1 watcher runs under
   TACTICS 4** (Ingrid, Kenji, Amara and a re-run or continuation for Lukas's
   field), not the exam or the money test. TACTICS 4 is titled "Free
   observation" and the pilot sits inside it.
3. **That the arithmetic in part 2 (1.1242, 2.615, 2.33, 1.54) is mine to do.**
   The pilot file states at line 40–41 that it draws no comparison and that any
   extrapolation belongs elsewhere. I computed ratios of two measured values,
   which is comparison, not extrapolation; I produced no full-run estimate.

## Steer check

**I found no steer in my instruction.** The question is put openly, it states no
comparison and no ratio, and it offers the null outcome explicitly — "If the
evidence does not select an effort level, say so."

Two things I record anyway, as accuracy rather than accusation:

- The instruction says the arms differ "only in effort level". The measured file
  is more precise (four lines differ, one of them the role/definition). The
  simplification runs in the direction of making the pilot look cleaner than it
  is; it did not tell me which arm to prefer, so I do not call it a steer, but it
  is the reason my objection (a) exists.
- My launch context (a git-status system note, not a file I opened) contained
  recent commit subject lines referring to `LEDGER.md` content, including "RULES
  25 measured: pilot costs, full-run estimate, pilot limitations". I did not open
  `LEDGER.md` or act on those subjects, and no cost figure from them appears
  anywhere above. Reporting it because it arrived unasked and touches a file
  closed to me.
