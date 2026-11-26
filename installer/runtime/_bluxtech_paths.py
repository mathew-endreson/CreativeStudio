"""Give the embedded runtime a normal Python's sys.path.

The embeddable Python ships a python312._pth file, and that file puts the interpreter in isolated mode (-I, which
implies -P): sys.path then holds neither the script's folder (python script.py) nor the current folder (python -m
package). We want the isolation (nothing from another Python on the customer's PC leaks in), but the engine starts
with `python -m bluxtech_engine` from <resources>/engine, and the bluxstudio-skill scripts import their siblings
(batch.py -> transcribe, map_beats; asset_lib -> gpt_assets), so put those two entries back.

Loaded at every start by bluxtech_paths.pth in Lib/site-packages (site runs `import` lines in .pth files).
"""
import os
import sys


def _script_entry():
    """The folder a normal Python would prepend: the script's, or the current one for -m / -c."""
    argv = list(getattr(sys, "orig_argv", None) or [])[1:]  # the real command line, minus python.exe
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-m", "-c"):
            return os.getcwd()
        if a in ("-X", "-W", "--check-hash-based-pycs"):
            i += 2
            continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        if a == "-":
            return os.getcwd()  # stdin
        return os.path.dirname(os.path.abspath(a))
    return os.getcwd()  # interactive


def _restore():
    try:
        entry = _script_entry()
    except Exception:  # never break the interpreter over this
        return
    if entry and entry not in sys.path:
        sys.path.insert(0, entry)


_restore()
