"""Where a record goes (`records.locate.follow`): a key named by place is never read on the block that took its place, a renamed file is followed by its text, and a region whose label went is read in the block it was in."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers import edit, ok
from tests.unit._quilts import demo

WHO = "Tester"
OUTLINE = "drafting/outline.tex"
CONSIDERED = "drafting/outline.tex#section:2"


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author(WHO)
    return demo(tmp_path)


def note(q: Path, key: str, *more: str) -> str:
    return ok("annotate", key, "Which?", *more, "--type", "question", "--as", WHO, cwd=q).output.split()[0]


def row(q: Path, ann: str) -> dict[str, Any]:
    from loom.cli._quilt import open_scan
    from loom.records.store import Records

    result = open_scan(str(q))
    manifest: dict[str, Any] = {"nodes": {}, "keys": {}, "diagnostics": []}
    Records(q, result.quilt.history_dir).apply(result, manifest)
    return manifest["annotations"][ann]  # type: ignore[no-any-return]


def test_a_note_on_a_key_named_by_place_is_never_read_on_the_block_put_in_at_its_place(q: Path) -> None:
    whole = note(q, CONSIDERED)
    quoted = note(q, CONSIDERED, "--quote", "Neither of these is proved.")
    edit(
        q / OUTLINE,
        "\\section{What is being considered}",
        "\\section{Notation}\nA word on notation.\n\n\\section{What is being considered}",
    )
    edit(q / OUTLINE, "Neither of these is proved.", "Neither of these is proved yet.")
    for ann in (whole, quoted):
        got = row(q, ann)
        # moved and edited: nothing says where its block went, so it is detached, and the section put in at its place does not take it
        assert got["detached"] is True and got["target"]["key"] == CONSIDERED, got


def test_a_note_on_a_block_edited_where_it_stands_stays_on_it_while_it_reads_like_it(q: Path) -> None:
    whole = note(q, CONSIDERED)
    edit(q / OUTLINE, "the question owes nothing.", "the question owes nothing at all.")
    got = row(q, whole)
    assert (got["detached"], got["target"]["key"]) == (False, CONSIDERED)
    # rewritten past recognition: the block at its place is no longer the one it was written on
    edit(
        q / OUTLINE,
        "Neither of these is proved. The conjecture owes a proof and appears among the blockers until it is proved or refuted; the question owes nothing at all.",
        "Two loose ends, recorded so they are not forgotten.",
    )
    assert row(q, whole)["detached"] is True


def test_a_note_follows_its_text_into_a_renamed_file(q: Path) -> None:
    ann = note(q, CONSIDERED, "--quote", "Neither of these is proved.")
    (q / OUTLINE).rename(q / "drafting/plan.tex")
    got = row(q, ann)
    assert got["target"]["key"] == "drafting/plan.tex#section:2"
    assert (got["detached"], got["anchored"]) == (False, True)


def test_a_note_on_an_equation_whose_label_went_is_read_in_the_block_it_was_in(q: Path) -> None:
    ann = note(q, "dm-0001#eq:fix", "--quote", "x\\in X : \\sigma x = x")
    edit(q / "drafting/nodes/dm-0001.tex", "\\label{eq:fix}", "\\label{eq:fixed}")
    got = row(q, ann)
    assert got["target"]["key"] == "dm-0001"
    assert (got["detached"], got["anchored"]) == (False, True)


def test_an_edit_follows_its_text_into_a_renamed_file_and_is_written_there_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_write_safety import call, suggest, synthetic

    root = synthetic(tmp_path, monkeypatch)
    eid = suggest(
        root,
        "drafting/sections/appendix.tex#remark:1",
        "no gadget has odd order",
        "--quote",
        "gadgets never have odd order",
    )
    assert eid is not None
    (root / "drafting/sections/appendix.tex").rename(root / "drafting/sections/later.tex")
    edit(root / "drafting/main.tex", "\\nest{sections/appendix}", "\\nest{sections/later}")
    assert call(root, "change-keep", {"changes": [eid]})["done"] == [eid]
    text = (root / "drafting/sections/later.tex").read_text()
    assert text.count("no gadget has odd order") == 1 and "gadgets never have odd order" not in text
