---
name: exam-names-never-relayed
description: "Never copy an agent's remark about which words a name-scan matched into LEDGER or any file outside exam/ — some exam coin base names are ordinary words."
metadata:
  node_type: memory
  type: feedback
  modified: 2026-10-02T00:20:22.742Z
---

Never relay into `LEDGER.md`, a juror file, or any file outside `exam/` an agent's description of what a coin-name scan matched, or any remark linking a word to "a coin's base name".

**Why:** on 2026-10-02 a juror-question author listed the words its own scan matched; one was an exam coin's base name (short, collides with an English word). The coordinator then copied the remark into `LEDGER.md` (line 6010) — a root document watchers can be pointed at, which TACTICS 1 keeps free of exam names. A word scan cannot clear such names because they are ordinary words; only not writing the linkage prevents the leak.

**How to apply:** when an agent's report mentions scan matches, record only "scan run, passed/failed" in the ledger. Refer to exam coins only by line number. Instructions to anyone writing juror-readable files must forbid listing matched words. Related: [[commit-subjects-are-broadcast]], [[user-is-observer-no-questions]].
