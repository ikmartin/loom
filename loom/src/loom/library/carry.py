"""The carry-over of a quilt an earlier loom made, in layout format 1, into the node store (`docs/specs/nodes.md` §7): run once, by `loom upgrade`, and the only module that knows the old layout.

The old library was a bibliography, `.loom/library/bibliography.bib`, whose entries held loom's own `loom-*` fields; a store, `.loom/library/storage/`, holding each work's `paper.pdf`, its source in `src/` and its `overview.md` in a folder named by the entry's `loom-file` or by the first identifier it states; the digests beside them; and notes on works naming a work by an identifier (`doi:…`, `arXiv:…`, `work:<hash>`). Each entry becomes a reference with its documents stored by hash, each note on a work names its reference, each overview becomes a note, each `cited:work:` link in loom's own pages a `quilt:` link, and then the old files go, the digests with them. Nothing is fatal: what cannot be carried is said in `Carried.problems` and left where it is.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from loom import clock
from loom.identity import is_agent
from loom.library import documents
from loom.library.checks import check_file
from loom.library.entries import identifiers, matchable
from loom.library.gather import held_keys
from loom.library.node import Node, NodeUnreadable, file_name, node_bytes
from loom.library.references import Minter, attach, make
from loom.library.store import NodeRefused, read
from loom.locks import locked
from loom.paths import (
    ANNOTATION_LOG,
    ID_LOCK,
    LIBRARY,
    LIBRARY_DOCUMENTS,
    LIBRARY_LOCK,
    LIBRARY_NODES,
    WRITES_LOCK,
)
from loom.scan.bib import citekey_slug, parse_bib, raw_entries
from loom.scan.tokenize import match_group

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: The old library's bibliography, its entries holding loom's own `loom-*` fields.
BIBLIOGRAPHY = f"{LIBRARY}/bibliography.bib"
#: What a person said could not be read, and the relations between results, kept and removed.
UNREADABLE = f"{LIBRARY}/unreadable.json"
LINKS = f"{LIBRARY}/links.jsonl"
LINKS_REMOVED = f"{LIBRARY}/links-removed.jsonl"
#: The old store of documents, a folder each work, and its ledger of what each copy was taken from.
STORAGE = f"{LIBRARY}/storage"
STORE_LEDGER = f"{STORAGE}/copied.json"
#: The write API's refusal when the research state the carry rewrites holds a link that names nothing or a byte that is not text, which the door will not write.
STATE_REFUSED = "state-refused"
#: Who an overview's note is written by: a name `identity.is_agent` reads as no agent's.
OVERVIEW_AUTHOR = "loom (carried overview)"
#: A work's folder in the old store: its PDF, its source's files, and its overview.
PAPER = "paper.pdf"
SOURCE = "src"
OVERVIEW = "overview.md"
#: The old library's own files directly under `.loom/library/`, beside the bibliography and the store: what a person said could not be read (`unreadable.json`) and the relations between results, kept and removed (`links.jsonl`, `links-removed.jsonl`).
OLD_FILES = (BIBLIOGRAPHY, UNREADABLE, LINKS, LINKS_REMOVED)
#: A digest's files directly under `.loom/library/`, by the end of their names: `<ck>.tex` its verified results and `<ck>.proposed.tex` its proposals (both `.tex`), `<ck>.results.json` each result's two texts, anchor and state, and `<ck>.proposals.jsonl` the proposals' events.
DIGEST_ENDINGS = (".tex", ".results.json", ".proposals.jsonl")
#: What the node store keeps under `.loom/library/`, which the carry leaves alone.
KEPT = (LIBRARY_NODES, LIBRARY_DOCUMENTS)
#: The schemes a note named a work by, as the earlier loom parsed them, in any case.
SCHEMES = ("doi", "arxiv", "mr", "zbl", "work")

_DOI_BARE = re.compile(r"^10\.\d{4,9}/\S+$")
_ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(\S+)$", re.I)
_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf|e-print)/([^\s?#]+)", re.I)
_DOI_URL = re.compile(r"(?:doi\.org/|dx\.doi\.org/)(10\.[^\s?#]+)", re.I)
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_FILED = re.compile(r"^file/([0-9a-f]{16})(-[0-9]+)?$")
_HEAD = re.compile(r"@\s*\w+\s*[{(]\s*[^,]*,")
_FIELD = re.compile(r"\s*([A-Za-z][\w-]*)\s*=\s*")
_PREFIX = re.compile(r"^%\s*!LOOM\s+prefix:\s*(\S+)", re.M)
_CITED_WORK = re.compile(r"(?<=\]\()cited:work:([^?#)\s]+)([?#][^)\s]*)?(?=\))")
_JSON_SPACE = " \t\n\r"


@dataclass
class Carried:
    """What one carry did, or with `write` False would do.

    Attributes
    ----------
    references : dict of str to str
        Each old citekey made a reference, to the reference's id.
    documents : int
        Documents put into the store by hash, each counted once.
    notes_rekeyed : int
        Lines of the annotation log whose target now names a reference.
    overviews : int
        Overviews carried as notes on their references.
    links_rewritten : int
        `cited:work:<hash>` links rewritten as `quilt:<ref>` in the research state and the carried overviews.
    removed : list of str
        Quilt-relative paths of the old files and folders removed.
    problems : list of str
        Sentences saying what could not be carried, and so was left; never fatal.
    """

    references: dict[str, str] = field(default_factory=dict)
    documents: int = 0
    notes_rekeyed: int = 0
    overviews: int = 0
    links_rewritten: int = 0
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class _Work:
    """One entry of the old bibliography: its key, its entry as a reference holds it, its fields, its folder in the old store, and what became of it.

    `kept` says its folder stays, its entry or a document of it not carried; `pdf` is the PDF its reference holds afterwards.
    """

    key: str
    text: str
    fields: dict[str, str]
    folder: Path | None
    ref: str | None = None
    pdf: str | None = None
    kept: bool = False

    @property
    def version(self) -> str:
        """The key this entry is another document of (`loom-copy-of`), '' for none."""
        return self.fields.get("loom-copy-of", "").strip()


def carry(root: Path, result: ScanResult, *, write: bool = True) -> Carried:
    """Carry a quilt's library from the earlier layout into the node store, once: references with their documents, notes re-keyed, overviews as notes, links rewritten, and the old files removed.

    Parameters
    ----------
    root : Path
        The quilt.
    result : ScanResult
        The quilt's scan, which stems are minted against and which names its research state.
    write : bool, default True
        Do it; False writes nothing and says what would be carried, the ids it would mint among it.

    Returns
    -------
    Carried
        What was carried, removed and left, with why for each thing left.

    Notes
    -----
    Holds the door's lock, then the id lock and the library's lock, throughout, the annotation log's while it is rewritten. The research state is rewritten only through the door (`pages.write`); where the door refuses it, the carry stops there with a `WriteRefused` that says why (`STATE_REFUSED` for a link that names nothing or a byte that is not text, else the door's own code), before the old library is removed, so the quilt keeps its old layout and an upgrade once the state is mended carries the rest. An entry whose key a reference already holds, ignoring case, makes none, so a second carry changes nothing; the old files are removed only after every reference and document is written, and a work's folder that could not be carried stays.
    """
    out = Carried()
    with _held(root, write):
        works = _works(root)
        _references(root, result, works, out, write=write)
        names = _Names(works)
        _notes(root, works, names, out, write=write)
        _overviews(root, works, names, out, write=write)
        _state(root, result, names, out, write=write)
        _remove(root, works, out, write=write)
    return out


@contextmanager
def _held(root: Path, write: bool) -> Iterator[None]:
    """The door's lock, then the id lock and then the library's lock, as gathering and every node writer take the last two; none when not writing, which makes no lock file. The door's lock comes first because the carry writes the research state through the door, and the door's lock is taken before the id lock everywhere (`cli._quilt.drawing_ids`): taken after it, a carry and a command drawing an id could each wait on the other."""
    with ExitStack() as stack:
        if write:
            stack.enter_context(locked(root / WRITES_LOCK))
            stack.enter_context(locked(root / ID_LOCK))
            stack.enter_context(locked(root / LIBRARY_LOCK))
        yield


def _rel(root: Path, path: Path) -> str:
    """`path` quilt-relative as a person reads it; as it is when it lies outside the quilt."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _counted(n: int, word: str) -> str:
    """`n` and `word`, plural unless one."""
    return f"{n} {word}" + ("" if n == 1 else "s")


