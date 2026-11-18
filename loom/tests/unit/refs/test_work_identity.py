"""A work's identity, which links and annotations name, does not move when a person corrects its details: a work that came in as a PDF stating no identifier is named by that PDF's hash (`refs.identity.filed`), the study's LIB-9 and QF-22."""

from __future__ import annotations

import hashlib
from pathlib import Path

from loom.links import resolve
from loom.refs.identity import identify
from loom.scan.bib import parse_bib
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok
from tests.unit._quilts import demo
from tests.unit.refs._made_pdfs import fake_pdf

BIB = ".loom/library/bibliography.bib"


def test_a_corrected_title_leaves_a_works_identity_and_its_links_alone(tmp_path: Path) -> None:
    q = demo(tmp_path)
    pdf = fake_pdf(tmp_path / "scan.pdf", "Statistical Inferense\nG. Casela\n")
    ok("library", "add", str(pdf), "--as", "A. Author", cwd=q)
    entries = parse_bib((q / BIB).read_text(encoding="utf-8"))
    (key,) = [k for k, e in entries.items() if e.fields.get("title") == "Statistical Inferense"]
    wid = identify(entries[key])[0]
    assert str(wid) == "work:" + hashlib.sha256(pdf.read_bytes()).hexdigest()[:8]
    href = f"cited:{wid}?page=1"
    assert resolve(scan(load_quilt(q)), q, href, []).key == key

    text = (q / BIB).read_text(encoding="utf-8")
    (q / BIB).write_text(text.replace("Statistical Inferense", "Statistical Inference"), encoding="utf-8")
    result = scan(load_quilt(q))
    assert result.bib[key].fields["title"] == "Statistical Inference"
    assert identify(result.bib[key])[0] == wid
    assert resolve(result, q, href, []).key == key
