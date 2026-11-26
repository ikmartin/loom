"""Where a stored paper's annotations stand on its pages (`library.places`): each placed as it stands now, made when asked for, read again from the cache, and seen to change when the annotations do."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from loom.library.places import PlacesRefused, places
from loom.library.store import read
from loom.records import log
from loom.records.marks import lines_of
from loom.records.store import Records
from loom.refs.pages import pages_home
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import showcase

pytestmark = pytest.mark.poppler

#: The showcase's work whose PDF carries notes of every kind: text anchors, a box, marks that record their own place, one detached, and notes on the whole work.
BELLAMY = "sh-0403-ref"


def _resolved(q: Path) -> tuple[Any, list[Any]]:
    result = scan(load_quilt(q))
    return result, [ra for ra in Records(q).resolved(result) if ra.work == BELLAMY]


def _page(ra: Any) -> int | None:
    a = ra.annotation
    return ra.page or a.page or (a.anchor.page if a.anchor else None)


def test_each_annotation_on_a_work_s_pdf_is_placed_as_it_stands(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    result, on_work = _resolved(q)
    got = places(result, BELLAMY)
    by = {p["annotation"]: p for p in got.places}
    node = read(q, BELLAMY)
    assert node is not None and got.pdf == node.pdf
    pdf = q / ".loom" / "library" / "documents" / f"{node.pdf.removeprefix('sha256:')}.pdf"
    text = next(
        ra
        for ra in on_work
        if ra.annotation.anchor and ra.annotation.anchor.basis == "text" and not ra.detached and not ra.refound
    )
    quote = text.annotation.selector.exact
    assert by[text.annotation.id]["rects"] == lines_of(pdf, _page(text), quote, pages_home(q, node.pdf)), (
        "a text anchor: its words among its page's word boxes"
    )
    box = next(ra for ra in on_work if ra.annotation.anchor and ra.annotation.anchor.basis == "box")
    assert by[box.annotation.id]["rects"] == (box.rects or box.annotation.anchor.quads), "a box: its record"
    mark = next(ra for ra in on_work if ra.annotation.anchor is None and ra.annotation.rects and not ra.detached)
    assert by[mark.annotation.id]["rects"] == (mark.rects or mark.annotation.rects), (
        "a mark: where it records it stands"
    )
    nowhere = [ra.annotation.id for ra in on_work if ra.detached or not _page(ra)]
    assert nowhere and not set(nowhere) & set(by), "a detached note, and a note on the whole work, stand nowhere"
    assert [p["page"] for p in got.places] == sorted(p["page"] for p in got.places)
    assert all(len(r) == 4 for p in got.places for r in p["rects"])


def test_the_pages_asked_for_are_the_pages_answered(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    result, _ = _resolved(q)
    everything = places(result, BELLAMY).places
    two = places(result, BELLAMY, [2]).places
    assert two and {p["page"] for p in two} == {2} and two == [p for p in everything if p["page"] == 2]


def test_a_page_asked_for_again_reads_no_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The word boxes of a page are kept by the PDF's hash the first time; every later ask reads them there."""
    from loom.refs import pages

    q = showcase(tmp_path)
    result, _ = _resolved(q)
    first = places(result, BELLAMY).places

    def no_pdf(args: list[str]) -> str:
        raise AssertionError(f"read the PDF again: {args}")

    monkeypatch.setattr(pages, "_pdftotext", no_pdf)
    assert places(result, BELLAMY).places == first


def test_an_annotation_taken_out_is_gone_from_the_next_answer_and_the_generation_moves(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    result, _ = _resolved(q)
    before = places(result, BELLAMY)
    assert places(result, BELLAMY).gen == before.gen, "nothing changed"
    gone = before.places[0]["annotation"]
    log.delete(q, [gone])
    after = places(scan(load_quilt(q)), BELLAMY)
    assert gone not in {p["annotation"] for p in after.places} and after.gen > before.gen


def test_a_work_with_no_pdf_and_no_work_are_refused(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    result, _ = _resolved(q)
    with pytest.raises(PlacesRefused) as no_pdf:
        places(result, "sh-0404-ref")
    assert (no_pdf.value.code, no_pdf.value.status) == ("no-document", 409) and "Cortez 2007" in no_pdf.value.message
    with pytest.raises(PlacesRefused) as none:
        places(result, "sh-0ZZZ-ref")
    assert (none.value.code, none.value.status) == ("no-such-ref", 404)
