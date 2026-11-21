"""A reference's BibTeX entry read for what the views and the intake need: its identifiers, and its words decoded (`library-views.md` §2, "Names").

The entry stays as its source wrote it (`docs/specs/nodes.md` §7); nothing here rewrites one but `expand_strings`, which gathering uses where an entry leans on a `@string` its file defines. Words are decoded as a reader sees them: braces dropped, TeX's accents made characters (`Kova{\\v{c}}` is "Kovač"), dashes made dashes, and mathematics kept between `$` for the viewer to draw.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field

from loom.library.body import entry_of
from loom.scan.bib import parse_bib

#: TeX's accent commands, each with the combining character it puts on its letter.
ACCENTS = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304", ".": "\u0307",
    "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "d": "\u0323", "b": "\u0331", "k": "\u0328", "r": "\u030a",
}  # fmt: skip
#: Letters TeX names by a command.
LETTERS = {
    "ss": "ß", "o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å", "l": "ł", "L": "Ł",
    "i": "ı", "j": "ȷ", "&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}",
}  # fmt: skip
_ACCENT = re.compile(r"\\([`'^\"~=.]|[uvHcdbkr](?![A-Za-z]))\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[A-Za-z]))")
_LETTER = re.compile(r"\\(ss|ae|AE|oe|OE|aa|AA|[oOlLij])(?![A-Za-z])\s*|\\([&%$#_{}])")
_COMMAND = re.compile(r"\\[A-Za-z]+\*?\s*")
_MATH = re.compile(r"(?<!\\)\$[^$]*(?<!\\)\$")
#: The schemes an entry states an identifier in, in the order they are trusted.
SCHEMES = ("doi", "arxiv", "mr", "zbl")
_ARXIV_DOI = re.compile(r"10\.48550/arxiv\.(.+)", re.I)
_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?(?:[?#]|$)", re.I)
_DOI_URL = re.compile(r"doi\.org/(10\.[^\s?#]+)", re.I)
_VERSION = re.compile(r"v\d+$")


@dataclass(frozen=True)
class Entry:
    """A reference's entry: its type and key, its fields as the BibTeX reader gives them, and its text exactly."""

    type: str
    key: str
    fields: Mapping[str, str] = field(default_factory=dict)
    text: str = ""


def read_entry(text: str) -> Entry | None:
    """The one entry `text` holds, or None when it holds none with a key.

    Parameters
    ----------
    text : str
        A reference's body, or one entry pasted or gathered.

    Returns
    -------
    Entry or None
        Its type in lower case, key, fields and text.
    """
    found = entry_of(text)
    if found is None or not found.key:
        return None
    parsed = parse_bib(text.strip())
    fields = parsed[found.key].fields if found.key in parsed else {}
    return Entry(found.type, found.key, dict(fields), text)


def identifiers(fields: Mapping[str, str]) -> list[str]:
    """Every identifier an entry states, as `scheme:value`, the most trusted first: a DOI (an arXiv DOI read as the arXiv number it names), an arXiv number from `eprint`, a MathSciNet and a zbMATH number, and failing all of these one read from `url`.

    Parameters
    ----------
    fields : mapping
        The entry's fields.

    Returns
    -------
    list of str
        Such as `doi:10.1000/xyz`, `arxiv:2401.01234v2`; empty when it states none.
    """
    out: list[str] = []
    doi = fields.get("doi", "").strip()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)
    if doi.startswith("10."):
        m = _ARXIV_DOI.match(doi)
        out.append(f"arxiv:{m.group(1)}" if m else f"doi:{doi}")
    eprint = fields.get("eprint", "").strip()
    archive = (fields.get("eprinttype") or fields.get("archiveprefix") or "arxiv").strip().lower()
    if eprint and archive == "arxiv" and not any(x.startswith("arxiv:") for x in out):
        value = re.sub(r"^arxiv:", "", eprint, flags=re.I)
        version = fields.get("version", "").strip()
        if version.isdigit() and not re.search(r"v\d+$", value):
            value = f"{value}v{version}"
        out.append(f"arxiv:{value}")
    for name, scheme in (("mrnumber", "mr"), ("zbl", "zbl"), ("zblnumber", "zbl")):
        value = fields.get(name, "").strip()
        if value and not any(x.startswith(f"{scheme}:") for x in out):
            out.append(f"{scheme}:{value}")
    if not out:
        url = fields.get("url", "")
        if m := _ARXIV_URL.search(url):
            out.append(f"arxiv:{m.group(1)}")
        elif m := _DOI_URL.search(url):
            out.append(f"doi:{m.group(1)}")
    return out


def matchable(identifier: str) -> str:
    """An identifier as two are compared: a DOI in lower case, an arXiv number without its version (`arxiv:2401.01234`), the rest as written."""
    scheme, _, value = identifier.partition(":")
    if scheme == "doi":
        return f"doi:{value.lower()}"
    if scheme == "arxiv":
        return "arxiv:" + _VERSION.sub("", value)
    return identifier


