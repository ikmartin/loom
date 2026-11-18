"""The one way a work comes into the library, for `loom library add` and the viewer alike (`docs/specs/write-api.md` §6).

Each thing taken in, a file or a pasted identifier or entry, becomes one row in one of four states: `added`, `here`, `question` or `cannot`. Nothing is filed under an existing work unless the person says it is that work. A drop waits in `.loom/incoming/<id>/`, and once taken its `act.json` holds what each act wrote, which is what makes an undo give back the records' exact bytes.

The library's writes are loom's own records, not a person's files, so they do not go through the door (`docs/design/writes.md`): every act holds the library's lock, writes the store before the entry that names it, and replaces each record file whole. No lock is held while the network is asked, and a receive waits on none, so no slow act of another's can cost a drop its bytes. An undo takes out only what its act left, found by its content, and otherwise refuses and names what is in the way.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

from loom.clock import stamp
from loom.paths import BIBLIOGRAPHY, INCOMING, LIBRARY_LOCK, STORAGE, UNREADABLE
from loom.scan.bib import BibEntry, parse_bib
from loom.scan.quilt import Quilt

#: The four states a row ends in; `received` is a file waiting to be taken, which only `waiting` lists.
STATES = ("added", "here", "question", "cannot")
#: How much of an upload is read at a time.
CHUNK = 1 << 20
#: What a receive leaves free on the disk beside the file it keeps.
SPARE = 256 << 20
#: The record of what each act on a drop wrote, newest last; the question a drop waits on; what it arrived as, with the name it was dropped under.
ACT, QUESTION, ARRIVED = "act.json", "question.json", "arrived.json"
#: The file a drop holds while it waits, under one name whatever it was dropped as, so two receives of the same bytes keep one file.
FILE = "document.pdf"
#: Where an unfiled document's page text waits, inside its drop, until the unfile is undone.
HELD = "held"
#: What reading a document writes into a work's home beside the PDF.
READ_OFF = ("pages", "sections.json")
LEDGER = f"{STORAGE}/copied.json"


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
    """One thing to take in: a file, from `.loom/incoming/` or anywhere on disk, or a pasted text."""

    path: Path | None = None
    name: str = ""
    text: str = ""
    #: A file received into `.loom/incoming/`, by its drop's id: what the viewer takes.
    drop: str = ""
    #: The work it was dropped on (`for`), or the one the person named (`--for`).
    work: str = ""
    #: The person named the work on the command line: it is filed there whatever the document shows.
    on_word: bool = False
    #: The person said it is a work of its own (`--new`).
    new: bool = False
    #: Taken from the command line out of a drop that waited in the viewer, which an undo leaves waiting again.
    over: bool = False


@dataclass
class Row:
    """What became of one item, in exactly one of `STATES`."""

    id: str
    item: int
    name: str
    state: str
    citekey: str = ""
    title: str = ""
    authors: str = ""
    year: str = ""
    why: str = ""
    code: str = ""
    under: str = ""
    sibling: str = ""
    pages: str = ""
    job: dict[str, Any] | None = None
    question: str = ""
    document: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, str]] = field(default_factory=list)
    #: The citekey this work's files were written as, beside `citekey` the work it went under: for the command line's report.
    filed_as: str = ""
    #: For a work of its own, the entry nearest it and why it is not that one: for the command line's report.
    nearest: str = ""
    apart: str = ""
    #: Filed in place of a document the person set aside (`library ignore`), at the work's home.
    replaced: bool = False
    #: The act that added it, which `library-undo` names so that it undoes this act and no later one.
    act: str = ""

    def to_json(self) -> dict[str, Any]:
        """The row as the write API answers it: the fields of its state and no others."""
        out: dict[str, Any] = {"id": self.id, "item": self.item, "name": self.name, "state": self.state}
        if self.state in ("added", "here"):
            out.update(citekey=self.citekey, title=self.title, authors=self.authors, year=self.year)
        if self.state == "added":
            out["pages"] = self.pages
            if self.act:
                out["act"] = self.act
            for k in ("under", "sibling"):
                if getattr(self, k):
                    out[k] = getattr(self, k)
            if self.job is not None:
                out["job"] = self.job
        if self.state == "question":
            out.update(question=self.question, document=self.document, candidates=self.candidates)
        if self.state in ("here", "cannot") or (self.state == "added" and self.why):
            out["why"] = self.why
        if self.state == "cannot":
            out["code"] = self.code
        return out


# ---- the drop -------------------------------------------------------------------------------------------------------


def incoming(root: Path) -> Path:
    """The directory every drop waits in."""
    return root / INCOMING


def drop_dir(root: Path, drop: str) -> Path:
    """One drop's directory; IntakeRefused (`no-such-intake`, 404) for an id that is not one's shape, which is never made into a path."""
    if not re.fullmatch(r"[0-9a-f]{64}|t-[0-9a-f]{16}", drop):
        raise IntakeRefused("no-such-intake", f"{drop[:24]} names no drop", 404)
    return incoming(root) / drop


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    write_whole(p, json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def read_exact(path: Path) -> str:
    """A record file's text as its bytes are, line endings untranslated: what a writer that changes only its own part reads, so a file kept with CRLF stays CRLF."""
    return path.read_bytes().decode("utf-8") if path.is_file() else ""


def write_whole(path: Path, text: str) -> None:
    """Replace `path` with `text` whole, by a temporary file beside it and a rename, so a crash leaves the old bytes or the new."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.loom-tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def waiting_file(d: Path) -> Path | None:
    """The PDF a drop holds while it waits, or None once it is taken."""
    return d / FILE if (d / FILE).is_file() else None


def put_file(src: Path, dst: Path, *, link: bool = False, replace: bool = False) -> None:
    """Give `dst` the bytes of `src`, which stays where it is: with `link` a hard link where the filesystem has them (for a file inside the quilt that loom lets go of next), else a copy. FileExistsError when `dst` exists, unless `replace`."""
    tmp = dst.with_name(f".{dst.name}.{secrets.token_hex(6)}.loom-tmp")
    try:
        try:
            if not link:
                raise OSError("a copy, not a link")
            os.link(src, tmp)
        except OSError:
            shutil.copyfile(src, tmp)
        if replace:
            os.replace(tmp, dst)
            return
        try:
            os.link(tmp, dst)
        except FileExistsError:
            raise
        except OSError:  # a filesystem with no hard links
            if dst.exists():
                raise FileExistsError(dst) from None
            os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def _drain(stream: Reads, left: int) -> None:
    """Read and drop what a refused upload still sends, so that its sender reads the refusal and not a broken connection."""
    while left > 0 and (chunk := stream.read(min(CHUNK, left))):
        left -= len(chunk)


def receive(root: Path, name: str, stream: Reads, length: int) -> dict[str, Any]:
    """Keep a dropped file as it streams in, at any size, in `.loom/incoming/<sha256>/`; the same bytes again are the drop already kept.

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
        `not-a-pdf` (400) for bytes that do not open as a PDF, `cut-short` (400) for a body that ended early; nothing is kept.
    """
    if not name.strip():
        _drain(stream, length)
        raise IntakeRefused("missing-field", "name is required: the file's name, in the query", 400)
    if length <= 0:
        raise IntakeRefused("not-a-pdf", f"{Path(name).name} is empty, which is no PDF", 400)
    base = incoming(root)
    base.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(base).free < length + SPARE:
        _drain(stream, length)
        raise IntakeRefused(
            "no-space", f"{Path(name).name} needs {length:,} bytes, and the disk has not that much to spare", 507
        )
    tmp = base / f".{secrets.token_hex(8)}.part"
    h = hashlib.sha256()
    got = 0
    try:
        with tmp.open("wb") as fh:
            while got < length:
                chunk = stream.read(min(CHUNK, length - got))
                if not chunk:
                    break
                if got == 0 and not chunk.startswith(b"%PDF-"):
                    _drain(stream, length - len(chunk))
                    raise IntakeRefused("not-a-pdf", f"{Path(name).name} is not a PDF", 400)
                h.update(chunk)
                fh.write(chunk)
                got += len(chunk)
            fh.flush()
            os.fsync(fh.fileno())
        if got < length or got == 0:
            raise IntakeRefused("cut-short", f"{Path(name).name} arrived cut short: {got} of {length} bytes", 400)
        sha = h.hexdigest()
        _place(root, base / sha, tmp, {"name": Path(name).name, "size": got, "when": stamp(), "not": []})
    finally:
        tmp.unlink(missing_ok=True)
    return {"incoming": sha, "name": Path(name).name, "size": got}


def _place(root: Path, d: Path, tmp: Path, arrived: dict[str, Any]) -> None:
    """Keep a received file in its drop, waiting on no lock: a drop whose file waits already keeps the one it has.

    An act lets a drop's file go only after recording itself, and only when these very bytes stand in the store (`_let_go`). A file placed beside an act that took these bytes in (a receive racing the act) goes the same way, at once when the library's lock is free, else at the next act on the drop, and waits unlisted until then; one placed while an undo of that act runs stays, and waits.
    """
    from loom.errors import EnvError
    from loom.locks import locked

    for _ in range(5):
        d.mkdir(exist_ok=True)
        try:
            put_file(tmp, d / FILE, link=True)
        except FileExistsError:
            return
        except FileNotFoundError:  # the drop was discarded as it was made: make it again
            continue
        try:
            with (d / ARRIVED).open("x", encoding="utf-8") as fh:
                fh.write(json.dumps(arrived, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
        except (FileExistsError, FileNotFoundError):
            pass
        try:
            with locked(root / LIBRARY_LOCK, wait=0):
                _clear_stale(root, d)
        except EnvError:
            pass
        return
    raise IntakeRefused("failed", "the file's drop was discarded each time it was made: drop it again", 409)


def _taken(d: Path) -> bool:
    """Whether a drop's last act took its bytes in, so a file beside it is a stale copy of bytes the store holds."""
    acts = _acts(d)
    return bool(acts) and acts[-1].get("kind") in ("added", "here")


