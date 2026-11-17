"""Suggested edits (plan 0.30, decision 10): filed with `loom suggest`, placed by `replace`, `before` and `after` or on the key's body, printed as a patch, kept or discarded by the person, published with their change, and told to the agent that suggested them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loom.records.edits import (
    Edit,
    Unplaced,
    body_span,
    find,
    is_taken,
    patch,
    place,
    replay,
    taken_how,
    where_taken,
)
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import copy, edit, exits, flat, json_of, ok, refused, run
from tests.unit._quilts import demo

LEMMA = "drafting/nodes/dm-0002.tex"
AGENT = {"AI_AGENT": "1"}


@pytest.fixture(autouse=True)
def tom() -> None:
    """The person keeping and discarding, by the name their config gives `loom changes`."""
    from loom.scan.quilt import save_author

    save_author("Tom")


def suggest(q: Path, *args: str, who: str = "Tom", key: str = "dm-0002", env: dict[str, str] | None = None) -> str:
    """File a suggested edit on `key`, returning its id."""
    return str(json_of("suggest", key, *args, "--as", who, "--json", cwd=q, env=env)["edit"])


def placed(q: Path, edit_id: str) -> tuple[Any, Edit]:
    found = find(q, edit_id)
    assert found is not None
    return scan(load_quilt(q)), found


def log(q: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (q / ".loom/edits" / "log.jsonl").read_text().splitlines() if x.strip()]


def test_filing_records_the_key_the_words_the_new_text_and_where_it_goes(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ann = ok("annotate", "dm-0002", "Too vague.", "--type", "revision", "--as", "Tom", cwd=q).stdout.split()[0]
    said = ok(
        "suggest", "dm-0002", "--quote", "one or two points", "--with", "at most two points", "--answers", ann,
        "--comment", "Sharper.", "--as", "Tom", cwd=q,
    ).stdout  # fmt: skip
    e = log(q)[-1]
    assert said.startswith(e["id"]) and e["id"].startswith("e-") and "replace" in said and "dm-0002" in said
    assert (e["target"], e["anchor"]["exact"], e["with"], e["placement"], e["answers"], e["comment"]) == (
        "dm-0002",
        "one or two points",
        "at most two points",
        "replace",
        ann,
        "Sharper.",
    )
    assert e["against"].startswith("sha256:") and (e["author"], e["kind"]) == ("Tom", "human")
    before = suggest(q, "--quote", "Every orbit", "--with", "Plainly,", "--before")
    after = suggest(q, "--quote", "one or two points", "--with", "(and never more)", "--after")
    body = suggest(q, "--with", "\\uses{dm-0001}", "--before")
    assert [find(q, x).placement for x in (before, after, body)] == ["before", "after", "before"]  # type: ignore[union-attr]
    assert find(q, body).selector is None  # type: ignore[union-attr]
    # the new text from stdin, as LaTeX a shell would mangle
    piped = json_of(
        "suggest",
        "dm-0002",
        "--quote",
        "Every orbit",
        "--with",
        "-",
        "--as",
        "Tom",
        "--json",
        cwd=q,
        stdin="Each orbit",
    )
    assert find(q, piped["edit"]).with_text == "Each orbit"  # type: ignore[union-attr]
    # a dry run writes nothing
    n = len(log(q))
    ok("suggest", "dm-0002", "--with", "x", "--dry-run", "--as", "Tom", cwd=q)
    assert len(log(q)) == n


def test_what_an_edit_cannot_say_is_refused_by_name(tmp_path: Path) -> None:
    q = demo(tmp_path)
    before = log(q)
    base = ("suggest", "dm-0002", "--as", "Tom")
    refused(*base, "--quote", "no such words", "--with", "x", cwd=q, code=2, match="quote not found in dm-0002")
    refused(*base, "--quote", "o", "--with", "x", cwd=q, code=2, match="ambiguous")
    refused(*base, "--with", "x", "--before", "--after", cwd=q, code=2, match="--before and --after")
    refused(*base, "--with", "x", "--answers", "a-1999-01-01-ekn992", cwd=q, code=2, match="no annotation")
    refused(*base, "--with", "", cwd=q, code=2, match="needs --quote")
    refused(
        *base, "--quote", "Every orbit", "--with", "", "--after", cwd=q, code=2, match="neither --before nor --after"
    )
    refused(*base, "--quote", "Every orbit", "--with", "Every orbit", cwd=q, code=2, match="changes nothing")
    refused("suggest", "dm-9999", "--with", "x", "--as", "Tom", cwd=q, code=2, match="dm-9999")
    assert log(q) == before


def test_replace_takes_exactly_the_quoted_words(tmp_path: Path) -> None:
    q = demo(tmp_path)
    p_ = place(*placed(q, suggest(q, "--quote", "one or two points", "--with", "at most two points")))
    assert p_.taken.count("at most two points") == 1 and "one or two points" not in p_.taken
    assert p_.own.replace("one or two points", "at most two points") == p_.taken and not p_.moved
    result, e = placed(q, find_last(q))
    assert patch(result, place(result, e)).startswith(f"--- a/{LEMMA}")


def find_last(q: Path) -> str:
    return replay(q)[0][-1].id


def test_after_and_before_go_right_beside_the_quote_joined_by_a_space(tmp_path: Path) -> None:
    q = demo(tmp_path)
    after = suggest(q, "--quote", "one or two points", "--with", "(and never more)", "--after")
    before = suggest(q, "--quote", "Every orbit", "--with", "Plainly,", "--before")
    assert "has one or two points (and never more), and" in place(*placed(q, after)).taken
    assert "Plainly, Every orbit of a widget" in place(*placed(q, before)).taken


def test_with_no_quote_the_anchor_is_the_body(tmp_path: Path) -> None:
    q = demo(tmp_path)
    whole = place(*placed(q, suggest(q, "--with", "Each orbit has one or two points.")))
    # the head and the end stay: the label is the key's identity, and the body is all it replaces
    assert whole.taken.startswith(
        "\\begin{lemma}[Orbits]\\label{dm-0002}\\label{lem:orbits}\nEach orbit has one or two points."
    )
    assert whole.taken.rstrip().endswith("\\end{lemma}") and "Every orbit" not in whole.taken
    tail = place(*placed(q, suggest(q, "--with", "Hence orbits are small.", "--after")))
    assert "union of the one-point orbits.\nHence orbits are small.\n\\end{lemma}" in tail.taken
    head = place(*placed(q, suggest(q, "--with", "\\uses{dm-0001}", "--before")))
    assert "\\label{lem:orbits}\n\\uses{dm-0001}\nEvery orbit" in head.taken


def test_the_body_skips_the_head_its_label_and_its_uses() -> None:
    own = "\\begin{proof}\n\\uses{dm-0002}\nBy Lemma~\\ref{lem:orbits} it holds.\n\\end{proof}"
    a, b = body_span(own)
    assert own[a:b] == "By Lemma~\\ref{lem:orbits} it holds."
    titled = "\\begin{theorem}[{\\cite[Theorem 2.1]{Kre99}}]\\label{x}\nStatement.\n\\end{theorem}"
    a, b = body_span(titled)
    assert titled[a:b] == "Statement."


def test_an_empty_text_deletes_the_quote(tmp_path: Path) -> None:
    q = demo(tmp_path)
    gone = suggest(q, "--quote", ", and $\\Fix(\\sigma)$ is the union of the one-point orbits", "--with", "")
    assert "has one or two points.\n" in place(*placed(q, gone)).taken


def test_a_quote_that_no_longer_stands_once_is_refused_and_a_moved_text_whose_quote_stands_is_said(
    tmp_path: Path,
) -> None:
    q = demo(tmp_path)
    a = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    edit(q / LEMMA, "the union of the one-point orbits", "the union of the orbits of size one")
    assert place(*placed(q, a)).moved
    edit(q / LEMMA, "one or two points", "one point or two")
    with pytest.raises(Unplaced, match="no longer stands"):
        place(*placed(q, a))
    edit(q / LEMMA, "one point or two", "one or two points, one or two points")
    with pytest.raises(Unplaced, match="2 times"):
        place(*placed(q, a))


def test_is_taken_for_each_placement(tmp_path: Path) -> None:
    q = demo(tmp_path)
    rep = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    ins = suggest(q, "--quote", "Every orbit", "--with", "Plainly,", "--before")
    gone = suggest(q, "--quote", " of a widget", "--with", "")
    for a in (rep, ins, gone):
        assert not is_taken(*placed(q, a))
    edit(q / LEMMA, "Every orbit of a widget has one or two points", "Plainly, Every orbit has at most two points")
    for a in (rep, ins, gone):
        assert is_taken(*placed(q, a)), a


def test_the_cli_lists_edits_and_prints_the_patch(tmp_path: Path) -> None:
    q = demo(tmp_path)
    mine = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    theirs = suggest(q, "--quote", "Every orbit", "--with", "Each orbit", who="Referee Agent", env=AGENT)
    out = ok("changes", mine, cwd=q).stdout
    assert out.startswith(f"--- a/{LEMMA}") and "+Every orbit of a widget has at most two points" in out
    data = json_of("changes", mine, "--json", cwd=q)
    assert data["change"]["path"] == LEMMA and data["patch"] == out
    exits(2, "changes", "e-1999-01-01-ekn992", cwd=q, match="no change e-1999-01-01-ekn992")
    assert {mine, theirs} <= {c["id"] for c in json_of("changes", "--json", cwd=q)["changes"]}
    assert [e["id"] for e in json_of("changes", "--by", "Tom", "--json", cwd=q)["edits"]] == [mine]
    assert [e["id"] for e in json_of("changes", "--by", "Referee Agent", "--json", cwd=q)["edits"]] == [theirs]
    ok("suggest", "--withdraw", theirs, "--why", "not needed", "--as", "Referee Agent", cwd=q, env=AGENT)
    listed = json_of("changes", "--by", "Referee Agent", "--json", cwd=q)["edits"]
    assert [(e["id"], e["status"], e["why"]) for e in listed] == [(theirs, "discarded", "not needed")]
    edit(q / LEMMA, "one or two points", "at most two points")
    (row,) = [c for c in json_of("changes", "--json", cwd=q)["changes"] if c["id"] == mine]
    assert row["state"] == "taken"


def test_keep_writes_it_in_keeping_a_version_first_and_keeping_it_resolves_what_it_answers(tmp_path: Path) -> None:
    from loom.history.acts import APPLY
    from loom.history.ledger import load_history
    from loom.records.annotations import find_annotation, load_records
    from loom.scan.owntext import key_hash

    q = demo(tmp_path)
    ann = ok("annotate", "dm-0002", "Too vague.", "--type", "revision", "--as", "Tom", cwd=q).stdout.split()[0]
    a = suggest(
        q,
        "--quote",
        "one or two points",
        "--with",
        "at most two points",
        "--answers",
        ann,
        who="Referee Agent",
        env=AGENT,
    )
    refused("changes", "--keep", a, cwd=q, env=AGENT, code=2, match="author's")
    out = flat(ok("changes", "--keep", a, cwd=q).stdout)
    assert out.startswith("kept 1 change")
    assert "at most two points" in (q / LEMMA).read_text() and "one or two points" not in (q / LEMMA).read_text()
    result, e = placed(q, a)
    assert e.status == "kept" and e.kept == {"hash": key_hash(result, "dm-0002")}
    found = find_annotation(load_records(q)[0], ann)
    assert found is not None and found[1].status == "resolved" and found[1].resolved_why == f"kept suggested edit {a}"
    history = load_history(result.quilt.history_dir)
    kept = [x for x in history.landmarks() if x.get("kept_for") == APPLY]
    assert kept and kept[-1].message == "Before keeping a suggested edit"
    line = [x for x in history.entries if x.action == APPLY][-1]
    assert (line.get("edit"), line.get("key"), line.get("path")) == (a, "dm-0002", LEMMA)
    exits(2, "changes", "--keep", a, cwd=q, match=f"no change {a}")
    # an edit the author took by hand is kept without writing, and discarding leaves what it answers alone
    other = ok("annotate", "dm-0002", "Say plainly.", "--type", "revision", "--as", "Tom", cwd=q).stdout.split()[0]
    by_hand = suggest(q, "--quote", "Every orbit", "--with", "Each orbit", "--answers", other)
    edit(q / LEMMA, "Every orbit", "Each orbit")
    assert ok("changes", "--keep", by_hand, cwd=q).stdout.startswith("kept 1 change")
    assert find(q, by_hand).status == "kept"  # type: ignore[union-attr]
    dropped = suggest(q, "--quote", "Each orbit", "--with", "Any orbit", "--answers", other)
    ok("changes", "--discard", dropped, cwd=q)
    assert find(q, dropped).status == "discarded"  # type: ignore[union-attr]


def test_an_agent_withdraws_only_its_own_and_the_viewers_undo_opens_one_again(tmp_path: Path) -> None:
    from loom.render.api import handle

    q = demo(tmp_path)
    mine = suggest(q, "--quote", "Every orbit", "--with", "Each orbit")
    theirs = suggest(q, "--quote", "one or two points", "--with", "two points", who="Referee Agent", env=AGENT)
    refused("suggest", "--withdraw", mine, "--as", "Referee Agent", cwd=q, env=AGENT, code=2, match="only your own")
    ok("suggest", "--withdraw", theirs, "--why", "wrong count", "--as", "Referee Agent", cwd=q, env=AGENT)
    assert (find(q, theirs).status, find(q, theirs).why) == ("discarded", "wrong count")  # type: ignore[union-attr]
    refused(
        "suggest", "--withdraw", theirs, "--as", "Referee Agent", cwd=q, env=AGENT, code=2, match="discarded already"
    )
    handle(q, "change-discard", {"changes": [theirs], "undo": True, "author": "Tom"})
    assert find(q, theirs).status == "open"  # type: ignore[union-attr]
    assert [e["event"] for e in log(q) if e["id"] == theirs] == ["created", "discarded", "reopened"]


def test_since_tells_an_agent_what_became_of_its_edits_once(tmp_path: Path) -> None:
    q = demo(tmp_path)
    who = "Referee Agent"
    a = suggest(q, "--quote", "one or two points", "--with", "at most two points", who=who, env=AGENT)
    b = suggest(q, "--quote", "Every orbit", "--with", "Each orbit", who=who, env=AGENT)
    json_of("since", "--as", who, "--json", cwd=q, env=AGENT)
    ok("changes", "--keep", a, cwd=q)
    ok("changes", "--discard", b, "--why", "no", cwd=q)
    got = json_of("since", "--as", who, "--json", cwd=q, env=AGENT)
    assert {(e["id"], e["act"], e["by"], e["why"]) for e in got["edits"]} == {
        (a, "kept", "Tom", ""),
        (b, "discarded", "Tom", "no"),
    }
    assert json_of("since", "--as", who, "--json", cwd=q, env=AGENT)["edits"] == []


def test_two_clones_merge_their_edits_each_with_an_id_of_its_own_and_a_bad_line_is_reported(tmp_path: Path) -> None:
    q = demo(tmp_path)
    one, two = copy(q, tmp_path / "one"), copy(q, tmp_path / "two")
    mine = suggest(one, "--quote", "Every orbit", "--with", "Each orbit")
    theirs = suggest(two, "--quote", "Every orbit", "--with", "Each orbit")
    assert mine != theirs
    with (one / ".loom/edits" / "log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write((two / ".loom/edits" / "log.jsonl").read_text().splitlines()[-1] + "\n")
        fh.write("{not json\n")
        fh.write(json.dumps({"event": "kept", "id": "e-1999-01-01-ekn992"}) + "\n")
    edits, problems = replay(one)
    assert {mine, theirs} <= {e.id for e in edits}
    assert len(problems) == 2 and "Expecting property name" in problems[0]
    assert problems[1].endswith(": kept names unknown edit e-1999-01-01-ekn992")
    diags = json.loads(run("lint", "--json", cwd=one).stdout)["diagnostics"]
    assert any("not a valid suggested edit" in d["message"] for d in diags)
    assert not [d for d in diags if d["code"] == "loom:repeated-id"]
    # one id given twice is the merge conflict a reply or a link could not tell apart
    with (one / ".loom/edits" / "log.jsonl").open("a", encoding="utf-8") as fh:
        first = json.loads((one / ".loom/edits" / "log.jsonl").read_text().splitlines()[0])
        fh.write(json.dumps({**first, "with": "a second text"}) + "\n")
    diags = json.loads(run("lint", "--json", cwd=one).stdout)["diagnostics"]
    assert any(d["code"] == "loom:repeated-id" and ".loom/edits/log.jsonl" in d["message"] for d in diags)


def test_the_manifest_publishes_each_edit_as_its_record_and_an_open_one_as_a_change(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ready = suggest(q, "--quote", "one or two points", "--with", "at most two points", "--comment", "Sharper *here*.")
    lost = suggest(q, "--quote", "the one-point orbits", "--with", "the fixed points")
    edit(q / LEMMA, "the one-point orbits", "the orbits of size one")
    ok("build", cwd=q)
    m = json.loads((q / ".loom/build" / "manifest.json").read_text())
    row = m["suggested_edits"][ready]
    assert (row["target"]["key"], row["quote"], row["with"], row["placement"], row["status"]) == (
        "dm-0002",
        "one or two points",
        "at most two points",
        "replace",
        "open",
    )
    # `with_html` is made by TeX, so it is checked in the tex suite (test_review_commands.py, the proposed theorem)
    assert "<em>here</em>" in row["comment_html"] and "change" not in row
    change = {c["id"]: c for c in m["changes"]}
    assert change[ready]["state"] == "ready" and change[ready]["block"]["fragment"].startswith("fragments/changes/")
    assert (q / ".loom/build" / change[ready]["diff"]).read_text().startswith(f"--- a/{LEMMA}")
    assert change[lost]["state"] == "unplaced" and change[lost]["block"] is None
    assert all("payload" not in a and "placement" not in a for a in m["annotations"].values())
    edit(q / LEMMA, "one or two points", "at most two points")
    ok("build", cwd=q)
    assert {c["id"]: c for c in json.loads((q / ".loom/build" / "manifest.json").read_text())["changes"]}[ready][
        "state"
    ] == "taken"
    ok("changes", "--keep", ready, cwd=q)
    ok("build", cwd=q)
    m = json.loads((q / ".loom/build" / "manifest.json").read_text())
    assert m["suggested_edits"][ready]["status"] == "kept" and ready not in {c["id"] for c in m["changes"]}


def test_keep_and_discard_over_the_api(tmp_path: Path) -> None:
    from loom.render.api import ApiError, handle

    q = demo(tmp_path)
    a = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    lost = suggest(q, "--quote", "the one-point orbits", "--with", "the fixed points")
    theirs = suggest(q, "--quote", "Every orbit", "--with", "Each orbit", who="Referee Agent", env=AGENT)
    with pytest.raises(ApiError) as agent:
        handle(q, "change-keep", {"changes": [a], "author": "Claude Agent"})
    assert (agent.value.code, agent.value.status) == ("author-only", 403)
    with pytest.raises(ApiError) as missing:
        handle(q, "change-keep", {"changes": ["e-1999-01-01-ekn992"], "author": "Tom"})
    assert (missing.value.code, missing.value.status) == ("no-such-change", 404)
    edit(q / LEMMA, "the one-point orbits", "the orbits of size one")
    said = handle(q, "change-keep", {"changes": [lost, a], "author": "Tom"})
    assert said["done"] == [a] and [r["id"] for r in said["refused"]] == [lost]
    assert said["result"].startswith("kept 1 change; 1 could not be")
    with pytest.raises(ApiError) as again:
        handle(q, "change-keep", {"changes": [a], "author": "Tom"})
    assert again.value.code == "no-such-change"
    got = handle(q, "change-discard", {"changes": [theirs], "why": "no", "author": "Tom"})
    assert got["done"] == [theirs] and find(q, theirs).why == "no"  # type: ignore[union-attr]
    assert handle(q, "change-discard", {"changes": [theirs], "undo": True, "author": "Tom"})["done"] == [theirs]


def test_new_text_that_opens_a_section_is_kept_once_and_never_written_twice(tmp_path: Path) -> None:
    from loom.render.api import ApiError, handle

    q = demo(tmp_path)
    main = q / "drafting/main.tex"
    added = "\\section*{Preface}\nA word before the setup.\n\\begin{proof}[Answer]\n\\end{proof}"
    a = suggest(q, "--quote", "\\maketitle", "--with", added, "--after", key="drafting/main.tex")
    assert not is_taken(*placed(q, a))
    said = handle(q, "change-keep", {"changes": [a], "author": "Tom"})
    assert said["done"] == [a] and said["refused"] == []
    result, e = placed(q, a)
    # the section it opens is the master's child now, and the master still reads as it taken
    assert e.status == "kept" and is_taken(result, e)
    with pytest.raises(ApiError) as again:
        handle(q, "change-keep", {"changes": [a], "author": "Tom"})
    assert again.value.code == "no-such-change"
    assert main.read_text().count("A word before the setup.") == 1


def test_text_written_in_and_edited_since_reads_as_taken_and_keep_writes_nothing(tmp_path: Path) -> None:
    """A suggested edit whose text is in the file already, with the person's words worked into it, is not written a second time by Keep: in quant, keeping one such pasted a whole homework body again."""
    q = demo(tmp_path)
    main = q / "drafting/main.tex"
    added = (
        "\\section*{Preface}\nThese notes collect what is known about widgets, what each lemma rests on,"
        " and which questions stay open for a reader to settle on a later pass through the text."
    )
    a = suggest(q, "--quote", "\\maketitle", "--with", added, "--after", key="drafting/main.tex")
    assert taken_how(*placed(q, a)) is None
    # written in by hand, then worked inside
    worked = added.replace("what each lemma rests on,", "what each lemma rests on, with a sketch of each proof,")
    edit(main, "\\maketitle", "\\maketitle\n" + worked)
    assert taken_how(*placed(q, a)) == "edited"
    ok("changes", "--keep", a, cwd=q)
    assert main.read_text().count("These notes collect") == 1
    assert placed(q, a)[1].status == "kept"
    # a short text must stand as it was suggested, and a replacement whose words still stand is not taken
    short = suggest(q, "--quote", "Every orbit", "--with", "Plainly, for a finite widget,", "--before")
    edit(q / LEMMA, "Every orbit", "Plainly, for every finite widget, Every orbit")
    assert taken_how(*placed(q, short)) is None
    longer = "one or two points, never more, as the counting of orbits below shows for every widget and every finite group that acts on it"
    rep = suggest(q, "--quote", "one or two points", "--with", longer)
    edit(
        q / LEMMA,
        "one or two points",
        "one or two points, never more, as counting orbits below shows for every widget and every finite group acting on it",
    )
    assert taken_how(*placed(q, rep)) is None


