"""The library's stored documents, by hash: `.loom/library/documents/<hex>.pdf`, and a work's TeX source as one file, `<hex>.tar`.

A reference names its documents by these hashes (`pdf`, `tex`; `docs/specs/nodes.md` §2), so one document is stored once whatever works hold it, and nothing about a work is read from where its documents sit. A source is kept in one form, an uncompressed tar of its files with names sorted and owners, modes and times fixed, so a folder, a `.tar.gz` and a `.zip` of the same files hash alike on any machine; it is made as the archive streams, a file at a time and within `MAX_EXPANDED` and `MAX_FILES`, refused in a sentence when the archive is damaged or holds what no disk keeps (`pack`), and unpacked into the cache when something reads it. Nothing here deletes a document: a document leaves the store only when no reference and no standing undo names it, which is the sweep's to judge.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import os
import secrets
import shutil
import tarfile
import tempfile
import unicodedata
import zipfile
import zlib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from loom.paths import LIBRARY_DOCUMENTS, LIBRARY_SOURCES

#: The two kinds a reference holds, each with the suffix its file takes.
SUFFIX = {"pdf": ".pdf", "tex": ".tar"}
#: How much of a file is read at a time while hashing.
CHUNK = 1 << 20
#: Main files by the names authors give them, preferred in this order among the files that declare a class.
MAIN_NAMES = ("main.tex", "ms.tex", "paper.tex", "article.tex")
#: The most a source may hold once unpacked. An arXiv source is tens of megabytes at most (arXiv refuses a submission over 50 MB packed), so this is several times any paper's, and an archive that unpacks past it is a bomb, refused before it fills the disk.
MAX_EXPANDED = 256 << 20
#: The most files a source may hold: a paper's source has tens, hundreds with its figures; tens of thousands of tiny files are no paper's, and each costs a file in the cache.
MAX_FILES = 10_000
#: The longest name a file of a source may have, in UTF-8 bytes: a part of its path as every disk loom runs on holds one (NAME_MAX), and the whole path, which stands under the quilt's cache on disks whose paths stop at 1,024 bytes.
MAX_PART, MAX_NAME = 255, 512


class _Reads(Protocol):
    """What a member's bytes are read from: a file of an archive, a gzip stream."""

    def read(self, size: int = -1, /) -> bytes: ...


class NotASource(ValueError):
    """Bytes or a folder that hold no TeX source the store keeps; its message is the one sentence a person reads."""


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


def put_source(root: Path, src: Path | bytes, *, name: str = "") -> str:
    """Keep a TeX source in the store, in its one form, and say its hash.

    Parameters
    ----------
    root : Path
        The quilt.
    src : Path or bytes
        A folder of the source's files, an archive (`.tar`, `.tar.gz`, `.tgz`, `.zip`, a gzipped single file as arXiv serves one), or one `.tex` file; or an archive's bytes.
    name : str, default ''
        The name it came under, which a refusal names it by.

    Returns
    -------
    str
        The hash of the source's tar, which a reference's `tex` names.

    Raises
    ------
    NotASource
        As `pack` refuses; nothing is stored.

    See Also
    --------
    pack : the same written to a file of the caller's, which `keep_packed` then stores.
    """
    store = root / LIBRARY_DOCUMENTS
    store.mkdir(parents=True, exist_ok=True)
    temporary = store / f".packing.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    try:
        with temporary.open("wb") as out:
            digest = pack(src, out, name=name, work=store)
        keep_packed(root, temporary, digest)
    finally:
        temporary.unlink(missing_ok=True)
    return digest


def keep_packed(root: Path, packed: Path, digest: str) -> None:
    """Store a source `pack` wrote to `packed` under its hash `digest`, by renaming it into place; a source the store holds already is kept as it is, and `packed` is left to its caller."""
    target = path_of(root, digest, "tex")
    if target.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        os.link(packed, temporary)
    except OSError:
        shutil.copyfile(packed, temporary)
    os.replace(temporary, target)


def source_tar(src: Path | bytes, *, name: str = "") -> bytes:
    """A source's one form, the tar `pack` writes, as bytes; for a source known to be small, a folder of loom's own, since the whole tar is held."""
    out = io.BytesIO()
    pack(src, out, name=name)
    return out.getvalue()


