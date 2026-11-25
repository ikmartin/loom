"""Reading and writing one node's file (`library.node`, docs/specs/nodes.md §1–2): the fences, the header's keys and types, loom's one form of header, and the hash."""

from __future__ import annotations

import hashlib

import pytest

from loom.library.node import Node, NodeUnreadable, node_bytes, node_hash, read_node
from tests.unit.library._examples import fixtures, from_spec


def problems(data: bytes, name: str = "tq-00K3.node") -> list[tuple[int, str]]:
    with pytest.raises(NodeUnreadable) as caught:
        read_node(data, name)
    return [(p.check, p.message) for p in caught.value.problems]


def file(header: str, body: str = "") -> bytes:
    return f"+++\n{header}+++\n{body}".encode()


def test_the_fixtures_are_the_nine_files_the_spec_prints() -> None:
    """The fixtures are §12's text byte for byte, so a change to either side fails here until the other follows."""
    spec = from_spec()
    assert len(spec) == 9
    assert fixtures() == spec


@pytest.mark.parametrize("name", sorted(from_spec()))
def test_an_example_reads_and_writes_back_byte_for_byte(name: str) -> None:
    data = fixtures()[name]
    node = read_node(data, name)
    assert node_bytes(node) == data
    assert node.id == name.removesuffix(".node")


def test_the_body_is_every_byte_after_the_second_fence_exactly() -> None:
    body = "Let $x$ be.\n\n+++\n% a comment, and a fence that is only text here\n\\[ a \\]"
    node = read_node(
        file('schema = 1\nid = "tq-00K3"\ntaxon = "lemma"\nsource = "tq-00A1-ref"\n', body), "tq-00K3.node"
    )
    assert node.body == body
    assert node_bytes(node) == file('schema = 1\nid = "tq-00K3"\ntaxon = "lemma"\nsource = "tq-00A1-ref"\n', body)


def test_a_stub_ends_with_the_line_feed_of_its_second_fence() -> None:
    stub = Node(id="tq-00B7", taxon="lemma", number="2.1", source="tq-00B1-ref")
    data = node_bytes(stub)
    assert data.endswith(b'source = "tq-00B1-ref"\n+++\n')
    assert read_node(data, "tq-00B7.node") == stub
    assert stub.empty


def test_a_body_of_whitespace_alone_is_empty_and_written_as_nothing() -> None:
    data = file('schema = 1\nid = "tq-00B7"\ntaxon = "lemma"\nsource = "tq-00B1-ref"\n', "  \n\n")
    node = read_node(data, "tq-00B7.node")
    assert node.empty
    assert node_bytes(node).endswith(b"+++\n")


@pytest.mark.parametrize(
    ("title", "written"),
    [
        ("Widget", '"Widget"'),
        ("The \\emph{widget} bound", "'The \\emph{widget} bound'"),
        ("Hilbert's \\emph{Nullstellensatz}", '"Hilbert\'s \\\\emph{Nullstellensatz}"'),
        ('A "quoted" name', '"A \\"quoted\\" name"'),
        ("tab\there\nand a line", '"tab\\there\\nand a line"'),
        ("bell \x07 and delete \x7f", '"bell \\u0007 and delete \\u007F"'),
        ("Satz von Stokes über $\\partial M$", "'Satz von Stokes über $\\partial M$'"),
    ],
)
def test_a_string_is_written_in_one_form_and_reads_back(title: str, written: str) -> None:
    """A string with a backslash a literal string can hold is written `'…'`, so a LaTeX title reads as LaTeX; every other is a basic string."""
    node = Node(id="tq-00K3", taxon="lemma", title=title, source="tq-00A1-ref", body="x\n")
    data = node_bytes(node)
    assert f"title = {written}\n".encode() in data
    assert read_node(data, "tq-00K3.node") == node


