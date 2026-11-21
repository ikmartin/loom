"""The person's acts on a work (`library.acts`) and the works list (`library.works`): look-up, an edited entry, a delete never refused and restored whole, and each row's words."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library import log
from loom.library.acts import ActRefused, delete, edit_entry, look_up, restore
from loom.library.checks import check
from loom.library.intake import Item, take
from loom.library.node import Node
from loom.library.store import write_node
from loom.library.works import works
from loom.paths import LIBRARY_UNDO
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan

ME = {"by": "Isaac", "kind": "person"}


def quilt(tmp_path: Path) -> Path:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nBy \\cite{Smi24}.\n\\bibliography{refs}\n\\end{document}\n"
    )
    (root / "refs.bib").write_text(
        "@article{Smi24,\n  author = {Smith, Jane and Kova{\\v{c}}, Ivan},\n  title = {Widgets},\n  year = {2024},\n  eprint = {2401.01234},\n}\n"
    )
    load_quilt(root)
    return root


def the_ref(root: Path) -> str:
    [row] = works(scan(load_quilt(root)))
    return str(row["ref"])


def test_the_works_list_gathers_and_draws_each_work_in_words(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    [row] = works(scan(load_quilt(root)))
    assert {k: row[k] for k in ("short", "title", "authors", "year", "used_in", "link", "digested", "lookup")} == {
        "short": "Smith and Kovač 2024",
        "title": "Widgets",
        "authors": ["Smith", "Kovač"],
        "year": "2024",
        "used_in": ["main.tex"],
        "link": "https://arxiv.org/abs/2401.01234",
        "digested": None,
        "lookup": None,
    }
    write_node(root, Node(id="tq-0009", taxon="lemma", number="2.1", source=row["ref"]))
    [again] = works(scan(load_quilt(root)))
    assert again["digested"] == {"statements": 0, "of": None, "compared": 0, "stubs": 1}


def test_a_work_made_from_an_identifier_alone_reads_unconfirmed(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    take(root, [Item(text="arXiv:2209.01234v2")], by="Isaac")
    rows = {r["short"]: r for r in works(scan(load_quilt(root)))}
    [unconfirmed] = [r for r in rows.values() if r["lookup"]]
    assert unconfirmed["lookup"] == {"state": "unconfirmed", "identifier": "arXiv 2209.01234v2"}


def test_an_edited_entry_is_written_and_recorded_and_refused_when_bad(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    ref = the_ref(root)
    node = edit_entry(root, ref, "@article{Smi24, title = {Widgets, corrected}}", **ME)
    assert "corrected" in node.body and log.replay(root).of(ref)[-1]["event"] == "edited"
    with pytest.raises(ActRefused) as bad:
        edit_entry(root, ref, "not bibtex", **ME)
    assert (bad.value.code, bad.value.status) == ("bad-entry", 400)
    take(root, [Item(text="@book{Other, title = {x}}\n")], by="Isaac")
    with pytest.raises(ActRefused) as taken:
        edit_entry(root, ref, "@article{other, title = {x}}", **ME)
    assert taken.value.code == "key-taken"


def test_a_look_up_writes_what_it_found_unless_the_entry_was_edited(tmp_path: Path) -> None:
    from tests.unit.refs.test_lookup import ATOM, fake

    root = quilt(tmp_path)
    ref = the_ref(root)
    edit_entry(root, ref, "@article{Smi24, title = {Mine}, eprint = {0805.2065}}", **ME)
    node = look_up(root, ref, http=fake({"https://export.arxiv.org/api/query": ATOM}), **ME)
    assert "Mine" in node.body, "an edited entry is the person's"
    assert log.replay(root).of(ref)[-1] == {**log.replay(root).of(ref)[-1], "event": "looked-up", "found": True}
    with pytest.raises(ActRefused) as none:
        edit_entry(root, ref, "@article{Smi24, title = {No identifier}}", **ME)
        look_up(root, ref, **ME)
    assert none.value.code == "no-identifier"


def test_a_delete_takes_the_work_its_results_and_notes_and_is_never_refused(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    ref = the_ref(root)
    stem = ref.removesuffix("-ref")
    write_node(root, Node(id=f"{stem}-macros", taxon="macros", body="\\newcommand{\\x}{y}\n"))
    write_node(root, Node(id="tq-0009", taxon="lemma", source=ref, body="A lemma.\n"))
    write_node(root, Node(id="tq-0009-proof00", taxon="proof", body="By hand.\n"))
    write_node(root, Node(id="tq-000A", taxon="remark", body="Uses it.\n", uses=("tq-0009",)))
    before = {p.name: p.read_bytes() for p in (root / ".loom/library/nodes").iterdir()}
    undo = delete(root, ref, **ME)
    left = sorted(p.name for p in (root / ".loom/library/nodes").iterdir())
    assert left == ["tq-000A.node"], "the cited work goes though a draft cites it, and its results with it"
    assert [d.code for d in check(root)] == ["loom:node-edge"], "what used its results says so"
    assert log.replay(root).deleted_keys() == {"Smi24"}
    assert works(scan(load_quilt(root))) == [], "gathering does not make it again"
    assert restore(root, undo, **ME) == ref
    assert {p.name: p.read_bytes() for p in (root / ".loom/library/nodes").iterdir()} == before
    assert not (root / LIBRARY_UNDO / undo).exists()
    with pytest.raises(ActRefused) as again:
        restore(root, undo, **ME)
    assert again.value.code == "no-such-undo"


def test_a_restore_is_refused_when_a_node_was_written_again_since(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    ref = the_ref(root)
    undo = delete(root, ref, **ME)
    (root / ".loom/library/nodes" / f"{ref}.node").write_text("+++\nother\n")
    with pytest.raises(ActRefused) as changed:
        restore(root, undo, **ME)
    assert changed.value.code == "changed"
