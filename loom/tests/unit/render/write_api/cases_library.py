"""The cases of the library's endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loom.render.serve import ServeSession
from tests.helpers import the
from tests.unit._quilts import mapped, propose, showcase
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    WHO,
    Serve,
    case,
    on_demo,
    refuses,
    succeeds,
)


def proposed(serve: Serve, tmp_path: Path) -> tuple[ServeSession, Path, str]:
    """The demo with a work whose page text is on disk and one proposed result, `<ck>-thm-1.1`, served."""
    q, ck = mapped(tmp_path)
    propose(q, ck, "thm-1.1", 1, "Let $f$ be a DM-type morphism", "S")
    return serve(q), q, f"{ck}-thm-1.1"


def result_state(q: Path, node: str) -> str:
    ck = node.split("-", 1)[0]
    recs = json.loads((q / ".loom/digests" / f"{ck}.results.json").read_text())["results"]
    return str(the(recs, lambda r: r["id"] == node, node)["state"])


@case("library-verify")
def _library_verify(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, node = proposed(serve, tmp_path)
    # an agent proposes and never vouches for its own reading, whatever surface it posts through
    refuses(s, "library-verify", {"node": node, "author": "Referee Agent"}, 403, "author-only", "is an agent")
    assert result_state(q, node) == "proposed"
    succeeds(s, "library-verify", {"node": node, "author": WHO})
    assert result_state(q, node) == "verified"


@case("library-discard")
def _library_discard(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, node = proposed(serve, tmp_path)
    refuses(s, "library-discard", {"node": node, "author": WHO}, 400, "missing-field", "why is required")
    refuses(s, "library-discard", {"node": node + ".9", "why": "x", "author": WHO}, 404, "no-such-node", node + ".9")
    assert result_state(q, node) == "proposed"
    succeeds(s, "library-discard", {"node": node, "why": "not the paper's", "author": WHO})
    assert result_state(q, node) == "discarded"


@case("locate")
def _locate(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s = serve(showcase(tmp_path))
    builds = s.builds
    text = "The median orders of a weighted digraph are in bijection with the vertices"
    said = succeeds(s, "locate", {"citekey": "Bellamy19", "page": 2, "text": text})
    assert said["anchor"]["basis"] == "text" and said["anchor"]["page"] == 2 and said["text"] == text, said
    # a quote with no page: the page that holds it
    found = succeeds(s, "locate", {"citekey": "Bellamy19", "text": text})
    assert found["page"] == 2 and found["anchor"]["page"] == 2, found
    # a read publishes nothing: the viewer asks again on each new manifest, so a rebuild after it would have it ask for ever
    assert s.builds == builds
    refuses(s, "locate", {"citekey": "Nope", "page": 1, "text": "x"}, 404, "no-such-work", "Nope")
    refuses(
        s,
        "locate",
        {"citekey": "Bellamy19", "text": "words on no page of it"},
        404,
        "not-found",
        "no page of Bellamy19",
    )


@case("library-update")
def _library_update(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    import time

    s, q, _ = on_demo(serve, tmp_path)
    said = succeeds(s, "library-update", {"works": ["Calloway14"]})
    assert said["job"]["works"] == ["Calloway14"]
    assert [step["name"] for step in said["job"]["steps"]] == ["resolve", "fetch", "extract", "map"]
    token = json.loads(get(s.url + "_api")[2])["token"]

    def jobs() -> list[dict[str, Any]]:
        return json.loads(get(s.url + "_api/jobs", {"X-Loom-Token": token})[2])["jobs"]  # type: ignore[no-any-return]

    deadline = time.monotonic() + 120
    while jobs()[0]["state"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.1)
    run = jobs()[0]
    # offline, as the demo is: the run finishes, says what it did as `loom library update` does, and the manifest was rebuilt after it
    assert run["state"] == "done" and run["online"] is False, run
    assert {step["state"] for step in run["steps"]} <= {"done", "skipped"}, run
    assert [step["state"] for step in run["steps"]][:2] == ["skipped", "skipped"], run
    assert run["report"]["verdict"], run
    # a digest made again is its extraction alone, which a cited work's problem offers
    said = succeeds(s, "library-update", {"works": ["Calloway14"], "redo": True, "steps": ["extract"]})
    assert [step["name"] for step in said["job"]["steps"]] == ["extract"], said
    while any(j["state"] in ("queued", "running") for j in jobs()) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert jobs()[0]["state"] == "done", jobs()[0]
    refuses(
        s, "library-update", {"works": ["Calloway14"], "steps": ["paint"]}, 400, "bad-field", "steps must be some of"
    )
    # the jobs are the token holder's to read
    assert get(s.url + "_api/jobs")[0] == 403
    refuses(
        s,
        "library-update",
        {"works": ["Calloway14"], "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author starts a library run",
    )
    refuses(s, "library-update", {"works": ["NoSuchWork99"]}, 404, "no-such-work", "NoSuchWork99")


ENTRY = "@article{Ost18,\n  author = {Ostrander, D.},\n  title = {Widget categories and their duals},\n  year = {2018},\n  journal = {J. Widget Theory}\n}"


def _fake_pdf(*lines: str) -> str:
    """A PDF the fake toolchain reads back: `pdftotext` answers with its lines, as page one."""
    import base64

    return base64.b64encode(("%PDF-1.4\n%FAKE-LOOM\n%%Pages: 1\n" + "\n".join(lines) + "\n").encode()).decode()


@case("library-recognise")
def _library_recognise(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, _, _ = on_demo(serve, tmp_path)
    said = succeeds(s, "library-recognise", {"text": "https://doi.org/10.4171/demo/14-1"})
    assert (said["kind"], said["value"], said["label"]) == ("doi", "10.4171/demo/14-1", "DOI")
    assert succeeds(s, "library-recognise", {"text": ENTRY})["entry"]["title"] == "Widget categories and their duals"
    refuses(s, "library-recognise", {}, 400, "missing-field", "text is required")


@case("library-lookup")
def _library_lookup(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, _, _ = on_demo(serve, tmp_path)
    found = succeeds(s, "library-lookup", {"text": ENTRY})["found"]
    assert found["state"] == "found" and found["key"] == "Ost18" and found["digest"] == "lookup"
    # the demo is offline: an identifier is not looked up, and says why
    assert succeeds(s, "library-lookup", {"text": "10.5555/x"})["found"]["state"] == "offline"
    refuses(
        s,
        "library-lookup",
        {"text": "10.5555/x", "online": True, "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author adds",
    )


@case("library-add")
def _library_add(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    said = succeeds(s, "library-add", {"text": ENTRY})
    assert said["citekey"] == "Ost18" and said["job"] is None
    assert "loom-added" in (q / ".loom" / "digests" / "bibliography.bib").read_text(encoding="utf-8")
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["references"]["Ost18"]["added"]["when"].endswith("Z")
    # with fetch, a run is queued on the new work
    other = ENTRY.replace("Ost18", "Ost18b").replace("Widget categories", "Gadget categories")
    assert succeeds(s, "library-add", {"text": other, "fetch": True})["job"]["works"] == ["Ost18b"]
    refuses(s, "library-add", {"text": "10.5555/x"}, 409, "lookup-offline", "needs the network")
    refuses(s, "library-add", {"text": ENTRY, "author": "Referee (Agent)"}, 403, "author-only", "only the author adds")


@case("library-upload")
def _library_upload(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    said = succeeds(
        s,
        "library-upload",
        {"name": "pullbacks.pdf", "data": _fake_pdf("Virtual pull-backs", "Cristina Manolache", "arXiv:0805.2065v2")},
    )
    assert said["best"] == "Man12", said
    assert (q / ".loom" / "incoming" / said["upload"] / "pullbacks.pdf").is_file()
    # one that shows no work in the library is offered an entry from its own pages
    other = succeeds(
        s,
        "library-upload",
        {"name": "Halberd - 2021 - Gadget towers.pdf", "data": _fake_pdf("Gadget towers", "arXiv:2102.11789")},
    )
    assert (
        other["best"] == "" and other["offer"]["eprint"] == "2102.11789" and other["offer"]["title"] == "Gadget towers"
    )
    refuses(s, "library-upload", {"name": "notes.txt", "data": "aGVsbG8="}, 400, "not-a-pdf", "notes.txt is not a PDF")


@case("library-file")
def _library_file(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    up = succeeds(
        s,
        "library-upload",
        {"name": "pullbacks.pdf", "data": _fake_pdf("Virtual pull-backs", "Cristina Manolache", "arXiv:0805.2065v2")},
    )
    filed = succeeds(s, "library-file", {"upload": up["upload"], "citekey": "Man12", "name": "pullbacks.pdf"})
    assert filed["citekey"] == "Man12" and filed["filed"] is True
    # filing answers at once, and reading its text is a run with no network in it
    assert [step["name"] for step in filed["job"]["steps"]] == ["map"] and filed["job"]["online"] is False
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["references"]["Man12"]["artifacts"]["pdf"] is True
    # a new work, its entry from the PDF's own account
    new = succeeds(
        s,
        "library-upload",
        {"name": "Halberd - 2021 - Gadget towers.pdf", "data": _fake_pdf("Gadget towers", "arXiv:2102.11789")},
    )
    made = succeeds(
        s, "library-file", {"upload": new["upload"], "new": True, "name": "Halberd - 2021 - Gadget towers.pdf"}
    )
    assert made["citekey"] == new["key"] and made["filed"] is True
    # a PDF whose pages give no title is a work all the same, under its file name or what the person typed
    bare = succeeds(s, "library-upload", {"name": "scan.pdf", "data": _fake_pdf("arXiv:2103.00001")})
    assert bare["offer"]["title"] == "scan"
    typed = succeeds(
        s, "library-file", {"upload": bare["upload"], "new": True, "entry": {"title": "A scanned note", "author": ""}}
    )
    assert typed["filed"] is True
    refs = json.loads(get(s.url + "build/manifest.json")[2])["references"]
    assert (
        refs[typed["citekey"]]["bib"]["title"] == "A scanned note"
        and refs[typed["citekey"]]["artifacts"]["pdf"] is True
    )
    # the same bytes again answer with the work holding them
    again = succeeds(s, "library-upload", {"name": "scan copy.pdf", "data": _fake_pdf("arXiv:2103.00001")})
    assert (again["best"], again["held"]) == (typed["citekey"], True)
    assert succeeds(s, "library-file", {"upload": again["upload"], "new": True})["citekey"] == typed["citekey"]
    # a PDF named for a work is filed there on the person's word, and what it shows otherwise is said
    other = succeeds(s, "library-upload", {"name": "other.pdf", "data": _fake_pdf("Nothing like that work")})
    refuses(s, "library-file", {"upload": other["upload"], "citekey": "Nobody"}, 404, "no-such-work", "no work Nobody")
    named = succeeds(s, "library-file", {"upload": other["upload"], "citekey": "Calloway14"})
    assert named["filed"] is True and named["sibling"] == "Calloway14-v2" and "does not show it is" in named["note"]
    # filed, it waits in `.loom/incoming/` no longer
    assert not (q / ".loom" / "incoming" / other["upload"]).exists()
    refuses(s, "library-file", {"upload": "0" * 64, "citekey": "Man12"}, 404, "no-such-upload", "no PDF was dropped")


@case("library-delete")
def _library_delete(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    succeeds(s, "library-add", {"text": ENTRY})
    assert succeeds(s, "library-delete", {"citekey": "Ost18"})["result"] == "deleted Ost18 from the library"
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert "Ost18" not in manifest["references"]
    refuses(s, "library-delete", {"citekey": "Calloway14"}, 409, "from-document", "gathering brings it back")
    refuses(s, "library-delete", {"citekey": "Nobody99"}, 404, "no-such-work", "no work Nobody99")


@case("library-ignore")
def _library_ignore(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    succeeds(s, "library-add", {"text": ENTRY})
    # a work whose store holds no document is declared unreadable, which the manifest says, and withdrawn again
    said = succeeds(s, "library-ignore", {"citekey": "Ost18", "why": "a living document"})["result"]
    assert said == "Ost18 declared unreadable: a living document"
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["references"]["Ost18"]["unreadable"]["why"] == "a living document"
    refuses(s, "library-ignore", {"citekey": "Ost18", "why": "again"}, 409, "already", "already declared unreadable")
    succeeds(s, "library-ignore", {"citekey": "Ost18", "why": "it has a version", "undo": True})
    assert "unreadable" not in json.loads(get(s.url + "build/manifest.json")[2])["references"]["Ost18"]
    refuses(s, "library-ignore", {"citekey": "Ost18", "why": "x", "undo": True}, 409, "not-ignored", "nothing to undo")
    refuses(s, "library-ignore", {"citekey": "Nobody99", "why": "x"}, 404, "no-such-work", "no work Nobody99")
    refuses(
        s,
        "library-ignore",
        {"citekey": "Ost18", "why": "x", "author": "Reading Agent"},
        403,
        "author-only",
        "author's claim",
    )


def _received(q: Path, name: str, *lines: str) -> str:
    """A file received as the viewer streams one, through the intake's own function; the drop's id."""
    import io

    from loom.refs.intake import receive

    data = ("%PDF-1.4\n%FAKE-LOOM\n%%Pages: 1\n" + "\n".join(lines) + "\n").encode()
    return str(receive(q, name, io.BytesIO(data), len(data))["incoming"])


def _library_files(q: Path) -> dict[str, bytes]:
    """Every file of the library's records, its store and its drops, with its bytes."""
    return {
        p.relative_to(q).as_posix(): p.read_bytes()
        for d in (q / ".loom" / "digests", q / ".loom" / "incoming")
        if d.is_dir()
        for p in sorted(d.rglob("*"))
        if p.is_file()
    }


