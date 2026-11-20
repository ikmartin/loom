"""The undo of a Keep (`change-undo`, `pending.unkeep`): the bytes the Keep replaced come back, every other byte stays, and an undo that cannot find what its Keep wrote refuses and writes nothing. Restore and put-back move a kept edit's record with its words."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.test_write_safety import call, files, scan, suggest, synthetic, waiting

LEMMA = "drafting/nodes/sy-0002.tex"
THEOREM = "drafting/nodes/sy-0003.tex"
REMARK = "drafting/nodes/sy-000A.tex"
# the agent's suggestion on sy-0002: "the fixed points are those of …" in place of "compare …"
FIXED = "e-2026-09-17-zwvx4m"
# the agent's suggestion on sy-0004
ANSWER = "e-2026-09-16-r2hw0m"


@pytest.fixture
def q(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the synthetic quilt as the write-safety test makes it: edits tracked, the person `Pat`, a first look taken."""
    return synthetic(tmp_path, monkeypatch)


def status(root: Path, edit: str) -> str:
    from loom.records.edits import find

    found = find(root, edit)
    return found.status if found else "gone"


def journal(root: Path) -> list[dict]:
    from loom.paths import JOURNAL

    return [json.loads(line) for line in (root / JOURNAL).read_text(encoding="utf-8").splitlines() if line]


def test_a_keep_is_undone_in_one_step_with_the_exact_bytes_back(q: Path) -> None:
    before = files(q)
    assert call(q, "change-keep", {"changes": [FIXED]})["done"] == [FIXED]
    assert files(q)[LEMMA] != before[LEMMA]
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert res["done"] == [FIXED] and res["refused"] == []
    assert files(q) == before
    assert status(q, FIXED) == "open"
    assert [p.state for p in waiting(q) if p.id == FIXED] == ["ready"]
    # one act, its Keep named apart from what loom wrote, the text it replaced kept as a version first
    undo = [e for e in journal(q) if e.get("event") == "begin" and e["kind"] == "undo"]
    assert len(undo) == 1 and undo[0]["undid"] == [f"{FIXED}:0"] and undo[0]["edits"] == []
    assert "a version of" in res["result"]
    # and kept again it is written again, once, as a new act; then undone again
    assert call(q, "change-keep", {"changes": [FIXED]})["done"] == [FIXED]
    assert files(q)[LEMMA].count(b"the fixed points are those of") == 1
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert files(q) == before


def test_an_undo_in_a_crlf_file_gives_back_its_bytes(q: Path) -> None:
    p = q / LEMMA
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    call(
        q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]}
    )  # the look takes it as it is now
    before = p.read_bytes()
    assert call(q, "change-keep", {"changes": [FIXED]})["done"] == [FIXED]
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert p.read_bytes() == before


def test_an_undo_keeps_what_changed_elsewhere_in_the_file_since(q: Path) -> None:
    p = q / LEMMA
    was = p.read_text()
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert p.read_text() == was.replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed.")


def test_an_undo_refuses_once_the_words_beside_what_it_wrote_changed(q: Path) -> None:
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("one or two points;", "at most two points;"))
    now = files(q)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert res["done"] == [] and [r["code"] for r in res["refused"]] == ["changed-since"]
    assert "restore a version" in res["refused"][0]["why"]
    assert files(q) == now and status(q, FIXED) == "kept"


def test_an_undo_refuses_where_the_words_it_wrote_stand_twice_with_their_neighbours(q: Path) -> None:
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text() + "\n" + p.read_text().replace("{sy-0002}", "{sy-0002b}"))
    now = files(q)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and files(q) == now


def test_of_two_edits_kept_in_one_file_at_once_one_is_undone_and_the_other_stays(q: Path) -> None:
    p = q / LEMMA
    before = p.read_text()
    other = suggest(q, "sy-0002", "Each orbit of a widget", "--quote", "Every orbit of a widget")
    assert other is not None
    assert sorted(call(q, "change-keep", {"changes": [FIXED, other]})["done"]) == sorted([FIXED, other])
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    text = p.read_text()
    assert "Each orbit of a widget has one or two points; compare \\eqref{eq:fix}" in text
    assert call(q, "change-undo", {"changes": [other]})["done"] == [other]
    assert p.read_text() == before


def test_keep_all_across_files_is_undone_by_one_request(q: Path) -> None:
    before = files(q)
    assert sorted(call(q, "change-keep", {"changes": [FIXED, ANSWER]})["done"]) == sorted([FIXED, ANSWER])
    assert files(q)[LEMMA] != before[LEMMA] and files(q)[THEOREM] != before[THEOREM]
    res = call(q, "change-undo", {"changes": [FIXED, ANSWER]})
    assert sorted(res["done"]) == sorted([FIXED, ANSWER])
    assert files(q) == before


