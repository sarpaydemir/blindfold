---
name: wall-audit
description: Audits Balıkçıl's wall — leaks from the old project, steers in instructions, access to exam cards, stale paths in the settings file. Use after an agent run, before an exam, and whenever the user asks whether anything leaked.
allowed-tools: Bash, Read, Glob, Grep
---

## Settings file

!`cat "${CLAUDE_PROJECT_DIR}/.claude/settings.json"`

## Where the project sits

!`pwd`

## Agent definitions and their wall fields

!`for f in "${CLAUDE_PROJECT_DIR}"/.claude/agents/*.md; do printf '%s: ' "$(basename "$f")"; grep -c 'omitClaudeMd: true' "$f" | tr -d '\n'; printf ' omitClaudeMd · tools: '; grep -m1 '^tools:' "$f" | cut -c8-; done 2>/dev/null`

## Installed plugins

!`claude plugin list 2>&1 | head -20`

## Instruction copies

!`ls -1 "${CLAUDE_PROJECT_DIR}/instructions/" 2>/dev/null | grep -v gitkeep | wc -l` instruction records

---

# The audit — work through it in order and report every item

This audit **changes no file.** It only looks and reports.

Mark each item "passed" or **"failed"**. If any item failed, say so plainly to
the user and write it into `LEDGER.md`.

## 1 · Do the settings paths actually point at this folder

Compare the `pwd` above against the paths in the settings file:

- Does `autoMemoryDirectory` point inside this folder? If not, **memory is being
  written outside the wall** — failed.
- Does `claudeMdExcludes` point at a file that actually exists?
- Are the `permissions.deny` paths still correct?

If the project has moved, all of these go stale. **A stale path is the wall
quietly opening:** it raises no error, it simply stops working.

## 2 · Is there a steer in the instructions (RULES 3)

Read every file under `instructions/` with this in mind:

- Has the agent been told **what it will find**?
- Is there a sentence like "pay attention to X", "usually it goes like this",
  "check whether X is there"?
- Does the instruction carry a threshold, number or duration the coordinator
  invented?
- Are the model and effort stated explicitly (RULES 24)?
- Is the instruction in English? Only `reporter` produces Turkish output, and
  its instruction is still English.

Report every sentence you find **by quoting it.** A leak is shown, not
summarised.

### The channel every agent is handed: commit subjects

Every agent starts with the repository's most recent commit subjects in its
context, and a role with `Bash` can read the whole history. **A commit subject is
therefore a message to every role at once**, including roles that may not open
the folder it describes. On 2026-10-01 a blind reviewer read the verdict it was
meant to reach blind from a subject the coordinator wrote.

```
git log --format='%h %s' -30
```

Every subject must be neutral: `ledger: <timestamp>`, `work: <timestamp>`,
`auto: working tree at <timestamp>`. **A subject carrying a verdict, a count, a
coin name, a finding or a "solved / not solved" is failed** — quote it. History
already pushed is not rewritten (RULES 30); the audit records it and checks that
the most recent subjects, the ones the next agent will be handed, are neutral.

## 3 · Is there any trace of the old project (RULES 1)

Search under `instructions/`, `notes/`, `canteen/`, `scripts/`, `reports/`:

```
grep -ril -e 'freqtrade' -e 'hyperopt' -e 'research_factory' -e 'user_data' \
  instructions notes canteen scripts reports
```

And for paths pointing outside this folder:

```
grep -rn -e '\.\./\.\.' -e '/home/user/freqtrade' instructions notes canteen scripts
```

The old project's name appearing in `LEDGER.md` and `.claude/settings.json` is
normal (the move record and the deny list). Appearing anywhere else is
**failed.**

## 4 · Is the exam closed (RULES 9, 10)

- Under `notes/` and `canteen/`, is there an exam coin's name, an exam card
  number, or a line from the answer key?
- In the `watcher`, `canteen-chair` and `skeptic` definitions, is `exam/`
  explicitly closed?
