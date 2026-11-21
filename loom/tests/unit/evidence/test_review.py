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


def _key(root: Path, label: str, doc: str | None = None) -> str:
    [node] = [n for n in DraftWeb(scan(load_quilt(root))).bearing[label] if doc is None or doc in n.reached_by]
    return node.key


def _lean(root: Path, label: str, doc: str | None = None) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    subject = web.subject(Here("block", _key(root, label, doc)))
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


def _attest(root: Path, label: str, doc: str | None = None) -> None:
    web = DraftWeb(scan(load_quilt(root)))
    here = Here("block", _key(root, label, doc))
    subject = web.subject(here)
    assert subject is not None
    lean = [r for r in replay(root).about("label", label, of="lean") if r.on and r.on.hash == subject.hash][-1]
    closure = [{k[0]: k[1], "hash": h} for k, h in sorted(web.closure(here).items())]
    statements = {d["name"]: d["statement"] for d in lean.get("declarations")}
    write(root, "attested", PERSON, on=subject, lean=lean.id, statements=statements, closure=closure, rulings=[])
    for name, digest in web.notation(here).items():
        write(root, "attested", PERSON, on=Subject("macro", name, digest))


def _edit(root: Path, old: str, new: str, doc: str = DOC) -> None:
    text = (root / doc).read_text(encoding="utf-8")
    assert old in text
    (root / doc).write_text(text.replace(old, new), encoding="utf-8")


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
    assert waiting["task"] == task.id and waiting["what"] == "read" and waiting["working"] is None
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


