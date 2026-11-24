from pathlib import Path

import pytest

from loom.scan.source import blank_comments, discover_files, lake_project, lake_root, read_source


def test_blank_comments_preserves_offsets() -> None:
    text = "a % comment\nb \\% not\n\\verb|%x| c % d\n\\begin{verbatim}\n% keep\n\\end{verbatim}\n"
    clean = blank_comments(text)
    assert len(clean) == len(text)
    assert clean.startswith("a          \nb \\% not\n")
    assert "\\verb|%x| c    " in clean
    assert "% keep" in clean


@pytest.mark.parametrize(
    "excluded",
    [
        pytest.param(".loom/cache/x.tex", id="derived"),
        pytest.param(".loom/records/retired/old.tex", id="a-retired-source"),
        pytest.param(".loom/library/documents/x.tex", id="the-librarys-documents"),
        pytest.param(".loom/cache/library/sources/0a/paper.tex", id="a-stored-source-unpacked"),
        pytest.param("lean/.lake/packages/mathlib/docs/notes.tex", id="a-lake-project-s-build-and-packages"),
        pytest.param("notes.txt", id="not-tex"),
    ],
)
def test_the_quilts_text_is_every_tex_file_outside_loom_s_directory(tmp_path: Path, excluded: str) -> None:
    """Nothing under `.loom/` is the quilt's text but an agent's copy: a work's source the library holds is a whole paper carrying its own labels (DR-108)."""
    for rel in ["drafting/main.tex", "drafting/nodes/a.tex", excluded]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    assert discover_files(tmp_path) == ["drafting/main.tex", "drafting/nodes/a.tex"]


def test_a_skipped_directory_is_never_listed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Lake project's `.lake` holds tens of thousands of files (Mathlib's alone), so the scan prunes it as it walks rather than listing the tree and filtering after; `.loom/` is pruned the same way."""
    import os

    from loom.scan import source

    for rel in [
        "drafting/main.tex",
        "lean/.lake/packages/mathlib/Mathlib/A.olean",
        ".loom/cache/library/sources/w/p.tex",
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    listed: list[str] = []
    walk = os.walk

    def recorded(top: Path):  # type: ignore[no-untyped-def]
        for here, dirs, files in walk(top):
            listed.append(Path(here).relative_to(tmp_path).as_posix())
            yield here, dirs, files

    monkeypatch.setattr(source.os, "walk", recorded)
    assert discover_files(tmp_path) == ["drafting/main.tex"]
    assert "lean" in listed
    assert not [d for d in listed if ".lake" in d.split("/") or d.startswith(".loom")], listed


def _files(root: Path, *rels: str) -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")


@pytest.mark.parametrize("lakefile", ["lakefile.toml", "lakefile.lean"])
def test_a_lake_project_is_pruned_from_the_scan_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lakefile: str
) -> None:
    """The skills' linters need the paper inside the Lake project, and a copy there scanned as source made five keys conflicted and three loose (LTRIAL-5): a folder holding a lakefile is pruned as the scan walks, never listed, and no `.tex` under it is read."""
    import os

    from loom.scan import source

    _files(tmp_path, "drafting/main.tex", f"lean/{lakefile}", "lean/source/nodes/a.tex", "lean/Proof/Basic.lean")
    listed: list[str] = []
    walk = os.walk

    def recorded(top: Path):  # type: ignore[no-untyped-def]
        for here, dirs, files in walk(top):
            listed.append(Path(here).relative_to(tmp_path).as_posix())
            yield here, dirs, files

    monkeypatch.setattr(source.os, "walk", recorded)
    assert discover_files(tmp_path) == ["drafting/main.tex"]
    assert not [d for d in listed if d == "lean" or d.startswith("lean/")], listed


def test_a_lean_toolchain_alone_makes_no_lake_project_and_the_quilt_s_root_is_never_one(tmp_path: Path) -> None:
    """Only a lakefile makes a Lake project's root; and a lakefile at the quilt's own root prunes nothing, since the quilt is not the agents' own."""
    _files(
        tmp_path,
        "lakefile.toml",
        "main.tex",
        "lean/lean-toolchain",
        "lean/a.tex",
        "proof/lakefile.lean",
        "proof/sub/lakefile.toml",
    )
    assert discover_files(tmp_path) == ["lean/a.tex", "main.tex"]
    assert not lake_root(tmp_path / "lean") and lake_root(tmp_path / "proof")
    assert lake_project(tmp_path, "main.tex") is None and lake_project(tmp_path, "lean/a.tex") is None
    assert lake_project(tmp_path, "proof/sub/Basic.lean") == "proof"


