"""The library's one generation (`docs/specs/library-views.md` §2, "Freshness"): a number that goes forward whenever anything a library read answers from changes, which every read and write of the library answers with and the publisher's stream sends as its `library` event.

What it is made from: the library's nodes and the tags on them (the index's own generation), every log under `.loom/records/` but the annotation log (the library's log, and whatever records another lane keeps there), the annotation log's lines on works (a note written or placed on a reference or a node of the store, and every line after it naming it), so a note on a draft moves nothing, the documents the store holds, the person's documents' citations, and the labels their last compiles cite each work by. A publish that changes none of these leaves it where it was, so a compile does not set every open view reading again.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from loom.clock import now
from loom.library.index import NodeIndex
from loom.paths import ANNOTATION_LOG, LIBRARY_DOCUMENTS, LIBRARY_NODES, RECORDS

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: The generation this process last gave each quilt, with what it was made from.
_GIVEN: dict[Path, tuple[tuple[object, ...], int]] = {}
#: The digest of each quilt's notes on works, by the annotation log's size, time and inode when it was read.
_NOTES: dict[Path, tuple[tuple[int, int, int], bytes]] = {}


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
    """What the generation is made from, as it stands now: the index's generation, each record log's size, time and inode but the annotation log's, a digest of the notes on works, the stored documents' names, and a digest of the citations and cite labels."""
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
    return (nodes, _logs(root), _notes_on_works(root), documents, words)


def _logs(root: Path) -> tuple[tuple[str, int, int, int], ...]:
    """Each `.json` and `.jsonl` file of the records and of each folder directly under them, by name, size, modification time and inode, but the annotation log (`_notes_on_works`); what lies deeper (the history's kept texts) is no log."""
    records, notes = root / RECORDS, root / ANNOTATION_LOG
    out: list[tuple[str, int, int, int]] = []
    for folder in (records, *(p for p in _entries(records) if p.is_dir())):
        for p in _entries(folder):
            if p.suffix in (".json", ".jsonl") and p != notes:
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


def _notes_on_works(root: Path) -> bytes:
    """A digest of the annotation log's lines on works: each line whose target is a reference or a node of the store (a note written or placed there), or that answers one, and every later line naming one; read again only when the log's size, time or inode moves."""
    from loom.library import ids
    from loom.library.node import file_name

    path = root / ANNOTATION_LOG
    digest = hashlib.blake2b(digest_size=16)
    try:
        st = path.stat()
    except OSError:
        return digest.digest()  # as a log holding no line on a work
    key = (st.st_size, st.st_mtime_ns, st.st_ino)
    kept = _NOTES.get(root)
    if kept is not None and kept[0] == key:
        return kept[1]
    held: dict[str, bool] = {}

    def of_library(target: str) -> bool:
        if target not in held:
            held[target] = bool(target) and (
                ids.kind_of(target) == ids.REFERENCE or (root / LIBRARY_NODES / file_name(target)).is_file()
            )
        return held[target]

    on: set[str] = set()
    try:
        with path.open("rb") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(event, dict):
                    continue
                name = str(event.get("id") or "")
                # a note written or placed on a work, or a reply to one, is on works from then on
                if of_library(str(event.get("target") or "")) or str(event.get("reply_to") or "") in on:
                    on.add(name)
                if name in on:
                    digest.update(line)
    except OSError:
        return hashlib.blake2b(b"unread", digest_size=16).digest()
    _NOTES[root] = (key, digest.digest())
    return _NOTES[root][1]
