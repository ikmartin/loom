"""Where a stored paper's annotations stand on its pages: what the reader needs to draw a note or a highlight on a page of a work's PDF, in the Library and beside a draft alike (`docs/specs/library-views.md` §3.3, `library-places`).

Made when it is asked for and never before. A work's nodes join the places of the pages asked for, as the digest marks ask while they are on, and one node's place is asked by itself: a statement's or a proof's place is its opening words, before its first formula, found on the page its `pages` names, with the words of its text that page lacks, and a stub's the mark to digest that names it. A text anchor's rectangles are its quotation found among the page's word boxes, which are read from the PDF the first time a page is asked for and kept under the cache by the PDF's hash (`refs.pages.pages_home`), so a page asked for again reads no PDF; a box's are its record, or where a changed copy found it again; a mark that records its own place stands there (`records.crops.rects_of` places each). Nothing of it is a record: it is found again from the annotation log and the PDF whenever they change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loom.library import ids
from loom.library.entries import read_entry, short
from loom.library.generation import generation
from loom.library.store import read

if TYPE_CHECKING:
    from pathlib import Path

    from loom.library.node import Node
    from loom.scan.scan import ScanResult


class PlacesRefused(Exception):
    """A read of places loom will not answer: its code, its sentence, and the HTTP status the write API gives it."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


#: The longest piece of a refused name a message repeats.
_SAID = 80


@dataclass
class Places:
    """What `places` answers: the PDF the rectangles are on, the generation, and each annotation's place, then each node's where asked."""

    pdf: str
    gen: int
    places: list[dict[str, Any]] = field(default_factory=list)


def places(result: ScanResult, ref: str | None, pages: list[int] | None = None, *, node: str | None = None) -> Places:
    """Each annotation on a work's stored PDF that stands somewhere, with its page and rectangles; and the work's nodes on the pages asked for.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, whose annotations are read as they stand now.
    ref : str or None
        The work's reference; None with `node`, whose work it is.
    pages : list of int, optional
        The pages to answer for, from 1, each of the work's nodes there among them, as the digest marks ask while they are on; every page an annotation is on, and no node, by default.
    node : str, optional
        Answer this node's place alone, and no annotation's.

    Returns
    -------
    Places
        `places` is `[{"annotation", "page", "rects"}]`, by page then by when each was written, `rects` one `[x0, y0, x1, y1]` a line in points from the page's top left; an annotation that stands nowhere (detached, or its words not found on its page) has no entry. A node's entry is `{"node", "name", "number", "page", "rects", "paper", "lean", "lacks"}`, `lacks` the words of its text its page does not have; a node with no place found has none. `gen` is the library's one generation (`library.generation`), which goes forward whenever anything the library's reads answer from changes, and never back.

    Raises
    ------
    PlacesRefused
        `no-such-ref` (404) for no reference of that id; `no-such-node` (404) for `node` naming no statement or proof, or one of another work; `no-document` (409) for a work holding no PDF.
    """
    from loom.records.crops import rects_of
    from loom.records.store import Records

    root = result.quilt.root
    held = read(root, node) if node is not None and ids.kind_of(node) in (ids.STATEMENT, ids.PROOF) else None
    if node is not None and (held is None or not held.source or ref not in (None, held.source)):
        raise PlacesRefused("no-such-node", f"the library has no statement or proof {node[:_SAID]} of that work", 404)
    ref = held.source if held is not None else ref
    work = read(root, ref) if ref and ids.kind_of(ref) == ids.REFERENCE else None
    if work is None:
        raise PlacesRefused("no-such-ref", f"the library has no work {(ref or '')[:_SAID]}", 404)
    if not work.pdf:
        entry = read_entry(work.body)
        named = short(entry.fields, entry.key) if entry is not None else work.id
        raise PlacesRefused("no-document", f"{named} holds no PDF, so nothing on it has a place")
    gen = generation(result)
    if held is not None:
        return Places(work.pdf, gen, _nodes(result, work, [held], None))
    asked = set(pages) if pages else None
    out: list[dict[str, Any]] = []
    for ra in sorted(Records(root).resolved(result), key=lambda r: r.annotation.created):
        a = ra.annotation
        if ra.work != work.id or ra.detached:
            continue
        page = ra.page or a.page or (a.anchor.page if a.anchor else None)
        if not page or (asked is not None and page not in asked):
            continue
        rects = rects_of(result, ra)
        if rects:
            out.append({"annotation": a.id, "page": page, "rects": rects})
    out.sort(key=lambda p: p["page"])
    if asked is not None:
        from loom.library.digest import of_work

        out += _nodes(result, work, of_work(root, work.id), asked)
    return Places(work.pdf, gen, out)


