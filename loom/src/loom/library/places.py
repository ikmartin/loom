"""Where a stored paper's annotations stand on its pages: what the reader needs to draw a note or a highlight on a page of a work's PDF, in the Library and beside a draft alike (`docs/specs/library-views.md` §3.3, `library-places`).

Made when it is asked for and never before. A text anchor's rectangles are its quotation found among the page's word boxes, which are read from the PDF the first time a page is asked for and kept under the cache by the PDF's hash (`refs.pages.pages_home`), so a page asked for again reads no PDF; a box's are its record, or where a changed copy found it again; a mark that records its own place stands there (`records.crops.rects_of` places each). Nothing of it is a record: it is found again from the annotation log and the PDF whenever they change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loom.library import ids
from loom.library.entries import read_entry, short
from loom.library.generation import generation
from loom.library.store import read

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


class PlacesRefused(Exception):
    """A read of places loom will not answer: its code, its sentence, and the HTTP status the write API gives it."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


@dataclass
class Places:
    """What `places` answers: the PDF the rectangles are on, the generation, and each annotation's place."""

    pdf: str
    gen: int
    places: list[dict[str, Any]] = field(default_factory=list)


def places(result: ScanResult, ref: str, pages: list[int] | None = None) -> Places:
    """Each annotation on a work's stored PDF that stands somewhere, with its page and rectangles.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, whose annotations are read as they stand now.
    ref : str
        The work's reference.
    pages : list of int, optional
        The pages to answer for, from 1; every page an annotation is on by default.

    Returns
    -------
    Places
        `places` is `[{"annotation", "page", "rects"}]`, by page then by when each was written, `rects` one `[x0, y0, x1, y1]` a line in points from the page's top left; an annotation that stands nowhere (detached, or its words not found on its page) has no entry. `gen` is the library's one generation (`library.generation`), which goes forward whenever anything the library's reads answer from changes, and never back.

    Raises
    ------
    PlacesRefused
        `no-such-ref` (404) for no reference of that id; `no-document` (409) for a work holding no PDF.
    """
    from loom.records.crops import rects_of
    from loom.records.store import Records

    root = result.quilt.root
    node = read(root, ref) if ids.kind_of(ref) == ids.REFERENCE else None
    if node is None:
        raise PlacesRefused("no-such-ref", f"the library has no work {ref}", 404)
    if not node.pdf:
        entry = read_entry(node.body)
        named = short(entry.fields, entry.key) if entry is not None else ref
        raise PlacesRefused("no-document", f"{named} holds no PDF, so nothing on it has a place")
    gen = generation(result)
    asked = set(pages) if pages else None
    out: list[dict[str, Any]] = []
    for ra in sorted(Records(root).resolved(result), key=lambda r: r.annotation.created):
        a = ra.annotation
        if ra.work != ref or ra.detached:
            continue
        page = ra.page or a.page or (a.anchor.page if a.anchor else None)
        if not page or (asked is not None and page not in asked):
            continue
        rects = rects_of(result, ra)
        if rects:
            out.append({"annotation": a.id, "page": page, "rects": rects})
    out.sort(key=lambda p: p["page"])
    return Places(node.pdf, gen, out)
