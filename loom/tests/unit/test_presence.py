"""Who is connected: `loom mcp` started as a process writes its record at its first request, notes each call, and removes the record when it is stopped; a reader lists only records a live server holds, and deletes the rest."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from loom.presence import FORMAT, Presence, live, record_path
from tests.unit._agent_server import CLIENT, AgentServer
from tests.unit._quilts import demo


def test_a_server_writes_its_record_at_its_first_request_and_sigint_removes_it(tmp_path: Path) -> None:
    """Claude Code sends `server/discover`, with who it is in `_meta`, and ends a conversation with SIGINT; the record says what the app said and the environment it gave."""
    q = demo(tmp_path)
    env = {"CLAUDE_CODE_SESSION_ID": "c0ffee-1", "CLAUDE_CODE_ENTRYPOINT": "claude-desktop"}
    with AgentServer(q, env=env) as server:
        server.discover()
        [record] = live(q)
        assert record["pid"] == server.pid and record["ppid"] == os.getpid()
        assert record["format"] == FORMAT and record["as"] == "Test Agent"
        assert record["client"] == CLIENT and record["protocol"] == "2026-07-28"
        assert record["conversation"] == "c0ffee-1" and record["entrypoint"] == "claude-desktop"
        assert record["session"] is None and record["last"] is None and record["started"]
        assert server.stop(signal.SIGINT) == -signal.SIGINT
        assert not server.record.exists()
    assert live(q) == []


def test_a_client_that_sends_initialize_is_recorded_from_it_and_sigterm_removes_it(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q) as server:
        server.initialize()
        [record] = live(q)
        assert record["client"] == {"name": "codex-mcp-client", "version": "0.9"}
        assert record["protocol"] == "2025-11-25" and record["conversation"] is None
        assert server.stop(signal.SIGTERM) == -signal.SIGTERM
        assert not server.record.exists()


def test_a_killed_server_leaves_its_record_and_the_next_look_deletes_it(tmp_path: Path) -> None:
    """SIGKILL runs no handler, but the lock goes with the process, so the record reads as nobody's."""
    q = demo(tmp_path)
    with AgentServer(q) as server:
        server.discover()
        assert server.stop(signal.SIGKILL) == -signal.SIGKILL
        assert server.record.exists()
        assert live(q) == []
        assert not server.record.exists()


def test_a_server_that_ends_on_its_own_removes_its_record(tmp_path: Path) -> None:
    """A client that closes standard input, as the SDK's does."""
    q = demo(tmp_path)
    with AgentServer(q) as server:
        server.discover()
        assert server.record.exists()
        assert server.proc.stdin is not None
        server.proc.stdin.close()
        assert server.wait() == 0
        assert not server.record.exists()


def test_two_servers_are_two_records(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with (
        AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "one"}) as a,
        AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "two"}) as b,
    ):
        a.discover()
        b.discover()
        assert {(r["pid"], r["conversation"]) for r in live(q)} == {(a.pid, "one"), (b.pid, "two")}
        a.stop()
        assert [r["pid"] for r in live(q)] == [b.pid]


def test_each_call_is_the_records_last(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q) as server:
        server.discover()
        server.call("loom_status")
        [record] = live(q)
        assert record["last"]["kind"] == "tool" and record["last"]["name"] == "loom_status" and record["last"]["when"]
        server.request("prompts/get", {"name": "quick"})
        assert live(q)[0]["last"]["kind"] == "prompt" and live(q)[0]["last"]["name"] == "quick"


def test_a_record_no_process_holds_is_not_connected_whatever_its_pid_names(tmp_path: Path) -> None:
    """A pid reused by another process, here one that is no loom server at all, does not make an old record live."""
    q = demo(tmp_path)
    other = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
    try:
        path = record_path(q, other.pid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"format": FORMAT, "pid": other.pid, "as": "Old Agent", "started": "x"}))
        assert live(q) == []
        assert not path.exists()
    finally:
        other.kill()
        other.wait()


def test_a_record_copied_with_its_quilt_is_not_connected_in_the_copy(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q) as server:
        server.discover()
        copy = tmp_path / "copy"
        shutil.copytree(q, copy)
        assert record_path(copy, server.pid).exists()
        assert live(copy) == []
        assert [r["pid"] for r in live(q)] == [server.pid]


def test_a_held_record_that_does_not_read_as_one_is_not_listed_and_is_left(tmp_path: Path) -> None:
    """Held, so a process is alive; unreadable, so nothing says it is a loom server: neither listed nor deleted."""
    q = demo(tmp_path)
    path = record_path(q, os.getpid())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"format": FORMAT, "pid": 1}))
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert live(q) == []
        assert path.exists()
    finally:
        os.close(fd)


def test_this_processs_record_is_listed_while_held_and_gone_once_ended(tmp_path: Path) -> None:
    q = demo(tmp_path)
    here = Presence(q, "Test Agent")
    try:
        here.called("tool", "loom_status")
        assert live(q) == [] and not here.path.exists(), "nothing is written before the first request"
        here.begin({"name": "claude-code"}, "2026-07-28")
        here.bound("s-2026-11-17-abcd")
        [record] = live(q)
        assert record["session"] == "s-2026-11-17-abcd" and record["last"]["name"] == "loom_status"
    finally:
        here.end()
        here.end()
    assert live(q) == [] and not here.path.exists()


def test_the_records_are_kept_out_of_git(tmp_path: Path) -> None:
    q = demo(tmp_path)
    assert "live/" in (q / ".loom" / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_a_record_written_starts_no_rebuild(tmp_path: Path) -> None:
    """A server writes its record at every call; the watcher that rebuilds the page does not look at it, while it still looks at the records beside it."""
    from loom.render.watch import snapshot

    q = demo(tmp_path)
    here = Presence(q, "Test Agent")
    try:
        here.begin(None, None)
        seen = {p.relative_to(q).as_posix() for p in snapshot(q)}
        assert not any(p.startswith(".loom/live/") for p in seen)
        assert any(p.startswith(".loom/annotations/") for p in seen)
    finally:
        here.end()
