"""A citation's postnote in its normal form (`scan.postnote`): abbreviations expanded, page references and filler dropped, and a postnote naming several results split."""

from __future__ import annotations

import pytest

from loom.scan.postnote import located, match, normalize, parts


def test_postnote_normalization_table() -> None:
    assert normalize("Theorem 4.1") == "theorem 4.1"
    assert normalize("Thm.~4.1, p.~12") == "theorem 4.1"
    assert normalize("Section 4") == "section 4" == normalize("\\S 4") == normalize("§4") == normalize("Sec. IV")
    assert normalize("see Prop. 3.11") == "proposition 3.11" == normalize("Proposition 3.11 (2)")
    assert normalize("\\href{https://stacks.math.columbia.edu/tag/04Y5}{Tag 04Y5}") == "tag 04y5"
    assert normalize("Cor. A.31") == "corollary a.31" and normalize("Rmk A.19") == "remark a.19"
    assert normalize("pp.~12--14") == ""
    assert parts("Theorems 4.1 and 4.3") == ["theorem 4.1", "theorem 4.3"]
    assert parts("Thm. A.20, Rmk A.19") == ["theorem a.20", "remark a.19"]
    assert parts("Theorem 4.1, p.~12") == ["theorem 4.1"]
    assert parts("Standing assumptions, Section 1") == [
        "standing assumption",
        "section 1",
    ]  # plurals fold on both sides


def test_a_postnote_matches_the_results_any_of_its_parts_names() -> None:
    candidates = [("a", {"theorem 4.1", "proposition 4.1"}), ("b", {"theorem 4.3"}), ("c", {"lemma 2.2"})]
    assert match("Theorems 4.1 and 4.3", candidates) == ["a", "b"]
    assert match("p.~12", candidates) == []


@pytest.mark.parametrize(
    ("postnote", "results"),
    [
        ("Lemma 2.1", [("lemma", "2.1")]),
        ("Lemma~2.1 and Theorem 3", [("lemma", "2.1"), ("theorem", "3")]),
        ("Lemmas 2.1 and 2.4", [("lemma", "2.1"), ("lemma", "2.4")]),
        ("Thm. 4.2(ii)", [("theorem", "4.2")]),
        ("Prop. A.3", [("proposition", "A.3")]),
        ("Theorem II", [("theorem", "II")]),
        ("Cor. 3.5, p. 12", [("corollary", "3.5")]),
        ("Chapter 2, Lemma 2.3", [("lemma", "2.3")]),
        ("p.~5", []),
        ("Section 3", []),
        ("Equation (3.2)", []),
        ("Theorem", []),
    ],
)
def test_a_postnote_locates_each_result_it_names_by_its_printed_number(postnote: str, results: list) -> None:
    """A stub is made for each, so a number keeps its case and its numerals as the citation prints it; a part of a work, a page, a display names no result."""
    assert located(postnote) == results
