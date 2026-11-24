"""A node's own text, each child cut out and stood for by its marker, and the hash of it that every record of a key holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loom.scan.hashing import child_marker, hash_text

if TYPE_CHECKING:
    from loom.scan.nodes import NodeRec
    from loom.scan.scan import ScanResult


def _provided_by(result: ScanResult, file: str) -> list[str]:
    """The keys a file brings in when it is included: its outermost nodes, in order."""
    nodes = sorted(
        (n for n in result.nodes.values() if n.file == file and n.kind not in ("file", "master")),
        key=lambda n: n.start,
    )
    out: list[str] = []
    reach = -1
    for n in nodes:
        if n.start >= reach:
            out.append(n.key)
            reach = n.end
    return out


def _marker(result: ScanResult, key: str) -> str:
    """The marker a child stands as in its parent's own text: by its place where a label keys it (`NodeRec.marker`), so its parent's hash is the one it had before the label did."""
    return child_marker(result.nodes[key].marker or key)


def _cuts(result: ScanResult, node: NodeRec) -> list[tuple[int, int, str]]:
    """(start, end, marker) for every child of `node` that its own text stands in for: a claimant cut out of the region, and an inclusion of a file whose nodes are children just the same."""
    cuts = [(result.nodes[k].start, result.nodes[k].end, _marker(result, k)) for k in node.claimants]
    seen: set[int] = set()
    for expansion in result.expansions.values():
        for inc in expansion.inclusions:
            if inc.parent != node.file or inc.child is None or inc.site_start in seen:
                continue
            if not (node.start <= inc.site_start and inc.site_end <= node.end):
                continue
            if any(a <= inc.site_start < b for a, b, _ in cuts):
                continue  # inside a claimed child, which already stands for everything within it
            keys = _provided_by(result, inc.child)
            if keys:
                seen.add(inc.site_start)
                cuts.append((inc.site_start, inc.site_end, "".join(_marker(result, k) for k in keys)))
    return sorted(cuts, key=lambda c: c[0])


def own_text(result: ScanResult, node: NodeRec) -> str:
    """The raw own text of a node with a child marker where each child was cut out or included, the text every hash is taken over.

    An inclusion line reads as the nodes the included file provides, so a node's hash is the same whether a child sits inline or in `nodes/<id>.tex`, and moving one there changes no state.
    """
    src = result.files[node.file]
    pieces: list[str] = []
    pos = node.start
    for start, end, marker in _cuts(result, node):
        if start > pos:
            pieces.append(src.text[pos:start])
        pieces.append(marker)
        pos = max(pos, end)
    if node.end > pos:
        pieces.append(src.text[pos : node.end])
    return "".join(pieces)


def key_hash(result: ScanResult, key: str) -> str:
    return hash_text(own_text(result, result.nodes[key]))
