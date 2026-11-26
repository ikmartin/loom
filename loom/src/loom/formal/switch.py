"""Whether formalization is on for a quilt on this machine: one file a quilt under loom's data folder, keyed by where the quilt lies and holding which folder lies there, and never in the quilt, so that opening a co-author's quilt, a copy of one's own, or a quilt cloned where a deleted one lay runs nothing until the person turns it on there."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

#: The folder of `machine.data_dir` that holds one file for each quilt formalization is on for.
FOLDER = "formal"


def switch_file(root: Path) -> Path:
    """Where the switch of the quilt at `root` is kept: `formal/<key>.json` in loom's data folder, keyed by the quilt's resolved path."""
    from loom.machine import data_dir

    key = hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:24]
    return data_dir() / FOLDER / f"{key}.json"


def is_on(root: Path) -> bool:
    """Whether the person turned formalization on for the quilt at `root` on this machine; a file naming another place or another folder at this one, or one that does not read, is off."""
    try:
        data = json.loads(switch_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(data, dict)
        and data.get("root") == str(Path(root).resolve())
        and data.get("folder") == _folder(root)
        and data.get("on") is True
    )


def _folder(root: Path) -> list[int] | None:
    """Which folder lies at `root`: its device and inode, which a folder made anew at the same place does not share."""
    try:
        st = os.stat(root)
    except OSError:
        return None
    return [st.st_dev, st.st_ino]


def turn_on(root: Path) -> None:
    """Keep the switch on for the quilt at `root`, readable by this user alone. The person's act alone: callers refuse an agent first."""
    p = switch_file(root)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(
            json.dumps({"root": str(Path(root).resolve()), "folder": _folder(root), "on": True, "at": at}, indent=1)
            + "\n"
        )


def turn_off(root: Path) -> None:
    """Turn formalization off for the quilt at `root` on this machine; what it installed stays."""
    switch_file(root).unlink(missing_ok=True)
