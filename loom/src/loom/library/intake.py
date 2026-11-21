"""The one way a work comes into the library (`docs/specs/write-api.md` §6): a file dropped, a file on the command line, or a pasted text, each becoming one row, `added`, `here`, `question` or `cannot`, and an `added` row a reference.

A drop waits in `.loom/local/incoming/<sha256>/` as `document.<suffix>` with `arrived.json` (`{name, size, when, not}`), until it is taken; what each act on it wrote is in its `act.json`, which an undo reads. A drop lets go of its file only once its act is recorded and these very bytes stand in the store with a reference naming them, so a crash never costs the only copy. Every act holds the library's lock and decides against the library as it is then; no lock is held while the network is asked.

Nothing is filed under a work unless the person says it is that work (`for`, an answer) or, for a paper an agent asked to be fetched, the file states that work's identifier. A file is offered as an existing work only by an identifier it states, never by its title or byline (the rulings of 2026-11-21 on `library-views.md` Opens 6 and 18); one stating an identifier the library has asks the one question.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loom.clock import stamp
from loom.library import documents, log
from loom.library.entries import identifiers, matchable, read_entry, short, surnames, title, year
from loom.library.node import SUFFIX, Node, NodeUnreadable, read_node
from loom.library.references import Minter, attach, make
from loom.library.store import NodeRefused, folder, remove_node
from loom.paths import INCOMING, LIBRARY_LOCK
from loom.scan.bib import raw_entries

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

STATES = ("added", "here", "question", "cannot")
#: How much of an upload is read at a time, and what a receive leaves free on the disk beside the file it keeps.
CHUNK = 1 << 20
SPARE = 256 << 20
ACT, QUESTION, ARRIVED = "act.json", "question.json", "arrived.json"
#: The name a drop's file takes, whatever it was dropped as, with the suffix of its kind.
FILE = "document"
#: Each kind of file the intake takes, by the suffix its drop keeps it under.
TAKEN = {".pdf": "pdf", ".bib": "bib", ".tex": "source", ".tar": "source", ".gz": "source", ".zip": "source"}
_ARXIV_NAME = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?![\d])|([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?")


class Reads(Protocol):
    """What an upload streams from: a request's body."""

    def read(self, size: int = -1, /) -> bytes: ...


