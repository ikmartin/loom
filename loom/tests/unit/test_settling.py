"""Settling a write the door left, as it stands (`loom.settling`): the person's word, which writes none of their files, loses no text and ends only the act it names."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loom import settling, writes
from tests.helpers import ok, run
from tests.unit.test_adopt import DOC, TEXT, made
from tests.unit.test_write_safety import Died

OLD, NEW = "Second statement uses", "The second statement uses"


def _quilt(tmp_path: Path) -> tuple[Path, Path, str]:
    """A quilt with one document and an agent's suggestion on it, waiting; its history and the suggestion's id."""
    from loom.scan.quilt import load_quilt

    root = tmp_path / "q"
    root.mkdir()
    made(root, TEXT)
    ok("suggest", "zk-0002", "--quote", OLD, "--with", NEW, "--as", "Referee Agent", cwd=root, env={"AI_AGENT": "1"})
    (edit,) = [c["id"] for c in json.loads(run("changes", "--json", cwd=root).stdout)["changes"]]
    return root, load_quilt(root).history_dir, edit


def _cut(root: Path, mp: pytest.MonkeyPatch, edit: str, where: str) -> str:
    """Keep `edit`, cut short `where`: `before the file` (the version stamped, the document not written) or `after the file` (every file written, no history line); then a line of the person's own at the document's end, so recovery can neither finish it nor put it back. Returns the left act's id."""
    if where == "before the file":
        real = writes._install

        def install(r: Path, rel: str, *args: Any, **kwargs: Any) -> None:
            if rel == DOC:
                raise Died
            real(r, rel, *args, **kwargs)

        mp.setattr(writes, "_install", install)
    else:

        def guarded(*args: Any, **kwargs: Any) -> None:
            raise Died

        mp.setattr(writes, "_append_guarded", guarded)
    with pytest.raises(Died):
        run("changes", "--keep", edit, cwd=root)
    mp.undo()
    doc = root / DOC
    doc.write_bytes(doc.read_bytes() + b"% the person's own line\n")
    ((act, *_),) = writes.left_acts(root, root / ".loom/records/history")
    return str(act)


def _person_s(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".loom" not in p.parts
    }


def _edit(root: Path, edit: str) -> Any:
    from loom.records.edits import replay

    return {e.id: e for e in replay(root)[0]}[edit]


def test_a_keep_whose_words_stand_is_settled_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Keep cut short after it wrote the document: its words stand at their place, so the suggestion is recorded kept. No file of the person's is written, and the notice is gone."""
    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "after the file")
    before = _person_s(root)
    plan = settling.preview(root, hist, act)
    assert plan.history == "" and [d.outcome for d in plan.edits] == ["kept"]
    said = " ".join(plan.said())
    assert (
        f"{DOC} stays as it is." in said
        and "Referee Agent's suggestion" in said
        and "kept, since its words stand" in said
    )
    assert act not in said and "sha256" not in said and "loom " not in said
    settling.settle(root, hist, act, "Tester")
    assert _person_s(root) == before
    assert _edit(root, edit).status == "kept" and writes.left_acts(root, hist) == []


def test_a_keep_cut_before_its_file_is_settled_open_again_and_keep_then_writes_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Keep cut short before it wrote the document: the words it would replace stand, so the suggestion is open again, and once settled Keep writes it, once."""
    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "before the file")
    before = _person_s(root)
    plan = settling.settle(root, hist, act, "Tester")
    assert [d.outcome for d in plan.edits] == ["open"] and _person_s(root) == before
    assert _edit(root, edit).status == "open" and writes.left_acts(root, hist) == []
    ok("changes", "--keep", edit, cwd=root)
    assert (root / DOC).read_text().count(NEW) == 1


def test_a_keep_whose_place_was_rewritten_is_settled_closed_as_no_longer_applying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The person rewrote the place since: neither the suggestion's words nor the ones they replace stand there, so it is closed, with why in words."""
    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "after the file")
    doc = root / DOC
    doc.write_text(doc.read_text().replace(NEW, "Entirely other words"))
    plan = settling.settle(root, hist, act, "Tester")
    assert [d.outcome for d in plan.edits] == ["closed"]
    e = _edit(root, edit)
    assert e.status == "discarded" and e.why == settling.NO_LONGER