class _Hashing:
    """A file being written, hashed as it is."""

    def __init__(self, out: BinaryIO) -> None:
        self.out = out
        self.hash = hashlib.sha256()
        self.written = 0

    def write(self, data: bytes) -> int:
        self.hash.update(data)
        self.written += len(data)
        self.out.write(data)
        return len(data)

    def tell(self) -> int:
        return self.written


def pack(src: Path | bytes, out: BinaryIO, *, name: str = "", work: Path | None = None) -> str:
    """Write a source's one form to `out` as its files stream out of it, and say its hash: the tar of its files, names sorted, every owner, mode and time fixed, so a folder, a `.tar.gz` and a `.zip` of the same files hash alike on any machine.

    Every limit is checked while the bytes stream, so neither memory nor the disk holds more than `MAX_EXPANDED` of an archive at any moment: an archive's files are spooled one at a time into a folder under `work`, then written in order. A member that climbs out, is absolute or hidden, and every link and device, is left out.

    Parameters
    ----------
    src : Path or bytes
        As `put_source` takes it.
    out : binary file
        Where the tar is written.
    name : str, default ''
        The name the source came under, which a refusal names it by.
    work : Path, optional
        A folder for the spool, removed after; default the system's.

    Returns
    -------
    str
        `sha256:` and the tar's hash.

    Raises
    ------
    NotASource
        With a sentence a person acts on, naming the source by `name`: damaged or not a TeX source (a truncated or corrupt archive, a `.gz` that is not gzip, one holding a PDF), protected by a password, expanding past `MAX_EXPANDED` or holding more than `MAX_FILES` files, holding a file and a folder of one name or two names a disk blind to case holds as one, a name no disk holds, or no `.tex` file at all.
    """
    shown = PurePosixPath(name).name or "the source"
    spool = Path(tempfile.mkdtemp(prefix=".spool.", dir=work))
    try:
        files = _spooled(src, shown, spool)
        hashing = _Hashing(out)
        with tarfile.open(fileobj=hashing, mode="w", format=tarfile.PAX_FORMAT) as tar:  # type: ignore[call-overload]
            for member in sorted(files):
                path = files[member]
                info = _info(member, path.stat().st_size)
                with path.open("rb") as fh:
                    tar.addfile(info, fh)
    finally:
        shutil.rmtree(spool, ignore_errors=True)
    return "sha256:" + hashing.hash.hexdigest()


def _info(member: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(member)
    info.size = size
    info.mode = 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


class _Damaged(Exception):
    """An archive's bytes that cannot be read as what they claim to be."""


#: What reading a damaged archive raises, by the module that reads it.
_UNREADABLE = (tarfile.TarError, EOFError, zlib.error, zipfile.BadZipFile, gzip.BadGzipFile, NotImplementedError)


def _spooled(src: Path | bytes, shown: str, spool: Path) -> dict[str, Path]:
    """Each file a source holds, by its path inside it, at a file of its own: a folder's in place, an archive's copied into `spool` as it streams; the limits and the names checked."""
    budget = _Budget(shown)
    if isinstance(src, Path) and src.is_dir():
        found = {}
        for rel, path in folder_paths(src).items():
            budget.file(path.stat().st_size)
            found[rel] = path
        return _checked(found, shown)
    files: dict[str, Path] = {}
    raw: BinaryIO = io.BytesIO(src) if isinstance(src, bytes) else src.open("rb")
    try:
        head = raw.read(512)
        raw.seek(0)
        try:
            if head[:4] == b"PK\x03\x04":
                _from_zip(raw, shown, spool, files, budget)
            elif head[:2] == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=raw) as gz:
                    inner = gz.read(512)
                raw.seek(0)
                if _is_tar(inner):
                    # gzip's own reader, which never decompresses more than it is asked for, so a bomb is read a piece at a time
                    with gzip.GzipFile(fileobj=raw) as gz, tarfile.open(fileobj=gz, mode="r|") as tar:
                        _from_tar(tar, spool, files, budget)
                else:
                    with gzip.GzipFile(fileobj=raw) as gz:
                        _single(gz, _single_name(src, ".gz"), spool, files, budget)
            elif _is_tar(head):
                with tarfile.open(fileobj=raw, mode="r|") as tar:
                    _from_tar(tar, spool, files, budget)
            else:
                _single(raw, _single_name(src, ""), spool, files, budget)
        except (_Damaged, *_UNREADABLE) as exc:
            raise NotASource(f"{shown} is damaged, or is not a TeX source") from exc
        except RuntimeError as exc:
            # zipfile's word for a member it needs a password to read
            raise NotASource(f"{shown} is protected by a password; drop the source without one") from exc
    finally:
        raw.close()
    return _checked(files, shown)


