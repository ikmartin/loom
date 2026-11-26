"""The texts as they stand now, as status asks them: a subject's hash, what a statement uses, which notation it is typeset with, and how a person accepted it.

A `Here` is what a status is asked of: a node of the library by its id, or a block of a draft by its key. A `Web` answers for it. `DraftWeb` answers for the drafts from a scan, `LibraryWeb` for the library from the node store's files, and `Joined` for both, a block by the first and a node by the second.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from loom.evidence.subjects import Subject, is_node
from loom.paths import LOOM
from loom.scan.macros import LOOM_MACROS

if TYPE_CHECKING:
    from loom.library.node import Node
    from loom.scan.model import Macro
    from loom.scan.nodes import NodeRec
    from loom.scan.scan import ScanResult

#: A command in a text, by its name without the backslash.
_COMMAND = re.compile(r"\\([A-Za-z@]+|[^A-Za-z@\s])")
#: An environment begun in a text, by its name.
_BEGIN = re.compile(r"\\begin\s*\{([A-Za-z@*]+)\}")
#: An environment a person defines.
_NEWENV = re.compile(r"\\(?:re)?newenvironment\*?\s*\{([A-Za-z@*]+)\}")
#: A citation, its optional arguments and its keys: the last optional argument, where there is one, is the locator.
_CITE = re.compile(
    r"\\(?:cite|parencite|textcite|autocite|citep|citet|Cite|Parencite|Textcite|footcite)\*?\s*"
    r"((?:\[[^\]]*\]\s*){0,2})\{([^}]*)\}"
)


@dataclass(frozen=True)
class Here:
    """What a status is asked of: `node` and a node's id, or `block` and a draft block's key."""

    kind: str
    name: str


class Web(Protocol):
    """The texts now, for status (`evidence.status`) and the acts that record about them."""

    def subject(self, here: Here) -> Subject | None:
        """The text at `here` now, by its lasting name; None when it is gone or has no lasting name."""

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        """The hash now of what `key` names, read as `near` reads it; None when nothing answers or two texts could be meant."""

    def closure(self, here: Here) -> dict[tuple[str, str], str | None]:
        """Every subject the statement at `here` uses, and what those use in turn, with its hash now; None for a library node a statement uses that the library no longer holds, which nothing answers for."""

    def notation(self, here: Here) -> dict[str, str] | None:
        """Each command a person defined that the statement at `here` or its closure is typeset with, by the hash of its definition; None when this web cannot say, as for a node the library no longer holds."""

    def acceptance(self, here: Here) -> str | None:
        """`fresh` or `changed` for a draft's result the person accepted, from the ledger; None otherwise."""

    def stub(self, here: Here) -> bool | None:
        """For a statement or proof node, whether its body is empty; None for anything else."""

    def holds(self, ref: str, want: str) -> bool | None:
        """Whether the work `ref` holds its `pdf` or `tex`; None when this web cannot say."""

    def cited(self, here: Here) -> list[str]:
        """Each citation the statement at `here` or its closure makes that no node yet answers: `KEY LOCATOR` for one result of a work, `KEY` for a work with no result named."""

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        """The block bearing a label as `near` reads it, where one text answers; None otherwise and for anything but a label."""

    def texts(self, key: tuple[str, str]) -> set[str]:
        """Every hash what `key` names has now, in any document: a label's, each block bearing it; a node's, its one text."""


