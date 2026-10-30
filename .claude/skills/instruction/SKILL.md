---
name: instruction
description: Writes an instruction for a Balıkçıl agent, runs it through a leak check, saves the full copy under instructions/, then launches the agent. Use whenever a watcher, canteen chair, skeptic, data engineer, exam candidate or reporter is to be run.
allowed-tools: Bash, Read, Write, Glob, Grep
argument-hint: "[agent name] [task]"
---

## Available agents

!`ls -1 "${CLAUDE_PROJECT_DIR}/.claude/agents/" 2>/dev/null | sed 's/\.md$//'`

## Instructions written so far

!`ls -1 "${CLAUDE_PROJECT_DIR}/instructions/" 2>/dev/null | grep -v '^\.gitkeep$' | tail -n 15`

## Time

!`date -u '+%Y-%m-%d %H:%M UTC'`

## The task

**$ARGUMENTS**

Before an agent runs, an instruction is written and **its full copy is kept.**
The user can check for leaks at any time (RULES 4).

### 1 · Write the instruction — in English

The laboratory runs in English. Instructions go to English agents, so the
instruction is written in English too. `reporter` is no exception: its
instruction is English as well, and it states that its output must be Turkish.

Use this skeleton:

```
# Instruction — <agent> · <YYYY-MM-DD HH:MM UTC> · <task name>

## Role
<which role this run is: e.g. "watcher · field of view: price itself",
"data-engineer · Mode B (blind exam cards)". Do not repeat what the agent
definition already says.>

## Model and effort
model: <opus> · effort: <low/medium/high/xhigh/max>
Reason: <why this effort level>

## What you may look at
<file paths and fields only. NO result, NO prediction, NO threshold, NO
"pay attention to X" sentence.>

## What you may not look at
<closed folders — if exam/ is closed, say so explicitly>

## Output
<which file, in what format. English — unless this is reporter.>

## Wall
Read nothing outside this folder: not with a tool, not from the command line.
Do not go up with `..`, do not use an absolute path pointing outside.
Never run `read-memories` or any tool that searches past session logs.
```

### 2 · Leak check — before launching

Read the instruction you wrote again, with this in mind:

- **Is there a result in it?** Has the agent been told what it will find? If so,
  delete it (RULES 3).
- **Is there a steer?** "Pay attention to X", "usually it goes like this", "check
  whether X is there" — all steers, all deleted.
- **Is there a threshold?** If the instruction carries a number you invented,
  delete it or write where it came from.
- **Is there anything from the old project?** No finding, number, file name or
  opinion from another laboratory belongs in an instruction.
- **Are the model and effort stated explicitly?** (RULES 24)
- **Is the exam closed?** `exam/` must be closed for the watcher, the canteen
  chair and the skeptic. `notes/` and `canteen/` must be closed for the exam
  candidate.
- **Does the exam candidate get anything beyond the recipe?** The candidate with
  no recipe (Tomás) sees no hint of method; the candidate with a recipe (Hana)
  sees only the frozen recipe. Their **model, effort and language must be
  identical** — if one sits the exam in English and the other in Turkish, the
  comparison is broken. Language is an exam condition too.
- **Is the instruction in English?** A Turkish instruction contradicts the
  agent's working language. The only Turkish output comes from `reporter`, and
  its instruction is still English.

### 3 · Save the copy

Write the **full text** of the instruction, exactly as sent to the agent, to:

```
instructions/<YYYY-MM-DD-HHMM>-<agent>-<task-name>.md
```

Not a summary — **the full copy.** The text sent to the agent and the text saved
must be the same.

### 4 · Launch

Run the agent with the `Agent` tool, passing the agent's name as
`subagent_type`. Model and effort come from the agent definition; if they differ
from what you wrote in the instruction, fix the definition, not the instruction.

Start work that will take longer than 10 minutes in a way that survives the
session closing (RULES 26).

### 5 · Afterwards

- Measure the tokens spent on the first 10 cards, write the estimate for the
  full run into `LEDGER.md`, and tell the user in **a single sentence** before
  starting (RULES 25).
- If the agent's report says "I saw a steer in the instruction", **stop** and
  tell the user.
- Record it with `/ledger`.
