"""Output cases for `loom formal`, formalization on this machine; see `tests/output_cases/__init__.py`.

No case runs Lean or reaches the network: `on` is run only where it is refused, and `check` only where it refuses before the fence is tried, with formalization off or with no Lean project.
"""

from __future__ import annotations

from pathlib import Path

from tests.output_cases.base import Case

AGENT = (("CLAUDECODE", "1"),)


def turned_on(q: Path) -> None:
    """Formalization on for the quilt on this machine, the test's own HOME, with no Lean project made."""
    from loom.formal import switch

    switch.turn_on(q)


KIND: dict[str, str] = {
    "formal": "report",
    "formal on": "report",
    "formal off": "report",
    "formal check": "report",
}

CASES: dict[str, list[Case]] = {
    "formal": [
        Case((), unchanged=True),
        Case((), turned_on, unchanged=True, why="on, with no Lean project"),
    ],
    "formal on": [
        Case((), env=AGENT, exit=2, unchanged=True, why="the person's"),
    ],
    "formal off": [
        Case((), unchanged=True),
        Case((), turned_on, unchanged=True, why="on before"),
        Case((), env=AGENT, exit=2, unchanged=True, why="the person's"),
    ],
    "formal check": [
        Case((), exit=2, unchanged=True, why="formalization is off here"),
        Case((), turned_on, exit=2, unchanged=True, why="on, with no Lean project to check"),
    ],
}
