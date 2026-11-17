"""Taking in a PDF a person provides, by `loom library add` or by a drop in the viewer: it is kept whatever is known about it, and what it shows only decides where.

A PDF that plainly is a work in the library is filed under it, beside any document the work holds, or recorded as a copy. Any other becomes a work of its own, its entry made from what can be read off it: a reference manager's file name, the PDF's document information, its first page, and at the least its file name. An identifier on its first pages is looked up where the network is allowed, and a lookup that finds nothing, or finds another work, changes nothing but the entry's fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom.refs.scan import Filing
from loom.scan.bib import BibEntry
from loom.scan.quilt import Quilt


@dataclass
class Seen:
    """What a provided PDF shows: the works it matches strongly, the one to file it under when one is best, whether that work holds these very bytes, and, matching none, the entry it makes of itself."""

    matches: list[dict[str, Any]] = field(default_factory=list)
    best: str = ""
    held: bool = False
    offer: dict[str, str] = field(default_factory=dict)
    key: str = ""
    digest: str = ""
    duplicates: list[str] = field(default_factory=list)
    weak: str = ""
    nearest: str = ""

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "matches": list(self.matches),
            "best": self.best,
            "held": self.held,
            "weak": self.weak,
            "nearest": self.nearest,
        }
        if self.offer:
            out.update(offer=dict(self.offer), key=self.key, digest=self.digest, duplicates=list(self.duplicates))
        return out


#: A title a PDF's document information carries that names no work: a tool's default, a file's own name, a publisher's internal id.
_NO_TITLE = re.compile(
    r"^(?:untitled.*|title|document\d*|layout \d+|slide \d+|cover|microsoft .*|doi[: ].*|pii[: ].*|arxiv:.*|\S+\.(?:dvi|pdf|tex|docx?|pptx?|indd|ps|qxd|qxp|fm))$",
    re.I,
)
#: An author a PDF's document information carries that names nobody: the account that made the file, a link, or the program that wrote it (a scan once gave its author as "https://imagemagick.org").
_NO_AUTHOR = re.compile(
    r"^(?:user|admin(?:istrator)?|owner|author|unknown|default|\S+@\S+|https?://\S*|www\.\S*)$"
    r"|\b(?:imagemagick|adobe|acrobat|microsoft|ghostscript|pdftex|latex|xetex|luatex|pdfcreator|scansnap|xerox|canon|epson)\b",
    re.I,
)
#: Marks a title on page one carries after it: a footnote's star or dagger.
_TITLE_MARKS = re.compile(r"[\s*†‡§¶]+$")
#: How much larger than the page's text a line must be set to be taken for its title.
TITLE_SIZE = 1.1
#: A number closing a file name, as a download's timestamp does.
_TAIL = re.compile(r"[\s_-]*\d{6,}$")


def _text(value: str) -> str:
    """A value read from a file, fit for a BibTeX field: one line, and no brace to unbalance the entry."""
    return re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()


def _info_title(info: dict[str, str]) -> str:
    title = _text(info.get("title", ""))
    return title if len(title) > 3 and any(c.isalpha() for c in title) and not _NO_TITLE.match(title) else ""


def _info_authors(info: dict[str, str]) -> str:
    """A PDF's `Author` as BibTeX writes names: `George Casella, Roger L. Berger` is two people, `Casella, George` one."""
    raw = _text(info.get("author", ""))
    if not raw or _NO_AUTHOR.match(raw) or not any(c.isalpha() for c in raw):
        return ""
    names = re.split(r"\s*;\s*|\s+and\s+|\s*&\s*", raw)
    if len(names) == 1 and "," in raw and all(len(n.split()) > 1 for n in raw.split(",")):
        names = raw.split(",")
    return " and ".join(n.strip() for n in names if n.strip())


