"""Review's lists, each a rule over the evidence, the asks, the scan and the manifest: what puts a row in, what takes it out, how a kind's rows are ordered and narrowed to one draft, and that the counts are the rows'."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from loom.evidence import review
from loom.evidence.asks import ask, say
from loom.evidence.log import replay, write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import DraftWeb, Here
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok
from tests.unit._quilts import track_edits

PERSON = Who("person", "A. Author")
AGENT = Who("agent", "Probe Agent")
LOOM = Who("loom")
MAIN = r"""\documentclass{article}
\usepackage{amsmath}
\newtheorem{lemma}{Lemma}
\newtheorem{definition}{Definition}
\newcommand{\Zcyc}{\mathcal{Z}}
\begin{document}
\begin{definition}\label{def:connected}
A quiver is connected if its underlying graph is connected.
\end{definition}
\begin{definition}\label{def:cycle}
For a connected quiver (Definition~\ref{def:connected}), $\Zcyc$ is the kernel.
\end{definition}
\begin{lemma}\label{lem:balanced}
Every $w \in \Zcyc$ on a tree vanishes, as in Definition~\ref{def:cycle}.
\end{lemma}
\end{document}
"""
DOC = "drafting/main.tex"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    root = tmp_path / "q"
    ok("init", str(root), "--demo", cwd=tmp_path)
    # the draft is rewritten here, which a quilt tracking edits would list as changes waiting on the person
    track_edits(root, on=False)
    # and the demo ships a suggested edit of its own
    (root / ".loom/records/edits/log.jsonl").unlink()
    (root / DOC).write_text(MAIN, encoding="utf-8")
    (root / "lean").mkdir()
    (root / "lean" / "A.lean").write_text("theorem a : True := trivial\n", encoding="utf-8")
    return root


def _gather(root: Path, manifest: dict | None = None) -> review.Gathered:
    return review.gather(root, scan(load_quilt(root)), manifest or {})


def _key(root: Path, label: str) -> str:
    [node] = DraftWeb(scan(load_quilt(root))).bearing[label]
    return node.key


def _lean(root: Path, label: str) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    subject = web.subject(Here("block", _key(root, label)))
    assert subject is not None
    digest = "sha256:" + hashlib.sha256((root / "lean" / "A.lean").read_bytes()).hexdigest()
    write(
        root,
        "lean",
        LOOM,
        on=subject,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": digest},
        files={"lean/A.lean": digest},
        declarations=[
            {
                "name": label,
                "kind": "theorem",
                "role": "states",
                "names": {"label": label},
                "statement": digest,
                "axioms": [],
                "sorry": False,
            }
        ],
        assumed=[],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=True,
    )


def _attest(root: Path, label: str) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    here = Here("block", _key(root, label))
    subject = web.subject(here)
    assert subject is not None
    lean = [r for r in replay(root).about("label", label, of="lean")][-1]
    closure = [{k[0]: k[1], "hash": h} for k, h in sorted(web.closure(here).items())]
    statements = {d["name"]: d["statement"] for d in lean.get("declarations")}
    write(root, "attested", PERSON, on=subject, lean=lean.id, statements=statements, closure=closure, rulings=[])
    for name, digest in web.notation(here).items():
        write(root, "attested", PERSON, on=Subject("macro", name, digest))


def _edit(root: Path, old: str, new: str) -> None:
    text = (root / DOC).read_text(encoding="utf-8")
    assert old in text
    (root / DOC).write_text(text.replace(old, new), encoding="utf-8")


def _rows(g: review.Gathered, kind: str) -> list[dict]:
    return [r.to_dict() for r in g.of(kind)]


def test_an_agents_question_waits_until_answered_and_names_its_choices(root: Path) -> None:
    q = ask(
        root,
        AGENT,
        "question",
        "person",
        {"label": "lem:balanced"},
        origin=[DOC],
        text="Both?",
        choices=["both", "one"],
    )
    [row] = _rows(_gather(root), "questions")
    assert row["row"] == f"questions:{q.id}" and row["choices"] == ["both", "one"] and row["docs"] == [DOC]
    say(root, PERSON, "answered", q.id, words="", choice=0)
    assert _rows(_gather(root), "questions") == []


def test_a_paper_waits_until_withdrawn_or_held_and_a_task_until_it_produces_or_is_withdrawn(root: Path) -> None:
    paper = ask(
        root,
        AGENT,
        "paper",
        "person",
        {"ref": "dm-00B1-ref"},
        ref="dm-00B1-ref",
        link="https://doi.org/10.1000/x.17",
        want="pdf",
    )
    task = ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    g = _gather(root)
    assert [r["link"] for r in _rows(g, "fetch")] == ["https://doi.org/10.1000/x.17"]
    [waiting] = _rows(g, review.AGENTS)
    assert waiting["task"] == task.id and waiting["kind"] == "read" and waiting["working"] is None
    say(root, AGENT, "withdrawn", paper.id)
    say(root, PERSON, "withdrawn", task.id)
    g = _gather(root)
    assert _rows(g, "fetch") == [] and _rows(g, review.AGENTS) == []


def test_lean_accepted_is_to_attest_until_attested(root: Path) -> None:
    _lean(root, "lem:balanced")
    [row] = _rows(_gather(root), "attest")
    assert row["result"] == _key(root, "lem:balanced") and row["what"] == "statement and proof"
    _attest(root, "lem:balanced")
    assert _rows(_gather(root), "attest") == []


def test_results_resting_on_a_changed_definition_are_nested_under_it(root: Path) -> None:
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _lean(root, label)
        _attest(root, label)
    assert _rows(_gather(root), "attested-changed") == []
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "def:connected") and row["changed"] == "statement"
    assert sorted(r["result"] for r in row["resting"]) == sorted(
        _key(root, label) for label in ("def:cycle", "lem:balanced")
    )


def test_a_result_changed_through_a_definition_nobody_attested_is_a_row_of_its_own(root: Path) -> None:
    _lean(root, "lem:balanced")
    _attest(root, "lem:balanced")
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "lem:balanced") and row["changed"] == "used"
    assert [c["changed"] for c in row["causes"]] == [{"label": "def:connected"}]


def test_an_accepted_result_that_changed_is_listed_from_the_published_ledger(root: Path) -> None:
    from loom.cli.review import write_acceptance
    from loom.render.build import build
    from loom.scan.quilt import save_author

    save_author("A. Author")
    key = _key(root, "lem:balanced")
    write_acceptance(scan(load_quilt(root)), [key], "A. Author")
    assert _rows(_gather(root, build(load_quilt(root)).manifest), "accepted-changed") == []
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    manifest = build(load_quilt(root)).manifest
    [row] = _rows(_gather(root, manifest), "accepted-changed")
    assert row["key"] == key and row["doc"] == DOC and row["name"].startswith("Lemma")


def test_an_agents_suggested_edit_is_a_proposed_edit(root: Path) -> None:
    key = _key(root, "lem:balanced")
    ok("suggest", key, "--with", "Every balanced weighting", "--quote", "Every", "--as", "Probe Agent", cwd=root)
    [row] = _rows(_gather(root), "edits")
    assert row["kind"] == "suggested" and row["key"] == key and row["by"] == "Probe Agent"


def test_everything_is_in_rank_order_counts_are_the_rows_and_a_draft_narrows_both(root: Path) -> None:
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=["drafting/other.tex"], text="Elsewhere?")
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=[DOC], text="Here?")
    ask(
        root,
        AGENT,
        "paper",
        "person",
        {"ref": "dm-00B1-ref"},
        origin=[DOC],
        ref="dm-00B1-ref",
        link="https://example.org/p",
        want="pdf",
    )
    _lean(root, "lem:balanced")
    g = _gather(root)
    groups = review.listed(g, "all")
    assert [grp["kind"] for grp in groups] == ["questions", "fetch", "attest"]
    counted = review.counts(g, [DOC, "drafting/other.tex"])
    assert counted["everything"] == 4 and counted["kinds"]["questions"] == 2 and counted["agents"] == 0
    assert counted["drafts"] == [{"doc": DOC, "n": 3}, {"doc": "drafting/other.tex", "n": 1}]
    assert [len(grp["rows"]) for grp in review.listed(g, "all", DOC)] == [1, 1, 1]
    assert review.find(g, groups[0]["rows"][0]["row"]) is not None
