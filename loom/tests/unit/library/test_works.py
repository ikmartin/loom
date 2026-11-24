"""The works list as a read (`library.works`, `library-views.md` §2 and §3.1): it gathers and writes nothing, opens no node file, and its generation stands while nothing a row is made from changes, so `since` answers `unchanged`."""

from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any

import pytest

from loom.library import log
from loom.library.gather import gather
from loom.library.generation import generation
from loom.library.intake import Item, take
from loom.library.works import works
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan

MAIN = "\\documentclass{article}\n\\begin{document}\nBy \\cite{Smi24}.\n\\bibliography{refs}\n\\end{document}\n"
BIB = "@article{Smi24,\n  author = {Smith, Jane},\n  title = {Widgets},\n  year = {2024},\n}\n@article{Jon19,\n  author = {Jones, Alex},\n  title = {Gadgets},\n  year = {2019},\n}\n"


def quilt(tmp_path: Path) -> Path:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(MAIN)
    (root / "refs.bib").write_text(BIB)
    load_quilt(root)
    return root


def kept(root: Path) -> dict[str, int]:
    """Every file of the quilt outside the cache, with when it was written."""
    return {
        p.relative_to(root).as_posix(): p.stat().st_mtime_ns
        for p in root.rglob("*")
        if p.is_file() and not p.relative_to(root).as_posix().startswith(".loom/cache/")
    }


def test_the_works_list_gathers_nothing_and_writes_nothing(tmp_path: Path) -> None:
    """The review's M-12: a read of the list is a read; gathering is a build's."""
    root = quilt(tmp_path)
    before = kept(root)
    assert works(scan(load_quilt(root))) == []
    assert kept(root) == before, "a read writes no node, no log line and no lock"
    gather(scan(load_quilt(root)))
    assert sorted(r["short"] for r in works(scan(load_quilt(root)))) == ["Jones 2019", "Smith 2024"]


def test_the_works_list_opens_no_node_file_no_pdf_and_no_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = quilt(tmp_path)
    gather(scan(load_quilt(root)))
    for node in (root / ".loom/library/nodes").iterdir():
        os.utime(node, ns=(node.stat().st_atime_ns, node.stat().st_mtime_ns - 3_600_000_000_000))
    result = scan(load_quilt(root))
    # the index brought up to date, as any read of the library brings it; a file written within its last moments it reads again
    works(result)
    opened: list[str] = []
    real = builtins.open

    def spy(file: Any, *args: Any, **kw: Any) -> Any:
        opened.append(str(file))
        return real(file, *args, **kw)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    rows = works(result)
    assert len(rows) == 2
    assert [p for p in opened if p.endswith((".node", ".pdf", ".tar"))] == []


def test_the_generation_stands_until_anything_a_row_reads_changes(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    gather(scan(load_quilt(root)))
    result = scan(load_quilt(root))
    first = generation(result)
    assert generation(result) == first, "nothing changed, so `since` answers unchanged"
    # a node: a work pasted
    take(root, [Item(text="@article{New1, title = {New}}\n")], by="A. Author")
    after_node = generation(result)
    assert after_node > first
    assert generation(result) == after_node
    # the log alone: a look-up recorded and nothing else
    [ref] = [r["ref"] for r in works(result) if r["short"] == "New"]
    log.record(root, "looked-up", ref, by="A. Author", kind="person", found=False)
    after_log = generation(result)
    assert after_log > after_node
    # the scan alone: a document cites another work, so `used_in` changes
    (root / "main.tex").write_text(MAIN.replace("\\cite{Smi24}", "\\cite{Smi24,Jon19}"))
    rescanned = scan(load_quilt(root))
    assert generation(rescanned) > after_log
    assert {r["short"]: r["used_in"] for r in works(rescanned)}["Jones 2019"] == ["main.tex"]
