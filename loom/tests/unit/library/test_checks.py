"""The eleven checks of docs/specs/nodes.md §11 (`library.checks`): the spec's nine files pass them all, and each check fails what it is for, said under its own code. Each case starts from the nine files and changes one thing."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library.checks import CODES, check, check_file, check_store
from loom.library.node import Node, node_bytes
from loom.paths import LIBRARY_NODES
from loom.scan.diagnostics import class_of
from tests.unit.library._examples import fixtures


def with_(*nodes: Node, drop: tuple[str, ...] = (), raw: dict[str, bytes] | None = None) -> dict[str, bytes]:
    """The nine files, with `nodes` written over or added, `drop` removed, and `raw` files as given."""
    files = fixtures()
    for name in drop:
        del files[name]
    files.update({n.file_name: node_bytes(n) for n in nodes})
    files.update(raw or {})
    return files


def found(files: dict[str, bytes]) -> list[tuple[str, str, str]]:
    """(file, code, message) for each diagnostic of the store."""
    return [(d.keys[0] + ".node", d.code, d.message) for d in check_store(files)]


def codes(files: dict[str, bytes]) -> list[tuple[str, str]]:
    return [(f, c) for f, c, _m in found(files)]


def says(files: dict[str, bytes], code: str, words: str) -> bool:
    return any(c == code and words in m for _f, c, m in found(files))


LEMMA = Node(
    id="tq-00K3",
    taxon="lemma",
    number="3.2",
    title="Test lemma",
    source="tq-00A1-ref",
    label="lem:test",
    pages="12",
    uses=("tq-00A4",),
    body="Let $W$ be a widget (Definition~\\ref{tq-00A4}). Then\n\\begin{equation}\\label{tq-00K3-eq00}\n  x\n\\end{equation}\n",
)


def lemma(**changes: object) -> Node:
    return Node(**{**LEMMA.__dict__, **changes})


def test_the_spec_s_nine_files_pass_every_check() -> None:
    assert check_store(fixtures()) == []


def test_each_failure_is_an_error_of_loom_s_records_under_its_check_s_code() -> None:
    files = with_(lemma(uses=("tq-00A4", "tq-00Z9")))
    [d] = check_store(files)
    assert (d.severity, d.code, d.class_, d.subject, d.owner) == (
        "error",
        "loom:node-edge",
        "internal",
        "record",
        "work",
    )
    assert d.locations[0].file == f"{LIBRARY_NODES}/tq-00K3.node"
    assert d.keys == ["tq-00K3"]
    assert all(class_of(code) == "internal" for code in CODES.values())


def test_a_node_stated_in_the_quilt_is_the_person_s_to_put_right() -> None:
    mine = Node(id="tq-00Q1", taxon="conjecture", authors=("Martin",), body="Every widget is round \\ref{tq-00Q2}.\n")
    [d] = check_store(with_(mine))
    assert (d.code, d.owner) == ("loom:node-body-ref", None)


def test_a_problem_in_the_body_names_the_file_s_line() -> None:
    files = with_(
        raw={
            "tq-00K9.node": b'+++\nschema = 1\nid = "tq-00K9"\ntaxon = "remark"\n# a comment\n+++\nFirst line.\nSee \\ref{tq-00A4}.\n'
        }
    )
    [d] = check_store(files)
    assert (d.code, d.locations[0].line) == ("loom:node-body-ref", 8)


# ---- 1 to 5: reading the file ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (b"schema = 1\n", "loom:node-unreadable"),
        (b'+++\nschema = 2\nid = "tq-00K9"\ntaxon = "lemma"\nsource = "tq-00A1-ref"\n+++\nx\n', "loom:node-schema"),
        (b'+++\nschema = 1\nid = "tq-00K8"\ntaxon = "lemma"\nsource = "tq-00A1-ref"\n+++\nx\n', "loom:node-id"),
        (b'+++\nschema = 1\nid = "tq-00K9"\ntaxon = "Lemma"\nsource = "tq-00A1-ref"\n+++\nx\n', "loom:node-taxon"),
        (
            b'+++\nschema = 1\nid = "tq-00K9"\ntaxon = "lemma"\nsource = "tq-00A1-ref"\nlean = "x"\n+++\nx\n',
            "loom:node-key",
        ),
    ],
)
def test_checks_1_to_5_are_said_of_a_file_no_node_is_read_from(data: bytes, code: str) -> None:
    assert codes(with_(raw={"tq-00K9.node": data})) == [("tq-00K9.node", code)]


def test_a_file_that_cannot_be_read_is_no_node_for_the_others() -> None:
    """The definition becomes unreadable: the lemma and both proofs that use it now name a node not in the library."""
    files = with_(raw={"tq-00A4.node": b"not a node\n"})
    assert ("tq-00A4.node", "loom:node-unreadable") in codes(files)
    assert {f for f, c in codes(files) if c == "loom:node-edge"} == {
        "tq-00K3.node",
        "tq-00K3-proof00.node",
        "tq-00K5.node",
    }


def test_check_file_without_a_view_checks_only_the_file() -> None:
    node, diags = check_file("tq-00K3.node", node_bytes(lemma(uses=("tq-00A4", "tq-00Z9"))))
    assert node is not None
    assert diags == []


# ---- 6: parents and sources --------------------------------------------------------------------------------------------


def test_check_6_a_proof_s_statement_exists() -> None:
    files = with_(drop=("tq-00K5.node",))
    assert says(files, "loom:node-parent", "tq-00K5-proof00.node is a proof of tq-00K5, which is not in the library.")


def test_check_6_a_macros_node_s_reference_exists() -> None:
    orphan = Node(id="tq-00C1-macros", taxon="macros", body="\\newcommand{\\x}{y}\n")
    assert says(with_(orphan), "loom:node-parent", "holds the macros of tq-00C1-ref, which is not in the library.")


@pytest.mark.parametrize("source", ["tq-00C1-ref", "tq-00A4", "Smi24"])
def test_check_6_a_source_is_a_reference_in_the_library(source: str) -> None:
    files = with_(lemma(source=source))
    assert says(files, "loom:node-parent", f"`source` is {source}, which is not a reference in the library.")


def test_check_6_a_stem_names_a_statement_or_a_work_never_both() -> None:
    clash = Node(id="tq-00A1", taxon="remark", source="tq-00B1-ref", body="x\n")
    files = with_(clash)
    assert says(files, "loom:node-parent", "tq-00A1.node's stem tq-00A1 is also the work tq-00A1-ref's")
    assert says(files, "loom:node-parent", "tq-00A1-ref.node's stem tq-00A1 is also the statement tq-00A1's")
    assert says(files, "loom:node-parent", "tq-00A1-macros.node's stem tq-00A1 is also the statement tq-00A1's")


# ---- 7: uses and mentions ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"uses": ("tq-00A4", "tq-00Z9")}, "`uses` names tq-00Z9, which is not in the library"),
        ({"mentions": ("tq-00A1-macros",)}, "`mentions` names tq-00A1-macros, a macros node"),
        ({"uses": ("tq-00A4",), "mentions": ("tq-00A4",)}, "lists tq-00A4 in both `uses` and `mentions`"),
        ({"uses": ("tq-00B7", "tq-00A4")}, "`uses` is not sorted."),
        ({"uses": ("tq-00A4", "tq-00A4")}, "lists tq-00A4 twice in `uses`."),
        ({"mentions": ("tq-00K3",)}, "lists itself in `mentions`."),
    ],
)
def test_check_7_what_a_node_lists_is_in_the_library_once_and_sorted(changes: dict[str, object], words: str) -> None:
    assert says(with_(lemma(**changes)), "loom:node-edge", words)


def test_check_7_a_node_may_list_what_its_body_does_not_point_at() -> None:
    """ "By the previous lemma": the header may list a node the text relies on without a reference to it."""
    assert check_store(with_(lemma(uses=("tq-00A4", "tq-00B7")))) == []


# ---- 8: what the body points at and defines ----------------------------------------------------------------------------


def body(text: str, **changes: object) -> dict[str, bytes]:
    """The nine files with the lemma's body `text`, still defining the anchor another proof points at."""
    return with_(lemma(body=text + "\\begin{equation}\\label{tq-00K3-eq00} x \\end{equation}\n", **changes))


