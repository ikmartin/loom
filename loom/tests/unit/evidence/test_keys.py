"""The evidence lane reads a block's key from a record, an ask or a request as the records resolve one (`evidence.web.blocks_named`, over `ScanResult.node_named` and `records.locate.shared_label`): a record written under a statement's place key is found once a label keys it, a place key is taken wherever a label key is, a label a copied draft defines again names each copy, and a label defined nowhere names nothing."""

from __future__ import annotations

from pathlib import Path

import pytest

from loom.evidence.asks import ask, open_asks, place_of
from loom.evidence.log import write
from loom.evidence.subjects import Who
from loom.evidence.web import DraftWeb, blocks_named
from loom.records.locate import block_hash, context_of
from loom.render.endpoints.base import ApiError
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import demo

PERSON = Who("person", "A. Author")
DOC = "drafting/main.tex"
MAIN = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\begin{lemma}%s
Every widget is bounded, as in \cite{Smi24}.
\end{lemma}
\begin{proof}
Trivially.
\end{proof}
\end{document}
"""


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-24T10:00:00Z")
    q = demo(tmp_path)
    (q / DOC).write_text(MAIN % "", encoding="utf-8")
    return q


def _lemma(root: Path) -> str:
    """The lemma's key now."""
    result = scan(load_quilt(root))
    [key] = [n.key for n in DraftWeb(result).blocks if "Every widget" in DraftWeb(result).text(n)]
    return key


def _label(root: Path) -> None:
    (root / DOC).write_text(MAIN % r"\label{lem:widget}", encoding="utf-8")


def test_a_place_key_names_the_block_once_a_label_keys_it_and_a_label_defined_nowhere_names_nothing(root: Path) -> None:
    place = _lemma(root)
    assert place.startswith(f"{DOC}#")
    _label(root)
    assert _lemma(root) == "lem:widget"
    result = scan(load_quilt(root))
    assert [n.key for n in blocks_named(result, place)] == ["lem:widget"] == [n.key for n in blocks_named(result, "lem:widget")]  # fmt: skip
    assert blocks_named(result, "lem:none") == []


def test_a_which_result_ask_on_a_place_key_closes_by_a_mention_written_once_a_label_keys_the_block(root: Path) -> None:
    place = _lemma(root)
    result = scan(load_quilt(root))
    node = result.nodes[place]
    then = {"key": place, "hash": block_hash(result, place), "context": context_of(result, node)}
    t = ask(root, PERSON, "which-result", "agent", {"block": then}, cites="tq-00B1-ref")
    _label(root)
    result = scan(load_quilt(root))
    node = result.nodes["lem:widget"]
    now = {"key": "lem:widget", "hash": block_hash(result, "lem:widget"), "context": context_of(result, node)}
    write(root, "mention", PERSON, block=now, cites="tq-00B1-ref", undo=False)
    [found] = [s for s in open_asks(root, closed=True, web=DraftWeb(result)) if s.ask.id == t.id]
    assert not found.open, "the ask's place key and the mention's label key name one block"


def test_a_place_key_is_taken_wherever_a_label_key_is(root: Path) -> None:
    from loom.render.endpoints.formal import _formal_plan, here_of
    from loom.render.endpoints.review import _block

    place = _lemma(root)
    _label(root)
    assert place_of(load_quilt(root), place)[0]["block"]["key"] == "lem:widget"
    assert _block(root, place)[0]["block"]["key"] == "lem:widget"
    assert here_of(DraftWeb(scan(load_quilt(root))), place).name == "lem:widget"
    assert [t["key"] for t in _formal_plan(root, {"targets": [place]})["targets"]] == ["lem:widget"]


def test_a_label_a_copied_draft_defines_again_names_each_copy_and_a_request_must_name_one_by_its_place(
    root: Path,
) -> None:
    from loom.errors import ContentError
    from loom.render.endpoints.formal import _formal_plan

    _label(root)
    (root / "drafting" / "copy.tex").write_text(MAIN % r"\label{lem:widget}", encoding="utf-8")
    result = scan(load_quilt(root))
    found = blocks_named(result, "lem:widget")
    assert len(found) == 2 and all(n.key.startswith(("drafting/main.tex#", "drafting/copy.tex#")) for n in found)
    with pytest.raises(ApiError) as caught:
        _formal_plan(root, {"targets": ["lem:widget"]})
    assert caught.value.code == "ambiguous" and all(n.key in caught.value.message for n in found)
    # one copy by its place is one result
    assert [t["key"] for t in _formal_plan(root, {"targets": [found[0].key]})["targets"]] == [found[0].key]
    # the label itself is a place an ask can be on, a subject by label and text; its proof names both copies
    assert place_of(load_quilt(root), "lem:widget")[0] == {"label": "lem:widget"}
    with pytest.raises(ContentError, match="names 2 blocks"):
        place_of(load_quilt(root), "lem:widget/proof")
    with pytest.raises(ApiError) as missing:
        _formal_plan(root, {"targets": ["lem:none"]})
    assert missing.value.code == "no-such-result"
