"""Digest (`library.digest`): a work's results written as nodes from its source's survey, its pointers rewritten, by loom's own hand, recorded as extracted."""

from __future__ import annotations

import re
from dataclasses import replace
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
    assert done.waiting == {
        "lem:far": "\\eqref{eq:outside}: an equation outside every result, which loom numbers only from a compile of the source"
    } and sorted(done.filled) == sorted([lemma, theorem]), (
        "the drafts' stubs, filled under their ids; a result pointing at an equation outside every result waits for the compile"
    )
    widget = stub(root, smith, "1.1")
    node = read(root, lemma)
    assert node is not None and (node.number, node.label, node.pages, node.uses) == ("1.2", "lem:bound", "1", (widget,))
    assert node.body == (
        f"Every widget $W$ (Definition~\\ref{{{widget}}}) satisfies\n\\begin{{equation}}\\label{{{lemma}-eq00}}\n|x| \\le 1 .\n\\end{{equation}}\n"
    ), "its own label in the header, a display's an anchor, a result of the same work its id"
    assert (node.anchors, node.awaiting) == ((), (f"{lemma}-eq00",)), (
        "without a compile its display's number waits for one"
    )
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
    from loom.library.digest import of_work

    assert not [n for n in of_work(root, smith) if n.number == "2.2"], (
        "not written until the compile numbers the equation it points at"
    )
    made = {r.on.name: r.get("from") for r in records(root, "digested")}  # type: ignore[attr-defined]
    assert set(made) == {widget, lemma, f"{lemma}-proof00", theorem, f"{theorem}-proof00"}
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
    assert undigested(root, smith, s) == ["lem:far"], "every item holds its text but the one waiting for the compile"


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
        "lem:far": "\\eqref{eq:outside}: an equation outside every result, which loom numbers only from a compile of the source"
    }, "which pointer, at what, and why"
    from loom.library.digest import of_work

    assert not [n for n in of_work(root, smith) if n.number == "2.2"], "an item that waits leaves no node behind"


def test_a_plan_writes_nothing(tmp_path: Path, pdf_text: list[str]) -> None:
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    s = surveyed(result, smith)
    files = sorted(p.name for p in (root / ".loom" / "library" / "nodes").iterdir())
    done = digest(result, smith, [i.item for i in s.items], s, write=False)
    assert (
        done.waiting
        == {
            "lem:far": "\\eqref{eq:outside}: an equation outside every result, which loom numbers only from a compile of the source"
        }
        and len(done.filled) == 2
        and done.made
    )
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


def test_a_pointer_proof_another_hand_made_is_kept_and_the_source_s_proof_takes_a_new_id(
    tmp_path: Path, pdf_text: list[str]
) -> None:
    """The review's C-4: a pointer is neither a stub nor loom's extraction, so digest writes the statement and its proof beside it and never over it."""
    from loom.library.node import Node
    from loom.library.store import write_nodes

    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    pointer = Node(id=f"{lemma}-proof00", taxon="proof", source=smith, pages="7")
    write_nodes(root, [pointer])
    held = read(root, pointer.id)
    done = digest(result, smith, ["lem:bound"], surveyed(result, smith))
    assert lemma in done.filled and read(root, pointer.id) == held, "the pointer as its hand left it"
    proofs = [p for p in done.made if p.startswith(f"{lemma}-proof")]
    assert proofs and pointer.id not in proofs
    written = read(root, proofs[0])
    assert written is not None and written.body.strip(), "the source's proof, read in full"


def test_a_node_whose_display_number_waits_passes_the_checks_and_draws_unnumbered(
    tmp_path: Path, pdf_text: list[str]
) -> None:
    """B, as ruled on 2026-11-25: without the person's compile a display's number is held back, the result written all the same; its anchor waits in `awaiting`, the checks pass it, a read draws a pointer at it with no number, and the outline says the result pointing outside every result waits."""
    from loom.library import reads
    from loom.library.checks import check

    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    digest(result, smith, ["lem:bound", "thm:main", "lem:far"], surveyed(result, smith))
    assert not [p for p in check(root) if p.code.startswith("loom:node")], "the store's checks pass it"
    theorem = stub(root, smith, "2.1")
    assert reads.node(result, theorem)["points"][f"{lemma}-eq00"] == {"number": None, "awaiting": True}
    from loom.evidence.webview import drafts

    assert drafts(result, {}, root).points(theorem)[f"{lemma}-eq00"] == {"number": None, "awaiting": True}, (
        "the Web's card draws it as the Library does"
    )
    rows = {i["item"]: i["waits"] for i in reads.work(result, smith)["outline"]["items"] if i["item"]}
    assert (rows["lem:far"], rows["lem:bound"]) == ("compile", None)


