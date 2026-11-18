"""How long loom keeps each kind of thing under `.loom/`, and the sweep that removes what has outlived its use.

Records are never deleted by loom, and the library only when the person removes a work. What is derived, in `.loom/cache/`, is kept while the build as it stands names it (`built`, the one reader of the build's index) or while the folder's own rule says what it is still for (`_Rules`); the rest goes in the sweep that follows a build that succeeds. An agent's scratch goes `KEEP_DAYS` after its session's last write, and a saved preview `KEEP_DAYS` after it was written. Nothing written in the last `FRESH` seconds is removed, whatever names it, since whatever wrote it may not have named it yet: another process's build, or a step whose page a viewer is about to fetch.

Every removal is of a path resolved and shown to lie in one of `SWEPT`, never through a link; a failure to remove one file stops nothing.
"""

from __future__ import annotations

import contextlib
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
    MARK_BOXES,
    MARKS,
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

    `fragments` is each fragment's input hash by its path in the site; `uses` what each was made from, a path or `@group`; `groups` what a group noted (`render.uses`); `beside` what the build read beside its fragments (the spans, the previews, marks found again); `site` every file the publish wrote or kept.
    """

    fragments: dict[str, str] = field(default_factory=dict)
    uses: dict[str, list[str]] = field(default_factory=dict)
    groups: dict[str, list[str]] = field(default_factory=dict)
    beside: list[str] = field(default_factory=list)
    site: list[str] = field(default_factory=list)


def read_index(root: Path) -> BuildIndex:
    """The build's index as the last build wrote it; empty when there is none or it is not this loom's."""
    try:
        data = json.loads((root / BUILD_INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
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


def write_index(root: Path, index: BuildIndex) -> None:
    """Write the build's index whole."""
    from loom.render.publish import write_atomic

    write_atomic(
        root / BUILD_INDEX,
        json.dumps(
            {
                "fragments": index.fragments,
                "uses": index.uses,
                "groups": index.groups,
                "beside": index.beside,
                "site": index.site,
            },
            indent=0,
            sort_keys=True,
        ),
    )


def in_cache(root: Path, notes: Iterable[str]) -> list[str]:
    """`notes` (`render.uses`) as the index keeps them: each path relative to `.loom/cache/`, a group as it is, and a path outside the cache left out."""
    base = root / CACHE
    out: set[str] = set()
    for n in notes:
        if n.startswith("@"):
            out.add(n)
            continue
        with contextlib.suppress(ValueError):
            out.add(Path(n).relative_to(base).as_posix())
    return sorted(out)


def built(root: Path, index: BuildIndex | None = None) -> set[str]:
    """What the build as it stands names under `.loom/cache/`, relative to it: the index itself, the manifest and every file the publish wrote or kept, and every cache file or folder its fragments were made from or it read beside them.

    The one reader of the build's index for what it names: an index that changes its shape changes this, and nothing else in the sweep.
    """
    index = read_index(root) if index is None else index
    out = {BUILD_INDEX.removeprefix(f"{CACHE}/"), "site/manifest.json"}
    out.update(f"site/{rel}" for rel in index.site)
    groups: set[str] = set()
    for said in [*(index.uses.get(rel, []) for rel in index.fragments), index.beside]:
        for n in said:
            if n.startswith("@"):
                groups.add(n[1:])
            else:
                out.add(n)
    for g in groups:
        out.update(index.groups.get(g, []))
    return out


# ---- removing ----------------------------------------------------------------------------------------------------------


@dataclass
class Swept:
    """What one sweep removed: files and links, the bytes they held, folders left empty, and removals that failed."""

    files: int = 0
    freed: int = 0
    folders: int = 0
    failed: int = 0

    def said(self) -> str:
        """One line for a log; '' when nothing was removed or failed."""
        if not self.files and not self.failed:
            return ""
        out = f"removed {self.files} file{'s' if self.files != 1 else ''} ({readable(self.freed)})"
        return out + (f"; {self.failed} could not be removed" if self.failed else "")


def _own(root: Path, rel: str) -> Path | None:
    """`root / rel` resolved, when it is that folder itself: None when a link on the way leads anywhere else, or it is not a folder."""
    there = root / rel
    try:
        real = Path(os.path.realpath(there))
        if real != Path(os.path.realpath(root)) / rel or not there.is_dir() or there.is_symlink():
            return None
    except OSError:
        return None
    return real


