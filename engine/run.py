"""Start the engine from any working directory (what .claude/launch.json and dev.ps1 use):

    python bluxtech-studio/engine/run.py --no-auth --open
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bluxtech_engine.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
