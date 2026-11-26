"""The cases of Review's endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.render.serve import ServeSession
from tests.unit.render._serve import get
from tests.unit.render.write_api._cases import (
    Serve,
    case,
    refuses,
    succeeds,
    synthetic,
)


@case("review-accept")
def _review_accept(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.records.store import Records
    from loom.scan.quilt import load_quilt

    s, root = synthetic(serve, tmp_path, watch=False)
    monkeypatch.setattr("loom.cli.review._master_compiles", lambda _result, _master=None: (True, ""))
    # accepting is the author's, whatever reviewer an agent names beside itself
    agent = {"reviewer": "The synthetic quilt", "keys": ["sy-0001"], "author": "Referee (Agent)"}
    refuses(s, "review-accept", agent, 403, "author-only", "only the author accepts")
    refuses(
        s, "review-accept", {"reviewer": "The synthetic quilt", "keys": ["sy-9999"]}, 409, "not-unresolved", "sy-9999"
    )
    # the fixture's acceptance of sy-0001 is stale; accepting records a fresh one beside it, and the queue loses it
    builds = s.builds
    stale = Records(root, load_quilt(root).history_dir).latest["sy-0001"]
    answer = succeeds(s, "review-accept", {"reviewer": "The synthetic quilt", "keys": ["sy-0001", "sy-000B"]})
    assert answer["result"] == "accepted 1 of 2" and answer["accepted"] == ["sy-0001"]
    assert answer["refused"][0]["key"] == "sy-000B" and "basis" in answer["refused"][0]["why"]
    fresh = Records(root, load_quilt(root).history_dir).latest["sy-0001"]
    assert fresh != stale and fresh.author == "The synthetic quilt", fresh
    assert s.builds == builds + 1
    raw = get(s.url + "build/manifest.json")[2]
    assert not [r for r in json.loads(raw)["unresolved"] if r["key"] == "sy-0001"]


# ---- Review's lists and asks (docs/specs/evidence.md §6, §7) ----------------------------------------------------------


def _asked(serve: Serve, tmp_path: Path) -> tuple[ServeSession, Path, str]:
    """The synthetic quilt served, with an agent's question to the person and a person's ask of an agent in its log."""
    from loom.evidence.asks import ask
    from loom.evidence.subjects import Who

    s, root = synthetic(serve, tmp_path, watch=False)
    question = ask(
        root,
        Who("agent", "Probe Agent"),
        "question",
        "person",
        {"label": "sy-0001"},
        text="Both?",
        choices=["both", "one"],
    )
    ask(root, Who("person", "The synthetic quilt"), "read", "agent", {"node": "sy-00B7"}, nodes=["sy-00B7"])
    return s, root, question.id


@case("review-counts")
def _review_counts(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root, _question = _asked(serve, tmp_path)
    counted = succeeds(s, "review-counts", {})
    assert counted["kinds"]["questions"] == 1 and counted["agents"] == 1 and counted["everything"] >= 1


@case("review-list")
def _review_list(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root, question = _asked(serve, tmp_path)
    listed = succeeds(s, "review-list", {"kind": "questions"})
    assert isinstance(listed["gen"], int)
    [group] = listed["groups"]
    assert group["kind"] == "questions" and group["rows"][0]["question"] == question
    agents = succeeds(s, "review-list", {"kind": "agents"})
    [row] = agents["groups"][0]["rows"]
    assert row["kind"] == "agents" and row["what"] == "read"
    refuses(s, "review-list", {"kind": "problems"}, 400, "bad-field", "kind is")


@case("review-row")
def _review_row(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root, question = _asked(serve, tmp_path)
    opened = succeeds(s, "review-row", {"row": f"questions:{question}"})
    assert opened["row"]["choices"] == ["both", "one"] and opened["body"] == {}
    refuses(s, "review-row", {"row": "questions:t-2026-11-21-zzzzzz"}, 404, "no-such-row", "reload")


@case("review-answer")
def _review_answer(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.evidence.asks import replay

    s, root, question = _asked(serve, tmp_path)
    agent = {"question": question, "choice": 0, "author": "Referee (Agent)"}
    refuses(s, "review-answer", agent, 403, "author-only", "the person's")
    # another person named is recorded as the reviewer, and the answer says so
    said = succeeds(
        s, "review-answer", {"question": question, "choice": 1, "text": "and say why", "author": "B. Other"}
    )
    assert said["result"] == "answered as The synthetic quilt, the reviewer"
    answer = replay(root).asks[question].answers[0]
    assert answer["choice"] == 1 and answer["words"] == "and say why"
    assert answer["by"] == {"kind": "person", "name": "The synthetic quilt"}
    refuses(s, "review-answer", {"question": question, "text": "again"}, 409, "closed", "answered")


@case("review-task")
def _review_task(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.evidence.asks import replay

    s, root = synthetic(serve, tmp_path, watch=False)
    made = succeeds(
        s,
        "review-task",
        {"kind": "ask", "on": {"key": "sy-0001", "quote": "a pair"}, "text": "Is this the usual pair?"},
    )
    found = replay(root).asks[made["task"]]
    assert found.what == "ask" and found.to == "agent" and found.on["block"]["key"] == "sy-0001"
    assert made["result"] == "asked" and found.origin == ("drafting/main.tex",)
    refuses(s, "review-task", {"kind": "formalize", "on": {"result": "sy-0001"}}, 400, "bad-field", "formal-ask")
    # the drafts it is for are the person's documents, named by path: not a path that is no document, nor an agent's copy
    stray = {"kind": "ask", "on": {"key": "sy-0001"}, "text": "Is this used?", "docs": ["not/a/doc.tex"]}
    refuses(s, "review-task", stray, 400, "bad-field", "not/a/doc.tex is not one of your documents")
    copy = {**stray, "docs": [".loom/agents/copies/aidoc.tex"]}
    refuses(s, "review-task", copy, 400, "bad-field", "aidoc.tex is not one of your documents")
    refuses(s, "review-task", {**stray, "docs": "drafting/talk.tex"}, 400, "bad-field", "docs is a list")
    named = succeeds(s, "review-task", {**stray, "docs": ["drafting/talk.tex"]})
    assert replay(root).asks[named["task"]].origin == ("drafting/talk.tex",)


@case("review-task-delete")
def _review_task_delete(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.evidence.asks import replay

    s, root, _question = _asked(serve, tmp_path)
    [task] = [a.id for a in replay(root).asks.values() if a.to == "agent"]
    succeeds(s, "review-task-delete", {"task": task})
    assert replay(root).asks[task].withdrawn is not None
    refuses(s, "review-task-delete", {"task": task}, 409, "closed", "withdrawn")
