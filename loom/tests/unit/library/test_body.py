"""Reading a node's body (`library.body`, docs/specs/nodes.md §4, §7, §8): what it points at, the anchors it defines, a reference's entry, and a macros node's items."""

from __future__ import annotations

from loom.library.body import blank_comments, entry_of, labels, macros_items, pointers, unknown


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
        ("citeauthor", "tq-00B1-ref", 1),
        ("nameref", "tq-0001", 1),
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


# ---- the commands a body points with, read or refused, and what it does not read ---------------------------------------


def test_cleveref_s_varioref_s_and_hyperref_s_commands_are_read() -> None:
    """N-7: every command of the lists, each argument as its shape says."""
    body = (
        "\\crefrange{tq-0001}{tq-0002} \\Crefrange*{tq-0003}{tq-0004} \\cpageref{tq-0005,tq-0006} \\Cpageref{tq-0007}\n"
        "\\labelcref{tq-0008} \\nameref{tq-0009} \\Nameref{tq-000A} \\autopageref{tq-000B} \\vrefrange{tq-000C}{tq-000D}\n"
        "\\hyperref[tq-000E]{the lemma} \\namecref{tq-000F} \\vpageref{tq-000G}\n"
    )
    assert [(c, t) for c, t, _ in said(body)] == [
        ("crefrange", "tq-0001"), ("crefrange", "tq-0002"), ("Crefrange", "tq-0003"), ("Crefrange", "tq-0004"),
        ("cpageref", "tq-0005"), ("cpageref", "tq-0006"), ("Cpageref", "tq-0007"), ("labelcref", "tq-0008"),
        ("nameref", "tq-0009"), ("Nameref", "tq-000A"), ("autopageref", "tq-000B"), ("vrefrange", "tq-000C"),
        ("vrefrange", "tq-000D"), ("hyperref", "tq-000E"), ("namecref", "tq-000F"), ("vpageref", "tq-000G"),
    ]  # fmt: skip
    assert unknown(body) == []


def test_every_citation_command_is_read_biblatex_s_notes_in_parentheses_passed_over() -> None:
    """N-7."""
    body = (
        "\\citeyearpar{tq-0001-ref} \\Citeauthor{tq-0002-ref} \\nocite{tq-0003-ref} \\fullcite{tq-0004-ref}\n"
        "\\citenum{tq-0005-ref} \\parencites(see)(and)[3]{tq-0006-ref}[4]{tq-0007-ref} \\textcites{tq-0008-ref}{tq-0009-ref}\n"
    )
    assert [(c, t) for c, t, _ in said(body)] == [
        ("citeyearpar", "tq-0001-ref"), ("Citeauthor", "tq-0002-ref"), ("nocite", "tq-0003-ref"), ("fullcite", "tq-0004-ref"),
        ("citenum", "tq-0005-ref"), ("parencites", "tq-0006-ref"), ("parencites", "tq-0007-ref"), ("textcites", "tq-0008-ref"),
        ("textcites", "tq-0009-ref"),
    ]  # fmt: skip


def test_a_command_named_as_a_pointer_and_not_read_is_found() -> None:
    """N-7: a new command is a refusal to widen the lists, never a pointer that passes unread."""
    body = "\\thmref{def:a} \\Citeyear{Jon19} \\mycites{x}\n\\href{https://x}{y} \\refstepcounter{x} % \\secref{x}\n"
    assert [(p.command, p.line) for p in unknown(body)] == [("thmref", 1), ("Citeyear", 1), ("mycites", 1)]


def test_a_reference_to_a_command_is_kept_for_the_checks() -> None:
    """N-17: `\\ref\\lbl` is passed on as it is, not passed over."""
    assert said("\\ref\\lbl") == [("ref", "\\lbl", 1)]


def test_verbatim_text_is_not_read() -> None:
    """N-17."""
    body = "Write \\verb|\\ref{def:a}| or \\verb*+\\cite{Jon19}+.\n\\begin{verbatim}\n\\ref{def:b} \\thmref{x}\n\\end{verbatim}\n\\ref{tq-0001}\n"
    assert said(body) == [("ref", "tq-0001", 5)]
    assert unknown(body) == []


def test_a_label_s_optional_type_is_passed_over() -> None:
    """N-17: cleveref's `\\label[type]{…}`."""
    assert [p.target for p in labels("\\label[equation]{tq-00K3-eq00}")] == ["tq-00K3-eq00"]


def test_an_entry_with_a_key_and_no_fields_has_its_key() -> None:
    """N-18."""
    found = entry_of("@misc{K1}\n")
    assert found is not None and found.key == "K1"


def test_an_entry_s_abbreviations_are_found_months_apart() -> None:
    """N-18."""
    found = entry_of(
        '@article{K1,\n  journal = jex # { Letters},\n  month = jan,\n  year = 2019,\n  note = "a {"} b" # x,\n}\n'
    )
    assert found is not None and found.bare == ("jex", "x")
    clean = entry_of("@article{K1, title = {A = B, # C}, year = {2019}}\n")
    assert clean is not None and clean.bare == ()


def test_a_work_s_own_commands_that_point_are_read_from_its_macros() -> None:
    from loom.library.body import wrapped, wrappers

    given = wrappers(
        "\\newcommand{\\eq}[1]{(\\ref{#1})}\n\\newcommand\\Lem[1]{Lemma~\\ref{lem:#1}}\n\\newcommand{\\cf}[2][see]{#1 \\cite{#2}}\n"
        "\\def\\thm#1{Theorem \\ref{#1}}\n\\newcommand{\\R}{\\mathbb{R}}\n\\renewcommand{\\ref}[1]{x}\n"
    )
    assert sorted(given) == ["Lem", "R", "cf", "eq", "thm"], "every command it defines; never one loom reads already"
    assert given["R"].uses == () and given["eq"].uses == (("ref", "#1"),)
    said = [
        (p.via, p.command, p.target)
        for p in wrapped("\\eq{a} \\Lem{b} \\cf{C1,C2} \\cf[cf.]{C3} \\thm{d} \\R % \\eq{e}\n", given)
    ]
    assert said == [
        ("eq", "ref", "a"), ("Lem", "ref", "lem:b"), ("cf", "cite", "C1"), ("cf", "cite", "C2"), ("cf", "cite", "C3"), ("thm", "ref", "d"),
    ]  # fmt: skip
