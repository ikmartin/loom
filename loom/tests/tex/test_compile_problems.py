"""TeX tier: a real compile's error is a problem in the person's LaTeX on its document, at the line TeX names, whether the run stopped on it or made its PDF regardless, and it goes once the document compiles."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.paths import document_build
from loom.tex.runner import compile_document
from tests.helpers import edit, exits, json_of, ok
from tests.unit._quilts import demo

DOC = "drafting/main.tex"


def _compiled(q: Path, code: int) -> list[dict]:  # type: ignore[type-arg]
    return [
        d for d in json_of("lint", "--json", cwd=q, code=code)["diagnostics"] if d["code"].startswith("loom:compile-")
    ]


@pytest.mark.tex
def test_a_real_compile_s_error_is_a_problem_at_its_line_until_the_document_compiles(tmp_path: Path) -> None:
    q = demo(tmp_path)
    text = (q / DOC).read_text(encoding="utf-8")
    line = text[: text.index("\\begin{document}")].count("\n") + 2  # the line after \begin{document}
    edit(q / DOC, "\\begin{document}\n", "\\begin{document}\n\\undefinedmacro\n")
    # `loom compile` stops on the first error, before any page: no PDF
    exits(1, "compile", DOC, cwd=q)
    (d,) = _compiled(q, 1)
    assert (d["code"], d["class"], d["severity"], d["keys"]) == ("loom:compile-failed", "latex", "error", [DOC])
    assert d["message"] == "drafting/main.tex did not compile: Undefined control sequence \\undefinedmacro"
    assert d["locations"] == [{"file": DOC, "line": line}]
    # the server's compile carries on past an error and makes its PDF
    res = compile_document(q, "drafting", DOC, q / document_build(DOC), halt_on_error=False)
    assert res.pdf is not None and res.errors, res.first_error
    (d,) = _compiled(q, 1)
    assert d["code"] == "loom:compile-errors" and d["locations"] == [{"file": DOC, "line": line}]
    assert d["message"].startswith("drafting/main.tex compiled with 1 error, the first: Undefined control sequence")
    edit(q / DOC, "\\undefinedmacro\n", "")
    ok("compile", DOC, cwd=q)
    assert _compiled(q, 0) == []


@pytest.mark.tex
def test_an_error_in_a_package_or_the_bibliography_is_placed_in_that_file_never_on_the_document(tmp_path: Path) -> None:
    """TeX's line is a line of the file it was reading: the person's own package is where the problem is put, at its line; the bibliography BibTeX wrote is a file of the compile's, so the problem is on the document with no line, its message saying where TeX was."""
    q = demo(tmp_path)
    d = q / "drafting"
    (d / "sty.tex").write_text(
        "\\documentclass{article}\n\\usepackage{amssymb}\n\\usepackage{mymacros}\n\\begin{document}\nHello $\\R$.\n\\end{document}\n"
    )
    (d / "mymacros.sty").write_text(
        "\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesPackage{mymacros}\n\\newcommand{\\R}{\\mathbb{R}}\n\\newcommand{\\R}{\\mathbf{R}}\n"
    )
    (d / "bbl.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nSee \\cite{Smith20}.\n\nMore text.\n\n\\bibliographystyle{plain}\n\\bibliography{amp}\n\\end{document}\n"
    )
    (d / "amp.bib").write_text(
        "@article{Smith20,\n  author = {Smith, John},\n  title = {Rings & Modules},\n  journal = {J. Alg.},\n  year = {2020},\n}\n"
    )
    for doc in ("drafting/sty.tex", "drafting/bbl.tex"):
        compile_document(q, "drafting", doc, q / document_build(doc), halt_on_error=False)
    found = {d["keys"][0]: d for d in _compiled(q, 1)}
    sty, bbl = found["drafting/sty.tex"], found["drafting/bbl.tex"]
    assert sty["locations"] == [{"file": "drafting/mymacros.sty", "line": 4}]
    assert sty["message"].endswith("Command \\R already defined, in drafting/mymacros.sty")
    assert bbl["locations"] == []
    assert bbl["message"].startswith(
        "drafting/bbl.tex compiled with 1 error, the first: Misplaced alignment tab character &, in bbl.bbl, line "
    )
    assert bbl["message"].endswith("(the bibliography BibTeX made from the .bib)")
