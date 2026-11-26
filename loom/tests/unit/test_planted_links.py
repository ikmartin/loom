"""Loom's own writers never write or remove through a link planted in their path: a folder of `.loom/` or the history made a link to a folder outside the quilt holding a canary, or a file of loom's made a link to the canary itself. Each writer refuses or writes nothing, and the folder outside keeps its canary and gains nothing."""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from loom import (
    gitignore,
    layout,
    locks,
    looks,
    mailbox,
    overleaf,
    own,
    presence,
    review_origins,
    review_queue,
    sessions,
    since,
    writes,
)
from loom.ai import layout as ai_layout
from loom.history import ledger as hledger
from loom.library import acts, documents, drawn, intake, store, survey, tags
from loom.library import log as llog
from loom.mcp import server as mcp_server
from loom.paths import (
    AI,
    ANNOTATION_LOG,
    ANNOTATION_TYPES,
    DRAWN_RUN,
    EDIT_LOG,
    HISTORY,
    INCOMING,
    LEDGER,
    LIBRARY_CACHE,
    LIBRARY_DOCUMENTS,
    LIBRARY_LOG,
    LIBRARY_NODES,
    LIBRARY_UNDO,
    LOCAL,
    LOOM_GITIGNORE,
    NODE_INDEX,
    RECORDS,
    REVIEW_DECISIONS,
    REVIEW_ORIGINS,
    SCRATCH,
    SITE,
    SITE_SVG,
    SURVEY_RUN,
    TAG_LOG,
)
from loom.records import edits, ledger, snapshots, types
from loom.records import log as alog
from loom.render import assets, publish
from tests.unit.library.test_store import _pair


@pytest.fixture
def q(tmp_path: Path) -> tuple[Path, Path]:
    """A quilt with an empty `.loom/` and history, and a folder outside it holding a canary file."""
    from loom.cli.quilt import write_minimal_quilt

    root = tmp_path / "q"
    root.mkdir()
    write_minimal_quilt(root, "q", readme=False)
    (root / RECORDS).mkdir(parents=True, exist_ok=True)
    (root / LOCAL).mkdir(parents=True, exist_ok=True)
    out = tmp_path / "outside"
    out.mkdir()
    (out / "canary").write_text("canary\n")
    return root, out


def untouched(out: Path) -> bool:
    """The folder outside holds its canary as it was, and nothing else, in any folder below it."""
    return (
        sorted(p.relative_to(out).as_posix() for p in out.rglob("*")) == ["canary"]
        and (out / "canary").read_text() == "canary\n"
    )


def plant(root: Path, rel: str, out: Path) -> None:
    """Make `rel` a link to `out`, setting aside whatever stood there."""
    p = root / rel
    if p.is_dir() and not p.is_symlink():
        p.rename(p.with_name(p.name + ".aside"))
    elif p.exists() or p.is_symlink():
        p.unlink()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.symlink_to(out)


def run(fn: Callable[[], object]) -> None:
    """Call a writer that meets a planted link: it may refuse, as every one here does, or write nothing."""
    with contextlib.suppress(Exception):
        fn()


def _event() -> dict[str, object]:
    return {"event": "created", "id": "a-1", "when": "2026-01-01T00:00:00Z"}


