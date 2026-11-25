"""The Web's reads over the drafts: a scope's results by document or by status, search in their statements, a result's card and its graph, what a statement uses kept apart from what a proof uses."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from loom.evidence import webview
from loom.evidence.log import write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here
from loom.evidence.webview import ScopeError, drafts
from loom.render.endpoints import base
from loom.render.endpoints.web import _drafts
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok

MAIN = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\newtheorem{theorem}{Theorem}
\newtheorem{definition}{Definition}
\begin{document}
\begin{definition}\label{def:connected}
A quiver is connected if its underlying graph is connected.
\end{definition}
\begin{definition}\label{def:cycle}
For a connected quiver (Definition~\ref{def:connected}), the cycle lattice is the kernel.
\end{definition}
\begin{lemma}\label{lem:balanced}
Every balanced weighting on a tree vanishes, as in Definition~\ref{def:cycle}.
\end{lemma}
\begin{proof}
Its support is connected (Definition~\ref{def:connected}), and a polynomial count follows.
\end{proof}
\begin{theorem}\label{thm:count}
The number of balanced weightings of height at most $h$ is a polynomial in $h$, by Lemma~\ref{lem:balanced}.
\end{theorem}
\end{document}
"""
OTHER = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\begin{lemma}\label{lem:other}
Something else entirely.
\end{lemma}
\end{document}
"""
DOC, OTHER_DOC = "drafting/main.tex", "drafting/other.tex"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "q"
    ok("init", str(root), "--demo", cwd=tmp_path)
    (root / DOC).write_text(MAIN, encoding="utf-8")
    (root / OTHER_DOC).write_text(OTHER, encoding="utf-8")
    return root


def _d(root: Path) -> webview.Drafts:
    return drafts(scan(load_quilt(root)), {}, root)


def _key(d: webview.Drafts, label: str) -> str:
    return next(n.key for n in d.results if label in n.labels)


def _names(rows: list[dict]) -> list[str]:
    return [r["name"] for r in rows]


def test_a_draft_lists_its_own_results_in_document_order_with_their_marks(root: Path) -> None:
    d = _d(root)
    listed = webview.listing(d, "draft", DOC)
    [section] = listed["sections"]
    assert section["head"] == "draft" and listed["count"] == 4
    assert _names(section["rows"]) == ["Definition", "Definition", "Lemma", "Theorem"]
    first = section["rows"][0]
    assert (
        first["source"] == {"doc": DOC}
        and first["paper"] is None
        and first["reading"] is None
        and first["lean"] == {"lean": "none", "role": None, "waiting_on": []}
        and first["taxon"] == "definition"
    )
    assert webview.listing(d, "draft", OTHER_DOC)["count"] == 1


def test_everything_groups_by_document_and_sends_a_groups_rows_only_when_open(root: Path) -> None:
    d = _d(root)
    listed = webview.listing(d, "all", None)
    drafts_section, library = listed["sections"]
    assert library == {"head": "library", "groups": []}
    # the demo's own outline is a draft of the person's too
    groups = {g["group"]: (g["n"], "rows" in g) for g in drafts_section["groups"]}
    assert groups[DOC] == (4, False) and groups[OTHER_DOC] == (1, False)
    reopened = webview.listing(d, "all", None, opened=[OTHER_DOC])["sections"][0]["groups"]
    opened = {g["group"]: "rows" in g for g in reopened}
    assert opened[OTHER_DOC] and not opened[DOC]
    assert webview.group(d, "all", None, OTHER_DOC)["n"] == 1


def test_a_scope_it_does_not_know_or_one_wanting_a_draft_is_refused(root: Path) -> None:
    d = _d(root)
    with pytest.raises(ScopeError):
        webview.listing(d, "everything", None)
    with pytest.raises(ScopeError):
        webview.listing(d, "draft", None)
    assert webview.listing(d, "library", None)["count"] == 0


def test_search_finds_a_name_first_then_words_of_a_statement_with_the_words_around_them(root: Path) -> None:
    d = _d(root)
    found = webview.search(d, "all", None, "polynomial in")
    [hit] = found["hits"]
    # the node index's snippet: the first word found, from the statement's LaTeX, a formula whole and cut at spaces outside it
    assert hit["row"]["result"] == _key(d, "thm:count") and hit["snippet"]["match"] == "polynomial"
    assert hit["snippet"]["before"].endswith("height at most $h$ is a ") and hit["snippet"]["after"].startswith(
        " in $h$"
    )
    named = webview.search(d, "draft", DOC, "lemma")
    # the name is found first; the theorem, whose statement says "Lemma", after it, with its words
    assert [h["row"]["result"] for h in named["hits"]] == [_key(d, "lem:balanced"), _key(d, "thm:count")]
    assert named["hits"][0]["snippet"] is None and named["hits"][1]["snippet"]["match"] == "Lemma"
    assert webview.search(d, "draft", OTHER_DOC, "polynomial")["count"] == 0


def test_a_card_keeps_what_its_statement_uses_apart_from_what_its_proof_uses(root: Path) -> None:
    d = _d(root)
    card = webview.focus(d, "all", None, _key(d, "lem:balanced"))
    assert [r["result"] for r in card["uses"]["statement"]] == [_key(d, "def:cycle")]
    assert [r["result"] for r in card["uses"]["proof"]] == [_key(d, "def:connected")]
    assert [r["result"] for r in card["used_by"]["rows"]] == [_key(d, "thm:count")]
    assert card["relative_to"] is None and card["more"] is None
    folded = webview.focus(d, "all", None, _key(d, "lem:balanced"), more=True)["more"]
    assert [p["uses"][0]["result"] for p in folded["proofs"]] == [_key(d, "def:connected")] and folded["record"] == []
    with pytest.raises(KeyError):
        webview.focus(d, "all", None, "drafting/main.tex#nothing:9")


def test_what_lies_outside_the_scope_is_counted_not_sent(root: Path) -> None:
    d = _d(root)
    card = webview.focus(d, "deps", DOC, _key(d, "thm:count"))
    assert card["uses"]["outside"] == {"statement": 0, "proof": 0}
    # the deps of the other draft hold none of main.tex's results
    other = webview.focus(d, "deps", OTHER_DOC, _key(d, "lem:balanced"))
    assert other["uses"]["statement"] == [] and other["uses"]["outside"] == {"statement": 1, "proof": 1}
    assert other["used_by"]["outside"] == 1


def test_a_drafts_deps_hold_what_its_results_use_by_statement_or_proof(root: Path) -> None:
    d = _d(root)
    assert set(d.scope("deps", DOC)) == {n.key for n in d.results if DOC in n.reached_by}


def test_the_graph_draws_two_steps_back_and_marks_a_use_by_a_proof(root: Path) -> None:
    d = _d(root)
    drawn = webview.graph(d, "all", None, _key(d, "thm:count"))
    assert [r["result"] for r in drawn["columns"]["uses"]] == [_key(d, "lem:balanced")]
    assert {r["result"] for r in drawn["columns"]["back"]} == {_key(d, "def:cycle"), _key(d, "def:connected")}
    assert drawn["columns"]["used_by"] == [] and drawn["more"] == {"back": 0, "uses": 0, "used_by": 0}
    edges = {(e["from"], e["to"], e["proof"]) for e in drawn["edges"]}
    assert (_key(d, "lem:balanced"), _key(d, "def:connected"), True) in edges
    assert (_key(d, "lem:balanced"), _key(d, "def:cycle"), False) in edges
    assert drawn["excerpt"] == "The number of balanced weightings of height at most h is a polynomial in h, by Lemma."


def test_by_status_what_waits_on_the_person_comes_first(root: Path) -> None:
    d = _d(root)
    d._status[_key(d, "thm:count")] = "unattested"  # as a Lean record accepted and not attested would make it
    listed = webview.listing(d, "draft", DOC, sort="status")
    assert listed["rows"][0]["result"] == _key(d, "thm:count") and listed["more"] == 0 and listed["count"] == 4


PREAMBLE = r"""\documentclass{article}
\usepackage{amsmath}
\newtheorem{lemma}{Lemma}
\newtheorem{theorem}{Theorem}
\newtheorem{definition}{Definition}
\begin{document}
"""
SHARED = r"""\begin{definition}\label{def:rank}
The rank of a quiver is
\begin{equation}\label{eq:rank}
r(Q) = a - v + c.
\end{equation}
\end{definition}
\begin{lemma}\label{lem:shared}
The rank in \eqref{eq:rank} is never negative.
\end{lemma}
"""
TWO_MAIN = (
    PREAMBLE
    + r"""\input{shared}
