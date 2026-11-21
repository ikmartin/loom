"""The person's acts on a work (`library.acts`) and the works list (`library.works`): look-up, an edited entry, a delete never refused and restored whole, and each row's words."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library import log
from loom.library.acts import ActRefused, delete, edit_entry, look_up, restore
from loom.library.checks import check
from loom.library.gather import gather
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
    # gathered, as a build gathers: the works list reads the library and makes nothing
    gather(scan(load_quilt(root)))
    return root


def the_ref(root: Path) -> str:
    [row] = works(scan(load_quilt(root)))
    return str(row["ref"])


def test_the_works_list_draws_each_work_in_words(tmp_path: Path) -> None:
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
    assert unconfirmed["lookup"] == {"state": "unconfirmed", "identifier": "arxiv:2209.01234v2"}


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


@pytest.mark.parametrize(
    ("bibtex", "code", "said"),
    [
        (
            "@article{Smi24, title = {Widgets}, journal = jfoo}",
            "bad-entry",
            "Smi24: its journal is jfoo, an abbreviation no @string in the entry defines; write it out in braces instead",
        ),
        (
            "@article{STRASSE1, title = {Widgets}}",
            "key-taken",
            "has the key STRASSE1 already; give this entry another key",
        ),
        ("@article{Smi24, title = {Widgets}} and more", "bad-entry", "Smi24 has more after its closing brace"),
    ],
)
def test_an_edited_entry_is_refused_in_words_about_the_entry_never_loom_s_files(
    tmp_path: Path, bibtex: str, code: str, said: str
) -> None:
    """M-8 for the work's tab: the key held in another case, as check 9 folds it, is the other work's, named by its short name."""
    root = quilt(tmp_path)
    ref = the_ref(root)
    take(root, [Item(text="@book{Straße1, author = {Weg, Anna}, title = {Streets}, year = {2020}}\n")], by="Isaac")
    with pytest.raises(ActRefused) as refused:
        edit_entry(root, ref, bibtex, **ME)
    assert refused.value.code == code and said in refused.value.message, refused.value.message
    assert ".node" not in refused.value.message and "-ref" not in refused.value.message


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
    again = gather(scan(load_quilt(root)))
    assert again.made == [] and again.deleted == ["Smi24"], "gathering does not make it again"
    assert works(scan(load_quilt(root))) == []
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


# A delete is one act, whole or finished after a kill, and its restore puts back the notes where they stood


def held(tmp_path: Path) -> tuple[Path, str]:
    """A quilt whose one work has a macros node, a lemma read from it with a proof, and notes on the work and the lemma among notes on other things, a reply among them; the log's lines written with their keys unsorted, as a hand or another tool might."""
    import json

    from loom.records.log import log_path

    root = quilt(tmp_path)
    ref = the_ref(root)
    stem = ref.removesuffix("-ref")
    write_node(root, Node(id=f"{stem}-macros", taxon="macros", body="\\newcommand{\\x}{y}\n"))
    write_node(root, Node(id="tq-0009", taxon="lemma", source=ref, body="A lemma.\n"))
    write_node(root, Node(id="tq-0009-proof00", taxon="proof", body="By hand.\n"))
    who = {"when": "2026-11-20T00:00:00Z", "author": "Isaac", "kind": "human", "type": "question"}
    events = [
        {"event": "created", "id": "a-2026-11-20-aaaaaa", "target": "tq-0001", "body": "Elsewhere.", **who},
        {"event": "created", "id": "a-2026-11-20-bbbbbb", "target": ref, "body": "On the work.", **who},
        {"event": "created", "id": "a-2026-11-20-cccccc", "target": "tq-0002", "body": "Elsewhere too.", **who},
        {"event": "replied", "id": "a-2026-11-20-dddddd", "reply_to": "a-2026-11-20-bbbbbb", "body": "A reply.", **who},
        {"event": "created", "id": "a-2026-11-20-eeeeee", "target": "tq-0009", "body": "On its lemma.", **who},
        {"event": "edited", "id": "a-2026-11-20-aaaaaa", "body": "Elsewhere, restated.", **who},
    ]
    p = log_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return root, ref


def kept(root: Path) -> dict[str, bytes]:
    """The library's nodes and the annotation log, byte for byte."""
    from loom.records.log import log_path

    out = {p.name: p.read_bytes() for p in (root / ".loom/library/nodes").glob("*.node")}
    return {**out, "annotations": log_path(root).read_bytes()}


def deleted_whole(root: Path, ref: str, undo: str) -> None:
    """What a finished delete leaves: none of the work's nodes or notes, its `deleted` recorded once, and a store no node of it is left in to be an orphan."""
    from loom.records.log import replay as replay_notes

    left = sorted(p.name for p in (root / ".loom/library/nodes").glob("*.node"))
    assert left == [], left
    records, _ = replay_notes(root)
    assert sorted(a.id for r in records for a in r.annotations) == ["a-2026-11-20-aaaaaa", "a-2026-11-20-cccccc"]
    assert [a.get("undo") for a in log.replay(root).of(ref) if a["event"] == "deleted"] == [undo]
    assert check(root) == [] and not (root / ".loom/local/library-undo/deleting").exists()