#: Each record writer, by what it writes, with the folder of `.loom/` or the history a link is planted at in its path.
RECORD_WRITERS: dict[str, tuple[str, Callable[[Path], object]]] = {
    "the history's text store": (f"{HISTORY}/texts", lambda r: writes.store(r / HISTORY, b"agent's note\n")),
    "a snapshot": (
        f"{HISTORY}/texts",
        lambda r: snapshots.write_snapshot(r, "x", r / HISTORY),
    ),
    "the history's ledger": (HISTORY, lambda r: hledger.append_entry(r / HISTORY, "stamp", {}, "me")),
    "the annotation log": (RECORDS, lambda r: alog.append(r, _event())),
    "the edit log": (RECORDS, lambda r: edits.append(r, _event())),
    "the library's log": (
        RECORDS,
        lambda r: llog.record(r, "made", "w1", by="me", kind="person"),
    ),
    "the tag log": (f"{RECORDS}/tags", lambda r: tags._append(r, _event())),
    "the types": (RECORDS, lambda r: types.save_types(r, None)),
    "the review queue": (RECORDS, lambda r: review_queue._write(r, {}, "me")),
    "the review origins": (RECORDS, lambda r: review_origins.write(r, {})),
    "a look": (
        RECORDS,
        lambda r: looks._write(r, looks.Look("me", "now")),
    ),
    "the journal": (LOCAL, lambda r: writes._append_journal(r, {"event": "begin"})),
    "the journal's index": (LOCAL, lambda r: writes._save_index(r, writes.Journal())),
    "a lock": (LOCAL, lambda r: locks.locked(r / LOCAL / "x.lock").__enter__()),
    "the sessions' index": (".loom/agents", lambda r: sessions.append_event(r, _event())),
    "the active session": (".loom/agents", lambda r: sessions.set_active(r, "s1")),
    "a message": (".loom/agents", lambda r: mailbox.post(r, "s-1", "hi", "me")),
    "the ignore file": (".loom", lambda r: gitignore.write_loom_ignore(r)),
    "a since marker": (LOCAL, lambda r: since.write_marker(r, "me", since.Marker(when="now", seen=set()))),
    "a deletion kept for since": (LOCAL, lambda r: since.note_deletion(r, [{"to": "me", "id": "a-1"}], "you")),
    "the format number": (".loom", lambda r: layout.stamp(r)),
}


@pytest.mark.parametrize("what", sorted(RECORD_WRITERS))
def test_a_record_writer_writes_nothing_through_a_planted_folder_link(q: tuple[Path, Path], what: str) -> None:
    root, out = q
    where, fn = RECORD_WRITERS[what]
    plant(root, where, out)
    run(lambda: fn(root))
    assert untouched(out)


#: Each record file, a link planted at the file itself, and the writer that appends to it or writes it.
RECORD_FILES: dict[str, tuple[str, Callable[[Path], object]]] = {
    "the annotation log": (ANNOTATION_LOG, lambda r: alog.append(r, _event())),
    "the edit log": (EDIT_LOG, lambda r: edits.append(r, _event())),
    "the ledger": (LEDGER, lambda r: ledger.append_rows(r, [])),
    "the library's log": (
        LIBRARY_LOG,
        lambda r: llog.record(r, "made", "w1", by="me", kind="person"),
    ),
    "the tag log": (TAG_LOG, lambda r: tags._append(r, _event())),
    "the types": (ANNOTATION_TYPES, lambda r: types.save_types(r, None)),
    "the review queue": (REVIEW_DECISIONS, lambda r: review_queue._write(r, {}, "me")),
    "the review origins": (REVIEW_ORIGINS, lambda r: review_origins.write(r, {})),
    "the history's ledger": (
        f"{HISTORY}/ledger.jsonl",
        lambda r: hledger.append_entry(r / HISTORY, "stamp", {}, "me"),
    ),
    "the journal": (f"{LOCAL}/writes.jsonl", lambda r: writes._append_journal(r, {"event": "begin"})),
    "the ignore file": (LOOM_GITIGNORE, lambda r: gitignore.write_loom_ignore(r)),
}


@pytest.mark.parametrize("what", sorted(RECORD_FILES))
@pytest.mark.parametrize("dangling", [False, True])
def test_a_record_file_that_is_a_link_is_written_through_by_no_writer(
    q: tuple[Path, Path], what: str, dangling: bool
) -> None:
    root, out = q
    rel, fn = RECORD_FILES[what]
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.unlink(missing_ok=True)
    p.symlink_to(out / ("gone" if dangling else "canary"))
    run(lambda: fn(root))
    assert untouched(out)