class IntakeRefused(Exception):
    """A request the intake will not carry out, with the code and status the write API answers."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass
class Item:
    """One thing to take in: a received file by its drop, a file on disk, or a pasted text; and the work it was dropped on (`for`)."""

    drop: str = ""
    path: Path | None = None
    text: str = ""
    work: str = ""
    #: A work of its own, whatever the file states (`loom library add --new`).
    new: bool = False
    #: Filed under `work` on the person's word, whatever the file states (`loom library add --for --force`).
    force: bool = False


@dataclass
class Row:
    """What became of one item, in exactly one of `STATES`."""

    id: str
    item: int
    name: str
    state: str
    ref: str = ""
    short: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    found_by: str = ""
    tex: bool = False
    unconfirmed: bool = False
    under: bool = False
    why: str = ""
    code: str = ""
    question: str = ""
    document: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    act: str = ""

    def to_json(self) -> dict[str, Any]:
        """The row as the write API answers it: the fields of its state and no others."""
        out: dict[str, Any] = {"id": self.id, "item": self.item, "name": self.name, "state": self.state}
        if self.state in ("added", "here"):
            out.update(ref=self.ref, short=self.short, title=self.title, authors=self.authors, year=self.year)
        if self.state == "added":
            out.update(found_by=self.found_by, tex=self.tex, unconfirmed=self.unconfirmed, under=self.under)
            if self.act:
                out["act"] = self.act
        if self.state == "question":
            out.update(question=self.question, document=self.document, candidates=self.candidates)
        if self.state in ("here", "cannot") or self.why:
            out["why"] = self.why
        if self.state == "cannot":
            out["code"] = self.code
        return out


# ---- the drop ---------------------------------------------------------------------------------------------------------


def incoming(root: Path) -> Path:
    """The folder every drop waits in."""
    return root / INCOMING


def drop_dir(root: Path, drop: str) -> Path:
    """One drop's folder; `no-such-intake` (404) for an id that is not one's shape, which is never made into a path."""
    if not re.fullmatch(r"[0-9a-f]{64}", drop):
        raise IntakeRefused("no-such-intake", f"{drop[:24]} names no drop", 404)
    return incoming(root) / drop


def waiting_file(d: Path) -> Path | None:
    """The file a drop holds while it waits, or None once it is taken."""
    found = sorted(p for p in d.glob(f"{FILE}.*") if p.suffix in TAKEN) if d.is_dir() else []
    return found[0] if found else None


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}.tmp")
    try:
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    finally:
        tmp.unlink(missing_ok=True)


def _suffix(name: str, head: bytes) -> str | None:
    """The suffix a received file is kept under, by its first bytes where they say, else by its name; None for a kind the intake does not take."""
    if head.startswith(b"%PDF-"):
        return ".pdf"
    if head.startswith(b"PK\x03\x04"):
        return ".zip"
    if head.startswith(b"\x1f\x8b"):
        return ".gz"
    if len(head) > 262 and head[257:262] == b"ustar":
        return ".tar"
    lower = name.lower()
    return next((s for s in (".bib", ".tex") if lower.endswith(s)), None)


def _drain(stream: Reads, left: int) -> None:
    """Read what a refused upload still sends, so its sender reads the refusal and not a broken connection."""
    while left > 0 and (chunk := stream.read(min(CHUNK, left))):
        left -= len(chunk)


def receive(root: Path, name: str, stream: Reads, length: int) -> dict[str, Any]:
    """Keep a dropped file as it streams in, at any size, in `.loom/local/incoming/<sha256>/`; the same bytes again are the drop already kept.

    Parameters
    ----------
    root : Path
        The quilt.
    name : str
        The name the file was dropped under.
    stream : binary file
        The request's body.
    length : int
        How many bytes the body holds.

    Returns
    -------
    dict
        `{incoming, name, size}`.

    Raises
    ------
    IntakeRefused
        `missing-field` (400) with no name; `not-a-document` (400) for a file that is no PDF, `.bib`, TeX file or archive of a source, an empty one among them; `cut-short` (400) for a body that ended early; `no-space` (507); nothing is kept.
    """
    shown = Path(name).name
    if not name.strip():
        _drain(stream, length)
        raise IntakeRefused("missing-field", "name is required: the file's name, in the query", 400)
    if length <= 0:
        raise IntakeRefused("not-a-document", f"{shown} is empty", 400)
    base = incoming(root)
    base.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(base).free < length + SPARE:
        _drain(stream, length)
        raise IntakeRefused("no-space", f"{shown} needs {length:,} bytes, and the disk has not that much to spare", 507)
    tmp = base / f".{secrets.token_hex(8)}.part"
    h = hashlib.sha256()
    got = 0
    suffix: str | None = None
    try:
        with tmp.open("wb") as fh:
            while got < length:
                chunk = stream.read(min(CHUNK, length - got))
                if not chunk:
                    break
                if got == 0:
                    suffix = _suffix(name, chunk)
                    if suffix is None:
                        _drain(stream, length - len(chunk))
                        raise IntakeRefused(
                            "not-a-document",
                            f"{shown} is no PDF, .bib, TeX file or archive of a TeX source",
                            400,
                        )
                h.update(chunk)
                fh.write(chunk)
                got += len(chunk)
        if got < length or suffix is None:
            raise IntakeRefused("cut-short", f"{shown} arrived cut short: {got} of {length} bytes", 400)
        sha = h.hexdigest()
        d = base / sha
        d.mkdir(exist_ok=True)
        if waiting_file(d) is None:
            os.replace(tmp, d / f"{FILE}{suffix}")
            if not (d / ARRIVED).is_file():
                _write_json(d / ARRIVED, {"name": shown, "size": got, "when": stamp(), "not": []})
    finally:
        tmp.unlink(missing_ok=True)
    return {"incoming": sha, "name": shown, "size": got}


def receive_file(root: Path, path: Path) -> str:
    """Keep a file on disk as a drop, as `receive` keeps an upload, and say its drop; the file itself is never touched."""
    with path.open("rb") as fh:
        return str(receive(root, path.name, fh, path.stat().st_size)["incoming"])


def _acts(d: Path) -> list[dict[str, Any]]:
    data = _read_json(d / ACT)
    return list(data.get("acts", [])) if isinstance(data, dict) else []


def _push(d: Path, act: dict[str, Any]) -> str:
    act = {"id": "x-" + secrets.token_hex(6), "when": stamp(), **act}
    _write_json(d / ACT, {"acts": [*_acts(d), act]})
    return str(act["id"])


def _named(root: Path, digest: str) -> bool:
    """Whether a reference names the document `digest`."""
    return any(digest in (n.pdf, n.tex) for n in _references(root).values())


def _let_go(root: Path, d: Path, digest: str, which: str) -> bool:
    """Remove a drop's file only when these very bytes stand in the store and a reference names them; whether the drop holds no file now."""
    f = waiting_file(d)
    if f is None:
        return True
    if not (documents.held(root, digest, which) and _named(root, digest)):
        return False
    f.unlink(missing_ok=True)
    (d / ARRIVED).unlink(missing_ok=True)
    return True


