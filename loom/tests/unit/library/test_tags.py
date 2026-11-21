"""The tag log (`library.tags`): who may take a tag off, a tag's case, what is written and what is not, and the lines that are not tags."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loom.library.node import node_hash
from loom.library.tags import TagRefused, normalise, problems, replay, tag, untag
from loom.paths import LIBRARY_NODES, TAG_LOG
from tests.unit.library._store import quilt

ME = {"by": "Isaac Martin", "kind": "person"}
AGENT = {"by": "Claude agent", "kind": "agent"}
OTHER_AGENT = {"by": "Codex agent", "kind": "agent"}


def lines(root: Path) -> list[dict[str, str]]:
    return [json.loads(line) for line in (root / TAG_LOG).read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize(
    ("typed", "tag_"),
    [("  open   problem ", "open problem"), ("14A20", "14A20"), ("Hodge\ttheory", "Hodge theory"), ("über", "über")],
)
def test_a_tag_is_stripped_and_spaced_and_keeps_its_case(typed: str, tag_: str) -> None:
    assert normalise(typed) == tag_


@pytest.mark.parametrize(
    ("typed", "said"), [("   ", "at least one character"), ("x" * 65, "at most 64"), ("a\x07b", "control")]
)
def test_a_tag_that_is_no_word_is_refused(typed: str, said: str) -> None:
    with pytest.raises(TagRefused, match=said):
        normalise(typed)


def test_a_tag_is_one_line_saying_who_and_when(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T09:00:00Z")
    root = quilt(tmp_path)
    before = node_hash((root / LIBRARY_NODES / "tq-00K3.node").read_bytes())
    assert tag(root, "tq-00K3", "compactness", **ME) is True
    assert lines(root) == [
        {
            "event": "tag",
            "node": "tq-00K3",
            "tag": "compactness",
            "by": "Isaac Martin",
            "kind": "person",
            "at": "2026-11-21T09:00:00Z",
        }
    ]
    assert node_hash((root / LIBRARY_NODES / "tq-00K3.node").read_bytes()) == before
    assert replay(root).of("tq-00K3") == ["compactness"]


def test_tagging_again_what_one_already_tagged_writes_nothing(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    assert tag(root, "tq-00K3", "compactness", **ME)
    assert tag(root, "tq-00K3", "Compactness", **ME) is False
    assert tag(root, "tq-00K3", "compactness", **AGENT) is True
    assert len(lines(root)) == 2


def test_two_tags_equal_ignoring_case_are_one_shown_as_first_written(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "14A20", **ME)
    tag(root, "tq-00K5", "14a20", **AGENT)
    tags = replay(root)
    assert tags.of("tq-00K3") == tags.of("tq-00K5") == ["14A20"]
    assert tags.nodes("14a20") == ["tq-00K3", "tq-00K5"]


def test_a_node_not_in_the_library_is_not_tagged(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    with pytest.raises(TagRefused, match="tq-00Z9 is not in the library"):
        tag(root, "tq-00Z9", "x", **ME)
    with pytest.raises(TagRefused, match="person or an agent"):
        tag(root, "tq-00K3", "x", by="Someone", kind="robot")
    assert not (root / TAG_LOG).exists()


def test_a_person_takes_off_any_tag_for_everyone(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "bounded", **AGENT)
    tag(root, "tq-00K3", "bounded", **OTHER_AGENT)
    assert untag(root, "tq-00K3", "BOUNDED", **ME) is True
    assert replay(root).of("tq-00K3") == []
    assert untag(root, "tq-00K3", "bounded", **ME) is False


def test_an_agent_takes_off_only_its_own(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "bounded", **ME)
    tag(root, "tq-00K3", "bounded", **AGENT)
    assert untag(root, "tq-00K3", "bounded", **AGENT) is True
    assert replay(root).of("tq-00K3") == ["bounded"], "the person's tag still stands"
    with pytest.raises(
        TagRefused, match="an agent takes off only its own tags, and Isaac Martin put bounded on tq-00K3"
    ):
        untag(root, "tq-00K3", "bounded", **OTHER_AGENT)
    assert replay(root).held("tq-00K3", "bounded") == {"Isaac Martin"}


def test_the_log_is_only_appended_to(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "a", **ME)
    first = (root / TAG_LOG).read_text(encoding="utf-8")
    untag(root, "tq-00K3", "a", **ME)
    assert (root / TAG_LOG).read_text(encoding="utf-8").startswith(first)


def test_a_line_that_is_not_a_tag_is_skipped_and_said(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "kept", **ME)
    with (root / TAG_LOG).open("a", encoding="utf-8") as fh:
        fh.write("<<<<<<< HEAD\n")
        fh.write(
            json.dumps({"event": "star", "node": "tq-00K3", "tag": "x", "by": "a", "kind": "person", "at": "t"}) + "\n"
        )
        fh.write(
            json.dumps({"event": "tag", "node": "widget", "tag": "x", "by": "a", "kind": "person", "at": "t"}) + "\n"
        )
        fh.write(
            json.dumps({"event": "tag", "node": "tq-00K5", "tag": " spaced ", "by": "a", "kind": "person", "at": "t"})
            + "\n"
        )
        fh.write(
            json.dumps({"event": "tag", "node": "tq-00K5", "tag": "fine", "by": "a", "kind": "person", "at": "t"})
            + "\n"
        )
    tags = replay(root)
    assert tags.of("tq-00K3") == ["kept"] and tags.of("tq-00K5") == ["fine"]
    said = problems(tags)
    assert [(d.code, d.locations[0].line) for d in said] == [("loom:foreign-tags", n) for n in (2, 3, 4, 5)]
    assert said[0].message == f"Line 2 of {TAG_LOG} is not a tag or an untag (it is not JSON), so it is skipped."
    assert {d.class_ for d in said} == {"internal"}


# ---- the review's findings ---------------------------------------------------------------------------------------------


def test_a_tag_composed_or_decomposed_is_one_tag(tmp_path: Path) -> None:
    """N-8: `café` typed with é and with e and a combining accent."""
    root = quilt(tmp_path)
    assert tag(root, "tq-00K3", "café", **ME)
    assert tag(root, "tq-00K3", "café", **AGENT) is not False or replay(root).held("tq-00K3", "café") == {
        "Isaac Martin",
        "Claude agent",
    }
    assert replay(root).of("tq-00K3") == ["café"]
    assert untag(root, "tq-00K3", "CAFÉ", **ME)
    assert replay(root).of("tq-00K3") == []


@pytest.mark.parametrize("separator", ["\x1c", "\x1d", "\x1e", "\x1f", "\x85"])
def test_a_tag_holding_a_separator_is_refused_not_spaced(separator: str) -> None:
    """N-20: Python's `split` takes these for spaces; they are control characters."""
    with pytest.raises(TagRefused, match="control"):
        normalise(f"open{separator}problem")


