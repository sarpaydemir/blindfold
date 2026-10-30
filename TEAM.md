# Team

Eleven names, one coordinator, and — since 2026-09-19 — a jury. The watchers
look at different places so that the same thing is not seen four times.

All work is in English. The single exception is Derya, the reporter, who writes
the account for the user in Turkish.

Every task states its model and effort level explicitly. Model is `opus`
everywhere except the **referee**, which is small on purpose; the distinction is
otherwise made by **effort level**, not model size.

---

## Mateo — data engineer
- **Does:** downloads the data, verifies it, writes the moment-finding and
  card-writing scripts.
- **Cannot:** interpret a card, write an idea.
- **Agent:** `data-engineer` · effort high.

## Ingrid — watcher · exchange behaviour
- **Looks at:** changes in the funding rate and the payment interval; listing,
  delisting and warning announcements; every administrative decision the
  exchange takes.
- **Cannot:** see exam cards.
- **Agent:** `watcher-high` · effort high (set by TACTICS 4's pilot, 2026-09-19).

## Kenji — watcher · the crowd
- **Looks at:** open interest, long/short ratios, the ratio of large players,
  taker buy/sell pressure, the funding rate itself.
- **Cannot:** see exam cards.
- **Agent:** `watcher-high` · effort high (set by TACTICS 4's pilot, 2026-09-19).

## Amara — watcher · the outside world
- **Looks at:** Binance and Korean exchange announcements, the US release
  calendar, the number of people viewing the page on Wikipedia, the prediction
  market, the state of bitcoin and ethereum over those hours.
- **Cannot:** see exam cards.
- **Agent:** `watcher-high` · effort high (set by TACTICS 4's pilot, 2026-09-19).

## Lukas — watcher · price itself
- **Looks at:** price, volume, trade count, order book depth, volatility.
- **Cannot:** see exam cards.
- **Agent:** `watcher-high` · effort high (set by TACTICS 4's pilot, 2026-09-19).

## Sofia — canteen chair
- **Does:** collects the notes, runs the discussion. Writes the surviving ideas
  in two forms: a mechanical rule (trigger · direction · exit) and a score
  recipe (which signal is worth how many points, at what score to buy, at what
  score to sell).
- **Cannot:** invent an idea. Every rule rests on at least one watcher note and
  a card number.
- **Agent:** `canteen-chair` · effort high.

## Viktor — skeptic
- **Does:** tries to kill every idea. The questions he asks:
  - Is it coincidence?
  - Doesn't price already say this?
  - Did the whole market move?
  - Does it rest on a single event?
  - Is the same thing present in calm moments too?
- **Red stamp:** can stop a rule by writing his reasoning. An unreasoned
  objection does not count.
- **Cannot:** propose new ideas.
- **Agent:** `skeptic` · effort xhigh.

## Nadia — exam preparer
- **Does:** writes the script that prepares the exam cards. Strips the names and
  dates, hides the price, seals the answer key.
- **Cannot:** read the observation notes or the canteen. So that she does not
  build the exam around the ideas.
- **Agent:** `data-engineer` in **Mode B** — in that mode `notes/` and
  `canteen/` are closed. Nadia is not a separate definition; see "Open item"
  below.

## Hana — exam candidate · on behalf of the team
- **Does:** takes Sofia's score recipe, reads the exam cards, answers.
- **Cannot:** use tools, read files. Does not see the observation notes or the
  canteen; only the recipe.
- **Agent:** `exam-candidate` · effort medium, with recipe.

## Tomás — fresh eyes
- **Does:** sits the exam without seeing any observation note, the canteen, or
  the recipe. Answers on his own common sense alone.
- **Why he exists:** if the team cannot beat Tomás, it learned nothing by
  watching.
- **Cannot:** use tools, read files.
- **Agent:** `exam-candidate` · effort medium, no recipe. Same definition as
  Hana, so model, effort and language are identical — which is what makes the
  comparison fair.

## Derya — reporter
- **Does:** reads the laboratory's English output and tells the user what
  happened, **in Turkish.** Plain first, technical after, then everything left
  open.
- **Cannot:** interpret, conclude, soften, add a number, fill a gap. Writes only
  into `reports/`. Carries no information between agents — a terminal node.
- **Technical terms are never translated:** `funding rate`, `open interest`,
  `taker buy volume`, `walk-forward`, `embargo`, `drawdown`, column names, file
  paths. Translating a term creates ambiguity, and ambiguity is what this
  laboratory is built to avoid.
- **Agent:** `reporter` · effort high.

## Greta — judge
- **Does:** compares the exam papers against the answer key, computes the chance
  line, applies Sofia's mechanical rules in the exam and the money test. Gives
  every run a number from the fingerprint of its input and locks the record.
- **Greta is a script, not an AI.** A judge has no opinions. Mateo writes the
  script.

## Jurors — the answer to an open question

- **Does:** answers one open question, alone, in a fresh context, without seeing
  any other juror's answer. Cites the file and line the answer rests on,
  writes the strongest case against itself, and gives a confidence of 1–5.
- **Cannot:** decide a trading rule, a threshold or a score; change a rule in
  `RULES.md`; see exam cards; see another juror's answer.
- **How many:** at least three per question (RULES 33).
- **Agent:** `juror` · effort high.

## The referee — mini on purpose

- **Does:** reads the jurors' answers and **ratifies or refuses.** Checks count,
  independence, grounding, the split, the reasoned objection and scope.
- **Cannot:** answer the question itself, even when every juror is wrong. Then
  it refuses and says why.
- **Model:** small (`haiku`) — the one role that is not `opus`, deliberately.
  A referee that reasons its way to a preference stops being a referee.
- **Agent:** `referee` · effort medium.

---

## Coordinator
- **Does:** writes the instructions, runs the agents, examines the results,
  explains them to the user.
- **Cannot:** interpret a card, write a rule, or sit the exam with their own
  hands. Cannot carry findings from the old project to the agents.
  **Cannot answer an open question alone** — that goes to three jurors and the
  referee (RULES 33–35).

---

# Agent definitions

Eight definitions in `.claude/agents/` cover the AI roles. Greta stays a
script.

| definition | roles it covers | effort |
|---|---|---|
| `data-engineer` | Mateo + Nadia (Mode B) + Greta's script (Mode C) | high |
| `watcher` | the medium-effort arm; kept for a future pilot, not used in the observation run | medium |
| `watcher-high` | Ingrid · Kenji · Amara · Lukas (field of view from the instruction) | high |
| `canteen-chair` | Sofia | high |
| `skeptic` | Viktor | xhigh |
| `exam-candidate` | Hana · Tomás | medium |
| `reporter` | Derya | high |
| `juror` | one open question, at least three run per question | high |
| `referee` | ratifies or refuses, **model `haiku`** | medium |

Structural decisions:
- All eight carry `omitClaudeMd: true` — an agent never sees a parent `CLAUDE.md`
  and reads its wall text from its own definition.
- **No definition has the `Skill` tool.** No agent can call a skill and walk
  around the wall.
- **`Bash` exists only in `data-engineer`.** The command-line hole that RULES 5
  admits is squeezed into a single agent.
- No definition has persistent `memory`. A watcher accumulating opinions between
  runs would break the blind exam.
- `exam-candidate` cannot be given zero tools (the agent fails to launch), so it
  has the one tool that cannot read a file: `TodoWrite`, plus `maxTurns: 1`.

**Open item:** Nadia is not a separate definition. Her work sits in
`data-engineer` Mode B, where `notes/` and `canteen/` are closed and each run
starts in a fresh context, so that run never sees the ideas. To follow the
letter of this file, Nadia should be split out as a seventh definition.
