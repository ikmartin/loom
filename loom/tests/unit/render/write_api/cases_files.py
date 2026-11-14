"""The cases of the endpoints for files and settings."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest

from tests.unit.render._serve import get, post
from tests.unit.render.write_api._cases import (
    ARDEN,
    WHO,
    Serve,
    case,
    on_demo,
    refuses,
    succeeds,
    synthetic,
    with_paper,
)


@case("pdf-save")
def _pdf_save(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q = with_paper(serve, tmp_path)
    data = base64.b64encode(ARDEN.read_bytes()).decode("ascii")
    done = succeeds(s, "pdf-save", {"path": "notes/edited.pdf", "data": data, "author": WHO})
    assert done["path"] == "notes/edited.pdf" and (q / "notes" / "edited.pdf").read_bytes() == ARDEN.read_bytes()
    before = (q / "notes" / "paper.pdf").read_bytes()
    refuses(s, "pdf-save", {"path": "notes/paper.pdf", "data": data, "author": WHO}, 409, "exists", "never replaces")
    assert (q / "notes" / "paper.pdf").read_bytes() == before
    refuses(s, "pdf-save", {"path": "../out.pdf", "data": data, "author": WHO}, 400, "bad-field", "outside the quilt")
    refuses(s, "pdf-save", {"path": "notes/new.txt", "data": data, "author": WHO}, 400, "bad-field", "ends in .pdf")
    refuses(
        s, "pdf-save", {"path": ".loom/new.pdf", "data": data, "author": WHO}, 403, "hidden", "hidden from the viewer"
    )
    refuses(
        s,
        "pdf-save",
        {"path": "notes/new.pdf", "data": base64.b64encode(b"no").decode(), "author": WHO},
        400,
        "bad-field",
        "not a PDF",
    )
    refuses(
        s,
        "pdf-save",
        {"path": "notes/new.pdf", "data": data, "author": "Reading Agent"},
        403,
        "author-only",
        "only the author",
    )


@case("reviewer-settings")
def _reviewer_settings(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, root = synthetic(serve, tmp_path)
    assert succeeds(s, "reviewer-settings", {"name": "Bob"})["reviewer"]["name"] == "Bob"
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["reviewer"]["name"] == "Bob"
    refuses(
        s,
        "review-accept",
        {"reviewer": "The synthetic quilt", "keys": ["sy-0001"]},
        409,
        "reviewer-changed",
        "Reviewer changed",
    )
    refuses(s, "reviewer-settings", {"name": " "}, 409, "settings-refused", "nonempty")
    refuses(
        s, "reviewer-settings", {"name": "Bot", "author": "Referee (Agent)"}, 403, "author-only", "names the reviewer"
    )


@case("open")
def _open(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom import files

    if not files.can_open():
        pytest.skip("loom opens applications on macOS and Linux")
    launched: list[list[str]] = []
    monkeypatch.setattr(files, "launch", launched.append)
    s, q, _ = on_demo(serve, tmp_path)
    (q / "deck.apkg").write_bytes(b"PK")
    succeeds(s, "open", {"app": "Anki"})
    succeeds(s, "open", {"file": "deck.apkg"})
    assert len(launched) == 2
    refuses(s, "open", {"file": "README.md"}, 400, "not-openable", "never opens a file that may run code")


@case("file-tick")
def _file_tick(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.looks import changes
    from loom.scan.quilt import load_quilt, save_author
    from loom.tasks import items

    save_author("Tester")
    s, q, _ = on_demo(serve, tmp_path)
    succeeds(s, "change-keep", {"all": True})
    p = q / "todo.md"
    p.write_text("- [ ] one\n- [x] two\n", encoding="utf-8")
    succeeds(s, "change-keep", {"all": True})
    one, two = (t.id for t in items(p.read_text(encoding="utf-8")))
    said = succeeds(s, "file-tick", {"path": "todo.md", "task": one, "done": True})
    assert said["result"] == "ticked a box in todo.md"
    assert p.read_text(encoding="utf-8") == "- [x] one\n- [x] two\n"
    # it is published before the answer comes, and not listed back to the person who made it
    m = json.loads(get(s.url + "build/manifest.json")[2])
    body = next(f["body"] for f in m["files"] if f["path"] == "todo.md")
    assert f'data-done="true" data-task="{one}"' in get(s.url + "build/" + body)[2].decode()
    assert [(a["path"], a["line"], a["done"]) for a in m["history"]["acts"] if a["action"] == "tick"] == [
        ("todo.md", 1, True)
    ]
    assert "todo.md" not in {c.path for c in changes(load_quilt(q), "Tester")}
    assert "already" in succeeds(s, "file-tick", {"path": "todo.md", "task": one, "done": True})["result"]
    assert succeeds(s, "file-tick", {"path": "todo.md", "task": two, "done": False})["result"].startswith("unticked")
    body = {"path": "todo.md", "task": one, "done": False}
    refuses(s, "file-tick", {**body, "author": "Referee (Agent)"}, 403, "author-only", "the person's")
    refuses(s, "file-tick", {"task": one, "done": False}, 400, "missing-field", "path")
    refuses(s, "file-tick", {"path": "todo.md", "done": False}, 400, "missing-field", "task")
    refuses(s, "file-tick", {"path": "todo.md", "task": one, "done": "yes"}, 400, "bad-field", "true or false")
    refuses(s, "file-tick", {**body, "path": "none.md"}, 404, "no-such-file", "none.md")
    refuses(s, "file-tick", {**body, "path": "config.toml"}, 409, "not-a-task", "not a Markdown file")
    refuses(s, "file-tick", {**body, "task": "1:00000000"}, 409, "stale", "changed since")
    # the token is what keeps other pages out, here as for every write
    assert post(s.url + "_api/file-tick", body, token="wrong")[0] == 403
    assert p.read_text(encoding="utf-8") == "- [x] one\n- [ ] two\n"


@case("settings-save")
def _settings_save(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, _ = on_demo(serve, tmp_path)
    before = (q / "config.toml").read_text(encoding="utf-8")
    succeeds(s, "settings-save", {"changes": {"quilt.name": "Renamed in Settings", "agents.deny": ["notes/"]}})
    after = (q / "config.toml").read_text(encoding="utf-8")
    assert 'name = "Renamed in Settings"' in after and 'deny = ["notes/"]' in after
    # the person's comments are all still there
    assert [line for line in before.splitlines() if line.lstrip().startswith("#")] == [
        line for line in after.splitlines() if line.lstrip().startswith("#")
    ]
    # the rebuild read the new config: the corpus is renamed and the list is published
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["corpus"]["name"] == "Renamed in Settings"
    assert manifest["config"]["agents"]["deny"] == ["notes/"]
    # a refusal names each setting it refused, and writes none of them
    status, said = post(s.url + "_api/settings-save", {"changes": {"quilt.name": "Again", "quilt.prefix": "r-1"}})
    assert status == 409 and said["error"]["code"] == "bad-value", said
    assert said["error"]["fields"] == {"quilt.prefix": "must be letters and digits, without hyphens"}
    assert (q / "config.toml").read_text(encoding="utf-8") == after
    refuses(
        s,
        "settings-save",
        {"changes": {"quilt.history": "records"}},
        409,
        "bad-value",
        "read-only",
    )
    refuses(
        s,
        "settings-save",
        {"changes": {"agents.deny": []}, "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author changes",
    )


@case("agents-update")
def _agents_update(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.cli.ai import install_layer

    s, q, _ = on_demo(serve, tmp_path)
    shutil.rmtree(q / ".loom" / "ai")
    refuses(s, "agents-update", {}, 409, "no-agent-layer", "loom ai init")
    install_layer(q)
    succeeds(s, "settings-save", {"changes": {"agents.deny": ["notes/"]}})
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["config"]["agents"]["stale"] is True
    (stale,) = [d for d in manifest["diagnostics"] if d["code"] == "loom:agent-permissions-stale"]
    assert stale["owner"] == "person" and stale["fixes"][0]["act"] == {"endpoint": "agents-update", "body": {}}, stale
    refuses(s, "agents-update", {"author": "Referee (Agent)"}, 403, "author-only", "only the author changes")
    assert succeeds(s, "agents-update", {})["result"].startswith("rewrote .claude/settings.json")
    denied = json.loads((q / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
    assert "Edit(/**/notes/**)" in denied, denied
    manifest = json.loads(get(s.url + "build/manifest.json")[2])
    assert manifest["config"]["agents"]["stale"] is False
    assert "loom:agent-permissions-stale" not in {d["code"] for d in manifest["diagnostics"]}
