"""Resolve bundled assets for source installs and one-file binaries."""

from __future__ import annotations

import sys
from pathlib import Path


def web_dir() -> Path:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = Path(meipass)
        candidates.extend(
            [
                root / "portway" / "web",
                root / "web",
            ]
        )
    here = Path(__file__).resolve().parent
    candidates.append(here / "web")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "web")
    for path in candidates:
        if (path / "index.html").is_file():
            return path
    return here / "web"
