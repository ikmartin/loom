"""The library's web over the node store's files (`LibraryWeb`), and a node's status read through it: the spec's nine example nodes, `docs/specs/nodes.md` §12."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from loom.evidence.asks import ask, open_asks
from loom.evidence.log import replay, write
from loom.evidence.memo import read_files
from loom.evidence.status import status
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here, Joined, LibraryWeb
from loom.library.node import node_hash
from loom.library.store import folder
from tests.unit.library._store import quilt

PERSON = Who("person", "A. Author")
LOOM = Who("loom")


def h(c: str) -> str:
    return "sha256:" + c * 64


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    return quilt(tmp_path)


def _file(root: Path, node: str) -> Path:
    return folder(root) / f"{node}.node"


def _rewrite(root: Path, node: str, old: str, new: str) -> None:
    path = _file(root, node)
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _status(root: Path, node: str) -> Any:
    return status(replay(root), LibraryWeb(root), Here("node", node), lean_now=lambda r: True)


def test_a_node_is_named_by_the_hash_of_its_whole_file_and_only_statements_and_proofs_are_subjects(root: Path) -> None:
    web = LibraryWeb(root)
    lemma = web.subject(Here("node", "tq-00K3"))
    assert lemma == Subject("node", "tq-00K3", node_hash(_file(root, "tq-00K3").read_bytes()))
    assert web.subject(Here("node", "tq-00K3-proof00")) is not None
    # an id in another case is another node, though a file system blind to case would open this file for it
    for other in ("tq-00A1-ref", "tq-00A1-macros", "tq-9999", "not an id", "TQ-00K3"):
        assert web.subject(Here("node", other)) is None, other
    assert web.subject(Here("block", "tq-00K3")) is None


def test_what_a_statement_uses_is_followed_through_the_library_and_a_stub_is_an_empty_statement(root: Path) -> None:
    web = LibraryWeb(root)
    definition = web.subject(Here("node", "tq-00A4"))
    assert definition is not None
    assert web.closure(Here("node", "tq-00K3")) == {("node", "tq-00A4"): definition.hash}
    assert web.stub(Here("node", "tq-00B7")) is True and web.stub(Here("node", "tq-00K3")) is False
    assert web.texts(("node", "tq-00A4")) == {definition.hash}
    assert web.resolve(("node", "tq-00A4"), Here("node", "tq-00K3")) == definition.hash


def test_a_nodes_notation_is_unknown_until_its_works_macros_are_read(root: Path) -> None:
    assert LibraryWeb(root).notation(Here("node", "tq-00K3")) is None


def test_a_file_that_does_not_read_is_no_text(root: Path) -> None:
    _file(root, "tq-00A4").write_text("not a node\n", encoding="utf-8")
    web = LibraryWeb(root)
    assert web.subject(Here("node", "tq-00A4")) is None
    assert web.closure(Here("node", "tq-00K3")) == {}


def test_a_quilt_with_no_library_answers_nothing(tmp_path: Path) -> None:
    web = LibraryWeb(tmp_path)
    assert web.subject(Here("node", "tq-00K3")) is None and web.stub(Here("node", "tq-00K3")) is None


def test_a_stub_reads_stub_and_a_compared_node_matches_until_its_file_changes(root: Path) -> None:
    assert _status(root, "tq-00B7").reading == "stub"
    assert _status(root, "tq-00A4").reading == "unchecked"
    on = LibraryWeb(root).subject(Here("node", "tq-00A4"))
    write(root, "compared", PERSON, on=on, **{"with": {"ref": "tq-00A1-ref", "pdf": h("4"), "pages": "4"}})
    assert _status(root, "tq-00A4").reading == "matches"


def test_a_header_changed_alone_on_a_compared_node_reads_not_compared(root: Path) -> None:
    """A node's hash is its whole file, so a page number corrected in its header asks for the match again, as a change to its body does."""
    on = LibraryWeb(root).subject(Here("node", "tq-00A4"))
    write(root, "compared", PERSON, on=on, **{"with": {"ref": "tq-00A1-ref", "pdf": h("4"), "pages": "4"}})
    _rewrite(root, "tq-00A4", 'pages = "4"', 'pages = "5"')
    found = _status(root, "tq-00A4")
    assert found.reading == "unchecked" and found.compared_before


def _lean_and_attest(root: Path, node: str) -> None:
    web = LibraryWeb(root)
    on = web.subject(Here("node", node))
    assert on is not None
    declaration = {"name": "lem", "kind": "theorem", "role": "states", "names": {"node": node}, "statement": h("5"), "axioms": [], "sorry": False}  # fmt: skip
    record = write(root, "lean", LOOM, on=on, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, files={"lean/A.lean": h("8")}, declarations=[declaration], assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    closure = [{k[0]: k[1], "hash": v} for k, v in sorted(web.closure(Here("node", node)).items())]
    write(root, "attested", PERSON, on=on, lean=record.id, statements={"lem": h("5")}, closure=closure, rulings=[])


def test_nothing_typeset_with_a_works_unknown_notation_reads_formalized(root: Path) -> None:
    """Proved, attested, itself and all it uses compared: still not formalized while nobody has been shown the notation its work's macros give it."""
    web = LibraryWeb(root)
    for node in ("tq-00K3", "tq-00A4"):
        write(root, "compared", PERSON, on=web.subject(Here("node", node)), **{"with": {"ref": "tq-00A1-ref", "pdf": h("4")}})  # fmt: skip
    _lean_and_attest(root, "tq-00K3")
    found = _status(root, "tq-00K3")
    assert found.lean == "unattested" and found.unattested_notation is None and found.attestation is not None


def test_a_used_node_changed_is_a_cause_of_an_attestation_no_longer_holding(root: Path) -> None:
    _lean_and_attest(root, "tq-00K3")
    _rewrite(root, "tq-00A4", "compact", "closed")
    found = _status(root, "tq-00K3")
    assert found.lean == "changed" and [c.key for c in found.causes] == [("node", "tq-00A4")]


def test_a_drafts_result_resting_on_a_node_whose_notation_is_unknown_has_unknown_notation(root: Path) -> None:
    class Draft:
        def notation(self, here: Here) -> dict[str, str]:
            return {"Zcyc": h("9")}

        def closure(self, here: Here) -> dict[tuple[str, str], str]:
            return {("label", "lem:a"): h("a"), ("node", "tq-00A4"): h("b")}

    joined = Joined(Draft(), LibraryWeb(root))  # type: ignore[arg-type]
    assert joined.notation(Here("block", "k1")) is None
    assert Joined(Draft(), LibraryWeb(root.parent / "none")).notation(Here("block", "k1")) == {"Zcyc": h("9")}  # type: ignore[arg-type]


def test_the_asks_default_web_is_the_library_so_a_read_closes_when_its_stub_gains_a_body(root: Path) -> None:
    read = ask(root, PERSON, "read", "agent", {"node": "tq-00B7"}, origin=["drafting/main.tex"], nodes=["tq-00B7"])
    assert [s.ask.id for s in open_asks(root)] == [read.id]
    _file(root, "tq-00B7").write_text(
        _file(root, "tq-00B7").read_text(encoding="utf-8") + "A lemma.\n", encoding="utf-8"
    )
    assert open_asks(root) == []


def test_a_kept_read_rests_on_every_node_file(root: Path) -> None:
    files = read_files(root)
    assert folder(root) in files and _file(root, "tq-00K3") in files
