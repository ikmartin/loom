"""Notes on a work and on a page of its PDF (plan 0.13 item 2): the target is the work's reference, named by its id or the key its entry has, and a place on a page is mapped against the page text and word boxes loom derives from the PDF the reference holds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import ok, refused, the
from tests.unit._quilts import open_session, showcase


def _ref(q: Path, key: str) -> str:
    """The reference whose entry has `key`."""
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    return scan(load_quilt(q)).refs[key]


def _page_text(q: Path, key: str, page: int) -> str:
    """The text loom derived from page `page` of the PDF the reference `key` holds."""
    from loom.library.store import read
    from loom.refs.pages import mapped, read_page

    node = read(q, _ref(q, key))
    assert node is not None and node.pdf
    home = mapped(q, node.pdf)
    assert home is not None
    return read_page(home, page) or ""


def _log(q: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (q / ".loom/records/annotations/log.jsonl").read_text().splitlines()]


@pytest.mark.poppler
def test_a_selection_on_a_real_page_becomes_an_anchor(tmp_path: Path) -> None:
    """What a reader selected, mapped against the page text and the word boxes of the PDF Bellamy19's reference holds; on a copy, because reading a page caches its text and boxes inside the quilt."""
    from loom.render.api import handle

    q = showcase(tmp_path)
    text = "The median orders of a weighted digraph are in bijection with the vertices"
    got = handle(q, "locate", {"ref": "Bellamy19", "page": 2, "text": text})
    a = got["anchor"]
    assert a["basis"] == "text" and a["page"] == 2 and a["quads"], got["result"]
    assert _page_text(q, "Bellamy19", 2)[a["start"] : a["end"]] == text
    assert got["page_box"] == {"width": 612.0, "height": 792.0}  # US Letter, in points
    # the reference's id names it as well as its key does
    assert handle(q, "locate", {"ref": _ref(q, "Bellamy19"), "page": 2, "text": text})["anchor"] == a

    # a region the reader drew: geometry of record, and the words under it as an unreliable hint
    box = handle(q, "locate", {"ref": "Bellamy19", "page": 2, "rects": [[82.0, 278.0, 530.0, 292.0]]})
    assert box["anchor"]["basis"] == "box" and "start" not in box["anchor"]
    assert "quasi-polynomial" in box["text"]


def test_locate_refuses_what_it_cannot_answer(tmp_path: Path) -> None:
    """The endpoint writes nothing, so its whole contract is the answer and the refusals: a work the library lacks, a work holding no PDF, and a request that selected neither text nor a region."""
    from loom.render.api import ApiError, handle

    q = showcase(tmp_path)
    for body, code in (
        ({"ref": "Nope", "page": 1, "text": "x"}, "no-such-ref"),
        ({"ref": "Bellamy19", "page": 1}, "missing-field"),
        ({"ref": "Bellamy19", "page": 0, "text": "x"}, "bad-field"),
        ({"ref": "Stacks", "page": 1, "text": "x"}, "not-readable"),
    ):
        with pytest.raises(ApiError) as exc:
            handle(q, "locate", body)
        assert exc.value.code == code, body


@pytest.mark.poppler
def test_quoted_words_on_a_project_pdf_are_found_on_their_page_or_the_first_that_holds_them(tmp_path: Path) -> None:
    """`locate` with `file`: what a `quilt:` link's quoted words on a project PDF light, found as a mark's words are; refused for a file the viewer does not show, and for words on no page."""
    from loom.render.api import ApiError, handle
    from tests.unit._pdfs import PROSE, lines_pdf

    q = showcase(tmp_path)
    lines_pdf(q / "papers/median.pdf", [["Nothing here."], PROSE])
    lines_pdf(q / ".hidden/secret.pdf", [PROSE])
    on = handle(q, "locate", {"file": "papers/median.pdf", "page": 2, "text": "incidence  matrix"})
    assert on["page"] == 2 and len(on["anchor"]["quads"]) == 1
    anywhere = handle(q, "locate", {"file": "papers/median.pdf", "text": "totally unimodular"})
    assert anywhere["page"] == 2 and anywhere["anchor"]["quads"]
    for body, code in (
        ({"file": "papers/median.pdf", "text": "not in it at all"}, "not-found"),
        ({"file": "papers/median.pdf", "page": 1, "text": "incidence matrix"}, "not-found"),
        ({"file": ".hidden/secret.pdf", "text": "incidence matrix"}, "no-such-file"),
        ({"file": "../outside.pdf", "text": "x"}, "no-such-file"),
        ({"file": "papers/median.pdf"}, "missing-field"),
        ({"file": "papers/median.pdf", "page": 0, "text": "x"}, "bad-field"),
    ):
        with pytest.raises(ApiError) as exc:
            handle(q, "locate", body)
        assert exc.value.code == code, body


