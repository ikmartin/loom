"""The survey of a TeX source: what it holds, read once and kept by the source's hash."""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest import mock

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


def _one_file(tmp_path: Path, text: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(text, encoding="utf-8")
    return src


def test_ntheorem_s_standard_results_are_read_each_on_its_own_counter(tmp_path: Path) -> None:
    """The review's D-3: a paper that loads ntheorem with `standard` declares no theorem of its own and still has results."""
    src = _one_file(
        tmp_path,
        "\\documentclass{article}\n\\usepackage[standard,thmmarks]{ntheorem}\n\\begin{document}\n\\section{N}\n"
        "\\begin{Theorem}\\label{t:n}An ntheorem Theorem.\\end{Theorem}\n\\begin{Lemma}An ntheorem Lemma.\\end{Lemma}\n"
        "\\begin{Proof}Its proof.\\end{Proof}\n\\begin{theorem}A second theorem.\\end{theorem}\n\\end{document}\n",
    )
    s = survey.read(src, "main.tex", TEX)
    assert [(i.item, i.name, i.taxon, i.emulated) for i in s.items] == [
        ("t:n", "Theorem", "theorem", "1"),
        ("i2", "Lemma", "lemma", "1"),
        ("i3", "Theorem", "theorem", "1"),
    ], "each of the set on its own counter, as ntheorem.std declares them"
    assert s.why is None


def test_a_paper_whose_results_loom_cannot_read_says_so(tmp_path: Path) -> None:
    """The review's D-3: tcolorbox's theorems are not ones the scanner reads, so the survey says it found none rather than showing an empty paper."""
    src = _one_file(
        tmp_path,
        "\\documentclass{article}\n\\usepackage{tcolorbox}\n\\tcbuselibrary{theorems}\n\\newtcbtheorem{mytheo}{Theorem}{}{th}\n"
        "\\begin{document}\n\\section{Boxes}\n\\begin{mytheo}{A title}{one}Boxed.\\end{mytheo}\n\\end{document}\n",
    )
    s = survey.read(src, "main.tex", TEX)
    assert (s.state, s.why, s.items) == ("reading", "no-results", [])
    done = survey.confirmed(tmp_path / "quilt", TEX, src, "main.tex")
    assert (done.state, done.why) == ("ready", "no-results")


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
    """A result restated in a group, as Slice4D writes it, reads as the result it restates, and the results after it are read again."""
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
    assert [i.emulated for i in s.items] == ["1", "2", "1", "3", "4", "5"]


IRREGULAR = [
    "a style linked to a file outside",
    "a folder linked outside",
    "a master that is a link",
    "a link loop",
    "a dangling link",
    "a hard link to a file outside",
    "a FIFO",
]


def _irregular(tmp_path: Path, case: str) -> Path:
    """A source folder holding one thing that is neither a folder nor a regular file with no other name; nothing here opens a device or the FIFO."""
    import os

    outside, src = tmp_path / "outside", tmp_path / "src"
    (outside / "sty").mkdir(parents=True)
    src.mkdir()
    secret = outside / "evil.sty"
    secret.write_text("\\setcounter{section}{7390}\n", encoding="utf-8")
    (outside / "sty" / "evil.sty").write_text("\\setcounter{section}{7390}\n", encoding="utf-8")
    main = (
        HOSTILE_HEAD
        + "\\usepackage{evil}\n\\begin{document}\n\\section{One}\n\\begin{thm}A theorem.\\end{thm}\n\\end{document}\n"
    )
    if case == "a master that is a link":
        (outside / "main.tex").write_text(main, encoding="utf-8")
        os.symlink(outside / "main.tex", src / "main.tex")
        return src
    (src / "main.tex").write_text(main, encoding="utf-8")
    if case == "a style linked to a file outside":
        os.symlink(secret, src / "evil.sty")
    elif case == "a folder linked outside":
        os.symlink(outside / "sty", src / "sty")
    elif case == "a link loop":
        os.symlink(src / "loop-b", src / "loop-a")
        os.symlink(src / "loop-a", src / "loop-b")
    elif case == "a dangling link":
        os.symlink(tmp_path / "nowhere.sty", src / "evil.sty")
    elif case == "a hard link to a file outside":
        os.link(secret, src / "evil.sty")
    else:
        os.mkfifo(src / "evil.sty")
    return src


@pytest.mark.parametrize("case", IRREGULAR)
def test_a_source_folder_holding_anything_but_plain_files_is_refused_before_anything_reads_it(
    tmp_path: Path, case: str
) -> None:
    """The review's D-12: a link, a file with another name elsewhere, or a FIFO refuses the whole source by `lstat` alone, so nothing is followed or opened and a loop or a dangling link fails rather than raises."""
    s = survey.read(_irregular(tmp_path, case), "main.tex", TEX)
    assert (s.state, s.why, s.items, s.sections) == ("failed", "not-regular", [], [])


@pytest.mark.parametrize("case", IRREGULAR[3:])
def test_a_staged_copy_of_a_source_follows_no_link_and_opens_nothing_but_plain_files(tmp_path: Path, case: str) -> None:
    from loom.tex.runner import stage_sources

    root = stage_sources(_irregular(tmp_path, case), tmp_path / "staged", regular_only=True)
    assert sorted(p.name for p in root.iterdir()) == ["main.tex"]


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


#: The fixture as a stored PDF's text, two pages, as `pdftotext` reads one, a display's number alone on its line: what a compile's word is checked against.
PDF = [
    "1. Introduction\nDefinition 1.1 (Widget). A widget is a set.\nLemma 1.2. Every widget is bounded:\n|x| ≤ 1 .\n(1)\nProof. By (1).\n"
    "2. Bounds\nTheorem 2.3 (Main). Widgets are compact.\nProof. Lemma.\nAcknowledgements\nClaim. Unnumbered.\n",
    "7. Later\nFigure 1. A picture\ny = 2\n(2)\nNotation 7.1. We write Hom.\nAppendix A. Proofs\nTheorem A.1. A theorem in the appendix.\n",
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
    assert labels["eq:bound"] == "1", "a display's number, as loom reads it and the compile agrees"
    assert (labels["it:first"], labels["fig:one"], labels["claim:star"]) == (None, None, None)
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


def test_a_stored_pdf_numbers_each_heading_and_result_at_the_start_of_its_own_line(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(said={"loom-survey-i2": "2.3"}), survey.Pages(PDF))
    assert [(i.item, i.number, i.page) for i in done.items] == [
        ("def:widget", "1.1", 1),
        ("i2", "1.2", 1),
        ("thm:main", "2.3", 1),
        ("claim:star", None, 1),
        ("not:hom", "7.1", 2),
        ("thm:app", "A.1", 2),
    ], "the number the PDF prints, a notation of too few words among them"
    assert [(x.number, x.page) for x in done.sections] == [("1", 1), ("2", 1), (None, None), ("7", 2), ("A", 2)]
    assert done.unconfirmed == [] and done.compiled
    assert (done.labels["eq:bound"].number, done.labels["eq:bound"].page) == ("1", 1), (
        "shown in parentheses on its result's page"
    )
    assert done.labels["it:first"].number is None, "not shown so"
    wrong = survey.confirm(s, _aux(said={"loom-survey-i2": "9.9"}), survey.Pages(PDF))
    assert wrong.item("thm:main").number == "2.3", "whatever the compile says"  # type: ignore[union-attr]
    assert survey.place(s, survey.Pages(PDF)) == {
        **{x.section: (x.number, x.page) for x in done.sections if x.number},
        **{i.item: (i.number, i.page) for i in done.items if i.page},
    }, "and with no compile at all; the unnumbered claim by its page alone"


#: The fixture as its published version prints it, numbered otherwise: sections 11, 12 and 17 where the source has 1, 2 and 7.
RENUMBERED = [
    "11. Introduction\nDefinition 11.1 (Widget). A widget is a set.\nLemma 11.2. Every widget is bounded:\n|x| ≤ 1 .\n(11.1)\n"
    "Proof. By (11.1).\n12. Bounds\nTheorem 12.1 (Main). Widgets are compact.\nProof. Lemma.\nAcknowledgements\nClaim. Unnumbered.\n",
    "17. Later\nFigure 1. A picture\ny = 2\n(17.1)\nNotation 17.1. We write Hom.\nAppendix A. Proofs\nTheorem A.1. A theorem in the appendix.\n",
]


def test_a_stored_pdf_that_numbers_otherwise_governs_and_a_longer_number_is_never_read_short(tmp_path: Path) -> None:
    """The review's D-13: a published version filed beside an arXiv source prints its own numbers, and those are the ones kept, the compile and loom's reading notwithstanding."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(), survey.Pages(RENUMBERED))
    assert [(i.item, i.number, i.page) for i in done.items] == [
        ("def:widget", "11.1", 1),
        ("i2", "11.2", 1),
        ("thm:main", "12.1", 1),
        ("claim:star", None, 1),
        ("not:hom", "17.1", 2),
        ("thm:app", "A.1", 2),
    ], (
        "a notation of too few words to witness it is found by its place between two results found by theirs, the PDF's own number read there"
    )
    assert [x.number for x in done.sections] == ["11", "12", None, "17", "A"], "12 is never read as the 2 it ends in"
    labels = {k: v.number for k, v in done.labels.items()}
    assert (labels["def:widget"], labels["thm:alias"], labels["sec:intro"]) == ("11.1", "12.1", "11")
    assert labels["eq:bound"] is None, (
        "the PDF numbers the display (11.1), so neither loom's (1) nor the compile's is its number"
    )
    assert done.unconfirmed == []
    unnumbered = [RENUMBERED[0].replace("Lemma 11.2.", "Lemma."), RENUMBERED[1]]
    bare = survey.confirm(s, _aux(), survey.Pages(unnumbered))
    assert bare.item("i2").number is None and "i2" in bare.unconfirmed, "shown under no number loom can read"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "contents",
    ["Contents\n1 Introduction\n2 Bounds\n7 Later\n", "Contents\n1. Introduction . . . 2\n2. Bounds . . . 2\n"],
)
def test_a_contents_page_is_never_where_a_heading_is_read(tmp_path: Path, contents: str) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    got = survey.place(s, survey.Pages([contents, *PDF]))
    assert (got["s1"], got["s2"]) == (("1", 2), ("2", 2)), "on the page the heading stands, not the contents'"


#: A line ending a paragraph, then a mark the PDF prints unnumbered: what the review's D-15 found taken as its number.
BEFORE = ["as in 2019.", "on X.", "and Y.", "in MCMXC.", "as DC.", "the group G.", "as in Theorem 3."]


@pytest.mark.parametrize("before", BEFORE)
def test_a_token_before_a_mark_is_never_read_as_its_number(tmp_path: Path, before: str) -> None:
    """The review's D-15: a heading and a lemma the PDF prints with no number keep none, whatever ends the line before them, alone on its own line or not."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    for tail in (f"By (1), {before}\n", f"By (1),\n{before.removesuffix('.').split()[-1]}\n"):
        page = (
            PDF[0]
            .replace("Proof. By (1).\n", tail)
            .replace("2. Bounds", "Bounds")
            .replace("Lemma 1.2. Every", f"{tail}Lemma. Every")
        )
        got = survey.place(s, survey.Pages([page, PDF[1]]))
        assert "s2" not in got and got.get("i2", (None, None))[0] is None, (tail, got)
        assert got["thm:main"] == ("2.3", 1), "the marks after are read as before"


def test_a_heading_is_read_as_it_is_printed_with_its_number_first_and_never_short(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    swapped = survey.place(s, survey.Pages([PDF[0].replace("Lemma 1.2. Every", "1.2 Lemma. Every"), PDF[1]]))
    assert swapped["i2"] == ("1.2", 1), "the number then the name"
    # a line of prose that opens with the name and a longer number, the lemma's words just after: read as nothing, never as its first part
    prose = PDF[0].replace("Lemma 1.2. Every widget", "Lemma 1.7 also shows the rest.\nEvery widget")
    assert "i2" not in survey.place(s, survey.Pages([prose, PDF[1]]))


def test_with_no_stored_pdf_the_unasked_path_confirms_nothing_and_names_every_numbered_mark(tmp_path: Path) -> None:
    done = survey.confirmed(tmp_path / "quilt", TEX, _source(tmp_path), "main.tex")
    assert (done.state, done.why, done.compiled) == ("ready", "no-pdf", False)
    assert done.unconfirmed == ["s1", "s2", "s4", "s5", "def:widget", "i2", "thm:main", "not:hom", "thm:app"]
    assert all(x.number is None and x.page is None for x in [*done.sections, *done.items])
    assert [i.emulated for i in done.items] == ["1.1", "1.2", "2.1", None, "7.1", "A.1"], (
        "the outline is loom's reading"
    )


@pytest.mark.poppler
@pytest.mark.parametrize("work", ["arden-cycle-spaces", "arden-cycle-spaces-v2", "bellamy-median-orders"])
def test_each_fixture_work_is_numbered_whole_from_its_own_pdf_with_no_compile(tmp_path: Path, work: str) -> None:
    """The route on the showcase's works and the PDFs committed beside them: every numbered heading and result is found, as loom reads it."""
    src = tmp_path / "src"
    src.mkdir()
    shutil.copy(ARDEN.with_name(f"{work}.tex"), src / "main.tex")
    done = survey.confirmed(
        tmp_path / "quilt", TEX, src, "main.tex", pdf="sha256:" + "ef" * 32, pdf_path=ARDEN.with_name(f"{work}.pdf")
    )
    numbered = [(x.emulated, x.number) for x in done.sections if x.emulated] + [
        (i.emulated, i.number) for i in done.items if i.numbered
    ]
    assert (done.state, done.unconfirmed, done.compiled) == ("ready", [], False), done.why
    assert numbered and all(read == printed for read, printed in numbered)


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
def test_a_mark_the_compile_never_reached_fails_only_itself_and_is_named_by_its_id(
    tmp_path: Path, without: str, unseen: list[str]
) -> None:
    """The review's D-4 and D-5: what fell short is named as the survey names it, never by the mark's own count from 0, and it alone has no number, the paper's other results keeping theirs."""
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, _aux(without=without))
    assert (done.state, done.why, done.unseen) == ("ready", None, unseen)
    if without == "loom-survey-i1":
        assert done.item("i2").number is None and done.unconfirmed == [], "it prints nothing to confirm"  # type: ignore[union-attr]
    assert done.item("thm:main").number == "2.1" and done.item("not:hom").number == "7.1"  # type: ignore[union-attr]


def test_a_compile_that_reached_no_mark_fails_the_survey(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    done = survey.confirm(s, ["\\relax"])
    assert (done.state, done.why, len(done.unseen)) == ("failed", "incomplete", 13)


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

    def slow(_src: Path, s: survey.Survey, _pdf: Path | None = None, **_kw: object) -> survey.Survey:
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


def _stored(tmp_path: Path, src: Path, name: str = "built", *, fenced: bool = True) -> Path:
    """`src` compiled as it stands, by this test and not the survey: the stand-in for a work's stored PDF.

    `fenced` False builds it as the person would outside loom, with the fence off (`loom.fence.OFF`), so a source that reads the machine's files prints them.
    """
    from loom import fence
    from loom.tex.runner import compile_tex

    copy = tmp_path / name
    shutil.copytree(src, copy)
    with mock.patch.dict(os.environ, {} if fenced else {fence.OFF: "off"}):
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
    unasked = survey.confirmed(tmp_path / "quilt", TEX, src, "main.tex", pdf="sha256:" + "ef" * 32, pdf_path=pdf)
    assert [(i.item, i.number) for i in unasked.items] == numbers and not unasked.compiled
    held = survey.complete(tmp_path / "quilt", TEX, src, "main.tex", pdf="sha256:" + "ef" * 32, pdf_path=pdf)
    assert held.compiled, "the person's own act compiles, whatever the unasked path kept"
    assert [(i.item, i.number) for i in held.items] == numbers
    assert [i.page for i in held.items] == [1, 1, 1, 1, 2, 2], (
        "found on the stored PDF's own pages, the unnumbered claim's too"
    )
    assert held.labels["eq:bound"].number == "1" and held.labels["sec:proofs"].number == "A"
    assert _bytes(src) == before and survey.kept(tmp_path / "quilt", TEX) == alone
    assert survey.kept(tmp_path / "quilt", TEX, "sha256:" + "ef" * 32) == held


@pytest.mark.tex
def test_a_book_s_chapters_and_its_appendix_are_read_from_its_pdf(tmp_path: Path) -> None:
    """A book prints `Chapter 1` and `Appendix A` on a line of their own, the title under them: the route reads them there, with no compile."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.tex").write_text(
        "\\documentclass{book}\n\\usepackage{amsthm}\n\\newtheorem{thm}{Theorem}[chapter]\n\\begin{document}\n"
        "\\chapter{Gadgets and towers}\nSome words about gadgets.\n\\section{First steps}\n"
        "\\begin{thm}Every gadget is a tower.\\end{thm}\n\\chapter{Widgets}\n\\begin{thm}Every widget is bounded.\\end{thm}\n"
        "\\appendix\n\\chapter{Proofs}\n\\begin{thm}A theorem in the appendix.\\end{thm}\n\\end{document}\n",
        encoding="utf-8",
    )
    pdf = _stored(tmp_path, src)
    done = survey.confirmed(tmp_path / "quilt", TEX, src, "main.tex", pdf="sha256:" + "ef" * 32, pdf_path=pdf)
    assert [(x.number, x.page) for x in done.sections] == [("1", 1), ("1.1", 1), ("2", 3), ("A", 5)]
    assert [(i.number, i.page) for i in done.items] == [("1.1", 1), ("2.1", 3), ("A.1", 5)]
    assert (done.unconfirmed, done.compiled) == ([], False)


#: A source whose compile never ends, spending CPU all the while.
NEVER_ENDS = "\\documentclass{article}\n\\begin{document}\nSpinning.\n\\loop\\iftrue\\repeat\n\\end{document}\n"


def _tex_under(marker: str) -> list[str]:
    """The command lines of TeX's programs running in a folder whose path holds `marker`."""
    import subprocess

    listed = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True, check=False).stdout
    return [line for line in listed.splitlines() if marker in line and ("tex" in line or "latexmk" in line)]


def _waited(until: Callable[[], bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if until():
            return True
        time.sleep(0.2)
    return until()


def _surveying(tmp_path: Path, script: str) -> tuple[Any, str, Path]:
    """A process surveying `NEVER_ENDS` by `script`, once its TeX runs: the process, what names its run folder, the quilt."""
    import subprocess
    import sys

    from loom.paths import SURVEY_RUN

    src, quilt = tmp_path / "spin", tmp_path / "quilt"
    src.mkdir()
    (src / "main.tex").write_text(NEVER_ENDS, encoding="utf-8")
    child = subprocess.Popen([sys.executable, "-c", script, str(quilt), str(src)])
    marker = f"{tmp_path.name}/quilt/{SURVEY_RUN}"
    assert _waited(lambda: bool(_tex_under(marker)), 60), "the survey's TeX never started"
    return child, marker, quilt


@pytest.mark.tex
def test_a_survey_killed_part_way_leaves_no_tex_past_its_cap_and_no_folder_past_the_next(tmp_path: Path) -> None:
    """The review's D-2: a foreign compile's programs are capped in CPU, so killing loom leaves nothing running for long; and the next compile empties the folder it ran in."""
    from loom.paths import SURVEY_RUN

    child, marker, quilt = _surveying(
        tmp_path,
        "import sys; from pathlib import Path; from loom.tex import runner; runner.FOREIGN_CPU = 2; "
        "from loom.library import survey; survey.complete(Path(sys.argv[1]), 'sha256:' + 'ab' * 32, Path(sys.argv[2]), 'main.tex')",
    )
    child.kill()
    child.wait()
    assert _waited(lambda: not _tex_under(marker), 30), _tex_under(marker)
    assert (quilt / SURVEY_RUN).is_dir(), "left by the kill"
    done = survey.complete(quilt, TEX, _source(tmp_path), "main.tex")
    assert done.state == "ready" and not (quilt / SURVEY_RUN).exists()


@pytest.mark.tex
def test_a_loom_that_exits_ends_the_foreign_compile_it_started(tmp_path: Path) -> None:
    child, marker, _quilt = _surveying(
        tmp_path,
        "import sys, threading; from pathlib import Path; from loom.library import survey; "
        "threading.Thread(target=lambda: survey.complete(Path(sys.argv[1]), 'sha256:' + 'ab' * 32, Path(sys.argv[2]), 'main.tex'), daemon=True).start(); "
        "import time; from loom.tex import runner\nwhile not runner._LIVE: time.sleep(0.1)\ntime.sleep(2)\nsys.exit(0)",
    )
    child.wait(timeout=60)
    assert _waited(lambda: not _tex_under(marker), 10), "ended at once, long before its CPU cap"


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
        # and the worst case: a PDF the person built on this very machine from the same source, outside loom's fence, which shows what the source read
        pdfs.append(("sha256:" + "fe" * 32, _stored(tmp_path, src, "here", fenced=False)))
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


#: Displays as a paper numbers them: within sections, a line at a time in `align`, a line left unnumbered, a tag, one inside a result, `subequations`, a starred one.
DISPLAYS = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}[section]
\numberwithin{equation}{section}
\begin{document}
\section{One}
\begin{equation}\label{e:a} a \end{equation}
By (1.2) at a line's end, which is no display.
\begin{align}
b &= c \label{e:b}\\
d &= e \nonumber\\
f &= g \tag{$\star$}\label{e:star}\\
h &= i \label{e:c}
\end{align}
\begin{lemma}\label{l:x}
\begin{equation}\label{e:in} x \end{equation}
\end{lemma}
\begin{subequations}
\begin{align} p \label{e:p} \\ q \end{align}
\end{subequations}
\begin{equation}\label{e:after} r \end{equation}
\begin{equation*} z \end{equation*}
\section{Two}
\begin{equation}\label{e:two} w \end{equation}
\end{document}
"""
#: Its PDF as `pdftotext` reads one: each display's number alone on its line, or opening its formula's first.
DISPLAYED = "1 One\na\n(1.1)\nBy (1.2) at a line's end, which is no display.\nb = c\n(1.2)\nd = e\nf = g\n(⋆)\n(1.3) h = i\nLemma 1.1. x\n(1.4)\np\n(1.5a)\nq\n(1.5b)\nr\n(1.6)\nz\n2 Two\nw\n(2.1)\n"


def _displayed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> survey.Survey:
    monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls([text])))
    root = tmp_path / ("q" + str(len(list(tmp_path.iterdir()))))
    root.mkdir()
    return survey.confirmed(root, TEX, _one_file(root, DISPLAYS), "main.tex", pdf=TEX, pdf_path=root / "x.pdf")


def test_a_display_is_numbered_by_its_counter_a_line_at_a_time(tmp_path: Path) -> None:
    s = survey.read(_one_file(tmp_path, DISPLAYS), "main.tex", TEX)
    shown = {k: v.emulated for k, v in s.labels.items() if v.kind == "equation"}
    assert shown == {
        "e:a": "1.1",
        "e:b": "1.2",
        "e:star": "$\\star$",
        "e:c": "1.3",
        "e:in": "1.4",
        "e:p": None,
        "e:after": "1.6",
        "e:two": "2.1",
    }, "an unnumbered line steps nothing, a tag is its own text, subequations steps once and loom reads none inside"
    assert s.labels["e:in"].owner == "l:x" and s.labels["e:a"].owner is None


def test_a_display_s_number_is_kept_where_the_stored_pdf_shows_it_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    done = _displayed(tmp_path, monkeypatch, DISPLAYED)
    kept = {k: (v.number, v.page) for k, v in done.labels.items() if v.kind == "equation" and v.number}
    assert kept == {
        "e:a": ("1.1", 1),
        "e:b": ("1.2", 1),
        "e:c": ("1.3", 1),
        "e:in": ("1.4", 1),
        "e:after": ("1.6", 1),
        "e:two": ("2.1", 1),
    }, (
        "a number opening its formula's line read too; a tag's text loom cannot compare, and a mention at a line's end never"
    )
    ending = _displayed(tmp_path, monkeypatch, DISPLAYED.replace("(1.3) h = i", "h = i (1.3)"))
    assert {k for k, v in ending.labels.items() if v.kind == "equation" and v.number} == set(kept), (
        "a number ending its formula's line read too"
    )
    lost = _displayed(tmp_path, monkeypatch, DISPLAYED.replace("(1.3) h = i", "h = i"))
    kept = {k for k, v in lost.labels.items() if v.kind == "equation" and v.number}
    assert kept == {"e:two"}, (
        "a number not where loom reads one leaves its window, here the whole of section One, unkept; the next window keeps its own"
    )


def test_a_display_loom_does_not_count_shifts_no_number_onto_its_neighbour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's C-1: an `align` whose last line ends in `\\\\`, a `\\be … \\ee` or a display the PDF's version adds prints a number loom does not count, and the uncounted display's own line shows the number loom expects next; nothing of that window is kept, and no number shifts."""
    extra = DISPLAYED.replace("(1.1)\n", "(1.1)\nv\n(1.2)\n").replace("(1.2)\nd = e", "(1.3)\nd = e")
    extra = extra.replace("(1.3) h = i", "(1.4) h = i")
    done = _displayed(tmp_path, monkeypatch, extra)
    kept = {k: v.number for k, v in done.labels.items() if v.kind == "equation" and v.number}
    assert kept == {"e:two": "2.1"}, "e:b would read the uncounted display's (1.2), e:c its neighbour's"
    fewer = _displayed(tmp_path, monkeypatch, DISPLAYED.replace("a\n(1.1)\n", "a\n"))
    assert {k for k, v in fewer.labels.items() if v.kind == "equation" and v.number} == {"e:two"}, (
        "a display the PDF's version leaves unnumbered: e:b never takes (1.2) as its own when loom counts it 1.2 too"
    )
    listed = DISPLAYED.replace("z\n", "z\n(i) one;\n(1.6) again;\n")
    kept = {k for k, v in _displayed(tmp_path, monkeypatch, listed).labels.items() if v.kind == "equation" and v.number}
    assert "e:after" in kept and "e:a" in kept, (
        "a list's items are no displays: one shaped as no display number is, one repeating a number shown alone"
    )


#: Two lemmas with a corollary between, and a second section: the source the review's variant PDFs print otherwise (D-16 to D-19).
CYCLES = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}[section]
\newtheorem{corollary}[lemma]{Corollary}
\begin{document}
\section{Cycles}
\begin{lemma}\label{l:a}
Every cycle of a finite quiver is a sum of simple cycles.
\end{lemma}
\begin{corollary}\label{c:mid}
The cycle space is spanned by simple cycles alone.
\end{corollary}
\begin{lemma}\label{l:b}
Every simple cycle closes after finitely many arrows.
\end{lemma}
\section{Paths}
Paths are read the same way.
\end{document}
"""
L_A = "Every cycle of a finite quiver is a sum of simple cycles."
MID = "The cycle space is spanned by simple cycles alone."
L_B = "Every simple cycle closes after finitely many arrows."


def _cycles(tmp_path: Path, *pages: str) -> dict[str, tuple[str | None, int]]:
    here = tmp_path / f"v{len(list(tmp_path.iterdir()))}"
    here.mkdir()
    s = survey.read(_one_file(here, CYCLES), "main.tex", TEX)
    return survey.place(s, survey.Pages(list(pages)))


@pytest.mark.parametrize(
    ("variant", "pages", "kept"),
    [
        (
            "as printed",
            [f"1 Cycles\nLemma 1.1. {L_A}\nCorollary 1.2. {MID}\nLemma 1.3. {L_B}\n2 Paths\n"],
            {"l:a": ("1.1", 1), "c:mid": ("1.2", 1), "l:b": ("1.3", 1)},
        ),
        (
            "a lemma inserted before l:a",
            [
                f"1 Cycles\nLemma 1.1. An inserted lemma on gadgets and widgets.\nLemma 1.2. {L_A}\nCorollary 1.3. {MID}\nLemma 1.4. {L_B}\n"
            ],
            {"l:a": ("1.2", 1), "c:mid": ("1.3", 1), "l:b": ("1.4", 1)},
        ),
        (
            "l:a and l:b swapped",
            [f"1 Cycles\nLemma 1.1. {L_B}\nCorollary 1.2. {MID}\nLemma 1.3. {L_A}\n"],
            {"l:a": ("1.3", 1), "c:mid": ("1.2", 1), "l:b": ("1.1", 1)},
        ),
        (
            "l:a missing",
            [f"1 Cycles\nCorollary 1.1. {MID}\nLemma 1.2. {L_B}\n"],
            {"c:mid": ("1.1", 1), "l:b": ("1.2", 1)},
        ),
        (
            "a forward mention opening a line",
            [
                f"1 Cycles\nLemma 1.1. {L_A}\nCorollary 1.2. {MID}\nLemma 1.3. It closes cycles, as we show below.\n",
                f"Lemma 1.3. {L_B}\n",
            ],
            {"l:a": ("1.1", 1), "c:mid": ("1.2", 1), "l:b": ("1.3", 2)},
        ),
        (
            "the published case: an extra lemma just before",
            [
                f"11 Cycles\nLemma 11.1. An extra lemma here too.\nLemma 11.2. {L_A}\nCorollary 11.3. {MID}\nLemma 11.4. {L_B}\n"
            ],
            {"l:a": ("11.2", 1), "c:mid": ("11.3", 1), "l:b": ("11.4", 1)},
        ),
    ],
)
def test_a_result_s_line_is_found_by_its_kind_and_its_own_words_never_by_its_number(
    tmp_path: Path, variant: str, pages: list[str], kept: dict[str, tuple[str, int]]
) -> None:
    """The review's D-16 and D-17: the number is read from the line the words identify, whatever loom reads; a line its words do not follow, before the next result's line, is no result's."""
    got = _cycles(tmp_path, *pages)
    assert {k: v for k, v in got.items() if k in ("l:a", "c:mid", "l:b")} == kept, variant


def test_a_lone_token_before_an_unnumbered_heading_continues_no_sequence(tmp_path: Path) -> None:
    """The review's D-18: a display holding only `X`, alone opening a block, and the title of a heading the PDF prints unnumbered after it."""
    got = _cycles(tmp_path, f"Some words before it.\n\nX\nCycles\nLemma 1.1. {L_A}\n\n2\nPaths\n")
    assert "s1" not in got, (
        "X continues nothing: no heading was found at its level before it, and it is not where one begins"
    )
    assert "s2" not in got and got["l:a"] == ("1.1", 1), "nor does 2, with no heading found before it at its level"
    numbered = _cycles(tmp_path, f"Some words before it.\n\n1\nCycles\nLemma 1.1. {L_A}\n\n2\nPaths\n")
    assert (numbered["s1"], numbered["s2"]) == (("1", 1), ("2", 1)), (
        "where the sequence begins and goes on, each is kept"
    )


def test_article_s_contents_page_holds_no_place(tmp_path: Path) -> None:
    """The review's D-19: `pdftotext` writes article's entries with their page numbers on later lines, and the body's heading as its number alone and its title."""
    contents = "Contents\n1 Cycles\n2 Paths\n2\n2\n"
    got = _cycles(tmp_path, contents, f"1\nCycles\nLemma 1.1. {L_A}\n\n2\nPaths\n")
    assert (got["s1"], got["s2"]) == (("1", 2), ("2", 2)), "on the page the heading stands, never the contents'"


#: Two lemmas whose first 24 letters agree, and a third: the source of the review's D-24 variants.
QUIVERS = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}[section]
\begin{document}
\section{Quivers}
\begin{lemma}\label{l:a}
Every finite quiver with loops has a spanning forest of its arrows.
\end{lemma}
\begin{proof}
Take the arrows one at a time.
\end{proof}
\begin{lemma}\label{l:b}
Every finite quiver with loops has a cycle space of finite rank.
\end{lemma}
\clearpage
\begin{lemma}\label{l:c}
Each arrow outside the forest closes exactly one cycle.
\end{lemma}
\end{document}
"""
Q_A = "Every finite quiver with loops has a spanning forest of its arrows."
Q_B = "Every finite quiver with loops has a cycle space of finite rank."
Q_C = "Each arrow outside the forest closes exactly one cycle."
TREE = "Every finite quiver with loops has a spanning tree of its arrows."


def _quivers(tmp_path: Path, *pages: str) -> dict[str, tuple[str | None, int]]:
    here = tmp_path / f"v{len(list(tmp_path.iterdir()))}"
    here.mkdir()
    s = survey.read(_one_file(here, QUIVERS), "main.tex", TEX)
    return {k: v for k, v in survey.place(s, survey.Pages(list(pages))).items() if k.startswith("l:")}


@pytest.mark.parametrize(
    ("variant", "pages", "kept"),
    [
        (
            "the two sharing their first 24 letters, swapped in print",
            [
                f"1 Quivers\nLemma 1.1. {Q_B}\nLemma 1.2. {Q_A}\nProof. Take the arrows one at a time.\n",
                f"Lemma 1.3. {Q_C}\n",
            ],
            {"l:a": ("1.2", 1), "l:b": ("1.1", 1), "l:c": ("1.3", 2)},
        ),
        (
            "a lemma inserted before l:a sharing its first 24 letters",
            [
                f"1 Quivers\nLemma 1.1. {TREE}\nLemma 1.2. {Q_A}\nProof. Take the arrows one at a time.\nLemma 1.3. {Q_B}\n",
                f"Lemma 1.4. {Q_C}\n",
            ],
            {"l:a": ("1.2", 1), "l:b": ("1.3", 1), "l:c": ("1.4", 2)},
        ),
        (
            "the 24-letter pair inserted before l:a",
            [
                f"1 Quivers\nLemma 1.1. {TREE}\nLemma 1.2. Every finite quiver with loops has a cycle basis.\nLemma 1.3. {Q_A}\nLemma 1.4. {Q_B}\n",
                f"Lemma 1.5. {Q_C}\n",
            ],
            {"l:a": ("1.3", 1), "l:b": ("1.4", 1), "l:c": ("1.5", 2)},
        ),
        (
            "a lemma inserted whose proof repeats l:a's words",
            [
                f"1 Quivers\nLemma 1.1. Spanning forests exist.\nProof. {Q_A}\nLemma 1.2. {Q_A}\nLemma 1.3. {Q_B}\n",
                f"Lemma 1.4. {Q_C}\n",
            ],
            {"l:a": ("1.2", 1), "l:b": ("1.3", 1), "l:c": ("1.4", 2)},
        ),
        (
            "an honest paper restating l:c at a line's start before it",
            [
                f"1 Quivers\nLemma 1.1. {Q_A}\nProof. Take the arrows one at a time.\nLemma 1.2. {Q_B}\nLemma 1.3. Each arrow outside the forest closes exactly one cycle, as shown below.\n",
                f"Lemma 1.3. {Q_C}\n",
            ],
            {"l:a": ("1.1", 1), "l:b": ("1.2", 1)},
        ),
    ],
)
def test_a_result_s_words_begin_its_statement_and_two_lines_witnessing_it_name_it(
    tmp_path: Path, variant: str, pages: list[str], kept: dict[str, tuple[str, int]]
) -> None:
    """The review's D-24, ruled: the words begin the statement, on the heading's line or the next, compared whole; where two lines witness one result, neither is taken and it is named."""
    assert _quivers(tmp_path, *pages) == kept, variant


def test_each_number_says_whether_its_words_found_it_or_its_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's D-25, ruled: the place rule cannot see two formula-only results swapped, so each kept number says how it was found, which digest writes into the node's header (`found`)."""
    text = CYCLES.replace(MID, "$\\dim Z = n - 1$.")
    page = f"1 Cycles\nLemma 1.1. {L_A}\nCorollary 1.2. dim Z = n − 1.\nLemma 1.3. {L_B}\n"
    monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls([page])))
    root = tmp_path / "q"
    root.mkdir()
    done = survey.confirmed(root, TEX, _one_file(root, text), "main.tex", pdf=TEX, pdf_path=root / "x.pdf")
    assert [(i.item, i.number, i.found) for i in done.items] == [
        ("l:a", "1.1", "words"),
        ("c:mid", "1.2", "place"),
        ("l:b", "1.3", "words"),
    ]
    assert survey.Survey.from_json(done.to_json()).item("c:mid").found == "place"  # type: ignore[union-attr]


