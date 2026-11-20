"""Where a record goes: the one rule by which an annotation and a suggested edit find the block they were written on (`follow`).

A record names a key and holds the hash of its block's own text when it was written (`against`). A stable key, an id or a label, names its own block, and a region names the block it is in. A key named by its place in its file (`FILE#proof:3`) names whichever block now stands there, so a record on it goes with its text and never falls back to the block that took its place. Nothing looks for a record's quote outside the block it is on.
"""

from __future__ import annotations

import difflib
import re

from loom.paths import LOOM
from loom.scan.nodes import NodeRec
from loom.scan.owntext import key_hash
from loom.scan.scan import ScanResult

#: How alike, word for word, the block at a record's place must read to the text the record was written on to be taken for it, with no other block of its file reading as alike.
LIKE = 0.6

#: A child's marker in a block's own text (`own_text`), which no person wrote and no likeness counts.
_CHILD = re.compile(r"^% !LOOM child: .*$", re.MULTILINE)

#: The scan the block hashes below were read from, and each key's hash; one scan at a time, held as one tuple so that a thread reading it never mixes two scans.
_BLOCK_HASHES: tuple[ScanResult, dict[str, str]] | None = None


def block_hash(result: ScanResult, key: str) -> str:
    """A block's hash as a record's `against` holds it (`key_hash`), remembered for the scan it was read from."""
    global _BLOCK_HASHES
    held = _BLOCK_HASHES
    if held is None or held[0] is not result:
        held = _BLOCK_HASHES = (result, {})
    known = held[1].get(key)
    if known is None:
        known = held[1][key] = key_hash(result, key)
    return known


def named_by_place(result: ScanResult, key: str, node: NodeRec | None) -> bool:
    """Whether `key` names a block by its place in its file (`FILE#proof:3`), which another block takes once one is put in before it.

    The scan's record of the block decides, not the key's shape: a key made from a label (`FILE#lab`) has a `#` too, and names its own block. A region inside a block is not named by place. A key that names no block now is taken as named by place, the kind that stops naming one.
    """
    if "#" not in key or key in result.assembly.regions:
        return False
    return node is None or key.split("#", 1)[1] not in node.labels


def line_before(result: ScanResult, node: NodeRec) -> str:
    """The last line with words above `node` in its file: what a suggested edit on a key named by place records beside the block's text (`near`), to tell the block from another that reads the same."""
    source = result.files.get(node.file)
    if source is None:
        return ""
    return source.text[: node.start].rstrip().rsplit("\n", 1)[-1].strip()


def alike(result: ScanResult, node: NodeRec) -> list[NodeRec]:
    """The other blocks of `node`'s file that hold the same text under the same line above: the ones a suggested edit on a key named by place could not be told from (`cli.suggest`)."""
    text, above = block_hash(result, node.key), line_before(result, node)
    return [
        n
        for n in result.nodes.values()
        if n.file == node.file
        and n is not node
        and block_hash(result, n.key) == text
        and line_before(result, n) == above
    ]


