#!/usr/bin/env bash
# Balıkçıl · Stop hook — commit and push the working tree at the end of every turn.
#
# Why: records that are pushed are records that survive (RULES 29-30). During an
# unattended run nobody is watching, so this must not depend on the model
# remembering to commit.
#
# This hook NEVER fails the turn: every path exits 0. A failed push is reported
# into reports/git-push.log rather than breaking the session (RULES 21 - a
# technical failure is not a result, but it is also not a reason to stop the
# laboratory).

set +e
DIR="${CLAUDE_PROJECT_DIR:-/home/user/balikcil}"
cd "$DIR" 2>/dev/null || exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0

git add -A >/dev/null 2>&1

# Nothing staged means nothing changed this turn.
if git diff --cached --quiet 2>/dev/null; then
  exit 0
fi

TS=$(date -u '+%Y-%m-%d %H:%M UTC')
git -c commit.gpgsign=false commit -q -m "auto: working tree at $TS" >/dev/null 2>&1

mkdir -p reports 2>/dev/null
if git push origin main >/dev/null 2>&1; then
  printf '%s  push ok\n' "$TS" >> reports/git-push.log 2>/dev/null
else
  # Never print the remote URL: the token is embedded in it.
  printf '%s  PUSH FAILED - commit is local only\n' "$TS" >> reports/git-push.log 2>/dev/null
fi

exit 0
