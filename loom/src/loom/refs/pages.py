"""Page text, the section map and word boxes of a work's PDF: derived from a stored PDF by its hash, under `.loom/cache/library/pages/<hex>/`, the first time something reads them (`mapped`).

Deterministic: no model, no judgement, nothing to review. Plain text per page (`pages/NNNN.txt`) is what a quotation is checked against; the word boxes (`boxes/NNNN.xml`, `-bbox-layout`) are read a page at a time, on demand, since they are some thirty times larger.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from loom import own
from loom.paths import LIBRARY_PAGES

# A numbered heading: "3", "3.1", "A.2". A bare single capital is deliberately NOT a number -- "C (F ) = Spec Sym(F )"
# and "E = C x_D X" are lines from a real paper in this corpus, and a lone letter matches far more mathematics than
# it does appendices. An appendix is found by the word, or by a letter that carries a subsection number.
_NUMBERED = re.compile(r"^\s{0,8}(\d{1,2}(?:\.\d{1,2}){0,2}|[A-F]\.\d{1,2}(?:\.\d{1,2})?)\.?\s+([^\s\d].{2,120})\s*$")
_APPENDIX = re.compile(r"^\s{0,8}Appendix\s+([A-F])\b\.?\s*[:.]?\s*(.{0,70})\s*$", re.I)
_UNNUMBERED = re.compile(
    r"^\s{0,8}(Abstract|Introduction|Preliminaries|Notation|Conventions|Acknowledg(?:e)?ments|References|Bibliography)\s*$",
    re.I,
)
# Lines that look like headings but are results, figures or running heads: never a section.
_NOT_A_HEADING = re.compile(
    r"^\s*(theorem|lemma|proposition|corollary|definition|remark|example|proof|figure|table|equation|claim|conjecture|construction|notation|case|step)\b",
    re.I,
)
# A table-of-contents line: dot leaders, or a title that ends in whitespace and a page number. The contents page
# lists every heading in the paper, so a pass that takes it at face value puts the whole document on page 1.
_TOC_LINE = re.compile(r"(\.\s*){4,}|\u2026|\s\.{2,}\s*\d+\s*$|^\s*\S.*\s{3,}\d{1,3}\s*$")
# Mathematics in a line that otherwise parses as a heading.
_MATHY = re.compile(r"[=→←⇒⊗⊕×∈⊆∼≅∗†‡∫∑∏√≤≥≠±∞]|\\[a-zA-Z]+|\^|_\{|\$")


class MapRefused(Exception):
    """There is no PDF, or the toolchain cannot read it."""


#: How a misread line starts or ends: a hypothesis's opening, or a clause cut off by the line.
_SENTENCE = re.compile(r"^(?:if|let|then|we|suppose|assume|since|note that|it follows)\b|[,;]$", re.I)


@dataclass
class Section:
    """One heading found in the page text, and where it starts."""

    n: str
    title: str
    page: int


@dataclass
class PageMap:
    """What a deterministic pass got out of one work's PDF."""

    sha256: str
    pages: int
    sections: list[Section] = field(default_factory=list)
    chars: int = 0

    @property
    def suspect(self) -> bool:
        """A map with far too few sections for its length, which is a guess rather than a map.

        The detector is tuned on papers. Alper's 679-page lecture notes came out as seven "sections", every one a
        footnote or a sentence opening: early junk took the numbers 1 to 3 and the real chapters were then rejected as
        going backwards. A map like that is reported as unreliable rather than shown as the book's structure.
        """
        sparse = self.pages >= 60 and len(self.sections) * 40 < self.pages
        # a "section" that reads as a sentence -- "If Y has irreducible components Y1 ," -- is a line the detector misread
        misread = sum(1 for sec in self.sections if _SENTENCE.search(sec.title.strip()))
        return sparse or (len(self.sections) >= 3 and misread * 3 >= len(self.sections))

    def section_of(self, page: int) -> Section | None:
        """The last section to have started at or before `page`; None when nothing was detected before it."""
        found = None
        for s in self.sections:
            if s.page <= page:
                found = s
            else:
                break
        return found


def pages_home(root: Path, pdf: str) -> Path:
    """Where the stored PDF `pdf` (`sha256:<hex>`, or the hex alone) has its page text, section map and word boxes kept: `.loom/cache/library/pages/<hex>/`, written by `mapped`."""
    return root / LIBRARY_PAGES / pdf.removeprefix("sha256:")