def _remove(path: Path, home: Path, swept: Swept, real: dict[Path, Path] | None = None) -> None:
    """Remove the file, link or empty folder at `path`, once its folder is resolved and shown to lie in `home` (one of `SWEPT`, resolved by `_own`); a link is removed itself, never followed. `real` keeps each folder as resolved, for a caller removing many files in few folders."""
    try:
        real = {} if real is None else real
        if path.parent not in real:
            real[path.parent] = Path(os.path.realpath(path.parent))
        where = real[path.parent] / path.name
        if where == home or not where.is_relative_to(home):
            swept.failed += 1
            return
        st = where.lstat()
        if stat.S_ISDIR(st.st_mode):
            os.rmdir(where)
            swept.folders += 1
            return
        os.unlink(where)
        swept.files += 1
        swept.freed += st.st_size
    except OSError:
        swept.failed += 1


def _walk(folder: Path) -> Iterator[tuple[Path, os.stat_result, bool]]:
    """Every entry under `folder`, a folder after what it holds, each with its own `lstat`, taken before anything under it is removed, and whether it is a folder; no link is followed, `folder` itself included."""
    try:
        if folder.is_symlink():
            return
        entries = list(os.scandir(folder))
    except OSError:
        return
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
    | frozenset(within(CACHE, p) for p in (STORE_BOXES, RESOLVED, MARKS, MARK_BOXES, REFOUND, CROPS, CLOSURES))
    | {
        "site/compare",
        "site/incorporation-review",
        "blocks/snippets/pictures",
    }
)


class _Rules:
    """What keeps a file under `.loom/cache/` that the build does not name: each folder's own rule of what it is still for."""

    def __init__(self, root: Path, result: Any, named: set[str], now: float) -> None:
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
            if first == "boxes" and "/" in name:
                # a stored work's word boxes, while its folder is in the store
                return (self.root / STORAGE / PurePosixPath(name).parent).is_dir()
            # an answer of a lookup, which loom can only ask again online, while an entry of the library asks it
            return first == "resolve" and name in self.answers
        # `blocks/`, `marks/` and anything else: named by the build or not at all
        return False

    def _is_named(self, rel: str) -> bool:
        """`rel` or a folder holding it is named by the build."""
        p = rel
        while True:
            if p in self.named:
                return True
            p, sep, _ = p.rpartition("/")
            if not sep:
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
            from loom.records.annotations import load_records

            self._marks = set()
            for record in load_records(self.root)[0]:
                for a in record.annotations:
                    written = a.artifact or (a.anchor.sha256 if a.anchor else "")
                    page = a.page or (a.anchor.page if a.anchor else None)
                    if written and page:
                        self._marks.add((written[:16], int(page)))
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
            pages = [site / rel.removeprefix("site/") for rel in self.named if rel.startswith("site/")]
            for folder in ("compare", "incorporation-review"):
                for path, st, is_dir in _walk(site / folder):
                    if not is_dir and self._site(folder, path.name, "", st.st_mtime):
                        pages.append(path)
            self._pictures = set()
            for page in pages:
                if page.suffix not in (".html", ".json"):
                    continue
                with contextlib.suppress(OSError):
                    self._pictures.update(_SVG.findall(page.read_text(encoding="utf-8", errors="replace")))
        return self._pictures


_SVG = re.compile(r"svg/([0-9a-f]{16}\.[A-Za-z0-9]+)")


def _doomed(folder: Path, rel: str, goes: Callable[[str, os.stat_result, bool], bool]) -> tuple[list[Path], bool]:
    """What under `folder` (at `rel` in its home) `goes` condemns, a folder after what it holds, and whether all of it goes; `goes` judges a folder only once all it holds goes, and no link is followed."""
    out: list[Path] = []
    whole = True
    try:
        entries = [] if folder.is_symlink() else list(os.scandir(folder))
    except OSError:
        return out, False
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
                out.append(Path(entry.path))
            else:
                whole = False
        elif goes(here, st, False):
            out.append(Path(entry.path))
        else:
            whole = False
    return out, whole


@dataclass
class Doomed:
    """What a sweep will remove, each path with the folder of `SWEPT` it was shown to lie in, in the order it goes: a folder after what it holds."""

    paths: list[tuple[Path, Path]] = field(default_factory=list)

    def add(self, home: Path, paths: Iterable[Path]) -> None:
        self.paths += [(p, home) for p in paths]

    def remove(self, swept: Swept | None = None) -> Swept:
        """Remove each, a failure stopping nothing, adding to `swept` when given."""
        swept = Swept() if swept is None else swept
        real: dict[Path, Path] = {}
        for path, home in self.paths:
            _remove(path, home, swept, real)
        return swept

    def parts(self, size: int = 1000) -> Iterator[Doomed]:
        """What goes in parts of `size`, in order, so that a caller holding a lock takes it for one part at a time."""
        for i in range(0, len(self.paths), size):
            yield Doomed(self.paths[i : i + size])


