"""Output cases for an agent's commands on the library's web (`loom.cli.library.web`); see `tests/output_cases/__init__.py`.

The demo's library holds Calloway 2014 (`dm-0012-ref`) with its PDF and TeX source, and two works with neither; the writes read from that source, so only a digest, numbered by the stored PDF, needs the real pdftotext.
"""

from __future__ import annotations

from pathlib import Path

from tests.output_cases.base import Case

#: Calloway 2014, which holds a PDF and its TeX source.
WORK = "dm-0012-ref"
#: Manolache 2012, which holds neither.
BARE = "dm-0013-ref"
#: The stub `stub` makes: Calloway's Proposition 3.2, not read yet.
STUB = "dm-0Z01"
#: The statement `read_one` makes: Calloway's Proposition 3.3, its text given.
READ = "dm-0Z02"
AS = ("--as", "Claude Agent")
#: Proposition 3.2 as Calloway's source states it.
CLOSED = "Let $X$ be a Hausdorff space and $\\sigma$ an involution of $X$. Then $\\Fix(\\sigma)$ is closed in $X$."


def stub(q: Path) -> None:
    """A stub of Calloway's Proposition 3.2: known to stand there, its text not read yet."""
    from loom.library.node import Node
    from loom.library.store import write_node

    write_node(q, Node(id=STUB, taxon="proposition", number="3.2", source=WORK), new=True)


def read_one(q: Path) -> None:
    """Calloway's Proposition 3.3 with its text, which nobody has compared."""
    from loom.library.node import Node
    from loom.library.store import write_node

    body = "Let $X$ be a finite set and $\\sigma$ an involution of $X$. Then $|X| \\equiv |\\Fix(\\sigma)| \\pmod 2$.\n"
    write_node(q, Node(id=READ, taxon="proposition", number="3.3", source=WORK, body=body), new=True)


KIND: dict[str, str] = {
    "library node": "report",
    "library search": "report",
    "library uses": "report",
    "library rests-on": "report",
    "library stubs": "report",
    "library work": "report",
    "library fill": "report",
    "library propose": "report",
    "library correct": "report",
    "library digest": "report",
}

CASES: dict[str, list[Case]] = {
    "library node": [
        Case((STUB,), stub, unchanged=True, why="a stub"),
        Case((READ,), read_one, unchanged=True),
        Case((WORK,), exit=1, unchanged=True, why="a work, not a statement or a proof"),
    ],
    "library search": [
        Case(("finite", "set"), read_one, unchanged=True),
        Case(("nothing",), unchanged=True, why="nothing found"),
    ],
    "library uses": [
        Case((WORK,), unchanged=True),
        Case(("dm-9999",), exit=1, unchanged=True, why="names no node"),
    ],
    "library rests-on": [
        Case(("drafting/main.tex",), unchanged=True),
        Case(("dm-0003",), unchanged=True, why="a result of the draft"),
        Case(("nothing-here",), exit=1, unchanged=True, why="names no result or document"),
    ],
    "library stubs": [
        Case((), unchanged=True, why="none"),
        Case(("--work", WORK), stub, unchanged=True),
    ],
    "library work": [
        Case((WORK,), unchanged=True),
        Case((BARE,), unchanged=True, why="holds neither a PDF nor a source"),
        Case(("dm-9999",), exit=1, unchanged=True, why="names no work"),
    ],
    "library fill": [
        Case((STUB, "--from", "tex", "--body", CLOSED, *AS), stub),
        Case(
            (STUB, "--from", "tex", "--body", "Every gadget is unbounded.", *AS),
            stub,
            exit=1,
            unchanged=True,
            why="words not on its source",
        ),
        Case(
            (STUB, "--from", "tex", "--pages", "3", "--body", CLOSED, *AS),
            stub,
            exit=1,
            unchanged=True,
            why="pages are the PDF's",
        ),
        Case(
            (READ, "--from", "tex", "--body", CLOSED, *AS), read_one, exit=1, unchanged=True, why="has its text already"
        ),
        Case(
            (STUB, "--from", "tex", "--body", CLOSED, "--as", "A. Author"),
            stub,
            exit=2,
            unchanged=True,
            why="not an agent's name",
        ),
    ],
    "library propose": [
        Case((WORK, "--taxon", "proposition", "--number", "3.2", "--from", "tex", "--body", CLOSED, *AS)),
        Case(
            (WORK, "--taxon", "proposition", "--number", "3.2", "--from", "tex", "--body", CLOSED, *AS),
            stub,
            exit=1,
            unchanged=True,
            why="a node holds it already",
        ),
        Case(
            ("dm-9999", "--taxon", "lemma", "--from", "tex", "--body", CLOSED, *AS),
            exit=1,
            unchanged=True,
            why="names no work",
        ),
    ],
    "library correct": [
        Case(
            (READ, "--body", "Let $X$ be a finite set. Then $|X| \\equiv 0 \\pmod 2$.", "--why", "a test", *AS),
            read_one,
            why="nobody compared it: written",
        ),
        Case(("dm-9999", "--body", "Words.", "--why", "a test", *AS), exit=1, unchanged=True, why="names no node"),
    ],
    "library digest": [
        Case((WORK, "--scope", "all"), poppler=True, why="numbered by its stored PDF, one result waiting"),
        Case((BARE,), exit=1, unchanged=True, why="holds no TeX source"),
        Case(("dm-9999",), exit=1, unchanged=True, why="names no work"),
    ],
}