def mapped(root: Path, pdf: str) -> Path | None:
    """The folder of a stored PDF's page text and section map, written the first time it is asked for.

    Parameters
    ----------
    root : Path
        The quilt.
    pdf : str
        The PDF's hash as a reference names it, `sha256:<hex>`.

    Returns
    -------
    Path or None
        `pages_home`; None when the store holds no such PDF or poppler cannot read it.
    """
    from loom.library import documents

    home = pages_home(root, pdf)
    if read_map(home) is not None:
        return home
    stored = documents.path_of(root, pdf, "pdf")
    if not stored.is_file():
        return None
    try:
        write_map(home, stored)
    except (MapRefused, OSError):
        return None
    return home


def sha256_of(path: Path) -> str:
    """The PDF's content hash, which is what an anchor names."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _pdftotext(args: list[str]) -> str:
    try:
        proc = subprocess.run(["pdftotext", *args], capture_output=True, text=True, timeout=300, check=False)
    except FileNotFoundError as exc:
        raise MapRefused("pdftotext is not installed (it ships with poppler; `brew install poppler`)") from exc
    except subprocess.TimeoutExpired as exc:
        raise MapRefused("pdftotext did not finish within five minutes") from exc
    if proc.returncode != 0:
        raise MapRefused(f"pdftotext failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


#: How many pages one `pdftotext` reads at a time when a document is read whole: small enough to tick, large enough that starting it is no cost.
RUN_OF_PAGES = 24


def _split_pages(raw: str) -> list[str]:
    """pdftotext's output as pages: it ends each with a form feed, which leaves an empty final element that is not a page."""
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def page_count(pdf: Path) -> int | None:
    """How many pages `pdf` has, from `pdfinfo`; None when that cannot say."""
    count = pdf_info(pdf).get("pages", "")
    return int(count) if count.isdigit() else None


def first_pages(pdf: Path, n: int = 2) -> list[str]:
    """The text of the first `n` pages, which is all that says what a document is.

    Asked of `pdftotext` alone: a 500-page book can take it twenty seconds whole and a twentieth of a second here.
    """
    return _split_pages(_pdftotext(["-q", "-f", "1", "-l", str(n), str(pdf), "-"]))[:n]


def page_texts(pdf: Path, progress: Callable[[int, int], None] | None = None) -> list[str]:
    """Every page of `pdf` as plain text, in order.

    A long document is read in runs of pages, one `pdftotext` to a processor, so a book takes seconds rather than most of a minute and each run says how far it has got. `progress` is told (pages read, pages) as they come back. Use `first_pages` to learn what a document is.
    """
    total = page_count(pdf) or 0
    if total <= RUN_OF_PAGES:
        pages = _split_pages(_pdftotext(["-q", str(pdf), "-"]))
        if progress is not None:
            progress(len(pages), len(pages))
        return pages
    starts = range(1, total + 1, RUN_OF_PAGES)

    def read(start: int) -> list[str]:
        last = min(start + RUN_OF_PAGES - 1, total)
        return _split_pages(_pdftotext(["-q", "-f", str(start), "-l", str(last), str(pdf), "-"]))

    pages = []
    with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as pool:
        for run in pool.map(read, starts):
            pages += run
            if progress is not None:
                progress(len(pages), total)
    return pages