def test_every_key_is_written_in_the_order_of_the_table() -> None:
    node = Node(
        id="tq-00K3-proof01",
        taxon="proof",
        mentions=("tq-00B1-ref",),
        uses=("tq-00A4", "tq-00B7"),
        pages="12-13",
        source="tq-00A1-ref",
        body="By the lemma.\n",
    )
    header = node_bytes(node).decode().split("+++\n")[1]
    assert [line.split(" = ")[0] for line in header.splitlines()] == [
        "schema",
        "id",
        "taxon",
        "source",
        "pages",
        "uses",
        "mentions",
    ]
    assert 'uses = ["tq-00A4", "tq-00B7"]' in header


def test_a_header_in_another_form_is_read_and_written_in_loom_s() -> None:
    data = file("taxon='definition'\nid   =   \"tq-00A4\"\n# a comment\nschema=1\n", "A body.\n")
    node = read_node(data, "tq-00A4.node")
    assert node == Node(id="tq-00A4", taxon="definition", body="A body.\n")
    assert node_bytes(node) == file('schema = 1\nid = "tq-00A4"\ntaxon = "definition"\n', "A body.\n")


def test_the_hash_is_of_the_file_s_bytes() -> None:
    data = fixtures()["tq-00A4.node"]
    assert node_hash(data) == "sha256:" + hashlib.sha256(data).hexdigest()
    assert node_hash(data + b" ") != node_hash(data)


# ---- check 1: the fences and the TOML ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "said"),
    [
        (b'+++\nschema = 1\nid = "tq-00K3"\n+++\n\xff', "is not UTF-8 text"),
        (b"schema = 1\n+++\nbody", "does not begin with a line `+++`"),
        (b"+++\r\nschema = 1\r\n+++\r\n", "a carriage return and a line feed"),
        (b'+++\nschema = 1\nid = "tq-00K3"\n', "has no second line `+++`"),
        (b'+++\nschema = 1\nid = "tq-00K3"\ntaxon = "lemma"\n+++', "second line `+++` does not end with a line feed"),
        (b"+++\nschema = 1\nid = tq-00K3\n+++\n", "header is not TOML"),
        (b" +++\nschema = 1\n+++\n", "does not begin with a line `+++`"),
    ],
)
def test_check_1_a_file_without_its_fences_or_its_toml_is_unreadable(data: bytes, said: str) -> None:
    found = problems(data)
    assert [c for c, _ in found] == [1]
    assert said in found[0][1]
    assert found[0][1].startswith("tq-00K3.node")


# ---- checks 2 to 5: the header ----------------------------------------------------------------------------------------


def test_check_2_the_schema_is_one_this_loom_reads() -> None:
    assert (2, "tq-00A4.node has no `schema`.") in problems(
        file('id = "tq-00A4"\ntaxon = "definition"\n'), "tq-00A4.node"
    )
    assert problems(file('schema = 2\nid = "tq-00A4"\ntaxon = "definition"\n'), "tq-00A4.node") == [
        (2, "tq-00A4.node is schema 2, and this loom reads schema 1.")
    ]
    assert [c for c, _ in problems(file('schema = true\nid = "tq-00A4"\ntaxon = "definition"\n'), "tq-00A4.node")] == [
        2
    ]
    assert [c for c, _ in problems(file('schema = "1"\nid = "tq-00A4"\ntaxon = "definition"\n'), "tq-00A4.node")] == [2]


@pytest.mark.parametrize(
    ("name", "header", "said"),
    [
        ("tq-00A4.node", 'schema = 1\ntaxon = "definition"\n', "tq-00A4.node has no `id`."),
        (
            "tq-00A4.node",
            'schema = 1\nid = "tq-00A5"\ntaxon = "definition"\n',
            "`id` is tq-00A5, where it is its file's name, tq-00A4.",
        ),
        ("widget.node", 'schema = 1\nid = "widget"\ntaxon = "definition"\n', "widget.node is not named by a node's id"),
        ("tq-00a4.node", 'schema = 1\nid = "tq-00a4"\ntaxon = "definition"\n', "is not named by a node's id"),
        ("tq-00A4-proof0.node", 'schema = 1\nid = "tq-00A4-proof0"\ntaxon = "proof"\n', "is not named by a node's id"),
        ("tq-00A4.tex", 'schema = 1\nid = "tq-00A4"\ntaxon = "definition"\n', "is not named by a node's id"),
        ("tq-00A4.node", 'schema = 1\nid = 4\ntaxon = "definition"\n', "`id` is not a string"),
    ],
)
def test_check_3_the_id_is_the_file_s_name_and_an_id(name: str, header: str, said: str) -> None:
    found = problems(file(header), name)
    assert 3 in [c for c, _ in found]
    assert any(said in m for c, m in found if c == 3), found