\begin{theorem}\label{thm:main}
A theorem of the main draft alone.
\end{theorem}
\begin{proof}
Count as in \eqref{eq:rank}.
\end{proof}
\end{document}
"""
)
TWO_BOUNDS = (
    PREAMBLE
    + r"""\input{shared}
\begin{lemma}\label{lem:bound}
A bound of the second draft alone, by Lemma~\ref{lem:shared}.
\end{lemma}
\end{document}
"""
)
BOUNDS_DOC = "drafting/bounds.tex"
PERSON, LOOM = Who("person", "A. Author"), Who("loom")


@pytest.fixture
def two(tmp_path: Path) -> Path:
    """Two drafts that both input a file holding a definition with a display and a lemma citing it."""
    root = tmp_path / "q"
    ok("init", str(root), "--demo", cwd=tmp_path)
    (root / "drafting/shared.tex").write_text(SHARED, encoding="utf-8")
    (root / DOC).write_text(TWO_MAIN, encoding="utf-8")
    (root / BOUNDS_DOC).write_text(TWO_BOUNDS, encoding="utf-8")
    return root


def test_a_display_a_statement_or_proof_cites_is_a_use_of_the_block_holding_it_as_status_reads_it(two: Path) -> None:
    d = _d(two)
    rank, shared, main = _key(d, "def:rank"), _key(d, "lem:shared"), _key(d, "thm:main")
    card = webview.focus(d, "all", None, shared)
    assert [r["result"] for r in card["uses"]["statement"]] == [rank]
    assert [r["result"] for r in webview.focus(d, "all", None, main)["uses"]["proof"]] == [rank]
    used = webview.focus(d, "all", None, rank)["used_by"]["rows"]
    assert {r["result"] for r in used} == {shared, main}
    # what a statement uses on its card is what status's closure walks, for every result
    for n in d.results:
        assert d.uses(n.key)[0] == [h.name for h in d.web.uses(Here("block", n.key)) if d.node(h.name)]


def test_a_result_two_drafts_read_is_in_the_group_of_each_in_the_list_as_when_a_group_is_opened(two: Path) -> None:
    d = _d(two)
    shared = _key(d, "lem:shared")
    listed = webview.listing(d, "all", None, opened=[DOC, BOUNDS_DOC])
    groups = {g["group"]: g for g in listed["sections"][0]["groups"]}
    for doc in (DOC, BOUNDS_DOC):
        opened = webview.group(d, "all", None, doc)
        assert groups[doc]["n"] == opened["n"] and groups[doc]["rows"] == opened["rows"]
        assert shared in [r["result"] for r in opened["rows"]]
        # a row under a draft's group names that draft as its source
        assert {r["source"]["doc"] for r in opened["rows"]} == {doc}
    # the count is the results, each once, though the groups hold one of them twice
    assert listed["count"] == len(d.results) == sum(g["n"] for g in groups.values()) - 2


def _lean(root: Path, on: Subject, states: dict[str, str], *, ok: bool = True) -> str:
    """A `lean` record on `on`, each of `states` a declaration stating the label it names; its id."""
    lean = root / "lean" / "A.lean"
    lean.parent.mkdir(exist_ok=True)
    lean.write_text("theorem a : True := trivial\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(lean.read_bytes()).hexdigest()
    declarations = [
        {"name": name, "kind": "theorem", "role": "states", "names": {"label": label}, "statement": digest}
        | {"axioms": [], "sorry": False}
        for name, label in states.items()
    ]
    return write(
        root,
        "lean",
        LOOM,
        on=on,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": digest},
        files={"lean/A.lean": digest},
        declarations=declarations,
        assumed=[],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=ok,
    ).id


def test_search_matches_the_words_of_a_statement_never_its_latex(root: Path) -> None:
    d = _d(root)
    for q in ("label", "begin", "ref", "lem:balanced", "support", "nomial"):
        # a command, a reference, an environment's name, a label, a proof's words, or the inside of a word
        assert webview.search(d, "all", None, q)["count"] == 0, q
    assert [h["snippet"]["match"] for h in webview.search(d, "all", None, "poly")["hits"]] == ["polynomial"]
    [hit] = webview.search(d, "all", None, "underlying graph")["hits"]
    assert hit["row"]["result"] == _key(d, "def:connected")
    assert hit["snippet"] == {
        "before": "A quiver is connected if its ",
        "match": "underlying",
        "after": " graph is connected.",
    }


def test_a_cards_fold_reads_only_the_records_on_its_own_text(root: Path) -> None:
    d = _d(root)
    key = _key(d, "lem:balanced")
    subject = d.web.subject(Here("block", key))
    assert subject is not None
    _lean(root, subject, {"balanced_here": "lem:balanced", "count_here": "thm:count"})
    # later, a run and an attestation on another text of the label: another document's, or one since edited
    other = Subject("label", "lem:balanced", "sha256:" + "0" * 64)
    there = _lean(root, other, {"balanced_there": "lem:balanced"})
    said = {"balanced_there": "sha256:" + "1" * 64}
    write(root, "attested", PERSON, on=other, lean=there, statements=said, closure=[], rulings=[])
    folded = webview.focus(_d(root), "all", None, key, more=True)["more"]
    assert folded["lean"] == ["balanced_here"]
    assert [(r["act"], r["by"]) for r in folded["record"]] == [("lean-accepted", "loom")]


def test_a_read_under_the_same_scan_and_unchanged_files_answers_from_the_last(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept = scan(load_quilt(root))
    monkeypatch.setitem(base._SCANS, root.resolve(), lambda: kept)
    first = _drafts(root)
    assert _drafts(root) is first
    _lean(root, Subject("label", "lem:balanced", "sha256:" + "0" * 64), {"b": "lem:balanced"}, ok=False)
    # a record written is read, and so is a Lean file changed
    second = _drafts(root)
    assert second is not first and len(second.evidence.records) == len(first.evidence.records) + 1
    assert _drafts(root) is second
    (root / "lean" / "A.lean").write_text("theorem a : 1 = 1 := rfl\n", encoding="utf-8")
    third = _drafts(root)
    assert third is not second
    # and a scan made afresh
    fresh = scan(load_quilt(root))
    monkeypatch.setitem(base._SCANS, root.resolve(), lambda: fresh)
    assert _drafts(root) is not third


def test_a_row_carries_how_its_result_stands_never_a_bare_word(root: Path) -> None:
    import hashlib

    from loom.evidence.log import write
    from loom.evidence.subjects import Who

    text = (
        (root / DOC)
        .read_text(encoding="utf-8")
        .replace("is a polynomial in $h$", r"is a polynomial in $h$ (\\cite[Theorem 2.1]{Calloway14})")
    )
    (root / DOC).write_text(text, encoding="utf-8")
    (root / "lean").mkdir()
    (root / "lean" / "C.lean").write_text("theorem c : True := trivial\n", encoding="utf-8")
    d = _d(root)
    key = _key(d, "thm:count")
    subject = d.web.subject(Here("block", key))
    assert subject is not None
    digest = "sha256:" + hashlib.sha256((root / "lean" / "C.lean").read_bytes()).hexdigest()
    declaration = {"name": "c", "kind": "theorem", "role": "states", "names": {"label": "thm:count"}, "statement": digest, "axioms": [], "sorry": False}  # fmt: skip
    write(root, "lean", Who("loom"), on=subject, project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": digest}, files={"lean/C.lean": digest}, declarations=[declaration], assumed=[], uses=[], replay={"tool": "leanchecker", "exit": 0, "output": ""}, ok=True)  # fmt: skip
    row = webview.focus(_d(root), "all", None, key)["row"]
    # Lean accepted it, and it cites a result of a work nothing answers for: the mark the person needs, not "unattested" alone
    assert row["reading"] is None and row["lean"] == {
        "lean": "unattested",
        "role": "proved",
        "waiting_on": [{"cite": "Calloway14 Theorem 2.1", "why": "unknown"}],
    }


# ---- the library's results ------------------------------------------------------------------------------------------


@pytest.fixture
def library(root: Path) -> Path:
    """The demo quilt with the spec's nine example nodes in its library: a definition, two results that use it, one with a proof, and a stub of another work."""
    from loom.library.store import folder
    from tests.unit.library._examples import fixtures

    folder(root).mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (folder(root) / name).write_bytes(data)
    return root