def follow(
    result: ScanResult,
    key: str,
    node: NodeRec | None,
    want: str,
    *,
    edit: bool = False,
    near: str = "",
    quoted: bool = False,
) -> NodeRec | None:
    """The block a record on `key` was written on, or None when nothing says which block that is.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    key : str
        The key the record names.
    node : NodeRec or None
        The block `key` names now (a region's container); None when it names none.
    want : str
        The record's `against`: the hash of its block's own text when it was written; '' is no evidence, and `node` is answered.
    edit : bool, default False
        Whether the record is a suggested edit, which Keep writes: one is never placed among blocks that read the same unless `near` says which.
    near : str, default ''
        A suggested edit's `near`, the line above its block when it was filed (`line_before`); '' for an annotation, which records none, and for an edit filed before it was recorded.
    quoted : bool, default False
        Whether the suggested edit quotes words of its block; only such an edit is taken at its place once the block there has changed (`place` then asks for its quote once, and nowhere else in the file).

    Returns
    -------
    NodeRec or None
        For a stable key, `node` always; for a region, or one whose label went, where the block it is in goes. For a key named by place, or a document's path once its file is gone: the one block that holds the record's text, in the key's file or, once that file is gone, in the quilt. Among several, the one under `near`; with no `near`, an annotation's block at its place while that holds its text, as it always has. Where none holds it, a quoted edit's block at its place while the line above is `near`, and an annotation's while that block reads like the text it was written on and no other block of its file does (`LIKE`). None otherwise: the block now at the place is never the answer for text it is not.

    See Also
    --------
    named_by_place : which keys a block put in before them renumbers.
    """
    if not want:
        return node
    head = _container_key(result, key, node)
    if head:
        # a region goes where the block it is in goes, whose text the record holds; one whose label went is read there
        return follow(result, head, result.nodes.get(head), want, edit=edit, near=near, quoted=quoted)
    # a document's own text is named by its file's path, which a rename takes away as it does a key named by place
    gone_document = node is None and key.endswith(".tex") and not key.startswith("prose:")
    if not named_by_place(result, key, node) and not gone_document:
        return node
    path = node.file if node is not None else key.split("#", 1)[0]
    same: list[NodeRec] = [n for n in result.nodes.values() if n.file == path and block_hash(result, n.key) == want]
    if not same and path.endswith(".tex") and path not in result.files:
        # its file is gone, renamed or taken apart: the text is followed wherever in the person's files it stands, never into an agent's copy under `.loom/`
        same = [
            n for n in result.nodes.values() if not n.file.startswith(f"{LOOM}/") and block_hash(result, n.key) == want
        ]
    if len(same) == 1:
        return same[0]
    if same:
        if near:
            under = [n for n in same if line_before(result, n) == near]
            return under[0] if len(under) == 1 else None
        # blocks that read the same, and nothing recorded to tell them apart: an annotation stays at its place while that holds its text, as it always has; an edit is not written into one of them blind
        return node if not edit and any(n is node for n in same) else None
    if node is None:
        return None
    if edit:
        # its block has changed: only an edit that quotes words, under the line it was filed under, is taken at its place
        return node if quoted and near and line_before(result, node) == near else None
    # its block edited where it stands: an annotation stays while the block still reads like what it was written on, and no other block of its file does
    return node if _reads_like(result, want, node) else None


def _container_key(result: ScanResult, key: str, node: NodeRec | None) -> str:
    """For a region key, or one whose label is gone and whose head names a block, the key of the block it is in; '' for any other key.

    A region of a document's own text (its head is a file's path) is left to the document; a key whose head is a document or a file (`FILE#label`) is a block's, not a region's.
    """
    if "#" not in key or (key not in result.assembly.regions and node is not None):
        return ""
    head = key.rsplit("#", 1)[0]
    block: NodeRec | None = result.nodes.get(head)
    if head in result.files or (block is not None and block.kind in ("master", "file")):
        return ""
    if key in result.assembly.regions or block is not None or "#" in head:
        return head
    return ""


#: Each scan's words, by block key and by the hash of a text frozen when a record was written; one scan at a time.
_WORDS: tuple[ScanResult, dict[str, list[str]]] | None = None


def _words_of(result: ScanResult, name: str, text: str | None) -> list[str]:
    """The words of `text` with child markers left out, remembered under `name` for the scan `result`; [] for no text."""
    global _WORDS
    held = _WORDS
    if held is None or held[0] is not result:
        held = _WORDS = (result, {})
    known = held[1].get(name)
    if known is None:
        known = held[1][name] = _CHILD.sub("", text).split() if text else []
    return known


def _likeness(a: list[str], b: list[str]) -> float:
    """How alike two lists of words read, 0 to 1, with the cheap bounds tried first."""
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.real_quick_ratio() < LIKE or m.quick_ratio() < LIKE:
        return 0.0
    return m.ratio()


def _reads_like(result: ScanResult, want: str, node: NodeRec) -> bool:
    """Whether `node` reads at least `LIKE` alike the text frozen as `want` when a record was written (`cli.review._version`), and no other block of its file does; False when that text is not in the store."""
    from loom.records.snapshots import read_snapshot
    from loom.scan.owntext import own_text

    frozen = _words_of(result, want, read_snapshot(result.quilt.root, want, result.quilt.history_dir))
    if _likeness(frozen, _words_of(result, node.key, own_text(result, node))) < LIKE:
        return False
    return not any(
        _likeness(frozen, _words_of(result, n.key, own_text(result, n))) >= LIKE
        for n in result.nodes.values()
        if n.file == node.file and n is not node and n.kind not in ("master", "file")
    )