def test_check_8_every_id_the_body_points_at_is_listed() -> None:
    files = body("By \\ref{tq-00A4} and \\cref{tq-00B7,tq-00K5}.\n")
    assert says(files, "loom:node-body-ref", "points at tq-00B7 and lists it in neither `uses` nor `mentions`.")
    assert says(files, "loom:node-body-ref", "points at tq-00K5 and lists it in neither")
    assert (
        check_store(
            body("By \\ref{tq-00A4} and \\cref{tq-00B7,tq-00K5}.\n", uses=("tq-00A4", "tq-00B7"), mentions=("tq-00K5",))
        )
        == []
    )


def test_check_8_an_anchor_s_owner_is_listed() -> None:
    proof = Node(id="tq-00K5-proof01", taxon="proof", uses=("tq-00A4",), body="By \\eqref{tq-00K3-eq00}.\n")
    assert says(with_(proof), "loom:node-body-ref", "points at tq-00K3 and lists it in neither")


def test_check_8_a_citation_is_of_a_listed_reference() -> None:
    assert says(
        body("See \\cite{tq-00B1-ref}.\n"), "loom:node-body-ref", "points at tq-00B1-ref and lists it in neither"
    )
    assert check_store(body("See \\cite[p.~3]{tq-00B1-ref}.\n", uses=(), mentions=("tq-00B1-ref",))) == []


