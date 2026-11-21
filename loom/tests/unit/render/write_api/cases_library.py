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
    recs = json.loads((q / ".loom/library" / f"{ck}.results.json").read_text())["results"]
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
    assert "loom-added" in (q / ".loom" / "library" / "bibliography.bib").read_text(encoding="utf-8")
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
    assert (q / ".loom" / "local" / "incoming" / said["upload"] / "pullbacks.pdf").is_file()
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
    # filed, it waits in `.loom/local/incoming/` no longer
    assert not (q / ".loom" / "local" / "incoming" / other["upload"]).exists()
    refuses(s, "library-file", {"upload": "0" * 64, "citekey": "Man12"}, 404, "no-such-upload", "no PDF was dropped")


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
    assert said["works"], "gathering makes the demo's cited works"
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
    refuses(s, "library-entry", {"ref": man12, "bibtex": "not bibtex"}, 400, "bad-entry", "not one BibTeX entry")
    other = _pasted(s, ENTRY)
    refuses(s, "library-entry", {"ref": other, "bibtex": "@article{man12, title = {x}}"}, 409, "key-taken", "is also")


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
