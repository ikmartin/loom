"""A work's macros node made from its source's preamble (`library.macros`): a conditional kept whole when its branches hold what a macros node may, and left out, said in the node, otherwise; and the node made typesets a body that uses it."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from loom.library.checks import check_file
from loom.library.macros import macros_node, preamble_items
from loom.library.node import node_bytes

JOURNAL = (
    "\\newif\\ifjournal\n\\journaltrue\n\\ifjournal\n\\newcommand{\\R}{\\mathbb{R}}\n\\else\n"
    "\\newcommand{\\R}{\\mathbf{R}}\n\\fi\n"
)
#: A source each: its preamble, its local files, and a body that uses what they define.
SOURCES: dict[str, tuple[str, dict[str, str], str]] = {
    "a flag choosing a definition": ("\\usepackage{amssymb}\n" + JOURNAL, {}, "$\\R$"),
    "a guard on a definition": (
        "\\newcommand{\\R}{\\mathbb{R}}\n\\usepackage{amssymb}\n\\ifdefined\\R\\else\\newcommand{\\R}{\\mathbf{R}}\\fi\n",
        {},
        "$\\R$",
    ),
    "a package's guard": (
        "\\usepackage{mine}\n",
        {"mine.sty": "\\RequirePackage{amssymb}\n\\@ifundefined{R}{\\newcommand{\\R}{\\mathbb{R}}}{}\n"},
        "$\\R$",
    ),
    "a local file read in a branch": (
        "\\newif\\ifshort\n\\shorttrue\n\\ifshort\\input{short}\\else\\newcommand{\\C}{\\mathbf{C}}\\fi\n",
        {"short.tex": "\\newcommand{\\C}{C}\n"},
        "$\\C$",
    ),
}


def source(tmp_path: Path, preamble: str, files: dict[str, str]) -> Path:
    folder = tmp_path / "src"
    folder.mkdir(parents=True)
    (folder / "main.tex").write_text(f"\\documentclass{{article}}\n{preamble}\\begin{{document}}\\end{{document}}\n")
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


def made(tmp_path: Path, name: str) -> str:
    """The macros node's body made from `SOURCES[name]`, which check 10 passes."""
    preamble, files, _body = SOURCES[name]
    node = macros_node("tq-00A1-ref", preamble_items(source(tmp_path, preamble, files)))
    assert node is not None
    assert check_file(node.file_name, node_bytes(node))[1] == []
    return node.body


def test_a_conditional_is_kept_whole_with_one_definition_in_each_branch(tmp_path: Path) -> None:
    """M-9: both branches of `\\ifjournal` define `\\R`, and only the conditional keeps the second from failing."""
    body = made(tmp_path, "a flag choosing a definition")
    assert body == "\\usepackage{amssymb}\n" + JOURNAL


def test_a_guard_and_a_package_s_guard_are_kept_whole(tmp_path: Path) -> None:
    assert "\\ifdefined\\R\n\n\\else\n\\newcommand{\\R}{\\mathbf{R}}\n\\fi" in made(
        tmp_path / "a", "a guard on a definition"
    )
    assert "\\@ifundefined{R}{\\newcommand{\\R}{\\mathbb{R}}}{}" in made(tmp_path / "b", "a package's guard")


def test_a_local_file_a_branch_reads_is_read_in_its_place(tmp_path: Path) -> None:
    body = made(tmp_path, "a local file read in a branch")
    assert "\\ifshort\n\\newcommand{\\C}{C}\n\\else\n\\newcommand{\\C}{\\mathbf{C}}\n\\fi" in body
    assert "\\input" not in body


@pytest.mark.parametrize(
    ("preamble", "said"),
    [
        (
            "\\newif\\ifdraft\n\\ifdraft\\newtheorem{lemma}{Lemma}\\else\\newcommand{\\D}{d}\\fi\n",
            "% left out: \\ifdraft … \\fi, a conditional holding \\newtheorem, which a macros node may not",
        ),
        (
            "\\ifnum\\value{page}>0 \\newcommand{\\D}{d}\\fi\n",
            "% left out: \\ifnum\\value{page}>0 \\newcommand{\\D}{d}\\fi, a conditional whose condition loom does not read",
        ),
    ],
)
def test_a_conditional_holding_what_a_macros_node_may_not_is_left_out_and_said(
    tmp_path: Path, preamble: str, said: str
) -> None:
    items = preamble_items(source(tmp_path, "\\newcommand{\\K}{k}\n" + preamble, {}))
    assert said in items and "\\newcommand{\\D}{d}" not in items
    node = macros_node("tq-00A1-ref", items)
    assert node is not None and check_file(node.file_name, node_bytes(node))[1] == []
    assert macros_node("tq-00A1-ref", [said]) is None, "a node holding only what was left out is none"


@pytest.mark.tex
@pytest.mark.parametrize("name", sorted(SOURCES))
def test_a_body_typesets_against_the_macros_node_made(tmp_path: Path, name: str) -> None:
    """The node is the only typesetting a work's results get: put before a body that uses it, under `article`, it compiles."""
    body = made(tmp_path, name)
    doc = tmp_path / "try.tex"
    doc.write_text(f"\\documentclass{{article}}\n{body}\\begin{{document}}\n{SOURCES[name][2]}\n\\end{{document}}\n")
    run = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", doc.name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        env=os.environ,
    )
    assert run.returncode == 0, next((ln for ln in run.stdout.splitlines() if ln.startswith("!")), run.stdout[-400:])


def test_a_large_source_is_read_only_to_its_preamble(tmp_path: Path) -> None:
    """A source may be hundreds of megabytes: the maker reads the main file up to `\\begin{document}` a line at a time, not whole."""
    import tracemalloc

    folder = tmp_path / "src"
    folder.mkdir()
    body = ("A line of the paper's text, long enough to count. " * 4 + "\n") * 120_000  # about 24 MB
    (folder / "main.tex").write_text(
        "\\documentclass{article}\n\\newcommand{\\R}{\\mathbb{R}}\n% \\begin{document} in a comment\n\\begin{document}\n"
        + body
        + "\\end{document}\n"
    )
    tracemalloc.start()
    try:
        items = preamble_items(folder)
        _now, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert items == ["\\newcommand{\\R}{\\mathbb{R}}"]
    assert peak < 4 * 1024 * 1024, f"read {peak} bytes for a preamble of two lines"


def test_a_local_file_over_the_cap_is_not_read_in_its_place(tmp_path: Path) -> None:
    from loom.library.macros import LOADED_CAP

    folder = source(
        tmp_path,
        "\\usepackage{small}\n\\usepackage{huge}\n",
        {
            "small.sty": "\\newcommand{\\S}{s}\n",
            "huge.sty": "\\newcommand{\\H}{h}\n" + "% filler\n" * (LOADED_CAP // 9 + 1),
        },
    )
    items = preamble_items(folder)
    assert "\\newcommand{\\S}{s}" in items and "\\usepackage{huge}" in items
    assert "\\newcommand{\\H}{h}" not in items
