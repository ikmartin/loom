"""The one door: every write loom makes to a person's file is an act through `act`.

An act holds `.loom/local/writes.lock` across processes and threads, settles what a crash left, lets its caller read, decide and stage under the lock, then keeps every before and after in the history's text store, journals `begin` in `.loom/local/writes.jsonl` before any file, writes each file whole (a temp beside it, the file read once more, its mode kept, a rename), appends the act's record lines and `done`. `docs/design/writes.md` is the design; this module is the only place a person's file is written by the acts routed through it.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import secrets
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom.errors import ContentError
from loom.locks import flush, locked
from loom.paths import JOURNAL, JOURNAL_INDEX, WRITES_LOCK

#: The suffix of the temporary file an act writes beside the file it replaces.
TEMP = ".loom-tmp"
#: A digest as the store names its texts: anything else is never made into a path.
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class WriteRefused(ContentError):
    """A write the door will not make, and why in the person's words; `code` is the write API's, and a command exits 1 with the message."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


# ---- the store ------------------------------------------------------------------------------------------------------


def digest(data: bytes | None) -> str | None:
    """`sha256:<hex>` of `data`; None for a file that is not there."""
    return None if data is None else "sha256:" + hashlib.sha256(data).hexdigest()


def _flush(fh: Any, full: bool = False) -> None:
    """Flush a written file to the disk; `full` asks the drive itself to empty its cache (`locks.flush`)."""
    fh.flush()
    flush(fh.fileno(), full)


def store(history: Path, data: bytes) -> str:
    """Keep `data` exactly in the history's `texts/`, as `<hex>.md` when it is UTF-8 and `<hex>.bin` otherwise; returns its digest.

    The names `records.snapshots.write_raw` gives, so versions, looks and the journal share one store. Written whole and flushed, or not at all: a stored text is named by its hash, and a half-written one would be trusted forever.
    """
    d = digest(data)
    assert d is not None
    try:
        data.decode("utf-8")
        suffix = ".md"
    except UnicodeDecodeError:
        suffix = ".bin"
    p = history / "texts" / f"{d.split(':', 1)[1]}{suffix}"
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}{TEMP}")
        try:
            with tmp.open("wb") as fh:
                fh.write(data)
                _flush(fh)
            os.replace(tmp, p)
        finally:
            tmp.unlink(missing_ok=True)
    return d


def fetch(history: Path, d: str) -> bytes | None:
    """The bytes stored as `d`, or None when the store does not hold them or `d` is not a digest's shape (`DIGEST`), which is never made into a path."""
    if not isinstance(d, str) or not DIGEST.match(d):
        return None
    hexd = d.split(":", 1)[1]
    for suffix in (".md", ".bin"):
        p = history / "texts" / f"{hexd}{suffix}"
        if p.is_file():
            return p.read_bytes()
    return None


# ---- the scan's reading, and splices into the file's own text ------------------------------------------------------


def scan_reading(data: bytes) -> str:
    """`data` as the scan reads a source file: decoded as `scan.source.decode` does, with CRLF and CR read as LF."""
    from loom.scan.source import decode

    return decode(data)[0].replace("\r\n", "\n").replace("\r", "\n")


def newline_of(text: str) -> str:
    """The line ending most of `text`'s lines end with: CRLF, CR or LF (LF for a text of one line)."""
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    best = max((lf, "\n"), (crlf, "\r\n"), (cr, "\r"), key=lambda c: c[0])
    return best[1] if best[0] else "\n"


def raw_offsets(raw: str) -> list[int]:
    """For each offset of `raw` in the scan's reading (CRLF and CR read as LF), the offset in `raw`; one more for the end."""
    out: list[int] = []
    i, n = 0, len(raw)
    while i < n:
        out.append(i)
        i += 2 if raw[i] == "\r" and i + 1 < n and raw[i + 1] == "\n" else 1
    out.append(n)
    return out


