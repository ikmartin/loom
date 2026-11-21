"""How long loom keeps each kind of thing under `.loom/`, and the sweep that removes what has outlived its use.

Records are never deleted by loom, and the library only when the person removes a work. What is derived, in `.loom/cache/`, is kept while the build as it stands names it (`built`, the one reader of the build's index) or while the folder's own rule says what it is still for (`_Rules`); the rest goes in the sweep that follows a build that published, and only while the index on disk is the one that build wrote. An agent's scratch goes `KEEP_DAYS` after its session's last write, and a saved preview `KEEP_DAYS` after it was written. Nothing written in the last `FRESH` seconds is removed, whatever names it, since whatever wrote it may not have named it yet: a step whose page a viewer is about to fetch, or a build in another process, unless that build has run for longer.

The sweep removes only in the folders of `SWEPT`, found by `_own` without a link on the way, and never in one that is or holds the history. Each file goes by its name in its folder, opened from that home one step at a time without following a link (`_remove_in`), so a folder swapped for a link while the sweep works is never entered; what changed since the sweep looked is left; a failure to remove one file stops nothing; and a system that cannot remove that way removes nothing (`CAN_REMOVE`).
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import re
import stat
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from loom.paths import (
    ADOPTION_PREVIEWS,
    ANNOTATION_LOG,
    BLOCK_PREVIEWS,
    BLOCK_SPANS,
    BLOCKS,
    BUILD_INDEX,
    CACHE,
    CLOSURES,
    CROPS,
    DRAFT_PREVIEWS,
    INCORPORATION_PREVIEWS,
    KINDS,
    LIBRARY_CACHE,
    LIBRARY_DOCUMENTS,
    LIBRARY_NODES,
    LIBRARY_SOURCES,
    LIBRARY_THUMBS,
    MARK_BOXES,
    MARKS,
    NODE_INDEX,
    REFOUND,
    RESOLVED,
    SCRATCH,
    SESSIONS,
    SITE,
    SITE_SVG,
    SNIPPETS,
    STORAGE,
    STORE_BOXES,
    TEX,
    document_build,
    within,
)

DAY = 86400.0
#: Days an agent's scratch outlives its session's last write, and a file in `scratch/none/` or a saved preview its own writing.
KEEP_DAYS = 14
#: Seconds a page made when asked for (a comparison's sides, a draft's preview in its paper) outlives the last time its step named it.
ON_REQUEST = KEEP_DAYS * DAY
#: Seconds within which a file just written is never removed.
FRESH = 3600.0
#: The size of one session's scratch above which `loom doctor` reports it.
LARGE_SCRATCH = 500 * 1000**2
#: The scratch folder of the MCP server's results for calls that name no session.
NO_SESSION = "none"
#: The folders the sweep removes in, and nothing else.
SWEPT = (CACHE, SCRATCH, ADOPTION_PREVIEWS, INCORPORATION_PREVIEWS)


# ---- the build's index ------------------------------------------------------------------------------------------------


@dataclass
class BuildIndex:
    """What the build as it stands names, as `paths.BUILD_INDEX` holds it; every path relative to `.loom/cache/`.

    `fragments` is each fragment's input hash by its path in the site; `uses` what each was made from, a path or `@group`; `groups` what a group noted (`render.uses`); `beside` what the build read or wrote beside its fragments (the spans, the previews, marks found again, the diffs of stale acceptances it writes into the site); `site` every file the publish wrote or kept.
    """

    fragments: dict[str, str] = field(default_factory=dict)
    uses: dict[str, list[str]] = field(default_factory=dict)
    groups: dict[str, list[str]] = field(default_factory=dict)
    beside: list[str] = field(default_factory=list)
    site: list[str] = field(default_factory=list)


def read_index(root: Path) -> BuildIndex:
    """The build's index as the last build wrote it.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    BuildIndex
        Empty when there is none or it is not this loom's.
    """
    try:
        return _parse_index((root / BUILD_INDEX).read_bytes())
    except OSError:
        return BuildIndex()


def _parse_index(raw: bytes) -> BuildIndex:
    """An index from its bytes; empty when they are not this loom's."""
    try:
        data = json.loads(raw)
    except ValueError:
        return BuildIndex()
    if not isinstance(data, dict) or not isinstance(data.get("fragments"), dict):
        return BuildIndex()
    try:
        return BuildIndex(
            {str(k): str(v) for k, v in data["fragments"].items()},
            {str(k): [str(n) for n in v] for k, v in (data.get("uses") or {}).items()},
            {str(k): [str(n) for n in v] for k, v in (data.get("groups") or {}).items()},
            [str(n) for n in data.get("beside") or []],
            [str(n) for n in data.get("site") or []],
        )
    except (AttributeError, TypeError):
        return BuildIndex()