def test_check_8_a_source_s_label_or_citekey_in_a_body_fails() -> None:
    files = body("By \\ref{def:widget}; see \\cite{Jon19} and \\cite{tq-00B7}.\n", uses=())
    assert says(
        files, "loom:node-body-ref", "points at def:widget with \\ref, and that is neither a node's id nor an anchor."
    )
    assert says(files, "loom:node-body-ref", "cites Jon19, which is not a reference's id")
    assert says(files, "loom:node-body-ref", "cites tq-00B7, which is not a reference's id")


def test_check_8_a_label_is_one_of_the_node_s_own_anchors_defined_once() -> None:
    files = body(
        "\\begin{equation}\\label{eq:bound} x \\end{equation}\\label{tq-00K5-eq00}\\label{tq-00K3-it00}\\label{tq-00K3-it00}\n",
        uses=(),
    )
    assert says(
        files,
        "loom:node-body-ref",
        "defines \\label{eq:bound}, and a label in a body is one of its own anchors, as tq-00K3-eq00 is.",
    )
    assert says(files, "loom:node-body-ref", "defines \\label{tq-00K5-eq00}")
    assert says(files, "loom:node-body-ref", "defines the anchor tq-00K3-it00 twice.")


def test_check_8_an_anchor_pointed_at_is_defined_by_its_owner() -> None:
    files = body("By \\eqref{tq-00K5-eq00} and \\eqref{tq-00K3-eq01}.\n", uses=("tq-00K5",))
    assert says(files, "loom:node-body-ref", "points at tq-00K5-eq00, which tq-00K5 does not define.")
    assert says(files, "loom:node-body-ref", "points at tq-00K3-eq01, which tq-00K3 does not define.")


def test_check_8_an_anchor_in_a_stub_cannot_be_known_and_passes() -> None:
    assert check_store(body("By \\eqref{tq-00B7-eq03}.\n", uses=("tq-00B7",))) == []


def test_check_8_a_proof_points_at_itself_its_statement_and_their_anchors_freely() -> None:
    proof = Node(
        id="tq-00K3-proof01",
        taxon="proof",
        body="By \\eqref{tq-00K3-eq00}, \\ref{tq-00K3} and \\eqref{tq-00K3-proof01-eq00}: \\begin{equation}\\label{tq-00K3-proof01-eq00}y\\end{equation}\n",
    )
    assert check_store(with_(proof)) == []


def test_check_8_an_anchor_given_a_number_is_defined_by_the_body() -> None:
    files = body("x\n", anchors=(("tq-00K3-eq00", "3.3"), ("tq-00K3-eq01", "3.4")))
    assert says(
        files,
        "loom:node-body-ref",
        "tq-00K3.node's `anchors` gives a number to tq-00K3-eq01, which its body does not define.",
    )
    assert check_store(body("x\n", anchors=(("tq-00K3-eq00", "3.3"),))) == []


def test_check_8_a_commented_reference_is_not_read() -> None:
    assert check_store(body("By \\ref{tq-00A4}. % and \\ref{tq-00K5}\n")) == []


# ---- 9: a reference's entry --------------------------------------------------------------------------------------------


def reference(text: str, node_id: str = "tq-00C1-ref") -> dict[str, bytes]:
    return with_(Node(id=node_id, taxon="reference", body=text))


