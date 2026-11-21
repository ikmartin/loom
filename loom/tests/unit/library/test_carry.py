"""The carry-over of an earlier loom's library (`library.carry`): each entry a reference standing alone with its documents stored by hash, notes on works re-keyed byte for byte, overviews made notes, links rewritten, the old files and digests removed, and nothing changed by a second carry or a dry run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from loom.identity import is_agent
from loom.library import documents, log
from loom.library.carry import BIBLIOGRAPHY, LINKS, OVERVIEW_AUTHOR, STORAGE, STORE_LEDGER, UNREADABLE, Carried, carry
from loom.library.checks import check
from loom.library.entries import read_entry
from loom.library.store import read
from loom.paths import ANNOTATION_LOG, CACHE, LIBRARY, LIBRARY_DOCUMENTS, LIBRARY_NODES, LOCAL
from loom.records.log import replay
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit.library._old import HAR77, PDF_A, SMI24, old_library

PDF_V = b"%PDF-1.4\n% its second version\n"
MAIN = "\\documentclass{amsart}\n\\newcommand{\\R}{\\mathbb{R}}\n\\title{Widgets}\n\\begin{document}\nWidgets.\n\\end{document}\n"
FILED = "file/0123456789abcdef"

SMI24_V2 = f"""@article{{Smi24-v2,
  author = {{Smith, Jane}},
  title  = {{Widgets}},
  year   = {{2024}},
  loom-source = {{smith-widgets-v2.pdf}},
  loom-file = {{{FILED}}},
  loom-copy-of = {{Smi24}},
  loom-parsed = {{heuristic}},
}}"""
CARRIED = {
    "Smi24": "@article{Smi24,\n  author = {Smith, Jane},\n  title  = {Widgets},\n  year   = {2024},\n  eprint = {2401.01234v1},\n  archiveprefix = {arXiv},\n}\n",
    "Smi24-v2": "@article{Smi24-v2,\n  author = {Smith, Jane},\n  title  = {Widgets},\n  year   = {2024},\n}\n",
    "Har77": HAR77 + "\n",
}
#: The old `work:` hash of Har77, which states no identifier: eight hex digits of its folded surname, title and year.
HAR77_WORK = hashlib.sha256(b"hartshorne|algebraicgeometry|1977").hexdigest()[:8]
DIGEST = "% !LOOM digest: Smi24\n% !LOOM prefix: Smi24\n% !LOOM extracted-from: arXiv:2401.01234v1\n% !LOOM method: extract\n\n\\begin{theorem}[{\\cite[Theorem 4.1]{Smi24}}]\\label{Smi24-thm-4.1}\nEvery widget is a widget.\n\\end{theorem}\n"


def event(**fields: object) -> str:
    """One annotation-log line as `records.log.append` writes it."""
    return json.dumps(fields, ensure_ascii=False, sort_keys=True)


NOTES = [
    event(event="created", id="a-2026-09-16-aaaaaa", author="Isaac", kind="person", when="2026-09-16T10:00:00Z", target="arXiv:2401.01234v1", anchor=None, type="note", body="Read §2 first."),
    event(event="created", id="a-2026-09-16-bbbbbb", author="Isaac", kind="person", when="2026-09-16T10:01:00Z", target=f"work:{HAR77_WORK}", anchor=None, type="question", body="Which edition — the 1977 one?"),
    event(event="created", id="a-2026-09-16-cccccc", author="Isaac", kind="person", when="2026-09-16T10:02:00Z", target="arXiv:2401.01234v1", anchor={"exact": "Widgets.", "prefix": "", "suffix": ""}, artifact=hashlib.sha256(PDF_V).hexdigest(), mark="box", page=1, rects=[[1.0, 2.0, 3.0, 4.0]], type=None, body=""),
    event(event="created", id="a-2026-09-16-dddddd", author="Isaac", kind="person", when="2026-09-16T10:03:00Z", target="tq-0001", anchor=None, type="note", body="On my own lemma."),
    event(event="created", id="a-2026-09-16-eeeeee", author="Isaac", kind="person", when="2026-09-16T10:04:00Z", target="Smi24-thm-4.1", anchor=None, type="note", body="On the digest's theorem."),
]  # fmt: skip


def old_quilt(tmp_path: Path, bib: str | None = None) -> Path:
    """A quilt in format 1 as an earlier loom left it: a bibliography with loom's fields, a store, a digest, notes on works and a research state linking a work by its hash."""
    root = tmp_path / "q"
    root.mkdir(parents=True)
    (root / "config.toml").write_text('[quilt]\nprefix = "tq"\n')
    arxiv = "arxiv/2401.01234v1"
    old_library(
        root,
        bib if bib is not None else "\n\n".join([SMI24, SMI24_V2, HAR77]),
        {
            f"{arxiv}/paper.pdf": PDF_A,
            f"{arxiv}/src/main.tex": MAIN.encode(),
            f"{arxiv}/overview.md": f"Widgets, read whole. Compare [](cited:work:{HAR77_WORK}).\n".encode(),
            f"{arxiv}/sections.json": b"{}\n",
            f"{FILED}/paper.pdf": PDF_V,
        },
    )
    library = root / LIBRARY
    (root / STORE_LEDGER).write_text(
        json.dumps({hashlib.sha256(PDF_V).hexdigest(): {"from": "smith-widgets-v2.pdf", "to": FILED}}) + "\n"
    )
    (library / "Smi24.tex").write_text(DIGEST)
    (library / "Smi24.results.json").write_text(json.dumps({"record": 1, "citekey": "Smi24", "results": [{"id": "Smi24-thm-4.1", "local": "thm-4.1"}]}) + "\n")  # fmt: skip
    (root / UNREADABLE).write_text("[]\n")
    (root / LINKS).write_text("")
    (root / ANNOTATION_LOG).parent.mkdir(parents=True)
    (root / ANNOTATION_LOG).write_text("".join(f"{line}\n" for line in NOTES))
    (root / "research-state.md").write_text(
        f"# State\n\nThe textbook is [](cited:work:{HAR77_WORK}); the rest waits.\n"
    )
    return root


