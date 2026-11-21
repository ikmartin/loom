"""The index (`library.index`): each question it answers, made only when asked, brought up to date after a file is added, changed or removed, and made again when it is old or broken."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import pytest

from loom.library.checks import check
from loom.library.index import NodeIndex, Snippet, snippet, words
from loom.library.node import Node, node_bytes, node_hash
from loom.library.store import read
from loom.library.tags import tag
from loom.paths import LIBRARY_NODES, NODE_INDEX
from tests.unit.library._examples import fixtures
from tests.unit.library._store import quilt


def ids_of(rows: list) -> list[str]:  # type: ignore[type-arg]
    return [r.id for r in rows]


def found(index: NodeIndex, text: str = "", **kw: object) -> list[str]:
    return [h.row.id for h in index.search(text, **kw)]  # type: ignore[arg-type]


def put(root: Path, node: Node) -> None:
    (root / LIBRARY_NODES / node.file_name).write_bytes(node_bytes(node))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return quilt(tmp_path)


def test_this_python_s_sqlite_has_fts5() -> None:
    """The index leans on FTS5; this fails first on any CI image whose Python lacks it."""
    sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(a)")


def test_nothing_is_made_before_it_is_asked_for(root: Path) -> None:
    check(root)
    read(root, "tq-00K3")
    assert not (root / NODE_INDEX).exists()
    with NodeIndex.open(root) as index:
        assert index.count() == 9
    assert (root / NODE_INDEX).is_file()


def test_a_node_by_its_id(root: Path) -> None:
    with NodeIndex.open(root) as index:
        for name, data in fixtures().items():
            node_id = name.removesuffix(".node")
            node = index.node(node_id)
            assert node is not None and node_bytes(node) == data
            row = index.row(node_id)
            assert row is not None and row.hash == node_hash(data)
        assert index.node("tq-00Z9") is None
        assert index.reference("smi24") == index.row("tq-00A1-ref")


def test_a_work_s_nodes_in_the_paper_s_order(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert ids_of(index.work("tq-00A1-ref")) == [
            "tq-00A4",
            "tq-00K3",
            "tq-00K3-proof00",
            "tq-00K5",
            "tq-00K5-proof00",
        ]
        assert ids_of(index.work("tq-00B1-ref")) == ["tq-00B7"]


def test_numbers_are_read_naturally_until_a_place_is_recorded(root: Path) -> None:
    for node_id, number in (("tq-00M1", "3.10"), ("tq-00M2", "3.9"), ("tq-00M3", "A.1"), ("tq-00M4", "10.1")):
        put(root, Node(id=node_id, taxon="remark", number=number, source="tq-00A1-ref", body="x\n"))
    put(root, Node(id="tq-00M5", taxon="remark", source="tq-00A1-ref", pages="2", body="unnumbered\n"))
    with NodeIndex.open(root) as index:
        order = [r.number or "-" for r in index.work("tq-00A1-ref") if r.kind == "statement"]
    assert order == ["2.1", "3.2", "3.4", "3.9", "3.10", "10.1", "A.1", "-"]


def test_what_a_node_uses_and_mentions_and_what_uses_it(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert ids_of(index.uses("tq-00K5-proof00")) == ["tq-00B7", "tq-00K3"]
        assert ids_of(index.mentions("tq-00K5-proof00")) == ["tq-00B1-ref"]
        assert ids_of(index.used_by("tq-00A4")) == ["tq-00K3", "tq-00K3-proof00", "tq-00K5"]
        assert ids_of(index.used_by("tq-00B7")) == ["tq-00K5-proof00"]
        assert ids_of(index.mentioned_by("tq-00B1-ref")) == ["tq-00K5-proof00"]
        assert ids_of(index.proofs("tq-00K3")) == ["tq-00K3-proof00"]
        assert ids_of(index.stubs()) == ["tq-00B7"] == ids_of(index.stubs("tq-00B1-ref"))
        assert index.stubs("tq-00A1-ref") == []


def test_search_over_title_words_and_work(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert found(index, "widget")[0] == "tq-00A4", "a title weighs more than a body"
        assert set(found(index, "widget")) == {"tq-00A4", "tq-00K3", "tq-00K5"}
        assert set(found(index, "widg")) == {"tq-00A4", "tq-00K3", "tq-00K5"}, "the last word is a prefix"
        assert found(index, "widget origin") == ["tq-00K5"], "every word must match"
        assert found(index, "Jones covering") == ["tq-00B7"], "a stub is found by its work"
        assert set(found(index, "Smith 2024")) == {"tq-00A4", "tq-00K3", "tq-00K5"}, "a bare year is a word"
        assert found(index, "nothing-like-this") == []


def test_search_reads_mathematics_but_not_markup_or_ids(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert found(index, "diam") == ["tq-00K3"], "a command's name is a word"
        assert found(index, "mathbb") == [] and found(index, "emph") == [], "markup is not"
        assert found(index, "equation") == [] and found(index, "enumerate") == []
        assert found(index, "eq00") == [] and found(index, "00A4") == [], "ids are not words"
    assert "hom" in words("$\\Hom(A, B) \\otimes \\alpha$").split(), "folded as the index folds"


def test_search_by_number_matches_it_exactly(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert found(index, "3.4") == ["tq-00K5"]
        assert set(found(index, "2.1")) == {"tq-00A4", "tq-00B7"}
        assert found(index, "2.1", work="Smi24") == ["tq-00A4"]
        assert found(index, "2.1", work="tq-00B1-ref") == ["tq-00B7"]
        assert found(index, "3.40") == []


def test_search_by_taxon_and_tag(root: Path) -> None:
    tag(root, "tq-00K5", "Bounds", by="Isaac", kind="person")
    with NodeIndex.open(root) as index:
        assert found(index, taxon="lemma") == ["tq-00K3", "tq-00B7"]
        assert found(index, tag="bounds") == ["tq-00K5"]
        assert found(index, "widget", tag="BOUNDS") == ["tq-00K5"]


def test_search_looks_in_proofs_when_asked_and_marks_the_statement(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert found(index, "triangle inequality") == []
        [hit] = index.search("triangle inequality", proofs=True)
        assert (hit.row.id, hit.in_proof) == ("tq-00K3", "tq-00K3-proof00")
        mixed = {h.row.id: h.in_proof for h in index.search("widget", proofs=True)}
        assert mixed["tq-00K3"] is None, "a statement found in its own words is not marked"


def test_tags_in_the_index_come_from_the_log(root: Path) -> None:
    tag(root, "tq-00K3", "14A20", by="Isaac", kind="person")
    tag(root, "tq-00K5", "14a20", by="Claude agent", kind="agent")
    tag(root, "tq-00K5", "compact", by="Claude agent", kind="agent")
    with NodeIndex.open(root) as index:
        assert index.tags("tq-00K5") == ["14A20", "compact"]
        assert ids_of(index.tagged("14a20")) == ["tq-00K3", "tq-00K5"]
        assert index.tags_in_use() == [("14A20", 2), ("compact", 1)]


# ---- keeping up --------------------------------------------------------------------------------------------------------


def test_one_changed_file_is_read_again_and_nothing_else(tmp_path: Path) -> None:
    root = quilt(tmp_path, aged=True)
    with NodeIndex.open(root) as index:
        pass
    with NodeIndex.open(root, refresh=False) as index:
        assert index.refresh().read == 0
        lemma = index.node("tq-00K3")
        assert lemma is not None
        put(root, Node(**{**lemma.__dict__, "body": lemma.body + "Moreover, the boundary is rectifiable.\n"}))
        done = index.refresh()
        assert (done.read, done.changed, done.removed) == (1, 1, 0)
        assert found(index, "rectifiable") == ["tq-00K3"]


def test_a_file_added_or_removed_is_seen(root: Path) -> None:
    with NodeIndex.open(root) as index:
        put(
            root,
            Node(
                id="tq-00K6",
                taxon="corollary",
                number="3.5",
                source="tq-00A1-ref",
                uses=("tq-00K5",),
                body="Every widget is bounded.\n",
            ),
        )
        index.refresh()
        assert ids_of(index.used_by("tq-00K5")) == ["tq-00K6"]
        assert "tq-00K6" in found(index, "bounded")
        (root / LIBRARY_NODES / "tq-00K6.node").unlink()
        assert index.refresh().removed == 1
        assert index.used_by("tq-00K5") == [] and index.node("tq-00K6") is None


def test_a_change_within_the_same_tick_is_still_seen(root: Path) -> None:
    """Git's racy case: the index looked at a file in the same tick it was written, and it changes again with its size and time as they were."""
    path = root / LIBRARY_NODES / "tq-00A4.node"
    tick = time.time_ns()
    os.utime(path, ns=(tick, tick))
    with NodeIndex.open(root):
        pass
    path.write_bytes(path.read_bytes().replace(b"compact set", b"closed  set"))
    os.utime(path, ns=(tick, tick))
    with NodeIndex.open(root) as index:
        assert found(index, "closed") == ["tq-00A4"]


