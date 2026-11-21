"""The works list (`library-views.md` §3.1, the read `library-works`): every reference as a row drawn with its words, what loom holds of it, what of it is digested, and the documents that cite it.

It gathers first, so the list holds every entry a document reads, and opens no node file but the references', no PDF and no source. A work's `digested` counts come from the index; `compared` and `of` wait for the evidence of a comparison and a source's survey, and are 0 and null until then.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loom.library import log
from loom.library.body import pointers
from loom.library.entries import identifiers, link, read_entry, short, surnames, title, year
from loom.library.gather import gather
from loom.library.index import NodeIndex

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


def cited_in(result: ScanResult) -> dict[str, list[str]]:
    """Each entry key the person's documents cite, folded to lower case, to the documents citing it, in order."""
    out: dict[str, list[str]] = {}
    for doc in sorted(m for m in result.masters if result.document_role(m) == "person" and m in result.expansions):
        for p in pointers(result.expansions[doc].text):
            if p.cites:
                docs = out.setdefault(p.target.lower(), [])
                if doc not in docs:
                    docs.append(doc)
    return out


def works(result: ScanResult, *, doc: str | None = None, write: bool = True) -> list[dict[str, Any]]:
    """Every work in the library as a row of the works list.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.
    doc : str, optional
        A document whose compile's citation labels each row carries as `cited_as` (the Docs picker, §6.1).
    write : bool, default True
        Gather first, making a reference for each entry a document reads that has none.

    Returns
    -------
    list of dict
        One row a reference, by `short` then id: `ref`, `short`, `title`, `authors`, `year`, `holds`, `digested`, `used_in`, `link`, `version`, `lookup`, `cited_as`.
    """
    root = result.quilt.root
    if write:
        gather(result)
    citing = cited_in(result)
    labels: dict[str, str] = {}
    if doc:
        from loom.tex.aux import read_cite_labels

        labels = {k.lower(): v for k, v in read_cite_labels(root, doc).items()}
    acts = log.replay(root)
    rows: list[dict[str, Any]] = []
    with NodeIndex.open(root) as index:
        counts = {
            (src, kind, empty): n
            for src, kind, empty, n in index.db.execute(
                "SELECT source, kind, empty, COUNT(*) FROM nodes WHERE source IS NOT NULL GROUP BY source, kind, empty"
            )
        }
        for (ref,) in index.db.execute("SELECT id FROM nodes WHERE kind = 'reference' ORDER BY id").fetchall():
            node = index.node(ref)
            entry = read_entry(node.body) if node else None
            if node is None or entry is None:
                continue
            fields = entry.fields
            statements = counts.get((ref, "statement", 0), 0)
            stubs = counts.get((ref, "statement", 1), 0)
            stated = identifiers(fields)
            rows.append(
                {
                    "ref": ref,
                    "short": short(fields, entry.key),
                    "title": title(fields),
                    "authors": surnames(fields),
                    "year": year(fields),
                    "holds": {"pdf": node.pdf, "tex": node.tex is not None},
                    "digested": {"statements": statements, "of": None, "compared": 0, "stubs": stubs}
                    if statements or stubs
                    else None,
                    "used_in": citing.get(entry.key.lower(), []),
                    "link": link(fields),
                    "version": fields.get("version") or None,
                    # `scheme:value`, as the intake's rows give it; the viewer says it as a person reads it
                    "lookup": {"state": "unconfirmed", "identifier": stated[0]}
                    if stated and acts.unconfirmed(ref)
                    else None,
                    "cited_as": labels.get(entry.key.lower()),
                }
            )
    return sorted(rows, key=lambda r: (r["short"].lower(), r["ref"]))
