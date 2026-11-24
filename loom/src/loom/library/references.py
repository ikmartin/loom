"""Making a reference (`docs/specs/nodes.md` §7): a work's node, its BibTeX entry as its body, its stored documents named by hash, and the act recorded in the library's log.

Every way a work comes in ends here: a drop and a pasted text (the intake), an entry of a bibliography a document reads (gathering), the carry-over of a quilt made by an earlier loom, and a TeX source dropped alone. A reference holding a TeX source gets its macros node from the source's preamble at once. Stems are drawn by a `Minter` under the id lock, from everything `loom id --next` counts, so a reference never takes an id a draft holds or held.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import documents, log
from loom.library.ids import mint_stem
from loom.library.macros import macros_node, preamble_items
from loom.library.node import Node
from loom.library.store import read, remove_node, write_node

if TYPE_CHECKING:
    from loom.scan.bib import BibEntry
    from loom.scan.scan import ScanResult


def entries(root: Path) -> dict[str, tuple[str, BibEntry]]:
    """Each reference's entry by its key as written, with the reference's id: the citekeys the scan knows (`ScanResult.bib`). Where two references hold one key, the first by id has it; a reference whose body holds no entry is passed over."""
    from loom.library.node import NodeUnreadable, read_node
    from loom.library.store import folder
    from loom.scan.bib import parse_bib

    out: dict[str, tuple[str, BibEntry]] = {}
    nodes = folder(root)
    if not nodes.is_dir():
        return out
    for path in sorted(nodes.glob("*-ref.node")):
        try:
            node = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
        for key, entry in parse_bib(node.body).items():
            out.setdefault(key, (node.id, entry))
            break
    return out


def named(result: ScanResult, word: str) -> str | None:
    """The reference `word` names: a reference's id, or the key its entry has, ignoring case; None for neither."""
    from loom.library.ids import REFERENCE, kind_of
    from loom.library.store import exists

    if kind_of(word) == REFERENCE:
        return word if exists(result.quilt.root, word) else None
    if word in result.refs:
        return result.refs[word]
    folded = word.lower()
    return next((ref for key, ref in result.refs.items() if key.lower() == folded), None)


class Minter:
    """Stems for the references one act makes, drawn from what the quilt has seen, read once, and counted on as they are given.

    A writer holds the id lock (`paths.ID_LOCK`) from before it reads what is seen until its last node is written, as every command that draws an id does.
    """

    def __init__(self, prefix: str, seen: Iterable[str]) -> None:
        self.prefix = prefix
        self.seen = list(seen)

    @classmethod
    def of(cls, result: ScanResult) -> Minter:
        """A minter for the scanned quilt: its prefix, and everything `scan.alloc.visible_locals` sees under it."""
        from loom.scan.alloc import visible_locals

        prefix = result.quilt.config.prefix
        return cls(prefix, [f"{prefix}-{local}" for local in visible_locals(result, prefix)])

    def stem(self) -> str:
        """The next stem, which no later call gives again."""
        stem = mint_stem(self.prefix, self.seen)
        self.seen.append(stem)
        return stem


def make(
    root: Path,
    entry: str,
    minter: Minter,
    *,
    by: str,
    kind: str,
    how: str,
    found_by: str = "entry",
    looked_up: bool = False,
    source: str | None = None,
    pdf: str | None = None,
    tex: str | None = None,
) -> Node:
    """Make a reference: its node written under the checks, its act recorded, and its macros node made where it holds a source.

    Parameters
    ----------
    root : Path
        The quilt.
    entry : str
        One BibTeX entry standing alone (`entries.expand_strings` first where it leans on a `@string`).
    minter : Minter
        Gives the reference's stem.
    by, kind : str
        Who makes it: a name, and `person`, `agent` or `loom`.
    how : str
        One of `log.HOW`.
    found_by : str, default 'entry'
        What the work was known by (`log.FOUND_BY`).
    looked_up : bool, default False
        Whether its details came from looking its identifier up.
    source : str, optional
        What it was made from, as a person would name it: a file's name, a `.bib` file's path, an identifier.
    pdf, tex : str, optional
        The hashes of its documents, which the store must hold.

    Returns
    -------
    Node
        The reference as written.

    Raises
    ------
    store.NodeRefused
        When the entry is not one entry standing alone, its key is another reference's, ignoring case, or a node of its id is there already; nothing is written.

    See Also
    --------
    attach : give an existing reference a document.
    """
    from loom.library.entries import read_entry

    for digest, which in ((pdf, "pdf"), (tex, "tex")):
        if digest and not documents.held(root, digest, which):
            raise FileNotFoundError(f"the store holds no {which} {digest}")
    node = Node(id=f"{minter.stem()}-ref", taxon="reference", body=entry.strip() + "\n", pdf=pdf, tex=tex)
    # written only where no node is: a stem another writer gave meanwhile is refused here, never written over
    write_node(root, node, new=True)
    found = read_entry(node.body)
    log.record(
        root, "made", node.id, by=by, kind=kind, how=how, found_by=found_by, looked_up=looked_up, source=source,
        key=found.key if found else None,
    )  # fmt: skip
    if tex:
        remake_macros(root, node.id)
    return node


def attach(
    root: Path, ref: str, which: str, digest: str | None, *, by: str, kind: str, source: str | None = None
) -> Node:
    """Give a reference a document, or with `digest` None take its document of that kind off, recording the act; its macros node follows its source.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.
    which : str
        `pdf` or `tex`.
    digest : str or None
        The document's hash, which the store must hold; None takes the reference's off.
    by, kind : str
        Who acts.
    source : str, optional
        What the document came from, as a person would name it.

    Returns
    -------
    Node
        The reference as written.
    """
    node = read(root, ref)
    if node is None:
        raise FileNotFoundError(f"{ref} is not in the library")
    was = getattr(node, which)
    if digest and not documents.held(root, digest, which):
        raise FileNotFoundError(f"the store holds no {which} {digest}")
    node = replace(node, pdf=digest) if which == "pdf" else replace(node, tex=digest)
    write_node(root, node)
    if digest:
        log.record(root, "filed", ref, by=by, kind=kind, which=which, hash=digest, source=source)
    elif was:
        log.record(root, "unfiled", ref, by=by, kind=kind, which=which, hash=was)
    if which == "tex":
        remake_macros(root, ref)
    return node


def remake_macros(root: Path, ref: str) -> Node | None:
    """Make a reference's macros node again from the source it holds: written when its preamble defines what a macros node holds, removed when the reference holds no source or the preamble defines nothing.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The reference.

    Returns
    -------
    Node or None
        The macros node as written, or None when it has none.
    """
    node = read(root, ref)
    items = preamble_items(documents.source_dir(root, node.tex)) if node is not None and node.tex else []
    made = macros_node(ref, items)
    if made is None:
        remove_node(root, ref.removesuffix("-ref") + "-macros")
        return None
    write_node(root, made)
    return made
