"""Output cases for what a person and an agent ask of each other, and what is known of a result -- `tasks`, `ask` and `evidence`; see `tests/output_cases/__init__.py`."""

from __future__ import annotations

import json
from pathlib import Path

from tests.output_cases.base import Case

AGENT = ("--as", "Probe Agent")
#: A person's ask of an agent to read a stub, a person's question to an agent, and an agent's question to the person, under fixed ids.
READ, ASKED, QUESTION = "t-2026-11-21-read01", "t-2026-11-21-ask001", "t-2026-11-21-quest1"

KIND: dict[str, str] = {
    "tasks": "report",
    "tasks take": "report",
    "tasks done": "report",
    "tasks answer": "report",
    "tasks withdraw": "report",
    "ask": "report",
    "evidence": "report",
}


def asked(q: Path) -> None:
    """Three asks written as loom writes them, so a case can name each by its id."""
    person = {"kind": "person", "name": "A. Author"}
    agent = {"kind": "agent", "name": "Probe Agent"}
    at = "2026-11-21T09:00:00Z"
    lines = [
        {"event": "asked", "id": READ, "at": at, "by": person, "what": "read", "to": "agent", "on": {"node": "dm-00B7"}, "from": ["drafting/main.tex"], "words": "", "nodes": ["dm-00B7"]},
        {"event": "asked", "id": ASKED, "at": at, "by": person, "what": "ask", "to": "agent", "on": {"label": "dm-0003"}, "from": ["drafting/main.tex"], "words": "", "text": "Does the count need the median order?"},
        {"event": "asked", "id": QUESTION, "at": at, "by": agent, "what": "question", "to": "person", "on": {"label": "dm-0003"}, "from": ["drafting/main.tex"], "words": "", "text": "Digest both, or only the proposition?", "choices": ["both", "only the proposition"]},
    ]  # fmt: skip
    log = q / ".loom" / "records" / "asks" / "log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines), encoding="utf-8")


def in_a_session(q: Path) -> None:
    """The asks, and an agent's session made the active one, which `tasks take` records."""
    from loom.sessions import create, set_active

    asked(q)
    set_active(q, create(q, "reading", "Probe Agent").id)


CASES: dict[str, list[Case]] = {
    "tasks": [
        Case((), setup=asked),
        Case(("--all",), setup=asked),
        Case((), why="nothing is asked of anyone", unchanged=True),
    ],
    "tasks take": [
        Case((READ, *AGENT), setup=in_a_session),
        Case((READ, "--as", "A. Author"), setup=in_a_session, exit=2, why="a person's name", unchanged=True),
        Case(("t-2026-11-21-zzzzzz", *AGENT), setup=in_a_session, exit=1, why="names no ask", unchanged=True),
    ],
    "tasks done": [
        Case((READ, "--made", "dm-00B7", *AGENT), setup=asked),
        Case((QUESTION, "--made", "dm-00B7", *AGENT), setup=asked, exit=1, why="not asked of an agent", unchanged=True),
    ],
    "tasks answer": [
        Case((ASKED, "No: any linear order will do.", *AGENT), setup=asked),
        Case((READ, "words", *AGENT), setup=asked, exit=1, why="only a question is answered", unchanged=True),
    ],
    "tasks withdraw": [
        Case((QUESTION, *AGENT), setup=asked),
        Case((READ, *AGENT), setup=asked, exit=1, why="a person's ask, not its own", unchanged=True),
    ],
    "ask": [
        Case(
            (
                "Should the count include the zero weighting?",
                "--on",
                "dm-0003",
                "--choice",
                "yes",
                "--choice",
                "no",
                *AGENT,
            )
        ),
        Case(("--paper", "dm-00B1-ref", "--link", "https://doi.org/10.1000/example.17", *AGENT)),
        Case(("Why?", *AGENT), exit=1, why="says nothing of where", unchanged=True),
        Case(("Why?", "--on", "nowhere-at-all", *AGENT), exit=1, why="names nothing of the quilt", unchanged=True),
        Case(
            ("--paper", "dm-00B1-ref", "--link", "javascript:alert(1)", *AGENT),
            exit=1,
            why="a link to run",
            unchanged=True,
        ),
        Case(("Why?", "--on", "dm-0003", "--as", "A. Author"), exit=2, why="a person's name", unchanged=True),
    ],
    "evidence": [
        Case(("dm-0003",)),
        Case(("no:such-label",), exit=1, why="names no result", unchanged=True),
    ],
}
