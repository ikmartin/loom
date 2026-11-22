"""From a place on a page to the anchor loom records (plan 0.13 item 2).

One function, called by everything that turns a selection or a drawn rectangle into an anchor: the `locate` endpoint, which answers and writes nothing; `loom annotate` on a page of a work's PDF; and the same write over the API. **They cannot disagree, because they do not each map.** The client's text layer is a third extraction of the page, after loom's page text and word boxes; only loom holds the other two, and only loom can say what its page text says, which is what an anchor is checked against.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.anchors import Anchor
from loom.records.selectors import CONTEXT, Selector


@dataclass
class Placed:
    """What mapping a place gives back: the anchor of record, the text triple beside it, and the words a person reads."""

    anchor: Anchor
    selector: Selector
    #: Whether the text asked for was found on the page at all. A box is always "found": what was drawn is the record.
    found: bool
    #: The page's width and height in points, for a caller drawing against it.
    page_box: tuple[float, float] | None
    #: `text` or `box`: the one word that says which description is of record.
    said: str
    #: A box's top left less its pin word's (`records.marks.context_at`), by which a changed copy of the work places it again; None for text, or a page with no words.
    gap: list[float] | None = None


def anchor_on_page(
    home: Path,
    pdf: Path,
    page: int,
    text: str | None = None,
    rects: list[list[float]] | None = None,
    span: tuple[int, int] | None = None,
) -> Placed:
    """Map a selection or a drawn rectangle on one page of a stored PDF to the anchor loom would record.

    Parameters
    ----------
    home : Path
        The PDF's page text and section map (`refs.pages.mapped`).
    pdf : Path
        The stored PDF.
    page : int
        The page, from 1.
    text : str, optional
        What was selected. Matched against the word boxes with a tolerance for hyphenation and ligatures, and then located in the page text for offsets. Where the words occur more than once on the page, the occurrence `rects` covers is the one recorded, the first when no `rects` are given.
    rects : list of [x0, y0, x1, y1], optional
        The lines a selection covers, as the viewer sends them, or what was drawn when there was no text worth selecting; in points with the origin at the top left.
    span : (start, end), optional
        Offsets into the page's text, as a `span=` locator carries them; the text between them is what is mapped, so a link written by offsets lights the same place a selection would.

    Returns
    -------
    Placed
        Basis `text` when the selection located in the page text, with `start`/`end` and derived quads, both of the occurrence chosen, and the triple's `prefix` and `suffix` the words around that occurrence; basis `box` otherwise, carrying the rectangles as the record and whatever words they cover as the triple's `exact`. Recording never fails: a selection found on the boxes but not in the page text is a box, a selection whose rectangles cover none of its words' occurrences, or two alike, is the box it covers, and a rectangle is a box.

    Notes
    -----
    The caller has already checked the PDF is readable (`refs.pages.mapped`); this raises nothing of its own beyond what `token_boxes` raises for a missing poppler.
    """
    from loom.refs.pages import page_box, read_map, read_page, token_boxes
    from loom.refs.search import every_offset, every_span

    m = read_map(home)
    xml = token_boxes(pdf, page, home)
    page_text = read_page(home, page) or ""
    if span and not text:
        a, b = max(0, span[0]), min(len(page_text), span[1])
        text = page_text[a:b].strip() or None
    anchor = Anchor(kind="pdf", sha256=m.sha256 if m else "", page=page)
    rects = [[float(v) for v in r] for r in rects or []]
    hits = every_span(xml, text, page) if text else []
    k = _chosen(hits, rects)
    hit = hits[k] if k is not None else None
    found = hit is not None or bool(rects)
    if hit is not None and k is not None:
        # the k-th occurrence in the page's text is the k-th on its boxes, when the two readings find as many
        every = every_offset(page_text, text or "")
        offsets = every[k] if len(every) == len(hits) else None
        anchor.quads = [list(q) for q in hit.lines]
        if offsets:
            a, b = offsets
            anchor.basis, anchor.start, anchor.end = "text", a, b
            selector = Selector(page_text[a:b], page_text[max(0, a - CONTEXT) : a], page_text[b : b + CONTEXT])
        else:
            # found on the page's boxes and not in its text: geometry is what can honestly be recorded
            anchor.basis = "box"
            selector = Selector(text or "")
    else:
        # a formula, a figure, a scan: what the reader drew is the record, and the words under and around it are how a changed copy finds it again
        anchor.basis, anchor.quads = "box", rects
        selector, gap = _around(home, pdf, page, rects)
        if not selector.exact and text:
            # a box on no words, given the words it means: they are its quote, and nothing pins it
            selector, gap = Selector(text, selector.prefix, selector.suffix), None
        return Placed(anchor, selector, found, page_box(xml), anchor.basis, gap)
    return Placed(anchor, selector, found, page_box(xml), anchor.basis)


def _chosen(hits: list[Any], rects: list[list[float]]) -> int | None:
    """Which occurrence of a selection's words is the one selected: the only one, the one its rectangles cover most, or the first when it came with none; None when its rectangles cover none, or two alike."""
    if len(hits) <= 1 or not rects:
        return 0 if hits else None
    covered = [sum(_overlap(line, r) for line in hit.lines for r in rects) for hit in hits]
    best = max(covered)
    if best <= 0 or covered.count(best) > 1:
        return None
    return covered.index(best)


def _overlap(a: Sequence[float], b: Sequence[float]) -> float:
    """The area two rectangles `[x0, y0, x1, y1]` share."""
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _around(home: Path, pdf: Path, page: int, rects: list[list[float]]) -> tuple[Selector, list[float] | None]:
    """The words under and around a box on a stored PDF's page, and its gap from them, from its words cached beside its page text (`records.marks.context_at`); nothing when the box is drawn on nothing or pdftotext cannot read the file."""
    from loom.records.marks import DocumentWords, context_at
    from loom.refs.pages import MapRefused, document_boxes, store_boxes

    if not rects:
        return Selector(""), None
    try:
        return context_at(DocumentWords(document_boxes(pdf, store_boxes(home))), page, rects)
    except MapRefused:
        return Selector(""), None
