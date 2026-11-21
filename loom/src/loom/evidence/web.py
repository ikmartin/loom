"""The texts as they stand now, as status asks them: a subject's hash, what a statement uses, which notation it is typeset with, and how a person accepted it.

A `Here` is what a status is asked of: a node of the library by its id, or a block of a draft by its key. A `Web` answers for it. `DraftWeb` answers for the drafts from a scan; the library's own (`LibraryWeb`, over the node store) and the joint one that follows a draft's citations into the library come with the store, and until then a node is gone to the drafts' web.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Protocol

from loom.evidence.subjects import Subject
from loom.paths import LOOM
from loom.scan.macros import LOOM_MACROS

if TYPE_CHECKING:
    from loom.scan.model import Macro
    from loom.scan.nodes import NodeRec
    from loom.scan.scan import ScanResult

#: A command in a text, by its name without the backslash.
_COMMAND = re.compile(r"\\([A-Za-z@]+|[^A-Za-z@\s])")
#: An environment begun in a text, by its name.
_BEGIN = re.compile(r"\\begin\s*\{([A-Za-z@*]+)\}")
#: An environment a person defines.
_NEWENV = re.compile(r"\\(?:re)?newenvironment\*?\s*\{([A-Za-z@*]+)\}")
#: A citation with a locator, its optional arguments and its keys: the last optional argument is the locator.
_CITE = re.compile(
    r"\\(?:cite|parencite|textcite|autocite|citep|citet|Cite|Parencite|Textcite|footcite)\*?\s*"
    r"((?:\[[^\]]*\]\s*){1,2})\{([^}]*)\}"
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

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        """Every subject the statement at `here` uses, and what those use in turn, with its hash now."""

    def notation(self, here: Here) -> dict[str, str]:
        """Each command a person defined that the statement at `here` or its closure is typeset with, by the hash of its definition."""

    def acceptance(self, here: Here) -> str | None:
        """`fresh` or `changed` for a draft's result the person accepted, from the ledger; None otherwise."""

    def stub(self, here: Here) -> bool | None:
        """For a statement or proof node, whether its body is empty; None for anything else."""

    def holds(self, ref: str, want: str) -> bool | None:
        """Whether the work `ref` holds its `pdf` or `tex`; None when this web cannot say."""

    def cited(self, here: Here) -> list[str]:
        """Each citation of one result of a work, a locator given, that the statement at `here` or its closure makes and no node yet answers, as `KEY LOCATOR`."""


class Blank:
    """A web that knows no text: every question is answered with nothing, so nothing reads as done and an ask a node would close stays open."""

    def subject(self, here: Here) -> Subject | None:
        return None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return None

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        return {}

    def notation(self, here: Here) -> dict[str, str]:
        return {}

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        return None

    def holds(self, ref: str, want: str) -> bool | None:
        return None

    def cited(self, here: Here) -> list[str]:
        return []


class Joined:
    """The drafts' web and the library's as one: a block is the drafts', a node the library's.

    What a draft's citation of a library result reaches is the drafts' web's to say once citations resolve to nodes; until then a draft's closure holds labels alone.
    """

    def __init__(self, draft: Web, library: Web) -> None:
        self.draft, self.library = draft, library

    def _for(self, here: Here) -> Web:
        return self.library if here.kind == "node" else self.draft

    def subject(self, here: Here) -> Subject | None:
        return self._for(here).subject(here)

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return (self.library if key[0] == "node" else self.draft).resolve(key, near)

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        return self._for(here).closure(here)

    def notation(self, here: Here) -> dict[str, str]:
        return self._for(here).notation(here)

    def acceptance(self, here: Here) -> str | None:
        return self._for(here).acceptance(here)

    def stub(self, here: Here) -> bool | None:
        return self._for(here).stub(here)

    def holds(self, ref: str, want: str) -> bool | None:
        return self.library.holds(ref, want)

    def cited(self, here: Here) -> list[str]:
        return self._for(here).cited(here)


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


class DraftWeb:
    """The drafts' results as one scan reads them.

    A result is a theorem-like block of a file some document reads, outside `.loom/`; a block is found by any of its labels. Its text, for every record, is its whole region with each file it inputs read in and its nested blocks kept, comments removed and spaces folded (`text_hash`), so a block nested in a statement or a statement's words put in by `\\input` are part of what it says. Built once per scan; each question is memoised on it.
    """

    def __init__(self, result: ScanResult, *, reviewer: str | None = None) -> None:
        self.result = result
        self.reviewer = reviewer
        self._texts: dict[str, str] = {}
        self._hashes: dict[str, str] = {}

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
        """The results the statement at `here` uses directly: the targets of its references, a display followed both to the block that holds it and through it to what it refers to, and what a result nested in it uses."""
        node = self._node(here)
        if node is None:
            return []
        deps = self.result.dependencies
        out: list[str] = []
        seen: set[str] = set()
        todo = list(deps.direct(node.key))
        for child in node.claimants:
            if child in self._keys:
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
        found = dict.fromkeys(k for k in out if k in self._keys and k != node.key)
        return [Here("block", k) for k in found]

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        """What the statement at `here` uses, and what those use in turn, by label with each one's hash now; a result with no label is left out, since nothing could name it."""
        seen: set[str] = {here.name}
        out: dict[tuple[str, str], str] = {}
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
        used = {m.group(1) for t in texts for m in _COMMAND.finditer(t)} - LOOM_MACROS
        used |= {"{" + m.group(1) + "}" for t in texts for m in _BEGIN.finditer(t)}
        rows: dict[str, set[str]] = {}
        for master in node.reached_by:
            defs = self._definitions.get(master, {})
            todo, seen = sorted(used), set()
            while todo:
                name = todo.pop()
                if name in seen or name not in defs:
                    continue
                seen.add(name)
                digest, body = defs[name]
                rows.setdefault(name, set()).add(digest)
                inner = {m.group(1) for m in _COMMAND.finditer(body)} - LOOM_MACROS
                inner |= {"{" + m.group(1) + "}" for m in _BEGIN.finditer(body)}
                todo.extend(sorted(inner - seen))
        return {name: _together(hashes) for name, hashes in sorted(rows.items())}

    def cited(self, here: Here) -> list[str]:
        """Each citation of one result of a work, its locator given, in the statement or a text of its closure: a use of a library result no node answers for until citations resolve to nodes (`KEY LOCATOR`)."""
        from loom.scan.source import blank_comments

        out: list[str] = []
        for text in self._texts_of(here):
            for m in _CITE.finditer(blank_comments(text)):
                locator = re.findall(r"\[([^\]]*)\]", m.group(1))[-1].strip()
                if not locator:
                    continue
                for key in m.group(2).split(","):
                    if key.strip():
                        out.append(f"{key.strip()} {locator}")
        return list(dict.fromkeys(out))

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