def test_the_library_lists_its_statements_by_work_with_how_each_reads_its_paper(library: Path) -> None:
    d = _d(library)
    assert d.scope("library", None) == ["tq-00A4", "tq-00K3", "tq-00K5", "tq-00B7"]
    row = d.row("tq-00K3")
    assert row["name"] == "lemma 3.2" and row["title"] == "Test lemma" and row["taxon"] == "lemma"
    assert row["source"] == {"ref": "tq-00A1-ref", "short": None} and row["paper"] == row["reading"] == "unchecked"
    assert d.row("tq-00B7")["reading"] == "stub"
    listed = webview.listing(d, "library", None)
    assert [s["head"] for s in listed["sections"]] == ["library"] and listed["count"] == 4
    [first, second] = listed["sections"][0]["groups"]
    assert (first["group"], first["n"], "rows" in first) == ("tq-00A1-ref", 3, False)
    assert (second["group"], second["n"]) == ("tq-00B1-ref", 1)
    # the second work's one result is a stub, and the demo's own works hold no statement: of every work but the first, nothing is read
    assert "tq-00B1-ref" in d.works and listed["undigested"] == len(d.works) - 1


def test_everything_holds_the_drafts_and_the_library_and_a_works_group_opens(library: Path) -> None:
    d = _d(library)
    listed = webview.listing(d, "all", None, opened=["tq-00A1-ref"])
    assert [s["head"] for s in listed["sections"]] == ["drafts", "library"]
    opened = listed["sections"][1]["groups"][0]
    assert [r["result"] for r in opened["rows"]] == ["tq-00A4", "tq-00K3", "tq-00K5"]
    assert webview.group(d, "all", None, "tq-00A1-ref") == {"group": "tq-00A1-ref", "n": 3, "rows": opened["rows"]}


