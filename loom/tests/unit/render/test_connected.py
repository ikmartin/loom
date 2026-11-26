"""Who is connected, as `loom serve` publishes it: the agent servers alive in `/_api`, and on the stream each time that changes."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pytest

from loom.presence import Presence
from loom.render.serve import ServeSession
from tests.helpers import PATIENCE
from tests.unit._quilts import demo
from tests.unit.render._serve import get


def events(resp: object) -> Callable[[], tuple[str, bytes]]:
    """A reader of the stream's next event, `(name, data)`, skipping comments."""

    def next_event() -> tuple[str, bytes]:
        name, data = "", b""
        while True:
            line = resp.readline()  # type: ignore[attr-defined]
            assert line, "the stream ended"
            if line == b"\n" and name:
                return name, data
            if line.startswith(b"event: "):
                name = line[len(b"event: ") :].strip().decode()
            elif line.startswith(b"data:"):
                data = line[len(b"data:") :].strip()

    return next_event


def test_api_and_the_stream_say_who_is_connected(serve: Callable[[Path], ServeSession], tmp_path: Path) -> None:
    """A record held by a live process is listed; once it ends, the next look takes it off, and the stream says so each time."""
    q = demo(tmp_path)
    s = serve(q)
    assert json.loads(get(s.url + "_api")[2])["connected"] == []
    with urllib.request.urlopen(s.url + "_api/stream", timeout=PATIENCE) as resp:
        following = events(resp)
        assert following() == ("compiles", b"{}")
        assert following() == ("connected", b"[]")
        here = Presence(q, "Claude Code Agent")
        try:
            here.begin({"name": "claude-code", "title": "Claude Code"}, "2026-07-28")
            name, data = following()
            assert name == "connected"
            [record] = json.loads(data)
            assert record["as"] == "Claude Code Agent" and record["client"]["title"] == "Claude Code"
            assert [r["pid"] for r in json.loads(get(s.url + "_api")[2])["connected"]] == [record["pid"]]
        finally:
            here.end()
        assert following() == ("connected", b"[]")


def test_a_record_written_republishes_nothing(serve: Callable[[Path], ServeSession], tmp_path: Path) -> None:
    """The stream says who is connected without a new manifest: a call an agent makes is no change to the page."""
    q = demo(tmp_path)
    s = serve(q)
    built = s.builds
    with urllib.request.urlopen(s.url + "_api/stream", timeout=PATIENCE) as resp:
        following = events(resp)
        assert following()[0] == "compiles" and following()[0] == "connected"
        here = Presence(q, "Test Agent")
        try:
            here.begin(None, None)
            assert following()[0] == "connected"
            here.called("tool", "loom_status")
            assert following()[0] == "connected"
        finally:
            here.end()
        assert following()[0] == "connected"
    assert s.builds == built


def test_api_answers_from_the_last_look(
    serve: Callable[[Path], ServeSession], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`GET /_api` says who is connected as the server's once-a-second look last found it, so no request waits on `.loom/local/live/`."""
    import loom.presence

    q = demo(tmp_path)
    s = serve(q)

    def looked(root: Path) -> list[object]:
        raise AssertionError("a request read .loom/local/live/")

    monkeypatch.setattr(loom.presence, "live", looked)
    assert json.loads(get(s.url + "_api")[2])["connected"] == []


def test_api_names_the_quilt_s_folder(serve: Callable[[Path], ServeSession], tmp_path: Path) -> None:
    """The viewer says which folder to choose in an agent's app from `/_api`'s `root`, the quilt's folder resolved, which only a request carrying the token is given."""
    q = demo(tmp_path)
    s = serve(q)
    bare = json.loads(get(s.url + "_api")[2])
    assert "root" not in bare
    assert json.loads(get(s.url + "_api", {"X-Loom-Token": bare["token"]})[2])["root"] == str(q.resolve())
    assert "root" not in json.loads(get(s.url + "_api", {"X-Loom-Token": "not-the-token"})[2])