- In `exam-candidate`, are `notes/` and `canteen/` closed? Is the `tools:` list
  narrow enough that it cannot read a file?
- Was the answer key's fingerprint written into `LEDGER.md` **before** the exam?
  If it was written afterwards, that exam is void.

## 5 · Are plugin skills punching through the wall

Look at the skill list of the installed plugins. Ask: **is there a skill that
reads past session logs, transcripts, or other projects on this machine?**

- **`read-memories`**, inside `duckdb-skills`, is such a skill: it searches past
  session logs. This machine holds session logs from the old project.
  **This skill is never run in Balıkçıl** — not by the coordinator, not by an
  agent.
- No agent definition has `Skill` in its `tools:` list — so no agent can call a
  skill and walk around the wall. If a definition has gained `Skill`, that is
  **failed.**
- `quant-analyst` and `risk-manager` arrived with a plugin and are **not** part
  of the team. The team is in `TEAM.md`. Running them is **failed.**

## 6 · The command-line hole (RULES 5)

Settings cannot block file reads via `Bash`. So:

- Is `data-engineer` still the only agent with `Bash`? If another has it,
  **failed.**
- In the commands under `instructions/`, is there anything whose scope escapes
  the folder (`..`, an absolute path, a `find` at the root)?
- Has a `PreToolUse` hook been installed to close this hole? If not, **write it
  down as an open item at every audit** — an unclosed hole must not be
  forgotten.

## 7 · The outbound hole — the half the wall was never written for

RULES 1 and 5 are written entirely about reading **into** this folder. Grep the
whole of `RULES.md` for `network`, `internet`, `outside`, `send`, `external`,
`api`. **If that search still returns nothing, the outbound half of the wall is
still unwritten, and that is an open item to be reported at every audit** — not
a failure, but a hole that must not be forgotten.

### Who can physically reach outside

Read the `tools:` line of every definition under `.claude/agents/`:

- Which ones carry `Bash` or `WebFetch`? Those are the only roles that can make
  a network call at all. Every other role is contained by its tool list, which
  is mechanism, not promise.
- If a role that previously could not reach the network has gained either tool,
  that is **failed** unless a recorded decision says otherwise.

### Is `exam/` closed by mechanism or only by instruction

For each role that can reach the network, ask how `exam/` is held shut. If the
answer is "the instruction says so", write that down as the weakest link **by
name**. An instruction is not a mechanism, and instructions in this laboratory
have leaked repeatedly.

### Is there a live credential on disk

- Is there a `.env` or similar? Is it in `.gitignore`? Verify with
  `git check-ignore -v`, not by eye.
- Has it ever been committed? `git log --all --oneline -- .env` — anything but
  empty output is **failed**, and the credential must be treated as exposed and
  rotated.
- **Is a credential present that nothing currently uses?** An unused credential
  next to a role that has `Bash` is capability with no benefit. Name it.

### Scan the tree

`scripts/23_manifest_and_scan.py` scans for an exact key, fragments of it, and
credential *shapes*. Run the shape scan across the working tree:

```
grep -rlE 'sk-or-|sk-ant-|ghp_|github_pat_' --exclude-dir=.git --exclude-dir=data .
```

Expect hits in files that *define* these patterns — this skill, `CLAUDE.md`, the
`ledger` skill, the scanner itself. **A hit anywhere else is failed.** A
credential-shaped literal is a finding even when it is a deliberately fake test
fixture: GitHub push protection matches the shape, and a blocked push is a
stalled laboratory.

**Never print a credential, or any fragment of one, in the report.** To compare
two values, compare their SHA-256 digests.

## 8 · Report

To the user, in this order, plainly:

1. How many items passed, how many failed.
2. Each failed item: what, where, with the quote.
3. Open holes that remain unclosed, by name.
4. If nothing was found: **where you looked** (RULES 20 — before saying "none",
   write down where you looked).

Then record it with `/ledger`.
