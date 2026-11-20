"""Where a record goes (`records.locate.follow`): a key named by place is never read on the block that took its place, a renamed file is followed by its text, and a region whose label went is read in the block it was in."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import edit, ok
from tests.unit._quilts import demo

WHO = "Tester"
OUTLINE = "drafting/outline.tex"
CONSIDERED = "drafting/outline.tex#section:2"


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author(WHO)
    return demo(tmp_path)


def note(q: Path, key: str, *more: str) -> str:
    return ok("annotate", key, "Which?", *more, "--type", "question", "--as", WHO, cwd=q).output.split()[0]


def row(q: Path, ann: str) -> dict[str, Any]:
    from loom.cli._quilt import open_scan
    from loom.records.store import Records

    result = open_scan(str(q))
    manifest: dict[str, Any] = {"nodes": {}, "keys": {}, "diagnostics": []}
    Records(q, result.quilt.history_dir).apply(result, manifest)
    return manifest["annotations"][ann]  # type: ignore[no-any-return]


def unrecorded(q: Path) -> None:
    """Take `context` off every annotation in the log: what a record written before it was recorded is."""
    log = q / ".loom/records/annotations/log.jsonl"
    lines = [json.loads(line) for line in log.read_text().splitlines() if line]
    log.write_text("".join(json.dumps({k: v for k, v in e.items() if k != "context"}) + "\n" for e in lines))


@pytest.mark.parametrize("context", [True, False])
def test_a_note_on_a_key_named_by_place_is_never_read_on_the_block_put_in_at_its_place(q: Path, context: bool) -> None:
    whole = note(q, CONSIDERED)
    quoted = note(q, CONSIDERED, "--quote", "Neither of these is proved.")
    if not context:
        unrecorded(q)
    edit(
        q / OUTLINE,
        "\\section{What is being considered}",
        "\\section{Notation}\nA word on notation.\n\n\\section{What is being considered}",
    )
    edit(q / OUTLINE, "the question owes nothing.", "the question owes nothing at all.")
    for ann in (whole, quoted):
        got = row(q, ann)
        if context:
            # the one section that reads like the one it was written on, moved below the new one
            assert got["detached"] is False and got["target"]["key"] == "drafting/outline.tex#section:3", got
        else:
            # nothing says where its block went: detached, and the section put in at its place does not take it
            assert got["detached"] is True and got["target"]["key"] == CONSIDERED, got


@pytest.mark.parametrize("context", [True, False])
def test_a_note_on_a_block_rewritten_where_it_stands(q: Path, context: bool) -> None:
    whole = note(q, CONSIDERED)
    if not context:
        unrecorded(q)
    edit(q / OUTLINE, "the question owes nothing.", "the question owes nothing at all.")
    got = row(q, whole)
    assert (got["detached"], got["target"]["key"]) == (False, CONSIDERED)
    edit(
        q / OUTLINE,
        "Neither of these is proved. The conjecture owes a proof and appears among the blockers until it is proved or refuted; the question owes nothing at all.",
        "Two loose ends, recorded so they are not forgotten.",
    )
    # rewritten past recognition: with the neighbours it recorded standing either side, it is the block it was written on; with none, the block at its place no longer reads like it
    assert row(q, whole)["detached"] is (not context)


def test_a_note_follows_its_text_into_a_renamed_file(q: Path) -> None:
    ann = note(q, CONSIDERED, "--quote", "Neither of these is proved.")
    (q / OUTLINE).rename(q / "drafting/plan.tex")
    got = row(q, ann)
    assert got["target"]["key"] == "drafting/plan.tex#section:2"
    assert (got["detached"], got["anchored"]) == (False, True)


def test_a_note_on_an_equation_whose_label_went_is_read_in_the_block_it_was_in(q: Path) -> None:
    ann = note(q, "dm-0001#eq:fix", "--quote", "x\\in X : \\sigma x = x")
    edit(q / "drafting/nodes/dm-0001.tex", "\\label{eq:fix}", "\\label{eq:fixed}")
    got = row(q, ann)
    assert got["target"]["key"] == "dm-0001"
    assert (got["detached"], got["anchored"]) == (False, True)


def test_an_edit_follows_its_text_into_a_renamed_file_and_is_written_there_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.test_write_safety import call, suggest, synthetic

    root = synthetic(tmp_path, monkeypatch)
    eid = suggest(
        root,
        "drafting/sections/appendix.tex#remark:1",
        "no gadget has odd order",
        "--quote",
        "gadgets never have odd order",
    )
    assert eid is not None
    (root / "drafting/sections/appendix.tex").rename(root / "drafting/sections/later.tex")
    edit(root / "drafting/main.tex", "\\nest{sections/appendix}", "\\nest{sections/later}")
    assert call(root, "change-keep", {"changes": [eid]})["done"] == [eid]
    text = (root / "drafting/sections/later.tex").read_text()
    assert text.count("no gadget has odd order") == 1 and "gadgets never have odd order" not in text


def test_a_note_on_an_id_stays_on_its_rewritten_block_and_under_verify_is_detached(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.records import locate

    whole = note(q, "dm-0002")
    quoted = note(q, "dm-0002", "--quote", "is the union of the one-point orbits")
    lemma = q / "drafting/nodes/dm-0002.tex"
    edit(lemma, "has one or two points", "has one or at most two points")
    # a word put in: it reads as it was written, so either way it is read there
    monkeypatch.setattr(locate, "VERIFY", True)
    assert row(q, whole)["detached"] is False and row(q, quoted)["detached"] is False
    edit(
        lemma,
        "Every orbit of a widget has one or at most two points, and $\\Fix(\\sigma)$ is the union of the one-point orbits.",
        "No widget is large.",
    )
    # rewritten past recognition: the id keeps it, unless records are read against their text
    assert row(q, whole)["detached"] is True and row(q, quoted)["detached"] is True
    monkeypatch.setattr(locate, "VERIFY", False)
    assert row(q, whole)["detached"] is False and row(q, whole)["target"]["key"] == "dm-0002"


def test_two_sections_suggested_after_one_quote_are_never_written_in_reverse_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The queue's item 56: a section kept after `\\maketitle` becomes a block of its own, so the document's own text there reads as it did; the file's words beside the place (`context["beside"]`) do not, and the second is unplaced once the first is kept."""
    from tests.unit.test_write_safety import call, suggest, synthetic

    root = synthetic(tmp_path, monkeypatch)
    main = root / "drafting/main.tex"
    first = suggest(root, "drafting/main.tex", "\\section*{First}\nOne.", "--quote", "\\maketitle", "--after")
    second = suggest(root, "drafting/main.tex", "\\section*{Second}\nTwo.", "--quote", "\\maketitle", "--after")
    assert first and second
    assert call(root, "change-keep", {"changes": [first]})["done"] == [first]
    answer = call(root, "change-keep", {"changes": [second]})
    assert answer["done"] == [] and "have changed since it was suggested" in answer["refused"][0]["why"]
    text = main.read_text()
    assert text.count("\\section*{First}") == 1 and "\\section*{Second}" not in text


