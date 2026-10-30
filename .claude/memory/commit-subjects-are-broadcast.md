---
name: commit-subjects-are-broadcast
description: "Every agent sees recent git commit subjects in its starting context; subjects must be neutral timestamps, never verdicts or findings."
metadata:
  node_type: memory
  type: feedback
  modified: 2026-10-02T00:20:18.242Z
---

Commit subjects in Balıkçıl must be neutral: `ledger: <timestamp>`, `work: <timestamp>`. Never a verdict, count, coin name or "solved / not solved".

**Why:** every subagent starts with the repository's most recent commit subjects in its context. On 2026-10-01 a blind reviewer read the verdict it was meant to reach blind from a subject the coordinator wrote ("R-04 not solved…"). A commit subject is a broadcast to every role, including roles closed to the folder it describes.

**How to apply:** before launching any blind run (reviewer, juror, watcher), check `git log --format='%s' -5` is neutral. Data-engineer instructions also put `git log`/`git show` outside the reading list. The `wall-audit` skill §2 now checks this. Related: [[exam-names-never-relayed]].