class LibraryWeb:
    """The library's texts now, read from the node store's files: a statement's or a proof's text by its id and the hash of its whole file, what its statement uses, and whether it is a stub.

    It reads each file once and keeps what it read for its life, so one is made for each read; a quilt with no library answers nothing. A node's notation is what its work's macros node defines and its text uses (`definitions_of`); a work with none defines nothing.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._read: dict[str, tuple[str, Node] | None] = {}
        self._defs: dict[str, dict[str, tuple[str, str]]] = {}
        self._entries: dict[str, tuple[str | None, str | None]] = {}

    @cached_property
    def _names(self) -> frozenset[str]:
        """The names of the files in the nodes folder, listed once for this web's life: a file is read only where its name is exactly there, so an id in another case on a file system blind to case reads as absent."""
        import os

        from loom.library.store import folder

        try:
            return frozenset(os.listdir(folder(self.root)))
        except OSError:
            return frozenset()

    def file(self, name: str) -> tuple[str, Node] | None:
        """A statement's or a proof's file, by its id: its hash and the node it holds; None for any other node, one absent, or one that does not read."""
        from loom.library.node import NodeUnreadable, node_hash, read_node
        from loom.library.store import folder

        if name not in self._read:
            found = None
            if is_node(name, "statement", "proof") and f"{name}.node" in self._names:
                try:
                    data = (folder(self.root) / f"{name}.node").read_bytes()
                    found = (node_hash(data), read_node(data, f"{name}.node"))
                except (OSError, NodeUnreadable):
                    found = None
            self._read[name] = found
        return self._read[name]

    def subject(self, here: Here) -> Subject | None:
        got = self.file(here.name) if here.kind == "node" else None
        return Subject("node", here.name, got[0]) if got else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        got = self.file(key[1]) if key[0] == "node" else None
        return got[0] if got else None

    def _uses(self, name: str) -> list[str]:
        """The statements a node's text says it uses, stubs included, in the order its header gives them."""
        got = self.file(name)
        return [u for u in got[1].uses if is_node(u, "statement")] if got else []

    def closure(self, here: Here) -> dict[tuple[str, str], str | None]:
        """What a node's statement uses, statements and stubs, and what those use in turn; a use whose node the library no longer holds is carried with no text, so what rests on it waits and says why."""
        out: dict[tuple[str, str], str | None] = {}
        if here.kind != "node":
            return out
        seen, todo = {here.name}, self._uses(here.name)
        while todo:
            name = todo.pop(0)
            if name in seen:
                continue
            seen.add(name)
            got = self.file(name)
            out[("node", name)] = got[0] if got is not None else None
            if got is not None:
                todo.extend(self._uses(name))
        return out

    def notation(self, here: Here) -> dict[str, str] | None:
        """A node's notation: each command, or environment as `{name}`, its work's macros node defines that its text or a text of its closure is typeset with, and each those definitions use in turn, by its definition's hash (`definitions_of`); a work with no macros node defines none, so its rows are none; None for a node the library does not hold."""
        from loom.scan.source import blank_comments

        if here.kind != "node":
            return {}
        got = self.file(here.name)
        if got is None:
            return None
        rows: dict[str, set[str]] = {}
        for name in [here.name, *(n for (k, n), digest in self.closure(here).items() if k == "node" and digest)]:
            held = self.file(name)
            if held is None:
                continue
            defs = self._definitions(held[1].source)
            for row, digest in used_rows([blank_comments(held[1].body)], defs).items():
                rows.setdefault(row, set()).add(digest)
        return {name: _together(hashes) for name, hashes in sorted(rows.items())}

    def short(self, ref: str | None) -> str | None:
        """A work's short name as a person reads it (`Smith 2024`), from its reference's entry; its key, or else its ref, where the entry names neither author nor title; None for no such work."""
        return self._entry(ref)[0]

    def title(self, ref: str | None) -> str | None:
        """A work's title, from its reference's entry; None where it gives none, or for no such work."""
        return self._entry(ref)[1]

    def _entry(self, ref: str | None) -> tuple[str | None, str | None]:
        """A work's short name and title, read once for this web's life."""
        from loom.library.entries import read_entry, short
        from loom.library.store import read

        if not ref:
            return None, None
        if ref not in self._entries:
            node = read(self.root, ref)
            entry = read_entry(node.body) if node is not None else None
            self._entries[ref] = (
                (short(entry.fields, entry.key), entry.fields.get("title") or None)
                if entry is not None
                else ((ref, None) if node is not None else (None, None))
            )
        return self._entries[ref]

    def macros(self, ref: str | None) -> dict[str, str] | None:
        """A work's macros node as a body draws it beside a node's text, `{node, hash, body}`; None for a work with none, or a node naming no work."""
        from loom.library.ids import macros_of
        from loom.library.node import NodeUnreadable, node_hash, read_node
        from loom.library.store import folder

        if not ref:
            return None
        name = macros_of(ref)
        try:
            data = (folder(self.root) / f"{name}.node").read_bytes()
            return {"node": name, "hash": node_hash(data), "body": read_node(data, f"{name}.node").body}
        except (OSError, NodeUnreadable):
            return None

    def _definitions(self, ref: str | None) -> dict[str, tuple[str, str]]:
        """A work's definitions, from its macros node, read once for this web's life; none for a work with none, or a node naming no work."""
        if not ref:
            return {}
        if ref not in self._defs:
            self._defs[ref] = definitions_of(self.root, ref)
        return self._defs[ref]

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        got = self.file(here.name) if here.kind == "node" else None
        return got[1].empty if got else None

    def holds(self, ref: str, want: str) -> bool | None:
        """Whether the work `ref` holds its `pdf` or its `tex`, by its reference; None for no such work."""
        from loom.library.store import read

        work = read(self.root, ref)
        return bool(getattr(work, want, None)) if work is not None else None

    def cited(self, here: Here) -> list[str]:
        return []

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        return None

    def texts(self, key: tuple[str, str]) -> set[str]:
        got = self.file(key[1]) if key[0] == "node" else None
        return {got[0]} if got else set()


