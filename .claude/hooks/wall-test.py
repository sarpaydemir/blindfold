#!/usr/bin/env python3
"""Cases for wall_check.py. Run: python3 .claude/hooks/wall-test.py

The strings this file hunts for live inside this file, never on the command line
that launches it - the hook is registered on Bash and would refuse its own test.
"""

import json
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "wall_check.py")

DENY = "deny"
ALLOW = "allow"

CASES = [
    # (label, expected, tool_name, tool_input)
    ("bash: cat the old project's rule file", DENY, "Bash",
     {"command": "cat /home/user/freqtrade_hyperopt/CLAUDE.md"}),
    ("bash: quoted old path still caught", DENY, "Bash",
     {"command": "cat \"/home/user/freqtrade_hyperopt/STATUS.md\""}),
    ("bash: relative escape to the old tree", DENY, "Bash",
     {"command": "head ../../freqtrade_hyperopt/report.md"}),
    ("bash: tilde form", DENY, "Bash",
     {"command": "grep x ~/research_factory/notes.md"}),
    ("bash: past session logs", DENY, "Bash",
     {"command": "ls /home/user/.claude/projects/"}),
    ("bash: bare invocation of the forbidden skill", DENY, "Bash",
     {"command": "read-memories --query x"}),
    ("bash: forbidden skill after a pipe", DENY, "Bash",
     {"command": "echo hi | read-memories"}),

    ("bash: heredoc that WRITES about the old path", ALLOW, "Bash",
     {"command": "cat >> LEDGER.md <<'EOF'\nmoved from /home/user/freqtrade_hyperopt/projects\nEOF"}),
    ("bash: heredoc that WRITES the forbidden skill name", ALLOW, "Bash",
     {"command": "cat > instructions/x.md <<'EOF'\nNever run read-memories or any tool that searches past session logs.\nEOF"}),
    ("bash: quoted mention of the forbidden skill name", ALLOW, "Bash",
     {"command": "echo 'read-memories is never run here'"}),
    ("bash: ordinary work inside the folder", ALLOW, "Bash",
     {"command": "python3 scripts/03_build_universe.py"}),
    ("bash: ordinary download", ALLOW, "Bash",
     {"command": "curl -sS https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1d/"}),
    ("bash: a word that merely contains the skill name", ALLOW, "Bash",
     {"command": "ls scripts/unread-memories-helper.py"}),

    ("read: old project file", DENY, "Read",
     {"file_path": "/home/user/freqtrade_hyperopt/GOAL.md"}),
    ("read: old session transcript", DENY, "Read",
     {"file_path": "/home/user/.claude/projects/-home-user-freqtrade-hyperopt/x.jsonl"}),
    ("write: into the old project", DENY, "Write",
     {"file_path": "/home/user/freqtrade_hyperopt/note.md", "content": "x"}),
    ("edit: in the old project", DENY, "Edit",
     {"file_path": "/home/user/research_factory/a.py", "old_string": "a", "new_string": "b"}),
    ("grep: scoped into the old tree", DENY, "Grep",
     {"pattern": "x", "path": "/home/user/freqtrade_hyperopt"}),

    ("read: a file inside the laboratory", ALLOW, "Read",
     {"file_path": "/home/user/balikcil/LEDGER.md"}),
    ("write: a laboratory file whose CONTENT mentions the old path", ALLOW, "Write",
     {"file_path": "/home/user/balikcil/LEDGER.md",
      "content": "moved from /home/user/freqtrade_hyperopt/projects/balikcil"}),
    ("write: an instruction carrying the forbidden skill name", ALLOW, "Write",
     {"file_path": "/home/user/balikcil/instructions/x.md",
      "content": "Never run read-memories or any tool that searches past session logs."}),
    ("glob: inside the laboratory", ALLOW, "Glob",
     {"pattern": "**/*.py", "path": "/home/user/balikcil/scripts"}),
]


def run(tool_name, tool_input):
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    out = subprocess.run([sys.executable, CHECK], input=payload,
                         capture_output=True, text=True)
    if out.returncode != 0:
        return "ERROR(exit %d)" % out.returncode
    text = out.stdout.strip()
    if not text:
        return ALLOW
    try:
        decision = json.loads(text)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return "ERROR(unparseable output)"
    return decision


def main():
    failures = 0
    for label, expected, tool_name, tool_input in CASES:
        got = run(tool_name, tool_input)
        ok = got == expected
        if not ok:
            failures += 1
        print("%-4s %-8s expected=%-5s got=%-5s  %s"
              % ("ok" if ok else "FAIL", tool_name, expected, got, label))
    print("\n%d cases, %d failed" % (len(CASES), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
