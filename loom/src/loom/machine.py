"""The machine's own place: what loom keeps for this machine and this person outside any quilt.

Loom's TeX and tools are there (`tex/private.py`), the one copy of a tool TeX unpacks on its first run (`unpacked`), and the token each running server's writes must carry, one file a quilt, so that a quilt committed or copied whole carries no token and grants nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

#: The folder of `data_dir` that holds each served quilt's write token.
TOKENS = "tokens"
#: The folder of `data_dir` a tool that unpacks itself on its first run unpacks into, once for the machine: TeX Live's `biber`, about 200 MB.
UNPACKED = "unpacked"


def data_dir() -> Path:
    """Loom's directory of machine-wide data: `~/Library/Application Support/loom` on a Mac, `$XDG_DATA_HOME/loom` elsewhere."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "loom"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "loom"


def unpacked() -> Path:
    """Where a self-unpacking tool a TeX run starts unpacks, `UNPACKED` in `data_dir`, made if it is not there: a tool given a folder it cannot write unpacks again elsewhere."""
    p = data_dir() / UNPACKED
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # the run still goes, and the tool unpacks where it can
    return p


def token_file(root: Path) -> Path:
    """Where the write token of the server on the quilt at `root` is kept: `tokens/<key>.json` in `data_dir`, keyed by the quilt's resolved path."""
    key = hashlib.sha256(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:24]
    return data_dir() / TOKENS / f"{key}.json"


def write_token(root: Path, token: str) -> None:
    """Keep `token` as the write token of the server on `root`, readable by this user alone.

    The folder is made closed to others, and a file an earlier server left is emptied and closed before the token goes in, since it keeps the mode it was made with.
    """
    p = token_file(root)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p.parent, 0o700)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"root": str(Path(root).resolve()), "token": token}, indent=1) + "\n")


def read_token(root: Path) -> str:
    """The write token of the server on `root`, or '' when none is kept or the file names another quilt."""
    try:
        data = json.loads(token_file(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict) or data.get("root") != str(Path(root).resolve()):
        return ""
    token = data.get("token")
    return token if isinstance(token, str) else ""


def forget_token(root: Path) -> None:
    """Remove the write token of the server on `root`: it has stopped."""
    token_file(root).unlink(missing_ok=True)