def test_check_9_a_reference_s_body_is_one_entry_standing_alone() -> None:
    assert says(reference("Jones, A. Covering estimates.\n"), "loom:node-bibtex", "is not a BibTeX entry")
    assert says(
        reference("@string{JE = {Journal of Examples}}\n"),
        "loom:node-bibtex",
        "is an @string, where a reference's body is one entry standing alone.",
    )
    assert says(reference('@preamble{"\\newcommand{\\x}{y}"}\n'), "loom:node-bibtex", "is an @preamble")
    assert says(
        reference("@book{A, title={x}}\n@book{B, title={y}}\n"), "loom:node-bibtex", "holds more than its one entry"
    )
    assert says(
        reference("@article{Smi24x, title = {x}}\n% a note\n"), "loom:node-bibtex", "holds more than its one entry"
    )
    assert says(reference("@article{title = {x}}\n"), "loom:node-bibtex", "entry has no key")
    assert check_store(reference("@misc(Rob21,\n  title = {Notes},\n)\n")) == []


def test_check_9_no_two_references_share_a_key_ignoring_case() -> None:
    files = reference("@article{smi24,\n  title = {Widgets, again},\n}\n")
    assert says(files, "loom:node-bibtex", "tq-00C1-ref.node's entry key smi24 is also tq-00A1-ref's")
    assert says(files, "loom:node-bibtex", "tq-00A1-ref.node's entry key Smi24 is also tq-00C1-ref's")


# ---- 10: a macros node ---------------------------------------------------------------------------------------------


def macros(text: str) -> dict[str, bytes]:
    return with_(Node(id="tq-00A1-macros", taxon="macros", body=text))


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("\\documentclass{amsart}\n", "holds \\documentclass, which a macros node does not"),
        ("\\newtheorem{lemma}{Lemma}\n", "holds \\newtheorem"),
        ("\\input{defs}\n", "holds \\input"),
        ("\\title{Widgets}\n", "holds \\title"),
        ("\\begin{document}\n", "holds \\begin"),
        ("\\newcommand{\\x}{y}\nSome words.\n", "holds text, 'Some words.'"),
    ],
)
def test_check_10_a_macros_node_holds_only_package_loads_and_definitions(text: str, words: str) -> None:
    assert says(macros(text), "loom:node-macros", words)


def test_check_10_every_command_the_list_allows_passes() -> None:
    text = (
        "\\usepackage[utf8]{inputenc}\n\\RequirePackage{amsmath}\n\\usepackage{tikz}\\usetikzlibrary{arrows.meta}\n"
        "\\tikzset{every node/.style={draw}}\n\\pgfplotsset{compat=1.18}\n"
        "\\newcommand{\\a}{a}\\renewcommand*{\\b}[1]{#1}\\providecommand\\c{c}\\DeclareRobustCommand{\\d}{d}\n"
        "\\DeclareMathOperator{\\diam}{diam}\\DeclareMathOperator*{\\esssup}{ess\\,sup}\n"
        "\\DeclarePairedDelimiter\\abs{\\lvert}{\\rvert}\n\\NewDocumentCommand{\\e}{m}{#1}\n"
        "\\newenvironment{claim}{\\par}{\\par}\n\\def\\f#1{#1}\\gdef\\g{g}\\edef\\h{h}\\xdef\\i{i}\n"
        "\\let\\eps=\\varepsilon\n\\makeatletter\\def\\@j{j}\\makeatother\n"
    )
    assert check_store(macros(text)) == []


def test_check_10_names_the_line_of_what_it_refused() -> None:
    [d] = check_store(macros("\\newcommand{\\x}{y}\n\\newtheorem{lemma}{Lemma}\n"))
    assert d.locations[0].line == 7


# ---- 11: stubs and pointers --------------------------------------------------------------------------------------------


def test_check_11_a_pointer_says_where_the_proof_is() -> None:
    pointer = Node(id="tq-00K5-proof01", taxon="proof", source="tq-00B1-ref")
    assert says(
        with_(pointer),
        "loom:node-incomplete",
        "tq-00K5-proof01.node is a pointer, a proof with no text, and has no `pages`",
    )
    bare = Node(id="tq-00K5-proof01", taxon="proof")
    assert says(with_(bare), "loom:node-incomplete", "has no `source` or `pages`")
    assert check_store(with_(Node(id="tq-00K5-proof01", taxon="proof", source="tq-00B1-ref", pages="7-9"))) == []