# ---- the old bibliography and store --------------------------------------------------------------------------------


def _works(root: Path) -> list[_Work]:
    """Each entry of the old bibliography in its order, its text without loom's fields and with line feeds alone, and its folder in the store.

    The folder is where the earlier loom put it, `storage/<loom-file>` or by the entry's identity; failing that, the ledger's place for a copy taken from the file the entry came from (`loom-source`).
    """
    path = root / BIBLIOGRAPHY
    if not path.is_file():
        return []
    ledger = _ledger(root)
    out: list[_Work] = []
    for key, raw in raw_entries(path.read_bytes().decode("utf-8", errors="replace")).items():
        text = raw.replace("\r\n", "\n").replace("\r", "\n")
        parsed = parse_bib(text)
        fields = dict(parsed[key].fields) if key in parsed else {}
        out.append(_Work(key, _without_loom_fields(text), fields, _folder(root, fields, ledger)))
    return out


def _without_loom_fields(entry: str) -> str:
    """One entry with every field whose name starts `loom-` taken out, every other byte kept.

    Fields are walked as `scan.bib` reads them, so a value spanning lines goes whole; a field with its lines to itself takes them, one sharing a line takes only itself, its comma and the blanks after.
    """
    head = _HEAD.match(entry)
    if head is None:
        return entry
    cuts: list[tuple[int, int]] = []
    pos = head.end()
    while (m := _FIELD.match(entry, pos)) is not None:
        end = _value_end(entry, m.end())
        stop = end
        while stop < len(entry) and entry[stop] in " \t":
            stop += 1
        if stop < len(entry) and entry[stop] == ",":
            stop += 1
        if m.group(1).lower().startswith("loom-"):
            cuts.append(_cut(entry, m.start(1), stop))
        pos = stop
    for start, stop in reversed(cuts):
        entry = entry[:start] + entry[stop:]
    return entry


