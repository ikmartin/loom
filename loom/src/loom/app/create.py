"""A new quilt from what the person drops on the home page: the files kept where they wait, an archive opened, the paper's main file found, the quilt made and the paper brought in through the door's one `import` act, then served.

Dropped files wait in `app/incoming/<drop>/files/` in loom's folder for the machine: outside every quilt and never under a cache, so nothing loom sweeps can take them before they are used. A drop goes once its quilt is made, or `KEEP_DAYS` after it was last added to.

A quilt comes into being whole or not at all: it is made in a hidden folder beside its place (`.loom-making-<key>/<name>`) and moved into its place by one rename at the end. A record in `app/making/` names that folder while the create runs, so the home's next start clears whatever a create cut short left (`recover`).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import secrets
import shutil
import tarfile
import threading
import time
import zipfile
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from loom.app import registry
from loom.app.registry import Entry, folder
from loom.render.endpoints.base import ApiError

#: The most one drop may hold, received or unpacked.
MAX_DROP = 1 << 30
#: The most files one drop may hold, received or unpacked.
MAX_FILES = 10_000
#: Days a drop no quilt was made from is kept after it was last added to.
KEEP_DAYS = 14
#: Where a new quilt goes unless the person chooses another place: outside the folders macOS asks before a program reads.
PLACE = "Quilts"
_DROP = re.compile(r"[0-9a-f]{16}")
#: The hidden folder beside a new quilt's place that it is made in, before it is moved into its place.
_NEST = re.compile(r"\.loom-making-[0-9a-f]{16}")
_COMMENT = re.compile(r"(?<!\\)%.*")


class _Reads(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


def incoming() -> Path:
    """The folder each drop waits in, one folder a drop."""
    return folder() / "incoming"


def making() -> Path:
    """The records of the quilts being made, one a create, which the home's next start reads to clear what a create cut short left."""
    return folder() / "making"


