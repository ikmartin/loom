"""The links a quilt's own files make (`docs/design/model.md`, "Notes"): read in Markdown, org, plain text and notebooks, raw or bracketed, resolved to what each names, and published in the manifest so the viewer lists beside an item the files that link to it."""

from __future__ import annotations

import json
from pathlib import Path

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