def _nodes(result: ScanResult, work: Node, held: list[Node], asked: set[int] | None) -> list[dict[str, Any]]:
    """Where each of a work's nodes stands on the pages `asked`: a node with text by its opening words on the page its `pages` names, a stub by the mark to digest naming it."""
    from loom.library import documents
    from loom.library.reads import Standing, _to_digest, name_of
    from loom.records.crops import rects_of
    from loom.refs.pages import mapped

    root = result.quilt.root
    assert work.pdf is not None
    home = mapped(root, work.pdf)
    pdf = documents.path_of(root, work.pdf, "pdf")
    standing = Standing(root)
    marks = {ra.annotation.node: ra for ra in _to_digest(result, work.id) if ra.annotation.node}
    out: list[dict[str, Any]] = []
    for n in held:
        if n.empty:
            ra = marks.get(n.id)
            page = (ra.page or ra.annotation.page) if ra is not None else None
            rects = rects_of(result, ra) if ra is not None and page else None
            lacks: list[str] = []
        else:
            page, rects, lacks = _placed(home, pdf, n)
        if not page or not rects or (asked is not None and page not in asked):
            continue
        out.append(
            {
                "node": n.id,
                "name": name_of(n) if n.kind == ids.STATEMENT else "Proof",
                "number": n.number,
                "page": page,
                "rects": rects,
                "paper": standing.paper(n.id),
                "lean": standing.lean(n.id),
                "lacks": lacks,
            }
        )
    return sorted(out, key=lambda p: (p["page"], p["rects"][0][1]))


def _placed(home: Path | None, pdf: Path, n: Node) -> tuple[int | None, list[list[float]] | None, list[str]]:
    """A node's place on its first page: the rectangles of its opening words where that page holds them, and the words of its text its pages lack."""
    import re

    from loom.refs.anchoring import anchor_on_page
    from loom.refs.pages import read_page
    from loom.refs.search import find_in_page, fold

    first = n.pages.split("-")[0] if n.pages else ""
    if home is None or not first.isdigit():
        return None, None, []
    page = int(first)
    last = int(n.pages.split("-")[-1]) if n.pages and n.pages.split("-")[-1].isdigit() else page
    words = _words(n.body)
    opening = " ".join(words[:8])
    text = read_page(home, page) or ""
    if len(opening) < 12 or not find_in_page(text, opening):
        return None, None, []
    try:
        placed = anchor_on_page(home, pdf, page, opening, [], None)
    except Exception:  # noqa: BLE001 -- poppler's boxes are a nicety on a page whose text holds the words
        return None, None, []
    held = set(re.findall(r"[^\W\d_]{3,}", fold(" ".join(read_page(home, p) or "" for p in range(page, last + 1)))))
    mine = re.findall(r"[^\W\d_]{3,}", fold(" ".join(words)))
    lacks = list(dict.fromkeys(w for w in mine if w not in held))
    return page, placed.anchor.quads or None, lacks[:20]


def _words(body: str) -> list[str]:
    """A node's text as words a page shows: comments, mathematics, commands and their braces taken out."""
    import re

    from loom.library.body import blank_comments

    text = blank_comments(body)
    text = re.sub(r"\$\$.*?\$\$|\$[^$]*\$|\\\[.*?\\\]|\\\(.*?\\\)", " ", text, flags=re.S)
    text = re.sub(
        r"\\begin\s*\{(equation|align|gather|multline|eqnarray|displaymath)\*?\}.*?\\end\s*\{\1\*?\}",
        " ",
        text,
        flags=re.S,
    )
    text = re.sub(r"\\(?:label|ref|eqref|cite\w*|cref|Cref)\*?\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?|[{}~]", " ", text)
    return re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", text)
