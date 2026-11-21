"""A node's id (docs/specs/nodes.md §3, §5): its grammar, the kind its suffix makes it, whose a proof or a macros node is, the anchors inside a body, and minting.

An id is opaque and permanent. A stem shares the quilt's id namespace with the author's own sources, so it is minted by `source-contract.md` §3.2's rule, one past the largest seen; a proof's number is minted the same way under its statement, so a number seen anywhere is never given again.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from loom.scan.labels import base36_decode, base36_encode, next_local

#: The four kinds of node, each named by the suffix its id ends in (a statement by none).
STATEMENT, PROOF, REFERENCE, MACROS = "statement", "proof", "reference", "macros"
KINDS = (STATEMENT, PROOF, REFERENCE, MACROS)

PREFIX = r"[A-Za-z0-9]+"
LOCAL = r"[0-9A-Z]{4}"
NN = r"[0-9A-Z]{2}"
STEM = rf"{PREFIX}-{LOCAL}"

_ID = re.compile(rf"(?P<stem>{STEM})(?:-(?P<suffix>ref|macros|proof(?P<nn>{NN})))?")
_ANCHOR = re.compile(rf"(?P<owner>{STEM}(?:-proof{NN})?)-(?P<kind>eq|it){NN}")
#: Characters that cannot stand beside an id in running text, so a search for one does not find it inside a longer name.
_EDGE_BEFORE = r"(?<![A-Za-z0-9])"
_EDGE_AFTER = r"(?![A-Za-z0-9])"


@dataclass(frozen=True)
class NodeId:
    """An id read by the grammar: the text, its stem, its kind, and a proof's two-character number."""

    text: str
    stem: str
    kind: str
    nn: str | None = None

    @property
    def parent(self) -> str | None:
        """The node this one belongs to by its suffix: a proof's statement, a macros node's reference; None for the others."""
        if self.kind == PROOF:
            return self.stem
        if self.kind == MACROS:
            return f"{self.stem}-ref"
        return None


def parse_id(text: str) -> NodeId | None:
    """`text` read as a node's id, or None when the grammar of §3 does not make it one.

    Parameters
    ----------
    text : str
        A candidate id, such as a file's name without `.node` or an argument of `\\ref`.

    Returns
    -------
    NodeId or None
        The id with its stem, kind and proof number; None for an anchor or anything else.
    """
    m = _ID.fullmatch(text)
    if m is None:
        return None
    suffix = m.group("suffix")
    if suffix is None:
        return NodeId(text, m.group("stem"), STATEMENT)
    if suffix == "ref":
        return NodeId(text, m.group("stem"), REFERENCE)
    if suffix == "macros":
        return NodeId(text, m.group("stem"), MACROS)
    return NodeId(text, m.group("stem"), PROOF, m.group("nn"))


def kind_of(text: str) -> str | None:
    """The kind of node `text` names by its suffix, or None when it is no id."""
    parsed = parse_id(text)
    return parsed.kind if parsed else None


def parent_of(text: str) -> str | None:
    """The id `text` belongs to by its suffix: a proof's statement, a macros node's reference; None otherwise."""
    parsed = parse_id(text)
    return parsed.parent if parsed else None


def anchor_owner(text: str) -> str | None:
    """The node an anchor (`owner-eqNN`, `owner-itNN`) is a place inside, or None when `text` is no anchor.

    Parameters
    ----------
    text : str
        A candidate anchor, such as an argument of `\\eqref` or `\\label`.

    Returns
    -------
    str or None
        The owner's id, a statement's or a proof's.
    """
    m = _ANCHOR.fullmatch(text)
    return m.group("owner") if m else None


def mint_stem(prefix: str, seen: Iterable[str]) -> str:
    """A new stem under `prefix`: one past the largest four-character local part any of `seen` holds under it, as `loom id --next` draws.

    Parameters
    ----------
    prefix : str
        The quilt's prefix.
    seen : iterable of str
        Every text an id may have been written in: ids, file names, lines of records. A stem is found in them wherever it stands, inside a longer id included.

    Returns
    -------
    str
        `prefix-XXXX`, `XXXX` base 36.

    See Also
    --------
    mint_proof : the next proof of a statement.
    """
    pattern = re.compile(_EDGE_BEFORE + re.escape(prefix) + rf"-({LOCAL}){_EDGE_AFTER}")
    found = {m.group(1) for text in seen for m in pattern.finditer(text)}
    local = next_local(found)
    if len(local) > 4:
        raise ValueError(f"every four-character id under the prefix {prefix} has been given")
    return f"{prefix}-{local}"


def mint_proof(statement: str, seen: Iterable[str]) -> str:
    """A new proof of `statement`: one past the largest proof number any of `seen` holds under it, `00` when none.

    Parameters
    ----------
    statement : str
        The statement's id, a bare stem.
    seen : iterable of str
        Every text a proof's id may have been written in, as for `mint_stem`; a proof removed from the store and seen in a record or in git keeps its number.

    Returns
    -------
    str
        `statement-proofNN`, `NN` base 36.

    See Also
    --------
    mint_stem : a new stem.
    """
    if kind_of(statement) != STATEMENT:
        raise ValueError(f"{statement} is not a statement's id, so it has no proofs")
    pattern = re.compile(_EDGE_BEFORE + re.escape(statement) + rf"-proof({NN}){_EDGE_AFTER}")
    numbers = [base36_decode(m.group(1)) for text in seen for m in pattern.finditer(text)]
    nxt = max(numbers) + 1 if numbers else 0
    if nxt >= 36**2:
        raise ValueError(f"every proof number under {statement} has been given")
    return f"{statement}-proof{base36_encode(nxt, 2)}"