def test_an_undo_opens_again_the_annotation_its_keep_resolved(q: Path) -> None:
    from loom.records.annotations import find_annotation, load_records

    asked = call(
        q, "annotate", {"target": "sy-000A", "quote": "the swap", "message": "Which swap?", "type": "revision"}
    )
    question = asked["result"].split()[0]
    answer = suggest(q, "sy-000A", "the swap of its two points", "--quote", "the swap", "--answers", question)
    assert answer is not None

    def status_of() -> str:
        found = find_annotation(load_records(q)[0], question)
        assert found is not None
        return found[1].status

    call(q, "change-keep", {"changes": [answer]})
    assert status_of() == "resolved"
    call(q, "change-undo", {"changes": [answer]})
    assert status_of() == "open"
    # one the person resolved again since is theirs, and stays resolved
    call(q, "change-keep", {"changes": [answer]})
    call(q, "resolve", {"annotation": question, "undo": True})
    call(q, "resolve", {"annotation": question, "message": "Settled."})
    call(q, "change-undo", {"changes": [answer]})
    assert status_of() == "resolved"


def test_an_undo_is_not_listed_as_an_edit_in_the_file(q: Path) -> None:
    call(q, "change-keep", {"changes": [FIXED]})
    call(q, "change-undo", {"changes": [FIXED]})
    assert [p.id for p in waiting(q) if p.kind == "edit"] == []


def test_an_annotation_on_the_words_a_keep_wrote_goes_back_onto_the_words_it_replaced(q: Path) -> None:
    from loom.records.annotations import find_annotation, load_records

    res = call(q, "annotate", {"target": "sy-0002", "quote": "compare \\eqref{eq:fix}", "message": "Which one?"})
    note = res["result"].split()[0]
    call(q, "change-keep", {"changes": [FIXED]})
    found = find_annotation(load_records(q)[0], note)
    assert found is not None and "fixed points" in (found[1].anchor or found[1].selector).exact
    call(q, "change-undo", {"changes": [FIXED]})
    found = find_annotation(load_records(q)[0], note)
    assert found is not None and "compare" in (found[1].anchor or found[1].selector).exact


def test_a_keep_that_wrote_nothing_is_not_undone(q: Path) -> None:
    p = q / LEMMA
    p.write_text(
        p.read_text().replace(
            "compare \\eqref{eq:fix} in Definition~\\ref{sy-0001}",
            "the fixed points are those of \\eqref{eq:fix} in Definition~\\ref{sy-0001}",
        )
    )
    assert [x.state for x in waiting(q) if x.id == FIXED] == ["taken"]
    call(q, "change-keep", {"changes": [FIXED]})
    now = files(q)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["not-written"] and files(q) == now
    assert status(q, FIXED) == "kept"


def test_a_keep_made_on_another_machine_is_not_undone_here(q: Path) -> None:
    from loom.paths import JOURNAL, JOURNAL_INDEX

    call(q, "change-keep", {"changes": [FIXED]})
    # what travels is the record and the texts; the journal is the machine's
    (q / JOURNAL).unlink()
    (q / JOURNAL_INDEX).unlink(missing_ok=True)
    now = files(q)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["not-written"] and "another machine" in res["refused"][0]["why"]
    assert files(q) == now


def test_a_keep_written_through_a_link_out_of_the_quilt_is_not_undone_from_its_record(q: Path, tmp_path: Path) -> None:
    # the person's own arrangement: a block kept in a file outside the quilt, linked in
    outside = tmp_path / "shared" / "sy-000A.tex"
    outside.parent.mkdir()
    (q / REMARK).replace(outside)
    (q / REMARK).symlink_to(outside)
    edit = suggest(q, "sy-000A", "the swap of its two points", "--quote", "the swap")
    assert edit is not None
    assert call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    assert "the swap of its two points" in outside.read_text()
    now = outside.read_bytes()
    res = call(q, "change-undo", {"changes": [edit]})
    assert [r["code"] for r in res["refused"]] == ["not-written"] and "not a file in the quilt" in res["refused"][0][
        "why"
    ]
    assert outside.read_bytes() == now and (q / REMARK).is_symlink()


def test_only_a_kept_edit_has_a_keep_to_undo(q: Path) -> None:
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["not-kept"]
    call(q, "change-discard", {"changes": [FIXED]})
    assert [r["code"] for r in call(q, "change-undo", {"changes": [FIXED]})["refused"]] == ["not-kept"]
    assert call(q, "change-undo", {"changes": ["e-2026-01-01-nothere"]}) == {"error": "no-such-change"}
    assert call(q, "change-undo", {"changes": []}) == {"error": "missing-field"}


def test_a_kept_edit_is_opened_again_only_by_the_undo_of_its_keep(q: Path) -> None:
    call(q, "change-keep", {"changes": [FIXED]})
    now = files(q)
    res = call(q, "change-discard", {"changes": [FIXED], "undo": True})
    assert res["done"] == [] and [r["code"] for r in res["refused"]] == ["kept"]
    assert status(q, FIXED) == "kept" and files(q) == now
    # a discarded one is still opened again: the undo of a Discard
    call(q, "change-discard", {"changes": [ANSWER]})
    assert call(q, "change-discard", {"changes": [ANSWER], "undo": True})["done"] == [ANSWER]