BOUNDS = "drafting/bounds.tex"
TWIN = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\begin{lemma}\label{lem:balanced}
A twin of the lemma, in other words.
\end{lemma}
\begin{lemma}\label{lem:twinned}
By Lemma~\ref{lem:balanced}, every twin is balanced.
\end{lemma}
\end{document}
"""


def test_one_label_on_two_texts_in_two_documents_is_two_rows_each_with_what_rests_on_it(root: Path) -> None:
    (root / BOUNDS).write_text(TWIN, encoding="utf-8")
    for label, doc in (("lem:balanced", DOC), ("lem:balanced", BOUNDS), ("lem:twinned", BOUNDS)):
        _lean(root, label, doc)
        _attest(root, label, doc)
    assert _rows(_gather(root), "attested-changed") == []
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    _edit(root, "in other words", "in yet other words", BOUNDS)
    rows = {r["result"]: r for r in _rows(_gather(root), "attested-changed")}
    here, there = _key(root, "lem:balanced", DOC), _key(root, "lem:balanced", BOUNDS)
    assert sorted(rows) == sorted([here, there])
    assert rows[here]["resting"] == [] and rows[here]["docs"] == [DOC]
    assert [u["result"] for u in rows[there]["resting"]] == [_key(root, "lem:twinned")]


def test_a_result_rests_under_a_member_whose_own_words_changed_never_under_one_resting_itself(root: Path) -> None:
    for label in ("def:connected", "def:cycle", "lem:balanced"):
        _lean(root, label)
        _attest(root, label)
    # the cycle's words change and it is attested again; the lemma, attested on its first words, is not
    _edit(root, "is the kernel.", "is the kernel of the boundary.")
    _lean(root, "def:cycle")
    _attest(root, "def:cycle")
    # then what both rest on changes: the cycle rests on it, and the lemma names the cycle first among its causes
    _edit(root, "is connected.", "is connected after its loops are removed.")
    [row] = _rows(_gather(root), "attested-changed")
    assert row["result"] == _key(root, "def:connected")
    assert sorted(u["result"] for u in row["resting"]) == sorted(_key(root, x) for x in ("def:cycle", "lem:balanced"))


def test_a_result_citing_a_result_of_a_work_no_node_answers_for_is_not_offered_to_attest(root: Path) -> None:
    cited = "\\begin{lemma}\\label{lem:cited}\nBy \\cite[Theorem 2.1]{Calloway14}, every cog is finite.\n\\end{lemma}\n"
    _edit(root, "\\end{document}", cited + "\\end{document}")
    _lean(root, "lem:cited")
    _lean(root, "lem:balanced")
    assert [r["result"] for r in _rows(_gather(root), "attest")] == [_key(root, "lem:balanced")]


def _served(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[list[object], list[int]]:
    """The publisher's kept scan offered for `root`, one scan object until the test swaps it, and `gather`'s calls counted."""
    from loom.render.endpoints import base

    held: list[object] = [scan(load_quilt(root))]
    monkeypatch.setitem(base._SCANS, root.resolve(), lambda: held[0])
    calls: list[int] = []
    real = review.gather
    monkeypatch.setattr(review, "gather", lambda *a, **k: calls.append(1) or real(*a, **k))
    return held, calls


def test_a_read_under_the_same_scan_and_files_answers_from_the_last(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.looks import keep_all, take
    from loom.render.endpoints.review import _gathered
    from loom.scan.quilt import save_author

    save_author("A. Author")
    track_edits(root)
    take(load_quilt(root), "A. Author")
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    held, calls = _served(root, monkeypatch)
    [change] = _gathered(root)[2].of("edits")
    assert _gathered(root)[2].of("edits") == [change] and len(calls) == 1
    # the person's look takes the change in: the same scan, another look
    keep_all(load_quilt(root), "A. Author")
    assert _gathered(root)[2].of("edits") == [] and len(calls) == 2
    ask(root, AGENT, "question", "person", {"label": "lem:balanced"}, origin=[DOC], text="Both?")
    assert len(_gathered(root)[2].of("questions")) == 1 and len(calls) == 3
    held[0] = scan(load_quilt(root))
    _gathered(root)
    assert len(calls) == 4


def test_an_ask_reads_working_while_the_session_that_took_it_is_alive_on_a_kept_read_too(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.evidence import asks
    from loom.render.endpoints.review import _gathered

    task = ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    say(root, AGENT, "took", task.id, session="s-2026-11-21-a8k2rx")
    _held, calls = _served(root, monkeypatch)
    alive: list[frozenset[str]] = [frozenset()]
    monkeypatch.setattr(asks, "live_sessions", lambda _root: alive[0])
    [row] = _gathered(root)[2].of(review.AGENTS)
    assert row.fields["working"] is None
    alive[0] = frozenset({"s-2026-11-21-a8k2rx"})
    [row] = _gathered(root)[2].of(review.AGENTS)
    assert row.fields["working"] == {"by": "Probe Agent"} and len(calls) == 1


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
    # numbered where the compile numbered it (the fake TeX of the unit tier numbers nothing)
    assert row["key"] == key and row["doc"] == DOC and row["name"] in ("Lemma", "Lemma 1")


def test_an_agents_suggested_edit_is_a_proposed_edit(root: Path) -> None:
    key = _key(root, "lem:balanced")
    ok("suggest", key, "--with", "Every balanced weighting", "--quote", "Every", "--as", "Probe Agent", cwd=root)
    [row] = _rows(_gather(root), "edits")
    assert row["type"] == "suggested" and row["key"] == key and row["by"] == "Probe Agent"


def test_a_rows_kind_is_its_kind_and_no_field_of_its_own_overwrites_it(root: Path) -> None:
    key = _key(root, "lem:balanced")
    ok("suggest", key, "--with", "Every balanced weighting", "--quote", "Every", "--as", "Probe Agent", cwd=root)
    ask(root, PERSON, "read", "agent", {"node": "dm-00B7"}, origin=[DOC], nodes=["dm-00B7"])
    g = _gather(root)
    assert [(r["kind"], r["type"]) for r in _rows(g, "edits")] == [("edits", "suggested")]
    assert [(r["kind"], r["what"]) for r in _rows(g, review.AGENTS)] == [(review.AGENTS, "read")]
    with pytest.raises(ValueError, match="kind"):
        review.Row("edits:e-1", "edits", (DOC,), fields={"kind": "suggested"}).to_dict()


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


def test_a_result_is_named_by_its_taxon_and_the_number_the_build_published() -> None:
    manifest = {
        "nodes": {
            "k": {
                "taxon": "Lemma",
                "numbers": {"a.tex": {"number": "3.3", "page": 2}, "b.tex": {"number": "1", "page": 1}},
            }
        }
    }
    assert review._name(manifest, "k", "b.tex") == "Lemma 1" and review._name(manifest, "k", "c.tex") == "Lemma 3.3"
    assert review._name({"nodes": {"k": {"taxon": "Remark", "numbers": {}}}}, "k", "a.tex") == "Remark"