def run(root: Path, *, write: bool = True) -> Carried:
    return carry(root, scan(load_quilt(root, older=True)), write=write)


def files(root: Path) -> dict[str, bytes]:
    """Every file of the quilt that travels with it, by quilt-relative path: the cache and this machine's state left out."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.relative_to(root).as_posix().startswith((f"{CACHE}/", f"{LOCAL}/"))
    }


def references(root: Path) -> dict[str, str]:
    """Each reference's entry key to its id."""
    out = {}
    for path in sorted((root / LIBRARY_NODES).glob("*-ref.node")):
        node = read(root, path.name.removesuffix(".node"))
        assert node is not None
        entry = read_entry(node.body)
        assert entry is not None
        out[entry.key] = node.id
    return out


def test_each_entry_becomes_a_reference_with_its_documents_and_its_notes(tmp_path: Path) -> None:
    root = old_quilt(tmp_path)
    done = run(root)
    refs = references(root)
    assert done.references == refs and set(refs) == {"Smi24", "Smi24-v2", "Har77"}
    for key, ref in refs.items():
        node = read(root, ref)
        assert node is not None and node.body == CARRIED[key]

    smith, version, book = read(root, refs["Smi24"]), read(root, refs["Smi24-v2"]), read(root, refs["Har77"])
    assert smith is not None and version is not None and book is not None
    assert smith.pdf == "sha256:" + hashlib.sha256(PDF_A).hexdigest() and documents.held(root, smith.pdf, "pdf")
    assert smith.tex is not None and documents.held(root, smith.tex, "tex")
    assert version.pdf == "sha256:" + hashlib.sha256(PDF_V).hexdigest() and version.tex is None
    assert book.pdf is None and book.tex is None
    macros = read(root, refs["Smi24"].removesuffix("-ref") + "-macros")
    assert macros is not None and macros.body == "\\newcommand{\\R}{\\mathbb{R}}\n"
    acts = log.replay(root)
    made = acts.made(refs["Smi24-v2"])
    assert made is not None and (made["how"], made["kind"], made["found_by"], made["looked_up"]) == (
        "carry",
        "loom",
        "entry",
        False,
    )
    assert made["source"] == "smith-widgets-v2.pdf copy-of Smi24"
    assert (acts.made(refs["Har77"]) or {})["source"] == "bibliography.bib"
    assert (done.documents, done.notes_rekeyed, done.overviews, done.links_rewritten) == (3, 3, 1, 2)

    # each note on a work now names its reference, the mark the version whose PDF it was drawn on, and nothing else in its line moved
    lines = (root / ANNOTATION_LOG).read_text().splitlines()
    assert lines[:5] == [
        NOTES[0].replace('"arXiv:2401.01234v1"', f'"{refs["Smi24"]}"'),
        NOTES[1].replace(f'"work:{HAR77_WORK}"', f'"{refs["Har77"]}"'),
        NOTES[2].replace('"arXiv:2401.01234v1"', f'"{refs["Smi24-v2"]}"'),
        NOTES[3],
        NOTES[4],
    ]
    overview = [a for r in replay(root)[0] for a in r.annotations if a.author_id == OVERVIEW_AUTHOR]
    assert len(overview) == 1 and not is_agent(OVERVIEW_AUTHOR)
    assert (overview[0].target_key, overview[0].type, overview[0].author_kind) == (refs["Smi24"], "note", "person")
    assert overview[0].body == f"Widgets, read whole. Compare [](quilt:{refs['Har77']}).\n"
    assert (
        root / "research-state.md"
    ).read_text() == f"# State\n\nThe textbook is [](quilt:{refs['Har77']}); the rest waits.\n"

    # the old library is gone, its digest with it, and the node store stays
    for gone in (BIBLIOGRAPHY, STORAGE, UNREADABLE, LINKS, f"{LIBRARY}/Smi24.tex", f"{LIBRARY}/Smi24.results.json"):
        assert not (root / gone).exists(), gone
        assert gone in done.removed
    assert sorted(p.name for p in (root / LIBRARY).iterdir()) == sorted(
        Path(p).name for p in (LIBRARY_NODES, LIBRARY_DOCUMENTS)
    )
    assert done.problems == ["1 note on a digest's result now names nothing, since the digests are removed with the old library."]  # fmt: skip
    assert check(root) == []


