"""What is derived from what a scan reads, remembered while it is in use.

A served quilt scans every file again on every change, and most files have not changed, so their tokens and comment-blanked text are looked up by the text itself rather than made again, and a style a preamble loads by its path and mtime. A build does the same with what it makes from the scan (`built` memos): an agent copy's comparison, a section draft's rendering, a version's marks. A memo keeps what is in use and nothing older: each scan and each build is a `reading`, and when the outermost reading ends every memo forgets the entries not asked for since it began, a `built` memo only when that reading is a build's. An edited file's old text is let go by the build that reads the new one, so what a memo holds is bounded by the quilt as it is now, not by how many saves came before.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")

_lock = threading.Lock()
_memos: list[Memo] = []  # type: ignore[type-arg]
_generation = 0


@dataclass
class _Reading:
    """An open reading: the generation it began in, its own; the oldest it reaches back to, which an older reading that ended while it was open lowers; when it keeps, the generation from which what was made is its own to let go; and whether it is a build's."""

    began: int
    keep: bool
    reaches: int
    own_from: int
    build: bool = False


#: Every open reading, in every thread, by the generation it began in.
_open: dict[int, _Reading] = {}


class Memo(Generic[K, V]):
    """`make(key)`, made once for each key in use: a text, or what names a file as it now is.

    An entry is kept while it is asked for: one not asked for since the outermost reading began is forgotten when that reading ends, and one asked for outside any reading lives until the next reading ends. A `built` memo holds what a build makes from its scan, which a scan alone never asks for, so only a build's reading forgets from it.
    """

    def __init__(self, make: Callable[[K], V] | None = None, *, built: bool = False) -> None:
        self._make = make
        self.built = built
        # each key's value, the generation it was last asked for in, and the one it was made in
        self._entries: dict[K, tuple[V, int, int]] = {}
        with _lock:
            _memos.append(self)

    def __call__(self, key: K) -> V:
        assert self._make is not None, "a memo made without `make` is asked through `get`"
        make = self._make
        return self.get(key, lambda: make(key))

    def get(self, key: K, make: Callable[[], V], holds: Callable[[V], bool] | None = None) -> V:
        """`make()`, made once while `key` is in use: for a memo whose key names its inputs without holding them, a digest of a long text among them.

        `holds` says whether a value stands for its key in ways the key cannot name (what it was made from is still on disk; nothing it met was the machine's passing state): a value that does not hold is handed out and not kept, and a kept one that no longer holds is made again.
        """
        hit = self._entries.get(key)
        if hit is not None and (holds is None or holds(hit[0])):
            value, made = hit[0], hit[2]
        else:
            value, made = make(), _generation
            if holds is not None and not holds(value):
                self._entries.pop(key, None)
                return value
        self._entries[key] = (value, _generation, made)
        return value

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __iter__(self) -> Iterator[K]:
        return iter(list(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def _forget(self, ended: _Reading) -> None:
        for key, (_, used, made) in list(self._entries.items()):
            if (made >= ended.own_from) if ended.keep else (used < ended.reaches):
                self._entries.pop(key, None)


@contextmanager
def reading(keep: bool = False, build: bool = False) -> Iterator[None]:
    """Read the quilt inside this: when it ends with no older reading still open, every memo forgets what was not asked for since it began, or since the oldest reading it overlapped began; with `keep`, it forgets only what was made while it alone was open. A `built` memo forgets only at the end of a `build`'s reading, since a scan of its own, a request's, asks for nothing a build makes.

    A scan inside a build forgets nothing, so the build's rendering finds what the build before it derived. A reading that begins during another and outlives it (a request's scan during a rebuild) reaches back to the other's start, so it does not take what the other asked for with it. A keeping reading reads no file of the quilt's as it now is: a build from a scan it already holds, or a scan of a copy (a pinned version, a temporary directory); the quilt's own entries must outlive it, while what only it made (a temporary copy's texts and styles) is let go.
    """
    global _generation
    with _lock:
        _generation += 1
        this = _Reading(_generation, keep, _generation, _generation, build)
        _open[this.began] = this
    try:
        yield
    finally:
        with _lock:
            del _open[this.began]
            _generation += 1  # what is made from here on is told from what was made while this was open
            for other in _open.values():
                if other.began > this.began:
                    other.reaches = min(other.reaches, this.reaches)
                    other.own_from = _generation
            if all(other.began > this.began for other in _open.values()):
                for memo in _memos:
                    if this.build or not memo.built:
                        memo._forget(this)


def forget() -> None:
    """Every memo forgets all it holds: a forced build makes everything again, a text TeX refused before among it."""
    with _lock:
        memos = list(_memos)
    for memo in memos:
        memo.clear()
