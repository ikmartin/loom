"""Adoption and a pull are each one act through the door (`docs/design/writes.md`, "Records an act writes"): the person's files and loom's records of them land together or not at all, and a crash is finished or put back whole."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import loom.sync as sync
from loom import writes
from loom.adopt import incorporate, prepare
from loom.history.ledger import append_entry, load_history
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from loom.sync import SyncError, SyncState, fetch
from tests.unit.test_adopt import COPY, DOC, TEXT, made
from tests.unit.test_adopt import edit as edit_copy
from tests.unit.test_sync import SOURCE, colleague, compiled, edit, paired, renamed_pair, run  # noqa: F401
from tests.unit.test_write_safety import Died, dying_before_the_rename

ORIGINS = ".loom/records/review-origins.json"


def acts(root: Path) -> list[dict]:
    """The journal's lines, in order."""
    p = root / ".loom/local/writes.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines()] if p.is_file() else []


def begun(root: Path) -> list[dict]:
    return [e for e in acts(root) if e["event"] == "begin"]


def steps(q) -> list[str]:  # type: ignore[no-untyped-def]
    """The history's step folders."""
    return sorted(p.name for p in q.history_dir.iterdir() if p.is_dir() and p.name != "texts")


def ready(tmp_path: Path, text: str = TEXT):  # type: ignore[no-untyped-def]
    """A quilt whose agent's copy proposes a new first statement, and the token of its preview."""
    q = made(tmp_path, text)
    edit_copy(q, "First statement.", "Proposal.")
    return q, prepare(scan(q), COPY)["token"]


def recovered(q) -> list[str]:  # type: ignore[no-untyped-def]
    return writes.recover(q.root, q.history_dir)


# ---- the door's part ----------------------------------------------------------------------------------------------


def test_a_staging_act_whose_history_moved_on_before_its_commit_writes_nothing(tmp_path: Path) -> None:
    """A history line planned in an act lands only where it was planned: another writer recording a step before the commit puts the act back, its person's file with it."""
    q = made(tmp_path, TEXT)
    ledger = q.history_dir / "ledger.jsonl"
    with pytest.raises(writes.WriteRefused, match="recorded another step"):
        with writes.act(q.root, q.history_dir, "adopt", "Tester") as w, writes.staging(w):
            w.replace(DOC, b"replaced\n")
            append_entry(q.history_dir, "move", {"from": "a.tex", "to": "b.tex", "moved": False}, "Tester")
            assert len(load_history(q.history_dir).entries) == 2  # the staged line is read with the ledger's own
            with ledger.open("a", encoding="utf-8") as fh:  # another process records a step meanwhile
                fh.write(json.dumps({"when": "now", "actor": None, "action": "note", "text": "x"}) + "\n")
    assert (q.root / DOC).read_text() == TEXT
    assert [e["event"] for e in acts(q.root)] == ["begin", "aborted"]
    assert [e.action for e in load_history(q.history_dir).entries] == ["copy", "note"]


def test_an_act_opened_inside_a_staging_act_joins_it(tmp_path: Path) -> None:
    q = made(tmp_path, TEXT)
    with writes.act(q.root, q.history_dir, "pull", "Tester") as w, writes.staging(w):
        w.replace(DOC, b"replaced\n")
        with writes.act(q.root, q.history_dir, "settings", "Tester") as inner:
            assert inner is w
            inner.replace("config.toml", (q.root / "config.toml").read_bytes() + b"# joined\n")
    (act,) = begun(q.root)
    assert act["kind"] == "pull" and set(act["files"]) == {DOC, "config.toml"}


# ---- adoption --------------------------------------------------------------------------------------------------------


def test_an_adoption_is_one_act_that_writes_the_document_and_its_records_together(tmp_path: Path) -> None:
    q, token = ready(tmp_path)
    before = steps(q)
    done = incorporate(scan(q), COPY, token)
    (act,) = begun(q.root)
    assert act["kind"] == "adopt" and [e["event"] for e in acts(q.root)] == ["begin", "done"]
    files = set(act["files"])
    assert DOC in files and ORIGINS in files
    made_steps = [s for s in steps(q) if s not in before]
    assert len(made_steps) == 2 and all(
        any(f.startswith(f"{q.config.history}/{s}/") for f in files) for s in made_steps
    )
    # the history's lines are guarded: each lands right after the lines the history held when it was planned
    lines = [r for r in act["records"] if r["log"].endswith("history/ledger.jsonl")]
    assert [json.loads(r["line"])["action"] for r in lines] == ["stamp", "adopt"]
    assert all("at" in r for r in lines) and lines[0]["at"] == len(load_history(q.history_dir).entries) - 2
    assert "Proposal." in (q.root / DOC).read_text() and done["landmark"]


def test_an_adoption_cut_short_between_its_files_is_put_back_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, token = ready(tmp_path)
    ledger = (q.history_dir / "ledger.jsonl").read_bytes()
    before = steps(q)
    restore = dying_before_the_rename(monkeypatch, after=2)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    restore()
    said = recovered(q)
    assert said and said[0].startswith("undid adopt:")
    assert (q.root / DOC).read_text() == TEXT
    assert (q.history_dir / "ledger.jsonl").read_bytes() == ledger
    assert steps(q) == before, "a step's folder emptied by the put-back is removed with it"
    assert not (q.root / ORIGINS).exists()
    # nothing is left for the person: the preview is still there, and taking the copy in again works
    incorporate(scan(q), COPY, token)
    assert "Proposal." in (q.root / DOC).read_text()


