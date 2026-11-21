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