def test_a_change_to_a_work_s_entry_reaches_its_results(root: Path) -> None:
    with NodeIndex.open(root) as index:
        ref = index.node("tq-00A1-ref")
        assert ref is not None
        put(root, Node(**{**ref.__dict__, "body": ref.body.replace("Smith, Jane", "Smyth, Jane")}))
        index.refresh()
        assert set(found(index, "Smyth")) == {"tq-00A4", "tq-00K3", "tq-00K5"}
        assert found(index, "Smith") == []


def test_a_file_that_does_not_read_is_left_out(root: Path) -> None:
    (root / LIBRARY_NODES / "tq-00K5.node").write_bytes(b"not a node\n")
    with NodeIndex.open(root) as index:
        assert index.node("tq-00K5") is None
        assert index.count() == 8
        assert ids_of(index.used_by("tq-00K3")) == ["tq-00K5-proof00"]


def test_an_index_sqlite_cannot_read_is_made_again(root: Path) -> None:
    (root / NODE_INDEX).parent.mkdir(parents=True)
    (root / NODE_INDEX).write_bytes(b"this is not a database, " * 100)
    with NodeIndex.open(root) as index:
        assert index.count() == 9


def test_an_index_of_another_version_is_made_again(root: Path) -> None:
    with NodeIndex.open(root):
        pass
    db = sqlite3.connect(root / NODE_INDEX)
    db.execute("PRAGMA user_version = 0")
    db.execute("DELETE FROM nodes")
    db.commit()
    db.close()
    with NodeIndex.open(root) as index:
        assert index.count() == 9


