"""Writing and removing a node (`library.store`): a write is checked against itself and the library as it stands and refused whole, lands by a rename under the library's lock, and touches nothing but the node's file, the lock and the index."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from loom.library.checks import check
from loom.library.index import NodeIndex
from loom.library.node import Node, node_bytes, node_hash, read_node
from loom.library.store import NodeRefused, node_ids, read, remove_node, write_node, write_nodes
from loom.paths import LIBRARY_NODES
from tests.unit.library._examples import fixtures
from tests.unit.library._store import quilt


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / LIBRARY_NODES).iterdir()}


def test_the_nine_files_are_written_one_at_a_time_as_the_store_grows(tmp_path: Path) -> None:
    """Each write is checked against what is already there, so a work comes before its results and a statement before its proof; the files are the spec's."""
    root = tmp_path / "q"
    order = [
        "tq-00A1-ref",
        "tq-00A1-macros",
        "tq-00B1-ref",
        "tq-00B7",
        "tq-00A4",
        "tq-00K3",
        "tq-00K3-proof00",
        "tq-00K5",
        "tq-00K5-proof00",
    ]
    for node_id in order:
        name = f"{node_id}.node"
        assert write_node(root, read_node(fixtures()[name], name)) == node_hash(fixtures()[name])
    assert {p.name: p.read_bytes() for p in (root / LIBRARY_NODES).iterdir()} == fixtures()
    assert node_ids(root) == sorted(order)
    assert check(root) == []


def test_a_write_out_of_order_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "q"
    with pytest.raises(NodeRefused) as caught:
        write_node(root, read_node(fixtures()["tq-00K3.node"], "tq-00K3.node"))
    assert {d.code for d in caught.value.diagnostics} == {"loom:node-parent", "loom:node-edge"}
    assert not (root / LIBRARY_NODES / "tq-00K3.node").exists()


@pytest.mark.parametrize(
    ("node", "code"),
    [
        (Node(id="tq-00K6", taxon="Lemma", source="tq-00A1-ref", body="x\n"), "loom:node-taxon"),
        (Node(id="tq-00K6", taxon="lemma", source="tq-00A1-ref", uses=("tq-00Z9",), body="x\n"), "loom:node-edge"),
        (Node(id="tq-00K6", taxon="lemma", source="tq-00A1-ref", body="By \\ref{tq-00K5}.\n"), "loom:node-body-ref"),
        (Node(id="tq-00K6", taxon="lemma", body=""), "loom:node-incomplete"),
        (Node(id="tq-00C1-ref", taxon="reference", body="@article{smi24, title={x}}\n"), "loom:node-bibtex"),
        (Node(id="tq-00K3-proof01", taxon="proof", source="tq-00A1-ref", title="Proof", body="x\n"), "loom:node-key"),
        (Node(id="TQ-00K3", taxon="lemma", source="tq-00A1-ref", body="x\n"), "loom:node-id"),
    ],
)
def test_a_write_that_would_fail_a_check_is_refused_and_writes_nothing(tmp_path: Path, node: Node, code: str) -> None:
    root = quilt(tmp_path)
    before = snapshot(root)
    with pytest.raises(NodeRefused) as caught:
        write_node(root, node)
    assert code in {d.code for d in caught.value.diagnostics}
    assert snapshot(root) == before


