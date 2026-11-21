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
from loom.library.acts import delete
from loom.library.checks import check
from loom.library.intake import (
    IntakeRefused,
    Item,
    Library,
    answer,
    receive,
    take,
    undo,
    unfile,
    waiting,
    waiting_file,
)
from loom.library.node import Node
from loom.library.store import NodeRefused, read, write_node
from loom.library.works import generation
from loom.paths import INCOMING, LIBRARY_DOCUMENTS
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._pdfs import lines_pdf

ME = {"by": "A. Author"}


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


# ---- untrusted drops --------------------------------------------------------------------------------------------------


def a_tar(members: list[tuple[str, bytes]], *, gz: bool = False) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue()) if gz else buffer.getvalue()


DOC = b"\\documentclass{article}\n\\newcommand{\\R}{\\mathbb{R}}\n\\title{T}\\author{A}\n\\begin{document}x\\end{document}\n"


def left_by(root: Path) -> dict[str, list[str]]:
    """What the store, the library's log, the cache's sources and the drops hold."""
    out = {
        where: sorted(p.relative_to(root / where).as_posix() for p in (root / where).rglob("*"))
        for where in (".loom/library", ".loom/records", ".loom/cache/library", ".loom/local/incoming")
        if (root / where).exists()
    }
    return {where: held for where, held in out.items() if held}


@pytest.mark.parametrize(
    ("name", "data", "why"),
    [
        (
            "damaged.tar.gz",
            a_tar([("main.tex", DOC)], gz=True)[:-40],
            "damaged.tar.gz is damaged, or is not a TeX source",
        ),
        ("a.gz", b"\x1f\x8b" + bytes(range(256)) * 8, "a.gz is damaged, or is not a TeX source"),
        (
            "both.tar",
            a_tar([("main.tex", DOC), ("a", b"x"), ("a/b.tex", b"y")]),
            "both.tar holds both a file and a folder named a",
        ),
        (
            "long.tar",
            a_tar([("main.tex", DOC), ("n" * 300 + ".tex", b"x")]),
            "long.tar holds a file whose name is too long; loom cannot keep it",
        ),
    ],
    ids=["truncated", "not-gzip", "file-and-folder", "long-name"],
)
def test_an_archive_a_source_cannot_be_kept_of_is_a_cannot_row_and_leaves_nothing(
    tmp_path: Path, name: str, data: bytes, why: str
) -> None:
    """The review's M-6: a sentence a person acts on, never a 500 with Python's words; nothing stored, logged or cached, and the drop goes."""
    root = quilt(tmp_path)
    before = left_by(root)
    drop = dropped(root, name, data)
    [row] = rows(root, Item(drop=drop))
    assert (row["state"], row["code"], row["why"]) == ("cannot", "not-a-source", why)
    assert left_by(root) == before
    assert waiting(root) == []