def test_a_store_link_into_an_agent_app_s_folder_takes_no_text(q: tuple[Path, Path]) -> None:
    """The route the review found (R2-29): the history's `texts/` made a link to `.claude/agents/`, and an act's text stored through it, there a subagent."""
    root, _out = q
    agents = root / ".claude/agents"
    agents.mkdir(parents=True)
    plant(root, f"{HISTORY}/texts", agents)
    with pytest.raises(own.Planted):
        writes.store(root / HISTORY, b"---\nname: planted\n---\n")
    assert not list(agents.iterdir())


@pytest.mark.parametrize("inside", [False, True])
def test_an_act_writes_no_record_through_a_planted_link(q: tuple[Path, Path], inside: bool) -> None:
    """A person's act whose history step goes through a link planted at `.loom/records/history/steps`, to a folder outside the quilt or to an agent app's folder inside it: refused, and nothing written in either."""
    root, out = q
    if inside:
        out = root / ".claude/agents"
        out.mkdir(parents=True)
        (out / "canary").write_text("canary\n")
    (root / "notes").mkdir()
    (root / "notes/a.md").write_text("one\n")
    plant(root, f"{HISTORY}/steps", out)
    with pytest.raises(writes.WriteRefused), writes.act(root, root / HISTORY, "restore") as w:
        w.replace("notes/a.md", b"two\n")
        w.replace(f"{HISTORY}/steps/0001-x/files.json", b"{}\n")
    assert untouched(out) and (root / "notes/a.md").read_text() == "one\n"


def test_with_no_link_each_record_writer_writes_what_it_wrote_before(q: tuple[Path, Path]) -> None:
    """The writers moved onto `loom.own` write the same bytes where no link is planted."""
    root, _out = q
    d = writes.store(root / HISTORY, b"a\r\nb\n")
    assert (root / HISTORY / "texts" / f"{d.split(':')[1]}.md").read_bytes() == b"a\r\nb\n"
    alog.append(root, _event())
    alog.append(root, _event())
    assert (root / ANNOTATION_LOG).read_text().splitlines() == [json.dumps(_event(), sort_keys=True)] * 2
    hledger.append_entry(root / HISTORY, "stamp", {"x": 1}, "me")
    assert json.loads((root / HISTORY / "ledger.jsonl").read_text())["x"] == 1


# ---- the library: its nodes, documents, drops, acts and caches ------------------------------------------------------


def _library(tmp_path: Path) -> tuple[Path, Path]:
    """The library's quilt of nine nodes, and a folder outside it holding a canary and a folder of loom's names (`drawn/run/keep`, `survey/run/keep`), which a removal through a link would take."""
    from tests.unit.library._store import quilt

    root = quilt(tmp_path)
    out = tmp_path / "outside"
    out.mkdir()
    (out / "canary").write_text("canary\n")
    return root, out


def _pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return p


LIBRARY_WRITERS: dict[str, tuple[str, Callable[[Path, Path], object]]] = {
    "a node written": (LIBRARY_NODES, lambda r, t: store.write_nodes(r, _pair())),
    "a node removed": (LIBRARY_NODES, lambda r, t: store.remove_node(r, "tq-00A4")),
    "the library's lock and a batch's record": (LOCAL, lambda r, t: store.write_nodes(r, _pair())),
    "a document kept": (LIBRARY_DOCUMENTS, lambda r, t: documents.put_pdf(r, _pdf(t))),
    "a source kept": (
        LIBRARY_DOCUMENTS,
        lambda r, t: documents.put_source(r, b"\\documentclass{article}\n", name="a.tex"),
    ),
    "a drop received": (INCOMING, lambda r, t: intake.receive(r, "a.pdf", io.BytesIO(b"%PDF-1.4\n"), 9)),
    "a delete's undo": (LIBRARY_UNDO, lambda r, t: acts._keep(r, "u-x", {"nodes": []})),
    "a drawing's run folder": (LIBRARY_CACHE, lambda r, t: drawn._scratch(r / DRAWN_RUN).__enter__()),
    "a survey's run folder": (LIBRARY_CACHE, lambda r, t: survey._scratch(r / SURVEY_RUN).__enter__()),
    "a survey kept": (
        LIBRARY_CACHE,
        lambda r, t: survey.keep(r, survey.Survey(tex="sha256:" + "0" * 64, main="a.tex")),
    ),
}