def test_carrying_again_changes_nothing(tmp_path: Path) -> None:
    root = old_quilt(tmp_path)
    run(root)
    result = scan(load_quilt(root, older=True))
    before = files(root)
    again = carry(root, result)
    assert files(root) == before
    assert again == Carried()


def test_a_dry_run_writes_nothing_and_says_what_a_carry_does(tmp_path: Path) -> None:
    dry_root = old_quilt(tmp_path / "dry")
    result = scan(load_quilt(dry_root, older=True))
    before = files(dry_root)
    said = carry(dry_root, result, write=False)
    assert files(dry_root) == before
    assert said == run(old_quilt(tmp_path / "real"))


def test_a_folder_no_entry_names_is_left_and_said(tmp_path: Path) -> None:
    root = old_quilt(tmp_path)
    stray = root / STORAGE / "doi" / "10.1000_stray"
    stray.mkdir(parents=True)
    (stray / "paper.pdf").write_bytes(b"%PDF-1.4\n% nobody's\n")
    done = run(root)
    assert (stray / "paper.pdf").read_bytes() == b"%PDF-1.4\n% nobody's\n"
    assert f"{STORAGE}/doi/10.1000_stray holds a work's documents and no entry names it, so it is left in place." in done.problems  # fmt: skip
    assert not (root / STORAGE / "arxiv").exists() and not (root / STORAGE / "file").exists()
    assert not (root / STORE_LEDGER).exists() and not (root / BIBLIOGRAPHY).exists()
    assert STORAGE not in done.removed and f"{STORAGE}/arxiv" in done.removed
    assert check(root) == []


def test_an_entry_the_checks_refuse_is_said_and_the_rest_are_carried(tmp_path: Path) -> None:
    jones = "@article{Jon19,\n  author  = {Jones, Alex},\n  journal = JEx,\n  year    = {2019},\n  doi     = {10.1000/jones},\n}"
    root = old_quilt(tmp_path, "\n\n".join([SMI24, jones, HAR77]))
    folder = root / STORAGE / "doi" / "10.1000_jones"
    folder.mkdir(parents=True)
    (folder / "paper.pdf").write_bytes(b"%PDF-1.4\n% Jones\n")
    done = run(root)
    assert set(references(root)) == {"Smi24", "Har77"} == set(done.references)
    refused = [p for p in done.problems if p.startswith("Jon19 ")]
    assert (
        len(refused) == 1
        and "JEx" in refused[0]
        and refused[0].endswith(f"its documents stay in {STORAGE}/doi/10.1000_jones.")
    )
    assert (folder / "paper.pdf").is_file() and not (root / STORAGE / "arxiv").exists()
    assert check(root) == []