def _remove_drop(d: Path) -> None:
    """Remove a drop the intake is done with: its records, and its folder unless a file waits in it again."""
    for name in (ACT, QUESTION):
        (d / name).unlink(missing_ok=True)
    if waiting_file(d) is None:
        (d / ARRIVED).unlink(missing_ok=True)
    try:
        d.rmdir()
    except OSError:
        return


@contextmanager
def library_lock(root: Path) -> Iterator[None]:
    """Hold the lock every writer of the library holds, across processes; reentrant within a thread."""
    from loom.locks import locked

    with locked(root / LIBRARY_LOCK):
        yield


# ---- the library as it stands -------------------------------------------------------------------------------------


def _references(root: Path) -> dict[str, Node]:
    out: dict[str, Node] = {}
    nodes = folder(root)
    if not nodes.is_dir():
        return out
    for path in sorted(nodes.glob(f"*-ref{SUFFIX}")):
        try:
            out[path.name.removesuffix(SUFFIX)] = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
    return out


@dataclass
class Library:
    """The references as they stand: by id, by entry key folded to lower case, by each identifier they state as compared, and by the hash of each document they hold."""

    refs: dict[str, Node] = field(default_factory=dict)
    by_key: dict[str, str] = field(default_factory=dict)
    by_id: dict[str, set[str]] = field(default_factory=dict)
    by_doc: dict[str, str] = field(default_factory=dict)

    @classmethod
    def read(cls, root: Path) -> Library:
        lib = cls(_references(root))
        for ref, node in lib.refs.items():
            entry = read_entry(node.body)
            if entry is not None:
                lib.by_key.setdefault(entry.key.lower(), ref)
                for x in identifiers(entry.fields):
                    lib.by_id.setdefault(matchable(x), set()).add(ref)
            for digest in (node.pdf, node.tex):
                if digest:
                    lib.by_doc.setdefault(digest, ref)
        return lib

    def stating(self, ids: list[str]) -> list[str]:
        """The references stating any of `ids`, in id order."""
        return sorted({r for x in ids for r in self.by_id.get(matchable(x), set())})

    def shown(self, ref: str) -> dict[str, Any]:
        """What a row says of a reference: its short name, title, surnames and year."""
        entry = read_entry(self.refs[ref].body) if ref in self.refs else None
        fields = entry.fields if entry else {}
        return {
            "ref": ref,
            "short": short(fields),
            "title": title(fields),
            "authors": surnames(fields),
            "year": year(fields),
        }


# ---- taking in --------------------------------------------------------------------------------------------------------


@dataclass
class _Take:
    root: Path
    by: str
    online: bool
    write: bool
    http: Any
    result: ScanResult | None
    minter: Minter | None = None
    lib: Library = field(default_factory=Library)

    def mint(self) -> Minter:
        if self.minter is None:
            if self.result is None:
                from loom.scan.quilt import load_quilt
                from loom.scan.scan import scan

                self.result = scan(load_quilt(self.root))
            self.minter = Minter.of(self.result)
        return self.minter


def take(
    root: Path,
    items: list[Item],
    *,
    by: str,
    online: bool = False,
    write: bool = True,
    http: Any = None,
    result: ScanResult | None = None,
) -> list[Row]:
    """Take in every item, each as one row (a pasted text as a row a line or an entry), in one of `STATES`.

    Parameters
    ----------
    root : Path
        The quilt.
    items : list of Item
        What to take in.
    by : str
        Who takes it in.
    online : bool, default False
        Whether a look-up may use the network.
    write : bool, default True
        False answers what would be done and writes nothing.
    http : callable, optional
        The look-up's transport; tests give their own.
    result : ScanResult, optional
        The quilt's scan, which new stems are drawn past; made when first needed.

    Returns
    -------
    list of Row
        In the order of `items`.
    """
    t = _Take(root, by, online, write, http, result)
    rows: list[Row] = []
    for n, item in enumerate(items):
        with library_lock(root) if write else nullcontext():
            t.lib = Library.read(root)
            if item.text:
                rows.extend(_take_text(t, n, item.text))
            else:
                fresh = False
                drop = item.drop
                if not drop and item.path is not None:
                    drop = _sha_of(item.path)
                    fresh = not (incoming(root) / drop).is_dir()
                    receive_file(root, item.path)
                rows.extend(_take_drop(t, n, drop, item.work, new=item.new, force=item.force))
                if fresh and not write:
                    # a dry run leaves no drop behind that it made itself
                    shutil.rmtree(incoming(root) / drop, ignore_errors=True)
    return rows


