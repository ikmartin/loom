"""The survey of a TeX source: what it holds, read once and kept by the source's hash."""

from __future__ import annotations

import shutil
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