def splice(raw: str, spans: list[tuple[int, int, str]]) -> tuple[str, list[dict[str, Any]]]:
    """Put each `(a, b, text)` into `raw` in place of `a`..`b`, offsets in the scan's reading of `raw`; every other character is kept, and `text` takes `raw`'s own line ending.

    Returns the new text and one splice per span, in the order given: `{at, old, new}`, `at` its offset in the new text. Raises ValueError for spans that overlap or fall outside the text.
    """
    pos = raw_offsets(raw)
    nl = newline_of(raw)
    order = sorted(range(len(spans)), key=lambda i: (spans[i][0], spans[i][1]))
    last = 0
    for i in order:
        a, b, _ = spans[i]
        if not 0 <= a <= b < len(pos) or a < last:
            raise ValueError(f"splice {a}..{b} overlaps another or leaves the text")
        last = b
    out: list[str] = []
    made: list[dict[str, Any]] = [{} for _ in spans]
    at = shift = 0
    for i in order:
        a, b, text = spans[i]
        ra, rb = pos[a], pos[b]
        new = text.replace("\r\n", "\n").replace("\r", "\n")
        new = new.replace("\n", nl) if nl != "\n" else new
        out.append(raw[at:ra])
        out.append(new)
        made[i] = {"at": ra + shift, "old": raw[ra:rb], "new": new}
        shift += len(new) - (rb - ra)
        at = rb
    out.append(raw[at:])
    return "".join(out), made


def reading_offset(raw: str, at: int) -> int:
    """Offset `at` of `raw` as an offset in the scan's reading of it (CRLF read as LF)."""
    return at - raw.count("\r\n", 0, at)


# ---- what an act wrote, found again -------------------------------------------------------------------------------

#: How many characters either side of an edit's words, as an act left them, find those words again.
BESIDE = 32


@dataclass(frozen=True)
class Written:
    """One splice the act `act` made in `rel`, for the suggested edit `edit` (`<id>:<generation>`): the words it put in (`new`) at `at` of the act's after text, the words they replaced (`old`), and up to `BESIDE` characters either side as they stood after the act (`left`, `right`) and before it (`was_left`, `was_right`). `before` and `after` are the digests of the file's bytes either side of the act, and `edits` every edit it spliced into the file."""

    act: str
    rel: str
    edit: str
    at: int
    old: str
    new: str
    left: str
    right: str
    was_left: str
    was_right: str
    before: str | None
    after: str
    edits: tuple[str, ...]

    @property
    def done(self) -> str:
        """The words the act put in, with their neighbours as it left them."""
        return self.left + self.new + self.right

    @property
    def undone(self) -> str:
        """The words the act replaced, with their neighbours as they were before it."""
        return self.was_left + self.old + self.was_right


def splices_of(history: Path, entry: dict[str, Any], edit: str | None = None) -> list[Written] | None:
    """Each splice the journal's `begin` line `entry` made, for the edit `edit` or for every edit, as `Written`; None when a text it needs is missing from the store, is not UTF-8, or the line does not read as a splice."""
    out: list[Written] = []
    files = entry.get("files") or {}
    try:
        for rel, made in (entry.get("splices") or {}).items():
            mine = [m for m in made if edit is None or m.get("edit") == edit]
            if not mine:
                continue
            ab = files.get(rel)
            if not ab or ab[1] is None:
                return None
            before = fetch(history, ab[0]) if ab[0] else b""
            after = fetch(history, ab[1])
            if before is None or after is None:
                return None
            was, now = before.decode("utf-8"), after.decode("utf-8")
            every = tuple(str(o.get("edit") or "") for o in made)
            # each splice in the text after the act, and in the text before it: each splice ahead of one moved it
            spans: list[tuple[int, int, int, int]] = []
            for o in made:
                at = int(o["at"])
                back = at - sum(len(str(x["new"])) - len(str(x["old"])) for x in made if int(x["at"]) < at)
                spans.append((at, at + len(str(o["new"])), back, back + len(str(o["old"]))))
            for m in mine:
                at, old, new = int(m["at"]), str(m["old"]), str(m["new"])
                a0, a1, b0, b1 = spans[made.index(m)]
                # its neighbours are the words beside it up to `BESIDE`, never the act's own words beside it
                lo = max([x[1] for x in spans if x[1] <= a0], default=0)
                hi = min([x[0] for x in spans if x[0] >= a1 and x != spans[made.index(m)]], default=len(now))
                was_lo = max([x[3] for x in spans if x[3] <= b0], default=0)
                was_hi = min([x[2] for x in spans if x[2] >= b1 and x != spans[made.index(m)]], default=len(was))
                out.append(
                    Written(
                        act=str(entry.get("act") or ""),
                        rel=str(rel),
                        edit=str(m.get("edit") or ""),
                        at=at,
                        old=old,
                        new=new,
                        left=now[max(lo, a0 - BESIDE) : a0],
                        right=now[a1 : min(hi, a1 + BESIDE)],
                        was_left=was[max(was_lo, b0 - BESIDE) : b0],
                        was_right=was[b1 : min(was_hi, b1 + BESIDE)],
                        before=ab[0],
                        after=ab[1],
                        edits=every,
                    )
                )
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeDecodeError):
        return None
    return out