def test_it_is_made_again_at_will(root: Path) -> None:
    with NodeIndex.open(root) as index:
        done = index.rebuild()
        assert (done.read, done.changed) == (9, 9)
        assert index.count() == 9
        assert found(index, "widget")[0] == "tq-00A4"


def test_a_quilt_with_no_library_has_an_empty_index(tmp_path: Path) -> None:
    with NodeIndex.open(tmp_path) as index:
        assert index.count() == 0
        assert index.search("widget") == []


# ---- what the views ask beyond the questions ---------------------------------------------------------------------------


def test_an_anchor_s_printed_number(root: Path) -> None:
    with NodeIndex.open(root) as index:
        assert index.anchor_number("tq-00K3-eq00") == "3.3"
        assert index.anchor_number("tq-00K3-eq01") is None


def test_a_hit_says_where_it_matched(root: Path) -> None:
    with NodeIndex.open(root) as index:
        hits = {h.row.id: h for h in index.search("widget")}
        assert hits["tq-00A4"].where == "name" and hits["tq-00A4"].snippet is None, "its title is Widget"
        assert hits["tq-00K3"].where == "text"
        assert {h.where for h in index.search("Jones")} == {"work"}
        assert [h.where for h in index.search("3.4")] == ["name"]
        assert [h.where for h in index.search("lemma 3.2")] == ["name"], "a result's name is its taxon and number"
        [proof] = index.search("triangle", proofs=True)
        assert (proof.where, proof.in_proof) == ("proof", "tq-00K3-proof00")
        assert proof.snippet is not None and proof.snippet.match == "triangle"


