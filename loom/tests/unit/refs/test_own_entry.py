"""The entry a PDF makes of itself (`refs.add.own_entry`): never a masthead for a title, the largest type on page one where a line stands out, no program or link for an author, and a lookup only of the identifier it states as its own. A textbook has no DOI and may be a scan with no text, and still makes an entry."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.refs.add import identify, own_entry
from loom.scan.bib import parse_bib
from tests.unit.refs._made_pdfs import fake_pdf, real_pdf

#: Page one of the Glosten–Milgrom PDF in the quant quilt, as pdftotext read it, whose entry was titled "of Financial".
GLOSTEN = (
    "Journal\nof Financial\nEconomics\nBID, ASK AND TRANSACTION PRICES IN A SPECIALIST MARKET\n"
    "14 (1985) 71-100. North-Holland\nLawrence R. GLOSTEN\nNorthwestern University, Evanston, IL 60201, USA\n"
)


def test_a_masthead_is_never_a_title(tmp_path: Path) -> None:
    """The quant incident's first half: the entry made of the Glosten–Milgrom PDF took "of Financial" for its title."""
    fields = own_entry(fake_pdf(tmp_path / "1-s2.0-0304405X85900443-main.pdf", GLOSTEN))
    assert fields["title"] == "BID, ASK AND TRANSACTION PRICES IN A SPECIALIST MARKET"


@pytest.mark.poppler
def test_the_largest_type_on_page_one_is_the_title_over_the_lines_it_takes(tmp_path: Path) -> None:
    pdf = real_pdf(
        tmp_path / "preprint.pdf",
        [
            [
                ("Preprint, under review at a journal of record", 9),
                ("Cycle spaces", 17),
                ("of finite quivers", 17),
                ("Elspeth Arden", 12),
                ("Abstract. We collect the standard facts about the cycle space of a quiver.", 10),
                ("The treatment is elementary and self-contained, and may be cited.", 10),
            ]
        ],
    )
    assert own_entry(pdf)["title"] == "Cycle spaces of finite quivers"


@pytest.mark.poppler
def test_a_masthead_set_larger_than_the_title_is_passed_over(tmp_path: Path) -> None:
    pdf = real_pdf(
        tmp_path / "jfe.pdf",
        [
            [
                ("Journal of Financial Economics", 20),
                ("Volume 7 (1979) 229-263. North-Holland", 9),
                ("OPTION PRICING: A SIMPLIFIED APPROACH*", 15),
                ("John C. COX", 11),
                ("Massachusetts Institute of Technology", 9),
                ("Received March 1979, final version received July 1979", 9),
                ("This paper presents a simple discrete-time model for valuing options.", 10),
                ("The fundamental economic principles of option pricing are made clear.", 10),
            ]
        ],
    )
    assert own_entry(pdf)["title"] == "OPTION PRICING: A SIMPLIFIED APPROACH"


@pytest.mark.poppler
def test_a_scan_names_no_program_or_link_for_its_author(tmp_path: Path) -> None:
    """B5: a scan ImageMagick made gave "https://imagemagick.org" as its author, and its key was `Htt`."""
    pdf = real_pdf(tmp_path / "scanned-surgery.pdf", [[], []], info={"Author": "https://imagemagick.org"})
    fields = own_entry(pdf)
    assert fields == {"title": "scanned-surgery"}


@pytest.mark.poppler
def test_a_scanned_textbook_with_no_doi_makes_its_entry_from_its_document_information(tmp_path: Path) -> None:
    pdf = real_pdf(
        tmp_path / "casella.pdf",
        [[], [], []],
        info={
            "Title": "Statistical Inference",
            "Author": "George Casella, Roger L. Berger",
            "Producer": "Adobe Acrobat",
        },
    )
    assert own_entry(pdf) == {"title": "Statistical Inference", "author": "George Casella and Roger L. Berger"}


def test_a_stamped_preprint_gives_its_id_and_its_year(tmp_path: Path) -> None:
    page = "arXiv:math/0211159v1 [math.DG] 11 Nov 2002\nThe entropy formula for the Ricci flow and its geometric applications\nGrisha Perelman\n"
    fields = own_entry(fake_pdf(tmp_path / "p.pdf", page))
    assert (fields["eprint"], fields["archiveprefix"], fields["year"]) == ("math/0211159v1", "arXiv", "2002")


def test_only_the_identifier_a_pdf_states_as_its_own_is_looked_up(tmp_path: Path) -> None:
    """A note citing a DOI in its abstract asks nothing of doi.org: the record would be the cited paper's."""
    asked: list[str] = []

    def http(url: str, headers: dict[str, str]) -> bytes:
        asked.append(url)
        return b'{"title": "Median orders on weighted digraphs", "DOI": "10.4171/showcase/19-2"}'

    note = (
        "A remark on median orders\nT. Critic\nAbstract\n"
        "We revisit the polytope of 10.4171/showcase/19-2 and show that its vertices need not be integral in general.\n"
    )
    seen = identify(tmp_path, parse_bib(""), fake_pdf(tmp_path / "note.pdf", note), online=True, http=http)
    assert asked == [] and seen.offer == {"title": "A remark on median orders"}
    own = fake_pdf(
        tmp_path / "own.pdf", "Median orders on weighted digraphs\nRosalind Bellamy\ndoi:10.4171/showcase/19-2\n"
    )
    seen = identify(tmp_path, parse_bib(""), own, online=True, http=http)
    assert len(asked) == 1 and seen.offer["doi"] == "10.4171/showcase/19-2"
