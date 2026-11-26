"""Annotations on a Markdown file the viewer draws: named by its path, on words quoted as the file or its page has them, found again after an edit above them, detached when they are gone, and marked on the page the publisher draws of the file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers import json_of, ok, refused
from tests.unit._quilts import demo

AGENT = "Reading Agent"
NOTE = "notes/day1.md"
TEXT = "# Day one\n\nThe *median order* of a graph is `n/2` when $n$ is even.\n\n- [ ] read the **second** proof\n"


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author("Tester")
    root = demo(tmp_path)
    (root / "notes").mkdir()
    (root / NOTE).write_text(TEXT, encoding="utf-8")
    return root


def annotate(q: Path, *args: str) -> str:
    return str(json_of("annotate", *args, "--as", AGENT, "--json", cwd=q, env={"AI_AGENT": "1"})["written"][0]["id"])


def placed(q: Path, ann: str) -> Any:
    from loom.cli._quilt import open_scan
    from loom.records.store import Records

    result = open_scan(str(q))
    return next(r for r in Records(q, result.quilt.history_dir).resolved(result) if r.annotation.id == ann)


def test_words_as_the_page_has_them_anchor_in_the_file_and_stay_on_them_after_an_edit_above(q: Path) -> None:
    ann = annotate(q, NOTE, "--quote", "The median order of a graph is n/2 when $n$ is even", "Say which graphs.")
    res = placed(q, ann)
    assert res.target == NOTE and not res.detached and res.recorded
    assert TEXT[res.span[0] : res.span[1]] == "The *median order* of a graph is `n/2` when $n$ is even"
    # a paragraph put in above the words moves them; the annotation stays on them, and the file it was written on is still kept
    (q / NOTE).write_text(TEXT.replace("# Day one\n", "# Day one\n\nA new first paragraph.\n"), encoding="utf-8")
    now = (q / NOTE).read_text(encoding="utf-8")
    res = placed(q, ann)
    assert not res.detached and res.recorded
    assert now[res.span[0] : res.span[1]].startswith("The *median order*")


def test_an_agent_quotes_the_file_as_written_and_its_words_once_gone_detach_it(q: Path) -> None:
    ann = annotate(q, NOTE, "--quote", "the **second** proof", "Which one?")
    assert placed(q, ann).span is not None
    (q / NOTE).write_text(TEXT.replace("the **second** proof", "both proofs"), encoding="utf-8")
    res = placed(q, ann)
    assert res.detached and res.span is None


def test_a_whole_file_takes_a_comment_and_a_quote_must_stand_once(q: Path) -> None:
    whole = annotate(q, NOTE, "On the whole day.")
    res = placed(q, whole)
    assert res.target == NOTE and not res.detached and res.span is None
    refused("annotate", NOTE, "--quote", "not in it", "x", cwd=q, code=2, match="quote not found in notes/day1.md")
    refused("annotate", NOTE, "--page", "1", "--quote", "graph", "x", cwd=q, code=2, match="Markdown file")


def test_the_files_page_marks_the_words_and_still_does_after_an_edit_above(q: Path) -> None:
    ann = annotate(q, NOTE, "--quote", "the **second** proof", "Which one?")
    whole = f'<mark class="annotation" data-annotation="{ann}">the <strong>second</strong> proof</mark>'

    def page() -> str:
        ok("build", cwd=q)
        return (q / ".loom/cache/site/files" / f"{NOTE}.html").read_text(encoding="utf-8")

    assert whole in page()
    (q / NOTE).write_text(TEXT.replace("# Day one\n", "# Day one\n\nA new first paragraph.\n\n- one\n"), encoding="utf-8")
    drawn = page()
    assert whole in drawn
    # each block names its lines in the file, which is how a mark and a change find their place on the page
    now = (q / NOTE).read_text(encoding="utf-8")
    start = now.index("The *median")
    assert f'<p data-src="{NOTE}:{start}:{now.index(chr(10), start)}">' in drawn


def test_a_link_quotes_words_of_the_file_and_is_a_problem_once_they_are_gone(q: Path) -> None:
    from loom.backlinks import words_found
    from loom.cli._quilt import open_scan

    link = ok("link", NOTE, "--quote", "median order of a graph", cwd=q).output.strip()
    assert link == "[](quilt:notes/day1.md#quote=median%20order%20of%20a%20graph)"
    said = {"kind": "file", "key": NOTE, "place": "", "quote": "median order of a graph"}
    assert words_found(open_scan(str(q)), q, said) is True
    (q / NOTE).write_text(TEXT.replace("median order", "mean order"), encoding="utf-8")
    assert words_found(open_scan(str(q)), q, said) is False
