"""The library's documents by hash (`library.documents`): one file a document, a source in one form whatever it came as, unpacked safely, and its main file found."""

from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from loom.library.documents import (
    NotASource,
    folder_files,
    held,
    main_file,
    path_of,
    put_pdf,
    put_source,
    source_dir,
    source_tar,
    tar_of,
    unpack,
)
from loom.paths import LIBRARY_DOCUMENTS

SOURCE = {
    "main.tex": b"\\documentclass{amsart}\n\\begin{document}x\\end{document}\n",
    "fig/a.pdf": b"%PDF-1.4 x",
    "defs.sty": b"\\newcommand{\\R}{\\mathbb{R}}\n",
}


def targz(files: dict[str, bytes], *, extra: list[tarfile.TarInfo] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in reversed(list(files.items())):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 1_700_000_000
            info.mode = 0o600
            tar.addfile(info, io.BytesIO(data))
        for info in extra or []:
            tar.addfile(info, io.BytesIO(b"evil"))
    return buffer.getvalue()


def a_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def test_a_pdf_is_kept_once_by_its_hash(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 a paper")
    first = put_pdf(tmp_path, pdf)
    assert put_pdf(tmp_path, pdf) == first
    assert path_of(tmp_path, first, "pdf").read_bytes() == pdf.read_bytes()
    assert held(tmp_path, first, "pdf") and not held(tmp_path, first, "tex")
    assert [p.name for p in (tmp_path / LIBRARY_DOCUMENTS).iterdir()] == [first.removeprefix("sha256:") + ".pdf"]


def test_a_copied_pdf_does_not_follow_its_original_and_a_linked_one_is_loom_s_own(tmp_path: Path) -> None:
    pdf = tmp_path / "theirs.pdf"
    pdf.write_bytes(b"%PDF-1.4 theirs")
    digest = put_pdf(tmp_path, pdf)
    assert path_of(tmp_path, digest, "pdf").stat().st_ino != pdf.stat().st_ino
    own = tmp_path / "drop.pdf"
    own.write_bytes(b"%PDF-1.4 a drop")
    linked = put_pdf(tmp_path, own, link=True)
    assert path_of(tmp_path, linked, "pdf").read_bytes() == own.read_bytes()


def test_a_source_hashes_alike_from_a_folder_an_archive_and_a_zip(tmp_path: Path) -> None:
    folder = tmp_path / "src"
    for name, data in SOURCE.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    (folder / ".DS_Store").write_bytes(b"x")
    from_folder = put_source(tmp_path, folder)
    assert put_source(tmp_path, targz(SOURCE)) == from_folder
    assert put_source(tmp_path, a_zip(SOURCE)) == from_folder
    assert unpack(path_of(tmp_path, from_folder, "tex").read_bytes()) == SOURCE
    assert source_tar(folder) == tar_of(SOURCE) == tar_of(dict(reversed(list(SOURCE.items()))))


def test_a_single_gzipped_file_is_a_source_of_one_file(tmp_path: Path) -> None:
    tex = b"\\documentclass{article}\\begin{document}y\\end{document}"
    assert unpack(gzip.compress(tex), "2401.01234v2.gz") == {"main.tex": tex}
    assert unpack(tex, "paper.tex") == {"paper.tex": tex}
    with pytest.raises(NotASource):
        source_tar(b"")


def test_nothing_escapes_or_hides_in_an_archive() -> None:
    evil = []
    for name in ("../outside.tex", "/etc/passwd", "a/../../up.tex", ".hidden/x.tex"):
        info = tarfile.TarInfo(name)
        info.size = 4
        evil.append(info)
    link = tarfile.TarInfo("link.tex")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    evil.append(link)
    assert unpack(targz(SOURCE, extra=evil)) == SOURCE
    assert unpack(a_zip({**SOURCE, "../z.tex": b"x"})) == SOURCE


def test_a_source_is_unpacked_into_the_cache_once(tmp_path: Path) -> None:
    digest = put_source(tmp_path, targz(SOURCE))
    out = source_dir(tmp_path, digest)
    assert folder_files(out) == SOURCE
    (out / "main.tex").write_bytes(b"changed")
    assert source_dir(tmp_path, digest) == out and (out / "main.tex").read_bytes() == b"changed"


def test_the_main_file_declares_the_class(tmp_path: Path) -> None:
    for name, text in {
        "sections/one.tex": "text",
        "deep/x/paper.tex": "\\documentclass{amsart}",
        "arxiv.tex": "\\documentclass{article}",
        "main.tex": "\\documentclass{amsart}",
    }.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    assert main_file(tmp_path) == tmp_path / "main.tex"
    (tmp_path / "main.tex").write_text("no class")
    assert main_file(tmp_path) == tmp_path / "deep/x/paper.tex", "a conventional name before a shallow one"
    (tmp_path / "deep/x/paper.tex").write_text("no class")
    assert main_file(tmp_path) == tmp_path / "arxiv.tex"
    assert main_file(tmp_path / "sections") is None