def test_only_digest_sets_or_clears_awaiting(tmp_path: Path, pdf_text: list[str]) -> None:
    """An agent's correction that numbers a waiting anchor, or drops it from `awaiting`, is refused by the check every correction passes before it is filed or taken (`acts._takeable`)."""
    from loom.evidence.acts import ActRefused, propose
    from loom.library.node import node_bytes

    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    digest(result, smith, ["lem:bound"], surveyed(result, smith))
    node = read(root, lemma)
    assert node is not None
    agent = Who("agent", "Claude Code Agent")
    for forged in (
        replace(node, awaiting=(), anchors=((f"{lemma}-eq00", "1.1"),)),
        replace(node, awaiting=(), body=node.body + " "),
    ):
        with pytest.raises(ActRefused) as refused:
            propose(root, lemma, node_bytes(forged), agent, "it is 1.1")
        assert refused.value.code == "refused" and "wait for a compile" in str(refused.value)


@pytest.mark.tex
def test_the_person_s_compile_numbers_what_waited(tmp_path: Path, pdf_text: list[str]) -> None:
    """The person's compile, their own act, confirms the displays' numbers against the stored PDF: digest then fills `anchors`, empties `awaiting`, and writes the result that pointed outside every result."""
    result, smith = quilt(
        tmp_path,
        source=SOURCE.replace("\\documentclass{article}\n", "\\documentclass{article}\n\\usepackage{amsmath,amsthm}\n"),
    )
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    every = [i.item for i in surveyed(result, smith).items]
    digest(result, smith, every, surveyed(result, smith))
    held = read(root, lemma)
    assert held is not None and held.awaiting == (f"{lemma}-eq00",)
    node = read(root, smith)
    assert node is not None and node.tex and node.pdf
    src = documents.source_dir(root, node.tex)
    compiled = survey.complete(
        root, node.tex, src, "main.tex", node.pdf, documents.path_of(root, node.pdf, "pdf"), online=False
    )
    assert compiled.compiled and compiled.state == "ready", compiled.why
    from loom.library.digest import scoped

    again = scoped(result, smith, compiled, "all", None)
    assert "lem:bound" in again, "scope all takes, after a compile, a node of loom's whose number waited"
    done = digest(result, smith, again, compiled)
    assert done.waiting == {}, done.waiting
    filled = read(root, lemma)
    assert filled is not None and (filled.anchors, filled.awaiting) == (((f"{lemma}-eq00", "1.1"),), ())
    from loom.library.digest import of_work

    far = next(n for n in of_work(root, smith) if n.number == "2.2")
    assert far.body == "This lemma uses (2.1) as its only display.\n", "its number as the compile confirms it"


def _compiled(result: ScanResult, ref: str) -> survey.Survey:
    """The unasked survey as the person's compile would leave it: judged by a compile, `eq:bound` confirmed as 1.1 (the TeX-tier test above runs the compile itself)."""
    s = survey.Survey.from_json(surveyed(result, ref).to_json())
    s.compiled = True
    s.labels["eq:bound"] = replace(s.labels["eq:bound"], number="1.1")
    return s


def _waiting(tmp_path: Path) -> tuple[ScanResult, str, str]:
    """Smith 2024 with Lemma 1.2 digested without a compile, its display's anchor waiting: the scan, the work and the lemma."""
    result, smith = quilt(tmp_path)
    root = result.quilt.root
    lemma = stub(root, smith, "1.2")
    digest(result, smith, ["lem:bound"], surveyed(result, smith))
    held = read(root, lemma)
    assert held is not None and held.awaiting == (f"{lemma}-eq00",) and held.anchors == ()
    return result, smith, lemma