def _cut(entry: str, start: int, stop: int) -> tuple[int, int]:
    """The span removing the field `entry[start:stop]`: its whole lines when nothing else shares them, else the field, its comma and the blanks after it."""
    line = entry.rfind("\n", 0, start) + 1
    newline = entry.find("\n", stop)
    rest = entry[stop:] if newline < 0 else entry[stop:newline]
    if not entry[line:start].strip() and not rest.strip() and newline >= 0:
        return line, newline + 1
    while stop < len(entry) and entry[stop] in " \t":
        stop += 1
    return start, stop


def _value_end(text: str, pos: int) -> int:
    """Where a field's value starting at `pos` ends, its `#`-joined parts included, read as `scan.bib` reads it."""
    p, end, n = pos, pos, len(text)
    while p < n:
        while p < n and text[p] in " \t\n":
            p += 1
        if p >= n:
            break
        if text[p] == "{":
            q = match_group(text, p)
            if q < 0:
                return n
            p = end = q
        elif text[p] == '"':
            q = text.find('"', p + 1)
            p = end = n if q < 0 else q + 1
        else:
            m = re.match(r"[^,#})\n]+", text[p:])
            if not m:
                break
            p = end = p + len(m.group(0).rstrip())
        q = p
        while q < n and text[q] in " \t\n":
            q += 1
        if q < n and text[q] == "#":
            p = q + 1
            continue
        break
    return end