def write_index(root: Path, index: BuildIndex) -> str:
    """Write the build's index whole.

    Parameters
    ----------
    root : Path
        The quilt's root.
    index : BuildIndex
        What the build names.

    Returns
    -------
    str
        The digest of the bytes written, as `on_disk` reads it.
    """
    from loom.render.publish import write_atomic

    raw = json.dumps(
        {
            "fragments": index.fragments,
            "uses": index.uses,
            "groups": index.groups,
            "beside": index.beside,
            "site": index.site,
        },
        indent=0,
        sort_keys=True,
    ).encode("utf-8")
    write_atomic(root / BUILD_INDEX, raw)
    return _digest(raw)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def on_disk(root: Path) -> str:
    """The digest of the build's index as it is on disk now: what a sweep by hand passes as `index`, having no build of its own.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    str
        A SHA-256 in hex; '' when there is no index.
    """
    digest = hashlib.sha256()
    try:
        with (root / BUILD_INDEX).open("rb") as f:
            while piece := f.read(_PIECE):
                digest.update(piece)
    except OSError:
        return ""
    return digest.hexdigest()


def in_cache(root: Path, notes: Iterable[str]) -> list[str]:
    """`notes` as the index keeps them.

    Parameters
    ----------
    root : Path
        The quilt's root the notes' paths were made from.
    notes : iterable of str
        What `render.uses.noting` collected: paths, and groups as `@name`.

    Returns
    -------
    list of str
        Each path relative to `.loom/cache/` and each group as it is, sorted, once; a path outside the cache left out.
    """
    base = root / CACHE
    out: set[str] = set()
    for n in notes:
        if n.startswith("@"):
            out.add(n)
            continue
        with contextlib.suppress(ValueError):
            out.add(Path(n).relative_to(base).as_posix())
    return sorted(out)


class Named:
    """What the build's index names: `names`, every string the index holds, exactly; a file of the site is named by its path in the site, as the publish names it, or by its path in the cache.

    Every string is taken as a name: the paths are what the index holds, a group is written only while a fragment names it, and the hashes and group names besides name no file. A caller that lists what the cache holds and is not named takes each path relative to `.loom/cache/` and asks `in`.
    """

    def __init__(self, names: set[str]) -> None:
        self.names = names

    def __contains__(self, rel: object) -> bool:
        """Whether `rel`, a path relative to `.loom/cache/`, is named: by itself, or for a file of the site by its path in the site."""
        if not isinstance(rel, str):
            return False
        return rel in self.names or (rel.startswith("site/") and rel[5:] in self.names)


#: A string of the index as JSON writes it.
_STRING = re.compile(rb'"((?:[^"\\]|\\.)*)"')


def built(root: Path) -> Named:
    """What the build as it stands names under `.loom/cache/`: the index itself, the manifest, every file the publish wrote or kept, and every cache file or folder its fragments were made from or it read or wrote beside them.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    Named
        Membership by a path relative to `.loom/cache/`; naming nothing but the index and the manifest when there is no index.

    Notes
    -----
    The one reader of the build's index for what it names (`_read_named`): an index that changes its shape changes it, and nothing else in the sweep.
    """
    found = _read_named(root)
    return found[0] if found is not None else _read_named_from([])[0]


def _read_named(root: Path) -> tuple[Named, str, bool] | None:
    """The index on disk read once, a line at a time: what it names, the digest of its bytes (`on_disk`), and whether it is this loom's; None when there is none.

    Every string in it is taken as a name: the paths are what the index holds, a group is written only while a fragment names it, and the hashes and group names besides name no file. JSON written with an indent puts each string of a list or a key on a line of its own, so no line is long.
    """
    try:
        f = (root / BUILD_INDEX).open("rb")
    except OSError:
        return None
    with f:
        return _read_named_from(f)