def _hash(root: Path, node: str) -> str:
    held = read(root, node)
    assert held is not None
    return node_hash(node_bytes(held))


def test_the_person_s_compile_numbers_a_compared_node_and_its_check_holds(tmp_path: Path, pdf_text: list[str]) -> None:
    """The author's choice of 2026-11-26: after the person's compile, the person's digest fills a checked node's waiting display numbers and nothing else, recorded `digested` how `numbered` from `{ref, tex}` naming the text it filled, and the person's `compared` holds on the new text."""
    from loom.library import reads

    result, smith, lemma = _waiting(tmp_path)
    root = result.quilt.root
    before = read(root, lemma)
    was = _hash(root, lemma)
    acts.check(root, lemma, was, ME)
    done = digest(result, smith, ["lem:bound"], _compiled(result, smith), numbers=True)
    assert done.numbered == [lemma] and lemma in done.kept, done
    after = read(root, lemma)
    assert after is not None and before is not None
    assert (after.anchors, after.awaiting) == (((f"{lemma}-eq00", "1.1"),), ())
    assert replace(after, anchors=(), awaiting=before.awaiting) == before, "nothing but the numbers changed"
    now = _hash(root, lemma)
    evidence = replay(root)
    filled = [r for r in evidence.about("node", lemma, of="digested") if r.on is not None and r.on.hash == now]
    assert [(r.by.kind, r.get("how"), r.get("was"), r.get("from")) for r in filled] == [
        ("loom", "numbered", was, {"ref": smith, "tex": read(root, smith).tex})  # type: ignore[union-attr]
    ]
    assert [r.on.hash for r in evidence.compared("node", lemma, now) if r.on] == [was], "the person's own record"
    got = reads.node(result, lemma)
    assert got["paper"] == "matches" and got["digested"]["how"] == "extracted", got
    assert digest(result, smith, ["lem:bound"], _compiled(result, smith), numbers=True).numbered == [], "once"
    status, _record = acts.propose(root, lemma, node_bytes(replace(after, body=after.body + "x\n")), Who("agent", "A"), "w")  # fmt: skip
    assert status == "proposed", "an agent's correction of it waits for the person, as of any node they compared"


