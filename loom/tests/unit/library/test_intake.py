"""The intake on references (`library.intake`, `docs/specs/write-api.md` §6): what a drop keeps, each row state, the rulings that offer a file as an existing work only by an identifier it states or a drop on its row, and undo and unfile by the act's record."""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from loom.library import documents, log
from loom.library.checks import check
from loom.library.intake import IntakeRefused, Item, answer, receive, take, undo, unfile, waiting, waiting_file
from loom.library.node import Node
from loom.library.store import read, write_node
from loom.paths import INCOMING, LIBRARY_DOCUMENTS
from loom.scan.quilt import load_quilt
from tests.unit._pdfs import lines_pdf

ME = {"by": "Isaac"}


def quilt(tmp_path: Path) -> Path:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\n')
    load_quilt(root)  # a quilt's first load stamps its format, as every real quilt has it
    return root


def dropped(root: Path, name: str, data: bytes) -> str:
    return str(receive(root, name, io.BytesIO(data), len(data))["incoming"])


def a_pdf(tmp_path: Path, lines: list[str], name: str = "paper.pdf") -> bytes:
    return lines_pdf(tmp_path / name, [lines]).read_bytes()


def source(title: str = "Gadget towers") -> bytes:
    files = {
        "main.tex": f"\\documentclass{{amsart}}\n\\newcommand{{\\G}}{{\\mathcal G}}\n\\title{{{title}}}\n\\author{{Ann Halberd \\and Paul Ravel}}\n\\begin{{document}}x\\end{{document}}\n".encode()
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue())


def rows(root: Path, *items: Item, **kw: Any) -> list[dict[str, Any]]:
    return [r.to_json() for r in take(root, list(items), **ME, **kw)]


# ---- what a drop keeps ------------------------------------------------------------------------------------------------