def test_the_scan_names_a_lake_project_as_what_keeps_it_out_and_reads_no_text_given_there(tmp_path: Path) -> None:
    """`unread_dir`, which a command asks before it makes or moves a document, names the Lake project's root, as the scan prunes it; and a text a caller lays over the quilt there is not read either."""
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan, unread_dir

    (tmp_path / "config.toml").write_text('[quilt]\nname = "q"\n', encoding="utf-8")
    _files(tmp_path, "main.tex", "lean/lakefile.toml")
    quilt = load_quilt(tmp_path)
    assert unread_dir(quilt, "lean/source/nodes/a.tex") == "lean"
    assert unread_dir(quilt, "drafting/a.tex") is None
    result = scan(quilt, overlay={"lean/source/b.tex": "\\begin{lemma}x\\end{lemma}\n", "c.tex": "y\n"})
    assert sorted(result.files) == ["c.tex", "main.tex"]


def test_non_utf8_source_decoded(tmp_path: Path) -> None:
    (tmp_path / "old.tex").write_bytes(b"pages 989\xd01004\n")
    src = read_source(tmp_path, "old.tex")
    assert src.encoding == "mac_roman"
    assert "989\u20131004" in src.text
    (tmp_path / "new.tex").write_bytes("pages 989\u20131004\n".encode())
    assert read_source(tmp_path, "new.tex").encoding == "utf-8"


def test_ignore_directive_and_lines(tmp_path: Path) -> None:
    (tmp_path / "f.tex").write_text("line1\n% !LOOM ignore\nline3\n", encoding="utf-8")
    src = read_source(tmp_path, "f.tex")
    assert src.ignored
    assert src.line_of(src.text.index("line3")) == 3
    assert src.col_of(src.text.index("line3")) == 1


def test_scan_reads_an_unsaved_buffer_from_an_overlay(tmp_path: Path) -> None:
    """An editor holds text the disk does not; `scan(quilt, overlay)` sees the buffer, so diagnostics follow the keystrokes rather than the last save."""
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.unit.scan.helpers import DEFAULT_CONFIG, PREAMBLE

    root = tmp_path / "q"
    (root / "drafting").mkdir(parents=True)
    (root / "drafting" / "nodes").mkdir()
    (root / "config.toml").write_text(DEFAULT_CONFIG, encoding="utf-8")
    (root / "drafting" / "main.tex").write_text(
        PREAMBLE + "\\begin{document}\n\\input{nodes/ab-0001}\n\\end{document}\n", encoding="utf-8"
    )
    (root / "drafting" / "nodes" / "ab-0001.tex").write_text(
        "\\begin{lemma}[Saved]\\label{ab-0001}\nOn disk.\n\\end{lemma}\n", encoding="utf-8"
    )
    quilt = load_quilt(root)

    assert scan(quilt).nodes["ab-0001"].title == "Saved"

    edited = scan(
        quilt, {"drafting/nodes/ab-0001.tex": "\\begin{lemma}[Edited]\\label{ab-0001}\nIn the buffer.\n\\end{lemma}\n"}
    )
    assert edited.nodes["ab-0001"].title == "Edited"
    assert "In the buffer." in edited.files["drafting/nodes/ab-0001.tex"].text
    assert "On disk." in (root / "drafting" / "nodes" / "ab-0001.tex").read_text()  # nothing was written

    # a file the buffer has created but never saved is scanned too
    created = scan(
        quilt,
        {
            "drafting/nodes/ab-0002.tex": "\\begin{lemma}[New]\\label{ab-0002}\nUnsaved.\n\\end{lemma}\n",
            "drafting/main.tex": PREAMBLE
            + "\\begin{document}\n\\input{nodes/ab-0001}\n\\input{nodes/ab-0002}\n\\end{document}\n",
        },
    )
    assert created.nodes["ab-0002"].title == "New"
    assert created.nodes["ab-0002"].reached_by == ["drafting/main.tex"]


def test_a_directory_of_the_person_s_own_is_read_whatever_its_name(tmp_path: Path) -> None:
    """`notes/` and `build/` are names a person may give any directory, so loom reads them as it reads every other; `% !LOOM ignore` keeps a file out."""
    from tests.unit.scan.helpers import PREAMBLE, make_quilt

    result = make_quilt(
        tmp_path,
        {
            "drafting/main.tex": PREAMBLE + "\\begin{document}\n\\input{notes/mine}\n\\end{document}\n",
            "drafting/notes/mine.tex": "\\begin{lemma}\\label{ab-0001}\nMine.\n\\end{lemma}\n",
            "build/colleague.tex": "% !LOOM ignore\n\\begin{lemma}\\label{ab-0002}\nTheirs.\n\\end{lemma}\n",
        },
    )
    assert "ab-0001" in result.nodes and "ab-0002" not in result.nodes
    assert "build/colleague.tex" in result.files and result.files["build/colleague.tex"].ignored
