"""The eleven checks of docs/specs/nodes.md §11, each failure a diagnostic of its own code (docs/specs/diagnostics.md, "The library's nodes").

A file is checked in three layers: reading it (`node.read_node`, checks 1 to 5), what it says of itself (`node_problems`: its own part of checks 7 to 11), and what it says of the rest of the store (`store_problems`: checks 6, 7, 8 and 9 against a `StoreView`). A whole store is checked by `check_store`; a write checks one file against the index (`store.write_node`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from loom.library import ids
from loom.library.body import (
    ARGUMENTS,
    Item,
    Pointer,
    Wrapper,
    conditional,
    entry_of,
    is_conditional,
    labels,
    macros_items,
    pointers,
    unknown,
    wrapped,
    wrappers,
)
from loom.library.node import SUFFIX, Node, NodeUnreadable, Problem, body_start, read_node
from loom.paths import LIBRARY_NODES
from loom.scan.model import Diagnostic, Location

#: The code each check's failures are said under, by its number in §11.
CODES = {
    1: "loom:node-unreadable",
    2: "loom:node-schema",
    3: "loom:node-id",
    4: "loom:node-taxon",
    5: "loom:node-key",
    6: "loom:node-parent",
    7: "loom:node-edge",
    8: "loom:node-body-ref",
    9: "loom:node-bibtex",
    10: "loom:node-macros",
    11: "loom:node-incomplete",
}
#: The entry types that are not entries: a reference's body is one entry standing alone.
NOT_ENTRIES = frozenset({"string", "preamble", "comment"})


class StoreView(Protocol):
    """What checking one node asks of the rest of the store."""

    def kind(self, node_id: str) -> str | None:
        """The kind of the node `node_id` when its file is in the store and readable, else None."""
        ...

    def empty(self, node_id: str) -> bool:
        """Whether the node's body holds nothing: a stub's or a pointer's."""
        ...

    def anchors(self, node_id: str) -> frozenset[str]:
        """The anchors the node's body defines."""
        ...

    def keyed(self, key: str) -> frozenset[str]:
        """The references whose entry's key is `key`, compared ignoring case."""
        ...

    def source(self, node_id: str) -> str | None:
        """The node's `source`, or None when it has none or is not in the store."""
        ...

    def macros(self, ref: str) -> str:
        """The body of the reference's macros node, '' when it has none."""
        ...