def pdf_info(pdf: Path) -> dict[str, str]:
    """The document information a PDF carries, as `pdfinfo` prints it, by lowercased name (`title`, `author`); {} when it cannot be read.

    Failing soft, as `pdfinfo` is optional: it is what a scan with no text layer says about itself, and a work is filed without it.
    """
    try:
        proc = subprocess.run(
            ["pdfinfo", "-enc", "UTF-8", str(pdf)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    pairs = (line.partition(":") for line in proc.stdout.splitlines())
    return {name.strip().lower(): value.strip() for name, sep, value in pairs if sep and value.strip()}


_PAGE = re.compile(r'<page\s+width="([\d.]+)"\s+height="([\d.]+)"')


def page_box(bbox_xml: str) -> tuple[float, float] | None:
    """A page's width and height in points, from its `-bbox-layout` output; None when the output names neither.

    Read from the output rather than from the PDF because a scan's pages are not all one size -- Atiyah and Bott's is 533x806 on one page and 535x808 on another -- so a viewer given one page box for the document draws every highlight slightly wrong.
    """
    m = _PAGE.search(bbox_xml)
    return (float(m.group(1)), float(m.group(2))) if m else None


def token_boxes(pdf: Path, page: int, home: Path | None = None) -> str:
    """The `-bbox-layout` XML for one page, written per page on demand and never in bulk (§4.2).

    With `home`, the PDF's `pages_home`, the output is cached there (`store_boxes`).
    """
    if home is None:
        return _pdftotext(["-q", "-bbox-layout", "-f", str(page), "-l", str(page), str(pdf), "-"])
    cache = store_boxes(home) / f"{page:04d}.xml"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    xml = _pdftotext(["-q", "-bbox-layout", "-f", str(page), "-l", str(page), str(pdf), "-"])
    own.mkdir(cache.parent)
    own.write_text(cache, xml, encoding="utf-8")
    return xml


def store_boxes(home: Path) -> Path:
    """Where the word boxes of a mapped PDF are cached, one file per page, inside its `pages_home`: `token_boxes`, `document_boxes` and `page_rotation` all write there."""
    return home / "boxes"


_PAGE_XML = re.compile(r"<page\b.*?</page>", re.S)


def document_boxes(pdf: Path, cache: Path | None = None) -> list[str]:
    """The `-bbox-layout` XML of every page of `pdf`, from one `pdftotext` over the whole file, split per page.

    Parameters
    ----------
    pdf : Path
        The PDF.
    cache : Path, optional
        A directory to keep the pages in, `NNNN.xml` each as `token_boxes` writes them, with `document.json` naming the file's hash; pages kept for another version of the file are read again.

    Returns
    -------
    list of str
        One `<page>` element per page, in order; MapRefused when pdftotext cannot read the file.
    """
    sha = sha256_of(pdf)
    if cache is not None and (cache / "document.json").is_file():
        try:
            known = json.loads((cache / "document.json").read_text(encoding="utf-8"))
            if known.get("sha256") == sha:
                count = int(known["pages"])
                return [(cache / f"{n:04d}.xml").read_text(encoding="utf-8") for n in range(1, count + 1)]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    pages = _PAGE_XML.findall(_pdftotext(["-q", "-bbox-layout", str(pdf), "-"]))
    if cache is not None:
        said = cache / "document.json"
        try:
            own.mkdir(cache)
            for n, xml in enumerate(pages, 1):
                own.write_text(cache / f"{n:04d}.xml", xml, encoding="utf-8")
            own.write_text(said, json.dumps({"sha256": sha, "pages": len(pages)}) + "\n", encoding="utf-8")
        except OSError:
            pass
    return pages


def _clean_title(raw: str) -> str:
    """A heading's own words, with a run-in paragraph and any dot leaders cut off.

    Several papers here set headings run-in: "1 Introduction. The purpose of this paper is to prove..." is one line, so a title taken whole swallows the first sentence. The cut is the first sentence boundary -- a period, then a space, then a capital.
    """
    t = re.split(r"(?:\s*\.\s*){3,}", raw)[0]
    t = re.sub(r"\s{2,}\d{1,3}\s*$", "", t)
    m = re.search(r"\.\s+(?=[A-Z(])", t)
    if m:
        t = t[: m.start()]
    return t.strip().strip(".").strip()


def _plausible(title: str) -> bool:
    """Whether a cleaned title reads as a heading rather than as a line of mathematics."""
    if not (2 <= len(title) <= 70) or not title[0].isupper():
        return False
    if _MATHY.search(title) or _NOT_A_HEADING.match(title):
        return False
    return sum(c.isdigit() for c in title) <= 3


def _monotonic(found: list[Section]) -> list[Section]:
    """Keep only headings whose top-level number does not go backwards.

    A paper's sections count up. A "3.2" appearing before any "3", or a "0" two thirds of the way through, is a cross-reference, a running head or a fragment of a formula -- and this is the one filter that needs no guess about what a heading looks like.
    """
    out: list[Section] = []
    top = 0
    for s in found:
        if not s.n or not s.n[0].isdigit():
            out.append(s)
            continue
        head = int(s.n.split(".")[0])
        if head < top or head > top + 1:
            continue
        top = max(top, head)
        out.append(s)
    return out


def _candidates(text: str, page: int) -> list[Section]:
    """Every heading-shaped line on one page, before any cross-page filtering."""
    out: list[Section] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if not line.strip() or _NOT_A_HEADING.match(line) or _TOC_LINE.search(line):
            continue
        m = _NUMBERED.match(line)
        if m:
            n, title = m.group(1), _clean_title(m.group(2))
            if n not in seen and _plausible(title):
                seen.add(n)
                out.append(Section(n=n, title=title, page=page))
            continue
        a = _APPENDIX.match(line)
        if a:
            key = f"App{a.group(1).upper()}"
            if key not in seen:
                seen.add(key)
                out.append(Section(n=a.group(1).upper(), title=_clean_title(a.group(2)) or "Appendix", page=page))
            continue
        u = _UNNUMBERED.match(line)
        if u and u.group(1).title() not in seen:
            seen.add(u.group(1).title())
            out.append(Section(n="", title=u.group(1).title(), page=page))
    return out


# A page carrying this many heading-shaped lines is the table of contents, which lists the whole paper. Believing
# it puts every section of a fifty-page paper on page 1 -- which is what the first version of this pass did.
CONTENTS_PAGE = 5


def _after_the_references(found: list[Section], pages: int) -> list[Section]:
    """Drop numbered headings that follow the reference list; a numbered bibliography reads exactly like a section list."""
    cut = 0
    for s in found:
        if not s.n and s.title in ("References", "Bibliography") and s.page > pages * 0.5:
            cut = s.page
    return [s for s in found if not (cut and s.n and s.page >= cut)]


def find_sections(pages: list[str]) -> list[Section]:
    """Headings across the whole document, in order, each with the page it starts on.

    Numbering and shape only, no font sizes: plain text carries no font information, and the numbering is what a section map is for -- turning "pages 210-240" into "chapter 4".

    Four things this corpus forced, each from a paper that broke the version before it: a contents page is skipped whole rather than line by line, a run-in heading is cut at its first sentence, a numbered bibliography entry after the reference list is not a section, and a heading whose top-level number goes backwards is dropped.
    """
    found: list[Section] = []
    seen: set[str] = set()
    for i, text in enumerate(pages, start=1):
        page_found = _candidates(text, i)
        if len(page_found) >= CONTENTS_PAGE:
            continue  # the contents page: it names every heading, and none of them start here
        for s in page_found:
            key = s.n or s.title
            if key in seen:
                continue
            seen.add(key)
            found.append(s)
    return _after_the_references(_monotonic(found), len(pages))


def write_map(home: Path, pdf: Path, progress: Callable[[int, int], None] | None = None) -> PageMap:
    """Write `pages/NNNN.txt` and `sections.json` under `home`; returns what was found.

    Parameters
    ----------
    home : Path
        The PDF's `pages_home`.
    pdf : Path
        The artifact to read.
    progress : callable, optional
        Told (pages read, pages) as the text comes back.

    Returns
    -------
    PageMap
        The artifact's hash, its page count and every heading found.

    See Also
    --------
    read_map : the same record, read back without the PDF.
    """
    pages = page_texts(pdf, progress)
    out = home / "pages"
    own.mkdir(out)
    for old in out.glob("*.txt"):
        own.unlink(old)
    chars = 0
    for i, text in enumerate(pages, start=1):
        body = text.strip("\n")
        own.write_text(out / f"{i:04d}.txt", body + "\n", encoding="utf-8")
        chars += len(body)
    m = PageMap(sha256=sha256_of(pdf), pages=len(pages), sections=find_sections(pages), chars=chars)
    own.write_text(
        home / "sections.json",
        json.dumps(
            {"sha256": m.sha256, "pages": m.pages, "chars": m.chars, "sections": [asdict(s) for s in m.sections]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return m


def read_map(home: Path) -> PageMap | None:
    """The recorded map, or None when this work has never been mapped; never touches the PDF."""
    path = home / "sections.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PageMap(
            sha256=str(data.get("sha256", "")),
            pages=int(data.get("pages", 0)),
            chars=int(data.get("chars", 0)),
            sections=[
                Section(n=str(s.get("n", "")), title=str(s.get("title", "")), page=int(s["page"]))
                for s in data.get("sections", [])
            ],
        )
    except (OSError, ValueError, TypeError, KeyError):
        return None


def read_page(home: Path, page: int) -> str | None:
    """One page's recorded text, or None when it was never written; this is what an anchor is checked against."""
    path = home / "pages" / f"{page:04d}.txt"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
