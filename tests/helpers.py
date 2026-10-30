"""Load the lab's scripts and hooks by file name.

The scripts are numbered (`15_event_collapse.py`), so they cannot be imported by
name. They load each other with importlib, and so do the tests. Loading a script
runs no pipeline: every script keeps its work behind `if __name__ == "__main__"`.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / ".claude" / "hooks"

# The scripts import lab_archive and lab_cards from their own folder.
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_script(filename):
    return load(SCRIPTS / filename, "script_" + filename[:-3])