def _is_tar(head: bytes) -> bool:
    return len(head) >= 262 and head[257:262] == b"ustar"


def _single_name(src: Path | bytes, suffix: str) -> str:
    """The name a source of one file keeps it under: its own file's, a `.tex`, so the same bytes keep one name however they were dropped; else `main.tex`."""
    own = src.name if isinstance(src, Path) else ""
    stem = own.removesuffix(suffix) if suffix else own
    return stem if stem.endswith(".tex") and _safe(stem) else "main.tex"


class _Budget:
    """What a source has spent of `MAX_FILES` and `MAX_EXPANDED`, refused the moment either is passed."""

    def __init__(self, shown: str) -> None:
        self.shown = shown
        self.files = 0
        self.bytes = 0

    def file(self, size: int = 0) -> None:
        self.files += 1
        if self.files > MAX_FILES:
            raise NotASource(f"{self.shown} holds more than {MAX_FILES:,} files, more than any paper's source")
        self.spend(size)

    def spend(self, size: int) -> None:
        self.bytes += size
        if self.bytes > MAX_EXPANDED:
            raise NotASource(f"{self.shown} unpacks to more than {MAX_EXPANDED >> 20} MB, more than any paper's source")


def _copy(reader: _Reads, target: Path, budget: _Budget) -> None:
    """Copy one member's bytes to `target` a piece at a time, spending them from `budget`; a read that fails is a damaged archive."""
    with target.open("wb") as fh:
        while True:
            try:
                chunk = reader.read(CHUNK)
            except (*_UNREADABLE, OSError) as exc:
                raise _Damaged from exc
            if not chunk:
                return
            budget.spend(len(chunk))
            fh.write(chunk)


def _spool_to(spool: Path, files: dict[str, Path], member: str, budget: _Budget) -> Path:
    """The spool's file for the member `budget` has just counted: a name of its own, and a name repeated in an archive replaces the first, as unpacking it would."""
    old = files.get(member)
    if old is not None:
        old.unlink(missing_ok=True)
    return spool / f"{budget.files:06d}"


def _from_tar(tar: tarfile.TarFile, spool: Path, files: dict[str, Path], budget: _Budget) -> None:
    for member in tar:
        safe = _safe(member.name)
        if not safe or not member.isfile():
            continue
        budget.file()
        reader = tar.extractfile(member)
        if reader is None:
            continue
        target = _spool_to(spool, files, safe, budget)
        _copy(reader, target, budget)
        files[safe] = target


def _from_zip(raw: BinaryIO, shown: str, spool: Path, files: dict[str, Path], budget: _Budget) -> None:
    with zipfile.ZipFile(raw) as zf:
        for info in zf.infolist():
            safe = _safe(info.filename)
            if not safe or info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise RuntimeError("encrypted")
            budget.file()
            target = _spool_to(spool, files, safe, budget)
            with zf.open(info) as reader:
                _copy(reader, target, budget)
            files[safe] = target


def _single(reader: _Reads, member: str, spool: Path, files: dict[str, Path], budget: _Budget) -> None:
    """A source of one file: a `.tex`, or a gzipped one as arXiv serves a source of one file; one holding a PDF, or anything not TeX, is none."""
    budget.file()
    target = spool / "000000"
    _copy(reader, target, budget)
    with target.open("rb") as fh:
        head = fh.read(1 << 16)
    if not _texlike(head):
        raise NotASource(f"{budget.shown} holds no TeX source")
    files[member] = target


def _texlike(head: bytes) -> bool:
    """Whether the first bytes of a file read as TeX: text with no NUL, and a command in it."""
    return bool(head.strip()) and b"\0" not in head and b"\\" in head and not head.startswith(b"%PDF")


