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
    by_hand(q)
    said = recovered(q)
    assert said and said[0].startswith("undid adopt:")
    assert (q.root / DOC).read_text() == TEXT and steps(q) == before
    assert [e.action for e in load_history(q.history_dir).entries][-1] == "move"


def by_hand(q) -> None:  # type: ignore[no-untyped-def]
    """A line put into the history by a writer that does not settle the journal first, as an older loom or a hand edit would."""
    import json as _json

    with (q.history_dir / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            _json.dumps(
                {
                    "when": "2026-11-21T00:00:00Z",
                    "actor": "Tester",
                    "action": "move",
                    "from": "a.tex",
                    "to": "b.tex",
                    "moved": False,
                }
            )
            + "\n"
        )


def recorded_folders_stand(q) -> bool:  # type: ignore[no-untyped-def]
    """Whether every step the ledger names has its folder, and every folder a step."""
    h = load_history(q.history_dir)
    return all((q.history_dir / e.dir).is_dir() for e in h.entries if e.dir) and h.unrecorded_dirs() == []


def test_a_stamp_after_a_crash_settles_the_act_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A command that draws an id holds the door's lock, and settles what a crash left before it reads the history, so its step is never numbered against an act in flight (D-1)."""
    from tests.helpers import ok

    q, token = ready(tmp_path)

    def die(*_a: object, **_k: object) -> None:
        raise Died

    monkeypatch.setattr(writes, "_append_guarded", die)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    said = ok("stamp", DOC, "-m", "between", cwd=q.root).stderr
    assert "finished adopt:" in said
    assert not writes.read_journal(q.root).begun
    assert [e.action for e in load_history(q.history_dir).entries][-3:] == ["stamp", "adopt", "stamp"]
    assert recorded_folders_stand(q)


def test_an_act_whose_history_lines_landed_and_were_followed_is_left_not_put_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Putting it back would leave its landed lines naming folders it removed: recovery leaves it, says so, and every line keeps its folder (D-1)."""
    q, token = ready(tmp_path)
    ledger_writes: list[Path] = []
    real = writes._append_line

    def second_dies(path: Path, text: str, full: bool = False) -> tuple[int, int]:
        if path.name == "ledger.jsonl":
            ledger_writes.append(path)
            if len(ledger_writes) == 2:
                raise Died
        return real(path, text, full)

    monkeypatch.setattr(writes, "_append_line", second_dies)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    by_hand(q)
    said = recovered(q)
    assert said and said[0].startswith("left adopt:") and "another step was recorded after them" in said[0]
    assert all((q.history_dir / e.dir).is_dir() for e in load_history(q.history_dir).entries if e.dir)
    ((_, _, _, settles),) = writes.left(q.root, q.history_dir)
    assert "settled by hand" in settles and "texts the history lacks" not in settles


def test_a_history_line_loom_writes_after_a_crash_settles_the_act_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every writer of the history from outside an act settles what a crash left first, as `loom live`, a draft closed and Keep all's line do through `append_entry`, so none leaves an act stuck (R-2), and says so, as a command that draws an id does."""
    q, token = ready(tmp_path)
    ledger_writes: list[Path] = []
    real = writes._append_line

    def second_dies(path: Path, text: str, full: bool = False) -> tuple[int, int]:
        if path.name == "ledger.jsonl":
            ledger_writes.append(path)
            if len(ledger_writes) == 2:
                raise Died
        return real(path, text, full)

    monkeypatch.setattr(writes, "_append_line", second_dies)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    capsys.readouterr()
    append_entry(q.history_dir, "live", {"path": "drafting/old.tex"}, "Tester")
    assert "loom: finished adopt:" in capsys.readouterr().err
    assert not writes.read_journal(q.root).begun
    assert [e.action for e in load_history(q.history_dir).entries][-3:] == ["stamp", "adopt", "live"]
    assert recorded_folders_stand(q)


@pytest.mark.parametrize("command", [("ai", "refresh", COPY), ("ai", "close", COPY, "--yes")])
def test_a_command_that_writes_a_history_line_after_a_crash_says_what_it_settled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: tuple[str, ...]
) -> None:
    """`loom ai refresh` and `loom ai close` settle an adoption cut between its two history lines before their own line, and say so on stderr, as a command that draws an id does."""
    from tests.helpers import ok

    q, token = ready(tmp_path)
    ledger_writes: list[Path] = []
    real = writes._append_line

    def second_dies(path: Path, text: str, full: bool = False) -> tuple[int, int]:
        if path.name == "ledger.jsonl":
            ledger_writes.append(path)
            if len(ledger_writes) == 2:
                raise Died
        return real(path, text, full)

    monkeypatch.setattr(writes, "_append_line", second_dies)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    monkeypatch.undo()
    assert "loom: finished adopt:" in ok(*command, cwd=q.root).stderr
    assert not writes.read_journal(q.root).begun and recorded_folders_stand(q)


