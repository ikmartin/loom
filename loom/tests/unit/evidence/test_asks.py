"""Asks close by what they produce, never by being called done: a question by its answer, a formalization by Lean's acceptance, a paper by its file; a live session shows as working."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence import asks
from loom.evidence.asks import ask, open_asks, say, standing
from loom.evidence.log import replay as replay_evidence
from loom.evidence.log import write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here
from tests.unit.evidence._nothing import Nothing

H = "sha256:" + "a" * 64
PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Claude Code Agent")
LOOM = Who("loom")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T09:00:00Z")
    return tmp_path


class Library(Nothing):
    """A web that knows some nodes have bodies and some works hold documents."""

    def __init__(self, bodied: set[str] = frozenset(), held: set[tuple[str, str]] = frozenset()) -> None:  # type: ignore[assignment]
        self.bodied, self.held = bodied, held

    def stub(self, here: Here) -> bool | None:
        return False if here.name in self.bodied else None

    def holds(self, ref: str, want: str) -> bool | None:
        return (ref, want) in self.held


def _standing(root: Path, made: asks.Ask, web: Nothing | None = None, **kw):  # type: ignore[no-untyped-def]
    return standing(asks.replay(root).asks[made.id], replay_evidence(root), web or Nothing(), **kw)


def test_a_question_closes_by_its_answer(root: Path) -> None:
    q = ask(root, AGENT, "question", "person", {"ref": "tq-00C2-ref"}, text="Both?", choices=["both", "one"])
    assert _standing(root, q).open
    say(root, PERSON, "answered", q.id, words="", choice=0)
    after = _standing(root, q)
    assert not after.open and after.why == "answered"


def test_a_read_closes_when_every_stub_has_a_body_whoever_wrote_it(root: Path) -> None:
    t = ask(root, PERSON, "read", "agent", {"node": "tq-00B7"}, nodes=["tq-00B7", "tq-00B8"])
    assert _standing(root, t, Library({"tq-00B7"})).open
    say(root, AGENT, "done", t.id, made=["tq-00B7", "tq-00B8"])  # saying so closes nothing
    assert _standing(root, t, Library({"tq-00B7"})).open
    assert not _standing(root, t, Library({"tq-00B7", "tq-00B8"})).open
    assert _standing(root, t).open  # a web that knows no node keeps it open


def test_a_paper_closes_when_its_work_holds_the_document_wanted(root: Path) -> None:
    p = ask(
        root,
        AGENT,
        "paper",
        "person",
        {"ref": "tq-00B1-ref"},
        ref="tq-00B1-ref",
        link="https://doi.org/10.1000/x.17",
        want="pdf",
    )
    assert _standing(root, p, Library(held={("tq-00B1-ref", "tex")})).open
    assert not _standing(root, p, Library(held={("tq-00B1-ref", "pdf")})).open


def _lean(root: Path, target: Subject, statement: str, ok: bool = True) -> None:
    write(
        root,
        "lean",
        LOOM,
        on=target,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": H},
        files={"lean/A.lean": H},
        declarations=[
            {
                "name": "A.b",
                "kind": "theorem",
                "role": "states",
                "names": {target.kind: target.name},
                "statement": statement,
                "axioms": [],
                "sorry": False,
            }
        ],
        assumed=[],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=ok,
    )


def test_a_formalization_closes_when_lean_accepts_its_target_after_the_ask(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = Subject("label", "lem:b", H)
    t = ask(
        root, PERSON, "formalize", "agent", {"label": "lem:b"}, target=target.to_dict(), state=[], prove=[], assume=[]
    )
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    _lean(root, target, H, ok=False)
    assert _standing(root, t).open
    _lean(root, target, H)
    assert not _standing(root, t).open
    assert _standing(root, t, lean_now=lambda _r: False).open  # Lean changed since: not believed


def test_a_restatement_closes_when_lean_states_it_otherwise_than_attested(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = Subject("label", "lem:b", H)
    _lean(root, target, H)
    write(
        root,
        "attested",
        PERSON,
        on=target,
        lean=replay_evidence(root).records[0].id,
        statements={"A.b": H},
        closure=[],
        rulings=[],
    )
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    t = ask(root, PERSON, "restate", "agent", {"label": "lem:b"}, target=target.to_dict(), differs="it drops n > 0")
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T11:00:00Z")
    _lean(root, target, H)  # the same statement run again
    assert _standing(root, t).open
    _lean(root, target, "sha256:" + "c" * 64)
    assert not _standing(root, t).open


def test_a_which_result_closes_when_the_person_says_only_a_mention(root: Path) -> None:
    block = {"key": "thm:main/proof", "hash": H, "context": {}}
    t = ask(root, PERSON, "which-result", "agent", {"block": block}, cites="tq-00B1-ref")
    assert _standing(root, t).open
    write(root, "mention", PERSON, block=block, cites="tq-00B1-ref", undo=False)
    assert not _standing(root, t).open
    write(root, "mention", PERSON, block=block, cites="tq-00B1-ref", undo=True)
    assert _standing(root, t).open


def test_withdrawn_is_closed_and_a_taken_task_is_working_only_while_its_session_lives(root: Path) -> None:
    t = ask(root, PERSON, "read", "agent", {"node": "tq-00B7"}, nodes=["tq-00B7"])
    say(root, AGENT, "took", t.id, session="s-2026-11-21-a8k2rx")
    assert _standing(root, t, sessions=frozenset({"s-2026-11-21-a8k2rx"})).working
    assert not _standing(root, t).working
    say(root, PERSON, "withdrawn", t.id)
    after = _standing(root, t, sessions=frozenset({"s-2026-11-21-a8k2rx"}))
    assert not after.open and after.why == "withdrawn" and not after.working


def test_open_asks_leaves_out_what_is_closed_unless_asked(root: Path) -> None:
    a = ask(root, AGENT, "question", "person", {"ref": "tq-00C2-ref"}, text="One?")
    b = ask(root, AGENT, "question", "person", {"ref": "tq-00C2-ref"}, text="Two?")
    say(root, PERSON, "answered", a.id, words="yes")
    assert [s.ask.id for s in open_asks(root)] == [b.id]
    assert [s.ask.id for s in open_asks(root, closed=True)] == [a.id, b.id]


# ---- the agents' commands ---------------------------------------------------------------------------------------------


def _demo(tmp_path: Path) -> Path:
    from tests.unit._quilts import demo

    return demo(tmp_path)


def test_an_agent_asks_a_question_on_a_result_and_reads_the_answer(tmp_path: Path) -> None:
    from tests.helpers import json_of

    q = _demo(tmp_path)
    made = json_of(
        "ask",
        "Should the count include the zero weighting?",
        "--choice",
        "yes",
        "--choice",
        "no",
        "--on",
        "dm-0003",
        "--as",
        "Claude Code Agent",
        "--json",
        cwd=q,
    )
    task = made["task"]
    found = asks.replay(q).asks[task]
    assert found.to == "person" and found.get("choices") == ["yes", "no"]
    assert found.origin == ("drafting/main.tex",)
    say(q, PERSON, "answered", task, words="only when the quiver has a cycle", choice=1)
    listed = json_of("tasks", "--all", "--json", cwd=q)
    [row] = listed["asked"]
    assert row["id"] == task and not row["open"] and row["answers"][0]["choice"] == 1


def test_an_agent_asks_for_a_paper_and_a_person_name_is_refused(tmp_path: Path) -> None:
    from tests.helpers import json_of, refused

    q = _demo(tmp_path)
    made = json_of(
        "ask",
        "--paper",
        "dm-00B1-ref",
        "--link",
        "https://doi.org/10.1000/x.17",
        "--as",
        "Claude Code Agent",
        "--json",
        cwd=q,
    )
    assert asks.replay(q).asks[made["task"]].get("want") == "pdf"
    refused(
        "ask",
        "--paper",
        "dm-00B1-ref",
        "--link",
        "javascript:alert(1)",
        "--as",
        "Claude Code Agent",
        cwd=q,
        code=1,
        match="link",
    )
    refused("ask", "Why?", "--on", "dm-0003", "--as", "A. Author", cwd=q, code=2, match="not an agent's name")


def test_an_agent_takes_a_task_in_its_session_and_withdraws_only_its_own(tmp_path: Path) -> None:
    from tests.helpers import json_of, ok, refused

    q = _demo(tmp_path)
    t = ask(q, PERSON, "read", "agent", {"node": "dm-00B7"}, nodes=["dm-00B7"])
    ok("session", "new", "--name", "reading", "--as", "Claude Code Agent", cwd=q)
    json_of("tasks", "take", t.id, "--as", "Claude Code Agent", "--json", cwd=q)
    assert asks.replay(q).asks[t.id].took
    refused("tasks", "withdraw", t.id, "--as", "Claude Code Agent", cwd=q, code=1, match="may not withdraw")
    listed = json_of("tasks", "--json", cwd=q)
    assert [r["id"] for r in listed["tasks"]] == [t.id]


def test_evidence_reads_a_results_status_and_records(tmp_path: Path) -> None:
    from tests.helpers import json_of, refused

    q = _demo(tmp_path)
    found = json_of("evidence", "dm-0003", "--json", cwd=q)
    assert [s["lean"] for s in found["status"]] == ["none"] and found["records"] == []
    refused("evidence", "no:such-label", cwd=q, code=1, match="no result")


def test_the_agents_commands_are_agents_and_their_tools_read_or_write(tmp_path: Path) -> None:
    from loom.ai.layout import ACTS, AGENT_COMMANDS

    for command, act in {
        "tasks": "read",
        "evidence": "read",
        "ask": "write",
        "tasks take": "write",
        "tasks done": "write",
        "tasks answer": "write",
        "tasks withdraw": "write",
    }.items():
        assert command in AGENT_COMMANDS and ACTS[command] == act, command