def test_a_note_on_one_of_two_empty_answers_is_told_from_its_twin_by_its_neighbours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SAFE-4's shape for notes: two empty answers read the same, and an answer put in above renumbers them; the note goes with the answer its neighbours say it was written on."""
    from tests.unit.test_write_safety import call, scan, synthetic

    root = synthetic(tmp_path, monkeypatch)
    main = root / "drafting/main.tex"
    empty = "\\begin{proof}[Answer]\n\\end{proof}\n"
    edit(main, "\\end{document}", f"\\section*{{One}}\n{empty}\\section*{{Two}}\n{empty}\\end{{document}}")
    result = scan(root)
    last = max((n.start, k) for k, n in result.nodes.items() if k.startswith("drafting/main.tex#proof:"))[1]
    said = call(root, "annotate", {"target": last, "message": "Which?", "type": "question"})
    ann = said["result"].split()[0]
    edit(main, "\\section*{One}", f"\\section*{{Zero}}\n{empty}\\section*{{One}}")
    got = row(root, ann)
    after = scan(root)
    assert got["detached"] is False and got["target"]["key"] != last
    # the answer under Two, wherever its key now numbers it
    assert (
        after.files["drafting/main.tex"]
        .text[: after.nodes[got["target"]["key"]].start]
        .rstrip()
        .endswith("\\section*{Two}")
    )


def test_a_record_written_now_holds_its_context(q: Path) -> None:
    import json as _json

    note(q, CONSIDERED, "--quote", "Neither of these is proved.")
    (event,) = [
        e
        for e in map(_json.loads, (q / ".loom/records/annotations/log.jsonl").read_text().splitlines())
        if e.get("target") == CONSIDERED
    ]
    context = event["context"]
    assert {"before", "after", "kind", "copies", "twin", "quote"} <= set(context)
    assert context["kind"] == "section" and context["copies"] == 1 and context["quote"] == 1


def test_an_acceptance_goes_with_its_statement_once_one_is_put_in_above_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KEY-9 of the study: an acceptance on a key named by place stayed on the key, so the statement put in above read "accepted, stale" and the one accepted read draft. A row is a claim about exact text, and goes with it."""
    from tests.helpers import json_of
    from tests.unit.test_write_safety import synthetic

    root = synthetic(tmp_path, monkeypatch)
    remark = "drafting/sections/appendix.tex#remark:1"
    ok("accept", remark, "--force", "--as", "Pat", cwd=root)
    assert json_of("status", "--json", cwd=root)["keys"][remark]["state"] == "accepted"
    edit(
        root / "drafting/sections/appendix.tex",
        "\\begin{remark}\nAn unlabelled remark",
        "\\begin{remark}\nA remark a co-author put in above.\n\\end{remark}\n\\begin{remark}\nAn unlabelled remark",
    )
    keys = json_of("status", "--json", cwd=root)["keys"]
    assert keys[remark]["state"] == "draft"
    moved = keys["drafting/sections/appendix.tex#remark:2"]
    assert moved["state"] == "accepted" and moved["acceptance"]["fresh"]