def _left_import(tmp_path: Path, mp: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    """An import cut short after it wrote the paper and its version as received, before the history's line for that version; then the person's own line in the paper, so recovery leaves it. The quilt, its history and the act."""
    from loom.scan.quilt import load_quilt
    from tests.unit.test_paper import bare_quilt, paper_dir

    p = paper_dir(tmp_path)
    q = bare_quilt(tmp_path)

    def guarded(*args: Any, **kwargs: Any) -> None:
        raise Died

    mp.setattr(writes, "_append_guarded", guarded)
    with pytest.raises(Died):
        run("import", str(p / "main.tex"), "--yes", "--no-check", cwd=q)
    mp.undo()
    main = q / "main/main.tex"
    main.write_bytes(main.read_bytes() + b"% the person's own line\n")
    hist = load_quilt(q).history_dir
    writes.recover(q, hist)
    ((act, *_),) = writes.left_acts(q, hist)
    return q, hist, str(act)


def test_a_version_whose_line_can_still_land_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The import wrote the paper as received, whole, and nothing has been recorded since: settling writes the history's line for it, as recovery's finish would, so the version is kept and no stray step is left."""
    from loom.history.ledger import load_history
    from loom.history.steps import refuse_interrupted

    q, hist, act = _left_import(tmp_path, monkeypatch)
    (stray,) = load_history(hist).unrecorded_dirs()
    before, steps = _person_s(q), len(load_history(hist).steps())
    plan = settling.preview(q, hist, act)
    assert plan.history == "lands" and "is recorded in your history" in " ".join(plan.said())
    assert plan.files and not [rel for rel in plan.files if rel.startswith(".loom/")]
    settling.settle(q, hist, act, "Tester")
    assert _person_s(q) == before and stray.is_dir()
    assert len(load_history(hist).steps()) == steps + 1 and load_history(hist).unrecorded_dirs() == []
    refuse_interrupted(load_history(hist))
    assert writes.left_acts(q, hist) == []


def test_a_version_that_can_no_longer_be_recorded_is_removed_and_its_texts_stay_in_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another line took the history on past the one the import planned: its version can never be recorded, so settling removes it, saying so, and every text it held stays in the history's store; no stray step is left to stop the next version, and the person's files are as they were."""
    from loom.history.ledger import append_entry, load_history
    from loom.history.steps import refuse_interrupted

    q, hist, act = _left_import(tmp_path, monkeypatch)
    (stray,) = load_history(hist).unrecorded_dirs()
    held = [p.read_bytes() for p in stray.rglob("*") if p.is_file()]
    assert held
    append_entry(hist, "page-write", {"page": "state", "path": "research-state.md"}, "Tester")
    before = _person_s(q)
    plan = settling.preview(q, hist, act)
    assert plan.history == "removed" and plan.steps
    assert "this version is not kept" in " ".join(plan.said())
    settling.settle(q, hist, act, "Tester")
    assert not stray.exists() and load_history(hist).unrecorded_dirs() == []
    assert all(writes.fetch(hist, str(writes.digest(b))) == b for b in held)
    refuse_interrupted(load_history(hist))
    assert _person_s(q) == before and writes.left_acts(q, hist) == []


def test_settling_ends_only_the_act_it_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two writes left; settling one leaves the other as it was, said and waiting."""
    root, hist, edit = _quilt(tmp_path)
    first = _cut(root, monkeypatch, edit, "before the file")
    other = root / ".mcp.json"
    other.write_text('{"mcpServers": {}}\n')
    from tests.unit.test_write_safety import dying_before_the_rename

    restore = dying_before_the_rename(monkeypatch, after=1)
    with pytest.raises(Died), writes.act(root, hist, "agents") as w:
        w.replace(".mcp.json", b'{"mcpServers": {"x": {}}}\n')
        w.replace("notes.md", b"# Notes\n")
    restore()
    writes.recover(root, hist)
    ids = [a for a, *_ in writes.left_acts(root, hist)]
    assert first in ids and len(ids) == 2
    settling.settle(root, hist, first, "Tester")
    assert [a for a, *_ in writes.left_acts(root, hist)] == [i for i in ids if i != first]


def test_a_settle_is_the_person_s_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refused to a declared agent on the endpoint, and in an agent's shell at the terminal, whatever it names; the act stays left."""
    from loom.render.api import handle
    from loom.render.endpoints.base import ApiError

    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "before the file")
    with pytest.raises(ApiError) as refused:
        handle(root, "write-settle", {"act": act, "author": "Referee Agent"})
    assert refused.value.code == "author-only" and refused.value.status == 403
    out = run("doctor", "--settle", act, cwd=root, env={"AI_AGENT": "1"})
    assert out.exit_code != 0 and "author's" in out.output
    assert [a for a, *_ in writes.left_acts(root, hist)] == [act]
    preview = handle(root, "write-settle-preview", {"act": act})
    assert preview["act"] == act and all(act not in line for line in preview["said"])
    done = handle(root, "write-settle", {"act": act})
    assert done["result"] == "settled a Keep as it stands" and writes.left_acts(root, hist) == []


