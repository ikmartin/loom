"""Digest (`library.digest`): a work's results written as nodes from its source's survey, its pointers rewritten, by loom's own hand, recorded as extracted."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence import acts
from loom.evidence.log import replay
from loom.evidence.subjects import Who
from loom.library import documents, log, survey
from loom.library.digest import digest, undigested, used
from loom.library.gather import gather
from loom.library.node import node_bytes, node_hash
from loom.library.references import attach
from loom.library.store import read
from loom.library.stubs import make
from loom.scan.quilt import load_quilt
from loom.scan.scan import ScanResult, scan

DRAFT = r"""\documentclass{article}
\begin{document}
By \cite[Lemma 1.2]{Smi24} and \cite[Theorem 2.1]{Smi24}.
\bibliography{refs}
\end{document}
"""
BIB = (
    "@article{Smi24,\n  author = {Smith, Jane},\n  title = {Widgets},\n  year = {2024},\n}\n"
    "@article{Jones19,\n  author = {Jones, Alex},\n  title = {Gadgets},\n  year = {2019},\n}\n"
)
#: The work's source: results pointing at each other, at a display inside one and one outside every result, at a heading, and at two other works, one the quilt holds under another key and one it does not.
SOURCE = r"""\documentclass{article}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{definition}[theorem]{Definition}
\numberwithin{equation}{section}
\begin{document}
\section{Widgets}\label{sec:w}
\begin{definition}[Widget]\label{def:widget}
A \emph{widget} is a compact set.
\end{definition}
\begin{lemma}\label{lem:bound}
Every widget $W$ (Definition~\ref{def:widget}) satisfies
\begin{equation}\label{eq:bound}
|x| \le 1 .
\end{equation}
\end{lemma}
\begin{proof}
By \eqref{eq:bound} and \cite[Lemma 2.1]{Jon19}; see \cite{Bel19}. % not \ref{def:widget}
\end{proof}
\section{Bounds}
\begin{theorem}[Main]\label{thm:main}
By Section~\ref{sec:w} and \eqref{eq:bound}, every widget is bounded.
\end{theorem}
\begin{proof}
Lemma~\ref{lem:bound}.
\end{proof}
\begin{lemma}\label{lem:far}
This lemma uses \eqref{eq:outside} as its only display.
\end{lemma}
\begin{equation}\label{eq:outside} y = 2 \end{equation}
\bibliography{refs}
\end{document}
"""
SOURCE_BIB = (
    "@article{Jon19,\n  author = {Jones, A.},\n  title = {Gadgets},\n  year = {2019},\n}\n"
    "@article{Bel19,\n  author = {Bellamy, B.},\n  title = {Orders},\n  year = {2019},\n  eprint = {1901.00001},\n  archiveprefix = {arXiv},\n}\n"
)
#: The work's stored PDF as `pdftotext` reads it.
PDF = [
    "1 Widgets\nDefinition 1.1 (Widget). A widget is a compact set.\nLemma 1.2. Every widget W (Definition 1.1) satisfies\n"
    "|x| ≤ 1 .\n(1.1)\nProof. By (1.1) and [2, Lemma 2.1]; see [1].\n",
    "2 Bounds\nTheorem 2.1 (Main). By Section 1 and (1.1), every widget is bounded.\nProof. Lemma 1.2.\n"
    "Lemma 2.2. This lemma uses (2.1) as its only display.\ny = 2\n(2.1)\n",
]
ME = Who("person", "A. Author")


@pytest.fixture
def pdf_text(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The stored PDF's pages as the survey reads them, which a test may change."""
    pages = list(PDF)
    monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls(pages)))
    return pages


def quilt(tmp_path: Path, draft: str = DRAFT, source: str = SOURCE) -> tuple[ScanResult, str]:
    """A quilt whose draft cites two results of Smith 2024, which holds its source and a PDF: the scan and Smith's reference."""
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(draft)
    (root / "refs.bib").write_text(BIB)
    result = scan(load_quilt(root))
    gather(result)
    make(result)
    smith = result.refs["Smi24"]
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "main.tex").write_text(source)
    (folder / "refs.bib").write_text(SOURCE_BIB)
    attach(root, smith, "tex", documents.put_source(root, folder), by="A. Author", kind="person")
    pdf = tmp_path / "smith.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    attach(root, smith, "pdf", documents.put_pdf(root, pdf), by="A. Author", kind="person")
    return result, smith