def test_an_agent_cannot_undo_a_keep(q: Path) -> None:
    call(q, "change-keep", {"changes": [FIXED]})
    assert call(q, "change-undo", {"changes": [FIXED], "author": "Agent Smith"}) == {"error": "author-only"}
    assert status(q, FIXED) == "kept"


def test_an_undo_cut_short_after_its_write_is_finished_once_by_the_next_act(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom import writes

    before = files(q)
    call(q, "change-keep", {"changes": [FIXED]})
    real = writes._append_records

    def crash(root: Path, records: list, **kw: object) -> None:
        raise SystemExit("killed after the rename")

    monkeypatch.setattr(writes, "_append_records", crash)
    with pytest.raises(SystemExit):
        call(q, "change-undo", {"changes": [FIXED]})
    monkeypatch.setattr(writes, "_append_records", real)
    assert files(q) == before and status(q, FIXED) == "kept"
    writes.recover(q, scan(q).quilt.history_dir)
    assert status(q, FIXED) == "open"
    from loom.records.edits import find

    edit = find(q, FIXED)
    assert edit is not None and sum(1 for a in edit.acts if a.get("event") == "reopened") == 1


# ---- records follow restore and put-back ------------------------------------------------------------------------


def record(root: Path, name: str) -> str:
    """Keep a version of the main document under `name`; its landmark's path, which restore takes."""
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt

    assert call(root, "history-record", {"document": "drafting/main.tex", "name": name}).get("ok")
    history = load_history(load_quilt(root).history_dir)
    entry = [e for e in history.landmarks() if e.message == name][-1]
    return history.landmark_path(entry).relative_to(root).as_posix()


def restore(root: Path, landmark: str) -> None:
    res = call(root, "history-restore", {"document": "drafting/main.tex", "version": landmark})
    assert res.get("ok"), res


def test_a_restore_that_takes_a_kept_edit_out_opens_it_again(q: Path) -> None:
    before = files(q)
    first = record(q, "First")
    call(q, "change-keep", {"changes": [FIXED]})
    restore(q, first)
    assert files(q)[LEMMA] == before[LEMMA]
    assert status(q, FIXED) == "open" and [p.state for p in waiting(q) if p.id == FIXED] == ["ready"]
    # kept again, it is written once
    call(q, "change-keep", {"changes": [FIXED]})
    assert files(q)[LEMMA].count(b"the fixed points are those of") == 1


def test_a_restore_that_brings_an_undone_edit_back_records_it_kept(q: Path) -> None:
    call(q, "change-keep", {"changes": [FIXED]})
    kept = files(q)[LEMMA]
    with_it = record(q, "With it")
    call(q, "change-undo", {"changes": [FIXED]})
    assert status(q, FIXED) == "open"
    restore(q, with_it)
    assert files(q)[LEMMA] == kept and status(q, FIXED) == "kept"
    assert [p.id for p in waiting(q) if p.id == FIXED] == []
    # recorded kept by the restore, not written by a Keep: there is no Keep of it to undo
    assert [r["code"] for r in call(q, "change-undo", {"changes": [FIXED]})["refused"]] == ["not-written"]


def test_a_restore_leaves_kept_an_edit_whose_words_the_person_changed_beside(q: Path) -> None:
    p = q / LEMMA
    first = record(q, "First")
    p.write_text(p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("one or two points;", "at most two points;"))
    restore(q, first)
    # its words are gone, and it stays kept: never open while a Keep could write it beside words that are its own
    assert b"the fixed points are those of" not in p.read_bytes()
    assert status(q, FIXED) == "kept"


def test_a_restore_of_the_very_bytes_a_keep_replaced_opens_its_edit_again(q: Path) -> None:
    p = q / LEMMA
    first = record(q, "First")
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("one or two points;", "at most two points;"))
    restore(q, first)
    assert status(q, FIXED) == "open" and [x.state for x in waiting(q) if x.id == FIXED] == ["ready"]


def test_putting_back_a_text_that_takes_a_kept_edit_out_opens_it_again(q: Path) -> None:
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt

    p = q / LEMMA
    # an edit made in the file and discarded: the text it had is set aside, without the suggestion
    p.write_text(p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    (change,) = [x.id for x in waiting(q) if x.kind == "edit"]
    call(q, "change-discard", {"changes": [change]})
    aside = [e for e in load_history(load_quilt(q).history_dir).entries if e.action == "undo"][-1].get("from")
    call(q, "change-keep", {"changes": [FIXED]})
    assert call(q, "history-restore", {"path": LEMMA, "text": aside}).get("ok")
    assert "as claimed" in p.read_text() and "the fixed points are those of" not in p.read_text()
    assert status(q, FIXED) == "open"