@pytest.mark.parametrize("what", sorted(LIBRARY_WRITERS))
def test_the_library_writes_and_removes_nothing_through_a_planted_link(tmp_path: Path, what: str) -> None:
    root, out = _library(tmp_path)
    where, fn = LIBRARY_WRITERS[what]
    for folder in ("drawn/run", "survey/run"):
        (out / folder).mkdir(parents=True)
        (out / folder / "keep").write_text("keep\n")
    plant(root, where, out)
    run(lambda: fn(root, tmp_path))
    for kept in ("drawn/run/keep", "survey/run/keep"):
        assert (out / kept).read_text() == "keep\n", kept
        (out / kept).unlink()
    for gone in ("drawn/run", "survey/run", "drawn", "survey"):
        (out / gone).rmdir()
    assert untouched(out)


def test_a_planted_link_where_the_node_index_belongs_goes_itself(tmp_path: Path) -> None:
    """SQLite opens the index by its path, so a link standing there is taken away before it opens, and its target is left."""
    from loom.library.index import NodeIndex

    root, out = _library(tmp_path)
    (root / NODE_INDEX).parent.mkdir(parents=True)
    (root / NODE_INDEX).symlink_to(out / "canary")
    with NodeIndex.open(root):
        pass
    assert untouched(out) and not (root / NODE_INDEX).is_symlink()


def test_with_no_link_the_library_writes_what_it_wrote_before(tmp_path: Path) -> None:
    root, _out = _library(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / LIBRARY_NODES).iterdir()}
    store.write_nodes(root, _pair())
    assert store.remove_node(root, "tq-0M02") and store.remove_node(root, "tq-0M01")
    assert {p.name: p.read_bytes() for p in (root / LIBRARY_NODES).iterdir()} == before
    d = documents.put_pdf(root, _pdf(tmp_path))
    assert documents.path_of(root, d, "pdf").read_bytes() == _pdf(tmp_path).read_bytes()


# ---- the agents' places, the build and this machine's part of the quilt ----------------------------------------------


def _picture(t: Path) -> Path:
    p = t / "pic.svg"
    p.write_text("<svg/>\n")
    return p


QUILT_WRITERS: dict[str, tuple[str, Callable[[Path, Path], object]]] = {
    "an agent's scratch": (SCRATCH, lambda r, t: mcp_server._keep(r, None, "x", "a large result\n")),
    "the agent layer's record": (AI, lambda r, t: ai_layout._write(r, f"{AI}/README.md", "x\n")),
    "the build's site": (SITE, lambda r, t: publish.write_atomic(r / SITE / "manifest.json", "{}")),
    "a picture published": (SITE, lambda r, t: assets.publish_picture(_picture(t), r / SITE_SVG)),
    "this machine's part of the mirror": (LOCAL, lambda r, t: overleaf._keep_here(r, who="me")),
    "the server's presence": (LOCAL, lambda r, t: presence.Presence(r, "test")._write()),
}


@pytest.mark.parametrize("what", sorted(QUILT_WRITERS))
def test_the_agents_places_and_the_build_take_no_write_through_a_planted_link(
    q: tuple[Path, Path], tmp_path: Path, what: str
) -> None:
    root, out = q
    where, fn = QUILT_WRITERS[what]
    plant(root, where, out)
    run(lambda: fn(root, tmp_path))
    assert untouched(out)


def test_a_mirror_s_clone_is_removed_through_no_link(q: tuple[Path, Path]) -> None:
    """Taking loom's clone away removes nothing of a folder a link on the way leads to."""
    root, out = q
    (out / "clone").mkdir()
    (out / "clone" / "keep").write_text("keep\n")
    plant(root, LOCAL, out)
    run(lambda: overleaf._remove(root / LOCAL / "clone"))
    assert (out / "clone" / "keep").read_text() == "keep\n"