def surveyed(result: ScanResult, ref: str) -> survey.Survey:
    root = result.quilt.root
    node = read(root, ref)
    assert node is not None and node.tex and node.pdf
    src = documents.source_dir(root, node.tex)
    return survey.confirmed(
        root, node.tex, src, "main.tex", pdf=node.pdf, pdf_path=documents.path_of(root, node.pdf, "pdf")
    )


def stub(root: Path, ref: str, number: str) -> str:
    from loom.library.digest import of_work

    return next(n.id for n in of_work(root, ref) if n.number == number)


def records(root: Path, kind: str) -> list[object]:
    return list(replay(root).of_kind(kind))


def test_a_work_s_results_are_written_from_its_source_its_pointers_rewritten(
    tmp_path: Path, pdf_text: list[str]
) -> None:
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma, theorem = stub(root, smith, "1.2"), stub(root, smith, "2.1")
    s = surveyed(result, smith)
    done = digest(result, smith, [i.item for i in s.items], s)
    assert done.waiting == {} and sorted(done.filled) == sorted([lemma, theorem]), (
        "the drafts' stubs, filled under their ids"
    )
    widget = stub(root, smith, "1.1")
    node = read(root, lemma)
    assert node is not None and (node.number, node.label, node.pages, node.uses) == ("1.2", "lem:bound", "1", (widget,))
    assert node.body == (
        f"Every widget $W$ (Definition~\\ref{{{widget}}}) satisfies\n\\begin{{equation}}\\label{{{lemma}-eq00}}\n|x| \\le 1 .\n\\end{{equation}}\n"
    ), "its own label in the header, a display's an anchor, a result of the same work its id"
    assert node.anchors == ((f"{lemma}-eq00", "1.1"),), "numbered as the PDF shows it"
    assert node.found == "words", "found in the PDF by its own words, and said so"
    proof = read(root, f"{lemma}-proof00")
    jones, bellamy = result.refs["Jones19"], next(r for r in done.made if r.endswith("-ref"))
    other = stub(root, jones, "2.1")
    assert proof is not None and proof.body == (
        f"By \\eqref{{{lemma}-eq00}} and \\ref{{{other}}}; see \\cite{{{bellamy}}}. % not \\ref{{def:widget}}\n"
    ), "a located citation the other work's stub, a work alone its reference; a comment as it stands"
    assert (proof.uses, proof.mentions) == (tuple(sorted((other, bellamy))), ()), (
        "its own statement's anchor listed nowhere; after 'see' a use too, since loom marks no mention"
    )
    assert read(root, jones) is not None, "the work the quilt holds as Jones19 is the one the source cites as Jon19"
    assert log.replay(root).cited_from(bellamy) == smith, "made from Smith's bibliography, and said so"
    main = read(root, theorem)
    assert main is not None and main.body == f"By Section~1 and \\eqref{{{lemma}-eq00}}, every widget is bounded.\n"
    assert main.uses == (lemma,), "a heading is no node: its number as the work prints it"
    far = read(root, stub(root, smith, "2.2"))
    assert far is not None and far.body == "This lemma uses (2.1) as its only display.\n", (
        "a display outside every result, its number as printed"
    )
    made = {r.on.name: r.get("from") for r in records(root, "digested")}  # type: ignore[attr-defined]
    assert set(made) == {widget, lemma, f"{lemma}-proof00", theorem, f"{theorem}-proof00", far.id}
    assert all(m == {"ref": smith, "tex": read(root, smith).tex} for m in made.values()), "what each was read from"  # type: ignore[union-attr]
    assert {r.get("how") for r in records(root, "digested")} == {"extracted"}  # type: ignore[attr-defined]


def test_digesting_again_writes_nothing_and_a_compared_node_is_kept(tmp_path: Path, pdf_text: list[str]) -> None:
    """The guards for "A digest records what it was read from" and "Redoing a step keeps what a person verified"."""
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    s = surveyed(result, smith)
    every = [i.item for i in s.items]
    digest(result, smith, every, s)
    lemma = stub(root, smith, "1.2")
    before = len(records(root, "digested"))
    again = digest(result, smith, every, s)
    assert (again.made, again.filled, again.rewritten, again.kept) == ([], [], [], []) and len(
        records(root, "digested")
    ) == before
    node = read(root, lemma)
    assert node is not None
    acts.check(root, lemma, node_hash(node_bytes(node)), ME)
    third = digest(result, smith, every, s)
    assert lemma in third.kept and "lem:bound" in third.waiting and read(root, lemma) == node
    assert undigested(root, smith, s) == [], "every item holds its text"


