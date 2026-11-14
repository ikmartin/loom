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
    assert (q / ".loom" / "build" / "uploads" / said["upload"] / "pullbacks.pdf").is_file()
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
    named = succeeds(s, "library-file", {"upload": other["upload"], "citekey": "Calloway14"})
    assert named["filed"] is True and named["sibling"] == "Calloway14A" and "does not show it is" in named["note"]
    refuses(s, "library-file", {"upload": other["upload"], "citekey": "Nobody"}, 404, "no-such-work", "no work Nobody")
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
