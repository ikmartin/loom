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
