"""The cases of the person's acts on a library result's text: comparing it with its paper, correcting it by hand, and taking or declining an agent's correction (`evidence.acts`, through `endpoints/library.py`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.render.write_api._cases import Serve, case, refuses, succeeds, synthetic

#: An agent, which reads and proposes but does none of these.
AGENT = "Referee (Agent)"


def _library(serve: Serve, tmp_path: Path) -> tuple[object, Path]:
    """The synthetic quilt, served, with the spec's example nodes in its library: a definition, a lemma and a proposition of a work holding its documents, and a stub of a work loom holds only as an entry."""
    from loom.library.store import folder
    from tests.unit.library._examples import fixtures

    s, root = synthetic(serve, tmp_path, watch=False)
    folder(root).mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (folder(root) / name).write_bytes(data)
    return s, root


def _hash(root: Path, node: str) -> str:
    from loom.evidence.web import Here, LibraryWeb

    found = LibraryWeb(root).subject(Here("node", node))
    assert found is not None
    return found.hash


def _proposal(root: Path, node: str) -> str:
    """An agent's correction of `node`, filed for the person since they compared its text: its id."""
    from loom.evidence import acts
    from loom.evidence.subjects import Who
    from loom.library.store import folder

    data = (folder(root) / f"{node}.node").read_bytes()
    _said, record = acts.propose(root, node, data.replace(b"compact", b"closed", 1), Who("agent", AGENT), "page 4")
    return record.id


@case("library-check")
def _library_check(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.evidence.log import replay

    s, root = _library(serve, tmp_path)
    shown = _hash(root, "tq-00A4")
    body = {"node": "tq-00A4", "hash": shown}
    refuses(s, "library-check", {**body, "author": AGENT}, 403, "author-only", "this is the person's")
    refuses(s, "library-check", {"node": "tq-9999", "hash": shown}, 404, "no-such-node", "tq-9999")
    refuses(s, "library-check", {**body, "hash": "sha256:" + "0" * 64}, 409, "changed", "changed since it was shown")
    refuses(s, "library-check", {"node": "tq-00B7", "hash": _hash(root, "tq-00B7")}, 409, "stub", "stub")
    refuses(s, "library-check", {"node": "tq-00A4"}, 400, "missing-field", "hash")
    assert "matches its paper" in succeeds(s, "library-check", body)["result"]
    [compared] = replay(root).about("node", "tq-00A4", of="compared")
    assert compared.on is not None and compared.on.hash == shown and compared.by.kind == "person"


@case("library-correct")
def _library_correct(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.evidence.log import replay

    s, root = _library(serve, tmp_path)
    shown = _hash(root, "tq-00A4")
    body = {
        "node": "tq-00A4",
        "hash": shown,
        "body": "A space is compact when every open cover has a finite subcover.\n",
    }
    refuses(s, "library-correct", {**body, "author": AGENT}, 403, "author-only", "this is the person's")
    refuses(s, "library-correct", {**body, "hash": "sha256:" + "0" * 64}, 409, "changed", "changed since it was shown")
    # the library's checks refuse a body naming a result it does not hold, and say so
    refuses(s, "library-correct", {**body, "body": "See Lemma~\\ref{tq-77ZZ}.\n"}, 400, "refused", "tq-77ZZ")
    answer = succeeds(s, "library-correct", body)
    assert answer["hash"] == _hash(root, "tq-00A4") != shown
    made = [r.get("how") for r in replay(root).about("node", "tq-00A4", of="digested")]
    assert made == ["written"] and [r.on.hash for r in replay(root).about("node", "tq-00A4", of="compared") if r.on] == [answer["hash"]]  # fmt: skip


@case("library-correction-take")
def _library_correction_take(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.evidence import acts
    from loom.evidence.subjects import Who

    s, root = _library(serve, tmp_path)
    acts.check(root, "tq-00A4", _hash(root, "tq-00A4"), Who("person", "The synthetic quilt"))
    proposal = _proposal(root, "tq-00A4")
    refuses(s, "library-correction-take", {"correction": proposal, "author": AGENT}, 403, "author-only", "this is the person's")  # fmt: skip
    refuses(s, "library-correction-take", {"correction": "ev-2026-11-21-zzzzzz"}, 404, "no-such-proposal", "ev-2026-11-21-zzzzzz")  # fmt: skip
    before = _hash(root, "tq-00A4")
    assert "took the correction" in succeeds(s, "library-correction-take", {"correction": proposal})["result"]
    assert _hash(root, "tq-00A4") != before
    # taken, the text it was made against is gone
    refuses(s, "library-correction-take", {"correction": proposal}, 409, "changed", "changed since it was shown")


@case("library-correction-decline")
def _library_correction_decline(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.evidence import acts
    from loom.evidence.log import replay
    from loom.evidence.subjects import Who

    s, root = _library(serve, tmp_path)
    acts.check(root, "tq-00A4", _hash(root, "tq-00A4"), Who("person", "The synthetic quilt"))
    proposal = _proposal(root, "tq-00A4")
    refuses(s, "library-correction-decline", {"correction": proposal, "author": AGENT}, 403, "author-only", "this is the person's")  # fmt: skip
    before = _hash(root, "tq-00A4")
    assert succeeds(s, "library-correction-decline", {"correction": proposal})["result"] == "declined the correction"
    assert _hash(root, "tq-00A4") == before and replay(root).declined(proposal) is not None
    refuses(s, "library-correction-decline", {"correction": proposal}, 409, "closed", "")


@case("library-mention")
def _library_mention(serve: Serve, tmp_path: Path, _: pytest.MonkeyPatch) -> None:
    from loom.evidence.log import replay

    s, root = _library(serve, tmp_path)
    lemma = root / "drafting" / "nodes" / "sy-0002.tex"
    lemma.write_text(lemma.read_text(encoding="utf-8").replace("Every orbit", "Every orbit, as in \\cite{Smi24},", 1), encoding="utf-8")  # fmt: skip
    s.rebuild()  # type: ignore[attr-defined]
    [row] = [r for g in succeeds(s, "review-list", {"kind": "cited"})["groups"] for r in g["rows"]]
    body = {"citation": row["citation"]}
    refuses(s, "library-mention", {**body, "author": AGENT}, 403, "author-only", "this is the person's")
    refuses(s, "library-mention", {"citation": "tq-00A1-ref"}, 400, "bad-field", "REF@KEY")
    refuses(s, "library-mention", {"citation": "tq-00B1-ref@" + row["key"]}, 404, "no-such-citation", "does not cite")
    refuses(s, "library-mention", {**body, "undo": "yes"}, 400, "bad-field", "undo")
    assert succeeds(s, "library-mention", body)["result"] == "only a mention"
    [said] = replay(root).of_kind("mention")
    assert said.get("cites") == "tq-00A1-ref" and said.get("block")["key"] == row["key"] and said.get("undo") is False
    assert succeeds(s, "review-list", {"kind": "cited"})["groups"] == []
    assert succeeds(s, "library-mention", {**body, "undo": True})["result"] == "cites it again"