def test_a_match_on_the_name_comes_before_one_in_the_text(root: Path) -> None:
    put(root, Node(id="tq-00K6", taxon="remark", number="3.5", source="tq-00A1-ref", body=("A widget, " * 30) + "\n"))
    with NodeIndex.open(root) as index:
        order = [h.row.id for h in index.search("widget")]
        assert order[0] == "tq-00A4" and order.index("tq-00A4") < order.index("tq-00K6")


def test_a_hit_in_the_text_carries_the_words_around_it(root: Path) -> None:
    with NodeIndex.open(root) as index:
        [hit] = [h for h in index.search("origin") if h.row.id == "tq-00K5"]
        assert hit.snippet is not None
        assert (hit.snippet.match, hit.snippet.after) == ("origin", ".")
        assert hit.snippet.before.endswith("lies in a ball about the ")


def test_a_snippet_is_cut_at_spaces_outside_mathematics() -> None:
    body = (
        "Let $W$ be a widget (Definition~\\ref{tq-00A4}). Then the number of weightings of $Q$ of height at most $h$ "
        "is a polynomial in $h$ of degree at most $n$, and $\\Hom(A, B) \\otimes C$ is flat. % a polynomial in a comment\n"
        "\\begin{equation}\\label{tq-00K3-eq00} |x| \\le \\diam W \\end{equation} Über alles.\n"
    )
    poly = snippet(body, ["polynomial"])
    assert poly == Snippet(
        "…the number of weightings of $Q$ of height at most $h$ is a ",
        "polynomial",
        " in $h$ of degree at most $n$, and $\\Hom(A, B) \\otimes C$…",
    )
    hom = snippet(body, ["Hom"])
    assert hom is not None and hom.match == "$\\Hom(A, B) \\otimes C$", "a match inside a formula is the formula"
    diam = snippet(body, ["diam"])
    assert diam is not None and diam.match.startswith("\\begin{equation}") and diam.match.endswith("\\end{equation}")
    weigh = snippet(body, ["weigh"])
    assert weigh is not None and weigh.match == "weightings", "a prefix's match is the whole word"
    uber = snippet(body, ["uber"])
    assert uber is not None and (uber.match, uber.after) == ("Über", " alles."), "accents and case are ignored"
    for unread in (["eq00"], ["emph"], ["equation"], ["comment"], ["nothing"]):
        assert snippet(body, unread) is None, unread


def test_the_generation_moves_when_a_node_or_a_tag_changes_and_not_otherwise(tmp_path: Path) -> None:
    root = quilt(tmp_path, aged=True)
    with NodeIndex.open(root) as index:
        first = index.generation()
        assert index.refresh().generation == first, "nothing changed"
        lemma = index.node("tq-00K3")
        assert lemma is not None
        put(root, Node(**{**lemma.__dict__, "body": lemma.body + "More.\n"}))
        assert index.refresh().generation == first + 1
        (root / LIBRARY_NODES / "tq-00K3.node").touch()
        assert index.refresh().generation == first + 1, "a file touched and not changed is no change"
        tag(root, "tq-00K5", "bounds", by="Isaac", kind="person")
        assert index.refresh().generation == first + 2
        tag(root, "tq-00K5", "Bounds", by="Isaac", kind="person")
        assert index.refresh().generation == first + 2, "a tag written again changes nothing"
        (root / LIBRARY_NODES / "tq-00K6.node").write_bytes(b"not a node\n")
        assert index.refresh().generation == first + 2, "a file that does not read changes no node"


# ---- the review's findings ---------------------------------------------------------------------------------------------


