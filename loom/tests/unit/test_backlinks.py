"""The links a quilt's own files make (`docs/design/model.md`, "Notes"): read in Markdown, org, plain text and notebooks, raw or bracketed, resolved to what each names, and published in the manifest so the viewer lists beside an item the files that link to it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit._pdfs import PROSE, lines_pdf
from tests.unit._quilts import demo


def put(q: Path, rel: str, text: str) -> None:
    p = q / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_every_link_in_the_shown_files_is_indexed_by_what_it_names(tmp_path: Path) -> None:
    from loom.cli._quilt import open_scan
    from loom.files import attach_files

    q = demo(tmp_path)
    lines_pdf(q / "papers/median.pdf", [PROSE])
    result = open_scan(str(q))
    ref = result.refs["Har77"]
    put(q, "notes/lemma.md", "# Lemma\n\nSee [the vertex](quilt:drafting/main.tex#dm-0003&quote=every%20vertex).\n")
    put(
        q,
        "notes/reading.org",
        f"* Har77\n[[quilt:{ref}#page=2&quote=the%20words][p. 2]] and [[quilt:papers/median.pdf#page=1&quote=incidence%20matrix]]\n",
    )
    put(q, "notes/plain.txt", "first line\nraw quilt:dm-0003, then quilt:dm-9999 which names nothing.\n")
    put(q, "notes/self.md", "# Top\n\n[here](quilt:notes/self.md#top)\n")
    nb = {
        "cells": [{"cell_type": "markdown", "source": ["A cell\n", "[w](quilt:drafting/main.tex)"]}],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    put(q, "notes/book.ipynb", json.dumps(nb))
    result = open_scan(str(q))
    manifest: dict = {"corpus": {}}
    attach_files(result, manifest, {})
    got = [(b["from"], b["line"], b["kind"], b["key"], b["place"], b["quote"]) for b in manifest["backlinks"]]
    assert ("notes/lemma.md", 3, "document", "drafting/main.tex", "dm-0003", "every vertex") in got
    assert ("notes/reading.org", 2, "work", ref, "page=2", "the words") in got
    assert ("notes/reading.org", 2, "file", "papers/median.pdf", "page=1", "incidence matrix") in got
    assert ("notes/plain.txt", 2, "node", "dm-0003", "", "") in got
    assert ("notes/book.ipynb", 2, "document", "drafting/main.tex", "", "") in got
    # a link that names nothing, and a file's link to itself, are no backlinks
    assert not any(k == "dm-9999" for *_, k, _p, _q in got)
    assert not any(f == "notes/self.md" for f, *_ in got)
    assert next(b for b in manifest["backlinks"] if b["from"] == "notes/plain.txt")["href"] == "quilt:dm-0003"


def test_an_org_link_with_spaces_an_html_amp_and_a_markdown_heading_are_read(tmp_path: Path) -> None:
    from loom.backlinks import backlinks
    from loom.cli._quilt import open_scan

    q = demo(tmp_path)
    put(q, "notes/a.org", "* A\n[[quilt:drafting/main.tex#dm-0003&quote=finite widget][see]]\n")
    put(q, "notes/b.html", '<p><a href="quilt:drafting/main.tex#dm-0003&amp;quote=a%20b">x</a></p>\n')
    md = "# Intro\n\n```\n# not a heading\n```\n\n## Orbits\n\nSee [it](quilt:dm-0002).\n\n## Orbits\n\n[again](quilt:dm-0003)\n"
    put(q, "notes/c.md", md)
    put(q, "notes/d.md", "Before any heading, quilt:dm-0002.\n")
    kinds = {"notes/a.org": "text", "notes/b.html": "html", "notes/c.md": "markdown", "notes/d.md": "markdown"}
    got = {(b["from"], b["line"]): b for b in backlinks(open_scan(str(q)), q, kinds)}
    assert got[("notes/a.org", 2)]["quote"] == "finite widget"
    assert (got[("notes/b.html", 1)]["place"], got[("notes/b.html", 1)]["quote"]) == ("dm-0003", "a b")
    # a Markdown note opens at the heading above its link, as its page names it, a repeat by its count; a fence holds no heading
    assert (got[("notes/c.md", 9)]["at"], got[("notes/c.md", 13)]["at"]) == ("orbits", "orbits-1")
    assert got[("notes/d.md", 1)]["at"] == "" and got[("notes/a.org", 2)]["at"] == ""


def test_a_quilt_whose_files_link_nowhere_has_none(tmp_path: Path) -> None:
    from loom.backlinks import backlinks
    from loom.cli._quilt import open_scan

    q = demo(tmp_path)
    put(q, "notes/a.md", "# A\n\nNo links, and the word quilt: alone.\n")
    assert backlinks(open_scan(str(q)), q, {"notes/a.md": "markdown", "papers/x.pdf": "pdf"}) == []


def test_a_link_whose_quoted_words_are_gone_is_a_problem_on_its_line(tmp_path: Path) -> None:
    from loom.backlinks import backlinks
    from loom.cli._quilt import open_scan
    from loom.scan.diagnostics import LATEX, LOOM
    from loom.scan.lint import link_words_missing
    from loom.scan.owntext import own_text

    q = demo(tmp_path)
    result = open_scan(str(q))
    assert "a finite set" in own_text(result, result.nodes["dm-0003"])
    said = "a%20finite%20set"
    put(
        q,
        "notes/a.org",
        f"* A\n[[quilt:drafting/main.tex#dm-0003&quote={said}][kept]]\nquilt:dm-0003#quote=words%20nobody%20wrote\n",
    )
    put(
        q,
        "notes/b.md",
        f"# B\n\n[whole](quilt:drafting/main.tex#quote={said}) and [gone](quilt:drafting/main.tex#quote=no%20such%20words)\n",
    )
    result = open_scan(str(q))
    links = backlinks(result, q, {"notes/a.org": "text", "notes/b.md": "markdown"})
    found = link_words_missing(result, links)
    assert [(d.locations[0].file, d.locations[0].line) for d in found] == [("notes/a.org", 3), ("notes/b.md", 3)]
    assert {d.code for d in found} == {"loom:link-words-missing"} and LOOM["loom:link-words-missing"].cls == LATEX
    assert "“words nobody wrote”" in found[0].message and "“no such words”" in found[1].message
    # a document's words are its own: words that stand only in another document do not keep a link to this one
    put(q, "notes/c.md", "# C\n\n[elsewhere](quilt:drafting/outline.tex#quote=a%20finite%20set)\n")
    result = open_scan(str(q))
    assert "a finite set" not in result.expansions["drafting/outline.tex"].text
    gone = link_words_missing(result, backlinks(result, q, {"notes/c.md": "markdown"}))
    assert [(d.locations[0].file, d.locations[0].line) for d in gone] == [("notes/c.md", 3)]


@pytest.mark.poppler
def test_quoted_words_on_a_project_pdf_are_looked_for_on_the_page_named(tmp_path: Path) -> None:
    from loom.backlinks import words_found
    from loom.cli._quilt import open_scan

    q = demo(tmp_path)
    lines_pdf(q / "papers/median.pdf", [PROSE])
    result = open_scan(str(q))
    link = {"kind": "file", "key": "papers/median.pdf", "place": "page=1", "quote": "incidence matrix"}
    assert words_found(result, q, link) is True
    assert words_found(result, q, {**link, "quote": "no such words"}) is False
    # a PDF with no page named is not judged
    assert words_found(result, q, {**link, "place": ""}) is None


def test_a_notebook_note_opens_at_the_heading_above_its_link(tmp_path: Path) -> None:
    from loom.backlinks import backlinks
    from loom.cli._quilt import open_scan

    q = demo(tmp_path)
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Setup\n", "Nothing yet."]},
            {"cell_type": "code", "source": ["# a comment, no heading\n", "x = 1"]},
            {"cell_type": "markdown", "source": ["## Orbits\n", "See [it](quilt:dm-0003)."]},
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    put(q, "notes/book.ipynb", json.dumps(nb))
    (link,) = backlinks(open_scan(str(q)), q, {"notes/book.ipynb": "notebook"})
    assert (link["line"], link["at"]) == (6, "orbits")
