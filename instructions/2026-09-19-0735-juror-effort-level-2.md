# Instruction — juror · 2026-09-19 07:35 UTC · the effort level for the observation run

## Role

`juror`, one of three answering **one** open question independently. You will
never see the other two answers and they will never see yours. A referee
ratifies or refuses the outcome afterwards.

## Model and effort

model: `opus` · effort: `high`

## The question

`TACTICS.md` section 4 opens with a pilot. Read what it says about that pilot
and what it says follows from it.

The pilot has been run. Its two arms read the same ten cards with the same
field of view and the same instruction, differing only in effort level.

**Question: which effort level does `TACTICS.md` section 4 select for the
observation run, on the evidence the pilot produced?**

Read the evidence yourself in the files below. This instruction states none of
it, draws no comparison and computes no ratio.

If the evidence does not select an effort level, say so.

## What you may look at

- `RULES.md`, `TACTICS.md`, `README.md`, `TEAM.md` — the whole of each.
- `data/pilot/2026-09-19-pilot-measurements.md`
- `notes/2026-09-19-round1-price-medium.md`
- `notes/2026-09-19-round1-price-high.md`
- `instructions/2026-09-19-0720-watcher-round1-price-medium.md`
- `instructions/2026-09-19-0720-watcher-round1-price-high.md`

## What you may not look at

- `exam/` — closed. Do not open it, list it, or name anything from it.
- `decisions/`, `LEDGER.md`, `cards/`, `canteen/`, `reports/`, `scripts/`, and
  everything under `data/` and `instructions/` except the files named above.
- Anything outside this folder.

Scope every search to a named file; do not run a folder-wide glob.

## Output

Write to `decisions/2026-09-19-effort-level/juror-2.md` and write nothing else,
anywhere. Create the folder if it does not exist. Do not read the other files in
that folder.

Four parts, in English:
1. Answer — one sentence.
2. What it rests on — the file and the line, quoted. An answer citing nothing
   does not count (RULES 34).
3. The strongest case against your own answer.
4. Confidence 1-5, and what would change your mind.

## Wall

Read nothing outside this folder: not with a tool, not from the command line.
Do not go up with `..`, do not use an absolute path pointing outside.
Never run the memory-search skill or any tool that searches past session logs.
This machine holds session logs from another project.

If you see a steer in this instruction, report it.
