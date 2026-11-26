"""Loom's own writes, never through a link: what `Path` writes, made, appended, renamed and removed through folders opened one part at a time from an anchor without following a link, so a link planted in `.loom/`, the history or the machine's own place carries none of them elsewhere.

The anchor is `root` where the path lies under it, else the folder holding the path's first `.loom` part, else the nearest folder above it holding a `.loom/` folder (a history kept outside `.loom/`), else the nearest folder above it that is there; it is resolved, so a link above it (the person's arrangement of their disk) is followed, and nothing below it is. A part that is a link, to a folder or to a file, a dangling one among them, raises `Planted` and nothing is written or removed; a link removed by `unlink` goes itself, its target untouched. `docs/design/writes.md` ("Loom's own places") says what this covers.
"""

from __future__ import annotations

import contextlib
import errno
import os
import shutil
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from loom.paths import LOOM

#: How each folder on the way is opened: as a folder, never through a link.
_FOLDER = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
#: `open`'s modes that write, as `os.open` flags; `b` and `t` are taken off first.
_MODES = {
    "w": os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
    "a": os.O_WRONLY | os.O_CREAT | os.O_APPEND,
    "x": os.O_WRONLY | os.O_CREAT | os.O_EXCL,
    "r+": os.O_RDWR,
    "w+": os.O_RDWR | os.O_CREAT | os.O_TRUNC,
    "a+": os.O_RDWR | os.O_CREAT | os.O_APPEND,
}


class Planted(OSError):
    """A link where loom writes its own files: nothing was written or removed through it."""

    def __init__(self, where: str) -> None:
        super().__init__(errno.ELOOP, f"{where} is a link, and loom writes nothing of its own through a link")


def _split(path: Path | str, root: Path | str | None) -> tuple[str, tuple[str, ...]]:
    """The resolved anchor of `path` and the parts below it, the file's own name last (`(anchor, ())` for the anchor itself)."""
    p = Path(os.path.abspath(path))
    if root is not None:
        r = Path(os.path.abspath(root))
        if p.is_relative_to(r):
            return os.path.realpath(r), p.relative_to(r).parts
    parts = p.parts
    if LOOM in parts[1:]:
        i = parts.index(LOOM, 1)
        return os.path.realpath(Path(*parts[:i])), parts[i:]
    for i in range(len(parts) - 1, 0, -1):
        # a history kept outside `.loom/` is anchored at the quilt holding it
        with contextlib.suppress(OSError):
            if stat.S_ISDIR(os.lstat(Path(*parts[:i], LOOM)).st_mode):
                return os.path.realpath(Path(*parts[:i])), parts[i:]
    i = len(parts) - 1
    while i > 1 and not os.path.isdir(Path(*parts[:i])):
        i -= 1
    return os.path.realpath(Path(*parts[:i])), parts[i:]


def _refuse(at: int, part: str, where: Path | str) -> None:
    """Raise `Planted` where `part` in the open folder `at` is a link; else nothing, and the caller's own error stands."""
    try:
        st = os.stat(part, dir_fd=at, follow_symlinks=False)
    except OSError:
        return
    if stat.S_ISLNK(st.st_mode):
        raise Planted(str(where))


@contextmanager
def _walk(anchor: str, folders: tuple[str, ...], *, make: bool = False) -> Iterator[int]:
    """The folder `folders` below `anchor`, opened a part at a time without following a link; with `make`, a part not there is made."""
    fd = os.open(anchor, _FOLDER)
    try:
        for i, part in enumerate(folders):
            where = os.path.join(anchor, *folders[: i + 1])
            try:
                nxt = os.open(part, _FOLDER, dir_fd=fd)
            except FileNotFoundError:
                if not make:
                    raise
                with contextlib.suppress(FileExistsError):
                    os.mkdir(part, 0o777, dir_fd=fd)
                try:
                    nxt = os.open(part, _FOLDER, dir_fd=fd)
                except OSError:
                    _refuse(fd, part, where)
                    raise
            except OSError:
                _refuse(fd, part, where)
                raise
            os.close(fd)
            fd = nxt
        yield fd
    finally:
        os.close(fd)


@contextmanager
def parent(path: Path | str, *, root: Path | str | None = None, make: bool = False) -> Iterator[tuple[int, str]]:
    """The open folder holding `path`, reached without following a link, and the file's own name in it.

    Parameters
    ----------
    path : Path or str
        A file in one of loom's own places.
    root : Path or str, optional
        The anchor, where `path` lies under it; default the folder holding `.loom`.
    make : bool, default False
        Make the folders on the way that are not there.

    Yields
    ------
    tuple of (int, str)
        The folder's descriptor, closed after the block, and the name.

    Raises
    ------
    Planted
        Where a folder on the way is a link.
    """
    anchor, parts = _split(path, root)
    if not parts:
        raise IsADirectoryError(errno.EISDIR, "the anchor itself is no file", str(path))
    with _walk(anchor, parts[:-1], make=make) as at:
        yield at, parts[-1]