def test_an_edit_goes_with_its_block_when_a_block_put_in_before_it_renumbers_the_keys(tmp_path: Path) -> None:
    """A key named by its place in its file (`#section:2`) names another block once a block is put in before it; the edit goes with the text it was written against, and is unplaced only when no block holds that text."""
    q = demo(tmp_path)
    outline = q / "drafting/outline.tex"
    a = suggest(
        q,
        "--quote",
        "Neither of these is proved.",
        "--with",
        "Neither of these is proved yet.",
        key="drafting/outline.tex#section:2",
    )
    b = suggest(q, "--quote", "These are settled", "--with", "These are proved", key="drafting/outline.tex#section:1")
    edit(
        outline,
        "\\section{What the paper rests on}",
        "\\section{Notation}\nA word on notation.\n\n\\section{What the paper rests on}",
    )
    assert place(*placed(q, a)).key == "drafting/outline.tex#section:3"
    assert place(*placed(q, b)).key == "drafting/outline.tex#section:2"
    ok("changes", "--keep", a, cwd=q)
    text = outline.read_text()
    assert text.count("Neither of these is proved yet.") == 1 and "A word on notation." in text
    # its block edited as well as moved: no block holds the text it was written against, and its key names another
    edit(outline, "already in the paper", "in the paper")
    with pytest.raises(Unplaced, match="no longer stands in drafting/outline.tex#section:1"):
        place(*placed(q, b))


