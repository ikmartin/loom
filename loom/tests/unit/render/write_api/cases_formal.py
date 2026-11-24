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
    s, root = synthetic(serve, tmp_path, watch=False)
    refuses(s, "formal-plan", {}, 400, "bad-field", "targets")
    refuses(s, "formal-plan", {"targets": ["sy-9999"]}, 404, "no-such-result", "sy-9999")
    # the theorem's proof uses a lemma, whose statement uses a definition: one to prove and one to state
    found = succeeds(s, "formal-plan", {"targets": ["sy-0003"]})
    assert [t["key"] for t in found["targets"]] == ["sy-0003"] and found["targets"][0]["doc"] == "drafting/main.tex"
    assert [r["result"] for r in found["state"]] == ["sy-0001"]
    assert [(r["result"], r["assume"]) for r in found["prove"]] == [("sy-0002", False)]
    assert found["stops"] == [] and found["assume"] == []
    # nothing Lean has said of it yet: its own Lean, which the agent writes, is the person's to attest after
    assert [(g["why"], g["when"], [r["result"] for r in g["results"]]) for g in found["before"]] == [("attest", "after", ["sy-0003"])]  # fmt: skip
    # assumed for now, the lemma is followed by its statement alone, which still uses the definition
    assumed = succeeds(s, "formal-plan", {"targets": ["sy-0003"], "assume": ["sy-0002"]})
    assert [(r["result"], r["assume"]) for r in assumed["prove"]] == [("sy-0002", True)]
    assert [r["result"] for r in succeeds(s, "formal-plan", {"targets": [UNLABELLED]})["stops"]] == [UNLABELLED]
    _two_texts(s, root)


def _before(found: dict[str, Any]) -> list[tuple[str, str, list[Any]]]:
    return [(g["why"], g["when"], [r.get("result") or r.get("label") for r in g["results"]]) for g in found["before"]]


#: A lemma in a file both of the synthetic quilt's documents read, keyed by its label, which no other block carries, and the lemma its proof uses, with a text in each.
BOUNDED = "thm:t"


def _two_texts(s: Any, root: Path) -> None:
    """The target proved from a lemma assumed for now, with a text in each document that reads the target: the list names the label two texts answer to before the agent's Lean is written and after the person attests it, while the target waits on it; once the texts are one, that lemma's own Lean."""
    import json

    from loom.evidence.log import write
    from loom.evidence.subjects import Who
    from loom.evidence.webview import drafts
    from loom.paths import MANIFEST
    from loom.render.endpoints.base import _scan

    (root / "drafting/nodes/bounded.tex").write_text("\\begin{lemma}[Bounded]\\label{thm:t}\nEvery widget is bounded.\n\\end{lemma}\n\\begin{proof}\nBy Lemma~\\ref{lem:b}.\n\\end{proof}\n", encoding="utf-8")  # fmt: skip
    for doc, text, around in (("main.tex", "One text of it.", "BODY"), ("talk.tex", "Another text of it.", "\\begin{frame}{Bounded}BODY\\end{frame}")):  # fmt: skip
        body = f"\\input{{nodes/bounded}}\n\\begin{{lemma}}\\label{{lem:b}}\n{text}\n\\end{{lemma}}\n"
        path = root / "drafting" / doc
        path.write_text(path.read_text(encoding="utf-8").replace("\\end{document}", around.replace("BODY", body) + "\n\\end{document}"), encoding="utf-8")  # fmt: skip
    s.rebuild()
    ask = {"targets": [BOUNDED], "assume": ["drafting/main.tex#lemma:1"]}
    # the lemma, assumed for now, is an axiom of the Lean to be made, and no one text answers to its label near the target
    found = succeeds(s, "formal-plan", ask)
    assert [(r["result"], r["assume"]) for r in found["prove"]] == [("drafting/main.tex#lemma:1", True)]
    assert _before(found) == [("ambiguous", "now", ["lem:b"]), ("attest", "after", [BOUNDED])]
    # the agent's Lean as the plan says, an axiom stating the lemma, and the person attests it
    web = drafts(_scan(root), {}, root).web
    decls = [{"name": "t", "kind": "theorem", "role": "states", "names": {"label": "thm:t"}, "statement": "sha256:" + "1" * 64, "axioms": ["propext", "b"], "sorry": False}, {"name": "b", "kind": "axiom", "role": "states", "names": {"label": "lem:b"}, "statement": "sha256:" + "5" * 64, "axioms": [], "sorry": False}]  # fmt: skip
    (root / "lean").mkdir(exist_ok=True)
    (root / "lean/A.lean").write_text("theorem t : True := trivial\n", encoding="utf-8")
    lean_file = "sha256:" + hashlib.sha256((root / "lean/A.lean").read_bytes()).hexdigest()
    record = write(root, "lean", Who("loom"), on=web.subject(web.heres("thm:t")[0]), project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64}, files={"lean/A.lean": lean_file}, declarations=decls, assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    succeeds(s, "formal-attest", {"result": BOUNDED, "observation": record.id})
    standing = drafts(_scan(root), json.loads((root / MANIFEST).read_text(encoding="utf-8")), root).standing(BOUNDED)
    assert standing.lean == "waiting" and [(w.key, w.why) for w in standing.waiting_on] == [(("label", "lem:b"), "unknown")]  # fmt: skip
    found = succeeds(s, "formal-plan", ask)
    assert _before(found) == [("ambiguous", "now", ["lem:b"])], found["before"]
    [label] = found["before"][0]["results"]
    assert sorted(r["source"]["doc"] for r in label["results"]) == ["drafting/main.tex", "drafting/talk.tex"]
    assert label["for"] == [BOUNDED]
    # one text: what it then needs is its own Lean, which the agent writes
    talk = root / "drafting/talk.tex"
    talk.write_text(
        talk.read_text(encoding="utf-8").replace("Another text of it.", "One text of it."), encoding="utf-8"
    )
    s.rebuild()
    assert [(w, t) for w, t, _ in _before(succeeds(s, "formal-plan", ask))] == [("attest", "after")]
    _vanished(s, root, ask)


