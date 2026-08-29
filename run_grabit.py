"""Launcher script.

This is both the way to run GrabIt from source (`python run_grabit.py`) and the
entry point PyInstaller bundles.
"""

import sys

from grabit.main import main

if __name__ == "__main__":
    sys.exit(main())
