"""A node's id (`library.ids`, docs/specs/nodes.md §3, §5): the grammar, the kind each suffix makes, parentage read from the id, anchors, and minting that never gives a number seen before."""

from __future__ import annotations

import pytest

from loom.library.ids import (
    MACROS,
    PROOF,
    REFERENCE,
    STATEMENT,
    anchor_owner,
    kind_of,
    mint_proof,
    mint_stem,
    parent_of,
    parse_id,
)


@pytest.mark.parametrize(
    ("text", "kind", "parent"),
    [
        ("tq-00K3", STATEMENT, None),
        ("tq-00A1-ref", REFERENCE, None),
        ("tq-00A1-macros", MACROS, "tq-00A1-ref"),
        ("tq-00K3-proof00", PROOF, "tq-00K3"),
        ("tq-00K3-proofZZ", PROOF, "tq-00K3"),
        ("Q7x-0001", STATEMENT, None),
    ],
)
def test_an_id_s_suffix_says_its_kind_and_whose_it_is(text: str, kind: str, parent: str | None) -> None:
    parsed = parse_id(text)
    assert parsed is not None
    assert (parsed.kind, parsed.parent, kind_of(text), parent_of(text)) == (kind, parent, kind, parent)


@pytest.mark.parametrize(
    "text",
    [
        "tq-00k3",
        "tq-0K3",
        "tq-00K3X",
        "tq_00K3",
        "-00K3",
        "tq-00K3-proof0",
        "tq-00K3-proof000",
        "tq-00K3-proofab",
        "tq-00K3-Ref",
        "tq-00K3-ref-macros",
        "tq-00K3-proof00-ref",
        "tq-00K3-eq00",
        "def:widget",
        "Jon19",
        "",
    ],
)
def test_anything_else_is_no_id(text: str) -> None:
    assert parse_id(text) is None
    assert kind_of(text) is None


@pytest.mark.parametrize(
    ("text", "owner"),
    [
        ("tq-00K3-eq00", "tq-00K3"),
        ("tq-00K3-it0A", "tq-00K3"),
        ("tq-00K3-proof01-eq02", "tq-00K3-proof01"),
        ("tq-00K3", None),
        ("tq-00A1-ref-eq00", None),
        ("tq-00K3-eq0", None),
        ("tq-00K3-fig00", None),
    ],
)
def test_an_anchor_is_a_place_inside_a_statement_or_a_proof(text: str, owner: str | None) -> None:
    assert anchor_owner(text) == owner


def test_a_stem_is_one_past_the_largest_seen_under_the_prefix() -> None:
    assert mint_stem("tq", []) == "tq-0001"
    assert mint_stem("tq", ["tq-00K3.node", "tq-00A1-ref", "q-0ZZZ", "tq-0009"]) == "tq-00K4"
    assert mint_stem("tq", ["tq-00ZZ"]) == "tq-0100"


def test_a_stem_is_seen_wherever_it_is_written() -> None:
    """Inside a proof's or an anchor's id, a line of a record, or a draft's `\\ref`; not inside a longer prefix's id."""
    assert mint_stem("tq", ['{"node": "tq-00K3-proof00", "tag": "x"}']) == "tq-00K4"
    assert mint_stem("tq", ["\\eqref{tq-0100-eq00}"]) == "tq-0101"
    assert mint_stem("tq", ["xtq-0ZZZ", "tq-0ZZZx", "tq-00A1"]) == "tq-00A2"


def test_a_proof_number_is_one_past_the_largest_seen() -> None:
    assert mint_proof("tq-00K3", []) == "tq-00K3-proof00"
    assert mint_proof("tq-00K3", ["tq-00K3-proof00.node", "tq-00K3-proof01.node"]) == "tq-00K3-proof02"
    assert mint_proof("tq-00K3", ["tq-00K3-proof09", "tq-00K4-proof0Z"]) == "tq-00K3-proof0A"


def test_a_removed_proof_s_number_is_not_given_again_where_it_is_seen() -> None:
    """`proof01` is gone from the store; a record still names it, so the next proof is `proof02`, and `proof02` is not renumbered when `proof00` goes."""
    store = ["tq-00K3-proof00.node"]
    record = '{"event": "tag", "node": "tq-00K3-proof01", "tag": "short"}'
    assert mint_proof("tq-00K3", [*store, record]) == "tq-00K3-proof02"
    assert mint_proof("tq-00K3", ["tq-00K3-proof01-eq00"]) == "tq-00K3-proof02"


def test_only_a_statement_has_proofs() -> None:
    for text in ("tq-00A1-ref", "tq-00K3-proof00", "widget"):
        with pytest.raises(ValueError, match="not a statement"):
            mint_proof(text, [])


def test_numbers_run_out_loudly() -> None:
    with pytest.raises(ValueError, match="every four-character id"):
        mint_stem("tq", ["tq-ZZZZ"])
    with pytest.raises(ValueError, match="every proof number"):
        mint_proof("tq-00K3", ["tq-00K3-proofZZ"])


def test_a_git_pattern_escapes_only_what_an_extended_pattern_reads() -> None:
    """N-28: `re.escape` writes `\\-`, which POSIX leaves undefined in `git grep -E`; an id's hyphen needs no escape."""
    from loom.scan.alloc import git_escape

    assert git_escape("tq-00K3") == "tq-00K3"
    assert git_escape("a.b+c(d)") == "a\\.b\\+c\\(d\\)"
