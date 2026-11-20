"""What a served quilt's builds remember of the work the build before did: each memo is made once for its inputs, and changing any one input makes it again, exactly as the work done afresh would come out.

The memos of whole parts of a build are tested beside their parts: an agent copy's shape in `test_adopt.py`, a section draft's rendering in `test_section_drafts.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any

import pytest

from loom.render import marks, review_compare
from loom.render.marks import MarkEntry, place_marks

HTML = '<p data-src="f.tex:0:60">Let X be a finite widget. Then the count is even.</p>'
#: The same words shown as their source, where an entry is placed by its offsets rather than by its quote.
SOURCE = '<pre class="source" data-src="f.tex:0:60">Let X be a finite widget. Then the count is even.</pre>'
ENTRY = MarkEntry("a-1", "finite widget", "f.tex", 11, 24)
GONE = MarkEntry("a-1", "finite widget", "f.tex", 24, 24, gone=True)
OTHER = replace(ENTRY, ann_id="a-2")

#: Each input of a placement changed alone, as (fragment, entries) before and after: the fragment, then every field of an entry that the placement reads, then the entries' order.
PLACEMENTS = {
    "the fragment": ((HTML, [ENTRY]), (HTML.replace("is even", "is odd"), [ENTRY])),
    "an entry's id": ((HTML, [ENTRY]), (HTML, [OTHER])),
    "an entry's quote": ((HTML, [ENTRY]), (HTML, [replace(ENTRY, quote="count is even")])),
    "an entry's file": ((HTML, [ENTRY]), (HTML, [replace(ENTRY, file="g.tex")])),
    "an entry's start": ((SOURCE, [ENTRY]), (SOURCE, [replace(ENTRY, start=4)])),
    "an entry's end": ((SOURCE, [ENTRY]), (SOURCE, [replace(ENTRY, end=30)])),
    "whether its words are gone": ((HTML, [ENTRY]), (HTML, [GONE])),
    "whether a gone mark leads": ((HTML, [GONE]), (HTML, [replace(GONE, lead=True)])),
    "whether it moved": ((HTML, [ENTRY]), (HTML, [replace(ENTRY, moved=True)])),
    "the entries' order": ((HTML, [ENTRY, OTHER]), (HTML, [OTHER, ENTRY])),
}


@pytest.fixture
def placing(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """A placement memo with nothing in it, and a count of the placements actually made."""
    made: list[int] = []
    place = marks._place
    monkeypatch.setattr(marks, "_place", lambda html, entries: made.append(1) or place(html, entries))
    marks._placed.clear()
    return made


@pytest.mark.parametrize("changed", sorted(PLACEMENTS))
def test_a_placement_is_made_once_and_again_when_any_input_changes(changed: str, placing: list[int]) -> None:
    (html, entries), (html_after, entries_after) = PLACEMENTS[changed]
    first = place_marks(html, entries)
    assert place_marks(html, entries) == first and len(placing) == 1
    again = place_marks(html_after, entries_after)
    assert len(placing) == 2
    assert again == marks._place(html_after, entries_after) != first


def test_a_placement_is_named_by_every_field_of_every_entry() -> None:
    """A field added to `MarkEntry` is part of the placement's key without anyone remembering to add it."""
    named = marks._placing(HTML, [ENTRY])[1][0]
    assert len(named) == len(fields(MarkEntry))
    assert marks._placing(HTML, [ENTRY]) != marks._placing(HTML, [replace(ENTRY, in_doc="d.tex")])


BEFORE, AFTER = "Every finite widget is even.", "Every finite gadget is even."