def test_a_replacement_that_keeps_its_quote_and_opens_a_section_reads_as_taken(tmp_path: Path) -> None:
    q = demo(tmp_path)
    new = "\\maketitle\n\\section*{Note}\nRead the setup first."
    a = suggest(q, "--quote", "\\maketitle", "--with", new, key="drafting/main.tex")
    assert not is_taken(*placed(q, a))
    ok("changes", "--keep", a, cwd=q)
    result, e = placed(q, a)
    assert e.status == "kept" and is_taken(result, e)
    # the quote standing again outside the new text is the replacement undone
    edit(q / "drafting/main.tex", "\\begin{document}", "\\begin{document}\n\\maketitle")
    assert not is_taken(*placed(q, a))


def test_an_edit_on_an_empty_file_is_kept_as_the_whole_file(tmp_path: Path) -> None:
    from loom.render.api import handle

    q = demo(tmp_path)
    blank = q / "drafting/sheet.tex"
    blank.write_text("")
    whole = "\\documentclass{article}\n\\begin{document}\nOne problem.\n\\end{document}\n"
    a = suggest(q, "--with", whole, key="drafting/sheet.tex")
    assert place(*placed(q, a)).at == (0, 0)
    assert handle(q, "change-keep", {"changes": [a], "author": "Tom"})["done"] == [a]
    assert blank.read_text() == whole


