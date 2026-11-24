"""Citations resolved to the library (`library.citations`) and the stubs a draft's citations make (`library.stubs`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library.gather import gather
from loom.library.node import Node
from loom.library.store import folder, read, write_node
from loom.library.stubs import make
from loom.scan.quilt import load_quilt
from loom.scan.scan import ScanResult, scan

MAIN = r"""\documentclass{article}
\begin{document}
By \cite[Lemma~2.1]{Smi24}, and again by \cite[Lemma 2.1]{Smi24}.
The work as a whole \cite{Smi24}, a page of it \cite[p.~5]{Smi24}, a part of it \cite[Section 3]{Smi24}.
Two at once \cite[Theorem 3 and Lemma 2.4]{Jon19}; a key the library holds no work for \cite[Lemma 9.9]{Nobody}.
\bibliography{refs}
\end{document}
"""
BIB = "@article{Smi24,\n  author = {Smith, Jane},\n  title = {Widgets},\n  year = {2024},\n}\n@article{Jon19,\n  author = {Jones, Alex},\n  title = {Gadgets},\n  year = {2019},\n}\n"


def quilt(tmp_path: Path) -> Path:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(MAIN)
    (root / "refs.bib").write_text(BIB)
    load_quilt(root)
    return root


def gathered(root: Path) -> ScanResult:
    """The quilt scanned and gathered, its references made, as a build leaves it before the stubs pass."""
    result = scan(load_quilt(root))
    gather(result)
    return result


def targets(result: ScanResult) -> dict[tuple[str, str | None], str | None]:
    return {(c.citekey, c.postnote): c.target for c in result.edges.cites}


def test_each_result_a_draft_cites_by_number_becomes_one_stub_of_its_work(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    result = gathered(root)
    smith, jones = result.refs["Smi24"], result.refs["Jon19"]
    made = make(result)
    stubs = [read(root, i) for i in made]
    assert [(n.taxon, n.number, n.source, n.empty) for n in stubs if n] == [
        ("lemma", "2.1", smith, True),
        ("theorem", "3", jones, True),
        ("lemma", "2.4", jones, True),
    ], "one for Lemma 2.1 however often it is cited, none for the work, a page, a part or a key with no work"
    got = targets(result)
    assert got[("Smi24", "Lemma~2.1")] == got[("Smi24", "Lemma 2.1")] == made[0]
    assert got[("Smi24", None)] == got[("Smi24", "p.~5")] == got[("Smi24", "Section 3")] == smith
    assert got[("Jon19", "Theorem 3 and Lemma 2.4")] == jones, "two results at once reach their work"
    assert got[("Nobody", "Lemma 9.9")] is None


def test_a_second_build_makes_no_stub_and_takes_no_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = quilt(tmp_path)
    made = make(gathered(root))
    before = sorted(p.name for p in folder(root).iterdir())

    def locked(_root: Path) -> None:
        raise AssertionError("nothing was due, so no lock is taken")

    monkeypatch.setattr("loom.library.gather.writing", locked)
    again = gathered(root)
    assert make(again) == [] and sorted(p.name for p in folder(root).iterdir()) == before
    assert targets(again)[("Smi24", "Lemma 2.1")] == made[0], "the next scan reaches the stub"


def test_a_cited_result_the_store_holds_is_reached_by_its_printed_number_its_taxon_breaking_a_tie(
    tmp_path: Path,
) -> None:
    """The source's taxon wins: a draft's "Lemma 2.1" reaches the work's Proposition 2.1, unless the work also prints a Lemma 2.1."""
    root = quilt(tmp_path)
    result = gathered(root)
    smith = result.refs["Smi24"]
    write_node(root, Node(id="tq-00P1", taxon="proposition", number="2.1", source=smith, body="A proposition.\n"))
    made = [read(root, i) for i in make(gathered(root))]
    assert [(n.number, n.source) for n in made if n] == [("3", result.refs["Jon19"]), ("2.4", result.refs["Jon19"])], (
        "Jones's two, and none for Smith's 2.1"
    )
    assert targets(gathered(root))[("Smi24", "Lemma 2.1")] == "tq-00P1"
    write_node(root, Node(id="tq-00Z1", taxon="lemma", number="2.1", source=smith, body="A lemma.\n"))
    assert targets(gathered(root))[("Smi24", "Lemma 2.1")] == "tq-00Z1"


def test_writing_nothing_says_what_would_be_made(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    result = gathered(root)
    assert make(result, write=False) == [
        f"{result.refs['Smi24']} lemma 2.1",
        f"{result.refs['Jon19']} theorem 3",
        f"{result.refs['Jon19']} lemma 2.4",
    ]
    assert not [p for p in folder(root).iterdir() if not p.name.endswith(("-ref.node", "-macros.node"))]


def test_a_fragment_is_made_again_when_what_its_citations_reach_changes(tmp_path: Path) -> None:
    """A stub made after a build changes what the citation's `data-target` names though the text is the same, so the fragment's cache key changes with it, and only then."""
    from loom.render.build import _input_hash

    root = quilt(tmp_path)
    first = gathered(root)
    key = next(k for k, n in first.nodes.items() if n.kind == "master")
    before = _input_hash(first, key, b"")
    make(first)
    after = _input_hash(gathered(root), key, b"")
    assert before != after and _input_hash(gathered(root), key, b"") == after