def test_a_library_results_card_draws_its_body_what_it_points_at_and_what_uses_it(library: Path) -> None:
    d = _d(library)
    card = webview.focus(d, "library", None, "tq-00K3")
    assert card["statement"]["body"].startswith("Let $W$ be a widget") and card["statement"]["macros"] is None
    assert card["statement"]["points"] == {"tq-00A4": {"name": "definition 2.1", "number": "2.1", "paper": "unchecked"}}
    assert [r["result"] for r in card["uses"]["statement"]] == ["tq-00A4"]
    assert [r["result"] for r in card["uses"]["proof"]] == ["tq-00A4"]
    assert card["relative_to"] is None and card["rests_on"] == []
    used = webview.focus(d, "library", None, "tq-00A4")["used_by"]["rows"]
    assert [r["result"] for r in used] == ["tq-00K3", "tq-00K5"]
    fold = webview.focus(d, "library", None, "tq-00K3", more=True)["more"]
    assert fold["proofs"] == [{"where": {"ref": "tq-00A1-ref", "short": None, "pages": "12-13"}, "uses": [d.row("tq-00A4")]}]  # fmt: skip


def test_an_anchor_a_body_points_at_draws_as_the_number_its_source_prints(library: Path) -> None:
    from loom.library.store import folder

    path = folder(library) / "tq-00K5.node"
    path.write_text(path.read_text(encoding="utf-8").replace("origin.", "origin, as in \\eqref{tq-00K3-eq00}."), encoding="utf-8")  # fmt: skip
    assert webview.focus(_d(library), "library", None, "tq-00K5")["statement"]["points"]["tq-00K3-eq00"] == {"number": "3.3"}  # fmt: skip


def test_search_and_the_graph_reach_the_library(library: Path) -> None:
    d = _d(library)
    found = webview.search(d, "library", None, "widget")
    assert {h["row"]["result"] for h in found["hits"]} == {"tq-00A4", "tq-00K3", "tq-00K5"}
    named = next(h for h in found["hits"] if h["row"]["result"] == "tq-00A4")
    assert named["snippet"] is None, "Widget is the definition's title"
    drawn = webview.graph(d, "library", None, "tq-00A4")
    assert [r["result"] for r in drawn["columns"]["used_by"]] == ["tq-00K3", "tq-00K5"]
    assert {"from": "tq-00K3", "to": "tq-00A4", "proof": False} in drawn["edges"]


def test_a_draft_scope_holds_no_library_result_until_citations_reach_one(library: Path) -> None:
    d = _d(library)
    assert not any(d.is_library(k) for k in d.scope("draft", DOC) + d.scope("deps", DOC))