def test_an_edit_on_an_agents_copy_is_not_kept_since_it_comes_in_with_the_copy(tmp_path: Path) -> None:
    import shutil

    from loom.render.api import handle
    from tests.unit._quilts import REPO

    q = tmp_path / "q"
    shutil.copytree(REPO / "tests" / "quilts" / "synthetic", q, ignore=shutil.ignore_patterns("build", ".git"))
    e = suggest(q, "--quote", "at most two points", "--with", "two points at most", key="sy-0002-ai")
    said = handle(q, "change-keep", {"changes": [e], "author": "Tom"})
    assert said["done"] == [] and said["refused"][0]["id"] == e and "aidoc.tex" in said["refused"][0]["why"]


def test_compile_with_an_edit_substitutes_its_text(tmp_path: Path) -> None:
    from loom.cli.build_cmds import substitution_for

    q = demo(tmp_path)
    a = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    region = substitution_for(scan(load_quilt(q)), "dm-0002", a)
    assert "at most two points" in region and "one or two points" not in region


def test_keep_all_keeps_the_suggested_edits_where_edits_in_place_are_not_tracked(tmp_path: Path) -> None:
    """With no look and no tracking, Keep all has no look to take first: it keeps what waits."""
    from loom.render.api import handle
    from loom.scan.quilt import save_author

    save_author("Tom")
    q = demo(tmp_path)
    a = suggest(q, "--quote", "one or two points", "--with", "at most two points")
    said = handle(q, "change-keep", {"all": True, "author": "Tom"})
    assert a in said["done"] and "first look" not in said["result"]
    assert "at most two points" in (q / LEMMA).read_text()