def _sha_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _take_drop(t: _Take, n: int, drop: str, work: str, *, new: bool = False, force: bool = False) -> list[Row]:
    d = drop_dir(t.root, drop)
    f = waiting_file(d)
    arrived = _read_json(d / ARRIVED) or {}
    name = str(arrived.get("name") or (f.name if f else drop[:12]))
    if f is None:
        # a drop taken already, its bytes held under a work: the same file given again is here
        held = t.lib.by_doc.get("sha256:" + drop)
        if held is not None and _acts(d):
            return [
                Row(
                    drop,
                    n,
                    name,
                    "here",
                    **t.lib.shown(held),
                    why=f"loom holds these very bytes as {t.lib.shown(held)['short']}'s",
                )
            ]
        raise IntakeRefused("no-such-incoming", f"nothing waits as {drop[:12]}: drop it again", 404)
    if work and work not in t.lib.refs:
        raise IntakeRefused("no-such-work", f"the library has no work {work}", 404)
    kind = TAKEN[f.suffix]
    if kind == "bib":
        # each entry a row, as a pasted text's; the file's own bytes are the person's, and its entries are kept by the references made of them
        rows = _take_text(t, n, f.read_text(encoding="utf-8", errors="replace"))
        if t.write:
            shutil.rmtree(d, ignore_errors=True)
        return rows
    which = "pdf" if kind == "pdf" else "tex"
    digest = "sha256:" + drop if which == "pdf" else "sha256:" + hashlib.sha256(documents.source_tar(f)).hexdigest()
    if digest in t.lib.by_doc:
        # these very bytes are held already: nothing is written, and the drop goes, since the store keeps them
        held = t.lib.by_doc[digest]
        if t.write and _let_go(t.root, d, digest, which):
            _remove_drop(d)
        return [
            Row(
                drop,
                n,
                name,
                "here",
                **t.lib.shown(held),
                why=f"loom holds these very bytes as {t.lib.shown(held)['short']}'s",
            )
        ]
    stated = _stated(f, name, which)
    others = (
        []
        if new or (work and force)
        else [r for r in t.lib.stating(stated) if r != work and r not in (arrived.get("not") or [])]
    )
    if work and not others:
        return [_file_under(t, n, d, f, name, which, digest, work)]
    if others:
        return [_ask(t, n, d, name, which, stated, [*([work] if work else []), *others])]
    return [_add_new(t, n, d, f, name, which, digest, stated)]


def _stated(f: Path, name: str, which: str) -> list[str]:
    """The identifiers a document states as its own: arXiv's stamp or an identifier set apart on a PDF's first page, and an arXiv number in the name it was dropped under (`2401.01234v2.tar.gz`, as arXiv names one)."""
    out: list[str] = []
    if which == "pdf":
        from loom.refs.ingest import own_identifiers
        from loom.refs.pages import first_pages

        try:
            pages = first_pages(f)
        except Exception:  # noqa: BLE001 -- a PDF poppler cannot read still comes in, stating nothing
            pages = []
        dois, arxivs, stamped = own_identifiers(pages[0] if pages else "")
        out += [f"arxiv:{a}" for a in sorted(stamped or arxivs)] + [f"doi:{x}" for x in sorted(dois)]
    if m := _ARXIV_NAME.search(name):
        out.append(f"arxiv:{(m.group(1) or m.group(3))}{m.group(2) or m.group(4) or ''}")
    return list(dict.fromkeys(out))


def _ask(t: _Take, n: int, d: Path, name: str, which: str, stated: list[str], candidates: list[str]) -> Row:
    """The one question, "is this one of these works?", its candidates those a stated identifier names and the work it was dropped on."""
    qid = "q-" + secrets.token_hex(6)
    shown = [
        {
            **t.lib.shown(c),
            "how": f"it states {', '.join(x for x in stated if c in t.lib.stating([x])) or 'nothing against it'}",
        }
        for c in dict.fromkeys(candidates)
    ]
    document = {"name": name, "kind": which, "identifiers": stated}
    if t.write:
        _write_json(d / QUESTION, {"question": qid, "document": document, "candidates": shown})
    return Row(d.name, n, name, "question", question=qid, document=document, candidates=shown)


def _file_under(t: _Take, n: int, d: Path, f: Path, name: str, which: str, digest: str, ref: str) -> Row:
    """File a document under the work the person named, replacing nothing it holds."""
    node = t.lib.refs[ref]
    if getattr(node, which):
        return Row(
            d.name,
            n,
            name,
            "cannot",
            code="has-document",
            why=f"{t.lib.shown(ref)['short']} holds a {which} already; take it off first",
        )
    act = ""
    if t.write:
        _store(t.root, f, which)
        before = _file_hash(t.root, ref)
        attach(t.root, ref, which, digest, by=t.by, kind="person", source=name)
        act = _push(
            d,
            {
                "kind": "added",
                "attached": {
                    "ref": ref,
                    "which": which,
                    "hash": digest,
                    "before": before,
                    "after": _file_hash(t.root, ref),
                },
            },
        )
        _let_go(t.root, d, digest, which)
    return Row(
        d.name,
        n,
        name,
        "added",
        **t.lib.shown(ref),
        found_by="entry",
        tex=which == "tex" or bool(node.tex),
        under=True,
        act=act,
    )


