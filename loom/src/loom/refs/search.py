"""Finding text in a work's pages, and the one normalisation a quotation is checked under (plan 0.12 §5).

Everything that compares a quotation to a page goes through `normalize` here: anchoring an annotation on a page (`refs.anchoring`), and placing a quotation's words in the word boxes (`locate_span`). Two implementations of "near enough" would mean a quotation that is found but will not anchor, which is the worst failure this layer could have. Page search finds under `fold`, which is `normalize` without case, and ranks what it finds by how often its terms occur.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# What a PDF text layer does to a document, undone. Ligatures are the common case; the rest turn up in older
# scans and in anything typeset before Unicode was settled.
_FOLD = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st",
    "‘": "'", "’": "'", "“": '"', "”": '"', "′": "'", "´": "'", "`": "'",
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "­": "",
}  # fmt: skip
_FOLD_RE = re.compile("|".join(map(re.escape, _FOLD)))
# One `<word>` of pdftotext's `-bbox-layout` output. Scanned rather than parsed as XML on purpose: the content of a
# word is whatever byte the font mapped, and a mathematics paper is full of glyphs that land on control codepoints
# (U+000F among them), which no XML parser will accept. Every page of every paper in this corpus failed to parse.
_WORD = re.compile(
    r'<word\s+xMin="([\d.eE+-]+)"\s+yMin="([\d.eE+-]+)"\s+xMax="([\d.eE+-]+)"\s+yMax="([\d.eE+-]+)"\s*>(.*?)</word>',
    re.S,
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_ENTITY = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}

# A word broken across a line: "morph-\nism" is one word on the page and two in the text layer.
_HYPHEN_BREAK = re.compile(r"-\s*\n\s*")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """The form two pieces of text are compared in: ligatures folded, hyphenation across lines joined, whitespace flattened.

    Parameters
    ----------
    text : str
        Page text or a quotation, either way as it was written.

    Returns
    -------
    str
        The comparison form. Case is **kept**: a statement's capitals are part of it, and folding them would let "let X be Finite" pass as the paper's words.

    See Also
    --------
    find_in_page : the search this normalisation exists for.
    """
    t = unicodedata.normalize("NFKC", text)
    t = _HYPHEN_BREAK.sub("", t)
    t = _FOLD_RE.sub(lambda m: _FOLD[m.group()], t)
    return _SPACE.sub(" ", t).strip()


def find_in_page(page: str, needle: str) -> bool:
    """Whether `needle` appears on `page`, both normalised."""
    n = normalize(needle)
    return bool(n) and n in normalize(page)


@dataclass
class Hit:
    """One page a search matched, with enough context to decide whether to read it."""

    ref: str
    page: int
    section: str
    context: str
    #: How often the search's terms occur on the page, which a page search ranks by.
    score: int = 0


def _context(page: str, needle: str, width: int = 70) -> str:
    """The matched text with a little either side, on one line; '' when the page does not contain it."""
    flat = normalize(page)
    i = flat.find(normalize(needle))
    if i < 0:
        return ""
    lo, hi = max(0, i - width // 2), min(len(flat), i + len(normalize(needle)) + width // 2)
    return ("…" if lo else "") + flat[lo:hi] + ("…" if hi < len(flat) else "")


def grep_work(home: Path, ref: str, needle: str) -> list[Hit]:
    """Every page of one mapped PDF (`pages.mapped`) whose text contains `needle`, for the reference `ref`; reads the page text, never the PDF."""
    from loom.refs.pages import read_map

    out: list[Hit] = []
    m = read_map(home)
    pages = sorted((home / "pages").glob("*.txt"))
    for path in pages:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not find_in_page(text, needle):
            continue
        n = int(path.stem)
        sec = m.section_of(n) if m and not m.suspect else None
        label = f"{sec.n} {sec.title}".strip() if sec else ""
        out.append(Hit(ref=ref, page=n, section=label, context=_context(text, needle)))
    return out


def fold(text: str) -> str:
    """`normalize`, then case-folded and with a hyphen inside a word dropped: the form a page search matches its terms in, so `pullback` finds `pull-back`.

    For finding only. An anchor is still checked under `normalize`, whose case and hyphens a statement keeps.
    """
    return _unhyphen(normalize(text).casefold())


def _unhyphen(text: str) -> str:
    return re.sub(r"(?<=\w)-(?=\w)", "", text)


def terms_of(text: str) -> list[str]:
    """The words of a search, folded, each once and in the order given."""
    out: list[str] = []
    for t in fold(text).split():
        if t not in out:
            out.append(t)
    return out


def snippet(text: str, terms: list[str], width: int = 60) -> str:
    """The text around the first of `terms` it contains, on one line; its opening when it contains none."""
    flat = _unhyphen(normalize(text))
    folded = flat.casefold()
    if len(folded) != len(flat):
        flat = folded  # a fold that changed a length (ß to ss) would misplace every offset after it
    at = min((i for i in (folded.find(t) for t in terms) if i >= 0), default=0)
    lo = max(0, at - width // 3)
    hi = min(len(flat), lo + width)
    return ("…" if lo else "") + flat[lo:hi].strip() + ("…" if hi < len(flat) else "")


def search_pages(home: Path, ref: str, terms: list[str]) -> list[Hit]:
    """Every page of one mapped PDF (`pages.mapped`) holding all of `terms`, folded, for the reference `ref`, each scored by how often they occur on it."""
    from loom.refs.pages import read_map

    out: list[Hit] = []
    if not terms:
        return out
    m = read_map(home)
    for path in sorted((home / "pages").glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        folded = fold(text)
        if not all(t in folded for t in terms):
            continue
        n = int(path.stem)
        # a map that is a guess names no section, rather than a misread line as one
        sec = m.section_of(n) if m and not m.suspect else None
        label = f"{sec.n} {sec.title}".strip() if sec else ""
        hit = Hit(ref=ref, page=n, section=label, context=snippet(text, terms, 70))
        hit.score = sum(folded.count(t) for t in terms)
        out.append(hit)
    return out


@dataclass
class Span:
    """Where a quotation sits on a page, in points with the origin at the TOP LEFT.

    That is the space `pdftotext -bbox-layout` emits, not PDF user space, whose origin is the bottom left. The two differ by a vertical flip, so a renderer handed these as user-space coordinates draws every highlight mirrored.
    """

    page: int
    quad: tuple[float, float, float, float]
    words: int
    #: One rectangle per line the quotation covers, in the same space. A single union box over three lines swallows the column between them, so this is what a highlight is drawn from; `quad` remains the union, for a caller that wants one number.
    lines: list[tuple[float, float, float, float]] = field(default_factory=list)


def _words(bbox: str) -> list[tuple[float, float, float, float, str]]:
    """Every word box in one page of `-bbox-layout` output, as (xMin, yMin, xMax, yMax, text)."""
    out: list[tuple[float, float, float, float, str]] = []
    for m in _WORD.finditer(bbox):
        raw = m.group(5)
        for ent, ch in _ENTITY.items():
            raw = raw.replace(ent, ch)
        out.append((float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)), _CONTROL.sub("", raw)))
    return out


def locate_span(bbox_xml: str, needle: str, page: int) -> Span | None:
    """The bounding box of `needle` on a page, from pdftotext's `-bbox-layout` output.

    Parameters
    ----------
    bbox_xml : str
        One page of `pdftotext -bbox-layout` output.
    needle : str
        The quotation to find, compared under `normalize`.
    page : int
        The page number, carried into the result.

    Returns
    -------
    Span or None
        The union of the matched words' boxes, one rectangle per line in `lines`, or None when the words are not on the page.

    See Also
    --------
    loom.refs.pages.token_boxes : produces the output, one page at a time and on demand.
    loom.refs.search.find_in_page : the strict comparison, which is what a claim is checked against.
    """
    words = _words(bbox_xml)
    if not words:
        return None
    text, owner = _flat(words)
    want = _loose(needle)
    if not want:
        return None
    at = text.find(want)
    if at < 0:
        return None
    hit = sorted(set(owner[at : at + len(want)]))
    if not hit:
        return None
    boxes = [words[i] for i in hit]
    return Span(
        page=page,
        quad=(min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)),
        words=len(boxes),
        lines=_by_line(boxes),
    )


#: Dropped from both sides when looking for a quotation's geometry: spaces, and the hyphens a line break leaves behind.
_LOOSE = {" ", "-", "‐", "‑"}


def _loose(s: str) -> str:
    """A quotation reduced to what two extractions of one page agree on.

    `pages/NNNN.txt` comes from plain `pdftotext` and the word boxes from `-bbox-layout`: two readings of the same page that disagree about spacing around mathematics (`hσ2 i` against `hσ2i`) and about hyphens a line break left behind (`denom-` `inators` against `denominators`). Measured over five documents, matching under `normalize` alone placed 81% of quotations and as little as 47% on a real arXiv paper; dropping spaces and hyphens from both sides placed 100%, with the matched span covering the right number of words in every case.

    This looseness is for **drawing only**. `find_in_page` stays strict, because a highlight two lines off is visible and a transcription wrongly called faithful is not.
    """
    return "".join(c for c in normalize(s) if c not in _LOOSE)


def _flat(words: list[tuple[float, float, float, float, str]]) -> tuple[str, list[int]]:
    """The page as one loose string, with the word each character came from.

    A character-offset map rather than a word-sequence match: a word box carries whatever punctuation touches it, so matching "perfect obstruction theory" against the tokens `perfect`, `obstruction`, `theory.` fails on the trailing period -- which is what a real page does to a real quotation.
    """
    flat: list[str] = []
    owner: list[int] = []
    for i, w in enumerate(words):
        piece = _loose(w[4])
        if not piece:
            continue
        flat.append(piece)
        owner.extend([i] * len(piece))
    return "".join(flat), owner


def _by_line(boxes: list[tuple[float, float, float, float, str]]) -> list[tuple[float, float, float, float]]:
    """One rectangle per line of a matched quotation, from word boxes that overlap vertically.

    The word regex ignores the `<line>` elements on purpose (`_words`), so lines are recovered from the geometry: two words are on one line when their vertical extents overlap by more than half of the shorter one, which holds for subscripts and superscripts and separates a line from the next.
    """
    out: list[tuple[float, float, float, float]] = []
    for b in sorted(boxes, key=lambda w: (w[1], w[0])):
        if out:
            x0, y0, x1, y1 = out[-1]
            overlap = min(y1, b[3]) - max(y0, b[1])
            if overlap > 0.5 * min(y1 - y0, b[3] - b[1]):
                out[-1] = (min(x0, b[0]), min(y0, b[1]), max(x1, b[2]), max(y1, b[3]))
                continue
        out.append((b[0], b[1], b[2], b[3]))
    return out


def locate_offsets(page_text: str, needle: str) -> tuple[int, int] | None:
    """Where `needle` sits in a page's text, as offsets into that text; None when it is not there.

    The counterpart of `locate_span`, and deliberately the same tolerance: the reader's selection came from a third extraction again -- the viewer's own text layer -- so spacing around mathematics and a hyphen left by a line break must not decide whether an anchor can be recorded. Offsets index the raw page text, not a normalised copy of it, so an anchor's offsets name the words a reader sees.
    """
    keep: list[int] = []
    flat: list[str] = []
    for i, ch in enumerate(page_text):
        piece = _loose(ch)
        if piece:
            flat.append(piece)
            keep.extend([i] * len(piece))
    text = "".join(flat)
    want = _loose(needle)
    if not want:
        return None
    at = text.find(want)
    if at < 0:
        return None
    return keep[at], keep[at + len(want) - 1] + 1
