"""The wall: the PreToolUse hook that refuses reads of the old project.

The 22 cases are the lab's own (`.claude/hooks/wall-test.py`), run here through
pytest. The extra tests pin what the hook's docstring promises: it never exits
non-zero, it states its residual gaps, and it only denies, never asks.
"""

import json
import subprocess
import sys

import pytest

from helpers import HOOKS, load

wall_test = load(HOOKS / "wall-test.py", "wall_test")
CHECK = HOOKS / "wall_check.py"


def run_check(stdin_text):
    return subprocess.run([sys.executable, str(CHECK)], input=stdin_text,
                          capture_output=True, text=True)


@pytest.mark.parametrize("label,expected,tool_name,tool_input", wall_test.CASES,
                         ids=[case[0] for case in wall_test.CASES])
def test_lab_case(label, expected, tool_name, tool_input):
    assert wall_test.run(tool_name, tool_input) == expected


def test_lab_case_runner_passes_as_written():
    out = subprocess.run([sys.executable, str(HOOKS / "wall-test.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    assert "22 cases, 0 failed" in out.stdout


def test_a_refusal_is_a_deny_decision_with_its_reason():
    payload = {"tool_name": "Read",
               "tool_input": {"file_path": "/home/user/freqtrade_hyperopt/GOAL.md"}}
    out = run_check(json.dumps(payload))
    assert out.returncode == 0
    decision = json.loads(out.stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"].startswith("Balikcil wall (RULES 1): ")


@pytest.mark.parametrize("stdin_text", ["", "not json", "[]", '{"tool_input": "x"}',
                                        '{"tool_input": {"command": 7}}'])
def test_never_breaks_a_turn(stdin_text):
    # "A broken wall must not break a turn": bad input is allowed through, exit 0.
    out = run_check(stdin_text)
    assert out.returncode == 0
    assert out.stdout == ""


def test_the_shell_wrapper_exits_zero_and_passes_the_decision_through():
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "ls /home/user/.claude/projects/"}})
    out = subprocess.run(["bash", str(HOOKS / "wall.sh")], input=payload,
                         capture_output=True, text=True)
    assert out.returncode == 0
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_the_documented_residual_gap_is_still_there():
    # wall_check.py states this hole in its docstring rather than hiding it:
    # without a leading slash the old project's name is not matched.
    assert wall_test.run(
        "Bash", {"command": "cd /home/user && cat freqtrade_hyperopt/CLAUDE.md"}) == "allow"


def test_an_unquoted_mention_of_the_forbidden_skill_is_refused():
    # Only quoted spans and heredoc bodies count as mentions; a bare word is an
    # invocation as far as the hook can tell.
    assert wall_test.run("Bash", {"command": "echo read-memories"}) == "deny"


@pytest.mark.xfail(strict=True, reason=(
    "Found while preparing this copy: the hook examines file_path/path keys only, "
    "so a Glob whose *pattern* is an absolute path into the old tree is not refused. "
    "The settings.json Read() deny rules are the control that remains."))
def test_a_glob_pattern_into_the_old_tree_is_refused():
    assert wall_test.run(
        "Glob", {"pattern": "/home/user/freqtrade_hyperopt/**/*.md"}) == "deny"
