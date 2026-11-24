"""A reference's entry read for the views and the intake (`library.entries`): identifiers, decoded words, a work's short name and link, and `@string` written out."""

from __future__ import annotations

import pytest

from loom.library.entries import (
    decode,
    expand_strings,
    identifiers,
    link,
    matchable,
    read_entry,
    short,
    surnames,
    title,
    year,
)


@pytest.mark.parametrize(
    ("raw", "said"),
    [
        ("Kova{\\v{c}}", "Kovač"),
        ('G{\\"o}del', "Gödel"),
        ("Erd\\H{o}s", "Erdős"),
        ("{\\'E}tale cohomology", "Étale cohomology"),
        ("Stra\\ss e and {\\o}re", "Straße and øre"),
        ("Widgets {and} their {B}ounds", "Widgets and their Bounds"),
        ("Pages 1--3 --- a dash", "Pages 1–3 — a dash"),
        ("The $\\ell^2$ {\\emph{norm}} of $\\{x\\}$", "The $\\ell^2$ norm of $\\{x\\}$"),
        ("Fourier~series \\& more", "Fourier series & more"),
        ("{\\c c}a and \\c{C}a", "ça and Ça"),
    ],
)
def test_words_are_decoded_as_a_reader_sees_them(raw: str, said: str) -> None:
    assert decode(raw) == said


def test_an_entry_is_read_with_its_key_and_fields() -> None:
    entry = read_entry(
        "@Article{Smi24,\n  author = {Smith, Jane and Jones, A.},\n  title = {Widgets},\n  year = 2024,\n}\n"
    )
    assert entry is not None
    assert (entry.type, entry.key, entry.fields["year"]) == ("article", "Smi24", "2024")
    assert read_entry("@article{title = {x}}") is None
    assert read_entry("not bibtex") is None


@pytest.mark.parametrize(
    ("fields", "found"),
    [
        ({"doi": "10.1000/XYZ"}, ["doi:10.1000/XYZ"]),
        ({"doi": "https://doi.org/10.1000/xyz"}, ["doi:10.1000/xyz"]),
        ({"doi": "10.48550/arXiv.2401.01234"}, ["arxiv:2401.01234"]),
        ({"eprint": "2401.01234", "archiveprefix": "arXiv", "version": "2"}, ["arxiv:2401.01234v2"]),
        ({"eprint": "math/0601001"}, ["arxiv:math/0601001"]),
        ({"eprint": "hal-001", "eprinttype": "hal"}, []),
        (
            {"doi": "10.1/a", "eprint": "2401.01234", "mrnumber": "123", "zbl": "1.2"},
            ["doi:10.1/a", "arxiv:2401.01234", "mr:123", "zbl:1.2"],
        ),
        ({"url": "https://arxiv.org/abs/2401.01234v3"}, ["arxiv:2401.01234v3"]),
        ({"url": "https://example.org/paper"}, []),
    ],
)
def test_the_identifiers_an_entry_states(fields: dict[str, str], found: list[str]) -> None:
    assert identifiers(fields) == found


def test_identifiers_compare_without_case_or_version() -> None:
    assert matchable("doi:10.1000/XYZ") == "doi:10.1000/xyz"
    assert matchable("arxiv:2401.01234v2") == matchable("arxiv:2401.01234") == "arxiv:2401.01234"
    assert matchable("mr:123") == "mr:123"


@pytest.mark.parametrize(
    ("authors", "named"),
    [
        ("Smith, Jane", "Smith 2024"),
        ("Jane Halberd and Ravel, P.", "Halberd and Ravel 2024"),
        ("A. Vance and B. Wu and C. Xu", "Vance et al. 2024"),
        ("Jan {van der Berg} and others", "van der Berg 2024"),
        ("Kova{\\v{c}}, Ivan", "Kovač 2024"),
    ],
)
def test_a_work_s_short_name(authors: str, named: str) -> None:
    assert short({"author": authors, "year": "2024"}) == named


def test_a_work_with_no_author_is_named_by_its_title_then_its_file() -> None:
    assert short({"title": "The {Stacks} project"}) == "The Stacks project"
    assert short({}, fallback="scan-0042.pdf") == "scan-0042.pdf"
    assert surnames({"editor": "Doe, J."}) == ["Doe"]
    assert year({"date": "2023-05-01"}) == "2023" and year({}) == ""
    assert title({"title": "On {$p$}-adic {L}-functions"}) == "On $p$-adic L-functions"


def test_a_work_s_link() -> None:
    assert link({"url": "https://example.org/p", "doi": "10.1/a"}) == "https://example.org/p"
    assert link({"doi": "10.1/a"}) == "https://doi.org/10.1/a"
    assert link({"eprint": "2401.01234v2"}) == "https://arxiv.org/abs/2401.01234v2"
    assert link({"title": "x"}) is None


def test_string_abbreviations_are_written_out_and_nothing_else_moves() -> None:
    entry = '@article{Jon19,\n  author  = {Jones, Alex},\n  journal = JEx,\n  note    = "see " # JEx # {, vol. 2},\n  month   = jan,\n}\n'
    out = expand_strings(entry, {"jex": "Journal of Examples"})
    assert "journal = {Journal of Examples},\n" in out
    assert "note    = {see Journal of Examples, vol. 2},\n" in out
    assert "  author  = {Jones, Alex},\n" in out and "month   = jan," in out
    assert expand_strings(entry, {}) == entry
    assert read_entry(out) is not None
