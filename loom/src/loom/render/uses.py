"""What a build reads and makes in `.loom/cache/`, noted as it goes, so the build's index can name every file a fragment was made from.

A reader of the cache calls `used` with each file or folder it read or wrote; whoever wants to know what a piece of work used wraps it in `noting`. The notes are per thread, since a build renders on a pool. A note that starts with `@` names a group: work several fragments share (a document's page, the nodes no document reaches, a digest), noted once in `FragmentRenderer.groups` and named by each fragment that took from it.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_local = threading.local()


@contextmanager
def noting(*, apart: bool = False) -> Iterator[set[str]]:
    """Collect every note this thread makes inside the block.

    Parameters
    ----------
    apart : bool, default False
        Keep the notes from the notings around this one, which a group uses so that what it noted is named once, by the group; otherwise they see them too.

    Yields
    ------
    set of str
        The notes, filled as the block runs.
    """
    outer: tuple[set[str], ...] = () if apart else getattr(_local, "sets", ())
    mine: set[str] = set()
    before = getattr(_local, "sets", ())
    _local.sets = (*outer, mine)
    try:
        yield mine
    finally:
        _local.sets = before


def used(*notes: Path | str) -> None:
    """Note what this thread read or made in the cache, in every noting around it; nothing outside one.

    Parameters
    ----------
    *notes : Path or str
        Each a cache file or folder, as a path, or a group taken from, as `@name`.
    """
    sets: tuple[set[str], ...] = getattr(_local, "sets", ())
    if not sets:
        return
    said = [str(n) for n in notes]
    for s in sets:
        s.update(said)