def test_a_drop_keeps_a_pdf_a_bib_a_source_and_nothing_else(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    for name, data in (
        ("p.pdf", a_pdf(tmp_path, ["x"])),
        ("refs.bib", b"@misc{a, title={x}}\n"),
        ("s.tar.gz", source()),
        ("main.tex", b"\\documentclass{article}"),
    ):
        drop = dropped(root, name, data)
        assert len(list((root / INCOMING / drop).glob("document.*"))) == 1, name
    for name, data in (("x.docx", b"PK\x03\x04 not really"), ("notes.txt", b"hello")):
        if name.endswith(".txt"):
            with pytest.raises(IntakeRefused) as caught:
                dropped(root, name, data)
            assert caught.value.code == "not-a-document"
    with pytest.raises(IntakeRefused) as empty:
        receive(root, "e.pdf", io.BytesIO(b""), 0)
    assert empty.value.code == "not-a-document"
    with pytest.raises(IntakeRefused) as short:
        receive(root, "s.pdf", io.BytesIO(b"%PDF-1.4 x"), 100)
    assert short.value.code == "cut-short"


def test_the_same_bytes_twice_are_one_drop(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    data = a_pdf(tmp_path, ["x"])
    assert dropped(root, "a.pdf", data) == dropped(root, "b.pdf", data)
    assert len(list((root / INCOMING).iterdir())) == 1


# ---- a work of its own, and the same bytes -----------------------------------------------------------------------------


def test_a_pdf_stating_nothing_is_a_work_of_its_own_stored_by_hash(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    data = a_pdf(tmp_path, ["Widgets and their bounds", "Jane Smith"])
    drop = dropped(root, "Smith - 2024 - Widgets and their bounds.pdf", data)
    [row] = rows(root, Item(drop=drop))
    assert (row["state"], row["found_by"], row["unconfirmed"], row["under"]) == ("added", "title", False, False)
    ref = row["ref"]
    node = read(root, ref)
    assert node is not None and node.pdf is not None and documents.path_of(root, node.pdf, "pdf").read_bytes() == data
    assert waiting_file(root / INCOMING / drop) is None, "the drop lets its file go once the store holds it"
    made = log.replay(root).made(ref)
    assert made is not None and (made["how"], made["kind"], made["source"]) == (
        "drop",
        "person",
        "Smith - 2024 - Widgets and their bounds.pdf",
    )
    assert check(root) == []
    again = dropped(root, "copy.pdf", data)
    [here] = rows(root, Item(drop=again))
    assert (here["state"], here["ref"]) == ("here", ref)


def test_a_title_alike_is_never_a_match(tmp_path: Path) -> None:
    """The rulings on Opens 6 and 18: a PDF that shares only its title with a work is a work of its own, and nothing is asked."""
    root = quilt(tmp_path)
    [first] = rows(
        root, Item(drop=dropped(root, "Smith - 2024 - Widgets.pdf", a_pdf(tmp_path, ["Widgets", "Jane Smith"])))
    )
    [second] = rows(
        root,
        Item(drop=dropped(root, "Smith - 2024 - Widgets.pdf", a_pdf(tmp_path, ["Widgets", "Jane Smith", "revised"]))),
    )
    assert second["state"] == "added" and second["ref"] != first["ref"]


@pytest.mark.poppler
def test_a_pdf_stating_an_identifier_the_library_has_asks_and_is_answered(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [pasted] = rows(
        root,
        Item(text="@article{Smi24,\n  title = {Widgets},\n  eprint = {2401.01234},\n  archiveprefix = {arXiv},\n}\n"),
    )
    stamped = a_pdf(tmp_path, ["arXiv:2401.01234v2 [math.AG] 3 Jan 2024", "Widgets", "Jane Smith"])
    drop = dropped(root, "preprint.pdf", stamped)
    [asked] = rows(root, Item(drop=drop))
    assert asked["state"] == "question" and [c["ref"] for c in asked["candidates"]] == [pasted["ref"]]
    assert asked["document"]["identifiers"] == ["arxiv:2401.01234v2"]
    assert [w["state"] for w in waiting(root)] == ["question"]
    filed = answer(root, asked["question"], pasted["ref"], **ME).to_json()
    assert (filed["state"], filed["ref"], filed["under"]) == ("added", pasted["ref"], True)
    node = read(root, pasted["ref"])
    assert node is not None and node.pdf is not None


@pytest.mark.poppler
def test_a_work_of_its_own_on_the_person_s_answer_keeps_the_others_apart(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [pasted] = rows(root, Item(text="@article{Smi24,\n  title = {Widgets},\n  eprint = {2401.01234},\n}\n"))
    drop = dropped(root, "p.pdf", a_pdf(tmp_path, ["arXiv:2401.01234v1 [math.AG] 3 Jan 2024", "Widgets"]))
    [asked] = rows(root, Item(drop=drop))
    own = answer(root, asked["question"], None, **ME).to_json()
    assert own["state"] == "added" and own["ref"] != pasted["ref"]
    assert own["found_by"] == "arxiv" and own["unconfirmed"] is True


@pytest.mark.poppler
def test_an_identifier_looked_up_online_is_confirmed(tmp_path: Path) -> None:
    from tests.unit.refs.test_lookup import ATOM, fake

    root = quilt(tmp_path)
    drop = dropped(root, "p.pdf", a_pdf(tmp_path, ["arXiv:0805.2065v2 [math.AG] 3 Jan 2024", "A title"]))
    [row] = rows(root, Item(drop=drop), online=True, http=fake({"https://export.arxiv.org/api/query": ATOM}))
    assert (row["state"], row["found_by"], row["unconfirmed"]) == ("added", "arxiv", False)
    made = log.replay(root).made(row["ref"])
    assert made is not None and made["looked_up"] is True


def test_a_drop_on_a_row_is_filed_under_it(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [pasted] = rows(root, Item(text="@article{Smi24, title = {Widgets}}\n"))
    drop = dropped(root, "anything.pdf", a_pdf(tmp_path, ["Something else entirely"]))
    [row] = rows(root, Item(drop=drop, work=pasted["ref"]))
    assert (row["state"], row["ref"], row["under"]) == ("added", pasted["ref"], True)
    [second] = rows(root, Item(drop=dropped(root, "b.pdf", a_pdf(tmp_path, ["another"])), work=pasted["ref"]))
    assert (second["state"], second["code"]) == ("cannot", "has-document")
    with pytest.raises(IntakeRefused) as caught:
        take(root, [Item(drop=dropped(root, "c.pdf", a_pdf(tmp_path, ["c"])), work="tq-0ZZZ-ref")], **ME)
    assert caught.value.code == "no-such-work"


def test_a_source_is_a_work_with_its_macros(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [row] = rows(root, Item(drop=dropped(root, "2401.01234v2.tar.gz", source())))
    assert (row["state"], row["found_by"], row["tex"], row["unconfirmed"]) == ("added", "arxiv", True, True)
    node = read(root, row["ref"])
    assert node is not None and node.tex is not None and node.pdf is None
    assert "Gadget towers" in node.body and "Halberd" in node.body
    macros = read(root, row["ref"].removesuffix("-ref") + "-macros")
    assert macros is not None and "\\newcommand{\\G}" in macros.body


# ---- pasted text ------------------------------------------------------------------------------------------------------


def test_pasted_identifiers_offline_make_unconfirmed_works(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    got = rows(root, Item(text="arXiv:2209.01234v2\nISBN 978-3-16-148410-0\nnot an identifier\n"))
    assert [(r["state"], r.get("code")) for r in got] == [
        ("added", None),
        ("cannot", "no-service"),
        ("cannot", "not-recognised"),
    ]
    assert got[0]["unconfirmed"] is True and got[0]["found_by"] == "arxiv"
    [again] = rows(root, Item(text="2209.01234"))
    assert (again["state"], again["ref"]) == ("here", got[0]["ref"])


def test_a_pasted_entry_is_here_taken_or_new_by_its_key(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    entry = "@article{Smi24,\n  title = {Widgets},\n  doi = {10.1000/w},\n}\n"
    [first] = rows(root, Item(text=entry))
    assert first["state"] == "added" and first["found_by"] == "entry" and first["unconfirmed"] is False
    [same] = rows(root, Item(text=entry.replace("  title", "title")))
    assert (same["state"], same["ref"]) == ("here", first["ref"])
    [taken] = rows(root, Item(text="@book{smi24, title = {Another book}}\n"))
    assert (taken["state"], taken["code"]) == ("cannot", "key-taken")
    [by_doi] = rows(root, Item(text="@article{Other, title = {W}, doi = {10.1000/W}}\n"))
    assert (by_doi["state"], by_doi["ref"]) == ("here", first["ref"])


def test_a_dropped_bib_is_a_row_an_entry(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    drop = dropped(root, "refs.bib", b"@article{A, title={a}}\n@article{B, title={b}}\n")
    assert [r["state"] for r in rows(root, Item(drop=drop))] == ["added", "added"]
    assert not (root / INCOMING / drop).exists()


# ---- undo and unfile --------------------------------------------------------------------------------------------------


def test_undoing_an_add_takes_out_what_it_left_and_frees_its_key(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    data = a_pdf(tmp_path, ["x"])
    drop = dropped(root, "Smith - 2024 - Widgets.pdf", data)
    [row] = rows(root, Item(drop=drop))
    said, waits = undo(root, drop, act=row["act"], **ME)
    assert read(root, row["ref"]) is None and waits is None
    assert not any((root / LIBRARY_DOCUMENTS).iterdir()), "a document no reference names goes with the add"
    assert log.replay(root).deleted_keys() == set(), "an add taken back is no delete"
    assert "taken out" in said


def test_an_undo_is_refused_once_the_work_changed_or_has_results(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    drop = dropped(root, "Smith - 2024 - Widgets.pdf", a_pdf(tmp_path, ["x"]))
    [row] = rows(root, Item(drop=drop))
    node = read(root, row["ref"])
    assert node is not None
    write_node(root, Node(id="tq-0002", taxon="lemma", source=row["ref"], body="A lemma.\n"))
    with pytest.raises(IntakeRefused) as results:
        undo(root, drop, **ME)
    assert results.value.code == "not-new"
    (root / ".loom/library/nodes/tq-0002.node").unlink()
    write_node(root, replace(node, body=node.body.replace("Widgets", "Gadgets")))
    with pytest.raises(IntakeRefused) as changed:
        undo(root, drop, **ME)
    assert changed.value.code == "changed"


def test_a_document_comes_off_its_work_and_undo_puts_it_back(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [pasted] = rows(root, Item(text="@article{Smi24, title = {Widgets}}\n"))
    rows(root, Item(drop=dropped(root, "w.pdf", a_pdf(tmp_path, ["wrong"])), work=pasted["ref"]))
    off = unfile(root, pasted["ref"], **ME)
    node = read(root, pasted["ref"])
    assert node is not None and node.pdf is None
    d = root / INCOMING / off["incoming"]
    assert json.loads((d / "arrived.json").read_text())["not"] == [pasted["ref"]]
    assert [w["state"] for w in waiting(root)] == ["received"]
    undo(root, off["incoming"], act=off["act"], **ME)
    back = read(root, pasted["ref"])
    assert back is not None and back.pdf is not None and waiting(root) == []
    with pytest.raises(IntakeRefused) as none:
        unfile(root, pasted["ref"], which="tex", **ME)
    assert none.value.code == "no-document"
