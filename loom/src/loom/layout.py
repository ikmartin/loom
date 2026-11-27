"""The layout's number: which arrangement of `.loom/` a quilt is in, read before anything else there.

`loom init` writes it, and so does the first load of a quilt that has no `.loom/` yet, which makes `.loom/` with its number already in it. A quilt whose `.loom/` has no number, or one this loom does not know, is refused by every command (`refusal`) and reported by `loom doctor`: read with another layout's names, its records would look absent and a second tree would be written beside them.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
from pathlib import Path

from loom import own
from loom.paths import FORMAT, LOOM

#: The layout this loom reads and writes.
NUMBER = 2
#: The earlier layouts this loom can bring forward to its own (`loom upgrade`, `library.carry`), which every other command refuses.
CARRIES = frozenset({"1"})


def carriable(root: Path) -> bool:
    """Whether the quilt at `root` is in an earlier layout this loom can bring forward to its own."""
    return found(root) in CARRIES


def found(root: Path) -> str | None:
    """What `.loom/format` holds, stripped; None when there is no such file."""
    try:
        return (root / FORMAT).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return "?"


def refusal(root: Path) -> str | None:
    """Why this loom will not open the quilt at `root`, in one sentence; None when its layout is this loom's or it has no `.loom/` yet."""
    said = found(root)
    if said == str(NUMBER):
        return None
    if said is None:
        if not (root / LOOM).exists():
            return None
        return (
            f"this quilt's {LOOM}/ has no format number, so an older loom made it, and this loom reads format {NUMBER}"
        )
    if said in CARRIES:
        return f"this quilt was made by an earlier loom, in format {said}, and this loom reads format {NUMBER}: loom upgrade brings it forward, its library carried into the node store"
    return f"this quilt's {FORMAT} says {said or 'nothing'}, and this loom reads format {NUMBER}"


def stamp(root: Path) -> None:
    """Write this loom's number to `.loom/format`, so that no other process ever reads `.loom/` without it or with part of it.

    A `.loom/` that is not there yet is made beside it with its number in it and renamed into place; when another process made one first, what it made stands. A `.loom/` that is there gets the number written whole, by rename.
    """
    folder = root / LOOM
    text = f"{NUMBER}\n"
    if not folder.exists():
        made = Path(tempfile.mkdtemp(prefix=f"{LOOM}-", dir=root))
        try:
            (made / Path(FORMAT).name).write_text(text, encoding="utf-8")
            try:
                os.rename(made, folder)
                return
            except OSError:
                return  # another process's `.loom/` is in place, and the caller reads what it holds
        finally:
            shutil.rmtree(made, ignore_errors=True)
    tmp = folder / f".format-{secrets.token_hex(6)}"
    try:
        with own.open(tmp, "x", encoding="utf-8", root=root, perm=0o600) as fh:
            fh.write(text)
        own.replace(tmp, root / FORMAT, root=root)
    finally:
        own.unlink(tmp, root=root, missing_ok=True)
