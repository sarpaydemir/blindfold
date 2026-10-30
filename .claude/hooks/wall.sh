#!/usr/bin/env bash
# Balıkçıl · PreToolUse hook · registered on Bash, Read, Write, Edit, Glob, Grep.
#
# Thin wrapper on purpose. All of the logic, and the reasoning behind every
# refusal, lives in wall_check.py next to this file, so that it can be run
# directly against its cases:  python3 .claude/hooks/wall-test.py
#
# This script never exits non-zero. A wall that breaks a turn is worse than the
# hole it guards, and it is not the only control (RULES 1, RULES 5).
set +e
python3 "$(dirname "${BASH_SOURCE[0]}")/wall_check.py"
exit 0
