"""`.loom/records/evidence/log.jsonl`: what someone did to a text, one record a line, each naming the text by its hash.

Appended under the log's lock and never rewritten, so two clones' lines merge by keeping both; replayed whole into `Evidence`, memoised by the log's size and time. A line that is not a record of a known kind, or whose fields are not that kind's (`docs/specs/evidence.md` §3), is skipped and reported as `loom:foreign-evidence`; it never stops the rest. Nothing here says what a record means for a result: that is `evidence.status`.
"""

from __future__ import annotations

import bisect
import json
import os
import re
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom.clock import stamp
from loom.evidence.subjects import HASH, Subject, Who, is_node, is_work, name_problem
from loom.library.node import pages_problem
from loom.locks import locked
from loom.paths import EVIDENCE_LOG
from loom.records.ids import EVIDENCE, draw

#: A record's id: `ev-`, the day it was written, and a random token (`records.ids`).
ID = re.compile(EVIDENCE)
#: When a record was written, in UTC to the second.
AT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
#: Every kind of record, in the order the spec gives them.
KINDS = ("digested", "compared", "proposed", "declined", "lean", "attested", "sought", "mention", "reading")
#: How a node's text was made, and the one kind of hand that makes it so.
HOWS = {
    "extracted": "loom",
    "transcribed": "agent",
    "read": "agent",
    "corrected": "agent",
    "written": "person",
    "numbered": "loom",
}
#: The one kind of hand each record may come from; a kind not here may come from any.
HANDS = {
    "compared": ("person",),
    "proposed": ("agent",),
    "declined": ("person",),
    "lean": ("loom",),
    "attested": ("person",),
    "sought": ("loom",),
    "mention": ("person",),
    "reading": ("agent",),
}
#: The keys every record has.
_COMMON = {"id", "kind", "at", "by"}
#: What a reading of a paper is about: a statement or a proof.
_READ = ("statement", "proof")


class EvidenceRefused(ValueError):
    """A record a writer built that is not one of `docs/specs/evidence.md`'s shapes: nothing was written."""