# ---- where an edit may go: inside its block, and on the block it was filed on ---------------------------------------

SHEET = "drafting/sheet.tex"
#: A document whose blocks are all named by their place: two empty answers that read the same, each under its own heading, and a remark.
SHEET_TEXT = r"""\documentclass{amsart}
\usepackage{amsthm}
\newtheorem{remark}{Remark}
\begin{document}
\section*{One}
What is asked first.
\begin{proof}[Answer]
\end{proof}
\section*{Two}
What is asked second.
\begin{proof}[Answer]
\end{proof}
What follows the second answer.
\begin{remark}
Widgets are finite here, and every orbit is small.
\end{remark}
\end{document}
"""


def sheet(tmp_path: Path) -> Path:
    q = demo(tmp_path)
    (q / SHEET).write_text(SHEET_TEXT, encoding="utf-8")
    return q


def filed(q: Path, key: str, new: str, quote: str | None = None, placement: str = "replace") -> str:
    """A suggested edit on `key` written as one was before the line above its block was recorded: its text's hash, and no `near`."""
    from loom.clock import stamp, today
    from loom.records.edits import append_new
    from loom.records.selectors import make_selector
    from loom.records.store import Records
    from loom.scan.owntext import key_hash

    result = scan(load_quilt(q))
    own = Records.own_pieces(result, result.nodes[key])[0]
    event = {
        "event": "created",
        "when": stamp(),
        "author": "Referee Agent",
        "kind": "agent",
        "target": key,
        "against": key_hash(result, key),
        "anchor": make_selector(own, quote).to_dict() if quote else None,
        "with": new,
        "placement": placement,
    }
    return append_new(q, event, today())


def test_words_that_reach_a_blocks_begin_or_end_are_no_place_for_an_edit(tmp_path: Path) -> None:
    """Text put beside a block's `\\end{…}` lands in the block around it, though the edit names this one; the v0.1 study found Keep writing it there again each time it was pressed (SAFE-1)."""
    q = demo(tmp_path)
    for quote, where in (
        ("\\end{lemma}", "--after"),
        ("\\begin{lemma}[Orbits]", "--before"),
        ("one-point orbits.\n\\end{lemma}", None),
    ):
        more = [where] if where else []
        refused("suggest", "dm-0002", "--quote", quote, "--with", "More.", *more, "--as", "Tom", cwd=q, code=2, match="reach the block's \\begin or \\end")  # fmt: skip
    # the title, the label and the words are the block's own, and an edit goes there as before
    for quote, new in (("Orbits", "Orbits of a widget"), ("one or two points", "at most two points")):
        assert place(*placed(q, suggest(q, "--quote", quote, "--with", new))).key == "dm-0002"
    # one filed before the refusal is on no place, and Keep writes nothing
    old = filed(q, "dm-0002", "More.", "\\end{lemma}", "after")
    with pytest.raises(Unplaced, match="reach the block's"):
        place(*placed(q, old))
    before = (q / LEMMA).read_text()
    said = ok("changes", "--keep", old, cwd=q).stdout
    assert said.startswith("kept nothing") and "reach the block's" in flat(said)
    assert (q / LEMMA).read_text() == before and placed(q, old)[1].status == "open"


