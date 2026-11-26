"""Problems by class: a document's last compile as a problem in the person's LaTeX, read from its log, in `loom lint` and in the manifest; and what reads the grades of loom's model, lint's exit and an agent's first look, says nothing of it as an error."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from loom import layout
from loom.paths import MANIFEST, document_build
from tests.helpers import edit, exits, json_of, ok
from tests.unit._quilts import demo

DOC = "drafting/main.tex"
QUILTS = Path(__file__).resolve().parents[1] / "quilts"
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
        "locations": [],  # the log opens no file, so TeX's line belongs to none the person can open
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
    assert d["message"] == (
        "drafting/main.tex compiled with 2 errors, the first: Undefined control sequence \\Orbit, in drafting/nodes/dm-0002.tex"
    )
    assert d["locations"] == [{"file": "drafting/nodes/dm-0002.tex", "line": 7}] and d["keys"] == [DOC]
    _log(q, "(./main.tex\nLaTeX Warning: Reference `x' on page 1 undefined.\nOutput written on main.pdf (1 page).\n")
    assert _linted(q) == []  # a warning is no error


def test_tex_s_line_is_a_line_of_the_file_it_was_reading_never_of_the_document(tmp_path: Path) -> None:
    """TeX's line belongs to the innermost file it was reading, whatever its kind: the person's own package is a place they can open; TeX's own file, the bibliography BibTeX wrote and the compile's aux are not, so the problem is on the document with no line, its message naming the file."""
    q = demo(tmp_path)
    (q / "drafting" / "mine.sty").write_text(
        "\\ProvidesPackage{mine}\n\\newcommand{\\R}{R}\n\\newcommand{\\R}{S}\n", encoding="utf-8"
    )
    _log(
        q,
        "(./main.tex (./mine.sty\n! LaTeX Error: Command \\R already defined.\n\nl.3 \\newcommand{\\R}\n                 {S}\n)\n",
    )
    (d,) = _linted(q, code=1)
    assert d["locations"] == [{"file": "drafting/mine.sty", "line": 3}]
    assert d["message"].endswith("Command \\R already defined, in drafting/mine.sty")
    _log(q, "(./main.tex (/usr/share/texmf/tex/latex/x/x.tex\n! Undefined control sequence.\nl.3 \\y\n)")
    (d,) = _linted(q, code=1)
    assert (d["code"], d["locations"]) == ("loom:compile-failed", [])
    assert d["message"] == "drafting/main.tex did not compile: Undefined control sequence \\y, in x.tex, line 3"
    # the bibliography, in the run's folder, its long path on one line, as every TeX loom starts writes its log (`runner.LOG_WIDTH`)
    line = "(./main.tex (" + str(q / ".loom/cache/tex/.main-0a1b2c3d.run-x1y2z3") + "/" + "b" * 80 + "/main.bbl"
    _log(
        q,
        f"{line}\n! Misplaced alignment tab character &.\nl.5 \\newblock Rings &\n                      modules.\n",
    )
    (d,) = _linted(q, code=1)
    assert d["locations"] == []
    assert d["message"] == (
        "drafting/main.tex did not compile: Misplaced alignment tab character &, in main.bbl, line 5 (the bibliography BibTeX made from the .bib)"
    )
    _log(
        q, "(./main.tex (./main.aux\n! Paragraph ended before \\@newl@bel was complete.\n<to be read again> \n\nl.4 \n)"
    )
    (d,) = _linted(q, code=1)
    assert d["locations"] == [] and d["message"].endswith(", in main.aux, line 4")


def test_a_file_the_fence_kept_out_is_said_as_that_and_not_as_missing(tmp_path: Path) -> None:
    """A file not found that the document's folder reaches through a link out of the quilt or into a hidden folder, or names by its full path, is one the fence kept out of the compile: the problem says so, in the person's words. A file no link leads to, or one truly missing, is said as TeX says it."""
    q = demo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "refs.sty").write_text("\\ProvidesPackage{refs}\n", encoding="utf-8")
    (q / "drafting/refs.sty").symlink_to(outside / "refs.sty")
    _log(q, "(./main.tex\n! LaTeX Error: File `refs.sty' not found.\n\nl.3 \\usepackage{refs}\n)\n")
    (d,) = _linted(q, code=1)
    assert d["message"] == (
        "drafting/main.tex did not compile: the fence kept TeX from reading refs.sty, which is outside the quilt; put a copy of it in the document's folder"
    )
    from loom.tex.runner import fence_refused

    here = q / "drafting"
    (q / ".private").mkdir()
    (q / ".private/notes.tex").write_text("x\n", encoding="utf-8")
    (here / "notes.tex").symlink_to("../.private/notes.tex")
    assert fence_refused("! I can't find file `notes'.", here, q).endswith(
        "reading notes, which is in a hidden folder; put a copy of it in the document's folder"
    )
    assert "named by its full path" in fence_refused(f"! LaTeX Error: File `{outside}/refs.sty' not found.", here, q)
    (here / "own.sty").write_text("\\ProvidesPackage{own}\n", encoding="utf-8")
    for error in (
        "! LaTeX Error: File `own.sty' not found.",  # in the folder, no link followed
        "! LaTeX Error: File `gone.sty' not found.",  # missing
        f"! LaTeX Error: File `{os.path.relpath(outside / 'refs.sty', here)}' not found.",  # above the document's folder: not staged, fenced or not
        "! Undefined control sequence.",
    ):
        assert fence_refused(error, here, q) == "", error


def test_a_line_a_document_writes_beginning_with_a_bang_is_no_error_and_a_runaway_s_message_ends_clean(
    tmp_path: Path,
) -> None:
    """TeX follows every error with its context; a `\\typeout{! …}` has none, so a document that compiles cleanly has no problem. A runaway argument's message keeps no trailing blank."""
    q = demo(tmp_path)
    _log(
        q,
        "(./main.tex\n! not an error, just a message\n\n\n[1\n\n{pdftex.map}]\n)\nOutput written on main.pdf (1 page).\n",
    )
    assert _linted(q) == []
    _log(
        q,
        "(./main.tex\n! File ended while scanning use of \\textbf .\n<inserted text> \n                \\par \n<*> main.tex\n",
    )
    (d,) = _linted(q, code=1)
    assert d["message"] == "drafting/main.tex did not compile: File ended while scanning use of \\textbf"


