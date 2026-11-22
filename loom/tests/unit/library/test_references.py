"""Making a reference and its macros node (`library.references`, `library.macros`): the node written under the checks, the act recorded, stems drawn so none repeats, and a source's preamble taken for what a macros node may hold."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library import log
from loom.library.checks import check
from loom.library.documents import put_pdf, put_source
from loom.library.macros import macros_node, preamble_items
from loom.library.references import Minter, attach, make, remake_macros
from loom.library.store import NodeRefused, read

ME = {"by": "A. Author", "kind": "person"}
ENTRY = "@article{Smi24,\n  author = {Smith, Jane},\n  title  = {Widgets},\n  year   = {2024},\n}\n"

MAIN = r"""\documentclass{amsart}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,mydefs}
\input{defs}
\newtheorem{thm}{Theorem}
\title{Widgets}
\author{Jane Smith}
\newcommand{\R}{\mathbb{R}}
% \newcommand{\commented}{x}
\makeatletter
\def\@widget{W}
\makeatother
\setlength{\parindent}{0pt}
\begin{document}
\newcommand{\inbody}{x}
\end{document}
"""
STY = "\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesPackage{mydefs}\n\\RequirePackage{amssymb}\n\\newcommand{\\Z}{\\mathbb{Z}}\n\\def\\p@x{y}\n"
DEFS = "\\DeclareMathOperator{\\diam}{diam}\n\\usepackage{mydefs}\n"


def source(tmp_path: Path) -> Path:
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "main.tex").write_text(MAIN)
    (folder / "mydefs.sty").write_text(STY)
    (folder / "defs.tex").write_text(DEFS)
    return folder


def test_a_preamble_gives_what_a_macros_node_may_hold(tmp_path: Path) -> None:
    assert preamble_items(source(tmp_path)) == [
        "\\usepackage[utf8]{inputenc}",
        "\\usepackage{amsmath}",
        "\\makeatletter",
        "\\RequirePackage{amssymb}",
        "\\newcommand{\\Z}{\\mathbb{Z}}",
        "\\def\\p@x{y}",
        "\\makeatother",
        "\\DeclareMathOperator{\\diam}{diam}",
        "\\newcommand{\\R}{\\mathbb{R}}",
        "\\makeatletter",
        "\\def\\@widget{W}",
        "\\makeatother",
    ]


def test_a_source_with_no_class_or_nothing_to_hold_makes_no_macros(tmp_path: Path) -> None:
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "notes.tex").write_text("\\newcommand{\\x}{y}")
    assert preamble_items(folder) == []
    (folder / "main.tex").write_text("\\documentclass{article}\n\\title{x}\n\\begin{document}\\end{document}")
    assert preamble_items(folder) == []
    assert macros_node("tq-00A1-ref", []) is None


def test_a_reference_is_written_and_its_making_recorded(tmp_path: Path) -> None:
    minter = Minter("tq", ["tq-0009"])
    node = make(tmp_path, ENTRY, minter, how="paste", found_by="entry", source="pasted", **ME)
    assert node.id == "tq-000A-ref"
    assert read(tmp_path, "tq-000A-ref") == node and node.body == ENTRY
    made = log.replay(tmp_path).made(node.id)
    assert made is not None and (made["how"], made["key"], made["by"]) == ("paste", "Smi24", "A. Author")
    assert check(tmp_path) == []


def test_a_reference_with_a_source_gets_its_macros(tmp_path: Path) -> None:
    tex = put_source(tmp_path, source(tmp_path))
    node = make(tmp_path, ENTRY, Minter("tq", []), how="drop", tex=tex, **ME)
    macros = read(tmp_path, "tq-0001-macros")
    assert macros is not None and "\\newcommand{\\R}{\\mathbb{R}}" in macros.body
    assert node.tex == tex and check(tmp_path) == []


def test_a_document_is_attached_and_taken_off_and_the_macros_follow(tmp_path: Path) -> None:
    node = make(tmp_path, ENTRY, Minter("tq", []), how="paste", **ME)
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.4 x")
    digest = put_pdf(tmp_path, pdf)
    assert attach(tmp_path, node.id, "pdf", digest, source="p.pdf", **ME).pdf == digest
    tex = put_source(tmp_path, source(tmp_path))
    attach(tmp_path, node.id, "tex", tex, **ME)
    assert read(tmp_path, "tq-0001-macros") is not None
    attach(tmp_path, node.id, "tex", None, **ME)
    assert read(tmp_path, "tq-0001-macros") is None and read(tmp_path, node.id).tex is None  # type: ignore[union-attr]
    events = [a["event"] for a in log.replay(tmp_path).of(node.id)]
    assert events == ["made", "filed", "filed", "unfiled"]
    assert remake_macros(tmp_path, node.id) is None


def test_a_key_another_reference_has_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    minter = Minter("tq", [])
    make(tmp_path, ENTRY, minter, how="paste", **ME)
    with pytest.raises(NodeRefused):
        make(tmp_path, ENTRY.replace("Smi24", "smi24"), minter, how="paste", **ME)
    assert len(log.replay(tmp_path).lines) == 1


def test_a_document_the_store_does_not_hold_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        make(tmp_path, ENTRY, Minter("tq", []), how="drop", pdf="sha256:" + "0" * 64, **ME)


def test_stems_are_drawn_past_everything_seen_and_never_twice() -> None:
    minter = Minter("tq", ["tq-00K3", "x tq-0100-proof00 y", "q-0ZZZ"])
    assert [minter.stem() for _ in range(3)] == ["tq-0101", "tq-0102", "tq-0103"]


def test_a_preamble_s_at_begin_document_and_conditionals_are_taken_as_check_10_reads_them(tmp_path: Path) -> None:
    from loom.library.checks import check_file
    from loom.library.node import node_bytes

    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "main.tex").write_text(
        "\\documentclass{article}\n\\newif\\ifdraft\n\\drafttrue\n"
        "\\AtBeginDocument{\\renewcommand{\\phi}{\\varphi}\\maketitle}\n\\AtBeginDocument{\\maketitle}\n"
        "\\begin{document}\\end{document}\n"
    )
    items = preamble_items(folder)
    assert items == ["\\newif\\ifdraft", "\\drafttrue", "\\AtBeginDocument{\\renewcommand{\\phi}{\\varphi}}"]
    node = macros_node("tq-00A1-ref", items)
    assert node is not None
    assert check_file(node.file_name, node_bytes(node))[1] == []


def test_a_made_reference_never_replaces_a_node_of_its_id(tmp_path: Path) -> None:
    """The third look's M-26: a stem another writer gave meanwhile is refused loudly, and the work there stays as it was."""
    first = make(tmp_path, "@article{First1, title={The first}}\n", Minter("tq", []), how="paste", **ME)
    before = (tmp_path / ".loom/library/nodes" / f"{first.id}.node").read_bytes()
    with pytest.raises(NodeRefused):
        make(tmp_path, "@article{Second2, title={The second}}\n", Minter("tq", []), how="paste", **ME)
    assert (tmp_path / ".loom/library/nodes" / f"{first.id}.node").read_bytes() == before
    assert [a["key"] for a in log.replay(tmp_path).lines if a["event"] == "made"] == ["First1"], "nothing recorded"