def _largest(lines: list[tuple[str, float]]) -> str:
    """The line of page one set in the largest type, with the lines under it in that type, up to three, or '' when no line is set larger than the page's text.

    Lines of a masthead are passed over first, since a journal's name is often the largest thing on the page.
    """
    from loom.refs.ingest import masthead

    lines = lines[:30]
    skip = masthead([text for text, _ in lines])
    shown = [(i, text, h) for i, (text, h) in enumerate(lines) if i not in skip and sum(c.isalpha() for c in text) >= 3]
    if not shown:
        return ""
    heights = sorted(h for _, h in lines)
    top = max(h for _, _, h in shown)
    if top < heights[len(heights) // 2] * TITLE_SIZE:
        return ""
    run: list[str] = []
    last = -2
    for i, text, h in shown:
        if abs(h - top) > 0.6:
            if run:
                break
            continue
        if run and i != last + 1:
            break
        run.append(text)
        last = i
        if len(run) == 3:
            break
    title = " ".join(run)
    return title if len(title.split()) <= 24 else ""


def _first_page_title(pdf: Path) -> str:
    """The title page one sets: its largest type where one line stands out, else the first line that could be a title and is no sentence; '' for a page with neither."""
    from loom.refs.ingest import title_lines
    from loom.refs.pages import first_pages, sized_lines

    if title := _largest(sized_lines(pdf, 1)):
        return _text(_TITLE_MARKS.sub("", title))
    try:
        pages = first_pages(pdf, 1)
    except Exception:  # noqa: BLE001 -- an unreadable PDF has no first page to read a title from
        return ""
    for line in title_lines(pages[0]) if pages else []:
        if not line.endswith(".") and len(line.split()) <= 16 and any(c.isalpha() for c in line):
            return _text(_TITLE_MARKS.sub("", line))
    return ""


def _arxiv_year(value: str) -> str:
    """The year an arXiv id was given in: `0805.2065` is 2008, `math/0211159` 2002; '' for anything else."""
    m = re.match(r"^(\d{2})\d{2}\.\d{4,5}", value) or re.match(r"^[a-z-]+(?:\.[A-Z]{2})?/(\d{2})\d{5}", value)
    if m is None:
        return ""
    yy = int(m.group(1))
    return str(1900 + yy if yy >= 91 else 2000 + yy)


def own_entry(pdf: Path, name: str = "") -> dict[str, str]:
    """The entry a PDF makes of itself, which always has a title.

    In order of trust: the identifier it states as its own (`ingest.own_identifiers`), a reference manager's file name, its document information, the title page one sets in its largest type or else its first line that could be a title, a masthead never, and at the least its file name. The title of a heuristic guess is one line a person corrects by hand; a PDF is never turned away for want of a better one.

    Parameters
    ----------
    pdf : Path
        The document.
    name : str, default ''
        The name it was given, where that is not `pdf`'s own: a stored copy is always `paper.pdf`.

    Returns
    -------
    dict of str to str
        BibTeX fields; `title` is never empty.
    """
    from loom.refs.ingest import filename_authors
    from loom.refs.lookup import UNTITLED
    from loom.refs.pages import pdf_info, sha256_of
    from loom.refs.scan import _own_account

    stem = Path(name).stem if name else pdf.stem
    wid, said = _own_account(pdf, name)
    fields = {k: _text(v) for k, v in said.items()}
    info = pdf_info(pdf)
    if fields.get("title"):
        if who := _text(filename_authors(stem)):
            fields["author"] = who
    elif title := _info_title(info):
        fields["title"] = title
    else:
        named = _text(_TAIL.sub("", re.sub(r"[_\s]+", " ", stem)))
        fields["title"] = (
            _first_page_title(pdf)
            or (named if any(c.isalpha() for c in named) else "")
            or f"{UNTITLED} {sha256_of(pdf)[:8]}"
        )
    if not fields.get("author") and _info_title(info) == fields["title"] and (who := _info_authors(info)):
        fields["author"] = who
    if wid is not None:
        if wid.scheme == "arxiv":
            fields.update(eprint=wid.value, archiveprefix="arXiv")
            if not fields.get("year") and (year := _arxiv_year(wid.value)):
                fields["year"] = year
        else:
            fields[wid.scheme] = wid.value
    return fields


def _offer(seen: Seen, bib: dict[str, BibEntry], pdf: Path, *, online: bool, http: Any = None, name: str = "") -> None:
    """Fill in the entry a PDF makes of itself, and what a lookup of the identifier it states adds.

    A found record is kept only when the PDF carries its title: an identifier on the first pages may be one the document cites, and then it is not this work's.
    """
    from loom.refs.fetch import carries_title
    from loom.refs.lookup import duplicates, key_for, look_up
    from loom.refs.pages import sha256_of

    fields = own_entry(pdf, name)
    ident = fields.get("eprint") or fields.get("doi") or ""
    try:
        found = look_up(ident, bib, online=online, http=http) if ident else None
    except Exception:  # noqa: BLE001 -- a connection dropped mid-answer is one more lookup that adds nothing
        found = None
    seen.digest = "lookup"
    if found is not None and found.state == "found":
        if carries_title(pdf, BibEntry("", "misc", found.entry))[0]:
            seen.offer, seen.digest = {k: _text(v) for k, v in found.entry.items()}, found.digest
            seen.key, seen.duplicates = found.key, found.duplicates
            return
        for name in ("eprint", "archiveprefix", "doi"):
            fields.pop(name, None)
    seen.offer = fields
    seen.key = key_for(fields, set(bib), sha=sha256_of(pdf))
    seen.duplicates = duplicates(fields, None, bib)


def identify(
    root: Path,
    bib: dict[str, BibEntry],
    pdf: Path,
    *,
    online: bool = False,
    http: Any = None,
    offer: bool = True,
    name: str = "",
) -> Seen:
    """What `pdf` shows itself to be against the library's entries, and the entry it makes of itself when it is none of them.

    Parameters
    ----------
    root : Path
        The quilt, whose ledger says whether these bytes are held already.
    bib : dict of str to BibEntry
        The library's entries.
    pdf : Path
        The document, under the name it was given.
    online : bool, default False
        Whether a lookup of the identifier on its pages may use the network.
    http : callable, optional
        The transport `refs.lookup.look_up` asks with; tests inject their own.
    offer : bool, default True
        Whether to make the entry it would be as a work of its own, which a person may want even of a PDF matching a work; a lookup is asked only where no work is best.
    name : str, default ''
        The name it was given, where `pdf` is kept under another: what a reference manager wrote into it is read from this.

    Returns
    -------
    Seen
        Never empty-handed: `best` names a work, or `offer` is an entry with a title.
    """
    from loom.refs.ingest import identify_document
    from loom.refs.pages import sha256_of
    from loom.refs.scan import held_under, one_work_of

    holder = held_under(root, bib, sha256_of(pdf))
    if holder:
        return Seen(best=holder, held=True)
    identity = identify_document(pdf, bib, name)
    seen = Seen(
        matches=[{"citekey": m.citekey, "strength": m.strength, "how": m.how} for m in identity.strong],
        nearest=identity.nearest,
    )
    best = identity.best()
    if len(best) > 1 and (top := one_work_of([m.citekey for m in best], bib)):
        best = [m for m in best if m.citekey == top] or best[:1]
    if len(best) == 1:
        seen.best = best[0].citekey
    else:
        seen.weak = identity.weak if not best else f"it names {' and '.join(m.citekey for m in best)} equally"
    if offer:
        _offer(seen, bib, pdf, online=online and not seen.best, http=http, name=name)
    return seen


def plan_new_work(
    root: Path,
    pdf: Path,
    key: str,
    fields: dict[str, str],
    came_from: str,
    planned: set[Path] | None = None,
    claimed: set[str] | None = None,
) -> Filing:
    """Plan `pdf` as a work of its own under `key`, its entry `fields`; reads only.

    A work with no identifier lives under the document's hash, and its entry says so in `loom-file`, since the home its author, title and year would hash to moves when a person corrects its title. One with an identifier lives where that names, unless another document is there already. A home is never one that holds anything, or one another entry names (`claimed`, the store-relative homes in `loom-file`): such a document gets `file/<hash>-2`, `-3`, …, so no work is ever written over another's.
    """
    from loom.refs.identity import declared
    from loom.refs.pages import sha256_of, storage_root

    planned = set() if planned is None else planned
    claimed = set() if claimed is None else claimed
    store = storage_root(root)
    sha = sha256_of(pdf)

    def free(home: Path) -> bool:
        taken = home.is_dir() and any(home.iterdir())
        return not taken and home not in planned and home.relative_to(store).as_posix() not in claimed

    own = store / "file" / sha[:16]
    n = 2
    while not free(own):
        own = store / "file" / f"{sha[:16]}-{n}"
        n += 1
    home = own
    ids = declared(BibEntry(key, "misc", dict(fields)))
    if ids:
        named = store / ids[0].path
        if free(named):
            home = named
    new = {k: v for k, v in fields.items() if not k.startswith("loom-")}
    new["loom-source"] = came_from
    if not ids or home == own:
        new["loom-file"] = own.relative_to(store).as_posix()
    planned.add(home)
    return Filing(pdf, key, "pdf", sha, came_from, home=home, named=True, new=new)


def withdraw_setting_aside(root: Path, sha: str, by: str) -> None:
    """A person providing a document again wants it: what set those bytes aside stands no longer."""
    from loom.refs.unreadable import declarations, declare

    for key, claim in declarations(root, "forget").items():
        if key == f"sha256:{sha}" or claim.sha256 == sha:
            declare(root, "forget", key, "added again", by, undo=True)


def file_new(
    quilt: Quilt,
    bib: dict[str, BibEntry],
    pdf: Path,
    by: str,
    *,
    came_from: str,
    online: bool = False,
    http: Any = None,
    edits: dict[str, str] | None = None,
    read_pages: bool = True,
) -> dict[str, Any]:
    """Keep `pdf` as a work of its own: the document is in the store before the entry naming it is written.

    Parameters
    ----------
    quilt : Quilt
        The quilt.
    bib : dict of str to BibEntry
        The library's entries.
    pdf : Path
        The document, anywhere on disk; it is copied into the store.
    by : str
        Who added it.
    came_from : str
        Where it came from, as the ledger and the entry's `loom-source` record it.
    online : bool, default False
        Whether a lookup of the identifier on its pages may use the network.
    http : callable, optional
        The lookup's transport; tests inject their own.
    edits : dict, optional
        Fields the person typed, over what the document gives; an empty one is ignored.
    read_pages : bool, default True
        Whether to write its page text now, or leave it to a library run.

    Returns
    -------
    dict
        `{citekey, filed, sibling, already, copy_of, note}`, as `file_under` says it; the same bytes already held answer with the work holding them.

    See Also
    --------
    file_under : the same under a work that exists.
    """
    from loom.refs.added import added_entry
    from loom.refs.lookup import key_for
    from loom.refs.pages import sha256_of
    from loom.refs.scan import append_entries, file_document, held_under

    root = quilt.root
    holder = held_under(root, bib, sha256_of(pdf))
    if holder:
        return _answer(holder, already=f"{pdf.name} is already in the library as {holder}")
    seen = Seen()
    _offer(seen, bib, pdf, online=online, http=http)
    fields = {**seen.offer, **{k: _text(v) for k, v in (edits or {}).items() if _text(v)}}
    key = key_for(fields, set(bib), sha=sha256_of(pdf))
    f = plan_new_work(root, pdf, key, fields, came_from)
    withdraw_setting_aside(root, f.sha, by)
    file_document(quilt, f, by=by, read_pages=read_pages)
    assert f.new is not None
    append_entries(quilt, [added_entry(key, f.new, by)])
    return _answer(key, filed=True, unmapped=f.unmapped)


def _answer(
    citekey: str,
    *,
    filed: bool = False,
    sibling: str = "",
    already: str = "",
    copy_of: str = "",
    note: str = "",
    unmapped: str = "",
) -> dict[str, Any]:
    return {
        "citekey": citekey,
        "filed": filed,
        "sibling": sibling,
        "already": already,
        "copy_of": copy_of,
        "note": note,
        "unmapped": unmapped,
    }


def named_for(identity: Any, bib: dict[str, BibEntry], citekey: str) -> tuple[str, str]:
    """The work a person named resolved against what the document shows: (the entry to file under, what it shows against that work).

    A document stating a version of the work named is that version's, which is no contradiction; anything else it shows is said beside the person's word.
    """
    from loom.refs.scan import one_work_of

    why = str(identity.refusal_for(citekey, bib[citekey]))
    other = next((m.citekey for m in identity.strong if m.citekey != citekey), "")
    return (other, "") if why and other and one_work_of([other, citekey], bib) else (citekey, why)


def file_under(
    quilt: Quilt,
    bib: dict[str, BibEntry],
    pdf: Path,
    citekey: str,
    by: str,
    *,
    came_from: str,
    read_pages: bool = True,
) -> dict[str, Any]:
    """File `pdf` under the work a person named for it, as `loom library add PDF --for CITEKEY` files it, and say where it went.

    The person's word files it. What the document shows to the contrary is said in `note` and recorded in the ledger with who named it, for them to look at.

    Parameters
    ----------
    quilt : Quilt
        The quilt.
    bib : dict of str to BibEntry
        The library's entries, holding `citekey`.
    pdf : Path
        The document, anywhere on disk; it is copied into the store.
    citekey : str
        The work it is filed under.
    by : str
        Who filed it, for the copy ledger.
    came_from : str
        Where it came from, as the ledger and a sibling entry's `loom-source` record it: the dropped file's name.
    read_pages : bool, default True
        Whether to write its page text now, or leave it to a library run.

    Returns
    -------
    dict
        `{citekey, filed, sibling, already, copy_of, note, unmapped}`: whether it was filed, under a sibling entry beside the work's first document, held already, or a copy of one of the work's documents; what it shows against the work; and why it has no page text.

    See Also
    --------
    file_new : a PDF that is no work in the library.
    """
    from loom.refs.ingest import identify_document
    from loom.refs.pages import sha256_of
    from loom.refs.scan import append_entries, file_document, plan_filing, record_copy_of

    citekey, why = named_for(identify_document(pdf, bib), bib, citekey)
    f = Filing(pdf, citekey, "pdf", sha256_of(pdf), came_from, forced=why, named=True)
    sibling = plan_filing(quilt, bib, f, set(bib), {})
    withdraw_setting_aside(quilt.root, f.sha, by)
    if not f.already:
        file_document(quilt, f, by=by, read_pages=read_pages)
    if f.copy_of:
        record_copy_of(quilt, bib, f)
    append_entries(quilt, [sibling] if sibling is not None else [])
    return _answer(
        citekey,
        filed=not f.already,
        sibling=f.sibling,
        already=f.already,
        copy_of=f.copy_of,
        note=why if not f.already else "",
        unmapped=f.unmapped,
    )