def test_a_display_begun_on_the_line_after_a_heading_labels_itself(tmp_path: Path) -> None:
    """The review's C-2, in the survey: the display's label is an equation's, so digest never writes the section's number for its `\\eqref`."""
    src = (
        "\\documentclass{article}\n\\usepackage{amsmath}\n\\numberwithin{equation}{section}\n\\begin{document}\n"
        "\\section{Bounds}\nWe now record the bound \\begin{equation}\\label{eq:first} a = b \\end{equation} which we use often.\n"
        "\\end{document}\n"
    )
    s = survey.read(_one_file(tmp_path, src), "main.tex", TEX)
    assert s.sections[0].label is None and s.labels["eq:first"].kind == "equation"
    assert s.labels["eq:first"].emulated == "1.1"


#: Three displays in a row, the last a formula too wide for its number to stand apart.
WIDE = r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section{One}
\begin{equation}\label{e:a} a \end{equation}
\begin{equation}\label{e:b} b \end{equation}
\begin{equation}\label{e:c} c + c + c \end{equation}
\end{document}
"""


def test_a_number_at_the_end_of_a_wide_display_s_line_is_counted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's C-8: `pdftotext` sets a wide display's number at its line's end; uncounted, it let one display loom does not count balance the window, and every number after it slid by one."""

    def kept(text: str) -> dict[str, str | None]:
        monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls([text])))
        root = tmp_path / ("q" + str(len(list(tmp_path.iterdir()))))
        root.mkdir()
        done = survey.confirmed(root, TEX, _one_file(root, WIDE), "main.tex", pdf=TEX, pdf_path=root / "x.pdf")
        return {k: v.number for k, v in done.labels.items() if v.kind == "equation" and v.number}

    assert kept("1 One\na\n(1)\nb\n(2)\nc + c + c (3)\n") == {"e:a": "1", "e:b": "2", "e:c": "3"}
    assert kept("1 One\na\n(1)\nv\n(2)\nb\n(3)\nc + c + c (4)\n") == {}, "e:b and e:c would read (2) and (3)"
