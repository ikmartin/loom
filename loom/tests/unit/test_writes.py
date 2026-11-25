"""The door every write to a person's file goes through (`loom.writes`): one lock, a journal before any file, the bytes it replaces kept exactly, and recovery from a write a crash cut short.

A crash is played in process by a `BaseException` raised from inside the commit, which the door's own failure handling (for `Exception`) does not catch, so the journal and the files are left as a dead process leaves them; one test kills a real process to show the two agree.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import pytest

from loom import writes
from loom.paths import JOURNAL, JOURNAL_INDEX, WRITES_LOCK
from loom.writes import WriteRefused


class Crash(BaseException):
    """The process dies here."""


@pytest.fixture
def q(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "q"
    (root / "drafting").mkdir(parents=True)
    (root / "drafting" / "a.tex").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    (root / "drafting" / "b.tex").write_bytes(b"alpha\nbeta\n")
    return root, root / ".loom" / "records" / "history"


def _root(history: Path) -> Path:
    """The quilt whose history `history` is, at the default place every test here keeps it: the journal is the quilt's, in `.loom/local/`."""
    return history.parents[2]


def journal(history: Path) -> list[dict[str, Any]]:
    p = _root(history) / JOURNAL
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def events(history: Path) -> list[str]:
    return [e["event"] for e in journal(history)]


def temps(root: Path) -> list[Path]:
    return [p for p in root.rglob(f"*{writes.TEMP}") if ".loom" not in p.relative_to(root).parts]


# ---- what an act writes and keeps --------------------------------------------------------------------------------


def test_an_act_writes_the_bytes_and_keeps_exactly_what_it_replaced(q: tuple[Path, Path]) -> None:
    root, history = q
    before = (root / "drafting/a.tex").read_bytes()
    with writes.act(root, history, "tick", "Pat") as w:
        raw = w.text("drafting/a.tex")
        assert raw is not None
        w.replace("drafting/a.tex", raw.replace("two", "TWO").encode())
    after = (root / "drafting/a.tex").read_bytes()
    assert after == b"one\r\nTWO\r\nthree\r\n"
    assert events(history) == ["begin", "done"]
    begin = journal(history)[0]
    assert begin["kind"] == "tick" and begin["actor"] == "Pat"
    assert begin["files"] == {"drafting/a.tex": [writes.digest(before), writes.digest(after)]}
    assert writes.fetch(history, writes.digest(before) or "") == before
    assert writes.fetch(history, writes.digest(after) or "") == after
    assert not temps(root)


