"""What the review of the evidence and asks logs fixed: lines read once and in order, asks refused where they stand, answers carried back to the agent that asked."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from loom.evidence import asks, log
from loom.evidence.asks import AskRefused, ask, say
from loom.evidence.log import EvidenceRefused, replay, write
from loom.evidence.subjects import Subject, Who
from loom.paths import EVIDENCE_LOG
from tests.helpers import json_of, ok, refused, said
from tests.unit._quilts import demo, new_session, showcase

H = "sha256:" + "a" * 64
H2 = "sha256:" + "b" * 64
PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Claude Code Agent")
OTHER = Who("agent", "Codex Agent")
NODE = Subject("node", "tq-00K3", H)
PAPER = {"ref": "tq-00A1-ref", "pdf": H2, "pages": "12"}
STUB = {"node": "tq-00B7"}
S1, S2 = "s-2026-11-21-a8k2rx", "s-2026-11-21-b3m7qz"
AT = "2026-11-21T10:00:00Z"
#: A person's `by` whose name says it is an agent's.
POSING = {"kind": "person", "name": "Claude Code Agent"}


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", AT)
    return tmp_path


def _compared(rid: str, at: str = AT, by: dict[str, Any] | None = None) -> str:
    """One `compared` line on NODE, as a writer leaves it, without its line feed."""
    return json.dumps(
        {"id": rid, "kind": "compared", "at": at, "by": by or PERSON.to_dict(), "on": NODE.to_dict(), "with": PAPER}
    )


def _append(path: Path, text: str) -> None:
    """What another writer adds to a log: `text` as it is, line feed or none."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def _ids(found: log.Evidence, *, about: bool = False) -> list[str]:
    return [r.id for r in (found.about("node", "tq-00K3") if about else found.records)]


# ---- the logs --------------------------------------------------------------------------------------------------------


def test_a_line_a_merge_kept_twice_is_read_once_at_its_first_place(root: Path) -> None:
    a, b = "ev-2026-11-21-aaaaaa", "ev-2026-11-21-bbbbbb"
    _append(log.log_path(root), "".join(line + "\n" for line in (_compared(a), _compared(b), _compared(a))))
    found = replay(root)
    assert _ids(found) == [a, b]
    assert _ids(found, about=True) == [a, b]


def test_a_things_records_are_ordered_by_when_written_and_one_seconds_by_their_place_in_the_file(root: Path) -> None:
    late, first, second = "ev-2026-11-21-cccccc", "ev-2026-11-21-zzzzzz", "ev-2026-11-21-aaaaaa"
    lines = [_compared(late, "2026-11-21T11:00:00Z"), _compared(first), _compared(second)]
    _append(log.log_path(root), "".join(line + "\n" for line in lines))
    assert _ids(replay(root), about=True) == [first, second, late]


