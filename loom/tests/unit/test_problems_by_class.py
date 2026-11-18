"""Problems by class: a document's last compile as a problem in the person's LaTeX, read from its log, in `loom lint` and in the manifest; and what reads the grades of loom's model, lint's exit and an agent's first look, says nothing of it as an error."""

from __future__ import annotations

import json
from pathlib import Path

from loom.paths import MANIFEST, document_build
from tests.helpers import edit, exits, json_of, ok
from tests.unit._quilts import demo

DOC = "drafting/main.tex"
#: A proof after `\item`, which LaTeX compiles and loom's model attaches to nothing.
UNATTACHED = "\\begin{enumerate}\n\\item One.\n\\begin{proof}\nThe answer is short.\n\\end{proof}\n\\end{enumerate}\n"


def _log(q: Path, text: str, doc: str = DOC) -> None:
    """A log as a compile of `doc` leaves it, in its compile folder."""
    out = q / document_build(doc)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{Path(doc).stem}.log").write_text(text, encoding="utf-8")


def _compiled(diags: list[dict]) -> list[dict]:  # type: ignore[type-arg]
    return [d for d in diags if d["code"].startswith("loom:compile-")]


def _linted(q: Path, code: int = 0) -> list[dict]:  # type: ignore[type-arg]
    return _compiled(json_of("lint", "--json", cwd=q, code=code)["diagnostics"])


def _published(q: Path) -> list[dict]:  # type: ignore[type-arg]
    return _compiled(json.loads((q / MANIFEST).read_text(encoding="utf-8"))["diagnostics"])


def test_a_failed_compile_is_a_problem_in_the_person_s_latex_on_its_document_until_it_compiles(tmp_path: Path) -> None:
    """The compile `loom compile` ran made no PDF: an error of class latex on the document, in lint's JSON and in the manifest alike, and gone once it compiles."""
    q = demo(tmp_path)
    exits(1, "compile", DOC, cwd=q, env={"FAKE_TEX_FAIL_MATCH": "main.tex"})
    (d,) = _linted(q, code=1)
    assert d == {
        "severity": "error",
        "code": "loom:compile-failed",
        "class": "latex",
        "message": "drafting/main.tex did not compile: LaTeX Error: fake failure requested by FAKE_TEX_FAIL",
        "locations": [{"file": DOC, "line": 1}],
        "keys": [DOC],
        "owner": "person",
    }
    exits(1, "build", cwd=q)
    assert _published(q) == [d]
    ok("compile", DOC, cwd=q)
    assert _linted(q) == []
    ok("build", cwd=q)
    assert _published(q) == []


def test_a_compile_with_errors_is_a_problem_at_the_file_and_line_tex_names(tmp_path: Path) -> None:
    """A PDF made though TeX reported errors: its first error, with the macro an undefined control sequence names, at the file TeX had open and the line it stopped at, on the document that compiles it."""
    q = demo(tmp_path)
    _log(
        q,
        "This is pdfTeX\n(./main.tex (./nodes/dm-0002.tex\n! Undefined control sequence.\nl.7 the orbit \\Orbit\n"
        "                    {x}\n)\n! Missing $ inserted.\nl.80 x^\n\nOutput written on main.pdf (3 pages, 1234 bytes).\n",
    )
    (d,) = _linted(q, code=1)
    assert (d["code"], d["class"], d["severity"]) == ("loom:compile-errors", "latex", "error")
    assert d["message"] == "drafting/main.tex compiled with 2 errors, the first: Undefined control sequence \\Orbit"
    assert d["locations"] == [{"file": "drafting/nodes/dm-0002.tex", "line": 7}] and d["keys"] == [DOC]
    # a log whose errors are in a file not of the quilt says the document, not a line of another file
    _log(q, "(./main.tex (/usr/share/texmf/tex/latex/x/x.tex\n! Undefined control sequence.\nl.3 \\y\n)")
    (d,) = _linted(q, code=1)
    assert (d["code"], d["locations"]) == ("loom:compile-failed", [{"file": DOC, "line": 1}])
    _log(q, "(./main.tex\nLaTeX Warning: Reference `x' on page 1 undefined.\nOutput written on main.pdf (1 page).\n")
    assert _linted(q) == []  # a warning is no error


def test_loom_s_model_is_no_error_in_lint_s_exit_or_an_agent_s_first_look_and_a_failed_compile_is(
    tmp_path: Path,
) -> None:
    """A proof after `\\item` compiles: loom's model, a warning, so lint exits 0 and the first look counts no error; a document whose last compile failed is an error in both."""
    q = demo(tmp_path)
    edit(q / DOC, "\\end{document}", UNATTACHED + "\\end{document}")
    r = ok("lint", cwd=q)
    assert "warning loom:unattached-proof (model) (1)" in r.output.splitlines()
    live = next(ln for ln in ok("ai", "orient", cwd=q).stdout.splitlines() if ln.startswith("- lint: "))
    assert "error" not in live and "warnings" in live, live
    _log(q, "(./main.tex\n! Emergency stop.\nl.12 \\end{document}\n")
    assert exits(1, "lint", cwd=q).output.splitlines()[0].startswith("1 error, ")
    live = next(ln for ln in ok("ai", "orient", cwd=q).stdout.splitlines() if ln.startswith("- lint: "))
    assert live.startswith("- lint: 1 error, "), live


def test_lint_says_every_diagnostic_s_class_and_keeps_every_code_for_agents(tmp_path: Path) -> None:
    """Every diagnostic in lint's JSON carries one of the three classes, and the headings say it: the person is shown latex alone, an agent every code."""
    from loom.scan.diagnostics import CLASSES

    q = demo(tmp_path)
    edit(q / DOC, "\\end{document}", UNATTACHED + "\\end{document}")
    data = json_of("lint", "--json", cwd=q)
    assert data["diagnostics"] and all(d["class"] in CLASSES for d in data["diagnostics"])
    assert {d["code"] for d in data["diagnostics"]} >= {"loom:unattached-proof", "loom:uses-missing"}
    headings = [g["heading"] for g in data["groups"]]
    assert "warning loom:unattached-proof (model)" in headings, headings


def test_check_compiles_every_document_itself_and_reads_no_log_an_earlier_compile_left(tmp_path: Path) -> None:
    """A log from a compile that failed before the document was put right: `check` compiles it again and passes, and the compile it ran clears what lint says."""
    q = demo(tmp_path)
    _log(q, "(./main.tex\n! Emergency stop.\nl.9 \\end{document}\n")
    assert _linted(q, code=1)
    r = ok("check", cwd=q)
    assert r.output.startswith("check passed:") and "compile-failed" not in r.output
    assert _linted(q) == []