def test_a_source_kept_is_unpacked_from_its_one_form(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [row] = rows(
        root, Item(drop=dropped(root, "paper.tar", a_tar([("main.tex", DOC), ("sec/a.tex", b"\\section{A}")])))
    )
    assert (row["state"], row["title"]) == ("added", "T")
    node = read(root, row["ref"])
    assert node is not None and node.tex is not None
    out = documents.source_dir(root, node.tex)
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["main.tex", "sec/a.tex"]
    assert not list((root / INCOMING).glob("*/.packed*")), (
        "the packed form is stored or removed, never left in the drop"
    )


def test_a_name_holding_a_nul_is_a_cannot_row_and_stores_nothing(tmp_path: Path) -> None:
    """The review's M-16: before, the PDF stayed in the store named by no reference."""
    root = quilt(tmp_path)
    drop = dropped(root, "a\nb\x00c.pdf", a_pdf(tmp_path, ["x"]))
    [row] = rows(root, Item(drop=drop))
    assert (row["state"], row["code"]) == ("cannot", "bad-name")
    assert row["why"] == "a b c.pdf has a control character in its name; rename the file without it and drop it again"
    assert not (root / LIBRARY_DOCUMENTS).exists() or not any((root / LIBRARY_DOCUMENTS).iterdir())


def test_dropping_the_same_bytes_again_leaves_the_first_add_s_undo_standing(tmp_path: Path) -> None:
    """The review's M-13."""
    root = quilt(tmp_path)
    data = a_pdf(tmp_path, ["x"])
    first = dropped(root, "Smith - 2024 - Widgets.pdf", data)
    [added] = rows(root, Item(drop=first))
    again = dropped(root, "again.pdf", data)
    assert again == first
    [here] = rows(root, Item(drop=again))
    assert (here["state"], here["ref"]) == ("here", added["ref"])
    said, _ = undo(root, first, act=added["act"], **ME)
    assert "taken out" in said and read(root, added["ref"]) is None


# ---- pasted and dropped bibliographies --------------------------------------------------------------------------------


def test_a_pasted_bib_has_its_abbreviations_written_into_each_entry(tmp_path: Path) -> None:
    """The review's M-8: a `@string` is expanded as gathering expands it, so a journal abbreviation is no refusal."""
    root = quilt(tmp_path)
    text = '@string{jex = {Journal of Examples}}\n@STRING(jfx = "Journal of Fixes")\n@article{Abb1, author={A, B}, title={T}, journal = jex, year=2001}\n@article{Abb2, title={U}, journal = jfx # " (new series)"}\n'
    got = rows(root, Item(text=text))
    assert [r["state"] for r in got] == ["added", "added"], got
    bodies = [n.body for n in (read(root, r["ref"]) for r in got) if n is not None]
    assert "journal = {Journal of Examples}" in bodies[0] and "journal = {Journal of Fixes (new series)}" in bodies[1]
    drop = dropped(root, "more.bib", b"@string{jb = {J. Bib.}}\n@article{Abb3, title={V}, journal = jb}\n")
    [row] = rows(root, Item(drop=drop))
    assert row["state"] == "added"


def test_an_entry_refused_is_said_by_its_key_and_what_in_it_to_change(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [row] = rows(root, Item(text="@article{Bad1, title={T}, journal = jnotdefined}\n"))
    assert (row["state"], row["code"]) == ("cannot", "refused")
    assert (
        row["why"]
        == "Bad1: its journal is jnotdefined, an abbreviation no @string in what you pasted defines; write it out in braces instead"
    )
    [dropped_row] = rows(root, Item(drop=dropped(root, "mine.bib", b"@article{Bad2, publisher = pnone}\n")))
    assert "no @string in mine.bib defines" in dropped_row["why"] and ".node" not in dropped_row["why"]


def test_two_entries_with_one_key_in_one_paste_report_the_second(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    got = rows(
        root,
        Item(
            text="@article{Dup1, author={Smith, J}, year={2020}, title={First}}\n@article{Dup1, title={Second}}\n@article{Dup1, author={Smith, J}, year={2020}, title={First}}\n"
        ),
    )
    assert [(r["state"], r.get("code")) for r in got] == [("added", None), ("cannot", "key-taken"), ("here", None)]
    assert (
        got[1]["why"] == "Smith 2020 has the key Dup1 already, above it in what you pasted; give this entry another key"
    )
    dry = [
        r.to_json()
        for r in take(root, [Item(text="@article{Dup9, title={A}}\n@article{dup9, title={B}}\n")], write=False, **ME)
    ]
    assert [(r["state"], r.get("code")) for r in dry] == [("added", None), ("cannot", "key-taken")]


def test_a_key_differing_only_in_a_case_beyond_ascii_is_taken(tmp_path: Path) -> None:
    """The review's M-18: keys compared as check 9 compares them (`casefold`), so `Straße1` beside `STRASSE1` is `key-taken`, not a refusal naming loom's files."""
    root = quilt(tmp_path)
    [first] = rows(root, Item(text="@article{STRASSE1, author={Weg, A}, year={2001}, title={A}}\n"))
    [second] = rows(root, Item(text="@article{Straße1, title={B}}\n"))
    assert (second["state"], second["code"]) == ("cannot", "key-taken")
    assert second["why"] == "Weg 2001 has the key STRASSE1 already; give the entry in what you pasted another key"


def test_a_pasted_identifier_of_another_version_is_a_work_of_its_own(tmp_path: Path) -> None:
    """The review's M-8: each version is a reference of its own, so `v1` beside a held `v2` is added, while the same version, or the number with none, is here."""
    root = quilt(tmp_path)
    [v2] = rows(root, Item(text="arXiv:2401.01234v2"))
    [v1] = rows(root, Item(text="arXiv:2401.01234v1"))
    assert v1["state"] == "added" and v1["ref"] != v2["ref"]
    assert [r["state"] for r in rows(root, Item(text="arXiv:2401.01234v2\n2401.01234\n"))] == ["here", "here"]
    [entry] = rows(root, Item(text="@misc{Other1, title={x}, eprint={2401.01234v3}}\n"))
    assert entry["state"] == "added"


# ---- unfile cut short -------------------------------------------------------------------------------------------------


def test_an_unfile_cut_short_before_the_document_comes_off_is_finished_or_undone_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's M-18: its act is recorded before the document comes off, so a kill there leaves nothing the undo cannot take back."""
    import loom.library.intake as intake

    root = quilt(tmp_path)
    [pasted] = rows(root, Item(text="@article{Smi24, title = {Widgets}}\n"))
    rows(root, Item(drop=dropped(root, "w.pdf", a_pdf(tmp_path, ["wrong"])), work=pasted["ref"]))
    held = read(root, pasted["ref"])
    assert held is not None and held.pdf is not None

    def killed(*_a: Any, **_k: Any) -> None:
        raise KeyboardInterrupt

    with monkeypatch.context() as m:
        m.setattr(intake, "attach", killed)
        with pytest.raises(KeyboardInterrupt):
            unfile(root, pasted["ref"], **ME)
    drop = held.pdf.removeprefix("sha256:")
    # undone: the work keeps its PDF, and nothing is left waiting or named by nobody
    said, waits = undo(root, drop, **ME)
    node = read(root, pasted["ref"])
    assert node is not None and node.pdf == held.pdf and waits is None and waiting(root) == []
    assert "as it was" in said
    # or run again: it finishes with the one act, which undo then takes back
    with monkeypatch.context() as m:
        m.setattr(intake, "attach", killed)
        with pytest.raises(KeyboardInterrupt):
            unfile(root, pasted["ref"], **ME)
    off = unfile(root, pasted["ref"], **ME)
    acts = json.loads((root / INCOMING / off["incoming"] / "act.json").read_text())["acts"]
    assert [a["kind"] for a in acts] == ["added", "unfiled"], "the filing, then the one unfile"
    node = read(root, pasted["ref"])
    assert node is not None and node.pdf is None
    undo(root, off["incoming"], act=off["act"], **ME)
    back = read(root, pasted["ref"])
    assert back is not None and back.pdf == held.pdf


# ---- the question settled, and what a drop that waits again says --------------------------------------------------------


def test_naming_one_of_two_candidates_files_the_drop_under_it(tmp_path: Path) -> None:
    """The person's answer is the person's word: it files under the work named, though another work states the identifier too."""
    root = quilt(tmp_path)
    v1, v2 = rows(root, Item(text="arXiv:2401.01234v1\narXiv:2401.01234v2"))
    drop = dropped(root, "2401.01234v3.pdf", a_pdf(tmp_path, ["Widgets"]))
    [asked] = rows(root, Item(drop=drop))
    assert asked["state"] == "question" and [c["ref"] for c in asked["candidates"]] == [v1["ref"], v2["ref"]]
    filed = answer(root, asked["question"], v2["ref"], **ME).to_json()
    assert (filed["state"], filed["ref"], filed["under"]) == ("added", v2["ref"], True), filed
    node = read(root, v2["ref"])
    assert node is not None and node.pdf == "sha256:" + drop and waiting(root) == []


def test_a_candidate_s_how_is_the_identifier_it_states_too(tmp_path: Path) -> None:
    """`how` is the identifier, which the viewer words; the work a file was dropped on, stating none of them, has none."""
    root = quilt(tmp_path)
    [held] = rows(root, Item(text="arXiv:2401.01234v1"))
    [plain] = rows(root, Item(text="@article{Smi24, title = {Widgets}}\n"))
    drop = dropped(root, "2401.01234v3.pdf", a_pdf(tmp_path, ["Widgets"]))
    [asked] = rows(root, Item(drop=drop, work=plain["ref"]))
    assert [(c["ref"], c["how"]) for c in asked["candidates"]] == [
        (plain["ref"], None),
        (held["ref"], "arxiv:2401.01234v3"),
    ]
    assert waiting(root)[0]["candidates"] == asked["candidates"]


def filed_and_off(tmp_path: Path, name: str = "smith-widgets.pdf") -> tuple[Path, str, str, dict[str, Any]]:
    """A quilt whose one work had a PDF dropped on it and taken off again: the quilt, the work, the drop, and what `unfile` answered."""
    root = quilt(tmp_path)
    [work] = rows(root, Item(text="@article{Smi24, title = {Widgets}}\n"))
    drop = dropped(root, name, a_pdf(tmp_path, ["w"]))
    rows(root, Item(drop=drop, work=work["ref"]))
    return root, work["ref"], drop, unfile(root, work["ref"], **ME)


def test_a_drop_that_waits_again_is_a_received_row_as_arriving_lists_it(tmp_path: Path) -> None:
    """Unfile and undo answer the drop that waits again as `arriving` lists it, in a state of its own, never as a refusal."""
    root, ref, drop, off = filed_and_off(tmp_path)
    [listed] = waiting(root)
    assert off["row"] == listed and set(listed) == {"id", "item", "name", "state"} and listed["state"] == "received"
    [back] = rows(root, Item(drop=drop, work=ref))
    _, again = undo(root, drop, act=back["act"], **ME)
    assert again is not None and again.to_json() == waiting(root)[0] == listed


def test_a_drop_that_waits_again_keeps_its_name_and_the_works_it_is_not(tmp_path: Path) -> None:
    """What arrived with a drop stays while an act on it stands: an unfile and an undo say its own name, and its `not` holds."""
    root, ref, drop, off = filed_and_off(tmp_path)
    assert off["row"]["name"] == "smith-widgets.pdf"
    [back] = rows(root, Item(drop=drop, work=ref))
    _, again = undo(root, drop, act=back["act"], **ME)
    assert again is not None and again.name == "smith-widgets.pdf"
    assert json.loads((root / INCOMING / drop / "arrived.json").read_text())["not"] == [ref]
    # once the unfile is undone, the PDF on the work again, it is that work; the same bytes received again wait under the name they came with now
    undo(root, drop, act=off["act"], **ME)
    assert json.loads((root / INCOMING / drop / "arrived.json").read_text())["not"] == []
    assert dropped(root, "copy.pdf", a_pdf(tmp_path, ["w"])) == drop
    assert waiting(root) == [{"id": drop, "item": 0, "name": "copy.pdf", "state": "received"}]


def held_whole(root: Path) -> None:
    """Every document a reference names is in the store."""
    for ref, node in Library.read(root).refs.items():
        for which in ("pdf", "tex"):
            digest = getattr(node, which)
            assert digest is None or documents.held(root, digest, which), (ref, which)


@pytest.mark.parametrize(
    "acts",
    [
        ["unfile", "take-for"],
        ["unfile", "take"],
        ["unfile", "take-for", "unfile", "take-for"],
        ["unfile", "take", "unfile-new", "take-for"],
    ],
    ids=["filed-again", "a-work-of-its-own", "twice", "on-a-new-work-then-back"],
)
def test_every_undo_of_acts_on_one_drop_leaves_the_store_whole(tmp_path: Path, acts: list[str]) -> None:
    """The views session's 500: an unfile's undo after a take's undo found the store without the document. Each undo, last first, puts back what its act took, and the work ends with its PDF as before."""
    root, ref, drop, off = filed_and_off(tmp_path)
    done, new = [off["act"]], ""
    for act in acts[1:]:
        if act.startswith("unfile"):
            done.append(unfile(root, new if act == "unfile-new" else ref, **ME)["act"])
            continue
        [row] = rows(root, Item(drop=drop, work=ref if act == "take-for" else ""))
        assert row["state"] == "added", row
        done.append(row["act"])
        new = row["ref"]
    held_whole(root)
    for act in reversed(done):
        undo(root, drop, act=act, **ME)
        held_whole(root)
    node = read(root, ref)
    assert node is not None and node.pdf == "sha256:" + drop and documents.held(root, node.pdf, "pdf")
    assert waiting(root) == []


def test_an_unfile_s_undo_is_refused_in_a_sentence_when_its_document_is_gone(tmp_path: Path) -> None:
    """With the drop's file and the store's copy both gone, the undo says so and changes nothing."""
    root, ref, drop, off = filed_and_off(tmp_path)
    [back] = rows(root, Item(drop=drop, work=ref))
    undo(root, drop, act=back["act"], **ME)
    (root / INCOMING / drop / "document.pdf").unlink()
    with pytest.raises(IntakeRefused) as gone:
        undo(root, drop, act=off["act"], **ME)
    assert (gone.value.code, gone.value.message) == (
        "changed",
        "the PDF taken off Widgets is on this machine no more; drop it on Widgets again",
    )
    node = read(root, ref)
    assert node is not None and node.pdf is None


def test_a_row_filed_under_a_work_names_the_identifier_its_entry_states(tmp_path: Path) -> None:
    """`identifier` is the first identifier the work's entry states, as on a row that made the work."""
    root = quilt(tmp_path)
    [work] = rows(root, Item(text="@article{Smi24, title = {Widgets}, doi = {10.1000/w}}\n"))
    [row] = rows(root, Item(drop=dropped(root, "w.pdf", a_pdf(tmp_path, ["w"])), work=work["ref"]))
    assert (row["state"], row["under"], row["identifier"]) == ("added", True, "doi:10.1000/w")


# ---- a paste taken back ----------------------------------------------------------------------------------------------


def test_a_pasted_work_is_taken_out_again_as_a_drop_s_add_is(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    first, second = rows(root, Item(text="arXiv:2209.01234v2\n10.1000/w.1"))
    assert first["act"] and second["act"] and first["act"] != second["act"]
    said, waits = undo(root, first["id"], act=first["act"], **ME)
    assert said == "arXiv:2209.01234v2 was taken out again" and waits is None and read(root, first["ref"]) is None
    assert log.replay(root).of(first["ref"])[-1]["event"] == "undone"
    assert not (root / INCOMING / first["id"]).exists()
    with pytest.raises(IntakeRefused) as again:
        undo(root, first["id"], act=first["act"], **ME)
    assert again.value.code == "no-such-intake"
    # refused, as a drop's add is, once the work has results or has changed
    node = read(root, second["ref"])
    assert node is not None
    write_node(root, Node(id="tq-0009", taxon="lemma", source=second["ref"], body="A lemma.\n"))
    with pytest.raises(IntakeRefused) as results:
        undo(root, second["id"], act=second["act"], **ME)
    assert results.value.code == "not-new"
    (root / ".loom/library/nodes/tq-0009.node").unlink()
    write_node(root, replace(node, body=node.body.replace("10.1000/w.1", "10.1000/w.2")))
    with pytest.raises(IntakeRefused) as changed:
        undo(root, second["id"], act=second["act"], **ME)
    assert changed.value.code == "changed" and read(root, second["ref"]) is not None
    # an entry of a dropped .bib is taken back the same way
    [entry] = rows(root, Item(drop=dropped(root, "refs.bib", b"@article{Bib1, title={B}}\n")))
    undo(root, entry["id"], act=entry["act"], **ME)
    assert read(root, entry["ref"]) is None


# ---- a drop refused --------------------------------------------------------------------------------------------------


def test_a_drop_refused_goes_but_one_refused_has_document_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`has-document` waits, since once the work's own is taken off the same take files it; a drop whose entry the checks refuse goes, as every other refused drop, since taking it again would say the same."""
    import loom.library.intake as intake

    root, ref, _, _ = filed_and_off(tmp_path)
    rows(root, Item(drop=dropped(root, "a.pdf", a_pdf(tmp_path, ["a"])), work=ref))
    later = dropped(root, "b.pdf", a_pdf(tmp_path, ["b"]))
    [row] = rows(root, Item(drop=later, work=ref))
    assert (row["state"], row["code"], row["why"]) == (
        "cannot",
        "has-document",
        "Widgets holds a PDF already; take it off first",
    )
    assert {"id": later, "item": 0, "name": "b.pdf", "state": "received"} in waiting(root)
    unfile(root, ref, **ME)
    [filed] = rows(root, Item(drop=later, work=ref))
    assert filed["state"] == "added"

    def refused(*_a: Any, **_k: Any) -> Node:
        raise NodeRefused([])

    monkeypatch.setattr(intake, "make", refused)
    gone = dropped(root, "c.pdf", a_pdf(tmp_path, ["c"]))
    [no] = rows(root, Item(drop=gone))
    assert (no["state"], no["code"]) == ("cannot", "refused")
    assert not (root / INCOMING / gone).exists() and gone not in {w["id"] for w in waiting(root)}


# ---- a fixed clock ---------------------------------------------------------------------------------------------------


def test_under_a_fixed_clock_two_runs_answer_alike(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LOOM_FIXED_TIME holds still the works list's generation and the ids of acts, questions and undos, as it holds loom's other ids, so a fixture made twice is the same."""
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-09-19T09:00:00Z")

    def run(where: Path) -> list[Any]:
        where.mkdir()
        root = quilt(where)
        [pasted] = rows(root, Item(text="arXiv:2401.01234v1"))
        [asked] = rows(root, Item(drop=dropped(root, "2401.01234v3.pdf", a_pdf(where, ["x"]))))
        own = answer(root, asked["question"], None, **ME)
        [again] = rows(root, Item(drop=dropped(root, "2401.01234v4.pdf", a_pdf(where, ["y"]))))
        undone = delete(root, pasted["ref"], by="A. Author", kind="person")
        return [
            pasted["act"],
            own.act,
            asked["question"],
            again["question"],
            undone,
            generation(scan(load_quilt(root))),
        ]

    first = run(tmp_path / "a")
    assert first == run(tmp_path / "b")
    assert first[-1] == 1789808400000, "the fixed time, in milliseconds"
    assert first[2] != first[3], "a question's id, its record gone once answered, is not drawn again for another drop"


def test_the_drops_that_wait_are_listed_oldest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`arriving` lists the drops in the order they came, as the manifest says, not by their bytes' hash."""
    root = quilt(tmp_path)
    for day, name in (("03", "third.pdf"), ("01", "first.pdf"), ("02", "second.pdf")):
        monkeypatch.setenv("LOOM_FIXED_TIME", f"2026-01-{day}T09:00:00Z")
        dropped(root, name, a_pdf(tmp_path, [name], name))
    assert [row["name"] for row in waiting(root)] == ["first.pdf", "second.pdf", "third.pdf"]


def test_a_write_s_result_names_the_work_as_a_person_reads_it(tmp_path: Path) -> None:
    """The sentence a write answers with names a work by its short name, never by its reference's id."""
    from loom.render.api import handle

    root, ref, _drop, _off = filed_and_off(tmp_path)
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\n\n[author]\nname = "A. Author"\n')
    said = [
        handle(
            root,
            "library-entry",
            {"ref": ref, "bibtex": "@article{Smi24, author = {Smith, Jane}, title = {Widgets}, year = {2024}}\n"},
        )["result"],
        handle(root, "library-delete", {"ref": ref})["result"],
    ]
    assert said == ["rewrote the entry of Smith 2024", "deleted Smith 2024"], said
    assert not any(ref in s for s in said)
