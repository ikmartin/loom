"""The Web's reads over the drafts: a scope's results by document or by status, search in their statements, a result's card and its graph, what a statement uses kept apart from what a proof uses."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence import webview
from loom.evidence.webview import ScopeError, drafts
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok
from tests.unit._quilts import track_edits

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
    track_edits(root, on=False)
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
        and first["lean"] == "none"
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
    assert hit["row"]["result"] == _key(d, "thm:count") and hit["snippet"]["match"] == "polynomial in"
    assert "height at most" in hit["snippet"]["before"] and hit["snippet"]["after"].startswith(" $h$")
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