def mkdir(path: Path | str, *, root: Path | str | None = None, exist_ok: bool = True) -> None:
    """`path.mkdir(parents=True, exist_ok=exist_ok)`, without following a link; `Planted` where a part is one."""
    anchor, parts = _split(path, root)
    if exist_ok or not parts:
        with _walk(anchor, parts, make=True):
            return
    with _walk(anchor, parts[:-1], make=True) as at:
        os.mkdir(parts[-1], 0o777, dir_fd=at)


def open(  # noqa: A001 - `Path.open`'s own name, for a write
    path: Path | str,
    mode: str = "w",
    *,
    root: Path | str | None = None,
    encoding: str | None = None,
    newline: str | None = None,
    perm: int = 0o666,
    make: bool = False,
) -> IO[Any]:
    """`path.open(mode)` for a write, never through a link: the folder on the way nor the file itself.

    Parameters
    ----------
    path : Path or str
        The file.
    mode : str, default 'w'
        One of `w`, `a`, `x`, `r+`, `w+`, `a+`, with `b` for bytes.
    root : Path or str, optional
        The anchor (`parent`).
    encoding, newline : str, optional
        As `open` takes them, for text.
    perm : int, default 0o666
        The permissions of a file made, before the umask.
    make : bool, default False
        Make the folders on the way.

    Returns
    -------
    file object
        Open on the file; the folder's descriptor is closed already.

    Raises
    ------
    Planted
        Where the file or a folder on the way is a link.
    """
    flags = _MODES[mode.replace("b", "").replace("t", "")] | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    with parent(path, root=root, make=make) as (at, name):
        try:
            fd = os.open(name, flags, perm, dir_fd=at)
        except OSError:
            _refuse(at, name, path)
            raise
    try:
        return os.fdopen(fd, mode, encoding=None if "b" in mode else encoding, newline=newline)
    except BaseException:
        os.close(fd)
        raise


def os_open(
    path: Path | str, flags: int, perm: int = 0o777, *, root: Path | str | None = None, make: bool = False
) -> int:
    """`os.open(path, flags, perm)` with `O_NOFOLLOW`, through folders opened without following a link; the descriptor, the caller's to close."""
    with parent(path, root=root, make=make) as (at, name):
        try:
            return os.open(name, flags | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0), perm, dir_fd=at)
        except OSError:
            _refuse(at, name, path)
            raise


def write_bytes(path: Path | str, data: bytes, *, root: Path | str | None = None, make: bool = False) -> None:
    """`path.write_bytes(data)`, never through a link."""
    with open(path, "wb", root=root, make=make) as fh:
        fh.write(data)


def write_text(
    path: Path | str,
    text: str,
    encoding: str | None = "utf-8",
    *,
    root: Path | str | None = None,
    newline: str | None = None,
    make: bool = False,
) -> None:
    """`path.write_text(text, encoding)`, never through a link."""
    with open(path, "w", root=root, encoding=encoding, newline=newline, make=make) as fh:
        fh.write(text)


def replace(src: Path | str, dst: Path | str, *, root: Path | str | None = None) -> None:
    """`os.replace(src, dst)`, each name in its folder opened without following a link; a link at `src` is moved as a link, and one at `dst` replaced, its target untouched."""
    with parent(src, root=root) as (a, s), parent(dst, root=root) as (b, d):
        os.replace(s, d, src_dir_fd=a, dst_dir_fd=b)


def link(src: Path | str, dst: Path | str, *, root: Path | str | None = None) -> None:
    """`os.link(src, dst)`, each name in its folder opened without following a link, and a link at `src` linked as itself."""
    with parent(src, root=root) as (a, s), parent(dst, root=root) as (b, d):
        os.link(s, d, src_dir_fd=a, dst_dir_fd=b, follow_symlinks=False)


def unlink(path: Path | str, *, root: Path | str | None = None, missing_ok: bool = False) -> None:
    """`path.unlink(missing_ok)` through folders opened without following a link: a link at `path` goes itself, never its target."""
    try:
        with parent(path, root=root) as (at, name):
            os.unlink(name, dir_fd=at)
    except FileNotFoundError:
        if not missing_ok:
            raise


def rmdir(path: Path | str, *, root: Path | str | None = None) -> None:
    """`path.rmdir()` through folders opened without following a link."""
    with parent(path, root=root) as (at, name):
        os.rmdir(name, dir_fd=at)


def rmtree(path: Path | str, *, root: Path | str | None = None, ignore_errors: bool = False) -> None:
    """`shutil.rmtree(path)` through folders opened without following a link, and nothing below them followed (`shutil.rmtree`'s own `dir_fd` walk); a link at `path` is refused, as `shutil.rmtree` refuses one, and nothing through it removed."""
    try:
        with parent(path, root=root) as (at, name):
            _refuse(at, name, path)
            shutil.rmtree(name, dir_fd=at, ignore_errors=ignore_errors)
    except OSError:
        if not ignore_errors:
            raise


def copyfile(src: Path | str, dst: Path | str, *, root: Path | str | None = None, make: bool = False) -> None:
    """`shutil.copyfile(src, dst)` with `dst` written never through a link; `src` is read as it is."""
    with Path(src).open("rb") as fin, open(dst, "wb", root=root, make=make) as fout:
        shutil.copyfileobj(fin, fout)
