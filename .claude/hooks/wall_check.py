#!/usr/bin/env python3
"""Balikcil wall check - the body of the PreToolUse hook.

Reads a PreToolUse payload on stdin. Prints a deny decision and exits 0 when the
call reaches for the old project or for past session logs; prints nothing
otherwise. Never exits non-zero: a broken wall must not break a turn.

Registered on Bash, Read, Write, Edit, Glob and Grep. Before 2026-09-18 21:xx
UTC it guarded Bash alone, which meant the same forbidden path went through
untouched via the Read tool.

Two different questions are asked, because reading a path and writing about a
path are not the same act:

  * A PATH reference (/freqtrade_hyperopt, /research_factory, /.claude/projects)
    is matched against the command with HEREDOC BODIES REMOVED. Text on its way
    into a file is not a read. Quoted spans are kept, because quoting a path is
    an ordinary way to read it and stripping quotes would open the door.

  * The forbidden TOOL NAME is matched against the command with heredoc bodies
    AND quoted spans removed, so that it matches an invocation and not a mention.
    This is the 21:01 UTC failure: the instruction skill's own skeleton requires
    every instruction to carry a sentence forbidding that tool, so the name
    appears inside the text of every instruction the laboratory writes.

For the file tools only the path arguments are examined. Their content is not
examined at all, which is the same distinction stated the other way round.

Residual gaps, stated rather than hidden:
  * `cd /home/user && cat freqtrade_hyperopt/FILE` still slips through - the name
    carries no leading slash there.
  * An unterminated heredoc swallows the rest of the command for path matching.
  * This is defence in depth, never the only control. The others are the agent
    definitions, the Read() deny rules in settings.json, and the fact that only
    data-engineer has Bash.
"""

import json
import re
import sys

FORBIDDEN_PATHS = (
    ("/freqtrade_hyperopt", "the old project's tree is closed"),
    ("/research_factory", "the old project's tree is closed"),
    ("/.claude/projects", "past session logs are closed - this machine holds the old project's transcripts"),
)

FORBIDDEN_TOOL = "read-memories"

PATH_KEYS = ("file_path", "path", "notebook_path", "filePath")

HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
QUOTED_SPAN = re.compile(r"'[^']*'|\"[^\"]*\"")
TOOL_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(FORBIDDEN_TOOL) + r"(?![A-Za-z0-9_-])")


def strip_heredoc_bodies(command):
    """Drop the body of every heredoc, keeping the line that opens it."""
    kept = []
    terminator = None
    for line in command.split("\n"):
        if terminator is None:
            kept.append(line)
            match = HEREDOC_START.search(line)
            if match:
                terminator = match.group(2)
        elif line.strip() == terminator:
            terminator = None
    return "\n".join(kept)


def deny(reason):
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Balikcil wall (RULES 1): " + reason + ".",
        }
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.exit(0)


def check_command(command):
    for_paths = strip_heredoc_bodies(command)
    for needle, reason in FORBIDDEN_PATHS:
        if needle in for_paths:
            deny(reason)
    for_tool = QUOTED_SPAN.sub(" ", for_paths)
    if TOOL_TOKEN.search(for_tool):
        deny("that skill searches past session logs and is never run in this laboratory")


def check_paths(tool_input):
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if not isinstance(value, str):
            continue
        for needle, reason in FORBIDDEN_PATHS:
            if needle in value:
                deny(reason)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if isinstance(command, str) and command:
        check_command(command)
    check_paths(tool_input)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