def _runs_done(s: ServeSession) -> None:
    """Wait until the publisher's library runs have finished, as a viewer following them would."""
    import time

    token = json.loads(get(s.url + "_api")[2])["token"]
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        jobs = json.loads(get(s.url + "_api/jobs", {"X-Loom-Token": token})[2])["jobs"]
        if not any(j["state"] in ("queued", "running") for j in jobs):
            return
        time.sleep(0.1)


PULLBACKS = ("Virtual pull-backs", "Cristina Manolache", "arXiv:0805.2065v2")


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
    drop = q / ".loom" / "incoming" / said["incoming"]
    assert (drop / "Halberd - 2021 - Gadget towers.pdf").read_bytes() == data
    # the same bytes again are the drop kept already, and receiving rebuilds nothing
    assert _stream(s, "again.pdf", data)[1]["incoming"] == said["incoming"]
    assert s.builds == builds and len(list(drop.glob("*.pdf"))) == 1
    assert succeeds(s, "library-take", {"items": [{"incoming": said["incoming"]}]})["rows"][0]["state"] == "added"
    # bytes that are no PDF are kept nowhere
    status, said = _stream(s, "notes.txt", b"plain text, not a document")
    assert (status, said["error"]["code"]) == (400, "not-a-pdf")
    kept = sorted(p.name for p in (q / ".loom" / "incoming").iterdir())
    assert kept == [drop.name], kept
    assert _stream(s, "x.pdf", data, token="")[0] == 403
    refuses(s, "library-receive", {"name": "x.pdf"}, 400, "bad-request", "application/octet-stream")