def test_filling_a_stub_is_a_write_over_its_file(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    stub = read(root, "tq-00B7")
    assert stub is not None and stub.empty
    filled = Node(**{**stub.__dict__, "body": "Every bounded set is covered by finitely many balls.\n"})
    digest = write_node(root, filled)
    assert read(root, "tq-00B7") == filled
    assert digest == node_hash(node_bytes(filled)) != node_hash(fixtures()["tq-00B7.node"])
    with NodeIndex.open(root) as index:
        assert [h.row.id for h in index.search("finitely many balls")] == ["tq-00B7"]
        assert index.stubs() == []


def test_a_write_refused_for_what_it_breaks_elsewhere_is_not_refused(tmp_path: Path) -> None:
    """Rewriting the lemma without the anchor a proof points at is the lemma's own text; the proof's failure is said when the store is checked."""
    root = quilt(tmp_path)
    lemma = read(root, "tq-00K3")
    assert lemma is not None
    write_node(
        root, Node(**{**lemma.__dict__, "body": "Let $W$ be a widget (Definition~\\ref{tq-00A4}).\n", "anchors": ()})
    )
    assert [(d.keys[0], d.code) for d in check(root)] == [("tq-00K5-proof00", "loom:node-body-ref")]


def test_removing_a_node_leaves_what_used_it_to_say_so(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    assert remove_node(root, "tq-00A4") is True
    assert remove_node(root, "tq-00A4") is False
    assert read(root, "tq-00A4") is None
    assert {d.keys[0] for d in check(root)} == {"tq-00K3", "tq-00K3-proof00", "tq-00K5"}
    with NodeIndex.open(root) as index:
        assert index.node("tq-00A4") is None
        assert index.uses("tq-00K3") == []


def test_a_write_touches_the_node_the_lock_and_the_index_alone(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    write_node(root, Node(id="tq-00K6", taxon="remark", source="tq-00A1-ref", pages="14", body="A remark.\n"))
    made = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    assert [m for m in made if not m.startswith(LIBRARY_NODES + "/")] == [
        ".loom/cache/library/nodes.sqlite3",
        ".loom/local/library.lock",
    ]
    assert not [m for m in made if m.endswith(".tmp")]


def test_a_proof_s_number_is_one_past_the_largest_seen(tmp_path: Path) -> None:
    from loom.library.store import next_proof
    from loom.library.tags import tag

    root = quilt(tmp_path)
    assert next_proof(root, "tq-00K3") == "tq-00K3-proof01"
    assert next_proof(root, "tq-00A4") == "tq-00A4-proof00"
    tag(root, "tq-00K3-proof00", "short", by="Isaac", kind="person")
    remove_node(root, "tq-00K3-proof00")
    assert next_proof(root, "tq-00K3") == "tq-00K3-proof01", "the tag log still names proof00"


def test_a_proof_git_remembers_is_not_given_again(tmp_path: Path) -> None:
    import subprocess

    from loom.gitprog import usable
    from loom.library.store import next_proof

    if not usable():
        pytest.skip("no git")
    root = quilt(tmp_path)
    write_node(root, Node(id="tq-00K3-proof01", taxon="proof", source="tq-00A1-ref", pages="14", body="Another way.\n"))

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True, capture_output=True
        )

    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "nodes")
    remove_node(root, "tq-00K3-proof01")
    assert next_proof(root, "tq-00K3") == "tq-00K3-proof02"


def test_a_library_stem_is_drawn_from_everything_loom_id_counts(tmp_path: Path) -> None:
    """A stem the author's sources hold, and one only the library holds, are both passed."""
    from loom.library.store import next_stem
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    (q / LIBRARY_NODES).mkdir(parents=True, exist_ok=True)
    (q / LIBRARY_NODES / "dm-0050-ref.node").write_text("+++\n")
    assert next_stem(scan(load_quilt(q))) == "dm-0051"


# ---- the review's findings ---------------------------------------------------------------------------------------------


def _pair() -> list[Node]:
    """A lemma that mentions a remark below it and the remark that uses the lemma, as one paper's results point at each other."""
    return [
        Node(
            id="tq-0M01",
            taxon="lemma",
            source="tq-00A1-ref",
            mentions=("tq-0M02",),
            body="See Remark~\\ref{tq-0M02}.\n",
        ),
        Node(id="tq-0M02", taxon="remark", source="tq-00A1-ref", uses=("tq-0M01",), body="By Lemma~\\ref{tq-0M01}.\n"),
    ]


def test_results_that_point_at_each_other_are_written_together(tmp_path: Path) -> None:
    """N-3: alone, each is refused, the other not being in the library; together they go in, and the store checks clean."""
    root = quilt(tmp_path)
    for node in _pair():
        with pytest.raises(NodeRefused):
            write_node(root, node)
    hashes = write_nodes(root, _pair())
    assert hashes == [node_hash(node_bytes(n)) for n in _pair()]
    assert check(root) == []
    with NodeIndex.open(root) as index:
        assert [r.id for r in index.used_by("tq-0M01")] == ["tq-0M02"]


def test_a_batch_is_refused_whole_with_every_failure(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    bad = Node(id="tq-0M03", taxon="Lemma", source="tq-00A1-ref", body="x\n")
    worse = Node(id="tq-0M04", taxon="lemma", source="tq-00A1-ref", uses=("tq-0Z99",), body="x\n")
    with pytest.raises(NodeRefused) as caught:
        write_nodes(root, [*_pair(), bad, worse])
    assert {(d.keys[0], d.code) for d in caught.value.diagnostics} == {
        ("tq-0M03", "loom:node-taxon"),
        ("tq-0M04", "loom:node-edge"),
    }
    assert read(root, "tq-0M01") is None, "nothing of a refused batch is written"


def test_sixty_results_are_written_in_one_look_at_the_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N-3: a paper's digest under the library's lock is one act, not sixty scans."""
    root = quilt(tmp_path)
    nodes = [
        Node(
            id=f"tq-0N{i:02d}",
            taxon="lemma",
            source="tq-00A1-ref",
            number=f"5.{i}",
            uses=(f"tq-0N{i + 1:02d}",) if i < 59 else (),
            body=f"Lemma {i}.\n",
        )
        for i in range(60)
    ]
    looks: list[str] = []
    real = os.scandir

    def scandir(path: object = ".") -> object:
        looks.append(str(path))
        return real(path)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "scandir", scandir)
    started = time.perf_counter()
    write_nodes(root, nodes)
    took = time.perf_counter() - started
    assert [p for p in looks if p.endswith(LIBRARY_NODES)] == [str(root / LIBRARY_NODES)]
    assert took < 1.0, took
    monkeypatch.undo()
    assert check(root) == []


def test_a_write_of_a_new_node_never_replaces_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N-4: `new` refuses an id the library holds, and one another writer made between the check and the write."""
    root = quilt(tmp_path)
    lemma = read(root, "tq-00K3")
    assert lemma is not None
    with pytest.raises(NodeRefused, match="only new nodes"):
        write_node(root, Node(**{**lemma.__dict__, "body": "Another text.\n"}), new=True)
    assert (root / LIBRARY_NODES / "tq-00K3.node").read_bytes() == fixtures()["tq-00K3.node"]

    theirs = Node(id="tq-0M09", taxon="remark", source="tq-00A1-ref", body="Theirs.\n")
    flushed = os.fsync

    def meanwhile(fd: int) -> None:
        """Another writer's file lands after the checks, as this one's is flushed."""
        if not (root / LIBRARY_NODES / "tq-0M09.node").exists():
            (root / LIBRARY_NODES / "tq-0M09.node").write_bytes(node_bytes(theirs))
        flushed(fd)

    monkeypatch.setattr(os, "fsync", meanwhile)
    with pytest.raises(NodeRefused, match="another hand"):
        write_node(root, Node(id="tq-0M09", taxon="remark", source="tq-00A1-ref", body="Mine.\n"), new=True)
    assert read(root, "tq-0M09") == theirs
    assert not [p for p in (root / LIBRARY_NODES).iterdir() if p.name.endswith(".tmp")]


def test_an_id_in_the_wrong_case_is_no_node(tmp_path: Path) -> None:
    """N-5: on a file system blind to case `TQ-00K3` opens `tq-00K3.node`, which is not its file."""
    root = quilt(tmp_path)
    assert read(root, "TQ-00K3") is None
    assert remove_node(root, "TQ-00K3") is False
    assert read(root, "tq-00K3") is not None


@pytest.mark.parametrize("bad", ["../../victim", "../q/.loom/library/nodes/tq-00K3", "tq-00K3/x", "", "tq-00K3.node"])
def test_what_is_no_id_never_reaches_a_path(tmp_path: Path, bad: str) -> None:
    """N-6."""
    root = quilt(tmp_path)
    (tmp_path / "victim.node").write_bytes(fixtures()["tq-00A4.node"])
    assert read(root, bad) is None
    with pytest.raises(ValueError):
        remove_node(root, bad)
    with pytest.raises(NodeRefused):
        write_node(root, Node(id=bad, taxon="remark", source="tq-00A1-ref", body="x\n"))
    assert (tmp_path / "victim.node").exists()
    assert len(node_ids(root)) == 9


def test_a_file_is_on_the_disk_before_its_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """N-14: the node files are the library's truth, flushed as the author's files are."""
    root = quilt(tmp_path)
    did: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (did.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (did.append("replace"), real_replace(a, b))[1])
    write_node(root, Node(id="tq-0M05", taxon="remark", source="tq-00A1-ref", body="x\n"))
    assert did[:2] == ["fsync", "replace"]


def test_a_killed_writer_s_temporary_file_is_removed_by_the_next(tmp_path: Path) -> None:
    """N-14."""
    root = quilt(tmp_path)
    left = root / LIBRARY_NODES / ".tq-0M06.node.99999.tmp"
    left.write_bytes(b"half a node")
    write_node(root, Node(id="tq-0M07", taxon="remark", source="tq-00A1-ref", body="x\n"))
    assert not left.exists()


def test_one_anchor_numbered_twice_is_refused(tmp_path: Path) -> None:
    """N-24: the header cannot hold it, so the write would drop one number silently."""
    root = quilt(tmp_path)
    lemma = read(root, "tq-00K3")
    assert lemma is not None
    with pytest.raises(NodeRefused, match="two numbers"):
        write_node(root, Node(**{**lemma.__dict__, "anchors": (("tq-00K3-eq00", "3.3"), ("tq-00K3-eq00", "3.4"))}))


def test_a_lone_surrogate_is_refused_not_raised(tmp_path: Path) -> None:
    """N-24."""
    root = quilt(tmp_path)
    with pytest.raises(NodeRefused) as caught:
        write_node(root, Node(id="tq-0M08", taxon="remark", source="tq-00A1-ref", body="half \ud800 a pair\n"))
    assert [d.code for d in caught.value.diagnostics] == ["loom:node-unreadable"]
