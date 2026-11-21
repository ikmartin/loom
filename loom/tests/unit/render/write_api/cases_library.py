"""The cases of the library's endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loom.render.serve import ServeSession
from tests.unit._quilts import showcase
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    Serve,
    case,
    on_demo,
    refuses,
    succeeds,
)


@case("locate")
def _locate(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s = serve(showcase(tmp_path))
    builds = s.builds
    text = "The median orders of a weighted digraph are in bijection with the vertices"
    said = succeeds(s, "locate", {"ref": "Bellamy19", "page": 2, "text": text})
    assert said["anchor"]["basis"] == "text" and said["anchor"]["page"] == 2 and said["text"] == text, said
    # a quote with no page: the page that holds it
    found = succeeds(s, "locate", {"ref": "Bellamy19", "text": text})
    assert found["page"] == 2 and found["anchor"]["page"] == 2, found
    # a read publishes nothing: the viewer asks again on each new manifest, so a rebuild after it would have it ask for ever
    assert s.builds == builds
    refuses(s, "locate", {"ref": "Nope", "page": 1, "text": "x"}, 404, "no-such-ref", "Nope")
    refuses(
        s,
        "locate",
        {"ref": "Bellamy19", "text": "words on no page of it"},
        404,
        "not-found",
        "no page of Bellamy19",
    )


def _received(q: Path, name: str, *lines: str) -> str:
    """A file received as the viewer streams one, through the intake's own function; the drop's id."""
    import io

    from loom.library.intake import receive

    data = ("%PDF-1.4\n%FAKE-LOOM\n%%Pages: 1\n" + "\n".join(lines) + "\n").encode()
    return str(receive(q, name, io.BytesIO(data), len(data))["incoming"])


def _library_files(q: Path) -> dict[str, bytes]:
    """Every file of the library's nodes, its documents and its drops, with its bytes."""
    return {
        p.relative_to(q).as_posix(): p.read_bytes()
        for d in (
            q / ".loom" / "library" / "nodes",
            q / ".loom" / "library" / "documents",
            q / ".loom" / "local" / "incoming",
        )
        if d.is_dir()
        for p in sorted(d.rglob("*"))
        if p.is_file()
    }


ENTRY = "@article{Ost18,\n  author = {Ostrander, D.},\n  title = {Widget categories and their duals},\n  year = {2018},\n  journal = {J. Widget Theory}\n}"
PULLBACKS = ("arXiv:0805.2065v2", "Virtual pull-backs", "Cristina Manolache")
MAN12 = "@article{Man12,\n  author = {Manolache, Cristina},\n  title = {Virtual pull-backs},\n  year = {2012},\n  eprint = {0805.2065},\n}\n"


def _pasted(s: ServeSession, text: str) -> str:
    """A work made by pasting its entry; its reference."""
    return str(succeeds(s, "library-take", {"items": [{"text": text}]})["rows"][0]["ref"])


