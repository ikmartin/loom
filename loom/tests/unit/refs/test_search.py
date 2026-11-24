"""A page search of a stored PDF (`refs.search`), which the Library's find reads: terms folded so case, ligatures and a word's hyphen do not hide a page, every term on the page, each page scored and shown by a snippet; and an exact phrase found by page."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.refs.search import grep_work, search_pages, snippet, terms_of


def pages(tmp_path: Path, *texts: str) -> Path:
    """A PDF's page text as `pages.mapped` keeps it, with no section map."""
    home = tmp_path / "home"
    (home / "pages").mkdir(parents=True)
    for n, text in enumerate(texts, 1):
        (home / "pages" / f"{n:04d}.txt").write_text(text, encoding="utf-8")
    return home


def test_a_search_s_terms_are_folded_each_once() -> None:
    assert terms_of("Pull-back  the ﬁbre pullback") == ["pullback", "the", "fibre"]


def test_a_page_holding_every_term_is_found_however_it_writes_them(tmp_path: Path) -> None:
    home = pages(
        tmp_path,
        "The Pull-back of a ﬁbre bundle.",
        "A pullback, and the pullback again, of the fibre.",
        "A fibre alone.",
    )
    hits = search_pages(home, "tq-00A1-ref", terms_of("pullback fibre"))
    assert [(h.ref, h.page, h.score) for h in hits] == [("tq-00A1-ref", 1, 2), ("tq-00A1-ref", 2, 3)]
    assert (
        hits[0].section == "" and hits[0].context == "The Pullback of a fibre bundle."
    )  # its case kept, its ligature not
    assert search_pages(home, "tq-00A1-ref", []) == []


def test_a_snippet_opens_at_the_first_term_it_holds() -> None:
    text = "Words before. " * 10 + "The main theorem follows."
    assert snippet(text, ["theorem"]).startswith("…") and "main theorem follows" in snippet(text, ["theorem"])
    assert snippet("Short text.", ["absent"]) == "Short text."


def test_an_exact_phrase_is_found_by_page(tmp_path: Path) -> None:
    home = pages(tmp_path, "a perfect ob-\nstruction theory E", "nothing here")
    [hit] = grep_work(home, "tq-00A1-ref", "perfect obstruction theory")
    assert hit.page == 1 and "perfect obstruction theory" in hit.context


@pytest.mark.poppler
def test_a_stored_pdf_is_searched_by_its_pages(tmp_path: Path) -> None:
    """On the showcase's Bellamy19, the page text derived from the stored PDF the first time it is asked for."""
    from loom.library.references import entries
    from loom.library.store import read
    from loom.refs.pages import mapped
    from tests.unit._quilts import showcase

    root = showcase(tmp_path)
    ref, _entry = entries(root)["Bellamy19"]
    node = read(root, ref)
    assert node is not None and node.pdf
    home = mapped(root, node.pdf)
    assert home is not None
    hits = search_pages(home, ref, terms_of("median orders bijection"))
    assert 2 in [h.page for h in hits] and all(h.score >= 3 for h in hits)
    assert [h.page for h in grep_work(home, ref, "are in bijection with the vertices")] == [2]