def _vanished(s: Any, root: Path, ask: dict[str, Any]) -> None:
    """The target's Lean resting on the lemma's own, both attested, formalized; the lemma given a second text again: the target reads changed, and the list names the label two texts answer to, never a word `formal-attest` refuses."""
    from loom.evidence.log import write
    from loom.evidence.subjects import Who
    from loom.evidence.webview import drafts
    from loom.render.endpoints.base import _scan

    web = drafts(_scan(root), {}, root).web
    lemma, target = web.subject(web.heres("lem:b")[0]), web.subject(web.heres("thm:t")[0])
    assert lemma is not None and target is not None
    lean_file = "sha256:" + hashlib.sha256((root / "lean/A.lean").read_bytes()).hexdigest()
    run = {"project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64}, "files": {"lean/A.lean": lean_file}, "assumed": [], "replay": {"tool": "leanchecker", "exit": 0, "output": ""}, "ok": True}  # fmt: skip
    b = write(root, "lean", Who("loom"), on=lemma, declarations=[{"name": "b", "kind": "theorem", "role": "states", "names": {"label": "lem:b"}, "statement": "sha256:" + "5" * 64, "axioms": ["propext"], "sorry": False}], uses=[], **run)  # fmt: skip
    succeeds(s, "formal-attest", {"result": "drafting/main.tex#lemma:1", "observation": b.id})
    t = write(root, "lean", Who("loom"), on=target, declarations=[{"name": "t", "kind": "theorem", "role": "states", "names": {"label": "thm:t"}, "statement": "sha256:" + "1" * 64, "axioms": ["propext"], "sorry": False}], uses=[{"label": "lem:b", "hash": lemma.hash}], **run)  # fmt: skip
    succeeds(s, "formal-attest", {"result": BOUNDED, "observation": t.id})
    assert succeeds(s, "formal-plan", ask)["before"] == []
    talk = root / "drafting/talk.tex"
    talk.write_text(talk.read_text(encoding="utf-8").replace("One text of it.\n\\end{lemma}\n\\end{frame}", "Another text of it.\n\\end{lemma}\n\\end{frame}"), encoding="utf-8")  # fmt: skip
    s.rebuild()
    standing = drafts(_scan(root), {}, root).standing(BOUNDED)
    assert standing.lean == "changed" and [(c.key, c.now) for c in standing.causes] == [(("label", "lem:b"), None)]
    assert _before(succeeds(s, "formal-plan", ask)) == [("ambiguous", "now", ["lem:b"])]
    refuses(s, "formal-attest", {"result": BOUNDED, "observation": t.id}, 409, "changed", "lem:b")


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
