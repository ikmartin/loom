"""The survey of a TeX source: what it holds, read once and kept by the source's hash."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path

import pytest

from loom.library import survey
from loom.paths import LIBRARY_SURVEYS

TEX = "sha256:" + "ab" * 32
ARDEN = Path(__file__).parents[2] / "quilts" / "sources" / "showcase-works" / "arden-cycle-spaces-v2.tex"

#: A source with what a real paper holds and the showcase's does not: a file it inputs, a starred heading and result, an unlabelled lemma, a counter set by hand, displays and lists inside results and outside them, a figure, a proof with a label of its own, a bibliography, and an appendix.
MAIN = r"""\documentclass{amsart}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem*{claim}{Claim}
\theoremstyle{definition}
\newtheorem{defn}[theorem]{Definition}
\newtheorem{notation}[theorem]{Notation}
\begin{document}
\section{Introduction}\label{sec:intro}
% \appendix in a comment changes nothing
\begin{defn}[Widget]\label{def:widget}
A widget is a set.
\end{defn}
\begin{lemma}
Every widget is bounded:
\begin{equation}\label{eq:bound}
  |x| \le 1 .
\end{equation}
\end{lemma}
\begin{proof}\label{pf:bound}
By \eqref{eq:bound}.
\begin{enumerate}
\item\label{it:first} first;
\end{enumerate}
\end{proof}
\input{part2}
\section*{Acknowledgements}
\begin{claim}\label{claim:star}
Unnumbered.
\end{claim}
\setcounter{section}{6}
\clearpage
\section{Later}
\begin{figure}\caption{A picture}\label{fig:one}\end{figure}
\begin{equation}\label{eq:outside} y = 2 \end{equation}
\begin{notation}\label{not:hom}
We write $\mathrm{Hom}$.
\end{notation}
\appendix
\section{Proofs}\label{sec:proofs}
\begin{theorem}\label{thm:app}
A theorem in the appendix.
\end{theorem}
\bibliography{refs,missing}
\end{document}
"""

PART2 = r"""\section{Bounds}
\begin{theorem}[Main]\label{thm:main}\label{thm:alias}
Widgets are compact.
\end{theorem}
\begin{proof}
Lemma~\ref{lem:none}.
\end{proof}
"""


def _source(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(MAIN, encoding="utf-8")
    (src / "part2.tex").write_text(PART2, encoding="utf-8")
    (src / "refs.bib").write_text("@article{A,title={T}}\n", encoding="utf-8")
    return src


def test_a_source_s_sections_and_results_are_read_in_order_with_emulated_numbers(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    assert s.state == "reading" and s.why is None and s.engine == "pdflatex"
    assert [(x.section, x.command, x.emulated, x.title) for x in s.sections] == [
        ("s1", "section", "1", "Introduction"),
        ("s2", "section", "2", "Bounds"),
        ("s3", "section", None, "Acknowledgements"),
        ("s4", "section", "7", "Later"),
        ("s5", "section", "A", "Proofs"),
    ]
    assert s.sections[0].label == "sec:intro" and s.sections[4].label == "sec:proofs"
    rows = [(i.item, i.taxon, i.name, i.emulated, i.title, i.label, i.section) for i in s.items]
    assert rows == [
        ("def:widget", "definition", "Definition", "1.1", "Widget", "def:widget", "s1"),
        ("i2", "lemma", "Lemma", "1.2", None, None, "s1"),
        ("thm:main", "theorem", "Theorem", "2.1", "Main", "thm:main", "s2"),
        ("claim:star", "other", "Claim", None, None, "claim:star", "s3"),
        ("not:hom", "other", "Notation", "7.1", None, "not:hom", "s4"),
        ("thm:app", "theorem", "Theorem", "A.1", None, "thm:app", "s5"),
    ]
    assert all(i.number is None and i.page is None for i in s.items), "nothing is printed before a compile"
    main = s.item("thm:main")
    assert main is not None and main.file == "part2.tex" and main.labels == ["thm:main", "thm:alias"]
    assert PART2[main.body_start : main.body_end].strip() == "\\label{thm:main}\\label{thm:alias}\nWidgets are compact."


#: Honest sources that set their own numbering, each with what TeX prints for its headings and its results: the review's D-10.
NUMBERING: dict[str, tuple[dict[str, str], list[str | None], list[str | None]]] = {
    "numberwithin, and a theorem counter set by hand": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm,amsmath}
\newtheorem{thm}{Theorem}
\numberwithin{thm}{section}
\newtheorem{lem}[thm]{Lemma}
\newtheorem*{mainthm}{Main Theorem}
\begin{document}
\begin{mainthm}The starred main theorem.\end{mainthm}
\section{A}
\begin{thm}One.\end{thm}
\setcounter{thm}{6}
\begin{lem}After a setcounter.\end{lem}
\section{B}
\begin{lem}In B.\end{lem}
\end{document}
"""
        },
        ["1", "2"],
        [None, "1.1", "1.7", "2.1"],
    ),
    "thmtools' numberwithin and sibling": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm,thmtools}