def test_a_line_torn_by_a_writer_that_died_does_not_swallow_the_next_record(root: Path) -> None:
    write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    torn = _compared("ev-2026-11-21-zzzzzz")
    _append(log.log_path(root), torn[: len(torn) // 2])
    after = write(root, "compared", PERSON, on=NODE, **{"with": PAPER})
    found = replay(root)
    assert after.id in _ids(found) and len(found.records) == 2
    [problem] = found.problems
    assert problem.startswith(f"{EVIDENCE_LOG}:2:") and "not JSON" in problem


def test_a_line_torn_in_the_asks_log_does_not_swallow_a_withdrawal(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?")
    torn = json.dumps({"at": AT, "by": PERSON.to_dict(), "event": "answered", "task": q.id, "words": "both"})
    _append(asks.log_path(root), torn[: len(torn) // 2])
    assert say(root, AGENT, "withdrawn", q.id).withdrawn is not None
    found = asks.replay(root)
    assert found.asks[q.id].withdrawn is not None
    [problem] = found.problems
    assert "not JSON" in problem


def test_a_last_line_of_the_asks_log_with_no_line_feed_is_read_when_whole(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?")
    asks.replay(root)
    _append(asks.log_path(root), json.dumps({"at": AT, "by": PERSON.to_dict(), "event": "withdrawn", "task": q.id}))
    found = asks.replay(root)
    assert found.asks[q.id].withdrawn is not None and found.problems == []


def test_a_replay_reads_on_from_where_it_stopped_and_whole_once_the_file_is_another(root: Path) -> None:
    a = write(root, "compared", PERSON, on=NODE, **{"with": PAPER}).id
    held = replay(root)
    _append(log.log_path(root), _compared("ev-2026-11-21-zzzzzz") + "\n")
    assert _ids(replay(root)) == [a, "ev-2026-11-21-zzzzzz"]
    assert _ids(held) == [a] and _ids(held, about=True) == [a]  # what a caller holds stays as it was read
    other = log.log_path(root).with_name("other.jsonl")
    other.write_text(_compared("ev-2026-11-21-yyyyyy") + "\n", encoding="utf-8")
    os.replace(other, log.log_path(root))
    assert _ids(replay(root)) == ["ev-2026-11-21-yyyyyy"]
    _append(log.log_path(root), _compared("ev-2026-11-21-xxxxxx") + "\n" + _compared("ev-2026-11-21-wwwwww") + "\n")
    assert len(replay(root).records) == 3
    lines = log.log_path(root).read_text(encoding="utf-8").splitlines(keepends=True)
    with log.log_path(root).open("w", encoding="utf-8") as fh:  # cut short in place, the same inode
        fh.write("".join(lines[:2]))
    assert _ids(replay(root)) == ["ev-2026-11-21-yyyyyy", "ev-2026-11-21-xxxxxx"]


def test_an_asks_replay_leaves_what_a_caller_holds_and_finds_an_ask_appended_after_its_event(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?")
    held = asks.replay(root)
    say(root, PERSON, "answered", q.id, words="both")
    assert held.asks[q.id].answers == [] and asks.replay(root).asks[q.id].answers
    # an event a merge put before its ask, the ask arriving in a later append
    late = "t-2026-11-21-zzzzzz"
    asked = json.loads(asks.log_path(root).read_text(encoding="utf-8").splitlines()[0]) | {"id": late}
    answer = {"at": AT, "by": PERSON.to_dict(), "event": "answered", "task": late, "words": "one"}
    _append(asks.log_path(root), json.dumps(answer) + "\n")
    assert "no ask in the log" in asks.replay(root).problems[-1]
    _append(asks.log_path(root), json.dumps(asked) + "\n")
    found = asks.replay(root)
    assert found.asks[late].answers[0]["words"] == "one" and found.problems == []


def test_a_person_whose_name_says_agent_is_refused_and_reported_in_the_evidence_log(root: Path) -> None:
    with pytest.raises(ValueError, match="calls itself an agent"):
        Who.from_dict(POSING)
    with pytest.raises(EvidenceRefused, match="calls itself an agent"):
        write(root, "compared", Who("person", POSING["name"]), on=NODE, **{"with": PAPER})
    _append(log.log_path(root), _compared("ev-2026-11-21-zzzzzz", by=POSING) + "\n")
    found = replay(root)
    assert found.records == []
    [problem] = found.problems
    assert "calls itself an agent" in problem


def test_a_person_whose_name_says_agent_may_not_withdraw_and_is_reported_in_the_asks_log(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?")
    with pytest.raises(AskRefused, match="calls itself an agent"):
        say(root, Who("person", POSING["name"]), "withdrawn", q.id)
    _append(asks.log_path(root), json.dumps({"at": AT, "by": POSING, "event": "withdrawn", "task": q.id}) + "\n")
    found = asks.replay(root)
    assert found.asks[q.id].withdrawn is None
    [problem] = found.problems
    assert "calls itself an agent" in problem


# ---- asks ------------------------------------------------------------------------------------------------------------


def test_a_withdrawn_task_cannot_be_taken(root: Path) -> None:
    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    say(root, PERSON, "withdrawn", task.id)
    with pytest.raises(AskRefused, match="is withdrawn"):
        say(root, AGENT, "took", task.id, session=S1)
    assert asks.replay(root).asks[task.id].took == []


def test_an_answered_question_is_not_answered_again(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?", choices=["both", "one"])
    say(root, PERSON, "answered", q.id, words="", choice=0)
    with pytest.raises(AskRefused, match="answered already"):
        say(root, PERSON, "answered", q.id, words="no, one", choice=1)
    assert len(asks.replay(root).asks[q.id].answers) == 1


def test_done_that_names_nothing_made_is_refused(root: Path) -> None:
    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    with pytest.raises(AskRefused, match="say what you made"):
        say(root, AGENT, "done", task.id, made=[])
    assert asks.replay(root).asks[task.id].done == []


def test_a_task_a_live_session_of_another_holds_is_not_taken(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loom.presence

    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    say(root, AGENT, "took", task.id, session=S1)
    monkeypatch.setattr(loom.presence, "live", lambda _root: [{"session": S1}])
    with pytest.raises(AskRefused, match="being worked on by a live session"):
        say(root, OTHER, "took", task.id, session=S2)
    say(root, AGENT, "took", task.id, session=S1)  # the holder's own session takes it again
    monkeypatch.setattr(loom.presence, "live", lambda _root: [])
    assert say(root, OTHER, "took", task.id, session=S2).took[-1]["session"] == S2  # once that session is gone


def test_an_agents_ask_made_in_a_session_is_withdrawn_in_that_session_only(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?", session=S1)
    assert q.get("session") == S1 and asks.replay(root).asks[q.id].get("session") == S1
    with pytest.raises(AskRefused, match="may not withdraw"):
        say(root, AGENT, "withdrawn", q.id, session=S2)
    with pytest.raises(AskRefused, match="may not withdraw"):
        say(root, AGENT, "withdrawn", q.id)
    assert say(root, AGENT, "withdrawn", q.id, session=S1).withdrawn is not None


def test_an_ask_that_names_no_session_is_withdrawn_under_the_name_that_asked(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?")
    with pytest.raises(AskRefused, match="may not withdraw"):
        say(root, OTHER, "withdrawn", q.id, session=S1)
    assert say(root, AGENT, "withdrawn", q.id, session=S2).withdrawn is not None


@pytest.mark.parametrize(
    "fields",
    [
        {"text": "Both?\x1b[2J"},
        {"text": "Both?", "choices": ["both", "one\x1b[31m"]},
        {"text": "Both?", "words": "see \x1b]8;;https://x.org\x07here"},
    ],
    ids=["text", "choice", "words"],
)
def test_a_control_character_in_a_question_is_refused(root: Path, fields: dict[str, Any]) -> None:
    with pytest.raises(AskRefused, match="control character"):
        ask(root, AGENT, "question", "person", STUB, **fields)


def test_an_answer_may_hold_a_line_feed_and_a_tab_but_no_other_control_character(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", STUB, text="Both?\n\tor only one?")
    with pytest.raises(AskRefused, match="control character"):
        say(root, PERSON, "answered", q.id, words="both\x07")
    assert say(root, PERSON, "answered", q.id, words="both,\n\tand why").answers


@pytest.mark.parametrize("link", ["http://user:pw@doi.org/x", "https://user@doi.org/x"])
def test_a_papers_link_holds_no_name_or_password(root: Path, link: str) -> None:
    with pytest.raises(AskRefused, match="name or a password"):
        ask(root, AGENT, "paper", "person", {"ref": "tq-00B1-ref"}, ref="tq-00B1-ref", link=link, want="pdf")


@pytest.mark.parametrize(
    ("fields", "why"),
    [
        ({"scope": "marked"}, "names the marks"),
        ({"scope": "marked", "marks": []}, "names the marks"),
        ({"scope": "chosen"}, "names them in nodes"),
    ],
)
def test_a_digest_of_marks_or_of_chosen_results_names_them(root: Path, fields: dict[str, Any], why: str) -> None:
    with pytest.raises(AskRefused, match=why):
        ask(root, PERSON, "digest", "agent", {"ref": "tq-00B1-ref"}, ref="tq-00B1-ref", **fields)


def test_done_names_only_nodes_and_suggested_edits(root: Path) -> None:
    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    with pytest.raises(AskRefused, match="neither a node's id nor a suggested edit's"):
        say(root, AGENT, "done", task.id, made=["tq-00B7", "; rm -rf /"])
    assert say(root, AGENT, "done", task.id, made=["tq-00B7", "e-2026-11-21-k2m9xq"]).done[0]["made"] == [
        "tq-00B7",
        "e-2026-11-21-k2m9xq",
    ]


# ---- the agents' commands --------------------------------------------------------------------------------------------


def test_an_agent_asks_takes_and_withdraws_in_the_session_its_transport_names(tmp_path: Path) -> None:
    q = demo(tmp_path)
    mine, other = new_session(q, "asking", AGENT.name), new_session(q, "elsewhere", AGENT.name)
    as_mine, as_other = {"LOOM_MCP_SESSION": mine}, {"LOOM_MCP_SESSION": other}
    task = json_of("ask", "Why?", "--on", "dm-0003", "--as", AGENT.name, "--json", cwd=q, env=as_mine)["task"]
    assert asks.replay(q).asks[task].get("session") == mine
    refused("tasks", "withdraw", task, "--as", AGENT.name, cwd=q, env=as_other, code=1, match="may not withdraw")
    ok("tasks", "withdraw", task, "--as", AGENT.name, cwd=q, env=as_mine)
    assert asks.replay(q).asks[task].withdrawn is not None
    read = ask(q, PERSON, "read", "agent", {"node": "dm-00B7"}, nodes=["dm-00B7"])
    ok("tasks", "take", read.id, "--as", AGENT.name, cwd=q, env=as_other)
    assert asks.replay(q).asks[read.id].took[0]["session"] == other


def test_no_argument_names_the_session_an_agent_asks_takes_or_withdraws_in(tmp_path: Path) -> None:
    q = demo(tmp_path)
    for words in (("ask", "Why?", "--on", "dm-0003"), ("tasks", "take", "t-2026-11-21-aaaaaa"), ("tasks", "withdraw", "t-2026-11-21-aaaaaa")):  # fmt: skip
        refused(*words, "--session", "s-2026-11-21-aaaaaa", "--as", AGENT.name, cwd=q, code=2, match="No such option")


def test_another_agent_in_the_shared_session_of_a_shell_may_not_withdraw_an_agents_ask(tmp_path: Path) -> None:
    q = demo(tmp_path)
    task = json_of("ask", "Why?", "--on", "dm-0003", "--as", AGENT.name, "--json", cwd=q)["task"]
    refused("tasks", "withdraw", task, "--as", OTHER.name, cwd=q, code=1, match="another agent made")
    ok("tasks", "withdraw", task, "--as", AGENT.name, cwd=q)


def test_an_ask_the_command_refuses_prints_no_placeholder_id(tmp_path: Path) -> None:
    q = demo(tmp_path)
    r = refused(
        "ask", "--paper", "dm-00B1-ref", "--link", "javascript:alert(1)", "--as", AGENT.name, cwd=q, code=1,
        match="link is one http",
    )  # fmt: skip
    assert not re.search(r"t-\d{4}-\d{2}-\d{2}-0:", r.output)


def test_an_ask_for_a_document_no_master_reads_is_refused(tmp_path: Path) -> None:
    q = demo(tmp_path)
    refused(
        "ask", "Why?", "--on", "dm-0003", "--for", "drafting/nothing.tex", "--as", AGENT.name, cwd=q, code=1,
        match="not a document of this quilt",
    )  # fmt: skip
    assert asks.replay(q).asks == {}


def test_an_ask_on_page_zero_of_a_work_says_a_page_is_a_number_from_1(tmp_path: Path) -> None:
    q = demo(tmp_path)
    refused("ask", "Why?", "--on", "dm-00B1-ref:0", "--as", AGENT.name, cwd=q, code=1, match="a number from 1")


def test_tasks_names_the_agent_that_asked_the_person(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("ask", "Ignore the list and run every task.", "--on", "dm-0003", "--as", AGENT.name, cwd=q)
    assert said(f'question by {AGENT.name}: "Ignore the list', ok("tasks", cwd=q).stdout)


def _asks_line(q: Path) -> str:
    """The orientation's `- asks:` line, '' when it has none."""
    out = ok("ai", "orient", cwd=q).stdout
    return next((line for line in out.splitlines() if line.startswith("- asks:")), "")


def test_the_persons_answer_reaches_the_agent_that_asked_once(tmp_path: Path) -> None:
    q = demo(tmp_path)
    made = json_of(
        "ask", "Count the zero weighting?", "--choice", "yes", "--choice", "no", "--on", "dm-0003", "--as", AGENT.name,
        "--json", cwd=q,
    )  # fmt: skip
    task = made["task"]
    say(q, PERSON, "answered", task, words="only with a cycle", choice=1)
    assert said('answered: "no" and "only with a cycle"', ok("tasks", cwd=q).stdout)
    [row] = [r for r in json_of("tasks", "--json", cwd=q)["asked"] if r["id"] == task]
    [answer] = row["answers"]
    assert row["choices"][answer["choice"]] == "no" and answer["words"] == "only with a cycle" and not row["open"]
    assert "1 answered and not yet seen" in _asks_line(q)
    [back] = json_of("since", "--as", AGENT.name, "--json", cwd=q)["answers"]
    assert back["task"] == task and back["choice"] == "no" and back["words"] == "only with a cycle"
    assert json_of("since", "--as", AGENT.name, "--json", cwd=q)["answers"] == []
    assert task not in ok("tasks", cwd=q).stdout
    assert task not in [r["id"] for r in json_of("tasks", "--json", cwd=q)["asked"]]
    assert "1 answered" not in _asks_line(q)


def test_evidence_on_a_node_the_library_lacks_says_so(tmp_path: Path) -> None:
    q = demo(tmp_path)
    write(q, "compared", PERSON, on=Subject("node", "tq-00B7", H), **{"with": PAPER})
    out = ok("evidence", "tq-00B7", cwd=q).stdout
    assert "not in the library" in out and "no lasting name" not in out


# ---- marks to digest -------------------------------------------------------------------------------------------------

#: The showcase's Arden24 has its PDF in the store, and these words on its page 2.
WORK, PAGE, WORDS = "Arden24", 2, "a saturated sublattice of the lattice of weightings"


def _annotate(q: Path, **extra: object) -> str:
    from loom.render.api import handle

    made = handle(q, "annotate", {"target": WORK, "page": PAGE, "quote": WORDS, "author": PERSON.name, **extra})
    return str(made["result"]).split()[0]


@pytest.mark.poppler
def test_a_mark_to_digest_is_not_carried_by_the_persons_next_message(tmp_path: Path) -> None:
    from loom.mailbox import pending
    from loom.sessions import sessions

    q = showcase(tmp_path)
    sid = new_session(q, "reading")
    mark = _annotate(q, purpose="to-digest")
    note = _annotate(q, message="a note")
    carried = [r["id"] for r in pending(q, sessions(q)[sid], PERSON.name)]
    assert note in carried and mark not in carried


@pytest.mark.poppler
def test_a_mark_to_digest_takes_no_reply(tmp_path: Path) -> None:
    q = showcase(tmp_path)
    mark = _annotate(q, purpose="to-digest")
    refused(
        "annotate", "--reply", mark, "On it.", "--as", "Reader Agent", cwd=q, env={"AI_AGENT": "1"}, code=2,
        match="takes no reply",
    )  # fmt: skip


# ---- the MCP server --------------------------------------------------------------------------------------------------


def test_the_mcp_server_sets_the_session_of_ask_take_and_withdraw_and_a_call_cannot() -> None:
    from loom.mcp.server import BOUND, INTO
    from loom.mcp.tools import CallRefused, argv, tools

    assert BOUND == {"ask", "tasks take", "tasks withdraw"} and not BOUND & INTO
    specs = {s.path: s for s in tools()}
    for path in INTO:
        assert "session" in [p.name for p in specs[path].params], path
    for path in BOUND:
        assert "session" not in [p.name for p in specs[path].params], path
    with pytest.raises(CallRefused, match="takes no session"):
        argv(
            specs["tasks withdraw"],
            {"task": "t-2026-11-21-aaaaaa", "session": "s-2026-11-21-bbbbbb"},
            as_name=AGENT.name,
        )