@dataclass(frozen=True)
class Record:
    """One line of the log as read: its id, kind, time, hand, subject (None for `declined` and `mention`), and the whole line."""

    id: str
    kind: str
    at: str
    by: Who
    on: Subject | None
    fields: Mapping[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """A field of the line, or `default`."""
        return self.fields.get(key, default)


@dataclass
class Evidence:
    """Every record of the log in the order written, the problems of the lines skipped, and indexes over them."""

    records: list[Record] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    _about: dict[tuple[str, str], list[Record]] = field(default_factory=dict, repr=False)
    _ids: dict[str, Record] = field(default_factory=dict, repr=False)
    _declined: dict[str, Record] = field(default_factory=dict, repr=False)

    def add(self, record: Record) -> None:
        """Take in one record read or just written; the indexes follow. A line a merge kept twice is the record it repeats, so its second copy is passed over wherever it stands (`loom:repeated-id` reports it)."""
        if record.id in self._ids:
            return
        self.records.append(record)
        self._ids[record.id] = record
        if record.on is not None:
            # by when it was written, not where a merge put it; records of one second keep the log's order
            bisect.insort_right(self._about.setdefault(record.on.key, []), record, key=lambda r: r.at)
        if record.kind == "declined":
            self._declined.setdefault(str(record.get("proposal")), record)

    def about(self, kind: str, name: str, *, of: str | None = None) -> list[Record]:
        """Every record on the thing `kind`, `name` names, at any hash, oldest first by `at`, records of one second in the order read; with `of`, only records of that kind."""
        found = self._about.get((kind, name), [])
        return [r for r in found if of is None or r.kind == of]

    def texts(self, kind: str, name: str, digest: str) -> list[str]:
        """The text `digest` and each it was numbered from, newest first: a loom `digested` how `numbered` on a text names the text its numbers were filled into (`was`), which differs from it only in its anchors' numbers, so a person's word on that one holds on this (`docs/specs/evidence.md` §3.1)."""
        out = [digest]
        while True:
            filled = [
                r
                for r in self.about(kind, name, of="digested")
                if r.on is not None and r.on.hash == out[-1] and r.get("how") == "numbered" and r.by.kind == "loom"
            ]
            was = filled[-1].get("was") if filled else None
            if not isinstance(was, str) or was in out:
                return out
            out.append(was)

    def compared(self, kind: str, name: str, digest: str) -> list[Record]:
        """The person's `compared` records that hold on the text `digest`: on it, or on a text it was numbered from (`texts`), oldest first."""
        held = set(self.texts(kind, name, digest))
        return [r for r in self.about(kind, name, of="compared") if r.on is not None and r.on.hash in held]

    def made(self, kind: str, name: str, digest: str) -> Record | None:
        """The latest `digested` saying how the words of the text `digest` were made: on it, else on the text it was numbered from, a `numbered` record saying only where its numbers came from."""
        for text in self.texts(kind, name, digest):
            said = [
                r
                for r in self.about(kind, name, of="digested")
                if r.on is not None and r.on.hash == text and r.get("how") != "numbered"
            ]
            if said:
                return said[-1]
        return None

    def by_id(self, record_id: str) -> Record | None:
        """The record with this id, the first if a merge kept two."""
        return self._ids.get(record_id)

    def declined(self, proposal: str) -> Record | None:
        """The person's `declined` of a proposal, or None."""
        return self._declined.get(proposal)

    def of_kind(self, kind: str) -> list[Record]:
        """Every record of one kind, oldest first."""
        return [r for r in self.records if r.kind == kind]

    def ids(self) -> Collection[str]:
        """Every record's id, for drawing a new one."""
        return self._ids.keys()

    def copy(self) -> Evidence:
        """A copy whose lists and indexes are its own, which a replay extends while a reader holds the first."""
        return Evidence(
            list(self.records),
            list(self.problems),
            {k: list(v) for k, v in self._about.items()},
            dict(self._ids),
            dict(self._declined),
        )


def log_path(root: Path) -> Path:
    """The log's file in `root`."""
    return root / EVIDENCE_LOG


@dataclass(frozen=True)
class Read:
    """How far a replay read a log: its inode, the bytes read (to the end of the last whole line), the lines read, and the bytes just before that end, by which the file is known for the same one grown."""

    ino: int
    size: int
    lines: int
    tail: bytes


#: The last replay of each log, by its path: how far it read, and what it read.
_MEMO: dict[str, tuple[Read, Evidence]] = {}
#: How many bytes before where a replay stopped must be unchanged for the file to be read on from there.
_TAIL = 64


def grown(path: Path, held: Read | None) -> tuple[bytes, int, bytes] | None:
    """The bytes appended to `path` since `held` read it, as whole lines, and the offset they start at; None when the file is not that one grown (another inode, shorter, or its last bytes read changed), which is read again whole. A line rewritten in place further back is not seen: the logs are appended to, never rewritten.

    A last line not yet ended is returned apart and not counted as read: a writer may be appending it now, and a line torn by a writer that died is ended by the next writer (`append_line` starts on a new line), then read and reported.
    """
    with path.open("rb") as fh:
        st = os.fstat(fh.fileno())
        if held is None or st.st_ino != held.ino or st.st_size < held.size:
            return None
        if held.size:
            fh.seek(max(0, held.size - _TAIL))
            if fh.read(min(_TAIL, held.size)) != held.tail:
                return None
        fh.seek(held.size)
        more = fh.read()
    end = more.rfind(b"\n") + 1
    return more[:end], held.size, more[end:]


def _whole(path: Path) -> tuple[bytes, int, bytes]:
    with path.open("rb") as fh:
        data = fh.read()
    end = data.rfind(b"\n") + 1
    return data[:end], 0, data[end:]


def stopped(path: Path, start: int, chunk: bytes, lines: int) -> Read:
    """Where a replay that read `chunk` from `start` stopped."""
    size = start + len(chunk)
    with path.open("rb") as fh:
        fh.seek(max(0, size - _TAIL))
        tail = fh.read(min(_TAIL, size))
        ino = os.fstat(fh.fileno()).st_ino
    return Read(ino, size, lines + chunk.count(b"\n"), tail)


def replay(root: Path) -> Evidence:
    """Every record of the quilt's evidence log, and one problem for each line skipped.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    Evidence
        In the order written, the first of two lines under one id standing for both. A replay reads on from where the last one stopped while the file is that one grown, and reads it whole otherwise; what it returns is a copy a later replay does not change, and a caller must not change it either.
    """
    path = log_path(root)
    if not path.is_file():
        return Evidence()
    held = _MEMO.get(str(path))
    found = grown(path, held[0] if held else None)
    if found is None or held is None:
        chunk, start, rest = _whole(path)
        value, lines = Evidence(), 0
    else:
        chunk, start, rest = found
        if not chunk and not rest.strip():
            return held[1]
        value, lines = held[1].copy(), held[0].lines
    _read(chunk.decode("utf-8"), value, lines)
    _MEMO[str(path)] = (stopped(path, start, chunk, lines), value)
    if rest.strip():
        # a last line with no line feed: read when it is a whole record, as a hand-written one is, and read again once ended
        try:
            value = value.copy()
            value.add(parse(json.loads(rest.decode("utf-8"))))
        except (ValueError, UnicodeDecodeError):
            pass
    return value


def _read(text: str, out: Evidence, before: int = 0) -> Evidence:
    """Parse lines of the log into `out`, numbering them from `before`; a line that fails `parse` is reported by its number and skipped."""
    for n, line in enumerate(text.splitlines(), before + 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            out.problems.append(f"{EVIDENCE_LOG}:{n}: not JSON ({exc.msg})")
            continue
        try:
            out.add(parse(raw))
        except ValueError as exc:
            out.problems.append(f"{EVIDENCE_LOG}:{n}: {exc}")
    return out


def parse(raw: Any) -> Record:
    """Read one record, checking it whole against its kind's shape.

    Parameters
    ----------
    raw : object
        A line of the log, parsed.

    Returns
    -------
    Record

    Raises
    ------
    ValueError
        Naming the first thing wrong with it.
    """
    if not isinstance(raw, dict):
        raise ValueError("not an object")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ValueError(f"{kind!r} is not a kind of record")
    rid = raw.get("id")
    if not isinstance(rid, str) or not ID.fullmatch(rid):
        raise ValueError(f"{rid!r} is not a record's id")
    at = raw.get("at")
    if not isinstance(at, str) or not AT.fullmatch(at):
        raise ValueError(f"{rid}: {at!r} is not a time")
    try:
        by = Who.from_dict(raw.get("by"))
        if kind in HANDS and by.kind not in HANDS[kind]:
            raise ValueError(f"a {kind} record is written by {' or '.join(HANDS[kind])}, not {by.kind}")
        on = _CHECKS[kind](raw, by)
    except ValueError as exc:
        raise ValueError(f"{rid}: {exc}") from None
    return Record(rid, kind, at, by, on, raw)


def _keys(raw: dict[str, Any], required: set[str], optional: frozenset[str] = frozenset()) -> None:
    """Refuse a key the kind does not have, and a key it needs that is missing."""
    have = set(raw) - _COMMON
    missing = required - have
    extra = have - required - optional
    if missing:
        raise ValueError(f"lacks {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"has {', '.join(sorted(extra))}, which this kind does not")


def _node_on(raw: dict[str, Any], kinds: tuple[str, ...] = _READ) -> Subject:
    on = Subject.from_dict(raw.get("on"), ("node",))
    if not is_node(on.name, *kinds):
        raise ValueError(f"{on.name} is not a {' or a '.join(kinds)}")
    return on


def _text(value: Any, what: str, *, empty: bool = True, most: int = 20000) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > most:
        raise ValueError(f"{what} is {'a' if empty else 'a non-empty'} string of at most {most} characters")
    return value


def _hash(value: Any, what: str) -> str:
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ValueError(f"{what} is not a hash")
    return value


def _document(value: Any, what: str, *, pages: bool) -> None:
    """A stored document of a work: `{ref, pdf | tex, pages?}`."""
    if not isinstance(value, dict):
        raise ValueError(f"{what} is an object")
    held = [k for k in ("pdf", "tex") if k in value]
    allowed = {"ref", *held, *(("pages",) if pages else ())}
    if len(held) != 1 or not set(value) <= allowed or "ref" not in value:
        raise ValueError(f"{what} names a reference and one of its documents, pdf or tex")
    if not is_work(value["ref"]):
        raise ValueError(f"{what}'s ref is not a reference's id")
    _hash(value[held[0]], f"{what}'s {held[0]}")
    if "pages" in value:
        # a node's pages as its file gives them, by the store's own rule
        said = pages_problem(value["pages"])
        if said:
            raise ValueError(f"{what}'s pages {said}")


def _digested(raw: dict[str, Any], by: Who) -> Subject:
    how = raw.get("how")
    _keys(raw, {"on", "how", "from", *(("was",) if how == "numbered" else ())})
    if how not in HOWS:
        raise ValueError(f"{how!r} is not how a node is made")
    if HOWS[how] != by.kind:
        raise ValueError(f"a node {how} is made by {HOWS[how]}, not {by.kind}")
    if how == "numbered":
        # numbers from the person's compile of the TeX source, filled into the text `was`
        _document(raw["from"], "from", pages=False)
        if "tex" not in raw["from"]:
            raise ValueError("a node is numbered from its work's TeX source")
        on = _node_on(raw)
        if _hash(raw["was"], "was") == on.hash:
            raise ValueError("was is the text before the numbers were filled, not the text after")
        return on
    if how == "written" and raw["from"] is None:
        return _node_on(raw)
    _document(raw["from"], "from", pages=True)
    return _node_on(raw)


def _compared(raw: dict[str, Any], by: Who) -> Subject:
    _keys(raw, {"on", "with"})
    _document(raw["with"], "with", pages=True)
    return _node_on(raw)


def _proposed(raw: dict[str, Any], by: Who) -> Subject:
    _keys(raw, {"on", "bytes", "why"})
    _text(raw["bytes"], "bytes", empty=False, most=1_000_000)
    _text(raw["why"], "why")
    return _node_on(raw)


def _declined(raw: dict[str, Any], by: Who) -> None:
    _keys(raw, {"proposal", "why"})
    if not isinstance(raw["proposal"], str) or not ID.fullmatch(raw["proposal"]):
        raise ValueError("proposal is not a record's id")
    _text(raw["why"], "why")
    return None


def _string_list(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{what} is a list of strings")
    return value


def _subjects(value: Any, what: str, kinds: tuple[str, ...]) -> list[Subject]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is a list")
    return [Subject.from_dict(v, kinds) for v in value]


def _lean(raw: dict[str, Any], by: Who) -> Subject:
    _keys(raw, {"on", "project", "files", "declarations", "assumed", "uses", "replay", "ok"}, frozenset({"errors"}))
    on = Subject.from_dict(raw["on"], ("node", "label"))
    project = raw["project"]
    if not isinstance(project, dict) or set(project) != {"root", "toolchain", "mathlib", "manifest"}:
        raise ValueError("project has root, toolchain, mathlib and manifest")
    for k in ("root", "toolchain", "mathlib"):
        _text(project[k], f"project's {k}", empty=False, most=400)
    _hash(project["manifest"], "project's manifest")
    files = raw["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError("files names every Lean file loom read, by hash")
    for path, digest in files.items():
        _text(path, "a file's path", empty=False, most=1000)
        _hash(digest, f"the hash of {path}")
    declarations = raw["declarations"]
    if not isinstance(declarations, list) or not declarations:
        raise ValueError("declarations is a non-empty list")
    for d in declarations:
        _declaration(d)
    _subjects(raw["assumed"], "assumed", ("node",))
    _subjects(raw["uses"], "uses", ("node", "label"))
    replay_ = raw["replay"]
    if not isinstance(replay_, dict) or set(replay_) != {"tool", "exit", "output"}:
        raise ValueError("replay has tool, exit and output")
    _text(replay_["tool"], "replay's tool", empty=False, most=200)
    if not isinstance(replay_["exit"], int) or isinstance(replay_["exit"], bool):
        raise ValueError("replay's exit is a number")
    _text(replay_["output"], "replay's output", most=200_000)
    if not isinstance(raw["ok"], bool):
        raise ValueError("ok is true or false")
    if "errors" in raw:
        _string_list(raw["errors"], "errors")
    return on


def _declaration(d: Any) -> None:
    """One declaration of a `lean` record (`docs/specs/evidence.md` §3.4)."""
    if not isinstance(d, dict) or not {"name", "kind", "role", "names", "statement", "axioms", "sorry"} <= set(d) <= {"name", "kind", "role", "names", "statement", "axioms", "sorry", "means", "shown"}:  # fmt: skip
        raise ValueError(
            "a declaration has name, kind, role, names, statement, axioms and sorry, and may have means and shown"
        )
    _text(d["name"], "a declaration's name", empty=False, most=1000)
    if d["kind"] not in ("theorem", "def", "axiom", "structure", "inductive", "instance", "abbrev", "opaque"):
        raise ValueError(f"{d['kind']!r} is not a kind of declaration")
    if d["role"] not in ("states", "supports"):
        raise ValueError("a declaration states a result or supports one")
    names = d["names"]
    if names is None:
        if d["role"] == "states":
            raise ValueError(f"{d['name']} states a result and names none")
    elif not isinstance(names, dict) or len(names) != 1 or next(iter(names)) not in ("node", "label"):
        raise ValueError(f"{d['name']} names a node or a label")
    else:
        problem = name_problem(*next(iter(names.items())))
        if problem:
            raise ValueError(problem)
    _hash(d["statement"], f"{d['name']}'s statement")
    _string_list(d["axioms"], f"{d['name']}'s axioms")
    if not isinstance(d["sorry"], bool):
        raise ValueError(f"{d['name']}'s sorry is true or false")
    if "means" in d:
        _string_list(d["means"], f"{d['name']}'s means")
    if d.get("shown") is not None:
        _text(d["shown"], f"{d['name']}'s shown", empty=False, most=20000)


def _attested(raw: dict[str, Any], by: Who) -> Subject:
    on = Subject.from_dict(raw.get("on"), ("node", "label", "macro"))
    if on.kind == "macro":
        _keys(raw, {"on"})
        return on
    _keys(raw, {"on", "lean", "statements", "closure", "rulings"})
    if on.kind == "node" and not is_node(on.name, "statement"):
        raise ValueError(f"{on.name} is not a statement")
    if not isinstance(raw["lean"], str) or not ID.fullmatch(raw["lean"]):
        raise ValueError("lean is not a record's id")
    statements = raw["statements"]
    if not isinstance(statements, dict) or not statements:
        raise ValueError("statements maps each stating declaration to its statement's hash")
    for name, digest in statements.items():
        _text(name, "a declaration's name", empty=False, most=1000)
        _hash(digest, f"{name}'s statement")
    _subjects(raw["closure"], "closure", ("node", "label"))
    rulings = raw["rulings"]
    if not isinstance(rulings, list) or not all(
        isinstance(r, dict) and set(r) == {"asked", "answer"} and all(isinstance(v, str) and v for v in r.values())
        for r in rulings
    ):
        raise ValueError("rulings is a list of {asked, answer}")
    return on


def _sought(raw: dict[str, Any], by: Who) -> Subject:
    _keys(raw, {"on", "from", "found"})
    _document(raw["from"], "from", pages=False)
    if raw["found"] is not False:
        raise ValueError("found is false: a result found is digested, not sought")
    return _node_on(raw, ("statement",))


def _mention(raw: dict[str, Any], by: Who) -> None:
    _keys(raw, {"block", "cites", "undo"})
    _block(raw["block"], "block")
    if not is_work(raw["cites"]):
        raise ValueError("cites is not a reference's id")
    if not isinstance(raw["undo"], bool):
        raise ValueError("undo is true or false")
    return None


def _block(value: Any, what: str) -> None:
    """A block of a person's document as a note names it: its key, the hash of its text, and its context (`records.locate.context_of`)."""
    if not isinstance(value, dict) or set(value) != {"key", "hash", "context"}:
        raise ValueError(f"{what} has key, hash and context")
    _text(value["key"], f"{what}'s key", empty=False, most=1000)
    _hash(value["hash"], f"{what}'s hash")
    if not isinstance(value["context"], dict):
        raise ValueError(f"{what}'s context is an object")


def _reading(raw: dict[str, Any], by: Who) -> Subject:
    """An agent's reading of a `lean` record in ordinary mathematics (`docs/specs/evidence.md` §3.8): each part names a declaration of the record, which `formal.reading.write` checks, and carries no Lean of its own."""
    _keys(raw, {"on", "lean", "parts", "difference"})
    on = Subject.from_dict(raw["on"], ("node", "label"))
    if on.kind == "node" and not is_node(on.name, "statement"):
        raise ValueError(f"{on.name} is not a statement")
    if not isinstance(raw["lean"], str) or not ID.fullmatch(raw["lean"]):
        raise ValueError("lean is not a record's id")
    parts = raw["parts"]
    if not isinstance(parts, list) or not parts or len(parts) > 100:
        raise ValueError("parts is a list of one to 100 parts")
    for p in parts:
        if not isinstance(p, dict) or set(p) != {"part", "draft", "declaration", "reading"}:
            raise ValueError("a part has part, draft, declaration and reading")
        _text(p["part"], "a part's name", most=40)
        _text(p["draft"], "a part's draft")
        _text(p["declaration"], "a part's declaration", empty=False, most=1000)
        _text(p["reading"], "a part's reading", empty=False)
    if len({p["part"] for p in parts}) != len(parts):
        raise ValueError("two parts have one name")
    if raw["difference"] is not None:
        _text(raw["difference"], "difference", empty=False)
    return on


_CHECKS: dict[str, Callable[[dict[str, Any], Who], Subject | None]] = {
    "digested": _digested,
    "compared": _compared,
    "proposed": _proposed,
    "declined": _declined,
    "lean": _lean,
    "attested": _attested,
    "sought": _sought,
    "mention": _mention,
    "reading": _reading,
}


def write(root: Path, kind: str, by: Who, *, on: Subject | None = None, **fields: Any) -> Record:
    """Append one record, its id drawn and its time stamped under the log's lock.

    A caller that must decide under the lock takes it first (`locked(log_path(root))`), which is reentrant within a thread, decides, then calls this.

    Parameters
    ----------
    root : Path
        The quilt.
    kind : str
        One of `KINDS`.
    by : Who
        Who acts.
    on : Subject, optional
        The text it is about; None for `declined` and `mention`.
    **fields
        The kind's own fields, as `docs/specs/evidence.md` §3 gives them.

    Returns
    -------
    Record
        As written.

    Raises
    ------
    EvidenceRefused
        When the record is not of its kind's shape; nothing was written.
    """
    line = _line(kind, by, on, fields)
    at = line["at"]
    path = log_path(root)
    # checked before the lock too, since taking it makes the log's file: a refusal writes nothing at all
    with locked(path):
        line["id"] = draw(f"ev-{at[:10]}-", replay(root).ids())
        record = parse(line)
        append_line(path, json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return record


def check(kind: str, by: Who, *, on: Subject | None = None, **fields: Any) -> None:
    """Whether `write` would take this record, writing nothing: an act that writes a file checks each record it will make first, so a record the log would refuse leaves the file as it was.

    Parameters
    ----------
    kind : str
        One of `KINDS`.
    by : Who
        Who acts.
    on : Subject, optional
        The text it is about.
    **fields
        The kind's own fields.

    Raises
    ------
    EvidenceRefused
        As `write` would, for a record not of its kind's shape.
    """
    _line(kind, by, on, fields)


def _line(kind: str, by: Who, on: Subject | None, fields: dict[str, Any]) -> dict[str, Any]:
    """A record's line as `write` appends it, its id still to draw, checked by its kind's rules (`parse`)."""
    at = stamp()
    line: dict[str, Any] = {"kind": kind, "at": at, "by": by.to_dict(), **fields}
    if on is not None:
        line["on"] = on.to_dict()
    try:
        parse({**line, "id": f"ev-{at[:10]}-0"})
    except ValueError as exc:
        raise EvidenceRefused(str(exc)) from None
    return line


def append_line(path: Path, text: str) -> None:
    """Append one line to a log, under its lock: on a line of its own even where a writer that died left the last one unended, which then reads as one bad line and not as the start of this one."""
    with path.open("a+b") as fh:
        fh.seek(0, os.SEEK_END)
        ended = True
        if fh.tell():
            fh.seek(-1, os.SEEK_END)
            ended = fh.read(1) == b"\n"
        fh.write((b"" if ended else b"\n") + text.encode("utf-8") + b"\n")
