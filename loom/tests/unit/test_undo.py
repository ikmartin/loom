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


def test_an_undo_after_the_files_line_endings_changed_writes_in_the_files_own(q: Path) -> None:
    p = q / LEMMA
    before = p.read_bytes()
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert p.read_bytes() == before.replace(b"\n", b"\r\n")


def test_words_a_keep_joined_onto_one_line_come_back_in_the_files_line_ending(q: Path) -> None:
    """The review's finding 4: a Keep joins two lines, the file is then saved with CRLF, and the undo writes no bare LF."""
    p = q / "drafting/nodes/sy-000B.tex"
    p.write_bytes(
        p.read_bytes().replace(
            b"Every finite widget of odd order has a fixed point, and the fixed locus is functorial.",
            b"Every finite widget of odd order, however large it may be, has a fixed point,\nand the fixed locus is functorial in every sense one could want.",
        )
    )
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    before = p.read_bytes()
    edit = suggest(q, "sy-000B", "has a fixed point; moreover", "--quote", "has a fixed point,\nand")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    assert call(q, "change-undo", {"changes": [edit]})["done"] == [edit]
    assert p.read_bytes() == before.replace(b"\n", b"\r\n")


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


def test_an_undo_refuses_where_its_words_and_their_neighbours_stand_twice(q: Path) -> None:
    """A copy of the kept passage, region and all: the place cannot be told from its twin, so the undo refuses."""
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text() + "\n" + p.read_text().replace("{sy-0002}", "{sy-0002b}"))
    copied = p.read_bytes()
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and p.read_bytes() == copied


TWINS = "drafting/nodes/twins.tex"


def twins(q: Path, second_proof: str = "Immediate.") -> Path:
    """A file of three lemmas brought into the main document, the first two with proofs alike."""
    f = q / TWINS
    f.write_text(
        "\\begin{lemma}\\label{sy-0E01}\nFirst claim holds.\n\\end{lemma}\n\\begin{proof}\nImmediate.\n\\end{proof}\n\n"
        "\\begin{lemma}\\label{sy-0E02}\nSecond claim holds.\n\\end{lemma}\n\\begin{proof}\n"
        + second_proof
        + "\n\\end{proof}\n\n\\begin{lemma}\\label{sy-0E03}\nThird claim holds.\n\\end{lemma}\n",
        encoding="utf-8",
    )
    m = q / "drafting/main.tex"
    m.write_bytes(m.read_bytes().replace(b"\\input{nodes/sy-000A}", b"\\input{nodes/twins}\n\n\\input{nodes/sy-000A}"))
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    return f


