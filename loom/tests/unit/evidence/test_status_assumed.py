"""One standard for a statement another's Lean assumes, a library node stated as an axiom or a result of the person's assumed for now: its own statement attested over Lean that elaborated, itself and every library node its statement uses read and compared, what only its proof uses not needed."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from loom.evidence.log import replay, write
from loom.evidence.status import status
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here

PERSON = Who("person", "A. Author")
LOOM = Who("loom")


def h(c: str) -> str:
    return "sha256:" + c * 64


def _text(name: str) -> str:
    """A text's hash, one for each block or node."""
    return "sha256:" + hashlib.sha256(name.encode()).hexdigest()


class Small:
    """A web of a few blocks and nodes, each with what its statement uses, spelled out."""

    def __init__(self, blocks: dict[str, str], nodes: dict[str, bool], uses: dict[str, list[tuple[str, str]]]) -> None:
        self.blocks, self.nodes, self.uses = blocks, nodes, uses

    def subject(self, here: Here) -> Subject | None:
        if here.kind == "node":
            return Subject("node", here.name, _text(here.name)) if here.name in self.nodes else None
        label = self.blocks.get(here.name)
        return Subject("label", label, _text(here.name)) if label else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        found = self.holder(key, near) if key[0] == "label" else Here("node", key[1])
        s = self.subject(found) if found else None
        return s.hash if s else None

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        return next((Here("block", k) for k, label in self.blocks.items() if key == ("label", label)), None)

    def texts(self, key: tuple[str, str]) -> set[str]:
        found = self.holder(key, Here("block", "")) if key[0] == "label" else Here("node", key[1])
        s = self.subject(found) if found else None
        return {s.hash} if s else set()

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        out: dict[tuple[str, str], str] = {}
        for kind, name in self.uses.get(here.name, []):
            got = self.resolve((kind, name), here)
            if got:
                out[(kind, name)] = got
        return out

    def notation(self, here: Here) -> dict[str, str]:
        return {}

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        return self.nodes.get(here.name) if here.kind == "node" else None

    def holds(self, ref: str, want: str) -> bool | None:
        return None

    def cited(self, here: Here) -> list[str]:
        return []


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    return tmp_path


def _decl(
    name: str, names: dict[str, str], *, kind: str = "theorem", axioms: list[str] | None = None
) -> dict[str, Any]:
    return {"name": name, "kind": kind, "role": "states", "names": names, "statement": h("5"), "axioms": axioms or [], "sorry": False}  # fmt: skip


