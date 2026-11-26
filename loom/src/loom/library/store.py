"""The library's folder of nodes, `.loom/library/nodes/`: reading one node, and writing or removing one.

A write is of one node or several at once, checked first as a whole: each file against itself, the rest of the batch and the store as the index holds it, so two new results that point at each other go in together; and refused whole with every failure (`NodeRefused`), so loom never writes a file the checks would report. What a write breaks in other files, an anchor another body points at among them, is not refused: it is reported when those files are checked. A write holds the library's lock and looks at the folder once, removing the temporary files of writers killed midway; every file of the act is flushed to the disk before any is renamed into place (or with `new` linked into a place nothing holds, so two writers of one new id never both win), and a batch of several is recorded first, so an exception while placing takes out what it placed and a writer killed midway leaves a record the next writer rolls back: the library holds a whole batch or none of it. Every function here takes an id only once the grammar of §3 says it is one, and reads a file only by its exact name, so neither a path nor an id in the wrong case reaches a file it does not name.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import ids
from loom.library.body import entry_of, labels
from loom.library.checks import check_file, diagnostics
from loom.library.index import NodeIndex
from loom.library.node import SUFFIX, Node, NodeUnreadable, Problem, file_name, node_bytes, node_hash, read_node
from loom.locks import locked
from loom.paths import ANNOTATION_LOG, LEDGER, LIBRARY_ACT, LIBRARY_LOCK, LIBRARY_NODES, TAG_LOG
from loom.scan.alloc import git_escape, git_mentions, visible_locals
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


def exists(root: Path, node_id: str) -> bool:
    """Whether the library holds a file named exactly `node_id`: an id in another case, on a file system blind to case, is not it."""
    if ids.parse_id(node_id) is None or not (folder(root) / file_name(node_id)).is_file():
        return False
    return file_name(node_id) in os.listdir(folder(root))


def read(root: Path, node_id: str) -> Node | None:
    """The node `node_id` read from its file, or None when the library has no file of exactly that name.

    Parameters
    ----------
    root : Path
        The quilt.
    node_id : str
        The node's id; anything the grammar of §3 does not make one reads as absent.

    Returns
    -------
    Node or None
        The node as its file says it.

    Raises
    ------
    NodeUnreadable
        When the file fails a check reading it takes.
    """
    if ids.parse_id(node_id) is None:
        return None
    try:
        data = (folder(root) / file_name(node_id)).read_bytes()
    except FileNotFoundError:
        return None
    try:
        return read_node(data, file_name(node_id))
    except NodeUnreadable:
        # on a file system blind to case, `TQ-0003` opens `tq-0003.node`, which is another id's file
        if not exists(root, node_id):
            return None
        raise


class _Batch:
    """A `checks.StoreView` of the store as the index holds it with a batch of nodes over it, which a batch is checked against."""

    def __init__(self, index: NodeIndex, nodes: dict[str, Node]) -> None:
        self.index = index
        self.nodes = nodes

    def kind(self, node_id: str) -> str | None:
        return self.nodes[node_id].kind if node_id in self.nodes else self.index.kind(node_id)

    def empty(self, node_id: str) -> bool:
        return self.nodes[node_id].empty if node_id in self.nodes else self.index.empty(node_id)

    def anchors(self, node_id: str) -> frozenset[str]:
        if node_id in self.nodes:
            return frozenset(p.target for p in labels(self.nodes[node_id].body))
        return self.index.anchors(node_id)

    def keyed(self, key: str) -> frozenset[str]:
        folded = key.casefold()
        here = {
            n.id
            for n in self.nodes.values()
            if n.kind == ids.REFERENCE and (e := entry_of(n.body)) and e.key.casefold() == folded
        }
        return frozenset(here | (self.index.keyed(key) - set(self.nodes)))

    def source(self, node_id: str) -> str | None:
        return self.nodes[node_id].source if node_id in self.nodes else self.index.source(node_id)

    def macros(self, ref: str) -> str:
        mid = ids.macros_of(ref)
        return self.nodes[mid].body if mid in self.nodes else self.index.macros(ref)


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
    seen.append(git_mentions(root, rf"{git_escape(statement)}-proof[0-9A-Z]{{2}}"))
    return ids.mint_proof(statement, seen)


def write_node(root: Path, node: Node, *, new: bool = False) -> str:
    """Write a node's file, after checking it against itself and the library as it stands.

    Parameters
    ----------
    root : Path
        The quilt.
    node : Node
        The node, new or replacing the file of its id.
    new : bool, default False
        Refuse it when the library holds its id already, as a node minted for the first time is written.

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
    write_nodes : several at once, checked together.
    remove_node : take a node's file out.
    """
    return write_nodes(root, [node], new=new)[0]


def check_against(root: Path, node: Node) -> list[Diagnostic]:
    """What the library's checks find in `node`'s file against the library as it stands now, as `write_nodes` checks each file it writes (`check_file` over the index with the node laid over it), writing nothing: for an act that must know a write would be taken before it records anything."""
    with NodeIndex.open(root) as index:
        _n, found = check_file(file_name(node.id), node_bytes(node), _Batch(index, {node.id: node}))
    return found


def write_nodes(root: Path, nodes: Iterable[Node], *, new: bool = False) -> list[str]:
    """Write several nodes' files as one act, checked together: each against itself, the others and the library, so results that point at each other go in at once.

    Parameters
    ----------
    root : Path
        The quilt.
    nodes : iterable of Node
        The nodes, each new or replacing the file of its id; no id twice.
    new : bool, default False
        Refuse any whose id the library holds already.

    Returns
    -------
    list of str
        Each written file's hash, in the order given.

    Raises
    ------
    NodeRefused
        With every failure the files would have; nothing is written.
    """
    batch = list(nodes)
    found: list[Diagnostic] = []
    data: dict[str, bytes] = {}
    folded: dict[str, str] = {}
    for node in batch:
        name = file_name(node.id)
        problems: list[Problem] = []
        if ids.parse_id(node.id) is None:
            problems.append(Problem(3, f"{node.id!r} is not a node's id, as tq-00K3 is."))
        elif node.id in data:
            problems.append(Problem(3, f"{name} is written twice in one act."))
        elif (twin := folded.setdefault(node.id.casefold(), node.id)) != node.id:
            problems.append(
                Problem(
                    3,
                    f"{name}'s id differs from {twin}'s only in case, and a file system blind to case holds one file for both.",
                )
            )
        if len({a for a, _ in node.anchors}) != len(node.anchors):
            problems.append(Problem(5, f"{name}'s `anchors` gives one anchor two numbers."))
        try:
            data[node.id] = node_bytes(node)
        except UnicodeEncodeError:
            problems.append(
                Problem(1, f"{name} holds a character UTF-8 cannot write, such as half of a surrogate pair.")
            )
        if problems:
            found += diagnostics(name if ids.parse_id(node.id) else "?.node", node, problems)
    if found:
        raise NodeRefused(found)
    with locked(root / LIBRARY_LOCK):
        target = folder(root)
        _roll_back(root)
        _roll_forward(root)
        with NodeIndex.open(root) as index:
            # every writer holds this lock while its temporary file exists, so one seen now is a killed writer's
            for name in index.leftovers:
                with contextlib.suppress(OSError):
                    (target / name).unlink()
            view = _Batch(index, {n.id: n for n in batch})
            for node in batch:
                name = file_name(node.id)
                _n, said = check_file(name, data[node.id], view)
                found += said
                problems = []
                if same := [x for x in index.same_but_case(node.id) if x not in view.nodes]:
                    problems.append(
                        Problem(
                            3,
                            f"{name}'s id differs from {', '.join(same)}'s only in case, and a file system blind to case holds one file for both.",
                        )
                    )
                if new and (index.kind(node.id) is not None or (target / name).exists()):
                    problems.append(
                        Problem(3, f"{name} is in the library already, and this write makes only new nodes.")
                    )
                found += diagnostics(name, node, problems)
            if found:
                raise NodeRefused(found)
            target.mkdir(parents=True, exist_ok=True)
            names = [file_name(n.id) for n in batch]
            _place(root, target, {name: data[n.id] for name, n in zip(names, batch, strict=True)}, new=new)
            index.take(names)
    return [node_hash(data[n.id]) for n in batch]


def _place(root: Path, target: Path, files: dict[str, bytes], *, new: bool) -> None:
    """Put a checked batch in the folder as one act: every file written to a temporary one and flushed first, then each renamed into place (or with `new` linked where nothing is), then the folder flushed once.

    A batch of several is recorded first (`LIBRARY_ACT`: its names, which were new, and the bytes of those it replaces), so that an exception while placing takes out what this act placed, and a writer killed midway leaves a record the next writer rolls back (`_roll_back`); one file needs none, since its rename is the whole act.
    """
    temporary = {name: target / f".{name}.{os.getpid()}.tmp" for name in files}
    placed: list[str] = []
    try:
        for name, data in files.items():
            with temporary[name].open("wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        made = {name for name in files if not (target / name).exists()}
        if len(files) > 1:
            _record(root, target, list(files), made)
        try:
            for name in files:
                if new:
                    try:
                        os.link(temporary[name], target / name)
                    except FileExistsError:
                        raise NodeRefused(
                            diagnostics(
                                name,
                                None,
                                [
                                    Problem(
                                        3,
                                        f"{name} was written by another hand meanwhile, and this write makes only new nodes.",
                                    )
                                ],
                            )
                        ) from None
                else:
                    os.replace(temporary[name], target / name)
                placed.append(name)
        except BaseException:
            _undo(root, target, placed, made)
            raise
        _flush_folder(target)
        _forget(root)
    finally:
        for path in temporary.values():
            with contextlib.suppress(FileNotFoundError):
                path.unlink()


def _record(root: Path, target: Path, names: list[str], made: set[str]) -> None:
    """Write the act's record, flushed: its names, the ones it makes, and a copy of each file it replaces."""
    act = root / LIBRARY_ACT
    shutil.rmtree(act, ignore_errors=True)
    act.mkdir(parents=True)
    for name in names:
        if name not in made:
            with (act / name).open("wb") as fh:
                fh.write((target / name).read_bytes())
                fh.flush()
                os.fsync(fh.fileno())
    with (act / "act.json").open("w", encoding="utf-8") as fh:
        json.dump({"names": names, "made": sorted(made)}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    _flush_folder(act)


def _undo(root: Path, target: Path, placed: list[str], made: set[str]) -> None:
    """Take out what this act placed: a file it made is removed, one it replaced is put back from the act's record."""
    act = root / LIBRARY_ACT
    for name in placed:
        if name in made:
            with contextlib.suppress(FileNotFoundError):
                (target / name).unlink()
        elif (act / name).is_file():
            os.replace(act / name, target / name)
    _flush_folder(target)
    _forget(root)


def _forget(root: Path) -> None:
    shutil.rmtree(root / LIBRARY_ACT, ignore_errors=True)


def _roll_back(root: Path) -> list[str]:
    """Roll back a batch whose writer died while placing it, as its record says, so the library is as it was before that act; the names it touched, for the index to take again.

    Called by every writer under the library's lock, which the dead writer held, so a record found then is no live writer's.
    """
    act = root / LIBRARY_ACT
    try:
        record = json.loads((act / "act.json").read_text(encoding="utf-8"))
        names, made = list(record["names"]), set(record["made"])
    except (OSError, ValueError, KeyError, TypeError):
        # no record, or one cut short before it was flushed, when nothing of the act had been placed
        _forget(root)
        return []
    target = folder(root)
    for name in names:
        if not ids.parse_id(name.removesuffix(SUFFIX)) or not name.endswith(SUFFIX):
            continue
        if name in made:
            with contextlib.suppress(FileNotFoundError):
                (target / name).unlink()
        elif (act / name).is_file():
            os.replace(act / name, target / name)
    _flush_folder(target)
    _forget(root)
    return names


def _roll_forward(root: Path) -> None:
    """Finish a delete of a work that its act left part done (`acts.finish`), so no writer works on a library holding part of a deleted work."""
    from loom.library.acts import finish

    finish(root)


def _flush_folder(target: Path) -> None:
    """Flush the folder itself, so the renames are on the disk; a system that cannot is passed over."""
    with contextlib.suppress(OSError):
        fd = os.open(target, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


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
        Whether there was a file of exactly that name to remove.

    Raises
    ------
    ValueError
        When `node_id` is no node's id, which never reaches a path.
    """
    if ids.parse_id(node_id) is None:
        raise ValueError(f"{node_id!r} is not a node's id")
    with locked(root / LIBRARY_LOCK):
        _roll_back(root)
        _roll_forward(root)
        if not exists(root, node_id):
            return False
        (folder(root) / file_name(node_id)).unlink()
    return True
