"""What a served quilt's builds remember of the work the build before did: each memo is made once for its inputs, and changing any one input makes it again, exactly as the work done afresh would come out.

The memos of whole parts of a build are tested beside their parts: an agent copy's shape in `test_adopt.py`, a section draft's rendering in `test_section_drafts.py`.
"""

from __future__ import annotations

from dataclasses import fields, replace

import pytest

from loom.render import marks
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
