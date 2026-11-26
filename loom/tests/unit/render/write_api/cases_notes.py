"""The cases of the endpoints for notes: New note, and the person's new-note command."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest

from tests.unit.render.write_api._cases import WHO, Serve, case, on_demo, refuses, succeeds

#: A stand-in editor: writes what the request file held beside itself.
STAND_IN = "import json, sys; from pathlib import Path; Path(sys.argv[0]).with_name('got.json').write_text(Path(sys.argv[1]).read_text())"


@case("notes-settings")
def _notes_settings(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom import notes

    s, q, _sid = on_demo(serve, tmp_path)
    assert succeeds(s, "notes-settings", {})["command"] == ""
    # with no Set in loom's dialog (the suite's default answer is Cancel), a write naming no author, as one with the server's token can send, saves nothing
    refuses(s, "notes-settings", {"command": "sh -c 'touch pwned'"}, 409, "not-confirmed", "choose Set")
    assert succeeds(s, "notes-settings", {})["command"] == ""
    monkeypatch.setattr(notes, "confirm", lambda command, quilt: command == "emacsclient -n {request}")
    assert (
        succeeds(s, "notes-settings", {"command": "emacsclient -n {request}", "author": WHO})["command"]
        == "emacsclient -n {request}"
    )
    assert "emacsclient" not in (q / "config.toml").read_text(encoding="utf-8")
    assert not [p for p in q.rglob("manifest.json") if "emacsclient" in p.read_text(encoding="utf-8")]
    refuses(
        s, "notes-settings", {"command": "touch x", "author": "Notes Agent"}, 403, "author-only", "never reads or sets"
    )
    refuses(s, "notes-settings", {"author": "Notes Agent"}, 403, "author-only", "never reads or sets")
    refuses(s, "notes-settings", {"command": "ed '(open"}, 400, "bad-command", "cannot be split")
    assert succeeds(s, "notes-settings", {})["command"] == "emacsclient -n {request}"


@case("new-note")
def _new_note(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom import files, notes

    monkeypatch.setattr(files, "launch", lambda argv: None)
    monkeypatch.setattr(notes, "confirm", lambda command, quilt: True)
    s, q, _sid = on_demo(serve, tmp_path)
    wrote = succeeds(s, "new-note", {"link": "quilt:main.tex", "title": "Main", "author": WHO})
    assert wrote["how"] == "wrote" and (q / wrote["path"]).read_text(encoding="utf-8").endswith(
        "[Main](quilt:main.tex)\n\n"
    )
    script = tmp_path / "editor.py"
    script.write_text(STAND_IN, encoding="utf-8")
    succeeds(s, "notes-settings", {"command": f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} {{request}}"})
    ran = succeeds(s, "new-note", {"link": "quilt:main.tex#quote=w", "quote": "w", "title": "Main"})
    assert ran["how"] == "ran"
    assert sorted(json.loads((tmp_path / "got.json").read_text())) == ["dir", "link", "quilt", "quote", "title"]
    refuses(s, "new-note", {"link": "quilt:main.tex", "author": "Notes Agent"}, 403, "author-only", "your click")
    refuses(s, "new-note", {"link": "https://example.org"}, 400, "bad-field", "quilt: link")
