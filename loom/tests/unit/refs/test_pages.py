"""What the library reads off a work's PDF: the section map of its page text, the one normalisation a quotation is checked under, where a quotation stands among the word boxes, and the anchor that records a place."""

from __future__ import annotations

from pathlib import Path


def test_a_contents_page_is_skipped_whole(tmp_path: Path) -> None:
    """Manolache's contents page lists every heading, so a line-by-line pass put a fifty-page paper entirely on page 1."""
    from loom.refs.pages import find_sections

    toc = "Contents\n1 Introduction . . . . . . . . . . 2\n2 Preliminaries . . . . . . . . . 4\n3 Results . . . . . . . . . . . . 9\n4 Applications . . . . . . . . . 14\n5 Appendix . . . . . . . . . . . 20\n"
    pages = [toc, "1 Introduction\nWe study widgets.", "", "2 Preliminaries\nLet X be a scheme."]
    secs = find_sections(pages)
    assert [(s.n, s.page) for s in secs] == [("1", 2), ("2", 4)]


def test_a_run_in_heading_is_cut_at_its_first_sentence() -> None:
    """Edidin and Graham set headings run-in, so a title taken whole swallowed the paragraph after it."""
    from loom.refs.pages import find_sections

    pages = [
        "1 Introduction. The purpose of this paper is to prove the localization theorem for equivariant Chow groups."
    ]
    assert [(s.n, s.title) for s in find_sections(pages)] == [("1", "Introduction")]


def test_mathematics_is_not_a_heading() -> None:
    """`C (F ) = Spec Sym(F )` and `E = C x_D X` are lines from this corpus that a bare-capital rule read as appendices."""
    from loom.refs.pages import find_sections

    pages = ["C (F ) = Spec Sym(F )\nE = C ×D,0 X ; then the sequence\n2 the diagram\n3 g is a DM-type morphism;"]
    assert find_sections(pages) == []


def test_section_numbers_do_not_go_backwards() -> None:
    from loom.refs.pages import find_sections

    pages = ["1 Introduction", "2 Setup", "9 Not a section here", "3 Results"]
    assert [s.n for s in find_sections(pages)] == ["1", "2", "3"]


def test_a_numbered_bibliography_is_not_a_section_list() -> None:
    """Behrend and Fantechi's reference list is numbered, and read as sections 8 through 20."""
    from loom.refs.pages import find_sections

    pages = [
        "1 Introduction",
        "2 Cones",
        "3 The intrinsic normal cone",
        "References",
        "8 Harris, J.: Algebraic Geometry\n9 Hartshorne, R.: Residues and Duality",
    ]
    got = [s.n or s.title for s in find_sections(pages)]
    assert got == ["1", "2", "3", "References"]


def test_a_book_length_map_with_almost_no_sections_says_it_is_a_guess() -> None:
    from loom.refs.pages import PageMap, Section

    book = PageMap(sha256="x", pages=679, sections=[Section("1", "See", 3), Section("2", "Grothendieck", 9)])
    paper = PageMap(sha256="x", pages=44, sections=[Section("1", "Introduction", 1)])
    assert book.suspect and not paper.suspect


def test_a_map_whose_titles_read_as_sentences_says_it_is_a_guess() -> None:
    """T4: `search --pages` printed section labels such as "[1 If Y has irreducible components Y1 ,]", and `check` called only one map a guess."""
    from loom.refs.pages import PageMap, Section

    misread = [Section("1", "If Y has irreducible components Y1 ,", 2), Section("2", "Let X be a scheme", 4)]
    titled = [Section("1", "Introduction", 1), Section("2", "Virtual pullbacks", 4), Section("3", "Functoriality", 9)]
    assert PageMap(sha256="x", pages=20, sections=[*misread, Section("3", "Functoriality", 9)]).suspect
    assert not PageMap(sha256="x", pages=20, sections=titled).suspect


def test_normalisation_joins_hyphenation_and_folds_ligatures() -> None:
    """The only sense in which a quotation "appears at" an anchor."""
    from loom.refs.search import find_in_page, normalize

    assert normalize("a perfect ob-\nstruction theory") == "a perfect obstruction theory"
    assert normalize("the ﬁrst ﬂat aﬃne") == "the first flat affine"
    assert normalize("X →  Y\n\n  Z") == "X → Y Z"
    assert normalize("morphism­") == "morphism"
    # case is kept: "let X be Finite" must not pass as the paper's words
    assert normalize("Let X Be") != normalize("let x be")
    assert find_in_page("...a perfect ob-\nstruction theory E...", "a perfect obstruction theory")


