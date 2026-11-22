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
