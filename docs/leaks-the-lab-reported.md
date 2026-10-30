# Leaks the lab reported about itself

Source: the private repository's `LEDGER.md`, with the entry time of each item. I asked to be approached for exactly two things: a wall leak or a broken rule (`.claude/memory/user-is-observer-no-questions.md`). This is what came to me, and what the lab changed because of it.

## Steers in the coordinator's own instructions

`RULES.md` 3: an agent is told what it may look at, never what to look for. Every instruction is saved in full under `instructions/` (`RULES.md` 4), and the definitions of the roles that receive instructions (watchers, jurors, skeptic, canteen chair, reporter) tell them to report any steer they see.

The ledger numbers **30 steers**, all in the coordinator's instructions. By 2026-09-20 it records the first nineteen as "every one caught by the receiving agent rather than by the coordinator". Examples: telling a reviewer "look for what is not there", which tells it what it will find; telling a fixer what a later run needs "to count events correctly", which presumes the allegation it was asked to test. The fix was structural, not a promise: the coordinator was cut out of the pre-exam work ([blind exam prep](blind-exam-prep.md)).

## The clock was typed, not read (2026-09-19 10:35)

`RULES.md` 23: the clock is read, not guessed. The data engineer found an instruction that dated an earlier run two hours wrong; the coordinator had typed times by hand. It happened twice more after the fix was recorded. The third time, the time was captured into a variable and interpolated into the instruction, so there is no longer a place to type one. Instruction titles before 2026-09-19 12:45 UTC, including the juror instructions in this repository, may be off by that much; the lab left them as sent rather than overwrite the record.

## A closed folder reached a juror (2026-09-19 06:52)

A juror's search globbed `*.md` across the lab and matched three lines of card boilerplate in `cards/`, which its question had closed. It stopped, did not open the output, re-ran the search on the two files it was allowed, and reported it unasked. The ledger names the cause as the coordinator's: the hook guards the old project, and nothing in the harness enforces a closure inside the lab. `exam/` rested on the same honour-plus-instruction basis, and that stayed recorded as open.

## Commit subjects are a broadcast (2026-09-19 09:46, again 2026-10-01 20:02)

The harness puts recent commit subjects into every subagent's starting context. A juror reported, unasked, that its context carried subjects describing ledger content it was not allowed to read. The `ledger` skill was rewritten: subjects became `ledger: <timestamp>` and nothing else.

On 2026-10-01 the coordinator broke it again: a subject stated a fix run's verdict, and the next blind reviewer saw it before opening any file. Since then the `wall-audit` skill checks the last 30 subjects, the coordinator checks the newest ones before every blind run, data-engineer instructions put `git log` out of reach, and the lesson is a memory file: [`commit-subjects-are-broadcast.md`](../.claude/memory/commit-subjects-are-broadcast.md).

## An exam coin's name in a juror-readable file (2026-10-02 00:09)

An agent writing a juror question listed the words its own name scan matched. One of the matched words was an exam coin's short base name, which is also an ordinary English word. The coordinator then copied the remark into the ledger, a root document watchers can be pointed at. The question file was moved under `exam/`; the ledger line stayed, because the ledger is append-only (`RULES.md` 30) while `TACTICS.md` 1 keeps exam names out of it. That conflict was handed to me rather than settled. The lesson: [`exam-names-never-relayed.md`](../.claude/memory/exam-names-never-relayed.md). A word scan cannot clear a name that is also a word; only not writing the link prevents it.

## The outbound half of the wall (2026-09-19 22:55 onward)

The wall was written entirely about reading **in**. Three things went the other way:


## Why this matters

None of these were found by the coordinator first. They were found by agents whose definitions told them what they could not see and asked them to say when something reached them anyway, and they were recorded rather than smoothed over. The fixes that held were mechanical: a hook, a neutral commit subject, a clock in a variable, a coordinator kept out.
