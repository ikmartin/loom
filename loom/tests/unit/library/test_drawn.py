"""A node drawn by TeX with its work's macros (`library.drawn`): only after the person's word for its work, kept on this machine and never in the quilt; made once, and a failure of TeX's kept too."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from loom import machine
from loom.library import drawn, ids
from loom.library.node import Node, node_bytes, node_hash
from loom.library.store import read, write_node
from loom.paths import LIBRARY_DRAWN
from loom.tex.runner import CompileResult
from tests.unit.library.test_digest import PDF, quilt, stub, surveyed

#: A macro the work's preamble defines, which its lemma's text uses.
MACROS = "\\newcommand{\\W}{\\mathcal{W}}\n"
SVG = '<svg xmlns="http://www.w3.org/2000/svg"/>\n'


@pytest.fixture
def pdf_text(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The digest tests' PDF text, read as the stored PDF's."""
    from loom.library import survey

    pages = list(PDF)
    monkeypatch.setattr(survey.Pages, "of", classmethod(lambda cls, _pdf: cls(pages)))
    return pages


def lemma(tmp_path: Path) -> tuple[Path, str, Node]:
    """The digest tests' quilt with Smith 2024's Lemma 1.2 digested, given a macros node it uses: the root, Smith's reference and the lemma."""
    from loom.library.digest import digest

    result, smith = quilt(tmp_path)
    s = surveyed(result, smith)
    digest(result, smith, [i.item for i in s.items], s)
    root = result.quilt.root
    write_node(root, Node(id=ids.macros_of(smith), taxon="macros", body=MACROS))
    found = read(root, stub(root, smith, "1.2"))
    assert found is not None and not found.empty
    assert "$W$" in found.body
    write_node(root, replace(found, body=found.body.replace("$W$", "$\\W$")))
    node = read(root, found.id)
    assert node is not None
    return root, smith, node


def name_of(root: Path, smith: str, node: Node) -> str:
    """The drawing's name, as the viewer makes it from `library-node`'s `hash` and `macros.hash`."""
    macros = read(root, ids.macros_of(smith))
    assert macros is not None
    hexes = [node_hash(node_bytes(n)).removeprefix("sha256:") for n in (node, macros)]
    return f"{hexes[0]}-{hexes[1]}.svg"


