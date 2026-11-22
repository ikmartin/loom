"""The survey of a TeX source: what it holds, read once and kept by the source's hash."""

from __future__ import annotations

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
    assert [(x.section, x.command, x.number, x.title) for x in s.sections] == [
        ("s1", "section", "1", "Introduction"),
        ("s2", "section", "2", "Bounds"),
        ("s3", "section", None, "Acknowledgements"),
        ("s4", "section", "7", "Later"),
        ("s5", "section", "A", "Proofs"),
    ]
    assert s.sections[0].label == "sec:intro" and s.sections[4].label == "sec:proofs"
    rows = [(i.item, i.taxon, i.name, i.number, i.title, i.label, i.section) for i in s.items]
    assert rows == [
        ("def:widget", "definition", "Definition", "1.1", "Widget", "def:widget", "s1"),
        ("i2", "lemma", "Lemma", "1.2", None, None, "s1"),
        ("thm:main", "theorem", "Theorem", "2.1", "Main", "thm:main", "s2"),
        ("claim:star", "other", "Claim", None, None, "claim:star", "s3"),
        ("not:hom", "other", "Notation", "7.1", None, "not:hom", "s4"),
        ("thm:app", "theorem", "Theorem", "A.1", None, "thm:app", "s5"),
    ]
    main = s.item("thm:main")
    assert main is not None and main.file == "part2.tex" and main.labels == ["thm:main", "thm:alias"]
    assert PART2[main.body_start : main.body_end].strip() == "\\label{thm:main}\\label{thm:alias}\nWidgets are compact."


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
    assert [x.number for x in s.sections] == ["1", "2", "3", "4", "5"]
    assert [f"{i.name} {i.number}" for i in s.items] == [
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


def test_a_number_or_page_is_taken_only_when_it_is_shaped_as_one(tmp_path: Path) -> None:
    s = survey.read(_source(tmp_path), "main.tex", TEX)
    aux = "\n".join(
        [
            r"\newlabel{loom-survey-i0}{{1.1}{2}}",
            r"\newlabel{loom-survey-i1}{{\input{/etc/hosts}}{2}}",
            r"\newlabel{loom-survey-i2}{{root:x:0:0:root:/root}{3}}",
            r"\newlabel{loom-survey-i3}{{1.3}{3}}",
            r"\newlabel{loom-survey-i4}{{7.1}{4}}",
            r"\newlabel{loom-survey-s0}{{1}{2}}",
            r"\newlabel{eq:bound}{{1}{2}}",
            r"\newlabel{claim:star}{{1.3}{3}}",
            r"\newlabel{fig:one}{{a-very-long-number-indeed}{4}}",
            r"\loomSurveySheet{loom-survey-i0}{2}",
            r"\loomSurveySheet{loom-survey-i4}{0}",
        ]
    )
    done = survey.numbered(s, [aux])
    assert done.state == "ready" and s.state == "reading"
    assert [(i.number, i.page, i.sheet) for i in done.items] == [
        ("1.1", 2, 2),
        (None, 2, None),
        (None, 3, None),
        (None, 3, None),
        ("7.1", 4, None),
        (None, None, None),
    ]
    assert (done.sections[0].number, done.sections[1].number) == ("1", None)
    assert done.labels["eq:bound"].number == "1" and done.labels["claim:star"].number is None
    assert done.labels["fig:one"].number is None and done.labels["fig:one"].page == 4


def test_a_quilt_compiles_one_source_at_a_time_and_keeps_what_it_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, src = tmp_path / "quilt", _source(tmp_path)
    spans: list[tuple[float, float]] = []

    def slow(_src: Path, s: survey.Survey) -> survey.Survey:
        start = time.monotonic()
        time.sleep(0.3)
        spans.append((start, time.monotonic()))
        return survey.numbered(s, [])

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


@pytest.mark.tex
def test_a_compile_numbers_every_result_as_its_source_prints_it_and_leaves_the_source_alone(tmp_path: Path) -> None:
    src = _source(tmp_path)
    before = _bytes(src)
    done = survey.complete(tmp_path / "quilt", TEX, src, "main.tex")
    assert (done.state, done.why) == ("ready", None)
    assert [(i.item, i.number) for i in done.items] == [
        ("def:widget", "1.1"),
        ("i2", "1.2"),
        ("thm:main", "2.1"),
        ("claim:star", None),
        ("not:hom", "7.1"),
        ("thm:app", "A.1"),
    ]
    assert [x.number for x in done.sections] == ["1", "2", None, "7", "A"]
    assert [i.page for i in done.items] == [1, 1, 1, 1, 2, 2] and [i.sheet for i in done.items] == [1, 1, 1, 1, 2, 2]
    assert {k: done.labels[k].number for k in ("eq:bound", "it:first", "fig:one", "eq:outside", "sec:proofs")} == {
        "eq:bound": "1",
        "it:first": "1",
        "fig:one": "1",
        "eq:outside": "2",
        "sec:proofs": "A",
    }
    assert _bytes(src) == before and survey.kept(tmp_path / "quilt", TEX) == done


@pytest.mark.tex
def test_a_source_that_does_not_compile_fails_and_numbers_nothing_it_did_not_see_printed(tmp_path: Path) -> None:
    src = _source(tmp_path)
    (src / "main.tex").write_text(MAIN.replace("{amsart}", "{loom-no-such-class}"), encoding="utf-8")
    done = survey.complete(tmp_path / "quilt", TEX, src, "main.tex")
    assert (done.state, done.why) == ("failed", "compile")
    assert all(i.page is None for i in done.items)