@pytest.fixture
def comparing(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    made: list[int] = []
    changes = review_compare.word_changes
    monkeypatch.setattr(review_compare, "word_changes", lambda *a: made.append(1) or changes(*a))
    review_compare._compared.clear()
    return made


@pytest.mark.parametrize("side", ["before", "after"])
def test_a_word_comparison_is_made_once_and_again_when_either_text_changes(side: str, comparing: list[int]) -> None:
    first = review_compare._changed(BEFORE, AFTER)
    assert review_compare._changed(BEFORE, AFTER) == first and len(comparing) == 1
    before, after = (BEFORE + " Indeed.", AFTER) if side == "before" else (BEFORE, AFTER + " Indeed.")
    again = review_compare._changed(before, after)
    assert again == review_compare.word_changes(before, after, lambda word: word) != first
    assert len(comparing) == 3


def test_a_remembered_comparison_is_handed_out_as_a_copy(comparing: list[int]) -> None:
    """A caller that changes the spans it was given changes nothing the next caller is given."""
    left, _ = review_compare._changed(BEFORE, AFTER)
    left.append([0, 1])
    left[0].append(99)
    assert review_compare._changed(BEFORE, AFTER) == review_compare.word_changes(BEFORE, AFTER, lambda word: word)


@pytest.fixture
def rendering(monkeypatch: pytest.MonkeyPatch) -> tuple[list[int], Callable[..., str]]:
    """A memo of rendered bodies with nothing in it, a count of the bodies actually rendered, and the rendering itself."""
    from loom.records import store

    made: list[int] = []
    real = store._render_markdown
    monkeypatch.setattr(store, "_render_markdown", lambda *a: made.append(1) or real(*a))
    store._rendered.clear()
    return made, real


def test_a_body_is_rendered_once_and_again_when_its_text_changes(
    rendering: tuple[list[int], Callable[..., str]],
) -> None:
    from loom.records.store import render_markdown

    made, real = rendering
    first = render_markdown("A note on $x$, **bold**.")
    assert render_markdown("A note on $x$, **bold**.") == first == real("A note on $x$, **bold**.", None, None)
    assert len(made) == 1
    again = render_markdown("A note on $y$, **bold**.")
    assert len(made) == 2 and again == real("A note on $y$, **bold**.", None, None) != first


@pytest.mark.parametrize("given", ["tokens", "raw"])
def test_a_body_rendered_with_a_callable_is_rendered_every_time(
    rendering: tuple[list[int], Callable[..., str]], given: str
) -> None:
    """What a callable does is not part of any key, so a body given one is never remembered."""
    from loom.records.store import render_markdown

    made, _ = rendering
    kw: dict[str, Any] = (
        {"tokens": lambda parsed: None} if given == "tokens" else {"raw": lambda piece, words: "<b>x</b>"}
    )
    render_markdown("A <i>note</i>.", **kw)
    render_markdown("A <i>note</i>.", **kw)
    assert len(made) == 2


@pytest.fixture
def hashing(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """A memo of text hashes with nothing in it, and a count of the texts actually normalised."""
    from loom.scan import hashing as H

    made: list[int] = []
    real = H.normalize
    monkeypatch.setattr(H, "normalize", lambda text: made.append(1) or real(text))
    H._hashed.clear()
    return made


def test_a_text_is_hashed_once_and_again_when_it_changes(hashing: list[int]) -> None:
    from loom.scan.hashing import hash_text, normalize, sha256

    text = "Let $x$ be a widget.\n% a comment\n\\label{a}\n"
    first = hash_text(text)
    assert hash_text(text) == first == sha256(normalize(text)) and len(hashing) == 2
    changed = text.replace("$x$", "$y$")
    assert hash_text(changed) == sha256(normalize(changed)) != first and len(hashing) == 4


def test_a_text_with_a_lone_surrogate_in_a_comment_is_hashed_as_before(hashing: list[int]) -> None:
    """`normalize` drops a comment line, so a surrogate there never reached the hash; the memo's key takes it too."""
    from loom.scan.hashing import hash_text, normalize, sha256

    text = "% a comment with a lone surrogate \udc80\nx\n"
    assert hash_text(text) == sha256(normalize(text))