def _holds(home: Path | None, result: Any) -> bool:
    """Whether `home`, a folder the sweep removes in, is or holds the quilt's history, which the loader refuses (`scan.quilt.removed_in`) and the sweep keeps clear of whatever the loader did."""
    if home is None:
        return False
    history = Path(os.path.realpath(result.quilt.history_dir))
    return history == home or history.is_relative_to(home)


def _cache(root: Path, result: Any, now: float, doomed: Doomed) -> None:
    """Every file under `.loom/cache/` that neither the build as it stands nor its folder's rule keeps, then each folder that leaves empty but those loom writes into by name."""
    home = _own(root, CACHE)
    index = read_index(root)
    if home is None or _holds(home, result) or not index.fragments and not index.site:
        # no build has said what it names, so nothing here is known to be unnamed
        return
    rules = _Rules(root, result, built(root, index), now)

    def goes(rel: str, st: os.stat_result, folder: bool) -> bool:
        if folder:
            return "/" in rel and rel not in _FOLDERS and now - st.st_mtime >= FRESH
        return not rules.keeps(rel, st.st_mtime)

    doomed.add(home, _doomed(home, "", goes)[0])


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
        entries = list(os.scandir(home))
    except OSError:
        return
    for entry in entries:
        path = Path(entry.path)
        if entry.name == NO_SESSION and entry.is_dir(follow_symlinks=False):
            doomed.add(home, _doomed(path, entry.name, lambda _rel, st, _folder: st.st_mtime <= since)[0])
            continue
        if _written_since(root, entry.name, since):
            continue
        doomed.add(home, [*(p for p, _st, _d in _walk(path)), path])


def _previews(root: Path, result: Any, now: float, doomed: Doomed) -> None:
    """Each saved preview of an adoption or an incorporation `KEEP_DAYS` after it was written; one applied is removed then (`drop_preview`)."""
    since = now - KEEP_DAYS * DAY
    for rel in (ADOPTION_PREVIEWS, INCORPORATION_PREVIEWS):
        home = _own(root, rel)
        if home is not None and not _holds(home, result):
            doomed.add(home, [p for p, st, is_dir in _walk(home) if not is_dir and st.st_mtime <= since])


def drop_preview(root: Path, rel: str, token: str) -> None:
    """Remove the saved preview `token` from `rel`, `ADOPTION_PREVIEWS` or `INCORPORATION_PREVIEWS`: it has been applied."""
    home = _own(root, rel) if rel in (ADOPTION_PREVIEWS, INCORPORATION_PREVIEWS) else None
    if home is not None and re.fullmatch(r"[0-9a-f]{64}", token) and (home / f"{token}.json").is_file():
        _remove(home / f"{token}.json", home, Swept())


def condemn(root: Path, result: Any, *, now: float | None = None) -> Doomed:
    """What has outlived its use under `.loom/`, found and not yet removed: in the cache what the build as it stands does not name and no folder's rule keeps, each scratch whose session last wrote `KEEP_DAYS` ago, and each saved preview written as long ago.

    Parameters
    ----------
    root : Path
        The quilt's root.
    result : ScanResult
        The scan the last build that succeeded published from: what says which documents, keys and entries the quilt holds.
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
    It only reads, so a server finds outside its publication lock and removes under it, only when no build ran in between (`render.serve`). A build in another process is kept safe by `FRESH`.
    """
    now = time.time() if now is None else now
    doomed = Doomed()
    _cache(root, result, now, doomed)
    _scratch(root, result, now, doomed)
    _previews(root, result, now, doomed)
    return doomed


def sweep(root: Path, result: Any, *, now: float | None = None) -> Swept:
    """Find what has outlived its use under `.loom/` (`condemn`) and remove it: what `loom build` runs after a whole build that succeeded.

    Parameters
    ----------
    root : Path
        The quilt's root.
    result : ScanResult
        The scan the build published from.
    now : float, optional
        The time to judge by, as `time.time()`; default now.

    Returns
    -------
    Swept
        What was removed, and how many removals failed.
    """
    return condemn(root, result, now=now).remove()


# ---- sizes, for loom doctor --------------------------------------------------------------------------------------------


def readable(n: float) -> str:
    """A size in the units a person reads: `512 B`, `6.5 MB`, `68 MB`, `3.4 GB`."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}" if n < 10 else f"{n:.0f} {unit}"
        n /= 1000
    return f"{n:.0f} TB"


def size_of(path: Path) -> int:
    """The bytes the file at `path`, or the files under it, hold, no link followed; 0 where there is nothing."""
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
    """The bytes each kind holds (`paths.KINDS`), and the agents' scratch on its own under `SCRATCH`."""
    out = {kind: size_of(root / kind) for kind in KINDS}
    out[SCRATCH] = size_of(root / SCRATCH)
    return out


def scratches(root: Path) -> list[Scratch]:
    """Each session's scratch but `none/`, with its size and its session's last write."""
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