def test_loom_doctor_lists_a_left_write_by_its_id_and_settles_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`loom doctor` names each write left with the id `--settle` takes, and the problem carries it in its fix's `act` alone, never in its words."""
    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "before the file")
    report = json.loads(run("doctor", "--json", cwd=root).stdout)
    (item,) = [i for i in report["items"] if i["name"] == "writes"]
    assert item["status"] == "warn" and [x["act"] for x in item["left"]] == [act]
    lint = json.loads(run("lint", "--json", cwd=root).stdout)
    (problem,) = [d for d in lint["diagnostics"] if d["code"] == "loom:write-left"]
    assert act not in problem["message"] and problem["fixes"][0]["act"] == {
        "endpoint": "write-settle",
        "body": {"act": act},
    }
    said = ok("doctor", "--settle", act, cwd=root).stdout
    assert "stays as it is" in said and writes.left_acts(root, hist) == []


def test_a_forged_settling_line_gains_nothing_a_forged_aborted_line_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `begin` naming an act to settle, with nothing else, whether `done` follows or recovery finishes it, ends that act and writes nothing, exactly as a forged `aborted` line ends it; one naming an act the journal does not hold ends nothing."""
    from loom.paths import JOURNAL, JOURNAL_INDEX

    root, hist, edit = _quilt(tmp_path)
    act = _cut(root, monkeypatch, edit, "before the file")
    journal = root / JOURNAL
    kept = journal.read_bytes()
    before = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p != journal and "local" not in p.parts
    }

    def forge(*lines: dict[str, Any]) -> list[str]:
        journal.write_bytes(kept)
        (root / JOURNAL_INDEX).unlink(missing_ok=True)
        with journal.open("a") as fh:
            for line in lines:
                fh.write(json.dumps(line) + "\n")
        writes.recover(root, hist)
        return [a for a, *_ in writes.left_acts(root, hist)]

    begin = {"event": "begin", "act": "settle:a1a1a1a1a1a1a1a1", "kind": "settle", "actor": "Tester", "by": "person", "when": "2026-11-24T00:00:00Z", "files": {}, "edits": [], "records": [], "settles": act}  # fmt: skip
    aborted = forge({"event": "aborted", "act": act, "when": "2026-11-24T00:00:00Z"})
    assert forge(begin, {"event": "done", "act": begin["act"], "when": "x"}) == aborted == []
    assert forge(begin) == aborted
    assert forge({**begin, "settles": "keep:b2b2b2b2b2b2b2b2"}) == [act]
    after = {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p != journal and "local" not in p.parts
    }
    assert {k: v for k, v in after.items() if not k.startswith(".loom/records")} == {
        k: v for k, v in before.items() if not k.startswith(".loom/records")
    }
    assert _edit(root, edit).status == "open"


def _guard_dies(mp: pytest.MonkeyPatch) -> None:
    """Every file of the next act is written and it dies before its records and `done`."""

    def guarded(*args: Any, **kwargs: Any) -> None:
        raise Died

    mp.setattr(writes, "_append_guarded", guarded)


@pytest.mark.parametrize("kind", sorted(k for k in writes.KINDS if k != "settle"))
def test_a_left_act_of_every_kind_is_settled_as_it_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """An act of each kind, cut short with its files written, then a line of the person's own in one of them, so recovery leaves it: settling it names the kind as a person does, writes none of their files, keeps the file it made, and ends that act alone."""
    root, hist, _ = _quilt(tmp_path)
    _guard_dies(monkeypatch)
    with pytest.raises(Died), writes.act(root, hist, kind, "Tester") as w:
        w.replace(DOC, (root / DOC).read_bytes() + b"% the act's line\n")
        w.replace("extra/made.md", b"made by the act\n")
    monkeypatch.undo()
    doc = root / DOC
    doc.write_bytes(doc.read_bytes() + b"% the person's own line\n")
    writes.recover(root, hist)
    ((act, named, *_),) = writes.left_acts(root, hist)
    assert named == writes.KINDS[kind]
    before = _person_s(root)
    plan = settling.preview(root, hist, act)
    assert plan.kind == writes.KINDS[kind] and plan.files == [DOC, "extra/made.md"]
    said = " ".join(plan.said())
    assert f"Settling {writes.KINDS[kind]} as it stands" in said and act not in said
    settling.settle(root, hist, act, "Tester")
    assert _person_s(root) == before and writes.left_acts(root, hist) == []
    assert writes.recover(root, hist) == [] and _person_s(root) == before