def _clear_stale(root: Path, d: Path) -> None:
    """Let go of a file a receive placed in a drop whose last act took these bytes in, through `_let_go`, the act recording that they were received again (`received`, what they arrived as), so that its undo gives the file back to wait rather than leave the bytes nowhere. Under the library's lock."""
    if not (d.is_dir() and _taken(d) and waiting_file(d) is not None and _stands(root, d)):
        return
    acts = _acts(d)
    # only where its undo keeps the drop, earlier acts standing or the file a command-line add took over; the undo of a drop's one add discards the drop, these bytes with it
    kept = len(acts) > 1 or bool((acts[-1].get("waiting") or {}).get("over"))
    if acts[-1].get("kind") == "added" and kept and "received" not in acts[-1]:
        acts[-1] = {**acts[-1], "received": _read_json(d / ARRIVED) or {}}
        _write_json(d / ACT, {"acts": acts})
    _let_go(root, d)


def _stands(root: Path, d: Path, also: tuple[Path, ...] = ()) -> bool:
    """Whether a drop's bytes stand in the store at a place an entry names: where the ledger sends them, a place of their own (`file/<sha16>`), a place an act on this drop filed or found them, or one of `also`."""
    from loom.refs.pages import sha256_of, storage_root
    from loom.refs.scan import claimed_places, load_ledger

    sha = d.name
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        return False
    store = storage_root(root)
    rec = load_ledger(root).get(sha) or {}
    places = [*also, store / "file" / sha[:16]]
    if isinstance(rec.get("to"), str) and rec["to"]:
        places.append(store / rec["to"])
    for a in _acts(d):
        home = a.get("home")
        if a.get("kind") in ("added", "here") and isinstance(home, str) and home.startswith(f"{STORAGE}/"):
            places.append(root / home)
    named: set[Path] | None = None
    for place in dict.fromkeys(places):
        paper = place / "paper.pdf"
        if paper.is_file() and sha256_of(paper) == sha:
            named = claimed_places(root, _bib_now(root)) if named is None else named
            if place in named:
                return True
    return False


def _let_go(root: Path, d: Path, also: tuple[Path, ...] = ()) -> bool:
    """Remove a drop's file, and what it arrived as, only when these very bytes stand in the store at a place an entry names (`_stands`); whether the drop holds no file now.

    Every removal of a drop's file but the person's own discard goes through here, so a crash that left the only copy in a drop, whatever the drop's record says, never costs it: the file waits instead.
    """
    if waiting_file(d) is None:
        return True
    if not _stands(root, d, also):
        return False
    (d / FILE).unlink(missing_ok=True)
    (d / ARRIVED).unlink(missing_ok=True)
    return True


def _remove_drop(root: Path, d: Path) -> None:
    """Remove a drop the intake is done with: its records, and the directory unless a receive has placed a file in it meanwhile, which then waits."""
    for name in (ACT, QUESTION):
        (d / name).unlink(missing_ok=True)
    shutil.rmtree(d / HELD, ignore_errors=True)
    if waiting_file(d) is None:
        (d / ARRIVED).unlink(missing_ok=True)
    try:
        d.rmdir()
    except OSError:
        return
    _tidy(incoming(root))


# ---- the lock and the records -----------------------------------------------------------------------------------------


@contextmanager
def library_lock(root: Path) -> Iterator[None]:
    """Hold the lock every writer of the library's bibliography and store holds, across processes; reentrant within a thread."""
    from loom.locks import locked

    with locked(root / LIBRARY_LOCK):
        yield