def test_a_stub_its_source_does_not_print_is_sought_once(tmp_path: Path, pdf_text: list[str]) -> None:
    result, smith = quilt(tmp_path, DRAFT.replace("Theorem 2.1", "Lemma 7.7"))
    root = result.quilt.root
    s = surveyed(result, smith)
    missing = stub(root, smith, "7.7")
    assert used(result, smith, s) == ["lem:bound"], "only what the drafts cite, by a number the source prints"
    done = digest(result, smith, used(result, smith, s), s)
    assert done.sought == [missing] and read(root, missing).empty  # type: ignore[union-attr]
    digest(result, smith, used(result, smith, s), s)
    assert [r.on.name for r in records(root, "sought")] == [missing], "looked for once for each source"  # type: ignore[attr-defined]


def test_an_item_waits_while_a_number_it_prints_is_not_confirmed(tmp_path: Path, pdf_text: list[str]) -> None:
    pdf_text[1] = pdf_text[1].replace("(2.1)\n", "").replace("Lemma 2.2.", "Lemma 2.2 has")
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    s = surveyed(result, smith)
    done = digest(result, smith, ["lem:far", "thm:main"], s)
    assert done.waiting == {"lem:far": "its number (2.2 as loom reads it) is not confirmed in the work's PDF"}
    pdf_text[1] = PDF[1].replace("(2.1)\n", "")
    (tmp_path / "b").mkdir()
    result, smith = quilt(tmp_path / "b")
    root = result.quilt.root
    s = surveyed(result, smith)
    done = digest(result, smith, ["lem:far"], s)
    assert done.waiting == {
        "lem:far": "\\eqref{eq:outside}: the display's number (2.1 as loom reads it) is not confirmed in the work's PDF"
    }, "which pointer, at what, and why"
    from loom.library.digest import of_work

    assert not [n for n in of_work(root, smith) if n.number == "2.2"], "an item that waits leaves no node behind"


def test_a_plan_writes_nothing(tmp_path: Path, pdf_text: list[str]) -> None:
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    s = surveyed(result, smith)
    files = sorted(p.name for p in (root / ".loom" / "library" / "nodes").iterdir())
    done = digest(result, smith, [i.item for i in s.items], s, write=False)
    assert done.waiting == {} and len(done.filled) == 2 and done.made
    assert sorted(p.name for p in (root / ".loom" / "library" / "nodes").iterdir()) == files and not records(
        root, "digested"
    )


def test_the_unasked_job_digests_what_the_drafts_cite(tmp_path: Path, pdf_text: list[str]) -> None:
    from loom.library.unasked import attempt, due

    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma, theorem = stub(root, smith, "1.2"), stub(root, smith, "2.1")
    done = attempt(root, smith, online=False)
    assert done is not None and (done.outcome, done.why) == ("digested", None)
    assert not read(root, lemma).empty and not read(root, theorem).empty  # type: ignore[union-attr]
    assert {
        n.label
        for n in __import__("loom.library.digest", fromlist=["of_work"]).of_work(root, smith)
        if not n.empty and n.label
    } == {
        "def:widget",
        "lem:bound",
        "thm:main",
    }, "what they rest on, and nothing the drafts do not use"
    assert smith not in due(root)


def test_a_pointer_at_a_label_the_source_defines_twice_waits(tmp_path: Path, pdf_text: list[str]) -> None:
    """The review's C-3: TeX's `\\ref` prints the last definition and the survey keeps the first, so the result pointing by it waits, naming the label, rather than reach the wrong result."""
    result, smith = quilt(tmp_path, source=SOURCE.replace("\\section{Bounds}", "\\section{Bounds}\\label{def:widget}"))
    s = surveyed(result, smith)
    assert s.twice == ["def:widget"]
    done = digest(result, smith, ["lem:bound", "def:widget"], s)
    assert done.waiting == {"lem:bound": "\\ref{def:widget}: the source defines this label more than once"}
    assert "def:widget" not in done.waiting, "the result whose own label it is first is written"
