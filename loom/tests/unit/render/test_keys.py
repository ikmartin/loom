"""What a cache key takes from a document's aux: its numbers always, its pages only for a text that prints one, so a page break that moves remakes nothing else."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from loom.render.keys import PAGEREF, aux_bytes, aux_digest, preamble_prints_pages
from loom.tex.aux import parse_aux

AUX = r"""\relax
\providecommand\hyper@newdestlabel[2]{}
\newlabel{sec:one}{{1}{3}{Intro}{section.1}{}}
\newlabel{sec:one@cref}{{[section][1][]1}{[1][3][]3}}
\newlabel{lem:a}{{2.7}{5}{}{theorem.2.7}{}}
\zref@newlabel{lem:z}{\default{2.8}\page{5}\abspage{5}}
\@writefile{toc}{\contentsline {section}{\numberline {1}Intro}{3}{section.1}\protected@file@percent }
\abx@aux@page{1}{4}
\bibcite{GP99}{GP99}
\gdef \@abspage@last{12}
"""


def shifted(text: str) -> str:
    """Every page one later, as a page break that moves early in the document leaves the aux."""
    for a, b in (
        ("{3}{Intro}", "{4}{Intro}"),
        ("[1][3][]3", "[1][4][]4"),
        ("{5}{}{theorem", "{6}{}{theorem"),
        ("\\page{5}\\abspage{5}", "\\page{6}\\abspage{6}"),
        ("{3}{section.1}\\protected", "{4}{section.1}\\protected"),
        ("{1}{4}", "{1}{5}"),
        ("{12}", "{13}"),
    ):
        assert a in text, a
        text = text.replace(a, b)
    return text


def written(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    return path


def test_the_numbers_loom_renders_with_hold_no_page() -> None:
    before, after = parse_aux(AUX), parse_aux(shifted(AUX))
    assert before["lem:a"].page != after["lem:a"].page
    assert aux_bytes({"m": before}, {}) == aux_bytes({"m": after}, {})
    assert aux_bytes({"m": before}, {}) != aux_bytes({"m": parse_aux(AUX.replace("{{2.7}", "{{2.8}"))}, {})


def test_a_text_that_prints_no_page_keeps_its_key_when_the_pages_move(tmp_path: Path) -> None:
    aux = written(tmp_path / "main.aux", AUX)
    see, page = "By Lemma~\\ref{lem:a}.", "On page~\\pageref{lem:a}."
    first = (aux_digest(aux, see), aux_digest(aux, page))
    written(aux, shifted(AUX))
    assert aux_digest(aux, see) == first[0]
    assert aux_digest(aux, page) != first[1]
    # a number that changes changes both, zref's among them
    for a, b in (("{{2.7}", "{{2.9}"), ("\\default{2.8}", "\\default{2.10}")):
        written(aux, AUX.replace(a, b))
        assert aux_digest(aux, see) != first[0], a


@pytest.mark.parametrize(
    "command",
    [
        "\\pageref{x}",
        "\\autopageref{x}",
        "\\cpageref{x}",
        "\\Cpageref{x}",
        "\\zpageref{x}",
        "\\vpageref{x}",
        "\\pagerefrange{x}{y}",
        "\\labelcpageref{x}",
        "\\vref{x}",
        "\\Vref{x}",
        "\\fullref{x}",
        "\\PreviousTotalPages",
    ],
)
def test_every_command_that_prints_a_page_is_one(command: str) -> None:
    assert PAGEREF.search(f"See {command} there.")


@pytest.mark.parametrize(
    "command", ["\\ref{x}", "\\cref{x}", "\\eqref{x}", "\\autoref{x}", "\\pagestyle{empty}", "\\nameref{x}", "\\vrefs"]
)
def test_a_command_that_prints_no_page_is_not(command: str) -> None:
    assert not PAGEREF.search(f"See {command} there.")


def test_a_preamble_whose_own_macro_prints_a_page_keys_every_text_on_pages(tmp_path: Path) -> None:
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "macros.tex").write_text(
        "\\newcommand{\\at}[1]{\\ref{#1} on page~\\pageref{#1}}\n", encoding="utf-8"
    )
    (tmp_path / "paper" / "house.sty").write_text("\\RequirePackage{deeper}\n", encoding="utf-8")
    (tmp_path / "paper" / "deeper.sty").write_text("\\newcommand{\\where}[1]{\\autopageref{#1}}\n", encoding="utf-8")
    plain = "\\documentclass{amsart}\n\\usepackage{amsmath,amsthm}\n"
    assert not preamble_prints_pages(tmp_path, "paper", plain)
    assert preamble_prints_pages(tmp_path, "paper", plain + "\\input{macros}\n")
    assert preamble_prints_pages(tmp_path, "paper", plain + "\\usepackage{amssymb,house}\n")
    assert not preamble_prints_pages(
        tmp_path, "", plain + "\\input{macros}\n"
    )  # read against the document's own directory
    aux = written(tmp_path / "main.aux", AUX)
    assert aux_digest(aux, "By \\ref{lem:a}.", pages=True) == aux_digest(aux, "On \\pageref{lem:a}.")


def test_a_page_break_that_moves_re_renders_no_block_and_a_renumbering_does(tmp_path: Path) -> None:
    from loom.paths import document_build
    from loom.render.build import build
    from loom.scan.quilt import load_quilt
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    keys = sorted(k for k, n in build(load_quilt(q)).result.nodes.items() if n.kind == "environment")

    def aux(page: int, first: int = 1) -> str:
        """Every statement numbered from `first`, the first on `page`, as hyperref writes it."""
        return "".join(
            f"\\newlabel{{{k}}}{{{{{first + i}}}{{{page + i}}}{{}}{{theorem.{i}}}{{}}}}\n" for i, k in enumerate(keys)
        )

    path = written(q / document_build("drafting/main.tex") / "main.aux", aux(1))
    assert keys and build(load_quilt(q)).rendered
    written(path, aux(2))
    # a kept version's landmark is keyed on its live document's whole aux, and is the one fragment made again
    assert [k for k in build(load_quilt(q)).rendered if not k.startswith("canon:")] == []
    written(path, aux(2, first=2))
    assert set(build(load_quilt(q)).rendered) >= set(keys)
