"""A mark to digest is an annotation with the purpose `to-digest`: the person's alone, on a page of a cited work, left out of every list of notes, and shown to an agent where a `digest` ask names it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.evidence import asks
from loom.evidence.subjects import Who
from loom.records.annotations import load_records
from loom.render.api import ApiError, handle
from tests.helpers import json_of, ok
from tests.unit._quilts import showcase

PERSON = "A. Author"
#: The showcase's Arden24 has its PDF in the store, and these words on its page 2.
WORK, PAGE, WORDS = "Arden24", 2, "a saturated sublattice of the lattice of weightings"
pytestmark = pytest.mark.poppler


def mapped(tmp_path: Path) -> tuple[Path, str]:
    return showcase(tmp_path), WORK


def _mark(q: Path, ck: str, **extra: object) -> str:
    said = handle(
        q,
        "annotate",
        {"target": ck, "page": PAGE, "quote": WORDS, "purpose": "to-digest", "author": PERSON, **extra},
    )
    return str(said["result"]).split()[0]


def _annotations(q: Path) -> dict[str, object]:
    return {a.id: a for rec in load_records(q)[0] for a in rec.annotations}


def test_a_person_marks_a_place_on_a_works_page_to_digest(tmp_path: Path) -> None:
    q, ck = mapped(tmp_path)
    mark = _mark(q, ck)
    found = _annotations(q)[mark]
    assert found.purpose == "to-digest" and found.to_dict()["purpose"] == "to-digest"  # type: ignore[attr-defined]
    note = handle(
        q, "annotate", {"target": ck, "page": PAGE, "quote": WORDS, "message": "a note", "author": PERSON}
    )
    assert "purpose" not in _annotations(q)[str(note["result"]).split()[0]].to_dict()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("extra", "why"),
    [
        ({"author": "Reader Agent"}, "an agent asks with"),
        ({"purpose": "to-read"}, "not a purpose"),
        ({"page": None}, "on a page of a cited work"),
    ],
)
def test_a_mark_to_digest_is_the_persons_on_a_works_page(tmp_path: Path, extra: dict, why: str) -> None:
    q, ck = mapped(tmp_path)
    with pytest.raises(ApiError, match=why):
        _mark(q, ck, **extra)


def test_a_mark_on_a_result_of_a_draft_is_refused(tmp_path: Path) -> None:
    q, _ck = mapped(tmp_path)
    with pytest.raises(ApiError, match="on a page of a cited work"):
        handle(q, "annotate", {"target": "sh-0003", "purpose": "to-digest", "message": "", "author": PERSON})


def test_no_list_of_notes_holds_a_mark_and_a_digest_ask_shows_where_it_stands(tmp_path: Path) -> None:
    q, ck = mapped(tmp_path)
    mark = _mark(q, ck)
    assert mark not in ok("ai", "annotations", "--json", cwd=q).output
    assert mark not in json.dumps(json_of("status", "--reading", "--json", cwd=q).get("reading", []))
    task = asks.ask(
        q,
        Who("person", PERSON),
        "digest",
        "agent",
        {"ref": "sh-00A1-ref", "page": PAGE},
        ref="sh-00A1-ref",
        scope="marked",
        marks=[mark],
    )
    listed = json_of("tasks", "--json", cwd=q)
    [row] = [r for r in listed["tasks"] if r["id"] == task.id]
    [place] = row["mark_places"]
    assert place["mark"] == mark and place["page"] == PAGE and place["quote"] == WORDS


def test_a_purpose_loom_does_not_know_reads_as_a_note_and_is_said(tmp_path: Path) -> None:
    q, ck = mapped(tmp_path)
    mark = _mark(q, ck)
    log = q / ".loom/records/annotations/log.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    changed = [json.dumps({**json.loads(line), "purpose": "to-weigh"}) if mark in line else line for line in lines]
    log.write_text("\n".join(changed) + "\n", encoding="utf-8")
    records, problems = load_records(q)
    assert _annotations(q)[mark].purpose is None  # type: ignore[attr-defined]
    assert any("'to-weigh' is not a purpose" in p for p in problems)
