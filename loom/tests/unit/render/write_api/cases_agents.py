"""The cases of the endpoints for agents and sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.unit._quilts import demo, new_session
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    WHO,
    Serve,
    case,
    events,
    noted,
    on_demo,
    refuses,
    succeeds,
    synthetic,
)


def index(q: Path, sid: str) -> list[dict[str, Any]]:
    """The session index's events for one session, in order."""
    lines = (q / ".loom" / "agents" / "sessions" / "index.jsonl").read_text(encoding="utf-8").splitlines()
    return [e for e in map(json.loads, filter(None, lines)) if e.get("id") == sid]


@case("session-use")
def _session_use(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import active, close, delete, sessions

    s, q, sid = on_demo(serve, tmp_path)
    close(q, sid, WHO)
    # a closed session is resumed by being chosen, and becomes the one writing lands in
    succeeds(s, "session-use", {"session": sid, "author": WHO})
    assert active(q) == sid and sessions(q)[sid].state == "open" and index(q, sid)[-1]["event"] == "resumed"
    gone = new_session(q, "a gone sitting")
    delete(q, gone, WHO)
    was = active(q)
    refuses(s, "session-use", {"session": gone}, 400, "refused", "was deleted")
    assert active(q) == was and sessions(q, deleted=True)[gone].state == "deleted"


@case("session-rename")
def _session_rename(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import sessions

    s, q, sid = on_demo(serve, tmp_path)
    succeeds(s, "session-rename", {"session": sid, "title": "second pass", "author": WHO})
    assert sessions(q)[sid].title == "second pass" and index(q, sid)[-1]["who"] == WHO
    refuses(s, "session-rename", {"session": sid}, 400, "missing-field", "title is required")


@case("session-delete")
def _session_delete(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import active, sessions

    s, q, sid = on_demo(serve, tmp_path)
    ann = noted(s, q, sid)
    succeeds(s, "session-delete", {"session": sid, "reason": "a false start", "author": WHO})
    assert index(q, sid)[-1] == {**index(q, sid)[-1], "event": "deleted", "why": "a false start"}
    assert sid not in sessions(q) and active(q) != sid
    assert events(q, ann), "a tombstone keeps what was written in the session"
    refuses(s, "session-delete", {"session": "s-1999-01-01-bfyfgz"}, 404, "no-such-session", "s-1999-01-01-bfyfgz")


@case("session-new")
def _session_new(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import active, sessions

    q = demo(tmp_path)
    s = serve(q)
    said = succeeds(s, "session-new", {"title": "from the page", "purpose": "check the orbits", "author": WHO})
    sid = said["result"].split()[0]
    assert active(q) == sid
    assert (sessions(q)[sid].title, sessions(q)[sid].purpose) == ("from the page", "check the orbits")
    refuses(s, "session-new", {"purpose": "untitled"}, 400, "missing-field", "title is required")


@case("session-close")
def _session_close(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import active, sessions

    s, q, sid = on_demo(serve, tmp_path)
    assert active(q) == sid
    succeeds(s, "session-close", {"session": sid, "author": WHO})
    assert sessions(q)[sid].state == "closed" and active(q) is None
    refuses(s, "session-close", {"session": sid}, 400, "refused", "is closed")


@case("session-reopen")
def _session_reopen(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import active, close, sessions

    s, q, sid = on_demo(serve, tmp_path)
    refuses(s, "session-reopen", {"session": sid}, 400, "refused", "already open")
    close(q, sid, WHO)
    was = active(q)
    assert succeeds(s, "session-reopen", {"session": sid, "author": WHO})["result"] == f"reopened {sid}"
    # reopening starts a new round and leaves which session is active alone
    assert sessions(q)[sid].state == "open" and len(sessions(q)[sid].rounds) == 2
    assert index(q, sid)[-1]["event"] == "resumed" and active(q) == was


@case("session-purpose")
def _session_purpose(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.sessions import sessions

    s, q, sid = on_demo(serve, tmp_path)
    assert (
        succeeds(s, "session-purpose", {"session": sid, "purpose": "the orbit lemma"})["result"]
        == f"{sid} is for the orbit lemma"
    )
    assert sessions(q)[sid].purpose == "the orbit lemma" and index(q, sid)[-1]["event"] == "purposed"
    # an empty purpose clears it
    succeeds(s, "session-purpose", {"session": sid})
    assert sessions(q)[sid].purpose == ""
    refuses(s, "session-purpose", {"session": "s-1999-01-01-bfyfgz", "purpose": "x"}, 404, "no-such-session", "s-1999")


@case("here")
def _here(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    s, q, sid = on_demo(serve, tmp_path)
    before = sorted(p.relative_to(q).as_posix() for p in q.rglob("*") if "cache" not in p.parts)
    place = {"route": "reading", "item": {"kind": "node", "id": "dm-0002"}, "session": sid}
    succeeds(s, "here", place)
    token = json.loads(get(s.url + "_api")[2])["token"]
    status, _, raw = get(s.url + "_api/here", {"X-Loom-Token": token})
    assert status == 200 and json.loads(raw)["place"] == place, raw
    # held in memory: nothing outside the build moved
    assert sorted(p.relative_to(q).as_posix() for p in q.rglob("*") if "cache" not in p.parts) == before
    refuses(
        s,
        "here",
        {"item": {"kind": "node", "id": "dm-0002"}},
        400,
        "bad-field",
        "route must be reading, review or elsewhere",
    )


@case("agents-mode-save")
def _agents_mode_save(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.ai.layout import VERSION_FILE, read_versions, sha, tracked_docs

    s, q = synthetic(serve, tmp_path)
    rel = ".loom/agents/instructions/modes/referee.md"
    loom = tracked_docs(q)[rel]
    refuses(s, "agents-mode-save", {"name": "referee", "text": "x", "author": WHO}, 409, "no-agent-layer", "set an")
    succeeds(s, "agents-setup", {"app": "claude-code", "author": WHO})
    mode = q / rel
    edited = loom.replace("When it fits:", "When it fits: as this quilt referees;", 1)
    said = succeeds(s, "agents-mode-save", {"name": "referee", "text": edited, "was": loom, "author": WHO})
    assert said["result"] == "saved the referee mode" and mode.read_text() == edited
    # what the person was shown is what the file must still hold, and an agent changes no mode
    refuses(s, "agents-mode-save", {"name": "referee", "text": "y", "was": loom, "author": WHO}, 409, "changed", "look")
    refuses(
        s,
        "agents-mode-save",
        {"name": "referee", "loom": True, "author": "Referee (Agent)"},
        403,
        "author-only",
        "only the author",
    )
    refuses(s, "agents-mode-save", {"name": "referee", "author": WHO}, 400, "missing-field", "loom: true")
    refuses(s, "agents-mode-save", {"name": "nope", "text": "z", "author": WHO}, 404, "no-such-mode", "referee")
    assert mode.read_text() == edited
    # put back, with the newer version loom wrote beside the edit taken away and the file recorded as loom's again
    (q / f"{rel}.new").write_text(loom)
    said = succeeds(s, "agents-mode-save", {"name": "referee", "loom": True, "author": WHO})
    assert said["result"] == "put the referee mode back to loom's" and mode.read_text() == loom
    assert not (q / f"{rel}.new").exists() and read_versions(q)["referee.md"] == sha(loom)
    assert (q / ".loom/agents/instructions" / VERSION_FILE).is_file()


@case("agents-setup")
def _agents_setup(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.ai.layout import MCP_LINE, variant

    s, q = synthetic(serve, tmp_path)
    assert not (q / ".loom" / "agents" / "instructions").exists()
    got = succeeds(s, "agents-setup", {"app": "claude-code", "author": WHO})
    # the layer and Claude Code's own files, over MCP, and no other app's
    for rel in (".loom/agents/instructions/orientation.md", "CLAUDE.md", ".claude/settings.json", ".mcp.json"):
        assert rel in got["written"] and (q / rel).is_file(), rel
    assert got["variant"] == variant(q) == "mcp" and MCP_LINE in (q / "CLAUDE.md").read_text()
    for rel in ("AGENTS.md", "GEMINI.md", ".codex", ".gemini", ".cursor"):
        assert not (q / rel).exists(), rel
    refuses(
        s, "agents-setup", {"app": "codex", "author": "Referee Agent"}, 403, "author-only", "only the author sets up"
    )