@pytest.fixture
def compiles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """TeX and the converter faked: each compile's document is recorded, and its page becomes `SVG`."""
    from loom.render import assets
    from loom.tex import runner

    texts: list[str] = []

    def compile_tex(root: Path, tex: str, out: Path, engine: str, **kw: object) -> CompileResult:
        texts.append((root / tex).read_text(encoding="utf-8"))
        assert kw.get("foreign") is True and kw.get("online") is False, "a foreign text, fetching nothing"
        out.mkdir(parents=True, exist_ok=True)
        (out / "node.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
        return CompileResult(ok=True, engine=engine, outdir=out, returncode=0, pdf=out / "node.pdf")

    def pdf_to_svg(_src: Path, out: Path) -> tuple[bool, bool]:
        out.write_text(SVG, encoding="utf-8")
        return True, False

    monkeypatch.setattr(runner, "compile_tex", compile_tex)
    monkeypatch.setattr(assets, "pdf_to_svg", pdf_to_svg)
    return texts


def test_nothing_is_drawn_before_the_persons_word_for_the_work_and_then_once(
    tmp_path: Path, pdf_text: list[str], compiles: list[str]
) -> None:
    root, smith, node = lemma(tmp_path)
    name = name_of(root, smith, node)
    assert drawn.drawn(root, name) is None and compiles == [], "no word, no compile"
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    made = drawn.drawn(root, name)
    assert made == root / LIBRARY_DRAWN / name and made.read_text(encoding="utf-8") == SVG
    assert len(compiles) == 1 and drawn.drawn(root, name) == made and len(compiles) == 1, "kept, not drawn twice"
    text = compiles[0]
    assert text.index(MACROS.strip()) < text.index("\\begin{document}") < text.index("\\textbf{Lemma 1.2}")
    assert "Every widget $\\W$" in text and "\\documentclass[border=1pt]{standalone}" in text
    widget, (anchor,) = stub(root, smith, "1.1"), node.awaiting
    assert f"\\@namedef{{r@{widget}}}{{{{1.1}}{{}}}}" in text, "a pointer prints its result's number"
    assert f"\\@namedef{{loom@tag@{anchor}}}{{\\tag*{{}}}}" in text, "a display awaiting its number is drawn with none"
    assert not (root / ".loom/cache/library/drawn/run").exists(), "the compile's folder is removed"
    write_node(root, replace(node, anchors=((anchor, "1.1"),), awaiting=()))
    numbered = read(root, node.id)
    assert numbered is not None and drawn.drawn(root, name_of(root, smith, numbered)) is not None
    assert f"\\@namedef{{loom@tag@{anchor}}}{{\\tag{{1.1}}}}" in compiles[1], "once numbered, its source's number"


def test_the_word_is_kept_on_the_machine_so_a_copy_of_the_quilt_draws_nothing(
    tmp_path: Path, pdf_text: list[str], compiles: list[str]
) -> None:
    root, smith, node = lemma(tmp_path)
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    kept = machine.words_file(root)
    assert kept.is_file() and not kept.resolve().is_relative_to(root.resolve())
    assert not [
        p for p in root.rglob("*") if p.is_file() and work.tex in p.read_text(errors="replace") and "words" in p.name
    ]
    copy = tmp_path / "copy"
    shutil.copytree(root, copy)
    shutil.rmtree(copy / LIBRARY_DRAWN, ignore_errors=True)
    assert drawn.drawn(copy, name_of(copy, smith, node)) is None and compiles == [], "a copy is another quilt"
    assert not drawn.given(root, smith, "sha256:" + "0" * 64), "a source put in its place asks again"


def test_a_name_naming_no_drawing_draws_nothing(tmp_path: Path, pdf_text: list[str], compiles: list[str]) -> None:
    root, smith, node = lemma(tmp_path)
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    node_hex = node_hash(node_bytes(node)).removeprefix("sha256:")
    assert drawn.drawn(root, f"{node_hex}-none.svg") is None, "its work has a macros node, so `none` is stale"
    assert drawn.drawn(root, f"{node_hex}-{'0' * 64}.svg") is None, "another macros node's"
    assert drawn.drawn(root, f"{'0' * 64}-none.svg") is None, "no node of the store"
    assert drawn.drawn(root, "../../config.toml") is None
    empty = read(root, stub(root, smith, "1.1"))
    assert empty is not None
    write_node(root, replace(empty, body=""))
    blank = read(root, empty.id)
    assert blank is not None and drawn.drawn(root, name_of(root, smith, blank)) is None, "a stub has no text"
    assert compiles == []


def test_a_failure_of_texs_is_kept_and_one_of_the_machines_is_not(
    tmp_path: Path, pdf_text: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.tex import runner

    root, smith, node = lemma(tmp_path)
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    name = name_of(root, smith, node)
    codes = [127, 1]

    def compile_tex(_root: Path, _tex: str, out: Path, engine: str, **_kw: object) -> CompileResult:
        return CompileResult(ok=False, engine=engine, outdir=out, returncode=codes.pop(0), errors=["! Undefined."])

    monkeypatch.setattr(runner, "compile_tex", compile_tex)
    assert drawn.drawn(root, name) is None and not (root / LIBRARY_DRAWN / name).with_suffix(".failed").exists()
    assert drawn.drawn(root, name) is None and (root / LIBRARY_DRAWN / name).with_suffix(".failed").is_file()
    assert drawn.drawn(root, name) is None and codes == [], "not tried again"


def test_the_sweep_keeps_a_drawing_while_its_node_stands(
    tmp_path: Path, pdf_text: list[str], compiles: list[str]
) -> None:
    from loom.lifetimes import Named, _Rules

    root, smith, node = lemma(tmp_path)
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    name = name_of(root, smith, node)
    assert drawn.drawn(root, name) is not None
    rel = f"library/drawn/{name}"
    assert _Rules(root, None, Named(set()), now=1e12).keeps(rel, 0.0)
    write_node(root, replace(node, body=node.body.replace("widget", "gadget")))
    assert not _Rules(root, None, Named(set()), now=1e12).keeps(rel, 0.0), "drawn from text the node no longer holds"


def test_the_server_draws_a_node_only_for_a_work_with_the_persons_word(
    tmp_path: Path, pdf_text: list[str], compiles: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.render import serve as serve_mod
    from loom.render.serve import ServeSession
    from loom.scan.quilt import load_quilt
    from tests.unit.render._serve import QuickServer, fake_bundle, get, post

    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    root, smith, node = lemma(tmp_path)
    url = f"_api/library/drawn/{name_of(root, smith, node)}"
    s = ServeSession(load_quilt(root), fake_bundle(tmp_path), port=0, compile_masters=False, interval=0.2)
    s.listen()
    try:
        assert get(s.url + url)[0] == 404 and compiles == []
        status, said = post(s.url + "_api/library-compile", {"ref": smith})
        assert status == 200 and said["ok"], said
        status, headers, body = get(s.url + url)
        assert status == 200 and headers["Content-Type"].startswith("image/svg+xml") and body == SVG.encode()
        assert "sandbox" in headers["Content-Security-Policy"] and "immutable" in headers["Cache-Control"]
    finally:
        s.stop()


@pytest.mark.tex
def test_tex_draws_a_node_with_its_works_macros(tmp_path: Path, pdf_text: list[str]) -> None:
    root, smith, node = lemma(tmp_path)
    work = read(root, smith)
    assert work is not None and work.tex
    drawn.give(root, smith, work.tex)
    made = drawn.drawn(root, name_of(root, smith, node))
    assert made is not None, [p.read_text() for p in (root / LIBRARY_DRAWN).glob("*.failed")]
    assert "<svg" in made.read_text(encoding="utf-8")
    write_node(root, replace(node, anchors=((node.awaiting[0], "1.1"),), awaiting=()))
    numbered = read(root, node.id)
    assert numbered is not None
    tagged = drawn.drawn(root, name_of(root, smith, numbered))
    assert tagged is not None, [p.read_text() for p in (root / LIBRARY_DRAWN).glob("*.failed")]
    assert tagged.read_bytes() != made.read_bytes(), "its display drawn with its source's number"