def test_an_adoption_cut_short_after_its_files_is_finished_by_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, token = ready(tmp_path)
    n = len(load_history(q.history_dir).entries)

    def die(*_a: object, **_k: object) -> None:
        raise Died

    monkeypatch.setattr(writes, "_append_guarded", die)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    assert len(load_history(q.history_dir).entries) == n  # the files are written, the history's lines are not
    said = recovered(q)
    assert said and said[0].startswith("finished adopt:")
    assert [e.action for e in load_history(q.history_dir).entries[n:]] == ["stamp", "adopt"]
    assert "Proposal." in (q.root / DOC).read_text() and (q.root / ORIGINS).is_file()
    assert load_history(q.history_dir).unrecorded_dirs() == []


def test_an_adoption_cut_short_is_put_back_once_the_history_has_moved_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another step recorded before recovery runs takes the number the act's lines were planned for: the act cannot be finished, so it is put back, and the other step stays."""
    q, token = ready(tmp_path)
    before = steps(q)

    def die(*_a: object, **_k: object) -> None:
        raise Died

    monkeypatch.setattr(writes, "_append_guarded", die)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    append_entry(q.history_dir, "move", {"from": "a.tex", "to": "b.tex", "moved": False}, "Tester")
    said = recovered(q)
    assert said and said[0].startswith("undid adopt:")
    assert (q.root / DOC).read_text() == TEXT and steps(q) == before
    assert [e.action for e in load_history(q.history_dir).entries][-1] == "move"


def test_a_document_saved_since_its_preview_is_not_written(tmp_path: Path) -> None:
    q, token = ready(tmp_path)
    saved = TEXT.replace("Original introduction.", "The person's own introduction.")
    (q.root / DOC).write_text(saved)
    with pytest.raises(SyncError, match="changed since this preview"):
        incorporate(scan(q), COPY, token)
    assert (q.root / DOC).read_text() == saved and begun(q.root) == []


def test_an_adoption_keeps_the_document_s_line_endings(tmp_path: Path) -> None:
    q, token = ready(tmp_path, TEXT.replace("\n", "\r\n"))
    incorporate(scan(q), COPY, token)
    data = (q.root / DOC).read_bytes()
    assert b"Proposal." in data and data.count(b"\r\n") == data.count(b"\n")


def test_an_adoption_into_a_document_that_is_not_utf8_is_refused(tmp_path: Path) -> None:
    """Loom has no reading of a Latin-1 file in which to write a merge, so the act refuses it whole (`not-utf8`) and writes nothing, as Keep does."""
    q, token = ready(tmp_path, TEXT.replace("Original introduction.", "Introduction r\u00e9sum\u00e9."))
    latin = (q.root / DOC).read_text().encode("latin-1")
    (q.root / DOC).write_bytes(latin)
    token = prepare(scan(q), COPY)["token"]
    with pytest.raises(writes.WriteRefused) as refused:
        incorporate(scan(q), COPY, token)
    assert refused.value.code == "not-utf8"
    assert (q.root / DOC).read_bytes() == latin and begun(q.root) == []


# ---- a pull ----------------------------------------------------------------------------------------------------------


def pulled(tmp_path: Path):  # type: ignore[no-untyped-def]
    """A paired quilt with a colleague's edit of its main document fetched and not yet taken in."""
    root, bare = paired(tmp_path)
    edit(colleague(tmp_path, bare), "edit", {"main.tex": SOURCE.replace("zk-0001}A", "zk-0001}B")})
    q = load_quilt(root)
    return q, fetch(q, SyncState.read(root))


def test_a_pull_is_one_act(tmp_path: Path, compiled: list[str]) -> None:  # noqa: F811
    q, state = pulled(tmp_path)
    sync.incorporate(q, state)
    (act,) = [e for e in begun(q.root) if e["kind"] == "pull"]
    assert "drafting/main.tex" in act["files"] and ".loom/records/source-sync.json" in act["files"]
    assert [json.loads(r["line"])["action"] for r in act["records"]] == ["stamp"]
    assert "zk-0001}B" in (q.root / "drafting/main.tex").read_text()


def test_a_pull_that_moves_the_main_document_changes_the_config_in_the_same_act(
    tmp_path: Path,
    compiled: list[str],  # noqa: F811
) -> None:
    root, other = renamed_pair(tmp_path)
    run(other, "mv", "main.tex", "paper.tex")
    run(other, "commit", "-q", "-m", "rename")
    run(other, "push", "-q", "origin", "HEAD:master")
    q = load_quilt(root)
    sync.incorporate(q, fetch(q, SyncState.read(root)))
    kinds = [e["kind"] for e in begun(root)]
    assert kinds.count("pull") == 1 and "settings" not in kinds, kinds
    (act,) = [e for e in begun(root) if e["kind"] == "pull"]
    assert {"config.toml", "drafting/main.tex", "drafting/paper.tex"} <= set(act["files"])
    assert act["files"]["drafting/main.tex"][1] is None  # removed, in the same act
    assert 'main = "drafting/paper.tex"' in (root / "config.toml").read_text()


def test_a_pull_cut_short_between_its_files_is_put_back_whole(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compiled: list[str],  # noqa: F811
) -> None:
    q, state = pulled(tmp_path)
    record = (q.root / ".loom/records/source-sync.json").read_bytes()
    landmarks = len(load_history(q.history_dir).landmarks())
    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died):
        sync.incorporate(q, state)
    restore()
    said = recovered(q)
    assert said and said[0].startswith("undid pull:")
    assert (q.root / "drafting/main.tex").read_text() == SOURCE
    assert (q.root / ".loom/records/source-sync.json").read_bytes() == record
    assert len(load_history(q.history_dir).landmarks()) == landmarks
    assert load_history(q.history_dir).unrecorded_dirs() == []
