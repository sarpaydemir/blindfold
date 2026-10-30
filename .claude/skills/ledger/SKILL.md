---
name: ledger
description: Appends a new entry to Balıkçıl's LEDGER.md. Only appends — never deletes or changes a line. Reads the clock from the system instead of guessing it. Use when something is set up, a decision is taken, a run completes, a fingerprint is sealed, or a rule changes.
allowed-tools: Bash, Read
argument-hint: "[subject of the entry]"
---

## Current time (read from the system)

!`date -u '+%Y-%m-%d %H:%M UTC'`

## Tail of the ledger

!`tail -n 12 "${CLAUDE_PROJECT_DIR}/LEDGER.md"`

## Length before this entry

!`wc -l < "${CLAUDE_PROJECT_DIR}/LEDGER.md"` lines

## The task

Subject: **$ARGUMENTS**

A single entry is **appended** to `LEDGER.md`. The rule: *append-only, no line
is ever deleted.*

1. **Use the time printed above.** Do not guess it, do not recall it, do not take
   it from anywhere else (RULES 23). Whatever is printed above is the time.
2. **Write the entry in English.** The laboratory's working language is English.
   Entries before 2026-09-18 are in Turkish; they are history and are not
   touched.
3. Write the entry in this shape:

   ```
   `YYYY-MM-DD HH:MM UTC` · **short label** · what happened. What it rests on,
   which file, the fingerprint if there is one. Never write an unmeasured
   number; if it is an estimate write "estimate" next to it (RULES 19).
   ```

4. **Append to the end of the file only.** Touch no existing line. Append with
   `>>`; do not rewrite the whole file with the `Write` tool — rewriting risks
   losing old lines.
5. After appending, verify the line count **grew.** If it shrank or stayed the
   same, stop and tell the user.
6. **Commit and push.** Stage the changed files, commit with a **contentless**
   one-line message — `ledger: <YYYY-MM-DD HH:MM UTC>` and nothing else — and
   push to `origin main`.

   **The message must not name the entry's label or summarise what happened.**
   The harness injects recent commit subjects into every subagent's launch
   context, including agents for whom `LEDGER.md` is closed and including exam
   candidates. A descriptive commit subject is therefore a hole straight through
   the wall. Found on 2026-09-19 by a juror who reported receiving commit
   subjects referencing ledger content it was not permitted to read. Records that are pushed
   are records that survive (RULES 29–30). Every ledger entry is one commit, so
   the git history and the ledger tell the same story.

   If the push fails, say so — a failed push is a technical failure and a
   technical failure is not a result (RULES 21). Do not carry on as if the
   record were safe.

   When printing git output, never print the remote URL: the token is embedded
   in it. Filter it:
   `git push origin main 2>&1 | sed -E 's/github_pat_[A-Za-z0-9_]+/***/g'`

## What must go into an entry

- If a **decision** was taken: who took it (the user or the coordinator) and
  which rule it supersedes.
- If a **run** happened: the run number (the fingerprint of the input) and the
  output file (RULES 29).
- If something was **sealed**: the fingerprint of the answer key (RULES 9).
- If a **rule changed**: a note that the user was asked first.
- If there is an **estimate**: the word "estimate" next to it.
- If something **could not be measured**: by name. "Could not be measured" never
  turns into "no problem" (RULES 22).