def _add_new(t: _Take, n: int, d: Path, f: Path, name: str, which: str, digest: str, stated: list[str]) -> Row:
    """A work of its own: its entry looked up by the identifier it states when the network may be used, else what the document says of itself."""
    fields, etype, found_by, looked = _entry_for(t, f, name, which, stated)
    text = _bibtex(etype, _key(t, fields), fields)
    if not t.write:
        return Row(
            d.name,
            n,
            name,
            "added",
            short=short(fields, name),
            title=title(fields),
            authors=surnames(fields),
            year=year(fields),
            found_by=found_by,
            tex=which == "tex",
            unconfirmed=found_by in log.LOOKABLE and not looked,
        )
    _store(t.root, f, which)
    try:
        node = make(
            t.root, text, t.mint(), by=t.by, kind="person", how="drop" if which == "pdf" else "source",
            found_by=found_by, looked_up=looked, source=name,
            pdf=digest if which == "pdf" else None, tex=digest if which == "tex" else None,
        )  # fmt: skip
    except NodeRefused as exc:
        return Row(d.name, n, name, "cannot", code="refused", why=str(exc))
    act = _push(d, {"kind": "added", "made": node.id, "after": _file_hash(t.root, node.id)})
    _let_go(t.root, d, digest, which)
    t.lib = Library.read(t.root)
    return Row(
        d.name,
        n,
        name,
        "added",
        **t.lib.shown(node.id),
        found_by=found_by,
        tex=which == "tex",
        unconfirmed=found_by in log.LOOKABLE and not looked,
        act=act,
    )


def _entry_for(t: _Take, f: Path, name: str, which: str, stated: list[str]) -> tuple[dict[str, str], str, str, bool]:
    """The fields, entry type, `found_by` and whether looked up, of a new work's entry."""
    from loom.refs.lookup import look_up

    found_by = stated[0].partition(":")[0] if stated else "none"
    if stated and t.online:
        found = look_up(stated[0].replace("arxiv:", "arXiv:"), {}, online=True, http=t.http)
        if found.state == "found" and found.entry:
            return dict(found.entry), "article", found_by, True
    fields: dict[str, str] = {}
    if which == "pdf":
        from loom.refs.ingest import filename_title

        named = filename_title(Path(name).stem)
        if named and named != Path(name).stem:
            fields["title"] = named
            found_by = found_by if stated else "title"
    else:
        fields.update(_source_says(f))
        if fields and not stated:
            found_by = "entry"
    for x in stated[:1]:
        scheme, _, value = x.partition(":")
        fields.update({"eprint": value, "archiveprefix": "arXiv"} if scheme == "arxiv" else {scheme: value})
    if not fields.get("title"):
        fields["title"] = Path(name).name
    return fields, "misc" if found_by == "none" else "article", found_by, False


def _source_says(f: Path) -> dict[str, str]:
    """The title and authors a source's main file states, which a source says exactly and is not guessed."""
    files = documents.unpack(f.read_bytes(), f.name)
    mains = [k for k, v in files.items() if k.endswith(".tex") and b"\\documentclass" in v[:100_000]]
    if not mains:
        return {}
    text = files[sorted(mains, key=lambda k: (k.count("/"), k))[0]].decode("utf-8", errors="replace")
    out: dict[str, str] = {}
    for cmd, key in (("title", "title"), ("author", "author")):
        if m := re.search(rf"\\{cmd}\s*(?:\[[^\]]*\])?\s*\{{", text):
            from loom.scan.tokenize import match_group

            end = match_group(text, m.end() - 1)
            if end > 0:
                value = re.sub(r"\s+", " ", text[m.end() : end - 1].replace("\\\\", " and ")).strip()
                out[key] = (
                    " and ".join(a.strip() for a in re.split(r"\s+and\s+|\\and\b", value) if a.strip())
                    if key == "author"
                    else value
                )
    return out


def _key(t: _Take, fields: dict[str, str]) -> str:
    """A key for a new work's entry, as `refs.lookup.key_for` makes one, then lettered on until no reference has it ignoring case (`docs/specs/nodes.md` check 9)."""
    from loom.refs.lookup import key_for

    taken = {read_entry(n.body).key for n in t.lib.refs.values() if read_entry(n.body)}  # type: ignore[union-attr]
    base = key_for(fields, taken) or "work"
    key, letter = base, ord("a")
    while key.lower() in t.lib.by_key:
        key, letter = f"{base}{chr(letter)}", letter + 1
    return key