def test_a_problem_from_before_a_later_change_says_so_and_is_no_error(tmp_path: Path) -> None:
    """A log older than a file its document reads says what the last compile found, before that change: still listed, as a warning that names the change, which no exit counts; the next compile settles it."""
    import os
    import time

    q = demo(tmp_path)
    _log(q, "(./main.tex\n! Undefined control sequence.\nl.9 \\oops\n")
    assert [d["severity"] for d in _linted(q, code=1)] == ["error"]
    later = time.time() + 5
    os.utime(q / "drafting" / "nodes" / "dm-0002.tex", (later, later))
    (d,) = _linted(q)
    assert (d["severity"], d["class"]) == ("warning", "latex")
    assert d["message"] == (
        "drafting/main.tex did not compile when last compiled, before drafting/nodes/dm-0002.tex changed: Undefined control sequence \\oops"
    )
    ok("build", "--no-compile", cwd=q)


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


#: An agent's copy of a document beside another document: what each change to the copy makes of adoption, as loom refused it before its model was graded by what TeX does.
ADOPTED = {
    # a \uses and a \ref of a node only the other document has: refused, whatever their grade now
    "\\uses{zk-0050}\nFirst statement.": "zk-0001 refers to zk-0050, which its master does not reach",
    "First statement, by \\ref{zk-0050}.": "zk-0001 refers to zk-0050, which its master does not reach",
    # a \uses of nothing, and a stray proof: taken, then and now
    "\\uses{zk-0999}\nFirst statement.": None,
}