def test_an_undo_of_a_keep_is_settled_by_the_words_it_put_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An undo of a Keep cut short with the old words back in the file: the suggestion is open again, its kept record answered, and no file of the person's written."""
    root, hist, edit = _quilt(tmp_path)
    ok("changes", "--keep", edit, cwd=root)
    assert _edit(root, edit).status == "kept"
    _guard_dies(monkeypatch)
    from loom.machine import quilt_id
    from loom.render.api import handle

    with pytest.raises(Died):
        handle(root, "change-undo", {"changes": [edit], "quilt": quilt_id(root)})
    monkeypatch.undo()
    doc = root / DOC
    assert NEW not in doc.read_text()
    doc.write_bytes(doc.read_bytes() + b"% the person's own line\n")
    writes.recover(root, hist)
    ((act, named, *_),) = writes.left_acts(root, hist)
    assert named == "an undo of a Keep"
    before = _person_s(root)
    plan = settling.settle(root, hist, act, "Tester")
    assert [d.outcome for d in plan.edits] == ["open"] and _person_s(root) == before
    assert _edit(root, edit).status == "open" and writes.left_acts(root, hist) == []


def _forge_left(root: Path, hist: Path, edit: str, new: str) -> str:
    """A Keep's `begin` line that no Keep wrote, naming the open `edit` with a splice of `new` for its quoted words, its texts in the store and neither of them what the file holds, so recovery leaves it. Returns its id."""
    from loom.paths import JOURNAL, JOURNAL_INDEX
    from loom.records.edits import generation

    doc = (root / DOC).read_text()
    was = doc + "% a line the forger says was there\n"
    at = was.index(OLD)
    now = was[:at] + new + was[at + len(OLD) :]
    gen = f"{edit}:{generation(_edit(root, edit))}"
    act = "keep:c3c3c3c3c3c3c3c3"
    begin = {
        "event": "begin",
        "act": act,
        "kind": "keep",
        "actor": "Tester",
        "by": "person",
        "when": "2026-11-24T00:00:00Z",
        "files": {DOC: [writes.store(hist, was.encode()), writes.store(hist, now.encode())]},
        "splices": {DOC: [{"at": at, "old": OLD, "new": new, "edit": gen}]},
        "edits": [gen],
        "records": [],
    }
    with (root / JOURNAL).open("a") as fh:
        fh.write(json.dumps(begin) + "\n")
    (root / JOURNAL_INDEX).unlink(missing_ok=True)
    writes.recover(root, hist)
    assert [a for a, *_ in writes.left_acts(root, hist)] == [act]
    return act