def _bibtex(etype: str, key: str, fields: dict[str, str]) -> str:
    body = "".join(
        f"  {k} = {{{v}}},\n" for k, v in fields.items() if v and not k.startswith("loom-") and k != "ENTRYTYPE"
    )
    return f"@{etype}{{{key},\n{body}}}\n"


def _store(root: Path, f: Path, which: str) -> str:
    return documents.put_pdf(root, f, link=True) if which == "pdf" else documents.put_source(root, f)


def _file_hash(root: Path, ref: str) -> str | None:
    from loom.library.node import node_hash

    p = folder(root) / f"{ref}{SUFFIX}"
    return node_hash(p.read_bytes()) if p.is_file() else None


# ---- pasted text ------------------------------------------------------------------------------------------------------


def _take_text(t: _Take, n: int, text: str) -> list[Row]:
    """A pasted text as rows: each BibTeX entry it holds, or each line as one identifier."""
    from loom.refs.identity import recognise

    if text.lstrip().startswith("@"):
        entries = raw_entries(text)
        if not entries:
            return [
                Row(
                    _text_id(text),
                    n,
                    text.strip()[:60],
                    "cannot",
                    code="not-recognised",
                    why="this BibTeX names no entry loom can read",
                )
            ]
        return [_take_entry(t, n, entry.strip() + "\n", key) for key, entry in entries.items()]
    rows = [_take_identifier(t, n, line, recognise(line)) for line in (x.strip() for x in text.splitlines()) if line]
    return rows or [Row(_text_id(text), n, "", "cannot", code="not-recognised", why="nothing was pasted")]


def _text_id(text: str) -> str:
    return "t-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


_CANNOT = {"missing": "missing", "unreachable": "unreachable"}


def _take_identifier(t: _Take, n: int, line: str, rec: Any) -> Row:
    from loom.refs.lookup import look_up

    rid = _text_id(line)
    if rec.kind not in ("doi", "arxiv", "zbl"):
        code = "no-service" if rec.kind in ("isbn", "mr") else "not-recognised"
        return Row(rid, n, line, "cannot", code=code, why=look_up(rec, {}, online=False).message)
    stated = [f"{rec.kind}:{rec.value}"]
    if held := t.lib.stating(stated):
        return Row(rid, n, line, "here", **t.lib.shown(held[0]), why=f"{t.lib.shown(held[0])['short']} states {line}")
    if t.online:
        found = look_up(rec, {}, online=True, http=t.http)
        if found.state != "found":
            return Row(rid, n, line, "cannot", code=_CANNOT.get(found.state, "not-recognised"), why=found.message)
        fields, looked = dict(found.entry), True
    else:
        fields = {"eprint": rec.value, "archiveprefix": "arXiv"} if rec.kind == "arxiv" else {rec.kind: rec.value}
        fields["title"] = line
        looked = False
    return _add_entry(
        t, n, rid, line, _bibtex("article" if looked else "misc", _key(t, fields), fields), rec.kind, looked
    )


def _take_entry(t: _Take, n: int, text: str, key: str) -> Row:
    """One pasted entry: `here` when a work has its key and its text or an identifier agrees, or states its identifier; `cannot` (`key-taken`) when a work has its key and is another; else a work of its own."""
    rid = _text_id(text)
    entry = read_entry(text)
    stated = identifiers(entry.fields) if entry else []
    held = t.lib.by_key.get(key.lower())
    if held:
        same = re.sub(r"\s+", "", t.lib.refs[held].body) == re.sub(r"\s+", "", text) or held in t.lib.stating(stated)
        if same:
            return Row(rid, n, key, "here", **t.lib.shown(held), why=f"the library has {key}")
        return Row(
            rid,
            n,
            key,
            "cannot",
            code="key-taken",
            why=f"{t.lib.shown(held)['short']} has the key {key}; change the key in what you paste",
        )
    if stating := t.lib.stating(stated):
        return Row(
            rid,
            n,
            key,
            "here",
            **t.lib.shown(stating[0]),
            why=f"{t.lib.shown(stating[0])['short']} states the same identifier",
        )
    return _add_entry(t, n, rid, key, text, "entry", False)


def _add_entry(t: _Take, n: int, rid: str, name: str, text: str, found_by: str, looked: bool) -> Row:
    entry = read_entry(text)
    fields = entry.fields if entry else {}
    unconfirmed = found_by in log.LOOKABLE and not looked
    if not t.write:
        return Row(
            rid,
            n,
            name,
            "added",
            short=short(fields, name),
            title=title(fields),
            authors=surnames(fields),
            year=year(fields),
            found_by=found_by,
            unconfirmed=unconfirmed,
        )
    try:
        node = make(
            t.root,
            text,
            t.mint(),
            by=t.by,
            kind="person",
            how="paste",
            found_by=found_by,
            looked_up=looked,
            source=name,
        )
    except NodeRefused as exc:
        return Row(rid, n, name, "cannot", code="refused", why=str(exc))
    t.lib = Library.read(t.root)
    return Row(rid, n, name, "added", **t.lib.shown(node.id), found_by=found_by, unconfirmed=unconfirmed)