def test_the_persons_compile_alone_numbers_what_awaits_it(
    tmp_path: Path, pdf_text: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`library-compile`'s job: the compile, then each anchor awaiting its number filled, and nothing else digested."""
    from loom.library.digest import compile_work, of_work

    result, smith, lemma = _waiting(tmp_path)
    root = result.quilt.root
    held = {n.id for n in of_work(root, smith)}
    monkeypatch.setattr(survey, "complete", lambda *_a, **_k: _compiled(result, smith))
    s = compile_work(root, smith, online=False)
    assert s is not None and s.compiled
    filled = read(root, lemma)
    assert filled is not None and (filled.anchors, filled.awaiting) == (((f"{lemma}-eq00", "1.1"),), ())
    assert {n.id for n in of_work(root, smith)} == held, "no result digested that was not asked for"


def test_a_corrected_node_is_numbered_alike(tmp_path: Path, pdf_text: list[str]) -> None:
    """A node an agent corrected, and one the person corrected by hand, are kept by digest as another hand's and numbered alike: the corrected words stay, and how they were made reads through the numbers."""
    for hand in ("agent", "person"):
        (tmp_path / hand).mkdir()
        result, smith, lemma = _waiting(tmp_path / hand)
        root = result.quilt.root
        held = read(root, lemma)
        assert held is not None
        words = held.body.replace("satisfies", "obeys")
        if hand == "agent":
            assert acts.propose(root, lemma, node_bytes(replace(held, body=words)), Who("agent", "A"), "w")[0] == "written"  # fmt: skip
        else:
            acts.correct(root, lemma, _hash(root, lemma), words, ME)
        was = _hash(root, lemma)
        done = digest(result, smith, ["lem:bound"], _compiled(result, smith), numbers=True)
        assert done.numbered == [lemma], (hand, done)
        after = read(root, lemma)
        assert after is not None and after.body == words and after.awaiting == ()
        evidence = replay(root)
        made = evidence.made("node", lemma, _hash(root, lemma))
        assert made is not None and made.get("how") == ("corrected" if hand == "agent" else "written")
        assert bool(evidence.compared("node", lemma, _hash(root, lemma))) == (hand == "person")
        assert evidence.texts("node", lemma, _hash(root, lemma)) == [_hash(root, lemma), was]


def test_numbering_refuses_any_change_beyond_the_numbers(tmp_path: Path, pdf_text: list[str]) -> None:
    """`acts.numbered` writes a file only where it is the one now with waiting anchors numbered, every other byte the same; anything else is refused, and nothing is written or recorded."""
    from loom.library.node import Node

    result, smith, lemma = _waiting(tmp_path)
    root = result.quilt.root
    held = read(root, lemma)
    assert held is not None
    was = _hash(root, lemma)
    tex = read(root, smith).tex  # type: ignore[union-attr]
    anchor = f"{lemma}-eq00"
    good = replace(held, anchors=((anchor, "1.1"),), awaiting=())
    assert acts.only_numbers(held, good) is None
    forged: list[Node] = [
        replace(good, body=held.body.replace("satisfies", "obeys")),
        replace(good, title="Bound"),
        replace(good, pages="9"),
        replace(good, uses=(*held.uses, smith)),
        replace(held, anchors=((anchor, ""),), awaiting=()),
        replace(held, anchors=((anchor, "1.1"), (f"{lemma}-eq01", "1.2")), awaiting=()),
        held,
    ]
    count = len(records(root, "digested"))
    for new in forged:
        with pytest.raises(acts.ActRefused) as refused:
            acts.numbered(root, lemma, was, new, {"ref": smith, "tex": tex})
        assert refused.value.code == "refused", new
    with pytest.raises(acts.ActRefused) as refused:
        acts.numbered(root, lemma, was, good, {"ref": "tq-0000-ref", "tex": tex})
    assert refused.value.code == "refused", "a number from another work's source"
    with pytest.raises(acts.ActRefused) as refused:
        acts.numbered(root, lemma, "sha256:" + "0" * 64, good, {"ref": smith, "tex": tex})
    assert refused.value.code == "changed", "a text no longer the one digest read"
    assert _hash(root, lemma) == was and len(records(root, "digested")) == count, "nothing written, nothing recorded"
    acts.numbered(root, lemma, was, good, {"ref": smith, "tex": tex})
    with pytest.raises(acts.ActRefused):
        acts.numbered(root, lemma, _hash(root, lemma), replace(good, anchors=((anchor, "2.1"),)), {"ref": smith, "tex": tex})  # fmt: skip


def test_no_agent_and_no_unasked_digest_reaches_numbering(tmp_path: Path, pdf_text: list[str]) -> None:
    """Only the person's digest after their compile fills a kept node's numbers: the log refuses `numbered` from any hand but loom's, an agent's correction cannot change `awaiting` (`test_only_digest_sets_or_clears_awaiting`), the unasked digest and a survey no compile judged leave it waiting, a node whose anchors loom gave from another source stays waiting, and only digest calls the act."""
    import loom
    from loom.evidence.log import EvidenceRefused, check

    result, smith, lemma = _waiting(tmp_path)
    root = result.quilt.root
    was = _hash(root, lemma)
    acts.check(root, lemma, was, ME)
    tex = read(root, smith).tex  # type: ignore[union-attr]
    on = replay(root).about("node", lemma, of="compared")[-1].on
    for hand in (Who("agent", "A"), ME):
        with pytest.raises(EvidenceRefused):
            check("digested", hand, on=on, how="numbered", was="sha256:" + "1" * 64, **{"from": {"ref": smith, "tex": tex}})  # fmt: skip
    with pytest.raises(acts.ActRefused):
        acts.digested(root, lemma, was, Who("agent", "A"), "numbered", {"ref": smith, "tex": tex})
    assert digest(result, smith, ["lem:bound"], _compiled(result, smith)).numbered == [], "the unasked path's digest"
    assert digest(result, smith, ["lem:bound"], surveyed(result, smith), numbers=True).numbered == [], "no compile"
    other = replace(_compiled(result, smith), tex="sha256:" + "2" * 64)
    from loom.library.digest import _Run

    run = _Run(result, read(root, smith), other, True, numbers=True)  # type: ignore[arg-type]
    run.work = replace(run.work, tex=other.tex)
    assert run.run(["lem:bound"]).numbered == [], "anchors given from another text of the source"
    assert _hash(root, lemma) == was
    src = Path(loom.__file__).parent
    calls = re.compile(r"from loom\.evidence\.acts import [^\n]*\bnumbered\b|acts\.numbered\(")
    callers = sorted(p.relative_to(src).as_posix() for p in src.rglob("*.py") if calls.search(p.read_text()))
    assert callers == ["library/digest.py"], callers


def test_a_number_goes_only_to_the_display_it_was_printed_for(tmp_path: Path, pdf_text: list[str]) -> None:
    """The numbered review's N-1 and N-2: an anchor is its label's place in the source, and a correction may move it to another display or give the node another result's label; the compile's number is filled only where the node's display holding the anchor is the source's display holding that label, so a corrected node whose displays still match is numbered and the rest wait."""
    two = SOURCE.replace(
        "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\n",
        "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\nand\n\\begin{equation}\\label{eq:two}\n|y| \\le 2 .\n\\end{equation}\n",
    ).replace(
        "By Section~\\ref{sec:w} and \\eqref{eq:bound}, every widget is bounded.\n",
        "By Section~\\ref{sec:w} and \\eqref{eq:bound}, every widget is bounded:\n\\begin{equation}\\label{eq:main}\nz = 3\n\\end{equation}\n",
    )
    pdf_text[0] = pdf_text[0].replace("(1.1)\nProof.", "(1.1)\nand\n|y| ≤ 2 .\n(1.2)\nProof.")
    pdf_text[1] = pdf_text[1].replace("every widget is bounded.\n", "every widget is bounded:\nz = 3\n(2.1)\n").replace("y = 2\n(2.1)", "y = 2\n(2.2)")  # fmt: skip

    def compiled(result: ScanResult, ref: str) -> survey.Survey:
        s = survey.Survey.from_json(surveyed(result, ref).to_json())
        s.compiled = True
        for name, number in (("eq:bound", "1.1"), ("eq:two", "1.2"), ("eq:main", "2.1")):
            s.labels[name] = replace(s.labels[name], number=number)
        return s

    for case in ("swapped", "relabelled", "reworded"):
        (tmp_path / case).mkdir()
        result, smith = quilt(tmp_path / case, source=two)
        root = result.quilt.root
        lemma = stub(root, smith, "1.2")
        digest(result, smith, ["lem:bound"], surveyed(result, smith))
        held = read(root, lemma)
        assert held is not None and held.awaiting == (f"{lemma}-eq00", f"{lemma}-eq01"), held
        a, b = f"\\label{{{lemma}-eq00}}", f"\\label{{{lemma}-eq01}}"
        if case == "swapped":
            acts.correct(root, lemma, _hash(root, lemma), held.body.replace(a, "@").replace(b, a).replace("@", b), ME)
        elif case == "relabelled":
            acts.propose(root, lemma, node_bytes(replace(held, label="thm:main")), Who("agent", "A"), "w")
            acts.check(root, lemma, _hash(root, lemma), ME)
        else:
            acts.correct(root, lemma, _hash(root, lemma), held.body.replace("satisfies", "obeys"), ME)
        before = read(root, lemma)
        done = digest(result, smith, ["lem:bound", "thm:main"], compiled(result, smith), numbers=True)
        after = read(root, lemma)
        assert after is not None
        if case == "reworded":
            assert lemma in done.numbered and after.anchors == ((f"{lemma}-eq00", "1.1"), (f"{lemma}-eq01", "1.2"))
        else:
            assert lemma not in done.numbered and after == before, (case, after)


@pytest.mark.parametrize(
    ("display", "printed"),
    [
        (
            "\\begin{align}\n|x| &\\le 1 \\label{eq:bound} \\\\\n|y| &\\le 2 \\label{eq:two}\n\\end{align}\n",
            "|x| ≤ 1\n(1.1)\n|y| ≤ 2\n(1.2)\n",
        ),  # fmt: skip
        (
            "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\nand\n\\begin{equation}\\label{eq:two}\n|x| \\le 1 .\n\\end{equation}\n",
            "|x| ≤ 1 .\n(1.1)\nand\n|x| ≤ 1 .\n(1.2)\n",
        ),  # fmt: skip
    ],
    ids=["rows-of-one-align", "two-displays-alike"],
)
def test_two_anchors_whose_displays_read_alike_never_trade_numbers(
    tmp_path: Path, pdf_text: list[str], display: str, printed: str
) -> None:
    """The numbered review's N-3: two rows of one environment, or two displays of the same text, compare alike once labels are dropped; swapping their labels leaves both waiting, since the anchor's place in its display and among the node's anchors must be the source's, while the text as extracted is numbered."""
    source = SOURCE.replace("\\documentclass{article}\n", "\\documentclass{article}\n\\usepackage{amsmath}\n").replace(
        "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\n", display
    )
    pdf_text[0] = pdf_text[0].replace("|x| ≤ 1 .\n(1.1)\n", printed)
    for case in ("swapped", "as-extracted"):
        (tmp_path / case).mkdir()
        result, smith = quilt(tmp_path / case, source=source)
        root = result.quilt.root
        lemma = stub(root, smith, "1.2")
        digest(result, smith, ["lem:bound"], surveyed(result, smith))
        held = read(root, lemma)
        assert held is not None and held.awaiting == (f"{lemma}-eq00", f"{lemma}-eq01"), held
        a, b = f"\\label{{{lemma}-eq00}}", f"\\label{{{lemma}-eq01}}"
        body = held.body.replace(a, "@").replace(b, a).replace("@", b) if case == "swapped" else held.body + "\n"
        acts.correct(root, lemma, _hash(root, lemma), body, ME)
        before = read(root, lemma)
        s = survey.Survey.from_json(surveyed(result, smith).to_json())
        s.compiled = True
        for name, number in (("eq:bound", "1.1"), ("eq:two", "1.2")):
            s.labels[name] = replace(s.labels[name], number=number)
        done = digest(result, smith, ["lem:bound"], s, numbers=True)
        after = read(root, lemma)
        if case == "swapped":
            assert lemma not in done.numbered and after == before, after
        else:
            assert after is not None and after.anchors == ((a[7:-1], "1.1"), (b[7:-1], "1.2")), after


def test_an_anchor_moved_onto_an_unlabelled_twin_waits(tmp_path: Path, pdf_text: list[str]) -> None:
    """The numbered review's N-4: a correction moving the one anchor onto an unlabelled display of the same text keeps its order and its text; the display's place among the body's environments is the source's or the anchor waits, while the text as extracted is numbered."""
    source = SOURCE.replace(
        "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\n",
        "\\begin{equation}\\label{eq:bound}\n|x| \\le 1 .\n\\end{equation}\nand\n\\begin{equation}\n|x| \\le 1 .\n\\end{equation}\n",
    )
    pdf_text[0] = pdf_text[0].replace("(1.1)\nProof.", "(1.1)\nand\n|x| ≤ 1 .\n(1.2)\nProof.")
    for case in ("moved", "as-extracted"):
        (tmp_path / case).mkdir()
        result, smith = quilt(tmp_path / case, source=source)
        root = result.quilt.root
        lemma = stub(root, smith, "1.2")
        digest(result, smith, ["lem:bound"], surveyed(result, smith))
        held = read(root, lemma)
        assert held is not None and held.awaiting == (f"{lemma}-eq00",), held
        label, opening = f"\\label{{{lemma}-eq00}}", "\\begin{equation}"
        body = held.body + "\n"
        if case == "moved":
            body = held.body.replace(label, "", 1)
            at = body.index(opening, body.index("and")) + len(opening)
            body = body[:at] + label + body[at:]
        acts.correct(root, lemma, _hash(root, lemma), body, ME)
        before = read(root, lemma)
        s = survey.Survey.from_json(surveyed(result, smith).to_json())
        s.compiled = True
        s.labels["eq:bound"] = replace(s.labels["eq:bound"], number="1.1")
        done = digest(result, smith, ["lem:bound"], s, numbers=True)
        after = read(root, lemma)
        if case == "moved":
            assert lemma not in done.numbered and after == before, after
        else:
            assert after is not None and after.anchors == ((f"{lemma}-eq00", "1.1"),), after