def test_words_that_run_across_a_block_inside_are_no_place_for_an_edit(tmp_path: Path) -> None:
    """A section's own text has its proofs cut out, so words either side of one read as one run and are two pieces of the file; replacing them would replace the first piece alone."""
    q = sheet(tmp_path)
    two = f"{SHEET}#section:2"
    refused(
        "suggest", two, "--quote", "What is asked second. What follows the second answer.", "--with", "Asked.",
        "--as", "Tom", cwd=q, code=2, match="run across a block inside",
    )  # fmt: skip
    assert place(*placed(q, suggest(q, "--quote", "What is asked second.", "--with", "Asked.", key=two))).key == two
    old = filed(q, two, "Asked.", "What is asked second. What follows the second answer.")
    with pytest.raises(Unplaced, match="run across a block inside"):
        place(*placed(q, old))


def test_a_sections_body_is_below_its_heading_and_one_across_a_block_inside_is_not_replaced(tmp_path: Path) -> None:
    """CUT-14 of the v0.1 study: a section's own text is its heading and the words under it, and a suggestion on its body replaced the heading and its label with them. With its proofs cut out, its body is several pieces of the file, and only the first would be replaced."""
    q = sheet(tmp_path)
    two = f"{SHEET}#section:2"
    refused("suggest", two, "--with", "Asked.", "--as", "Tom", cwd=q, code=2, match="runs across a block inside")
    head = suggest(q, "--with", "Read this first.", "--before", key=two)
    assert place(*placed(q, head)).taken.startswith("\\section*{Two}\nRead this first.\nWhat is asked second.")
    old = filed(q, two, "Asked.")
    with pytest.raises(Unplaced, match="runs across a block inside"):
        place(*placed(q, old))
    one = suggest(q, "--with", "What is asked at first.", key=f"{SHEET}#section:1")
    ok("changes", "--keep", one, cwd=q)
    assert "\\section*{One}\nWhat is asked at first.\n\\begin{proof}[Answer]" in (q / SHEET).read_text()
    assert body_span("\\section{Results}\\label{r}\\label{s}\n\nThe results.\n") == (
        len("\\section{Results}\\label{r}\\label{s}\n\n"),
        len("\\section{Results}\\label{r}\\label{s}\n\nThe results."),
    )


def test_blocks_that_read_the_same_are_told_apart_by_the_line_above(tmp_path: Path) -> None:
    """An answer suggested on the second of two empty answers stays on it when a third is put in above and every key after it is renumbered (SAFE-4): the line above the block was recorded with the edit."""
    q = sheet(tmp_path)
    a = suggest(q, "--with", "The answer to two.", key=f"{SHEET}#proof:2")
    assert log(q)[-1]["near"] == "What is asked second." and find(q, a).near == "What is asked second."  # type: ignore[union-attr]
    labelled = suggest(q, "--quote", "one or two points", "--with", "two")
    assert "near" not in next(e for e in log(q) if e["id"] == labelled)
    edit(
        q / SHEET,
        "\\section*{One}",
        "\\section*{Zero}\nWhat is asked before.\n\\begin{proof}[Answer]\n\\end{proof}\n\\section*{One}",
    )
    assert place(*placed(q, a)).key == f"{SHEET}#proof:3"
    ok("changes", "--keep", a, cwd=q)
    text = (q / SHEET).read_text()
    assert text.count("The answer to two.") == 1 and text.index("The answer to two.") > text.index(
        "What is asked second."
    )
    # an edit with no line recorded has only its text to go by, and three blocks hold that
    old = filed(q, f"{SHEET}#proof:1", "The answer to zero.")
    with pytest.raises(Unplaced, match="named by its place"):
        place(*placed(q, old))


def test_blocks_that_read_the_same_under_the_same_line_take_no_edit(tmp_path: Path) -> None:
    q = sheet(tmp_path)
    edit(q / SHEET, "What is asked second.", "What is asked first.")
    refused("suggest", f"{SHEET}#proof:2", "--with", "An answer.", "--as", "Tom", cwd=q, code=2, match="the same under the same line")  # fmt: skip
    # the remark reads like no other block, and takes one
    assert suggest(q, "--with", "A remark.", "--after", key=f"{SHEET}#remark:1")


def test_a_phrase_suggested_beside_the_very_words_that_already_stand_there_is_not_read_as_taken(tmp_path: Path) -> None:
    """Harness seed 3077 of the door's spike: a phrase suggested where the same phrase already stood read as taken, and Keep wrote nothing (SAFE-8). An insertion is taken only when its text stands at its place with the words recorded beside the place beyond it, or gone."""
    q = demo(tmp_path)
    after = suggest(q, "--quote", "Every orbit", "--with", "of a widget", "--after")
    foot = suggest(q, "--with", "the one-point orbits.", "--after")
    for a in (after, foot):
        assert taken_how(*placed(q, a)) is None
    ok("changes", "--keep", after, cwd=q)
    ok("changes", "--keep", foot, cwd=q)
    text = (q / LEMMA).read_text()
    assert "Every orbit of a widget of a widget has" in text and text.count("the one-point orbits.") == 2


def test_a_replacement_whose_new_text_holds_its_quote_is_judged_beside_the_quote(tmp_path: Path) -> None:
    """Harness seed 3019: a replacement that adds words after its quote, where those very words already followed it, read as taken and was never written."""
    q = demo(tmp_path)
    a = suggest(q, "--quote", "$\\Fix(\\sigma)$ is", "--with", "$\\Fix(\\sigma)$ is the union")
    assert taken_how(*placed(q, a)) is None
    b = suggest(q, "--quote", "one or two points", "--with", "one or two points (never more)")
    edit(q / LEMMA, "one or two points", "one or two points (never more)")
    assert taken_how(*placed(q, b)) == "as-written"
    # touched once written in, it is placed nowhere, never written beside itself
    edit(q / LEMMA, "(never more)", "(never more than two)")
    assert taken_how(*placed(q, b)) is None
    with pytest.raises(Unplaced, match="right after the text"):
        place(*placed(q, b))


