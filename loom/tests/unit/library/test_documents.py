"""The library's documents by hash (`library.documents`): one file a document, a source in one form whatever it came as, unpacked safely, and its main file found."""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
import tracemalloc
import zipfile
from pathlib import Path
from typing import Any

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


def files_of(root: Path, src: Path | bytes, name: str = "") -> dict[str, bytes]:
    """The files of a source as the store keeps it and the cache unpacks it."""
    return folder_files(source_dir(root, put_source(root, src, name=name)))


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
    assert folder_files(source_dir(tmp_path, from_folder)) == SOURCE
    assert source_tar(folder) == tar_of(SOURCE) == tar_of(dict(reversed(list(SOURCE.items()))))


def test_a_single_gzipped_file_is_a_source_of_one_file(tmp_path: Path) -> None:
    tex = b"\\documentclass{article}\\begin{document}y\\end{document}"
    assert files_of(tmp_path / "a", gzip.compress(tex), "2401.01234v2.gz") == {"main.tex": tex}
    (tmp_path / "paper.tex").write_bytes(tex)
    assert files_of(tmp_path / "b", tmp_path / "paper.tex", "Paper (final).tex") == {"paper.tex": tex}
    assert files_of(tmp_path / "c", tex, "paper.tex") == {"main.tex": tex}, "bytes have no file name of their own"
    with pytest.raises(NotASource):
        source_tar(b"")


def test_nothing_escapes_or_hides_in_an_archive(tmp_path: Path) -> None:
    evil = []
    for name in ("../outside.tex", "/etc/passwd", "a/../../up.tex", ".hidden/x.tex"):
        info = tarfile.TarInfo(name)
        info.size = 4
        evil.append(info)
    link = tarfile.TarInfo("link.tex")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    evil.append(link)
    assert files_of(tmp_path / "a", targz(SOURCE, extra=evil)) == SOURCE
    assert files_of(tmp_path / "b", a_zip({**SOURCE, "../z.tex": b"x"})) == SOURCE


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


# ---- archives that are damaged, unusual, or larger than any paper's source -------------------------------------------

DOC = b"\\documentclass{article}\n\\begin{document}x\\end{document}\n"


def a_tar(members: list[tuple[str, bytes]], *, gz: bool = False) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue()) if gz else buffer.getvalue()