class Makings:
    """The quilts a home is making: one create at a time a folder, and none moved into its place once the home is stopping."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        #: Each folder a create runs for, resolved, with the hidden folder it is being made in once there is one.
        self.running: dict[Path, Path | None] = {}
        self.closed = False

    def claim(self, where: Path) -> None:
        """Hold `where` for one create; ApiError `exists` while another create is making a quilt there."""
        with self.lock:
            if self.closed:
                raise ApiError("stopping", "loom's home is stopping", status=503)
            if where.resolve() in self.running:
                raise ApiError("exists", "a quilt of that name is being made there already", status=409)
            self.running[where.resolve()] = None

    def release(self, where: Path) -> None:
        """Let go of `where` once its create has ended, whichever way."""
        with self.lock:
            self.running.pop(where.resolve(), None)

    def close(self) -> None:
        """End every create running, as the home stops: what each has made so far is removed and none is moved into its place after; the records stay, so the next start clears anything made after this."""
        with self.lock:
            self.closed = True
            for nest in self.running.values():
                if nest is not None:
                    shutil.rmtree(nest, ignore_errors=True)


def _drop_dir(drop: str) -> Path:
    if not _DROP.fullmatch(drop) or not (incoming() / drop).is_dir():
        raise ApiError("no-such-drop", "nothing was dropped under that name", status=404)
    return incoming() / drop


def _safe(rel: str) -> PurePosixPath:
    """`rel` as a path inside a drop, or ApiError: no absolute path, no `..`, nothing empty."""
    path = PurePosixPath(rel)
    if not rel or "\x00" in rel or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ApiError("bad-path", "a dropped file's path must stay inside what was dropped")
    return path


def _held(d: Path) -> tuple[int, int]:
    files = [p for p in d.rglob("*") if p.is_file()]
    return sum(p.stat().st_size for p in files), len(files)


def receive(drop: str | None, rel: str, stream: _Reads, length: int) -> dict[str, Any]:
    """Keep one dropped file, streamed, in a drop: a new one when `drop` is None.

    Parameters
    ----------
    drop : str or None
        The drop the file belongs to, as an earlier answer named it; None begins one.
    rel : str
        The file's path within what was dropped: its name, or for a folder its path under the folder.
    stream : binary file
        Where its bytes are read from.
    length : int
        How many bytes to read.

    Returns
    -------
    dict
        `{drop, path, size}`.
    """
    path = _safe(rel)
    if drop is None:
        drop = secrets.token_hex(8)
        (incoming() / drop / "files").mkdir(parents=True)
    files = _drop_dir(drop) / "files"
    size, count = _held(files)
    if size + length > MAX_DROP or count >= MAX_FILES:
        raise ApiError("too-large", "a drop holds at most 1 GB in 10,000 files", status=413)
    target = files / path
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except (FileExistsError, NotADirectoryError) as exc:
        raise ApiError("bad-path", "a dropped file's folder is a file already") from exc
    tmp = files / f".{secrets.token_hex(4)}.part"
    left = length
    with open(tmp, "wb") as out:
        while left > 0:
            chunk = stream.read(min(left, 1 << 20))
            if not chunk:
                break
            out.write(chunk)
            left -= len(chunk)
    if left:
        tmp.unlink()
        raise ApiError("cut-short", "the file ended before its length")
    try:
        tmp.replace(target)
    except OSError as exc:
        tmp.unlink()
        raise ApiError("bad-path", "a dropped file's path is a folder already") from exc
    return {"drop": drop, "path": path.as_posix(), "size": length}


def _archive(p: Path) -> str | None:
    """`zip`, `tar` or `gzip` by what the file holds rather than its name; None for anything else."""
    if zipfile.is_zipfile(p):
        return "zip"
    if tarfile.is_tarfile(p):
        return "tar"
    with open(p, "rb") as f:
        return "gzip" if f.read(2) == b"\x1f\x8b" else None


def _copy(data: _Reads, to: Path) -> None:
    """Copy `data` to the file `to`, refusing past `MAX_DROP`, which a small archive can unpack to."""
    total = 0
    with open(to, "wb") as copy:
        while chunk := data.read(1 << 20):
            total += len(chunk)
            if total > MAX_DROP:
                raise ValueError("larger than a drop may be")
            copy.write(chunk)


def _unpack(src: Path, kind: str, out: Path) -> None:
    """Open the archive `src` into `out`: never outside it, never through a link, and within `MAX_DROP` and `MAX_FILES`; nothing is left of a refused one."""
    out.mkdir(parents=True)
    try:
        if kind == "zip":
            with zipfile.ZipFile(src) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_DROP:
                    raise ValueError("too large")
                for info in infos:
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError("a link")
                    to = out / _safe(info.filename)
                    to.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as data:
                        _copy(data, to)
        elif kind == "tar":
            with tarfile.open(src) as t:
                members = t.getmembers()
                if len(members) > MAX_FILES or sum(m.size for m in members) > MAX_DROP:
                    raise ValueError("too large")
                t.extractall(out, filter="data")
        else:
            # one file gzipped, as arXiv serves a paper of a single file
            name = src.name.removesuffix(".gz") or "paper"
            with gzip.open(src) as data:
                _copy(data, out / (name if name.endswith(".tex") else f"{name}.tex"))
    except (OSError, EOFError, tarfile.TarError, zipfile.BadZipFile, ValueError, ApiError) as exc:
        shutil.rmtree(out, ignore_errors=True)
        raise ApiError("bad-archive", "loom cannot open that archive safely") from exc


def sources(drop: str) -> Path:
    """The folder the dropped paper's sources are in: the files as dropped, or the one archive dropped, opened (once)."""
    d = _drop_dir(drop)
    files = [p for p in (d / "files").rglob("*") if p.is_file()]
    kind = _archive(files[0]) if len(files) == 1 else None
    if kind is None:
        return d / "files"
    out = d / "unpacked"
    if not out.is_dir():
        _unpack(files[0], kind, out)
    return out


