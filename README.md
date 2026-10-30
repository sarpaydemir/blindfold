# blindfold

A multi-agent lab that keeps its agents blind: hook-enforced information walls, blind exams, three independent jurors and a referee, and a ledger that reports its own leaks.

This is the method layer of a private lab I ran in Claude Code from 2026-09-13 to 2026-10-02. Its code name was Balıkçıl, Turkish for heron: a bird that stands still for hours, watches, then strikes once. The lab had eleven named roles and one goal, a scoring rule for crypto futures found by watching first and tested blind. It never struck. Observation produced no directional rule, and the blind exam could not be shown to be blind under the lab's own rules, so it stopped and reported both. What is here is what made those answers trustworthy: the rules, the wall, the agent definitions, the instruments, and their tests.

## Results

- **The observation found nothing, and recorded that plainly.** Four watchers read all 306 cards (153 sharp 24-hour moves, 153 calm stretches, 10 coins) in separate contexts: 36 runs, 8,035,146 tokens. The skeptic examined 90 items and stopped 52 directional ideas with reasoned red stamps. The canteen chair's book: *"Directional rules: the list is empty."* The recipe's instruction on every card is *do nothing*. [Observation and the canteen](docs/observation-and-canteen.md)
- **The skeptic found the chance line was too easy before the exam existed.** 296 of 306 cards share a clock hour with another card (495 pairs, a chain of 20, only 10 cards independent), so shuffling cards would have made chance easy to beat. The answer is an engine that collapses events first and shuffles whole events ([`scripts/15_event_collapse.py`](scripts/15_event_collapse.py)).
- **A blind review caught a shuffle that broke events apart.** With the coordinator kept out, one agent fixed and another reviewed. The reviewer showed the first block shuffle mixed events: in 175 of 200 draws an event read answers from more than one source event, and an event-constant answer vector survived 138 of 1,000 permutations where a correct shuffle keeps all 1,000. It rebuilt every output byte for byte and re-verified 60 fingerprints. [Blind exam prep](docs/blind-exam-prep.md)
- **The exam was never built, because it could not be shown to be blind.** Eight fix runs, eight independent reviews and 11 juries (all ratified, including 2–1 splits) left one problem open: review 8 found a sequencing circle and a rule conflict that no fix run could remove. The lab stopped on 2026-10-02 and handed four items to me. The last night: 37 agent runs, 5,961,372 tokens.
- **A cheap outside judge lost to a constant.** Calibrated against an answer key notarised at the provider 66 seconds before the first item call, it scored 73/100 on which watcher wrote a line (25% by chance) and 100/100 on a mechanical count, but 37/100 on the watcher's own 1–5 confidence, against 51/100 for always answering "4". An accept-above-0.9 rule let 4 of 27 errors through, one at confidence 1.00. Cost: $0.0117 for 402 calls. It got no role. [Outside judge](docs/outside-judge-calibration.md)
- **The lab logged its own leaks.** The ledger numbers 30 steers in the coordinator's own instructions, the first 19 all caught by the agents receiving them. Commit subjects turned out to reach every agent, including a blind reviewer that read a verdict from one. An exam coin's name reached a juror-readable file. [Leaks](docs/leaks-the-lab-reported.md)

## Method rules

1. **The wall is enforced by the harness, not by memory.** [`.claude/settings.json`](.claude/settings.json) denies reads of the old project and of past session transcripts, and registers a PreToolUse hook on Bash, Read, Write, Edit, Glob and Grep ([`wall_check.py`](.claude/hooks/wall_check.py)) that refuses paths into the old tree and states its own residual gaps. All nine agent definitions set `omitClaudeMd`, none has the `Skill` tool, none keeps memory between runs, and only the data engineer has `Bash` and `WebFetch`. The exam candidate gets one tool that cannot read a file and one turn.
2. **Agents are told what they may look at, never what to look for** (`RULES.md` 3). Every instruction is saved in full under `instructions/` (`RULES.md` 4), and receiving agents report steers. When the coordinator kept leaking, it was cut out: the pre-exam fix was done and reviewed by agents that never told it how.
3. **Blind exam, three rivals, chance by shuffle.** Exam cards hide the coin, the date and the price; the answer key is sealed by SHA-256 before the exam (`RULES.md` 9–10). A result counts only if it beats a coin flip, a "last 24 hours continues" rule, and an agent who never watched (`RULES.md` 11). The chance line is the best 1% of 1,000 shuffles over events collapsed first (`RULES.md` 12–13), and the engine refuses to compute it from anything it cannot re-derive from the sealed key.
4. **An open question is never answered by one agent.** Three jurors answer in separate contexts, each quoting the file and line it rests on; a deliberately small referee (Haiku) checks count, independence, grounding, the split, reasoned objections and scope, and never answers the question itself (`RULES.md` 33–35). A juror may decide procedure and definition, never a trading rule, a threshold or a score. One full jury is in [`decisions/2026-09-19-effort-level/`](decisions/2026-09-19-effort-level/).
5. **Records are append-only and every run has a number.** The run number is the SHA-256 of the run's inputs; a script refuses to write different content under an existing number (`RULES.md` 29–30). "An unmeasured number is not written down" (`RULES.md` 19), "a technical failure is not a result" (21), and the clock is read, never typed (23).

