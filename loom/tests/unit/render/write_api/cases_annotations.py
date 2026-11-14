"""The cases of the endpoints for annotations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import the
from tests.unit.render._serve import get, log
from tests.unit.render.write_api._cases import (
    WHO,
    Serve,
    case,
    events,
    noted,
    on_demo,
    refuses,
    succeeds,
    with_paper,
)


@case("annotations-take")
def _annotations_take(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q = with_paper(serve, tmp_path)
    items = [
        {"page": 1, "mark": "pin", "rects": [[50, 50, 66, 66]], "body": "a sticky note"},
        {"page": 1, "mark": "pin"},
    ]
    done = succeeds(s, "annotations-take", {"target": "notes/paper.pdf", "items": items, "author": WHO})
    assert (done["taken"], done["already"], done["skipped"]) == (1, 0, 1)
    again = succeeds(s, "annotations-take", {"target": "notes/paper.pdf", "items": items, "author": WHO})
    assert (again["taken"], again["already"]) == (0, 1)
    refuses(s, "annotations-take", {"target": "dm-0003", "items": items, "author": WHO}, 400, "not-a-pdf", "not a PDF")
    refuses(s, "annotations-take", {"target": "notes/paper.pdf", "author": WHO}, 400, "missing-field", "items")


@case("annotate")
def _annotate(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    ann = noted(s, q, sid)
    assert "session" not in the(events(q, ann), lambda e: True, "event")  # a session sent with it is ignored
    # an annotation belongs to no session, so a write that names none is written
    succeeds(s, "annotate", {"target": "dm-0003", "message": "Named no session.", "type": "note", "author": WHO})
    refuses(
        s,
        "annotate",
        {"session": sid, "target": "nope-9999", "message": "x", "author": WHO},
        404,
        "no-such-node",
        "no such key",
    )


@case("reply")
def _reply(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    ann = noted(s, q, sid)
    succeeds(s, "reply", {"session": sid, "annotation": ann, "message": "Answered.", "author": WHO})
    reply = the(log(q), lambda e: e["event"] == "replied", "reply")
    assert (reply["reply_to"], reply["body"], "session" in reply) == (ann, "Answered.", False), reply
    refuses(s, "reply", {"session": sid, "message": "to nothing"}, 400, "missing-field", "annotation is required")


@case("resolve")
def _resolve(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    note = noted(s, q, sid)
    refuses(s, "resolve", {"session": sid, "annotation": note, "author": WHO}, 400, "bad-request", "nothing to resolve")
    ann = noted(s, q, sid, "A question to answer.", type_id="question")
    said = succeeds(s, "resolve", {"session": sid, "annotation": ann, "message": "Fixed.", "author": WHO})
    assert said["result"] == f"resolved {ann}"
    # the undo is another event, and puts it back
    said = succeeds(s, "resolve", {"session": sid, "annotation": ann, "undo": True, "author": WHO})
    assert said["result"] == f"reopened {ann}"
    assert [(e["event"], e.get("body"), e.get("undo")) for e in events(q, ann)[1:]] == [
        ("resolved", "Fixed.", None),
        ("resolved", "", True),
    ]
    missing = "a-1999-01-01-ekn992"
    refuses(
        s,
        "resolve",
        {"session": sid, "annotation": missing, "author": WHO},
        404,
        "no-such-annotation",
        f"no annotation {missing}",
    )


@case("edit")
def _edit(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    ann = noted(s, q, sid, type_id="revision")
    succeeds(s, "edit", {"session": sid, "annotation": ann, "message": "Restated.", "author": WHO})
    edited = events(q, ann)[-1]
    assert (edited["event"], edited["body"]) == ("edited", "Restated."), edited
    # restyled and retyped: a null type takes it off, and the look set on it stays
    succeeds(s, "edit", {"session": sid, "annotation": ann, "type": None, "look": {"style": "strike"}, "author": WHO})
    edited = events(q, ann)[-1]
    assert (edited["type"], edited["look"], edited["drawn"]["style"]) == (None, {"style": "strike"}, "strike"), edited
    # a null look drops the look set on it, so it is drawn in its type's and follows a later edit to the type
    succeeds(s, "edit", {"session": sid, "annotation": ann, "type": "question", "look": None, "author": WHO})
    edited = events(q, ann)[-1]
    assert (edited["type"], edited["look"], edited["drawn"]["color"]) == ("question", {}, "blue"), edited
    refuses(
        s, "edit", {"session": sid, "annotation": ann, "look": "red", "author": WHO}, 400, "bad-field", "look must be"
    )
    missing = "a-1999-01-01-ekn992"
    refuses(
        s,
        "edit",
        {"session": sid, "annotation": missing, "message": "x", "author": WHO},
        404,
        "no-such-annotation",
        missing,
    )


@case("delete")
def _delete(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    mine = noted(s, q, sid)
    # an agent deletes only its own annotations, whatever surface it posts through
    refuses(
        s,
        "delete",
        {"session": sid, "annotation": mine, "author": "Referee Agent"},
        400,
        "refused",
        "deletes only its own annotations",
    )
    said = succeeds(s, "delete", {"session": sid, "annotation": mine, "author": WHO})
    assert said["result"] == f"deleted {mine}" and [e["event"] for e in said["removed"]] == ["created"]
    assert events(q, mine) == []
    refuses(s, "delete", {"author": WHO}, 400, "missing-field", "annotation is required")


@case("restore")
def _restore(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    ann = noted(s, q, sid, "A question.", type_id="question")
    succeeds(s, "reply", {"session": sid, "annotation": ann, "message": "Answered.", "author": WHO})
    before = log(q)
    removed = succeeds(s, "delete", {"session": sid, "annotation": ann, "author": WHO})["removed"]
    # the viewer's undo of a delete: what it removed goes back, reply and all
    said = succeeds(s, "restore", {"session": sid, "events": removed, "author": WHO})
    assert said["result"].startswith(f"restored {ann}")
    assert sorted(map(json.dumps, log(q))) == sorted(map(json.dumps, before))
    refuses(s, "restore", {"session": sid, "events": removed, "author": WHO}, 400, "refused", "in the log already")
    refuses(s, "restore", {"session": sid, "events": [{"event": "liked"}], "author": WHO}, 400, "bad-field", "events")


@case("types-save")
def _types_save(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.records.types import default_text, load_types

    s, q, _ = on_demo(serve, tmp_path)
    look = {"color": "green", "style": "underline", "weight": 2, "opacity": 60}
    given = [
        {"name": "Citation \\cite", **look, "open": False, "notes": True, "instructions": 'Use \\cite{x} and """.'},
        {"id": "revision", "name": "Must change", **look, "color": "red", "open": True, "notes": False},
    ]
    said = succeeds(s, "types-save", {"types": given})
    assert said["result"] == "saved 2 annotation types"
    # in the order given, an id drawn from the name where none was, every field as sent
    assert [(t["id"], t["name"]) for t in said["types"]] == [
        ("citation-cite", "Citation \\cite"),
        ("revision", "Must change"),
    ]
    assert said["types"][0]["instructions"] == 'Use \\cite{x} and """.' and said["types"][0]["look"] == look
    text = (q / ".loom" / "annotation-types.toml").read_text(encoding="utf-8")
    assert text.startswith(default_text().split("\n[[type]]", 1)[0])
    assert [t.id for t in load_types(q).types] == ["citation-cite", "revision"]
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert [t["id"] for t in manifest["annotation_types"]] == ["citation-cite", "revision"]
    # a refusal names the type, and writes nothing
    for body, match in (
        ({"types": [{**given[1], "name": " "}]}, "type 1 has no name"),
        ({"types": [given[1], {**given[1], "id": None}]}, "type 'Must change' is named twice"),
        ({"types": [{**given[1], "color": "mauve"}]}, "type 'Must change'"),
        ({"types": [{**given[1], "weight": None}]}, "type 'Must change' has no weight"),
        ({"types": [{**given[1], "id": "Bad id"}]}, "its id is lowercase"),
    ):
        refuses(s, "types-save", body, 400, "bad-field", match)
    assert (q / ".loom" / "annotation-types.toml").read_text(encoding="utf-8") == text
    # the plain look is saved with the types when sent, and kept when not
    plain = {"color": "green", "style": "underline", "weight": 1, "opacity": 100}
    assert succeeds(s, "types-save", {"types": given, "plain": plain})["plain"] == plain
    assert load_types(q).plain.to_dict() == plain
    assert succeeds(s, "types-save", {"types": given})["plain"] == plain
    assert json.loads(get(s.url + "build/manifest.json")[2])["annotation_plain"] == plain
    refuses(s, "types-save", {"types": given, "plain": {**plain, "color": "mauve"}}, 400, "bad-field", "the plain look")
    refuses(s, "types-save", {"types": given, "plain": "green"}, 400, "bad-field", "plain is a look")
    refuses(s, "types-save", {}, 400, "missing-field", "types is the list")
    refuses(s, "types-save", {"defaults": True, "author": "Referee (Agent)"}, 403, "author-only", "only the author")
    said = succeeds(s, "types-save", {"defaults": True})
    assert said["result"] == "restored the default annotation types"
    assert (q / ".loom" / "annotation-types.toml").read_text(encoding="utf-8") == default_text()