def test_the_journal_names_the_act_before_any_file_is_written(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    seen: list[list[str]] = []
    real = writes._rename

    def rename(tmp: Path, target: Path) -> None:
        seen.append(events(history))
        real(tmp, target)

    monkeypatch.setattr(writes, "_rename", rename)
    with writes.act(root, history, "tick") as w:
        w.replace("drafting/b.tex", b"alpha\nBETA\n")
    assert seen == [["begin"]]


def test_a_file_keeps_its_mode_and_a_symlink_stays_a_link(q: tuple[Path, Path]) -> None:
    root, history = q
    os.chmod(root / "drafting/b.tex", 0o640)
    (root / "shared.tex").write_bytes(b"shared\n")
    (root / "drafting/link.tex").symlink_to(root / "shared.tex")
    with writes.act(root, history, "tick") as w:
        w.replace("drafting/b.tex", b"changed\n")
        w.replace("drafting/link.tex", b"through the link\n")
    assert (root / "drafting/b.tex").stat().st_mode & 0o777 == 0o640
    assert (root / "drafting/link.tex").is_symlink()
    assert (root / "shared.tex").read_bytes() == b"through the link\n"


def test_a_file_that_is_not_utf8_is_never_read_as_text(q: tuple[Path, Path]) -> None:
    root, history = q
    latin = "Schröder\n".encode("latin-1")
    (root / "drafting/latin.tex").write_bytes(latin)
    with pytest.raises(WriteRefused) as exc, writes.act(root, history, "keep") as w:
        w.text("drafting/latin.tex")
    assert exc.value.code == "not-utf8"
    assert (root / "drafting/latin.tex").read_bytes() == latin and not journal(history)


def test_a_plan_holds_while_the_file_reads_as_the_scan_read_it(q: tuple[Path, Path]) -> None:
    root, history = q
    with writes.act(root, history, "keep") as w:
        w.expect("drafting/a.tex", "one\ntwo\nthree\n")  # the scan reads CRLF as LF
        with pytest.raises(WriteRefused) as exc:
            w.expect("drafting/b.tex", "alpha\n")
    assert exc.value.code == "changed"


def test_an_act_that_changes_no_file_writes_no_journal_but_keeps_its_records(q: tuple[Path, Path]) -> None:
    root, history = q
    log = root / ".loom/records/edits/log.jsonl"
    with writes.act(root, history, "keep") as w:
        w.replace("drafting/b.tex", (root / "drafting/b.tex").read_bytes())
        w.log(log, {"event": "kept", "id": "e-1"})
    assert not journal(history)
    assert [json.loads(line) for line in log.read_text().splitlines()] == [{"event": "kept", "id": "e-1"}]


def test_an_exception_in_the_block_writes_nothing(q: tuple[Path, Path]) -> None:
    root, history = q
    with pytest.raises(RuntimeError), writes.act(root, history, "tick") as w:
        w.replace("drafting/b.tex", b"never\n")
        raise RuntimeError("the caller changed its mind")
    assert (root / "drafting/b.tex").read_bytes() == b"alpha\nbeta\n" and not journal(history)


def test_a_save_made_before_the_rename_undoes_the_act_and_keeps_the_save(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    real = writes._rename
    calls: list[Path] = []

    def rename(tmp: Path, target: Path) -> None:
        calls.append(target)
        real(tmp, target)
        if len(calls) == 1:
            (root / "drafting/b.tex").write_bytes(b"the editor saved\n")  # before the second file's last read

    monkeypatch.setattr(writes, "_rename", rename)
    a_before = (root / "drafting/a.tex").read_bytes()
    with pytest.raises(WriteRefused) as exc, writes.act(root, history, "restore") as w:
        w.replace("drafting/a.tex", b"new a\n")
        w.replace("drafting/b.tex", b"new b\n")
    assert exc.value.code == "changed"
    assert (root / "drafting/a.tex").read_bytes() == a_before
    assert (root / "drafting/b.tex").read_bytes() == b"the editor saved\n"
    assert events(history) == ["begin", "aborted"] and not temps(root)


def test_a_commit_cut_short_puts_back_only_a_file_that_still_holds_what_loom_wrote(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    real = writes._rename
    calls: list[Path] = []

    def rename(tmp: Path, target: Path) -> None:
        calls.append(target)
        if len(calls) == 2:
            # the person saves the first file in the instant after loom wrote it, then the disk fills
            (root / "drafting/a.tex").write_bytes(b"the person saved over it\n")
            raise OSError(28, "No space left on device")
        real(tmp, target)

    monkeypatch.setattr(writes, "_rename", rename)
    b_before = (root / "drafting/b.tex").read_bytes()
    with pytest.raises(OSError), writes.act(root, history, "keep") as w:
        w.replace("drafting/a.tex", b"new a\n")
        w.replace("drafting/b.tex", b"new b\n")
        w.wrote("e-2026-01-01-aaaaaa:0")
    monkeypatch.undo()
    # the person's save stands, the second file was never written, and the act is not called undone
    assert (root / "drafting/a.tex").read_bytes() == b"the person saved over it\n"
    assert (root / "drafting/b.tex").read_bytes() == b_before
    assert events(history) == ["begin"] and not temps(root)
    # recovery leaves it for the person, says so, and its edit is not written until they have looked
    said = writes.recover(root, history)
    assert (
        len(said) == 1
        and said[0].startswith("left keep:")
        and "drafting/a.tex neither as before the act nor as it left it" in said[0]
    )
    assert [e["act"] for e in writes.unsettled(root, history)] == [journal(history)[0]["act"]]
    with writes.act(root, history, "keep") as w:
        assert "e-2026-01-01-aaaaaa:0" in w.unsettled_edits()


def test_recovery_never_deletes_a_file_whose_text_before_the_store_lacks(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_rename", after=1)
    with pytest.raises(Crash):
        two_file_act(root, history)
    monkeypatch.undo()
    before = journal(history)[0]["files"]["drafting/a.tex"][0]
    for p in (history / "texts").glob(before.split(":")[1] + ".*"):
        p.unlink()
    writes.recover(root, history)
    assert (root / "drafting/a.tex").read_bytes() == b"new a\r\n"
    assert [e["kind"] for e in writes.unsettled(root, history)] == ["restore"]


def test_recovery_puts_back_all_of_an_act_or_none_and_says_which(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's finding 9: three files, cut short after two renames, the second's text before missing from the store."""
    root, history = q
    (root / "drafting/c.tex").write_bytes(b"gamma\n")
    crash_at(monkeypatch, "_rename", after=2)
    with pytest.raises(Crash), writes.act(root, history, "restore", "Pat") as w:
        w.replace("drafting/a.tex", b"new a\r\n")
        w.replace("drafting/b.tex", b"new b\n")
        w.replace("drafting/c.tex", b"new c\n")
    monkeypatch.undo()
    before = journal(history)[0]["files"]["drafting/b.tex"][0]
    for p in (history / "texts").glob(before.split(":")[1] + ".*"):
        p.unlink()
    said = writes.recover(root, history)
    assert len(said) == 1 and said[0].startswith("left restore:") and "lacks a text of drafting/b.tex" in said[0]
    assert (
        "drafting/a.tex, drafting/b.tex as the act left it" in said[0] and "drafting/c.tex as before the act" in said[0]
    )
    # none of it put back: the document is not made of files from two moments without a word
    assert (root / "drafting/a.tex").read_bytes() == b"new a\r\n" and (
        root / "drafting/b.tex"
    ).read_bytes() == b"new b\n"
    assert (root / "drafting/c.tex").read_bytes() == b"gamma\n"
    # and the server says it again each time it starts, while the act stays
    assert writes.recover(root, history) == said


def test_a_record_line_that_cannot_be_written_leaves_the_act_for_recovery(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    log = root / ".loom/records/edits/log.jsonl"
    real = writes._append_records

    def broken(*args: Any, **kw: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(writes, "_append_records", broken)
    with pytest.raises(OSError), writes.act(root, history, "keep") as w:
        w.replace("drafting/b.tex", b"alpha\nbeta\ngamma\n")
        w.log(log, {"event": "kept", "id": "e-1"})
    assert (root / "drafting/b.tex").read_bytes() == b"alpha\nbeta\ngamma\n" and events(history) == ["begin"]
    monkeypatch.setattr(writes, "_append_records", real)
    assert writes.recover(root, history) == [f"finished {journal(history)[0]['act']}"]
    assert log.read_text().count("e-1") == 1 and events(history) == ["begin", "done"]


# ---- a crash, and recovery -----------------------------------------------------------------------------------------


def crash_at(monkeypatch: pytest.MonkeyPatch, name: str, after: int = 0, when: Any = None) -> None:
    """Make `writes.<name>` die on its `after`-th call (from 0) that `when` accepts."""
    real = getattr(writes, name)
    count = [0]

    def dying(*args: Any, **kw: Any) -> Any:
        if when is None or when(*args, **kw):
            if count[0] == after:
                raise Crash
            count[0] += 1
        return real(*args, **kw)

    monkeypatch.setattr(writes, name, dying)


def two_file_act(root: Path, history: Path) -> None:
    with writes.act(root, history, "restore", "Pat") as w:
        w.replace("drafting/a.tex", b"new a\r\n")
        w.replace("drafting/b.tex", b"new b\n")
        w.log(history / "ledger.jsonl", '{"action": "restore"}')


def test_a_crash_before_the_journal_leaves_everything_as_it_was(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_append_journal")
    with pytest.raises(Crash):
        two_file_act(root, history)
    assert not journal(history) and (root / "drafting/b.tex").read_bytes() == b"alpha\nbeta\n"


def test_a_crash_between_the_journal_and_the_first_rename_is_undone_by_the_next_act(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    a, b = (root / "drafting/a.tex").read_bytes(), (root / "drafting/b.tex").read_bytes()
    crash_at(monkeypatch, "_rename")
    with pytest.raises(Crash):
        two_file_act(root, history)
    assert temps(root) and events(history) == ["begin"]
    monkeypatch.undo()
    with writes.act(root, history, "tick"):
        pass
    assert (root / "drafting/a.tex").read_bytes() == a and (root / "drafting/b.tex").read_bytes() == b
    assert events(history) == ["begin", "aborted"] and not temps(root)
    assert not (history / "ledger.jsonl").exists()


def test_a_crash_between_two_files_is_undone_whole(q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    root, history = q
    a, b = (root / "drafting/a.tex").read_bytes(), (root / "drafting/b.tex").read_bytes()
    crash_at(monkeypatch, "_rename", after=1)
    with pytest.raises(Crash):
        two_file_act(root, history)
    assert (root / "drafting/a.tex").read_bytes() == b"new a\r\n"  # the first file was written
    monkeypatch.undo()
    said = writes.recover(root, history)
    assert said and said[0].startswith("undid")
    assert (root / "drafting/a.tex").read_bytes() == a and (root / "drafting/b.tex").read_bytes() == b
    assert not temps(root)


def test_a_crash_after_the_last_rename_is_finished_with_its_records_once(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_append_records")
    with pytest.raises(Crash):
        two_file_act(root, history)
    monkeypatch.undo()
    writes.recover(root, history)
    assert (root / "drafting/b.tex").read_bytes() == b"new b\n"
    assert (history / "ledger.jsonl").read_text() == '{"action": "restore"}\n'
    assert events(history) == ["begin", "done"]


def test_a_crash_after_the_records_never_writes_them_twice(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_append_journal", when=lambda h, entry, **kw: entry["event"] == "done")
    with pytest.raises(Crash):
        two_file_act(root, history)
    monkeypatch.undo()
    writes.recover(root, history)
    assert (history / "ledger.jsonl").read_text() == '{"action": "restore"}\n'
    assert events(history) == ["begin", "done"]


def test_recovery_leaves_an_act_whose_file_someone_changed_since(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_rename", after=1)
    with pytest.raises(Crash):
        two_file_act(root, history)
    monkeypatch.undo()
    (root / "drafting/a.tex").write_bytes(b"the person typed here\n")
    said = writes.recover(root, history)
    # left, and said, naming each file's state
    assert (
        len(said) == 1
        and said[0].startswith("left restore:")
        and "drafting/a.tex neither as before the act nor as it left it" in said[0]
    )
    assert "drafting/b.tex as before the act" in said[0]
    assert (root / "drafting/a.tex").read_bytes() == b"the person typed here\n"
    left = writes.unsettled(root, history)
    assert [e["kind"] for e in left] == ["restore"]
    # both texts are kept, so nothing is lost while it waits
    before, after = left[0]["files"]["drafting/a.tex"]
    assert writes.fetch(history, before) == b"one\r\ntwo\r\nthree\r\n" and writes.fetch(history, after) == b"new a\r\n"
    # and it does not stop the next act
    with writes.act(root, history, "tick") as w:
        w.replace("drafting/b.tex", b"next\n")
    assert (root / "drafting/b.tex").read_bytes() == b"next\n"


def test_a_real_process_killed_after_the_journal_is_settled_by_the_next(q: tuple[Path, Path]) -> None:
    root, history = q
    child = textwrap.dedent(
        f"""
        import os
        from pathlib import Path
        from loom import writes
        writes._rename = lambda tmp, target: os._exit(9)
        root = Path({str(root)!r})
        with writes.act(root, root / ".loom" / "records" / "history", "tick") as w:
            w.replace("drafting/b.tex", b"never\\n")
        """
    )
    done = subprocess.run([sys.executable, "-c", child], capture_output=True, timeout=60)
    assert done.returncode == 9, done.stderr
    assert events(history) == ["begin"] and temps(root)
    assert writes.recover(root, history)[0].startswith("undid")
    assert (root / "drafting/b.tex").read_bytes() == b"alpha\nbeta\n" and not temps(root)


def test_an_act_in_another_process_holds_the_door_until_it_is_done(q: tuple[Path, Path]) -> None:
    root, history = q
    marker = root.parent / "holding"
    child = textwrap.dedent(
        f"""
        import time
        from pathlib import Path
        from loom import writes
        root = Path({str(root)!r})
        with writes.act(root, root / ".loom" / "records" / "history", "tick") as w:
            Path({str(marker)!r}).write_text("x")
            time.sleep(1.0)
            w.replace("drafting/b.tex", b"from the other process\\n")
        """
    )
    proc = subprocess.Popen([sys.executable, "-c", child])
    try:
        deadline = time.monotonic() + 60
        while not marker.exists():
            assert time.monotonic() < deadline and proc.poll() is None
            time.sleep(0.02)
        with writes.act(root, history, "tick") as w:
            # the other act is done by the time this one reads
            assert w.read("drafting/b.tex") == b"from the other process\n"
            w.replace("drafting/b.tex", b"from this one\n")
    finally:
        proc.wait(timeout=60)
    assert events(history) == ["begin", "done", "begin", "done"]


# ---- the index -------------------------------------------------------------------------------------------------------


def test_the_index_reads_only_what_is_new_and_is_rebuilt_when_lost(q: tuple[Path, Path]) -> None:
    root, history = q
    for n in range(3):
        with writes.act(root, history, "keep") as w:
            w.replace("drafting/b.tex", f"version {n}\n".encode())
            w.wrote(f"e-{n}:0")
    index = json.loads((root / JOURNAL_INDEX).read_text())
    assert index["offset"] == (root / JOURNAL).stat().st_size
    assert set(index["wrote"]) == {"e-0:0", "e-1:0", "e-2:0"}
    assert writes.written(root, history) == {"e-0:0", "e-1:0", "e-2:0"}
    begin = writes.entry_at(root, index["wrote"]["e-1:0"])
    assert begin is not None and begin["edits"] == ["e-1:0"]
    (root / JOURNAL_INDEX).unlink()
    assert writes.written(root, history) == {"e-0:0", "e-1:0", "e-2:0"}
    (root / JOURNAL_INDEX).write_text("{not json")
    assert writes.written(root, history) == {"e-0:0", "e-1:0", "e-2:0"}


def test_a_line_a_crash_cut_short_is_passed_over(q: tuple[Path, Path]) -> None:
    root, history = q
    (root / JOURNAL).parent.mkdir(parents=True)
    (root / JOURNAL).write_bytes(b'{"event": "begin", "act": "x", "fi')
    with writes.act(root, history, "keep") as w:
        w.replace("drafting/b.tex", b"after the cut\n")
        w.wrote("e-9:0")
    assert writes.written(root, history) == {"e-9:0"}
    assert writes.unsettled(root, history) == []


def test_an_unsettled_act_counts_as_written_only_where_its_files_hold_what_it_wrote(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, history = q
    crash_at(monkeypatch, "_append_records")
    with pytest.raises(Crash), writes.act(root, history, "keep") as w:
        w.replace("drafting/b.tex", b"kept\n")
        w.wrote("e-1:0")
    assert writes.written(root, history) == {"e-1:0"}  # recovery will finish it
    (root / "drafting/b.tex").write_bytes(b"alpha\nbeta\n")
    assert writes.written(root, history) == set()  # recovery will undo it


# ---- splices, paths and the store ------------------------------------------------------------------------------------


def test_a_splice_keeps_every_other_byte_and_the_files_line_endings() -> None:
    raw = "one\r\ntwo\r\nthree\r\n"
    # offsets in the scan's reading, "one\ntwo\nthree\n"
    new, made = writes.splice(raw, [(4, 7, "2\nand a half"), (14, 14, "four\n")])
    assert new == "one\r\n2\r\nand a half\r\nthree\r\nfour\r\n"
    assert made[0] == {"at": 5, "old": "two", "new": "2\r\nand a half"}
    assert made[1]["at"] == new.index("four") and made[1]["old"] == ""
    with pytest.raises(ValueError):
        writes.splice(raw, [(0, 5, "x"), (3, 6, "y")])
    assert writes.splice("a\rb\r", [(2, 3, "B\nC")])[0] == "a\rB\rC\r"


def test_newline_of_takes_the_ending_most_lines_use() -> None:
    assert writes.newline_of("a\r\nb\r\nc\n") == "\r\n"
    assert writes.newline_of("a\nb\nc\r\n") == "\n"
    assert writes.newline_of("a\rb\r") == "\r"
    assert writes.newline_of("one line") == "\n"


@pytest.mark.parametrize("rel", ["../outside.tex", "/etc/passwd", "drafting/../../outside.tex", "", ".", "C:/x"])
def test_an_act_never_writes_outside_the_quilt(q: tuple[Path, Path], rel: str) -> None:
    root, history = q
    with pytest.raises(WriteRefused) as exc, writes.act(root, history, "put-back") as w:
        w.replace(rel, b"x")
    assert exc.value.code == "outside-quilt"
    assert not (root.parent / "outside.tex").exists()


def test_a_new_file_in_a_directory_that_leads_out_of_the_quilt_is_refused(q: tuple[Path, Path], tmp_path: Path) -> None:
    root, history = q
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "out").symlink_to(elsewhere)
    with pytest.raises(WriteRefused) as exc, writes.act(root, history, "put-back") as w:
        w.replace("out/new.tex", b"x")
    assert exc.value.code == "outside-quilt" and not list(elsewhere.iterdir())


def test_the_store_keeps_bytes_exactly_under_the_names_versions_and_looks_use(tmp_path: Path) -> None:
    from loom.records.snapshots import read_raw, write_raw

    history = tmp_path / "history"
    crlf = "a\r\nb\r\n"
    d = write_raw(tmp_path, crlf, history)
    assert d == writes.digest(crlf.encode()) and read_raw(tmp_path, d, history) == crlf
    assert writes.store(history, crlf.encode()) == d and writes.fetch(history, d) == crlf.encode()
    latin = "ö\n".encode("latin-1")
    dl = writes.store(history, latin)
    assert (history / "texts" / f"{dl.split(':')[1]}.bin").read_bytes() == latin
    assert writes.fetch(history, dl) == latin and read_raw(tmp_path, dl, history) is None


# ---- a journal is not trusted ----------------------------------------------------------------------------------------
# A quilt someone hands you can carry a journal of its own. Recovery acts on an entry only when every file it names stays in the quilt, every digest is a digest, and every record goes to one of loom's own logs; anything else is left and reported, and nothing is read or written for it.


def plant(history: Path, *entries: dict[str, Any]) -> None:
    """Write `entries` into the journal as `begin` lines a crash left, the acts named `planted-1`, `planted-2`…"""
    (_root(history) / JOURNAL).parent.mkdir(parents=True, exist_ok=True)
    with (_root(history) / JOURNAL).open("a") as fh:
        for n, e in enumerate(entries, 1):
            fh.write(json.dumps({"event": "begin", "act": f"planted-{n}", "kind": "keep", **e}) + "\n")


def test_recovery_never_appends_a_record_to_a_file_outside_the_quilt(q: tuple[Path, Path], tmp_path: Path) -> None:
    root, history = q
    profile = tmp_path / "profile"
    profile.write_text("# the person's shell starts here\n")
    plant(history, {"files": {}, "records": [{"log": str(profile), "line": json.dumps("$(touch pwned)")}]})
    said = writes.recover(root, history)
    assert said and said[0].startswith("left") and "names no file" in said[0]
    assert profile.read_text() == "# the person's shell starts here\n"
    assert [e["kind"] for e in writes.unsettled(root, history)] == ["keep"]


def test_recovery_never_writes_a_file_outside_the_quilt(q: tuple[Path, Path], tmp_path: Path) -> None:
    root, history = q
    stored = writes.store(history, b"echo planted\n")
    b = (root / "drafting/b.tex").read_bytes()
    outside = root.parent / "elsewhere" / "created.txt"
    plant(
        history,
        {
            "files": {
                "drafting/b.tex": [writes.digest(b), writes.digest(b"other")],
                "../elsewhere/created.txt": [stored, None],
            }
        },
    )
    said = writes.recover(root, history)
    assert said[0].startswith("left") and "not a file in the quilt" in said[0]
    assert not outside.exists() and (root / "drafting/b.tex").read_bytes() == b


def test_recovery_never_follows_a_symlink_out_of_the_quilt(q: tuple[Path, Path], tmp_path: Path) -> None:
    root, history = q
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "existing.txt").write_bytes(b"")
    (root / "out").symlink_to(elsewhere)
    stored = writes.store(history, b"echo planted\n")
    b = (root / "drafting/b.tex").read_bytes()
    # the inside file holds its before and the outside one its after: undoing would write the planted bytes out there
    plant(
        history,
        {
            "files": {
                "drafting/b.tex": [writes.digest(b), writes.digest(b"x")],
                "out/existing.txt": [stored, writes.digest(b"")],
            }
        },
        {"files": {"drafting/b.tex": [writes.digest(b), writes.digest(b"x")], "out/created.txt": [stored, None]}},
    )
    said = writes.recover(root, history)
    assert len(said) == 2 and all(s.startswith("left") for s in said)
    assert (elsewhere / "existing.txt").read_bytes() == b"" and not (elsewhere / "created.txt").exists()


def test_recovery_appends_only_records_that_are_records_to_loom_s_own_logs(q: tuple[Path, Path]) -> None:
    root, history = q
    b = (root / "drafting/b.tex").read_bytes()
    one = {
        "drafting/b.tex": [writes.digest(b"before"), writes.digest(b)]
    }  # every file holds its after: it would be finished
    plant(
        history,
        {"files": one, "records": [{"log": ".loom/records/edits/log.jsonl", "line": json.dumps("not a record")}]},
        {"files": one, "records": [{"log": "drafting/b.tex", "line": json.dumps({"event": "kept"})}]},
        {"files": one, "records": [{"log": ".loom/records/history/ledger.jsonl", "line": "{}"}], "extra": 1},
    )
    said = writes.recover(root, history)
    assert [s.split(":")[0] for s in said] == ["left planted-1", "left planted-2", "finished planted-3"], said
    assert (root / "drafting/b.tex").read_bytes() == b and not (root / ".loom/records/edits/log.jsonl").exists()
    assert (history / "ledger.jsonl").read_text() == "{}\n"


def test_a_digest_that_is_not_a_digest_is_never_made_into_a_path(q: tuple[Path, Path]) -> None:
    from loom.records.snapshots import read_raw

    root, history = q
    (history / "texts").mkdir(parents=True)
    (root.parent / "secret.md").write_text("not loom's")
    for bad in ("sha256:../../../secret", "sha256:" + "0" * 63, "../secret", "sha256:" + "A" * 64):
        assert writes.fetch(history, bad) is None and read_raw(root, bad, history) is None, bad


def test_an_act_stages_records_only_for_loom_s_own_logs(q: tuple[Path, Path], tmp_path: Path) -> None:
    root, history = q
    for log in (tmp_path / "profile", root / "drafting/b.tex", root / ".loom/records/edits/../../drafting/b.tex"):
        with pytest.raises(WriteRefused) as exc, writes.act(root, history, "keep") as w:
            w.log(log, {"event": "kept"})
        assert exc.value.code == "outside-quilt", log


def test_the_journal_stays_on_this_machine(q: tuple[Path, Path]) -> None:
    from loom.gitignore import write_loom_ignore

    root, history = q
    if subprocess.run(["git", "--version"], capture_output=True).returncode:
        pytest.skip("no git")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    write_loom_ignore(root)
    with writes.act(root, history, "tick") as w:
        w.replace("drafting/b.tex", b"changed\n")
    names = [JOURNAL, JOURNAL_INDEX, WRITES_LOCK]
    assert all((root / n).is_file() for n in names)
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", *names], capture_output=True, text=True
    ).stdout.split()
    assert ignored == names
    # the store of texts is the history's, and travels with it
    kept = next(p.relative_to(root).as_posix() for p in (history / "texts").glob("*.md"))
    assert subprocess.run(["git", "-C", str(root), "check-ignore", "-q", kept]).returncode == 1


def test_recovery_removes_a_temporary_text_a_crash_left_and_not_one_being_written(q: tuple[Path, Path]) -> None:
    """A crash between writing a text's temporary file and its rename leaves the file in the history's `texts/`, in no ignored folder; recovery removes it once it is older than a store takes, and leaves a young one, which another process may be writing."""
    root, history = q
    writes.store(history, b"kept text\n")
    texts = history / "texts"
    left = texts / f".{'a' * 64}.md.{'0' * 12}{writes.TEMP}"
    young = texts / f".{'b' * 64}.bin.{'1' * 12}{writes.TEMP}"
    other = texts / "notes.loom-tmp"
    for p in (left, young, other):
        p.write_bytes(b"half")
    then = time.time() - 2 * writes.LEFT
    os.utime(left, (then, then))
    os.utime(other, (then, then))
    assert writes.recover(root, history) == ["removed 1 temporary file a crash left in the history's texts/"]
    assert not left.exists() and young.is_file() and other.is_file()
    assert len([p for p in texts.iterdir() if p.suffix == ".md"]) == 1


def _unresolvable(monkeypatch: pytest.MonkeyPatch, part: str) -> list[bool]:
    """`os.path.realpath` raising for any path holding `part` once the returned switch is set, as Python before 3.13 raises while a folder on the way is being renamed."""
    real, on = os.path.realpath, [False]

    def realpath(p: Any, *args: Any, **kwargs: Any) -> str:
        if on[0] and part in str(p):
            raise OSError("a folder on the way is being renamed")
        return real(p, *args, **kwargs)

    monkeypatch.setattr(writes.os.path, "realpath", realpath)
    return on


def test_a_commit_put_back_while_a_link_cannot_be_followed_raises_its_own_failure_and_leaves_the_act(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A commit that fails puts back what it wrote; where the file system cannot follow a link it wrote through just then, the put-back, its temporaries and its empty folders take the path as one they cannot judge, and the commit's own failure is raised, the act left for recovery, rather than the race's."""
    root, history = q
    (root / "real.md").write_text("before\n", encoding="utf-8")
    (root / "link.md").symlink_to("real.md")
    on = _unresolvable(monkeypatch, "link.md")
    real_rename, calls = writes._rename, [0]

    def rename(tmp: Path, target: Path) -> None:
        calls[0] += 1
        if calls[0] == 2:
            on[0] = True
            raise RuntimeError("the disk is full")
        real_rename(tmp, target)

    monkeypatch.setattr(writes, "_rename", rename)
    with pytest.raises(RuntimeError, match="the disk is full"), writes.act(root, history, "restore") as w:
        w.replace("link.md", b"after\n")
        w.replace("made/new.md", b"new\n")
    assert [e["kind"] for e in writes.unsettled(root, history)] == ["restore"]
    on[0] = False
    monkeypatch.setattr(writes, "_rename", real_rename)
    (said,) = writes.recover(root, history)
    assert said.startswith("undid restore:"), said
    assert (root / "real.md").read_text(encoding="utf-8") == "before\n" and (root / "link.md").is_symlink()


def test_a_link_that_cannot_be_followed_is_written_through_by_no_act(
    q: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the file system cannot follow a link just then, the act writing through it is refused (`changed`) and writes nothing, and the folders an act made are left rather than judged blind."""
    root, history = q
    (root / "real.md").write_text("before\n", encoding="utf-8")
    (root / "link.md").symlink_to("real.md")
    on = _unresolvable(monkeypatch, "link.md")
    on[0] = True
    with pytest.raises(WriteRefused, match="could not be followed"), writes.act(root, history, "restore") as w:
        w.replace("link.md", b"after\n")
    assert (root / "real.md").read_text(encoding="utf-8") == "before\n"
    (root / ".loom/kept/a").mkdir(parents=True)
    on2 = _unresolvable(monkeypatch, "kept")
    on2[0] = True
    writes._prune(root, history, [".loom/kept/a/x.md"])
    assert (root / ".loom/kept/a").is_dir()
