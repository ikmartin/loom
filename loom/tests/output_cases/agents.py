"""Output cases for the agents commands -- `session`, `here`, `since`, `write` and `ai`; see `tests/output_cases/__init__.py`."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.output_cases.base import Case, ai_copy, author

S1 = "s-2026-09-16-p9z37z"
AGENT = ("--as", "Probe Agent")

KIND: dict[str, str] = {
    "session new": "report",
    "session use": "report",
    "session list": "report",
    "session rename": "report",
    "session close": "report",
    "session delete": "report",
    "session say": "report",
    "here": "report",
    "since": "report",
    "mcp": "running",
    "ai delete": "report",
    "ai init": "report",
    "ai orient": "raw",
    "ai mode": "raw",
    "write": "report",
    "ai drafts": "report",
    "ai close": "report",
    "ai reopen": "report",
    "ai annotations": "report",
    "ai refresh": "report",
    "sync init": "report",
    "sync fetch": "report",
    "sync status": "report",
    "sync documents": "report",
    "sync incorporate": "report",
    "sync publish": "report",
}


def closed_copy(q: Path) -> None:
    from tests.helpers import ok

    ai_copy(q)
    ok("ai", "close", "contribution.tex", "--yes", cwd=q)


def no_ai(q: Path) -> None:
    """A quilt without the agent layer, which `ai init` writes."""
    shutil.rmtree(q / ".loom/agents/instructions")


def marked(q: Path) -> None:
    """A person's annotation in the session, not yet carried by a message: what `session say` with no words carries."""
    from tests.helpers import ok

    author(q)
    ok("annotate", "dm-0003", "Is this right?", "--type", "question", cwd=q)


NOWHERE = ("--session", "no-such-session")

CASES: dict[str, list[Case]] = {
    "session new": [
        Case(("--name", "probe sitting")),
        Case(("--name", "probe sitting", "--no-use")),
        Case(("--name", "probe sitting", "--dry-run"), unchanged=True),
    ],
    "session use": [
        Case((S1,)),
        Case((S1, "--dry-run"), unchanged=True),
        Case(("no-such-session",), exit=2, why="names no session", unchanged=True),
    ],
    "session list": [Case(()), Case(("--all",))],
    "session rename": [
        Case((S1, "--name", "A new title")),
        Case((S1, "--name", "A new title", "--dry-run"), unchanged=True),
        Case(("no-such-session", "--name", "x"), exit=2, why="names no session", unchanged=True),
    ],
    "session close": [
        Case(()),
        Case((S1,)),
        Case((S1, "--dry-run"), unchanged=True),
        Case(("no-such-session",), exit=2, why="names no session", unchanged=True),
    ],
    "session delete": [
        Case((S1,)),
        Case((S1, "--dry-run"), unchanged=True),
        Case((S1, "--purge", "--yes", "--as", "A. Author")),
        Case((S1, "--purge", "--dry-run", "--as", "A. Author"), unchanged=True),
        Case(
            (S1, "--purge", "--as", "A. Author"),
            exit=2,
            why="--purge with nobody to ask and no --yes",
            unchanged=True,
        ),
        Case(("no-such-session",), exit=2, why="names no session", unchanged=True),
    ],
    "session say": [
        Case(("Read it; one objection.", *AGENT)),
        Case(("Have a look.", "--as", "A. Author")),
        Case(("--session", S1, "--as", "Tester"), setup=marked),
        Case(("Have a look.", "--as", "A. Author", "--dry-run"), unchanged=True),
        Case(("--as", "Somebody Else"), exit=2, why="no words and nothing marked", unchanged=True),
        Case(("hello", *NOWHERE, "--as", "A. Author"), exit=2, why="names no session", unchanged=True),
    ],
    "here": [Case((), why="nothing serves the quilt", unchanged=True)],
    "since": [
        Case(AGENT, setup=marked, why="a first look, with a person's annotation in the session"),
        Case((*AGENT, "--dry-run"), setup=marked, unchanged=True),
        Case((), env=(("AI_AGENT", "1"),), exit=2, why="an agent that has not said who it is", unchanged=True),
    ],
    "ai delete": [
        Case(("--by", "agent", "--yes", "--as", "Tester"), why="an agent's annotation, which its next look reports"),
        Case(("--target", "dm-0003", "--before", "2026-09-17", "--yes", "--as", "Tester"), why="every filter together"),
        Case(("--by", "The loom demo", "--dry-run"), unchanged=True),
        Case(("--before", "2000-01-01", "--yes", "--as", "Tester"), unchanged=True, why="nothing matches"),
        Case(("--by", "agent", "--as", "Tester"), exit=2, unchanged=True, why="no --yes and no terminal to ask"),
        Case((), exit=2, why="names nothing to delete", unchanged=True),
        Case(("--target", "dm-9999", "--yes"), exit=2, why="names no key", unchanged=True),
        Case(
            ("--by", "agent", "--yes"),
            env=(("AI_AGENT", "1"),),
            exit=2,
            unchanged=True,
            why="the author's, refused under an agent",
        ),
    ],
    "ai init": [
        Case((), setup=no_ai),
        Case((), why=".loom/agents/instructions/ exists: refreshes it"),
        Case(("--dry-run",), setup=no_ai, unchanged=True),
    ],
    "ai orient": [Case(()), Case(NOWHERE, exit=2, why="names no session")],
    "write": [
        Case(("state", "Goals: the parity theorem.", *AGENT)),
        Case(("Calloway14", "## [overview]\nA reading of the paper.", *AGENT), why="a work's overview"),
        Case(("state", "Goals.", "--dry-run", *AGENT), unchanged=True),
        Case(
            ("state", "Goals.", "--base", "sha256:00", *AGENT),
            exit=2,
            unchanged=True,
            why="a page not yet written takes no --base",
        ),
        Case(("state", "See [](quilt:dm-9999).", *AGENT), exit=2, unchanged=True, why="a link that names nothing"),
        Case(("Nobody99", "Goals.", *AGENT), exit=2, unchanged=True, why="names no work"),
        Case(("state", " ", *AGENT), exit=2, unchanged=True, why="nothing to write"),
    ],
    "ai mode": [
        Case(("flow",)),
        Case(("referee",), setup=no_ai, why="no ai/: the shipped copy"),
        Case(("brainstorm",), exit=2, unchanged=True, why="a mode loom does not ship"),
    ],
    "ai drafts": [Case(()), Case((), setup=ai_copy), Case(("--closed",), setup=closed_copy)],
    "ai close": [
        Case(("contribution.tex", "--yes"), setup=ai_copy),
        Case(("contribution.tex", "--dry-run"), setup=ai_copy, unchanged=True),
    ],
    "ai reopen": [
        Case(("contribution.tex",), setup=closed_copy),
        Case(("contribution.tex", "--dry-run"), setup=closed_copy, unchanged=True),
    ],
    "ai annotations": [
        Case((), why="every annotation"),
        Case(("--by", "The loom demo", "--type", "revision", "--status", "open")),
        Case(("--target", "dm-0003/proof")),
        Case(("--by", "Nobody"), why="nothing matches"),
        Case(("--target", "dm-9999"), exit=2, unchanged=True, why="names no key"),
        Case(NOWHERE, exit=2, unchanged=True, why="an annotation belongs to no session"),
    ],
    "ai refresh": [
        Case(("contribution.tex",), setup=ai_copy),
        Case(("contribution.tex", "--dry-run"), setup=ai_copy, unchanged=True),
        Case(("no-such-copy.tex",), exit=2, why="names no agent document", unchanged=True),
    ],
}
