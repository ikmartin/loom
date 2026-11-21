"""The person's acts on a work beyond the intake (`library-views.md` §3.1): looking it up, editing its entry, deleting it, and restoring what a delete took.

A delete is never refused (the ruling on Open 5): the reference, its macros node, every node read from it and the proofs of those, and the notes on any of them, go in one act, and what it took is kept on this machine (`.loom/local/library-undo/<undo>/`) for its one undo, `restore`. The library's log records both, so gathering leaves a deleted key alone until the work is added again, and the evidence records naming the nodes' hashes stay, so whatever rested on them reads that it rests on something gone. The undo is on the disk before anything is removed, a delete cut short is finished from it by the next writer (`finish`), and a restore cut short finishes when it is run again.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from loom.library import log
from loom.library.entries import identifiers, read_entry
from loom.library.ids import STATEMENT, kind_of
from loom.library.node import SUFFIX, Node, file_name
from loom.library.store import NodeRefused, folder, read, remove_node, write_node
from loom.locks import locked
from loom.paths import LIBRARY_DELETING, LIBRARY_LOCK, LIBRARY_UNDO

#: The undos of the deletes this process has under way, which `finish` leaves to them.
_active: set[str] = set()


class ActRefused(Exception):
    """An act on a work loom will not carry out, with the code and status the write API answers."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _reference(root: Path, ref: str) -> Node:
    node = read(root, ref) if ref.endswith("-ref") else None
    if node is None:
        raise ActRefused("no-such-ref", f"the library has no work {ref}", 404)
    return node


def look_up(root: Path, ref: str, *, by: str, kind: str, http: Any = None) -> Node:
    """Look up, with the network, the identifier a reference states, and write the details found into its entry unless the person has edited it; recorded either way.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.
    by, kind : str
        Who asks.
    http : callable, optional
        The look-up's transport; tests give their own.

    Returns
    -------
    Node
        The reference as it stands after.

    Raises
    ------
    ActRefused
        `no-such-ref` (404), `no-identifier` (409) for an entry stating none, `unreachable` (409) when the service could not be asked.
    """
    from loom.refs.lookup import look_up as ask

    node = _reference(root, ref)
    entry = read_entry(node.body)
    stated = identifiers(entry.fields) if entry else []
    if entry is None or not stated:
        raise ActRefused("no-identifier", "its entry states no DOI, arXiv number or zbMATH number to look up")
    scheme, _, value = stated[0].partition(":")
    found = ask(f"{'arXiv' if scheme == 'arxiv' else scheme}:{value}", online=True, http=http)
    if found.state == "unreachable":
        raise ActRefused("unreachable", found.message or "the service could not be asked")
    ok = found.state == "found" and bool(found.entry)
    log.record(root, "looked-up", ref, by=by, kind=kind, identifier=stated[0], found=ok)
    if ok and not any(a["event"] == "edited" for a in log.replay(root).of(ref)):
        fields = {k: v for k, v in found.entry.items() if v and k != "ENTRYTYPE"}
        body = f"@{entry.type}{{{entry.key},\n" + "".join(f"  {k} = {{{v}}},\n" for k, v in fields.items()) + "}\n"
        node = replace(node, body=body)
        write_node(root, node)
    return node


def edit_entry(root: Path, ref: str, bibtex: str, *, by: str, kind: str) -> Node:
    """Replace a reference's entry with one the person wrote, which then no look-up or gathering rewrites (Open 4).

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.
    bibtex : str
        One BibTeX entry standing alone.
    by, kind : str
        Who edits it.

    Returns
    -------
    Node
        The reference as written.

    Raises
    ------
    ActRefused
        `no-such-ref` (404); `bad-entry` (400) for text that is not one entry standing alone; `key-taken` (409) for a key another reference has, ignoring case; each said of the entry and the work holding the key, never of loom's files.
    """
    from loom.library.body import entry_of
    from loom.library.entries import entry_fault
    from loom.library.intake import Library

    node = _reference(root, ref)
    holder = Library.read(root).holder(but=ref)
    fault = entry_fault(bibtex, holder=holder, where=" in the entry")
    if fault is not None:
        found = entry_of(bibtex)
        taken = found is not None and bool(found.key) and holder(found.key) is not None
        raise ActRefused("key-taken" if taken else "bad-entry", fault, 409 if taken else 400)
    written = replace(node, body=bibtex.strip() + "\n")
    try:
        write_node(root, written)
    except NodeRefused as exc:
        # what the entry itself gets wrong is said above; what is left is the store's, said of the entry
        raise ActRefused(
            "bad-entry", "loom could not keep this entry as the work's, by a fault of its own", 400
        ) from exc
    log.record(root, "edited", ref, by=by, kind=kind)
    return written


