"""The acts that write the evidence log's records (`docs/specs/evidence.md` §3): how a node was made, a person's match of it with its paper, an agent's correction and the person's taking or declining it, a person's own correction, and a person's attestation of a Lean statement.

This module is the one writer of these records, for this lane and the node store's alike: digesting and filling a stub write their `digested` through `digested`, and an agent's correction goes through `propose`, which alone decides whether it is written at once or waits. Each act holds the library's lock and then the evidence log's, the one order every writer of both takes, and decides under them from the texts now; a node it writes goes through the store's checks (`store.write_node`), and a refusal leaves the store and the log as they were.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.evidence.log import EvidenceRefused, Record, log_path, replay, write
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Here, LibraryWeb
from loom.locks import locked
from loom.paths import LIBRARY_LOCK

if TYPE_CHECKING:
    from collections.abc import Callable

    from loom.evidence.web import Web
    from loom.library.node import Node


class ActRefused(ValueError):
    """An act loom will not record, and why: `code` is the write API's (`author-only`, `agent-only`, `no-such-node`, `no-such-result`, `changed`, `stub`, `no-document`, `no-such-proposal`, `closed`, `no-lean`, `unchecked`, `refused`), `diagnostics` the store's checks' where a node would not be written."""

    def __init__(self, code: str, message: str, diagnostics: list[Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or []


@contextmanager
def _held(root: Path) -> Iterator[None]:
    """The library's lock and then the evidence log's, held for one act."""
    with locked(root / LIBRARY_LOCK), locked(log_path(root)):
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


def _write(root: Path, kind: str, by: Who, **fields: Any) -> Record:
    try:
        return write(root, kind, by, **fields)
    except EvidenceRefused as exc:
        raise ActRefused("refused", str(exc)) from None


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


def digested(root: Path, node: str, by: Who, how: str, source: dict[str, Any] | None) -> Record:
    """Record how a node's text now was made, after its file is written.

    Parameters
    ----------
    root : Path
        The quilt.
    node : str
        A statement's or a proof's id.
    by : Who
        Loom for `extracted`, an agent for `transcribed`, `read` and `corrected`, a person for `written`.
    how : str
        One of `log.HOWS`.
    source : dict or None
        The work's document read, `{ref, pdf | tex, pages?}`; None only for a node a person wrote from no document.

    Returns
    -------
    Record
        The `digested` record on the node's text now.

    Raises
    ------
    ActRefused
        `no-such-node`; `stub` for a node with no text; `refused` for a record not of its shape or from the wrong hand.
    """
    with _held(root):
        digest, found = _text(root, node)
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
    from loom.library.checks import check_file
    from loom.library.node import node_hash

    _only(by, "agent")
    name = f"{node}.node"
    with _held(root):
        digest, found = _text(root, node)
        if found.empty:
            raise ActRefused("stub", f"{node} has no text yet: fill it, do not correct it")
        new, problems = check_file(name, data, None)
        if new is None or problems:
            raise ActRefused("refused", f"the proposed file is not a valid {name}", problems)
        if node_hash(data) == digest:
            raise ActRefused("refused", "the proposed file is the node's file now")
        evidence = replay(root)
        compared = any(r.on is not None and r.on.hash == digest for r in evidence.about("node", node, of="compared"))
        if compared:
            return "proposed", _write(root, "proposed", by, on=Subject("node", node, digest), bytes=data.decode("utf-8"), why=why)  # fmt: skip
        source = document_of(root, new)
        if source is None:
            raise ActRefused("no-document", f"{node}'s work holds no document it was corrected from")
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
        `author-only`; `no-such-proposal`; `closed` when declined; `changed` when the node is no longer the text it corrects; `refused` when its file fails the library's checks now; `no-document`.
    """
    from loom.library.node import read_node

    _only(by, "person")
    with _held(root):
        found = _proposal(root, proposal)
        assert found.on is not None
        _shown(root, found.on.name, found.on.hash)
        new = read_node(str(found.get("bytes")).encode("utf-8"), f"{found.on.name}.node")
        if document_of(root, new) is None:
            raise ActRefused("no-document", f"{new.id}'s work holds no document to compare it with")
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
        _proposal(root, proposal)
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
        new = replace(found, body=body)
        source = document_of(root, new)
        if source is None:
            raise ActRefused("no-document", f"{node}'s work holds no document to correct it against")
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
        The `attested` record on the result's text now.

    Raises
    ------
    ActRefused
        `author-only`; `no-such-result` for no result with a lasting name at `here`; `no-lean` when no standing Lean record states it or Lean did not accept the statement; `changed` when `observation` is not the latest standing one on its text now, or a member of its closure resolves to nothing; `unchecked` naming each library node under it, or itself, not read and compared with its paper on its text now, and each citation nothing answers for.
    """
    from loom.evidence.status import closure_now, statements_of, states

    _only(by, "person")
    with _held(root):
        subject = web.subject(here)
        if subject is None:
            raise ActRefused(
                "no-such-result", f"{here.name} is no result with a lasting name; a draft's result needs a label"
            )
        evidence = replay(root)
        standing = [
            r
            for r in evidence.about(*subject.key, of="lean")
            if r.on is not None and r.on.hash == subject.hash and states(r, subject) and lean_now(r)
        ]
        if not standing:
            raise ActRefused("no-lean", "no Lean that loom ran states this text now")
        latest = standing[-1]
        if latest.id != observation:
            raise ActRefused("changed", "Lean has stated this result again since; read the latest statement")
        if not latest.get("ok") or (latest.get("replay") or {}).get("exit") != 0:
            raise ActRefused("no-lean", "Lean did not accept this statement")
        closure = closure_now(web, here, standing)
        gone = sorted(name for (_kind, name), digest in closure.items() if digest is None)
        if gone:
            raise ActRefused("changed", f"what it uses no longer reads as one text: {', '.join(gone)}")
        nodes = ([subject.name] if subject.kind == "node" else []) + [n for k, n in closure if k == "node"]
        compared = {r.on.hash for n in nodes for r in evidence.about("node", n, of="compared") if r.on is not None}
        short = [n for n in nodes if web.stub(Here("node", n)) is not False or web.resolve(("node", n), here) not in compared]  # fmt: skip
        cites = list(web.cited(here))
        if short or cites:
            said = [*(f"{n} is not read and compared with its paper" for n in short), *(f"its citation {c} names no node yet" for c in cites)]  # fmt: skip
            raise ActRefused("unchecked", "; ".join(said))
        rows = web.notation(here) or {}
        for name, digest in sorted(rows.items()):
            if not any(r.on is not None and r.on.hash == digest for r in evidence.about("macro", name, of="attested")):
                _write(root, "attested", by, on=Subject("macro", name, digest))
        members = [{kind: name, "hash": digest} for (kind, name), digest in sorted(closure.items())]
        return _write(root, "attested", by, on=subject, lean=latest.id, statements=statements_of(latest), closure=members, rulings=[])  # fmt: skip