def stands_once(text: str, needle: str) -> int | None:
    """Where `needle` starts in `text` when it stands there exactly once; None when nowhere or more than once."""
    i = text.find(needle)
    if i < 0 or text.find(needle, i + 1) >= 0:
        return None
    return i


def where_now(text: str, w: Written) -> int | None:
    """Where `w`'s words stand in `text`, found with their neighbours as the act left them, and only where those stand exactly once."""
    i = stands_once(text, w.done)
    return None if i is None else i + len(w.left)


# ---- paths ----------------------------------------------------------------------------------------------------------


def contained(root: Path, rel: str) -> str:
    """`rel` normalised as a path in the quilt; WriteRefused (`outside-quilt`) for one that is absolute, climbs out with `..`, or would be made in a directory outside the quilt.

    A file or symlink the quilt already holds is the person's own arrangement, and is allowed wherever it points.
    """
    if not rel or rel.startswith(("/", "\\")) or (len(rel) > 1 and rel[1] == ":"):
        raise WriteRefused("outside-quilt", f"{rel or 'an empty path'} is outside the quilt")
    norm = posixpath.normpath(rel.replace("\\", "/"))
    if norm == "." or norm == ".." or norm.startswith("../"):
        raise WriteRefused("outside-quilt", f"{rel} is outside the quilt")
    p = root / norm
    if not (p.exists() or p.is_symlink()):
        parent = p.parent.resolve()
        if not parent.is_relative_to(root.resolve()):
            raise WriteRefused("outside-quilt", f"{rel} is outside the quilt")
    return norm


def _target(root: Path, rel: str) -> Path:
    """The file a write to `rel` lands in: a symlink's target, so the link stays a link."""
    p = root / rel
    return Path(os.path.realpath(p)) if p.is_symlink() else p


def _read(root: Path, rel: str) -> bytes | None:
    t = _target(root, rel)
    try:
        return t.read_bytes()
    except FileNotFoundError:
        return None
    except IsADirectoryError as exc:
        raise WriteRefused("not-a-file", f"{rel} is a directory") from exc


def _rename(tmp: Path, target: Path) -> None:
    os.replace(tmp, target)