def _taken_with(root: Path, ref: str) -> list[str]:
    """The nodes a delete of `ref` takes: it, its macros node, every node read from it, and the proofs of those."""
    stem = ref.removesuffix("-ref")
    names: list[str] = []
    statements: set[str] = set()
    for path in sorted(folder(root).glob(f"*{SUFFIX}")) if folder(root).is_dir() else []:
        node_id = path.name.removesuffix(SUFFIX)
        text = path.read_text(encoding="utf-8", errors="replace")
        if node_id in (ref, f"{stem}-macros") or f'source = "{ref}"' in text:
            names.append(node_id)
            if kind_of(node_id) == STATEMENT:
                statements.add(node_id)
    for path in sorted(folder(root).glob(f"*-proof*{SUFFIX}")) if folder(root).is_dir() else []:
        node_id = path.name.removesuffix(SUFFIX)
        if node_id.rsplit("-proof", 1)[0] in statements and node_id not in names:
            names.append(node_id)
    return names


def delete(root: Path, ref: str, *, by: str, kind: str) -> str:
    """Delete a work as one act: its reference, its macros node, the nodes read from it and their proofs, and the notes on any of them; never refused.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.
    by, kind : str
        Who deletes it.

    Returns
    -------
    str
        The undo, which `restore` takes.

    Raises
    ------
    ActRefused
        `no-such-ref` (404).

    Notes
    -----
    Nothing is removed before the undo, the notes it will take among it, is on the disk and named as the delete under way (`LIBRARY_DELETING`); then the notes go, `deleted` is recorded, and the nodes go. A delete killed after that point is finished from its undo by the next act on the library or write of a node (`finish`), so the library is never left holding part of a work.
    """
    from loom.records import log as notes
    from loom.records.log import replay as replay_notes

    with locked(root / LIBRARY_LOCK):
        finish(root)
        node = _reference(root, ref)
        entry = read_entry(node.body)
        undos = root / LIBRARY_UNDO
        for aside in undos.glob(".u-*.tmp") if undos.is_dir() else []:
            shutil.rmtree(aside, ignore_errors=True)  # an undo a killed delete was writing, which nothing names
        undo = "u-" + secrets.token_hex(6)
        taken = _taken_with(root, ref)
        on = set(taken)
        records, _problems = replay_notes(root)
        ids = sorted({a.id for r in records for a in r.annotations if a.target_key in on})
        record = {"ref": ref, "key": entry.key if entry else None, "by": by, "kind": kind, "nodes": taken}
        _active.add(undo)
        try:
            # the undo is written under the annotation log's lock, so the notes it holds are the very ones that go
            notes.delete(root, ids, keep=lambda lines: _keep(root, undo, {**record, "notes": lines}))
            log.record(root, "deleted", ref, by=by, kind=kind, key=record["key"], undo=undo)
            for node_id in reversed(taken):
                remove_node(root, node_id)
            _done(root)
        finally:
            _active.discard(undo)
    return undo


