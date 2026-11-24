"""What a document states of itself: the identifier it prints as its own on its first page, and the title a reference manager's file name gives it.

An identifier is a document's own only when it is set apart where a document prints its own, or is arXiv's stamp; one anywhere else may be one it cites. The intake asks whether a document is a work the library has only by such an identifier, never by its title or byline.
"""

from __future__ import annotations

import re

_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
_ARXIV = re.compile(r"arXiv[:\s]\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", re.I)
#: arXiv's stamp in a preprint's margin, as the text layer prints it: the id, its category in brackets, the date.
_ARXIV_STAMP = re.compile(
    r"^arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)\s+\[[A-Za-z.-]+\]\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}$"
)
#: The words that label an identifier set on a line of its own: `doi:`, a doi.org link, `arXiv:`.
_ID_LABEL = re.compile(r"https?://(?:dx\.)?doi\.org/|\bdoi\b\s*:?|\barxiv\b\s*:?", re.I)
#: How many lines at the head and at the foot of page one a document prints its own identifier among.
EDGE_LINES = 10
#: The most words a line at the head or foot may hold beside an identifier for it to be the document's own: a journal's reference fits, a sentence of an abstract citing another paper does not.
EDGE_WORDS = 10
#: A word of prose beside an identifier, which no journal's reference holds: lower case and longer than a short connective ("of", "the", "and"): "a question raised in arXiv:…".
_PROSE = re.compile(r"^[a-z][a-z'’-]{3,}[.,;:]?$")
#: A line that begins by naming the work a document answers: an identifier after "Erratum to", "Comment on", "Reply to" and the like is that work's, which the document cites. Only at the line's start, and never "Review of" or "Supplement to", which begin journals' names ("Review of Economic Studies", "Supplement to the Annals of Statistics") and a journal's line carries the paper's own DOI.
_ANSWERS = re.compile(
    r"^\W*(?:errat(?:um|a)|corrigend(?:um|a)|addend(?:um|a)|comments?|commentary|repl(?:y|ies)|response|rejoinder"
    r"|retraction|correction|discussion)\s+(?:to|on|of|for)\b",
    re.I,
)


def filename_title(stem: str) -> str:
    """The title part of a filename like `Author and Author - 2019 - The Real Title`.

    Zotero and most reference managers write that shape, and comparing the whole stem to a title scores the authors and the year against nothing -- which is why two papers that *are* in the bibliography matched none of it.
    """
    m = re.match(r"^.{0,80}?\s-\s(?:\d{4}\s-\s)?(.+)$", stem)
    return (m.group(1) if m else stem).strip()


def identifiers_in(text: str) -> tuple[set[str], set[str]]:
    """(DOIs, arXiv ids) appearing in some text, lowercased for comparison."""
    dois = {m.group(0).rstrip(".,;)").lower() for m in _DOI.finditer(text)}
    arxivs = {m.group(1).lower() for m in _ARXIV.finditer(text)}
    return dois, arxivs


def own_identifiers(first_page: str) -> tuple[set[str], set[str], set[str]]:
    """(DOIs, arXiv ids, arXiv ids stamped in the margin) a document states as its own, lowercased.

    Own means arXiv's stamp anywhere on page one, or an identifier set apart at its head or foot: on one of its first or last `EDGE_LINES` lines, beside at most `EDGE_WORDS` other words and no word of prose, and the one identifier of its kind there. An identifier anywhere else may be one the document cites, or the original an erratum or a reply answers: a note citing Perelman's arXiv id was once announced as Perelman's paper, and one whose abstract opened on "a question raised in arXiv:…" took that paper's identity. A survey listing several at its foot states none of them as its own, and a line naming what the document answers (`_ANSWERS`: "Erratum to doi:…") states the answered work's.
    """
    lines = [" ".join(x.split()) for x in first_page.splitlines() if x.strip()]
    stamped = {m.group(1).lower() for x in lines if (m := _ARXIV_STAMP.match(x))}
    dois: set[str] = set()
    arxivs: set[str] = set()
    for x in [*lines[:EDGE_LINES], *lines[EDGE_LINES:][-EDGE_LINES:]]:
        if _ARXIV_STAMP.match(x) or _ANSWERS.search(x):
            continue
        found = identifiers_in(x)
        rest = _ID_LABEL.sub(" ", _ARXIV.sub(" ", _DOI.sub(" ", x))).split()
        if (found[0] or found[1]) and len(rest) <= EDGE_WORDS and not any(_PROSE.match(w) for w in rest):
            dois |= found[0]
            arxivs |= found[1]
    return (
        (dois if len(dois) == 1 else set()),
        (arxivs if len({re.sub(r"v\d+$", "", a) for a in arxivs}) == 1 else set()),
        stamped,
    )
