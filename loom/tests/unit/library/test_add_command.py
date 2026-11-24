"""`loom library add` on the new intake: documents added as works or under one, a dry run that leaves nothing behind, and `--for` by a reference or its entry's key."""

from __future__ import annotations

from pathlib import Path

from loom.library.intake import incoming
from tests.helpers import json_of, refused
from tests.unit._pdfs import lines_pdf


def quilt(tmp_path: Path) -> Path:
    from loom.scan.quilt import load_quilt

    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\n\n[library]\nonline = false\n')
    load_quilt(root)
    return root


def test_documents_are_added_as_works_and_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    pdf = lines_pdf(tmp_path / "Smith - 2024 - Widgets.pdf", [["Widgets", "Jane Smith"]])
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{Jon19, title = {Covers}}\n")
    dry = json_of("library", "add", str(pdf), str(bib), "--dry-run", "--json", "--as", "A. Author", cwd=root)
    assert dry["added"] == 2
    assert not (root / ".loom/library/nodes").exists() and not any(incoming(root).glob("*"))
    done = json_of("library", "add", str(pdf), str(bib), "--json", "--as", "A. Author", cwd=root)
    assert [d["state"] for d in done["documents"]] == ["added", "added"]
    assert pdf.read_bytes().startswith(b"%PDF"), "the person's own file is never touched"


def test_for_names_a_work_by_its_reference_or_its_key(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{Jon19, title = {Covers}}\n")
    [row] = json_of("library", "add", str(bib), "--json", "--as", "A. Author", cwd=root)["documents"]
    pdf = lines_pdf(tmp_path / "covers.pdf", [["Covers"]])
    [filed] = json_of("library", "add", str(pdf), "--for", "jon19", "--json", "--as", "A. Author", cwd=root)[
        "documents"
    ]
    assert (filed["state"], filed["ref"], filed["under"]) == ("added", row["ref"], True)
    refused(
        "library", "add", str(pdf), "--for", "Nobody", "--as", "A. Author", cwd=root, code=2, match="no work Nobody"
    )
