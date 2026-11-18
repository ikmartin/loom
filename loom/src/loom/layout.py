"""The layout's number: which arrangement of `.loom/` a quilt is in, read before anything else there.

`loom init` writes it, and so does the first load of a quilt that has no `.loom/` yet. A quilt whose `.loom/` has no number, or one this loom does not know, is refused by every command (`refusal`) and reported by `loom doctor`: read with another layout's names, its records would look absent and a second tree would be written beside them.
"""

from __future__ import annotations

from pathlib import Path

from loom.paths import FORMAT, LOOM

#: The layout this loom reads and writes.
NUMBER = 1


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
    return f"this quilt's {FORMAT} says {said or 'nothing'}, and this loom reads format {NUMBER}"


def stamp(root: Path) -> None:
    """Write this loom's number to `.loom/format`, making `.loom/` if needed."""
    p = root / FORMAT
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"{NUMBER}\n", encoding="utf-8")