def test_a_delete_and_its_restore_leave_the_annotation_log_as_it_was(tmp_path: Path) -> None:
    root, ref = held(tmp_path)
    before = kept(root)
    undo = delete(root, ref, **ME)
    deleted_whole(root, ref, undo)
    assert restore(root, undo, **ME) == ref
    assert kept(root) == before, "every node and every line of the log where it stood"


def _cut(monkeypatch: pytest.MonkeyPatch, owner: object, name: str, *, after: bool = True) -> None:
    """Interrupt the act once at `owner.name`, after or before it runs, as a Ctrl-C or a kill does: nothing of the act's own is undone."""
    real = getattr(owner, name)
    count = {"n": 0}

    def cut(*args: object, **kw: object) -> object:
        count["n"] += 1
        if count["n"] == 1 and not after:
            raise KeyboardInterrupt
        out = real(*args, **kw)
        if count["n"] == 1:
            raise KeyboardInterrupt
        return out

    monkeypatch.setattr(owner, name, cut)


@pytest.mark.parametrize(
    ("where", "name", "after"),
    [
        ("undo written", "_keep", True),
        ("notes taken out", "_rewrite", True),
        ("deleted recorded", "record", True),
        ("first node removed", "remove_node", True),
        ("every node removed", "_done", False),
    ],
)
def test_a_delete_cut_short_after_its_undo_is_finished_by_the_next_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, where: str, name: str, after: bool
) -> None:
    import loom.library.acts as acts
    import loom.records.log as notes
    from loom.library.store import remove_node

    root, ref = held(tmp_path)
    before = kept(root)
    owner = {"_rewrite": notes, "record": acts.log}.get(name, acts)
    _cut(monkeypatch, owner, name, after=after)
    with pytest.raises(KeyboardInterrupt):
        delete(root, ref, **ME)
    monkeypatch.undo()
    [undo] = [p.name for p in (root / LIBRARY_UNDO).glob("u-*")]
    assert (root / LIBRARY_UNDO / "deleting").read_text().strip() == undo, where
    assert remove_node(root, "tq-0ZZZ") is False  # the next writer, writing nothing of the work's
    deleted_whole(root, ref, undo)
    assert restore(root, undo, **ME) == ref
    assert kept(root) == before, where


def test_a_delete_cut_short_while_writing_its_undo_leaves_the_work_and_its_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import loom.library.acts as acts

    root, ref = held(tmp_path)
    before = kept(root)
    _cut(monkeypatch, acts, "_flushed")
    with pytest.raises(KeyboardInterrupt):
        delete(root, ref, **ME)
    monkeypatch.undo()
    assert kept(root) == before and not [p for p in (root / LIBRARY_UNDO).glob("u-*")]
    undo = delete(root, ref, **ME)
    deleted_whole(root, ref, undo)
    assert [p.name for p in (root / LIBRARY_UNDO).iterdir()] == [undo], "the half-written undo is cleared"


@pytest.mark.parametrize("name", ["_flushed", "put_back", "record"])
def test_a_restore_cut_short_finishes_when_run_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    import loom.library.acts as acts
    import loom.records.log as notes

    root, ref = held(tmp_path)
    before = kept(root)
    undo = delete(root, ref, **ME)
    _cut(monkeypatch, {"put_back": notes, "record": acts.log}.get(name, acts), name)
    with pytest.raises(KeyboardInterrupt):
        restore(root, undo, **ME)
    monkeypatch.undo()
    assert restore(root, undo, **ME) == ref
    assert kept(root) == before, name
    assert [a["event"] for a in log.replay(root).of(ref)].count("restored") == 1
    assert not (root / LIBRARY_UNDO / undo).exists()


def test_two_restores_of_one_undo_at_once_give_one_restore_and_one_no_such_undo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    import time

    import loom.library.acts as acts

    root, ref = held(tmp_path)
    undo = delete(root, ref, **ME)
    real = acts.log.record

    def slow(*args: object, **kw: object) -> object:
        time.sleep(0.3)  # the first restore is still at work when the second asks
        return real(*args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(acts.log, "record", slow)
    said: list[str] = []
    start = threading.Barrier(2)

    def one() -> None:
        start.wait()
        try:
            said.append(restore(root, undo, **ME))
        except ActRefused as exc:
            said.append(exc.code)

    threads = [threading.Thread(target=one) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(said) == sorted([ref, "no-such-undo"])
    assert [a["event"] for a in log.replay(root).of(ref)].count("restored") == 1