def _digest(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


@dataclass
class _Before:
    """The record files as an act found them, for the act's record: enough to give their bytes back."""

    bib_size: int
    bib_digest: str | None
    ledger: dict[str, Any]
    ledger_digest: str | None
    events: int
    unreadable_digest: str | None


def _before(root: Path, shas: list[str]) -> _Before:
    from loom.refs.scan import load_ledger
    from loom.refs.unreadable import load_events

    bib = root / BIBLIOGRAPHY
    ledger = load_ledger(root)
    return _Before(
        bib.stat().st_size if bib.is_file() else -1,
        _digest(bib),
        {sha: ledger.get(sha) for sha in shas},
        _digest(root / LEDGER),
        len(load_events(root)) if (root / UNREADABLE).is_file() else -1,
        _digest(root / UNREADABLE),
    )


def _records(root: Path, b: _Before) -> dict[str, Any]:
    """What an act did to the three record files, as its record keeps it: each one's digest before and after, and the parts the act changed, as they were and as it left them."""
    from loom.refs.scan import load_ledger
    from loom.refs.unreadable import load_events

    events = load_events(root) if (root / UNREADABLE).is_file() else []
    ledger = load_ledger(root)
    return {
        "bibliography": {"size": b.bib_size, "before": b.bib_digest, "after": _digest(root / BIBLIOGRAPHY)},
        "ledger": {
            "records": b.ledger,
            "left": {sha: ledger.get(sha) for sha in b.ledger},
            "before": b.ledger_digest,
            "after": _digest(root / LEDGER),
        },
        "unreadable": {
            "events": events[max(b.events, 0) :],
            "count": b.events,
            "before": b.unreadable_digest,
            "after": _digest(root / UNREADABLE),
        },
    }


def _written(root: Path, keys: list[str], since: int) -> dict[str, str]:
    """The exact text of each entry an act appended after byte `since` of the bibliography, its `% from` line and the blank line before it included: what an undo finds it by."""
    from loom.refs.added import _block

    text = (root / BIBLIOGRAPHY).read_bytes()[max(since, 0) :].decode("utf-8")
    out = {}
    for key in keys:
        if (where := _block(text, key)) is not None:
            out[key] = text[where[0] : where[1]]
    return out


def _bib_now(root: Path) -> dict[str, BibEntry]:
    path = root / BIBLIOGRAPHY
    return parse_bib(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _place_of(root: Path, entry: BibEntry) -> Path | None:
    from loom.refs.fetch import FetchRefused, work_dir

    try:
        return work_dir(root, entry)
    except FetchRefused:
        return None


#: What an undo does to the bibliography: leave it, remove it, or write this text.
_Bib = tuple[str, str]


def _unwritten(root: Path, act: dict[str, Any]) -> _Bib:
    """The bibliography with an add's own entries taken out: byte for byte as the act found it while it holds what the act left, else each entry found by the exact text the act wrote. IntakeRefused (`changed`) when an entry is no longer as written, edited or renamed by hand, since taking out what a person wrote is never an undo's."""
    bib = root / BIBLIOGRAPHY
    b = act["records"]["bibliography"]
    if b["after"] == b["before"]:
        return "keep", ""
    if b["after"] is not None and _digest(bib) == b["after"]:
        return ("unlink", "") if b["size"] < 0 else ("write", bib.read_bytes()[: b["size"]].decode("utf-8"))
    text = read_exact(bib)
    for key, block in act["blocks"].items():
        at = text.find(block)
        if at < 0:
            raise IntakeRefused(
                "changed",
                f"the entry this drop wrote for {key} was changed by hand or taken out since, and an undo never takes out what you wrote: delete the work instead",
                409,
            )
        text = text[:at] + text[at + len(block) :]
    return "write", text


def _put_back(root: Path, act: dict[str, Any]) -> _Bib:
    """The bibliography with the entries an unfile took out back in: each at its place while the file holds what the unfile left, else at the end."""
    bib = root / BIBLIOGRAPHY
    removed = act["removed"]
    if not removed:
        return "keep", ""
    text = read_exact(bib)
    exact = _digest(bib) == act["records"]["bibliography"]["after"]
    eol = "\r\n" if "\r\n" in text else "\n"
    for block in removed.values():
        at, body = block.split("\0", 1)
        if exact and int(at) <= len(text):
            text = text[: int(at)] + body + text[int(at) :]
        else:
            text = (text if not text or text.endswith("\n") else text + eol) + body
    return "write", text


def _restore_records(root: Path, rec: dict[str, Any], bib_plan: _Bib) -> None:
    """Give the record files back as an act found them: the bibliography as `bib_plan` says, the ledger's records the act changed where they still hold what it left, and the events it recorded taken out."""
    from loom.refs.scan import load_ledger
    from loom.refs.unreadable import load_events, path_of

    bib = root / BIBLIOGRAPHY
    if bib_plan[0] == "unlink":
        bib.unlink(missing_ok=True)
    elif bib_plan[0] == "write":
        write_whole(bib, bib_plan[1])
    led = rec["ledger"]
    ledger_path = root / LEDGER
    if led["after"] != led["before"]:
        ledger = load_ledger(root)
        left = led.get("left") or {}
        for sha, was in led["records"].items():
            if ledger.get(sha) != left.get(sha):
                continue  # recorded since by another act, whose record it is
            if was is None:
                ledger.pop(sha, None)
            else:
                ledger[sha] = was
        if not ledger and led["before"] is None:
            ledger_path.unlink(missing_ok=True)
        else:
            write_whole(ledger_path, json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    un = rec["unreadable"]
    if un["after"] != un["before"]:
        added = un["events"]
        events = [e for e in load_events(root) if e not in added] if added else load_events(root)
        if not events and un["count"] < 0:
            path_of(root).unlink(missing_ok=True)
        else:
            write_whole(path_of(root), json.dumps({"events": events}, indent=1, ensure_ascii=False) + "\n")


# ---- what a document is -----------------------------------------------------------------------------------------------


def _show(entry: BibEntry | dict[str, str]) -> dict[str, str]:
    """A work's title, authors and year as a row shows them: braces out."""
    fields = entry.fields if isinstance(entry, BibEntry) else entry
    plain = {
        k: re.sub(r"\s+", " ", str(fields.get(k) or "").replace("{", "").replace("}", "")).strip()
        for k in ("title", "author", "year")
    }
    return {"title": plain["title"], "authors": plain["author"], "year": plain["year"]}


def _candidate(bib: dict[str, BibEntry], key: str, how: str) -> dict[str, str]:
    return {"citekey": key, **_show(bib[key]), "how": how}


def _duplicate_how(fields: dict[str, str], other: BibEntry) -> str:
    from loom.refs.identity import arxiv_base, declared

    def norm(w: Any) -> tuple[str, str]:
        return (w.scheme, arxiv_base(w.value) if w.scheme == "arxiv" else w.value.lower())

    mine = {norm(w): w for w in declared(BibEntry("", "misc", dict(fields)))}
    for w in declared(other):
        if norm(w) in mine:
            return f"it states {w}, as {other.key} does"
    return f"its title is {other.key}'s"


def _document(pdf: Path, offer: dict[str, str]) -> dict[str, Any]:
    """What a PDF shows of itself, for a question to set beside the works it may be: its title, its byline, its own identifiers."""
    from loom.refs.ingest import own_identifiers
    from loom.refs.pages import first_pages

    try:
        page = next(iter(first_pages(pdf, 1)), "")
    except Exception:  # noqa: BLE001 -- a scan shows nothing, and the question still stands
        page = ""
    dois, arxivs, stamped = own_identifiers(page)
    lines = [" ".join(x.split()) for x in page.splitlines() if x.strip()]
    title = offer.get("title", "")
    byline = ""
    for i, line in enumerate(lines[:20]):
        if title and line and line.lower() in title.lower() and i + 1 < len(lines):
            byline = lines[i + 1]
    ids = [f"doi:{d}" for d in sorted(dois)] + [f"arXiv:{a}" for a in sorted(arxivs | stamped)]
    return {"title": title, "byline": byline or offer.get("author", ""), "identifiers": ids}


# ---- taking in ----------------------------------------------------------------------------------------------------------


@dataclass
class _Take:
    """One call's state: the quilt, the library as it grows, and how to read a document's pages."""

    quilt: Quilt
    bib: dict[str, BibEntry]
    by: str
    online: bool
    write: bool
    runner: Callable[[str, bool], dict[str, Any] | None] | None
    fetch: bool
    http: Any
    #: The bytes this call has taken already, by hash, and the row each became.
    made: dict[str, Row] = field(default_factory=dict)
    planned: set[Path] = field(default_factory=set)

    @property
    def root(self) -> Path:
        return self.quilt.root


def take(
    quilt: Quilt,
    bib: dict[str, BibEntry],
    items: list[Item],
    *,
    by: str,
    online: bool = False,
    write: bool = True,
    fetch: bool = False,
    runner: Callable[[str, bool], dict[str, Any] | None] | None = None,
    http: Any = None,
) -> list[Row]:
    """Take in every item, each as one row (a pasted text as a row a line or an entry), in one of `STATES`.

    Parameters
    ----------
    quilt : Quilt
        The quilt.
    bib : dict of str to BibEntry
        The library's entries as the last scan read them.
    items : list of Item
        What to take in.
    by : str
        Who takes it in.
    online : bool, default False
        Whether a lookup may use the network: the quilt's answer, or `--online` for one run.
    write : bool, default True
        False answers what would be done and writes nothing (`--dry-run`).
    fetch : bool, default False
        Ask the runner to fetch each work added, beside reading its pages.
    runner : callable, optional
        `(citekey, fetch) -> job` queues a library run on a work; with none, its pages are read at once.
    http : callable, optional
        The lookup's transport; tests inject their own.

    Returns
    -------
    list of Row
        In the order of `items`.
    """
    t = _Take(quilt, dict(bib), by, online, write, runner, fetch, http)
    rows: list[Row] = []
    for n, item in enumerate(items):
        if online and write:
            # every lookup is asked first, holding no lock, and heard again once the lock is held
            heard = _Heard(http)
            dry = replace(t, write=False, bib=dict(t.bib), made=dict(t.made), planned=set(t.planned), http=heard.ask)
            with suppress(Exception):
                _fresh(dry)
                _decide(dry, n, item)
            t.http = heard.again
        # each item is decided and written under the library's lock, against the library as it is then: what another process added since the scan is in it, and the same bytes it filed meanwhile are already here
        with library_lock(t.root) if write else _nothing():
            _fresh(t)
            rows.extend(_decide(t, n, item))
        t.http = http
    return rows


def _decide(t: _Take, n: int, item: Item) -> list[Row]:
    if item.drop:
        return [_take_drop(t, n, item)]
    if item.path is not None:
        return [_take_file(t, n, item)]
    return _take_text(t, n, item.text)


class _Heard:
    """A lookup's transport that asks the network once, holding no lock, then gives the same answers again once the library's lock is held: a slow or silent service holds up no other writer."""

    def __init__(self, http: Any) -> None:
        self.http = http
        self.heard: dict[str, bytes | Exception] = {}

    def ask(self, url: str, headers: dict[str, str]) -> bytes:
        from loom.refs import resolve

        try:
            got = (self.http or resolve.http_get)(url, headers)
        except Exception as exc:
            self.heard[url] = exc
            raise
        self.heard[url] = got
        return bytes(got)

    def again(self, url: str, headers: dict[str, str]) -> bytes:
        from loom.refs.resolve import ResolveRefused

        got = self.heard.get(url)
        if got is None:
            raise ResolveRefused(f"{url.split('?')[0]}: not asked before the library was locked")
        if isinstance(got, Exception):
            raise got
        return got


def _fresh(t: _Take) -> None:
    """Decide on the bibliography as it is now: under the lock, its entries and no others, so a work deleted since the caller's scan is gone and one another process added is there; a dry run keeps what it has decided so far beside them."""
    now = _bib_now(t.root)
    if t.write:
        t.bib = now
    else:
        for key, entry in now.items():
            t.bib.setdefault(key, entry)


def _take_drop(t: _Take, n: int, item: Item) -> Row:
    """A received file, by its drop: the file that waits there, or, the same bytes having been taken in already, the work they went to."""
    d = drop_dir(t.root, item.drop)
    pdf = waiting_file(d) if d.is_dir() else None
    if d.is_dir() and _taken(d) and t.write:
        _clear_stale(t.root, d)
        pdf = waiting_file(d)
    if d.is_dir() and _taken(d) and (pdf is None or (not t.write and _stands(t.root, d))):
        key = str(_acts(d)[-1]["citekey"])
        return Row(item.drop, n, item.name, "here", key, *_shown(t, key), why=f"these very bytes are {key}'s")
    # a file beside an act whose bytes the store does not hold is the only copy, as a crash leaves it: it is taken
    if pdf is not None:
        arrived = _read_json(d / ARRIVED) or {}
        return _take_file(
            t, n, Item(path=pdf, name=item.name or str(arrived.get("name") or pdf.name), work=item.work, new=item.new)
        )
    raise IntakeRefused("no-such-incoming", f"nothing waits as {item.drop[:16]}: receive the file first", 404)


def _take_file(t: _Take, n: int, item: Item) -> Row:
    from loom.refs.add import identify
    from loom.refs.pages import sha256_of
    from loom.refs.scan import held_under

    assert item.path is not None
    pdf = item.path
    name = item.name or pdf.name
    try:
        with pdf.open("rb") as fh:
            is_pdf = fh.read(5) == b"%PDF-"
    except OSError:
        is_pdf = False
    if not is_pdf:
        return Row("", n, name, "cannot", code="not-a-pdf", why=f"{name} is not a PDF")
    sha = sha256_of(pdf)
    if sha in t.made:
        first = t.made[sha]
        return Row(
            sha,
            n,
            name,
            "here",
            first.filed_as or first.citekey,
            *_shown(t, first.citekey),
            why=f"these very bytes came in as {first.name}",
        )
    if holder := held_under(t.root, t.bib, sha):
        return _here(t, sha, n, name, holder, f"these very bytes are {holder}'s")
    d = incoming(t.root) / sha
    waiting_now = waiting_file(d) if t.write and d.is_dir() else None
    if waiting_now is not None and item.path != waiting_now:
        # the same bytes wait in a drop of the viewer's: this take is that drop's, so its record and its file stay one
        item = Item(path=waiting_now, name=item.name, work=item.work, on_word=item.on_word, new=item.new, over=True)
        pdf = waiting_now
    arrived = _read_json(d / ARRIVED) or {}
    excluded = set(arrived.get("not") or [])
    if item.new:
        seen = identify(t.root, t.bib, pdf, online=t.online, http=t.http, name=item.name)
        return _add_new(t, n, item, sha, seen.offer)
    if item.work:
        return _take_for(t, n, item, sha, excluded)
    seen = identify(t.root, t.bib, pdf, online=t.online, http=t.http, name=item.name)
    candidates = [_candidate(t.bib, m["citekey"], str(m["how"])) for m in seen.matches if m["citekey"] not in excluded]
    named = {c["citekey"] for c in candidates}
    for key in seen.duplicates:
        if key not in named and key not in excluded and key in t.bib:
            candidates.append(_candidate(t.bib, key, _duplicate_how(seen.offer, t.bib[key])))
            named.add(key)
    if candidates:
        return _ask(t, n, item, sha, candidates, seen.offer)
    row = _add_new(t, n, item, sha, seen.offer)
    row.nearest, row.apart = seen.nearest, seen.weak
    return row


def _shown(t: _Take, key: str) -> tuple[str, str, str]:
    s = _show(t.bib[key]) if key in t.bib else {"title": "", "authors": "", "year": ""}
    return s["title"], s["authors"], s["year"]


def _here(t: _Take, rid: str, n: int, name: str, key: str, why: str) -> Row:
    """A row for something the library holds already, these very bytes or (for a pasted text) a work stating it: a waiting drop of it goes, since nothing is left to take. One an earlier act stands on keeps its record: its file goes under an act of its own, which an undo gives back."""
    if t.write and rid and re.fullmatch(r"[0-9a-f]{64}|t-[0-9a-f]{16}", rid):
        d = incoming(t.root) / rid
        home = _place_of(t.root, t.bib[key]) if key in t.bib else None
        also = (home,) if home is not None else ()
        if d.is_dir() and not (d / ACT).is_file():
            if _let_go(t.root, d, also):
                _remove_drop(t.root, d)
        elif d.is_dir():
            if waiting_file(d) is not None and home is not None and _stands(t.root, d, also):
                _push(
                    d,
                    {
                        "kind": "here",
                        "citekey": key,
                        "home": _rel(t.root, home),
                        "name": FILE,
                        "sha": rid,
                        "arrived": _read_json(d / ARRIVED),
                        "when": stamp(),
                        "by": t.by,
                    },
                )
                _let_go(t.root, d, also)
            (d / QUESTION).unlink(missing_ok=True)
    return Row(rid, n, name, "here", key, *_shown(t, key), why=why)


def _take_for(t: _Take, n: int, item: Item, sha: str, excluded: set[str]) -> Row:
    """A PDF dropped on a work, or named for it: filed there unless it shows it is another work, which makes a question; the command line's `--for` files it on the person's word."""
    from loom.refs.add import named_for, own_entry
    from loom.refs.ingest import identify_document

    assert item.path is not None
    if item.work not in t.bib:
        raise IntakeRefused("no-such-work", f"the library has no work {item.work}", 404)
    identity = identify_document(item.path, t.bib, item.name)
    if item.on_word:
        key, why = named_for(identity, t.bib, item.work)
        return _file_under(t, n, item, sha, key, note=why)
    others = [m for m in identity.strong if m.citekey != item.work and m.citekey not in excluded]
    if others and item.work not in {m.citekey for m in identity.strong}:
        candidates = [_candidate(t.bib, item.work, "it was dropped on this work")]
        candidates += [_candidate(t.bib, m.citekey, m.how) for m in others]
        return _ask(t, n, item, sha, candidates, own_entry(item.path, item.name))
    key, _why = named_for(identity, t.bib, item.work)
    return _file_under(t, n, item, sha, key)


def _ask(t: _Take, n: int, item: Item, sha: str, candidates: list[dict[str, str]], offer: dict[str, str]) -> Row:
    """One question: is this one of these works? Nothing is written but the question beside the drop, and only for a drop that waits in `.loom/incoming/`."""
    assert item.path is not None
    document = _document(item.path, offer)
    row = Row(sha, n, item.name or item.path.name, "question", question=sha, document=document, candidates=candidates)
    d = incoming(t.root) / sha
    if t.write and item.path.parent == d:
        _write_json(
            d / QUESTION,
            {"kind": "file", "candidates": candidates, "document": document, "offer": offer, "when": stamp()},
        )
    return row


def _drop_of(t: _Take, item: Item, sha: str) -> tuple[Path, bool]:
    """The drop a file is taken from, and whether the file waits there (else it is on disk elsewhere, from the command line)."""
    d = incoming(t.root) / sha
    return d, item.path is not None and item.path.parent == d


def _held_before(d: Path, item: Item, waits: bool) -> dict[str, Any]:
    """What a drop held before an act took its file: the file's name and what it arrived as, which an undo puts back where earlier acts stand or the file was the viewer's drop taken from the command line (`over`). A question it waited on is not kept: taking the file again asks it again."""
    return {
        "file": FILE if waits else None,
        "arrived": _read_json(d / ARRIVED),
        "over": item.over,
    }


def _home_names(home: Path) -> list[str] | None:
    return sorted(os.listdir(home)) if home.is_dir() else None


def _read_pages(t: _Take, key: str, f: Any) -> tuple[str, dict[str, Any] | None, str]:
    """(pages, job, why) for a filed PDF: the run that reads them, or what reading them at once found."""
    if t.runner is not None:
        return "reading", t.runner(key, t.fetch), ""
    if f.unmapped:
        return "none", None, f.unmapped
    return "read", None, ""


def _add_new(t: _Take, n: int, item: Item, sha: str, offer: dict[str, str]) -> Row:
    """Keep the PDF as a work of its own, its entry the one it makes of itself; the store is written before the entry that names it."""
    from loom.refs.add import plan_new_work, withdraw_setting_aside
    from loom.refs.added import added_entry
    from loom.refs.lookup import key_for
    from loom.refs.scan import append_entries, file_document

    assert item.path is not None
    name = item.name or item.path.name
    offer = _not_anothers(offer, t.bib)
    with library_lock(t.root) if t.write else _nothing():
        taken = set(t.bib) | (
            set(parse_bib((t.root / BIBLIOGRAPHY).read_text(encoding="utf-8")))
            if (t.root / BIBLIOGRAPHY).is_file()
            else set()
        )
        key = key_for(offer, taken, sha=sha)
        f = plan_new_work(t.root, t.bib, item.path, key, offer, name, t.planned)
        assert f.home is not None and f.new is not None
        t.bib[key] = BibEntry(key, "misc", dict(f.new))
        row = Row(sha, n, name, "added", key, *_shown(t, key), filed_as=key)
        t.made[sha] = row
        if not t.write:
            return row
        d, waits = _drop_of(t, item, sha)
        held = _held_before(d, item, waits)
        before = _before(t.root, [sha])
        names = _home_names(f.home)
        withdraw_setting_aside(t.root, sha, t.by)
        file_document(t.quilt, f, by=t.by, read_pages=t.runner is None, link=waits)
        append_entries(t.quilt, [added_entry(key, f.new, t.by, source=f"{name}, added by hand")])
        row.act = _push(
            d,
            {
                "kind": "added",
                "citekey": key,
                "entries": [key],
                "blocks": _written(t.root, [key], before.bib_size),
                "home": _rel(t.root, f.home),
                "names": names,
                "name": name,
                "sha": sha,
                "waiting": held,
                "records": _records(t.root, before),
                "when": stamp(),
                "by": t.by,
            },
        )
        if waits:
            _let_go(t.root, d)
        _settled(d)
    row.pages, row.job, row.why = _read_pages(t, key, f)
    return row


#: The fields of an entry that state an identifier.
_IDENTIFIERS = ("doi", "eprint", "archiveprefix", "eprinttype", "mrnumber", "zbl", "zblnumber", "url")


def _not_anothers(offer: dict[str, str], bib: dict[str, BibEntry]) -> dict[str, str]:
    """The entry a work of its own is written with: never stating an identifier another work in the library states, since one identifier names one work, and a PDF said not to be that work only cited it."""
    from loom.refs.identity import arxiv_base, declared

    def norm(w: Any) -> tuple[str, str]:
        return (w.scheme, arxiv_base(w.value) if w.scheme == "arxiv" else w.value.lower())

    mine = {norm(w) for w in declared(BibEntry("", "misc", dict(offer)))}
    if not mine & {norm(w) for e in bib.values() for w in declared(e)}:
        return offer
    return {k: v for k, v in offer.items() if k not in _IDENTIFIERS}


def _file_under(t: _Take, n: int, item: Item, sha: str, key: str, note: str = "") -> Row:
    """File a PDF under the work `key` the person said it is: at the work's place when it holds none, else beside its first document as a version, however like that document it looks; only these very bytes, held already, answer `here`."""
    from loom.refs.add import withdraw_setting_aside
    from loom.refs.scan import Filing, append_entries, file_document, plan_filing

    assert item.path is not None
    name = item.name or item.path.name
    with library_lock(t.root) if t.write else _nothing():
        f = Filing(item.path, key, "pdf", sha, name, forced=note, named=True)
        taken = set(t.bib)
        sibling = plan_filing(t.quilt, t.bib, f, taken, {}, t.planned)
        if f.already:
            return _here(t, sha, n, name, f.holder or key, f.already)
        assert f.home is not None
        filed_as = sibling.key if sibling is not None else key
        if sibling is not None:
            t.bib[sibling.key] = BibEntry(sibling.key, "misc", {})
        row = Row(
            sha, n, name, "added", key, *_shown(t, key), under=key, sibling=f.sibling, why=note, filed_as=filed_as
        )
        row.replaced = bool(f.replaces)
        t.made[sha] = row
        if not t.write:
            return row
        d, waits = _drop_of(t, item, sha)
        held = _held_before(d, item, waits)
        before = _before(t.root, [sha])
        names = _home_names(f.home)
        withdraw_setting_aside(t.root, sha, t.by)
        file_document(t.quilt, f, by=t.by, read_pages=t.runner is None, link=waits)
        append_entries(t.quilt, [sibling] if sibling is not None else [])
        entries = [sibling.key] if sibling is not None else []
        row.act = _push(
            d,
            {
                "kind": "added",
                "citekey": filed_as,
                "entries": entries,
                "blocks": _written(t.root, entries, before.bib_size),
                "home": _rel(t.root, f.home),
                "names": names,
                "name": name,
                "sha": sha,
                "waiting": held,
                "records": _records(t.root, before),
                "when": stamp(),
                "by": t.by,
            },
        )
        if waits:
            _let_go(t.root, d)
        _settled(d)
    row.pages, row.job, row.why = _read_pages(t, filed_as, f)
    if note:
        row.why = note
    return row


def _take_text(t: _Take, n: int, text: str) -> list[Row]:
    """A pasted text as rows: each BibTeX entry it holds, or each line as one identifier."""
    from loom.refs.identity import recognise

    rows: list[Row] = []
    if text.lstrip().startswith("@"):
        entries = list(parse_bib(text).values())
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
        for e in entries:
            fields = {k: v for k, v in e.fields.items() if not k.startswith("loom-") and v}
            rows.append(
                _take_entry(t, n, _text_id(e.key + json.dumps(fields, sort_keys=True)), e.key, fields, e.key, e.type)
            )
        return rows
    for line in (x.strip() for x in text.splitlines()):
        if not line:
            continue
        rows.append(_take_identifier(t, n, line, recognise(line)))
    return rows or [Row(_text_id(text), n, "", "cannot", code="not-recognised", why="nothing was pasted")]


def _text_id(text: str) -> str:
    return "t-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


#: A lookup's state, as the code of the row it cannot add.
_CANNOT = {"offline": "offline", "missing": "missing", "unreachable": "unreachable"}


def _take_identifier(t: _Take, n: int, line: str, rec: Any) -> Row:
    from loom.refs.lookup import look_up

    rid = _text_id(line)
    found = look_up(rec, t.bib, online=t.online, http=t.http)
    if found.state != "found":
        code = _CANNOT.get(found.state) or ("no-service" if found.kind in ("isbn", "mr") else "not-recognised")
        return Row(rid, n, line, "cannot", code=code, why=found.message)
    return _take_entry(t, n, rid, line, dict(found.entry), "", "")


def _take_entry(t: _Take, n: int, rid: str, name: str, fields: dict[str, str], wanted: str, etype: str) -> Row:
    """One work named by an entry: here when a work states its identifier, a question when one shares its title and year, else added under the person's key or loom's."""
    from loom.refs.identity import declared
    from loom.refs.lookup import duplicates

    if not fields.get("title"):
        return Row(
            rid,
            n,
            name,
            "cannot",
            code="not-recognised",
            why="the entry has no title, so the library could not show it",
        )
    same = duplicates(fields, None, t.bib)
    mine = {str(w).lower() for w in declared(BibEntry("", "misc", dict(fields)))}
    for key in same:
        if mine & {str(w).lower() for w in declared(t.bib[key])}:
            return _here(t, rid, n, name, key, f"{key} states {', '.join(sorted(mine))}")
    if same:
        candidates = [_candidate(t.bib, k, _duplicate_how(fields, t.bib[k])) for k in same]
        if t.write:
            _write_json(
                incoming(t.root) / rid / QUESTION,
                {
                    "kind": "text",
                    "candidates": candidates,
                    "fields": fields,
                    "wanted": wanted,
                    "type": etype,
                    "name": name,
                    "when": stamp(),
                },
            )
        return Row(
            rid,
            n,
            name,
            "question",
            question=rid,
            document={"title": _show(fields)["title"], "byline": _show(fields)["authors"], "identifiers": sorted(mine)},
            candidates=candidates,
        )
    return _add_entry(t, n, rid, name, fields, wanted, etype)


def _add_entry(t: _Take, n: int, rid: str, name: str, fields: dict[str, str], wanted: str, etype: str) -> Row:
    """Add a pasted work under the person's key or loom's; `here` when a work in the library is the same work to loom, stating its identifier or, neither stating one, its authors, title and year, since two entries of one identity are one work shown twice."""
    from loom.refs.added import added_entry
    from loom.refs.identity import primary
    from loom.refs.lookup import key_for
    from loom.refs.scan import append_entries

    with library_lock(t.root) if t.write else _nothing():
        mine = primary(BibEntry("", etype or "misc", dict(fields)))
        for other, entry in t.bib.items():
            theirs = primary(entry) if not entry.fields.get("loom-copy-of") else None
            if (
                mine is not None
                and theirs is not None
                and (theirs.scheme, theirs.value.lower()) == (mine.scheme, mine.value.lower())
            ):
                said = "its authors, title and year, and no identifier" if mine.scheme == "work" else str(mine)
                return _here(t, rid, n, name, other, f"{other} is this work to loom: it has {said}")
        taken = set(t.bib) | (
            set(parse_bib((t.root / BIBLIOGRAPHY).read_text(encoding="utf-8")))
            if (t.root / BIBLIOGRAPHY).is_file()
            else set()
        )
        key = key_for(fields, taken, wanted)
        t.bib[key] = BibEntry(key, etype or "misc", dict(fields))
        row = Row(rid, n, name, "added", key, *_shown(t, key), filed_as=key, pages="none")
        if not t.write:
            return row
        d = incoming(t.root) / rid
        before = _before(t.root, [])
        append_entries(t.quilt, [added_entry(key, fields, t.by, etype)])
        (d / QUESTION).unlink(missing_ok=True)
        row.act = _push(
            d,
            {
                "kind": "added",
                "citekey": key,
                "entries": [key],
                "blocks": _written(t.root, [key], before.bib_size),
                "home": "",
                "names": None,
                "name": name,
                "records": _records(t.root, before),
                "when": stamp(),
                "by": t.by,
            },
        )
    if t.runner is not None and t.fetch:
        row.job = t.runner(key, True)
    return row


@contextmanager
def _nothing() -> Iterator[None]:
    yield


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _acts(d: Path) -> list[dict[str, Any]]:
    data = _read_json(d / ACT)
    return list(data.get("acts") or []) if isinstance(data, dict) else []


def _push(d: Path, act: dict[str, Any]) -> str:
    """Record an act on a drop, newest last, under an id of its own, which an undo may name so that it undoes that act and no other; the id."""
    act = {"act": secrets.token_hex(4), **act}
    _write_json(d / ACT, {"acts": [*_acts(d), act]})
    return str(act["act"])


def _settled(d: Path) -> None:
    """A drop that is taken waits no longer: its question goes, and what it arrived as."""
    (d / QUESTION).unlink(missing_ok=True)
    (d / ARRIVED).unlink(missing_ok=True)


def _tidy(d: Path) -> None:
    """Remove `d` and each parent up to the quilt's `.loom/` while it is empty."""
    while d.name and d.name != ".loom" and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


# ---- answering ----------------------------------------------------------------------------------------------------------


def answer(
    quilt: Quilt,
    bib: dict[str, BibEntry],
    question: str,
    same: str | None,
    *,
    by: str,
    online: bool = False,
    runner: Callable[[str, bool], dict[str, Any] | None] | None = None,
    http: Any = None,
) -> Row:
    """Settle the one question a drop waits on: `same` names the work it is, or None for a work of its own.

    Raises
    ------
    IntakeRefused
        `no-such-question` (404) for a drop that waits on none; `not-a-candidate` (400) for a work the question did not name.
    """
    if online:
        # a lookup is asked first, holding no lock, and heard again once the lock is held
        heard = _Heard(http)
        with suppress(Exception):
            _answer(quilt, bib, question, same, by=by, online=online, runner=runner, http=heard.ask, write=False)
        http = heard.again
    with library_lock(quilt.root):
        return _answer(quilt, bib, question, same, by=by, online=online, runner=runner, http=http)


def _answer(
    quilt: Quilt,
    bib: dict[str, BibEntry],
    question: str,
    same: str | None,
    *,
    by: str,
    online: bool,
    runner: Callable[[str, bool], dict[str, Any] | None] | None,
    http: Any,
    write: bool = True,
) -> Row:
    d = drop_dir(quilt.root, question)
    asked = _read_json(d / QUESTION)
    if not isinstance(asked, dict):
        raise IntakeRefused("no-such-question", f"no question waits as {question[:16]}", 404)
    keys = [c["citekey"] for c in asked.get("candidates") or []]
    if same is not None and same not in keys:
        raise IntakeRefused("not-a-candidate", f"{same} is not one of the works asked about: {', '.join(keys)}", 400)
    t = _Take(quilt, dict(bib), by, online, write, runner, False, http)
    _fresh(t)
    if same is not None and same not in t.bib:
        raise IntakeRefused("no-such-work", f"the library has no work {same} now", 404)
    if asked.get("kind") == "text":
        name = str(asked.get("name") or "")
        if same is not None:
            return _here(t, question, 0, name, same, f"you said it is {same}")
        return _add_entry(
            t,
            0,
            question,
            name,
            dict(asked.get("fields") or {}),
            str(asked.get("wanted") or ""),
            str(asked.get("type") or ""),
        )
    pdf = waiting_file(d)
    if pdf is None:
        raise IntakeRefused("no-such-question", f"the file {question[:16]} was dropped as is no longer there", 404)
    arrived = _read_json(d / ARRIVED) or {}
    item = Item(path=pdf, name=str(arrived.get("name") or pdf.name))
    sha = question
    if same is None:
        from loom.refs.add import Seen, _offer

        seen = Seen()
        _offer(seen, t.bib, pdf, online=online, http=http, name=item.name)
        return _add_new(t, 0, item, sha, seen.offer or dict(asked.get("offer") or {}))
    from loom.refs.add import named_for
    from loom.refs.ingest import identify_document

    key, _why = named_for(identify_document(pdf, t.bib, item.name), t.bib, same)
    return _file_under(t, 0, item, sha, key)


# ---- undo and unfile ----------------------------------------------------------------------------------------------------


def _not_new(result: Any, keys: list[str]) -> str:
    """Why a work can no longer be taken out by an undo, or '': it has results, is cited, or carries annotations."""
    from loom.records.annotations import load_records
    from loom.refs.build import cited_counts
    from loom.refs.identity import identify
    from loom.refs.proposals import load_results

    root = result.quilt.root
    cited = cited_counts(result)
    records, _ = load_records(root)
    targets = {a.target_key for r in records for a in r.annotations}
    for key in keys:
        if load_results(root, key):
            return f"{key} has results read off it"
        if cited.get(key):
            return f"{key} is cited by your documents"
        names = {key} | ({str(w) for w in identify(result.bib[key])} if key in result.bib else set())
        if names & targets:
            return f"{key} carries annotations"
    return ""


def _read_off(root: Path, key: str) -> str:
    from loom.refs.proposals import load_results

    return f"{key} has results read off it" if load_results(root, key) else ""


def undo(result: Any, drop: str, *, by: str, act: str = "") -> tuple[str, Row | None]:
    """Reverse the last act on a drop: an add (the work, or the document filed under one, and every record it wrote), an unfile (the document goes back under its work), a drop let go because these very bytes were held (it waits again), or a drop still waiting (it is discarded).

    An undo takes out only what its act left, each part checked by its content: an entry is found by the exact text the act wrote, and a place in the store by the bytes it holds. Anything else in the way, an entry edited, renamed or taken since, a document filed under a pasted work, another entry naming the place, refuses the undo and is named.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan, for whether the work is still new.
    drop : str
        The drop's id, a row's `id`.
    by : str
        Who undoes it.
    act : str, default ''
        The act the person means, a row's `act`: refused (`not-last`) when another act is the last, so that a second click undoes nothing more.

    Returns
    -------
    tuple of (str, Row or None)
        What was done in words, and the row the drop is now when it waits again.

    Raises
    ------
    IntakeRefused
        `no-such-intake` (404); `not-last` (409); `not-new` (409) once the work has results, citations or annotations; `changed` (409) when the bibliography or the store holds something the act did not leave there, which an undo never writes over or removes; `untrusted` (409) for a record of an act loom could not have written.
    """
    root = result.quilt.root
    d = drop_dir(root, drop)
    with library_lock(root):
        if not d.is_dir():
            raise IntakeRefused("no-such-intake", f"nothing was dropped as {drop[:16]}", 404)
        acts = _acts(d)
        if not acts:
            shutil.rmtree(d)  # the person's own discard
            _tidy(incoming(root))
            return "discarded the drop, which was never taken in", None
        last = acts[-1]
        if act and last.get("act") != act:
            raise IntakeRefused("not-last", "that act is undone already, or another came after it", 409)
        if why := _untrusted(root, d, last):
            raise IntakeRefused("untrusted", f"the record of this drop cannot be trusted: {why}", 409)
        act_ = last
        if act_["kind"] == "unfiled":
            plan = _check_unfile(root, d, act_)
            _undo_unfile(root, d, act_, plan)
            said = f"filed it again under {act_['citekey']}"
        elif act_["kind"] == "here":
            _check_here(root, d, act_)
            _undo_here(d, root, act_)
            said = f"it waits again; these very bytes are still {act_['citekey']}'s"
        else:
            # a work the act made, or the version entry it made, is the act's alone while new; a document filed under a work the person had is the act's while nothing was read off it
            why = _not_new(result, list(act_["entries"])) if act_["entries"] else _read_off(root, act_["citekey"])
            if why:
                raise IntakeRefused(
                    "not-new",
                    f"{why}, so it is no longer only what the intake added; take it off with unfile or delete it",
                    409,
                )
            plan = _check_add(root, act_)
            _undo_add(root, d, act_, plan, keep=len(acts) > 1 or bool((act_.get("waiting") or {}).get("over")))
            said = (
                f"took {act_['citekey']} out again"
                if act_["entries"]
                else f"took the document off {act_['citekey']} again"
            )
        # the record last: a crash before here leaves the act standing, its file where the act's own order put it
        rest = acts[:-1]
        if rest:
            _write_json(d / ACT, {"acts": rest})
        else:
            (d / ACT).unlink(missing_ok=True)
        if act_["kind"] == "unfiled":
            _let_go(root, d, (root / act_["home"],))  # the document stands under its work again
        if rest or waiting_file(d) is not None:
            waits = waiting_file(d) is not None or (d / QUESTION).is_file()
            return said, _waiting_row(d, 0) if waits else None
        _remove_drop(root, d)
        return said, None


def _untrusted(root: Path, d: Path, act: dict[str, Any]) -> str:
    """Why the record of an act cannot be acted on, in words, or '': a drop travels with a quilt copied as a folder, so every path it names must be one loom writes, inside the store or the drop, before an undo reads or writes anything for it."""
    from loom.refs.pages import storage_root

    store = os.path.realpath(storage_root(root))
    home = act.get("home")
    if not isinstance(home, str) or (home and not (home.startswith(f"{STORAGE}/") and ".." not in home.split("/"))):
        return "its home is not a place in loom's store"
    if home and not os.path.realpath(root / home).startswith(store + os.sep):
        return "its home leads out of loom's store"
    names = ([act.get("name")] if home else []) + list(act.get("names") or []) + list(act.get("moved") or [])
    if not all(isinstance(n, str) and n and "/" not in n and n not in (".", "..") for n in names):
        return "a file it names is no plain name"
    if not set(act.get("moved") or []) <= set(READ_OFF):
        return "it names what reading a document never writes"
    held = act.get("held", f"{HELD}/0")
    if not (isinstance(held, str) and re.fullmatch(rf"{HELD}/\d+", held)):
        return "where it held page text is no place in the drop"
    if act.get("sha") is not None and not re.fullmatch(r"[0-9a-f]{64}", str(act["sha"])):
        return "its document's hash is no hash"
    if act.get("kind") == "added" and set(act.get("blocks") or {}) != set(act.get("entries") or []):
        return "it does not say what it wrote of each entry"
    if act.get("kind") not in ("added", "unfiled", "here"):
        return "it is no act loom records"
    return ""


def _check_add(root: Path, act: dict[str, Any]) -> _Bib:
    """Refuse to undo an add whose parts are no longer as it left them; else what to make of the bibliography. Its document must stand at its place, no entry but its own may name that place, its entries must be found as written, and a work it made must hold nothing filed under it since."""
    from loom.refs.pages import sha256_of

    home = root / act["home"] if act["home"] else None
    key = act["citekey"]
    if home is not None and act.get("sha") is not None:
        paper = home / "paper.pdf"
        if not paper.is_file() or sha256_of(paper) != act["sha"]:
            raise IntakeRefused(
                "changed",
                f"{key}'s place in the store no longer holds the document this drop added; undoing it would remove what is there now",
                409,
            )
    plan = _unwritten(root, act)
    now = _bib_now(root)
    mine = set(act["entries"]) | {key}
    if home is not None:
        others = sorted(k for k, e in now.items() if k not in mine and _place_of(root, e) == home)
        if others:
            raise IntakeRefused(
                "changed",
                f"{others[0]} names {key}'s place in the store now; undoing would leave it naming nothing",
                409,
            )
    for made in act["entries"]:
        versions = sorted(k for k, e in now.items() if str(e.fields.get("loom-copy-of") or "").strip() == made)
        if versions:
            raise IntakeRefused(
                "changed", f"{versions[0]} was filed as another document of {made} since: delete that first", 409
            )
        entry = now.get(made)
        place = _place_of(root, entry) if entry is not None else None
        if place is not None and place != home and place.is_dir() and any(place.iterdir()):
            raise IntakeRefused(
                "changed",
                f"{made} holds a document filed under it since: take that off first (unfile it), then undo",
                409,
            )
    return plan


def _check_unfile(root: Path, d: Path, act: dict[str, Any]) -> _Bib:
    """Refuse to undo an unfile when what it left has changed; else what to make of the bibliography. The document must still wait, its place must hold nothing, and the place must still be its work's: the work's entry naming it, or for a version, its key free and no entry naming the place."""
    home = root / act["home"]
    key = act["citekey"]
    if not (d / act["name"]).is_file():
        raise IntakeRefused("changed", "the document this unfile took off no longer waits in its drop", 409)
    if (home / "paper.pdf").exists() or any((home / n).exists() for n in act["moved"]):
        from loom.refs.pages import sha256_of

        if (home / "paper.pdf").is_file() and sha256_of(home / "paper.pdf") == d.name:
            raise IntakeRefused(
                "changed", f"{key} holds this very document still: the unfile stopped before the store let it go", 409
            )
        raise IntakeRefused(
            "changed", f"{key} holds another document now: take that one off first, and this one can go back", 409
        )
    now = _bib_now(root)
    naming = sorted(k for k, e in now.items() if _place_of(root, e) == home)
    if act["removed"]:
        for k in act["removed"]:
            if k in now:
                raise IntakeRefused(
                    "changed", f"{k} is another entry's key now: rename that one, and this one can go back", 409
                )
        if naming:
            raise IntakeRefused("changed", f"{naming[0]} names the place {key}'s document stood now", 409)
        return _put_back(root, act)
    if key not in now or _place_of(root, now[key]) != home:
        raise IntakeRefused(
            "changed",
            f"{key} is no longer in the bibliography as it was, so its document has nowhere to go back to",
            409,
        )
    if set(naming) - {key}:
        raise IntakeRefused("changed", f"{sorted(set(naming) - {key})[0]} names {key}'s place now", 409)
    return "keep", ""


def _check_here(root: Path, d: Path, act: dict[str, Any]) -> None:
    """Refuse to give back a drop let go as already held when the place that held its bytes holds them no longer, since there is then nothing to copy back."""
    from loom.refs.pages import sha256_of

    paper = root / act["home"] / "paper.pdf"
    if not paper.is_file() or sha256_of(paper) != act["sha"]:
        raise IntakeRefused(
            "changed", f"{act['citekey']}'s place no longer holds these bytes, so there is nothing to give back", 409
        )


def _undo_here(d: Path, root: Path, act: dict[str, Any]) -> None:
    """The drop waits again, a copy of the held bytes as its file."""
    put_file(root / act["home"] / "paper.pdf", d / FILE, replace=True)
    if act.get("arrived") is not None:
        _write_json(d / ARRIVED, act["arrived"])


def _undo_add(root: Path, d: Path, act: dict[str, Any], plan: _Bib, *, keep: bool) -> None:
    """Take out what an add wrote: the records as `plan` and the act's record say, then its home or what it put in one and the word boxes read off it; with `keep`, earlier acts on the drop standing, its file waits there again, as it did before the act or as it was received again while the act stood, linked back before the store lets go of it.

    The records go before the store, so an entry never names a place emptied under it, whenever this stops.
    """
    from loom.refs.pages import storage_root

    held = act.get("waiting") or {}
    home = root / act["home"] if act["home"] else None
    if keep:
        # its file waited before the act, or these very bytes were received again while it stood
        if (held.get("file") or "received" in act) and home is not None and (home / "paper.pdf").is_file():
            put_file(home / "paper.pdf", d / FILE, link=True, replace=True)
        arrived = held.get("arrived") if held.get("arrived") is not None else act.get("received") or None
        if arrived is not None:
            _write_json(d / ARRIVED, arrived)
        (d / QUESTION).unlink(missing_ok=True)
    _restore_records(root, act["records"], plan)
    if home is not None:
        names = act["names"]
        if names is None:
            shutil.rmtree(home, ignore_errors=True)
        else:
            for extra in set(os.listdir(home)) - set(names) if home.is_dir() else set():
                p = home / extra
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        boxes = storage_root(root) / "cache" / "boxes" / home.parent.name / home.name
        shutil.rmtree(boxes, ignore_errors=True)
        _tidy(boxes.parent)
        _tidy(home.parent)


def _link_tree(src: Path, dst: Path) -> None:
    """Give `dst` what `src` holds, a file or a tree, by hard links where the filesystem has them, else by copies; `src` stays."""

    def one(a: str, b: str) -> None:
        try:
            os.link(a, b)
        except OSError:
            shutil.copy2(a, b)

    if src.is_dir():
        shutil.copytree(src, dst, copy_function=one)
    else:
        one(str(src), str(dst))


def _clear_unrecorded(d: Path) -> None:
    """Remove the `held/<n>` an unfile that stopped before recording itself left: copies of page text whose originals still stand, since an unfile removes nothing from the store until its act is recorded."""
    recorded = {a.get("held") for a in _acts(d)}
    for p in sorted((d / HELD).iterdir()) if (d / HELD).is_dir() else []:
        if f"{HELD}/{p.name}" not in recorded:
            shutil.rmtree(p, ignore_errors=True)


def unfile(result: Any, citekey: str, *, by: str) -> dict[str, Any]:
    """Take a work's stored PDF off it: the PDF waits again in `.loom/incoming/<sha>/` with that work in `not`, its page text beside it until the unfile is undone; a version entry made for it goes too, and the work stays.

    Raises
    ------
    IntakeRefused
        `no-such-work` (404); `no-document` (409) for a work holding no PDF; `has-results` (409) for one whose results were read off it; `own-document` (409) for a work that came in with this very PDF, which an undo or a delete takes out whole.
    """
    with library_lock(result.quilt.root):
        return _unfile(result, citekey, by=by)


def _unfile(result: Any, citekey: str, *, by: str) -> dict[str, Any]:
    from loom.refs.fetch import work_dir
    from loom.refs.pages import sha256_of, storage_root
    from loom.refs.proposals import load_results
    from loom.refs.scan import load_ledger

    root = result.quilt.root
    bib = _bib_now(root)  # as it is under the lock, not as the caller's scan read it
    if citekey not in bib:
        raise IntakeRefused("no-such-work", f"the library has no work {citekey}", 404)
    home = work_dir(root, bib[citekey])
    paper = home / "paper.pdf"
    if not paper.is_file():
        raise IntakeRefused("no-document", f"{citekey} holds no PDF to take off", 409)
    if load_results(root, citekey):
        raise IntakeRefused(
            "has-results", f"{citekey} has results read off this PDF, which would be left reading nothing", 409
        )
    entry = bib[citekey]
    own = str(entry.fields.get("loom-file") or "").strip() == _rel(storage_root(root), home)
    if own and not entry.fields.get("loom-copy-of"):
        raise IntakeRefused(
            "own-document",
            f"{citekey} came in with this PDF and is nothing without it: undo the drop, or delete the work",
            409,
        )
    with library_lock(root):
        sha = sha256_of(paper)
        d = incoming(root) / sha
        _clear_stale(root, d)
        if waiting_file(d) is not None:
            raise IntakeRefused("already-waiting", f"the same file waits to be taken in already, as {sha[:12]}", 409)
        rec = load_ledger(root).get(sha) or {}
        name = FILE
        before = _before(root, [sha])
        d.mkdir(parents=True, exist_ok=True)
        arrived = _read_json(d / ARRIVED)
        _clear_unrecorded(d)
        slot = len(_acts(d))
        while (d / HELD / str(slot)).exists():
            slot += 1
        place = f"{HELD}/{slot}"
        held = d / place
        held.mkdir(parents=True)
        # linked into the drop first; the store lets go of the document only once the act is recorded, so a crash anywhere leaves a copy where a record finds it
        try:
            put_file(paper, d / name, link=True)
        except FileExistsError:
            pass  # a receive of these very bytes placed it meanwhile
        moved = [n for n in READ_OFF if (home / n).exists()]
        for n in moved:
            _link_tree(home / n, held / n)
        boxes = storage_root(root) / "cache" / "boxes" / home.parent.name / home.name
        if boxes.is_dir():
            _link_tree(boxes, held / "boxes")
        removed: dict[str, str] = {}
        if entry.fields.get("loom-copy-of") and own:
            removed = _remove_entry(root, citekey)
        if rec.get("to") == _rel(storage_root(root), home):
            ledger = load_ledger(root)
            ledger.pop(sha, None)
            write_whole(root / LEDGER, json.dumps(ledger, indent=2, sort_keys=True) + "\n")
        made = set(os.listdir(home)) <= {"paper.pdf", *moved}
        refused = sorted({*(arrived or {}).get("not", []), citekey, str(entry.fields.get("loom-copy-of") or citekey)})
        _write_json(
            d / ARRIVED,
            {
                "name": Path(str(rec.get("from") or name)).name,
                "size": (d / name).stat().st_size,
                "when": stamp(),
                "not": refused,
            },
        )
        act_id = _push(
            d,
            {
                "kind": "unfiled",
                "citekey": citekey,
                "home": _rel(root, home),
                "emptied": made,
                "held": place,
                "arrived": arrived,
                "moved": moved,
                "name": name,
                "removed": removed,
                "records": _records(root, before),
                "when": stamp(),
                "by": by,
            },
        )
        paper.unlink()
        for n in moved:
            shutil.rmtree(home / n) if (home / n).is_dir() else (home / n).unlink()
        shutil.rmtree(boxes, ignore_errors=True)
        if made and home.is_dir() and not any(home.iterdir()):
            home.rmdir()
    return {"incoming": sha, "act": act_id, "row": _waiting_row(d, 0).to_json()}


def _remove_entry(root: Path, key: str) -> dict[str, str]:
    """Take one entry out of the bibliography; {key: "<offset>\\0<its exact text>"}, for an undo to put back."""
    from loom.refs.added import _block

    bib = root / BIBLIOGRAPHY
    text = read_exact(bib)
    where = _block(text, key)
    if where is None:
        return {}
    write_whole(bib, text[: where[0]] + text[where[1] :])
    return {key: f"{where[0]}\0{text[where[0] : where[1]]}"}


def _undo_unfile(root: Path, d: Path, act: dict[str, Any], plan: _Bib) -> None:
    """Put a document an unfile took off back under its work, with what was read off it: linked into its place before its entry is put back, and let go of in the drop (`undo`, through `_let_go`) only once the act is undone."""
    from loom.refs.pages import storage_root

    home = root / act["home"]
    home.mkdir(parents=True, exist_ok=True)
    put_file(d / act["name"], home / "paper.pdf", link=True)
    held = d / act["held"]
    for n in act["moved"]:
        if (held / n).exists():
            shutil.move(str(held / n), str(home / n))
    if (held / "boxes").is_dir():
        boxes = storage_root(root) / "cache" / "boxes" / home.parent.name / home.name
        boxes.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(held / "boxes"), str(boxes))
    _restore_records(root, act["records"], plan)
    shutil.rmtree(held, ignore_errors=True)
    _tidy(held.parent)
    if act.get("arrived") is not None:
        _write_json(d / ARRIVED, act["arrived"])
    (d / QUESTION).unlink(missing_ok=True)


# ---- what waits -----------------------------------------------------------------------------------------------------------


def _waiting_row(d: Path, n: int) -> Row:
    """The row a drop that waits is: its question, or `received` for a file not yet taken."""
    asked = _read_json(d / QUESTION)
    arrived = _read_json(d / ARRIVED) or {}
    if isinstance(asked, dict):
        name = str(asked.get("name") or arrived.get("name") or "")
        return Row(
            d.name,
            n,
            name,
            "question",
            question=d.name,
            document=dict(asked.get("document") or {}),
            candidates=list(asked.get("candidates") or []),
        )
    return Row(d.name, n, str(arrived.get("name") or ""), "received")


def waiting(root: Path) -> list[dict[str, Any]]:
    """Every drop that waits on the person, as rows, oldest first: a question, or a file received and not yet taken; what the manifest's `arriving` lists."""
    base = incoming(root)
    if not base.is_dir():
        return []
    out = []
    drops: list[tuple[float, Path]] = []
    # a receive under way writes and renames files here outside the publication's lock, so only drops are looked at, and one gone meanwhile is passed over
    for d in base.iterdir():
        if re.fullmatch(r"[0-9a-f]{64}|t-[0-9a-f]{16}", d.name):
            try:
                drops.append((d.stat().st_mtime, d))
            except FileNotFoundError:
                continue
    for _, d in sorted(drops):
        if d.is_dir() and ((d / QUESTION).is_file() or (waiting_file(d) is not None and not _taken(d))):
            row = _waiting_row(d, 0).to_json()
            row.pop("item", None)
            if row["state"] == "received":
                row = {"id": d.name, "name": row["name"], "state": "received"}
            out.append(row)
    return out