\declaretheorem[numberwithin=section]{theorem}
\declaretheorem[sibling=theorem]{lemma}
\declaretheorem[name=Claim,numbered=no]{claim}
\begin{document}
\section{T}
\begin{theorem}A thmtools theorem.\end{theorem}
\begin{lemma}A thmtools lemma.\end{lemma}
\begin{claim}An unnumbered claim.\end{claim}
\end{document}
"""
        },
        ["1"],
        ["1.1", "1.2", None],
    ),
    "a number printed roman, and one set upright": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm}
\newtheorem{thm}{Theorem}
\renewcommand{\thethm}{\Roman{thm}}
\newtheorem{lem}{Lemma}
\renewcommand{\thelem}{\textup{\arabic{lem}}}
\begin{document}
\begin{thm}A roman theorem.\end{thm}
\begin{thm}Another.\end{thm}
\begin{lem}A lemma numbered through textup.\end{lem}
\end{document}
"""
        },
        [],
        ["I", "II", "1"],
    ),
    "a reset with the number left plain, and a counter moved on": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm}
\newtheorem{thm}{Theorem}
\newtheorem{rem}{Remark}
\counterwithin*{rem}{section}
\begin{document}
\section{A}
\begin{thm}One.\end{thm}
\begin{rem}A remark.\end{rem}
\section{B}
\begin{rem}Another remark.\end{rem}
\addtocounter{thm}{2}
\begin{thm}Three later.\end{thm}
\end{document}
"""
        },
        ["1", "2"],
        ["1", "1", "1", "4"],
    ),
    "a local style's numbering": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm}
\newtheorem{thm}{Theorem}
\usepackage{numbering}
\begin{document}
\section{A}
\begin{thm}One.\end{thm}
\section{B}
\begin{thm}Two.\end{thm}
\end{document}
""",
            "numbering.sty": "\\RequirePackage{amsmath}\n\\numberwithin{thm}{section}\n",
        },
        ["1", "2"],
        ["1.1", "2.1"],
    ),
    "headings deeper than the class numbers, and a depth set by hand": (
        {
            "main.tex": r"""\documentclass{article}
\usepackage{amsthm}
\newtheorem{thm}{Theorem}[subsection]
\begin{document}
\section{A}
\subsection{B}
\paragraph{Unnumbered.}
\begin{thm}One.\end{thm}
\setcounter{secnumdepth}{1}
\subsection{C}
\begin{thm}Two.\end{thm}
\end{document}
"""
        },
        ["1", "1.1", None, None],
        ["1.1.1", "1.1.2"],
    ),
    "a book's chapters, a section printed through them, and a lettered appendix": (
        {
            "main.tex": r"""\documentclass{book}
\usepackage{amsthm}
\newtheorem{thm}{Theorem}[chapter]
\renewcommand{\thesection}{\thechapter.\Alph{section}}
\begin{document}
\chapter{One}
\section{S}
\begin{thm}In one.\end{thm}
\chapter{Two}
\begin{thm}In two.\end{thm}
\appendix
\chapter{Extra}
\section{E}
\begin{thm}In the appendix.\end{thm}
\end{document}
"""
        },
        ["1", "1.A", "2", "A", "A.A"],
        ["1.1", "2.1", "A.1"],
    ),
}


def _numbering(tmp_path: Path, case: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for name, text in NUMBERING[case][0].items():
        (src / name).write_text(text, encoding="utf-8")
    return src


@pytest.mark.parametrize("case", list(NUMBERING))
def test_loom_reads_the_numbering_a_source_sets_as_tex_prints_it(tmp_path: Path, case: str) -> None:
    _files, sections, items = NUMBERING[case]
    s = survey.read(_numbering(tmp_path, case), "main.tex", TEX)
    assert ([x.emulated for x in s.sections], [i.emulated for i in s.items]) == (sections, items)


def test_loom_follows_only_the_numbering_a_source_writes_literally(tmp_path: Path) -> None:
    """A counter set from a value the source computes or reads stays where loom's reading had it, and a format of anything else has no reading at all, so nothing loom reads can carry a file the source read."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(
        HOSTILE_HEAD
        + "\\newtheorem{lem}{Lemma}\n\\newcounter{v}\n\\renewcommand{\\thethm}{\\input{/etc/hosts}}\n\\begin{document}\n"
        + "\\begin{thm}One.\\end{thm}\n\\setcounter{lem}{\\value{v}}\\addtocounter{lem}{\\v}\n"
        + "\\begin{lem}Two.\\end{lem}\n\\end{document}\n",
        encoding="utf-8",
    )
    s = survey.read(src, "main.tex", TEX)
    assert [i.emulated for i in s.items] == [None, "1"]


def test_a_format_holds_until_its_group_closes(tmp_path: Path) -> None:
    """A result restated in a group, as Slice4D writes it, has no reading of loom's, and the results after it are read again."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(
        HOSTILE_HEAD
        + "\\begin{document}\n\\begin{thm}\\label{thm:a}First.\\end{thm}\n\\begin{thm}Second.\\end{thm}\n"
        + "{\n\\renewcommand{\\thethm}{\\ref{thm:a}}\n\\begin{thm}First again.\\end{thm}\n\\addtocounter{thm}{-1}\n}\n"
        + "\\begin{thm}Third.\\end{thm}\n\\begin{thm}\\renewcommand\\thethm{\\Roman{thm}}Fourth.\\end{thm}\n"
        + "\\begin{thm}Fifth.\\end{thm}\n\\end{document}\n",
        encoding="utf-8",
    )
    s = survey.read(src, "main.tex", TEX)
    assert [i.emulated for i in s.items] == ["1", "2", None, "3", "4", "5"]