def test_check_11_a_stub_says_which_work_it_stands_in() -> None:
    stub = Node(id="tq-00B8", taxon="lemma", number="2.2")
    assert says(
        with_(stub), "loom:node-incomplete", "tq-00B8.node is a stub, a statement with no text, and has no `source`"
    )
    whitespace = Node(id="tq-00B8", taxon="lemma", body="  \n\n")
    assert says(with_(whitespace), "loom:node-incomplete", "is a stub")


# ---- a quilt's store ---------------------------------------------------------------------------------------------------


def test_a_quilt_s_store_is_its_node_files_and_nothing_else(tmp_path: Path) -> None:
    assert check(tmp_path) == []
    folder = tmp_path / LIBRARY_NODES
    folder.mkdir(parents=True)
    for name, data in fixtures().items():
        (folder / name).write_bytes(data)
    (folder / ".DS_Store").write_bytes(b"\x00")
    (folder / "notes.txt").write_text("not a node")
    (folder / "old").mkdir()
    assert check(tmp_path) == []
    (folder / "tq-00K3.node").write_bytes(b"broken")
    assert ("tq-00K3", "loom:node-unreadable") in [(d.keys[0], d.code) for d in check(tmp_path)]


# ---- the review's findings ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["\\thmref{def:a}", "\\Citeyear{Jon19}", "\\secrefs{x}"])
def test_check_8_a_command_named_as_a_pointer_and_not_read_is_refused(command: str) -> None:
    """N-7."""
    assert says(
        body(f"By {command}.\n", uses=()), "loom:node-body-ref", "which loom does not read as pointing at anything"
    )


@pytest.mark.parametrize(
    "command",
    [
        "\\crefrange{tq-00A4}{def:b}",
        "\\hyperref[def:a]{text}",
        "\\citeyearpar{Jon19}",
        "\\cites(pre)(post){Jon19}",
        "\\nocite{Jon19}",
    ],
)
def test_check_8_a_source_s_label_in_a_command_off_the_old_lists_is_refused(command: str) -> None:
    """N-7: each of these let a source's label or key through."""
    found = check_store(body(f"See {command}.\n", uses=("tq-00A4",)))
    assert any(d.code == "loom:node-body-ref" and ("def:" in d.message or "Jon19" in d.message) for d in found), found


def test_check_8_a_reference_to_a_command_is_refused() -> None:
    """N-17."""
    assert says(body("By \\ref\\lbl.\n", uses=()), "loom:node-body-ref", "points at \\lbl with \\ref")


def test_check_8_a_label_with_cleveref_s_type_and_a_pointer_in_verbatim_pass() -> None:
    """N-17."""
    files = with_(
        lemma(body="See \\verb|\\ref{def:a}|.\n\\begin{equation}\\label[equation]{tq-00K3-eq00} x \\end{equation}\n")
    )
    assert check_store(files) == []


@pytest.mark.parametrize(
    ("data", "words"),
    [
        (
            b'+++\nschema = 1\nid = "tq-00K6"\ntaxon = "remark"\n+++\nA line.\r\nAnother.\n',
            "carriage return, where a node file ends its lines with a line feed alone, on line 6",
        ),
        (b'+++\nschema = 1\r\nid = "tq-00K6"\ntaxon = "remark"\n+++\nA line.\n', "carriage return"),
        (b'+++\nschema = 1\nid = "tq-00K6"\ntaxon = "remark"\n+++\nA \x00 line.\n', "NUL"),
    ],
)
def test_check_1_a_carriage_return_or_a_nul_anywhere_is_refused(data: bytes, words: str) -> None:
    """N-10: the same text with other line endings hashes otherwise, so a checkout through `core.autocrlf` would stale every record."""
    found = check_store(with_(raw={"tq-00K6.node": data}))
    assert [(d.code, words in d.message) for d in found] == [("loom:node-unreadable", True)], found


def test_check_9_an_entry_with_a_key_and_no_fields_has_a_key() -> None:
    """N-18."""
    assert check_store(reference("@misc{K1}\n")) == []


def test_check_9_an_abbreviation_left_unexpanded_is_refused_a_month_apart() -> None:
    """N-18."""
    assert says(
        reference("@article{K1,\n  journal = jex # { Letters},\n}\n"), "loom:node-bibtex", "uses jex unexpanded"
    )
    assert check_store(reference("@article{K1,\n  month = jan,\n  year = 2019,\n}\n")) == []