def _checked(files: dict[str, Path], shown: str) -> dict[str, Path]:
    """`files`, refused when a name is one no disk holds, when a file shares a name with a folder or folds to another's as a disk blind to case or to Unicode's forms folds it, or when no file is a `.tex`."""
    if not files:
        raise NotASource(f"{shown} holds no file of a TeX source")
    seen: dict[str, str] = {}
    folders: dict[str, str] = {}
    for member in files:
        if why := _unholdable(member):
            raise NotASource(f"{shown} holds a file whose name {why}; loom cannot keep it")
        folded = unicodedata.normalize("NFC", member).casefold()
        if (other := seen.get(folded)) is not None:
            raise NotASource(
                f"{shown} holds both {other} and {member}, names a disk keeps as one file, since they differ only in case or in how an accent is written"
            )
        seen[folded] = member
        parts = folded.split("/")
        for i in range(1, len(parts)):
            folders.setdefault("/".join(parts[:i]), "/".join(member.split("/")[:i]))
    for folded, member in seen.items():
        if folded in folders:
            raise NotASource(f"{shown} holds both a file and a folder named {member}")
    if not any(m.lower().endswith((".tex", ".ltx")) for m in files):
        raise NotASource(f"{shown} holds no .tex file, so it is not a TeX source")
    return files


def _unholdable(member: str) -> str:
    """Why no disk loom runs on holds a file of this name under the cache, or ''."""
    if any(unicodedata.category(c) == "Cc" for c in member):
        return "has a control character in it"
    if len(member.encode("utf-8")) > MAX_NAME or any(len(p.encode("utf-8")) > MAX_PART for p in member.split("/")):
        return "is too long"
    return ""


def folder_files(folder: Path) -> dict[str, bytes]:
    """Every regular file under `folder`, by its path inside it, with its bytes; links and hidden files are left out."""
    return {rel: path.read_bytes() for rel, path in folder_paths(folder).items()}


def folder_paths(folder: Path) -> dict[str, Path]:
    """Every regular file under `folder`, by its path inside it; links and hidden files are left out."""
    out: dict[str, Path] = {}
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in rel.parts):
            continue
        out[rel.as_posix()] = path
    return out


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
        for member in sorted(files):
            tar.addfile(_info(member, len(files[member])), io.BytesIO(files[member]))
    return buffer.getvalue()


def source_dir(root: Path, digest: str) -> Path:
    """The stored source `digest` unpacked under `.loom/cache/library/sources/<hex>/`, unpacked the first time it is asked for.

    A member the folder cannot hold beside another, a file named as a folder is, or two names a disk blind to case holds as one, is left out rather than refused, so a source the store holds can always be read again; what `pack` keeps has none.

    Raises
    ------
    FileNotFoundError
        When the store does not hold it.
    """
    out = root / LIBRARY_SOURCES / hex_of(digest)
    if out.is_dir():
        return out
    stored = path_of(root, digest, "tex")
    if not stored.is_file():
        raise FileNotFoundError(f"the store holds no source {digest}")
    partial = out.with_name(f".{out.name}.{os.getpid()}")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    try:
        with tarfile.open(stored, mode="r:") as tar:
            for member in tar:
                safe = _safe(member.name)
                reader = tar.extractfile(member) if safe and member.isfile() else None
                if reader is None:
                    continue
                target = partial / safe
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as fh:
                        shutil.copyfileobj(reader, fh, CHUNK)
                except (FileExistsError, NotADirectoryError, IsADirectoryError):
                    continue
        os.replace(partial, out)
    except OSError:
        if not out.is_dir():
            raise
    finally:
        shutil.rmtree(partial, ignore_errors=True)
    return out


def main_text(packed: Path, limit: int = 1 << 20) -> str:
    """The opening of the main file of a source `pack` wrote, the file declaring its class as `main_file` chooses it; '' when none does."""
    with tarfile.open(packed, mode="r:") as tar:
        mains = []
        for member in tar:
            reader = tar.extractfile(member) if member.isfile() and member.name.endswith(".tex") else None
            if reader is not None and _declares_class(reader.read(100_000)):
                mains.append(member)
        if not mains:
            return ""
        mains.sort(
            key=lambda m: (PurePosixPath(m.name).name.lower() not in MAIN_NAMES, m.name.count("/"), m.name.lower())
        )
        reader = tar.extractfile(mains[0])
        return reader.read(limit).decode("utf-8", errors="replace") if reader is not None else ""


def _declares_class(head: bytes) -> bool:
    return b"\\documentclass" in head or b"\\documentstyle" in head


def main_file(folder: Path) -> Path | None:
    """The file of a source that declares its class: by a conventional name first, then the shallowest, then by name; None when none does."""
    found: list[Path] = []
    for path in sorted(folder.rglob("*.tex")):
        try:
            # the opening alone: a file of the source may be as large as `MAX_EXPANDED`
            with path.open("rb") as fh:
                head = fh.read(100_000)
        except OSError:
            continue
        if _declares_class(head):
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
