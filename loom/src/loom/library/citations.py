"""What each citation of a draft reaches in the library: the reference its key names, and the node of each result its postnote locates (`library.stubs` makes those the store lacks)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import ids
from loom.scan.postnote import located

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult

#: A work's statements as the store holds them: (taxon, printed number, id) for each that has a number.
Numbered = dict[str, list[tuple[str, str, str]]]


def resolve(result: ScanResult) -> None:
    """Resolve every citation the scan found, as the store holds the library now.

    Each `CiteRec` gets its reference (`references.named`), the results its postnote locates, the node of its work holding each by printed number, the taxon breaking a tie, and its target: the node where it locates one result the store holds, else its reference.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan; its citations are resolved in place.
    """
    from loom.library.references import named

    cites = result.edges.cites
    for c in cites:
        c.ref = named(result, c.citekey)
        c.results = tuple(located(c.postnote)) if c.postnote else ()
    works = numbered(result.quilt.root, {c.ref for c in cites if c.ref and c.results})
    for c in cites:
        c.nodes = tuple(node_of(works, c.ref, taxon, number) for taxon, number in c.results) if c.ref else ()
        c.target = c.nodes[0] if len(c.nodes) == 1 and c.nodes[0] else c.ref


def numbered(root: Path, refs: set[str]) -> Numbered:
    """The numbered statements of the works `refs` name, read from the store's files."""
    from loom.library.node import NodeUnreadable, read_node
    from loom.library.store import folder

    out: Numbered = {ref: [] for ref in refs}
    nodes = folder(root)
    if not refs or not nodes.is_dir():
        return out
    for path in sorted(nodes.glob("*.node")):
        if ids.kind_of(path.stem) != ids.STATEMENT:
            continue
        try:
            node = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
        if node.source in out and node.number:
            out[node.source].append((node.taxon, node.number, node.id))
    return out


def node_of(works: Numbered, ref: str, taxon: str, number: str) -> str | None:
    """The statement of `ref` printed with `number`, the one of `taxon` where two share it; None where it holds none."""
    same = [(t, n, i) for t, n, i in works.get(ref, []) if n == number]
    return next((i for t, _n, i in same if t == taxon), same[0][2] if same else None)