@case("library-take")
def _library_take(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    new = _received(q, "Halberd - 2021 - Gadget towers.pdf", "Gadget towers", "A. Halberd")
    asked = _received(q, "pullbacks.pdf", *PULLBACKS)
    items = [{"incoming": new}, {"incoming": asked}, {"text": ENTRY}, {"text": "10.5555/x"}]
    rows = succeeds(s, "library-take", {"items": items})["rows"]
    assert [(r["state"], r.get("citekey")) for r in rows] == [
        ("added", "halberdGadgetTowers2021"),
        ("question", None),
        ("added", "Ost18"),
        ("cannot", None),
    ], rows
    # its pages are read by a run on the publisher's runner, with no network in it
    assert rows[0]["pages"] == "reading" and [x["name"] for x in rows[0]["job"]["steps"]] == ["map"]
    assert [c["citekey"] for c in rows[1]["candidates"]] == ["Man12"] and rows[3]["code"] == "offline"
    references = json.loads(get(s.url + "build/manifest.json")[2])["references"]
    assert {"halberdGadgetTowers2021", "Ost18"} <= set(references)
    # the same file again is already here
    assert succeeds(s, "library-take", {"items": [{"incoming": new}]})["rows"][0]["state"] == "here"
    refuses(s, "library-take", {"items": [{"incoming": "0" * 64}]}, 404, "no-such-incoming", "receive the file first")
    refuses(s, "library-take", {"items": [{"incoming": asked, "for": "Nobody"}]}, 404, "no-such-work", "no work Nobody")
    refuses(s, "library-take", {"items": [{"name": "x"}]}, 400, "bad-field", "each item is")
    refuses(
        s,
        "library-take",
        {"items": [{"text": ENTRY}], "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author",
    )
    # a quilt that has not said whether loom may look papers up is asked first, and nothing is read
    config = q / "config.toml"
    config.write_text(config.read_text().replace("online = false", ""))
    refuses(s, "library-take", {"items": [{"incoming": asked}]}, 409, "network-unasked", "has not said")


@case("library-answer")
def _library_answer(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    asked = _received(q, "pullbacks.pdf", *PULLBACKS)
    assert succeeds(s, "library-take", {"items": [{"incoming": asked}]})["rows"][0]["question"] == asked
    refuses(s, "library-answer", {"question": asked, "same": "Har77"}, 400, "not-a-candidate", "not one of the works")
    refuses(s, "library-answer", {"question": "0" * 64, "same": None}, 404, "no-such-question", "no question waits")
    refuses(s, "library-answer", {"question": asked}, 400, "missing-field", "same is required")
    refuses(
        s,
        "library-answer",
        {"question": asked, "same": "Man12", "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author",
    )
    row = succeeds(s, "library-answer", {"question": asked, "same": "Man12"})["row"]
    assert (row["state"], row["under"]) == ("added", "Man12"), row
    references = json.loads(get(s.url + "build/manifest.json")[2])["references"]
    assert references["Man12"]["artifacts"]["pdf"] is True


@case("library-undo")
def _library_undo(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    before = _library_files(q)
    drop = _received(q, "Halberd - 2021 - Gadget towers.pdf", "Gadget towers", "A. Halberd")
    row = succeeds(s, "library-take", {"items": [{"incoming": drop}]})["rows"][0]
    assert row["state"] == "added"
    _runs_done(s)
    assert succeeds(s, "library-undo", {"id": row["id"]})["result"] == "took halberdGadgetTowers2021 out again"
    assert _library_files(q) == before
    assert "halberdGadgetTowers2021" not in json.loads(get(s.url + "build/manifest.json")[2])["references"]
    refuses(s, "library-undo", {"id": drop}, 404, "no-such-intake", "nothing was dropped")
    refuses(s, "library-undo", {"id": "../config"}, 404, "no-such-intake", "names no drop")
    refuses(s, "library-undo", {"id": drop, "author": "Referee (Agent)"}, 403, "author-only", "only the author")


@case("library-unfile")
def _library_unfile(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    drop = _received(q, "schedule.pdf", "Department of Mathematics", "Seminar schedule, spring")
    assert succeeds(s, "library-take", {"items": [{"incoming": drop, "for": "Man12"}]})["rows"][0]["under"] == "Man12"
    _runs_done(s)
    filed = _library_files(q)
    said = succeeds(s, "library-unfile", {"citekey": "Man12"})
    assert said["incoming"] == drop and said["row"]["state"] == "received"
    assert json.loads(get(s.url + "build/manifest.json")[2])["references"]["Man12"]["artifacts"]["pdf"] is False
    refuses(s, "library-unfile", {"citekey": "Man12"}, 409, "no-document", "holds no PDF")
    refuses(s, "library-unfile", {"citekey": "Calloway14"}, 409, "has-results", "results read off this PDF")
    refuses(s, "library-unfile", {"citekey": "Nobody"}, 404, "no-such-work", "no work Nobody")
    # the unfile is undone in one step, and the store is as it was
    succeeds(s, "library-undo", {"id": drop})
    assert _library_files(q) == filed