@dataclass
class MemoryView:
    """A `StoreView` over nodes in hand: a whole store being checked, or a test's few."""

    nodes: dict[str, Node] = field(default_factory=dict)
    _anchors: dict[str, frozenset[str]] = field(default_factory=dict)
    _keys: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def of(cls, nodes: Iterable[Node]) -> MemoryView:
        view = cls()
        for node in nodes:
            view.nodes[node.id] = node
            view._anchors[node.id] = frozenset(p.target for p in labels(node.body))
            if node.kind == ids.REFERENCE and (entry := entry_of(node.body)) and entry.key:
                view._keys.setdefault(entry.key.casefold(), set()).add(node.id)
        return view

    def kind(self, node_id: str) -> str | None:
        node = self.nodes.get(node_id)
        return node.kind if node else None

    def empty(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        return node is None or node.empty

    def anchors(self, node_id: str) -> frozenset[str]:
        return self._anchors.get(node_id, frozenset())

    def keyed(self, key: str) -> frozenset[str]:
        return frozenset(self._keys.get(key.casefold(), ()))

    def source(self, node_id: str) -> str | None:
        node = self.nodes.get(node_id)
        return node.source if node else None

    def macros(self, ref: str) -> str:
        node = self.nodes.get(ids.macros_of(ref))
        return node.body if node else ""


def node_problems(node: Node, given: dict[str, Wrapper] | None = None) -> list[Problem]:
    """What a readable node gets wrong about itself: its lists' order (7), what its body points at and defines (8), its entry (9), its macros (10), and what a stub or a pointer needs (11).

    Parameters
    ----------
    node : Node
        A node `read_node` made, or one about to be written.
    given : dict of str to Wrapper, optional
        Its work's own commands (`body.wrappers` of its macros node, `wrappers_of`): those that point or label read as check 8 reads `\\ref` and `\\cite`, through one another, and none of them refused as a pointer loom does not read; none by default.

    Returns
    -------
    list of Problem
        Each failure with its check's number and the line of the file it is on, where it has one.
    """
    out: list[Problem] = []
    name = node.file_name
    if node.kind in (ids.STATEMENT, ids.PROOF):
        out += _lists(node, name)
        out += _body_refs(node, name, given or {})
    if node.kind == ids.REFERENCE:
        out += _entry(node, name)
    if node.kind == ids.MACROS:
        out += _macros(node, name)
    if node.empty and node.kind == ids.PROOF:
        missing = [k for k in ("source", "pages") if not getattr(node, k)]
        if missing:
            said = " or ".join(f"`{k}`" for k in missing)
            out.append(
                Problem(
                    11,
                    f"{name} is a pointer, a proof with no text, and has no {said}: a pointer says where the proof is.",
                )
            )
    if node.empty and node.kind == ids.STATEMENT and not node.source:
        out.append(
            Problem(
                11,
                f"{name} is a stub, a statement with no text, and has no `source`: a stub says which work it stands in.",
            )
        )
    return out


def _lists(node: Node, name: str) -> list[Problem]:
    out: list[Problem] = []
    for key in ("uses", "mentions"):
        listed: tuple[str, ...] = getattr(node, key)
        if list(listed) != sorted(listed):
            out.append(Problem(7, f"{name}'s `{key}` is not sorted."))
        twice = sorted({x for x in listed if listed.count(x) > 1})
        for x in twice:
            out.append(Problem(7, f"{name} lists {x} twice in `{key}`."))
        if node.id in listed:
            out.append(Problem(7, f"{name} lists itself in `{key}`."))
    for x in sorted(set(node.uses) & set(node.mentions)):
        out.append(
            Problem(
                7,
                f"{name} lists {x} in both `uses` and `mentions`; a node either rests on another or only points at it.",
            )
        )
    return out


def wrappers_of(node: Node, view: StoreView) -> dict[str, Wrapper]:
    """The commands a statement's or a proof's work defines, with what each points at or labels (`body.wrappers`): its source's macros node's, a proof with no source taking its statement's. A command named like a pointer that is among them is read as its definition says, never refused as unread."""
    if node.kind not in (ids.STATEMENT, ids.PROOF):
        return {}
    source = node.source or (view.source(node.parent) if node.kind == ids.PROOF and node.parent else None)
    return wrappers(view.macros(source)) if source else {}


def _pointing(node: Node, given: dict[str, Wrapper]) -> list[Pointer]:
    """What the body points at, written plainly or through its work's own commands, `\\label` apart."""
    return [*pointers(node.body), *(p for p in wrapped(node.body, given) if p.command != "label")]


def _how(p: Pointer) -> str:
    return f"\\{p.via} (its work's command for \\{p.command})" if p.via else f"\\{p.command}"


def _body_refs(node: Node, name: str, given: dict[str, Wrapper]) -> list[Problem]:
    out: list[Problem] = []
    listed = set(node.uses) | set(node.mentions)
    exempt = {node.id} | ({node.parent} if node.kind == ids.PROOF and node.parent else set())
    for p in _pointing(node, given):
        line = p.line
        if p.cites:
            if ids.kind_of(p.target) != ids.REFERENCE:
                out.append(
                    Problem(
                        8,
                        f"{name} cites {p.target}{' through ' + _how(p) if p.via else ''}, which is not a reference's id, as `tq-00B1-ref` is.",
                        line,
                        True,
                    )
                )
                continue
            owner: str | None = p.target
        else:
            owner = p.target if ids.parse_id(p.target) else ids.anchor_owner(p.target)
            if owner is None:
                out.append(
                    Problem(
                        8,
                        f"{name} points at {p.target} with {_how(p)}, and that is neither a node's id nor an anchor.",
                        line,
                        True,
                    )
                )
                continue
        if owner not in exempt and owner not in listed:
            out.append(
                Problem(8, f"{name} points at {owner} and lists it in neither `uses` nor `mentions`.", line, True)
            )
    for p in wrapped(node.body, given):
        if p.command == "label":
            out.append(
                Problem(
                    8,
                    f"{name} defines a label through \\{p.via}, its work's command for \\label; write \\label{{{node.id}-eq00}} itself in the body, so the anchor is one loom reads.",
                    p.line,
                    True,
                )
            )
    for p in unknown(node.body):
        if p.command in given:
            continue
        out.append(
            Problem(
                8,
                f"{name} uses \\{p.command}, which loom does not read as pointing at anything; write what it points at with \\ref, \\cref, \\hyperref[...] or a citation loom reads (§4), so it is checked.",
                p.line,
                True,
            )
        )
    seen: set[str] = set()
    for p in labels(node.body):
        line = p.line
        if ids.anchor_owner(p.target) != node.id:
            out.append(
                Problem(
                    8,
                    f"{name} defines \\label{{{p.target}}}, and a label in a body is one of its own anchors, as {node.id}-eq00 is.",
                    line,
                    True,
                )
            )
        elif p.target in seen:
            out.append(Problem(8, f"{name} defines the anchor {p.target} twice.", line, True))
        seen.add(p.target)
    for anchor, _number in node.anchors:
        if anchor not in seen:
            out.append(Problem(8, f"{name}'s `anchors` gives a number to {anchor}, which its body does not define."))
    return out


def _entry(node: Node, name: str) -> list[Problem]:
    entry = entry_of(node.body)
    if entry is None:
        return [Problem(9, f"{name}'s body is not a BibTeX entry, which a reference's body is.")]
    if entry.type in NOT_ENTRIES:
        return [Problem(9, f"{name}'s body is an @{entry.type}, where a reference's body is one entry standing alone.")]
    out: list[Problem] = []
    if not entry.key:
        out.append(Problem(9, f"{name}'s entry has no key, which documents cite the work by."))
    if entry.outside:
        out.append(Problem(9, f"{name}'s body holds more than its one entry: {entry.outside[:40]!r} follows it."))
    if entry.bare:
        out.append(
            Problem(
                9,
                f"{name}'s entry uses {', '.join(entry.bare)} unexpanded, where a reference's entry stands alone with no `@string` to expand it.",
            )
        )
    return out


def _macros(node: Node, name: str) -> list[Problem]:
    items = macros_items(node.body)
    if not items:
        return [Problem(10, f"{name} holds nothing; a work whose results need no macros has no macros node.")]
    # a conditional `\\newif\\ifdraft` defines, and so may set, `\\drafttrue` and `\\draftfalse`
    flags = {f"{n}{v}" for n in re.findall(r"\\newif\s*\\if([A-Za-z@]+)", node.body) for v in ("true", "false")}
    return _items(name, node.body, items, flags)


def _items(name: str, body: str, items: list[Item], flags: set[str]) -> list[Problem]:
    """Check 10 on what a macros body holds at one level; `\\AtBeginDocument`'s group, and each branch of a conditional, is checked as a body of its own."""
    out: list[Problem] = []
    for item in items:
        if item.command == "AtBeginDocument":
            group = body[item.start : item.end]
            inner = group[group.find("{") + 1 : group.rfind("}")] if "{" in group else ""
            out += [p._replace(line=item.line) for p in _items(name, inner, macros_items(inner), flags)]
            continue
        if is_conditional(item.command):
            cond = conditional(body, item)
            if cond is None:
                out.append(
                    Problem(
                        10,
                        f"{name} holds \\{item.command}, a conditional loom does not read whole: its condition tests what a macros node does not say, or no \\fi ends it.",
                        item.line,
                        True,
                    )
                )
                continue
            for branch in cond.branches:
                out += [p._replace(line=item.line) for p in _items(name, branch, macros_items(branch), flags)]
            continue
        if item.command in ARGUMENTS or item.command in flags:
            continue
        line = item.line
        if item.command == "text":
            out.append(
                Problem(
                    10,
                    f"{name} holds text, {item.text[:40]!r}, where a macros node holds only package loads and definitions.",
                    line,
                    True,
                )
            )
        else:
            out.append(
                Problem(
                    10,
                    f"{name} holds \\{item.command}, which a macros node does not: it holds only package loads and definitions.",
                    line,
                    True,
                )
            )
    return out


def store_problems(node: Node, view: StoreView) -> list[Problem]:
    """What a readable node gets wrong about the rest of the store: its parent and its source (6), what it lists (7), the anchors it points at (8), and its entry's key (9).

    Parameters
    ----------
    node : Node
        The node, as it is or as it is about to be written.
    view : StoreView
        The rest of the store; the node's own file in it, if any, is read as `node`.

    Returns
    -------
    list of Problem
        Each failure with its check's number.
    """
    out: list[Problem] = []
    name = node.file_name
    parsed = ids.parse_id(node.id)
    assert parsed is not None, node.id
    parent = parsed.parent
    if node.kind == ids.PROOF and parent and view.kind(parent) != ids.STATEMENT:
        out.append(Problem(6, f"{name} is a proof of {parent}, which is not in the library."))
    if node.kind == ids.MACROS and parent and view.kind(parent) != ids.REFERENCE:
        out.append(Problem(6, f"{name} holds the macros of {parent}, which is not in the library."))
    if node.source and (ids.kind_of(node.source) != ids.REFERENCE or view.kind(node.source) != ids.REFERENCE):
        out.append(Problem(6, f"{name}'s `source` is {node.source}, which is not a reference in the library."))
    if node.kind in (ids.STATEMENT, ids.PROOF) and view.kind(f"{parsed.stem}-ref") is not None:
        out.append(
            Problem(
                6,
                f"{name}'s stem {parsed.stem} is also the work {parsed.stem}-ref's; a stem names a statement or a work, never both.",
            )
        )
    if node.kind in (ids.REFERENCE, ids.MACROS) and view.kind(parsed.stem) is not None:
        out.append(
            Problem(
                6,
                f"{name}'s stem {parsed.stem} is also the statement {parsed.stem}'s; a stem names a statement or a work, never both.",
            )
        )
    for key in ("uses", "mentions"):
        for target in getattr(node, key):
            kind = view.kind(target) if target != node.id else node.kind
            if kind is None:
                out.append(
                    Problem(
                        7,
                        f"{name}'s `{key}` names {target}, which is not in the library; a result not yet read has a stub.",
                    )
                )
            elif kind == ids.MACROS:
                out.append(
                    Problem(7, f"{name}'s `{key}` names {target}, a macros node, which nothing uses or mentions.")
                )
    if node.kind in (ids.STATEMENT, ids.PROOF):
        own = frozenset(p.target for p in labels(node.body))
        for p in _pointing(node, wrappers_of(node, view)):
            owner = ids.anchor_owner(p.target)
            if owner is None or p.cites:
                continue
            defined = own if owner == node.id else view.anchors(owner)
            if (
                owner == node.id or (view.kind(owner) is not None and not view.empty(owner))
            ) and p.target not in defined:
                out.append(Problem(8, f"{name} points at {p.target}, which {owner} does not define.", p.line, True))
    if node.kind == ids.REFERENCE and (entry := entry_of(node.body)) and entry.key:
        others = sorted(view.keyed(entry.key) - {node.id})
        if others:
            out.append(
                Problem(
                    9,
                    f"{name}'s entry key {entry.key} is also {', '.join(others)}'s; documents cite a work by its key, so no two share one.",
                )
            )
    return out


def diagnostics(name: str, node: Node | None, problems: Iterable[Problem], start: int = 1) -> list[Diagnostic]:
    """`problems` of the file `name` said as diagnostics, in check order: each its check's code, the file and line, and the node's id; `start` is the file's line its body begins on.

    Every one is an error of loom's records (class `internal`, subject `record`). A node read from a work, and a reference or its macros, is the work's to put right (owner `work`).
    """
    node_id = name.removesuffix(SUFFIX)
    owned = node is not None and (node.source is not None or node.kind in (ids.REFERENCE, ids.MACROS))
    return [
        Diagnostic(
            "error",
            CODES[p.check],
            p.message,
            [Location(f"{LIBRARY_NODES}/{name}", (p.line + start - 1 if p.body else p.line) if p.line else 1)],
            [node_id],
            subject="record",
            owner="work" if owned else None,
        )
        for p in sorted(problems, key=lambda p: p.check)
    ]


def check_file(name: str, data: bytes, view: StoreView | None = None) -> tuple[Node | None, list[Diagnostic]]:
    """Check one file: reading it, what it says of itself, and, given `view`, what it says of the store.

    Parameters
    ----------
    name : str
        The file's name, `<id>.node`.
    data : bytes
        Its bytes.
    view : StoreView, optional
        The rest of the store; without it check 6 and the store's parts of 7 to 9 are not run.

    Returns
    -------
    tuple of (Node or None, list of Diagnostic)
        The node when the file can be read, and every failure found, in check order.
    """
    try:
        node = read_node(data, name)
    except NodeUnreadable as exc:
        return None, diagnostics(name, None, exc.problems)
    given = wrappers_of(node, view) if view is not None else {}
    problems = node_problems(node, given) + (store_problems(node, view) if view is not None else [])
    return node, diagnostics(name, node, problems, body_start(data, node.body))


def check_store(files: Mapping[str, bytes]) -> list[Diagnostic]:
    """Every check over a whole store given as its files.

    Parameters
    ----------
    files : mapping of str to bytes
        Each file's name and bytes.

    Returns
    -------
    list of Diagnostic
        Every failure, by file and then by check; empty for a store that passes.

    See Also
    --------
    check : the same over a quilt's store on disk.
    """
    read: dict[str, Node] = {}
    out: dict[str, list[Diagnostic]] = {}
    for name in sorted(files):
        try:
            read[name] = read_node(files[name], name)
        except NodeUnreadable as exc:
            out[name] = diagnostics(name, None, exc.problems)
    view = MemoryView.of(read.values())
    for name, node in read.items():
        problems = node_problems(node, wrappers_of(node, view)) + store_problems(node, view)
        out[name] = diagnostics(name, node, problems, body_start(files[name], node.body))
    return [d for name in sorted(out) for d in out[name]]


def check(root: Path) -> list[Diagnostic]:
    """Every check over the quilt's store, `.loom/library/nodes/`: each `<id>.node` file directly in it.

    Parameters
    ----------
    root : Path
        The quilt.

    Returns
    -------
    list of Diagnostic
        As `check_store`; empty where the quilt has no store.
    """
    folder = root / LIBRARY_NODES
    if not folder.is_dir():
        return []
    return check_store({p.name: p.read_bytes() for p in folder.iterdir() if p.name.endswith(SUFFIX) and p.is_file()})
