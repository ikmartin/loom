"""What a read computes, kept while nothing it read has changed: the same scan object the publisher keeps while it is current, and the same bytes of each file it names.

Review's and the Web's reads compute their rows from the scan, the logs, the manifest and the Lean files the records name; a read after one that changed none of them answers from what that one computed. A scan made afresh for each call (no publisher) is a new object, so nothing is kept for it.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

#: For each quilt and kind of read: the file states it was computed under, the scan it read, and what it computed.
_KEPT: dict[tuple[str, str], tuple[tuple[Any, ...], Any, Any]] = {}


def stamps(paths: Iterable[Path]) -> tuple[Any, ...]:
    """Each file's inode, size and time, None for one that is absent: what tells a file changed without reading it."""
    out: list[Any] = []
    for path in paths:
        try:
            st = os.stat(path)
        except OSError:
            out.append((str(path), None))
            continue
        out.append((str(path), st.st_ino, st.st_size, st.st_mtime_ns))
    return tuple(out)


def kept(root: Path, what: str, scan: Any, paths: Callable[[], Iterable[Path]], make: Callable[[], T]) -> T:
    """`make()`, or what it returned last for this quilt and `what` while `scan` is the same object and no file of `paths()` changed.

    Parameters
    ----------
    root : Path
        The quilt.
    what : str
        Which read's work this is; one value per kind of result.
    scan : ScanResult
        The scan the work reads; kept by identity, so a fresh scan computes anew.
    paths : callable
        The files the work reads, asked again on each call so that a record naming a new file is seen.
    make : callable
        Computes the work.

    Returns
    -------
    object
        What `make` returned, now or under the same scan and files.
    """
    key = (str(root.resolve()), what)
    marks = stamps(paths())
    held = _KEPT.get(key)
    if held is not None and held[1] is scan and held[0] == marks:
        return held[2]  # type: ignore[no-any-return]
    value = make()
    # the files as they stood before `make` read them: one changed while it ran is seen as changed next time
    _KEPT[key] = (marks, scan, value)
    return value


def read_files(root: Path) -> list[Path]:
    """What a read of Review or the Web rests on beside the scan: the evidence, asks, annotations and edits logs, the published manifest, and every Lean file a record names."""
    from loom.evidence.log import replay
    from loom.paths import ANNOTATION_LOG, ASK_LOG, EDIT_LOG, EVIDENCE_LOG, MANIFEST

    lean = {path for r in replay(root).of_kind("lean") for path in dict(r.get("files", {}))}
    logs = [EVIDENCE_LOG, ASK_LOG, ANNOTATION_LOG, EDIT_LOG, MANIFEST]
    return [*(root / p for p in logs), *(root / p for p in sorted(lean))]