@pytest.mark.parametrize("change", list(ADOPTED), ids=["uses-other-doc", "ref-other-doc", "uses-dangling"])
def test_adoption_refuses_what_it_refused_before_any_regrade(tmp_path: Path, change: str) -> None:
    """Adoption will not bring in a new problem of a code that was an error, at any grade but info: a `\\uses` of a node the document does not reach is a warning now, and is refused as it was."""
    from loom.adopt import comparison, prepare
    from loom.history.ledger import load_history
    from loom.history.steps import write_step
    from loom.layout import stamp
    from loom.reshape.copy import plan_copy
    from loom.scan.quilt import load_quilt, save_author
    from loom.scan.scan import scan
    from loom.sync import SyncError

    save_author("Tester")  # the test's own HOME
    root = tmp_path / "q"
    (root / "drafting").mkdir(parents=True)
    stamp(root)
    (root / ".loom" / "agents" / "copies").mkdir(parents=True)
    (root / "config.toml").write_text('[quilt]\nname = "gate"\nprefix = "zk"\nmain = "drafting/main.tex"\n')
    (root / "drafting" / "loom.sty").write_text(
        (QUILTS / "edge" / "double-inclusion" / "drafting" / "loom.sty").read_text()
    )
    (root / DOC).write_text(
        "\\documentclass{article}\n\\usepackage{loom}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\nOriginal introduction.\n"
        "\\begin{lemma}\\label{zk-0001}\nFirst statement.\n\\end{lemma}\n\\begin{lemma}\\label{zk-0002}\nSecond statement uses \\ref{zk-0001}.\n\\end{lemma}\n\\end{document}\n"
    )
    (root / "drafting" / "other.tex").write_text(
        "\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n\\begin{lemma}\\label{zk-0050}\nOf the other document.\n\\end{lemma}\n\\end{document}\n"
    )
    copy = ".loom/agents/copies/proposal.tex"
    q = load_quilt(root)
    history = load_history(q.history_dir)
    cp = plan_copy(scan(q), history, DOC, copy)
    (root / copy).write_text(cp.text.replace("First statement.", change, 1))
    write_step(
        history,
        "copy",
        "copy-proposal",
        cp.freeze,
        "Tester",
        {"from": DOC, "to": copy, "bases": cp.bases},
        cp.source_text,
        "main.tex",
    )
    result = scan(q)
    keys = [r["key"] for r in comparison(result, copy)["changes"] if r.get("offered")]
    refused = ADOPTED[change]
    if refused is None:
        prepare(scan(q), copy, keys, True)
    else:
        with pytest.raises(SyncError, match=refused):
            prepare(scan(q), copy, keys, True)


def test_a_gate_reads_codes_not_grades() -> None:
    """A code that was an error before the regrades gates at any grade but info; a code added since gates nothing."""
    from loom.scan.diagnostics import gates
    from loom.scan.model import Diagnostic

    assert gates(Diagnostic("warning", "duplicate-id", "", []))
    assert gates(Diagnostic("warning", "loom:reference-to-loose", "", []))
    assert not gates(Diagnostic("info", "loom:reference-to-loose", "", []))
    assert not gates(Diagnostic("error", "loom:compile-failed", "", []))
    assert not gates(Diagnostic("warning", "loom:dependency-cycle", "", []))


def test_doing_what_an_id_defined_twice_says_leaves_no_new_problem(tmp_path: Path) -> None:
    """An id two documents define: the fix names the fresh id's place and every reference that goes with it, and doing exactly that leaves the quilt with no problem it did not have, no reference pointing at the other document's node."""
    import re

    q = tmp_path / "q"
    (q / "drafting" / "nodes").mkdir(parents=True)
    (q / ".loom").mkdir()
    (q / ".loom" / "format").write_text(f"{layout.NUMBER}\n")
    (q / "config.toml").write_text('[quilt]\nname = "fix"\nmain = "drafting/main.tex"\nprefix = "gr"\n')
    (q / "drafting" / "loom.sty").write_text(
        (QUILTS / "edge" / "double-inclusion" / "drafting" / "loom.sty").read_text()
    )
    head = "\\documentclass{amsart}\n\\usepackage{amsthm}\n\\usepackage{loom}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\n"
    (q / DOC).write_text(head + "\\input{nodes/x}\n\\input{nodes/y}\n\\end{document}\n")
    (q / "drafting" / "other.tex").write_text(
        head + "\\begin{lemma}\\label{gr-0005}\nOther X.\n\\end{lemma}\n\\end{document}\n"
    )
    (q / "drafting" / "nodes" / "x.tex").write_text("\\begin{lemma}\\label{gr-0005}\nX.\n\\end{lemma}\n")
    (q / "drafting" / "nodes" / "y.tex").write_text(
        "\\begin{lemma}\\label{gr-0006}\nBy Lemma~\\ref{gr-0005}, Y.\n\\end{lemma}\n"
    )
    before = json_of("lint", "--json", cwd=q)["diagnostics"]
    (dup,) = [d for d in before if d["code"] == "duplicate-id"]
    fix = next(f["command"] for f in dup["fixes"] if " in drafting/nodes/x.tex" in f["command"])
    assert fix == (
        "loom id --next, and put that id in place of gr-0005 in drafting/nodes/x.tex, "
        "and in every reference to gr-0005 in drafting/main.tex and the files it inputs"
    )
    fresh = ok("id", "--next", cwd=q).output.strip()
    for name in ("main.tex", "nodes/x.tex", "nodes/y.tex"):  # drafting/main.tex and the files it inputs
        f = q / "drafting" / name
        f.write_text(re.sub(r"\{gr-0005\}", "{" + fresh + "}", f.read_text()))
    after = json_of("lint", "--json", cwd=q)["diagnostics"]
    assert not [d for d in after if d["code"] in ("duplicate-id", "loom:reference-to-loose", "dangling-link")], after
    # what is new is the two lemmas, each a node of its own again, saying they have no proof
    new = {(d["code"], d["message"]) for d in after} - {(d["code"], d["message"]) for d in before}
    assert {code for code, _ in new} == {"loom:missing-proof"} and not [d for d in after if d["class"] == "latex"]


