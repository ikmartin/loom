"""Looking one pasted or stated identifier up, and the key a new work's entry is given (`docs/design/library.md`: a reference's details are looked up, not typed).

A DOI is asked of doi.org by content negotiation, which answers for every registry's DOIs, so its 404 means the DOI names nothing. An arXiv id is asked of the arXiv API, a zbMATH number of zbMATH Open. ISBNs and MathSciNet numbers are recognised and not looked up, since loom uses no service for them.
"""

from __future__ import annotations

import http.client
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from loom.version import __version__

USER_AGENT = f"loom/{__version__} (+https://github.com/ikmartin/loom)"
DOI_ORG = "https://doi.org/"
ARXIV_API = "https://export.arxiv.org/api/query"
ZBMATH = "https://api.zbmath.org/v1/document/_search"
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"

#: `(url, headers) -> bytes`: how a look-up asks a service; tests pass their own.
Http = Callable[[str, dict[str, str]], bytes]


class LookupRefused(Exception):
    """A service could not be reached, or answered with an error."""


class NothingFound(LookupRefused):
    """A service answered that it has no such record (a 404): a look-up with no match, not a failure."""


def http_get(url: str, headers: dict[str, str]) -> bytes:
    """GET with loom's User-Agent, the default transport. A 404 is `NothingFound`; any other failure, a timeout or a broken answer among them, is `LookupRefused`."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return bytes(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NothingFound(url.split("?")[0]) from exc
        raise LookupRefused(f"{url.split('?')[0]}: HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LookupRefused(f"{url.split('?')[0]}: {exc.reason}") from exc
    except (OSError, http.client.HTTPException) as exc:  # a timeout reading the answer, a connection reset
        raise LookupRefused(f"{url.split('?')[0]}: {exc or type(exc).__name__}") from exc


# ---- what a pasted line is ---------------------------------------------------------------------------------------------

_DOI_ANY = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+?)[.,;)\]]*$", re.I)
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(\S+)$", re.I)
_ARXIV_NEW = r"\d{4}\.\d{4,5}(?:v\d+)?"
_ARXIV_OLD = r"[a-z][a-z-]*(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?"
_ARXIV_ANY = re.compile(
    rf"^(?:arxiv:\s*|https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|e-print)/)?({_ARXIV_NEW}|{_ARXIV_OLD})(?:\.pdf)?/?$",
    re.I,
)
_ZBL = re.compile(r"^(?:zbl\s*:?\s*|zbmath\s*:?\s*|https?://zbmath\.org/(?:\?q=an:)?)(\d{4}\.\d{5}|\d{8})/?$", re.I)
_MR = re.compile(r"^(?:mr\s*:?\s*|https?://mathscinet\.ams\.org/mathscinet-getitem\?mr=(?:MR)?)(\d{5,8})$", re.I)
_ISBN = re.compile(r"^(?:isbn(?:-1[03])?\s*:?\s*)?([0-9][0-9 -]{8,16}[0-9Xx])$", re.I)


@dataclass(frozen=True)
class Recognised:
    """What a pasted line is: its `kind` (`doi`, `arxiv`, `zbl`, `mr`, `isbn` or `unknown`) and the identifier it carries as loom writes it."""

    kind: str
    value: str = ""


def _isbn_ok(digits: str) -> bool:
    """Whether an ISBN-10 or ISBN-13's check digit holds."""
    if len(digits) == 10:
        total = sum((10 - i) * (10 if c in "Xx" else int(c)) for i, c in enumerate(digits))
        return total % 11 == 0 and not any(c in "Xx" for c in digits[:9])
    if len(digits) == 13 and digits.isdigit():
        return sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(digits)) % 10 == 0
    return False


def recognise(text: str) -> Recognised:
    """What `text` is, read without the network: a DOI, an arXiv id, a zbMATH number, an MR number, an ISBN, or none of them.

    Parameters
    ----------
    text : str
        One pasted line: a bare identifier, a prefixed one (`doi:`, `arXiv:`, `Zbl`, `MR`, `ISBN`) or a link to it.

    Returns
    -------
    Recognised
        Its kind and identifier; a DOI under arXiv's own prefix (10.48550) is the arXiv id it mints.
    """
    raw = text.strip()
    if m := _DOI_ANY.match(raw):
        doi = m.group(1)
        if a := _ARXIV_DOI.match(doi):
            return Recognised("arxiv", a.group(1))
        return Recognised("doi", doi)
    if m := _ARXIV_ANY.match(raw):
        return Recognised("arxiv", m.group(1))
    if m := _ZBL.match(raw):
        return Recognised("zbl", m.group(1))
    if m := _MR.match(raw):
        return Recognised("mr", m.group(1))
    if m := _ISBN.match(raw):
        digits = re.sub(r"[ -]", "", m.group(1))
        if _isbn_ok(digits):
            return Recognised("isbn", digits.upper())
    return Recognised("unknown")