@pytest.mark.parametrize(
    ("name", "taxon", "said"),
    [
        ("tq-00A1-ref.node", "article", "is a reference by its id, so its taxon is reference, not article."),
        ("tq-00A1-macros.node", "reference", "is a macros node by its id, so its taxon is macros, not reference."),
        ("tq-00K3-proof00.node", "lemma", "is a proof by its id, so its taxon is proof, not lemma."),
        ("tq-00K3.node", "proof", "is a statement by its id, and proof is not a statement's taxon."),
        ("tq-00K3.node", "Lemma", "taxon `Lemma` is not a word of lower-case letters and hyphens."),
        ("tq-00K3.node", "main theorem", "is not a word of lower-case letters and hyphens."),
    ],
)
def test_check_4_the_taxon_agrees_with_the_id(name: str, taxon: str, said: str) -> None:
    node_id = name.removesuffix(".node")
    found = problems(file(f'schema = 1\nid = "{node_id}"\ntaxon = "{taxon}"\n'), name)
    assert [c for c, _ in found] == [4]
    assert said in found[0][1]


def test_check_4_a_statement_s_taxon_is_any_such_word() -> None:
    for taxon in ("lemma", "main-theorem", "other", "conjecture"):
        assert read_node(file(f'schema = 1\nid = "tq-00K3"\ntaxon = "{taxon}"\n', "x\n"), "tq-00K3.node").taxon == taxon
    assert [c for c, _ in problems(file('schema = 1\nid = "tq-00K3"\n'))] == [4]


@pytest.mark.parametrize(
    ("name", "extra", "said"),
    [
        ("tq-00K3.node", 'status = "verified"\n', "has a key `status`, which a node's file does not have."),
        ("tq-00K3.node", 'lean = "Widget.bound"\n', "has a key `lean`"),
        ("tq-00K3.node", 'pdf = "sha256:' + "0" * 64 + '"\n', "`pdf` is not a key of a statement"),
        ("tq-00K3-proof00.node", 'number = "3.2"\n', "`number` is not a key of a proof"),
        ("tq-00K3-proof00.node", 'title = "Proof"\n', "`title` is not a key of a proof"),
        ("tq-00K3-proof00.node", 'label = "pf"\nsource = "tq-00A1-ref"\n', "`label` is not a key of a proof"),
        ("tq-00A1-ref.node", 'title = "Widgets"\n', "`title` is not a key of a reference"),
        ("tq-00A1-macros.node", 'source = "tq-00A1-ref"\n', "`source` is not a key of a macros node"),
        ("tq-00K3.node", 'label = "lem:test"\n', "has `label` and no `source`"),
        ("tq-00K3.node", 'pages = "12"\n', "has `pages` and no `source`"),
        (
            "tq-00K3.node",
            'authors = ["Smith"]\nsource = "tq-00A1-ref"\n',
            "has a key `authors`, which a node's file does not have.",
        ),
        ("tq-00K3.node", "number = 3.2\n", "`number` is not a string"),
        ("tq-00K3.node", 'title = ""\n', "`title` is empty, where a key with nothing to say is left out"),
        ("tq-00K3.node", 'uses = "tq-00A4"\n', "`uses` is not a list of ids"),
        ("tq-00K3.node", "uses = []\n", "`uses` is an empty list"),
        ("tq-00K3.node", 'mentions = ["tq-00A4", 3]\n', "`mentions` is not a list of ids"),
        ("tq-00A1-ref.node", 'pdf = "sha256:ABC"\n', "`pdf` is not `sha256:` and 64 lower-case hexadecimal digits"),
        ("tq-00A1-ref.node", 'tex = "' + "a" * 64 + '"\n', "`tex` is not `sha256:`"),
        ("tq-00K3.node", "[extra]\nkey = 1\n", "has a key `extra`"),
    ],
)
def test_check_5_every_key_is_one_the_table_allows_with_its_type(name: str, extra: str, said: str) -> None:
    node_id = name.removesuffix(".node")
    taxon = {"ref": "reference", "macros": "macros", "proof00": "proof"}.get(node_id.rsplit("-", 1)[-1], "lemma")
    found = problems(file(f'schema = 1\nid = "{node_id}"\ntaxon = "{taxon}"\n{extra}'), name)
    assert 5 in [c for c, _ in found], found
    assert any(said in m for c, m in found if c == 5), found


