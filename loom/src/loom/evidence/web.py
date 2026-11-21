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


def macro_hash(macro: Macro) -> str:
    """The hash a record names a macro's definition by (`docs/specs/evidence.md` §5.1).

    SHA-256 of `[kind, name, args, default, body]` as compact JSON, as `scan.macros.parse_macros` reads the definition: a comment or a space between its parts does not change it, and a change to what it typesets does.
    """
    canon = json.dumps(
        [macro.kind, macro.name, macro.args, macro.default, macro.body], ensure_ascii=False, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def label_of(node: NodeRec) -> str | None:
    """The label a record names a block by: its id where it has one, else its first `\\label`; None for none."""
    return node.labels[0] if node.labels else None


class DraftWeb:
    """The drafts' results as one scan reads them.

    A result is a theorem-like block of a file some document reads, outside `.loom/`; a block is found by any of its labels. Built once per scan; each question is memoised on it.
    """

    def __init__(self, result: ScanResult, *, reviewer: str | None = None) -> None:
        self.result = result
        self.reviewer = reviewer

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

    def subject(self, here: Here) -> Subject | None:
        """A block's subject: its label and the hash every record of a block holds (`records.locate.block_hash`)."""
        from loom.records.locate import block_hash

        node = self._node(here)
        label = label_of(node) if node else None
        if node is None or label is None:
            return None
        return Subject("label", label, block_hash(self.result, node.key))

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        """A label's hash as `near` reads it: the block bearing it in a document that reads `near`, else the one text it has in the quilt."""
        from loom.records.locate import block_hash

        kind, name = key
        if kind != "label":
            return None
        holders = self.bearing.get(name, [])
        mine = self._node(near)
        if mine is not None:
            close = [n for n in holders if set(n.reached_by) & set(mine.reached_by)]
            holders = close or holders
        hashes = {block_hash(self.result, n.key) for n in holders}
        return hashes.pop() if len(hashes) == 1 else None

    def uses(self, here: Here) -> list[Here]:
        """The results the statement at `here` uses directly: the targets of its references, through displays (`Dependencies.review_targets`)."""
        node = self._node(here)
        if node is None:
            return []
        out: list[Here] = []
        for key in self.result.dependencies.review_targets(node.key):
            target = self.result.nodes.get(key)
            if target is not None and target.key in self._keys and target.key != node.key:
                out.append(Here("block", target.key))
        return out

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

    def notation(self, here: Here) -> dict[str, str]:
        """Each command a person defined in the preamble of a document that reads `here` and that the statement or its closure uses; loom's own commands are not rows."""
        node = self._node(here)
        if node is None:
            return {}
        texts = [self._text(node)]
        for key in self.closure(here):
            holders = [n for n in self.bearing.get(key[1], []) if set(n.reached_by) & set(node.reached_by)]
            texts.extend(self._text(n) for n in holders[:1])
        used = {m.group(1) for text in texts for m in _COMMAND.finditer(text)} - LOOM_MACROS
        out: dict[str, str] = {}
        for master in node.reached_by:
            closure = self.result.closures.get(master)
            if closure is None:
                continue
            for name in sorted(used - set(out)):
                macro = closure.macros.get(name)
                if macro is not None:
                    out[name] = macro_hash(macro)
        return out

    def _text(self, node: NodeRec) -> str:
        from loom.scan.owntext import own_text
        from loom.scan.source import blank_comments

        return blank_comments(own_text(self.result, node))

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
