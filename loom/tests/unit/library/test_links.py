"""Links to the library (`loom.links`): a node by its id under `quilt:`, a place in it by its anchor, `cited:` through the identifiers references state, and `cited:work:` no longer honoured."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.library.intake import Item, take
from loom.library.node import Node
from loom.library.store import write_node
from loom.links import LinkError, resolve
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan


def quilt(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\n')
    load_quilt(root)
    [row] = take(root, [Item(text="@article{Smi24, title = {Widgets}, eprint = {2401.01234v2}}\n")], by="Isaac")
    write_node(
        root,
        Node(
            id="tq-0009", taxon="lemma", source=row.ref, body="\\begin{equation}\\label{tq-0009-eq00}x\\end{equation}\n"
        ),
    )
    return root, row.ref


def test_a_library_node_is_linked_by_its_id(tmp_path: Path) -> None:
    root, ref = quilt(tmp_path)
    result = scan(load_quilt(root))
    assert (resolve(result, root, f"quilt:{ref}").kind, resolve(result, root, f"quilt:{ref}").key) == ("library", ref)
    placed = resolve(result, root, "quilt:tq-0009#tq-0009-eq00")
    assert (placed.kind, placed.place) == ("library", "tq-0009-eq00")
    with pytest.raises(LinkError, match="not a place in tq-0009"):
        resolve(result, root, "quilt:tq-0009#tq-0010-eq00")
    with pytest.raises(LinkError, match="no key tq-00ZZ"):
        resolve(result, root, "quilt:tq-00ZZ")


def test_cited_resolves_through_what_references_state(tmp_path: Path) -> None:
    root, ref = quilt(tmp_path)
    result = scan(load_quilt(root))
    work = resolve(result, root, "cited:arXiv:2401.01234?page=3")
    assert (work.kind, work.key, work.place) == ("work", ref, "page=3")
    with pytest.raises(LinkError, match="no work in the library states"):
        resolve(result, root, "cited:doi:10.1000/none")
    with pytest.raises(LinkError, match="no longer linked by work:"):
        resolve(result, root, "cited:work:abcdef0123456789")
