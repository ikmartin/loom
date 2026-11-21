"""The library's folder of nodes, `.loom/library/nodes/`: reading one node, and writing or removing one.

A write is checked first, the file against itself and against the store as the index holds it, and refused with every failure (`NodeRefused`), so loom never writes a file the checks would report. What a write breaks in other files, an anchor another body points at among them, is not refused: it is reported when those files are checked. A write holds the library's lock, so two writers see each other's nodes, and lands by renaming a whole file into place.
"""

from __future__ import annotations

import contextlib
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import ids
from loom.library.checks import check_file, diagnostics
from loom.library.index import NodeIndex
from loom.library.node import SUFFIX, Node, Problem, file_name, node_bytes, node_hash, read_node
from loom.locks import locked
from loom.paths import ANNOTATION_LOG, LEDGER, LIBRARY_LOCK, LIBRARY_NODES, TAG_LOG
from loom.scan.alloc import git_mentions, visible_locals
from loom.scan.model import Diagnostic

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


class NodeRefused(ValueError):
    """A write the checks refuse, with every failure they found."""

    def __init__(self, found: list[Diagnostic]) -> None:
        super().__init__(" ".join(d.message for d in found))
        self.diagnostics = found


def folder(root: Path) -> Path:
    """The quilt's folder of nodes, which may not exist yet."""
    return root / LIBRARY_NODES


def node_ids(root: Path) -> list[str]:
    """The id of every node file in the quilt's library, in order, whether or not it reads."""
    try:
        return sorted(
            p.name.removesuffix(SUFFIX) for p in folder(root).iterdir() if p.name.endswith(SUFFIX) and p.is_file()
        )
    except FileNotFoundError:
        return []


def read(root: Path, node_id: str) -> Node | None:
    """The node `node_id` read from its file, or None when the library has no such file.

    Parameters
    ----------
    root : Path
        The quilt.
    node_id : str
        The node's id.

    Returns
    -------
    Node or None
        The node as its file says it.

    Raises
    ------
    NodeUnreadable
        When the file fails a check reading it takes.
    """
    try:
        data = (folder(root) / file_name(node_id)).read_bytes()
    except FileNotFoundError:
        return None
    return read_node(data, file_name(node_id))


def next_stem(result: ScanResult) -> str:
    """A new stem for a library node: one past the largest local part anything in the quilt names under its prefix, the author's sources, records, the library and git history among them, as `loom id --next` draws.

    A writer draws it under the id lock (`loom.locks`, `paths.ID_LOCK`), held from before its scan, as the commands that draw an author's id do.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan.

    Returns
    -------
    str
        `prefix-XXXX`.
    """
    prefix = result.quilt.config.prefix
    return ids.mint_stem(prefix, [f"{prefix}-{local}" for local in visible_locals(result, prefix)])


def next_proof(root: Path, statement: str) -> str:
    """A new proof's id under `statement`: one past the largest proof number the library's files, the tag log, the annotation log, the acceptance ledger and git history name under it, so a number seen anywhere is not given again.

    Parameters
    ----------
    root : Path
        The quilt.
    statement : str
        The statement's id.

    Returns
    -------
    str
        `statement-proofNN`.
    """
    seen = [file_name(n) for n in node_ids(root)]
    for record in (TAG_LOG, ANNOTATION_LOG, LEDGER):
        with contextlib.suppress(FileNotFoundError):
            seen.append((root / record).read_text(encoding="utf-8", errors="replace"))
    seen.append(git_mentions(root, rf"{re.escape(statement)}-proof[0-9A-Z]{{2}}"))
    return ids.mint_proof(statement, seen)


def write_node(root: Path, node: Node) -> str:
    """Write a node's file, after checking it against itself and the library as it stands.

    Parameters
    ----------
    root : Path
        The quilt.
    node : Node
        The node, new or replacing the file of its id.

    Returns
    -------
    str
        The written file's hash.

    Raises
    ------
    NodeRefused
        With every failure of the eleven checks the file would have, and an id another node's equals ignoring case; nothing is written.

    See Also
    --------
    remove_node : take a node's file out.
    """
    data = node_bytes(node)
    name = node.file_name
    with locked(root / LIBRARY_LOCK):
        with NodeIndex.open(root) as index:
            _node, found = check_file(name, data, index)
            same = index.same_but_case(node.id)
            if same:
                found += diagnostics(
                    name,
                    node,
                    [
                        Problem(
                            3,
                            f"{name}'s id differs from {', '.join(same)}'s only in case, and a file system blind to case holds one file for both.",
                        )
                    ],
                )
            if found:
                raise NodeRefused(found)
            target = folder(root)
            target.mkdir(parents=True, exist_ok=True)
            temporary = target / f".{name}.{os.getpid()}.tmp"
            try:
                temporary.write_bytes(data)
                os.replace(temporary, target / name)
            finally:
                with contextlib.suppress(FileNotFoundError):
                    temporary.unlink()
            index.take([name])
    return node_hash(data)


def remove_node(root: Path, node_id: str) -> bool:
    """Take a node's file out of the library; what used it says so when the store is next checked, and the index forgets it when next opened.

    Parameters
    ----------
    root : Path
        The quilt.
    node_id : str
        The node's id.

    Returns
    -------
    bool
        Whether there was a file to remove.
    """
    with locked(root / LIBRARY_LOCK):
        try:
            (folder(root) / file_name(node_id)).unlink()
        except FileNotFoundError:
            return False
    return True
