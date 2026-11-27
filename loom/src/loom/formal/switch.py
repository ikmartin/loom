"""Whether formalization is on for a quilt on this machine: one file a quilt under loom's data folder, keyed by where the quilt lies and holding which folder lies there, and never in the quilt, so that opening a co-author's quilt, a copy of one's own, or a quilt cloned where a deleted one lay runs nothing until the person turns it on there. Beside it, which state of the quilt's Lean loom last checked on its own (`again`), and when loom last checked it and what came of it (`loom doctor`)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loom import own
from loom.machine import data_dir

#: The folder of `machine.data_dir` that holds one file for each quilt formalization is on for.
FOLDER = "formal"


def switch_file(root: Path) -> Path:
    """Where the switch of the quilt at `root` is kept: `formal/<key>.json` in loom's data folder, keyed by the quilt's resolved path."""

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
    with own.open(p, "w", encoding="utf-8", root=data_dir(), perm=0o600) as f:
        f.write(
            json.dumps({"root": str(Path(root).resolve()), "folder": _folder(root), "on": True, "at": at}, indent=1)
            + "\n"
        )


def turn_off(root: Path) -> None:
    """Turn formalization off for the quilt at `root` on this machine; what it installed stays."""
    own.unlink(switch_file(root), root=data_dir(), missing_ok=True)
    own.unlink(checked_file(root), root=data_dir(), missing_ok=True)


def checked_file(root: Path) -> Path:
    """Where `again` keeps which state of the quilt's Lean and of the texts it states it last checked on its own: beside the switch, `formal/<key>.checked`."""
    return switch_file(root).with_suffix(".checked")


def checked(root: Path) -> str:
    """The state `again` last checked on its own for the quilt at `root`, as `remember_checked` kept it; '' for none."""
    try:
        return checked_file(root).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def remember_checked(root: Path, state: str) -> None:
    """Keep `state` as the one `again` last checked on its own for the quilt at `root`, so a server started again over the same Lean runs nothing."""
    p = checked_file(root)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with own.open(p, "w", encoding="utf-8", root=data_dir(), perm=0o600) as f:
        f.write(state + "\n")


def last_file(root: Path) -> Path:
    """Where loom keeps when it last checked the quilt's Lean and what came of it: beside the switch, `formal/<key>.last`."""
    return switch_file(root).with_suffix(".last")


def last_check(root: Path) -> dict[str, Any] | None:
    """When loom last checked the Lean of the quilt at `root` on this machine and what came of it, as `remember_check` kept it; None for never, or a file that does not read."""
    try:
        data = json.loads(last_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("at"), str) else None


def remember_check(root: Path, came: dict[str, Any]) -> None:
    """Keep that loom checked the quilt's Lean now, and what came of it (`came`: counts of what it recorded, or why it refused), for `loom doctor`."""
    p = last_file(root)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with own.open(p, "w", encoding="utf-8", root=data_dir(), perm=0o600) as f:
        f.write(json.dumps({"at": at, **came}, indent=1) + "\n")