def _attested(root: Path, web: Small, on: Subject, here: Here, declarations: list[dict[str, Any]]) -> None:
    """Lean on `on` that elaborated, and the person's attestation of all it states, its closure as it reads now."""
    record = write(root, "lean", LOOM, on=on, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, files={"lean/A.lean": h("8")}, declarations=declarations, assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    statements = {d["name"]: d["statement"] for d in declarations}
    closure = [{k[0]: k[1], "hash": v} for k, v in sorted(web.closure(here).items())]
    write(root, "attested", PERSON, on=on, lean=record.id, statements=statements, closure=closure, rulings=[])


def _compare(root: Path, web: Small, node: str) -> None:
    on = web.subject(Here("node", node))
    assert on is not None
    write(root, "compared", PERSON, on=on, **{"with": {"ref": "tq-00A1-ref", "pdf": h("9")}})


def _lean_of(root: Path, web: Small, here: Here) -> Any:
    return status(replay(root), web, here, lean_now=lambda r: True)


def test_an_assumed_library_node_counts_once_its_statement_is_attested_whatever_its_own_proof_rests_on(
    root: Path,
) -> None:
    # tq-00X1 states what lem:a assumes; its statement uses tq-00Z3, and its own Lean rests on tq-00Y2, unread
    web = Small({"kA": "lem:a"}, {"tq-00X1": False, "tq-00Y2": True, "tq-00Z3": False}, {"tq-00X1": [("node", "tq-00Z3")]})  # fmt: skip
    x = web.subject(Here("node", "tq-00X1"))
    assert x is not None
    _attested(root, web, x, Here("node", "tq-00X1"), [_decl("x", {"node": "tq-00X1"}, axioms=["ay"]), _decl("ay", {"node": "tq-00Y2"}, kind="axiom")])  # fmt: skip
    for node in ("tq-00X1", "tq-00Z3"):
        _compare(root, web, node)
    assert _lean_of(root, web, Here("node", "tq-00X1")).lean == "waiting"  # its own proof waits on tq-00Y2
    a = web.subject(Here("block", "kA"))
    assert a is not None
    _attested(root, web, a, Here("block", "kA"), [_decl("a", {"label": "lem:a"}, axioms=["ax"]), _decl("ax", {"node": "tq-00X1"}, kind="axiom")])  # fmt: skip
    found = _lean_of(root, web, Here("block", "kA"))
    assert found.lean == "formalized" and found.relative_to == (("node", "tq-00X1"),)


def test_an_assumed_statement_whose_own_statement_uses_an_unread_library_node_does_not_count(root: Path) -> None:
    # lem:b, which lem:a assumes, and tq-00X1, which lem:c assumes, each state something that uses tq-00Z3, a stub
    web = Small({"kA": "lem:a", "kB": "lem:b", "kC": "lem:c"}, {"tq-00X1": False, "tq-00Z3": True}, {"kB": [("node", "tq-00Z3")], "tq-00X1": [("node", "tq-00Z3")]})  # fmt: skip
    b, x = web.subject(Here("block", "kB")), web.subject(Here("node", "tq-00X1"))
    assert b is not None and x is not None
    _attested(root, web, b, Here("block", "kB"), [_decl("b", {"label": "lem:b"})])
    _attested(root, web, x, Here("node", "tq-00X1"), [_decl("x", {"node": "tq-00X1"}, kind="axiom")])
    _compare(root, web, "tq-00X1")
    a, c = web.subject(Here("block", "kA")), web.subject(Here("block", "kC"))
    assert a is not None and c is not None
    _attested(root, web, a, Here("block", "kA"), [_decl("a", {"label": "lem:a"}, axioms=["bx"]), _decl("bx", {"label": "lem:b"}, kind="axiom")])  # fmt: skip
    _attested(root, web, c, Here("block", "kC"), [_decl("c", {"label": "lem:c"}, axioms=["xx"]), _decl("xx", {"node": "tq-00X1"}, kind="axiom")])  # fmt: skip
    for key, assumed in (("kA", ("label", "lem:b")), ("kC", ("node", "tq-00X1"))):
        found = _lean_of(root, web, Here("block", key))
        assert found.lean == "waiting" and [(w.key, w.why) for w in found.waiting_on] == [(assumed, "unattested")], key


def _lean_uses(
    root: Path, web: Small, on: Subject, declarations: list[dict[str, Any]], uses: list[tuple[str, str]]
) -> Any:
    """Lean on `on` that elaborated and that uses the Lean of `uses`, each named by its hash now."""
    used = [{k: n, "hash": web.resolve((k, n), Here("block", "")) or web.subject(Here("node", n)).hash} for k, n in uses]  # type: ignore[union-attr]  # fmt: skip
    return write(root, "lean", LOOM, on=on, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, files={"lean/A.lean": h("8")}, declarations=declarations, assumed=[], uses=used, replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip


def _attest_record(root: Path, web: Small, on: Subject, here: Here, record: Any) -> None:
    from loom.evidence.status import closure_now, statements_of

    closure = [{k[0]: k[1], "hash": v} for k, v in sorted(closure_now(web, here, [record]).items())]
    write(
        root, "attested", PERSON, on=on, lean=record.id, statements=statements_of(record), closure=closure, rulings=[]
    )


def test_a_result_reads_formalized_only_once_the_lean_its_lean_uses_is_attested_all_the_way_down(root: Path) -> None:
    # thm:t's Lean uses def:d's Lean, from def:d's own record, and def:d's uses def:e's
    web = Small({"kT": "thm:t", "kD": "def:d", "kE": "def:e"}, {}, {})
    t, d, e = (web.subject(Here("block", k)) for k in ("kT", "kD", "kE"))
    assert t is not None and d is not None and e is not None
    lean_e = _lean_uses(root, web, e, [_decl("e", {"label": "def:e"}, kind="def")], [])
    lean_d = _lean_uses(root, web, d, [_decl("d", {"label": "def:d"}, kind="def")], [("label", "def:e")])
    lean_t = _lean_uses(root, web, t, [_decl("t", {"label": "thm:t"})], [("label", "def:d")])
    _attest_record(root, web, t, Here("block", "kT"), lean_t)
    found = _lean_of(root, web, Here("block", "kT"))
    assert found.lean == "waiting" and [(w.key, w.why) for w in found.waiting_on] == [
        (("label", "def:d"), "unattested")
    ]
    _attest_record(root, web, d, Here("block", "kD"), lean_d)
    assert _lean_of(root, web, Here("block", "kT")).lean == "waiting", "def:d's own Lean rests on def:e's, not attested"
    _attest_record(root, web, e, Here("block", "kE"), lean_e)
    assert _lean_of(root, web, Here("block", "kT")).lean == "formalized"


def test_what_a_record_states_itself_is_covered_by_its_own_attestation(root: Path) -> None:
    # thm:t's record states def:d too, so thm:t's attestation holds for it, and def:d needs no record of its own
    web = Small({"kT": "thm:t", "kD": "def:d"}, {}, {})
    t = web.subject(Here("block", "kT"))
    assert t is not None
    lean_t = _lean_uses(root, web, t, [_decl("t", {"label": "thm:t"}), _decl("d", {"label": "def:d"}, kind="def")], [("label", "def:d")])  # fmt: skip
    _attest_record(root, web, t, Here("block", "kT"), lean_t)
    assert _lean_of(root, web, Here("block", "kT")).lean == "formalized"