def test_a_uses_written_in_by_hand_at_the_head_of_the_body_reads_as_taken(tmp_path: Path) -> None:
    """A `\\uses{…}` taken in is read as the block's head, so the body starts after it with the words it started with."""
    q = demo(tmp_path)
    a = suggest(q, "--with", "\\uses{dm-0001}", "--before")
    edit(q / LEMMA, "\\label{lem:orbits}\n", "\\label{lem:orbits}\n\\uses{dm-0001}\n")
    assert taken_how(*placed(q, a)) == "as-written"
    (span,) = where_taken(*placed(q, a))
    assert (q / LEMMA).read_text()[span[0] : span[1]] == "\\uses{dm-0001}"


def test_an_insertion_is_placed_only_while_the_words_beside_its_place_stand(tmp_path: Path) -> None:
    """Text the person wrote beside an insertion's place since it was suggested is not something Keep can tell from the edit touched (SAFE-1 of the v0.1 study), so the edit is unplaced rather than written beside it."""
    q = demo(tmp_path)
    after = suggest(q, "--quote", "one or two points", "--with", "(and never more)", "--after")
    before = suggest(q, "--quote", "Every orbit", "--with", "Plainly,", "--before")
    foot = suggest(q, "--with", "Hence orbits are small.", "--after")
    head = suggest(q, "--with", "\\uses{dm-0001}", "--before")
    assert find(q, foot).edge.endswith("the one-point orbits.") and find(q, head).edge.startswith("Every orbit")  # type: ignore[union-attr]
    old = filed(q, "dm-0002", "Hence.", None, "after")  # one filed before the body's foot was recorded
    # words changed away from every place leave each where it was
    edit(q / LEMMA, "[Orbits]", "[Orbits of a widget]")
    for a in (after, before, foot, head):
        assert place(*placed(q, a)).moved
    edit(q / LEMMA, "the one-point orbits.", "the orbits of one point.")
    with pytest.raises(Unplaced, match="end of the body"):
        place(*placed(q, foot))
    assert "Hence." in place(*placed(q, old)).taken
    edit(q / LEMMA, "one or two points, and", "one or two points (at most), and")
    with pytest.raises(Unplaced, match="right after the text"):
        place(*placed(q, after))
    edit(q / LEMMA, "\\label{lem:orbits}\nEvery orbit", "\\label{lem:orbits}\nSo Every orbit")
    with pytest.raises(Unplaced, match="right before the text"):
        place(*placed(q, before))
    with pytest.raises(Unplaced, match="head of the body"):
        place(*placed(q, head))
    # Keep writes nothing for one unplaced
    text = (q / LEMMA).read_text()
    ok("changes", "--keep", after, cwd=q)
    assert (q / LEMMA).read_text() == text and find(q, after).status == "open"  # type: ignore[union-attr]


def test_an_insertion_beside_a_quote_that_ends_or_starts_its_blocks_text_holds_to_that_end(tmp_path: Path) -> None:
    """The integrator's review of step 4: a quote that ends a section's own text records only whitespace after it, which said nothing, so a suggestion typed in after it by hand and reworded was written in ahead of the person's sentence. Only whitespace recorded says the text ended there."""
    q = sheet(tmp_path)
    two = f"{SHEET}#section:2"
    after = suggest(
        q, "--quote", "What follows the second answer.", "--with", "Zebra remark at the end.", "--after", key=two
    )
    assert log(q)[-1]["anchor"]["suffix"].strip() == ""
    before = suggest(q, "--quote", "\\documentclass{amsart}", "--with", "% Zebra line on top.", "--before", key=SHEET)
    assert log(q)[-1]["anchor"]["prefix"] == ""
    for a in (after, before):
        assert place(*placed(q, a))
    edit(
        q / SHEET, "What follows the second answer.", "What follows the second answer. Zebra remark, reworded by hand."
    )
    with pytest.raises(Unplaced, match="right after the text"):
        place(*placed(q, after))
    edit(q / SHEET, "\\documentclass{amsart}", "\\PassOptionsToPackage{draft}{graphicx}\n\\documentclass{amsart}")
    with pytest.raises(Unplaced, match="right before the text"):
        place(*placed(q, before))
    text = (q / SHEET).read_text()
    ok("changes", "--keep", after, cwd=q)
    assert (q / SHEET).read_text() == text
    # typed in exactly as suggested, it is taken where it stands
    exact = suggest(q, "--quote", "Zebra remark, reworded by hand.", "--with", "Zebra coda.", "--after", key=two)
    edit(q / SHEET, "Zebra remark, reworded by hand.", "Zebra remark, reworded by hand. Zebra coda.")
    assert taken_how(*placed(q, exact)) == "as-written"


def test_a_heading_is_read_as_the_scan_reads_one() -> None:
    """The integrator's review of step 4: `\\part` in `\\partial` was read as a heading, and a heading's titles were read only with no space before them."""
    for text in (
        "\\partial_t u = \\Delta u",
        "\\paragraphmark{x} y",
        "\\sectionmark{x} y",
        "\\partname y",
        "\\chaptername y",
    ):
        assert body_span(text) == (0, len(text)), text
    spaced = "\\subsection [short] {Long title}\\label {x}\nThe text.\n"
    a, b = body_span(spaced)
    assert spaced[a:b] == "The text."
    assert body_span("\\section*{T}") == (len("\\section*{T}"), len("\\section*{T}"))