def mains(src: Path) -> list[str]:
    """The files under `src` that a paper is typeset from: the top-level file an arXiv source's `00README.json` names, else each `.tex` that has a `\\documentclass` and a `\\begin{document}` outside comments."""
    try:
        said = json.loads((src / "00README.json").read_text(encoding="utf-8"))
        top = [s["filename"] for s in said.get("sources", []) if s.get("usage") == "toplevel"]
        if len(top) == 1 and (src / _safe(top[0])).is_file():
            return top
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ApiError):
        pass
    found = []
    for p in sorted(src.rglob("*.tex")):
        rel = p.relative_to(src)
        if any(part.startswith(".") or part == "__MACOSX" for part in rel.parts) or not p.is_file():
            continue
        try:
            text = _COMMENT.sub("", p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if "\\documentclass" in text and "\\begin{document}" in text:
            found.append(rel.as_posix())
    return found


def target(name: str, place: str | None) -> Path:
    """The folder a new quilt named `name` is made in: under `place`, else `~/Quilts`; ApiError where it cannot go."""
    from loom.scan.quilt import is_quilt_root

    folder_name = re.sub(r"[/:\x00-\x1f]", "-", name.strip()).lstrip(".").strip()
    if not folder_name:
        raise ApiError("bad-field", "the quilt needs a name")
    base = Path(place).expanduser() if place else Path.home() / PLACE
    if not base.is_absolute():
        raise ApiError("bad-field", "place is a folder's whole path")
    there = base / folder_name
    if there.exists() and (not there.is_dir() or any(there.iterdir())):
        raise ApiError("exists", "a folder of that name is there already", status=409)
    if any(is_quilt_root(p) for p in there.parents):
        raise ApiError("inside-a-quilt", "that place is inside a quilt", status=409)
    return there


def reading(drop: str) -> list[Path]:
    """The PDFs dropped to be read, when the drop holds PDFs and nothing else, by what each file holds; [] for any other drop."""
    files = sorted(p for p in (_drop_dir(drop) / "files").rglob("*") if p.is_file())
    pdfs = []
    for p in files:
        with open(p, "rb") as f:
            if f.read(5) != b"%PDF-":
                return []
        pdfs.append(p)
    return pdfs


def paper(drop: str, main: str | None) -> Path | list[str]:
    """The dropped paper's main file, or the files that could be when it is not one and `main` does not say which."""
    src = sources(drop)
    found = mains(src)
    if main is not None:
        if main not in found:
            raise ApiError("bad-field", "main is not one of the files a paper is typeset from")
        return src / main
    if not found:
        raise ApiError("no-paper", "what was dropped holds no .tex file that begins a document", status=409)
    return src / found[0] if len(found) == 1 else found


def make(
    where: Path,
    main: Path | None,
    step: Callable[[str], None],
    start: Callable[[Entry], dict[str, Any]],
    makings: Makings | None = None,
    read: Sequence[Path] = (),
) -> dict[str, Any]:
    """Make the quilt at `where`, bring in the paper at `main` when there is one, or take the PDFs `read` into its library, put it on the list as open and serve it.

    The quilt is made beside `where` and moved there in one rename once it is whole; whatever stops the create first leaves nothing in `where`.

    Parameters
    ----------
    where : Path
        The new quilt's folder, which `target` chose.
    main : Path or None
        The paper's main file; None makes an empty quilt.
    step : callable
        Told each step as it begins: `making`, `importing`, `starting`.
    start : callable
        Serves the quilt's entry and answers its state.
    makings : Makings, optional
        The home's creates, which hold the move back once the home is stopping; default one of its own.
    read : sequence of Path, default ()
        PDFs to read: each taken into the new quilt's library as the library's intake takes a dropped file, by the person, with no look-up on the network; a document it cannot place waits there as the library's question.

    Returns
    -------
    dict
        `{quilt, folder, tex, state, url?}`, with PDFs `{read}` (how many), and with a paper `{document, typeset, untypeset, differs}`: `differs` when the drafted document does not typeset as the paper did, which is then brought in all the same and nothing reads as checked.
    """
    from loom.cli.paper import Differs, run_import
    from loom.cli.quilt import write_minimal_quilt
    from loom.config_edit import set_values
    from loom.errors import ContentError, EnvError
    from loom.looks import first
    from loom.scan.quilt import load_quilt
    from loom.tex import private

    makings = makings if makings is not None else Makings()
    key = secrets.token_hex(8)
    nest = where.parent / f".loom-making-{key}"
    staged = nest / where.name
    record = making() / f"{key}.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"nest": str(nest), "where": str(where)}) + "\n", encoding="utf-8")
    done: dict[str, Any] = {"folder": str(where)}
    try:
        with makings.lock:
            if makings.closed:
                raise ApiError("stopping", "loom's home is stopping", status=503)
            makings.running[where.resolve()] = nest
        step("making")
        nest.mkdir(parents=True)
        write_minimal_quilt(staged, "q", readme=False)
        if main is not None:
            step("importing")
            try:
                try:
                    brought = run_import(load_quilt(staged), main, True, fix_anchors=True)
                    done["differs"] = False
                except Differs:
                    brought = run_import(load_quilt(staged), main, True, check=False, fix_anchors=True)
                    done["differs"] = True
            except (ContentError, EnvError, OSError) as exc:
                said = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
                raise ApiError("cannot-import", said, 409) from exc
            document = brought.data["document"]
            # the quilt opens on the paper, not on a page about loom
            set_values(load_quilt(staged), {"quilt.home": document})
            done.update(document=document, typeset=brought.data["typeset"], untypeset=brought.data["untypeset"])
        elif read:
            from loom.identity import whoever
            from loom.library.intake import Item, take

            step("importing")
            take(staged, [Item(path=p) for p in read], by=whoever(staged, sniff=False), online=False)
            done["read"] = len(read)
        first(load_quilt(staged))
        with makings.lock:
            if makings.closed:
                raise ApiError("stopping", "loom's home is stopping", status=503)
            try:
                os.rename(staged, where)  # the one step: the quilt is whole in its place, or not there
            except OSError as exc:
                raise ApiError("exists", "a folder of that name is there already", status=409) from exc
            makings.running[where.resolve()] = None  # in its place: nothing of it is the stop's to remove
    except BaseException:
        shutil.rmtree(nest, ignore_errors=True)
        if not nest.exists():
            record.unlink(missing_ok=True)
        raise
    # the quilt is in its place: were the home stopped now, its next start would put it on the list (`recover`)
    entry = registry.remember(where)
    registry.set_open(entry.id, True)
    entry.open = True
    nest.rmdir()
    record.unlink()
    step("starting")
    return {**done, "quilt": entry.id, "tex": private.active(year=False).kind, **start(entry)}


def recover() -> None:
    """Clear what each create cut short left, as the home starts: the hidden folder it was making the quilt in is removed, and a quilt it had moved into its place already is put on the list as open."""
    from loom.scan.quilt import is_quilt_root

    try:
        records = sorted(making().glob("*.json"))
    except OSError:
        return
    for record in records:
        try:
            said = json.loads(record.read_text(encoding="utf-8"))
            nest, where = Path(said["nest"]), Path(said["where"])
        except (OSError, ValueError, KeyError, TypeError):
            record.unlink(missing_ok=True)
            continue
        if not _NEST.fullmatch(nest.name):
            record.unlink(missing_ok=True)  # a record names nothing but a create's own folder
            continue
        try:
            if not (nest / where.name).exists() and is_quilt_root(where):
                registry.set_open(registry.remember(where).id, True)
        except registry.Unreadable:
            continue  # kept for a start that can read the list
        shutil.rmtree(nest, ignore_errors=True)
        if not nest.exists():
            record.unlink(missing_ok=True)


def sweep() -> None:
    """Remove every drop last added to more than `KEEP_DAYS` ago. Nothing a drop holds can stop it: each file's own time is read, never through a link, and a drop that cannot be read is old."""
    cutoff = time.time() - KEEP_DAYS * 86400
    try:
        drops = list(incoming().iterdir())
    except OSError:
        return
    for d in drops:
        try:
            newest = max((p.lstat().st_mtime for p in d.rglob("*")), default=d.lstat().st_mtime)
        except OSError:
            newest = 0.0
        if newest < cutoff:
            shutil.rmtree(d, ignore_errors=True)


def let_go(drop: str) -> None:
    """Remove a drop whose quilt is made."""
    shutil.rmtree(_drop_dir(drop), ignore_errors=True)