def _read_named_from(lines: Iterable[bytes]) -> tuple[Named, str, bool]:
    names = {BUILD_INDEX.removeprefix(f"{CACHE}/"), "site/manifest.json"}
    digest = hashlib.sha256()
    ours = False
    for line in lines:
        digest.update(line)
        ours = ours or b'"fragments":' in line
        for m in _STRING.finditer(line):
            word = m.group(1)
            said = json.loads(b'"' + word + b'"') if b"\\" in word else word.decode("utf-8", errors="replace")
            names.add(said.removeprefix("@"))
    return Named(names), digest.hexdigest(), ours


# ---- removing ----------------------------------------------------------------------------------------------------------


@dataclass
class Swept:
    """What one sweep removed: files and links, the bytes they held, folders left empty; what it left because it changed since the sweep looked; removals that failed; and whether this system could remove at all (`CAN_REMOVE`)."""

    files: int = 0
    freed: int = 0
    folders: int = 0
    changed: int = 0
    failed: int = 0
    unable: bool = False

    def said(self) -> str:
        """One line for a log; '' when nothing was removed or failed."""
        if self.unable:
            return "removed nothing: this system cannot remove a file through an open folder"
        if not self.files and not self.failed:
            return ""
        out = f"removed {self.files} file{'s' if self.files != 1 else ''} ({readable(self.freed)})"
        return out + (f"; {self.failed} could not be removed" if self.failed else "")


#: Whether this system removes a file by its name in an open folder, opening each folder without following a link, which is the only way the sweep removes anything.
CAN_REMOVE = (
    {os.open, os.stat, os.unlink, os.rmdir} <= os.supports_dir_fd
    and os.stat in os.supports_follow_symlinks
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
)
_OPEN = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


@dataclass(frozen=True)
class Home:
    """A folder the sweep removes in, as `_own` found it: its resolved path, and its device and inode, which the folder opened at removal must still have."""

    path: Path
    dev: int
    ino: int


def _own(root: Path, rel: str) -> Home | None:
    """`root / rel`, resolved, when it is that folder itself: None when a link on the way leads anywhere else, or it is not a folder."""
    there = root / rel
    try:
        real = Path(os.path.realpath(there))
        if real != Path(os.path.realpath(root)) / rel or not there.is_dir() or there.is_symlink():
            return None
        st = os.stat(real, follow_symlinks=False)
    except OSError:
        return None
    return Home(real, st.st_dev, st.st_ino)


@dataclass(frozen=True)
class Doom:
    """One thing a sweep removes: its home, its path's parts below the home, and the inode and modification time the sweep saw, without which it is left."""

    home: Home
    parts: tuple[str, ...]
    ino: int
    mtime_ns: int
    folder: bool

    @property
    def path(self) -> Path:
        return self.home.path.joinpath(*self.parts)


def _remove_in(home: Home, dooms: list[Doom], swept: Swept) -> None:
    """Remove `dooms`, all in `home`, each by its name in its folder opened one component at a time from the home without following a link, so that a folder swapped for a link is never entered: one folder's chain is open at a time. What has changed since the sweep looked is left (`Swept.changed`); a folder on the way that is gone or became a link counts as failed."""
    try:
        top = os.open(home.path, _OPEN)
    except OSError:
        swept.failed += len(dooms)
        return
    chain: list[tuple[str, int]] = []
    try:
        st = os.fstat(top)
        if (st.st_dev, st.st_ino) != (home.dev, home.ino):
            swept.failed += len(dooms)
            return
        for doom in dooms:
            folders, name = doom.parts[:-1], doom.parts[-1]
            same = 0
            while same < min(len(chain), len(folders)) and chain[same][0] == folders[same]:
                same += 1
            while len(chain) > same:
                os.close(chain.pop()[1])
            try:
                for part in folders[same:]:
                    chain.append((part, os.open(part, _OPEN, dir_fd=chain[-1][1] if chain else top)))
            except OSError:
                swept.failed += 1
                continue
            _remove_one(chain[-1][1] if chain else top, name, doom, swept)
    finally:
        for _part, fd in chain:
            os.close(fd)
        os.close(top)


