"""The acts that write the evidence log's records (`docs/specs/evidence.md` §3): how a node was made, a person's match of it with its paper, an agent's correction and the person's taking or declining it, a person's own correction, and a person's attestation of a Lean statement.

This module is the one writer of these records, for this lane and the node store's alike: digesting and filling a stub write their `digested` through `digested`, and an agent's correction goes through `propose`, which alone decides whether it is written at once or waits. Each act holds the library's lock and then the evidence log's, the one order every writer of both takes, and decides under them from the texts now; a node it writes goes through the store's checks (`store.write_node`), and a refusal leaves the store and the log as they were.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.evidence.log import Evidence, EvidenceRefused, Record, log_path, replay, write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here, LibraryWeb
from loom.locks import locked
from loom.paths import LIBRARY_LOCK

if TYPE_CHECKING:
    from collections.abc import Callable

    from loom.evidence.web import Web
    from loom.library.node import Node
    from loom.scan.scan import ScanResult


class ActRefused(ValueError):
    """An act loom will not record, and why: `code` is the write API's (`author-only`, `agent-only`, `no-such-node`, `no-such-result`, `changed`, `stub`, `no-document`, `no-such-proposal`, `no-such-citation`, `ambiguous`, `closed`, `no-lean`, `unchecked`, `refused`), `diagnostics` the store's checks' where a node would not be written."""

    def __init__(self, code: str, message: str, diagnostics: list[Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or []


@contextmanager
def _held(root: Path) -> Iterator[None]:
    """The library's lock and then the evidence log's, held for one act; the log's only where it exists, since taking it makes it.

    Before the first record the acts, the only writers of what they decide on, are held apart by the library's lock alone, so a refused act makes no log and moves no generation.
    """
    log = log_path(root)
    with locked(root / LIBRARY_LOCK):
        if log.exists():
            with locked(log):
                yield
        else:
            yield


def _only(by: Who, kind: str) -> None:
    if by.kind != kind:
        code = "author-only" if kind == "person" else "agent-only"
        raise ActRefused(code, f"only {'a person' if kind == 'person' else 'an agent'} does this")


def _text(root: Path, node: str) -> tuple[str, Node]:
    """The node's hash and file now; refused when the library holds no statement or proof of that id."""
    got = LibraryWeb(root).file(node)
    if got is None:
        raise ActRefused("no-such-node", f"the library has no statement or proof {node}")
    return got


def _shown(root: Path, node: str, shown: str) -> Node:
    """The node now, when its text is still the one the person was shown; refused `changed` otherwise and `stub` for a text not read."""
    now, found = _text(root, node)
    if now != shown:
        raise ActRefused("changed", f"{node} has changed since it was shown")
    if found.empty:
        raise ActRefused("stub", f"{node} has no text yet: it is a stub")
    return found


def document_of(root: Path, found: Node) -> dict[str, Any] | None:
    """The work's document a node is read against, `{ref, pdf | tex, pages?}`: its reference's PDF, else its TeX source, with the node's pages; None when its work holds neither."""
    from loom.library.store import read

    work = read(root, found.source) if found.source else None
    if work is None:
        return None
    held = {"pdf": work.pdf} if work.pdf else {"tex": work.tex} if work.tex else None
    if held is None:
        return None
    return {"ref": work.id, **held, **({"pages": found.pages} if found.pages else {})}


def bare_citation(result: ScanResult, key: str, citekey: str) -> int | None:
    """Which of the citations in the block `key` names now (`web.blocks_named`, as the records read a key) is the first that cites `citekey` and names no result of it, counted from 0 among the block's citations; None where it makes none now, or where the key names no one block."""
    from loom.evidence.web import DraftWeb, blocks_named, citations_in
    from loom.scan.source import blank_comments

    named = blocks_named(result, key)
    if len(named) != 1:
        return None
    node = named[0]
    found = citations_in(blank_comments(DraftWeb(result).text(node)))
    return next((i for i, (k, locator) in enumerate(found) if k.casefold() == citekey.casefold() and not locator), None)  # fmt: skip


def mention(root: Path, result: ScanResult, key: str, ref: str, by: Who, *, undo: bool = False) -> Record:
    """The person's word that a citation of the work `ref` in the block at `key`, which names no result of it, is only a mention and rests on nothing (`mention`); `undo` takes an earlier word back.

    Parameters
    ----------
    root : Path
        The quilt.
    result : ScanResult
        The quilt as scanned now, in which the block is found and by which it is found again (`records.locate.context_of`).
    key : str
        The citing block, by its key as the records read one: its label key or its place key.
    ref : str
        The work cited, by its reference's id.
    by : Who
        A person.
    undo : bool, default False
        Take the word back.

    Returns
    -------
    Record
        The `mention` record: the block by its key, its hash and its context, and the reference.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-citation` where the block does not now cite that work without naming a result of it; `ambiguous` where the key is a label two copies of a draft carry, naming each by its place.
    """
    from loom.evidence.web import blocks_named
    from loom.library.entries import read_entry
    from loom.library.store import read
    from loom.records.locate import block_hash, context_of

    _only(by, "person")
    work = read(root, ref)
    entry = read_entry(work.body) if work is not None else None
    # the block as the records read a key: its place key once a label keys it, and a label two copies carry names neither alone
    named = blocks_named(result, key)
    if len(named) > 1:
        raise ActRefused("ambiguous", f"{key} names {len(named)} blocks, one in each copy of its label; name one by its place: {', '.join(sorted(n.key for n in named))}")  # fmt: skip
    node = named[0] if named else None
    if node is None or entry is None or bare_citation(result, node.key, entry.key) is None:
        raise ActRefused("no-such-citation", "that block does not cite that work without naming a result now; reload")
    key = node.key
    with _held(root):
        block = {"key": key, "hash": block_hash(result, key), "context": context_of(result, node)}
        return _write(root, "mention", by, block=block, cites=ref, undo=undo)


def unreadable(root: Path, node: str) -> str | None:
    """Why a node cannot be read or compared against its paper now, as `check` and a reading would refuse it (`document_of`): `no-source` where it names no work, `no-document` where its work holds neither PDF nor TeX source; None where it can be, or where the library holds no such node."""
    got = LibraryWeb(root).file(node)
    if got is None:
        return None
    if not got[1].source:
        return "no-source"
    return "no-document" if document_of(root, got[1]) is None else None


def _write(root: Path, kind: str, by: Who, **fields: Any) -> Record:
    try:
        return write(root, kind, by, **fields)
    except EvidenceRefused as exc:
        raise ActRefused("refused", str(exc)) from None


def _checked(kind: str, by: Who, **fields: Any) -> None:
    """A record the act will make, checked by the log's own rules (`log.check`) before anything is written: refused `refused` where the log would refuse it."""
    from loom.evidence.log import check

    try:
        check(kind, by, **fields)
    except EvidenceRefused as exc:
        raise ActRefused("refused", str(exc)) from None


#: Whoever takes a correction: the record a take makes is checked for its shape before it is filed, by whom it will be made is the person's, not known yet.
_TAKER = Who("person", "the person")


def _takeable(node: str, data: bytes, root: Path) -> tuple[Node, dict[str, Any]]:
    """A correction's file as `take` would write it, and the document it is compared with; refused as `take` refuses it: `refused` where the file fails the library's checks or the `compared` record taking it makes would be refused by the log, `stub` where it gives the node no text, `no-document` where its work holds no document.

    `propose` calls it before filing a correction and `take` before writing one, so a correction is filed only where it can be taken, and the record is checked before any file changes.
    """
    from loom.library.checks import check_file
    from loom.library.store import check_against

    name = f"{node}.node"
    new, problems = check_file(name, data, None)
    if new is None or problems:
        raise ActRefused("refused", f"the proposed file is not a valid {name}", problems)
    # and against the library as it stands, as the store will check it when it is written
    problems = check_against(root, new)
    if problems:
        raise ActRefused("refused", "the proposed file fails the library's checks against the library now", problems)
    if new.empty:
        raise ActRefused("stub", f"the proposed file gives {node} no text")
    document = document_of(root, new)
    if document is None:
        raise ActRefused("no-document", f"{node}'s work, as the proposed file names it, holds no document to compare it with")  # fmt: skip
    _checked("compared", _TAKER, on=Subject("node", node, _to_store(new)), **{"with": document})
    return new, document


def take_refusal(root: Path, proposal: str) -> ActRefused | None:
    """Why `take` would refuse an agent's correction now, by take's own checks, writing nothing; None where it would take it: for Review, which offers the take only then, a correction filed while it could be taken may stop being one, as when a result its file uses leaves the library."""
    try:
        found = _proposal(root, proposal)
        assert found.on is not None
        _shown(root, found.on.name, found.on.hash)
        _takeable(found.on.name, str(found.get("bytes")).encode("utf-8"), root)
    except ActRefused as exc:
        return exc
    return None


def _to_store(found: Node) -> str:
    """The hash a node will have once the store writes it, its whole file as `node_bytes` makes it."""
    from loom.library.node import node_bytes, node_hash

    return node_hash(node_bytes(found))


def _store(root: Path, found: Node) -> str:
    """Write a node through the store's checks; its new hash, or refused with the checks' diagnostics."""
    from loom.library.store import NodeRefused, write_node

    try:
        return write_node(root, found)
    except NodeRefused as exc:
        raise ActRefused("refused", "the node's file fails the library's checks", list(exc.diagnostics)) from None


def _matched(root: Path, found: Node, digest: str, by: Who) -> Record:
    """The person's `compared` on the node's text `digest`, against its work's document."""
    document = document_of(root, found)
    if document is None:
        raise ActRefused("no-document", f"{found.id}'s work holds no document to compare it with")
    return _write(root, "compared", by, on=Subject("node", found.id, digest), **{"with": document})


def digested(root: Path, node: str, written: str, by: Who, how: str, source: dict[str, Any] | None) -> Record:
    """Record how a node's text was made, by the hand that wrote it, on the text it wrote.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        A statement's or a proof's id.
    written : str
        The hash of the file the caller wrote (`store.write_node`'s answer): the record names that text, and only while the file on disk is still it.
    by : Who
        Loom for `extracted`, an agent for `transcribed`, `read` and `corrected`, a person for `written`.
    how : str
        One of `log.HOWS`.
    source : dict or None
        The work's document read, `{ref, pdf | tex, pages?}`; None only for a node a person wrote from no document.

    Returns
    -------
    Record
        The `digested` record on the text `written`.

    Raises
    ------
    ActRefused
        `no-such-node`; `changed` when the file on disk is no longer the text `written`, another hand having written it since; `stub` for a node with no text; `refused` for a record not of its shape or from the wrong hand.
    """
    with _held(root):
        digest, found = _text(root, node)
        if digest != written:
            raise ActRefused("changed", f"{node} is no longer the text that was written; another hand wrote it since")
        if found.empty:
            raise ActRefused("stub", f"{node} has no text yet: a stub is made by no one")
        return _write(root, "digested", by, on=Subject("node", node, digest), how=how, **{"from": source})


def check(root: Path, node: str, shown: str, by: Who) -> Record:
    """The person's record that a node's text matches its paper (`compared`), which the viewer words "matches the paper".

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        A statement's or a proof's id.
    shown : str
        The hash of the text the person compared.
    by : Who
        A person.

    Returns
    -------
    Record
        The `compared` record, against the work's document and the node's pages.

    Raises
    ------
    ActRefused
        `author-only` for anyone but a person; `no-such-node`; `changed` when the text is no longer `shown`; `stub`; `no-document` when its work holds no document.
    """
    _only(by, "person")
    with _held(root):
        found = _shown(root, node, shown)
        return _matched(root, found, shown, by)


def propose(root: Path, node: str, data: bytes, by: Who, why: str) -> tuple[str, Record]:
    """An agent's correction of a node: written at once where no person has compared its text now, else filed for the person to take or decline.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        A statement's or a proof's id.
    data : bytes
        The node's whole new file.
    by : Who
        An agent.
    why : str
        The agent's reason.

    Returns
    -------
    tuple of (str, Record)
        `written` and the `digested` record (how `corrected`) on the new text, or `proposed` and the `proposed` record on the text it corrects.

    Raises
    ------
    ActRefused
        `agent-only`; `no-such-node`; `stub` (a stub is filled, not corrected); `refused` for a file that does not read as this node or fails the library's checks.
    """
    from loom.library.node import node_hash

    _only(by, "agent")
    with _held(root):
        digest, found = _text(root, node)
        if found.empty:
            raise ActRefused("stub", f"{node} has no text yet: fill it, do not correct it")
        # whatever taking it would refuse is refused now, by take's own check, so a correction filed is one the person can take
        new, source = _takeable(node, data, root)
        if node_hash(data) == digest:
            raise ActRefused("refused", "the proposed file is the node's file now")
        evidence = replay(root)
        compared = any(r.on is not None and r.on.hash == digest for r in evidence.about("node", node, of="compared"))
        if compared:
            return "proposed", _write(root, "proposed", by, on=Subject("node", node, digest), bytes=data.decode("utf-8"), why=why)  # fmt: skip
        _checked("digested", by, on=Subject("node", node, _to_store(new)), how="corrected", **{"from": source})
        written = _store(root, new)
        return "written", _write(root, "digested", by, on=Subject("node", node, written), how="corrected", **{"from": source})  # fmt: skip


def _proposal(root: Path, proposal: str) -> Record:
    """An open proposal by its id; refused when there is none or it is closed."""
    evidence = replay(root)
    found = next((r for r in evidence.of_kind("proposed") if r.id == proposal), None)
    if found is None or found.on is None:
        raise ActRefused("no-such-proposal", f"no correction {proposal} was proposed")
    if evidence.declined(proposal) is not None:
        raise ActRefused("closed", f"the correction {proposal} was declined")
    return found


def take(root: Path, proposal: str, by: Who) -> Record:
    """The person takes an agent's correction: its file is written, and their match with the paper recorded on the new text, since they read it against the text they had compared.

    Parameters
    ----------
    root : Path
        The quilt.
    proposal : str
        The `proposed` record's id.
    by : Who
        A person.

    Returns
    -------
    Record
        The `compared` record on the new text.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-proposal`; `closed` when declined; `changed` when the node is no longer the text it corrects; `refused` when its bytes do not read as that node's file, or the file fails the library's checks now; `no-document`.
    """

    _only(by, "person")
    with _held(root):
        found = _proposal(root, proposal)
        assert found.on is not None
        _shown(root, found.on.name, found.on.hash)
        new, _document = _takeable(found.on.name, str(found.get("bytes")).encode("utf-8"), root)
        written = _store(root, new)
        return _matched(root, new, written, by)


def decline(root: Path, proposal: str, by: Who, why: str = "") -> Record:
    """The person declines an agent's correction; the text they compared stands.

    Parameters
    ----------
    root : Path
        The quilt.
    proposal : str
        The `proposed` record's id.
    by : Who
        A person.
    why : str, default ''
        Their reason, if they give one.

    Returns
    -------
    Record
        The `declined` record.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-proposal`; `closed` when declined already.
    """
    _only(by, "person")
    with _held(root):
        found = _proposal(root, proposal)
        assert found.on is not None
        # decided under the lock against the text the correction was made against: one taken, or overtaken, is not there to decline
        _shown(root, found.on.name, found.on.hash)
        return _write(root, "declined", by, proposal=proposal, why=why)


def correct(root: Path, node: str, shown: str, body: str, by: Who) -> Record:
    """The person corrects a node's text by hand, against its paper: the new body is written through the library's checks, recorded as theirs (`digested`, how `written`), and matched with the paper at once, since they have just read it there.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        A statement's or a proof's id.
    shown : str
        The hash of the text the person corrected.
    body : str
        The node's new body; its header is kept.
    by : Who
        A person.

    Returns
    -------
    Record
        The `compared` record on the new text.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-node`; `changed`; `stub`; `no-document`; `refused` with the checks' diagnostics.
    """
    _only(by, "person")
    with _held(root):
        found = _shown(root, node, shown)
        if not body.strip():
            raise ActRefused("stub", f"a correction gives {node} a text; one of none would make it a stub")
        new = replace(found, body=body)
        source = document_of(root, new)
        if source is None:
            raise ActRefused("no-document", f"{node}'s work holds no document to correct it against")
        # both records made and checked before the file changes, so one the log would refuse leaves the store as it was
        will = Subject("node", node, _to_store(new))
        _checked("digested", by, on=will, how="written", **{"from": source})
        _checked("compared", by, on=will, **{"with": source})
        written = _store(root, new)
        _write(root, "digested", by, on=Subject("node", node, written), how="written", **{"from": source})
        return _matched(root, new, written, by)


def attest(
    root: Path, web: Web, here: Here, observation: str, by: Who, *, lean_now: Callable[[Record], bool]
) -> Record:
    """The person's word that the Lean statement of the result at `here` says what the result says: the statements of the Lean record `observation`, the closure as it reads now, and each row of its notation not yet attested in its definition now.

    Parameters
    ----------
    root : Path
        The quilt.
    web : Web
        The texts now, the drafts' and the library's (`Joined`).
    here : Here
        A draft's block or a node.
    observation : str
        The `lean` record whose statements the person read: the latest standing one on the result's text now.
    by : Who
        A person.
    lean_now : callable
        Whether a `lean` record's Lean is unchanged since loom ran it (`status.files_unchanged`).

    Returns
    -------
    Record
        The `attested` record on the result's text now; the one already there, and nothing written, where the person gave the same word on the same text, statements and closure before.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-result` for no result with a lasting name at `here`; `no-lean` when no standing Lean record states it or Lean did not accept the statement; `changed` when `observation` is not the latest standing one on its text now, or a member of its closure resolves to nothing; `unchecked` naming each library node under it, or itself, not read and compared with its paper on its text now, and each citation nothing answers for.
    """
    from loom.evidence.status import statements_of

    _only(by, "person")
    with _held(root):
        evidence = replay(root)
        found = _attestable(evidence, web, here, lean_now, observation)
        if isinstance(found, Unattestable):
            raise ActRefused(found.code, found.message)
        subject, latest, closure = found
        rows = web.notation(here) or {}
        notation = [Subject("macro", name, digest) for name, digest in sorted(rows.items()) if not any(r.on is not None and r.on.hash == digest for r in evidence.about("macro", name, of="attested"))]  # fmt: skip
        members = [{kind: name, "hash": digest} for (kind, name), digest in sorted(closure.items())]
        statements = statements_of(latest)
        # the same word given again is the one already given: the latest of these statements on this text, which status reads, over the same closure
        given = [a for a in evidence.about(*subject.key, of="attested") if a.by.kind == "person" and a.on == subject and dict(a.get("statements", {})) == statements]  # fmt: skip
        again = bool(given) and _members(given[-1]) == _members_of(members)
        word = {"on": subject, "lean": latest.id, "statements": statements, "closure": members, "rulings": []}
        # every record checked before any is written, so one the log would refuse writes none
        for row in notation:
            _checked("attested", by, on=row)
        if not again:
            _checked("attested", by, **word)
        for row in notation:
            _write(root, "attested", by, on=row)
        return given[-1] if again else _write(root, "attested", by, **word)


@dataclass(frozen=True)
class Unattestable:
    """Why attesting a result would be refused, beyond who asks (`attest_refusal`): the code and message `attest` raises, and what stands in its way, each member of its closure that reads as no one text (`gone`), each node under it, or itself, a stub or not read (`unread`) or not compared on its text now (`unchecked`), and each citation nothing answers for (`cites`)."""

    code: str
    message: str
    gone: tuple[tuple[str, str], ...] = ()
    unread: tuple[str, ...] = ()
    unchecked: tuple[str, ...] = ()
    cites: tuple[str, ...] = ()


def attest_refusal(evidence: Evidence, web: Web, here: Here, lean_now: Callable[[Record], bool]) -> Unattestable | None:
    """Why `attest` would refuse the person's word on the result at `here` now, over the latest Lean record standing on its text; None where it would take it.

    Parameters
    ----------
    evidence : Evidence
        The replayed evidence log.
    web : Web
        The texts now, as `attest` reads them.
    here : Here
        A draft's block or a node.
    lean_now : callable
        Whether a `lean` record's Lean is unchanged since loom ran it.

    Returns
    -------
    Unattestable or None
        What `attest` checks, by the same function, so a list that offers an attestation only where this is None offers nothing it refuses.
    """
    found = _attestable(evidence, web, here, lean_now)
    return found if isinstance(found, Unattestable) else None


def _attestable(
    evidence: Evidence, web: Web, here: Here, lean_now: Callable[[Record], bool], observation: str | None = None
) -> tuple[Subject, Record, dict[tuple[str, str], str | None]] | Unattestable:
    """The result's subject, its latest standing Lean record and its closure now, where `attest` would take a word on it; else why not.

    `observation`, where given, is the record the person read, which must be the latest.
    """
    from loom.evidence.status import closure_now, states

    subject = web.subject(here)
    if subject is None:
        return Unattestable("no-such-result", f"{here.name} is no result with a lasting name; a draft's result needs a label")  # fmt: skip
    standing = [
        r
        for r in evidence.about(*subject.key, of="lean")
        if r.on is not None and r.on.hash == subject.hash and states(r, subject) and lean_now(r)
    ]
    if not standing:
        return Unattestable("no-lean", "no Lean that loom ran states this text now")
    latest = standing[-1]
    if observation is not None and latest.id != observation:
        return Unattestable("changed", "Lean has stated this result again since; read the latest statement")
    if not latest.get("ok") or (latest.get("replay") or {}).get("exit") != 0:
        return Unattestable("no-lean", "Lean did not accept this statement")
    closure = closure_now(web, here, standing)
    gone = tuple(sorted(key for key, digest in closure.items() if digest is None))
    if gone:
        return Unattestable("changed", f"what it uses no longer reads as one text: {', '.join(n for _, n in gone)}", gone=gone)  # fmt: skip
    nodes = ([subject.name] if subject.kind == "node" else []) + [n for k, n in closure if k == "node"]
    compared = {r.on.hash for n in nodes for r in evidence.about("node", n, of="compared") if r.on is not None}
    unread = tuple(n for n in nodes if web.stub(Here("node", n)) is not False)
    unchecked = tuple(n for n in nodes if n not in unread and web.resolve(("node", n), here) not in compared)
    cites = tuple(web.cited(here))
    if unread or unchecked or cites:
        said = [*(f"{n} is not read and compared with its paper" for n in (*unread, *unchecked)), *(f"its citation {c} names no node yet" for c in cites)]  # fmt: skip
        return Unattestable("unchecked", "; ".join(said), unread=unread, unchecked=unchecked, cites=cites)
    return subject, latest, closure


def _members_of(raw: list[dict[str, Any]]) -> set[tuple[tuple[str, str], str]]:
    out = set()
    for m in raw:
        s = Subject.from_dict(m, ("node", "label"))
        out.add((s.key, s.hash))
    return out


def _members(record: Record) -> set[tuple[tuple[str, str], str]]:
    return _members_of(list(record.get("closure", [])))