def decode(text: str) -> str:
    """`text` as a reader sees it: braces dropped, accents made characters, `--` and `---` made dashes, `~` a space, other commands dropped and their arguments kept, mathematics between `$` left as it is.

    Parameters
    ----------
    text : str
        A field's value as BibTeX holds it.

    Returns
    -------
    str
        The words, whitespace made single spaces, in Unicode's composed form.
    """
    pieces: list[str] = []
    last = 0
    for m in _MATH.finditer(text):
        pieces.append(_words(text[last : m.start()]))
        pieces.append(m.group(0))
        last = m.end()
    pieces.append(_words(text[last:]))
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def _words(text: str) -> str:
    def accent(m: re.Match[str]) -> str:
        letter = m.group(2) or m.group(3) or ""
        letter = LETTERS.get(letter[1:], letter[1:]) if letter.startswith("\\") else letter
        return unicodedata.normalize("NFC", letter + ACCENTS[m.group(1)])

    text = _ACCENT.sub(accent, text)
    text = _LETTER.sub(lambda m: LETTERS[m.group(1) or m.group(2)], text)
    text = _COMMAND.sub("", text)
    text = text.replace("---", "\u2014").replace("--", "\u2013").replace("~", " ")
    return text.replace("{", "").replace("}", "")


def surnames(fields: Mapping[str, str]) -> list[str]:
    """The authors' surnames in order, decoded; the editors' where the entry names no author, and `others` left out."""
    names = fields.get("author") or fields.get("editor") or ""
    out: list[str] = []
    for part in re.split(r"\s+and\s+", names):
        part = part.strip()
        if not part or part.lower() == "others":
            continue
        surname = part.split(",")[0] if "," in part else _last_word(part)
        if surname := decode(surname):
            out.append(surname)
    return out


def _last_word(name: str) -> str:
    """A `First Last` name's surname: its last word, or the last braced group, kept whole (`{van der Berg}`)."""
    if name.endswith("}") and "{" in name:
        depth = 0
        for i in range(len(name) - 1, -1, -1):
            depth += {"}": 1, "{": -1}.get(name[i], 0)
            if depth == 0:
                return name[i:]
    return name.split()[-1]


def year(fields: Mapping[str, str]) -> str:
    """The entry's year, from `year` or a biblatex `date`; '' when it states none."""
    for value in (fields.get("year", ""), fields.get("date", "")):
        if m := re.search(r"\b(1[5-9]|20)\d\d\b", value):
            return m.group(0)
    return ""


def title(fields: Mapping[str, str]) -> str:
    """The entry's title, decoded; '' when it has none."""
    return decode(fields.get("title", ""))


def short(fields: Mapping[str, str], fallback: str = "") -> str:
    """How a work is named in a row: `Smith 2024`, `Halberd and Ravel 2021`, `Vance et al. 2023`; the title for an entry naming nobody, and `fallback` for one with neither.

    Parameters
    ----------
    fields : mapping
        The entry's fields.
    fallback : str, default ''
        What to say when the entry names neither author nor title, such as the name a file was dropped under.

    Returns
    -------
    str
        The work's short name.
    """
    names = surnames(fields)
    when = year(fields)
    if not names:
        return title(fields) or fallback
    who = names[0] if len(names) == 1 else f"{names[0]} and {names[1]}" if len(names) == 2 else f"{names[0]} et al."
    return f"{who} {when}".strip()


def link(fields: Mapping[str, str]) -> str | None:
    """The work's own page: its `url`, else its DOI's resolver, else its arXiv page; None when it states none."""
    url = fields.get("url", "").strip()
    if url.startswith(("http://", "https://")):
        return url
    for identifier in identifiers(fields):
        scheme, _, value = identifier.partition(":")
        if scheme == "doi":
            return f"https://doi.org/{value}"
        if scheme == "arxiv":
            return f"https://arxiv.org/abs/{value}"
    return None


def expand_strings(text: str, strings: Mapping[str, str]) -> str:
    """An entry with each `@string` abbreviation it uses written out, so it stands alone (`docs/specs/nodes.md` §7); `text` itself when it uses none.

    Only a field whose value is, or concatenates with `#`, a bare name `strings` defines is written again, as `{value}`; every other byte of the entry is kept.
    """
    if not strings:
        return text
    folded = {k.lower(): v for k, v in strings.items()}

    def value(m: re.Match[str]) -> str:
        parts = [p.strip() for p in re.split(r"\s*#\s*", m.group(2))]
        if not any(p.lower() in folded for p in parts):
            return m.group(0)
        out = []
        for p in parts:
            if p.lower() in folded:
                out.append(folded[p.lower()])
            elif p[:1] in '{"' and p[-1:] in '}"':
                out.append(p[1:-1])
            else:
                out.append(p)
        return f"{m.group(1)}{{{''.join(out)}}}{m.group(3)}"

    return re.sub(
        r"(\b[A-Za-z][\w-]*\s*=\s*)((?:[A-Za-z][\w:.-]*|\{[^{}]*\}|\"[^\"]*\")(?:\s*#\s*(?:[A-Za-z][\w:.-]*|\{[^{}]*\}|\"[^\"]*\"))*)(\s*[,}\n])",
        value,
        text,
    )
