"""Links into what the viewer shows (plan 0.14 phase 3): `quilt:` for what the quilt owns, `cited:` for a place in a cited work, checked when an agent posts one and printed by `loom link`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import ok, refused
from tests.unit._quilts import demo


@pytest.fixture
def q(tmp_path: Path) -> Path:
    return demo(tmp_path)


def scanned(q: Path):  # type: ignore[no-untyped-def]
    from loom.cli._quilt import open_scan

    return open_scan(str(q))


def test_each_kind_resolves(q: Path) -> None:
    from loom.links import resolve

    result = scanned(q)
    assert resolve(result, q, "quilt:dm-0003").kind == "node"
    assert resolve(result, q, "quilt:dm-0003/proof").kind == "node"
    doc = resolve(result, q, "quilt:drafting/main.tex#dm-0003")
    assert (doc.kind, doc.key, doc.place) == ("document", "drafting/main.tex", "dm-0003")
    assert resolve(result, q, "quilt:a-2026-09-16-ecnav2").kind == "annotation"
    assert resolve(result, q, "quilt:s-2026-09-16-p9z37z").kind == "session"
    work = resolve(result, q, "cited:doi:10.4171/demo/14-1?page=2")
    assert (work.kind, work.key, work.place) == ("work", result.refs["Calloway14"], "page=2")
    assert resolve(result, q, "cited:arxiv:0805.2065v2").key == result.refs["Man12"]
    work = resolve(result, q, f"quilt:{result.refs['Har77']}")  # a work by its reference
    assert (work.kind, work.key, work.place) == ("work", result.refs["Har77"], "")


def test_a_place_carries_quoted_words(q: Path) -> None:
    from loom.links import resolve

    result = scanned(q)
    har77 = result.refs["Har77"]
    doc = resolve(result, q, "quilt:drafting/main.tex#dm-0003&quote=every%20vertex")
    assert (doc.kind, doc.key, doc.place, doc.quote) == ("document", "drafting/main.tex", "dm-0003", "every vertex")
    whole = resolve(result, q, "quilt:drafting/main.tex#quote=a%20%26%20b")
    assert (whole.place, whole.quote) == ("", "a & b")  # an encoded & stays in the words
    page = resolve(result, q, f"quilt:{har77}#page=4&quote=the+words")
    assert (page.kind, page.key, page.place, page.quote) == ("work", har77, "page=4", "the words")
    assert resolve(result, q, "quilt:dm-0003#quote=x").quote == "x"


def test_quoted_words_need_a_place_that_holds_words(q: Path) -> None:
    from loom.links import LinkError, resolve

    result = scanned(q)
    for href, why in [
        ("quilt:a-2026-09-16-ecnav2#quote=x", "quoted words are for"),
        ("quilt:s-2026-09-16-p9z37z#quote=x", "quoted words are for"),
        (f"quilt:{result.refs['Har77']}#page=two&quote=x", "page=N"),
    ]:
        with pytest.raises(LinkError, match=why):
            resolve(result, q, href)


def test_raw_links_are_read_in_any_text() -> None:
    from loom.links import raw_links

    org = "* Reading\nSee [[quilt:papers/a.pdf#page=2&quote=x%20y][the lemma]] and [[quilt:dm-0003]].\n"
    assert raw_links(org) == [(2, "quilt:papers/a.pdf#page=2&quote=x%20y"), (2, "quilt:dm-0003")]
    md = "A [lemma](quilt:drafting/main.tex#dm-0003), then quilt:dm-0004. And <quilt:state>, cited:arxiv:0805.2065v2?page=9;"
    assert [h for _, h in raw_links(md)] == [
        "quilt:drafting/main.tex#dm-0003",
        "quilt:dm-0004",
        "quilt:state",
        "cited:arxiv:0805.2065v2?page=9",
    ]
    # a word ending in the scheme's letters is not a link, and a scheme with nothing after it is none
    assert raw_links("unquilt:x and quilt: alone") == []
    # an org link in brackets is read whole, though it holds a space; emphasis and code markers after a raw link are not part of it
    assert raw_links("[[quilt:dm-0003#quote=finite widget][see]] then quilt:dm-0004") == [
        (1, "quilt:dm-0003#quote=finite widget"),
        (1, "quilt:dm-0004"),
    ]
    assert [h for _, h in raw_links("**quilt:notes/a.md** `quilt:x` =quilt:y= /quilt:z/ _quilt:w_")] == [
        "quilt:notes/a.md",
        "quilt:x",
        "quilt:y",
        "quilt:z",
        "quilt:w",
    ]


def test_what_the_viewer_does_not_show_is_refused(q: Path) -> None:
    from loom.links import LinkError, resolve

    result = scanned(q)
    unreached = next(
        k for k, n in result.nodes.items() if n.kind == "environment" and "drafting/main.tex" not in n.reached_by
    )
    for href, why in [
        ("quilt:dm-9999", "no key"),
        ("quilt:drafting/nodes/dm-0001.tex", "file the documents include"),
        ("quilt:a-2026-01-01-zjcz9t", "no annotation"),
        ("quilt:s-2026-01-01-54qgjt", "no session"),
        (f"quilt:drafting/main.tex#{unreached}", "does not include"),
        ("quilt:dm-0003#dm-0001", "is not in"),
        ("cited:doi:10.0/nobody", "no work in the library states"),
        ("cited:Calloway14", "identifier"),
        ("cited:doi:10.4171/demo/14-1?page=zero", "page"),
    ]:
        with pytest.raises(LinkError, match=why):
            resolve(result, q, href)


def test_a_deleted_session_is_not_linkable(q: Path) -> None:
    from loom.links import LinkError, resolve

    ok("session", "delete", "s-2026-09-16-p9z37z", "--as", "A. Author", cwd=q)
    with pytest.raises(LinkError, match="no session"):
        resolve(scanned(q), q, "quilt:s-2026-09-16-p9z37z")


def test_check_names_every_bad_link(q: Path) -> None:
    from loom.links import check

    text = "See [](quilt:dm-0003), [this](quilt:dm-9999) and [that](cited:doi:10.0/none), and a [web page](https://example.org)."
    bad = check(scanned(q), q, text)
    assert len(bad) == 2 and "dm-9999" in bad[0] and "10.0/none" in bad[1]
    assert check(scanned(q), q, "no links at all") == []


def test_loom_link_prints_what_the_viewer_follows(q: Path) -> None:
    def link(*args: str) -> str:
        return ok("link", *args, cwd=q).output.strip()

    assert link("dm-0003") == "[](quilt:dm-0003)"
    assert link("drafting/main.tex", "--at", "dm-0003") == "[](quilt:drafting/main.tex#dm-0003)"
    assert link("a-2026-09-16-tc3rcf") == "[](quilt:a-2026-09-16-tc3rcf)"
    assert link("s-2026-09-16-p9z37z") == "[](quilt:s-2026-09-16-p9z37z)"
    refs = scanned(q).refs
    # a work by its reference, a place on its pages with the words to light
    assert (
        link("Calloway14", "--page", "2", "--quote", "a (phrase)")
        == f"[](quilt:{refs['Calloway14']}#page=2&quote=a%20%28phrase%29)"
    )
    assert link("Har77") == f"[](quilt:{refs['Har77']})"
    assert (
        link("drafting/main.tex", "--at", "dm-0003", "--quote", "every  vertex")
        == "[](quilt:drafting/main.tex#dm-0003&quote=every%20vertex)"
    )
    # words ending a sentence keep their full stop when the link is read raw, as an editor hands it to loom open
    ended = link("dm-0003", "--quote", "ends here.")
    assert ended == "[](quilt:dm-0003#quote=ends%20here%2E)"
    from loom.links import raw_links, split_quote

    assert split_quote(raw_links(ended)[0][1].partition("#")[2])[1] == "ends here."
    refused("link", "drafting/nodes/dm-0001.tex", cwd=q, code=2, match="file the documents include")
    refused("link", "dm-0003", "--page", "2", cwd=q, code=2, match="for a work")  # a page is a work's
    refused("link", "a-2026-09-16-tc3rcf", "--quote", "x", cwd=q, code=2, match="quoted words are for")


def test_an_agent_posting_a_bad_link_is_refused_and_a_good_one_lands(q: Path) -> None:
    from loom.mailbox import read_events

    agent = {"AI_AGENT": "1"}
    sid = "s-2026-09-16-p9z37z"
    bad = refused(
        "session",
        "say",
        "See [](quilt:dm-9999).",
        "--session",
        sid,
        "--as",
        "Referee Agent",
        cwd=q,
        env=agent,
        code=2,
        match="dm-9999",
    )
    assert "loom link" in bad.output
    ok("session", "say", "See [](quilt:dm-0003).", "--session", sid, "--as", "Referee Agent", cwd=q, env=agent)
    assert read_events(q, sid)[-1].body == "See [](quilt:dm-0003)."
    # an annotation's body the same way, when an agent writes it
    refused(
        "annotate",
        "dm-0002",
        "As [](quilt:dm-9999) shows.",
        "--as",
        "Referee Agent",
        cwd=q,
        env=agent,
        code=2,
        match="dm-9999",
    )
    # a person's comment is their own business
    ok(
        "annotate",
        "dm-0002",
        "As [](quilt:dm-9999) shows.",
        "--as",
        "A. Author",
        cwd=q,
    )


def test_the_formatting_document_is_in_force() -> None:
    text = (Path(__file__).resolve().parents[2] / "src" / "loom" / "assets" / "ai" / "formatting.md").read_text(
        encoding="utf-8"
    )
    assert "stub" not in text.lower() and "loom link" in text and "\\uses{" in text