@pytest.mark.parametrize("new", ["Words the agent never suggested", NEW])
def test_a_forged_left_line_gains_nothing_when_settled(tmp_path: Path, new: str) -> None:
    """A left Keep forged into the journal, naming an open suggestion with a splice of other words, or of its own words where the file holds the words they replace: settling it writes none of the person's files and leaves the suggestion open, its record untouched."""
    from loom.paths import EDIT_LOG

    root, hist, edit = _quilt(tmp_path)
    act = _forge_left(root, hist, edit, new)
    log = (root / EDIT_LOG).read_bytes()
    before = _person_s(root)
    plan = settling.settle(root, hist, act, "Tester")
    assert [d.outcome for d in plan.edits] == ["as-is" if new != NEW else "open"]
    assert all(d.record is None for d in plan.edits)
    assert _person_s(root) == before and (root / EDIT_LOG).read_bytes() == log
    assert _edit(root, edit).status == "open" and writes.left_acts(root, hist) == []


def test_an_untrusted_left_line_is_only_ended(tmp_path: Path) -> None:
    """A left line naming a file outside the quilt, as one copied in with a folder may: settling it decides nothing, confirms nothing and writes nothing; it only ends the notice."""
    from loom.paths import EDIT_LOG, JOURNAL, JOURNAL_INDEX

    root, hist, edit = _quilt(tmp_path)
    act = "keep:d4d4d4d4d4d4d4d4"
    d = writes.store(hist, b"x\n")
    begin = {"event": "begin", "act": act, "kind": "keep", "actor": "Tester", "by": "person", "when": "2026-11-24T00:00:00Z", "files": {"../outside.tex": [d, d]}, "edits": [f"{edit}:0"], "records": []}  # fmt: skip
    with (root / JOURNAL).open("a") as fh:
        fh.write(json.dumps(begin) + "\n")
    (root / JOURNAL_INDEX).unlink(missing_ok=True)
    writes.recover(root, hist)
    assert [a for a, *_ in writes.left_acts(root, hist)] == [act]
    log, before = (root / EDIT_LOG).read_bytes(), _person_s(root)
    plan = settling.settle(root, hist, act, "Tester")
    assert not plan.trusted and plan.edits == [] and plan.files == []
    assert _person_s(root) == before and (root / EDIT_LOG).read_bytes() == log
    assert _edit(root, edit).status == "open" and writes.left_acts(root, hist) == []


def test_a_settling_cut_short_is_finished_by_recovery_once_or_left_when_a_file_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settling that dies after its journal line and before its records: recovery finishes it while the document still holds what the person settled on, recording the suggestion kept once and ending the act it names; where the document was saved in between, the settling is left too, and settling the first act again settles it."""
    from loom.paths import EDIT_LOG

    for saved in (False, True):
        (tmp_path / str(saved)).mkdir()
        root, hist, edit = _quilt(tmp_path / str(saved))
        act = _cut(root, monkeypatch, edit, "after the file")
        before = _person_s(root)

        def records(*args: Any, **kwargs: Any) -> None:
            raise Died

        monkeypatch.setattr(writes, "_append_records", records)
        with pytest.raises(Died):
            settling.settle(root, hist, act, "Tester")
        monkeypatch.undo()
        assert _person_s(root) == before
        if not saved:
            writes.recover(root, hist)
            assert writes.left_acts(root, hist) == [] and _edit(root, edit).status == "kept"
            kept = [ln for ln in (root / EDIT_LOG).read_text().splitlines() if '"kept"' in ln]
            assert len(kept) == 1 and _person_s(root) == before
            continue
        doc = root / DOC
        doc.write_bytes(doc.read_bytes() + b"% saved again\n")
        writes.recover(root, hist)
        left = [a for a, *_ in writes.left_acts(root, hist)]
        assert act in left and len(left) == 2 and _edit(root, edit).status == "open"
        settling.settle(root, hist, act, "Tester")
        (stale,) = [a for a, *_ in writes.left_acts(root, hist)]
        assert stale.startswith("settle:") and _edit(root, edit).status == "kept"
        settling.settle(root, hist, stale, "Tester")
        assert writes.left_acts(root, hist) == [] and _edit(root, edit).status == "kept"