def _remove_one(at: int, name: str, doom: Doom, swept: Swept) -> None:
    """Remove `name` in the open folder `at` when it is still what the sweep saw: the same inode, and for a file the same modification time."""
    try:
        st = os.stat(name, dir_fd=at, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError:
        swept.failed += 1
        return
    is_dir = stat.S_ISDIR(st.st_mode)
    if st.st_ino != doom.ino or is_dir != doom.folder or (not is_dir and st.st_mtime_ns != doom.mtime_ns):
        swept.changed += 1
        return
    try:
        if is_dir:
            os.rmdir(name, dir_fd=at)
            swept.folders += 1
        else:
            os.unlink(name, dir_fd=at)
            swept.files += 1
            swept.freed += st.st_size
    except OSError as exc:
        if is_dir and exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
            swept.changed += 1
        else:
            swept.failed += 1


def _walk(folder: Path) -> Iterator[tuple[Path, os.stat_result, bool]]:
    """Every entry under `folder`, a folder after what it holds, each with its own `lstat`, taken before anything under it is removed, and whether it is a folder; no link is followed, `folder` itself included."""
    try:
        if folder.is_symlink():
            return
        entries = os.scandir(folder)
    except OSError:
        return
    # one entry at a time: a folder of the cache can hold a hundred thousand
    with entries:
        for entry in entries:
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            is_dir = stat.S_ISDIR(st.st_mode)
            if is_dir:
                yield from _walk(Path(entry.path))
            yield Path(entry.path), st, is_dir


# ---- the cache ---------------------------------------------------------------------------------------------------------


_CROP = re.compile(r"^([0-9a-f]{16})-p(\d+)-")
#: The folders loom writes into by name, relative to the cache, which stay when empty: a writer makes one and then writes in it.
_FOLDERS = (
    frozenset(
        within(CACHE, p)
        for p in (SITE, SITE_SVG, DRAFT_PREVIEWS, TEX, BLOCKS, SNIPPETS, BLOCK_PREVIEWS, BLOCK_SPANS, LIBRARY_CACHE)
    )
    | frozenset(
        within(CACHE, p)
        for p in (STORE_BOXES, RESOLVED, LIBRARY_SOURCES, LIBRARY_THUMBS, MARKS, MARK_BOXES, REFOUND, CROPS, CLOSURES)
    )
    | {
        "site/compare",
        "site/incorporation-review",
        "blocks/snippets/pictures",
    }
)


#: The node index's name, and the folder of unpacked sources, in `LIBRARY_CACHE`.
_NODE_INDEX = within(LIBRARY_CACHE, NODE_INDEX)
_SOURCES = within(LIBRARY_CACHE, LIBRARY_SOURCES)
_THUMBS = within(LIBRARY_CACHE, LIBRARY_THUMBS)


class _Rules:
    """What keeps a file under `.loom/cache/` that the build does not name: each folder's own rule of what it is still for."""

    def __init__(self, root: Path, result: Any, named: Named, now: float) -> None:
        self.root = root
        self.result = result
        self.named = named
        self.now = now
        self._documents: set[str] | None = None
        self._keys: set[str] | None = None
        self._marks: set[tuple[str, int]] | None = None
        self._answers: set[str] | None = None
        self._pictures: set[str] | None = None

    def keeps(self, rel: str, mtime: float) -> bool:
        """Whether the file at `rel`, relative to the cache and last written at `mtime`, stays."""
        if self.now - mtime < FRESH or self._is_named(rel):
            return True
        top, _, rest = rel.partition("/")
        first, _, name = rest.partition("/")
        if top == "site":
            return self._site(first, name, rest, mtime)
        if top == "tex":
            # one folder for each document in the quilt, and for each other TeX file of it `loom compile` was given
            return first in self.documents
        if top == "closures":
            # a key's closure document and its compile folder, while the key is in the quilt
            return first.removesuffix(".tex") in self.keys
        if top == "crops":
            # a crop of a mark's page, while an annotation is on that page of the copy it was written on
            m = _CROP.match(first)
            return m is not None and (m.group(1), int(m.group(2))) in self.marks
        if top == "library":
            work = PurePosixPath(name).parts[:2]
            if first == "boxes" and len(PurePosixPath(name).parts) > 2:
                # a stored work's word boxes, its source's among them, while the work's folder, `<scheme>/<id>`, is in the store
                return (self.root / STORAGE).joinpath(*work).is_dir()
            if first == _THUMBS:
                # a stored PDF's first page, while the store holds the PDF
                return (self.root / LIBRARY_DOCUMENTS / f"{PurePosixPath(name).stem}.pdf").is_file() if name else True
            if first == _SOURCES:
                # a stored source unpacked, while the store holds its tar
                return (
                    (self.root / LIBRARY_DOCUMENTS / f"{PurePosixPath(name).parts[0]}.tar").is_file() if name else True
                )
            if first in (_NODE_INDEX, f"{_NODE_INDEX}-journal"):
                # the index of the library's nodes, and its journal while a write to it is under way, while the library has nodes
                return (self.root / LIBRARY_NODES).is_dir()
            # an answer of a lookup, which loom can only ask again online, while an entry of the library asks it
            return first == "resolve" and name in self.answers
        # `blocks/`, `marks/` and anything else: named by the build or not at all
        return False

    def _is_named(self, rel: str) -> bool:
        """`rel` is named by the build, or, under `marks/`, where the build names a folder of word boxes whole, a folder holding it is."""
        if rel in self.named:
            return True
        p = rel
        while rel.startswith("marks/"):
            p, sep, _ = p.rpartition("/")
            if not sep:
                return False
            if p in self.named:
                return True
        return False

    def _site(self, first: str, name: str, rest: str, mtime: float) -> bool:
        if first == "svg":
            # a picture, while a page the site serves names it
            return name in self.pictures
        if first in ("compare", "draft-previews"):
            # made when a viewer asks, and touched each time its step names it again
            return self.now - mtime < ON_REQUEST
        if first == "incorporation-review":
            # the rendered sides of an incorporation's preview, while its saved preview waits to be applied
            return (self.root / INCORPORATION_PREVIEWS / f"{name.split('-', 1)[0]}.json").is_file()
        return False

    @property
    def documents(self) -> set[str]:
        if self._documents is None:
            files = [*self.result.masters, *(f for f in self.result.files if f.endswith(".tex"))]
            self._documents = {PurePosixPath(document_build(f)).name for f in files}
        return self._documents

    @property
    def keys(self) -> set[str]:
        if self._keys is None:
            from loom.tex.bundle import bundle_filename

            self._keys = {bundle_filename(k).removesuffix(".tex") for k in self.result.nodes}
        return self._keys

    @property
    def marks(self) -> set[tuple[str, int]]:
        """Each page of each copy of a PDF an annotation was written on: its hash's first sixteen digits, and the page."""
        if self._marks is None:
            self._marks = _marked_pages(self.root)
        return self._marks

    @property
    def answers(self) -> set[str]:
        if self._answers is None:
            from loom.refs.resolve import answer_names

            contact = self.result.quilt.config.contact
            self._answers = set()
            for entry in self.result.bib.values():
                with contextlib.suppress(Exception):
                    self._answers |= answer_names(entry, contact)
        return self._answers

    @property
    def pictures(self) -> set[str]:
        """Every picture under `site/svg/` that a page the site serves or keeps names."""
        if self._pictures is None:
            site = self.root / SITE
            self._pictures = set()
            for path, st, is_dir in _walk(site):
                if is_dir or path.suffix not in (".html", ".json"):
                    continue
                rel = path.relative_to(site).as_posix()
                first, _, name = rel.partition("/")
                if f"site/{rel}" in self.named or (
                    first in ("compare", "incorporation-review") and self._site(first, name, "", st.st_mtime)
                ):
                    _pictures_in(path, self._pictures)
        return self._pictures


_SVG = re.compile(rb"svg/([0-9a-f]{16}\.[A-Za-z0-9]+)")
#: How much of a page is read at once for the pictures it names, and how much of each piece is read again with the next, longer than any picture's name.
_PIECE, _OVERLAP = 1 << 16, 64


def _pictures_in(page: Path, into: set[str]) -> None:
    """Add to `into` each picture `page` names, reading it in pieces, so a page of any size costs one piece of memory."""
    try:
        with page.open("rb") as f:
            tail = b""
            while piece := f.read(_PIECE):
                into.update(m.decode("ascii") for m in _SVG.findall(tail + piece))
                tail = piece[-_OVERLAP:]
    except OSError:
        pass


def _marked_pages(root: Path) -> set[tuple[str, int]]:
    """Each page of each copy of a PDF an annotation in the log was written or moved onto, by its hash's first sixteen digits and the page, read a line at a time."""
    out: set[tuple[str, int]] = set()
    pages: dict[str, int] = {}
    try:
        log = (root / ANNOTATION_LOG).open(encoding="utf-8")
    except OSError:
        return out
    with log:
        for line in log:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            given = event.get("anchor")
            anchor: dict[str, Any] = given if isinstance(given, dict) else {}
            page = event.get("page") or anchor.get("page") or pages.get(str(event.get("id")))
            written = event.get("artifact") or anchor.get("sha256")
            if isinstance(page, int) and not isinstance(page, bool):
                pages.setdefault(str(event.get("id")), page)
                if isinstance(written, str) and written:
                    out.add((written[:16], page))
    return out


def _doomed(
    folder: Path, rel: str, goes: Callable[[str, os.stat_result, bool], bool]
) -> tuple[list[tuple[Path, os.stat_result]], bool]:
    """What under `folder` (at `rel` in its home) `goes` condemns, each with what the look saw of it, a folder after what it holds, and whether all of it goes; `goes` judges a folder only once all it holds goes, and no link is followed."""
    out: list[tuple[Path, os.stat_result]] = []
    whole = True
    try:
        if folder.is_symlink():
            return out, False
        entries = os.scandir(folder)
    except OSError:
        return out, False
    # one entry at a time: a folder of the cache can hold a hundred thousand
    with entries:
        for entry in entries:
            here = f"{rel}/{entry.name}" if rel else entry.name
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError:
                whole = False
                continue
            if stat.S_ISDIR(st.st_mode):
                under, all_of_it = _doomed(Path(entry.path), here, goes)
                out += under
                if all_of_it and goes(here, st, True):
                    out.append((Path(entry.path), st))
                else:
                    whole = False
            elif goes(here, st, False):
                out.append((Path(entry.path), st))
            else:
                whole = False
    return out, whole


@dataclass
class Doomed:
    """What a sweep will remove, in the order it goes, a folder after what it holds; `stale` when the cache was not looked at because the index on disk is not the build's own."""

    dooms: list[Doom] = field(default_factory=list)
    stale: bool = False

    @property
    def paths(self) -> list[tuple[Path, Path]]:
        """Each path that goes, with its home's."""
        return [(d.path, d.home.path) for d in self.dooms]

    def add(self, home: Home, found: Iterable[tuple[Path, os.stat_result]]) -> None:
        for path, st in found:
            parts = path.relative_to(home.path).parts
            self.dooms.append(Doom(home, parts, st.st_ino, st.st_mtime_ns, stat.S_ISDIR(st.st_mode)))

    def remove(self, swept: Swept | None = None) -> Swept:
        """Remove each through its open folder (`_remove_in`), a failure stopping nothing, adding to `swept` when given; on a system that cannot (`CAN_REMOVE`), nothing."""
        swept = Swept() if swept is None else swept
        if not CAN_REMOVE:
            swept.unable = True
            return swept
        start = 0
        while start < len(self.dooms):
            end = start
            while end < len(self.dooms) and self.dooms[end].home == self.dooms[start].home:
                end += 1
            _remove_in(self.dooms[start].home, self.dooms[start:end], swept)
            start = end
        return swept

    def parts(self, size: int = 1000) -> Iterator[Doomed]:
        """What goes in parts of `size`, in order, so that a caller holding a lock takes it for one part at a time."""
        for i in range(0, len(self.dooms), size):
            yield Doomed(self.dooms[i : i + size])


def _holds(home: Home | None, result: Any) -> bool:
    """Whether `home`, a folder the sweep removes in, is or holds the quilt's history, which the loader refuses (`scan.quilt.removed_in`) and the sweep keeps clear of whatever the loader did."""
    if home is None:
        return False
    history = Path(os.path.realpath(result.quilt.history_dir))
    return history == home.path or history.is_relative_to(home.path)


def _cache(root: Path, result: Any, built_index: str, now: float, doomed: Doomed) -> None:
    """Every file under `.loom/cache/` that neither the build as it stands nor its folder's rule keeps, then each folder that leaves empty but those loom writes into by name; nothing, and `doomed.stale`, when the index on disk is not `built_index`, the one the caller's build wrote."""
    home = _own(root, CACHE)
    found = _read_named(root)
    if found is None:
        # no build has said what it names, so nothing here is known to be unnamed
        return
    named, digest, ours = found
    if digest != built_index:
        # another build wrote the index since, at another state of the quilt or of some keys only: its own sweep follows it
        doomed.stale = True
        return
    if home is None or _holds(home, result) or not ours:
        return
    rules = _Rules(root, result, named, now)

    def goes(rel: str, st: os.stat_result, folder: bool) -> bool:
        if folder:
            return "/" in rel and rel not in _FOLDERS and now - st.st_mtime >= FRESH
        return not rules.keeps(rel, st.st_mtime)

    doomed.add(home, _doomed(home.path, "", goes)[0])


# ---- the scratch and the saved previews ---------------------------------------------------------------------------------


def _written_since(root: Path, session: str, since: float) -> bool:
    """Whether anything the session left was written after `since`: its files under `agents/sessions/<id>/`, its run log among them, and its scratch."""
    for rel in (f"{SESSIONS}/{session}", f"{SCRATCH}/{session}"):
        there = root / rel
        try:
            if there.lstat().st_mtime > since:
                return True
        except OSError:
            continue
        if any(st.st_mtime > since for _p, st, _d in _walk(there)):
            return True
    return False


def _scratch(root: Path, result: Any, now: float, doomed: Doomed) -> None:
    """Each session's scratch `KEEP_DAYS` after its session's last write, and each file of `none/` `KEEP_DAYS` after it was written, with the folders that leaves empty."""
    home = _own(root, SCRATCH)
    if home is None or _holds(home, result):
        return
    since = now - KEEP_DAYS * DAY
    try:
        entries = list(os.scandir(home.path))
    except OSError:
        return
    for entry in entries:
        path = Path(entry.path)
        if entry.name == NO_SESSION and entry.is_dir(follow_symlinks=False):
            doomed.add(home, _doomed(path, entry.name, lambda _rel, st, _folder: st.st_mtime <= since)[0])
            continue
        if _written_since(root, entry.name, since):
            continue
        try:
            itself = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        doomed.add(home, [*((p, st) for p, st, _d in _walk(path)), (path, itself)])


def _previews(root: Path, result: Any, now: float, doomed: Doomed) -> None:
    """Each saved preview of an adoption or an incorporation `KEEP_DAYS` after it was written; one applied is removed then (`drop_preview`)."""
    since = now - KEEP_DAYS * DAY
    for rel in (ADOPTION_PREVIEWS, INCORPORATION_PREVIEWS):
        home = _own(root, rel)
        if home is not None and not _holds(home, result):
            doomed.add(home, [(p, st) for p, st, is_dir in _walk(home.path) if not is_dir and st.st_mtime <= since])


def drop_preview(root: Path, rel: str, token: str) -> None:
    """Remove a saved preview that has been applied, through its open folder as the sweep removes.

    Parameters
    ----------
    root : Path
        The quilt's root.
    rel : str
        `paths.ADOPTION_PREVIEWS` or `paths.INCORPORATION_PREVIEWS`; anything else removes nothing.
    token : str
        The preview's token, 64 hex digits; anything else removes nothing.
    """
    home = _own(root, rel) if rel in (ADOPTION_PREVIEWS, INCORPORATION_PREVIEWS) else None
    if home is None or not re.fullmatch(r"[0-9a-f]{64}", token):
        return
    path = home.path / f"{token}.json"
    try:
        st = path.lstat()
    except OSError:
        return
    if stat.S_ISREG(st.st_mode):
        doomed = Doomed()
        doomed.add(home, [(path, st)])
        doomed.remove()


def condemn(root: Path, result: Any, *, index: str, now: float | None = None) -> Doomed:
    """What has outlived its use under `.loom/`, found and not yet removed: in the cache what the build as it stands does not name and no folder's rule keeps, each scratch whose session last wrote `KEEP_DAYS` ago, and each saved preview written as long ago.

    Parameters
    ----------
    root : Path
        The quilt's root.
    result : ScanResult
        The scan the last build that succeeded published from: what says which documents, keys and entries the quilt holds.
    index : str
        The digest of the index that build wrote (`BuildReport.index`, or `on_disk` for a sweep by hand): the cache is looked at only while it is the index on disk.
    now : float, optional
        The time to judge by, as `time.time()`; default now.

    Returns
    -------
    Doomed
        What to remove; `Doomed.remove` removes it.

    See Also
    --------
    sweep : finds and removes at once.

    Notes
    -----
    It only reads, so a server finds outside its publication lock and removes under it, only while no build has begun since (`render.serve`). A build in another process that wrote the index since makes the cache wait (`Doomed.stale`); one still running is kept safe by `FRESH` for its first hour, and no further.
    """
    now = time.time() if now is None else now
    doomed = Doomed()
    _cache(root, result, index, now, doomed)
    _scratch(root, result, now, doomed)
    _previews(root, result, now, doomed)
    return doomed


def sweep(root: Path, result: Any, *, index: str, now: float | None = None) -> Swept:
    """Find what has outlived its use under `.loom/` (`condemn`) and remove it: what `loom build` runs after a whole build that succeeded.

    Parameters
    ----------
    root : Path
        The quilt's root.
    result : ScanResult
        The scan the build published from.
    index : str
        The digest of the index the build wrote (`BuildReport.index`).
    now : float, optional
        The time to judge by, as `time.time()`; default now.

    Returns
    -------
    Swept
        What was removed, and how many removals failed.
    """
    return condemn(root, result, index=index, now=now).remove()


# ---- sizes, for loom doctor --------------------------------------------------------------------------------------------


def readable(n: float) -> str:
    """A size in the units a person reads.

    Parameters
    ----------
    n : float
        Bytes.

    Returns
    -------
    str
        `512 B`, `6.5 MB`, `68 MB`, `3.4 GB`: decimal units, one decimal below ten.
    """
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}" if n < 10 else f"{n:.0f} {unit}"
        n /= 1000
    return f"{n:.0f} TB"


