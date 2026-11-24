"""The library's one generation (`docs/specs/library-views.md` §2, "Freshness"): a number that goes forward whenever anything a library read answers from changes, which every read and write of the library answers with and the publisher's stream sends as its `library` event.

What it is made from: the library's nodes and the tags on them (the index's own generation), every log under `.loom/records/` (the library's log, the annotation log, and whatever records another lane keeps there), the documents the store holds, the person's documents' citations, and the labels their last compiles cite each work by. A publish that changes none of these leaves it where it was, so a compile does not set every open view reading again.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from loom.clock import now
from loom.library.index import NodeIndex
from loom.paths import LIBRARY_DOCUMENTS, RECORDS

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: The generation this process last gave each quilt, with what it was made from.
_GIVEN: dict[Path, tuple[tuple[object, ...], int]] = {}


def generation(result: ScanResult) -> int:
    """The library's generation as it stands now.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, whose documents' citations and cite labels a read answers from.

    Returns
    -------
    int
        The time, in milliseconds, at which this process first saw the library as it now stands, or one more than the last number it gave when that is not later: the same number while nothing it is made from has changed, so `since` answers `unchanged`, and never a smaller one. The clock is LOOM_FIXED_TIME's under it, so a fixture's first answer is that time and each change one more.
    """
    root = result.quilt.root
    seen = made_from(result)
    kept = _GIVEN.get(root)
    if kept is not None and kept[0] == seen:
        return kept[1]
    gen = max(int(now().timestamp() * 1000), kept[1] + 1 if kept else 0)
    _GIVEN[root] = (seen, gen)
    return gen


def made_from(result: ScanResult) -> tuple[object, ...]:
    """What the generation is made from, as it stands now: the index's generation, each record log's size, time and inode, the stored documents' names, and a digest of the citations and cite labels."""
    from loom.library.works import cite_labels, cited_in

    root = result.quilt.root
    with NodeIndex.open(root) as index:
        nodes = index.generation()
    citations = cited_in(result)
    labels = {doc: cite_labels(root, doc) for doc in sorted({d for docs in citations.values() for d in docs})}
    words = hashlib.blake2b(json.dumps([citations, labels], sort_keys=True).encode(), digest_size=16).digest()
    try:
        documents = tuple(sorted(os.listdir(root / LIBRARY_DOCUMENTS)))
    except OSError:
        documents = ()
    return (nodes, _logs(root / RECORDS), documents, words)


def _logs(records: Path) -> tuple[tuple[str, int, int, int], ...]:
    """Each `.json` and `.jsonl` file of the records and of each folder directly under them, by name, size, modification time and inode; what lies deeper (the history's kept texts) is no log."""
    out: list[tuple[str, int, int, int]] = []
    for folder in (records, *(p for p in _entries(records) if p.is_dir())):
        for p in _entries(folder):
            if p.suffix in (".json", ".jsonl"):
                try:
                    st = p.stat()
                except OSError:
                    continue
                out.append((p.relative_to(records).as_posix(), st.st_size, st.st_mtime_ns, st.st_ino))
    return tuple(sorted(out))


def _entries(folder: Path) -> list[Path]:
    try:
        return list(folder.iterdir())
    except OSError:
        return []