class Joined:
    """The drafts' web and the library's as one: a block is the drafts', a node the library's.

    What a draft's citation of a library result reaches is the drafts' web's to say once citations resolve to nodes; until then a draft's closure holds labels alone. A draft's result whose closure holds a node is typeset with that node's notation too, so where the library cannot say it, neither can this.
    """

    def __init__(self, draft: Web, library: Web) -> None:
        self.draft, self.library = draft, library

    def _for(self, here: Here) -> Web:
        return self.library if here.kind == "node" else self.draft

    def subject(self, here: Here) -> Subject | None:
        return self._for(here).subject(here)

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return (self.library if key[0] == "node" else self.draft).resolve(key, near)

    def closure(self, here: Here) -> dict[tuple[str, str], str | None]:
        return self._for(here).closure(here)

    def notation(self, here: Here) -> dict[str, str] | None:
        own = self._for(here).notation(here)
        if own is None or here.kind == "node":
            return own
        # a library node a draft's result rests on is typeset with its work's macros, which are part of what is attested
        rows = dict(own)
        for key in self.draft.closure(here):
            if key[0] == "node":
                theirs = self.library.notation(Here("node", key[1]))
                if theirs is None:
                    return None
                rows.update(theirs)
        return rows

    def acceptance(self, here: Here) -> str | None:
        return self._for(here).acceptance(here)

    def stub(self, here: Here) -> bool | None:
        return self._for(here).stub(here)

    def holds(self, ref: str, want: str) -> bool | None:
        return self.library.holds(ref, want)

    def cited(self, here: Here) -> list[str]:
        return self._for(here).cited(here)

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        return self.draft.holder(key, near) if key[0] == "label" else None

    def texts(self, key: tuple[str, str]) -> set[str]:
        return (self.library if key[0] == "node" else self.draft).texts(key)

    def placed(self, block: dict[str, Any]) -> list[str]:
        """The drafts' blocks a stored block is on now (`DraftWeb.placed`); its key as written where the drafts' web cannot say."""
        placed = getattr(self.draft, "placed", None)
        return placed(block) if placed is not None else [str(block.get("key"))]

    def edit_on(self, edit: Any) -> list[str]:
        """The drafts' block a suggested edit is on now (`DraftWeb.edit_on`); its key as written where the drafts' web cannot say."""
        on = getattr(self.draft, "edit_on", None)
        return on(edit) if on is not None else [edit.target_key]


def block_of(result: ScanResult, node: NodeRec) -> dict[str, Any]:
    """A block as a mention or an ask names it (`docs/specs/evidence.md` §3.7): its key, the hash of its text and its context (`records.locate.context_of`).

    Writes the text to the snapshot store, as a note's is kept, since a record follows its text only where the store holds it (`records.locate.follow`).
    """
    from loom.records.locate import context_of
    from loom.records.snapshots import write_snapshot
    from loom.scan.owntext import own_text

    digest, _ = write_snapshot(result.quilt.root, own_text(result, node), result.quilt.history_dir)
    return {"key": node.key, "hash": digest, "context": context_of(result, node)}