def _flush_dir(d: Path) -> None:
    try:
        fd = os.open(d, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _install(root: Path, rel: str, data: bytes | None, expect: bytes | None) -> None:
    """Make `rel` hold `data` (None removes it), whole or not at all, refusing (`changed`) when it no longer holds `expect`.

    The temp is written and flushed beside the target, the target read once more, the mode kept, then the rename: the window in which a save can be lost is the instant between the read and the rename. A temp is removed when this fails and left by a crash, for recovery.
    """
    if data is None:
        if _read(root, rel) != expect:
            raise WriteRefused("changed", f"{rel} changed while loom was writing it; nothing was written")
        (root / rel).unlink(missing_ok=True)
        _flush_dir((root / rel).parent)
        return
    target = _target(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{secrets.token_hex(6)}{TEMP}")
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            _flush(fh)
        try:
            mode = target.stat().st_mode & 0o7777
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp, mode)
        if _read(root, rel) != expect:
            raise WriteRefused("changed", f"{rel} changed while loom was writing it; nothing was written")
        _rename(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _flush_dir(target.parent)


def _put(root: Path, rel: str, data: bytes | None) -> None:
    """Make `rel` hold `data` with no check: recovery's and a failed act's way of putting the before bytes back."""
    if data is None:
        (root / rel).unlink(missing_ok=True)
        return
    target = _target(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{secrets.token_hex(6)}{TEMP}")
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            _flush(fh)
        try:
            os.chmod(tmp, target.stat().st_mode & 0o7777)
        except FileNotFoundError:
            pass
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def _temps(root: Path, rel: str) -> list[Path]:
    t = _target(root, rel)
    return list(t.parent.glob(f".{t.name}.*{TEMP}")) if t.parent.is_dir() else []


# ---- the journal and its index --------------------------------------------------------------------------------------


@dataclass
class Journal:
    """The journal as read so far: where reading stopped, the acts begun and not settled (by id: the offset of their `begin` and the line), and each `<edit>:<generation>` a done act wrote, with the offset of its `begin`."""

    offset: int = 0
    begun: dict[str, tuple[int, dict[str, Any]]] = field(default_factory=dict)
    wrote: dict[str, int] = field(default_factory=dict)

    def fold(self, at: int, entry: dict[str, Any]) -> None:
        """Take in the line at `at`."""
        act = str(entry.get("act") or "")
        event = entry.get("event")
        if event == "begin":
            self.begun[act] = (at, entry)
        elif event == "done":
            begun = self.begun.pop(act, None)
            if begun is not None:
                for gen in begun[1].get("edits") or []:
                    self.wrote[str(gen)] = begun[0]
        elif event == "aborted":
            self.begun.pop(act, None)

    def append(self, root: Path, entry: dict[str, Any], *, full: bool = False) -> None:
        """Append `entry` to the quilt's journal and take it in; under the lock, so nothing else was appended since this was read."""
        start, end = _append_journal(root, entry, full=full)
        self.fold(start, entry)
        self.offset = end


def _append_line(path: Path, text: str, full: bool = False) -> tuple[int, int]:
    """Append one line to `path`, on a line of its own even after a crash cut the last one short, and flush it; returns where it starts and ends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        start = fh.seek(0, os.SEEK_END)
        if start:
            with path.open("rb") as rd:
                rd.seek(start - 1)
                if rd.read(1) != b"\n":
                    fh.write(b"\n")
                    start += 1
        data = text.encode("utf-8") + b"\n"
        fh.write(data)
        _flush(fh, full)
    return start, start + len(data)


def _append_journal(root: Path, entry: dict[str, Any], *, full: bool = False) -> tuple[int, int]:
    return _append_line(root / JOURNAL, json.dumps(entry, ensure_ascii=False, sort_keys=True), full)


def read_journal(root: Path) -> Journal:
    """The quilt's journal folded through its last whole line, starting from the index where the index holds; never writes."""
    p = root / JOURNAL
    size = p.stat().st_size if p.is_file() else 0
    j = _load_index(root)
    if j is None or j.offset > size:
        j = Journal()
    if j.offset == size:
        return j
    with p.open("rb") as fh:
        fh.seek(j.offset)
        at = j.offset
        for line in fh:
            if not line.endswith(b"\n"):
                break  # an append still being written, or one a crash cut short: the next append starts a new line
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                entry = None
            if isinstance(entry, dict):
                j.fold(at, entry)
            at += len(line)
        j.offset = at
    return j


def entry_at(root: Path, offset: int) -> dict[str, Any] | None:
    """The quilt's journal's line that starts at `offset`."""
    p = root / JOURNAL
    try:
        with p.open("rb") as fh:
            fh.seek(offset)
            entry = json.loads(fh.readline())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return entry if isinstance(entry, dict) else None


def _load_index(root: Path) -> Journal | None:
    try:
        data = json.loads((root / JOURNAL_INDEX).read_text(encoding="utf-8"))
        return Journal(
            offset=int(data["offset"]),
            begun={str(k): (int(v[0]), dict(v[1])) for k, v in data["begun"].items()},
            wrote={str(k): int(v) for k, v in data["wrote"].items()},
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        return None


def _save_index(root: Path, j: Journal) -> None:
    """Write the index by rename; it is a cache of the journal, so it is not flushed, and losing it costs one read from the start."""
    p = root / JOURNAL_INDEX
    tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}{TEMP}")
    try:
        tmp.write_text(
            json.dumps({"offset": j.offset, "begun": {k: list(v) for k, v in j.begun.items()}, "wrote": j.wrote}),
            encoding="utf-8",
        )
        os.replace(tmp, p)
    except OSError:
        pass
    finally:
        tmp.unlink(missing_ok=True)


def _holds(root: Path, rel: str, want: str | None) -> bool:
    try:
        return digest(_read(root, rel)) == want
    except (OSError, WriteRefused):
        return False


def _all_after(root: Path, entry: dict[str, Any]) -> bool:
    return all(_holds(root, rel, ab[1]) for rel, ab in (entry.get("files") or {}).items())


def _in_quilt(root: Path, rel: Any) -> bool:
    """Whether `rel`, as a journal names it, is a path in the quilt in its normal form that stays inside it with every symlink followed: the only kind recovery reads or writes."""
    if not isinstance(rel, str):
        return False
    try:
        if contained(root, rel) != rel:
            return False
    except WriteRefused:
        return False
    return Path(os.path.realpath(root / rel)).is_relative_to(os.path.realpath(root))


def _logs(root: Path, history: Path) -> dict[str, Path]:
    """The record logs an act may append to, by the name a journal gives each: the edits', the annotations' and the ledger, nothing else."""
    from loom.history.ledger import LEDGER
    from loom.paths import EDIT_LOG
    from loom.records.log import log_path

    return {_log_name(root, p): p for p in (root / EDIT_LOG, log_path(root), history / LEDGER)}


def _log_name(root: Path, log: Path) -> str:
    rel = os.path.relpath(log, root)
    return log.as_posix() if rel.startswith("..") else Path(rel).as_posix()


def _log_ok(root: Path, history: Path, name: Any) -> bool:
    """Whether `name` is one of loom's own logs (`_logs`) and still in `.loom/` or the history directory with every symlink followed."""
    from loom.paths import LOOM

    p = _logs(root, history).get(name) if isinstance(name, str) else None
    if p is None:
        return False
    real = Path(os.path.realpath(p))
    return any(real.is_relative_to(os.path.realpath(d)) for d in (root / LOOM, history))


def untrusted(root: Path, history: Path, entry: dict[str, Any]) -> str:
    """Why recovery may not act on the journal's `begin` line `entry`, in words; '' when it may.

    A journal travels with a copied quilt, so nothing in it is taken on trust: every file must be a path in the quilt that stays in it (`_in_quilt`), every digest a digest, every record line a JSON object bound for one of loom's own logs (`_log_ok`), and the act must name a file at all, since the door journals no act that writes none.
    """
    files = entry.get("files")
    if not isinstance(files, dict) or not files:
        return "it names no file"
    for rel, ab in files.items():
        if not _in_quilt(root, rel):
            return f"{rel!r} is not a file in the quilt"
        if (
            not isinstance(ab, list)
            or len(ab) != 2
            or not all(d is None or (isinstance(d, str) and DIGEST.match(d)) for d in ab)
        ):
            return f"what it says of {rel} is not two digests"
    records = entry.get("records") or []
    if not isinstance(records, list):
        return "its records are not a list"
    for rec in records:
        if not isinstance(rec, dict) or not _log_ok(root, history, rec.get("log")):
            return "a record goes somewhere other than loom's own logs"
        text = rec.get("line")
        try:
            line = json.loads(text) if isinstance(text, str) else None
        except json.JSONDecodeError:
            line = None
        if not isinstance(line, dict):
            return "a record is not one record"
    return ""


def unsettled(root: Path, history: Path) -> list[dict[str, Any]]:
    """Each act begun and neither done nor aborted, as its `begin` line: what recovery has yet to settle, or could not."""
    return [e for _, e in read_journal(root).begun.values()]


def written(root: Path, history: Path) -> set[str]:
    """Every `<edit>:<generation>` loom has written into a file, by the journal: a done act's, and an unsettled act's when every file holds what it wrote, as recovery will find. For readers outside the lock."""
    j = read_journal(root)
    out = set(j.wrote)
    for _, e in j.begun.values():
        if e.get("edits") and not untrusted(root, history, e) and _all_after(root, e):
            out.update(str(g) for g in e["edits"])
    return out


# ---- record lines ---------------------------------------------------------------------------------------------------


def _log_path(root: Path, log: str) -> Path:
    """Where the log a record names is: only ever one `_log_ok` allowed, checked before this is called."""
    return Path(log) if os.path.isabs(log) else root / log


def _append_record(root: Path, log: str, line: str, *, unless_there: bool = False) -> None:
    """Append `line` to the record log `log` under that log's own lock; with `unless_there`, only when no line of the log is the same line."""
    p = _log_path(root, log)
    with locked(p):
        if unless_there and p.is_file():
            want = json.loads(line)
            for have in p.read_text(encoding="utf-8").splitlines():
                try:
                    if json.loads(have) == want:
                        return
                except json.JSONDecodeError:
                    continue
        _append_line(p, line)


def _append_records(root: Path, records: list[dict[str, str]], *, unless_there: bool = False) -> None:
    for rec in records:
        _append_record(root, rec["log"], rec["line"], unless_there=unless_there)


# ---- recovery -------------------------------------------------------------------------------------------------------


def _settle(root: Path, history: Path, j: Journal) -> list[str]:
    """Settle each act `j` holds begun: finished when every file holds its after bytes, undone when each holds its before or its after, left when someone changed one since, and left untouched when anything it names fails `untrusted`. Returns what was done, in words. Call holding the lock."""
    from loom.clock import stamp

    said: list[str] = []
    for act_id, (_, e) in list(j.begun.items()):
        why = untrusted(root, history, e)
        if why:
            said.append(f"left {act_id}: {why}")
            continue
        files: dict[str, list[str | None]] = e.get("files") or {}
        for rel in files:
            for tmp in _temps(root, rel):
                tmp.unlink(missing_ok=True)
        holds = {rel: (_holds(root, rel, ab[0]), _holds(root, rel, ab[1])) for rel, ab in files.items()}
        if all(after for _, after in holds.values()):
            _append_records(root, e.get("records") or [], unless_there=True)
            j.append(root, {"event": "done", "act": act_id, "when": stamp(), "recovered": True})
            said.append(f"finished {act_id}")
        elif all(before or after for before, after in holds.values()):
            for rel, (before, after) in holds.items():
                if after and not before:
                    b = files[rel][0]
                    _put(root, rel, fetch(history, b) if b else None)
            j.append(root, {"event": "aborted", "act": act_id, "when": stamp(), "why": "cut short", "recovered": True})
            said.append(f"undid {act_id}")
    return said


#: Seconds after which a temporary file in the history's `texts/` is one a crash left, not one a store in another process is writing: `store` writes one and renames it within a moment.
LEFT = 3600.0


def recover(root: Path, history: Path, *, now: float | None = None) -> list[str]:
    """Settle what a crash left, holding the lock: the acts it cut short, and the temporary files a crash in `store` left in the history's `texts/` (`LEFT`). What `loom serve` runs as it starts; every act settles the acts first. Returns what was done, in words."""
    with locked(root / WRITES_LOCK):
        said = _left_temps(history, time.time() if now is None else now)
        j = read_journal(root)
        if not j.begun:
            return said
        said += _settle(root, history, j)
        _save_index(root, j)
        return said


def _left_temps(history: Path, now: float) -> list[str]:
    """Remove each temporary file `store` names `.<hex>.<ext>.<token>.loom-tmp` in the history's `texts/` that is older than `LEFT`, and say so."""
    texts = history / "texts"
    gone = 0
    try:
        entries = list(os.scandir(texts)) if texts.is_dir() and not texts.is_symlink() else []
    except OSError:
        entries = []
    for entry in entries:
        if not _STORE_TEMP.match(entry.name):
            continue
        try:
            st = entry.stat(follow_symlinks=False)
            if stat.S_ISREG(st.st_mode) and now - st.st_mtime > LEFT:
                os.unlink(entry.path)
                gone += 1
        except OSError:
            continue
    return (
        [f"removed {gone} temporary file{'s' if gone != 1 else ''} a crash left in the history's texts/"]
        if gone
        else []
    )


#: The name `store` gives the temporary file it writes a text through.
_STORE_TEMP = re.compile(r"^\.[0-9a-f]{64}\.(md|bin)\.[0-9a-f]{12}" + re.escape(TEMP) + "$")


# ---- an act ---------------------------------------------------------------------------------------------------------


class Act:
    """One act through the door: what its caller read, and what it stages to write, until the `act` block ends."""

    def __init__(self, root: Path, history: Path, kind: str, actor: str | None, journal: Journal) -> None:
        self.root = root
        self.history = history
        self.kind = kind
        self.actor = actor
        self.id = f"{kind}:{secrets.token_hex(8)}"
        self.journal = journal
        self.before: dict[str, bytes | None] = {}
        self.after: dict[str, bytes | None] = {}
        self.splices: dict[str, list[dict[str, Any]]] = {}
        self.edits: list[str] = []
        self.undone: list[str] = []
        self.records: list[dict[str, str]] = []
        self.follow: list[Callable[[], None]] = []

    # what the caller reads

    def read(self, rel: str) -> bytes | None:
        """The file's bytes now, under the lock; None for one that is not there. The last read before the file is staged (`replace`) is what the act replaces, and the commit refuses if the file holds anything else by then."""
        rel = contained(self.root, rel)
        data = _read(self.root, rel)
        if rel not in self.after:
            self.before[rel] = data
        return data

    def text(self, rel: str, *, again: bool = True) -> str | None:
        """The file as UTF-8 text with its own line endings; None for one that is not there. WriteRefused (`not-utf8`) for a file that is not UTF-8, which loom never writes into. With `again` False, the bytes this act last read of it, so that what a plan was checked against is what it is spliced into."""
        data = self.read(rel) if again or rel not in self.before else self.before[rel]
        if data is None:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WriteRefused(
                "not-utf8", f"{rel} is not UTF-8 text, so loom does not write into it; save it as UTF-8 first"
            ) from exc

    def reads_as(self, rel: str, planned: str | None) -> bool:
        """Whether the file, read now as the scan reads it, is `planned`: the text a plan's offsets are in."""
        data = self.read(rel)
        return (None if data is None else scan_reading(data)) == planned

    def expect(self, rel: str, planned: str | None) -> None:
        """WriteRefused (`changed`) unless the file reads now as `planned` (`reads_as`)."""
        if not self.reads_as(rel, planned):
            raise WriteRefused("changed", f"{rel} changed since loom read it; nothing was written, look at it again")

    def wrote_before(self, gen: str) -> bool:
        """Whether loom has written `<edit>:<generation>` already, by the journal as recovery left it."""
        return gen in self.journal.wrote

    def unsettled_edits(self) -> set[str]:
        """The edits named by acts recovery could not settle: loom may have written them, and cannot tell."""
        return {str(g) for _, e in self.journal.begun.values() for g in e.get("edits") or []}

    # what the caller stages

    def replace(self, rel: str, data: bytes | None, splices: list[dict[str, Any]] | None = None) -> None:
        """Stage `data` as the file's new bytes (None removes it); `splices` say what replaced what, for an undo."""
        rel = contained(self.root, rel)
        if rel not in self.before:
            self.read(rel)
        self.after[rel] = data
        if splices:
            self.splices.setdefault(rel, []).extend(splices)

    def wrote(self, gen: str) -> None:
        """Name a suggested edit's `<edit>:<generation>` as one this act writes."""
        self.edits.append(gen)

    def undid(self, gen: str) -> None:
        """Name a suggested edit's `<edit>:<generation>` as one whose Keep this act undoes; kept apart from `edits`, so the journal's `wrote` still says only what loom wrote."""
        self.undone.append(gen)

    def log(self, log: Path, line: dict[str, Any] | str) -> None:
        """A record line written with the act, after its files and before `done`; recovery appends it too when it finishes the act. A dict is written as the edit and annotation logs write theirs; a string is the line exactly. WriteRefused (`outside-quilt`) for a log that is not one of loom's own (`_logs`)."""
        text = line if isinstance(line, str) else json.dumps(line, ensure_ascii=False, sort_keys=True)
        name = _log_name(self.root, log)
        if not _log_ok(self.root, self.history, name):
            raise WriteRefused("outside-quilt", f"{log} is not one of loom's own logs")
        self.records.append({"log": name, "line": text})

    def then(self, fn: Callable[[], None]) -> None:
        """A step after `done` and still under the lock (a rescan, the look, carrying annotations); recovery never replays it."""
        self.follow.append(fn)

    # the commit

    def _commit(self) -> None:
        from loom.clock import stamp

        changed = {rel: data for rel, data in self.after.items() if data != self.before.get(rel)}
        if not changed:
            _append_records(self.root, self.records)
            self._follow()
            return
        files = {
            rel: [
                store(self.history, b) if (b := self.before.get(rel)) is not None else None,
                store(self.history, data) if data is not None else None,
            ]
            for rel, data in changed.items()
        }
        begin = {
            "event": "begin",
            "act": self.id,
            "kind": self.kind,
            "actor": self.actor,
            "when": stamp(),
            "files": files,
            "splices": {rel: s for rel, s in self.splices.items() if rel in changed},
            "edits": self.edits,
            "records": self.records,
        }
        if self.undone:
            begin["undid"] = self.undone
        self.journal.append(self.root, begin, full=True)
        done: list[str] = []
        try:
            for rel, data in changed.items():
                _install(self.root, rel, data, self.before.get(rel))
                done.append(rel)
        except Exception as exc:
            for rel in reversed(done):
                _put(self.root, rel, self.before.get(rel))
            for rel in changed:
                for tmp in _temps(self.root, rel):
                    tmp.unlink(missing_ok=True)
            why = exc.message if isinstance(exc, WriteRefused) else f"{type(exc).__name__}: {exc}"
            self.journal.append(self.root, {"event": "aborted", "act": self.id, "when": stamp(), "why": why})
            _save_index(self.root, self.journal)
            raise
        # every file holds its after bytes: the act has happened, and a failure from here on is recovery's to finish
        _append_records(self.root, self.records)
        self.journal.append(self.root, {"event": "done", "act": self.id, "when": stamp()})
        _save_index(self.root, self.journal)
        self._follow()

    def _follow(self) -> None:
        for fn in self.follow:
            fn()


@contextmanager
def act(root: Path, history: Path, kind: str, actor: str | None = None) -> Iterator[Act]:
    """Hold the door for one act; what the block stages is written when it ends without an exception.

    Parameters
    ----------
    root : Path
        The quilt.
    history : Path
        The quilt's history directory (`[quilt] history`): the text store is there; the lock and the journal are in `.loom/local/`.
    kind : str
        What the act is: `keep`, `undo`, `discard`, `restore`, `put-back`, `tick`, `settings`.
    actor : str, optional
        Who asked for it, for the journal.

    Yields
    ------
    Act
        Read, decide and stage through it; an exception out of the block writes nothing.

    Raises
    ------
    WriteRefused
        From the commit: a file changed at the last read before its rename, and the act was undone.
    """
    with locked(root / WRITES_LOCK):
        j = read_journal(root)
        if j.begun:
            _settle(root, history, j)
            _save_index(root, j)
        a = Act(root, history, kind, actor, j)
        yield a
        a._commit()