def test_an_undo_never_takes_the_persons_own_like_words_from_another_block(q: Path) -> None:
    """The review's case w: the person's second proof already says the kept sentence; they reword the kept one, then undo."""
    f = twins(q, second_proof="Immediate. This is clear.")
    edit = suggest(q, "sy-0E01/proof", "This is clear.", "--quote", "Immediate.", "--after")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    f.write_text(f.read_text().replace("Immediate. This is clear.", "Immediate. This is clear from the definition.", 1))
    reworded = f.read_bytes()
    res = call(q, "change-undo", {"changes": [edit]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and f.read_bytes() == reworded


def lemma(n: int, word: str, proof: str) -> str:
    return f"\\begin{{lemma}}\\label{{sy-0E0{n}}}\n{word} claim holds.\n\\end{{lemma}}\n\\begin{{proof}}\n{proof}\n\\end{{proof}}\n\n"


@pytest.mark.parametrize("kept_in", [1, 2])
def test_an_undo_never_takes_a_twins_words_after_the_person_swaps_two_alike_blocks(q: Path, kept_in: int) -> None:
    """The second review's R2-1: two proofs end with the same sentence, one by a Keep, one the person's; the person swaps the two lemmas, then undoes."""
    proofs = {1: "Immediate.", 2: "Immediate."}
    proofs[3 - kept_in] = "Immediate. This is clear."
    f = twins(q)
    f.write_text(lemma(1, "First", proofs[1]) + lemma(2, "Second", proofs[2]) + lemma(3, "Third", "Immediate."))
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    edit = suggest(q, f"sy-0E0{kept_in}/proof", "This is clear.", "--quote", "Immediate.", "--after")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    one, two = lemma(1, "First", "Immediate. This is clear."), lemma(2, "Second", "Immediate. This is clear.")
    f.write_text(f.read_text().replace(one + two, two + one))
    swapped = f.read_bytes()
    res = call(q, "change-undo", {"changes": [edit]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and f.read_bytes() == swapped


def test_an_undo_refuses_a_copy_of_its_words_elsewhere_once_the_original_is_reworded(q: Path) -> None:
    """What the line diff decides that a search would not: the person copies the kept lemma to the end of the file and rewords the original; the region's one occurrence is the copy, out of order with the Keep's place, so the undo refuses rather than edit the copy."""
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    lemma = p.read_text().split("\\begin{proof}")[0]
    copied = p.read_text() + "\n% a copy of mine\n" + lemma.replace("{sy-0002}", "{sy-0002c}")
    p.write_text(copied.replace("the fixed points are those of", "the fixed points are just those of", 1))
    before = p.read_bytes()
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and p.read_bytes() == before


def test_an_undo_past_its_bound_of_work_refuses_and_says_the_file_changed_too_much(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The third review's R3-3: finding a place is bounded by work, not the clock; past the bound the undo refuses, writes nothing, and says why."""
    from loom import writes

    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    # changes before and after the words, so the place is found by the diff, not by what the texts share
    changed = p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed.")
    p.write_text(changed.replace("% !LOOM tags: orbits, setup", "% !LOOM tags: orbits, setup, mine"))
    before = p.read_bytes()
    monkeypatch.setattr(writes, "PAIRING", -1_000_000)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and "changed too much" in res["refused"][0]["why"]
    assert p.read_bytes() == before and status(q, FIXED) == "kept"


def test_an_undo_after_typing_at_a_files_end_beside_its_words_refuses(q: Path) -> None:
    """The second review's R2-2: kept words end a file with no final newline, and the person types right after them."""
    f = q / "drafting/sections/tail.tex"
    f.write_text("\\section{Tail}\\label{sy-0E41}\nThe paper ends here")
    m = q / "drafting/main.tex"
    m.write_bytes(
        m.read_bytes().replace(b"\\input{nodes/sy-000A}", b"\\input{sections/tail}\n\n\\input{nodes/sy-000A}")
    )
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    edit = suggest(q, "sy-0E41", "ends at last", "--quote", "ends here")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    f.write_text(f.read_text() + "ing.")
    typed = f.read_bytes()
    res = call(q, "change-undo", {"changes": [edit]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and f.read_bytes() == typed


def test_an_undo_after_typing_at_a_files_start_within_its_neighbours_refuses(q: Path) -> None:
    """The second review's R2-2 at the other edge: a character typed at the very start, 30 characters before the kept words."""
    p = q / REMARK
    orig = p.read_text()
    edit = suggest(q, "sy-000A", "Gadgets do exist:", "--quote", "Gadgets exist:")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    p.write_text("X" + p.read_text())
    typed = p.read_bytes()
    assert [r["code"] for r in call(q, "change-undo", {"changes": [edit]})["refused"]] == ["changed-since"]
    assert p.read_bytes() == typed
    # a whole line put above meets the file's start too, and is refused the same way: the edge is part of the region
    p.write_text("% a line of mine\n" + p.read_text()[1:])
    assert [r["code"] for r in call(q, "change-undo", {"changes": [edit]})["refused"]] == ["changed-since"]
    # and once the start is as the Keep left it, the undo goes ahead
    p.write_text(p.read_text().split("\n", 1)[1])
    assert call(q, "change-undo", {"changes": [edit]})["done"] == [edit] and p.read_text() == orig


def test_words_put_back_take_the_files_line_ending_at_their_place(q: Path) -> None:
    """The second review's R2-6: a mostly-LF file with a CRLF inside the replaced words and one elsewhere, made all LF since: no CR comes back. Where the file is still as the Keep left it, the bytes before come back exactly, CR and all."""
    p = q / "drafting/nodes/sy-000B.tex"
    p.write_bytes(
        p.read_bytes()
        .replace(
            b"Every finite widget of odd order has a fixed point, and the fixed locus is functorial.",
            b"Every finite widget of odd order, however large it may be, has a fixed point,\r\nand the fixed locus is functorial in every sense one could want.",
        )
        .replace(b"\\end{proof}\n", b"\\end{proof}\r\n")
    )
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    edit = suggest(q, "sy-000B", "has a fixed point; moreover", "--quote", "has a fixed point,\nand")
    assert edit is not None and call(q, "change-keep", {"changes": [edit]})["done"] == [edit]
    p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n"))
    assert call(q, "change-undo", {"changes": [edit]})["done"] == [edit]
    assert b"\r" not in p.read_bytes() and b"has a fixed point,\nand" in p.read_bytes()


def test_an_undo_never_takes_out_another_keeps_like_words(q: Path) -> None:
    """The review's case v: two Keeps put the same sentence after two proofs alike; the first is reworded, then undone."""
    f = twins(q)
    one = suggest(q, "sy-0E01/proof", "This is clear.", "--quote", "Immediate.", "--after")
    two = suggest(q, "sy-0E02/proof", "This is clear.", "--quote", "Immediate.", "--after")
    assert one and two
    call(q, "change-keep", {"changes": [one]})
    call(q, "change-keep", {"changes": [two]})
    f.write_text(f.read_text().replace("Immediate. This is clear.", "Immediate. This is clear from the definition.", 1))
    reworded = f.read_bytes()
    res = call(q, "change-undo", {"changes": [one]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and f.read_bytes() == reworded
    assert status(q, one) == "kept" and status(q, two) == "kept"


def test_an_undo_of_edits_kept_side_by_side_never_writes_in_another_block(q: Path) -> None:
    """The review's case u: three one-word edits kept together, the middle one changed by the person, then the Keep undone."""
    f = q / THEOREM
    edits = [
        suggest(q, "sy-0005", "Enumerate", "--quote", "Count"),
        suggest(q, "sy-0005", "disjoint", "--quote", "fixed"),
        suggest(q, "sy-0005", "orbits", "--quote", "points"),
    ]
    assert all(edits) and sorted(call(q, "change-keep", {"changes": edits})["done"]) == sorted(edits)
    f.write_text(f.read_text().replace("Enumerate disjoint orbits", "Enumerate disjointed orbits"))
    changed = f.read_bytes()
    res = call(q, "change-undo", {"changes": edits})
    assert res["done"] == [] and {r["code"] for r in res["refused"]} == {"changed-since"}
    assert f.read_bytes() == changed and b"is a disjoint union" in changed


def test_of_two_edits_kept_in_one_file_at_once_one_is_undone_and_the_other_stays(q: Path) -> None:
    p = q / LEMMA
    before = p.read_text()
    other = suggest(q, "sy-0002", "Each orbit of a widget", "--quote", "Every orbit of a widget")
    assert other is not None
    assert sorted(call(q, "change-keep", {"changes": [FIXED, other]})["done"]) == sorted([FIXED, other])
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    text = p.read_text()
    assert "Each orbit of a widget has one or two points; compare \\eqref{eq:fix}" in text
    # the other's neighbours as that Keep left them held the first's words, which are gone: its place is not established
    res = call(q, "change-undo", {"changes": [other]})
    assert [r["code"] for r in res["refused"]] == ["changed-since"] and p.read_text() == text
    # undone together, as the viewer undoes a Keep of both, they come back whole
    call(q, "change-keep", {"changes": [FIXED]})
    call(q, "change-undo", {"changes": [FIXED]})
    assert call(q, "change-keep", {"changes": [FIXED]})["done"] == [FIXED]
    assert sorted(call(q, "change-undo", {"changes": [FIXED, other]})["done"]) == sorted([FIXED, other])
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


def test_an_undo_leaves_the_persons_own_pending_change_listed_and_lists_nothing_of_its_own(q: Path) -> None:
    """The look takes the undo's own change, carried to its place, while the person's change elsewhere in the file still waits, as it was."""
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    mine = [(x.id, x.old, x.new) for x in waiting(q) if x.kind == "edit"]
    assert len(mine) == 1
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert [(x.id, x.old, x.new) for x in waiting(q) if x.kind == "edit"] == mine


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


def test_a_save_made_while_the_undo_keeps_its_version_survives_and_nothing_is_undone(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's finding 10: between the undo's plan and its write, the person's editor saves; the undo refuses and the save stands."""
    import loom.history.acts as acts

    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    real = acts.keep_versions

    def saving(*args: object, **kw: object) -> object:
        p.write_text(p.read_text() + "% saved while the undo ran\n")
        return real(*args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(acts, "keep_versions", saving)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert res["done"] == [] and [r["code"] for r in res["refused"]] == ["changed"]
    text = p.read_text()
    assert text.endswith("% saved while the undo ran\n") and "the fixed points are those of" in text
    assert status(q, FIXED) == "kept"


def test_a_save_made_between_the_undos_plan_and_its_version_survives(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The review's finding 10, its window: the plan read the file, the person saves, and the scan the version is stamped from reads the save."""
    import loom.pending as pending

    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    real = pending._undo_in

    def then_save(*args: object, **kw: object) -> object:
        plan = real(*args, **kw)  # type: ignore[arg-type]
        p.write_text(p.read_text() + "% saved after the plan\n")
        return plan

    monkeypatch.setattr(pending, "_undo_in", then_save)
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert res["done"] == [] and [r["code"] for r in res["refused"]] == ["changed"]
    assert p.read_text().endswith("% saved after the plan\n") and status(q, FIXED) == "kept"


def test_a_restore_that_leaves_an_open_edits_words_where_they_stood_leaves_its_record(q: Path) -> None:
    """The record moves only when the act moves the words: an edit undone and typed in again by hand stays open across a restore that keeps them."""
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    kept = p.read_text()
    call(q, "change-undo", {"changes": [FIXED]})
    p.write_text(kept.replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    mine = record(q, "Mine")
    p.write_text(kept)
    assert status(q, FIXED) == "open"
    restore(q, mine)
    assert "as claimed" in p.read_text() and status(q, FIXED) == "open"


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


def plant(q: Path, before: bytes, after: bytes, splices: list[dict], gen: str) -> None:
    """What a copied quilt could carry: FIXED recorded kept, two texts in the store, and a Keep of it in the journal."""
    from loom import writes
    from loom.paths import EDIT_LOG, JOURNAL, JOURNAL_INDEX

    hist = scan(q).quilt.history_dir
    b, a = writes.store(hist, before), writes.store(hist, after)
    with (q / EDIT_LOG).open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "event": "kept",
                    "id": FIXED,
                    "when": "2026-11-01T00:00:00Z",
                    "author": "Pat",
                    "kind": "human",
                    "hash": "x",
                }
            )
            + "\n"
        )
    act = {"act": "keep:feedfacefeedface", "kind": "keep", "actor": "Pat", "when": "x"}
    with (q / JOURNAL).open("a") as fh:
        line = {
            **act,
            "event": "begin",
            "files": {LEMMA: [b, a]},
            "splices": {LEMMA: splices},
            "edits": [gen],
            "records": [],
        }
        fh.write(json.dumps(line) + "\n" + json.dumps({"event": "done", "act": act["act"], "when": "x"}) + "\n")
    (q / JOURNAL_INDEX).unlink(missing_ok=True)


def test_an_undo_writes_nothing_its_journal_line_and_texts_do_not_bear_out(q: Path) -> None:
    """The review's finding 11: a journal that came with a copied quilt names a Keep whose texts and splices disagree."""
    p = q / LEMMA
    shipped = p.read_bytes()
    # before bytes the file never held, with a splice that does not turn them into the after bytes
    plant(
        q,
        b"\\immediate\\write18{echo hi}\n",
        shipped,
        [{"edit": f"{FIXED}:0", "at": 0, "old": "", "new": ""}],
        f"{FIXED}:0",
    )
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["not-written"] and p.read_bytes() == shipped


def test_an_undo_splices_in_nothing_its_texts_do_not_hold(q: Path) -> None:
    p = q / LEMMA
    shipped = p.read_bytes()
    plant(
        q,
        shipped,
        shipped + b"%\n",
        [{"edit": f"{FIXED}:0", "at": 0, "old": "\\input{/etc/passwd}", "new": ""}],
        f"{FIXED}:0",
    )
    p.write_bytes(shipped.replace(b"by \\eqref{eq:prose}.", b"by \\eqref{eq:prose}, mine."))
    edited = p.read_bytes()
    res = call(q, "change-undo", {"changes": [FIXED]})
    assert [r["code"] for r in res["refused"]] == ["not-written"] and p.read_bytes() == edited


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


@pytest.mark.parametrize("act", ["keep", "undo"])
def test_a_keep_or_undo_recovery_finished_is_not_listed_as_the_persons_edit(
    q: Path, monkeypatch: pytest.MonkeyPatch, act: str
) -> None:
    """The review's finding 8: recovery finishes the files and records, and the look as the act's follow-up would have."""
    from loom import writes

    if act == "undo":
        call(q, "change-keep", {"changes": [FIXED]})
    real = writes._append_records

    def crash(root: Path, records: list, **kw: object) -> None:
        raise SystemExit("killed after the rename")

    monkeypatch.setattr(writes, "_append_records", crash)
    with pytest.raises(SystemExit):
        call(q, f"change-{act}", {"changes": [FIXED]})
    monkeypatch.setattr(writes, "_append_records", real)
    said = writes.recover(q, scan(q).quilt.history_dir)
    assert said and said[0].startswith("finished ")
    assert [x.id for x in waiting(q) if x.kind == "edit"] == []


def test_a_write_recovery_leaves_is_listed_as_a_problem_in_the_persons_file(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second review's last item: what recovery leaves is said where a person looks, as a problem in their file, and not only on the server's terminal."""
    from click.testing import CliRunner

    from loom import writes
    from loom.cli import main

    call(q, "change-keep", {"changes": [FIXED, ANSWER]})
    real, renamed = writes._rename, []

    def dying(tmp: Path, target: Path) -> None:
        if renamed:
            raise SystemExit("killed between the two files")
        renamed.append(target)
        real(tmp, target)

    monkeypatch.setattr(writes, "_rename", dying)
    with pytest.raises(SystemExit):
        call(q, "change-undo", {"changes": [FIXED, ANSWER]})
    monkeypatch.setattr(writes, "_rename", real)
    first = renamed[0].relative_to(q).as_posix()
    (q / first).write_text((q / first).read_text() + "% the person's line\n")
    res = CliRunner().invoke(main, ["lint", "--json", "--quilt", str(q)])
    found = [d for d in json.loads(res.stdout)["diagnostics"] if d["code"] == "loom:write-left"]
    assert len(found) == 1 and found[0]["message"].startswith("loom could neither finish nor undo an undo of a Keep")
    assert f"{first} changed since loom began writing it" in found[0]["message"]
    # what the person can do, in plain words, with no command and no id
    assert "Look at the file: if it reads as you want, there is nothing to do" in found[0]["message"]
    assert (
        "`" not in found[0]["message"]
        and "loom lint" not in found[0]["message"]
        and "loom doctor" not in found[0]["message"]
    )
    assert "undo:" not in found[0]["message"] and "keep:" not in found[0]["message"]
    # once the act is settled it is no problem any more: here, the person puts the file back as loom wrote it
    (q / first).write_text((q / first).read_text().replace("% the person's line\n", ""))
    res = CliRunner().invoke(main, ["lint", "--json", "--quilt", str(q)])
    assert not [d for d in json.loads(res.stdout)["diagnostics"] if d["code"] == "loom:write-left"]


def test_a_record_recovery_cannot_trust_or_bear_out_is_said_with_no_path_and_no_false_claim(q: Path) -> None:
    """The third review's R3-4: a journal that came with a copied folder names a file outside the quilt, or texts the store lacks."""
    from click.testing import CliRunner

    from loom.cli import main
    from loom.paths import JOURNAL, JOURNAL_INDEX

    def problems() -> list[dict]:
        res = CliRunner().invoke(main, ["lint", "--json", "--quilt", str(q)])
        return [d for d in json.loads(res.stdout)["diagnostics"] if d["code"] == "loom:write-left"]

    def plant(rel: str, digests: list[str]) -> None:
        line = {
            "event": "begin",
            "act": "keep:feedfacefeedface",
            "kind": "keep",
            "actor": "Pat",
            "when": "x",
            "files": {rel: digests},
            "splices": {},
            "edits": [],
            "records": [],
        }
        (q / JOURNAL).parent.mkdir(parents=True, exist_ok=True)
        (q / JOURNAL).write_text(json.dumps(line) + "\n")
        (q / JOURNAL_INDEX).unlink(missing_ok=True)

    plant("../outside.tex", ["sha256:" + "1" * 64, "sha256:" + "2" * 64])
    (found,) = problems()
    assert "outside" not in found["message"] and not found.get("locations") and "cannot trust" in found["message"]
    plant("drafting/main.tex", ["sha256:" + "1" * 64, "sha256:" + "2" * 64])
    (found,) = problems()
    assert "lacks a text of drafting/main.tex" in found["message"] and "kept in the history" not in found["message"]


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
    # recorded kept by the restore on the Keep that wrote those words, which an undo takes out again
    assert call(q, "change-undo", {"changes": [FIXED]})["done"] == [FIXED]
    assert b"the fixed points are those of" not in (q / LEMMA).read_bytes()


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


def test_restores_back_and_forth_leave_the_record_as_the_file_reads(q: Path) -> None:
    """The review's finding 6: restore the version before a Keep, the one after it, and the one before again."""
    before, after = record(q, "Before"), ""
    call(q, "change-keep", {"changes": [FIXED]})
    after = record(q, "After")
    restore(q, before)
    assert status(q, FIXED) == "open"
    restore(q, after)
    assert status(q, FIXED) == "kept"
    restore(q, before)
    assert status(q, FIXED) == "open" and [x.state for x in waiting(q) if x.id == FIXED] == ["ready"]


def test_a_restore_never_opens_an_edit_whose_words_stand_elsewhere(q: Path) -> None:
    """The review's finding 5: the person moved the kept words into the proof and typed the old ones back; a version of that is restored."""
    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    kept = p.read_text()
    moved = kept.replace(
        "the fixed points are those of \\eqref{eq:fix} in Definition~\\ref{sy-0001}.",
        "compare \\eqref{eq:fix} in Definition~\\ref{sy-0001}.",
    ).replace(
        "by \\eqref{eq:prose}.",
        "by \\eqref{eq:prose}; here the fixed points are those of \\eqref{eq:fix} in Definition~\\ref{sy-0001}.",
    )
    p.write_text(moved)
    v = record(q, "Moved")
    p.write_text(kept)
    call(q, "change-keep", {"changes": [x.id for x in waiting(q) if x.kind == "edit"]})
    restore(q, v)
    assert status(q, FIXED) == "kept"
    call(q, "change-keep", {"all": True})
    assert p.read_text().count("the fixed points are those of") == 1


def test_discarding_a_change_that_brings_a_kept_edits_words_back_records_it_kept(q: Path) -> None:
    """The review's finding 7: a restore takes a Keep out, Your Changes lists that as the person's edit, and Discard writes the words back."""
    first = record(q, "First")
    call(q, "change-keep", {"changes": [FIXED]})
    restore(q, first)
    assert status(q, FIXED) == "open"
    (change,) = [x.id for x in waiting(q) if x.kind == "edit" and x.path == LEMMA]
    call(q, "change-discard", {"changes": [change]})
    assert b"the fixed points are those of" in (q / LEMMA).read_bytes()
    assert status(q, FIXED) == "kept" and [x.id for x in waiting(q) if x.id == FIXED] == []


def test_a_discard_of_a_change_away_from_a_kept_edit_does_not_look_for_its_place(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second review's R2-3: a Discard, a restore or a put-back looks at a Keep's place only when what it writes touches it, so a Discard elsewhere runs no diff."""
    from loom import writes

    p = q / LEMMA
    call(q, "change-keep", {"changes": [FIXED]})
    p.write_text(p.read_text().replace("by \\eqref{eq:prose}.", "by \\eqref{eq:prose}, as claimed."))
    (change,) = [x.id for x in waiting(q) if x.kind == "edit"]
    looked: list[object] = []
    real = writes.place_in

    def placing(*args: object, **kw: object) -> object:
        looked.append(args)
        return real(*args, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(writes, "place_in", placing)
    assert call(q, "change-discard", {"changes": [change]})["done"] == [change]
    assert looked == [] and status(q, FIXED) == "kept"


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