def _stream(s: ServeSession, name: str, data: bytes, *, token: str | None = None) -> tuple[int, Any]:
    """POST a file's bytes to `library-receive` as the viewer streams a drop: `application/octet-stream`, the token, the name in the query."""
    import urllib.error
    import urllib.parse
    import urllib.request

    if token is None:
        token = json.loads(get(s.url + "_api")[2])["token"]
    req = urllib.request.Request(
        s.url + "_api/library-receive?" + urllib.parse.urlencode({"name": name}),
        data=data,
        headers={"Content-Type": "application/octet-stream", "X-Loom-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@case("library-receive")
def _library_receive(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    builds = s.builds
    data = ("%PDF-1.4\n%FAKE-LOOM\n%%Pages: 1\nGadget towers\nA. Halberd\n" + "padding\n" * 300_000).encode()
    status, said = _stream(s, "Halberd - 2021 - Gadget towers.pdf", data)
    assert status == 200 and said["size"] == len(data) and said["name"] == "Halberd - 2021 - Gadget towers.pdf", said
    drop = q / ".loom" / "local" / "incoming" / said["incoming"]
    assert (drop / "document.pdf").read_bytes() == data
    assert json.loads((drop / "arrived.json").read_text())["name"] == "Halberd - 2021 - Gadget towers.pdf"
    # the same bytes again are the drop kept already, and receiving rebuilds nothing
    assert _stream(s, "again.pdf", data)[1]["incoming"] == said["incoming"]
    assert s.builds == builds
    assert succeeds(s, "library-take", {"items": [{"incoming": said["incoming"]}]})["rows"][0]["state"] == "added"
    # a .bib and a source are taken; bytes that are none of these are kept nowhere
    assert _stream(s, "refs.bib", b"@misc{x, title = {x}}\n")[0] == 200
    status, said = _stream(s, "notes.txt", b"plain text, not a document")
    assert (status, said["error"]["code"]) == (400, "not-a-document")
    assert _stream(s, "x.pdf", data, token="")[0] == 403
    refuses(s, "library-receive", {"name": "x.pdf"}, 400, "bad-request", "application/octet-stream")


@case("library-take")
def _library_take(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    new = _received(q, "Halberd - 2021 - Gadget towers.pdf", "Gadget towers", "A. Halberd")
    asked = _received(q, "pullbacks.pdf", *PULLBACKS)
    items = [{"incoming": new}, {"incoming": asked}, {"text": ENTRY}, {"text": "ISBN 978-3-16-148410-0"}]
    rows = succeeds(s, "library-take", {"items": items})["rows"]
    assert [r["state"] for r in rows] == ["added", "question", "added", "cannot"], rows
    assert rows[0]["short"] == "Gadget towers" and rows[0]["found_by"] == "title"
    assert [c["ref"] for c in rows[1]["candidates"]] == [man12] and rows[3]["code"] == "no-service"
    # the same file again is already here, and nothing is matched by its title
    assert succeeds(s, "library-take", {"items": [{"incoming": new}]})["rows"][0]["state"] == "here"
    refuses(s, "library-take", {"items": [{"incoming": "0" * 64}]}, 404, "no-such-incoming", "drop it again")
    refuses(s, "library-take", {"items": [{"incoming": asked, "for": "tq-0ZZZ-ref"}]}, 404, "no-such-work", "no work")
    refuses(s, "library-take", {"items": [{"name": "x"}]}, 400, "bad-field", "each item is")
    refuses(
        s,
        "library-take",
        {"items": [{"text": ENTRY}], "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author",
    )
    refuses(
        s, "library-take", {"items": [{"text": ENTRY}], "online": "yes"}, 400, "bad-field", "online is true or false"
    )
    config = q / "config.toml"
    config.write_text(config.read_text().replace("online = false", ""))
    refuses(s, "library-take", {"items": [{"incoming": asked}]}, 409, "network-unasked", "online false")
    # made again without the network: each work added names the identifier found, which its row offers to look up this once
    row = succeeds(s, "library-take", {"items": [{"text": "arXiv:2209.01234v2"}], "online": False})["rows"][0]
    assert (row["state"], row["unconfirmed"], row["identifier"]) == ("added", True, "arxiv:2209.01234v2"), row
    assert rows[0]["identifier"] is None, "a work found by its title alone states none"


@case("library-answer")
def _library_answer(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    asked = _received(q, "pullbacks.pdf", *PULLBACKS)
    question = succeeds(s, "library-take", {"items": [{"incoming": asked}]})["rows"][0]["question"]
    refuses(s, "library-answer", {"question": question, "same": "tq-0ZZZ-ref"}, 400, "not-a-candidate", "not one of")
    refuses(s, "library-answer", {"question": "q-000000000000", "same": None}, 404, "no-such-question", "no drop waits")
    refuses(s, "library-answer", {"question": question}, 400, "missing-field", "same is required")
    refuses(
        s,
        "library-answer",
        {"question": question, "same": man12, "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author",
    )
    row = succeeds(s, "library-answer", {"question": question, "same": man12})["row"]
    assert (row["state"], row["ref"], row["under"]) == ("added", man12, True), row


@case("library-undo")
def _library_undo(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    before = _library_files(q)
    drop = _received(q, "Halberd - 2021 - Gadget towers.pdf", "Gadget towers", "A. Halberd")
    row = succeeds(s, "library-take", {"items": [{"incoming": drop}]})["rows"][0]
    assert succeeds(s, "library-undo", {"id": row["id"], "act": row["act"]})["result"].endswith("taken out again")
    assert _library_files(q) == before
    refuses(s, "library-undo", {"id": "0" * 64}, 404, "no-such-intake", "names no drop")
    refuses(s, "library-undo", {"id": "../config"}, 404, "no-such-intake", "names no drop")
    refuses(s, "library-undo", {"id": drop, "author": "Referee (Agent)"}, 403, "author-only", "only the author")


@case("library-unfile")
def _library_unfile(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    drop = _received(q, "schedule.pdf", "Department of Mathematics", "Seminar schedule, spring")
    assert succeeds(s, "library-take", {"items": [{"incoming": drop, "for": man12}]})["rows"][0]["under"] is True
    filed = _library_files(q)
    said = succeeds(s, "library-unfile", {"ref": man12})
    assert said["incoming"] == drop and said["row"]["state"] == "cannot"
    refuses(s, "library-unfile", {"ref": man12}, 409, "no-document", "holds no pdf")
    refuses(s, "library-unfile", {"ref": "tq-0ZZZ-ref"}, 404, "no-such-work", "no work")
    refuses(s, "library-unfile", {"ref": man12, "which": "djvu"}, 400, "bad-field", "pdf or tex")
    succeeds(s, "library-undo", {"id": drop, "act": said["act"]})
    assert {k: v for k, v in _library_files(q).items() if "nodes/" in k} == {
        k: v for k, v in filed.items() if "nodes/" in k
    }


@case("library-works")
def _library_works(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    builds = s.builds
    said = succeeds(s, "library-works", {})
    assert said["works"], "the demo's cited works, gathered by its build"
    assert {
        "ref",
        "short",
        "title",
        "authors",
        "year",
        "holds",
        "digested",
        "used_in",
        "link",
        "version",
        "lookup",
        "cited_as",
    } <= set(said["works"][0])
    assert isinstance(said["gen"], int) and s.builds == builds
    # `since` while the generation stands: unchanged, and nothing else
    again = succeeds(s, "library-works", {"since": said["gen"]})
    assert {k: again[k] for k in ("gen", "unchanged")} == {
        "gen": said["gen"],
        "unchanged": True,
    } and "works" not in again
    # a work added moves it, and the list comes whole again
    _pasted(s, ENTRY)
    moved = succeeds(s, "library-works", {"since": said["gen"]})
    assert moved["gen"] > said["gen"] and len(moved["works"]) == len(said["works"]) + 1, moved
    refuses(s, "library-works", {"since": "41"}, 400, "bad-field", "since is the gen")
    # a build gathers an entry a document's bibliography gains; the list, a read, gathers nothing
    bib = q / "drafting" / "refs.bib"
    bib.write_text(
        bib.read_text(encoding="utf-8") + "\n@article{Gat25, title = {Gathered by a build}}\n", encoding="utf-8"
    )
    s.rebuild()
    assert "Gathered by a build" in {w["title"] for w in succeeds(s, "library-works", {})["works"]}


@case("library-look-up")
def _library_look_up(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    plain = _pasted(s, "@misc{Notes, title = {Notes with no identifier}}\n")
    refuses(s, "library-look-up", {"ref": man12}, 409, "offline", "needs the network")
    # the person's yes for this one look-up passes a quilt with the network off; `plain` states nothing to look up
    refuses(s, "library-look-up", {"ref": plain, "online": True}, 409, "no-identifier", "states no")
    refuses(s, "library-look-up", {"ref": man12, "online": False}, 409, "offline", "online true")
    config = q / "config.toml"
    config.write_text(config.read_text().replace("online = false", "online = true"))
    refuses(s, "library-look-up", {"ref": plain}, 409, "no-identifier", "states no")
    refuses(s, "library-look-up", {"ref": "tq-0ZZZ-ref"}, 404, "no-such-ref", "no work")
    refuses(s, "library-look-up", {"ref": man12, "author": "Referee (Agent)"}, 403, "author-only", "only the author")


@case("library-entry")
def _library_entry(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    succeeds(s, "library-entry", {"ref": man12, "bibtex": MAN12.replace("Virtual pull-backs", "Virtual pullbacks")})
    assert "Virtual pullbacks" in (q / ".loom/library/nodes" / f"{man12}.node").read_text()
    refuses(s, "library-entry", {"ref": man12, "bibtex": "not bibtex"}, 400, "bad-entry", "not a BibTeX entry")
    other = _pasted(s, ENTRY)
    # said of the work that holds the key, never of loom's files
    refuses(
        s,
        "library-entry",
        {"ref": other, "bibtex": "@article{man12, title = {x}}"},
        409,
        "key-taken",
        "has the key man12 already",
    )


@case("library-delete")
def _library_delete(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    undo = succeeds(s, "library-delete", {"ref": man12})["undo"]
    assert not (q / ".loom/library/nodes" / f"{man12}.node").exists() and undo.startswith("u-")
    refuses(s, "library-delete", {"ref": man12}, 404, "no-such-ref", "no work")
    refuses(s, "library-delete", {"ref": man12, "author": "Referee (Agent)"}, 403, "author-only", "only the author")


@case("library-restore")
def _library_restore(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    man12 = _pasted(s, MAN12)
    before = _library_files(q)
    undo = succeeds(s, "library-delete", {"ref": man12})["undo"]
    assert succeeds(s, "library-restore", {"undo": undo})["ref"] == man12
    assert {k: v for k, v in _library_files(q).items() if "nodes/" in k} == {
        k: v for k, v in before.items() if "nodes/" in k
    }
    refuses(s, "library-restore", {"undo": undo}, 404, "no-such-undo", "names no delete")
    refuses(s, "library-restore", {"undo": "../x"}, 404, "no-such-undo", "names no delete")


def _files(q: Path) -> dict[str, int]:
    """Every file of the quilt, with when it was last written."""
    return {p.relative_to(q).as_posix(): p.stat().st_mtime_ns for p in sorted(q.rglob("*")) if p.is_file()}


@case("library-upgrade")
def _library_upgrade(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A quilt an earlier loom made is served waiting: the viewer's files, `GET /_api` with its format, the stream and `library-upgrade`, and nothing else until the upgrade carries its library and makes its agents' layer this loom's, as `loom upgrade` does, after which the server builds as it starts. The `serve` fixture loads a quilt in this loom's layout only, so this case starts its own server."""
    import urllib.request

    from loom.cli.report import counted
    from loom.doctor import OK, check_ai_files, check_permissions
    from loom.paths import AI, FORMAT, SERVE_JSON
    from loom.scan.quilt import load_quilt
    from tests.helpers import PATIENCE
    from tests.unit.library._old import OLD_COMMAND, OLD_MODE, OLD_RULE, older_quilt
    from tests.unit.render._serve import fake_bundle

    q = older_quilt(tmp_path, agents=True)
    mode, skill = f"{AI}/modes/{OLD_MODE}.md", f".claude/skills/loom-{OLD_MODE}/SKILL.md"
    assert check_permissions(q).status != OK  # the earlier loom's rule is stale
    before = _files(q)
    s = ServeSession(
        load_quilt(q, older=True), fake_bundle(tmp_path / "older"), port=0, compile_masters=False, interval=0.2
    )
    assert s.older == 1
    s.start()
    stream = None
    try:
        status, _, raw = get(s.url + "_api")
        said = json.loads(raw)
        assert status == 200 and said["format"] == {"found": 1, "reads": 2}, said
        assert said["capabilities"] == ["library-upgrade"] and said["token"] and said["stream"], said
        # the frame is the viewer's own, served as always
        assert get(s.url)[0] == 200 and get(s.url + "node/dm-0003")[0] == 200
        # any other request is the quilt's, which this loom cannot read yet
        refuses(s, "library-take", {"items": [{"text": MAN12}]}, 409, "format-old", "made by an earlier loom")
        refuses(s, "library-works", {}, 409, "format-old", "library-upgrade")
        assert get(s.url + "build/manifest.json")[0] == 409
        refuses(s, "library-upgrade", {"author": "Referee (Agent)"}, 403, "author-only", "only the author")
        assert s.builds == 0 and s.watcher is None and s.frames is None
        # nothing is written but the server's own record
        assert {k: v for k, v in _files(q).items() if k != SERVE_JSON} == before

        stream = urllib.request.urlopen(s.url + "_api/stream", timeout=PATIENCE)
        assert stream.readline() == b": open\n"
        done = succeeds(s, "library-upgrade", {})
        carried = done["carried"]
        assert (q / FORMAT).read_text(encoding="utf-8") == "2\n"
        assert set(carried) == {
            "references",
            "documents",
            "notes_rekeyed",
            "overviews",
            "links_rewritten",
            "removed",
            "problems",
        }, done
        # its works become references, its old library files go
        assert carried["references"] >= 1 and carried["removed"] and carried["problems"] == [], done
        assert done["result"].startswith(
            f"brought the quilt forward to format 2, {counted(carried['references'], 'work')} carried into the library; wrote "
        ), done
        assert done["result"].endswith("; removed 2 files"), done
        assert not (q / ".loom" / "library" / "bibliography.bib").exists()
        # and its agents are told and allowed what this loom has: the gone mode and its skill removed, the rules and the permissions this loom's
        agents = done["agents"]
        assert sorted(agents["removed"]) == sorted([mode, skill]), agents
        assert f"{AI}/rules.md" in agents["written"] and ".claude/settings.json" in agents["written"], agents
        assert f".claude/settings.json: allow {OLD_RULE}" in agents["dropped"], agents
        assert not (q / mode).exists() and not (q / skill).exists()
        assert OLD_COMMAND not in (q / AI / "rules.md").read_text(encoding="utf-8")
        assert OLD_RULE not in (q / ".claude" / "settings.json").read_text(encoding="utf-8")
        assert check_permissions(q).status == OK and check_ai_files(q).status == OK
        # served again as soon as it answers, and built after
        assert succeeds(s, "library-works", {})["works"]
        line = b""
        while line != b"event: manifest\n":
            line = stream.readline()
            assert line, "the stream ended before the first build was published"
        assert get(s.url + "build/manifest.json")[0] == 200 and s.builds >= 1
        said = json.loads(get(s.url + "_api")[2])
        assert said["format"] == {"found": 2, "reads": 2} and "library-take" in said["capabilities"], said
        assert said["frames"], said
        again = succeeds(s, "library-upgrade", {})
        assert again["result"].startswith("already current") and again["carried"]["references"] == 0, again
        assert again["agents"]["written"] == [] and again["agents"]["removed"] == [], again
    finally:
        if stream is not None:
            stream.close()
        s.stop()
