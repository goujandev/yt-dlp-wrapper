"""Locating bundled asset files, both from source and inside the frozen exe."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ICON = "GrabIt.ico"
WINDOW_ICON = "icon.png"


def _search_dirs() -> list[Path]:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # PyInstaller unpacks datas here; assets keep their subfolder.
        return [Path(meipass) / "assets", Path(meipass)]

    project_root = Path(__file__).resolve().parent.parent
    return [project_root / "assets", project_root]


def resource_path(name: str) -> str | None:
    """Absolute path to a bundled asset, or None if it is not there."""
    for directory in _search_dirs():
        candidate = directory / name
        if candidate.is_file():
            return str(candidate)
    return None