def size_of(path: Path) -> int:
    """The bytes a file, or the files under a folder, hold.

    Parameters
    ----------
    path : Path
        A file or a folder; no link is followed, `path` itself included.

    Returns
    -------
    int
        Apparent sizes summed; 0 where there is nothing.
    """
    try:
        st = path.lstat()
    except OSError:
        return 0
    if not stat.S_ISDIR(st.st_mode):
        return st.st_size if stat.S_ISREG(st.st_mode) else 0
    return sum(st.st_size for _p, st, is_dir in _walk(path) if not is_dir)


@dataclass
class Scratch:
    """One session's scratch: its size, when its session last wrote, and when it is removed."""

    session: str
    size: int
    last: float

    @property
    def expires(self) -> float:
        return self.last + KEEP_DAYS * DAY


def sizes(root: Path) -> dict[str, int]:
    """What `.loom/` holds by kind, for `loom doctor`.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    dict of str to int
        Bytes by each of `paths.KINDS`, and the agents' scratch on its own under `paths.SCRATCH`.
    """
    out = {kind: size_of(root / kind) for kind in KINDS}
    out[SCRATCH] = size_of(root / SCRATCH)
    return out


def scratches(root: Path) -> list[Scratch]:
    """Each session's scratch, for `loom doctor`.

    Parameters
    ----------
    root : Path
        The quilt's root.

    Returns
    -------
    list of Scratch
        By session, `none/` left out: its size, and its session's last write.
    """
    out: list[Scratch] = []
    try:
        entries = sorted(os.scandir(root / SCRATCH), key=lambda e: e.name)
    except OSError:
        return out
    for entry in entries:
        if entry.name == NO_SESSION:
            continue
        size, last = 0, 0.0
        for rel in (f"{SESSIONS}/{entry.name}", f"{SCRATCH}/{entry.name}"):
            with contextlib.suppress(OSError):
                last = max(last, (root / rel).lstat().st_mtime)
            for _p, st, is_dir in _walk(root / rel):
                last = max(last, st.st_mtime)
                if rel.startswith(SCRATCH) and not is_dir:
                    size += st.st_size
        out.append(Scratch(entry.name, size, last))
    return out
