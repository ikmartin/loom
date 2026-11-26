"""The asks log: each ask in its shape, asked by the hand its kind allows; events said only by whoever may say them, and found whatever order a merge left them in."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.evidence import asks
from loom.evidence.asks import AskRefused, ask, replay, say
from loom.evidence.subjects import Who

H = "sha256:" + "a" * 64
PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Claude Code")
OTHER = Who("agent", "Codex")
STUB = {"node": "tq-00B7"}


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T09:00:00Z")
    return tmp_path


def _question(root: Path, by: Who = AGENT) -> asks.Ask:
    return ask(
        root,
        by,
        "question",
        "person",
        {"ref": "tq-00C2-ref", "page": 7},
        origin=["drafting/main.tex"],
        text="Digest both?",
        choices=["both", "only the proposition"],
    )


def test_a_person_asks_an_agent_to_read_and_an_agent_takes_it(root: Path) -> None:
    made = ask(root, PERSON, "read", "agent", STUB, origin=["drafting/main.tex"], nodes=["tq-00B7"])
    assert made.id.startswith("t-2026-11-21-") and made.origin == ("drafting/main.tex",)
    after = say(root, AGENT, "took", made.id, session="s-2026-11-21-a8k2rx")
    assert after.took[0]["session"] == "s-2026-11-21-a8k2rx"
    assert replay(root).asks[made.id].took == after.took


@pytest.mark.parametrize(
    ("by", "what", "to", "fields"),
    [
        (AGENT, "read", "agent", {"nodes": ["tq-00B7"]}),
        (PERSON, "paper", "person", {"ref": "tq-00B1-ref", "link": "https://example.org/p", "want": "pdf"}),
        (PERSON, "question", "person", {"text": "why?"}),
        (AGENT, "ask", "agent", {"text": "why?"}),
        (PERSON, "question", "agent", {"text": "why?"}),
    ],
)
def test_an_ask_comes_from_the_hand_its_kind_allows(root: Path, by: Who, what: str, to: str, fields: dict) -> None:
    with pytest.raises(AskRefused, match="is not asked of"):
        ask(root, by, what, to, STUB, **fields)


@pytest.mark.parametrize(
    "link", ["javascript:alert(1)", "file:///etc/passwd", "https://", "https://a b", "ftp://x.org/p"]
)
def test_a_papers_link_is_one_http_address(root: Path, link: str) -> None:
    with pytest.raises(AskRefused, match="link"):
        ask(root, AGENT, "paper", "person", {"ref": "tq-00B1-ref"}, ref="tq-00B1-ref", link=link, want="pdf")


def test_a_question_to_a_person_offers_at_most_six_distinct_choices(root: Path) -> None:
    with pytest.raises(AskRefused, match="at most 6"):
        ask(root, AGENT, "question", "person", STUB, text="which?", choices=[str(n) for n in range(7)])
    with pytest.raises(AskRefused, match="the same"):
        ask(root, AGENT, "question", "person", STUB, text="which?", choices=["a", "a"])
    with pytest.raises(AskRefused, match="choices"):
        ask(root, PERSON, "ask", "agent", STUB, text="which?", choices=["a"])


def test_a_question_is_answered_with_a_choice_words_or_both(root: Path) -> None:
    q = _question(root)
    with pytest.raises(AskRefused, match="only the person answers"):
        say(root, AGENT, "answered", q.id, words="both", choice=0)
    with pytest.raises(AskRefused, match="choice"):
        say(root, PERSON, "answered", q.id, words="", choice=2)
    with pytest.raises(AskRefused, match="a choice, words, or both"):
        say(root, PERSON, "answered", q.id, words="  ")
    after = say(root, PERSON, "answered", q.id, words="and say why", choice=1)
    assert after.answers[0]["choice"] == 1


def test_only_a_person_or_the_asking_agent_withdraws(root: Path) -> None:
    q = _question(root)
    with pytest.raises(AskRefused, match="may not withdraw"):
        say(root, OTHER, "withdrawn", q.id)
    assert say(root, AGENT, "withdrawn", q.id).withdrawn is not None
    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    with pytest.raises(AskRefused, match="may not withdraw"):
        say(root, AGENT, "withdrawn", task.id)
    assert say(root, PERSON, "withdrawn", task.id).withdrawn is not None


def test_only_an_agent_takes_a_task_and_only_one_asked_of_an_agent(root: Path) -> None:
    q = _question(root)
    with pytest.raises(AskRefused, match="only an agent"):
        say(root, AGENT, "took", q.id, session="s-2026-11-21-a8k2rx")
    task = ask(root, PERSON, "read", "agent", STUB, nodes=["tq-00B7"])
    with pytest.raises(AskRefused, match="only an agent"):
        say(root, PERSON, "took", task.id, session="s-2026-11-21-a8k2rx")
    with pytest.raises(AskRefused, match="no ask"):
        say(root, AGENT, "took", "t-2026-11-21-zzzzzz", session="s-2026-11-21-a8k2rx")


def test_a_person_asks_an_agent_a_question_and_an_agent_answers_it(root: Path) -> None:
    made = ask(
        root,
        PERSON,
        "ask",
        "agent",
        {"ref": "tq-00C2-ref", "page": 7},
        text="Does the count need the median order?",
        quote="the median order",
    )
    with pytest.raises(AskRefused, match="only an agent answers"):
        say(root, PERSON, "answered", made.id, words="yes")
    assert say(root, AGENT, "answered", made.id, words="No: any linear order will do.").answers


def test_a_correct_is_on_the_node_and_a_which_result_on_the_citing_block(root: Path) -> None:
    ask(root, PERSON, "correct", "agent", {"node": "tq-00K3"}, text="page 12 has closed, not compact")
    with pytest.raises(AskRefused, match="on the node"):
        ask(root, PERSON, "correct", "agent", {"label": "lem:b"}, text="")
    block = {"key": "thm:main/proof", "hash": H, "context": {}}
    ask(root, PERSON, "which-result", "agent", {"block": block}, cites="tq-00B1-ref")
    with pytest.raises(AskRefused, match="citing block"):
        ask(root, PERSON, "which-result", "agent", STUB, cites="tq-00B1-ref")


def test_a_formalize_ask_names_its_target_and_boundary(root: Path) -> None:
    target = {"label": "lem:balanced", "hash": H}
    made = ask(
        root,
        PERSON,
        "formalize",
        "agent",
        {"label": "lem:balanced"},
        target=target,
        state=[{"label": "def:connected", "hash": H}],
        prove=[],
        assume=[{"node": "tq-00B7", "hash": H}],
    )
    assert made.get("target") == target
    with pytest.raises(AskRefused):
        ask(root, PERSON, "formalize", "agent", {"label": "lem:balanced"}, target=target, state=[], prove=[])


def test_an_event_above_its_ask_is_found_and_one_with_no_ask_is_reported(root: Path) -> None:
    q = _question(root)
    lines = asks.log_path(root).read_text(encoding="utf-8").splitlines()
    answer = {"at": "2026-11-21T10:00:00Z", "by": PERSON.to_dict(), "event": "answered", "task": q.id, "words": "both"}
    stray = {**answer, "task": "t-2026-11-21-zzzzzz"}
    asks.log_path(root).write_text(
        "\n".join([json.dumps(answer), json.dumps(stray), *lines, "{"]) + "\n", encoding="utf-8"
    )
    found = replay(root)
    assert found.asks[q.id].answers[0]["words"] == "both"
    assert len(found.problems) == 2
    assert "no ask in the log" in found.problems[0] and "not JSON" in found.problems[1]


def test_an_unreadable_line_is_a_lint_warning(tmp_path: Path) -> None:
    from tests.helpers import ok
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    path = q / asks.ASK_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"event": "asked"}\n', encoding="utf-8")
    out = ok("lint", cwd=q).output
    assert "foreign-asks" in out and asks.ASK_LOG in out