@pytest.mark.poppler
def test_a_note_on_a_page_is_written_by_reference_or_key_and_refused_legibly(tmp_path: Path) -> None:
    """`loom annotate` on a work's page: the target may be the key the agent knows or the reference's id, and the record stores the reference's id and the PDF's hash. Text is mapped with the word boxes' tolerance and recorded with offsets; a box is recorded as drawn. Each way of getting it wrong says what to do instead."""
    q = showcase(tmp_path)
    ref = _ref(q, "Bellamy19")
    who = ("--as", "A. Author")
    said = ok(
        "annotate", "Bellamy19", "Is this needed?", "--page", "2", "--quote", "totally unimodular",
        "--type", "question", *who, cwd=q,
    )  # fmt: skip
    assert f"{ref} p.2 (text)  question" in said.output, said.output
    drawn = ok(
        "annotate", "Bellamy19", "the polytope", "--page", "2", "--box", "82,278,529,316", "--type", "note", *who, cwd=q
    )
    assert "p.2 (box)  note" in drawn.output, drawn.output
    ok("annotate", ref, "by its reference", "--page", "2", "--quote", "Boundedness holds", *who, cwd=q)

    text, box, by_ref = _log(q)[-3:]  # appended in order, after the showcase's own
    assert text["target"] == ref and text["against"].startswith("sha256:")
    page_text = _page_text(q, "Bellamy19", 2)
    assert (
        text["anchor"]["basis"] == "text"
        and page_text[text["anchor"]["start"] : text["anchor"]["end"]] == "totally unimodular"
    )
    assert (
        text["anchor"]["exact"] == "totally unimodular" and text["anchor"]["prefix"] and "quads" not in text["anchor"]
    )
    assert box["anchor"]["basis"] == "box" and box["anchor"]["quads"] == [[82.0, 278.0, 529.0, 316.0]]
    assert "quasi-polynomial" in box["anchor"]["exact"]  # the words under the rectangle, as a hint
    assert by_ref["target"] == ref  # the key and the reference's id name one work

    # the refusals, each naming what to do
    refused("annotate", "Bellamy19", "no page", "--quote", "x", *who, code=2, match="say which page", cwd=q)
    refused(
        "annotate", "sh-0003", "page on a key", "--page", "2", "--quote", "x", *who,
        code=2, match="is a key in this quilt", cwd=q,
    )  # fmt: skip
    refused("annotate", "Nobody99", "unknown", "--page", "2", "--quote", "x", *who, code=2, match="names none", cwd=q)
    refused(
        "annotate", "Bellamy19", "both", "--page", "2", "--quote", "x", "--box", "1,2,3,4", *who,
        code=2, match="not both", cwd=q,
    )  # fmt: skip
    refused(
        "annotate", "Bellamy19", "absent", "--page", "2", "--quote", "zebra crossing", *who,
        code=1, match="is not on", cwd=q,
    )  # fmt: skip
    refused(
        "annotate", "Bellamy19", "bad box", "--page", "2", "--box", "1,2,3", *who, code=2, match="x0,y0,x1,y1", cwd=q
    )
    refused(
        "annotate",
        "Stacks",
        "no PDF",
        "--page",
        "1",
        "--quote",
        "x",
        *who,
        code=1,
        match="holds no readable PDF",
        cwd=q,
    )

    # a batch line carries the same two keys
    batched = ok(
        "annotate", "--batch", "--as", "A. Author", "--quilt", str(q),
        stdin='{"target":"Bellamy19","message":"batched","page":2,"box":"82,278,529,316","type":"note"}\n',
    )  # fmt: skip
    assert "(box)  note" in batched.output, batched.output


def test_a_note_on_a_whole_work_names_its_reference(tmp_path: Path) -> None:
    """With no page, a note is on the whole work: its target is the reference's id, however the work was named."""
    q = showcase(tmp_path)
    ok("annotate", "Arden24", "Read before Section 3.", "--type", "note", "--as", "A. Author", cwd=q)
    event = _log(q)[-1]
    assert event["target"] == _ref(q, "Arden24") and event["anchor"] is None