## Run the tests

Requires [uv](https://docs.astral.sh/uv/). The scripts use the standard library only; Python 3.12 or later (uv installs it).

```sh
uv sync
uv run pytest        # 118 tests: no network, no market data, no API key
uv run ruff check .
python3 .claude/hooks/wall-test.py   # the lab's own 22 wall cases
```

Two tests are marked as expected failures. Both are gaps I found while preparing this copy and left in the code as it ran: the wall hook does not examine a Glob's `pattern`, so an absolute pattern into the old tree is not refused (the `Read()` deny rules remain), and the card reader does not parse the `T` suffix the card writer can print for values of 10¹² and up (no card came near one).

The scripts themselves need data that is not here. `01`, `02`, `05` and `07` download from the public Binance archive (`data.binance.vision`), `08` from public sources (release calendars, Wikipedia page views, Polymarket), and every later script reads their output.

## Layout

| Path | What |
|---|---|
| `RULES.md`, `TACTICS.md`, `TEAM.md` | The 35 rules, the step-by-step method, and the eleven roles with what each cannot do |
| `CLAUDE.md` | The coordinator's session instruction |
| `.claude/settings.json`, `.claude/hooks/` | The wall: deny rules, the PreToolUse hook and its cases, and the Stop hook that commits after every turn |
| `.claude/agents/` | Nine definitions: data engineer, two watcher arms, canteen chair, skeptic, exam candidate, reporter, juror, referee |
| `.claude/skills/` | The lab's own skills: `ledger`, `instruction`, `wall-audit` |
| `.claude/memory/` | Three lessons the coordinator kept: commit subjects are a broadcast, never relay scan-matched words, the user is an observer |
| `scripts/01`–`08`, `lab_archive.py` | Archive index, verified downloads, universe, draw, moments, external sources |
| `scripts/09`–`14`, `lab_cards.py` | Card writer with its Before/After guard, card checks, card order, overlap map |
| `scripts/15`–`18` | Event-collapse engine and chance line, identity audit, blinding, residual diagnostic |
| `decisions/`, `instructions/` | One jury as it ran: three instructions, three answers, the referee's verdict |
| `docs/` | Four write-ups, each naming the ledger entries it comes from |

## Not included, on purpose

- **Data and everything derived from it.** No archive downloads, no cards, no watcher notes, no canteen book, no exam preparation (about 4,500 files), no exam draw. The write-ups publish counts and fingerprints instead.
- **The ledger and the reports.** `LEDGER.md` (6,263 lines) is the source of every number in `docs/`. Its early entries are in Turkish, it records private exchanges with me, and one line names an exam coin; the reporter's accounts were written to me in Turkish.
- **The outside-judge memo, its scripts (`19`–`23`) and artefacts.** They target an undocumented provider endpoint. The calibration is summarised in [docs](docs/outside-judge-calibration.md).
- **The one-off check scripts** (`24`–`35`, `exam_*`). Each verifies one run's claims against files that are not published.
- **Skills taken from other repositories.** Nine MIT-licensed skills from two repositories; sources, pinned commits and licences are in [`.claude/skills/SOURCES.md`](.claude/skills/SOURCES.md).

The files are copied from the original repository without its history. Changes: `scripts/08_external_sources.py` sends a generic User-Agent; the Stop autocommit hook is disabled in `.claude/settings.json`; the Turkish report template in `.claude/agents/reporter.md` is translated; session ids were removed from the memory files; absolute lab paths in prose became relative. `.claude/settings.json`, the hooks and the hook tests keep the lab machine's `/home/user` paths, because those paths are what the wall matches. Instruction titles typed before 2026-09-19 12:45 UTC may be off by up to two hours; the lab recorded that as a breach of its own clock rule and left the copies as sent.

**Before opening this folder in Claude Code**, read `.claude/settings.json`: it turns on the lab's wall hook, and `CLAUDE.md` makes the session the lab's coordinator. The original Stop hook that committed and pushed after every turn is kept as `.claude/hooks/autocommit.sh` for reference but is not enabled here.

## How it was built

I built this by directing AI coding agents under written rules, as in [hunkrisk](https://github.com/sarpaydemir/hunkrisk) and [unfooled](https://github.com/sarpaydemir/unfooled). Here the agents also ran the lab. A Claude Code session acted as coordinator: it wrote the instructions, launched the role agents and kept the ledger, and it could not read a card, write a rule, sit the exam or answer an open question. I watched as an observer and was approached for two things only, a wall leak or a broken rule. The calls the rules left to me, as the ledger records them:

- **2026-09-18:** every role on Opus, separated by effort level; the lab works in English, with one reporter writing to me in Turkish.
- **2026-09-19:** an open question is never answered by one agent: three jurors and a small referee. I brought that rule unprompted; it became `RULES.md` 33–35.
- **2026-09-19:** the coordinator was cut out of the pre-exam fix: one agent solves, another reviews, and neither tells it how.
- **2026-09-19:** the outside judge may be called; after it lost, keep the record and remove the credential.

The lab was built to stop before it fooled itself, and it did.

## License

MIT.
