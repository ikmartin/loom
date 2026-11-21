"""The works list (`library-views.md` §3.1, the read `library-works`): every reference as a row drawn with its words, what loom holds of it, what of it is digested, and the documents that cite it.

A read and nothing more: it gathers nothing and writes nothing (gathering runs after a build, `library.gather`), and opens no node file, no PDF and no source, the references and the counts of their nodes coming from the index in one pass. A row's words are made once for each entry's text, and the documents citing each key once for each scan. A work's `digested` counts come from the index; `compared` and `of` wait for the evidence of a comparison and a source's survey, and are 0 and null until then.
"""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.library import log
from loom.library.body import pointers
from loom.library.entries import identifiers, link, read_entry, short, surnames, title, year
from loom.library.index import NodeIndex
from loom.paths import LIBRARY_LOG

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: The documents citing each key, for the last scan asked about: a publisher holds one scan until a file it reads changes.
_CITED: tuple[ScanResult | None, dict[str, list[str]]] = (None, {})
#: The library's log as last read, by its file's size, time and inode.
_REPLAYED: dict[Path, tuple[tuple[int, int, int], log.Acts]] = {}
#: Each list's generation as this process last gave it, with what it was given for: by quilt and document.
_GENERATIONS: dict[tuple[Path, str | None], tuple[tuple[Any, ...], int]] = {}


def cited_in(result: ScanResult) -> dict[str, list[str]]:
    """Each entry key the person's documents cite, case folded, to the documents citing it, in order; read once for each scan."""
    global _CITED
    if _CITED[0] is result:
        return _CITED[1]
    out: dict[str, list[str]] = {}
    for doc in sorted(m for m in result.masters if result.document_role(m) == "person" and m in result.expansions):
        for p in pointers(result.expansions[doc].text):
            if p.cites:
                docs = out.setdefault(p.target.casefold(), [])
                if doc not in docs:
                    docs.append(doc)
    _CITED = (result, out)
    return out


def _stamp(path: Path) -> tuple[int, int, int]:
    try:
        st = path.stat()
    except OSError:
        return (0, 0, 0)
    return st.st_size, st.st_mtime_ns, st.st_ino


def _replayed(root: Path) -> log.Acts:
    """The library's log, replayed again only once its file has changed."""
    stamp = _stamp(root / LIBRARY_LOG)
    kept = _REPLAYED.get(root)
    if kept is None or kept[0] != stamp or stamp[1] >= time.time_ns() - 2_000_000_000:
        # a log written within the last two seconds may change again within its time's resolution
        kept = (stamp, log.replay(root))
        _REPLAYED[root] = kept
    return kept[1]


def _labels(root: Path, doc: str | None) -> dict[str, str]:
    if not doc:
        return {}
    from loom.tex.aux import read_cite_labels

    return {k.casefold(): v for k, v in read_cite_labels(root, doc).items()}


def generation(result: ScanResult, *, doc: str | None = None) -> int:
    """The library's generation as the works list reads it: a number that goes forward whenever anything a row is made from changes.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, whose citations make `used_in`.
    doc : str, optional
        A document whose cite labels the list carries.

    Returns
    -------
    int
        The time, in milliseconds, at which this process first saw the library as it now stands: its nodes and tags (the index's generation), the library's log, the documents' citations and, given `doc`, its cite labels. A number given again while none of these has changed, so `since` answers `unchanged`, and never a smaller one, a restarted publisher's included.
    """
    root = result.quilt.root
    with NodeIndex.open(root) as index:
        nodes = index.generation()
    citations = hashlib.blake2b(json.dumps(cited_in(result), sort_keys=True).encode(), digest_size=16).digest()
    labels = json.dumps(_labels(root, doc), sort_keys=True) if doc else ""
    seen = (nodes, _stamp(root / LIBRARY_LOG), citations, labels)
    kept = _GENERATIONS.get((root, doc))
    if kept is not None and kept[0] == seen:
        return kept[1]
    gen = max(time.time_ns() // 1_000_000, kept[1] + 1 if kept else 0)
    _GENERATIONS[(root, doc)] = (seen, gen)
    return gen


@lru_cache(maxsize=4096)
def _words(body: str) -> tuple[str, str, str, list[str], str, str | None, str | None, list[str]] | None:
    """What a row says of a reference's entry, made once for each text: its key, short name, title, surnames, year, link, version and identifiers; None for a body holding no entry."""
    entry = read_entry(body)
    if entry is None:
        return None
    fields = entry.fields
    return (
        entry.key,
        short(fields, entry.key),
        title(fields),
        surnames(fields),
        year(fields),
        link(fields),
        fields.get("version") or None,
        identifiers(fields),
    )


def works(result: ScanResult, *, doc: str | None = None) -> list[dict[str, Any]]:
    """Every work in the library as a row of the works list.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    doc : str, optional
        A document whose compile's citation labels each row carries as `cited_as` (the Docs picker, §6.1).

    Returns
    -------
    list of dict
        One row a reference, by `short` then id: `ref`, `short`, `title`, `authors`, `year`, `holds`, `digested`, `used_in`, `link`, `version`, `lookup`, `cited_as`.

    See Also
    --------
    generation : the number the list is answered with, which `since` is compared against.
    """
    root = result.quilt.root
    citing = cited_in(result)
    labels = _labels(root, doc)
    acts = _replayed(root)
    rows: list[dict[str, Any]] = []
    with NodeIndex.open(root) as index:
        counts = {
            (src, kind, empty): n
            for src, kind, empty, n in index.db.execute(
                "SELECT source, kind, empty, COUNT(*) FROM nodes WHERE source IS NOT NULL GROUP BY source, kind, empty"
            )
        }
        refs = index.db.execute("SELECT id, header, body FROM nodes WHERE kind = 'reference' ORDER BY id").fetchall()
    for ref, header, body in refs:
        words = _words(body)
        if words is None:
            continue
        key, named, titled, authors, when, page, version, stated = words
        held = json.loads(header)
        statements = counts.get((ref, "statement", 0), 0)
        stubs = counts.get((ref, "statement", 1), 0)
        rows.append(
            {
                "ref": ref,
                "short": named,
                "title": titled,
                "authors": list(authors),
                "year": when,
                "holds": {"pdf": held.get("pdf"), "tex": held.get("tex") is not None},
                "digested": {"statements": statements, "of": None, "compared": 0, "stubs": stubs}
                if statements or stubs
                else None,
                "used_in": list(citing.get(key.casefold(), [])),
                "link": page,
                "version": version,
                # `scheme:value`, as the intake's rows give it; the viewer says it as a person reads it
                "lookup": {"state": "unconfirmed", "identifier": stated[0]}
                if stated and acts.unconfirmed(ref)
                else None,
                "cited_as": labels.get(key.casefold()),
            }
        )
    return sorted(rows, key=lambda r: (r["short"].lower(), r["ref"]))
