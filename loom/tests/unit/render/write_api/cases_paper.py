"""The cases of the endpoints that bring a paper into a quilt from its empty page: the files received into a drop outside the quilt, the drop brought in as the paper or as PDFs to read, and a file chosen in the system's dialog."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from loom.app import create
from loom.render.serve import ServeSession
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import Serve, case, refuses, succeeds

PAPER = b"\\documentclass{article}\n\\newtheorem{thm}{Theorem}\n\\begin{document}\nHello.\n\\end{document}\n"
#: A PDF as the intake's tests stand one in: its title and author on its first lines.
PDF = b"%PDF-1.4\n%FAKE-LOOM\n%%Pages: 1\nGadget towers\nA. Halberd\n"


def empty(serve: Serve, tmp_path: Path) -> tuple[ServeSession, Path]:
    """A quilt with nothing in it, as New quilt makes one, served."""
    from loom.cli.quilt import write_minimal_quilt

    q = tmp_path / "empty"
    write_minimal_quilt(q, "q", readme=False)
    return serve(q), q


def dropped(files: dict[str, bytes]) -> str:
    """A drop holding `files`, each received as `paper-receive` keeps it."""
    key: str | None = None
    for rel, data in files.items():
        key = create.receive(key, rel, io.BytesIO(data), len(data))["drop"]
    assert key is not None
    return key


def stream(s: ServeSession, path: str, data: bytes, drop: str = "", *, token: str | None = None) -> tuple[int, Any]:
    """POST a file's bytes to `paper-receive` as the viewer sends a drop: `application/octet-stream`, the token, its path and drop in the query."""
    if token is None:
        token = json.loads(get(s.url + "_api")[2])["token"]
    query = urllib.parse.urlencode({"path": path, **({"drop": drop} if drop else {})})
    req = urllib.request.Request(
        s.url + "_api/paper-receive?" + query,
        data=data,
        headers={"Content-Type": "application/octet-stream", "X-Loom-Token": token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@case("paper-receive")
def _paper_receive(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q = empty(serve, tmp_path)
    builds = s.builds
    status, said = stream(s, "paper.tex", PAPER)
    assert status == 200 and (said["path"], said["size"]) == ("paper.tex", len(PAPER)), said
    status, more = stream(s, "sections/intro.tex", b"Hello.\n", said["drop"])
    assert status == 200 and more["drop"] == said["drop"], more
    # kept outside the quilt, in loom's folder for the machine, and receiving rebuilds nothing
    files = create.incoming() / said["drop"] / "files"
    assert (files / "paper.tex").read_bytes() == PAPER and (files / "sections" / "intro.tex").is_file()
    assert not list(q.rglob("paper.tex")) and s.builds == builds
    status, refused = stream(s, "../outside.tex", b"x")
    assert (status, refused["error"]["code"]) == (400, "bad-path"), refused
    assert stream(s, "x.tex", b"x", token="")[0] == 403
    refuses(s, "paper-receive", {"path": "x.tex"}, 400, "not-a-stream", "application/octet-stream")


@case("paper-import")
def _paper_import(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q = empty(serve, tmp_path)
    # several files a paper could be: the question, the drop kept for the answer
    drop = dropped({"a.tex": PAPER, "slides.tex": PAPER})
    asked = succeeds(s, "paper-import", {"drop": drop})
    assert asked["question"] == {"choices": ["a.tex", "slides.tex"]} and asked["drop"] == drop, asked
    refuses(s, "paper-import", {"drop": drop, "main": "c.tex"}, 400, "bad-field", "main is not")
    done = succeeds(s, "paper-import", {"drop": drop, "main": "a.tex"})
    assert done["document"] == "a/a.tex" and (q / "a" / "a.tex").is_file() and done["differs"] is False, done
    assert not (create.incoming() / drop).exists()
    # PDFs and nothing else are read: each a work in the library
    read = succeeds(s, "paper-import", {"drop": dropped({"towers.pdf": PDF})})
    assert read["read"] == 1 and list((q / ".loom" / "library" / "nodes").rglob("*")), read
    drop = dropped({"notes.txt": b"no paper here"})
    refuses(s, "paper-import", {"drop": drop}, 409, "no-paper", "no .tex file that begins a document")
    assert not (create.incoming() / drop).exists()
    refuses(s, "paper-import", {"drop": "0" * 16}, 404, "no-such-drop", "nothing was dropped")
    refuses(s, "paper-import", {}, 400, "missing-field", "drop is required")


@case("paper-choose")
def _paper_choose(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.app import server

    s, q = empty(serve, tmp_path)
    chosen: list[Path | None] = [None]
    monkeypatch.setattr(server, "choose_file", lambda prompt: chosen[0])
    assert succeeds(s, "paper-choose", {})["cancelled"] is True
    # a .tex is read where it lies, with its folder, which is left as it was
    paper = tmp_path / "mine" / "towers.tex"
    paper.parent.mkdir()
    paper.write_bytes(PAPER)
    chosen[0] = paper
    done = succeeds(s, "paper-choose", {})
    assert done["document"] == "towers/towers.tex" and (q / "towers" / "towers.tex").is_file(), done
    assert paper.read_bytes() == PAPER
    # anything else is kept as a drop first, as one dropped is
    pdf = tmp_path / "mine" / "halberd.pdf"
    pdf.write_bytes(PDF)
    chosen[0] = pdf
    assert succeeds(s, "paper-choose", {})["read"] == 1
    (tmp_path / "mine" / "part.tex").write_text("Only a section.\n")
    chosen[0] = tmp_path / "mine" / "part.tex"
    refuses(s, "paper-choose", {}, 409, "no-paper", "does not begin a document")