def test_an_id_in_the_wrong_case_is_not_tagged(tmp_path: Path) -> None:
    """N-5: on a file system blind to case `TQ-00K3` finds `tq-00K3.node`, a file of another id."""
    root = quilt(tmp_path)
    with pytest.raises(TagRefused, match="not in the library"):
        tag(root, "TQ-00K3", "bounds", **ME)
    assert not (root / TAG_LOG).exists()


@pytest.mark.parametrize("bad", ["../../victim", "tq-00K3/../tq-00K5", ""])
def test_what_is_no_id_is_neither_tagged_nor_untagged(tmp_path: Path, bad: str) -> None:
    """N-6."""
    root = quilt(tmp_path)
    (tmp_path / "victim.node").write_text("x")
    for act in (tag, untag):
        with pytest.raises(TagRefused, match="not a node's id"):
            act(root, bad, "bounds", **ME)


def test_a_line_cut_short_costs_that_line_alone(tmp_path: Path) -> None:
    """N-20: a crash mid-append left half a line; the next tag starts a line of its own."""
    root = quilt(tmp_path)
    tag(root, "tq-00K3", "first", **ME)
    with (root / TAG_LOG).open("a", encoding="utf-8") as fh:
        fh.write('{"event": "tag", "node": "tq-00K5", "ta')
    assert tag(root, "tq-00K5", "second", **ME)
    tags = replay(root)
    assert tags.of("tq-00K3") == ["first"] and tags.of("tq-00K5") == ["second"]
    assert [n for n, _ in tags.skipped] == [2]
