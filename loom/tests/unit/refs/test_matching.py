"""Which works a PDF names plainly (`refs.ingest`): by the identifier it states as its own, or by its whole title with the work's first author leading its byline, and never by a title alone. The study's reproductions of the wrong matches (`docs/reports/v0.1-study/raw/library.md`, section 5 and B1, B2) are tests here."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.refs.ingest import identify_document, own_identifiers
from loom.scan.bib import parse_bib
from tests.unit.refs._made_pdfs import fake_pdf

#: Page one of the Cox–Ross–Rubinstein PDF in the quant quilt, as pdftotext read it: the journal's masthead over three lines, then the title.
COX = (
    "Journal\nof Financial\nEconomics\nOPTION PRICING: A SIMPLIFIED APPROACH*\n7 (1979) 229-263.\n"
    "John C. COX\nMassachusetts Institute of Technology, Cambridge, MA 02139, USA\n"
    "Stephen A. ROSS\nYale University, New Haven, CT 06520, USA\nReceived March 1979\n"
)
#: The entry the Glosten–Milgrom PDF, of the same journal, had made of itself: a masthead fragment for a title, and no author.
OF = "@misc{Of, title={of Financial}, loom-added={2026-11-11T21:00:00Z, A Reader}}"
PERELMAN = (
    "@article{perelman_EntropyFormulaRicci2002, author={Perelman, Grisha}, "
    "title={The entropy formula for the Ricci flow and its geometric applications}, year={2002}, eprint={math/0211159}}"
)


def test_the_quant_incident_no_longer_reproduces(tmp_path: Path) -> None:
    """B1: the Cox PDF named `Of`, whose title "of Financial" is a line of its masthead and whose entry names no author. A title alone names nothing now."""
    pdf = fake_pdf(tmp_path / "1-s2.0-0304405X79900151-main.pdf", COX)
    got = identify_document(pdf, parse_bib(OF))
    assert got.strong == [], got.strong


def test_an_entry_naming_no_author_is_matched_by_its_identifier_alone(tmp_path: Path) -> None:
    """Li and Tian's gathered entry has a title and no author: its whole title on page one, or in a reference manager's file name, names it no longer; the identifier it states does."""
    bib = "@article{LiTian98, title={Virtual moduli cycles and Gromov-Witten invariants of algebraic varieties}}"
    page = "VIRTUAL MODULI CYCLES AND GROMOV-WITTEN INVARIANTS OF ALGEBRAIC VARIETIES\nJUN LI AND GANG TIAN\nIntroduction\n"
    pdf = fake_pdf(
        tmp_path / "Li and Tian - 1998 - Virtual moduli cycles and Gromov-Witten invariants of algebraic varieties.pdf",
        page,
    )
    assert identify_document(pdf, parse_bib(bib)).strong == []
    stamped = fake_pdf(tmp_path / "s.pdf", "arXiv:alg-geom/9602007v1 [alg-geom] 12 Feb 1996\n" + page)
    named = identify_document(stamped, parse_bib(bib[:-1] + ", eprint={alg-geom/9602007}}"))
    assert [(m.citekey, m.how) for m in named.strong] == [
        ("LiTian98", "arXiv:alg-geom/9602007 is stamped in its margin")
    ]


def test_an_arxiv_id_a_note_cites_is_not_its_own(tmp_path: Path) -> None:
    """B2: a note whose abstract cites Perelman's arXiv id was announced as Perelman's paper."""
    note = (
        "A remark on monotone quantities\nAda Byron\nAbstract\n"
        "We extend the entropy formula of arXiv:math/0211159 to manifolds with boundary and show that it\n"
        "remains monotone under the flow.\n"
    )
    assert identify_document(fake_pdf(tmp_path / "note.pdf", note), parse_bib(PERELMAN)).strong == []


def test_arxivs_stamp_names_the_preprint(tmp_path: Path) -> None:
    page = (
        "arXiv:math/0211159v1 [math.DG] 11 Nov 2002\n"
        "The entropy formula for the Ricci flow and its geometric applications\nGrisha Perelman\n"
    )
    got = identify_document(fake_pdf(tmp_path / "p.pdf", page), parse_bib(PERELMAN))
    assert [m.how for m in got.strong] == ["arXiv:math/0211159 is stamped in its margin"]


@pytest.mark.parametrize(
    ("page", "named"),
    [
        pytest.param(
            "Median orders on weighted digraphs\nRosalind Bellamy\nAnn. Fict. Math. 19 (2019), 203–241.\ndoi:10.4171/showcase/19-2\nAbstract\n",
            True,
            id="a DOI set apart at the head, under the work's title",
        ),
        pytest.param(
            "A reply to Bellamy\nT. Critic\ndoi:10.4171/showcase/19-2\nAbstract\n",
            False,
            id="the DOI of the paper a reply answers, under another title",
        ),
        pytest.param(
            "Median orders on weighted digraphs\nRosalind Bellamy\nAbstract\n"
            + "".join(f"Line {k} of the abstract, which goes on.\n" for k in range(12))
            + "As shown in doi:10.4171/showcase/19-2 the polytope is integral, which we use below.\n"
            + "".join(f"Line {k} of the introduction, which goes on.\n" for k in range(12)),
            False,
            id="a DOI in the middle of the page",
        ),
        pytest.param(
            "Median orders on weighted digraphs\nRosalind Bellamy\nAbstract\n"
            "We prove the median orders of 10.4171/showcase/19-2 form a polytope whose vertices are integral and whose volume grows.\n",
            False,
            id="a DOI in a sentence at the head",
        ),
    ],
)
def test_a_doi_is_the_documents_own_only_set_apart_at_its_head_or_foot_under_its_title(
    tmp_path: Path, page: str, named: bool
) -> None:
    bib = (
        "@article{Bellamy19, author={Bellamy, Rosalind}, title={Something else entirely}, doi={10.4171/showcase/19-2}}"
    )
    if named:
        bib = bib.replace("Something else entirely", "Median orders on weighted digraphs")
    got = identify_document(fake_pdf(tmp_path / "x.pdf", page), parse_bib(bib))
    assert [m.citekey for m in got.strong if m.strength == 2] == (["Bellamy19"] if named else [])


def test_an_identifier_printed_under_the_byline_is_the_documents_own() -> None:
    """The showcase's Arden PDFs print their arXiv id on a line of its own under the byline, not in arXiv's margin."""
    dois, arxivs, stamped = own_identifiers(
        "Cycle spaces of finite quivers\nElspeth Arden\narXiv:2504.01234v1\nAbstract\n"
    )
    assert (dois, arxivs, stamped) == (set(), {"2504.01234v1"}, set())
