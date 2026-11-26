"""Output cases for `loom formal`, formalization on this machine; see `tests/output_cases/__init__.py`.

No case runs Lean or reaches the network: `on` is run only where it is refused, and `check` only where it refuses before the fence is tried, with formalization off or with no Lean project. `read` reads a `lean` record written as loom's check would write it.
"""

from __future__ import annotations

from pathlib import Path

from tests.output_cases.base import Case

AGENT = (("CLAUDECODE", "1"),)


def turned_on(q: Path) -> None:
    """Formalization on for the quilt on this machine, the test's own HOME, with no Lean project made."""
    from loom.formal import switch

    switch.turn_on(q)


READER = ("--as", "Reader Agent")


def checked(q: Path) -> None:
    """A `lean` record of loom's stating the demo's dm-0004, as its check writes one, with the definition its statement names."""
    from loom.evidence.log import write
    from loom.evidence.subjects import Subject, Who

    h = "sha256:" + "a" * 64

    def decl(name: str, kind: str, names: dict[str, str], means: list[str], shown: str) -> dict[str, object]:
        return {"name": name, "kind": kind, "role": "states", "names": names, "statement": h, "axioms": [], "sorry": False, "means": means, "shown": shown}  # fmt: skip

    write(
        q,
        "lean",
        Who("loom"),
        on=Subject("label", "dm-0004", h),
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h},
        files={"lean/Formal/A.lean": h},
        declarations=[
            decl(
                "Formal.main",
                "theorem",
                {"label": "dm-0004"},
                ["Formal.Good"],
                "theorem Formal.main (n : Nat) : Formal.Good n",
            ),
            decl("Formal.Good", "def", {"label": "dm-0005"}, [], "def Formal.Good (n : Nat) : Prop :=\n  0 ≤ n"),
        ],
        assumed=[],
        uses=[],
        replay={"tool": "t", "exit": 0, "output": ""},
        ok=True,
    )


KIND: dict[str, str] = {
    "formal": "report",
    "formal on": "report",
    "formal off": "report",
    "formal check": "report",
    "formal read": "report",
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
    "formal read": [
        Case(("dm-0004",), exit=1, unchanged=True, why="no Lean recorded for it"),
        Case(("dm-0004",), checked, unchanged=True, why="the Lean to read"),
        Case(
            ("dm-0004", "--declaration", "Formal.main", "--reading", "Every $n$ is good.", *READER),
            checked,
            why="a reading of one part",
        ),
        Case(
            (
                "dm-0004",
                "--part",
                "(i)",
                "--part",
                "good",
                "--declaration",
                "Formal.main",
                "--declaration",
                "Formal.Good",
                "--reading",
                "Every $n$ is good.",
                "--reading",
                "$n$ is good when $n \\ge 0$.",
                "--difference",
                "None.",
                *READER,
            ),
            checked,
            why="parts and a difference",
        ),
        Case(
            ("dm-0004", "--declaration", "Formal.other", "--reading", "x", *READER),
            checked,
            exit=1,
            unchanged=True,
            why="a declaration loom did not record",
        ),
        Case(
            ("dm-0004", "--declaration", "Formal.main", "--reading", "x", "--as", "A. Author"),
            checked,
            exit=2,
            unchanged=True,
            why="a person's name",
        ),
    ],
}
