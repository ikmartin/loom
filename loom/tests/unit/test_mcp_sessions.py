"""A loom session per conversation: `loom mcp` binds one at a conversation's first look or write when a call names none, finds it again when the conversation resumes in a new process, and gives it to what writes into a session or looks as one."""

from __future__ import annotations

from pathlib import Path

from loom.mailbox import read_events
from loom.presence import live
from loom.sessions import sessions
from tests.helpers import ok
from tests.unit._agent_server import AgentServer
from tests.unit._quilts import demo, new_session

WHO = "A. Author"


def made_for(q: Path, conversation: str) -> list[str]:
    return [s.id for s in sessions(q).values() if s.conversation == conversation]


def said(q: Path, sid: str) -> list[str]:
    return [e.body for e in read_events(q, sid)]


def test_a_conversations_first_write_makes_its_session_and_its_report_lands_there(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q, "Claude Code Agent", env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_status")
        assert made_for(q, "conv-a") == [], "a read makes no session"
        got = server.call("loom_session_say", {"text": "Mode: quick, on dm-0003."})
        assert not got.get("isError"), got
        [sid] = made_for(q, "conv-a")
        assert said(q, sid) == ["Mode: quick, on dm-0003."]
        assert sessions(q)[sid].title.startswith("Claude Code Agent · ")
        assert live(q)[0]["session"] == sid
        assert "loom session say" in (q / ".loom/sessions" / sid / "run.log").read_text()


def test_a_resumed_conversation_writes_into_its_session_again(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_session_say", {"text": "first sitting"})
    with AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_session_say", {"text": "second sitting"})
    [sid] = made_for(q, "conv-a")
    assert said(q, sid) == ["first sitting", "second sitting"]


def test_two_conversations_have_two_sessions_and_each_sees_what_came_since_it_looked(tmp_path: Path) -> None:
    """The window is the conversation's own: one looking does not move the other's."""
    q = demo(tmp_path)
    with (
        AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as a,
        AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-b"}) as b,
    ):
        for server in (a, b):
            server.discover()
            server.call("loom_since")
        assert len(made_for(q, "conv-a")) == len(made_for(q, "conv-b")) == 1
        ok("annotate", "dm-0003", "Is this sharp?", "--as", WHO, cwd=q)
        assert "Is this sharp?" in a.call("loom_since")["content"][0]["text"]
        assert "Is this sharp?" in b.call("loom_since")["content"][0]["text"]


def test_a_session_the_call_names_is_the_one_written_into(tmp_path: Path) -> None:
    q = demo(tmp_path)
    mine = new_session(q, "the author's", WHO)
    with AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_session_say", {"text": "here, as asked", "session": mine})
    assert said(q, mine) == ["here, as asked"]
    assert made_for(q, "conv-a") == []


def test_a_session_the_agent_opens_is_the_one_its_later_calls_write_into(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_session_new", {"name": "refereeing chapter 2"})
        server.call("loom_session_say", {"text": "begun"})
    [opened] = [s for s in sessions(q).values() if s.title == "refereeing chapter 2"]
    assert said(q, opened.id) == ["begun"]
    assert made_for(q, "conv-a") == []


def test_a_session_the_person_closed_is_not_written_into_again(tmp_path: Path) -> None:
    q = demo(tmp_path)
    with AgentServer(q, env={"CLAUDE_CODE_SESSION_ID": "conv-a"}) as server:
        server.discover()
        server.call("loom_session_say", {"text": "before"})
        [first] = made_for(q, "conv-a")
        ok("session", "close", first, "--as", WHO, cwd=q)
        server.call("loom_session_say", {"text": "after"})
        later = [sid for sid in made_for(q, "conv-a") if sid != first]
        assert said(q, first) == ["before"] and len(later) == 1 and said(q, later[0]) == ["after"]
