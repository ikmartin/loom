"""The person's acts on a work beyond the intake (`library-views.md` §3.1): looking it up, editing its entry, deleting it, and restoring what a delete took.

A delete is never refused (the ruling on Open 5): the reference, its macros node, every node read from it and the proofs of those, and the notes on any of them, go in one act, and what it took is kept on this machine (`.loom/local/library-undo/<undo>/`) for its one undo, `restore`. The library's log records both, so gathering leaves a deleted key alone until the work is added again, and the evidence records naming the nodes' hashes stay, so whatever rested on them reads that it rests on something gone.
"""

from __future__ import annotations

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
from loom.library.node import SUFFIX, Node
from loom.library.store import NodeRefused, folder, read, remove_node, write_node
from loom.locks import locked
from loom.paths import LIBRARY_LOCK, LIBRARY_UNDO


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
    found = ask(f"{'arXiv' if scheme == 'arxiv' else scheme}:{value}", {}, online=True, http=http)
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
        `no-such-ref` (404); `bad-entry` (400) for text that is not one entry standing alone; `key-taken` (409) for a key another reference has, ignoring case.
    """
    node = _reference(root, ref)
    if read_entry(bibtex) is None:
        raise ActRefused("bad-entry", "this is not one BibTeX entry with a key", 400)
    try:
        written = replace(node, body=bibtex.strip() + "\n")
        write_node(root, written)
    except NodeRefused as exc:
        clash = any(d.code == "loom:node-bibtex" and "is also" in d.message for d in exc.diagnostics)
        raise ActRefused("key-taken" if clash else "bad-entry", str(exc), 409 if clash else 400) from exc
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
    """
    from loom.records import log as notes
    from loom.records.log import replay as replay_notes

    with locked(root / LIBRARY_LOCK):
        node = _reference(root, ref)
        entry = read_entry(node.body)
        undo = "u-" + secrets.token_hex(6)
        home = root / LIBRARY_UNDO / undo
        (home / "nodes").mkdir(parents=True)
        taken = _taken_with(root, ref)
        for node_id in taken:
            shutil.copyfile(folder(root) / f"{node_id}{SUFFIX}", home / "nodes" / f"{node_id}{SUFFIX}")
        on = set(taken)
        records, _problems = replay_notes(root)
        ids = sorted({a.id for r in records for a in r.annotations if a.target_key in on})
        removed = notes.delete(root, ids) if ids else []
        (home / "undo.json").write_text(
            json.dumps({"ref": ref, "nodes": taken, "notes": removed}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        for node_id in reversed(taken):
            remove_node(root, node_id)
        log.record(root, "deleted", ref, by=by, kind=kind, key=entry.key if entry else None, undo=undo)
    return undo


def restore(root: Path, undo: str, *, by: str, kind: str) -> str:
    """Put back what one delete took, whole.

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
        `no-such-undo` (404); `changed` (409) when a node of another text has taken a deleted node's place since, naming it.
    """
    from loom.records import log as notes

    if not undo.startswith("u-") or not all(c in "0123456789abcdef" for c in undo[2:]):
        raise ActRefused("no-such-undo", f"{undo[:24]} names no delete", 404)
    home = root / LIBRARY_UNDO / undo
    if not (home / "undo.json").is_file():
        raise ActRefused("no-such-undo", f"{undo} names no delete, or it was restored already", 404)
    with locked(root / LIBRARY_LOCK):
        record = json.loads((home / "undo.json").read_text(encoding="utf-8"))
        for node_id in record["nodes"]:
            here = folder(root) / f"{node_id}{SUFFIX}"
            if here.is_file() and here.read_bytes() != (home / "nodes" / here.name).read_bytes():
                raise ActRefused("changed", f"{node_id} has been written again since the delete")
        folder(root).mkdir(parents=True, exist_ok=True)
        for node_id in record["nodes"]:
            target = folder(root) / f"{node_id}{SUFFIX}"
            temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
            shutil.copyfile(home / "nodes" / target.name, temporary)
            os.replace(temporary, target)
        if record.get("notes"):
            notes.restore(root, record["notes"])
        log.record(root, "restored", record["ref"], by=by, kind=kind, undo=undo)
        shutil.rmtree(home, ignore_errors=True)
    return str(record["ref"])
