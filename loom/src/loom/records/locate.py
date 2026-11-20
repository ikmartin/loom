"""Where a record goes: the one rule by which an annotation and a suggested edit find the block they were written on (`follow`).

A record names a key and holds the hash of its block's own text when it was written (`against`). A stable key, an id or a label, names its own block, and a region names the block it is in. A key named by its place in its file (`FILE#proof:3`) names whichever block now stands there, so a record on it goes with its text and never falls back to the block that took its place. Nothing looks for a record's quote outside the block it is on.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from loom.paths import LOOM
from loom.scan.nodes import NodeRec
from loom.scan.owntext import key_hash
from loom.scan.scan import ScanResult

#: How alike, word for word, the block at a record's place must read to the text the record was written on to be taken for it, with no other block of its file reading as alike.
LIKE = 0.6

#: How a record on a stable key (an id or a label) whose block no longer reads like it, and whose text stands in no other block, is read: False, it stays on its key, rewritten under it (`Found.rewritten`); True, it is detached. Which loom does is the author's to decide; the anchoring harness's `--verify` reads with True. Either way, a record whose text stands once in another block follows it there: its label moved.
VERIFY = False

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
    quote: str = "",
    context: dict[str, Any] | None = None,
) -> NodeRec | None:
    """The block a record on `key` was written on, or None where two answers are possible or none is.

    A record goes to a block other than the one at its own key only when nothing else could be meant (`docs/design/writes.md`, "Where a record goes"); wherever two blocks could be meant, it is on none, and says so.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    key : str
        The key the record names.
    node : NodeRec or None
        The block `key` names now (a region's container); None when it names none.
    want : str
        The record's `against`: the hash of its block's own text when it was written, frozen in the store; '' is no evidence, and `node` is answered.
    edit : bool, default False
        Whether the record is a suggested edit, which Keep writes.
    near : str, default ''
        A suggested edit's `near`, the line above its block when it was filed; it tells apart blocks of the very same text for an edit filed before `context` was recorded.
    quoted : bool, default False
        Whether the suggested edit quotes words of its block.
    quote : str, default ''
        The words the record quotes.
    context : dict, optional
        The record's `context` (`context_of`), for one written since it was recorded.

    Returns
    -------
    NodeRec or None
        For a stable key, its block, unless that block no longer reads like the record and the record's text stands once in another block (the label moved: that block), or, under `VERIFY`, stands nowhere (None). For a region, where the block it is in goes. For a key named by place, `_by_place`.

    See Also
    --------
    named_by_place : which keys a block put in before them renumbers.
    """
    if not want:
        return node
    head = _container_key(result, key, node)
    if head:
        container: NodeRec | None = result.nodes.get(head)
        if not context and container is not None and block_hash(result, container.key) == want:
            # unchanged, a region with no context is read in its block as loom always read it
            return container
        # a region goes where the block it is in goes, whose text the record holds; one whose label went is read there
        return follow(
            result,
            head,
            result.nodes.get(head),
            want,
            edit=edit,
            near=near,
            quoted=quoted,
            quote=quote,
            context=context,
        )
    # a document's own text is named by its file's path, which a rename takes away as it does a key named by place
    gone_document = node is None and key.endswith(".tex") and not key.startswith("prose:")
    if not named_by_place(result, key, node) and not gone_document:
        return _stable(result, key, node, want, quote, context or {})
    return _by_place(result, key, node, want, edit=edit, near=near, quote=quote, context=context or {})


def rewritten(result: ScanResult, node: NodeRec, want: str, quote: str = "") -> bool:
    """Whether a record on a stable key that stays on `node` was written on a text `node` no longer reads like: its block was rewritten under its key, which a reader is told."""
    return bool(want) and not _still(result, want, node, quote)


def _stable(
    result: ScanResult, key: str, node: NodeRec | None, want: str, quote: str, context: dict[str, Any]
) -> NodeRec | None:
    """A stable key's record: on the block that carries its id or label, unless that label moved, or, for an id's proof (`ID/proof`, numbered by its place among the proofs), unless the proof at the key no longer holds its text and stands apart from its recorded neighbours.

    The label moved only where the record's text, labels aside, stands in one other block between the record's recorded neighbours on both sides (the block now carrying the label left out of the count), a text long enough to be someone's and not a twin its context recorded: the record follows it there, never to a copy standing elsewhere. Otherwise the record stays on the key's block, marked rewritten where that block no longer reads like it (`rewritten`), or detached under `VERIFY`. A record with no context stays on the key's block, as loom always read it. An id two blocks define places none. A key whose block is in a file no document reads now is on no block until one reads it again, unless the record was written while none read it (`unread`), never looked for elsewhere.
    """
    if node is None:
        return None
    documents = _pool(result, node.file)
    if node.kind == "conflict":
        # an id two blocks define: the one of the documents that reads like the record, where only one does; else either could be meant
        mine = [n for n in documents if _still(result, want, n, quote)]
        return mine[0] if len(mine) == 1 else None
    if not any(n is node for n in documents):
        # its file stands but no document reads it now (an `\\input` commented out): on no block until one reads it again, never sent looking elsewhere; a record written while none read it (a scratch file) is on its block
        return node if not context or context.get("unread") else None
    still = _still(result, want, node, quote)
    if (
        context
        and block_hash(result, node.key) != want
        and _PROOF_OF_ID.match(key)
        and _sides(result, node, context)[1]
    ):
        # an id's proofs are numbered by their place among its proofs: a proof standing apart from the record's neighbours is another one, which took the key of one deleted
        return None
    if context and block_hash(result, node.key) != want:
        moved = _moved(result, want, node, documents, context)
        if moved is not None:
            return moved
    return node if still or not VERIFY else None


def _moved(
    result: ScanResult, want: str, node: NodeRec, documents: list[NodeRec], context: dict[str, Any]
) -> NodeRec | None:
    """Where a stable key's label went from: the one block other than `node` holding the record's text, labels aside, and standing between the record's recorded neighbours on both sides, `node` (the block that now carries the label) counted as the neighbour it was or left out, for a label moved onto the next block or onto one put in beside it; when that text is long enough to be someone's and its context recorded no twin. When an author moves a label, the block that lost it is still where it was; a copy standing elsewhere is never it."""
    words = _own_words(_frozen(result, want))
    if len(words) < TRIVIAL or context.get("twin") or int(context.get("copies") or 1) > 1:
        return None
    bare = _bare_frozen(result, want)
    found = [
        n
        for n in documents
        if n is not node
        and bare
        and _bare_of(result, n) == bare
        and max(_sides(result, n, context)[0], _sides(result, n, context, skip=node)[0]) == 2
    ]
    return found[0] if len(found) == 1 else None


def _by_place(
    result: ScanResult,
    key: str,
    node: NodeRec | None,
    want: str,
    *,
    edit: bool,
    near: str,
    quote: str,
    context: dict[str, Any],
) -> NodeRec | None:
    """A record on a key named by place (or a document's path whose file is gone).

    Its own key's block first: while it holds the record's text, or reads like it with no neighbour saying otherwise, it is the record's, however exact a copy elsewhere. Where the record's context recorded a twin or two copies, a block holding its very text is taken only with no recorded neighbour against it (of several such, the one with both beside it), and one reading alike only with both beside it. Otherwise only a block nothing else could be: the one holding its very text among the documents' blocks, where no other did when it was written; where every block holding it has a recorded neighbour against it, or none holds it, the one block reading `LIKE` alike, with both neighbours beside it for a record that had a twin or a block of another kind; its quote, standing in one block alone. A text with nothing of its own to recognise (`TRIVIAL`) is followed only to the one block of its very text standing between both its recorded neighbours. A record with no context follows only its very text standing once. A key whose block is in a file no document reads now is on no block, unless the record was written while none read it (`unread`).
    """
    frozen = _frozen(result, want)
    trivial = len(_own_words(frozen)) < TRIVIAL
    if not context:
        return _unrecorded(result, node, want, edit=edit, near=near, trivial=trivial)
    copies = int(context.get("copies") or 1)
    twin = bool(context.get("twin")) or copies > 1
    path = node.file if node is not None else key.split("#", 1)[0]
    documents = _pool(result, path)
    if node is not None and not context.get("unread") and not any(n is node for n in documents):
        # its file stands but no document reads it now: on no block until one reads it again, never sent looking elsewhere
        return None
    if node is not None and block_hash(result, node.key) == want:
        others = [n for n in documents if n is not node and block_hash(result, n.key) == want]
        if not others and not twin:
            # its very text stands once, at its own key, and stood once: its block
            return node
        told = _told(result, [node, *others], context, twin)
        if told is not None or not _all_against(result, [node, *others], context, twin):
            return told
    if node is not None and trivial and _sides(result, node, context)[0] == 2:
        # a text with nothing of its own, its block being filled in where it stands between both its neighbours
        return node
    if node is not None and not trivial and _like(result, want, node) >= LIKE and not _sides(result, node, context)[1]:
        if not twin:
            # edited where it stands: never left for another block, however exact a copy made since
            return node
        # its block had a twin when it was written, and the block at its place may be that twin: only with both its neighbours beside it, no block holding its very text, and reading closer to it than any other by `AHEAD`
        mine = _like(result, want, node)
        rivals = [n for n in documents if n is not node and _like(result, want, n) >= LIKE]
        if (
            _sides(result, node, context)[0] == 2
            and not any(block_hash(result, n.key) == want for n in rivals)
            and all(mine - _like(result, want, n) >= AHEAD for n in rivals)
        ):
            return node
        return None
    exact = [n for n in documents if n is not node and block_hash(result, n.key) == want]
    if trivial:
        # nothing of its own to recognise: only the one block of its very text that stands between both its neighbours
        both = [n for n in exact if _sides(result, n, context)[0] == 2]
        return both[0] if len(both) == 1 else None
    short = len(_own_words(frozen)) < SHORT
    if exact:
        if len(exact) == 1 and not twin and not (short and _sides(result, exact[0], context)[1]):
            return exact[0]
        told = _told(result, exact, context, twin)
        if told is not None or not _all_against(result, exact, context, twin):
            return told
    # every block holding its very text, where any does, has a recorded neighbour against it: its own block may stand edited, which reads like it
    taken = {id(n) for n in exact}
    pool = [
        n for n in documents if n is not node and id(n) not in taken and (n.file == path or path not in result.files)
    ]
    best = _closest(result, want, pool)
    if best is not None:
        if (twin or _sort(best) != context.get("kind")) and _sides(result, best, context)[0] != 2:
            return None
        if short and _sides(result, best, context)[1]:
            return None
        return best
    if quote and len(quote.split()) >= QUOTE_WORDS and context.get("quote") == 1:
        holders = [n for n in documents if quote in _own_text(result, n)]
        if len(holders) == 1:
            return holders[0]
    return None


def _unrecorded(
    result: ScanResult, node: NodeRec | None, want: str, *, edit: bool, near: str, trivial: bool
) -> NodeRec | None:
    """A record on a key named by place written before `context` was recorded: where its key's block holds its text, as loom always read it (an annotation there; an edit there while no other block of its file holds that text, or under its `near`); an annotation also while that block reads `LIKE` alike and no other block of its file does, and while it reads alike neither leaves it for another; otherwise only its very text standing once among the documents' blocks, never a text with nothing of its own (`TRIVIAL`)."""
    if node is not None and block_hash(result, node.key) == want:
        if not edit:
            return node
        same = [n for n in result.nodes.values() if n.file == node.file and block_hash(result, n.key) == want]
        if len(same) == 1:
            return node
        under = [n for n in same if near and line_before(result, n) == near]
        return under[0] if len(under) == 1 else None
    if node is not None and not trivial and _like(result, want, node) >= LIKE:
        # edited where it stands: never left for another block; an annotation stays while no other block of its file reads as alike, and an edit, which the base never placed on a changed block, is on none
        alike = any(_like(result, want, n) >= LIKE for n in _in_order(result, node.file) if n is not node)
        return node if not edit and not alike else None
    if trivial:
        return None
    path = node.file if node is not None else ""
    pool = _pool(result, path)
    exact = [n for n in pool if n is not node and block_hash(result, n.key) == want]
    if edit and near and len(exact) > 1:
        under = [n for n in exact if line_before(result, n) == near]
        return under[0] if len(under) == 1 else None
    if len(exact) != 1:
        return None
    # its very text standing once, but another block reading like it may be the record's own, edited: none can be told
    rivals = [n for n in pool if n is not node and n is not exact[0] and _like(result, want, n) >= LIKE]
    return None if rivals else exact[0]


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


#: A text with fewer words of its own than this (an empty proof, "Obvious.") has nothing to recognise it by, and a record on it is followed nowhere but its own key.
TRIVIAL = 4

#: A text with fewer words of its own than this is too short to follow by its words alone where a recorded neighbour says the block holding them is not its own.
SHORT = 6

#: The key of a proof under an id (`ID/proof`, `ID/proof/2`), named by its place among the statement's proofs.
_PROOF_OF_ID = re.compile(r"^[^#]+/proof(/\d+)?$")

#: How far ahead of the next block the closest must read for likeness alone to place a record (`_closest`).
AHEAD = 0.1

#: The fewest words a quote must have to place a record on its own, where it stood in one block of the quilt when the record was written and stands in one now.
QUOTE_WORDS = 4

#: An environment's delimiters and a label, which are no words of a block's own.
_DELIMITERS = re.compile(r"^\\(begin|end)\{[^}]*\}(\[[^\]]*\])?$|^\\label\{[^}]*\}$")

#: A label, left out where a stable key's record asks whether its text stands elsewhere (`_bare_of`).
_LABEL = re.compile(r"\\label\{[^}]*\}")

#: Each scan's derived values, by name; one scan at a time.
_SCAN: tuple[ScanResult, dict[Any, Any]] | None = None

#: How alike a frozen text and a block's text read, by (frozen hash, block hash): the same two texts read alike in every scan, so a build after an edit compares only what changed.
_LIKENESS: dict[tuple[str, str], float] = {}


def _held(result: ScanResult) -> dict[Any, Any]:
    """The values remembered for the scan `result`."""
    global _SCAN
    if _SCAN is None or _SCAN[0] is not result:
        _SCAN = (result, {})
    return _SCAN[1]


def _own_text(result: ScanResult, node: NodeRec) -> str:
    from loom.scan.owntext import own_text

    held = _held(result)
    found = held.get(("text", node.key))
    if found is None:
        found = held[("text", node.key)] = own_text(result, node)
    return str(found)


def _frozen(result: ScanResult, want: str) -> list[str]:
    """The words of the text frozen as `want` when a record was written (`cli.review._version`), child markers left out; [] when the store does not hold it."""
    from loom.records.snapshots import read_snapshot

    held = _held(result)
    found = held.get(("frozen", want))
    if found is None:
        text = read_snapshot(result.quilt.root, want, result.quilt.history_dir)
        found = held[("frozen", want)] = _CHILD.sub("", text).split() if text else []
    return list(found)


def _words(result: ScanResult, node: NodeRec) -> list[str]:
    held = _held(result)
    found = held.get(("words", node.key))
    if found is None:
        found = held[("words", node.key)] = _CHILD.sub("", _own_text(result, node)).split()
    return list(found)


def _own_words(words: list[str]) -> list[str]:
    """The words a person wrote: an environment's delimiters and labels left out."""
    return [w for w in words if not _DELIMITERS.match(w)]


def _likeness(a: list[str], b: list[str]) -> float:
    """How alike two lists of words read, 0 to 1, with the cheap bounds tried first."""
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if m.real_quick_ratio() < LIKE or m.quick_ratio() < LIKE:
        return 0.0
    return m.ratio()


def _like(result: ScanResult, want: str, node: NodeRec) -> float:
    """How alike `node` reads to the text frozen as `want`, remembered across scans by the two texts' hashes (`_LIKENESS`)."""
    pair = (want, block_hash(result, node.key))
    found = _LIKENESS.get(pair)
    if found is None:
        if len(_LIKENESS) > 200_000:
            _LIKENESS.clear()
        found = _LIKENESS[pair] = _likeness(_frozen(result, want), _words(result, node))
    return found


def _still(result: ScanResult, want: str, node: NodeRec, quote: str) -> bool:
    """Whether `node` still reads as a record on it was written: it holds the text frozen as `want`, or the record's quote, or reads `LIKE` alike that text."""
    if block_hash(result, node.key) == want:
        return True
    if quote and quote in _own_text(result, node):
        return True
    return _like(result, want, node) >= LIKE


def _bare(text: str) -> str:
    """`text` as the store keeps it (`normalize`), its labels and child markers left out and its spaces collapsed."""
    from loom.scan.hashing import normalize

    return " ".join(_CHILD.sub("", _LABEL.sub("", normalize(text))).split())


def _bare_frozen(result: ScanResult, want: str) -> str:
    from loom.records.snapshots import read_snapshot

    text = read_snapshot(result.quilt.root, want, result.quilt.history_dir)
    return _bare(text) if text else ""


def _bare_of(result: ScanResult, node: NodeRec) -> str:
    held = _held(result)
    found = held.get(("bare", node.key))
    if found is None:
        found = held[("bare", node.key)] = _bare(_own_text(result, node))
    return str(found)


def _pool(result: ScanResult, path: str) -> list[NodeRec]:
    """Where a record whose key lies in `path` can be found: an agent's copy's blocks for one written in an agent's copy under `.loom/`, the documents' blocks for any other (`_documents`)."""
    if not path.startswith(f"{LOOM}/"):
        return _documents(result)
    held = _held(result)
    found = held.get("copies")
    if found is None:
        found = held["copies"] = [
            n for n in result.nodes.values() if n.kind not in ("master", "file") and n.file.startswith(f"{LOOM}/")
        ]
    return list(found)


def _documents(result: ScanResult) -> list[NodeRec]:
    """The blocks a record can be found on: each document's own text and the blocks of the files a document reads, never an agent's copy under `.loom/` nor a file no document reads (a backup beside the paper)."""
    held = _held(result)
    found = held.get("documents")
    if found is None:
        found = held["documents"] = [
            n
            for n in result.nodes.values()
            if (n.kind == "master" or (n.kind != "file" and n.reached_by)) and not n.file.startswith(f"{LOOM}/")
        ]
    return list(found)


def _mark(result: ScanResult, node: NodeRec) -> str:
    """What a block is recognised by as a neighbour: the hash of its own text with child markers and labels left out, which a child renumbered by a block put in elsewhere, or a label moved onto or off the block, does not change."""
    import hashlib

    held = _held(result)
    found = held.get(("mark", node.key))
    if found is None:
        text = " ".join(_LABEL.sub("", _CHILD.sub("", _own_text(result, node))).split())
        found = held[("mark", node.key)] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
    return str(found)


def _sort(node: NodeRec) -> str:
    """What kind of block `node` is, for likeness to compare like with like: an environment's name, `proof`, or `section` at any level."""
    if node.kind == "environment":
        return node.env or "environment"
    return node.kind


def _in_order(result: ScanResult, path: str) -> list[NodeRec]:
    """The blocks of `path` in file order, documents and files left out: what a record's neighbours are counted among."""
    held = _held(result)
    found = held.get(("order", path))
    if found is None:
        found = held[("order", path)] = sorted(
            (n for n in result.nodes.values() if n.file == path and n.kind not in ("master", "file")),
            key=lambda n: (n.start, -n.end),
        )
    return list(found)


def context_of(result: ScanResult, node: NodeRec, quote: str = "") -> dict[str, Any]:
    """What a record written now on `node` stores to be found again by (`context`); {} for a document or a file, which no block takes the place of.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned now.
    node : NodeRec
        The block the record is written on (a region's container).
    quote : str, default ''
        The words it quotes, if any.

    Returns
    -------
    dict
        `before` and `after`: the nearest block on each side whose text stands once in its file, as `{"hash", "gap"}` with `hash` its text without child markers (`_mark`) with `gap` 1 for the block beside it, or `{"edge": n}` where none does, `n` counting to the file's edge; `kind`, what `_sort` calls it; `copies`, how many blocks of the documents held its very text; `twin`, whether another block of its file reads `LIKE` alike it; `unread`, present and true where no document reads its file; and with a quote, `quote`, how many blocks of the documents it stands in.
    """
    if node.kind in ("master", "file"):
        return {}
    order = _in_order(result, node.file)
    at = next((i for i, n in enumerate(order) if n is node), None)
    out: dict[str, Any] = {}
    if at is not None:
        counts: dict[str, int] = {}
        for n in order:
            counts[_mark(result, n)] = counts.get(_mark(result, n), 0) + 1
        for side, step in (("before", -1), ("after", 1)):
            i, gap = at + step, 1
            while 0 <= i < len(order) and counts[_mark(result, order[i])] != 1:
                i, gap = i + step, gap + 1
            out[side] = {"hash": _mark(result, order[i]), "gap": gap} if 0 <= i < len(order) else {"edge": gap}
    out["kind"] = _sort(node)
    if not any(n is node for n in _pool(result, node.file)):
        out["unread"] = True
    own = block_hash(result, node.key)
    out["copies"] = sum(1 for n in _documents(result) if block_hash(result, n.key) == own) or 1
    words = _words(result, node)
    out["twin"] = any(
        _likeness(words, _words(result, n)) >= LIKE for n in _in_order(result, node.file) if n is not node
    )
    if quote:
        out["quote"] = sum(1 for n in _documents(result) if quote in _own_text(result, n))
    return out


def _sides(result: ScanResult, block: NodeRec, context: dict[str, Any], skip: NodeRec | None = None) -> tuple[int, int]:
    """Of the neighbours `context` recorded, how many still stand at their recorded distance from `block`, and how many say it is not the block: a neighbour standing elsewhere in its file, or a file's edge at another distance. A neighbour that stands nowhere, edited since, says neither."""
    order = [n for n in _in_order(result, block.file) if n is not skip]
    at = next((i for i, n in enumerate(order) if n is block), None)
    if at is None:
        return 0, 0
    held = against = 0
    for side, step in (("before", -1), ("after", 1)):
        rec = context.get(side)
        if not isinstance(rec, dict):
            continue
        if "edge" in rec:
            if (at + 1 if step < 0 else len(order) - at) == rec["edge"]:
                held += 1
            else:
                against += 1
        elif "hash" in rec:
            j = at + step * int(rec.get("gap") or 1)
            if 0 <= j < len(order) and _mark(result, order[j]) == rec["hash"]:
                held += 1
            elif any(_mark(result, n) == rec["hash"] for n in order):
                against += 1
    return held, against


def _all_against(result: ScanResult, blocks: list[NodeRec], context: dict[str, Any], twin: bool) -> bool:
    """Whether none of `blocks`, holding the very text of a record whose context recorded a twin, has a recorded neighbour beside it and none against it: none of them is its block, and one that reads like it between both its neighbours may be."""
    return twin and all(_sides(result, n, context)[1] or not _sides(result, n, context)[0] for n in blocks)


def _told(result: ScanResult, blocks: list[NodeRec], context: dict[str, Any], twin: bool) -> NodeRec | None:
    """Among blocks holding a record's very text, the one that is its: where its context recorded a twin or two copies, only one with a recorded neighbour beside it and none against it, and among several such the one with both beside it; where it recorded none, the one with both neighbours beside it."""
    if twin:
        clear = [n for n in blocks if _sides(result, n, context)[0] and not _sides(result, n, context)[1]]
        if len(clear) <= 1:
            return clear[0] if clear else None
        blocks = clear
    both = [n for n in blocks if _sides(result, n, context)[0] == 2]
    return both[0] if len(both) == 1 else None


def _closest(result: ScanResult, want: str, blocks: list[NodeRec]) -> NodeRec | None:
    """The one block of `blocks` reading at least `LIKE` alike the text frozen as `want`, ahead of every other by `AHEAD`; None when none is, or two read near alike."""
    scored = sorted(((_like(result, want, n), n) for n in blocks), key=lambda s: -s[0])
    if not scored or scored[0][0] < LIKE or (len(scored) > 1 and scored[0][0] - scored[1][0] < AHEAD):
        return None
    return scored[0][1]