@pytest.mark.parametrize(
    "case", ["a style linked to a file outside", "a folder linked outside", "a master that is a link"]
)
def test_a_survey_reads_only_regular_files_inside_its_folder(tmp_path: Path, case: str) -> None:
    """The review's D-12: whatever its caller passes, a survey reads nothing through a link out of the source's folder, so a style's literal setting there moves nothing loom reads."""
    import os

    outside, src = tmp_path / "outside", tmp_path / "src"
    (outside / "sty").mkdir(parents=True)
    src.mkdir()
    for where in (outside / "evil.sty", outside / "sty" / "evil.sty"):
        where.write_text("\\setcounter{section}{7390}\n", encoding="utf-8")
    main = (
        HOSTILE_HEAD
        + "\\usepackage{%s}\n\\begin{document}\n\\section{One}\n\\begin{thm}A theorem.\\end{thm}\n\\end{document}\n"
    )
    if case == "a style linked to a file outside":
        os.symlink(outside / "evil.sty", src / "evil.sty")
        (src / "main.tex").write_text(main % "evil", encoding="utf-8")
    elif case == "a folder linked outside":
        os.symlink(outside / "sty", src / "sty")
        (src / "main.tex").write_text(main % "sty/evil", encoding="utf-8")
    else:
        (outside / "main.tex").write_text(main % "amsmath", encoding="utf-8")
        os.symlink(outside / "main.tex", src / "main.tex")
    s = survey.read(src, "main.tex", TEX)
    if case == "a master that is a link":
        assert (s.state, s.why, s.items) == ("failed", "no-main", [])
    else:
        assert s.state == "reading" and [x.emulated for x in s.sections] == ["1"]


def test_a_number_a_compile_sets_in_a_face_is_read_through_it(tmp_path: Path) -> None:
    s = survey.read(_numbering(tmp_path, "a number printed roman, and one set upright"), "main.tex", TEX)
    said = ["I", "II", r"\textup {1}"]
    done = survey.confirm(s, ["\n".join(rf"\newlabel{{loom-survey-i{k}}}{{{{{n}}}{{1}}}}" for k, n in enumerate(said))])
    assert ([i.number for i in done.items], done.unconfirmed) == (["I", "II", "1"], [])