def test_a_step_recorded_beside_a_left_act_takes_a_number_its_folders_do_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An act recovery must leave keeps its step folders; the next step is numbered past them, so no two folders carry one number (D-11)."""
    from tests.helpers import ok

    q, token = ready(tmp_path)
    restore = dying_before_the_rename(monkeypatch, after=2)
    with pytest.raises(Died):
        incorporate(scan(q), COPY, token)
    restore()
    (q.root / DOC).write_text(TEXT + "% the person's line\n", encoding="utf-8")
    said = ok("stamp", DOC, "-m", "mine", cwd=q.root).stderr
    assert "left adopt:" in said
    numbers = [name[:4] for name in steps(q)]
    assert len(numbers) == len(set(numbers)), steps(q)


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


def test_an_adoption_keeps_each_untouched_line_s_own_ending_in_a_mixed_file(tmp_path: Path) -> None:
    """A mostly-LF file with two CRLF lines away from the change: every byte but the change's is as it was (D-5)."""
    lines = TEXT.split("\n")
    crlf = [i for i, line in enumerate(lines[:-1]) if line and "First statement." not in line][:2]
    mixed = "".join(line + ("\r\n" if i in crlf else "\n") for i, line in enumerate(lines[:-1])) + lines[-1]
    q, token = ready(tmp_path, mixed)
    incorporate(scan(q), COPY, token)
    assert (q.root / DOC).read_bytes() == mixed.replace("First statement.", "Proposal.").encode("utf-8")