def test_a_replacement_typed_in_by_hand_is_taken_though_its_quote_reads_like_a_plain_word_further_on(
    tmp_path: Path,
) -> None:
    """The integrator's review of step 4: read as the page prints it, `\\emph{orbit}` stands wherever the plain word does, so once the person typed the replacement in by hand the quote "still stood" in `orbits` further on, and Keep wrote the replacement over that word. An edit's quote is the source's own words, found again only as written."""
    q = demo(tmp_path)
    edit(q / LEMMA, "Every orbit of a widget", "Every \\emph{orbit} of a widget")
    a = suggest(q, "--quote", "\\emph{orbit}", "--with", "\\emph{cycle}")
    edit(q / LEMMA, "\\emph{orbit}", "\\emph{cycle}")  # typed in by hand, exactly
    assert taken_how(*placed(q, a)) == "as-written"
    text = (q / LEMMA).read_text()
    ok("changes", "--keep", a, cwd=q)
    assert (q / LEMMA).read_text() == text and "the one-point orbits." in text


def test_a_replacement_whose_quote_was_rewritten_goes_nowhere_though_it_reads_like_a_plain_word_further_on(
    tmp_path: Path,
) -> None:
    """The same, with the person's own words in place of the quote: on `main` as well, `place` followed the reading as printed to the plain word, and Keep wrote the replacement there."""
    q = demo(tmp_path)
    edit(q / LEMMA, "Every orbit of a widget", "Every \\emph{orbit} of a widget")
    a = suggest(q, "--quote", "\\emph{orbit}", "--with", "\\emph{cycle}")
    edit(q / LEMMA, "\\emph{orbit}", "\\emph{class}")
    with pytest.raises(Unplaced, match="no longer stands"):
        place(*placed(q, a))
    text = (q / LEMMA).read_text()
    ok("changes", "--keep", a, cwd=q)
    assert (q / LEMMA).read_text() == text and "the one-point orbits." in text


def test_a_whole_body_replacement_is_judged_by_the_body_alone(tmp_path: Path) -> None:
    """The body's own words are compared with those the replacement was suggested on: a title changed since leaves it placed, a word of the body changed refuses it."""
    q = demo(tmp_path)
    a = suggest(q, "--with", "Each orbit has one or two points.")
    edit(q / LEMMA, "[Orbits]", "[Orbits of a widget]")
    assert place(*placed(q, a)).moved
    edit(q / LEMMA, "the union of", "the set of")
    with pytest.raises(Unplaced, match="has changed since"):
        place(*placed(q, a))
    # one whose text was not kept goes by the whole block's text
    old = filed(q, "dm-0002", "Each orbit is small.")
    assert place(*placed(q, old))
    edit(q / LEMMA, "[Orbits of a widget]", "[Orbits]")
    with pytest.raises(Unplaced, match="has changed since"):
        place(*placed(q, old))


def test_whitespace_moved_beside_an_insertion_leaves_it_placed(tmp_path: Path) -> None:
    q = demo(tmp_path)
    after = suggest(q, "--quote", "one or two points,", "--with", "never more,", "--after")
    edit(q / LEMMA, "one or two points, and $\\Fix(\\sigma)$ is", "one or two points,\n  and $\\Fix(\\sigma)$\nis")
    assert "one or two points, never more,\n  and" in place(*placed(q, after)).taken


def test_an_insertion_in_an_empty_body_is_unplaced_once_the_body_has_words(tmp_path: Path) -> None:
    q = demo(tmp_path)
    body = "Every orbit of a widget has one or two points, and $\\Fix(\\sigma)$ is the union of the one-point orbits.\n"
    edit(q / LEMMA, body, "")
    a = suggest(q, "--with", "Two points.", "--after")
    assert log(q)[-1]["edge"] == "" and "Two points." in place(*placed(q, a)).taken
    edit(q / LEMMA, "\\label{lem:orbits}\n", "\\label{lem:orbits}\nMine.\n")
    with pytest.raises(Unplaced, match="was empty when it was suggested"):
        place(*placed(q, a))


def test_the_second_of_two_insertions_after_one_quote_is_unplaced_once_the_first_is_kept(tmp_path: Path) -> None:
    """The first, kept, stands where the second's recorded neighbour stood: the second is not put in ahead of it, out of the order they were suggested in."""
    q = demo(tmp_path)
    first = suggest(q, "--quote", "one or two points", "--with", "(never more)", "--after")
    second = suggest(q, "--quote", "one or two points", "--with", "(as counted)", "--after")
    ok("changes", "--keep", first, cwd=q)
    with pytest.raises(Unplaced, match="right after the text"):
        place(*placed(q, second))
    assert "(as counted)" not in (q / LEMMA).read_text()


def test_an_edit_on_a_block_named_by_place_that_has_changed_goes_there_only_by_its_quote(tmp_path: Path) -> None:
    """Once the block's text has changed, no block holds what the edit was filed on. An edit that quotes words still goes on the block at its place while the line above stands, where `place` needs its quote; one on the body has nothing to say the block is the one, and is unplaced."""
    q = sheet(tmp_path)
    remark = f"{SHEET}#remark:1"
    quoted = suggest(q, "--quote", "every orbit is small", "--with", "every orbit has at most two points", key=remark)
    body = suggest(q, "--with", "It follows that the count is even.", "--after", key=remark)
    old = filed(q, remark, "every orbit has two points", "every orbit is small")
    edit(q / SHEET, "Widgets are finite here", "Widgets are finite throughout")
    got = place(*placed(q, quoted))
    assert got.key == remark and got.moved
    for unplaced in (body, old):
        with pytest.raises(Unplaced, match="named by its place"):
            place(*placed(q, unplaced))
    # a remark put in under the same line takes the key; the quote is not in it, so the edit is unplaced, never written there
    edit(
        q / SHEET,
        "\\begin{remark}",
        "\\begin{remark}\nAnother remark altogether.\n\\end{remark}\n\\begin{remark}",
        count=1,
    )
    with pytest.raises(Unplaced, match="no longer stands"):
        place(*placed(q, quoted))
    # nor when it does hold the quote: the remark the edit was suggested on holds it too, and the line above no longer says which
    edit(q / SHEET, "Another remark altogether.", "Another remark, and every orbit is small.")
    with pytest.raises(Unplaced, match="stand in another block"):
        place(*placed(q, quoted))
    text = (q / SHEET).read_text()
    ok("changes", "--keep", quoted, cwd=q)
    assert (q / SHEET).read_text() == text