# ---- the key a new work is given ---------------------------------------------------------------------------------------


def _surnames(author: str) -> list[str]:
    out = []
    for part in re.split(r"\s+and\s+", author):
        part = part.strip()
        if part:
            out.append(part.split(",")[0].strip() if "," in part else part.split()[-1])
    return out


#: The words Better BibTeX's `shorttitle` passes over: articles, prepositions and conjunctions, in the languages a mathematical library holds.
FUNCTION_WORDS = frozenset(
    "a ab aboard about above across after against al along amid among an and anti around as at before behind below "
    "beneath beside besides between beyond but by d da das de dei del della delle dello dem den der des despite die do "
    "down du during ein eine einem einen einer eines el en et except for from gli i il in inside into is l la las le les "
    "like lo los near nor of off on onto or over past per plus round save since so some sur than the through to toward "
    "towards un una unas under underneath une unlike uno unos until up upon versus via von while with within without "
    "yet zu zum".split()
)


def _ascii(text: str) -> str:
    """`text` as plain ASCII: TeX's commands and braces out, accents folded (`G{\\"o}del` is `Godel`)."""
    text = re.sub(r"\\[^A-Za-z]|\\[A-Za-z]+\s*", "", text).replace("{", "").replace("}", "")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def derived_key(entry: Mapping[str, str]) -> str:
    """Better BibTeX's default key, `auth.lower + shorttitle(3,3) + year`: the first author's surname in lower case, the first three words of the title that are not function words, each capitalised, and the year (`coxOptionPricingSimplified1979`); a part not known is left out, never guessed, and '' when neither the author nor the title gives a letter."""
    surnames = _surnames(entry.get("author", ""))
    auth = re.sub(r"[^A-Za-z0-9]", "", _ascii(surnames[0])).lower() if surnames else ""
    title = entry.get("title", "")
    words = [w for w in re.findall(r"[A-Za-z0-9]+", _ascii(title)) if w.lower() not in FUNCTION_WORDS]
    short = "".join(w[:1].upper() + w[1:].lower() for w in words[:3])
    if not re.search(r"[A-Za-z]", auth + short):
        return ""
    year = m.group(0) if (m := re.search(r"\b(?:1[5-9]|20)\d\d\b", entry.get("year", ""))) else ""
    return auth + short + year


def key_for(entry: Mapping[str, str], taken: set[str]) -> str:
    """The key a new work's entry is given: `derived_key`, else `untitled`; a key taken already gets `a`, `b`, … as Better BibTeX gives them.

    Parameters
    ----------
    entry : mapping
        The work's fields, as good as they will get on this act.
    taken : set of str
        The keys the library holds.

    Returns
    -------
    str
        The key.
    """
    base = derived_key(entry) or "untitled"
    return base if base not in taken else free_key(base, taken)


def free_key(key: str, taken: set[str]) -> str:
    """`key` with the first of `a`, `b`, …, `z`, then `2`, `3`, … that no work holds: two works whose details make one key."""
    import string

    for letter in string.ascii_lowercase:
        if f"{key}{letter}" not in taken:
            return f"{key}{letter}"
    n = 2
    while f"{key}{n}" in taken:
        n += 1
    return f"{key}{n}"


# ---- the look-up -------------------------------------------------------------------------------------------------------


@dataclass
class Found:
    """What a look-up found: `state` is `found`, `missing` (the identifier names nothing), `unreachable` (the service could not be asked; `message` says why), `offline` (it needs the network, which this act may not use) or `cannot` (an ISBN, a MathSciNet number, or text that is no identifier); `entry` holds the fields found."""

    state: str
    kind: str
    value: str = ""
    entry: dict[str, str] = field(default_factory=dict)
    message: str = ""


def _from_csl(data: dict[str, Any]) -> dict[str, str]:
    """BibTeX fields from doi.org's CSL JSON."""
    title = data.get("title") or ""
    title = " ".join(title) if isinstance(title, list) else str(title)
    authors = [
        ", ".join(x for x in [a.get("family", ""), a.get("given", "")] if x) or a.get("literal", "")
        for a in data.get("author") or []
    ]
    parts = ((data.get("issued") or data.get("published") or {}).get("date-parts") or [[None]])[0]
    venue = data.get("container-title") or ""
    venue = " ".join(venue) if isinstance(venue, list) else str(venue)
    out = {
        "author": " and ".join(a for a in authors if a),
        "title": title,
        "year": str(parts[0]) if parts and parts[0] else "",
        "journal" if venue else "publisher": venue or str(data.get("publisher") or ""),
        "doi": str(data.get("DOI") or ""),
    }
    return {k: v for k, v in out.items() if v}