def test_an_adoption_over_a_file_deleted_since_its_scan_is_refused_and_brings_nothing_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The document deleted after the scan under the lock and before the act reads it: refused, not written again (D-14)."""
    q, token = ready(tmp_path)
    real = writes.Act.text
    gone: list[bool] = []

    def text(self: writes.Act, rel: str) -> str | None:
        if rel == DOC and not gone:
            gone.append(True)
            (q.root / DOC).unlink()
        return real(self, rel)

    monkeypatch.setattr(writes.Act, "text", text)
    with pytest.raises(SyncError, match="changed since loom read it"):
        incorporate(scan(q), COPY, token)
    assert not (q.root / DOC).exists()


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


def test_a_second_pull_of_one_revision_is_refused_as_taken_in_and_writes_nothing(
    tmp_path: Path,
    compiled: list[str],  # noqa: F811
) -> None:
    """Both read the record before either took the lock: the second reads it again under the lock and finds the revision taken in, rather than advising the person to remove what the first brought (D-7)."""
    q, state = pulled(tmp_path)
    stale = SyncState(**state.__dict__)
    sync.incorporate(q, state)
    text = (q.root / "drafting/main.tex").read_bytes()
    ledger = (q.history_dir / "ledger.jsonl").read_bytes()
    with pytest.raises(SyncError, match="taken in already"):
        sync.incorporate(q, stale)
    assert (q.root / "drafting/main.tex").read_bytes() == text
    assert (q.history_dir / "ledger.jsonl").read_bytes() == ledger


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


# ---- the other writers -----------------------------------------------------------------------------------------------


def test_a_move_is_one_act_with_its_history_line_and_the_config_s_main(tmp_path: Path) -> None:
    from tests.helpers import ok

    q = made(tmp_path, TEXT)
    ok("mv", DOC, "drafting/paper.tex", cwd=q.root)
    (act,) = [e for e in begun(q.root) if e["kind"] == "mv"]
    assert act["files"][DOC][1] is None and act["files"]["drafting/paper.tex"][0] is None
    assert "config.toml" in act["files"] and [r for r in begun(q.root) if r["kind"] == "settings"] == []
    (line,) = act["records"]
    assert json.loads(line["line"])["action"] == "move" and "at" in line
    assert (q.root / "drafting/paper.tex").read_text() == TEXT and not (q.root / DOC).exists()
    assert load_quilt(q.root).config.main == "drafting/paper.tex"


def test_the_root_gitignore_is_written_through_the_door(tmp_path: Path) -> None:
    from loom.gitignore import ensure

    q = made(tmp_path, TEXT)
    assert ensure(q.root)
    (act,) = begun(q.root)
    assert act["kind"] == "agents" and list(act["files"]) == [".gitignore"]


def test_a_file_named_outside_the_quilt_is_written_as_an_ordinary_file(tmp_path: Path) -> None:
    (tmp_path / "q").mkdir()
    q = made(tmp_path / "q", TEXT)
    out = tmp_path / "elsewhere" / "pull.diff"
    writes.save(q.root, q.history_dir, out, b"a patch\n", kind="patch")
    assert out.read_bytes() == b"a patch\n" and begun(q.root) == []
    writes.save(q.root, q.history_dir, q.root / "notes" / "pull.diff", b"inside\n", kind="patch")
    (act,) = begun(q.root)
    assert act["kind"] == "patch" and list(act["files"]) == ["notes/pull.diff"]


def test_the_door_refuses_a_file_that_is_not_a_regular_file_without_waiting_on_it(tmp_path: Path) -> None:
    import os

    q = made(tmp_path, TEXT)
    os.mkfifo(q.root / "drafting" / "pipe.tex")
    with pytest.raises(writes.WriteRefused) as refused:
        writes.put(q.root, None, "drafting/pipe.tex", b"text\n", kind="agents")
    assert refused.value.code == "not-a-file" and begun(q.root) == []


# ---- a write made from an earlier read (D-2) ---------------------------------------------------------------------


def saving_before_the_act(monkeypatch: pytest.MonkeyPatch, path: Path, line: bytes) -> None:
    """The person saves `path` the moment loom's act opens: after loom's writer read it, before the act reads it under the lock."""
    real = writes.act
    done: list[bool] = []

    def act(*a: object, **k: object):  # type: ignore[no-untyped-def]
        if not done:
            done.append(True)
            path.write_bytes((path.read_bytes() if path.exists() else b"") + line)
        return real(*a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(writes, "act", act)


@pytest.mark.parametrize("case", ["gitignore", "root line"])
def test_a_file_saved_after_loom_read_it_is_never_written_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    from loom.ai.layout import ensure_root_line
    from loom.gitignore import ensure

    q = made(tmp_path, TEXT)
    target = q.root / (".gitignore" if case == "gitignore" else "CLAUDE.md")
    target.write_text("the person's first line\n", encoding="utf-8")
    saving_before_the_act(monkeypatch, target, b"the person's line, saved while loom waited\n")
    with pytest.raises(writes.WriteRefused) as refused:
        ensure(q.root) if case == "gitignore" else ensure_root_line(q.root, True, shell=True)
    assert refused.value.code == "changed"
    assert "saved while loom waited" in target.read_text(encoding="utf-8")


def test_a_page_saved_after_its_base_was_checked_is_never_written_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `--base` check is made again against what the act reads, and `from` is that text (D-2)."""
    from loom.pages import read as read_page
    from loom.pages import state_page
    from loom.pages import write as write_page

    q = made(tmp_path, TEXT)
    result = scan(q)
    page = state_page(q.config)
    write_page(result, page, "The first state.\n", actor="Tester", session=None)
    seen = read_page(q.root, page)
    saving_before_the_act(monkeypatch, q.root / page.path, b"The person's own line.\n")
    with pytest.raises(writes.WriteRefused) as refused:
        write_page(scan(q), page, "The agent's whole page.\n", actor="Some Agent", session=None, seen=seen)
    assert refused.value.code == "changed" and "has changed since you read it" in str(refused.value)
    assert "The person's own line." in (q.root / page.path).read_text(encoding="utf-8")


# ---- the person's look follows their act (P-1) ------------------------------------------------------------------


def looked_by_the_person(q, monkeypatch: pytest.MonkeyPatch) -> str:  # type: ignore[no-untyped-def]
    from loom.looks import take
    from loom.scan.quilt import reviewer_identity, save_author

    if not reviewer_identity(q.root)[0]:
        save_author("Tester")
    who = reviewer_identity(q.root)[0]
    take(q, who)
    return who


def test_an_adoption_the_person_takes_in_is_not_listed_back_to_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.pending import in_place

    q, token = ready(tmp_path)
    who = looked_by_the_person(q, monkeypatch)
    incorporate(scan(q), COPY, token)
    assert [p.path for p in in_place(scan(q), who)] == []


def test_a_pull_the_person_takes_in_is_not_listed_back_and_cannot_be_discarded_behind_its_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compiled: list[str],  # noqa: F811
) -> None:
    from loom.pending import in_place

    q, state = pulled(tmp_path)
    who = looked_by_the_person(q, monkeypatch)
    sync.incorporate(q, state)
    assert [p.path for p in in_place(scan(q), who)] == []