def _lemmas(root: Path, count: int) -> None:
    """`count` lemmas named "Lemma", each a node of its own, written straight into the folder."""
    for i in range(count):
        put(
            root,
            Node(id=f"tq-{1000 + i:04d}", taxon="lemma", number=f"9.{i}", body=f"Lemma body {i} on compact sets.\n"),
        )


def test_a_search_on_a_common_name_reads_no_more_rows_than_it_returns(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """N-1: a word on four hundred statements' names used to turn every one into a row in Python, and test each against a set made again for each."""
    import loom.library.index as index_module

    _lemmas(root, 400)
    with NodeIndex.open(root) as index:
        made: list[int] = []
        real = index_module._row
        monkeypatch.setattr(index_module, "_row", lambda record: (made.append(1), real(record))[1])
        hits = index.search("lemma", limit=10)
        assert len(hits) == 10 and {h.where for h in hits} == {"name"}
        assert len(made) <= 10


def test_a_search_matching_more_names_than_sqlite_takes_variables_answers(root: Path) -> None:
    """N-2: the names matched used to go back to SQLite as one bound variable each, past the 32,766 the SQLite of CI's Pythons takes."""
    _lemmas(root, 120)
    with NodeIndex.open(root) as index:
        index.db.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 50)
        assert len(index.search("lemma", limit=100)) == 100


def test_punctuation_alone_finds_nothing(root: Path) -> None:
    """N-22: a search of no words answered as the empty search does, every statement."""
    with NodeIndex.open(root) as index:
        assert index.search("*") == [] and index.search('"') == [] and index.search("\\") == []
        assert len(index.search("")) == 4, "the empty search is every statement"


def test_the_generation_never_goes_back(root: Path) -> None:
    """N-9: a view holding a generation must never meet it again after the index is made again."""
    with NodeIndex.open(root) as index:
        held = index.generation()
        index.rebuild()
        assert index.generation() > held, "made again at will"
        held = index.generation()
    (root / NODE_INDEX).unlink()
    with NodeIndex.open(root) as index:
        assert index.generation() > held, "made again from nothing"


def test_a_file_put_back_to_its_size_and_time_is_still_seen(tmp_path: Path) -> None:
    """N-15: its change time moved, which no one sets by hand."""
    root = quilt(tmp_path, aged=True)
    path = root / LIBRARY_NODES / "tq-00A4.node"
    with NodeIndex.open(root) as index:
        assert found(index, "widget")[0] == "tq-00A4"
        before = path.stat()
        path.write_bytes(path.read_bytes().replace(b"widget", b"gadget"))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        assert path.stat().st_size == before.st_size
        index.refresh()
        assert "tq-00A4" in found(index, "gadget")


def _work(root: Path, author: str, key: str = "Mul19") -> None:
    put(
        root,
        Node(
            id="tq-0R00-ref",
            taxon="reference",
            body=f"@article{{{key},\n  author = {{{author}}},\n  title = {{Sheaves}},\n  year = {{2019}},\n}}\n",
        ),
    )
    put(root, Node(id="tq-0R01", taxon="lemma", number="1.1", source="tq-0R00-ref", body="A sheaf.\n"))


@pytest.mark.parametrize("author", ['M\\"uller, Karl', 'M{\\"u}ller, Karl', 'M\\"{u}ller, Karl', "Müller, Karl"])
def test_a_work_s_author_written_in_tex_is_found_as_written_and_without_accents(root: Path, author: str) -> None:
    """N-11: `M\"uller` is indexed as "Müller", not as `m` and `uller`."""
    _work(root, author)
    with NodeIndex.open(root) as index:
        assert found(index, "Müller") == ["tq-0R01"]
        assert found(index, "muller") == ["tq-0R01"]


def test_named_letters_and_accents_written_in_tex_are_read() -> None:
    from loom.library.index import _accents

    assert (
        _accents('Erd\\H{o}s and {\\o}ystein and G{\\"o}del and Kova{\\v c} and \\L{}ojasiewicz')
        == "Erdős and øystein and Gödel and Kovač and Łojasiewicz"
    )