def test_locate_reads_bbox_output_that_is_not_valid_xml() -> None:
    """Every page of every paper in this corpus failed to parse: a math glyph lands on U+000F, which no XML parser accepts."""
    from loom.refs.search import locate_span

    page = (
        '<html xmlns="http://www.w3.org/1999/xhtml"><body><page>'
        '<word xMin="10.0" yMin="20.0" xMax="30.0" yMax="28.0">perfect</word>'
        '<word xMin="32.0" yMin="20.0" xMax="60.0" yMax="28.0">obstruction</word>'
        '<word xMin="62.0" yMin="20.0" xMax="80.0" yMax="28.0">theory.</word>'
        '<word xMin="82.0" yMin="20.0" xMax="88.0" yMax="28.0">\x0f</word>'
        "</page></body></html>"
    )
    got = locate_span(page, "perfect obstruction theory", 5)
    assert got is not None
    # the trailing period belongs to the word box, and a word-sequence match failed on exactly that
    assert got.quad == (10.0, 20.0, 80.0, 28.0) and got.words == 3
    assert locate_span(page, "not on this page", 5) is None


def test_locate_matches_across_the_two_extractions_of_one_page() -> None:
    """`pages/NNNN.txt` is plain `pdftotext` and the boxes are `-bbox-layout`: two readings of one page that disagree about spacing around mathematics and about a hyphen a line break left behind. Measured over five documents, matching under `normalize` alone placed 81% of quotations and 47% on a real arXiv paper; dropping spaces and hyphens from both sides placed 100%."""
    from loom.refs.search import locate_span

    page = (
        "<html><body><page>"
        '<word xMin="10.0" yMin="20.0" xMax="30.0" yMax="28.0">polytope</word>'
        '<word xMin="32.0" yMin="20.0" xMax="44.0" yMax="28.0">M (D)</word>'
        '<word xMin="46.0" yMin="20.0" xMax="52.0" yMax="28.0">⊆</word>'
        '<word xMin="54.0" yMin="20.0" xMax="58.0" yMax="28.0">R</word>'
        '<word xMin="58.0" yMin="16.0" xMax="62.0" yMax="22.0">A</word>'
        '<word xMin="64.0" yMin="20.0" xMax="78.0" yMax="28.0">cut</word>'
        '<word xMin="10.0" yMin="40.0" xMax="36.0" yMax="48.0">denom-</word>'
        '<word xMin="38.0" yMin="40.0" xMax="70.0" yMax="48.0">inators</word>'
        "</page></body></html>"
    )
    # the superscript is its own word box, so the page text's `RA` is `R A` here
    assert locate_span(page, "polytope M (D) ⊆ RA cut", 2) is not None
    # and the line break leaves a hyphen the plain extraction has already joined
    assert locate_span(page, "denominators", 2) is not None
    assert locate_span(page, "a phrase this page does not carry", 2) is None


def test_a_quotation_over_two_lines_is_one_rectangle_per_line() -> None:
    """A union box over three lines swallows the column between them, so a highlight is drawn from one rectangle per line; the subscript on the first line stays with it rather than becoming a line of its own."""
    from loom.refs.search import locate_span

    page = (
        "<html><body><page>"
        '<word xMin="10.0" yMin="20.0" xMax="30.0" yMax="28.0">the</word>'
        '<word xMin="32.0" yMin="22.0" xMax="36.0" yMax="26.0">rank</word>'
        '<word xMin="10.0" yMin="40.0" xMax="48.0" yMax="48.0">is</word>'
        '<word xMin="50.0" yMin="40.0" xMax="70.0" yMax="48.0">free</word>'
        "</page></body></html>"
    )
    got = locate_span(page, "the rank is free", 1)
    assert got is not None
    assert got.quad == (10.0, 20.0, 70.0, 48.0)  # the union is still there for a caller that wants one number
    assert got.lines == [(10.0, 20.0, 36.0, 28.0), (10.0, 40.0, 70.0, 48.0)]


def test_the_anchor_check_stays_strict_while_geometry_is_loose() -> None:
    """Looseness is for drawing only: a highlight two lines off is visible, and a transcription wrongly called faithful is not."""
    from loom.refs.search import find_in_page

    assert find_in_page("the rank of the kernel", "rank of the")
    assert not find_in_page("the rank of the kernel", "rankofthe")


