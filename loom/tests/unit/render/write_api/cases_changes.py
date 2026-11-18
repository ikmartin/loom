"""The cases of the endpoints for changes and history."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit._quilts import track_edits
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    WHO,
    Serve,
    case,
    filed,
    on_demo,
    refuses,
    succeeds,
    synthetic,
)


@case("compare")
def _compare(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, root = synthetic(serve, tmp_path)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if "cache" not in p.parts)
    said = succeeds(s, "compare", {"left": "drafting/main.tex", "right": ".loom/agents/copies/aidoc.tex"})
    pairs = {p["pair"]: p for p in said["pairs"]}
    assert pairs["sy-0002"]["base"] == "left" and pairs["sy-0001"]["base"] == "both", pairs
    # the renderings are served from the build directory, and nothing outside it moved
    raw = get(s.url + "build/" + pairs["sy-0002"]["right"]["fragment"])[2]
    assert b"review-changed" in raw
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if "cache" not in p.parts) == before
    refuses(s, "compare", {"left": "drafting/main.tex", "right": "nowhere-v9"}, 404, "unknown-item", "nowhere-v9")


@case("history-record")
def _history_record(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt, save_author

    save_author("Tester")
    s, q, _ = on_demo(serve, tmp_path)
    assert succeeds(s, "history-record", {"document": "drafting/main.tex", "name": "Before referee"})["result"] == (
        "kept this version of main.tex as “Before referee”"
    )
    newest = load_history(load_quilt(q).history_dir).landmarks()[-1]
    assert newest.message == "Before referee" and newest.get("in") == "drafting/main.tex" and newest.get("files")
    refuses(
        s,
        "history-record",
        {"document": "drafting/main.tex", "name": "Before referee"},
        409,
        "name-in-use",
        "kept already",
    )
    refuses(s, "history-record", {"document": "drafting/main.tex", "name": " "}, 400, "bad-field", "needs a name")
    refuses(s, "history-record", {"document": "README.md", "name": "x"}, 400, "bad-field", "not one of your documents")
    agent = {"document": "drafting/main.tex", "name": "y", "author": "Referee (Agent)"}
    refuses(s, "history-record", agent, 403, "author-only", "only the author records")


@case("change-keep")
def _change_keep(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.scan.quilt import save_author

    s, q, _sid = on_demo(serve, tmp_path)
    save_author(WHO)
    track_edits(q)
    # before a first look, keeping all takes one
    assert succeeds(s, "change-keep", {"all": True})["result"] == "took your first look"
    lemma = q / "drafting" / "nodes" / "dm-0002.tex"
    lemma.write_text(lemma.read_text().replace("Every orbit", "Each orbit"))
    edit = filed(q, "--quote", "one or two points", "--with", "at most two points")
    s.rebuild()
    pending = {c["id"]: c for c in json.loads(get(s.url + "build/manifest.json")[2])["changes"]}
    (inplace,) = [i for i, c in pending.items() if c["kind"] == "edit"]
    refuses(s, "change-keep", {"changes": [inplace], "author": "Claude Agent"}, 403, "author-only", "only the author")
    refuses(s, "change-keep", {"changes": ["c-00000000"]}, 404, "no-such-change", "no change c-00000000")
    refuses(s, "change-keep", {}, 400, "missing-field", "changes is the list")
    said = succeeds(s, "change-keep", {"changes": [inplace, edit]})
    assert said["done"] == [inplace, edit] and said["refused"] == [] and said["result"].startswith("kept 2 changes; ")
    assert "at most two points" in lemma.read_text() and "Each orbit" in lemma.read_text()
    s.rebuild()
    left = [c["id"] for c in json.loads(get(s.url + "build/manifest.json")[2])["changes"]]
    assert inplace not in left and edit not in left


@case("change-discard")
def _change_discard(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.scan.quilt import save_author

    s, q, _sid = on_demo(serve, tmp_path)
    save_author(WHO)
    track_edits(q)
    succeeds(s, "change-keep", {"all": True})
    lemma = q / "drafting" / "nodes" / "dm-0002.tex"
    lemma.write_text(lemma.read_text().replace("Every orbit", "Each orbit"))
    edit = filed(q, "--quote", "one or two points", "--with", "at most two points", who="Referee Agent")
    s.rebuild()
    pending = [c for c in json.loads(get(s.url + "build/manifest.json")[2])["changes"] if c["kind"] == "edit"]
    refuses(s, "change-discard", {"changes": [edit], "author": "Referee Agent"}, 403, "author-only", "only the author")
    said = succeeds(s, "change-discard", {"changes": [pending[0]["id"], edit], "why": "not needed"})
    assert said["done"] == [pending[0]["id"], edit] and "Every orbit" in lemma.read_text()
    # the viewer's undo opens a discarded suggested edit again; an in-place change comes back from History
    assert succeeds(s, "change-discard", {"changes": [edit], "undo": True})["done"] == [edit]
    refuses(s, "change-discard", {"changes": ["c-00000000"], "undo": True}, 404, "no-such-change", "from History")


@case("history-restore")
def _history_restore(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt, save_author

    save_author("Tester")
    s, q, _ = on_demo(serve, tmp_path)
    track_edits(q)
    main = q / "drafting" / "main.tex"
    before = main.read_text()
    succeeds(s, "history-record", {"document": "drafting/main.tex", "name": "First"})
    main.write_text(before.replace("\\begin{document}", "\\begin{document}\nAn edit.\n"), encoding="utf-8")
    history = load_history(load_quilt(q).history_dir)
    first = history.landmark_path(history.landmark("main-first")).relative_to(q).as_posix()
    said = succeeds(s, "history-restore", {"document": "drafting/main.tex", "version": first})["result"]
    assert said.startswith(
        "put main.tex back as “First” holds it; its text before is the version “Before restoring “First””"
    )
    assert main.read_text() == before
    refuses(
        s,
        "history-restore",
        {"document": "drafting/main.tex", "version": "nowhere"},
        404,
        "unknown-version",
        "not a version",
    )
    agent = {"document": "drafting/main.tex", "version": first, "author": "Referee (Agent)"}
    refuses(s, "history-restore", agent, 403, "author-only", "only the author")
    # the text an undo set aside goes back into its file, the file's text now kept first
    from loom.pending import in_place
    from loom.scan.scan import scan

    succeeds(s, "change-keep", {"all": True})
    (q / "README.md").write_text("an edit undone\n", encoding="utf-8")
    ids = [c.id for c in in_place(scan(load_quilt(q))) if c.path == "README.md"]
    succeeds(s, "change-discard", {"changes": ids})
    undone = [e for e in load_history(load_quilt(q).history_dir).entries if e.action == "undo"][-1]
    succeeds(s, "history-restore", {"path": "README.md", "text": undone.get("from")})
    assert (q / "README.md").read_text() == "an edit undone\n"
    outside = {"path": "../outside.md", "text": undone.get("from")}
    refuses(s, "history-restore", outside, 409, "outside-quilt", "outside the quilt")
    assert not (q.parent / "outside.md").exists()