def _from_atom(data: bytes, asked: str) -> dict[str, str] | None:
    """BibTeX fields from the arXiv API's Atom feed, or None when it holds no paper (arXiv answers an unknown id with an error entry)."""
    root = ET.fromstring(data)  # noqa: S314 -- the arXiv API's own feed, parsed for text only
    for entry in root.iter(f"{_ATOM}entry"):
        ident = (entry.findtext(f"{_ATOM}id") or "").strip()
        if not ident or "/api/errors" in ident:
            continue
        title = re.sub(r"\s+", " ", entry.findtext(f"{_ATOM}title") or "").strip()
        names = [re.sub(r"\s+", " ", a.findtext(f"{_ATOM}name") or "").strip() for a in entry.iter(f"{_ATOM}author")]
        authors = [f"{n.split()[-1]}, {' '.join(n.split()[:-1])}".strip(", ") for n in names if n]
        out = {
            "author": " and ".join(authors),
            "title": title,
            "year": (entry.findtext(f"{_ATOM}published") or "")[:4],
            "eprint": asked,
            "archiveprefix": "arXiv",
            "doi": (entry.findtext(f"{_ARXIV_NS}doi") or "").strip(),
            "journal": (entry.findtext(f"{_ARXIV_NS}journal_ref") or "").strip(),
        }
        return {k: v for k, v in out.items() if v} if title else None
    return None


def _from_zbmath(data: dict[str, Any], zbl: str) -> dict[str, str] | None:
    """BibTeX fields from zbMATH Open's answer, or None when it holds no document."""
    for r in data.get("result") or []:
        title = r.get("title")
        title = title.get("title", "") if isinstance(title, dict) else str(title or "")
        authors = [a.get("name", "") for a in (r.get("contributors") or {}).get("authors", []) if a.get("name")]
        links = r.get("links") or []
        doi = next((x["identifier"] for x in links if x.get("type") == "doi" and x.get("identifier")), "")
        arxiv = next((x["identifier"] for x in links if x.get("type") == "arxiv" and x.get("identifier")), "")
        out = {
            "author": " and ".join(authors),
            "title": title,
            "year": str(r.get("year") or ""),
            "zbl": zbl,
            "doi": doi,
        }
        if arxiv:
            out.update(eprint=arxiv, archiveprefix="arXiv")
        return {k: v for k, v in out.items() if v}
    return None


def look_up(text: str | Recognised, *, online: bool, http: Http | None = None) -> Found:
    """What an identifier names, as the fields of an entry loom would write for it.

    Parameters
    ----------
    text : str or Recognised
        What was pasted or stated, or what `recognise` made of it.
    online : bool
        Whether this look-up may use the network: the person's allowance for this act, or `[library] online`.
    http : callable, optional
        `(url, headers) -> bytes`; default `http_get`, which raises `NothingFound` on a 404.

    Returns
    -------
    Found
        Its state, and when found the entry's fields.
    """
    rec = text if isinstance(text, Recognised) else recognise(text)
    if rec.kind in ("isbn", "mr", "unknown"):
        why = (
            "Loom has no service to look this up: paste its DOI, its arXiv id or its BibTeX entry instead."
            if rec.kind != "unknown"
            else "This is not an identifier loom recognises: paste a DOI, an arXiv id, a zbMATH number or a BibTeX entry."
        )
        return Found("cannot", rec.kind, rec.value, message=why)
    if not online:
        return Found(
            "offline", rec.kind, rec.value, message="Looking this up needs the network, which this quilt has off."
        )
    get = http or http_get
    try:
        if rec.kind == "doi":
            raw = get(
                DOI_ORG + urllib.parse.quote(rec.value, safe="/"), {"Accept": "application/vnd.citationstyles.csl+json"}
            )
            entry = _from_csl(json.loads(raw.decode("utf-8")))
        elif rec.kind == "arxiv":
            raw = get(
                ARXIV_API + "?" + urllib.parse.urlencode({"id_list": rec.value}), {"Accept": "application/atom+xml"}
            )
            got = _from_atom(raw, rec.value)
            if got is None:
                return Found("missing", rec.kind, rec.value, message=f"arXiv has no paper {rec.value}.")
            entry = got
        else:
            params = {"search_string": f"an:{rec.value}", "page": "0", "results_per_page": "1"}
            raw = get(ZBMATH + "?" + urllib.parse.urlencode(params), {})
            got = _from_zbmath(json.loads(raw.decode("utf-8")), rec.value)
            if got is None:
                return Found("missing", rec.kind, rec.value, message=f"zbMATH Open has no document Zbl {rec.value}.")
            entry = got
    except NothingFound:
        where = {
            "doi": f"This DOI did not resolve: doi.org has no record of {rec.value}.",
            "arxiv": f"arXiv has no paper {rec.value}.",
        }
        return Found(
            "missing", rec.kind, rec.value, message=where.get(rec.kind, f"Nothing is recorded as {rec.value}.")
        )
    except (LookupRefused, ValueError, ET.ParseError) as exc:
        return Found("unreachable", rec.kind, rec.value, message=str(exc))
    return Found("found", rec.kind, rec.value, entry)
