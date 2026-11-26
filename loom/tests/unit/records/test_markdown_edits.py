"""Suggested edits on a Markdown file the viewer draws: filed on the file by its path and words of it as written, listed with what waits on the person, kept through the door into exactly the words quoted and undone back to every byte, discarded leaving every byte, and kept or discarded by the person alone."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import json_of, ok, refused
from tests.unit._quilts import demo

AGENT = "Reading Agent"
NOTE = "notes/day1.md"
TEXT = "# Day one\r\n\r\nThe median order of a graph is $n/2$ when $n$ is even.\r\n\r\nRead the second proof.\r\n"
AS_AGENT = {"env": {"AI_AGENT": "1"}}


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author("Tester")
    root = demo(tmp_path)
    (root / "notes").mkdir()
    (root / NOTE).write_bytes(TEXT.encode("utf-8"))
    return root


def suggest(q: Path, *args: str) -> str:
    return str(json_of("suggest", NOTE, *args, "--as", AGENT, "--json", cwd=q, **AS_AGENT)["edit"])


def listed(q: Path, edit: str) -> dict[str, Any]:
    return next(c for c in json_of("changes", "--json", cwd=q)["changes"] if c["id"] == edit)


def events(q: Path, edit: str) -> list[str]:
    lines = (q / ".loom/records/edits/log.jsonl").read_text(encoding="utf-8").splitlines()
    return [e["event"] for e in map(json.loads, lines) if e["id"] == edit]


def test_kept_after_an_edit_above_it_writes_exactly_its_words_and_carries_the_annotation_on_them(q: Path) -> None:
    edit = suggest(q, "--quote", "the second proof", "--with", "both proofs", "--comment", "The first is shorter.")
    note = json_of(
        "annotate", NOTE, "--quote", "Read the second proof", "Which?", "--as", AGENT, "--json", cwd=q, **AS_AGENT
    )
    ann = note["written"][0]["id"]
    row = listed(q, edit)
    assert (row["kind"], row["path"], row["key"], row["state"]) == ("suggested", NOTE, None, "ready")
    assert "-Read the second proof." in ok("changes", edit, cwd=q).output
    # the person writes a paragraph above it: the edit still goes on its words, and nothing else of the file moves
    (q / NOTE).write_bytes(TEXT.replace("# Day one\r\n", "# Day one\r\n\r\nA paragraph above.\r\n").encode("utf-8"))
    before = (q / NOTE).read_bytes()
    ok("changes", "--keep", edit, cwd=q)
    assert (q / NOTE).read_bytes() == before.replace(b"Read the second proof.", b"Read both proofs.")
    assert events(q, edit) == ["created", "kept"]
    # the annotation on the words the edit replaced stands on its new words
    from loom.cli._quilt import open_scan
    from loom.records.store import Records

    result = open_scan(str(q))
    res = next(r for r in Records(q).resolved(result) if r.annotation.id == ann)
    assert not res.detached and res.annotation.earlier == {"quote": "Read the second proof", "change": edit}
    # and its Keep undone puts back exactly the words it replaced, the edit open again
    from loom.pending import unkeep

    done, no = unkeep(result, "Tester", [edit], ("human", "Tester"))
    assert (done, no) == ([edit], [])
    assert (q / NOTE).read_bytes() == before and events(q, edit) == ["created", "kept", "reopened"]
    # the annotation the Keep carried onto the new words is carried back onto the words put back
    result = open_scan(str(q))
    res = next(r for r in Records(q).resolved(result) if r.annotation.id == ann)
    assert not res.detached and res.annotation.selector.exact.startswith("Read the second proof")


def test_discarded_it_leaves_every_byte_and_only_the_person_keeps_or_discards(q: Path) -> None:
    edit = suggest(q, "--quote", "$n/2$", "--with", "$\\lfloor n/2 \\rfloor$")
    before = (q / NOTE).read_bytes()
    refused("changes", "--keep", edit, cwd=q, code=2, match="the author's", **AS_AGENT)
    refused("changes", "--discard", edit, cwd=q, code=2, match="the author's", **AS_AGENT)
    ok("changes", "--discard", edit, cwd=q)
    assert (q / NOTE).read_bytes() == before
    assert events(q, edit) == ["created", "discarded"]
    assert all(c["id"] != edit for c in json_of("changes", "--json", cwd=q)["changes"])


def test_an_agent_quotes_the_file_once_and_withdraws_its_own(q: Path) -> None:
    refused("suggest", NOTE, "--with", "x", "--as", AGENT, cwd=q, code=2, match="--quote", **AS_AGENT)
    refused(
        "suggest", NOTE, "--quote", "is", "--with", "was", "--as", AGENT, cwd=q, code=2, match="ambiguous", **AS_AGENT
    )
    edit = suggest(q, "--quote", "is even.", "--with", " (an even number)", "--after")
    assert listed(q, edit)["state"] == "ready"
    ok("suggest", "--withdraw", edit, "--as", AGENT, cwd=q, **AS_AGENT)
    assert events(q, edit) == ["created", "discarded"]
    assert (q / NOTE).read_bytes() == TEXT.encode("utf-8")


def test_a_file_that_moves_while_its_edit_is_kept_is_placed_again_and_never_written_at_a_stale_place(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import loom.history.acts as acts
    from loom.cli._quilt import open_scan
    from loom.pending import keep

    edit = suggest(q, "--quote", "the second proof", "--with", "both proofs")
    moved = TEXT.replace("# Day one\r\n", "# Day one\r\n\r\nA paragraph the person typed.\r\n").encode("utf-8")
    real = acts.keep_versions

    def typing(*args: Any, **kw: Any) -> Any:
        # the person saves while loom keeps a version before writing
        out = real(*args, **kw)
        if (q / NOTE).read_bytes() != moved:
            (q / NOTE).write_bytes(moved)
        return out

    monkeypatch.setattr(acts, "keep_versions", typing)
    done, refused_ = keep(open_scan(str(q)), "Tester", [edit], ("human", "Tester"))
    now = (q / NOTE).read_bytes()
    assert b"A paragraph the person typed." in now
    if done:
        assert now == moved.replace(b"Read the second proof.", b"Read both proofs.")
    else:
        assert now == moved and refused_[0]["code"] == "changed"