@pytest.mark.poppler
def test_the_endpoint_and_the_record_map_a_place_the_same_way(tmp_path: Path) -> None:
    """`locate` answers and writes nothing; `annotate` writes. Both call `anchor_on_page`, so what the viewer previewed is what the log says."""
    from loom.render.api import handle

    q = showcase(tmp_path)
    text = "the constraint matrix is an incidence matrix"
    preview = handle(q, "locate", {"ref": "Bellamy19", "page": 2, "text": text})["anchor"]
    written = handle(
        q,
        "annotate",
        {
            "session": open_session(q),
            "target": "Bellamy19",
            "message": "so it is integral",
            "page": 2,
            "quote": text,
            "type": "note",
            "author": "A. Author",
        },
    )
    assert written["ok"], written
    event = _log(q)[-1]
    recorded = {k: v for k, v in event["anchor"].items() if k not in ("exact", "prefix", "suffix")}
    # the preview carries derived quads so the viewer can draw before anything is written; the record does not
    assert recorded == {k: v for k, v in preview.items() if k != "quads"}
    drawn = handle(
        q,
        "annotate",
        {
            "session": open_session(q),
            "target": "Bellamy19",
            "message": "that display",
            "page": 2,
            "rects": [[82, 278, 529, 316]],
            "type": "note",
            "author": "A. Author",
        },
    )
    assert drawn["ok"] and "(box)" in drawn["result"], drawn


@pytest.mark.poppler
def test_a_locator_by_offsets_lights_the_same_place_a_selection_would(tmp_path: Path) -> None:
    """`span=A-B` names the page text by offsets; `locate` maps it to the rectangles a selection of that text would get, so a link and a selection light one place."""
    from loom.render.api import handle

    q = showcase(tmp_path)
    a = _page_text(q, "Bellamy19", 2).index("totally unimodular")
    by_span = handle(q, "locate", {"ref": "Bellamy19", "page": 2, "span": [a, a + len("totally unimodular")]})
    by_text = handle(q, "locate", {"ref": "Bellamy19", "page": 2, "text": "totally unimodular"})
    assert by_span["ok"] and by_span["anchor"]["quads"] == by_text["anchor"]["quads"]
    assert by_span["anchor"]["start"] == a and by_span["text"] == "totally unimodular"


@pytest.mark.poppler
def test_a_change_carries_an_address_its_reader_can_use(tmp_path: Path) -> None:
    """A page note travels with the work's reference and its page, so an agent given the changed-annotation block reads the paper and the page, not an address it must decode."""
    from loom.mailbox import pending, render
    from loom.sessions import create, sessions

    q = showcase(tmp_path)
    ref = _ref(q, "Bellamy19")
    sid = create(q, "reading", "A. Author").id
    ok(
        "annotate", "Bellamy19", "why unimodular?", "--page", "2", "--quote", "totally unimodular",
        "--type", "question", "--as", "A. Author", cwd=q,
    )  # fmt: skip
    ok("annotate", "sh-0003", "and one on a key, which has no work", "--type", "note", "--as", "A. Author", cwd=q)

    changed = pending(q, sessions(q)[sid], "A. Author")
    page_note = the(changed, lambda c: bool(c["page"]), "change on a page")
    assert page_note["work"] == ref and page_note["page"] == 2 and page_note["target"] == ref
    on_key = the(changed, lambda c: not c["page"], "change on a key")
    assert on_key["work"] is None and on_key["target"] == "sh-0003"
    said = render(
        [type("E", (), {"who": "A. Author", "when": "now", "kind": "message", "body": "look", "changed": changed})()]
    )
    assert f"{ref} p.2" in said, said


@pytest.mark.poppler
def test_a_mark_on_a_work_with_its_source_is_published_with_where_its_words_stand_there(tmp_path: Path) -> None:
    """Arden24's reference holds its LaTeX: a mark on its page is aligned to it when the manifest is published, as a LaTeX anchor's span in the unpacked source, and the record carries none of it."""
    from loom.cli._quilt import open_scan
    from loom.records.store import Records

    q = showcase(tmp_path)
    quote = "a saturated sublattice of the lattice of weightings"
    ok("annotate", "Arden24", "Why saturated?", "--page", "2", "--quote", quote, "--as", "A. Author", cwd=q)
    event = _log(q)[-1]
    assert "source" not in event and "source" not in event["anchor"]
    result = open_scan(str(q))
    manifest: dict[str, Any] = {"nodes": {}, "keys": {}, "diagnostics": []}
    Records(q, result.quilt.history_dir).apply(result, manifest)
    source = manifest["annotations"][event["id"]]["source"]
    assert source["path"].startswith(".loom/cache/library/sources/") and source["exact"] == quote
    assert source["path"].endswith(".tex")
    data = (q / source["path"]).read_bytes()
    assert data[source["bytes"][0] : source["bytes"][1]].decode() == quote
    # a work with only a PDF has none
    ok("annotate", "Bellamy19", "Why?", "--page", "2", "--quote", "totally unimodular", "--as", "A. Author", cwd=q)
    bellamy = _log(q)[-1]["id"]
    result = open_scan(str(q))
    Records(q, result.quilt.history_dir).apply(result, manifest)
    assert manifest["annotations"][bellamy]["source"] is None
