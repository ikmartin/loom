"""The cases of formalization's endpoints."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tests.unit.render.write_api._cases import Serve, case, refuses, succeeds, synthetic


def _lean(root: Path, label: str) -> tuple[Any, Any]:
    """A `lean` record loom wrote on the draft's result `label`, accepted: its block and the record."""
    from loom.evidence.log import write
    from loom.evidence.subjects import Who
    from loom.evidence.web import DraftWeb
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    web = DraftWeb(scan(load_quilt(root)))
    here = web.heres(label)[0]
    (root / "lean").mkdir(exist_ok=True)
    (root / "lean" / "A.lean").write_text("theorem a : True := trivial\n", encoding="utf-8")
    lean_file = "sha256:" + hashlib.sha256((root / "lean" / "A.lean").read_bytes()).hexdigest()
    declaration = {"name": "A.a", "kind": "theorem", "role": "states", "names": {"label": label}, "statement": "sha256:" + "a" * 64, "axioms": ["propext"], "sorry": False}  # fmt: skip
    record = write(root, "lean", Who("loom"), on=web.subject(here), project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64}, files={"lean/A.lean": lean_file}, declarations=[declaration], assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    return here, record


@case("formal-attest")
def _formal_attest(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.evidence.log import replay

    s, root = synthetic(serve, tmp_path, watch=False)
    here, record = _lean(root, "sy-0202")
    body = {"result": here.name, "observation": record.id}
    refuses(s, "formal-attest", {**body, "author": "Referee (Agent)"}, 403, "author-only", "this is the person's")
    refuses(s, "formal-attest", {**body, "result": "sy-9999"}, 404, "no-such-result", "sy-9999")
    refuses(s, "formal-attest", {**body, "observation": "ev-2026-11-21-zzzzzz"}, 409, "changed", "latest")
    refuses(s, "formal-attest", {"result": here.name}, 400, "missing-field", "observation")
    assert succeeds(s, "formal-attest", body)["result"] == "attested"
    attested = replay(root).about("label", "sy-0202", of="attested")
    assert [a.get("lean") for a in attested] == [record.id] and attested[0].by.name == "The synthetic quilt"


#: A result of the synthetic quilt's talk with no label, which loom never gives it.
UNLABELLED = "drafting/talk.tex#lemma:1"


@case("formal-plan")
def _formal_plan(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s, _root = synthetic(serve, tmp_path, watch=False)
    refuses(s, "formal-plan", {}, 400, "bad-field", "targets")
    refuses(s, "formal-plan", {"targets": ["sy-9999"]}, 404, "no-such-result", "sy-9999")
    # the theorem's proof uses a lemma, whose statement uses a definition: one to prove and one to state
    found = succeeds(s, "formal-plan", {"targets": ["sy-0003"]})
    assert [t["key"] for t in found["targets"]] == ["sy-0003"] and found["targets"][0]["doc"] == "drafting/main.tex"
    assert [r["result"] for r in found["state"]] == ["sy-0001"]
    assert [(r["result"], r["assume"]) for r in found["prove"]] == [("sy-0002", False)]
    assert found["stops"] == [] and found["before"] == [] and found["assume"] == []
    # assumed for now, the lemma is followed by its statement alone, which still uses the definition
    assumed = succeeds(s, "formal-plan", {"targets": ["sy-0003"], "assume": ["sy-0002"]})
    assert [(r["result"], r["assume"]) for r in assumed["prove"]] == [("sy-0002", True)]
    assert [r["result"] for r in succeeds(s, "formal-plan", {"targets": [UNLABELLED]})["stops"]] == [UNLABELLED]


@case("formal-ask")
def _formal_ask(serve: Serve, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.evidence.asks import replay

    s, root = synthetic(serve, tmp_path, watch=False)
    body = {"targets": ["sy-0003"]}
    refuses(s, "formal-ask", {**body, "author": "Referee (Agent)"}, 403, "author-only", "this is the person's")
    refuses(s, "formal-ask", {"targets": ["sy-0003", UNLABELLED]}, 409, "needs-label", "needs a label first")
    assert replay(root).asks == {}, "a refused request asks nothing"
    answer = succeeds(s, "formal-ask", body)
    [task] = answer["tasks"]
    made = replay(root).asks[task]
    assert made.what == "formalize" and made.to == "agent" and made.on == {"label": "sy-0003"}
    assert [x["label"] for x in made.get("state")] == ["sy-0001"]
    assert [x["label"] for x in made.get("prove")] == ["sy-0002"] and made.get("assume") == []