def test_a_person_is_still_told_of_a_circle_in_their_reasoning_and_of_a_document_never_closed(tmp_path: Path) -> None:
    """Two of the person's statements resting on each other is theirs to see, a warning of class latex as no block says it yet; a document whose `\\begin{document}` nothing closes is the fault TeX stops on, an error of class latex, where a theorem across two files stays loom's model's."""
    q = demo(tmp_path)
    circle = (
        "\\begin{lemma}\\label{dm-0090}\nBy Lemma~\\ref{dm-0091}.\n\\end{lemma}\n"
        "\\begin{lemma}\\label{dm-0091}\nBy Lemma~\\ref{dm-0090}.\n\\end{lemma}\n"
    )
    edit(q / DOC, "\\end{document}", circle + "\\end{document}")
    (cycle,) = [d for d in json_of("lint", "--json", cwd=q)["diagnostics"] if d["code"] == "loom:dependency-cycle"]
    assert (cycle["severity"], cycle["class"], cycle["owner"]) == ("warning", "latex", "person")
    edit(q / DOC, "\\end{document}", "")
    (unended,) = [
        d
        for d in json_of("lint", "--json", cwd=q, code=1)["diagnostics"]
        if d["code"] == "loom:environment-spans-files"
    ]
    assert (unended["severity"], unended["class"]) == ("error", "latex")
    assert unended["message"] == "\\begin{document} is never closed in this file"


def test_a_reference_to_a_block_the_document_does_not_read_is_graded_by_what_tex_prints(tmp_path: Path) -> None:
    """A `\\ref` from the document to a block only another document defines prints ?? in its PDF: an error of class latex. A `\\uses` of it prints nothing: a warning of loom's model. Between two files no document reads: an info."""
    q = demo(tmp_path)
    (q / "drafting" / "other.tex").write_text(
        (q / DOC).read_text().split("\\begin{document}")[0]
        + "\\begin{document}\n\\begin{lemma}\\label{dm-0095}\nElsewhere.\n\\end{lemma}\n\\end{document}\n"
    )
    uses = "\\begin{lemma}\\label{dm-0096}\n\\uses{dm-0095}\nUses it.\n\\end{lemma}\n"
    refs = "\\begin{lemma}\\label{dm-0097}\nBy Lemma~\\ref{dm-0095}.\n\\end{lemma}\n"
    edit(q / DOC, "\\end{document}", uses + refs + "\\end{document}")
    (q / "drafting" / "nodes" / "loose-a.tex").write_text(
        "\\begin{lemma}\\label{dm-0098}\nSee \\ref{dm-0099}.\n\\end{lemma}\n"
    )
    (q / "drafting" / "nodes" / "loose-b.tex").write_text("\\begin{lemma}\\label{dm-0099}\nLoose.\n\\end{lemma}\n")
    graded = {
        tuple(d["keys"][:1]): (d["severity"], d["class"])
        for d in json_of("lint", "--json", cwd=q, code=1)["diagnostics"]
        if d["code"] == "loom:reference-to-loose"
    }
    assert graded == {
        ("dm-0096",): ("warning", "model"),
        ("dm-0097",): ("error", "latex"),
        ("dm-0098",): ("info", "model"),
    }
