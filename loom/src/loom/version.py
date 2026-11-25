"""Version constants; the single place both the package and the manifest read them from."""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0.dev0"


def code_stamp() -> tuple[int, int]:
    """loom's Python as it stands on disk: how many modules, and the newest one's mtime, which an edit, a merge or an install moves."""
    times = [p.stat().st_mtime_ns for p in Path(__file__).parent.rglob("*.py")]
    return len(times), max(times, default=0)
