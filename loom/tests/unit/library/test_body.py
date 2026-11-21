"""Reading a node's body (`library.body`, docs/specs/nodes.md §4, §7, §8): what it points at, the anchors it defines, a reference's entry, and a macros node's items."""

from __future__ import annotations

from loom.library.body import blank_comments, entry_of, labels, macros_items, pointers


def said(body: str) -> list[tuple[str, str, int]]:
    return [(p.command, p.target, p.line) for p in pointers(body)]


def test_every_referencing_command_and_citation_is_read() -> None:
    body = (
        "By Lemma~\\ref{tq-00K3} and \\eqref{tq-00K3-eq00},\n"
        "see \\cref{tq-00A4, tq-00A5} and \\Cref*{tq-00A6}; \\autoref{tq-00A7}, \\pageref{tq-00A8}.\n"
        "Compare \\cite[p.~4]{tq-00B1-ref}, \\citep[see][Thm.~2]{tq-00C1-ref,tq-00D1-ref} and \\citealp{tq-00E1-ref}.\n"
    )
    assert said(body) == [
        ("ref", "tq-00K3", 1),
        ("eqref", "tq-00K3-eq00", 1),
        ("cref", "tq-00A4", 2),
        ("cref", "tq-00A5", 2),
        ("Cref", "tq-00A6", 2),
        ("autoref", "tq-00A7", 2),
        ("pageref", "tq-00A8", 2),
        ("cite", "tq-00B1-ref", 3),
        ("citep", "tq-00C1-ref", 3),
        ("citep", "tq-00D1-ref", 3),
        ("citealp", "tq-00E1-ref", 3),
    ]


def test_a_ref_s_argument_is_one_name_even_with_a_comma() -> None:
    assert said("\\ref{a,b}") == [("ref", "a,b", 1)]


def test_biblatex_s_cites_reads_every_group() -> None:
    assert said("\\cites[3]{tq-00B1-ref}[see][]{tq-00C1-ref}.") == [
        ("cites", "tq-00B1-ref", 1),
        ("cites", "tq-00C1-ref", 1),
    ]


def test_a_commented_reference_is_not_read() -> None:
    body = "A $50\\%$ bound \\ref{tq-0001} % not \\ref{tq-0002}\n% \\cite{tq-0003-ref}\n\\\\% after a line break \\ref{tq-0004}"
    assert said(body) == [("ref", "tq-0001", 1)]
    assert len(blank_comments(body)) == len(body)


def test_a_longer_command_is_not_a_reference() -> None:
    assert said("\\refstepcounter{x} \\citeauthor{tq-00B1-ref} \\nameref{tq-0001} \\cited{x}") == [
        ("citeauthor", "tq-00B1-ref", 1)
    ]


def test_labels_are_read_with_their_lines() -> None:
    body = "Then\n\\begin{equation}\\label{tq-00K3-eq00}\n x \\label{eq:bound}\n\\end{equation} % \\label{gone}\n"
    assert [(p.target, p.line) for p in labels(body)] == [("tq-00K3-eq00", 2), ("eq:bound", 3)]


def test_a_reference_s_body_is_read_as_its_entry_and_what_is_outside_it() -> None:
    entry = entry_of("\n@Article{Smi24,\n  title = {Widgets {and} bounds},\n}\n")
    assert entry is not None
    assert (entry.type, entry.key, entry.outside) == ("article", "Smi24", "")
    two = entry_of("@book{A, title={x}}\n@book{B, title={y}}\n")
    assert two is not None
    assert (two.key, two.outside) == ("A", "@book{B, title={y}}")
    paren = entry_of("@misc(K, note = {x})")
    assert paren is not None
    assert paren.key == "K"
    assert entry_of("Smith, J. Widgets. 2024.") is None
    assert entry_of("@article{Smi24, title = {open") is None
    keyless = entry_of("@article{title = {x}}")
    assert keyless is not None


def test_a_macros_body_is_read_item_by_item() -> None:
    body = (
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{amssymb,amsmath}\n"
        "\\newcommand{\\Wid}{\\mathcal{W}}\n"
        "\\newcommand*\\norm[1]{\\lVert #1\\rVert}\n"
        "\\renewcommand{\\phi}[2][x]{\\varphi_{#1}(#2)}\n"
        "\\DeclareMathOperator*{\\esssup}{ess\\,sup}\n"
        "\\DeclarePairedDelimiter\\abs{\\lvert}{\\rvert}\n"
        "\\def\\R#1{\\mathbb{R}^{#1}}\n"
        "\\let\\oldphi=\\phi\n"
        "\\let\\eps\\varepsilon\n"
        "\\makeatletter\\def\\@x{y}\\makeatother\n"
        "\\newenvironment{claim}[1][]{\\par\\textbf{Claim #1.}}{\\par}\n"
        "% \\documentclass{article}\n"
    )
    assert [i.command for i in macros_items(body)] == [
        "usepackage",
        "usepackage",
        "newcommand",
        "newcommand",
        "renewcommand",
        "DeclareMathOperator",
        "DeclarePairedDelimiter",
        "def",
        "let",
        "let",
        "makeatletter",
        "def",
        "makeatother",
        "newenvironment",
    ]


def test_what_a_macros_body_should_not_hold_is_an_item_of_its_own() -> None:
    """A command the reading does not know takes the groups after it, so each fault is one item."""
    items = macros_items("\\documentclass{amsart}\n\\newtheorem{lemma}{Lemma}\nSome words.\n\\input{defs}\n")
    commands = [(i.command, i.line) for i in items if i.command != "text"]
    assert commands == [("documentclass", 1), ("newtheorem", 2), ("input", 4)]
    assert any(i.command == "text" and "Some words." == i.text and i.line == 3 for i in items)
    assert len(items) == 4
