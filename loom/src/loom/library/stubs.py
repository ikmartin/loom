"""Stubs from drafts' citations: a result a draft cites by number in a work the library holds, where the store holds no node of it, becomes a stub `{taxon, number, source}` that digest or an agent fills.

Every build runs it with gathering, before any fragment is drawn (`render.build`), so the build's fragments name the stubs it made. With nothing due it takes no lock, and under the locks it decides again from the store as it is then, so two builds at once make one stub.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loom.library.citations import resolve

if TYPE_CHECKING:
    from loom.scan.scan import ScanResult


def due(result: ScanResult) -> list[tuple[str, str, str]]:
    """The stubs the drafts' citations want and the store lacks, as (reference, taxon, printed number), each once, in the order cited."""
    out: dict[tuple[str, str], tuple[str, str, str]] = {}
    for c in result.edges.cites:
        if c.ref is None:
            continue
        for (taxon, number), node in zip(c.results, c.nodes, strict=True):
            if node is None:
                out.setdefault((c.ref, number), (c.ref, taxon, number))
    return list(out.values())


def make(result: ScanResult, *, write: bool = True) -> list[str]:
    """Make a stub for each result a draft cites by number that the store holds no node of, and resolve the citations again.

    Parameters
    ----------
    result : ScanResult
        The quilt's scan; its citations are resolved (`citations.resolve`) first, as gathering may have made references since, and again after.
    write : bool, default True
        Write the stubs; False says what would be made, and takes no lock.

    Returns
    -------
    list of str
        The ids made, or, not writing, `ref taxon number` for each that would be.
    """
    from loom.library.gather import writing
    from loom.library.node import Node
    from loom.library.references import Minter
    from loom.library.store import write_node

    resolve(result)
    wanted = due(result)
    if not write or not wanted:
        return [" ".join(w) for w in wanted]
    made: list[str] = []
    with writing(result.quilt.root):
        resolve(result)
        minter = Minter.of(result)
        for ref, taxon, number in due(result):
            stem = minter.stem()
            write_node(result.quilt.root, Node(id=stem, taxon=taxon, number=number, source=ref), new=True)
            made.append(stem)
    resolve(result)
    return made