def _keep(root: Path, undo: str, record: dict[str, Any]) -> None:
    """Write `undo` whole, flushed, before anything is removed: a copy of each node it takes and `undo.json`, made aside and renamed into place, then `LIBRARY_DELETING` naming it."""
    home = root / LIBRARY_UNDO / undo
    aside = home.with_name(f".{undo}.tmp")
    shutil.rmtree(aside, ignore_errors=True)
    aside.mkdir(parents=True)
    for node_id in record["nodes"]:
        _flushed(aside / file_name(node_id), (folder(root) / file_name(node_id)).read_bytes())
    _flushed(aside / "undo.json", (json.dumps(record, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    os.replace(aside, home)
    _flushed(root / LIBRARY_DELETING, f"{undo}\n".encode())


def _done(root: Path) -> None:
    """The delete under way is whole: `LIBRARY_DELETING` goes."""
    (root / LIBRARY_DELETING).unlink(missing_ok=True)
    _flush_dir(root / LIBRARY_UNDO)


def finish(root: Path) -> None:
    """Finish a delete its act left part done, from its undo: the notes it holds taken out of the annotation log where they are still there, `deleted` recorded where it is not, and each node it took removed where its file is still the one the undo copied.

    Called under the library's lock by every act on a work and every writer of a node (`store.write_nodes`, `remove_node`); a delete this process has under way is its own to finish.
    """
    from loom.records import log as notes

    pointer = root / LIBRARY_DELETING
    try:
        undo = pointer.read_text(encoding="utf-8").strip()
    except OSError:
        undo = ""
    if not undo or undo in _active:
        return
    home = root / LIBRARY_UNDO / undo
    try:
        record = json.loads((home / "undo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _done(root)
        return
    ref = str(record["ref"])
    notes.take_out(root, [str(line) for _place, line in record.get("notes", {}).get("lines", [])])
    if not any(a["event"] == "deleted" and a.get("undo") == undo for a in log.replay(root).of(ref)):
        by, kind = str(record.get("by") or "loom"), str(record.get("kind") or "loom")
        log.record(root, "deleted", ref, by=by, kind=kind, key=record.get("key"), undo=undo)
    for node_id in reversed(record["nodes"]):
        here = folder(root) / file_name(node_id)
        copy = home / file_name(node_id)
        if here.is_file() and copy.is_file() and here.read_bytes() == copy.read_bytes():
            here.unlink()
    _done(root)


def restore(root: Path, undo: str, *, by: str, kind: str) -> str:
    """Put back what one delete took, whole, and the notes each where it stood in the annotation log.

    Parameters
    ----------
    root : Path
        The quilt.
    undo : str
        What `delete` answered.
    by, kind : str
        Who restores it.

    Returns
    -------
    str
        The reference restored.

    Raises
    ------
    ActRefused
        `no-such-undo` (404), and for a second restore of one undo; `changed` (409) when a node of another text has taken a deleted node's place since, naming it.

    Notes
    -----
    Run again after it was cut short, it finishes: a node already back, a note already in the log and a `restored` already recorded are not put back twice. The undo goes last.
    """
    from loom.records import log as notes

    if not undo.startswith("u-") or not all(c in "0123456789abcdef" for c in undo[2:]):
        raise ActRefused("no-such-undo", f"{undo[:24]} names no delete", 404)
    home = root / LIBRARY_UNDO / undo
    with locked(root / LIBRARY_LOCK):
        finish(root)
        try:
            record = json.loads((home / "undo.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ActRefused("no-such-undo", f"{undo} names no delete, or it was restored already", 404) from None
        for node_id in record["nodes"]:
            here = folder(root) / file_name(node_id)
            if here.is_file() and here.read_bytes() != (home / here.name).read_bytes():
                raise ActRefused("changed", f"{node_id} has been written again since the delete")
        folder(root).mkdir(parents=True, exist_ok=True)
        for node_id in record["nodes"]:
            target = folder(root) / file_name(node_id)
            if target.is_file():
                continue  # put back by a restore cut short, as the check above found
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            _flushed(temporary, (home / target.name).read_bytes())
            os.replace(temporary, target)
        _flush_dir(folder(root))
        if isinstance(record.get("notes"), dict):
            notes.put_back(root, record["notes"])
        ref = str(record["ref"])
        if not any(a["event"] == "restored" and a.get("undo") == undo for a in log.replay(root).of(ref)):
            log.record(root, "restored", ref, by=by, kind=kind, undo=undo)
        (home / "undo.json").unlink()
        shutil.rmtree(home, ignore_errors=True)
    return ref


def _flushed(path: Path, data: bytes) -> None:
    """Write `data` to `path` and flush it to the disk."""
    with path.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _flush_dir(path: Path) -> None:
    """Flush a folder, so the renames and removals in it are on the disk; a system that cannot is passed over."""
    with contextlib.suppress(OSError):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
