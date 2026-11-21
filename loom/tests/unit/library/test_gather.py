"""Gathering (`library.gather`): a reference for each entry the documents read, verbatim and standing alone, made once, left alone once the person deleted it, and following its `.bib` until edited in loom."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from loom.library import log
from loom.library.checks import check
from loom.library.entries import read_entry
from loom.library.gather import bibitem_entry, gather, strings_of
from loom.library.store import read, write_node
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan

MAIN = "\\documentclass{article}\n\\begin{document}\nSee \\cite{Smi24} and \\cite{Jon19}.\n\\bibliography{refs}\n%s\\end{document}\n"
BIB = "@string{JEx = {Journal of Examples}}\n\n@article{Smi24,\n  author = {Smith, Jane},\n  title  = {Widgets},\n  year   = {2024},\n}\n\n@article{Jon19,\n  author  = {Jones, Alex},\n  journal = JEx,\n  year    = {2019},\n}\n"


def quilt(tmp_path: Path, bibitems: str = "") -> Path:
    root = tmp_path / "q"
    root.mkdir()
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\nmain = "main.tex"\n')
    (root / "main.tex").write_text(MAIN % bibitems)
    (root / "refs.bib").write_text(BIB)
    return root


def refs(root: Path) -> dict[str, str]:
    """Each reference's entry key to its body."""
    out = {}
    for path in sorted((root / ".loom/library/nodes").glob("*-ref.node")):
        node = read(root, path.name.removesuffix(".node"))
        assert node is not None
        entry = read_entry(node.body)
        assert entry is not None
        out[entry.key] = node.body
    return out


def test_each_entry_a_document_reads_becomes_a_reference_standing_alone(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    done = gather(scan(load_quilt(root)))
    assert len(done.made) == 2 and done.refused == []
    got = refs(root)
    assert got["Smi24"] == "@article{Smi24,\n  author = {Smith, Jane},\n  title  = {Widgets},\n  year   = {2024},\n}\n"
    assert "journal = {Journal of Examples}," in got["Jon19"]
    assert check(root) == []
    made = log.replay(root).made(done.made[0])
    assert made is not None and (made["how"], made["kind"], made["source"]) == (
        "gather",
        "loom",
        "main.tex via refs.bib",
    )


def test_a_key_held_already_makes_nothing_whatever_its_case(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    gather(scan(load_quilt(root)))
    (root / "refs.bib").write_text(BIB.replace("Smi24", "smi24"))
    (root / "main.tex").write_text(MAIN.replace("Smi24", "smi24") % "")
    assert gather(scan(load_quilt(root))).made == []


def test_a_deleted_key_is_left_alone_until_the_work_is_added_again(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    done = gather(scan(load_quilt(root)))
    smith = next(r for r in done.made if "Smi24" in (read(root, r).body if read(root, r) else ""))  # type: ignore[union-attr]
    (root / ".loom/library/nodes" / f"{smith}.node").unlink()
    log.record(root, "deleted", smith, key="Smi24", undo="u-1", by="Isaac", kind="person")
    again = gather(scan(load_quilt(root)))
    assert again.made == [] and again.deleted == ["Smi24"]
    log.record(root, "restored", smith, undo="u-1", by="Isaac", kind="person")
    assert len(gather(scan(load_quilt(root))).made) == 1


def test_a_gathered_reference_follows_its_bib_until_edited_in_loom(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    gather(scan(load_quilt(root)))
    (root / "refs.bib").write_text(BIB.replace("{Widgets}", "{Widgets and bounds}"))
    done = gather(scan(load_quilt(root)))
    assert len(done.followed) == 1 and "Widgets and bounds" in refs(root)["Smi24"]
    ref = done.followed[0]
    node = read(root, ref)
    assert node is not None
    write_node(root, replace(node, body=node.body.replace("Widgets and bounds", "Widgets, corrected")))
    log.record(root, "edited", ref, by="Isaac", kind="person")
    (root / "refs.bib").write_text(BIB.replace("{Widgets}", "{Widgets again}"))
    assert gather(scan(load_quilt(root))).followed == []
    assert "Widgets, corrected" in refs(root)["Smi24"]


def test_a_dry_run_says_what_would_be_made_and_writes_nothing(tmp_path: Path) -> None:
    root = quilt(tmp_path)
    assert sorted(gather(scan(load_quilt(root)), write=False).made) == ["Jon19", "Smi24"]
    assert not (root / ".loom/library/nodes").exists()


def test_a_bibitem_is_its_text_and_the_identifiers_it_writes(tmp_path: Path) -> None:
    root = quilt(
        tmp_path,
        "\\begin{thebibliography}{9}\n\\bibitem{Ber21} K. Berg, \\emph{Gadgets}, arXiv:2101.00001v2, doi 10.1000/gadget.\n\\end{thebibliography}\n",
    )
    gather(scan(load_quilt(root)))
    assert refs(root)["Ber21"] == (
        "@misc{Ber21,\n  note = {K. Berg, \\emph{Gadgets}, arXiv:2101.00001v2, doi 10.1000/gadget.},\n"
        "  eprint = {2101.00001v2},\n  archiveprefix = {arXiv},\n  doi = {10.1000/gadget},\n}\n"
    )
    assert bibitem_entry("X", "a } stray") == "@misc{X,\n  note = {a ) stray},\n}\n"


def test_strings_are_read_from_braces_and_quotes() -> None:
    assert strings_of('@string{a = {A {b}}}\n@STRING(c = "C")\n') == {"a": "A {b}", "c": "C"}