def test_a_result_s_proofs_and_every_label_are_known_by_whose_text_holds_them(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    lemma, main = s.item("i2"), s.item("thm:main")
    assert lemma is not None and main is not None
    assert [p.file for p in lemma.proofs] == ["main.tex"] and [p.file for p in main.proofs] == ["part2.tex"]
    assert MAIN[lemma.proofs[0].body_start : lemma.proofs[0].body_end].lstrip().startswith(r"\label{pf:bound}")
    seen = {k: (v.kind, v.owner, v.proof, v.result) for k, v in s.labels.items()}
    assert seen == {
        "sec:intro": ("section", None, None, False),
        "def:widget": ("defn", "def:widget", None, True),
        "eq:bound": ("equation", "i2", None, False),
        "pf:bound": ("other", "i2", 0, False),
        "it:first": ("enumi", "i2", 0, False),
        "thm:main": ("theorem", "thm:main", None, True),
        "thm:alias": ("theorem", "thm:main", None, True),
        "claim:star": ("claim", "claim:star", None, True),
        "fig:one": ("figure", None, None, False),
        "eq:outside": ("equation", None, None, False),
        "not:hom": ("notation", "not:hom", None, True),
        "sec:proofs": ("section", None, None, False),
        "thm:app": ("theorem", "thm:app", None, True),
    }


def test_a_source_s_bibliography_is_the_files_it_names_and_holds(tmp_path: Path) -> None:
    src = _source(tmp_path)
    assert survey.read(src, "main.tex", TEX).bibliography == ["refs.bib"]
    (src / "main.bbl").write_text("\\begin{thebibliography}{1}\\end{thebibliography}\n", encoding="utf-8")
    assert survey.read(src, "main.tex", TEX).bbl == "main.bbl"


def test_the_showcase_s_paper_is_surveyed_whole() -> None:
    s = survey.read(ARDEN.parent, ARDEN.name, TEX)
    assert s.state == "reading"
    assert [x.emulated for x in s.sections] == ["1", "2", "3", "4", "5"]
    assert [f"{i.name} {i.emulated}" for i in s.items] == [
        "Definition 1.1",
        "Definition 1.2",
        "Proposition 2.1",
        "Lemma 2.2",
        "Theorem 3.1",
        "Corollary 3.2",
        "Remark 4.1",
        "Remark 4.2",
        "Theorem 5.1",
        "Corollary 5.2",
        "Remark 5.3",
    ]
    assert [len(i.proofs) for i in s.items] == [0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 0]


@pytest.mark.parametrize(
    ("main", "why"),
    [("absent.tex", "no-main"), ("../main.tex", "no-main"), ("part2.tex", "no-document")],
)
def test_a_source_that_cannot_be_read_fails_and_says_why(tmp_path: Path, main: str, why: str) -> None:
    s = survey.read(_source(tmp_path), main, TEX)
    assert (s.state, s.why, s.items) == ("failed", why, [])


def test_nothing_outside_the_source_s_folder_is_read(tmp_path: Path) -> None:
    src = _source(tmp_path)
    (tmp_path / "secret.tex").write_text(
        "\\begin{theorem}\\label{thm:secret}Outside.\\end{theorem}\n", encoding="utf-8"
    )
    (src / "main.tex").write_text(
        MAIN.replace("\\input{part2}", "\\input{part2}\n\\input{../secret}"), encoding="utf-8"
    )
    s = survey.read(src, "main.tex", TEX)
    assert s.item("thm:secret") is None and "thm:secret" not in s.labels


def test_a_survey_is_kept_by_the_source_s_hash_and_read_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, src = tmp_path / "quilt", _source(tmp_path)
    first = survey.survey(root, TEX, src, "main.tex")
    assert (root / LIBRARY_SURVEYS / f"{'ab' * 32}.json").is_file()

    def unread(*_a: object) -> survey.Survey:
        raise AssertionError("read again")

    monkeypatch.setattr(survey, "read", unread)
    assert survey.survey(root, TEX, src, "main.tex") == first
    shutil.rmtree(src)
    assert survey.survey(root, TEX, src, "main.tex") == first


def test_a_kept_survey_of_another_version_is_read_again(tmp_path: Path) -> None:
    root, src = tmp_path / "quilt", _source(tmp_path)
    old = survey.read(src, "main.tex", TEX)
    old.version, old.items = 0, []
    survey.keep(root, old)
    assert survey.kept(root, TEX) is None
    assert len(survey.survey(root, TEX, src, "main.tex").items) == 6


def _bytes(src: Path) -> dict[str, bytes]:
    return {p.relative_to(src).as_posix(): p.read_bytes() for p in sorted(src.rglob("*")) if p.is_file()}


def test_a_marked_copy_marks_each_heading_result_and_proof_and_the_source_is_not_written(tmp_path: Path) -> None:
    src = _source(tmp_path)
    before = _bytes(src)
    s = survey.read(src, "main.tex", TEX)
    root = survey.marked(src, s, tmp_path / "copy")
    main = (root / "main.tex").read_text(encoding="utf-8")
    assert main.index(survey.MARKER) < main.index("\\begin{document}")
    assert "\\section{Introduction}\\loomSurveyMark{loom-survey-s0}\\label{sec:intro}" in main
    assert "\\begin{lemma}\\loomSurveyMark{loom-survey-i1}\n" in main
    assert "\\begin{proof}\\loomSurveyMark{loom-survey-p1-0}\\label{pf:bound}" in main
    assert "\\begin{defn}[Widget]\\loomSurveyMark{loom-survey-i0}\\label{def:widget}" in main
    part2 = (root / "part2.tex").read_text(encoding="utf-8")
    assert "\\begin{theorem}[Main]\\loomSurveyMark{loom-survey-i2}" in part2
    assert "\\begin{proof}\\loomSurveyMark{loom-survey-p2-0}" in part2
    assert _bytes(src) == before


#: An .aux for the fixture in which every mark loom adds is there, each saying what the source's counters say: its five headings, six results and two proofs.
WHOLE = [
    r"\newlabel{loom-survey-s0}{{1}{1}}",
    r"\newlabel{loom-survey-s1}{{2}{1}}",
    r"\newlabel{loom-survey-s2}{{2}{1}}",
    r"\newlabel{loom-survey-s3}{{7}{2}}",
    r"\newlabel{loom-survey-s4}{{A}{2}}",
    r"\newlabel{loom-survey-i0}{{1.1}{1}}",
    r"\newlabel{loom-survey-i1}{{1.2}{1}}",
    r"\newlabel{loom-survey-p1-0}{{1}{1}}",
    r"\newlabel{loom-survey-i2}{{2.1}{1}}",
    r"\newlabel{loom-survey-p2-0}{{2.1}{1}}",
    r"\newlabel{loom-survey-i3}{{2.1}{1}}",
    r"\newlabel{loom-survey-i4}{{7.1}{2}}",
    r"\newlabel{loom-survey-i5}{{A.1}{2}}",
    r"\loomSurveySheet{loom-survey-i0}{1}",
    r"\loomSurveySheet{loom-survey-i2}{1}",
    r"\loomSurveySheet{loom-survey-i5}{2}",
    r"\newlabel{eq:bound}{{1}{1}}",
    r"\newlabel{it:first}{{(i)}{1}}",
    r"\newlabel{claim:star}{{2.1}{1}}",
    r"\newlabel{fig:one}{{1}{2}}",
    r"\newlabel{def:widget}{{1.1}{1}}",
]


def _aux(*, without: str = "", said: dict[str, str] | None = None) -> list[str]:
    """`WHOLE` with the line of `without` left out and each mark of `said` saying another number."""
    lines = [x for x in WHOLE if not (without and f"{{{without}}}" in x)]
    for mark, number in (said or {}).items():
        lines = [x for x in lines if f"{{{mark}}}{{" not in x] + [rf"\newlabel{{{mark}}}{{{{{number}}}{{1}}}}"]
    return ["\n".join(lines)]


#: The fixture as a stored PDF's text, two pages, as `pdftotext` reads one: what a compile's word is checked against.
PDF = [
    "1. Introduction\nDefinition 1.1 (Widget). A widget is a set.\nLemma 1.2. Every widget is bounded:\n|x| ≤ 1 . (1)\nProof. By (1).\n"
    "2. Bounds\nTheorem 2.3 (Main). Widgets are compact.\nProof. Lemma.\nAcknowledgements\nClaim. Unnumbered.\n",
    "7. Later\nFigure 1. A picture\ny = 2 (2)\nNotation 7.1. We write Hom.\nAppendix A. Proofs\nTheorem A.1. A theorem in the appendix.\n",
]


def test_with_no_stored_pdf_a_number_is_kept_only_where_it_is_loom_s_own_reading(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux())
    assert (done.state, done.why, done.unseen, done.unconfirmed) == ("ready", None, [], []) and s.state == "reading"
    assert [(i.number, i.page) for i in done.items] == [
        ("1.1", None),
        ("1.2", None),
        ("2.1", None),
        (None, None),
        ("7.1", None),
        ("A.1", None),
    ], "no page without the stored PDF's text"
    assert [x.number for x in done.sections] == ["1", "2", None, "7", "A"]
    labels = {k: v.number for k, v in done.labels.items()}
    assert (labels["def:widget"], labels["thm:alias"], labels["sec:proofs"]) == ("1.1", "2.1", "A")
    assert (labels["eq:bound"], labels["it:first"], labels["fig:one"], labels["claim:star"]) == (None, None, None, None)
    other = survey.confirm(s, _aux(said={"loom-survey-i4": "7.2", "loom-survey-s1": "3"}))
    assert (other.item("not:hom").number, other.sections[1].number) == (None, None)  # type: ignore[union-attr]
    assert other.unconfirmed == ["s2", "not:hom"], "named, so the item waits where the person looks"


@pytest.mark.parametrize(
    "said", [r"\input{/etc/hosts}", "ghp-AAAA1111BBBB", "hunter2", "AbCdEfGhIjKlMnOp", "root:x:0:0:root:/root", ""]
)
def test_a_number_a_compile_says_is_kept_on_no_word_of_its_own(tmp_path: Path, said: str) -> None:
    """The review's D-1: a source nobody at loom wrote can read the person's files into what it prints, sixteen characters at a time, so what the compile says is only a hint."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    for pages, kept in ((None, None), (survey.Pages(PDF), "1.2")):
        done = survey.confirm(s, _aux(said={"loom-survey-i1": said, "loom-survey-i2": said}), pages)
        lemma = done.item("i2")
        assert done.state == "ready" and lemma is not None and lemma.number == kept, (
            "loom's own reading, where the PDF shows it"
        )
        assert said == "" or said not in json.dumps(done.to_json()), "no byte of it in what is kept"


def test_a_stored_pdf_governs_the_number_heading_a_statement_and_gives_its_page(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(said={"loom-survey-i2": "2.3"}), survey.Pages(PDF))
    main = done.item("thm:main")
    assert main is not None and (main.number, main.page) == ("2.3", 1), "the number the PDF heads its words with"
    assert [(i.item, i.number, i.page) for i in done.items if i.item != "thm:main"] == [
        ("def:widget", "1.1", 1),
        ("i2", "1.2", 1),
        ("claim:star", None, None),
        ("not:hom", None, None),
        ("thm:app", "A.1", 2),
    ], "with a stored PDF loom's reading never stands alone: a statement whose words are too few to find has no number"
    assert [(x.number, x.page) for x in done.sections] == [("1", 1), ("2", 1), (None, 1), (None, None), ("A", 2)]
    assert done.unconfirmed == ["s4", "not:hom"]
    assert (done.labels["eq:bound"].number, done.labels["eq:bound"].page) == ("1", 1), (
        "shown in parentheses on its result's page"
    )
    assert done.labels["it:first"].number is None, "not shown so"
    wrong = survey.confirm(s, _aux(said={"loom-survey-i2": "9.9"}), survey.Pages(PDF))
    assert wrong.item("thm:main").number == "2.3", "whatever the compile says"  # type: ignore[union-attr]


#: The fixture as its published version prints it, numbered otherwise: sections 11, 12 and 17 where the source has 1, 2 and 7.
RENUMBERED = [
    "11. Introduction\nDefinition 11.1 (Widget). A widget is a set.\nLemma 11.2. Every widget is bounded:\n|x| ≤ 1 . (11.1)\n"
    "Proof. By (11.1).\n12. Bounds\nTheorem 12.1 (Main). Widgets are compact.\nProof. Lemma.\nAcknowledgements\nClaim. Unnumbered.\n",
    "17. Later\nFigure 1. A picture\ny = 2 (17.1)\nNotation 17.1. We write Hom.\nAppendix A. Proofs\nTheorem A.1. A theorem in the appendix.\n",
]


def test_a_stored_pdf_that_numbers_otherwise_governs_and_a_longer_number_is_never_read_short(tmp_path: Path) -> None:
    """The review's D-13: a published version filed beside an arXiv source prints its own numbers, and those are the ones kept, the compile and loom's reading notwithstanding."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(), survey.Pages(RENUMBERED))
    assert [(i.item, i.number, i.page) for i in done.items] == [
        ("def:widget", "11.1", 1),
        ("i2", "11.2", 1),
        ("thm:main", "12.1", 1),
        ("claim:star", None, None),
        ("not:hom", None, None),
        ("thm:app", "A.1", 2),
    ]
    assert [x.number for x in done.sections] == ["11", "12", None, None, "A"], "12 is never read as the 2 it ends in"
    labels = {k: v.number for k, v in done.labels.items()}
    assert (labels["def:widget"], labels["thm:alias"], labels["sec:intro"]) == ("11.1", "12.1", "11")
    assert labels["eq:bound"] is None, "the PDF numbers its result otherwise, so the compile's (1) is not its number"
    assert done.unconfirmed == ["s4", "not:hom"]
    contents = "Contents\n1 Introduction\n9 Bounds\n"
    honest = survey.confirm(s, _aux(), survey.Pages([contents + PDF[0], PDF[1]]))
    assert honest.sections[1].number == "2", "of the places its words stand, the one headed as loom reads it"
    other = survey.confirm(s, _aux(), survey.Pages([contents + RENUMBERED[0], RENUMBERED[1]]))
    assert other.sections[1].number is None and "s2" in other.unconfirmed, "two places, two numbers, none loom's: none"
    unnumbered = [RENUMBERED[0].replace("Lemma 11.2.", "Lemma."), RENUMBERED[1]]
    bare = survey.confirm(s, _aux(), survey.Pages(unnumbered))
    assert bare.item("i2").number is None and "i2" in bare.unconfirmed, "shown under no number loom can read"  # type: ignore[union-attr]


def test_a_restated_result_is_numbered_as_its_stored_pdf_prints_it_and_without_one_not_at_all(tmp_path: Path) -> None:
    """A paper that restates a theorem prints its first statement's number through `\\ref`, which the .aux holds as the reference; loom's reading of the restatement is another number, so only the stored PDF numbers it."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    restated = _aux(said={"loom-survey-i1": r"\ref {def:widget}"})
    alone = survey.confirm(s, restated)
    assert alone.item("i2").number is None and "i2" in alone.unconfirmed  # type: ignore[union-attr]
    shown = [PDF[0].replace("Lemma 1.2.", "Lemma 1.1."), PDF[1]]
    for said in (r"\ref {def:widget}", r"\ref{loom-nowhere}"):
        held = survey.confirm(s, _aux(said={"loom-survey-i1": said}), survey.Pages(shown))
        assert held.item("i2").number == "1.1" and "i2" not in held.unconfirmed  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("without", "unseen"),
    [("loom-survey-i1", ["i2"]), ("loom-survey-p1-0", ["i2:proof0"]), ("loom-survey-s1", ["s2"])],
)
def test_a_mark_the_compile_never_reached_fails_the_survey_and_is_named_by_its_id(
    tmp_path: Path, without: str, unseen: list[str]
) -> None:
    """The review's D-4: what fell short is named as the survey names it, never by the mark's own count from 0."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(without=without))
    assert (done.state, done.why, done.unseen) == ("failed", "incomplete", unseen)
    assert all(i.number is None and i.page is None for i in done.items)


def test_a_source_s_compile_starts_no_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: dict[str, object] = {}

    def compile_tex(*args: object, **kwargs: object) -> object:
        asked.update(kwargs)
        raise RuntimeError("stop here")

    monkeypatch.setattr(survey, "compile_tex", compile_tex)
    src = _source(tmp_path)
    with pytest.raises(RuntimeError):
        survey.compile_marks(src, survey.read(src, "main.tex", TEX))
    assert asked["foreign"] is True


def test_a_quilt_compiles_one_source_at_a_time_and_keeps_what_it_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, src = tmp_path / "quilt", _source(tmp_path)
    spans: list[tuple[float, float]] = []

    def slow(_src: Path, s: survey.Survey, _pdf: Path | None = None) -> survey.Survey:
        start = time.monotonic()
        time.sleep(0.3)
        spans.append((start, time.monotonic()))
        return survey.confirm(s, _aux())

    monkeypatch.setattr(survey, "compile_marks", slow)
    other = "sha256:" + "cd" * 32
    threads = [threading.Thread(target=survey.complete, args=(root, t, src, "main.tex")) for t in (TEX, other)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    (a0, a1), (b0, b1) = sorted(spans)
    assert a1 <= b0
    assert survey.complete(root, TEX, src, "main.tex").state == "ready" and len(spans) == 2


def _stored(tmp_path: Path, src: Path, name: str = "built") -> Path:
    """`src` compiled as it stands, by this test and not the survey: the stand-in for a work's stored PDF."""
    from loom.tex.runner import compile_tex

    copy = tmp_path / name
    shutil.copytree(src, copy)
    res = compile_tex(copy, "main.tex", tmp_path / f"{name}-out")
    assert res.pdf is not None, res.errors
    return res.pdf


@pytest.mark.tex
def test_a_compile_numbers_each_result_as_confirmed_and_pages_it_only_from_the_stored_pdf(tmp_path: Path) -> None:
    src = _source(tmp_path)
    before = _bytes(src)
    alone = survey.complete(tmp_path / "quilt", TEX, src, "main.tex")
    assert (alone.state, alone.why, alone.unconfirmed) == ("ready", None, [])
    numbers = [
        ("def:widget", "1.1"),
        ("i2", "1.2"),
        ("thm:main", "2.1"),
        ("claim:star", None),
        ("not:hom", "7.1"),
        ("thm:app", "A.1"),
    ]
    assert [(i.item, i.number) for i in alone.items] == numbers
    assert all(i.page is None for i in alone.items) and [x.number for x in alone.sections] == ["1", "2", None, "7", "A"]
    pdf = _stored(tmp_path, src)
    held = survey.complete(tmp_path / "quilt", TEX, src, "main.tex", pdf="sha256:" + "ef" * 32, pdf_path=pdf)
    assert [(i.item, i.number) for i in held.items] == [
        (item, None if item == "not:hom" else number) for item, number in numbers
    ], "the notation opens with too few words to find, and with a stored PDF loom's reading never stands alone"
    assert [i.page for i in held.items] == [1, 1, 1, None, None, 2], "found on the stored PDF's own pages"
    assert held.labels["eq:bound"].number == "1" and held.labels["sec:proofs"].number == "A"
    assert _bytes(src) == before and survey.kept(tmp_path / "quilt", TEX) == alone
    assert survey.kept(tmp_path / "quilt", TEX, "sha256:" + "ef" * 32) == held


@pytest.mark.tex
def test_a_source_that_does_not_compile_fails_and_numbers_nothing(tmp_path: Path) -> None:
    src = _source(tmp_path)
    (src / "main.tex").write_text(MAIN.replace("{amsart}", "{loom-no-such-class}"), encoding="utf-8")
    done = survey.complete(tmp_path / "quilt", TEX, src, "main.tex")
    assert (done.state, done.why) == ("failed", "compile")
    assert all(i.number is None and i.page is None for i in done.items)


@pytest.mark.tex
def test_a_source_whose_figure_is_missing_still_reads_ready(tmp_path: Path) -> None:
    src = _source(tmp_path)
    text = MAIN.replace("\\begin{document}", "\\usepackage{graphicx}\n\\begin{document}", 1)
    text = text.replace("\\begin{figure}", "\\begin{figure}\\includegraphics{loom-no-such-figure}", 1)
    (src / "main.tex").write_text(text, encoding="utf-8")
    done = survey.complete(tmp_path / "quilt", TEX, src, "main.tex")
    assert (done.state, done.unseen) == ("ready", [])
    assert [i.number for i in done.items] == ["1.1", "1.2", "2.1", None, "7.1", "A.1"]


@pytest.mark.tex
def test_a_foreign_compile_has_shell_escape_off_and_a_person_s_build_keeps_it_restricted(tmp_path: Path) -> None:
    from loom.tex.runner import compile_tex

    (tmp_path / "a.tex").write_text(
        "\\documentclass{article}\\begin{document}\\typeout{loom-escape=\\the\\pdfshellescape}x\\end{document}\n",
        encoding="utf-8",
    )
    for foreign, status in ((True, "0"), (False, "2")):
        res = compile_tex(tmp_path, "a.tex", tmp_path / f"out-{foreign}", foreign=foreign)
        assert res.log is not None and f"loom-escape={status}" in res.log.read_text(encoding="utf-8", errors="replace")


@pytest.mark.tex
@pytest.mark.parametrize("case", list(NUMBERING))
def test_with_no_stored_pdf_an_honest_source_keeps_the_numbers_it_sets_for_itself(tmp_path: Path, case: str) -> None:
    """The review's D-10: where loom reads a source's numbering as TeX prints it, the compile agrees and every number is kept, with no PDF to confirm it."""
    _files, sections, items = NUMBERING[case]
    done = survey.complete(tmp_path / "quilt", TEX, _numbering(tmp_path, case), "main.tex")
    assert (done.state, done.unconfirmed) == ("ready", [])
    assert ([x.number for x in done.sections], [i.number for i in done.items]) == (sections, items)


#: The reviewer's sources that read files of the person's from outside the source's folder into printed numbers (`review-refs/scripts/survey_hostile.py`).
HOSTILE_HEAD = "\\documentclass{article}\n\\usepackage{amsthm}\n\\newtheorem{thm}{Theorem}\n"


def _hostile(outside: Path) -> dict[str, str]:
    lines = outside / "lines.txt"
    whole = outside / "secret.txt"
    return {
        "a file whole": HOSTILE_HEAD
        + "\\renewcommand{\\thethm}{\\input{"
        + str(whole)
        + "}}\n\\begin{document}\n\\begin{thm}One is the first of them all.\\end{thm}\n\\end{document}\n",
        "a line at a time": HOSTILE_HEAD
        + "\\newread\\leak\n\\openin\\leak="
        + str(lines)
        + "\n\\newcommand{\\nextline}{\\read\\leak to\\got \\expandafter\\stripnl\\got\\relax}\n"
        + "\\def\\stripnl#1 \\relax{\\gdef\\lineval{#1}}\n\\renewcommand{\\thethm}{\\lineval}\n\\begin{document}\n"
        + "".join(
            f"\\nextline\\begin{{thm}}Statement number {w} of four.\\end{{thm}}\n"
            for w in ("one", "two", "three", "four")
        )
        + "\\end{document}\n",
    }


@pytest.mark.tex
@pytest.mark.parametrize("case", ["a file whole", "a line at a time"])
def test_no_byte_of_a_file_a_source_reads_from_outside_is_kept(tmp_path: Path, case: str) -> None:
    """The review's D-1, by the reviewer's own sources, with and without a stored PDF: whatever the compile printed from the person's files, nothing of it is anywhere under `.loom/`."""
    outside = tmp_path / "outside"
    outside.mkdir()
    secrets = ["Kx7Q2p9Z", "ghp-AAAA1111BBBB", "2222CCCC3333DDDD", "hunter2", "my.host.local"]
    (outside / "secret.txt").write_text(secrets[0] + "\n", encoding="utf-8")
    (outside / "lines.txt").write_text("\n".join(secrets[1:]) + "\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(_hostile(outside)[case], encoding="utf-8")
    quilt = tmp_path / "quilt"
    # the paper as built elsewhere, on arXiv's machine say, where the files it reads are not the person's
    clean = tmp_path / "clean"
    clean.mkdir()
    statements = "".join(
        f"\\begin{{thm}}{line}\\end{{thm}}\n"
        for line in re.findall(r"\\begin\{thm\}(.*?)\\end\{thm\}", _hostile(outside)[case])
    )
    (clean / "main.tex").write_text(
        HOSTILE_HEAD + "\\begin{document}\n" + statements + "\\end{document}\n", encoding="utf-8"
    )
    pdfs = [("sha256:" + "ef" * 32, _stored(tmp_path, clean, "elsewhere"))]
    if case == "a line at a time":
        # and the worst case: a PDF built on this very machine from the same source, which shows what the source read
        pdfs.append(("sha256:" + "fe" * 32, _stored(tmp_path, src, "here")))
    for done in (
        survey.complete(quilt, TEX, src, "main.tex"),
        *(survey.complete(quilt, TEX, src, "main.tex", pdf=digest, pdf_path=path) for digest, path in pdfs),
    ):
        assert done.state in ("ready", "failed"), done
        printed = {str(k + 1) for k in range(len(done.items))} if done.pdf == "sha256:" + "ef" * 32 else set()
        assert all(i.number in (None, i.emulated) or i.number in printed for i in done.items), (
            "loom's own reading, or what the stored PDF from elsewhere prints"
        )
    kept = b"".join(p.read_bytes() for p in quilt.rglob("*") if p.is_file())
    assert kept and not [x for x in secrets if x.encode() in kept]