def test_a_problem_names_its_key_s_line() -> None:
    with pytest.raises(NodeUnreadable) as caught:
        read_node(file('schema = 1\nid = "tq-00K3"\ntaxon = "lemma"\nstatus = "ok"\n'), "tq-00K3.node")
    assert [(p.check, p.line) for p in caught.value.problems] == [(5, 5)]


def test_every_problem_of_a_file_is_said_at_once() -> None:
    found = problems(file('schema = 7\nid = "tq-00K4"\ntaxon = "Lemma"\nstatus = "ok"\n'))
    assert sorted(c for c, _ in found) == [2, 3, 4, 5]


# ---- anchors: the numbers a source prints for its anchors ---------------------------------------------------------------


def test_anchors_are_a_table_on_one_line_in_order() -> None:
    node = Node(
        id="tq-00K3",
        taxon="lemma",
        source="tq-00A1-ref",
        anchors=(("tq-00K3-eq00", "3.3"), ("tq-00K3-it01", "ii")),
        body="x\n",
    )
    data = node_bytes(node)
    assert b'anchors = {tq-00K3-eq00 = "3.3", tq-00K3-it01 = "ii"}\n' in data
    assert read_node(data, "tq-00K3.node") == node


def test_anchors_written_as_a_section_are_read() -> None:
    data = file('schema = 1\nid = "tq-00K3"\ntaxon = "lemma"\n[anchors]\ntq-00K3-eq00 = "3.3"\n', "x\n")
    assert read_node(data, "tq-00K3.node").anchors == (("tq-00K3-eq00", "3.3"),)


@pytest.mark.parametrize(
    ("value", "said"),
    [
        ('["tq-00K3-eq00"]', "is not a table from anchors to the numbers their source prints"),
        ("{tq-00K3-eq00 = 3}", "is not a table from anchors"),
        ("{}", "is an empty table"),
        ('{tq-00K3-eq00 = ""}', "gives an anchor an empty number"),
        ('{tq-00K5-eq00 = "3.3"}', "`anchors` names tq-00K5-eq00, which is not one of tq-00K3's anchors."),
        ('{tq-00K3 = "3.3"}', "`anchors` names tq-00K3, which is not one of tq-00K3's anchors."),
    ],
)
def test_check_5_anchors_number_the_node_s_own_anchors(value: str, said: str) -> None:
    found = problems(file(f'schema = 1\nid = "tq-00K3"\ntaxon = "lemma"\nanchors = {value}\n', "x\n"))
    assert any(c == 5 and said in m for c, m in found), found


def test_anchors_are_not_a_reference_s() -> None:
    found = problems(
        file('schema = 1\nid = "tq-00A1-ref"\ntaxon = "reference"\nanchors = {tq-00A1-eq00 = "1"}\n'),
        "tq-00A1-ref.node",
    )
    assert any(c == 5 and "`anchors` is not a key of a reference" in m for c, m in found), found


def test_found_says_one_of_three_ways() -> None:
    """How loom found a statement's number and page in its work: words, place or compile, and nothing else."""
    from loom.library.node import header_problems

    good = {"schema": 1, "id": "tq-00K3", "taxon": "lemma", "source": "tq-00A1-ref", "found": "place"}
    assert header_problems(good, "tq-00K3.node") == []
    said = header_problems({**good, "found": "guessed"}, "tq-00K3.node")
    assert [p.check for p in said] == [5] and "words, place, compile" in said[0].message