def _ledger(root: Path) -> dict[str, dict[str, Any]]:
    """The old store's copy ledger (`storage/copied.json`), a document's sha to where it went; empty when absent or unreadable."""
    try:
        data = json.loads((root / STORE_LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def _folder(root: Path, fields: Mapping[str, str], ledger: Mapping[str, Mapping[str, Any]]) -> Path | None:
    """Where the old store kept an entry's documents, or None when nothing is there: `loom-file`, else its identity's place, else the ledger's for its `loom-source`."""
    filed = fields.get("loom-file", "").strip()
    if filed:
        place = _place(root, filed)
    else:
        scheme, value = _identity(fields)
        place = _place(root, f"{scheme}/{_UNSAFE.sub('_', value.strip())}")
    if place.is_dir():
        return place
    came = fields.get("loom-source", "").strip()
    for sha in sorted(ledger):
        to = str(ledger[sha].get("to") or "")
        if came and to and ledger[sha].get("from") == came and _place(root, to).is_dir():
            return _place(root, to)
    return None


def _place(root: Path, rel: str) -> Path:
    """A place the old store names, relative to it, as the path its own listing gives; one that climbs out of the store, as a hand-written `loom-file` may, made whole so that it is never taken for a folder inside it."""
    clean = os.path.normpath(rel)
    if os.path.isabs(clean) or clean.split(os.sep)[0] == os.pardir:
        return Path(os.path.normpath(root / STORAGE / rel))
    return root / STORAGE / clean


def _declared(fields: Mapping[str, str]) -> list[tuple[str, str]]:
    """Every identifier an entry states, as (scheme, value), the most trusted first, exactly as the earlier loom read them to name a work's folder."""
    out: list[tuple[str, str]] = []
    doi = fields.get("doi", "").strip()
    if doi and (_DOI_BARE.match(doi) or doi.startswith("10.")):
        m = _ARXIV_DOI.match(doi)
        out.append(("arxiv", m.group(1)) if m else ("doi", doi))
    eprint = fields.get("eprint")
    kind = (fields.get("eprinttype") or fields.get("archiveprefix") or "arxiv").strip().lower()
    if eprint and kind == "arxiv":
        value = re.sub(r"^arxiv:", "", eprint.strip(), flags=re.I)
        found = re.search(r"v(\d+)$", eprint)
        version = fields.get("version") or (found.group(1) if found else None)
        if value and version and not re.search(r"v\d+$", value):
            value = f"{value}v{version}"
        if value and not any(s == "arxiv" for s, _ in out):
            out.append(("arxiv", value))
    for name, scheme in (("mrnumber", "mr"), ("zbl", "zbl"), ("zblnumber", "zbl")):
        value = fields.get(name, "").strip()
        if value and not any(s == scheme for s, _ in out):
            out.append((scheme, value))
    if not out:
        url = fields.get("url", "")
        if m := _ARXIV_URL.search(url):
            out.append(("arxiv", m.group(1)))
        elif m := _DOI_URL.search(url):
            out.append(("doi", m.group(1)))
    return out


def _identity(fields: Mapping[str, str]) -> tuple[str, str]:
    """The one identifier the old store named an entry's folder by: the first it states, else the work hash of the PDF it came in with, else the hash of its authors, title and year."""
    found = _declared(fields)
    if found:
        return found[0]
    return "work", _filed(fields) or _synthetic(fields)


def _filed(fields: Mapping[str, str]) -> str | None:
    """The work hash of an entry stating no identifier that came in as a PDF: the first eight digits of the PDF's hash its `loom-file` names, with a place's number after them."""
    m = _FILED.match(fields.get("loom-file", "").strip())
    return m.group(1)[:8] + (m.group(2) or "") if m else None


def _synthetic(fields: Mapping[str, str]) -> str:
    """The old `work:` hash of an entry: eight hex digits of the SHA-256 of its surnames, title and year, folded to lower-case ASCII letters and digits."""
    surnames = []
    for part in re.split(r"\s+and\s+", fields.get("author", "")):
        part = part.strip()
        if part:
            surnames.append(part.split(",")[0] if "," in part else part.split()[-1] if part.split() else "")
    raw = "|".join(["+".join(surnames), fields.get("title", ""), fields.get("year", "")])
    folded = "".join(c for c in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(c))
    return hashlib.sha256(re.sub(r"[^a-z0-9|+]+", "", folded.lower()).encode("utf-8")).hexdigest()[:8]


# ---- references and their documents ----------------------------------------------------------------------------------


def _references(root: Path, result: ScanResult, works: list[_Work], out: Carried, *, write: bool) -> None:
    """Make a reference of each entry no reference holds, its documents put in the store first; give one whose key a reference holds the documents that reference lacks.

    An entry is checked by itself before anything of it is stored, so an entry the checks refuse leaves no document behind; a write refused by the rest of the store is said the same way. A reference holding another document of a kind leaves the folder in place, said. Not writing, the ids are minted all the same.
    """
    minter = Minter.of(result)
    # keys folded as check 9 folds them, so a key a reference holds in another case (`STRASSE1`, `Straße1`) is held
    held = {key.casefold(): ref for key, ref in held_keys(root).items()}
    holding: dict[str, dict[str, str | None]] = {}
    stored: set[tuple[str, str]] = set()
    for w in works:
        where = _rel(root, w.folder) if w.folder is not None else ""
        stays = f"; its documents stay in {where}" if w.folder is not None else ""
        ref = held.get(w.key.casefold())
        refused = _refused(w.text, minter.prefix) if ref is None else ""
        if refused:
            out.problems.append(
                f"{w.key} was not carried, since the checks refuse its entry: {refused.rstrip('.')}{stays}."
            )
            w.kept = True
            continue
        try:
            pdf, tex = _documents(root, w.folder, write=write)
        except OSError as exc:
            out.problems.append(f"{w.key} was not carried, since its documents could not be read ({exc}){stays}.")
            w.kept = True
            continue
        found = {"pdf": pdf, "tex": tex}
        if ref is None:
            try:
                ref = _make(root, w, minter, pdf, tex) if write else f"{minter.stem()}-ref"
            except NodeRefused as exc:
                out.problems.append(
                    f"{w.key} was not carried, since the checks refuse its entry: {str(exc).rstrip('.')}{stays}."
                )
                w.kept = True
                continue
            held[w.key.casefold()] = ref
            holding[ref] = dict(found)
            out.references[w.key] = ref
            stored |= {(k, d) for k, d in found.items() if d}
        else:
            if ref not in holding:
                holding[ref] = _holds(root, ref)
            has = holding[ref]
            for which, digest in found.items():
                if not digest or has.get(which) == digest:
                    continue
                if has.get(which) is None:
                    if write:
                        attach(root, ref, which, digest, by="loom", kind="loom", source=_source(w))
                    has[which] = digest
                    stored.add((which, digest))
                else:
                    out.problems.append(f"{w.key}'s {which} in {where} is not the one {ref} holds, so it stays there.")
                    w.kept = True
        pdf = holding[ref].get("pdf")
        w.ref, w.pdf = ref, pdf if pdf and pdf.startswith("sha256:") else None
    out.documents = len(stored)


def _refused(entry: str, prefix: str) -> str:
    """What the checks refuse in an entry by itself, as a reference standing alone would be checked, '' for nothing; said of "the reference", since it has no id yet."""
    probe = f"{prefix}-0000-ref"
    _node, said = check_file(file_name(probe), node_bytes(Node(id=probe, taxon="reference", body=entry.strip() + "\n")))
    return " ".join(d.message.replace(file_name(probe), "the reference") for d in said)


def _make(root: Path, w: _Work, minter: Minter, pdf: str | None, tex: str | None) -> str:
    """The id of the reference made of `w`, carried by loom from its entry."""
    made = make(root, w.text, minter, by="loom", kind="loom", how="carry", found_by="entry", looked_up=False, source=_source(w), pdf=pdf, tex=tex)  # fmt: skip
    return made.id


def _holds(root: Path, ref: str) -> dict[str, str | None]:
    """The documents a reference already in the library holds, by kind; a reference loom cannot read holds an unknown one of each."""
    try:
        node = read(root, ref)
    except NodeUnreadable:
        node = None
    if node is None:
        return {"pdf": "?", "tex": "?"}
    return {"pdf": node.pdf, "tex": node.tex}


def _documents(root: Path, folder: Path | None, *, write: bool) -> tuple[str | None, str | None]:
    """The hashes of a work folder's `paper.pdf` and `src/`, put in the store when writing; None for one it does not have.

    A `src/` holding no file is no source. Raises OSError for a document that cannot be read, which the caller says.
    """
    if folder is None:
        return None, None
    paper, src = folder / PAPER, folder / SOURCE
    pdf = tex = None
    if paper.is_file():
        pdf = documents.put_pdf(root, paper) if write else documents.hash_file(paper)
    if src.is_dir():
        try:
            if write:
                tex = documents.put_source(root, src)
            else:
                tex = "sha256:" + hashlib.sha256(documents.source_tar(src)).hexdigest()
        except documents.NotASource:
            tex = None
    return pdf, tex


def _source(w: _Work) -> str:
    """What a reference was carried from, as a person would name it: the file the entry came from, else its place in the old store, else the bibliography; a version says whose."""
    said = w.fields.get("loom-source", "").strip() or w.fields.get("loom-file", "").strip()
    said = said or PurePosixPath(BIBLIOGRAPHY).name
    return f"{said} copy-of {w.version}" if w.version else said


# ---- naming a work as the old records did ------------------------------------------------------------------------------


class _Names:
    """The carried references by what the old records named a work by: an identifier, a `work:` hash, and the hash of a PDF.

    Where several answer, the one that is no other's version wins, then the first in the bibliography, as the old lookups took the first entry that answered.
    """

    def __init__(self, works: list[_Work]) -> None:
        carried = sorted((w for w in works if w.ref), key=lambda w: bool(w.version))
        self.identifier: dict[str, str] = {}
        self.stating: dict[str, str] = {}
        self.unstating: dict[str, str] = {}
        self.pdf: dict[str, str] = {}
        for w in carried:
            assert w.ref is not None
            declared = _declared(w.fields)
            said = {matchable(x) for x in identifiers(w.fields)} | {matchable(f"{s}:{v}") for s, v in declared}
            for x in said:
                self.identifier.setdefault(x, w.ref)
            hashes = [h for h in (_filed(w.fields), _synthetic(w.fields)) if h]
            for h in hashes:
                (self.stating if declared else self.unstating).setdefault(h, w.ref)
            if w.pdf:
                self.pdf.setdefault(w.pdf, w.ref)

    def work(self, scheme: str, value: str) -> str | None:
        """The reference a note's `scheme:value` names, or None."""
        if scheme == "work":
            return self.unstating.get(value) or self.stating.get(value)
        return self.identifier.get(matchable(f"{scheme}:{value}"))


def _named_work(target: str) -> tuple[str, str] | None:
    """(scheme, value) when `target` names a work by an identifier or a `work:` hash, the scheme in lower case; None for anything else."""
    scheme, sep, value = target.strip().partition(":")
    if not sep or scheme.strip().lower() not in SCHEMES or not value.strip():
        return None
    return scheme.strip().lower(), value.strip()


# ---- notes on works --------------------------------------------------------------------------------------------------


def _notes(root: Path, works: list[_Work], names: _Names, out: Carried, *, write: bool) -> None:
    """Rewrite the annotation log once, under its lock, each line naming a work in its `target` naming its reference instead, every other byte kept.

    A note drawn or anchored on a PDF (`artifact`, or a page anchor's `sha256`) names the reference holding that PDF by hash; any other names the reference its identifier answers. A note no reference answers, and a note on a digest's result, is left and said.
    """
    path = root / ANNOTATION_LOG
    if not path.is_file():
        return
    results = _digest_results(root)
    unanswered: dict[str, int] = {}
    unheld = on_results = 0
    with locked(path) if write else nullcontext():
        pieces = path.read_bytes().decode("utf-8", errors="surrogateescape").split("\n")
        changed = 0
        for i, piece in enumerate(pieces):
            try:
                event = json.loads(piece)
            except ValueError:
                continue
            target = event.get("target") if isinstance(event, dict) else None
            if not isinstance(target, str):
                continue
            named = _named_work(target)
            if named is None:
                if event.get("event") in ("created", "replied") and _on_result(target, results):
                    on_results += 1
                continue
            drawn_on = _pdf_of(event)
            ref = names.pdf.get(f"sha256:{drawn_on}") if drawn_on else None
            if ref is None:
                ref = names.work(*named)
                unheld += bool(ref and drawn_on)
            span = _value_span(piece, "target")
            if ref is None or span is None:
                unanswered[target] = unanswered.get(target, 0) + 1
                continue
            pieces[i] = piece[: span[0]] + json.dumps(ref, ensure_ascii=False) + piece[span[1] :]
            changed += 1
        if changed and write:
            with path.open("r+b") as fh:
                fh.write("\n".join(pieces).encode("utf-8", errors="surrogateescape"))
                fh.truncate()
    out.notes_rekeyed = changed
    for target, n in unanswered.items():
        out.problems.append(f"{_counted(n, 'line')} of the annotation log {'names' if n == 1 else 'name'} {target}, which no carried reference answers, so {'it is' if n == 1 else 'they are'} left naming it.")  # fmt: skip
    if unheld:
        out.problems.append(f"{_counted(unheld, 'note')} on a work's page {'was' if unheld == 1 else 'were'} drawn on a PDF no reference holds, so each names the reference its work's identifier answers.")  # fmt: skip
    if on_results:
        out.problems.append(f"{_counted(on_results, 'note')} on a digest's result now {'names' if on_results == 1 else 'name'} nothing, since the digests are removed with the old library.")  # fmt: skip


def _pdf_of(event: Mapping[str, Any]) -> str:
    """The hash of the PDF a note was drawn or anchored on, 64 hex digits: a mark's `artifact`, or a page anchor's `sha256`; '' for neither."""
    anchor = event.get("anchor")
    for value in (event.get("artifact"), anchor.get("sha256") if isinstance(anchor, dict) and anchor.get("kind") == "pdf" else None):  # fmt: skip
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            return value
    return ""


def _value_span(line: str, key: str) -> tuple[int, int] | None:
    """Where the value of `key` stands in the JSON object `line`, as (start, end) of its text; None when `line` is no object holding it.

    Only the object's own keys are read, never a nested object's; a key given twice is read last, as `json.loads` reads it.
    """
    decoder = json.JSONDecoder()
    found: tuple[int, int] | None = None
    try:
        i = _skip(line, 0)
        if line[i] != "{":
            return None
        i = _skip(line, i + 1)
        if line[i] == "}":
            return None
        while True:
            name, i = decoder.raw_decode(line, i)
            i = _skip(line, i)
            if line[i] != ":":
                return None
            start = _skip(line, i + 1)
            _value, end = decoder.raw_decode(line, start)
            if name == key:
                found = (start, end)
            i = _skip(line, end)
            if line[i] == "}":
                return found
            if line[i] != ",":
                return None
            i = _skip(line, i + 1)
    except (ValueError, IndexError):
        return None


def _skip(text: str, i: int) -> int:
    while i < len(text) and text[i] in _JSON_SPACE:
        i += 1
    return i


def _digest_results(root: Path) -> tuple[frozenset[str], tuple[str, ...]]:
    """What a digest's result was named by: every id its `<ck>.results.json` records, and each id prefix a digest declares (`% !LOOM prefix:`) or its citekey gives."""
    folder = root / LIBRARY
    found: set[str] = set()
    prefixes: set[str] = set()
    if not folder.is_dir():
        return frozenset(), ()
    for path in sorted(folder.iterdir()):
        if not path.is_file() or not path.name.endswith(DIGEST_ENDINGS):
            continue
        citekey = next(path.name.removesuffix(e) for e in (".proposed.tex", *DIGEST_ENDINGS) if path.name.endswith(e))
        prefixes.add(citekey_slug(citekey))
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.name.endswith(".tex"):
            prefixes.update(_PREFIX.findall(text))
        elif path.name.endswith(".results.json"):
            try:
                data = json.loads(text)
            except ValueError:
                continue
            listed = data.get("results") if isinstance(data, dict) else None
            found.update(str(r["id"]) for r in listed or [] if isinstance(r, dict) and r.get("id"))
    return frozenset(found), tuple(sorted(p for p in prefixes if p))


def _on_result(target: str, results: tuple[frozenset[str], tuple[str, ...]]) -> bool:
    """Whether a note's target is a digest's result, or a proof or a place in one: an id a digest recorded, or one under a digest's prefix."""
    ids, prefixes = results
    key = target.split("#", 1)[0].split("/", 1)[0]
    return key in ids or any(key.startswith(f"{p}-") for p in prefixes)


# ---- overviews and links ---------------------------------------------------------------------------------------------


def _overviews(root: Path, works: list[_Work], names: _Names, out: Carried, *, write: bool) -> None:
    """Make each carried work's `overview.md` one note on its reference, of type `note`, by `OVERVIEW_AUTHOR`, its `cited:work:` links rewritten; one the log holds already is not made again."""
    from loom.records.log import append_new, replay
    from loom.records.types import drawn_look, load_types

    have = {(a.target_key, a.body) for r in replay(root)[0] for a in r.annotations if a.author_id == OVERVIEW_AUTHOR}
    types = load_types(root)
    done: set[tuple[str, str]] = set()
    for w in works:
        page = w.folder / OVERVIEW if w.folder is not None else None
        if w.ref is None or page is None or not page.is_file():
            continue
        text, links = _rewrite_links(page.read_bytes().decode("utf-8", errors="replace"), names, out, _rel(root, page))
        if not text.strip() or (w.ref, text) in have | done:
            continue
        done.add((w.ref, text))
        out.overviews += 1
        out.links_rewritten += links
        if not write:
            continue
        # `loom annotate` writes a note on a whole work through `append_new`, and needs a session and a citekey to get there; this is that event, written the same way
        event = {
            "when": clock.stamp(),
            "author": OVERVIEW_AUTHOR,
            "kind": "agent" if is_agent(OVERVIEW_AUTHOR) else "person",
            "event": "created",
            "target": w.ref,
            "anchor": None,
            "type": None,
            "look": {},
            "drawn": drawn_look(None, {}, types.plain),
            "body": text,
        }
        append_new(root, event, clock.today())


def _state(root: Path, result: ScanResult, names: _Names, out: Carried, *, write: bool) -> None:
    """Rewrite the research state's `cited:work:` links as `quilt:` links to their references, through the door as a page is written, and recorded as loom's.

    Where the door refuses, the carry stops with a `WriteRefused` (409) saying so, `STATE_REFUSED` for a link of the state's that names nothing or a byte that is not text, else the door's own code; the state is as it was, being the person's file, which only the door writes.
    """
    from loom.links import LinkError
    from loom.pages import state_page
    from loom.pages import write as write_page
    from loom.writes import WriteRefused

    rel = result.quilt.config.research_state
    path = root / rel
    if not path.is_file():
        return
    text = path.read_bytes().decode("utf-8", errors="surrogateescape")
    new, links = _rewrite_links(text, names, out, rel)
    out.links_rewritten += links
    if not links or not write:
        return
    try:
        write_page(result, state_page(result.quilt.config), new, actor="loom", session=None)
    except (LinkError, UnicodeEncodeError, WriteRefused) as exc:
        why = "it holds bytes that are not text" if isinstance(exc, UnicodeEncodeError) else str(exc)
        code, status = (exc.code, exc.status) if isinstance(exc, WriteRefused) else (STATE_REFUSED, 409)
        raise WriteRefused(
            code,
            f"the carry stopped at {rel}, whose links to works it rewrites, because loom could not write it: {why}. {rel} is as it was, and the old library and the quilt's layout are kept; once {rel} is mended, an upgrade carries the rest, and nothing twice",
            status,
        ) from None


def _rewrite_links(text: str, names: _Names, out: Carried, where: str) -> tuple[str, int]:
    """`text` with each `[](cited:work:<hash>)` that a carried reference answers made `[](quilt:<ref>)`, and how many; a hash none answers, and a page a `quilt:` link cannot say, are said."""
    unknown: list[str] = []
    dropped = 0

    def one(m: re.Match[str]) -> str:
        nonlocal dropped
        ref = names.work("work", m.group(1))
        if ref is None:
            unknown.append(m.group(1))
            return m.group(0)
        dropped += bool(m.group(2))
        return f"quilt:{ref}"

    new, n = _CITED_WORK.subn(one, text)
    if unknown:
        said = ", ".join(f"work:{h}" for h in dict.fromkeys(unknown))
        out.problems.append(f"{where} links to {said}, which no carried reference answers, so those links are left.")
    if dropped:
        out.problems.append(f"{where} linked a place in {_counted(dropped, 'work')}, which a link to a reference cannot say, so the link names the whole work.")  # fmt: skip
    return new, n - len(unknown)


# ---- removing the old library ----------------------------------------------------------------------------------------


def _remove(root: Path, works: Iterable[_Work], out: Carried, *, write: bool) -> None:
    """Remove the old library, digests and all, once everything is carried: the bibliography and the old files beside it, each digest's files, and the store but the folders left in it.

    A folder in the store holding a work's documents that no entry names is left and said, and so is a folder whose entry or documents were not carried; anything under `.loom/library/` that is neither the node store's nor nameable as the old library's is left and said.
    """
    library = root / LIBRARY
    if not library.is_dir():
        return
    store = root / STORAGE
    works = list(works)
    named = {w.folder for w in works if w.folder is not None}
    kept = {w.folder for w in works if w.kept and w.folder is not None and store in w.folder.parents}
    for folder in _work_folders(store):
        if folder not in named:
            out.problems.append(f"{_rel(root, folder)} holds a work's documents and no entry names it, so it is left in place.")  # fmt: skip
            kept.add(folder)
    for child in sorted(library.iterdir()):
        rel = _rel(root, child)
        if rel in KEPT:
            continue
        if rel == STORAGE:
            _clear(root, child, kept, out, write=write)
        elif rel in OLD_FILES or (child.is_file() and child.name.endswith(DIGEST_ENDINGS)):
            _gone(root, child, out, write=write)
        else:
            out.problems.append(f"{rel} is not the old library's, so it is left in place.")


def _work_folders(store: Path) -> list[Path]:
    """Every folder of the old store holding a work's documents or overview, not looking inside one."""
    out: list[Path] = []
    if not store.is_dir():
        return out
    for child in sorted(store.iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        if (child / PAPER).is_file() or (child / SOURCE).is_dir() or (child / OVERVIEW).is_file():
            out.append(child)
        else:
            out += _work_folders(child)
    return out


def _clear(root: Path, folder: Path, kept: set[Path], out: Carried, *, write: bool) -> None:
    """Remove `folder` whole, or with folders of `kept` in it, everything beside them."""
    if not any(folder == k or folder in k.parents for k in kept):
        _gone(root, folder, out, write=write)
        return
    if folder in kept:
        return
    for child in sorted(folder.iterdir()):
        _clear(root, child, kept, out, write=write)


def _gone(root: Path, path: Path, out: Carried, *, write: bool) -> None:
    if write:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    out.removed.append(_rel(root, path))