def test_offsets_come_from_the_page_text_as_read() -> None:
    """A reader's selection arrives from the viewer's own text layer, a third extraction after the page text and the word boxes, so the offsets are found under the same tolerance the geometry is; and they index the raw page text."""
    from loom.refs.search import locate_offsets

    page = "Let Q be a quiver whose\nunderlying graph has c connected components, and let W(Q)\n"
    got = locate_offsets(page, "underlying graph has c connected components")
    assert got is not None
    assert page[got[0] : got[1]] == "underlying graph has c connected components"
    # spacing around mathematics differs between extractions, and the offsets are still the raw ones
    spaced = locate_offsets(page, "hasc connected")
    assert spaced is not None and page[spaced[0] : spaced[1]] == "has c connected"
    assert locate_offsets(page, "a phrase this page does not carry") is None


def test_an_anchor_round_trips_in_both_bases() -> None:
    """Each kind of anchor carries exactly its own keys, and reads back equal: a LaTeX anchor never claims a `basis`, and a page anchor never carries a byte range."""
    from loom.anchors import Anchor

    cases = [
        (
            Anchor(kind="pdf", sha256="a" * 64, page=3, quads=[[1.0, 2.0, 3.0, 4.0]], basis="text", start=10, end=42),
            {"kind", "sha256", "page", "quads", "basis", "start", "end"},
        ),
        # a box records geometry and no offsets
        (
            Anchor(kind="pdf", sha256="b" * 64, page=7, quads=[[5.0, 6.0, 7.0, 8.0]], basis="box"),
            {"kind", "sha256", "page", "quads", "basis"},
        ),
        # a file anchor has no page, no geometry and no basis
        (
            Anchor(kind="tex", sha256="c" * 64, path="src/main.tex", bytes=[100, 200]),
            {"kind", "sha256", "path", "bytes"},
        ),
        (Anchor(kind="tex", sha256="d" * 64, path="notes/x.tex"), {"kind", "sha256", "path"}),
    ]
    for a, keys in cases:
        out = a.to_dict()
        assert set(out) == keys, (a, sorted(out))
        assert Anchor.from_dict(out) == a


def test_a_hyphenated_line_and_a_ligature_both_place() -> None:
    """The two extractions of a page disagree about hyphens a line break left behind and about ligatures: the word boxes carry `ﬃ` as one glyph where a selection or the page text spells `ffi`."""
    from loom.refs.search import locate_span

    # one word broken across a line, as `-bbox-layout` reports it, and a ligature the two readings spell differently
    words = [
        ("Let", 72.0, 100.0, 90.0, 112.0),
        ("the", 94.0, 100.0, 112.0, 112.0),
        ("denom-", 116.0, 100.0, 160.0, 112.0),
        ("inators", 72.0, 114.0, 110.0, 126.0),
        ("be", 114.0, 114.0, 128.0, 126.0),
        ("a\ufb03ne", 132.0, 114.0, 164.0, 126.0),
    ]
    xml = "".join(f'<word xMin="{a}" yMin="{b}" xMax="{c}" yMax="{d}">{w}</word>' for w, a, b, c, d in words)
    span = locate_span(xml, "Let the denominators be affine", 1)
    assert span is not None, "a word split by a line break and a ligature must still place"
    assert span.words == 6 and len(span.lines) == 2, "one rectangle per line, because the quotation crosses one"
    assert locate_span(xml, "Let the denominators be afine", 1) is None, "the ligature folds to ffi, not to anything"


def test_a_filename_is_author_year_title() -> None:
    from loom.refs.ingest import filename_title

    assert filename_title("Behrend and Fantechi - 1997 - The intrinsic normal cone") == "The intrinsic normal cone"
    assert filename_title("Manolache - 2011 - Virtual pull-backs") == "Virtual pull-backs"
    assert filename_title("Virtual_classes") == "Virtual_classes"


def test_the_library_is_committed_like_anything_else(tmp_path: Path) -> None:
    """The library's nodes and stored documents travel with the quilt, a line of the person's own keeping the PDFs out. `loom init --demo` writes loom's own lines."""
    from loom.gitignore import LOOM_IGNORE
    from loom.paths import LIBRARY

    rules = [ln for ln in LOOM_IGNORE.splitlines() if ln and not ln.startswith("#")]
    inside = LIBRARY.removeprefix(".loom/")
    assert not any(ln.startswith(inside) for ln in rules), "nothing of the library is ignored"
    from tests.unit._quilts import demo

    assert (demo(tmp_path) / ".loom" / ".gitignore").read_text() == LOOM_IGNORE
