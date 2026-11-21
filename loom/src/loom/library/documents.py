"""The library's stored documents, by hash: `.loom/library/documents/<hex>.pdf`, and a work's TeX source as one file, `<hex>.tar`.

A reference names its documents by these hashes (`pdf`, `tex`; `docs/specs/nodes.md` §2), so one document is stored once whatever works hold it, and nothing about a work is read from where its documents sit. A source is kept in one form, an uncompressed tar of its files with names sorted and owners, modes and times fixed, so a folder, a `.tar.gz` and a `.zip` of the same files hash alike on any machine; it is unpacked into the cache when something reads it. Nothing here deletes a document: a document leaves the store only when no reference and no standing undo names it, which is the sweep's to judge.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import os
import tarfile
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from loom.paths import LIBRARY_DOCUMENTS, LIBRARY_SOURCES

#: The two kinds a reference holds, each with the suffix its file takes.
SUFFIX = {"pdf": ".pdf", "tex": ".tar"}
#: How much of a file is read at a time while hashing.
CHUNK = 1 << 20
#: Main files by the names authors give them, preferred in this order among the files that declare a class.
MAIN_NAMES = ("main.tex", "ms.tex", "paper.tex", "article.tex")


class NotASource(ValueError):
    """Bytes or a folder that hold no file of a TeX source."""


def hex_of(digest: str) -> str:
    """The 64 hexadecimal digits of `sha256:…`, as a file and an address name a document."""
    return digest.removeprefix("sha256:")


def path_of(root: Path, digest: str, kind: str) -> Path:
    """Where the store keeps the document `digest` of `kind` (`pdf` or `tex`), whether or not it is there."""
    return root / LIBRARY_DOCUMENTS / f"{hex_of(digest)}{SUFFIX[kind]}"


def held(root: Path, digest: str, kind: str) -> bool:
    """Whether the store holds the document `digest` of `kind`."""
    return path_of(root, digest, kind).is_file()


def hash_file(path: Path) -> str:
    """`sha256:` and the hexadecimal SHA-256 of a file's bytes, read a piece at a time."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def put_pdf(root: Path, src: Path, *, link: bool = False) -> str:
    """Keep a PDF in the store and say its hash.

    Parameters
    ----------
    root : Path
        The quilt.
    src : Path
        The PDF; it is never moved or changed.
    link : bool, default False
        Link the file in rather than copy it, where the file system allows: only for a file of loom's own, such as a drop's, since a link shares every later change to the file.

    Returns
    -------
    str
        `sha256:` and 64 hexadecimal digits, which a reference's `pdf` names.

    See Also
    --------
    put_source : the same for a TeX source.
    """
    digest = hash_file(src)
    target = path_of(root, digest, "pdf")
    if not target.is_file():
        _place(target, src=src, link=link)
    return digest


def put_source(root: Path, src: Path | bytes) -> str:
    """Keep a TeX source in the store, in its one form, and say its hash.

    Parameters
    ----------
    root : Path
        The quilt.
    src : Path or bytes
        A folder of the source's files, an archive (`.tar`, `.tar.gz`, `.tgz`, `.zip`, a gzipped single file as arXiv serves one), or one `.tex` file; or an archive's bytes.

    Returns
    -------
    str
        The hash of the source's tar, which a reference's `tex` names.

    Raises
    ------
    NotASource
        When nothing in it is a file.
    """
    data = source_tar(src)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    target = path_of(root, digest, "tex")
    if not target.is_file():
        _place(target, data=data)
    return digest


def source_tar(src: Path | bytes) -> bytes:
    """A source's one form: the tar of its files, names sorted, every owner, mode and time fixed."""
    if isinstance(src, Path) and src.is_dir():
        files = folder_files(src)
    else:
        data = src if isinstance(src, bytes) else src.read_bytes()
        name = "" if isinstance(src, bytes) else src.name
        files = unpack(data, name)
    if not files:
        raise NotASource("it holds no file")
    return tar_of(files)


def folder_files(folder: Path) -> dict[str, bytes]:
    """Every regular file under `folder`, by its path inside it; links and hidden files are left out."""
    out: dict[str, bytes] = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in rel.parts):
            continue
        out[rel.as_posix()] = path.read_bytes()
    return out


def unpack(data: bytes, name: str = "") -> dict[str, bytes]:
    """The files an archive's bytes hold, by safe relative path: a tar (gzipped or not), a zip, a gzipped single file, or one TeX file itself.

    A member whose path is absolute or climbs out with `..`, and every link and device, is left out.
    """
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return {
                safe: zf.read(info) for info in zf.infolist() if not info.is_dir() and (safe := _safe(info.filename))
            }
    raw = data
    if data[:2] == b"\x1f\x8b":
        raw = gzip.decompress(data)
    with contextlib.suppress(tarfile.TarError):
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            out: dict[str, bytes] = {}
            for member in tar.getmembers():
                safe = _safe(member.name)
                if safe and member.isfile() and (f := tar.extractfile(member)) is not None:
                    out[safe] = f.read()
            if out:
                return out
    if raw[:4] == b"%PDF" or not raw.strip():
        return {}
    stem = PurePosixPath(name).name.removesuffix(".gz") or "main.tex"
    return {stem if stem.endswith(".tex") else "main.tex": raw}


def _safe(name: str) -> str:
    """`name` as a path inside the archive, or '' when it is absolute, climbs out, or is hidden."""
    parts = [p for p in PurePosixPath(name.replace("\\", "/")).parts if p not in ("", ".")]
    if not parts or name.startswith("/") or ".." in parts or any(p.startswith(".") for p in parts):
        return ""
    return "/".join(parts)


def tar_of(files: Mapping[str, bytes]) -> bytes:
    """The tar of `files`, the same bytes for the same files on any machine: names sorted, mode 0644, owner 0, time 0."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(files[name])
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(files[name]))
    return buffer.getvalue()


def source_dir(root: Path, digest: str) -> Path:
    """The stored source `digest` unpacked under `.loom/cache/library/sources/<hex>/`, unpacked the first time it is asked for.

    Raises
    ------
    FileNotFoundError
        When the store does not hold it.
    """
    out = root / LIBRARY_SOURCES / hex_of(digest)
    if out.is_dir():
        return out
    files = unpack(path_of(root, digest, "tex").read_bytes())
    partial = out.with_name(f".{out.name}.{os.getpid()}")
    for name, data in files.items():
        target = partial / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    partial.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(partial, out)
    except OSError:
        if not out.is_dir():
            raise
    return out


def main_file(folder: Path) -> Path | None:
    """The file of a source that declares its class: by a conventional name first, then the shallowest, then by name; None when none does."""
    found: list[Path] = []
    for path in sorted(folder.rglob("*.tex")):
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:100_000]
        except OSError:
            continue
        if "\\documentclass" in head or "\\documentstyle" in head:
            found.append(path)
    if not found:
        return None
    found.sort(key=lambda p: (p.name.lower() not in MAIN_NAMES, len(p.relative_to(folder).parts), p.name.lower()))
    return found[0]


def _place(target: Path, *, src: Path | None = None, data: bytes | None = None, link: bool = False) -> None:
    """Put a document at `target` whole: from `src`, linked when `link` and the file system allow, else copied to a temporary name beside it; or `data`; then renamed into place."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        if src is not None:
            try:
                if not link:
                    raise OSError("copy")
                os.link(src, temporary)
            except OSError:
                with src.open("rb") as fin, temporary.open("wb") as fout:
                    while chunk := fin.read(CHUNK):
                        fout.write(chunk)
        else:
            temporary.write_bytes(data or b"")
        os.replace(temporary, target)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