# ---- the question, undo and unfile --------------------------------------------------------------------------------


def answer(
    root: Path,
    question: str,
    same: str | None,
    *,
    by: str,
    online: bool = False,
    http: Any = None,
    result: ScanResult | None = None,
) -> Row:
    """Settle a drop's one question: `same` the work it is, or None for a work of its own.

    Parameters
    ----------
    root : Path
        The quilt.
    question : str
        The question's id.
    same : str or None
        A candidate's reference id, or None.
    by : str
        Who answers.
    online : bool, default False
        Whether a work of its own may be looked up.
    http : callable, optional
        The look-up's transport.
    result : ScanResult, optional
        The quilt's scan, for a new stem.

    Returns
    -------
    Row
        What became of the drop.

    Raises
    ------
    IntakeRefused
        `no-such-question` (404), `not-a-candidate` (400).
    """
    for d in sorted(incoming(root).glob("*")) if incoming(root).is_dir() else []:
        q = _read_json(d / QUESTION)
        if not (isinstance(q, dict) and q.get("question") == question):
            continue
        refs = [c["ref"] for c in q.get("candidates", [])]
        if same is not None and same not in refs:
            raise IntakeRefused("not-a-candidate", f"{same} is not one of this question's works", 400)
        with library_lock(root):
            (d / QUESTION).unlink(missing_ok=True)
            arrived = _read_json(d / ARRIVED) or {}
            if same is None:
                arrived["not"] = sorted({*arrived.get("not", []), *refs})
                _write_json(d / ARRIVED, arrived)
            t = _Take(root, by, online, True, http, result, lib=Library.read(root))
            return _take_drop(t, 0, d.name, same or "")[0]
    raise IntakeRefused("no-such-question", f"no drop waits on {question}", 404)


def undo(root: Path, drop: str, *, by: str, act: str = "") -> tuple[str, Row | None]:
    """Take back the last act on a drop, touching only what it left, each part checked by its content.

    Parameters
    ----------
    root : Path
        The quilt.
    drop : str
        The drop's id.
    by : str
        Who undoes it.
    act : str, default ''
        The act meant; refused `not-last` when another came after it.

    Returns
    -------
    tuple of (str, Row or None)
        What was done, in words, and the drop's row when it waits again.

    Raises
    ------
    IntakeRefused
        `no-such-intake` (404), `not-last` (409), `not-new` (409) once a node of the work's has been made, `changed` (409) when a file differs from what the act left.
    """
    d = drop_dir(root, drop)
    with library_lock(root):
        acts = _acts(d)
        if not acts:
            if waiting_file(d) is not None:
                shutil.rmtree(d, ignore_errors=True)
                return "the drop was discarded", None
            raise IntakeRefused("no-such-intake", f"{drop[:12]} names no drop", 404)
        last = acts[-1]
        if act and last.get("id") != act:
            raise IntakeRefused("not-last", "another act on this drop came after it, or it is undone already", 409)
        lib = Library.read(root)
        said = _take_back(root, d, last, lib, by)
        rest = acts[:-1]
        if rest:
            _write_json(d / ACT, {"acts": rest})
        else:
            (d / ACT).unlink(missing_ok=True)
        f = waiting_file(d)
        if not rest and f is not None and last.get("kind") != "unfiled":
            shutil.rmtree(d, ignore_errors=True)
            return said, None
        row = (
            Row(
                drop,
                0,
                str((_read_json(d / ARRIVED) or {}).get("name") or drop[:12]),
                "cannot",
                code="received",
                why="it waits to be taken",
            )
            if f
            else None
        )
        return said, row


