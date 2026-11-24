"""What a document states of itself (`refs.ingest`): the identifier it prints as its own on its first page, and the title a reference manager's file name gives it."""

from __future__ import annotations

import pytest

from loom.refs.ingest import own_identifiers


def test_an_identifier_printed_under_the_byline_is_the_documents_own() -> None:
    """The showcase's Arden PDFs print their arXiv id on a line of its own under the byline, not in arXiv's margin."""
    dois, arxivs, stamped = own_identifiers(
        "Cycle spaces of finite quivers\nElspeth Arden\narXiv:2504.01234v1\nAbstract\n"
    )
    assert (dois, arxivs, stamped) == (set(), {"2504.01234v1"}, set())


@pytest.mark.parametrize(
    "head",
    [
        "Erratum to doi:10.4171/showcase/19-2",
        "Comment on arXiv:0805.2065",
        "Reply to the comment on arXiv:0805.2065",
        "Corrigendum to arXiv:0805.2065",
    ],
)
def test_an_identifier_after_erratum_to_or_comment_on_is_the_answered_works(head: str) -> None:

    page = f"{head}\nErratum: Median orders on weighted digraphs\nRosalind Bellamy\nWe correct Lemma 3.\n"
    assert own_identifiers(page)[:2] == (set(), set())


@pytest.mark.parametrize(
    ("head", "doi"),
    [
        (
            "The Review of Symbolic Logic, Volume 12, Number 3, doi:10.1017/S1755020319000182",
            "10.1017/s1755020319000182",
        ),
        ("Review of Economic Studies (2020) 87, 1-30 doi:10.1093/restud/rdz001", "10.1093/restud/rdz001"),
        ("Supplement to the Annals of Statistics doi:10.1214/19-AOS1234SUPP", "10.1214/19-aos1234supp"),
    ],
)
def test_a_journals_line_that_names_a_review_or_a_supplement_keeps_the_papers_own_doi(head: str, doi: str) -> None:
    """The third review's finding 5: the answered-work rule read "Review of" and "Supplement to" anywhere on a line, and so took the paper's own DOI off a journal's line. It reads only the words that begin a line, and neither of those."""
    assert own_identifiers(f"{head}\nModal logics of finite frames\nAnna Smith\nAbstract. We study.\n")[0] == {doi}


def test_a_survey_listing_identifiers_at_its_foot_states_none_of_them_as_its_own() -> None:

    page = "A survey of quivers\nLena Field\nBody text.\narXiv:2504.01234\narXiv:0805.2065\ndoi:10.4171/x.1\ndoi:10.4171/x.2\n"
    assert own_identifiers(page) == (set(), set(), set())
