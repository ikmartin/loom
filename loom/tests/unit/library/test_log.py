"""The library's log (`library.log`): one line an act, what it says of a reference (unconfirmed, followed, deleted), and the lines that are no act."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.library.log import problems, record, replay
from loom.paths import LIBRARY_LOG

LOOM = {"by": "loom", "kind": "loom"}
ME = {"by": "Isaac", "kind": "person"}


def test_an_act_is_one_line_with_who_and_when(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T09:00:00Z")
    record(
        tmp_path,
        "made",
        "tq-00A1-ref",
        how="drop",
        found_by="arxiv",
        looked_up=False,
        source="2401.01234v2.pdf",
        key="Smi24",
        **ME,
    )
    [line] = (tmp_path / LIBRARY_LOG).read_text(encoding="utf-8").splitlines()
    assert json.loads(line) == {
        "event": "made", "ref": "tq-00A1-ref", "by": "Isaac", "kind": "person", "at": "2026-11-21T09:00:00Z",
        "how": "drop", "found_by": "arxiv", "looked_up": False, "source": "2401.01234v2.pdf", "key": "Smi24",
    }  # fmt: skip


def test_an_act_or_key_the_log_does_not_have_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no act starred"):
        record(tmp_path, "starred", "tq-00A1-ref", **ME)
    with pytest.raises(ValueError, match="a made act has no colour"):
        record(tmp_path, "made", "tq-00A1-ref", colour="red", **ME)
    with pytest.raises(ValueError, match="person, an agent or loom"):
        record(tmp_path, "edited", "tq-00A1-ref", by="x", kind="robot")


def test_a_reference_from_an_identifier_is_unconfirmed_until_looked_up(tmp_path: Path) -> None:
    record(tmp_path, "made", "tq-00A1-ref", how="drop", found_by="arxiv", looked_up=False, **ME)
    record(tmp_path, "made", "tq-00B1-ref", how="drop", found_by="arxiv", looked_up=True, **ME)
    record(tmp_path, "made", "tq-00C1-ref", how="paste", found_by="entry", looked_up=False, **ME)
    acts = replay(tmp_path)
    assert (acts.unconfirmed("tq-00A1-ref"), acts.unconfirmed("tq-00B1-ref"), acts.unconfirmed("tq-00C1-ref")) == (
        True,
        False,
        False,
    )
    record(tmp_path, "looked-up", "tq-00A1-ref", identifier="arxiv:2401.01234", found=False, **ME)
    assert replay(tmp_path).unconfirmed("tq-00A1-ref"), "a look-up that found nothing confirms nothing"
    record(tmp_path, "looked-up", "tq-00A1-ref", identifier="arxiv:2401.01234", found=True, **ME)
    assert not replay(tmp_path).unconfirmed("tq-00A1-ref")


def test_a_gathered_reference_follows_its_bib_until_edited_in_loom(tmp_path: Path) -> None:
    record(tmp_path, "made", "tq-00A1-ref", how="gather", found_by="entry", source="refs.bib", key="Smi24", **LOOM)
    record(tmp_path, "made", "tq-00B1-ref", how="drop", found_by="doi", **ME)
    acts = replay(tmp_path)
    assert acts.follows("tq-00A1-ref") and not acts.follows("tq-00B1-ref")
    record(tmp_path, "followed", "tq-00A1-ref", source="refs.bib", **LOOM)
    assert replay(tmp_path).follows("tq-00A1-ref")
    record(tmp_path, "edited", "tq-00A1-ref", **ME)
    assert not replay(tmp_path).follows("tq-00A1-ref")


def test_a_deleted_key_stays_deleted_until_made_or_restored(tmp_path: Path) -> None:
    record(tmp_path, "made", "tq-00A1-ref", how="gather", key="Smi24", **LOOM)
    record(tmp_path, "deleted", "tq-00A1-ref", key="Smi24", undo="u-1", **ME)
    assert replay(tmp_path).deleted_keys() == {"Smi24"}
    record(tmp_path, "restored", "tq-00A1-ref", undo="u-1", **ME)
    assert replay(tmp_path).deleted_keys() == set()
    record(tmp_path, "deleted", "tq-00A1-ref", key="Smi24", undo="u-2", **ME)
    record(tmp_path, "made", "tq-00B1-ref", how="drop", key="Smi24", **ME)
    assert replay(tmp_path).deleted_keys() == set(), "added again by the person"


def test_a_line_that_is_no_act_is_skipped_and_said(tmp_path: Path) -> None:
    record(tmp_path, "edited", "tq-00A1-ref", **ME)
    with (tmp_path / LIBRARY_LOG).open("a", encoding="utf-8") as fh:
        fh.write("<<<<<<< HEAD\n")
        fh.write(json.dumps({"event": "edited", "ref": "tq-00A1-ref", "by": "x", "kind": "person"}) + "\n")
    acts = replay(tmp_path)
    assert [a["event"] for a in acts.of("tq-00A1-ref")] == ["edited"]
    assert [(d.code, d.locations[0].line) for d in problems(acts)] == [
        ("loom:foreign-library-acts", 2),
        ("loom:foreign-library-acts", 3),
    ]