def blocks_named(result: ScanResult, key: str) -> list[NodeRec]:
    """The blocks a key names now, as the records resolve one, for a key a record, an ask or a request holds: a label two or more statements of the documents now carry names each of them (`records.locate.shared_label`); any other key the block it names itself or by the place it was written at (`ScanResult.node_named`); none where nothing is named so.

    So a record written on a statement's place key is found once a label keys it, a place key is taken wherever a label key is, and a label a copied draft defines again names both texts, as an acceptance holds for both.
    """
    from loom.records.locate import shared_label

    shared = shared_label(result, key) if key not in result.nodes else None
    if shared is not None:
        return list(shared)
    found = result.node_named(key)
    return [found] if found is not None and found.kind not in ("master", "file") else []


def fold(text: str) -> str:
    """`text` with every run of whitespace one space and none at either end: what a hash reads, so a line broken or indented anew changes nothing."""
    return " ".join(text.split())


def text_hash(text: str) -> str:
    """The hash a record names a draft's text by: its comments removed and its spaces folded (`docs/specs/evidence.md` §2)."""
    from loom.scan.source import blank_comments

    return "sha256:" + hashlib.sha256(fold(blank_comments(text)).encode("utf-8")).hexdigest()


def macro_hash(macro: Macro) -> str:
    """The hash a record names a macro's definition by (`docs/specs/evidence.md` §5.1).

    SHA-256 of `[kind, name, args, default, body]` as compact JSON, as `scan.macros.parse_macros` reads the definition from comment-blanked text, its default and body with their spaces folded: a comment or a line broken inside it changes nothing, and a change to what it typesets does.
    """
    default = fold(macro.default) if macro.default is not None else None
    canon = json.dumps(
        [macro.kind, macro.name, macro.args, default, fold(macro.body)], ensure_ascii=False, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def citations_in(clean: str) -> list[tuple[str, str]]:
    """Each citation in comment-blanked text, in order, as `(KEY, LOCATOR)`: the key cited and the last optional argument, `''` where it names no result of the work; one `\\cite` of several keys is one citation of each."""
    out: list[tuple[str, str]] = []
    for m in _CITE.finditer(clean):
        given = re.findall(r"\[([^\]]*)\]", m.group(1))
        locator = given[-1].strip() if given else ""
        out += [(key.strip(), locator) for key in m.group(2).split(",") if key.strip()]
    return out


def used_rows(texts: list[str], defs: dict[str, tuple[str, str]]) -> dict[str, str]:
    """Each definition of `defs` that comment-blanked `texts` use, a command or an environment as `{name}`, and each those definitions use in turn, by its hash; loom's own commands are not rows."""
    used = {m.group(1) for t in texts for m in _COMMAND.finditer(t)} - LOOM_MACROS
    used |= {"{" + m.group(1) + "}" for t in texts for m in _BEGIN.finditer(t)}
    rows: dict[str, str] = {}
    todo, seen = sorted(used), set()
    while todo:
        name = todo.pop()
        if name in seen or name not in defs:
            continue
        seen.add(name)
        digest, body = defs[name]
        rows[name] = digest
        inner = {m.group(1) for m in _COMMAND.finditer(body)} - LOOM_MACROS
        inner |= {"{" + m.group(1) + "}" for m in _BEGIN.finditer(body)}
        todo.extend(sorted(inner - seen))
    return rows


def definitions_of(root: Path, ref: str) -> dict[str, tuple[str, str]]:
    """The definitions a work's macros node holds, each command and each environment as `{name}`, with its definition's hash and its text, as a draft's are read (`macro_hash`, `environments`); none where the work has no macros node or it does not read."""
    from loom.library.ids import macros_of
    from loom.library.node import NodeUnreadable, read_node
    from loom.library.store import folder
    from loom.scan.macros import parse_macros
    from loom.scan.source import blank_comments

    name = f"{macros_of(ref)}.node"
    try:
        body = blank_comments(read_node((folder(root) / name).read_bytes(), name).body)
    except (OSError, NodeUnreadable):
        return {}
    defs = {n: (macro_hash(m), f"{m.body} {m.default or ''}") for n, m in parse_macros(body).items()}
    defs.update(environments(body))
    return defs


def _together(hashes: set[str]) -> str:
    """One row's hash where the documents reading a block define a command differently: the hash of their definitions' hashes, so a change to any of them changes it."""
    if len(hashes) == 1:
        return next(iter(hashes))
    canon = json.dumps(sorted(hashes), separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def environments(clean: str) -> dict[str, tuple[str, str]]:
    """Each environment `\\newenvironment` or `\\renewenvironment` defines in comment-blanked text, as `{name}`, with its definition's hash and its text; the last definition wins."""
    from loom.scan.tokenize import match_group, read_optional, skip_space

    out: dict[str, tuple[str, str]] = {}
    for m in _NEWENV.finditer(clean):
        pos = skip_space(clean, m.end())
        parts: list[str | None] = []
        for _ in range(2):
            got, _start, _end, after = read_optional(clean, pos)
            if got is None:
                break
            parts.append(got)
            pos = skip_space(clean, after)
        codes = []
        for _ in range(2):
            pos = skip_space(clean, pos)
            end = match_group(clean, pos)
            if end < 0:
                break
            codes.append(clean[pos + 1 : end - 1])
            pos = end
        if len(codes) != 2:
            continue
        canon = json.dumps(["environment", m.group(1), *[fold(x or "") for x in parts], *[fold(c) for c in codes]])
        out["{" + m.group(1) + "}"] = ("sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest(), " ".join(codes))
    return out


def label_of(node: NodeRec) -> str | None:
    """The label a record names a block by: its id where it has one, else its first `\\label`; None for none."""
    return node.labels[0] if node.labels else None


def rests_on(result: ScanResult, key: str, results: frozenset[str] | set[str]) -> list[str]:
    """The results, among `results`, that the text at `key` (a statement or a proof) uses directly: the targets of its references, a display followed both to the block that holds it and through it to what it refers to, and what a result nested in it uses.

    The one walk for status's closure (`DraftWeb.uses`) and the Web's cards and graph (`webview`), so the two never disagree about what rests on what.
    """
    deps = result.dependencies
    node = result.nodes.get(key)
    out: list[str] = []
    seen: set[str] = set()
    todo = list(deps.direct(key))
    for child in node.claimants if node is not None else []:
        if child in results:
            out.append(child)
            todo.extend(deps.direct(child))
    while todo:
        target = todo.pop(0)
        if target in seen:
            continue
        seen.add(target)
        if target.startswith("equation:"):
            owner = deps.owners.get(target)
            if owner:
                out.append(owner)
            todo.extend(deps.direct(target))
        else:
            out.append(target)
    return list(dict.fromkeys(k for k in out if k in results and k != key))


class DraftWeb:
    """The drafts' results as one scan reads them.

    A result is a theorem-like block of a file some document reads, outside `.loom/`; a block is found by any of its labels. Its text, for every record, is its whole region with each file it inputs read in and its nested blocks kept, comments removed and spaces folded (`text_hash`), so a block nested in a statement or a statement's words put in by `\\input` are part of what it says. Built once per scan; each question is memoised on it.
    """

    def __init__(self, result: ScanResult, *, reviewer: str | None = None) -> None:
        self.result = result
        self.reviewer = reviewer
        self._texts: dict[str, str] = {}
        self._hashes: dict[str, str] = {}
        self._placed: dict[str, list[str]] = {}

    @cached_property
    def blocks(self) -> list[NodeRec]:
        """Every result of the drafts, in no order a reader may rely on."""
        return [
            n
            for n in self.result.nodes.values()
            if n.kind == "environment" and n.reached_by and not n.external and not n.file.startswith(f"{LOOM}/")
        ]

    @cached_property
    def _keys(self) -> frozenset[str]:
        return frozenset(n.key for n in self.blocks)

    @cached_property
    def bearing(self) -> dict[str, list[NodeRec]]:
        """Each label, with the blocks that bear it."""
        out: dict[str, list[NodeRec]] = {}
        for n in self.blocks:
            for label in n.labels:
                out.setdefault(label, []).append(n)
        return out

    def heres(self, label: str) -> list[Here]:
        """Every block that bears `label`, as a `Here`."""
        return [Here("block", n.key) for n in self.bearing.get(label, [])]

    def _node(self, here: Here) -> NodeRec | None:
        if here.kind != "block":
            return None
        return self.result.nodes.get(here.name) if here.name in self._keys else None

    def text(self, node: NodeRec) -> str:
        """A block's whole text: its region as written, each file it inputs read in, its nested blocks kept."""
        if node.key not in self._texts:
            self._texts[node.key] = self._region(node.file, node.start, node.end, frozenset({node.file}))
        return self._texts[node.key]

    def _region(self, path: str, start: int, end: int, seen: frozenset[str]) -> str:
        source = self.result.files[path].text
        sites = sorted(
            {
                (inc.site_start, inc.site_end, inc.child)
                for expansion in self.result.expansions.values()
                for inc in expansion.inclusions
                if inc.parent == path and inc.child and start <= inc.site_start and inc.site_end <= end
            }
        )
        out, pos = [], start
        for a, b, child in sites:
            if a < pos or child is None or child in seen or child not in self.result.files:
                continue
            out.append(source[pos:a])
            whole = self.result.files[child].text
            out.append(self._region(child, 0, len(whole), seen | {child}))
            pos = b
        out.append(source[pos:end])
        return "".join(out)

    def _hash(self, node: NodeRec) -> str:
        if node.key not in self._hashes:
            self._hashes[node.key] = text_hash(self.text(node))
        return self._hashes[node.key]

    def subject(self, here: Here) -> Subject | None:
        """A block's subject: its label and the hash of its whole text (`text_hash`)."""
        node = self._node(here)
        label = label_of(node) if node else None
        if node is None or label is None:
            return None
        return Subject("label", label, self._hash(node))

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        """A label's hash as `near` reads it: the block bearing it in a document that reads `near`, else the one text it has in the quilt."""
        kind, name = key
        if kind != "label":
            return None
        holders = self.bearing.get(name, [])
        mine = self._node(near)
        if mine is not None:
            close = [n for n in holders if set(n.reached_by) & set(mine.reached_by)]
            holders = close or holders
        hashes = {self._hash(n) for n in holders}
        return hashes.pop() if len(hashes) == 1 else None

    def uses(self, here: Here) -> list[Here]:
        """The results the statement at `here` uses directly (`rests_on`)."""
        node = self._node(here)
        return [Here("block", k) for k in rests_on(self.result, node.key, self._keys)] if node is not None else []

    def closure(self, here: Here) -> dict[tuple[str, str], str | None]:
        """What the statement at `here` uses, and what those use in turn, by label with each one's hash now; a result with no label is left out, since nothing could name it."""
        seen: set[str] = {here.name}
        out: dict[tuple[str, str], str | None] = {}
        todo = self.uses(here)
        while todo:
            step = todo.pop(0)
            if step.name in seen:
                continue
            seen.add(step.name)
            subject = self.subject(step)
            if subject is not None:
                out.setdefault(subject.key, subject.hash)
            todo.extend(self.uses(step))
        return out

    def _texts_of(self, here: Here) -> list[str]:
        """The statement at `here` and every text of its closure, each as the documents that read `here` read it."""
        node = self._node(here)
        if node is None:
            return []
        texts = [self.text(node)]
        for key in self.closure(here):
            holders = [n for n in self.bearing.get(key[1], []) if set(n.reached_by) & set(node.reached_by)]
            texts.extend(self.text(n) for n in holders[:1])
        return texts

    @cached_property
    def _definitions(self) -> dict[str, dict[str, tuple[str, str]]]:
        """Each document's definitions, by command name or `{environment}`, with each one's hash and the text it is defined as: its preamble's, then those in its body."""
        from loom.scan.macros import parse_macros
        from loom.scan.preamble import document_start
        from loom.scan.source import blank_comments

        out: dict[str, dict[str, tuple[str, str]]] = {}
        for master, closure in self.result.closures.items():
            defs = {name: (macro_hash(m), f"{m.body} {m.default or ''}") for name, m in closure.macros.items()}
            defs.update(environments(closure.clean_text()))
            src = self.result.files.get(master)
            begun = document_start(src) if src is not None else None
            if src is not None and begun is not None:
                body = blank_comments(src.text[begun:])
                defs.update(
                    {name: (macro_hash(m), f"{m.body} {m.default or ''}") for name, m in parse_macros(body).items()}
                )
                defs.update(environments(body))
            out[master] = defs
        return out

    def notation(self, here: Here) -> dict[str, str]:
        """Each command, or environment as `{name}`, a person defined and the statement or its closure is typeset with, and each that those definitions use in turn; loom's own commands are not rows.

        A block read by documents that define one differently has one row for it, the hash of their definitions together (`_together`), so a change in any of them is seen.
        """
        from loom.scan.source import blank_comments

        node = self._node(here)
        if node is None:
            return {}
        texts = [blank_comments(t) for t in self._texts_of(here)]
        rows: dict[str, set[str]] = {}
        for master in node.reached_by:
            for name, digest in used_rows(texts, self._definitions.get(master, {})).items():
                rows.setdefault(name, set()).add(digest)
        return {name: _together(hashes) for name, hashes in sorted(rows.items())}

    def cited(self, here: Here) -> list[str]:
        """Each citation in the statement or a text of its closure, which no node answers for until citations resolve to nodes: `KEY LOCATOR` for one result of a work, `KEY` for a work with no result named, which a `mention` will let go once it can name the work."""
        from loom.scan.source import blank_comments

        out = [f"{key} {locator}".strip() for text in self._texts_of(here) for key, locator in citations_in(blank_comments(text))]  # fmt: skip
        return list(dict.fromkeys(out))

    def placed(self, block: dict[str, Any]) -> list[str]:
        """The keys of the blocks a stored block (`{key, hash, context}`, a mention's or an ask's) is on now: where its text went, as every record goes (`records.locate.follow`).

        A label two copies of a draft carry: each copy holding its very text, as an acceptance holds. None where nothing says which block, so a block put in above one named by place never takes its record.
        """
        from loom.records.locate import block_hash, follow, shared_label

        memo = json.dumps(block, sort_keys=True)
        if memo in self._placed:
            return self._placed[memo]
        key, want = str(block.get("key")), str(block.get("hash") or "")
        shared = shared_label(self.result, key) if key not in self.result.nodes else None
        if shared is not None:
            out = [n.key for n in shared if block_hash(self.result, n.key) == want]
        else:
            found = follow(self.result, key, self.result.nodes.get(key), want, context=block.get("context") or None)
            out = [found.key] if found is not None and found.kind not in ("master", "file") else []
        self._placed[memo] = out
        return out

    def edit_on(self, edit: Any) -> list[str]:
        """The key of the block a suggested edit is on now (`records.edits.home`); none where it is on none."""
        from loom.records.edits import home

        found = home(self.result, edit)
        return [found.key] if found is not None else []

    def texts(self, key: tuple[str, str]) -> set[str]:
        """The hash of each block bearing a label now, in any document; empty for anything but a label."""
        return {self._hash(n) for n in self.bearing.get(key[1], [])} if key[0] == "label" else set()

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        """The block bearing a label as `near` reads it: the one text in a document that reads `near`, else the quilt's one; None where none or two texts answer."""
        kind, name = key
        if kind != "label":
            return None
        holders = self.bearing.get(name, [])
        mine = self._node(near)
        if mine is not None:
            holders = [n for n in holders if set(n.reached_by) & set(mine.reached_by)] or holders
        if len({self._hash(n) for n in holders}) != 1:
            return None
        return Here("block", holders[0].key)

    @cached_property
    def _accepted(self) -> dict[str, str]:
        """The ledger's word on each block the reviewer accepted, through the resolver every record uses (`records.store`)."""
        if not self.reviewer:
            return {}
        from loom.records.store import Records

        held = Records(self.result.quilt.root, self.result.quilt.history_dir, reviewer=self.reviewer)
        states = held.key_states(self.result, observe=False)
        return {key: ("fresh" if s.fresh else "changed") for key, s in states.items() if s.row is not None}

    def acceptance(self, here: Here) -> str | None:
        """`fresh` or `changed` where the reviewer accepted the block, from the ledger; None where they never did."""
        return self._accepted.get(here.name) if here.kind == "block" else None

    def stub(self, here: Here) -> bool | None:
        """A draft's block is never a stub."""
        return None

    def holds(self, ref: str, want: str) -> bool | None:
        """The drafts hold no work."""
        return None