def a_locked_zip() -> bytes:
    """A zip whose member is marked encrypted, in its local header and the central directory, as `zip -P` marks one."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("main.tex", DOC)
    data = bytearray(buffer.getvalue())
    data[data.find(b"PK\x03\x04") + 6] |= 1
    data[data.find(b"PK\x01\x02") + 8] |= 1
    return bytes(data)


REFUSED = [
    ("damaged.tar.gz", a_tar([("main.tex", DOC)], gz=True)[:-40], "damaged.tar.gz is damaged, or is not a TeX source"),
    ("noise.gz", b"\x1f\x8b" + bytes(range(256)) * 8, "noise.gz is damaged, or is not a TeX source"),
    ("paper.pdf.gz", gzip.compress(b"%PDF-1.4\n" + b"x" * 100), "paper.pdf.gz holds no TeX source"),
    ("broken.zip", b"PK\x03\x04" + bytes(range(256)) * 12, "broken.zip is damaged, or is not a TeX source"),
    ("locked.zip", a_locked_zip(), "locked.zip is protected by a password; drop the source without one"),
    (
        "both.tar",
        a_tar([("main.tex", DOC), ("a", b"x"), ("a/b.tex", b"y")]),
        "both.tar holds both a file and a folder named a",
    ),
    (
        "long.tar",
        a_tar([("main.tex", DOC), ("n" * 300 + ".tex", b"x")]),
        "long.tar holds a file whose name is too long; loom cannot keep it",
    ),
    (
        "feed.tar",
        a_tar([("main.tex", DOC), ("bad\nname.tex", b"x")]),
        "feed.tar holds a file whose name has a control character in it; loom cannot keep it",
    ),
    (
        "case.tar",
        a_tar([("main.tex", DOC), ("Main.tex", b"x")]),
        "case.tar holds both main.tex and Main.tex, names a disk keeps as one file, since they differ only in case or in how an accent is written",
    ),
    ("figures.tar", a_tar([("fig.png", b"\x89PNG")]), "figures.tar holds no .tex file, so it is not a TeX source"),
    ("binary.tex", bytes(range(256)) * 4, "binary.tex holds no TeX source"),
]


@pytest.mark.parametrize(("name", "data", "said"), REFUSED, ids=[r[0] for r in REFUSED])
def test_an_archive_damaged_or_unusual_is_refused_in_a_sentence_and_nothing_is_stored(
    tmp_path: Path, name: str, data: bytes, said: str
) -> None:
    """The review's M-6: each is one sentence a person acts on, never Python's words, and the store keeps nothing of it."""
    with pytest.raises(NotASource) as refused:
        put_source(tmp_path, data, name=name)
    assert str(refused.value) == said
    assert list((tmp_path / LIBRARY_DOCUMENTS).iterdir()) == [], "nothing stored, no spool and no temporary left"


def test_a_held_source_is_unpacked_again_whatever_its_names(tmp_path: Path) -> None:
    """A tar in the store holding a file and a folder of one name, as an earlier loom kept one: the cache leaves out what it cannot hold beside the rest, and every later read of the source succeeds."""
    data = a_tar([("main.tex", DOC), ("a", b"x"), ("a/b.tex", b"y"), ("main.tex", b"again")])
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    stored = path_of(tmp_path, digest, "tex")
    stored.parent.mkdir(parents=True)
    stored.write_bytes(data)
    out = source_dir(tmp_path, digest)
    assert folder_files(out) == {"main.tex": DOC, "a": b"x"}
    assert source_dir(tmp_path, digest) == out
    assert [p.name for p in out.parent.iterdir()] == [out.name], "no partial folder is left beside it"


class Zeros(io.RawIOBase):
    """`size` zero bytes, made as they are read, so a test builds a bomb without holding it."""

    def __init__(self, size: int) -> None:
        self.left = size

    def readable(self) -> bool:
        return True

    def readinto(self, b: Any) -> int:
        n = min(len(b), self.left)
        b[:n] = b"\0" * n
        self.left -= n
        return n


def a_bomb(path: Path, inside: int) -> Path:
    """A `.tar.gz` holding a main file and `inside` zero bytes, written as it is made."""
    with gzip.open(path, "wb", compresslevel=9) as gz, tarfile.open(fileobj=gz, mode="w|") as tar:
        tar.addfile(tarfile.TarInfo("main.tex"), io.BytesIO(b""))
        info = tarfile.TarInfo("zeros.tex")
        info.size = inside
        tar.addfile(info, io.BufferedReader(Zeros(inside), 1 << 20))
    return path


def packed_peak(root: Path, src: Path) -> tuple[str | None, int]:
    """What `put_source` said of `src`, a hash or a refusal, and the most memory Python held while it ran."""
    tracemalloc.start()
    try:
        said: str | None = put_source(root, src, name=src.name)
    except NotASource as exc:
        said = str(exc)
    finally:
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    return said, peak


def test_an_archive_unpacking_past_the_limit_is_refused_as_it_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review's M-7, with the limit made small so the bomb is: refused once the limit is passed, holding a piece at a time, and nothing stored."""
    import loom.library.documents as documents

    monkeypatch.setattr(documents, "MAX_EXPANDED", 8 << 20)
    bomb = a_bomb(tmp_path / "bomb.tar.gz", 96 << 20)
    assert bomb.stat().st_size < 1 << 20
    said, peak = packed_peak(tmp_path / "q", bomb)
    assert said == "bomb.tar.gz unpacks to more than 8 MB, more than any paper's source"
    assert peak < 6 << 20, f"held {peak >> 20} MB"
    assert list((tmp_path / "q" / LIBRARY_DOCUMENTS).iterdir()) == []


def test_an_archive_within_the_limit_is_packed_without_holding_it(tmp_path: Path) -> None:
    said, peak = packed_peak(tmp_path / "q", a_bomb(tmp_path / "big.tar.gz", 48 << 20))
    assert said is not None and said.startswith("sha256:")
    assert peak < 6 << 20, f"held {peak >> 20} MB of a 48 MB source"
    assert folder_files(source_dir(tmp_path / "q", said))["zeros.tex"] == b"\0" * (48 << 20)


def test_an_archive_of_more_files_than_a_paper_has_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loom.library.documents as documents

    monkeypatch.setattr(documents, "MAX_FILES", 50)
    many = a_tar([("main.tex", DOC)] + [(f"f{i}.tex", b"x") for i in range(60)])
    with pytest.raises(NotASource) as refused:
        put_source(tmp_path, many, name="many.tar")
    assert str(refused.value) == "many.tar holds more than 50 files, more than any paper's source"


def test_the_limits_are_those_a_paper_s_source_never_reaches() -> None:
    from loom.library.documents import MAX_EXPANDED, MAX_FILES

    assert MAX_EXPANDED >= 200 << 20 and MAX_FILES >= 5_000