def test_a_citekey_is_found_ignoring_the_case_of_any_letter(root: Path) -> None:
    """N-13: the index folds keys as the checks do, not as SQLite's NOCASE, which folds ASCII alone."""
    _work(root, "Müller, Karl", key="Müller19")
    with NodeIndex.open(root) as index:
        assert index.keyed("MÜLLER19") == frozenset({"tq-0R00-ref"})
        row = index.reference("müller19")
        assert row is not None and row.id == "tq-0R00-ref"


def test_a_folder_where_the_index_belongs_is_replaced(root: Path) -> None:
    """N-19."""
    (root / NODE_INDEX).mkdir(parents=True)
    (root / NODE_INDEX / "junk").write_text("x")
    with NodeIndex.open(root) as index:
        assert index.count() == 9


def test_an_index_at_this_version_missing_a_table_is_made_again(root: Path) -> None:
    """N-19: a damaged index is made again, not refused on every question."""
    with NodeIndex.open(root):
        pass
    db = sqlite3.connect(root / NODE_INDEX)
    db.execute("DROP TABLE anchors")
    db.commit()
    db.close()
    with NodeIndex.open(root) as index:
        assert index.anchor_number("tq-00K3-eq00") == "3.3"


def test_an_anchor_s_number_is_read_by_its_key(root: Path) -> None:
    """N-21: by the owner the anchor names, which the table's key starts with, not a scan."""
    with NodeIndex.open(root) as index:
        plans: list[str] = []
        real = index.db

        class Spy:
            def execute(self, sql: str, args: object = ()) -> sqlite3.Cursor:
                if "FROM anchors" in sql:
                    plans.extend(r[3] for r in real.execute("EXPLAIN QUERY PLAN " + sql, args))  # type: ignore[arg-type]
                return real.execute(sql, args)  # type: ignore[arg-type]

        index.db = Spy()  # type: ignore[assignment]
        try:
            assert index.anchor_number("tq-00K3-eq00") == "3.3"
            assert index.anchor_number("not an anchor") is None
        finally:
            index.db = real
        assert plans and all(p.startswith("SEARCH") for p in plans), plans


def test_a_snippet_in_a_long_display_is_the_line_that_holds_the_word() -> None:
    """N-12: a hit in a display of two hundred lines is not the display."""
    lines = "\n".join(f"  a_{{{i}}} &= b_{{{i}}} + c_{{{i}}} \\\\" for i in range(200))
    body = f"Before.\n\\begin{{align}}\n{lines}\n  z &= \\zeta\n\\end{{align}}\nAfter.\n"
    hit = snippet(body, ["zeta"])
    assert hit is not None
    assert hit.match == "z &= \\zeta" and (hit.before, hit.after) == ("…", "…")
    one = (
        "x = "
        + " + ".join(f"y_{{{i}}}" for i in range(200))
        + " + \\zeta + "
        + " + ".join(f"w_{{{i}}}" for i in range(200))
    )
    long = snippet(f"\\[ {one} \\]\n", ["zeta"])
    assert long is not None and "\\zeta" in long.match and len(long.match) <= 160
    short = snippet("Then $a + \\zeta$ holds.\n", ["zeta"])
    assert short is not None and short.match == "$a + \\zeta$"


@pytest.mark.parametrize(
    ("written", "typed"), [("Straße", "strasse"), ("strasse", "Straße"), ("ﬁnite", "finite"), ("finite", "ﬁnite")]
)
def test_a_word_is_found_as_its_letters_are_folded_in_full(root: Path, written: str, typed: str) -> None:
    """N-22: ß folds to ss and a ligature is its letters, in the index and in what is typed alike."""
    put(root, Node(id="tq-0P01", taxon="lemma", number="7.1", source="tq-00A1-ref", body=f"A {written} sequence.\n"))
    with NodeIndex.open(root) as index:
        hits = index.search(typed)
        assert [h.row.id for h in hits] == ["tq-0P01"]
        assert hits[0].snippet is not None and hits[0].snippet.match == written
