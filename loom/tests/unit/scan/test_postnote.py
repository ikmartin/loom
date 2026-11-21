"""A citation's postnote in its normal form (`scan.postnote`): abbreviations expanded, page references and filler dropped, and a postnote naming several results split."""

from __future__ import annotations

from loom.scan.postnote import match, normalize, parts


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