def _take_back(root: Path, d: Path, last: dict[str, Any], lib: Library, by: str) -> str:
    kind = last.get("kind")
    if kind == "unfiled":
        ref, which, digest = last["ref"], last["which"], last["hash"]
        node = lib.refs.get(ref)
        if node is None or getattr(node, which):
            raise IntakeRefused("changed", f"{ref} is gone or holds a {which} again", 409)
        attach(root, ref, which, digest, by=by, kind="person")
        _let_go(root, d, digest, which)
        return f"its {which} is back on {lib.shown(ref)['short']}"
    if made := last.get("made"):
        if _file_hash(root, made) != last.get("after"):
            raise IntakeRefused("changed", f"{lib.shown(made)['short']} has changed since it was added", 409)
        if _has_nodes(root, made):
            raise IntakeRefused("not-new", f"{lib.shown(made)['short']} has results now; delete the work instead", 409)
        which = "pdf" if lib.refs[made].pdf else "tex"
        digest = getattr(lib.refs[made], which) or ""
        _restore_file(root, d, digest, which)
        remove_node(root, made.removesuffix("-ref") + "-macros")
        remove_node(root, made)
        log.record(root, "undone", made, by=by, kind="person", act=last.get("id"))
        _forget(root, digest)
        return f"{lib.shown(made)['short']} was taken out again"
    attached = last.get("attached") or {}
    ref, which = attached.get("ref", ""), attached.get("which", "pdf")
    if _file_hash(root, ref) != attached.get("after"):
        raise IntakeRefused("changed", f"{lib.shown(ref)['short']} has changed since the document was filed", 409)
    _restore_file(root, d, str(attached.get("hash", "")), which)
    attach(root, ref, which, None, by=by, kind="person")
    _forget(root, str(attached.get("hash", "")))
    return f"the {which} is off {lib.shown(ref)['short']} again"


def _restore_file(root: Path, d: Path, digest: str, which: str) -> None:
    """Give a drop its file back from the store, when it has let it go: a PDF as it was, a source in its one form."""
    if waiting_file(d) is not None or not digest:
        return
    src = documents.path_of(root, digest, which)
    if src.is_file():
        shutil.copyfile(src, d / f"{FILE}{documents.SUFFIX[which]}")


def _forget(root: Path, digest: str) -> None:
    """Remove a stored document no reference names now."""
    if not digest or _named(root, digest):
        return
    for which in ("pdf", "tex"):
        documents.path_of(root, digest, which).unlink(missing_ok=True)


def _has_nodes(root: Path, ref: str) -> bool:
    for path in folder(root).glob(f"*{SUFFIX}") if folder(root).is_dir() else []:
        if f'source = "{ref}"' in path.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def unfile(root: Path, ref: str, *, which: str = "pdf", by: str) -> dict[str, Any]:
    """Take a work's document off it: the work stays with no document of that kind, and the document waits again in a drop with the work in its `not`, which `undo` puts back.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.
    which : str, default 'pdf'
        `pdf` or `tex`.
    by : str
        Who acts.

    Returns
    -------
    dict
        `{incoming, act, row}`.

    Raises
    ------
    IntakeRefused
        `no-such-work` (404), `no-document` (409), `has-results` (409) for a work whose results were read off it.
    """
    with library_lock(root):
        lib = Library.read(root)
        node = lib.refs.get(ref)
        if node is None:
            raise IntakeRefused("no-such-work", f"the library has no work {ref}", 404)
        digest = getattr(node, which)
        if not digest:
            raise IntakeRefused("no-document", f"{lib.shown(ref)['short']} holds no {which}", 409)
        if _has_nodes(root, ref):
            raise IntakeRefused(
                "has-results", f"results were read off {lib.shown(ref)['short']}; delete the work instead", 409
            )
        src = documents.path_of(root, digest, which)
        sha = digest.removeprefix("sha256:") if which == "pdf" else hashlib.sha256(src.read_bytes()).hexdigest()
        d = incoming(root) / sha
        d.mkdir(parents=True, exist_ok=True)
        if waiting_file(d) is None:
            shutil.copyfile(src, d / f"{FILE}{documents.SUFFIX[which]}")
        arrived = _read_json(d / ARRIVED) or {
            "name": f"{lib.shown(ref)['short']}{documents.SUFFIX[which]}",
            "when": stamp(),
        }
        arrived["not"] = sorted({*arrived.get("not", []), ref})
        _write_json(d / ARRIVED, arrived)
        attach(root, ref, which, None, by=by, kind="person")
        act = _push(d, {"kind": "unfiled", "ref": ref, "which": which, "hash": digest})
        row = Row(sha, 0, arrived["name"], "cannot", code="received", why="it waits to be taken")
        return {"incoming": sha, "act": act, "row": row.to_json()}


def waiting(root: Path) -> list[dict[str, Any]]:
    """The drops that wait on the person, as rows: each in state `question`, or `received` for a file not yet taken; what the manifest's `arriving` lists."""
    out: list[dict[str, Any]] = []
    for d in sorted(incoming(root).glob("*")) if incoming(root).is_dir() else []:
        f = waiting_file(d)
        if f is None:
            continue
        arrived = _read_json(d / ARRIVED) or {}
        name = str(arrived.get("name") or f.name)
        q = _read_json(d / QUESTION)
        if isinstance(q, dict):
            out.append(
                Row(
                    d.name,
                    0,
                    name,
                    "question",
                    question=q["question"],
                    document=q["document"],
                    candidates=q["candidates"],
                ).to_json()
            )
        else:
            out.append({"id": d.name, "item": 0, "name": name, "state": "received"})
    return out
